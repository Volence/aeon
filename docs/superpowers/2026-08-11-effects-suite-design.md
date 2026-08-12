# Effects Suite Design — Raster Engine, Palette Engine, Effects Library, Aurora Tooling

**Date:** 2026-08-11
**Status:** Design approved in brainstorming; awaiting user spec review → per-phase implementation plans
**Scope anchor:** ENGINE_ARCHITECTURE.md §4.6 (shipped parallax), §7 (planned visual effects — this design is its execution shape)

## 1. Goal

Take the engine's visual layer "top of the line": implement the §7 visual-effects system
(raster engine + palette engine + frame effects), grow the existing parallax/deform data
into a reusable, shareable effects library, and give Aurora a first-class authoring
surface with a bit-exact preview. Usability, looks, and implementation quality together —
not one showcase effect.

**Acceptance (project level):** the OJZ water cluster — palette variant below the water
line, Shadow/Highlight surface transparency, sprite-table-switch reflections, animated
water line — first shipped engine-side hand-authored, then **re-authored through Aurora
end-to-end** (Effects Lab → Map assignment → export → build → oracle) with no hand-edited
`.emp`. Once that pipe is proven, content like a "sky showcase" (gradient + clouds +
cycling) is user-creatable in the tool rather than a scheduled milestone.

## 2. What exists today (baseline)

- **Shipped (§4.6):** 8-band shift-add parallax, per-line FG/BG H-deform tables,
  per-column VSRAM V-deform, 16-frame section lerp, comptime DSL
  (`engine/level/parallax_dsl.emp`), small game-side library
  (`games/sonic4/data/parallax/configs.emp`). All scroll-table-based — no HInt.
- **Design-only (§7):** unified raster command table, palette system beyond dirty-line
  DMA, S/H usage, sprite-table switching, effects engine. `sec_raster_table`, `sec_pal`,
  `sec_pal_cycle`, `sec_anim_blocks` are dead descriptor fields — **no consumer**.
  Notably, per-section palettes are NOT implemented: game code hand-pokes
  `Palette_Buffer`.
- **Aurora:** Map/Art/Sprite modes; zero effects authoring/preview.
- **Perf context (DEFERRED_WORK):** HInt is already an ~8.5–10.8% flat tax and the
  per-line HScroll DMA ~20% — new raster work must live inside an explicit budget model
  (§8 below), not on vibes.

## 3. Architecture overview

Three coupled sub-projects, one contract set:

```
engine/effects/raster.emp     — HInt raster engine (two-tier: sparse table + dense runs)
engine/effects/palette.emp    — palette engine (composition pipeline + variants)
engine/effects/effects.emp    — frame-level effects (sequencer, oscillators, shake, hit-stop) [Phase 6]
engine/level/parallax_dsl.emp — existing comptime vocabulary (unchanged)
engine/effects/raster_dsl.emp — comptime constructors → compiled raster programs
engine/effects/palette_dsl.emp— comptime constructors → variants, cycles, fades

games/<game>/data/effects/    — presets: hand-authored .emp + generated .emp (from Aurora)
games/<game>/data/editor/effects/ — Aurora preset JSON + section assignments (source of truth for tool-authored content)

aurora: Effects Lab mode + Map-mode section Effects panel + TS scanline simulator
tools/effects_gen.py          — editor JSON → deterministic .emp + simulator golden fixtures
```

**Layering rule (load-bearing):** frame-level systems (effects engine, game code) write
*inputs* — patch slots, deform phases, oscillator values — to the parallax/palette/raster
engines. Only the raster engine touches the VDP mid-frame; only the palette engine
composes CRAM content. This is what keeps effects composable and simulator-reproducible.

## 4. Raster engine (`engine/effects/raster.emp`)

**Chosen approach (over pure interpreter and compiled-code-per-section):** two-tier —
a sparse command-table interpreter for events, specialized unrolled handlers for dense
per-line runs. Rationale: sparse events are cheap and stackable Batman-style; dense
effects (gradients, VSRAM runs) genuinely need hand-tuned 68k, and the library/tool
*parameterize* those handlers rather than generate code.

**Compiled raster program** = sorted array of `(scanline, command, args)` + attached data
blobs. Initial command set:

| Command | Args | Covers |
|---|---|---|
| `WRITE_REG` | reg, value | S/H toggle, nametable swap, window resize, mode tweaks |
| `WRITE_CRAM` | index, 1–3 colors | small palette touch-ups at a line |
| `PAL_REGION` | variant id | full region swap to a palette variant (CRAM burst, §5) |
| `SAT_SWITCH` | table address | sprite-table switch (reflections, §7.6 trick) |
| `RUN_GRADIENT` | end line, stream ptr | per-scanline CRAM gradient (dense handler) |
| `RUN_VSRAM` | end line, column data | mid-frame per-column vscroll (dense handler) |
| `END` | — | terminator (generator-guaranteed) |

**Sparse means sparse interrupts.** HInt counter (reg `$0A`) is programmed with the
*delta to the next event* — a water-line-only section takes exactly one HInt per frame.
Dense runs set the counter to 0 for their range, then restore delta dispatch. Empty
table = today's cost (the design's zero-regression guarantee).

**Static base + dynamic patch + double buffer.** Compiled tables are ROM. Sections with
dynamic values (water line height, gradient scroll offset) get a RAM working copy with
**named patch slots** the frame loop pokes (e.g. `Water_Level`). Working tables are
double-buffered; VInt flips; HInt never walks a half-updated table.

**Section integration:** `sec_raster_table` consumed on section crossing alongside
`sec_parallax_config`. Raster programs snap (no lerp) — perceptual smoothing at
boundaries is the palette engine's cross-fade job.

**Coexistence:** the existing per-line HScroll DMA path (parallax) is untouched; raster
work must fit the VInt/HInt budget beside it (§8).

## 5. Palette engine (`engine/effects/palette.emp`)

**One owner for CRAM content.** Deterministic per-frame composition order:

```
base palette (sec_pal)  →  cycling (sec_pal_cycle scripts)  →  cross-fade (16-frame RGB lerp
on section crossing)  →  global operators (fade to black/white, white/negative flash)
→  variant derivation  →  dirty-line DMA (existing path, unchanged bottom layer)
```

**Per-section palettes are a Phase-1 deliverable** — the `sec_pal` consumer (instant
snap first; cross-fade when that phase lands). This design finally implements them.

**Palette variants + scanline regions (generalized water — user ruling 2026-08-11).**
The screen splits into palette regions by scanline (raster `PAL_REGION` commands); each
region shows a **variant** derived from the *live composed* base palette — so variants
never go stale under cycling/cross-fade. A variant is:

- a **transform**: per-channel `clamp((c >> shift) + bias)` for R/G/B — covers deep
  water, muddy water, poison, dusk-above-treeline, cave dark, night; authorable by
  sliders; cheap to recompute per frame; or
- an **explicit palette** when a transform isn't expressive enough ("promote to explicit"
  in Aurora).

**Water is a library preset, not an engine concept**: variant below line X + S/H toggle
at X + `SAT_SWITCH` at X + the `Water_Level` patch slot (which game physics also reads).
A treeline is the same composition minus physics and S/H. Regions stack (treeline AND
water in one section).

**Budgeted limit:** a small fixed number of simultaneously active variants (target 2–4;
final number set by the RAM/CRAM-bandwidth analysis in the Phase-2 plan — a full-palette
region swap is a mid-frame CRAM burst costing real scanline bandwidth).

## 6. Effects library

**Engine-side vocabulary (hand-written comptime code, emits zero bytes itself):**
`raster_dsl.emp` — `region_boundary(line:, variant:, sh:, sat:)`, `gradient(top:,
bottom:, colors:)`, `nt_split(...)`, `letterbox(...)` → compiled sorted programs.
`palette_dsl.emp` — variant transforms, cycle scripts, fade curves. Both sit beside the
existing `parallax_dsl.emp`.

**Game-side presets (data):** a named preset bundles parallax config + raster program +
variants + cycle scripts. Examples in the **starter pack** (ships with Phase 3):
`Water_Deep`, `Water_Murky`, `Poison_Surface`, `Treeline_Dusk`, `Sky_Gradient_Sunset`,
`Surface_Ripple_Hydrocity`, plus a couple of deliberately weird ones to show range.
Starter presets are templates — meant to be forked in the lab.

**Dead-data guarantee (load-bearing):** only presets a shipped section references emit
ROM bytes, so the library can grow without ROM cost. **Open question for Phase 3:**
verify sigil actually prunes unreferenced consts/data today; if not, this becomes a
small sigil ask. Gate: build-diff proof (referenced → bytes; unreferenced → zero).

**Sharing (user ruling 2026-08-11 — creativity is the adoption driver):** preset files
are **self-contained and portable** — a `.preset.json` embeds everything it references
(deform tables, transforms, gradient data). Drop someone else's preset into your project
and it works. Aurora supports import/export of presets and preset packs.

## 7. Aurora — Effects Lab + Map integration

**Effects Lab (fourth mode).** One canvas, four author surfaces:

1. **Parallax editor** — band stack as horizontal strips over real BG art; factor picker
   (`FACTOR_*` + custom shift-add composer); amplitude/phase per band; **deform curve
   editor** (sine/triangle/custom or hand-drawn → live-compiled 256-byte table).
2. **Raster track** — vertical scanline ruler beside the preview; drop/drag events
   (region boundary, gradient run, S/H toggle, nametable split). A direct visual of the
   compiled raster program, with the live cycle meter (§8).
3. **Variant designer** — R/G/B shift/bias sliders live against the working palette;
   promote-to-explicit for hand-tuning.
4. **Cycle/sequence editor** — palette cycling steps on a timeline.

**Preview = TS scanline simulator, bit-exact where it counts.** The simulator reproduces
integer math exactly — factor decode, deform sampling, band boundaries, palette
composition order, variant transforms — with a scrubbing/playable camera against test
backdrops or real section art. Where it approximates (DMA timing, CRAM dots) it labels
the approximation on-screen rather than pretending. **Golden tests keep it honest:**
`effects_gen.py` emits fixture scroll tables + composed palettes for known camera
positions; vitest asserts the TS compositor produces identical bytes. Drift = failing CI,
not a lying preview.

**Map mode:** section Effects panel assigns presets from the library, allows per-section
parameter overrides, previews in context of that section's art/palette.

**Verify button (the truth loop):** shells `./build.sh`, loads oracle, captures — Aurora
previews fast, oracle is the truth, sigil makes the round-trip cheap.

## 8. Data flow, validation, error handling

**One direction, no sync loops** (same pattern as collision + VRAM registry):

```
Aurora preset JSON + assignments ──→ tools/effects_gen.py ──→ generated .emp ──→ sigil ──→ ROM
hand-authored presets (.emp) ────────────────────────────────────┘   (generator never touches these)
                                          └──→ simulator golden fixtures (vitest)
```

Generated `.emp` is deterministic (stable ordering, byte-reproducible). Section
descriptor emission wires `sec_raster_table` / `sec_pal` / `sec_pal_cycle` alongside the
existing `sec_parallax_config` path.

**Shared budget model (one rule source, two enforcement points):** a machine-readable
file — cycles per raster command, HBlank window size, CRAM burst bandwidth, max events
per line, variant count, RAM working-buffer limits. `effects_gen.py` enforces it as a
**hard build gate** (fail loudly; no silent fallback — row-178 lesson). Aurora reads the
same file to drive the live per-scanline cycle meter, so the gate almost never fires.

**Runtime defense:** the generator guarantees sorted tables + `END`, so the engine trusts
input; debug shape adds a table-sanity assert on install; release rides the standard
ReleaseFault path.

## 9. Frame effects engine (`engine/effects/effects.emp`, Phase 6)

§7.4/7.5 as designed: 16-oscillator bank, screen-shake tables, hit-stop counter,
512-entry sine table (quarter-wave cos trick), compound rotation helpers, and the
data-driven **sequencer** (wait / set_palette / set_scroll / fade / loop / call / end)
for boss intros, transitions, cutscene beats. Strictly frame-level: writes inputs to the
other engines (an oscillator can drive a deform phase or the water-line patch slot);
never touches the VDP directly. Included in this design so the patch-slot and input
contracts account for it; built last because nothing else depends on it.

## 10. Phasing

Each phase = its own research + plan + implementation cycle off this spec; mergeable to
master independently; engine → library → tool.

| Phase | Delivers | Gate |
|---|---|---|
| 1 | Raster core (sparse dispatch, double buffer), `sec_pal` consumer, `sec_raster_table` wiring | Test section with region boundary + S/H toggle verified on oracle **mid-scroll** |
| 2 | Palette engine composition, variants, gradient/VSRAM dense runs | **OJZ water cluster hand-authored** (variant + S/H + reflections + live `Water_Level`) |
| 3 | `raster_dsl`/`palette_dsl`, preset format, starter pack, dead-data proof | Referenced preset → bytes; unreferenced → zero (build diff) |
| 4 | TS simulator + golden tests, Effects Lab surfaces, preset import/export | Simulator-vs-fixture byte equality in CI |
| 5 | Map assignment, full `effects_gen.py` path, verify button | **Acceptance:** water cluster re-authored in Aurora end-to-end, no hand-edited `.emp` |
| 6 | Frame effects engine (sequencer, oscillators, shake, hit-stop) | Sequencer-driven transition demo on oracle |

**Verification doctrine (all phases):** oracle captures during motion, never at-rest;
input-replay fixtures for regression; profiler runs at max scroll against the budget
model; each phase's plan opens with the full reference-research sweep (Batman & Robin,
Titan, Kabuto, S.C.E., Bloodlines, plus online sources) re-verified for its slice.

## 11. Open questions / risks

1. **Sigil dead-data pruning** — is the "unreferenced presets cost zero ROM" property
   true today? Verify in Phase 3; file a sigil ask if not.
2. **CRAM burst bandwidth for `PAL_REGION`** — how many colors can swap at a boundary
   line without visible artifacts; sets the variant budget (Phase 2 analysis; S3K's
   mid-frame underwater DMA is the reference point).
3. **HInt budget interplay** — raster dispatch shares the frame with the existing
   ~10% HInt and ~20% per-line HScroll DMA taxes; the budget model must be calibrated
   against measured profiler numbers, not datasheet arithmetic (Phase 1).
4. **Simulator scope creep** — the TS compositor must stay pinned to the golden-fixture
   contract; anything not fixture-tested is officially "approximate."
5. **`sec_anim_blocks`** (per-section animated tiles) remains out of scope — separate
   DEFERRED_WORK entry, not part of this suite.
