# Editor Collision Authoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aurora chunks carry real dual-plane collision; stamping reproduces it atomically; paint defaults to "just here"; legacy collision encodings retired; suite tools updated. Fixes "reused art drags collision."

**Architecture:** Work is in the **Aurora repo** (`/home/volence/sonic_hacks/aurora/` — Electron/TS, vitest). G1: ChunkDef collision planes + migration + import upgrade. G2: stamp-carry (atomic undo) + capture-from-map. G3: chunk-composer collision editing + paint default flip. G4: legacy retirement + MCP/Aether tools + aeon doc closeouts + the end-to-end scenario. Spec: `aeon/docs/superpowers/specs/2026-07-02-editor-collision-authoring-design.md` (APPROVED).

**Standing rules:** research step first — Aurora file anchors below are from the 2026-07-02 audit and WILL drift. Test runner: `npm test` (vitest) in aurora; commit per green task on branch `feat/chunk-collision` in the **aurora** repo (aeon gets one doc commit). **Do NOT edit `aeon/tools/ojz_strip_gen.py` or anything under `aeon/games/sonic4/data/editor/ojz/**` — daemon-watched; this design needs zero aeon code changes.** The end-to-end verification (Task 8) builds the aeon ROM and uses oracle — read `aeon/CLAUDE.md` conventions before it.

---

### Task 1: Branch + model research

- [ ] **Step 1: Research.** Read (aurora repo): `src/core/model/s4-types.ts` (`ChunkDef`, `Section`, `createChunkDef`, `packNametableWord`), `src/core/collision/collision-cell-word.ts` (`packCollisionCell`/`unpackCollisionCell` — the 16-bit word), `src/core/collision/collision-paint.ts` (`collisionPaintTargets` modes), `src/core/editing/commands.ts` (`set-tiles`, `set-collision-edit`, the history/undo model), `src/renderer/components/MapViewport.tsx` stamp-chunk handler (~:748-794) + paint-collision handler (~:796+), `src/core/formats/chunk-mappings.ts` (`importChunks`, `blockRefToCollision`, `CHUNK_TILES=16`, `TILES_PER_BLOCK=2`), `src/core/formats/s4-collattr.ts`, `src/renderer/hooks/useProject.ts` save/load (~:145-341, ~:441-452), `docs/specs/2026-06-20-collision-authoring-v2-block-keyed-design.md` + `docs/plans/2026-06-21-collision-flags-authoring-plan.md` (the anticipated model — this plan completes them).
- [ ] **Step 2: Branch.** In aurora: `git checkout -b feat/chunk-collision`. Run `npm test` — record the green baseline count.

### Task 2: G1a — ChunkDef collision planes + migration

**Files (aurora):**
- Modify: `src/core/model/s4-types.ts` (ChunkDef fields + createChunkDef), the chunk-library JSON (de)serialization in `useProject.ts` (~:208-220)
- Test: `test/` sibling to existing model tests

- [ ] **Step 1: Write failing tests.** vitest: (a) `createChunkDef` yields `collisionA`/`collisionB` as `Uint16Array((w/2)*(h/2))` zero-filled; (b) chunk-library round-trip (serialize→parse) preserves both planes; (c) **legacy migration**: a stored chunk with the old `collision: Uint8Array` byte plane loads as: byte bit1 (solidTop) → word `{shape: FULL_BLOCK_SHAPE_ID, solidity: top}`, bit0 (solidAll) → `{FULL_BLOCK, all}`, 0 → air word 0; migration is idempotent (re-load of migrated = unchanged). Resolve `FULL_BLOCK_SHAPE_ID` from the S&K base bank (the all-16-heights shape — find its index via the adapter, don't hardcode blindly).
- [ ] **Step 2: Run tests — fail.** `npm test -- chunk` (or the file filter): new tests FAIL (fields absent).
- [ ] **Step 3: Implement.** Fields + ctor + (de)serialization + the load-time migration (legacy field consumed and deleted; log one migration line per chunk). Keep the legacy field readable for migration only — no writer.
- [ ] **Step 4: Tests green.** Full `npm test` — baseline + new all pass.
- [ ] **Step 5: Commit.** `feat(model): ChunkDef carries dual-plane 16-bit collision; legacy byte plane migrates on load`

### Task 3: G1b — chunk import seeds real collision

**Files (aurora):**
- Modify: `src/core/formats/chunk-mappings.ts` (`importChunks`, `blockRefToCollision` → `blockRefToCollisionWord`)
- Test: existing import tests extended

- [ ] **Step 1: Failing test.** Import fixture (existing test fixtures) → each imported chunk's `collisionA` has full-block words where the block-ref had solidTop/solidAll (correct solidity per bit), air elsewhere; `collisionB` mirrors A (sonic_hack import has no per-path split at this level — document in the test).
- [ ] **Step 2-4: Implement, green, commit.** `feat(import): chunk import seeds real collision words from block-ref solidity`

### Task 4: G2 — stamp carries collision atomically + capture-from-map

**Files (aurora):**
- Modify: `MapViewport.tsx` stamp-chunk handler, `src/core/editing/commands.ts` (composed command or extended `set-tiles` carrying collision-edit deltas), the marquee/save-chunk capture path (find it: the `save_chunk` MCP tool + whatever UI creates chunks from selections — `docFromChunk` inverse)
- Test: command-level tests (stamp → one history entry → undo restores BOTH planes + nametable)

- [ ] **Step 1: Research.** How the stamp handler builds its undo payload today (`{oldNt,newNt,oldColl,newColl}` per cell — note `oldColl` is the LEGACY plane; that field dies in Task 6); whether commands compose into one history entry (a batch/transaction primitive — if none exists, add one; check `history.ts`).
- [ ] **Step 2: Failing tests.** (a) stamping a chunk with collision writes the destination `collisionEdit`/`collisionEditB` cells (16px-aligned mapping: chunk cell (cx,cy) → section cell (originCx+cx, originCy+cy); assert the stamp origin snaps or errors on odd-tile origins — decide: SNAP to even tile, matching block alignment, documented); (b) air chunk cells CLEAR destination cells; (c) one undo restores nametable + both planes; (d) the "art only" modifier leaves collision untouched.
- [ ] **Step 3: Implement** stamp + the modifier + capture-from-map symmetric (marquee capture reads `collisionEdit`/`B` into the new chunk def).
- [ ] **Step 4-5: Green, commit.** `feat(map): stamps carry collision — atomic art+collision placement, symmetric capture`

### Task 5: G3 — chunk composer collision editing + paint default flip

**Files (aurora):**
- Modify: `src/renderer/state/artStore.ts` ('collision' tool targets chunk planes when the doc is a chunk), `docFromChunk`/doc-to-chunk writeback, `src/core/collision/collision-paint.ts` + `MapViewport.tsx` (default mode "just here", propagation = modifier), `MapToolOptions.tsx` (the modifier UI), overlay wiring for the composer
- Test: paint-target defaults; chunk-doc collision round-trip

- [ ] **Step 1: Research.** How the Art-mode collision tool resolves its target today (tile-doc space); how `docFromChunk` maps doc↔chunk and where writeback commits; the paint-target mode selection plumbing (tool options state → `collisionPaintTargets` args).
- [ ] **Step 2: Failing tests.** (a) `collisionPaintTargets` default = brush-area-only; propagation only with the explicit flag; (b) chunk-doc round trip: paint collision in the composer → chunk def planes updated → re-open shows it.
- [ ] **Step 3-4: Implement, green.** Composer gets the same `CollisionPalette` + overlay (reuse `drawCollisionOverlay` with the chunk planes as source); plane A/B toggle honored.
- [ ] **Step 5: Commit.** `feat(editor): chunk composer collision editing; paint defaults to just-here (propagate = modifier)`

### Task 6: G4a — legacy retirement

**Files (aurora):**
- Delete/modify: `tileGrid.collision` plane + `.coll.bin` export (`useProject.ts`, `s4-collision.ts`), the legacy nibble path in paint, `serializeCollision`, export `section_{i}.coll.bin` writes, all readers (grep `tileGrid.collision` + `.coll.bin`)
- Test: save path emits no `.coll.bin`; loading a project WITH old `.coll.bin` files ignores them cleanly

- [ ] **Step 1: Research.** Every consumer of the legacy plane (grep); confirm the aeon generator never reads `.coll.bin` (the audit says collision comes from `.collattr*` only — verify by grep in aeon tools, read-only).
- [ ] **Step 2: Implement + green.** Clean deletion, no dormant paths; loaders tolerate old files on disk (ignored + logged once). Add a status banner to `aurora/docs/specs/2026-06-20-collision-authoring-v2-block-keyed-design.md` + the 06-19/06-21 docs ("completed/superseded by 2026-07-02 chunk-collision design; the 'generator ignores editor collision' claim is stale").
- [ ] **Step 3: Commit.** `refactor(editor): legacy collision encodings retired — collattr planes are the single model`

### Task 7: G4b — MCP/Aether surface

**Files (aurora):**
- Modify: `src/main/mcp-server.ts`, `src/main/aether/{protocol,adapter}.ts`, `src/main/agent-bridge.ts`, `src/shared/agent-protocol.ts`, `docs/MCP.md`

- [ ] **Step 1: Research.** How `stamp_chunk`/`paint_region` route into commands (the bridge pattern); tool schema conventions.
- [ ] **Step 2: Implement.** `paint_collision` (rect + packed word + plane → one `set-collision-edit` history entry); `save_chunk`/`stamp_chunk` schemas gain/emit the collision payload. Update `docs/MCP.md`.
- [ ] **Step 3: Verify + commit.** Exercise via the MCP surface (the suite's own test harness or a manual JSON-RPC call — Aurora serves Streamable HTTP; the audit cites `~/.aurora/mcp.json` discovery). `feat(mcp): paint_collision tool; chunk tools carry collision`

### Task 8: End-to-end — the user's scenario + aeon doc closeouts

- [ ] **Step 1: The scenario (spec §5), full stack.** In Aurora: author a chunk (ground cells solid, grass cells solidity NONE) → stamp twice into a section → save (Aurora writes the editor tree as the user — normal operation, daemon commits it). In aeon: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` → oracle: walk both placements — identical collision, decorative cells passable at both; collision probe (`collision_pipeline.py --probe`) spot-checks the baked attr bytes. Path B variant: differing B plane on the chunk → probe layer B.
- [ ] **Step 2: aeon docs (aeon repo, doc-only commit).** Rewrite `docs/DEFERRED_WORK.md:439-450` (Path-B entry) to current truth (editor-authorable now; remaining = path-swapper objects); verify ARCH's collision-pipeline section states the live model (all-air + editor-authoritative + S&K vocabulary) — update if stale; queue-doc log. Commit in aeon: `docs: collision pipeline truth sync — editor authoring live, Path-B entry rewritten (design #6)`
- [ ] **Step 3: Merge** `feat/chunk-collision` → aurora master (aurora repo's convention — check its branch state first).

---

## Self-review (done at write time)

- **Spec coverage:** §2.1→T2-3; §2.2+capture→T4; §2.3-2.4→T5; §2.5→T2 (migration) + T6 (retirement); §2.6→T7; §4→T8; §5 verification→T4/T5 tests + T8.
- **Placeholders:** none — the two open choices (batch-command primitive if absent; stamp-origin snapping) are flagged decisions with criteria in T4.
- **Consistency:** `collisionA/collisionB`, `collisionEdit/collisionEditB`, `set-collision-edit`, `FULL_BLOCK_SHAPE_ID`, "just here"/propagate-modifier, `paint_collision` uniform. Daemon rule stated twice (header + T8) because T8 is where an agent would be tempted.
