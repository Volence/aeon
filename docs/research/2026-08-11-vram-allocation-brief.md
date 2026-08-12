# VRAM allocation — problem brief and design direction ("the VRAM linker")

**Date:** 2026-08-11
**Status:** scoping brief, pre-design. User-initiated pivot: character work is
PAUSED while this is specced ("this is a really good and important time to
really spec and scope this all out and do it first").
**Trigger:** the dust-effect VRAM placement thrash (below) — three placement
recommendations in one day, each withdrawn or broken by a fact recorded nowhere.

---

## 1. The incident that forced this (evidence, while fresh)

Placing 28 tiles of dust art (16 resident + 12 DPLC) took three attempts:

1. **"Top of the FG pool, 28 tiles"** — withdrawn. The pool is page-quantised
   (`ensure(PAGE_FRAMES * ART_POOL_PAGE_TILES == POOL_TILE_CEILING)`, 64-tile
   pages), so 28 tiles costs 64. Discoverable only by reading the `ensure`.
2. **"BG region, 448 → 420"** — approved, then dead on measurement. The
   generated blob `bg_tiles.bin` is **exactly 448 tiles**; the cap is spent to
   the byte. The 468-510-tile editor tilesets that suggested headroom are
   PRE-dedup sources, not the shipped blob. Lowering the cap would have made
   `BG_Init`'s length clamp silently truncate background art.
3. **"FG pool, whole page (960 → 896)"** — implemented (aeon `8265772e`,
   sigil `10fe3ed2`), VRAM-correct, and then:
   - `POOL_TILE_CEILING` turned out to be a **RAM knob too**: it derives
     `PAGE_FRAMES`, which sizes `Page_Frames` (−8 B, both shapes) and the
     debug-only `Page_Audit_Scratch` (−2 B) — so debug RAM below it slid −2.
   - **126 pins moved** (all Work-RAM), **16 golden-ROM tests staled**, and the
     **replay gate desynced**: `REPLAY DESYNC` at `Logic_Tick 2`, actual hash
     `0x1D3B0C1E` vs expected `0x1D3B0C20` — low by exactly the −2 slide.
     Control run on the golden ROM (the exact pre-change baseline, same
     fixture, same recipe): **PASS**, `Replay_Done=$FF`. The desync is real
     and caused by the RAM shift, not by any behaviour change.
   - ROM **length** was unchanged in both shapes; every one of the 24 (plain) /
     1069 (debug) differing bytes was classified with zero residue.

The common factor across all three: **every budget constant has an
undocumented blast radius, and there is no map.** Each attempt required
archaeology (grep, measure, diff), and each dig missed one fact.

## 2. The structural problem, stated generally

- **VRAM has no allocation mechanism at any tier.** 2048 tiles are covered by
  hand-picked constants (`VRAM_*`, `POOL_TILE_CEILING`, `BG_TILE_CAPACITY`,
  plane/SAT/HScroll bases) plus `ensure` walls between *adjacent* pairs. There
  is no registry, no full-coverage check, no document of what is free. Today's
  genuinely free space (~4 tiles at 1020, ~3 after the appendage window) is
  knowable only by re-deriving the whole map by hand.
- **Every art-bearing addition renegotiates the address space by hand.** Dust
  needed it; every badnik, monitor, boss and effect will need it again. This is
  the "anytime anyone adds an object the whole game breaks" feeling, and it is
  accurate.
- **The verification net prices every moved byte.** Pins, goldens, frozen
  tables, replay fixtures. The net is doing its job (it caught a real latent
  bug today), and regeneration is one command per artifact — but undocumented
  blast radii turn cheap bookkeeping into incident response.

## 3. Two latent bugs found in the process (fix regardless of design)

1. **`PAGE_FRAMES` couples RAM layout to a VRAM budget.** Sizing the two RAM
   arrays by a fixed `PAGE_FRAMES_MAX` (15) and letting `PAGE_FRAMES` be the
   live count would make `POOL_TILE_CEILING` a genuinely VRAM-only knob, at a
   cost of 10 bytes of RAM slack. Every future pool resize then stops moving
   pins and stops perturbing the replay net.
2. **The replay hash contains a RAM pointer.** `Replay_Hash`'s own header
   demands every hashed field be address-free, yet the hashed window includes
   `interact` ($4E) — which `collision.emp:295` fills with the ADDRESS of the
   claiming solid (`move.w a3, interact_off()(a2)`). Any RAM-shifting parcel
   desyncs the net for zero behaviour change. It is the only pointer-typed
   field in the hashed spans and the prime suspect for the −2, but this is
   **not yet proven** — the proving step is a breakpoint at `Replay_Hash` on
   both builds and a diff of the hashed words. Fixing it (exclude the word, or
   hash a slot INDEX instead of an address) costs one fixture re-record and
   buys the property the hash map already claims to have.

## 4. The idea: build-time VRAM linking in sigil

**Do for VRAM what `map.toml` + the sigil chainer already did for ROM.** ROM
placement used to be an include-order manifest with hand anchors; it is now a
declared map consumed by the packer, and nobody hand-picks a ROM address. VRAM
is the same problem at 64KB scale, plus two wrinkles ROM does not have
(lifetimes and per-act variation) — which is where the novelty lives.

**Declare → solve → emit → verify → report:**

- **Declare.** Game and engine modules declare VRAM regions: name, size (tiles),
  alignment/quantisation (e.g. 64-tile pages), lifetime class
  (`boot` / `act` / `state(...)` / `streamed-window`), and coupling (a region
  whose base is baked into a VDP register write is declared as such). The
  declaration lives with the owner, like `pub data` does today.
- **Solve.** A deterministic build-time packer assigns tile bases. At N≈30
  regions, first-fit-decreasing with fixed anchors is sufficient — **the value
  is the contract, not the algorithm**, and building a clever solver for a
  30-item problem is a named anti-goal. Determinism rules (stable sort,
  declared tie-breaks) so identical inputs give identical layouts; optionally
  prefer-previous-assignment so small additions do not reshuffle the world.
- **Emit.** Assigned bases flow back as link-time constants through the
  machinery that already exists (link-imm / `extern`), replacing today's
  hand `VRAM_*` values. For VDP-register-coupled regions (planes, SAT,
  HScroll — all provably movable; the SAT was already hand-relocated once) the
  packer emits the register values too.
- **Verify.** Comptime/link-time: every tile 0..2047 is owned or explicitly
  free; overlap is a build error **unless** the two regions' lifetime classes
  are declared disjoint (see overlays); over-budget is a build error naming
  the requester and the occupants.
- **Report.** Every build emits a human-readable VRAM map (per shape, per act)
  and a budget report — the document that never existed, generated so it
  cannot rot.

**The two genuinely novel pieces:**

- **State overlays, verified.** Two regions may share an address range iff
  their declared lifetimes cannot coexist. This makes the classic trick SAFE:
  S3K shares the dust window with the drowning countdown by hand, and the cost
  is `air_left >= 12` guards sprinkled through every dust path plus documented
  glitches. Declared overlays give the same packing density with the collision
  checked at build time instead of guarded at runtime. (This is `ld`'s OVERLAY
  directive, transposed to VRAM and made state-aware.)
- **Per-act solving.** Acts differ (pool window size, BG budget, zone-specific
  objects). The packer can solve per act and park act-varying bases in the act
  descriptor, which the engine already threads everywhere. "Pack as much as
  possible" then means: per act, not one worst-case layout for the whole game.

**The elastic pool (user idea, 2026-08-11, adopted).** The FG art pool is
already a residency cache (§9.7) — but its SIZE is a guess (960), not a
measurement. Invert it: the pool becomes the one ELASTIC region. It declares a
per-act **measured floor** — the worst-case page-granular working set over all
reachable camera positions (pages touched by the viewport, not distinct tiles:
a 64-tile page is resident if any tile in it is visible), plus the prefetch
window (the lap-rate slot budget), plus famine headroom (the
pinned+transients>clamp arithmetic), plus teleport-destination bursts — and
then absorbs ALL remaining slack after every fixed-size region is placed.
Adding an art-bearing object then never renegotiates anything: it shrinks the
cache's slack silently until the measured floor, where the build fails naming
the act and the shortfall. Today's act needs 10 pages against 15, so ~5 pages
(~320 tiles) of real slack exist already with zero behaviour change; the
measured-floor mode is also what makes the mega-act tech demo feasible (a
seamless multi-zone act can never be fully resident, so its pool requirement
must be its working set, not its tileset). Costs to state: smaller cache
trades VRAM for DMA traffic and pop-in risk, and the floor is act- and
path-dependent, so this lives in T2's per-act solving with a conservative
reachability model.

**Prior art, honestly:** Dragon's Castle allocates effect VRAM with assembler
`rs` chains — build-time bump allocation, the primitive form (no lifetimes, no
verification, no map). SGDK has a RUNTIME allocator whose fragmentation pain is
documented by its own users (Tänzer's boss-explosion failures); the research
corpus is unanimous that runtime alloc/free of VRAM is the wrong model for this
hardware. `ld` overlays prove the declared-disjoint-lifetime concept at the
linker level. The full composition — declared lifetimes + state overlays +
per-act solving + emitted constants + full-coverage verification — has no known
precedent on this platform (research fan-out is verifying that claim).

## 5. Scope tiers

- **T0 — registry only, no sigil change.** One game-side module declares every
  region; all `VRAM_*` constants derive from it; a comptime full-coverage
  check accounts for all 2048 tiles; ordering is still by hand. Gets the map,
  the verification, and single-file discovery immediately. Pure `.emp`.
- **T1 — the packer.** sigil assigns bases from declarations, emits constants
  and the map artifact, and gains a lint: **no raw VRAM literal outside the
  registry** (the fence that prevents regression to hand-placement).
- **T2 — overlays + per-act solving + VDP-register emission.**
- **T3 — object art as pool pages.** The §9.7 pager grows pinned/permanent
  pages; a build tool packs object/effect art into pages per act and emits a
  manifest. Adding an art-bearing object becomes: add art + manifest entry.
  No constants, no negotiation. This is the ENGINE_ARCHITECTURE end-state
  ("unified VRAM art pool") that the hand windows currently bypass.

Costs to state plainly: any layout change re-captures goldens (accepted,
scripted, one command — the map diff explains every move); T1 puts a solver in
the build path, so its determinism rules are part of the byte-identity
contract; T3 is a real engine parcel with its own design cycle.

## 6. Disposition of in-flight work

- Dust **Task 1** (asset importer + generated data): complete, both reviews
  passed, zero ROM delta — **keeps**.
- Dust **Task 2** (`aeon 8265772e` + `sigil 10fe3ed2`): breaks the replay gate
  (proven, control-tested). Disposition pending user ruling: revert both (and
  place dust through the new system when it lands) vs keep + land the
  `PAGE_FRAMES_MAX` decouple on top. The dust spec/plan stay valid either way;
  only §4/VRAM sourcing re-lands through the registry.
- Dust Tasks 3-6, Knuckles Task 9-11: resume after this design (user ruling).

## 7. Research fan-out (dispatched 2026-08-11)

1. **Internal audit** — every VRAM consumer, load site, lifetime, and each
   budget constant's full blast radius; the complete 0..2047 map incl. free
   gaps; the raw-literal baseline for the future lint; the demo game's map.
2. **Reference survey** — how all nine local disassemblies express their VRAM
   maps; every observed time-multiplexed window and its guards/bugs; per-zone
   variation mechanisms; any build-time checking anywhere. Output doubles as
   the requirements set: what a declarative allocator must be able to express.
3. **Toolchain prior art** — ld MEMORY/OVERLAY semantics and map files, GBA/
   SNES/NeoGeo budget tooling, Tanglewood/Dragon's Castle build-time
   allocation, atlas-packing determinism, incremental-link stability, and the
   honest novelty assessment.

## 8. Rulings wanted from the user (ANSWERED 2026-08-11)

**Rulings received:** (1) spec T0-T2 as one design, implement T0+T1 first,
T2 when a consumer needs it, T3 stays a banked follow-on; (2) the packer lives
inside sigil's chainer; (3) both latent bugs land NOW as a prep parcel, with
the proving step first — and approving the `PAGE_FRAMES_MAX` decouple is also
the style ruling: capacity-vs-count separation is house-acceptable at 10 bytes
of slack for permanent pin stability. (4) resolved by (3).

Original questions kept below for the record.

1. Which tier ships first (T0 alone is a small parcel; T0+T1 is the real fix;
   my lean: spec T0-T2 as one design, implement T0+T1 first, bank T2/T3).
2. Home of the packer: inside sigil's existing chainer (my lean — placement is
   already its domain, and the map.toml precedent lives there) vs a standalone
   generator emitting `.emp`.
3. The two independent bug fixes (§3): land now vs fold into the design's
   first parcel. The hash fix needs one fixture re-record; the RAM decouple is
   10 bytes of slack against permanent pin stability.
4. Whether `PAGE_FRAMES_MAX`-style capacity-vs-count separation is acceptable
   house style (it trades exactness for layout stability — against the grain,
   but deliberately).
