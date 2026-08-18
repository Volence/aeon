# Scanline Services — Unified Parallax + Raster Effects Design (C+)

**Status:** DRAFT r1 — pre-sweep
**Date:** 2026-08-17
**Owner ruling trail:** ratified Step-2 "full parallax engine phase" (2026-08-17 sequence);
approach C+ selected by owner 2026-08-17 evening (one authored scene model, comptime
lowering with per-game runtime specialization, over the two proven runtimes).
**Research base:** docs/research/2026-08-17-parallax-phase-research-synthesis.md (commit
34865383). Supersedes the parallax/raster halves of
2026-07-02-raster-parallax-authoring-design.md where they conflict (that doc's Aurora
viewport/live-preview guidance still stands); composes with, and does not reopen,
2026-08-11-effects-suite-design.md and the banked effects-tail r3.1.

## 0. Requirements → design map

| Req (owner, 2026-08-17) | Where satisfied |
|---|---|
| R1 many H bands, distinct speeds | §2 bands, §4.1 factor curves |
| R2 deeper-reading BG | §2 vertical, §4.1 world-Y re-glue, per-column VSRAM policy |
| R3 foreground (plane A) parallax | §2 FG strips (tier 1), §9 out-of-scope (tier 2 ledgered) |
| R4 BG tile animation interplay | §2 attachments, §4.3 BgAnim band binding |
| R5 unified raster vocabulary | §1 one contract, §2 raster programs as attachments |
| R6 transition corridors / floating origin | §6 |
| R7 budgeted authoring | §5 |
| R8 pay-for-what-you-use compile-out | §3.2–§3.3 |
| R9 Aurora authorability | §7 |
| R10 feature-complete | §2 vocabulary + §9 explicit non-goals (nothing implicit) |

## 1. Architecture

Three layers, strictly one-directional:

```
SCENE MODEL (authored)          one document per section-config: world-Y bands +
                                anchors + attachments. Hand path = comptime .emp
                                constructors; Aurora path = JSON → effects_gen.py →
                                .emp that CALLS THE SAME CONSTRUCTORS (§7).
        │ comptime
        ▼
LOWERING (sigil, build time)    derives runtime-native records (parallax configs,
                                raster programs, arm words, DMA lengths, VSRAM
                                strides); computes the frame-cost ledger and
                                ensure-fails over budget (§5); derives the game's
                                capability set and specializes the runtimes (§3).
        │
        ▼
RUNTIMES (proven engines)       parallax walker → per-line/per-cell HScroll + VSRAM
                                (VBlank-DMA'd tables, NEVER HInt — corpus Ruling 4d);
                                sparse raster dispatcher (counter-fired HInt);
                                VBlank services (palette compose, DMA queue);
                                HBlank_Install escape hatch for computed effects.
```

**The inversion:** the scene model is the single source of geometry truth. Today parallax
bands (scanline space), raster patches (anchor channels), BgAnim strips (VRAM tile slots),
and palette regions are four independently-authored structures agreeing by convention. In
this design a band is declared once in world-Y space and everything else is an
*attachment*; the lowering derives the per-runtime representations and guarantees agreement
at compile time (palette boundary == scroll boundary stops being a runtime coordination
problem).

**Deliberately unchanged:** the runtime execution split (mandated by hardware); the shipped
trap discipline — reg $0B write protocol, `Parallax_Active_Config` transition routing,
VBlank emit order (HScroll DMA → VSRAM → rest), the flat-fill remainder-tail guard, the
trampoline HInt dispatch. §8.4 carries the full trap ledger into implementation.

**Why not a unified kernel (rejected approach B):** a single bytecode runtime buys no new
effects (the vocabulary is hardware-bounded), costs ~20+ cycles/op threaded dispatch in a
224-line hot path, and hides seams the hardware mandates. B&R itself — the best bytecode
precedent — interpreted band *setup* and kept specialized writers for hot fills. B's best
ideas are absorbed instead: resumable budget → §4.4 degradation valve; combinatorial
palette-DMA selection → informs palette compose; shadow command buffers → already our DMA
queue's family.

## 2. The scene model (authored vocabulary)

A **scene** = one section-config's visual behavior. One scene per `sec_*` config slot;
sections reference scenes; acts default-inherit (existing `0 = inherit` semantics kept).

**Bands** — declared by `world_y` top (act space), not plane cells. Per band:
- FG + BG scroll factors — existing shift-add encoding (unchanged; multiply-free is
  right). NEW: a factor may be a **curve**: `curve(from, to)` interpolates the effective
  scroll per line across the band (S3K `$8000` linear-band idea; increment precomputed at
  bake — no runtime division). Perspective floors, continuous canopy depth.
- Optional **deform ref** — `{table, amplitude_shift_a/b, phase, speed}`. Per-band table +
  speed (today: one shared table+speed per plane — a ratified gap). Tables are 256-byte
  generated data: `sine`, `triangle`, `points[256]` (Aurora-authorable).
- Optional **attachments**:
  - `palette_region` — tint/variant applied within/below the band (lowers to raster
    PAL_REGION/ramp records bound to the band's lowered boundary).
  - `bganim` — a BgAnim strip whose driver phase derives from this band's *effective
    scroll* (§4.3).
- `fg_strip` marker (below).

**Anchors** — the existing patch channels (`Effects_World_Y[ch]` → screen-line latch, one
derivation per frame, `Raster_GetChannelBand` as the single clamp source — all unchanged).
Promoted in the model: an anchor is a *dynamic band boundary*; water lines, reflection
splits, boss-driven splits are "boundary = channel N" instead of static world-Y. The
Parcel W runtime band split stays the mechanism.

**FG strips (tier 1 foreground parallax)** — a band declared `fg_strip` scrolls plane A at
its own factor. Contract: the strip's plane-A content is **horizontally self-tiling at the
512-px wrap period** (the World of Illusion pattern — proven, seam-free by construction,
per-tile priority carries the "in front" reading). This is a bake-time content proof: the
generator/lowering verifies the strip's nametable columns tile; a non-tiling strip is a
build error. Non-strip FG lines stay hard-locked to `-Camera_X` (the 2026-06-10 seam lesson
stays encoded — disabled-band FG seed remains `-camX`, plane A never lerps). Tier 2
(streaming FG at non-camera speed) is OUT OF SCOPE (§9).

**Raster programs** — the existing sparse op vocabulary (SET_REG / CRAM / PAL_REGION /
RUN_GRADIENT / RUN_RAMP incl. VSRAM target / PAL_RESTORE) authored as scene attachments
bound to bands/anchors instead of a parallel structure. Dense tier remains a distinct
program kind with its existing constructors; sparse/dense per-section exclusivity is kept
and now *enforced by the scene* (one scene cannot declare both). Sentinels, arm-word
precompute, priming records, ≤3-CRAM-words rule: all unchanged.

**Computed effects** — a scene may name an `HBlank_Install` handler symbol for what data
cannot express (Ristar-validated: zoom accumulators, camera-tracked computed splits).
First-class: the scene declares it plus a **declared cost row** (§5) so budgeting still
holds; the build cannot price arbitrary code, so the declaration is the author's contract,
verified by the runtime lag instrumentation (§8.3).

**Vertical** — per-scene `v_factor_bg`/center/offset (unchanged semantics, 15=lock);
optional per-band v-factor for BG depth stacks (lowered to per-column VSRAM values when
band-granular, whole-plane when uniform). Any scene using per-column VSRAM MUST declare its
**left-column mask policy**: `sprite_mask` | `factor0_lock` | `accept`. The hardware glitch
becomes an authored, budgeted choice (sprite_mask costs a sprite slot — priced in §5).
FG per-column VSRAM stays unwired (no requirement demands it; §9).

**Scene-level fields** — transition mode (smooth 16-frame / instant snap, existing),
deform speeds, anchor declarations, mask policy, computed-handler ref, budget class (§5).

## 3. Comptime lowering & specialization

### 3.1 Lowering
Comptime functions consume scenes and emit the runtimes' native records. World-Y tops lower
to the walker's band representation; arm words, DMA lengths, VSRAM strides, mode bits are
all derived here. The lowering owns today's coordination hazards:
- the per-cell/per-line mode key and its DMA-length twin in `engine.buffers` are computed
  from one derivation (twin-key desync becomes impossible by construction);
- record shapes are capability-dependent: scenes using no new capability lower to the
  EXISTING 28-byte header + 10-byte band entries **byte-identically** (§8.1 migration
  gate); per-band deform refs lower to an extended band record ONLY in games whose
  capability set includes them (pay-for-what-you-use at the data level too).

Existing hand-authored configs (`configs.emp`, `ojz_effects.emp`) migrate to scene
constructors; the superseded direct constructors are DELETED (clean, not bolted-on). The
DSL modules (`parallax_dsl`, `raster_dsl`) survive as the lowering's internals.

### 3.2 Capability derivation
The build scans every scene the game links and derives the **capability set**: PER_LINE,
PER_COLUMN_VSRAM, DEFORM, MULTI_DEFORM_TABLE, FACTOR_CURVE, ANCHORS, FG_STRIPS, DENSE_TIER,
BGANIM, BGANIM_BOUND, TRANSITIONS, COMPUTED, DEGRADE. Authoring an effect IS enabling its
capability — no hand-maintained flag list. Override: a game may force-enable capabilities
(`game.emp` declaration) for scenes installed from data the scan cannot see.

### 3.3 Specialization
Each capability guards runtime code with comptime conditionals (`if CAP_X == 1` bodies —
the `SOUND_DRIVER_ENABLED` pattern) plus use-closure module elision. Specialization depth:
- Module-level: a game with zero scenes links zero parallax/raster/palette-compose bytes.
  `games/demo` becomes the permanent zero-bytes gate (§8.2), the same role it plays for
  engine-agnosticism.
- Path-level: no-deform games get a walker without the sampling loop; never-per-line games
  get no 224-entry fill and no 896-byte DMA entry (the 112-byte cell entry only); no-anchor
  games get no Step-4b split.
- Data-level: §3.1 record shapes.

Two trap-ledger constraints are design inputs:
- **Unreachable-module dead-guard trap:** scene validation `ensure`s MUST live in modules
  always inside the use closure (the scene constructors themselves), never in
  capability-gated modules — a gated-out module's ensures silently stop validating.
- **Derive, don't copy:** every specialization gate's expected value is derived from the
  capability set, never copied from a neighboring pin.

## 4. Runtime changes

### 4.1 Parallax walker
- **World-Y re-glue:** band boundaries recomputed from world space each frame (S3K
  seed-and-search adapted to the shadow-band layout): subtract the BG-space camera Y from
  band tops to find the top visible band + partial offset. Replaces cell-anchored tops.
  Compiled out when a game's scenes are all single-band (capability-derived).
- **Per-band deform refs** (extended record, MULTI_DEFORM_TABLE capability).
- **Factor curves:** per-line interpolated factor path in the fill loop; increment
  precomputed at bake. FACTOR_CURVE capability.
- **FG strips:** strip bands write factor-derived plane-A words for their lines; the seam
  constraint is discharged by the bake-time tiling proof, zero runtime work. All other FG
  lines unchanged (`-Camera_X` hard lock).
- Hot-path discipline unchanged: shift-add decode, unrolled fills with the remainder-tail
  guard, no mulu/divu anywhere new.

### 4.2 Raster dispatcher
Mechanism unchanged. The lowering emits its programs. **Banked-work revival conditions**
(stated here so the trail is explicit):
- An authored scene with OVERLAPPING patchable bands ⇒ revive effects-tail **Part A**
  (one plan+execute session against r3.1; never an ad-hoc `check_intervals` relaxation).
- A scene whose VSRAM op mix hits the OP_CRAM-class ceiling ⇒ evaluate **Part B**
  (op-class split) against its r3.1 §B revival conditions.
Until an authored scene demands them, both stay banked.

### 4.3 BgAnim band binding
A `bganim` attachment derives its driver phase from the owning band's *effective scroll*
(factor-applied camera term) instead of raw Camera_X/Y — waterfall tiles animate at the
speed their band scrolls. Lowered to a new driver kind in the 44-byte record (BGANIM_BOUND
capability); standalone strips (raw camera / Logic_Tick drivers) remain legal and
unchanged. `inject_editor_bg.py`'s LOCKSTEP contract gains the new driver kind.

### 4.4 Degradation valve (B&R resumable-budget, adapted)
Opt-in per attachment: `deferrable: true` marks work (deform phase advance, BgAnim steps,
palette cycling) the engine may skip/defer on lag frames instead of lagging the loop.
Runtime: a per-frame flag set by the existing lag detection; deferrable updates check it.
OFF by default; zero bytes when no scene uses it (DEGRADE capability). Explicitly NOT
applied to scroll-critical work (camera, band scroll, HScroll buffer) — those are
correctness, not flourish. This is the honest answer to the known max-diagonal ~76%-lag
profile (option C of the old ledger entry, now authorable per effect instead of global).

### 4.5 Untouched inventory
VBlank emit order; DMA queue; reg $0B protocol (parallax sole writer, direct write on
mode-change frame with command-state reset + IRQ/Z80 masking); Active_Config structural
routing; 16-frame plane-B-only lerp; recross-cancel; snap semantics; `HBlank_Install`;
trampoline; `Effects_LatchWorldLines` single-derivation ordering; VSRAM N+1 landing-line
model; EFX_BLANK_DELAY semantics.

## 5. Budget model (budgeted authoring)

**One model file** — `tools/effects_budget_model.toml` grows `[parallax]`, `[scene]`, and
`[dma_pools]` tables beside the existing raster rows. Constants pinned to code symbols
(existing `[symbols]` gate pattern) or marked NEEDS-MEASUREMENT with the measurement
methodology named (oracle-next profiler; wall-clock discipline per the 2026-08-13 lesson).

**Cost axes** (a scene's ledger totals each independently — they are different pools):
1. **Main-loop cycles**: walker cost = f(band count, mode, deform refs, curves, re-glue) +
   BgAnim steps + anchor latch. Seed values from measured data (410 cyc 5-band per-cell,
   ~800+ per-line; 6.8k worst-case diagonal) then re-measured per specialization.
2. **VBlank DMA bytes** against the measured pool (7524 B NTSC H40): HScroll entry (896 vs
   112 B — the single biggest authored line item), VSRAM stride, palette lines, BgAnim
   transfers. The ledger prices the per-line choice visibly: an author sees "per-line mode:
   896 B = 12% of VBlank DMA pool" the moment a deform table or anchor forces it.
3. **VBlank CPU cycles**: compose, drain, emit ordering.
4. **HInt cycles**: existing measured fire costs (396–660 cyc/fire) × the program's fires,
   against RASTER_SCANLINE_CYC — the existing G-A6 machinery, now fed from the scene.
5. **Sprite slots**: mask policies that consume sprites (left-column mask) are priced.
6. **Declared rows**: computed handlers carry an author-declared cycle row (§2).

**Enforcement**: the lowering sums per-scene ledgers and `ensure`-fails over budget with an
itemized message naming the authored construct (never a runtime symptom). Budgets have
engine defaults per axis (fractions of frame/pool) overridable per game in `game.emp`, and
per-scene `budget_class` for deliberate hero scenes (a boss room may budget higher with the
owner's eyes open). The full per-scene ledger is emitted as a build artifact
(`<game>_scene_budgets.txt`) so Aurora can display cost-as-you-compose from the same
numbers later (single rulebook — Aurora renders the ledger, never re-computes it).

**Poison discipline**: a fixture scene authored to exceed each axis must fail the build
(§8.2) — a budget gate that cannot fail is vacuous.

## 6. Transitions, corridors, floating origin

- **Per-section transitions**: existing machinery is the contract (Active_Config routing,
  plane-B-only 16-frame lerp, snap, recross-cancel). Scenes reference each other only via
  section descriptors, as today.
- **Transition corridors (mega-act)**: an authoring *pattern*, not new runtime: adjacent
  scenes intended for corridor handoff share a **band skeleton** (same band count and
  compatible tops through the overlap region) so the 16-frame lerp lands smoothly; the
  lowering emits a warning when adjacent-declared scenes' skeletons diverge (declaration:
  `corridor_pair(scene_a, scene_b)` in the act descriptor — advisory, not load-bearing).
  Corridor content/streaming machinery stays with the mega-act program (§9).
- **Floating origin**: world-Y values that live in RAM at runtime — anchor bank
  (`Effects_World_Y`, already rebase-aware) and the new world-Y band tops (§4.1) — MUST
  join the §4.11 rebase checklist. The lowering emits band tops act-relative; the runtime
  re-glue subtracts BG-space camera each frame, so rebase invariance = both terms rebase
  together (same invariant the mod-512 plane math already satisfies). Stated as a contract
  test (§8.2).

## 7. Authoring pipeline (Aurora contract)

**Two front-ends, one rulebook:**
- Hand path: scene constructors in `.emp` under `games/<game>/data/effects/` — the
  reference authoring surface, always available.
- Aurora path: JSON documents under `games/<game>/data/editor/effects/` (Zod-validated in
  Aurora), baked by **`tools/effects_gen.py`** into `.emp` that **calls the same scene
  constructors** — NOT raw records. Sigil's ensures are the single validator (avoids the
  Gate-3 second-implementation trap); the generator's job is transcription + early schema
  errors, and its LOCKSTEP surface is JSON-field→constructor-arg (small), not
  JSON→binary-record (large). Golden fixtures: generator output committed + drift-gated
  (`regenerate-level.sh` + `verify` pattern); simulator fixtures for Aurora's TS packer
  come with the Aurora lab phase, not this one.
- Deform `points[256]` tables and any bulk data emit as `.bin` + `embed()` (the
  `inject_editor_bg.py` precedent).
- Aurora never emits `.emp` directly; compression stays Crucible's; live preview stays on
  the Aether path already specified (symbol-resolved DEBUG override blocks; deferred to the
  Aurora lab phase — save→build→reload_rom is the interim loop).
- JSON schema is versioned from day one (`"schema": 1`) — Aurora binds to it later; this
  phase ships the generator + schema + one migrated reference scene as the fixture.

## 8. Verification

### 8.1 Migration gate (the strong one)
Migrating existing configs to scene constructors with no new capabilities MUST produce a
**byte-identical `s4.bin`** (crc-compared, both canonical shapes). This single gate proves
the lowering's record emission end-to-end before any new mechanism lands.

### 8.2 Build-time gates
- **Demo zero-bytes gate**: `demo.bin` contains zero parallax/raster/palette-compose bytes
  — measured by symbol SPANS, not names (release-leak audit method).
- **Per-capability span gates**: capability off ⇒ its code spans absent from the map.
- **Budget poison fixtures**: one over-budget fixture per cost axis must fail the build.
- **Tiling proof poison**: a deliberately non-tiling FG strip must fail.
- **Corridor-skeleton warning fixture**; **rebase invariance contract test** (§6).
- Gates must observe the SUBJECT (poison the subject, not the expectation —
  raster_source_gate lesson); no gate may pass vacuously (verified-vacuous-gates lesson:
  each new gate ships with its poison).

### 8.3 Runtime verification (oracle-next)
Per the 2026-08-17 switch, verification runs on oracle-next; oracle stays the
absolute-measure reference. Non-negotiables from the instrument ledger:
- **Verify during motion** — at-rest frames hide scroll tearing (the per-cell closure was
  found this way). Banded scroll, curves, re-glue, FG strips all get moving-camera checks.
- Replay net is pixel-blind; raster gates need pinned-camera captures; press-wedge
  avoidance (hold + resume + wait_for_break); CRAM is frame-latched — use arm words /
  memory_hash, not CRAM reads; screenshots are not deterministic gates.
- Profiler counters (per-routine rows) validate the budget model's measured seeds; every
  timing figure ships with a wall-clock uptime beside it.

### 8.4 Trap ledger carry-forward
The implementation plan MUST enumerate, per parcel, which of the recorded traps it touches:
reg $0B protocol; buffers twin-key (now owned by lowering); Active_Config mid-transition;
plane-A seam/lerp history; flat-fill remainder tail (zero-remainder branch); VSRAM N+1 +
emulator disagreement (no real HW — oracle is the arbiter); VSRAM-after-HScroll order;
unreachable-module dead guards; comptime free-name call-site resolution (inline + pin);
Buf_B observability gap (BUGS.md); EFX-4b over-read (booked); left-column VSRAM glitch.

## 9. Non-goals (explicit, so feature-complete has edges)

- **Tier-2 streaming FG bands** — deferred; precondition ledgered (streamer left-edge
  lookahead ≥ max FG offset/deform amplitude). Revisit when content demands a
  non-self-tiling foreground.
- **FG per-column VSRAM** — reserved fields stay; no requirement demands wiring.
- **Debug-register ($C0001C) layer tricks, interlace hi-res, border opening** —
  catalogue-only; revision-sensitive, emulator-variant; not engine services.
- **Sprite multiplexing / dual-SAT mid-frame swap service** — stays on the
  visual-techniques backlog (VRAM + SAT-binning blocked, per §20 there).
- **Window-plane masking service** — window quirks with plane-A hscroll unverified;
  needs a primary-source/oracle check before it can be a contract.
- **Mega-act corridor streaming machinery** — the mega-act program's; this design only
  ships the corridor-skeleton authoring contract (§6).
- **Aurora UI itself** — the Aurora lab phase; this design ships its data contract (§7).
- **Effects-tail Parts A/B revival** — condition-gated (§4.2), not scheduled.

## 10. Suggested implementation phasing (input to writing-plans)

- **P1 — Scene model + lowering + migration**: constructors, lowering to existing records,
  configs.emp/ojz_effects.emp migrated, §8.1 byte-identity gate green. No new runtime.
- **P2 — Capability derivation + specialization**: -D wiring, demo zero-bytes gate,
  span gates, budget model `[parallax]`/`[scene]` rows + ledger + poison fixtures.
- **P3 — Walker mechanisms**: world-Y re-glue, factor curves, per-band deform refs,
  FG strips (+ tiling proof). Motion-verified on oracle-next per mechanism.
- **P4 — BgAnim binding + degradation valve.**
- **P5 — effects_gen.py + JSON schema + reference scene fixture** (Aurora handoff point).

Each parcel lands atomically with its gates; master never holds a half-migrated state
(the migration in P1 is one landing cluster, per the effects-tail precedent).
