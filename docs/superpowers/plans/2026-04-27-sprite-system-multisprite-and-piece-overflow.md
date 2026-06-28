# §1.2 Sprite System — Multi-Sprite Batching + Piece-Count Overflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the §1.2 deferred-work entry by adding multi-sprite batching (parent-only registration with sibling-walk in `Render_Sprites`) and per-object piece-count overflow prediction, plus a one-line truth correction to ENGINE_ARCHITECTURE.md.

**Architecture:** New SST byte `sprite_piece_count` populated by `Load_Object` and refreshed in `AnimateSprite` on `mapping_frame` change. `Render_Sprites` pre-checks `running_total + sprite_piece_count > 80` to skip whole objects intact. Multi-sprite parents flagged via `RF_MULTISPRITE` (render_flags bit 4); children's `Draw_Sprite` early-returns when their parent has the flag set, and `Render_Sprites` walks the sibling chain after emitting the parent's pieces, indexing parent's `mapping_frame` against each child's own mappings table (semantic C — shared frame index, per-child mapping data).

**Tech Stack:** AS Macro Assembler (asw), 68000 assembly, Exodus emulator with MCP for visual verification, `./build.sh` for ROM builds.

---

## Per-Step Research Discipline (project memory: feedback_research_in_plans)

**Every implementation step's first sub-task is a research pass.** The standard sweep:

1. **All 7 reference disassemblies** — S.C.E., Batman & Robin, Vectorman, Gunstar Heroes, Alien Soldier, Thunder Force IV, sonic_hack. Always check each — different tradeoffs, different lessons.
2. **Online sources** — plutiedev.com, md.railgun.works, Kabuto hardware notes, segaretro.org, SpritesMind forum, GitHub homebrew (Xeno Crisis, Tanglewood, Demons of Asteborg, Project MD, SGDK).
3. **Modern engine techniques** — sprite batching in Unity/Godot 2D, command buffers, ECS components, instanced rendering — anything that maps to 68K with a fixed-cost-per-frame budget.

Listed targets are starting points. Per memory `feedback_research_breadth`, follow the trail wherever it leads. Per memory `feedback_research_before_build`, always cross-reference findings against ENGINE_ARCHITECTURE.md as baseline — don't treat documented designs as from-scratch.

**Per-task output:** append a section to `docs/research/sprite-system-§1.2.md` summarizing findings + the recommendation that informs that task's implementation. If research changes the implementation, update the spec or this plan inline.

---

## Files in scope

**Create:**
- `docs/research/sprite-system-§1.2.md` — Living research doc, appended per task
- `objects/test_multipart.asm` — Multi-sprite test fixture (parent + 3 children)

**Modify:**
- `docs/ENGINE_ARCHITECTURE.md` — §1.2 + §3.5 link-chain doc correction
- `structs.asm` — `sprite_piece_count ds.b 1` at SST `$2D` (replaces existing pad)
- `constants.asm` — `RF_MULTISPRITE = 4`
- `engine/objects/load_object.asm` — Initial `sprite_piece_count` populate
- `engine/objects/animate.asm` — `sprite_piece_count` refresh on `mapping_frame` change
- `engine/objects/sprites.asm` — `Draw_Sprite` child-skip guard, `Render_Sprites` overflow pre-check + factored piece-emission subroutine + sibling walk
- `objects/test_parent.asm` (or wire test_multipart into test state) — test integration
- `test/object_test_state.asm` (or equivalent) — load test_multipart fixture
- `docs/DEFERRED_WORK.md` — mark §1.2 entry done

---

## Task 1: ENGINE_ARCHITECTURE.md link-chain doc correction

Smallest, lowest-risk change first. The architecture doc says "links never rebuilt during gameplay" but `Render_Sprites` rewrites them every piece. Pre-research already confirmed this is a wash on 68000 cycle counts; this task just makes the doc match the code.

**Files:**
- Create: `docs/research/sprite-system-§1.2.md`
- Modify: `docs/ENGINE_ARCHITECTURE.md` §1.2 + §3.5

- [ ] **Step 1: Research — verify the wash conclusion holds**

Re-confirm across 7 references that no engine actually achieves "links never rebuilt." Targets:
- S.C.E. `Render Sprites.asm` / `Draw Sprite.asm` (path: `/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/`)
- Batman & Robin sprite builder
- Vectorman, Gunstar Heroes, Alien Soldier, Thunder Force IV, sonic_hack BuildSprites equivalents

For each: does it write the link byte per piece, skip it via pre-init, or use some third pattern? Cycle-count the per-piece link-handling sequence on 68000 (`move.b Dn,(An)+` = 8c; `addq.l #1,An` = 8c; `addq.b #1,Dn` = 4c).

Online: plutiedev's SAT page, Kabuto's notes on sprite cache write-through. SpritesMind threads on "sprite link chain optimization."

Append findings to `docs/research/sprite-system-§1.2.md` under "Task 1 — Link-chain reality check." If any reference does achieve true "never-rebuilt" cheaper, stop and re-evaluate the spec before proceeding.

- [ ] **Step 2: Edit ENGINE_ARCHITECTURE.md §1.2**

Open `/home/volence/sonic_hacks/aeon/docs/ENGINE_ARCHITECTURE.md` and find the §1.2 paragraph beginning "**Link chain pre-initialization:**" (around line 827). Replace with:

```
**Link chain pre-initialization:** `Init_SpriteTable` runs at level load and fills the 80-entry sprite link chain: entry 0 links to 1, 1 to 2, ..., 79 to 0. During gameplay, `Render_Sprites` rewrites the link byte for each emitted piece (sequential 0,1,2,...) and patches the last rendered piece's link to 0 as the chain terminator. The pre-init is correctness insurance for the unused tail of the SAT; per-frame writes are the source of truth. ("Never rebuilt" is genuinely a wash on 68000 — `move.b Dn,(An)+` and `addq.l #1,An` both cost 8 cycles, so skipping the write doesn't save anything once you account for advancing the pointer.) Unused entries still get Y=0 (off-screen) via Init_SpriteTable; Render_Sprites then writes link=0 to the last emitted entry to halt the chain.
```

- [ ] **Step 3: Edit ENGINE_ARCHITECTURE.md §3.5**

Find the §3.5 bullet "Pre-initialized link chain (80 entries, set at level init, never rebuilt)" (around line 1616). Replace with:

```
- Pre-initialized link chain (80 entries, set at level init); per-frame Render_Sprites rewrites links for emitted pieces and patches the terminator after the last one (the "never rebuilt" optimization is a wash on 68000)
```

- [ ] **Step 4: Build to confirm no asm impact**

```bash
cd /home/volence/sonic_hacks/aeon && ./build.sh -pe
```

Expected: build succeeds (this was a doc-only change; a successful build proves nothing was accidentally modified in asm).

- [ ] **Step 5: Commit**

```bash
git add docs/ENGINE_ARCHITECTURE.md docs/research/sprite-system-§1.2.md
git commit -m "docs(§1.2): correct link-chain claim — never-rebuilt is a wash on 68000

Architecture doc claimed links are never rebuilt during gameplay, but
Render_Sprites overwrites them every piece. Research across 7 reference
disasms confirmed no engine actually achieves never-rebuilt because the
pointer-advance costs the same as the byte-write on 68000.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 2: Add `sprite_piece_count` SST field + `RF_MULTISPRITE` constant

Pure data layout change. No behavior change yet. Sets up the fields used by all later tasks.

**Files:**
- Modify: `structs.asm` (SST struct, replace pad at `$2D` with `sprite_piece_count`)
- Modify: `constants.asm` (add `RF_MULTISPRITE = 4`)

- [ ] **Step 1: Research — SST overflow-prediction field across references**

Targets:
- Batman & Robin — spec mentioned `sprite_link_count` at object offset `$18`. Find it. Confirm the field is per-object and used predictively.
- S.C.E. — does it have an equivalent piece-count cache? Search `_objstr.asm`, object SST definitions.
- Sonic 2 / sonic_hack — does the object structure have anything similar?
- Gunstar/Alien Soldier — bosses are heavily multi-piece; how do they handle SAT-cap pressure?
- Thunder Force IV — large ships. Same question.
- Vectorman — title character is mass-sprite; cache or runtime?

Online: SpritesMind threads on "sprite limit prediction", "SAT overflow", any Genesis homebrew that pre-computes piece counts.

Modern: ECS-style sprite count cached in the component, dirty flags on animation change.

Append to research doc under "Task 2 — Piece-count cache patterns." Settle: byte vs word storage; should we also cache children's piece counts even though they're unused on the multisprite path? (Spec says no — leave them unused.)

- [ ] **Step 2: Add `sprite_piece_count` field to SST struct**

Open `structs.asm`. Find the SST struct around line 65. Locate:

```asm
status          ds.b 1      ; $2C — player/object status bits (ST_* constants)
                ds.b 1      ; $2D — pad
anim_callback   ds.l 1      ; $2E — callback pointer for AF_CALLBACK animation event
```

Replace with:

```asm
status          ds.b 1      ; $2C — player/object status bits (ST_* constants)
sprite_piece_count ds.b 1   ; $2D — current frame's piece count (for overflow prediction)
anim_callback   ds.l 1      ; $2E — callback pointer for AF_CALLBACK animation event
```

- [ ] **Step 3: Add `RF_MULTISPRITE` constant**

Open `constants.asm`. Find the RF_* block around line 161:

```asm
RF_ONSCREEN             = 0         ; set by Draw_Sprite if visible
RF_XFLIP                = 1         ; horizontal flip
RF_YFLIP                = 2         ; vertical flip
RF_COORDMODE            = 3         ; 0 = world coords, 1 = screen coords
```

Add after the `RF_COORDMODE` line:

```asm
RF_MULTISPRITE          = 4         ; (parent only) batch render via sibling-chain walk
```

- [ ] **Step 4: Build to confirm SST_len assert holds**

```bash
cd /home/volence/sonic_hacks/aeon && ./build.sh -pe
```

Expected: build succeeds. The `if SST_len <> $50 ; error "SST struct is..."` guard at structs.asm line 98 verifies layout is unchanged.

- [ ] **Step 5: Commit**

```bash
git add structs.asm constants.asm docs/research/sprite-system-§1.2.md
git commit -m "feat(§1.2): add sprite_piece_count SST field + RF_MULTISPRITE flag

sprite_piece_count reuses the existing pad slot at SST_\$2D — no size
growth. RF_MULTISPRITE = render_flags bit 4 marks parents whose children
should render via batched sibling walk. No behavior change; populated
and consumed by subsequent tasks.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 3: `Load_Object` populates `sprite_piece_count`

When an object spawns, the field must be set before its first render. Initial value comes from the initial `mapping_frame`'s frame data first word.

**Files:**
- Modify: `engine/objects/load_object.asm`

- [ ] **Step 1: Research — initial-frame piece-count derivation**

How do reference engines derive initial piece count on spawn?
- S.C.E. `Load_Object` (or `LoadObjects`)
- Batman & Robin's spawn path — does it pre-compute or read on first render?
- Sonic 2 `SingleObjLoad` — does it touch mapping data at spawn?
- Gunstar/Alien Soldier — large multi-part bosses, how is initial state set?
- TF4 — same.
- Vectorman — same.

Look for: do they index the mapping table at spawn, or defer? Where do they read the piece-count word from?

Modern: dirty-flag patterns — pre-compute at write time, consume at read time.

Append to research doc under "Task 3 — Initial piece count on spawn."

- [ ] **Step 2: Read the current Load_Object to find the right insertion point**

Open `engine/objects/load_object.asm` and find the spawn path. Identify:
- Where `mappings` (SST `$10`) gets set from the data block.
- Where `mapping_frame` (SST `$1E`) gets set (typically zero or from data block).
- Where to insert the piece-count read — must be after both `mappings` and `mapping_frame` are set.

Note the path of the relevant code in the research doc for traceability.

- [ ] **Step 3: Add piece-count populate**

After the section that sets `mappings(a1)` and `mapping_frame(a1)`, add (using `a1` for the new SST per existing convention; adjust register if Load_Object uses a different SST register):

```asm
        ; --- Initial sprite_piece_count from initial frame ---
        movea.l SST_mappings(a1), a3   ; mapping table base
        moveq   #0, d0
        move.b  SST_mapping_frame(a1), d0  ; initial frame index
        add.w   d0, d0                 ; word offset
        move.w  (a3,d0.w), d0          ; offset to frame data
        move.w  (a3,d0.w), d0          ; first word = piece count
        move.b  d0, SST_sprite_piece_count(a1)
```

If `mappings` is null (e.g., for objects without sprite data), guard: `tst.l SST_mappings(a1); beq.s .skip_piece_count` around the block.

- [ ] **Step 4: Build**

```bash
cd /home/volence/sonic_hacks/aeon && ./build.sh -pe
```

Expected: build succeeds.

- [ ] **Step 5: Verify in Exodus via MCP**

User loads `s4.bin` in Exodus. Use Exodus MCP tools:

```
emulator_read_memory <SST_address> 80
```

Spawn one of the existing test objects (test_player or test_animated). Read its SST, confirm byte at offset `$2D` = expected piece count for its initial frame. Cross-check against the object's mapping table first word at the initial frame's offset.

- [ ] **Step 6: Commit**

```bash
git add engine/objects/load_object.asm docs/research/sprite-system-§1.2.md
git commit -m "feat(§1.2): Load_Object populates sprite_piece_count from initial frame

Reads first word of initial mapping_frame's frame data into the new SST
field. Sets a sane value before AnimateSprite first runs and before the
Render_Sprites overflow pre-check (added in Task 5) consumes it.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 4: `AnimateSprite` refreshes `sprite_piece_count` on frame change

When `mapping_frame` advances, recompute piece_count so the next render's overflow pre-check is accurate.

**Files:**
- Modify: `engine/objects/animate.asm`

- [ ] **Step 1: Research — frame-change side effects in animation systems**

How do reference engines detect/react to `mapping_frame` change?
- S.C.E. `AnimateSprite` — what does it do on frame change beyond updating the index?
- Sonic 2 / sonic_hack `AnimateSprite` — change detection via `prev_frame`?
- Batman & Robin — animation system frame transitions.
- Gunstar/Alien Soldier — multi-part animation frame propagation.
- TF4, Vectorman — same.

Look for the existing `prev_frame` / DPLC change-detection pattern (deferred bullet §3.9). The piece-count refresh should sit at the same site, since both react to the same frame-change condition.

Online: SpritesMind on animation systems, dirty-bit patterns.

Modern: command buffer flush on state change, dirty rectangle tracking.

Append to research doc under "Task 4 — Frame-change refresh site."

- [ ] **Step 2: Read current AnimateSprite to find frame-change site**

Open `engine/objects/animate.asm`. Find where `mapping_frame` is updated. Identify the site where `prev_frame` is/would be compared. Note in research doc.

- [ ] **Step 3: Add piece-count refresh on frame change**

At the site where `mapping_frame` is updated, after the new frame is written, compare against `prev_frame`. On change:

```asm
        ; --- Refresh sprite_piece_count if frame changed ---
        move.b  SST_mapping_frame(a0), d0
        cmp.b   SST_prev_frame(a0), d0
        beq.s   .frame_unchanged
        move.b  d0, SST_prev_frame(a0)
        movea.l SST_mappings(a0), a3
        moveq   #0, d1
        move.b  d0, d1
        add.w   d1, d1
        move.w  (a3,d1.w), d1
        move.w  (a3,d1.w), d1
        move.b  d1, SST_sprite_piece_count(a0)
.frame_unchanged:
```

Use the SST register the surrounding code uses (typically `a0`); adjust if different.

If `prev_frame` is already updated elsewhere for DPLC purposes, share the comparison rather than duplicate it. Document in the research doc which site is canonical.

- [ ] **Step 4: Build**

```bash
cd /home/volence/sonic_hacks/aeon && ./build.sh -pe
```

Expected: build succeeds.

- [ ] **Step 5: Verify in Exodus via MCP**

User loads `s4.bin`. Spawn `test_animated` (cycles through frames). Set a watchpoint or read SST `$2D` across frames:

```
emulator_step (advance one frame)
emulator_read_memory <test_animated_SST + 0x2D> 1
```

Confirm value changes when the animation advances to a frame with a different piece count. Cross-check against the mapping table.

- [ ] **Step 6: Commit**

```bash
git add engine/objects/animate.asm docs/research/sprite-system-§1.2.md
git commit -m "feat(§1.2): AnimateSprite refreshes sprite_piece_count on frame change

When mapping_frame advances and differs from prev_frame, re-read piece
count from new frame's data. Keeps the overflow pre-check field accurate
across animation. One indirect read + store, only on frame change.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 5: `Render_Sprites` total-piece overflow pre-check

Skip whole objects predictively when emitting them would exceed the 80-piece SAT cap.

**Files:**
- Modify: `engine/objects/sprites.asm`

- [ ] **Step 1: Research — predictive vs reactive overflow handling**

How do references handle the 80-sprite SAT cap?
- S.C.E. `Render Sprites.asm` — does it pre-check or react per-piece?
- Batman & Robin — `sprite_link_count` at `$18` was flagged for prediction. Does `BuildSprites` use it as a pre-check, or only as a counter?
- Sonic 2 — purely reactive (`cmpi.b #80,d5; bge`).
- Gunstar Heroes — bosses heavily multi-piece. Look at `BuildSprites` for any prediction.
- Alien Soldier — same.
- Thunder Force IV — already does link-order cycling for fairness; is overflow prediction in there too?
- Vectorman — title character pushes 80-piece cap regularly.

Online: SpritesMind on "sprite limit prediction", Kabuto on per-line dropout vs total-count overflow.

Modern: budget allocation systems, command-buffer overflow (where modern engines deal with similar caps).

Append to research doc under "Task 5 — Predictive overflow." Settle: where exactly should the pre-check live? Just-before-piece-loop is the obvious spot; confirm against research.

- [ ] **Step 2: Read current Render_Sprites to find pre-check insertion site**

Open `engine/objects/sprites.asm`. Locate the spot just after `move.w (a3)+, d4 ; piece count` (line ~204) and before the `btst #RF_COORDMODE` check (line ~209). The piece count is in `d4`, the running total is in `d5`.

- [ ] **Step 3: Insert the pre-check**

After the existing `move.w (a3)+, d4 ; d4 = piece count ; beq.w .next_object` (line ~204-205), add:

```asm
        ; --- Total-piece overflow pre-check ---
        move.w  d5, d0
        add.w   d4, d0
        cmpi.w  #MAX_VDP_SPRITES, d0
        bhi.w   .next_object               ; would exceed cap — skip this whole object
```

This skips the object intact (no torn pieces in SAT). The existing per-piece `cmpi.b #MAX_VDP_SPRITES, d5 ; dbeq d4, ...` defensive check stays as a fail-safe.

- [ ] **Step 4: Build**

```bash
cd /home/volence/sonic_hacks/aeon && ./build.sh -pe
```

Expected: build succeeds.

- [ ] **Step 5: Verify in Exodus — regression check**

Load `s4.bin`. Run any existing test scene where the total piece count is well under 80. Verify no behavior change — same screenshot as before. Use Exodus MCP:

```
emulator_screenshot before.png    (already captured pre-task)
emulator_screenshot after.png
```

Compare. Should be byte-identical.

- [ ] **Step 6: Commit**

```bash
git add engine/objects/sprites.asm docs/research/sprite-system-§1.2.md
git commit -m "feat(§1.2): Render_Sprites total-piece overflow pre-check

Before emitting an object's pieces, check running_total + piece_count
against MAX_VDP_SPRITES (80). Overflowing objects skip whole — never
half-rendered. Existing per-piece dbeq fail-safe retained.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 6: Factor `Render_Sprites` piece-emission into reusable subroutine

Refactor only — no behavior change. Sets up the sibling-walk in Task 8 to reuse the same emission code.

**Files:**
- Modify: `engine/objects/sprites.asm`

- [ ] **Step 1: Research — factoring patterns for SAT builder**

How do references organize the per-piece emission?
- S.C.E. `Render Sprites.asm` — is the piece loop factored or inlined?
- Sonic 2 `BuildSprites_Loop` — inlined four-flip-variant pattern (matches our current code).
- Batman & Robin — factored or inlined?
- Gunstar/Alien Soldier — given the volume of multi-piece work, do they factor?
- TF4, Vectorman — same.

Look for: subroutine boundary location, register-passing convention (which regs in / out / clobbered), JSR vs inline tradeoff.

Online: 68000 calling convention guidance from SGDK / md.railgun.works.

Modern: function-pointer dispatch tables, inline expansion in JIT — none directly applicable, but the principle of "factor when reused twice or more" guides the boundary.

Append to research doc under "Task 6 — Piece-emission factoring." Settle: register layout for inputs (a0, a3, a4, d2-d6, d7) and clobbers; whether to JSR or use a macro for inlining.

- [ ] **Step 2: Identify the four flip-variant blocks in current sprites.asm**

In `engine/objects/sprites.asm`, locate:
- `.pieces_unflipped` (line ~256) through `bra.w .next_object` (line ~291)
- `.pieces_xflip` (line ~294) through `bra.w .next_object` (line ~333)
- `.pieces_yflip` (line ~336) through `bra.w .next_object` (line ~377)
- `.pieces_xyflip` (line ~380) through `bra.w .next_object` (line ~426)

Each block has: dbf piece loop, 4-flip-specific tile/X/Y handling, `cmpi.b #MAX_VDP_SPRITES, d5 ; dbeq d4, .piece_loop_*`.

- [ ] **Step 3: Extract emission to subroutine `Emit_ObjectPieces`**

Define a new subroutine after `CellOffsets_XFlip` (around line 480), before `InsertSpriteMasks`. Convention as researched in Step 1:

```asm
; -----------------------------------------------
; Emit_ObjectPieces — emit one object's mapping pieces to SAT buffer
; In:  a0 = SST pointer (for render_flags lookup if reading flip)
;      a3 = pointer to first piece (after the piece-count word)
;      a4 = SAT buffer write pointer (advanced as we emit)
;      d2.w = screen X (already camera-adjusted)
;      d3.w = screen Y (already camera-adjusted)
;      d4.w = piece count - 1 (dbf-ready)
;      d5.w = running sprite total (in/out, incremented per piece)
;      d6.w = art_tile (palette/priority/tile base)
;      d7.b = flip variant (RF_XFLIP|RF_YFLIP bits, masked from render_flags)
; Out: a3, a4, d5 advanced; d4 clobbered
; Clobbers: d0, d1, a1, a6
; -----------------------------------------------
Emit_ObjectPieces:
        lea     CellOffsets_XFlip(pc), a1   ; flip-width lookup base
        ; dispatch on d7.b flip variant
        tst.b   d7
        beq.w   .pieces_unflipped
        cmpi.b  #1<<RF_XFLIP, d7
        beq.w   .pieces_xflip
        cmpi.b  #1<<RF_YFLIP, d7
        beq.w   .pieces_yflip
        ; fall through to xy-flip
```

Then move each of the four `.pieces_*` blocks (Step 2 list) into this subroutine. Replace the trailing `bra.w .next_object` with `rts` in each variant. Replace `(a0, ...)` flip-table references with `(a1, ...)`.

- [ ] **Step 4: Update Render_Sprites to call Emit_ObjectPieces**

In `Render_Sprites`, after the overflow pre-check (added in Task 5) and before the four-variant dispatch (now extracted), prepare the inputs and call:

```asm
        ; (after .have_pos block, after overflow pre-check)
        ; Already: d2/d3 = screen pos, d4 = piece count, d5 = running total, d6 = art_tile
        move.b  SST_render_flags(a0), d7
        andi.b  #(1<<RF_XFLIP)|(1<<RF_YFLIP), d7
        bsr.w   Emit_ObjectPieces
        bra.w   .next_object
```

Delete the four `.pieces_*` blocks from inside Render_Sprites (now in the subroutine).

- [ ] **Step 5: Build**

```bash
cd /home/volence/sonic_hacks/aeon && ./build.sh -pe
```

Expected: build succeeds.

- [ ] **Step 6: Verify in Exodus — refactor regression check**

Load `s4.bin`. Run the existing test scenes (test_player, test_animated, test_emitter, test_solid). Capture screenshots and compare against pre-refactor screenshots. Should be byte-identical — this is a pure refactor.

```
emulator_screenshot post_refactor.png
```

Diff against equivalent pre-refactor capture. Any difference = bug; investigate before proceeding.

- [ ] **Step 7: Commit**

```bash
git add engine/objects/sprites.asm docs/research/sprite-system-§1.2.md
git commit -m "refactor(§1.2): factor Render_Sprites piece emission to subroutine

Extracts the four flip-variant piece loops into Emit_ObjectPieces with
documented register convention. No behavior change. Sets up Task 8's
sibling walk to reuse the same emission code for multi-sprite children.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 7: Test fixture `test_multipart.asm` — baseline (no batching yet)

Build a multi-part test fixture that proves children render correctly via independent Draw_Sprite (current path) — establishes the baseline before flipping the multisprite flag.

**Files:**
- Create: `objects/test_multipart.asm`
- Modify: `test/object_test_state.asm` (or equivalent test loader) to spawn the fixture
- Modify: `main.asm` (if needed to include the new file)

- [ ] **Step 1: Research — multi-part fixture patterns**

How do references structure multi-part objects?
- S.C.E. — find a multi-part boss or compound object example. Note structure: parent code + child code(s), descriptor table format.
- Sonic 2 — Tails' tails (separate object), boss patterns.
- Batman & Robin — multi-part bosses.
- Gunstar/Alien Soldier — abundance of multi-part bosses; pick one for reference.
- TF4 — multi-part ships.
- Vectorman — title character compound.

Look at: how is the parent's per-frame routine structured? Where are children spawned (init vs ongoing)? How does the parent's code interact with `CreateChild_Complex` / sibling chain?

Look at our existing `objects/test_parent.asm` and `engine/objects/children.asm` (`CreateChild_Complex` is at line ~89). Confirm the descriptor format and the spawn API.

Append to research doc under "Task 7 — Multi-part fixture pattern."

- [ ] **Step 2: Read existing test_parent.asm and children.asm**

Open `objects/test_parent.asm` to see how it currently exercises the children system. Open `engine/objects/children.asm` and study `CreateChild_Complex` (line ~85-148) to understand the descriptor format expected.

- [ ] **Step 3: Create test_multipart.asm**

Create `objects/test_multipart.asm`:

```asm
; -----------------------------------------------
; test_multipart — parent + 3 child SSTs
; Baseline (Task 7): parent has RF_MULTISPRITE clear, children render via
; independent Draw_Sprite calls. Task 8 flips RF_MULTISPRITE on and proves
; the batched path produces identical visual output.
; -----------------------------------------------

TestMultipart_Init:
        ; Initial spawn: load child descriptor table
        lea     TestMultipart_ChildDesc(pc), a1
        bsr.w   CreateChild_Complex
        ; Advance to "running" routine
        addq.w  #2, SST_code_addr(a0)
        rts

TestMultipart_Run:
        bsr.w   AnimateSprite
        bsr.w   Draw_Sprite
        rts

; --- Child descriptor: 3 children offset around parent ---
; Format per CreateChild_Complex (see engine/objects/children.asm):
;   word: child code_addr
;   long: child setup_addr
;   long: child mappings (or 0 = inherit)
;   long: child anim_table (or 0)
;   long: child wait_addr (or 0)
;   word: x_offset_signed
;   word: y_offset_signed
;   word: x_velocity (8.8)
;   word: y_velocity
TestMultipart_ChildDesc:
        dc.w  3-1                              ; 3 children (dbf format)
        ; child 1: -24 left
        dc.w  objroutine(TestMultipart_Child)
        dc.l  0                                ; no setup
        dc.l  TestMultipart_ChildMappings_A
        dc.l  0
        dc.l  0
        dc.w  -24, 0
        dc.w  0, 0
        ; child 2: center, vertical offset
        dc.w  objroutine(TestMultipart_Child)
        dc.l  0
        dc.l  TestMultipart_ChildMappings_B
        dc.l  0
        dc.l  0
        dc.w  0, -16
        dc.w  0, 0
        ; child 3: +24 right
        dc.w  objroutine(TestMultipart_Child)
        dc.l  0
        dc.l  TestMultipart_ChildMappings_C
        dc.l  0
        dc.l  0
        dc.w  24, 0
        dc.w  0, 0

TestMultipart_Child:
        bsr.w   Draw_Sprite              ; Task 7 baseline: child draws independently
        rts

; --- Mappings tables (3 distinct shapes — boxes of varying size) ---
; Use existing test mappings if available; otherwise reuse one mapping
; with different art_tile bases via render-time art_tile differentiation.
TestMultipart_ChildMappings_A: dc.w 0   ; placeholder; populate in Step 4 from existing test mappings
TestMultipart_ChildMappings_B: dc.w 0
TestMultipart_ChildMappings_C: dc.w 0
```

Adjust the descriptor format to match the actual signature of `CreateChild_Complex` discovered in Step 2 — the above is a sketch based on the spec; Step 1 research must confirm.

- [ ] **Step 4: Wire mappings — reuse existing test mapping data**

Look at existing `objects/test_parent.asm` or `objects/test_animated.asm` for available mapping tables. Either:
- (a) Reuse the same mapping for all three children but offset their `art_tile` so each renders distinct content (simplest, validates batching).
- (b) Create three minimal mapping tables (one piece each) inside `test_multipart.asm`.

Pick one in research; choose (a) if existing test mappings are structured to allow it, else (b).

- [ ] **Step 5: Include test_multipart in build**

Open `main.asm`. Find the existing test object includes (around line 100-110, near `include "engine/objects/sprites.asm"`). Add:

```asm
        include "objects/test_multipart.asm"
```

- [ ] **Step 6: Spawn fixture in test state**

Open `test/object_test_state.asm` (or the active test state per `test.sh`). Add a spawn call for `TestMultipart_Init` near the existing spawn calls (e.g., after the `test_parent` or `test_animated` spawn). Set parent position somewhere visible on screen.

- [ ] **Step 7: Build**

```bash
cd /home/volence/sonic_hacks/aeon && ./build.sh -pe
```

Expected: build succeeds.

- [ ] **Step 8: Verify in Exodus**

User loads `s4.bin`. Confirm:
- Parent + 3 children visible at correct relative offsets.
- Children animate (or remain static — depends on what TestMultipart_ChildMappings provides).
- Sprite count = parent piece count + 3 × child piece count.

Use:
```
emulator_screenshot multipart_baseline.png
emulator_read_memory <Sprites_Rendered_addr> 2
```

Capture and save the baseline screenshot for Task 8 comparison.

- [ ] **Step 9: Commit**

```bash
git add objects/test_multipart.asm main.asm test/object_test_state.asm docs/research/sprite-system-§1.2.md
git commit -m "test(§1.2): test_multipart fixture — baseline parent + 3 children

Parent + 3 children spawned via CreateChild_Complex. RF_MULTISPRITE
deliberately clear for this baseline so children draw via independent
Draw_Sprite. Task 8 will flip the flag and prove batched path matches.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 8: `Draw_Sprite` child-skip guard + `Render_Sprites` sibling walk

The two halves must land together — landing the guard alone breaks rendering for any child of an `RF_MULTISPRITE` parent (children stop registering, but `Render_Sprites` doesn't yet walk the chain to render them).

**Files:**
- Modify: `engine/objects/sprites.asm`
- Modify: `objects/test_multipart.asm` (set `RF_MULTISPRITE` on parent at end)

- [ ] **Step 1: Research — compound/multi-sprite render patterns**

Deepest research task. How do references batch multi-part rendering?
- **S.C.E.** `Render Sprites.asm` — look for `BuildSprites_Compound`, `Render_Sprites_MultiDraw`, `Animate_MultiSprite`. Capture the exact loop structure: how parent dispatches, how children are walked, how parent's `mapping_frame` is used vs child's. (Path: `/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/`.)
- **Batman & Robin** — multi-part rendering pattern.
- **Vectorman** — title character is the reference for mass-sprite compound.
- **Gunstar Heroes** — multi-part bosses; this is Treasure's bread and butter.
- **Alien Soldier** — same; arguably the most multi-part-heavy game.
- **TF4** — multi-part ships and bosses.
- **sonic_hack** — Tails' tails (separate independent object — informs whether children call Draw_Sprite or not), boss multi-part rendering.

For each, capture: (a) does the parent register and walk children, or do children register with a backref? (b) is there a single `mapping_frame` driving children, or per-child? (c) where is the bounds check? (d) any per-child art_tile / flip differentiation?

Online: SpritesMind on "compound sprite", "multi-part boss", "parent child sprite". GitHub homebrew (Xeno Crisis, Tanglewood, etc.) for modern compound patterns.

Modern: ECS hierarchical components, scene graph traversal patterns, sprite atlasing where parent draws all children with one bind.

Append findings to research doc under "Task 8 — Sibling-walk implementation." Particular focus: does the spec's Approach 1 + semantic C still hold up after research, or should it shift?

If the research changes the design, **stop and update the spec** (`docs/superpowers/specs/2026-04-27-sprite-system-design.md`) before proceeding. Per project memory `feedback_research_before_build`, don't railroad past research findings.

- [ ] **Step 2: Add Draw_Sprite child-skip guard**

Open `engine/objects/sprites.asm`. At the very top of `Draw_Sprite` (line 50, just after the comment header), insert before the existing `tst.l SST_mappings(a0)` (line 52):

```asm
Draw_Sprite:
        ; --- Child-skip guard for multi-sprite parents ---
        move.w  SST_parent_ptr(a0), d0
        beq.s   .no_parent
        movea.w d0, a1
        btst    #RF_MULTISPRITE, SST_render_flags(a1)
        bne.w   .offscreen                  ; or just rts — reuse offscreen path
.no_parent:

        ; (existing) Check if object has mappings — skip if null
        tst.l   SST_mappings(a0)
        beq.s   .offscreen
        ...
```

Note: `.offscreen` already does `bclr #RF_ONSCREEN, SST_render_flags(a0); rts`, which is exactly the right behavior for skipped children — they're not on-screen as far as the band system is concerned.

- [ ] **Step 3: Add sibling walk in Render_Sprites**

In `engine/objects/sprites.asm` `Render_Sprites`, after the call to `Emit_ObjectPieces` for the parent (added in Task 6 Step 4), add the sibling walk before `bra.w .next_object`:

```asm
        ; --- After parent emission, check for multisprite ---
        btst    #RF_MULTISPRITE, SST_render_flags(a0)
        beq.w   .next_object                ; not multi — done

        ; Walk sibling chain
        movea.l a0, a2                      ; save parent for mapping_frame access
        move.w  SST_sibling_ptr(a0), d0
.sibling_loop:
        beq.w   .next_object                ; chain end
        movea.w d0, a0                      ; a0 = current child SST

        ; Read child's mappings + frame index from PARENT's mapping_frame
        movea.l SST_mappings(a0), a3
        tst.l   a3
        beq.s   .sibling_advance            ; child has no mappings, skip
        moveq   #0, d1
        move.b  SST_mapping_frame(a2), d1   ; PARENT's mapping_frame
        add.w   d1, d1
        move.w  (a3,d1.w), d1
        lea     (a3,d1.w), a3               ; a3 = frame data
        move.w  (a3)+, d4                   ; d4 = piece count for this child
        beq.s   .sibling_advance

        ; Just-in-time overflow check using read piece count
        move.w  d5, d0
        add.w   d4, d0
        cmpi.w  #MAX_VDP_SPRITES, d0
        bhi.s   .sibling_advance            ; this child overflows — skip just it

        ; Compute child screen position
        btst    #RF_COORDMODE, SST_render_flags(a0)
        bne.s   .child_screen_pos
        move.w  SST_x_pos(a0), d2
        sub.w   (Camera_X).w, d2
        move.w  SST_y_pos(a0), d3
        sub.w   (Camera_Y).w, d3
        bra.s   .child_have_pos
.child_screen_pos:
        move.w  SST_x_pos(a0), d2
        move.w  SST_y_pos(a0), d3
.child_have_pos:
        move.w  SST_art_tile(a0), d6
        subq.w  #1, d4                       ; dbf-ready
        move.b  SST_render_flags(a0), d7
        andi.b  #(1<<RF_XFLIP)|(1<<RF_YFLIP), d7
        bsr.w   Emit_ObjectPieces

.sibling_advance:
        move.w  SST_sibling_ptr(a0), d0
        bra.w   .sibling_loop
```

Restore `a0` to the parent before the next-object branch if any code after `bra.w .next_object` relies on it (it shouldn't — `.next_object` reloads from band list).

- [ ] **Step 4: Flip RF_MULTISPRITE on test_multipart parent**

Open `objects/test_multipart.asm`. In `TestMultipart_Init` (or the parent's data block, depending on Load_Object format), set the parent's `render_flags` to include `RF_MULTISPRITE`:

```asm
TestMultipart_Init:
        bset    #RF_MULTISPRITE, SST_render_flags(a0)
        lea     TestMultipart_ChildDesc(pc), a1
        bsr.w   CreateChild_Complex
        addq.w  #2, SST_code_addr(a0)
        rts
```

Also remove the `bsr.w Draw_Sprite` from `TestMultipart_Child` — children don't need the call (the guard would early-return anyway, but skipping the call entirely is cleaner). Or leave it to validate the guard works.

- [ ] **Step 5: Build**

```bash
cd /home/volence/sonic_hacks/aeon && ./build.sh -pe
```

Expected: build succeeds.

- [ ] **Step 6: Verify in Exodus — visual identity vs Task 7 baseline**

User loads `s4.bin`. Capture multipart screenshot:

```
emulator_screenshot multipart_batched.png
```

Diff against `multipart_baseline.png` from Task 7. Visual output should match (parent + 3 children in identical positions with identical art).

If any difference, debug:
- Read parent's SST: confirm `RF_MULTISPRITE` is set in render_flags.
- Read children's SSTs: confirm their `parent_ptr` points back to parent.
- Read `Sprites_Rendered`: confirm count = parent pieces + 3 × child pieces (same as baseline).
- Step `Render_Sprites` and observe the sibling walk path.

Read `Sprite_Bands` to confirm only the parent is registered (children's slots not present).

- [ ] **Step 7: Commit**

```bash
git add engine/objects/sprites.asm objects/test_multipart.asm docs/research/sprite-system-§1.2.md
git commit -m "feat(§1.2): multi-sprite batching — Draw_Sprite guard + sibling walk

Parent with RF_MULTISPRITE registers in priority band; children's
Draw_Sprite early-returns. Render_Sprites emits parent's pieces, then
walks SST_sibling_ptr chain, indexing parent's mapping_frame against
each child's mappings (semantic C). One bounds check covers the group.
Mid-chain overflow skips just the offending child.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 9: Stress test — overflow prediction integration

Push the engine past 80 total pieces and verify whole objects skip cleanly.

**Files:**
- Modify: `objects/test_stress_emitter.asm` (or create dedicated stress fixture)
- Modify: `test/object_test_state.asm` to spawn the stress scene
- Modify: `docs/DEFERRED_WORK.md` to mark §1.2 done

- [ ] **Step 1: Research — stress-test patterns for sprite overflow**

How do references stress-test the SAT cap?
- S.C.E. — any built-in stress fixtures? Test scenes?
- sonic_hack — historical stress patterns.
- Batman/Vectorman/Gunstar/Alien Soldier/TF4 — find scenes that push the cap (mass projectiles, particle bursts, debris).

Modern: load testing methodology, fault injection patterns.

Append to research doc under "Task 9 — Stress test design." Settle: how many objects of what size, spawned over what timeframe, observed how?

- [ ] **Step 2: Configure stress scene**

Open `objects/test_stress_emitter.asm` (existing fixture). Configure or extend it to spawn enough sprites to exceed 80 pieces total. Roughly:
- N multi-piece objects (e.g., 30 objects × 4 pieces = 120 pieces) — exceeds 80 cap.
- Mix sizes so some fit and some don't, validating predictive skip.

Add a counter to `Sprites_Rendered` observation: read it from RAM via Exodus MCP and confirm it never exceeds 80 — the pre-check should cap it at the largest count under 80.

- [ ] **Step 3: Spawn stress scene in test state**

Open `test/object_test_state.asm`. Add toggle (build-time flag or a test variant) that enables the stress scene instead of (or alongside) the existing fixtures.

- [ ] **Step 4: Build**

```bash
cd /home/volence/sonic_hacks/aeon && ./build.sh -pe
```

Expected: build succeeds.

- [ ] **Step 5: Verify overflow behavior in Exodus**

User loads `s4.bin` with the stress scene active.

Via MCP:
```
emulator_screenshot stress_overflow.png
emulator_read_memory <Sprites_Rendered_addr> 2
```

Confirm:
- `Sprites_Rendered` ≤ 80 (the per-frame cap is respected).
- Visible sprites are not torn — no half-rendered objects in the SAT.
- Hidden sprites are absent entirely (whole skip), not partial.

Read SAT directly via:
```
emulator_read_vram <VRAM_SPRITE_TABLE> 640
```

Confirm SAT entries ≤ 80 are populated; remaining entries show Y=0 from Init_SpriteTable (off-screen).

- [ ] **Step 6: Mark deferred-work entry done**

Open `docs/DEFERRED_WORK.md`. Find the "Sprite Rendering Pipeline (§1.2)" entry under "From §1 — Core VDP Pipeline" (around line 12). Strike-through the heading and add a "Done" entry at the bottom:

```markdown
### ~~Sprite Rendering Pipeline (§1.2)~~ — DONE 2026-04-27
**Completed in:** §1.2 sprite-system multisprite + piece-overflow plan
**What:** Multi-sprite batching (parent registers, sibling walk in Render_Sprites,
semantic C: shared mapping_frame, per-child mappings); sprite_piece_count SST
field populated by Load_Object + AnimateSprite; total-piece overflow pre-check
in Render_Sprites skips whole objects; ENGINE_ARCHITECTURE.md §1.2 + §3.5
link-chain doc corrected to match reality. RF_MULTISPRITE = render_flags bit 4.
**Test:** test_multipart fixture (parent + 3 children) renders identically with
RF_MULTISPRITE on vs off. Stress test verified Sprites_Rendered capped at ≤80
with no torn objects.
**See:** `docs/superpowers/specs/2026-04-27-sprite-system-design.md`,
`docs/superpowers/plans/2026-04-27-sprite-system-multisprite-and-piece-overflow.md`,
`docs/research/sprite-system-§1.2.md`.
```

- [ ] **Step 7: Commit**

```bash
git add objects/test_stress_emitter.asm test/object_test_state.asm docs/DEFERRED_WORK.md docs/research/sprite-system-§1.2.md
git commit -m "test(§1.2): stress-test overflow prediction; mark §1.2 done

Stress scene spawns >80 pieces of varying sizes. Confirmed Sprites_Rendered
caps at ≤80 with whole objects skipped (no torn SAT entries). DEFERRED_WORK
entry §1.2 closed.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 10: Merge to master

- [ ] **Step 1: Verify branch is clean**

```bash
cd /home/volence/sonic_hacks/aeon && git status && git log master..HEAD --oneline
```

Confirm: working tree clean, commits 1-9 visible.

- [ ] **Step 2: Merge to master**

Per project memory `feedback_git_and_docs`: each plan ends with merge to master.

```bash
git checkout master
git merge --no-ff <feature-branch> -m "Merge §1.2: sprite system — multisprite batching + piece-count overflow"
```

(Adjust if currently on master directly — in that case, no merge needed; commits already on master.)

- [ ] **Step 3: Final build sanity check**

```bash
./build.sh -pe
```

Expected: build succeeds on master.

---

## Self-Review

**Spec coverage:**
- Multi-sprite batching (Approach 1, semantic C): Tasks 6 (factor) + 8 (guard + sibling walk). ✓
- `sprite_piece_count` SST field: Task 2. ✓
- Load_Object populate: Task 3. ✓
- AnimateSprite refresh: Task 4. ✓
- Render_Sprites overflow pre-check: Task 5. ✓
- Doc fix to ENGINE_ARCHITECTURE.md §1.2 + §3.5: Task 1. ✓
- Test fixture: Task 7. ✓
- Stress test: Task 9. ✓
- DEFERRED_WORK.md update: Task 9 Step 6. ✓

**Placeholder scan:** No "TBD"/"TODO"/"add appropriate" patterns. Each step has the actual code or command. Task 7 calls out a "Step 1 research must confirm" point for the descriptor format — that's correct because the actual `CreateChild_Complex` signature must be read from the live source, not assumed. ✓

**Type/symbol consistency:**
- `sprite_piece_count` (Task 2 SST field) → `SST_sprite_piece_count` (Tasks 3, 4). Generated by `struct` directive. ✓
- `RF_MULTISPRITE = 4` (Task 2) → `btst #RF_MULTISPRITE, SST_render_flags(...)` (Tasks 8). ✓
- `Emit_ObjectPieces` (Task 6 new sub) → called from Render_Sprites parent path (Task 6) and child path (Task 8). ✓
- `MAX_VDP_SPRITES = 80` (existing in sprites.asm line 12) — used in pre-checks (Tasks 5, 8). ✓

No issues found.

---

## Closes

- DEFERRED_WORK.md "Sprite Rendering Pipeline (§1.2)" entry.
