# Parallax Engine Phase — Research Synthesis (2026-08-17)

Input record for the ratified Step-2 "full parallax engine phase" (research → design →
sweep). Six research lanes ran 2026-08-17: internal audit, Sonic lineage (S.C.E./S3K/S2/
sonic_hack), Treasure/Technosoft (B&R/TF4/Gunstar/Alien Soldier/Vectorman), Ristar +
prior-notes corpus, online catalogue, Aurora/export-pipeline assessment. This file is the
distilled, durable synthesis; the full lane reports were session artifacts.

## 0. Ratified requirements (owner, 2026-08-17)

- The three OJZ asks: tree bands at distinct speeds, deeper-reading BG, more band granularity.
- Mega-act needs: transition corridors, floating-origin invariance.
- Aurora authorability as a design constraint (the lab binds to what this phase blesses).
- Foreground (plane A) parallax as a first-class requirement.
- Per-column vertical (VSRAM) effects as a requirement, not a nice-to-have.
- BG tile animation interplay with parallax bands.
- **Feature-complete** vocabulary; **pay-for-what-you-use** (unused capabilities compile out
  of a game's ROM); **one unified contract** with the raster effects pack; **budgeted
  authoring** (per-capability documented per-frame cost, computed at build, warn/error over
  frame budget).

## 1. Internal audit — shipped system vs requirements (verdicts)

| Req | Verdict | Notes |
|---|---|---|
| R1 many H bands, distinct speeds | SHIPPED | 10-byte band_entry, shift-add factor encoding (multiply-free), per-band FG/BG factors + deform amplitude/phase; per-line mode gives scanline-exact boundaries since Parcel W. Gaps: single shared deform table + frequency per plane. |
| R2 depth (V parallax, per-column VSRAM, 64×64) | SHIPPED (BG) / PARTIAL (FG) | Whole-plane + per-column BG VSRAM shipped; `pcfg_v_factor_fg`/FG column path reserved-unwired. Leftmost 16-px partial-column VSRAM=0 silicon trap known (mask/lock/accept). |
| R3 FG (plane A) parallax offset | MISSING by hard constraint | Plane A hard-locked to camera (never lerped; disabled-band FG seed = -camX). Reason: camera-anchored 64-col wrap window drags the seam on-screen at any offset. Ledgered relaxation: extend left-edge draw lookahead ≥ max FG offset/deform amplitude (DEFERRED_WORK "FG H-deform vs streaming seam"). FG per-line *deform* (zero net offset) already works (haze configs). |
| R4 BG-anim interplay | PARTIAL | bg_anim.emp shipped but geometry-uncoordinated: BgAnim bands are VRAM tile-slot ranges; parallax bands are scanline ranges. Coordination is author convention only. |
| R5 unified raster vocabulary | SHIPPED core / PARTIAL unification | Rich op set (SET_REG/CRAM/PAL_REGION/RUN_GRADIENT/RUN_RAMP incl. VSRAM target/PAL_RESTORE) + DSL combinators. But sparse/dense tiers mutually exclusive per section; parallax deform and raster ops are two independent per-line vocabularies sharing only the anchor bank (`Effects_World_Y` + `Raster_GetChannelBand`). |
| R6 transitions + mega-act | PARTIAL | Per-section transitions fully shipped (Active_Config routing, 16-frame plane-B lerp, snap, recross-cancel). Floating-origin invariance holds (mod-512/mod-64 math). Corridors/theme handoff unbuilt (backlog). |
| R7 build-time budgeting | PARTIAL (raster only) | `tools/effects_budget_model.toml` + `effects_budget_check.py` + comptime fire-cost guards exist for raster. Parallax has NO build-time cost model (prose numbers only). |
| R8 compile-out | PARTIAL (weak) | Everything runtime-branched off config fields; nothing capability-gated. Precedents to follow: `SOUND_DRIVER_ENABLED` -D flags + `if CAP==1`, DEBUG/CRASH_REPORT shapes, use-closure module elision, bg_anim_port standalone lowering. |
| R9 Aurora authorability | PARTIAL | BG art/anim + collision flow editor→engine today; parallax configs/effects presets/palette variants are hand-authored .emp. |
| R10 feature-completeness | PARTIAL | Explicit gap list: FG offset, FG per-column VSRAM, per-band deform tables/frequency, VSRAM op-class split (banked Part B), patchable overlap (banked Part A), variable-length HScroll DMA (deleted infra), perspective floors, mirage/vortex/earthquake/banking backlog. |

**Cost facts (documented):** per-line HScroll DMA 896 B/frame vs 112 B per-cell — ~20%/frame
flat tax, the single biggest line item, NOT config-capturable for OJZ (per-cell tearing
CLOSED: band boundaries land on arbitrary scanlines, per-cell rounds to 8-px rows → ≤7 px
tear at every boundary during scroll). Parallax_Update ~410 cyc 5-band per-cell, ~800+
per-line; ~6.8k cyc/frame under max diagonal (~7.4%). Raster fire costs measured: reg1=396,
vsram1=458, cram3=518, region3=566, water=660 cyc; RASTER_SCANLINE_CYC=488.

**Trap ledger (all file:line'd in the audit; must survive into the design/sweep):**
reg $0B shadow write discipline (parallax = sole writer; direct write on mode-change frame
with command-state reset + IRQ/Z80 masking); per-cell/per-line twin key in `engine.buffers`
(DMA length must change with mode); `Parallax_Active_Config` routes ALL structural decisions
to Target mid-transition; plane-A lerp seam bug history (2026-06-10/11); flat-fill remainder
tail (zero remainder MUST branch around dbf — 65536-iteration VDP-freeze spray otherwise);
VSRAM landing line = N+1 (oracle-measured; emulators disagree on mid-frame VSRAM, no real
HW); VSRAM writes AFTER HScroll DMA in VBlank; VSRAM op is OP_CRAM-class (target-agnostic
command longword; banked Part B lifts the ceiling, +26 cyc/op today); Raster Buf_B
patched-path observability dead since C2 (BUGS.md); EFX-4b copy_program over-read (benign,
booked); EFX_BLANK_DELAY guards CRAM only (SET_REG mixed in same fire still mid-line);
unreachable-module dead-guard trap (ensures + layouts unvalidated outside use closure);
comptime free names resolve at call site (dropped import → silent label reference).

## 2. Sonic lineage (S.C.E. / S3K / S2 / sonic_hack)

**The S3K/S.C.E. `ApplyDeformation` deform-array model** is the authorable-data benchmark:
- Band table = pure data: word = band height in scanlines; `$8000` flag = "linear" band
  (fresh scroll value read per line — gradients/warps inside one band); `$7FFF` terminator.
- **World-Y band selection**: walker seeds from `Camera_Y_pos_BG_copy` and subtracts band
  heights to find which band the top scanline falls in + partial offset — bands stay glued
  to the background during vertical scroll, generically, with zero per-zone code.
- `ApplyFGandBGDeformation` merges a precomputed FG array + BG scroll table + a per-line
  delta table (`add.w (a6)+`) — the ripple path.
- **Ripple mechanism**: delta tables (dc.w +1/0/-1/-2 per line) + phase = frame counter
  masked and used to slide the table start pointer (2 bytes/step, wrap 64) → the wave
  travels. FG and BG sample at different phase rates for depth.
- **Per-column VSRAM wobble** (AIZ flame): 16-entry sine dc.b table indexed
  `(frame>>2)&$F`, written to 20 columns; mode `$8B03`→`$8B07`.
- Water = HInt palette swap at camera-tracked line (no distortion); oscillation = pure
  phase-counter + (freq, amplitude) data tables.
- S2 contrast: mostly hardcoded inline bands (screen-relative); MCZ row-heights `dc.b`
  table + world-Y gluing is S2's one authorable analog; HPZ expands 16-line blocks with a
  computed-jmp Duff partial-top-block entry.
- sonic_hack OJZ: fully hardcoded shift-fan bands, BG-Y locked; "water ripple" comment is
  STALE (no ripple exists); vestigial dead buffer-tail write — do not copy anything.

**Authorable-as-data vs needs-code split (from the lineage):** band boundaries, scroll
factors (p2 shifts), ripple/wave deltas, VSRAM wobble tables, water tint palettes,
oscillator tables = data. Band walker, non-p2 math, per-column DMA, HInt palette bursts =
engine code. HCZ waterline-reflection warp is the one effect that stayed bespoke code even
in S3K.

## 3. Treasure / Technosoft

- **B&R scroll-band bytecode**: threaded interpreter (`movea.w (a6)+,a0; jmp (a0)` —
  opcodes are routine addresses + inline operands, call stack 4 deep). Band writers for
  constant-per-band and per-line-from-table HScroll. **Resumable raster budget**: a counter
  (`$ff9916`) decremented as bands are consumed; the interpreter stops mid-table when
  exhausted and saves a continuation for next frame — runtime graceful degradation prior
  art.
- **B&R VDP-command shadow buffer**: game code appends fully-formed VDP command words to a
  RAM list; VBlank drains via an unrolled jump-indexed writer — zero per-entry math at
  interrupt time. (Aeon's DMA queue is the same family.)
- **B&R combinatorial palette-DMA selector**: 4 independent effect flags form a 4-bit index
  into a 16-entry CRAM-DMA descriptor table — independent palette effects compose into one
  VBlank DMA without runtime merging.
- **TF4**: 8 layers from a FORMULA (factor = -(i*2-7) × scroll) + one shared 32×16 deform
  table in ROM; a second 14-band consumer re-reads the same table with phase stepping for
  the per-line waterfall. Extreme data compactness: N layers ≈ zero per-level data.
- **Vectorman**: double-buffered precomputed DMA queue with per-entry budget guards (max 54
  entries AND max 2880 bytes/frame, checked per-entry so partial lists succeed). 64×64
  plane dims kept in a RAM shadow feeding wrap math.
- **Gunstar/Alien Soldier**: HInt = executable RAM code at `$FFFFEE00` (disable = write
  `rte` opcode). Heavier muls budgets for scale/rotation illusions. Alien pre-builds VDP
  command blocks (zero-compute VBlank).
- Caveat: the bundled ANALYSIS.md files mis-address in places — always re-verified against
  raw bytes (TF4 layer base is $8198 not $8000).

## 4. Ristar + prior-notes corpus (settled — do not re-derive)

- **HInt dispatch CONFIRMED from bytes**: RAM trampoline at $FFEA70 = inline `jmp $XXXXXXXX.l`
  whose target longword ($FFEA72) is the installed handler; stage-indexed ROM table installs
  {HInt, VBlank} as a PAIR; VBlank re-arms the HInt program EVERY frame; scripts are
  self-chaining handler stages (each fire rewrites the target to the next stage + reg $0A
  spacing); park = `$8AFF` + install bare-rte. Camera-tracked split: `line = featureY -
  cameraY` clamped, one-shot arm flag, unrolled CRAM burst at the split.
- **Computed per-line values are load-bearing**: the boss-zoom accumulator and
  camera-tracked splits are genuinely computed and cannot be declarative data. Aeon's
  existing call (DSL for the expressible subset + `HBlank_Install` escape hatch) is
  validated — the escape hatch is a first-class feature, not a footnote.
- **Corpus rulings that bind this design** (docs/research/2026-08-12-raster-hint-survey.md,
  2026-08-14-s1nxl-hint-dispatch.md, visual-techniques-backlog.md §19,
  2026-06-23-parallax-multilayer-deep-dive.md): reg $0A BIAS=1 + one-interrupt pipeline lag
  → build-time-precomputed arm words + two priming records; ≤3 CRAM words per HBlank from a
  68k handler (cycle-bound); never write reg $0A from main thread during active display;
  mid-frame arming writes $C00004 directly (bypass deferred shadow); S/H stays frame-level
  (no disasm toggles it in HInt); never combine S/H toggle with resolution change;
  **per-line HScroll belongs in the VBlank-DMA'd table, never HInt** (Ruling 4d); sparse
  counter-reprogramming from inside the handler is shipped Treasure practice; Aeon already
  ships the trampoline mechanism — one-handler-walking-data is POLICY, not capability;
  diagonal-scroll perf work is PARKED (branch perf/fillcol-hoist).

## 5. Online catalogue + numbers

**Technique catalogue** (rasterscroll.com; all achievable with existing primitives + new
services): perspective floors (monotonic per-line deltas), cylindrical tunnels (opposed
curves), rotating platforms (band-reversed scroll), tilting (per-line H + per-column V
combined — Bloodlines towers, Gunstar bosses), vertical scaling/stretch (mid-frame VSRAM —
planes only), sprite multiplexing + dual-SAT mid-frame base swap (Bloodlines waterline
reflections), S/H per-line toggle (Mega Turrican water), backdrop-color gradients (cheap
alternative to CRAM rewrites), debug-register layer tricks (Overdrive 2 — catalogue-only,
revision-sensitive, NOT an engine service).

**Numbers for the budget model:**
- Scanline = 3420 MCLK = ~488.6 68k cycles (H32 and H40 both).
- NTSC H40 DMA pools: 7524 B/VBlank, 4032 B across active display (~18 B/line), 11556
  B/frame. PAL H40: 17622 B/VBlank.
- CRAM/VSRAM = 1 word/slot, VRAM = 1 byte/slot; 18 external slots per active H40 line;
  display-off → ~205 slots/line.
- Safe per-HBlank writes (regime-dependent, sources agree once regimes separated): ~8 CRAM
  colors polled port writes; ~6 VSRAM words via HInt (hardware-measured); ~23 DMA slots
  land before visible area.
- 68k DMA stall: CRAM/VSRAM ≈ words×2.4+5.6 cyc; VRAM ≈ max(that, words×4.7-6).
  → 896 B line table ≈ 2100 cyc stall ≈ 12% of NTSC VBlank DMA pool (the audit's ~20%
  "flat tax" figure = DMA + enqueue + drain overheads under load).
- HInt every line ≈ 20-50% of 68k — always prefer counter-fired sparse HInts and
  table-driven hardware paths (validates shipped architecture).
- HScroll table entry for line N is fetched as the FIRST access of line N; VSRAM is
  consumed per-column DURING the line.
- **Leftmost-column glitch**: 2-cell vscroll + hscroll makes the first partial column fetch
  garbage; every commercial game masked it (sprite strip — Battle Mania 2) or shipped it
  (Gynoug). A mask policy must be a first-class budgeted artifact of any per-column-VSRAM
  feature. (MD1 vs MD2 fill value unpinned — verify before depending on it.)

**FG parallax precedent:** the dominant commercial answer is **self-tiling repeating strips
inside plane A** at non-camera speeds with per-tile priority (World of Illusion, Shinobi
III, TF4, Rocket Knight) — those bands never stream, so no seam problem. Streaming FG bands
at non-camera speed are essentially unprecedented (nesdev discussion of staggered seam
updates is the best worked treatment; almost no commercial game shipped it). Design
implication: FG bands as self-tiling strips = cheap and proven; streaming FG bands = novel
work gated on streamer lookahead ≥ max offset.

**Ecosystem check:** SGDK mirrors reg $0B as a mode enum + per-line array + queued DMA (same
architecture as ours) but has NO independently-streaming parallax bands and NO authoring
tool/data format. No copper-list-style declarative scanline display list has ever shipped on
MD. Aurora authoring a declarative band/effect format is genuinely novel territory; the
ingredients are all proven.

## 6. Aurora + export pipeline

- Aurora (Electron/React/TS, Zod formats, Zustand + shared undo) is architecturally ready
  (established "new AppMode" recipe) but has ZERO parallax/effects authoring today; BG
  support = assigning pre-baked Plane-B layouts to sections. Not yet an outbound Aether
  client (live preview blocked on `src/main/aether/client.ts`); save→build→`reload_rom` is
  the supported fallback and ships first.
- **Ratified suite contract**: Aurora authors JSON documents under
  `games/<game>/data/editor/effects/`; a generator bakes deterministic `.emp` (+`.bin`)
  with an explicit LOCKSTEP comment tying emitted records to engine structs + simulator
  golden fixtures (Aurora TS packer golden-tested against Python output). Aurora NEVER
  emits `.emp` directly; compression is Crucible/sigil's, never Aurora's. Precedent:
  `tools/inject_editor_bg.py` (JSON → .emp module with `embed()` + .bin). Re-bake is manual
  (`tools/regenerate-level.sh`) + build-time drift gate (`verify_level_bin.py` pattern).
- `tools/effects_gen.py` is specified (2026-08-11 effects-suite design) but UNBUILT — it is
  the seam this phase's format feeds. Long-term: sigil is absorbing Python generators as
  comptime; keep the JSON→artifact transform simple enough to migrate.
- Section struct already reserves the anchor fields: `sec_pal` $10, `sec_parallax_config`
  $14, `sec_raster_table` $18, `sec_pal_cycle` $24.
- Two existing docs to reconcile: 2026-07-02-raster-parallax-authoring-design.md (older,
  design #8: parallax_gen/raster_gen, static-guides-only viewport) and
  2026-08-11-effects-suite-design.md (newer, ratified shape). Aether constraints if live
  preview lands: symbol-resolved addresses only, role-namespaced methods, loopback-only.

## 7. Synthesis — the design axes the spec must rule on

1. **Band geometry representation**: shipped scanline-space bands + runtime anchor split
   vs S3K world-Y bands re-derived per frame. World-Y is the natural mega-act/Aurora
   representation (author in world space); scanline-space is what the runtime needs. A
   comptime/lowering answer (author world-Y → compile or derive to scanline) is available.
2. **Unification shape**: one contract over two proven runtimes (parallax walker + sparse
   raster dispatcher) vs one merged scanline-services kernel (B&R-style program). Corpus
   ruling 4d (HScroll in VBlank table, not HInt) means true merger is bounded anyway.
3. **Budget model**: extend effects_budget_model.toml + comptime guards to cover parallax
   (per-line vs per-cell DMA line items, walker cycles per band count, VSRAM stride, BgAnim
   bands) with the §5 numbers as constants; runtime resumable-budget (B&R) as a separate,
   optional degradation mechanism.
4. **Compile-out**: -D capability flags + `if CAP==1` + use-closure elision, applied
   per-capability (per-line mode, per-column VSRAM, deform sampling, anchors, dense tier,
   BgAnim, transitions). Beware the unreachable-module dead-guard trap.
5. **FG parallax**: tier 1 = self-tiling strip bands in plane A (proven, cheap, priority-
   carried); tier 2 = streaming FG bands (novel; gated on streamer lookahead ≥ max offset).
6. **Coordination**: shared band geometry so parallax bands, BgAnim strips, raster patches,
   and palette regions can reference the same authored bands/anchors.
7. **Escape hatch**: `HBlank_Install` computed handlers stay first-class (Ristar-validated);
   the declarative op set covers the expressible subset only.
8. **Banked-work revival check**: does the design demand overlapping patchable bands
   (Part A) or the VSRAM op-class split (Part B)? Revival = one plan+execute session
   against effects-tail r3.1 — do not relax check_intervals ad hoc.
