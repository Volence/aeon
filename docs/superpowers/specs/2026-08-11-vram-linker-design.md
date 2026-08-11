# VRAM Linker — design spec (T0-T2)

**Date:** 2026-08-11
**Status:** for user review. The direction, tiers and packer home were ratified
in the design dialogue (rulings recorded in the brief §8); this document is the
design itself.
**Lineage:**
- Brief: `docs/research/2026-08-11-vram-allocation-brief.md` (problem, incident
  evidence, tiers, the elastic pool)
- Ground truth: `docs/research/2026-08-11-vram-linker-internal-audit.md` (the
  full 0..2047 occupancy map, per-constant blast radii, the raw-literal lint
  baseline)
- Requirements source: `docs/research/2026-08-11-vram-linker-reference-survey.md`
  (nine disassemblies; the observed lifetime/sharing taxonomy)
- Prior art: `docs/research/2026-08-11-vram-linker-toolchain-prior-art.md`
  (rgblink, TFLM, ld OVERLAY, the ten steals)
- Foundation: the prep parcel, SHIPPED — aeon `5129060c` + sigil `3d1c7f7e`
  (chain entry 96). The replay hash is layout-proof and `POOL_TILE_CEILING` is
  a genuinely VRAM-only knob. Without that parcel, this design's first landing
  would have desynced the regression net; with it, layout changes cost exactly
  one goldens re-capture.

---

## 1. Goal & ratified scope

Replace hand-placed VRAM constants with **declared regions, deterministic
build-time packing, emitted constants, full-coverage verification, and a
generated map** — the same move `map.toml` + the sigil chainer made for ROM
placement, extended with the two things VRAM has that ROM does not: lifetimes
and per-act variation.

Ratified tiers:

| Tier | What | When |
|---|---|---|
| **T0** | The registry: `vram.toml` + a generator emitting the constants module, the coverage checks, and the human map. No sigil change. | build now |
| **T1** | The packer moves into sigil's chainer: floating regions solved, constants emitted through the existing define plumbing, the no-raw-literal lint, map + diff artifacts per build. | build now |
| **T2** | State overlays with runtime ownership contracts, per-act solving, VDP-register emission, the elastic pool with measured floors. | specced here, built when a consumer needs it |
| T3 | Object art as pinned pool pages (the ARCH §9.7 end-state). | banked, separate design |

Anti-goals, explicit: **no runtime VRAM allocator** (SGDK's own issue tracker
documents the fragmentation → defrag-API spiral; Tänzer's shipped failure is
the case study), **no clever solver** (N≈30 regions; first-fit-decreasing plus
an exact fallback is provably sufficient at this scale — the value is the
contract, not the algorithm), and **no prefer-previous-layout tie-breaking**
for now (genuinely novel per the prior-art survey, but our churn does not need
it; ledgered).

## 2. The problem, in one paragraph

Placing 28 tiles of dust art took three attempts, each defeated by a fact
recorded nowhere: page quantisation, a budget spent to the byte, and a VRAM
constant that secretly sized RAM arrays. The audit generalises it: ~35 distinct
hand-placed addresses across two games, budget constants with undocumented
blast radii (the BG "448" lives in FOUR independent hand-copies), six VDP
register bytes encoding VRAM bases that nothing checks, a `-D` value with no
build-time drift net, and two games that agree on tile 992 by coincidence.
Every art-bearing addition renegotiates the address space by hand, and there is
no map. Meanwhile the reference survey found **zero build-time VRAM
verification in nine shipped-game disassemblies** — the entire genre coordinates
sharing by comment, guard, and luck. This is a solved problem class (linkers)
applied to an address space nobody applied it to.

## 3. Requirements (from observed usage, not invention)

The reference survey's taxonomy is the coverage bar — a declaration language
that cannot express these patterns will be bypassed, and bypass is regression:

1. **Named regions, symbolic-only references.** s2disasm proves full
   symbolization is achievable for a whole shipped game (638/654 sites).
2. **Lifetime scopes** — `boot` / `mode` / `act` / `state(...)` / `streamed`.
   Overlap is an error only between lifetimes that can coexist.
3. **Declared overlays.** s2's silent equal-valued constants
   (`Signpost = $0434 = Spikes`) become checked intent, and mid-state overlaps
   (S3K's dust/drowning window) enumerate their guard obligation.
4. **Streamed windows with declared peak**, verified against the actual art
   (`dplc_peak_tiles` already does this — ahead of all nine references; the
   registry adopts it as the norm).
5. **Arena regions** the packer reserves but does not subdivide (the FG pool,
   any future Vectorman-style budget streamer).
6. **Grouped blocks** whose relative offsets are baked into mappings (S2's
   HUD chain) — move only as a unit; derived sub-regions by offset arithmetic
   (`ring + 4`-style).
7. **Pinned regions** — VDP-register-coupled tables and anything whose base is
   baked into data.
8. **Replicated instances** — per-player window pairs, double-buffer pairs.
9. **Per-act parameterization** — one logical name, per-act physical base (T2).
10. **State-transition contracts** — the one documented VRAM bug in the corpus
    (S2's HTZ cloud DMA landing on Continue-screen art) is a *queued transfer
    outliving the state that owned its destination*. Build-time packing cannot
    prevent it; the overlay system's runtime half must (T2, §7.1).

## 4. Architecture

**Declare → solve → emit → verify → report.**

- **Authority:** `games/<game>/vram.toml`, the exact peer of `map.toml`. Each
  game owns its VRAM contract; engine-owned fixed regions (planes, SAT,
  HScroll) appear in every game's map as pinned entries whose values
  cross-check the engine constants (coverage without moving authority; T2's
  register emission may move authority later).
- **Solve:** pinned regions place themselves; floating regions are packed by
  first-fit-decreasing over free space, honoring alignment/quantisation and
  (T2) lifetime interference — TFLM's proven planner shape. Deterministic by
  documented sort key: size descending, then declaration order. If greedy
  reports no-fit, an exact search (trivial at N<100) runs before the build
  fails, so "over budget" is a fact, not a heuristic artifact.
- **Emit:** solved bases flow back as the constants the code already consumes,
  through the existing define/link-immediate plumbing (`emp_defines` /
  `extern`). Consumers keep their local `ensure`s as independent cross-checks
  (the `RING_WIDTH` pattern): the data-owning module still asserts its peak
  fits its window, so a wrong emit is loud on both sides.
- **Verify:** every tile 0..2047 is owned or explicitly free; overlap between
  coexisting lifetimes is a build error; over-budget errors are byte-precise
  and name the occupants (`ld65` style: "region DustPuff (16 tiles) does not
  fit: free runs are [1020..1023], [1501..1503], [1532..1535]").
- **Report:** every build emits the human map (per game, per shape; per act in
  T2), an `ld --print-memory-usage`-style budget summary, a cross-reference
  table (which modules consume each region), and a **diff against the previous
  committed map** — the SuperSize lesson: the diff is the review artifact, and
  it becomes part of the refreeze evidence for any layout-moving parcel.

### 4.1 The declaration schema

```toml
# games/sonic4/vram.toml — the declared VRAM placement contract.
# Sizes in tiles. Order is not placement; the solver places.

[[region]]
name = "fg_art_pool"
owner = "engine.level.page_cache"
kind = "arena"                  # reserved, internally managed (page cache)
tiles = 896                     # T0/T1: a declared choice. T2: elastic (§7.4)
base = 0                        # pinned: level art must start at tile 0
quantum = 64                    # ART_POOL_PAGE_TILES — size must be a multiple
lifetime = "act"

[[region]]
name = "dust_puff"
owner = "games.sonic4.dust_puff"
kind = "window"                 # resident block, addressed from its base
tiles = 16
lifetime = "act"                # floating: the solver places it

[[region]]
name = "dust_spindash"
owner = "games.sonic4.dust_spindash"
kind = "window"                 # DPLC target; peak checked by the owner's ensure
tiles = 12
lifetime = "act"

[[region]]
name = "character_window"
owner = "games.sonic4.player"
kind = "window"
tiles = 32
base = 960                      # PINNED, deliberately — the base is baked into
lifetime = "act"                # the player's art_tile word, which the replay
                                # hash covers, so MOVING it re-stamps both
                                # fixtures. GROWING it is not moving it: a
                                # bigger cast peak (Hyper forms etc.) raises
                                # `tiles` with the base held, art_tile is
                                # unchanged, and the floating neighbors above
                                # re-solve for free. Grow in place; relocate
                                # only as a deliberate parcel.

[[region]]
name = "sprite_table"
owner = "engine.system.buffers"
kind = "table"
tiles = 20
base = 1472                     # pinned: VDP register $05 encodes this base
lifetime = "boot"
register = "vdp:0x05"           # T2: the encoder emits the register byte

[[region]]
name = "window_plane"
owner = "engine.system.boot"
kind = "plane"
tiles = 128
base = 1920
lifetime = "boot"
overlay_with = ["plane_b"]      # DECLARED overlap: the window plane is
register = "vdp:0x03"           # disabled (regs $11/$12 = 0) and deliberately
                                # aliases Plane B — today's map already
                                # contains one overlay; it just isn't declared
```

Fields: `name`, `owner`, `kind` (`window` / `table` / `plane` / `arena`),
`tiles` (+ optional `quantum`), optional `base` (pinned) — absent means
floating, `lifetime`, optional `overlay_with` (T2 checks state-disjointness;
T0/T1 accepts only provably-static cases like `window_plane`), optional
`register` (T2), optional `group` (moves as a unit), optional `per_act` (T2),
and `instances = 2` for replicated pairs. The demo game gets its own ~6-line
`games/demo/vram.toml` — the two games stop agreeing on tile 992 by
coincidence and start agreeing or differing on purpose.

## 5. T0 — the registry (generator, no sigil change)

A deterministic generator, `tools/gen_vram_map.py` (the `ojz_strip_gen`
conventions: no timestamps, byte-identical reruns), consumes `vram.toml` and
emits:

1. **`games/<game>/config/vram_map.emp`** — the constants module (every
   `VRAM_*` value, plus derived walls), carrying comptime `ensure`s for full
   coverage, non-overlap, and quantum fit. Consumers repoint their imports
   here module-by-module; `POOL_TILE_CEILING` stays engine-owned but gains an
   `ensure` against the map's `fg_art_pool.tiles`.
2. **`tools/vram_map.py`** — the Python-side mirror, importable by
   `inject_editor_bg.py`, `ojz_strip_gen.py`, `png_to_bg_override.py`. **This
   kills the four-copies-of-448 problem**: the tools import the value instead
   of restating it, and the generator is the one place it lives.
3. **`docs/generated/vram-map-<game>.md`** — the human map: the occupancy
   table, free runs, per-region provenance, the cross-reference list. The
   document that never existed, generated so it cannot rot.

T0 placement is hand-carried (`base` on every entry, exactly today's values —
except see §8) — the generator *verifies*; it does not yet *solve*. Acceptance
gate: **byte-identical goldens** when declaring today's map (a pure refactor),
then one deliberate change (§8) with its ritual.

Known seams accepted at T0, closed at T1: `VRAM_RING_PLACEHOLDER` is a
sigil-side `-D` with no `.emp` authority — T0 documents it in the map and adds
a `build.sh`-side check script; T1 makes the chainer feed the define from the
map, deleting the copy. The six `boot_data.emp` register-byte literals are
exempted from coverage complaints at T0 (annotated in the map as
"register-coupled, unchecked") and become emitted values at T2.

## 6. T1 — the packer in sigil's chainer

The chainer (already the ROM placement authority, already the `-D` plumbing
owner) takes over:

1. **Reads `games/<game>/vram.toml`** next to `map.toml`.
2. **Solves floating regions** (FFD + exact fallback, documented sort key).
   Acceptance test: given T0's fully-pinned map, the solver in verify-mode
   reproduces it; given the same map with dust unpinned, it places dust into
   the identical bases (a fixpoint gate, like R2's order validation).
3. **Emits** the solved values through `emp_defines` — `vram_map.emp` becomes
   generated-with-extern-values rather than generated-with-literals, and the
   ring-placeholder `-D` is fed from the map (one authority).
4. **Lints**: no raw VRAM literal outside the registry. The audit's baseline
   is clean (every `vram_art`/`vram_bytes` call site already passes a named
   constant), so the lint's job is keeping it that way. Scope guard: the Z80
   bank window's `$8000`s are a different address space — the lint keys on
   `vram_art`/`vram_bytes` arguments and VDP-command construction, not bare
   hex.
5. **Artifacts**: the map, the budget summary, and the **map diff vs the
   committed previous map** land in the goldens directory; `refreeze` picks
   the diff up as part of the freeze evidence, so every layout change ships
   with its explanation.

### Sigil asks (T1) — enumerated for the sigil-side plan

- S-1: `vram.toml` schema + parser in the harness (peer of the map.toml one).
- S-2: the solver (FFD + lifetime interference stub + exact fallback) with the
  fixpoint acceptance test.
- S-3: define emission — VRAM names join `emp_defines`, replacing the
  hand-typed ring placeholder values in `native.rs` (all profiles).
- S-4: the no-raw-literal lint in the existing lint pass.
- S-5: map/budget/diff artifact emission + `refreeze` integration.
- S-6 (T2): per-act solve outputs into the act-descriptor generation path.

Each is a normal byte-changing-adjacent parcel; S-3 is the only one that can
move ROM bytes on its own (define plumbing), and it must land value-neutral
(same values, new source) with byte-identical goldens as its gate.

## 7. T2 — the expressive tier (specced now, built on demand)

### 7.1 State overlays + the runtime contract

Two regions may share tiles iff their lifetimes are disjoint — checked at
build. The S2 bug class needs the runtime half:

- **A DMA-flush point at game-state transitions**: entering a state that owns
  overlay space flushes (or drains) the DMA queue first, exactly the fix S2
  shipped for HTZ→Continue, made a *rule of the transition* instead of a
  per-bug patch. One call site in the game-state dispatcher.
- **Debug-shape ownership asserts**: in DEBUG, each overlay region carries an
  owner byte; `QueueDMA_*` destinations inside overlay space assert the
  current owner matches. Byte-neutral in release (DEBUG-fenced), catches the
  "queued transfer outlives its owner" class live rather than as corruption
  three frames later. The S3K drowning-digits pattern (mid-state sharing)
  becomes: declare the overlay, and the build REQUIRES the owner-byte
  handshake to exist — the guard obligation is enumerated, not remembered at
  six call sites.

### 7.2 Per-act solving

Regions marked `per_act` solve per act; solved bases land in generated
act-descriptor fields (the `act_bg_tiles` precedent — the descriptor is
already the per-act parameter channel). Consumers of per-act regions read
their base through the act context instead of a global constant. This is what
makes "zone-specific object art" a manifest entry rather than a negotiation,
and it is the mega-act's enabling mechanism.

### 7.3 VDP-register emission

A comptime encoder (`vdp_reg`-family, wired to the map's `register` fields)
derives the six register bytes in `boot_data.emp` from the same constants the
regions declare, with `ensure`s pinning equality. Kills the last unchecked
VRAM literals in the tree; after this, *moving the SAT is a one-line TOML
edit* whose register byte, DMA entries, walls and map all follow.

### 7.4 The elastic pool

The FG pool inverts from fixed wall to residual claimant:

- `floor` — per act, **measured**: pages touched by any reachable camera
  viewport (page-granular, not distinct tiles), plus the prefetch window (the
  lap-rate slot budget), plus famine headroom (the pinned+transients
  arithmetic), plus teleport-destination bursts. A build tool
  (`tools/measure_act_floor.py`, riding the strip generator's layout data)
  computes and records it in the act manifest.
- `want = all` — after every fixed region places, the pool absorbs the
  residual. Adding a 28-tile object shrinks slack silently; the build fails
  only at the floor, byte-precisely, naming the act.
- **Prerequisite, named:** C4-3 (the famine capacity fix) must land before any
  act runs with `granted` near `floor` — the STRESS_EVICT famine is measured
  evidence that tight-cache mode has an open defect. Until C4-3, floors are
  conservative (full residency for acts that fit). This graduates C4-3 from
  backlog to the mega-act's critical path, deliberately.
- The report gains `pool: floor N pages, granted M, slack M−N` per act.

## 8. Migration & first consumers

1. **T0 captures today's map verbatim** → byte-identical goldens (the
   refactor gate).
2. **The first deliberate layout change re-runs the dust decision, safely**:
   `fg_art_pool.tiles: 960 → 896` plus floating `dust_puff`/`dust_spindash`.
   The prep parcel already made this harmless — no RAM moves
   (`PAGE_FRAMES_MAX`), no desync (layout-proof hash) — so what cost a
   day of forensics as Task 2 becomes a TOML edit, a goldens re-capture, and
   a map diff that explains itself. **Dust Tasks 3-6 then resume on the
   registry**, spec §4 of the dust design amended to cite the map.
3. Consumers repoint imports module-by-module (small commits, byte-identical
   each); the Python tools swap their literals for `tools/vram_map.py`
   imports.
4. Knuckles Task 9-11 resumes after dust, unchanged except reading its
   windows from the map.

## 9. Determinism & the byte-identity contract

Same declarations → same layout, always (documented sort key, no ambient
state). A layout change therefore happens only when a declaration or content
changes, and every one costs: goldens re-capture + repin + a map diff in the
freeze evidence. That is the same ritual byte-moving parcels already owe —
the linker adds the diff artifact that makes the movement self-explaining.
The acceptance-baseline test (`repin_pins`) keeps its role unchanged.

## 10. Risks

| Risk | Mitigation |
|---|---|
| T0 refactor silently changes a value | byte-identical goldens gate; the generator diffs its output against the audit's table on first run |
| the lint fights legitimate low-level code | lint keys on `vram_art`/`vram_bytes`/VDP-command args only; Z80 `$8000` bank space explicitly out of scope; `boot_data` register bytes exempt until T2 |
| solver placement churn on unrelated edits | pins on everything initially; floating regions opt in; fixpoint acceptance test |
| per-act solving complicates the act pipeline | it rides the existing descriptor-generation path; no new runtime mechanism |
| elastic floors mis-measured → famine in the field | C4-3 prerequisite named; floors conservative until it lands; famine is already loud (watchdog) |
| two placement authorities during migration | T0's generator asserts equality with the engine constants it hasn't absorbed yet; seams enumerated (§5) |

## 11. Verification

- **T0:** goldens byte-identical; generated map == audit's table (mechanical
  diff); demo game covered by its own registry; the four Python copies of 448
  replaced by imports and their tools' outputs byte-identical.
- **T1:** solver fixpoint vs the pinned map; define-plumbing swap
  value-neutral (byte-identical goldens); lint green on the clean baseline;
  artifacts present per build.
- **The dust re-landing** is the end-to-end proof: TOML edit → solve → build →
  goldens re-capture with the map diff as evidence → replay gates PASS
  (they will — the hash is layout-proof now, and that is the point of having
  done the prep parcel first).

## 12. Riders (ledgered, not this design)

- T3: object/effect art as pinned pool pages (ARCH end-state; supersedes
  hand windows for object art).
- Prefer-previous-assignment as a solver secondary objective (novel; unneeded
  at current churn).
- An `empyrean/docs/SIGIL_VRAM.md` language-level spec if the declarations
  ever move from TOML into `.emp` syntax proper (locality argument); TOML
  chosen now for zero language surface and exact `map.toml` symmetry.
- `tools/evict_witness.py`'s hand-copied `PAGE_FRAMES_CLAMP = 9` gains an
  import from the generated mirror when it next changes.
