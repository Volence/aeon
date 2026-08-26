# Per-section BG seam streaming — research synthesis & design proposal (2026-08-08)

Research pass for the next engine feature after art-streaming Phase 2: per-section
background swap/streaming (Plane B is currently drawn once at `BG_Init` and never
rebased during play). Baseline spec sketch: `DEFERRED_WORK.md` §"SPEC: Per-section
background grid with seam streaming" (~line 1583). Three research lanes ran per the
CLAUDE.md checklist: the 8 reference disassemblies, online/modern sources (SGDK, S3K,
community), and a deep-read of our own machinery + the art-streaming P2 plan seams.

**Design-only.** Implementation is gated on the P2 merge (it consumes P2's budget
seams and P2 owns `vblank.emp`/`ram.emp`/`constants.emp` right now).

---

## 1. Corrections to the record (do these before trusting older docs)

The lanes falsified several claims the spec sketch and prior research rest on.

### 1a. `per-section-background.md` — three citation errors

1. **The Alien Soldier "closest industry precedent" claim is a misread.** The cited
   "6-byte per-section BG headers" (`aliensoldier disasm.asm:42148-42250`) sit inside
   a region the disassembler itself marks as data; the code there requests the **Z80
   bus** and writes six bytes into **Z80 RAM** (`$A01FE8...`) — it is a sound-driver
   mailbox dispatch, not Plane B management. The "$80D4 plane-size bits" cite
   (`:5278`, `andi.w #$e000`) is DMA-destination-address extraction. Alien Soldier
   has a data-driven DMA loader, but the specific per-section-BG evidence is wrong.
   The real precedents are S.C.E. and sonic_hack (§2).
2. **sonic_hack's Plane B is at $E000, not $6000.** The `$6000` in
   `scroll_camera.asm:355,983` is the VDP-command *high word* encoding $E000
   (reg 4 = `$8407`). The doc's "different VRAM split" note is wrong — same split as ours.
3. **The Gunstar Heroes cites** (`disasm.asm:1527-1544`, `6944-6989`) fall in a
   mis-decoded data region; treat those specifics as unverified.

A correction banner now sits at the top of that doc.

### 1b. The DEFERRED_WORK spec sketch — four stale/contradicted assumptions

1. **BG layouts are 64×64 = 8192 bytes, not 64×32 = 4096.** Since NEW-5 (2026-08-05)
   all 64 rows are live (`bg.emp:47` `BG_LAYOUT_SIZE = 64*64*2`; shipped OJZ art has
   real content in rows 32-63). Every 4 KB/128-byte figure in the spec's headroom and
   ROM math needs re-deriving. (`per-section-background.md` Q4/Q5, and the docstrings
   of `inject_editor_bg.py` + `gen_multi_band_bg.py`, carry the same stale 64×32 —
   the tool docstrings are code files, left for a build-gated session.)
2. **The transport the spec names is not the one that exists.** The spec says
   "rewritten via `QueueDMA_Deferrable`", but the purpose-built BG producer already
   shipped on the **`Plane_Buffer`** path: `Draw_BG_TileColumn`
   (`plane_buffer.emp:364-410`) — widened for exactly this feature, header comment
   says "**zero callers today**". Plane_Buffer entries drain via direct data-port
   pokes in `VInt_DrawLevel`, charged against `DMA_Budget_Remaining` via
   `Plane_Buffer_Ptr` — a different budget/queue regime than the DMA queue (§4).
3. **There is no single horizontal "BG camera."** Plane B horizontal scroll is
   per-band (`Parallax_Current_Scroll_B[0..7]`, each band `-(camX>>s1 ± camX>>s2)`);
   only vertical has one whole-plane value (`Parallax_Current_Vscroll_BG`). The
   spec's uniform "camX/8 hidden margin" seam **does not exist horizontally** — the
   seam is per-band. Vertical-first (the spec's own build order) is therefore not
   just convenient, it is the only axis where "the BG seam" is well-defined today.
4. **VRAM figures:** the BG tile ceiling is **448 tiles at slots 1024-1471
   ($8000-$B7FF)** (`bg.emp:49-51`; `BG_TILE_CAPACITY=512` is stale). The spec's
   "two ~224 half-pools" idea remains consistent with 448.

---

## 2. What the wild does (references + online)

Four patterns exist; two are load-bearing for us.

**Pattern A — the BG camera owns the seam** (S.C.E., sonic_hack, Ristar by lineage;
SGDK's MAP engine is the modern restatement). Give Plane B a dedicated camera
variable, advance it each frame by the parallax-scaled delta, and run the same
quantized boundary-crossing test the FG streamer uses (16 px in the classics;
metatile-quantized position diff in SGDK's `MAP_scrollToEx`). **No ratio arithmetic
exists in the drawer** — the fraction lives entirely in how the camera is
incremented; fractional rates just cross boundaries less often. Sub-tile motion is
carried by the scroll registers. SGDK adds catch-up clamps (`COLUMN_AHEAD=21`,
`ROW_AHEAD=16`) and falls back to a full redraw beyond them.

**Pattern B — full/partial redraw at a transition, hidden off-screen** (sonic_hack's
`BG_Dirty_flag` → `Draw_BG_All`; S.C.E.'s `Refresh_PlaneFullDirect_BG`; and the
gold-standard: **S3K Mushroom Hill 2's mid-act season swap** — a position-triggered
event state machine copies a replacement BG layout, queues new art through the
async KosM queue, and repaints Plane B **one row per frame, bottom-up, while trigger
geometry keeps the region off-screen**. No fade. `sonic3k.asm` `MHZ2_BackgroundEvent`
~line 112849). This maps almost 1:1 onto our page-in request queue + plane buffer.

**Pattern C — don't stream: scroll a repeating pattern by formula** (Thunder Force
IV's 8-layer factor system; S.C.E.'s DEZ starfield). The correct choice for
repeating-pattern themes — our shipped T1 behavior is already this. Confirms that
themes which loop should *never* enter the streamer.

**Pattern D — object-owned per-frame DMA display lists** (Vectorman, Gunstar,
Alien Soldier). Powerful, but not organized around a camera seam; over-engineered
for a slower-scrolling continuous BG. Not taken.

**Multi-band + rewritten plane** (the hard sub-problem): the commercial answer is
**band = horizontal strip with its own camera and its own seam** — Sonic 2's
`Draw_BG2`/`Draw_BG3` redraw separate Plane B strips driven by separate
`Camera_BG2/BG3_X_pos`. The community generalization (NESdev staggered-seam thread)
adds rate-proportional scheduling per band. Bands whose offsets stay within the
plane's overdraw slack (~192 px beyond the 320 px window on a 64-wide plane) can
share one seam; beyond that, per-strip streams are required.

**Budget numbers** (verified): ~205 bytes/line VRAM DMA during blanking vs ~18
active (H40) — SGDK's practical NTSC working number is 7.2 KB/VBlank (ours is
budgeted at `DMA_Budget_Default` = 6144 NTSC). One 64-wide plane row = 128 B; one
64-tall column entry in our Plane_Buffer format = 132 B. Steady-state BG streaming
at sane ratios is nearly free; **the spike is theme swaps** (full plane = 8 KB >
one VBlank — must amortize row-by-row, as both S3K and our own
`Section_RedrawPlanes` ~3-4-frame storm already do).

**Hard VDP constraint:** Planes A and B share one size register (64×64 and 128×32
are legal, 128×64+ are not). The BG can never independently go 128-wide; all seam
math fits the 512 px wrap of our 64×64 planes.

---

## 3. What we already have (deep-read highlights)

- **`Draw_BG_TileColumn`** (`plane_buffer.emp:364`): ships today, zero callers,
  reads `Sec.sec_bg_layout` (Act fallback) column-major from ROM into a 132-byte
  Plane_Buffer column entry. **No BG row producer exists** — the vertical case
  needs a `Draw_BG_TileRow` sibling (FG's `Draw_TileRow_FromCache` is the template;
  the Plane_Buffer row-entry format already supports Plane B destinations).
- **FG streamer to mirror** (`Section_UpdateColumns`, `section.emp:466-685`): four
  edge trackers (`Section_{Right,Left,Top,Bottom}_Col/Row_Written`), one
  column/row of blocks per iteration, cross-clamped to the 63-cell plane window.
- **Vertical BG scroll is a single value** (`Parallax_Current_Vscroll_BG`,
  `(camY − v_center_y) >> v_factor_bg + v_offset`), whole-plane VSRAM, wraps
  mod 512. This is effectively the vertical BG camera Pattern A needs — it
  already exists.
- **Parallax config swap** fires on the camera *centre* crossing a section
  boundary (`Parallax_CheckBoundary`), 16-frame lerp with exact-ramp horizontal /
  exponential+snap vertical. The art seam, by contrast, lives at the plane wrap in
  the hidden margin — **two different trigger points** that a "theme swaps art +
  parallax together" rule must reconcile.
- **VBlank/DMA regime**: Plane_Buffer (1536 B) charges `DMA_Budget_Remaining`
  (6144 NTSC) via `Plane_Buffer_Ptr`; the plane drain is skipped on lag frames.
  Post-P2: `QueueDMA_*` additionally gets the `DMA_ENQ_BYTE_CAP` (12288) admission
  cap, and page-ins self-throttle under `act_art_budget` (4096). BG work must pick
  a lane (§4) and, if it uses page-in for theme art, respects those caps.
- **RAM**: no shadow plane needed (ROM-direct read, FG pattern); a full Plane B
  shadow would be 8192 B and is infeasible in DEBUG (+10,280 B tail already).
  Seam-tracker state is a handful of words at the RAM tail.
- **Editor/tools**: `ojz_bglib.json` per-section theme library exists (the spec's
  "UI exists, engine unwired" is confirmed) — but **no tool emits the
  section→theme grid**; everything emits the single zone-wide T1 override.
  `png_to_bg_override.py` already has the palette lock/quantize modes the seam
  palette-compatibility contract wants.

---

## 4. Design proposal

### Core shape (Pattern A + B, sequenced vertical-first)

1. **Adopt "the BG camera owns the seam."** Vertical first: quantize
   `Parallax_Current_Vscroll_BG` to 8 px rows, keep a `BG_Row_Written` tracker pair
   (top/bottom), and emit `Draw_BG_TileRow` entries when the quantized value
   crosses — exactly the FG edge logic with the BG's own coordinate. No ratio math
   anywhere in the drawer. Catch-up clamp + full-redraw fallback à la SGDK.
2. **Transport = Plane_Buffer, not QueueDMA_Deferrable.** Resolve the spec's
   transport fork in favor of the path that already exists (`Draw_BG_TileColumn`),
   is purpose-built, drains inside the existing lag-frame-safe plane drain, and is
   already charged against `DMA_Budget_Remaining`. The DMA queue is the wrong tool:
   its entries are (source,dest,len) block transfers from RAM/ROM, while BG strips
   are assembled per-entry from ROM layout reads — the Plane_Buffer producer *is*
   that assembly step. (The spec text should be amended; done as an annotation.)
3. **Theme swaps = the S3K event pattern on our machinery.** A theme change
   (disconnected seam, or connects-to across a section row) stages: (a) the next
   theme's tile blob **paged into the inactive half of the 448-tile BG pool via the
   P2 page-in queue** (post-merge; respects `act_art_budget` + enq cap), (b) palette
   variant applied per the existing CRAM dirty path, (c) rows repainted through the
   streamer while off-screen. Position-triggered, no fade, amortized — never a
   synchronous blit (the old superseded per-section blit note in DEFERRED_WORK
   already ruled that out).
4. **Horizontal, when it comes, is per-strip** (S2 `Draw_BG2/BG3` precedent):
   bands that need distinct streaming get strip-local cameras + seams; bands within
   the ~192 px shared-seam slack share one. First horizontal milestone should
   *constrain authored content* (connects-to horizontal seams share band config)
   before building N-strip generality.
5. **Trigger reconciliation:** theme *art* seams key off the BG camera(s) at the
   plane wrap; theme *parallax/palette* swaps stay on the existing camera-centre
   `Parallax_CheckBoundary`. They are different events; the theme record binds
   them, the safe-swap rule is "art rows of theme N+1 may not enter view before
   both have fired" — enforced by the seam tracker, not by frame counting.

### Revised build order (spec's order, corrected by findings)

- **(0)** Doc/number reconciliation (this doc + annotations; tool docstrings when a
  build gate exists).
- **(1) Palette variants per section** — standalone first win, zero streaming.
- **(2) Vertical seam streaming** — `Draw_BG_TileRow` producer + BG row trackers on
  the quantized vertical BG camera; the motivating forest→firefly case. T2 grid
  emitter in the injector (section-row granularity only).
- **(3) Theme tile-pool halving + paged theme swap** — consumes P2's page-in
  (hard dependency: post-P2-merge).
- **(4) Horizontal connects-to** with the shared-band constraint.
- **(5) Per-theme anim-band + parallax handoff; editor seam contracts** (bglib
  connects-to/disconnected flags → build-time seam validation).

### Open questions for user ruling (design-level, not defects)

1. **Theme vertical slice height** — 512 px (full plane wrap) vs 256 px slices.
   512 keeps wrap-on-theme-boundary trivial (spec's own lean); 256 doubles theme
   density per world height at the cost of a split-plane tracker. Recommend 512
   until authored content demands otherwise.
2. **Horizontal ambition** — is per-strip N-band streaming (S2-style) in scope for
   the mega-act, or is "connects-to horizontal seams share band config" an
   acceptable permanent authoring constraint? (Recommend the constraint first;
   strips only if a zone's art forces it.)
3. **Whether step (1)+(2) may start before P2 merges** — they touch none of P2's
   files except `ram.emp`/`constants.emp` additions (new state words). Recommend
   **waiting for the P2 merge anyway**: the RAM/constants collision risk and the
   sigil pin-coupling make parallel engine work on those files a false economy.

### Explicitly not taken

- Full Plane B RAM shadow (8 KB — infeasible in DEBUG, unnecessary: ROM-direct).
- QueueDMA transport for steady-state strips (wrong tool; see 4.2).
- Pattern D display-list generality (over-engineering).
- 128-wide plane for BG margin (illegal independently of Plane A; moot).
- Streaming repeating-pattern themes (Pattern C stays scroll-only — T1 behavior).

---

## 5. Dependencies and sequencing

- **Hard:** P2 merge (build order step 3+; and pragmatically steps 1-2 per ruling
  Q3). The P2 plan's Task 8/9 seams (`DMA_ENQ_BYTE_CAP`, `act_art_budget`) are the
  budget contract theme swaps ride.
- **Feeds:** the mega-act tech demo (transition corridors want theme swaps +
  the Harmony-study "marker-relative rebase" idea for parallax residue across
  corridor seams — that item lives with the mega-act track, not here, but the
  theme-record shape should not preclude it).
- **Editor:** the grid emitter (injector change) is daemon-adjacent
  (`ojz_strip_gen.py` is auto-committed by the watcher) — schedule with the same
  ask-first care the P2 plan uses for Task 5/11.

## Addendum 2026-08-26 — S3K background heights, measured (for Q1 / d-16)

Parsed every `skdisasm/Levels/*/Layout/*.bin` header (words: FG width, BG width, FG height,
BG height, in 128 px chunks; SonLVL-documented order, consistent with the row-pointer
indexing at `8(a2,d0.w)` in sonic3k.asm but the loader itself was not traced). BG heights in
px, playable acts: 256 — ALZ, CGZ, DPZ, EMZ, DEZ1, DEZ2, MGZ1; 384 — BPZ, DDZ, LBZ1;
512 — DEZ3, LRZ2, LRZ3; 640 — CNZ2; 768 — ICZ2, MHZ1/2/3, HPZ; 896 — MGZ2, SOZ1;
1024 — HCZ1, HCZ2, ICZ1; 1152 — CNZ1; 1280 — AIZ2; 1408 — AIZ1; 1536 — FBZ1, FBZ2, LBZ2;
2048 — SOZ2; 2560 — LRZ1; 2816 — SSZ1.

S3K's scroll planes are 64x32 cells = 512x256 px (`$9001`), so every BG taller than 256 is
streamed row-by-row into a 256-tall wrapping plane, like the FG. S3K therefore had no chunk
height choice: BG height is arbitrary, the resident window is 256. Aeon's 64x64 planes already
hold twice that. Bearing on Q1: the precedent argues for streaming into a fixed window rather
than for a chunk size; 256-px chunks buy two looks visibly coexisting, nothing else.
