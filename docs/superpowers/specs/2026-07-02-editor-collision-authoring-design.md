# Editor Collision Authoring — Chunks Carry Collision — design spec

**Date:** 2026-07-02
**Status:** Approved by user (design dialogue 2026-07-02; user-raised issue)
**Repos:** primarily **Aurora** (`/home/volence/sonic_hacks/aurora/`); aeon changes
are doc-only. Extends Aurora's own collision design lineage
(`aurora/docs/specs/2026-06-19..21-collision-*.md`) — this COMPLETES that work.
**Design-week queue:** #6 of 6

---

## 1. The problem (user-reported) & the verified root cause

Reused art drags collision where it isn't wanted. Verified state (2026-07-02
two-agent audit — one earlier claim corrected: the aeon pipeline **already
consumes editor collision authoritatively**; `.collattr.bin`/`.collattrb.bin` are
the ROM's collision, all-air-except-painted, baked via the S&K shape bank):

1. **Chunks (Aurora's stamps — the classic-chunk reuse unit) don't carry real
   collision.** `ChunkDef.collision` is a legacy 2-bit byte plane that flattens
   into the dead legacy `tileGrid.collision`; the real 16-bit collision-edit
   layer does not travel with stamps. Stamp art ⇒ no collision ⇒ hand-paint per
   placement.
2. **The collision paint tool's default propagates by art identity** ("block-
   content reuse" mode paints every 2×2-tile-matching cell in the section) — the
   exact "reuse adds collision to pieces we don't want" failure. The "just here"
   override exists but is the modifier (Alt), not the default.

In classic Sonic the chunk definition carries per-block-placement solidity, so
chunk reuse reproduces collision. Aurora's chunks take that role.

## 2. The design

### 2.1 Chunks carry real collision (both paths)
`ChunkDef` gains `collisionA` / `collisionB: Uint16Array` — one **16-bit cell
word** per 16-px cell (8×8 = 64 words per plane for a 16×16-tile chunk), the SAME
encoding as the section edit planes (`collision-cell-word.ts`: shape 9:0, xflip
10, yflip 11, solidity 13:12). The legacy `ChunkDef.collision` byte plane is
**deleted** (migration in §2.5).

### 2.2 Stamping writes collision atomically
The `stamp-chunk` handler writes the chunk's nametable AND its collision planes
into `section.tileGrid.nametable` + `collisionEdit`/`collisionEditB` in **one
undo step** (the existing `set-tiles` + `set-collision-edit` commands composed
into a single history entry). Stamp reuse now reproduces collision exactly —
classic chunk semantics. Stamped cells whose chunk word is air (0) CLEAR the
destination cell (the chunk is authoritative for its footprint; a "stamp art
only" modifier is available for overlay/decoration workflows).

### 2.3 Authoring collision on the chunk
The chunk composer (double-click → Art-mode document) gets the collision layer:
the existing Art-mode `'collision'` tool + `CollisionPalette` operate on the
chunk's `collisionA/B` planes with the same overlay rendering
(`drawCollisionOverlay`) and plane toggle. **Capture-from-map is symmetric**:
`save_chunk` / marquee-to-chunk captures the selection's collision-edit words
into the new chunk def alongside the art.

### 2.4 Paint-tool default flip
`paint-collision` targeting defaults to **"just here"** (brush area only);
art-identity propagation ("all matching block cells") becomes the explicit
modifier. Rationale: propagation is the surprise that caused this design; with
chunks carrying collision, the reuse-first workflow is stamping, not
propagation. The modifier remains for bulk-fixups.

### 2.5 Legacy retirement (clean, not bolted-on)
One migration pass deletes the three dead encodings: `tileGrid.collision`
(nibble plane) + its `.coll.bin` export, `ChunkDef.collision` (2-bit), and the
legacy `paint-collision` nibble path. Chunk import (`chunk-mappings.ts`) seeds
the new planes from block-ref solidity bits as full-block shapes tagged
approximate (`blockRefToCollision` upgraded); existing project chunk libraries
migrate on load (legacy byte → full-block word, logged). Aurora's stale
2026-06-20 doc claims ("generator ignores editor collision") get a status
banner.

### 2.6 Suite surface
New `editor/paint_collision` Aether method + MCP tool (cell rect + word value +
plane, routed through the `set-collision-edit` command = one undo step);
`save_chunk`/`stamp_chunk` tool schemas gain the collision payload. (Aurora only
serves the bus; no client work.)

## 3. What does NOT change

The aeon pipeline: **zero code changes** — `.collattr.bin`/`.collattrb.bin`
consumption, the S&K base bank, `bake_plane_cell`, the attr-set intern (13/255
used today, ~242 slots headroom), the dual-plane strips and runtime lookup all
stand. The daemon-watched files (`tools/ojz_strip_gen.py`,
`games/sonic4/data/editor/ojz/**`) are not edited by this design (Aurora WRITES
the editor tree at save-time as the user, exactly as today). Path-swapper
objects (`SST_layer` writers) stay deferred (DEFERRED_WORK §4.7).

## 4. aeon doc closeouts (riding along)

- `docs/DEFERRED_WORK.md:439-450` "Path-B collision content" is STALE (predates
  the S&K import + editor authoring): rewrite to current truth — path B is
  editor-authorable now; remaining = path-swapper objects + this design's
  stamp-carry.
- ARCH collision-pipeline section: state the live model (all-air + editor-
  authoritative overlay + S&K vocabulary) if not already current.

## 5. Verification

- **The user's scenario, end-to-end:** author a chunk with ground collision +
  decorative grass cells at solidity NONE → stamp it twice → full build
  (`SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`) → oracle: both placements
  collide identically; the decorative cells are passable at both.
- Stamp undo = one step (art + collision revert together); "art only" modifier
  leaves destination collision untouched.
- Capture-from-map round-trip: marquee → chunk → stamp elsewhere → identical
  words.
- Migration: vitest goldens — legacy chunk byte → expected word plane; project
  load migration idempotent.
- Path B: author differing B on a chunk, stamp, verify `.collattrb.bin` diff +
  in-game layer B via the collision probe.
- MCP: `paint_collision` + collision-carrying `stamp_chunk` exercised via the
  Aether surface.

## 6. Research provenance

2026-07-02 two-agent pass: Aurora facts sheet (ChunkDef/stamp flatten path,
the three collision encodings, collisionEdit planes + persistence, paint-target
modes, overlay/palette/MCP surfaces, the June design-doc lineage) and the aeon
collision-flow sheet (live all-air + editor-authoritative bake at
`ojz_strip_gen.py:1065-1120,1196-1241`, S&K vocabulary import, attr-set
headroom 13/255, daemon constraints, stale DEFERRED_WORK entry). Corrected
en route: "editor collision never reaches the ROM" was stale-doc folklore —
the live generator consumes it authoritatively.
