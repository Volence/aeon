# Shannon Birt survey — multiplexing, CRAM racing, S&H expanders, interrupt-gap threading — 2026-08-01

Survey of Shannon Birt's (@birt_shannon, NZ) public devlogs, filtered for what Aeon
doesn't already have. Birt is pushing the Genesis harder than almost anyone currently
active: Lufthoheit (Thunder Force-style shmup), Mega Parodius (w/ Pyron + Vector Orbitex),
a polygon 3D engine (w/ Toni Gálvez), and the tech-demo series that made the rounds
(1013 sprites / 1013 colors; SNES-style transparency).

**No source is available.** No GitHub, no blog, no released ROMs — their footprint is
X threads, a YouTube channel (Sprite Multiplexing Madness, youtu.be/8waFxFKjDn4), and a
Retro Gamer #259 interview. Everything below is reconstructed from their own devlog
claims; numbers are theirs, verified on real hardware (MD1 VA6 + PVM) per their posts,
not by us. Treat all of it as CLAIMED until we prototype. Stack: SGDK skeleton with the
engine "heavily written in 68k assembly with only the level scheduler in C"; they debug
with Exodus (sprite boxing) — same lineage as our oracle.

Sources (status IDs on x.com/birt_shannon):
- 1013-sprite demo breakdown — status/1773248052817805433 (pinned, Mar 2024)
- Lufthoheit engine update (multiplexer + HInt rewrite + DMA rewrite) — status/1793484641061757317
- 56-HInt scene + offscreen-sprite bandwidth fix — status/1806096301383385408
- Transparency Part 3 (software + S&H) — status/1824449491245871582
- Transparency Part 4 (VDP debug register) — status/1825381140791968118
- Sprite Color Expanders Part 2 (S&H over FG) — status/1852348487092023546
- Lufthoheit Tunnel/Vortex stage (CRAM racing + co-op threading) — status/1836852694038045149
- Mega Parodius 19-color BG — status/1968189940128419907
- Mega Parodius warmup starfield (168-sprite multiplexer) — status/2083355390981603555
- Lufthoheit 5x sprite scaler — status/1975761636142293103
- 3D engine updates 8 / 8.5 (interleaved-plane framebuffer, sprite background) —
  status/2077723799316013354, status/2081168090247880746

YouTube pass (2026-08-01, via yt-dlp auto-captions + descriptions; channel
UC5CAIwM8ADZxzoSDfqKu4mg, 6 videos):
- Sprite Multiplexing Madness (8waFxFKjDn4, 7:30, Nov 2023) — transcript
- Lufthoheit WIP preview (DtnqBoSfbro, 11:43) — transcript
- Mega Parodius Stage 8 boss "Puyon" (pqNbWbk8iPA) — description (dense)
- Mega Parodius WIP / VRAM defrag (pq_IworHJr4) — description (dense)
- Mega Parodius Catboss update (ID2WfqSnyk0) — description (dense)
- Stage 1 WIP shooter engine (Uu__HghyWzY) — description

---

## KEEP #1 — Co-operative threading inside interrupt-wait gaps

**What:** In the Tunnel stage, HInt-driven CRAM racing means the 68k spends large
stretches of active display waiting for the next HBlank window. Instead of polling,
they run a co-operative multi-threading system that executes object logic (rolling
cannons, bullets, debris movement) in those gaps, yielding back before the window.
Claim: **up to 25% of total CPU reclaimed** — "normally wasted polling for rhs/hblank."

**Why it matters to us:** Today Aeon's HInt load is light, so we have no polling waste
to reclaim. But the visual-techniques backlog (#2 HInt palette regions, #19 per-section
HInt dispatch, #20 multiplexing) all pull toward HInt-heavy scenes, and the mega-act
showcase will want exactly that. The lesson to bank at design time: **an HInt-heavy
scene design must budget the inter-interrupt gaps as schedulable time, not dead time.**
A cooperative "run N iterations of a work list, yield before scanline X" slicer is much
simpler than it sounds when the work items are already object-update calls.

**Caveats:** Yield discipline is the whole game — a work item that overruns corrupts the
next CRAM write window. Their model works because shmup object updates are tiny and
uniform; our object updates are not. If we ever adopt, slice at object granularity with
a scanline-counter guard, and only admit objects tagged cheap.

**Where it lands:** Note on backlog #19 (per-section HInt dispatch) — the dispatcher is
the natural owner of the gap scheduler. No action until an HInt-heavy zone exists.

---

## KEEP #2 — Offscreen sprites still eat line bandwidth; cull by TRUE width

**What:** Every scanline has a fixed sprite-pixel budget (320 px in H40) counted across
*all* SAT sprites on that line — including ones fully offscreen left/right. Their
multiplexer culled at x < 96 assuming worst-case 32 px width; for 16 px-wide sprites
that leaves a 16 px band where an invisible sprite still burns line budget and can
starve visible sprites into dropout. Fix: cull against actual sprite width per entry.

**Why it matters to us:** Directly auditable against our sprite renderer today. If our
offscreen rejection uses a single worst-case margin (or worse, only culls at SAT-build
time by object AABB), wide-margin invisible sprites are stealing per-line budget in
exactly the crowded scenes where dropout shows. Cheap to check, cheap to fix.

**Caveats:** Per-entry width lookup costs a few cycles per sprite in the SAT build path;
only worth it if we actually cull with a shared margin now. Also remember the other
direction: a sprite at x=0 (fully off-left) still terminates the line fetch on real VDP
if masking rules engage — our masking behavior (backlog #10) interacts here.

**Where it lands:** Audit item for engine/objects sprite path (SAT build / visibility
rejection). Worth a 20-minute read of the culling code next time that file is open.

---

## KEEP #3 — CRAM racing, with real numbers + two composition tricks

**What:** The Tunnel stage runs **40 variable-spaced HInts** covering 120 scanlines of
color change at **5 colors per line = 600 CRAM writes per frame**, on top of music,
game logic, and 60 FPS. Parodius runs ~9 mixed-purpose interrupts (laser effects +
BG color extension) for ~8% CPU. Two composition tricks worth stealing:

1. **Variable-spaced interrupts as an effect primitive** — the expansion/compression
   "breathing" of the tunnel texture is driven by *moving the interrupt lines*, not by
   rewriting more colors. Reprogramming VDP reg $0A per fire makes interrupt spacing
   itself an animation channel.
2. **Temporal color blending** — at band seams, alternate two similar colors at 60 Hz
   to fake an intermediate shade. This is the temporal cousin of backlog #15 (dithering
   across S/H tiers); it costs zero CRAM and zero resolution, and on CRT/blur it reads
   as a real color. (Classic demoscene trick; their contribution is using it only at
   seams between brightness regions, where the eye would otherwise catch banding.)

**Why it matters to us:** Backlog #2 already banks HInt palette regions; these numbers
calibrate its budget note (600 writes/frame is achievable alongside a 60 FPS game, cost
center is the interrupt count, ~1%/interrupt in their Parodius accounting). The seam
flicker-blend is directly applicable to any vertical gradient sky/water we ship.

**Caveats:** Their interrupt-collision note (laser HInts vs color HInts "had to be
sorted out") is the real warning — two independent HInt consumers need a single sorted
dispatch list, which is exactly backlog #19's design. Temporal blending shimmer is
visible on sharp LCDs; gate it behind the same taste check as any dither.

**Where it lands:** Numbers → backlog #2's cost section when it graduates. Tricks →
same note. No code now.

---

## KEEP #4 — Multiplexing calibration points (what the VDP actually caps at)

**What:** Hard numbers from the 1013-sprite demo and production use:
- VDP ceiling: **~4.5 sprite X/Y repositions per scanline** simultaneously with
  **4-5 CRAM color DMAs per scanline** — "VDP maximum level," ~97% CPU/DMA, tight timing.
- Production-scale version: Parodius warmup runs a **168-sprite multiplexer**
  (96 starfield stars = 8 hardware sprites reused 12×, at 96 distinct speeds, + 72
  general-purpose) in a shipping level, alongside a 32-speed line-scrolled FG starfield.
- 3D engine: **114-sprite multiplexed background** entirely of 16x32 strips (6×17 grid).
- Lufthoheit uses multiplexed sprites for *all* game objects ("enemy-hell"), not just
  bullets — with a modular HInt system ordered so color updates or sprite updates can
  go first depending on the scene.

**Why it matters to us:** Backlog #20 banks multiplexing as a per-state opt-in with no
sizing data. These are the sizing data: a starfield-depth layer for the mega-act
showcase costs ~8 real sprites and an HInt handler, and the ceiling for "how much can
one scene multiplex" is known before we prototype. Their reuse pattern (tiny sprite set
recycled N× for particles at distinct speeds) is the exact cheap-depth trick the
showcase background wants.

**Caveats:** All their heavy multiplex scenes are shmup camera (no vertical scroll
coupling); Sonic-speed vertical camera movement re-bins bands every frame. Backlog #20's
per-line 20-sprite cap note still governs.

**Where it lands:** Fold into backlog #20 when it graduates. Mega-act showcase
candidate: multiplexed starfield/particle BG layer.

---

## KEEP #5 — S&H "sprite color expander": measured yield for a banked idea

**What:** Sprite Color Expanders Part 2: two base palettes (30 colors) in the
foreground plane + S&H operator sprites individually darkening/brightening per-pixel →
**~90 on-screen colors, up to 45 colors per tile**. Their stated costs: 2× VRAM for the
region, consumes both sprites and FG plane over the effect area, and every derived
color is a brightness sibling of a base color. Transparency Part 3 layers this further:
software per-pixel blending (5120 px/frame brute force) + S&H + a separate outline
layer, achieving two overlapping see-through layers at 60 FPS with CPU to spare.

**Why it matters to us:** Backlog #1 (S/H tier system) and #6 (operator sprites) bank
this family as IDEA with a theoretical 3× multiplier. This is field confirmation of the
practical yield (3× per palette confirmed: 30 → ~90) plus the honest cost sheet. Their
artist's reaction ("feels like a different machine") matches the mood-win rationale
already in the backlog. Set-piece scope (a boss, a showcase vista), not whole-zone.

**Caveats:** Their expander dedicates the sprite layer over the boosted region — for us
that collides with actual gameplay sprites anywhere the player can be. Fits static
vista bands (backdrop above/below play space) or boss intros where sprite load is
choreographed.

**Where it lands:** Confirmation + numbers for backlog #1/#6. No new entry needed.

---

## KEEP #6 — VDP debug-register blending: catalogued, with the compat sheet

**What:** Transparency Part 4: the undocumented VDP debug/test register can force
layer/sprite blend behavior — BG plane ANDed into sprites full-screen, **zero CPU**
(whole demo ~10% CPU, all logic). Their field findings:
- Works on ~70% of MDs: VA3/VA4 broken, VA6 / MD2 / Wondermega correct.
- Vertical border garbage: fixed by disabling debug mode in VInt, re-enabling at line 0.
- No overlapping transparencies; effectively monochromatic (8 shades per ghost);
  outlines nearly impossible (sprite layer gets fully AND-masked).
- Their verdict: not superior to software+S&H (Part 3); would ship only behind a
  detect/select option with fallback.

**Why it matters to us:** Not in the backlog at all — this catalogues it so we never
re-research it. Titan Overdrive lineage, Kabuto's notes territory. For Aeon the compat
sheet is the decision: a technique that breaks on 30% of consoles fails our
works-on-real-hardware bar for anything load-bearing, and oracle likely doesn't model
it either. Park it as a "demo/easter-egg only" tool.

**Where it lands:** This note is the record. Do not promote to backlog as a zone
technique; revisit only for a non-gameplay flourish with explicit fallback.

---

## KEEP #7 — Smaller ideas worth one line each

- **Variable-rate collision:** bullet-vs-player checks run at 60 Hz only when close,
  decimated with distance. Trivial, composable with our collision scheduling if object
  count ever pressures the frame.
- **Dirty min/max line tracking for big DMA buffers:** 3D engine sends up to 20 KB of
  framebuffer per frame but analyses min/max dirtied tile lines and sends only that
  span — same shape as our plane-buffer partial-drain thinking; useful precedent for
  any future framebuffer-ish effect (special stage).
- **Interleaved Plane A/B framebuffer + all-sprite background:** their 3D renderer
  interleaves the two planes so double-buffered RAM → VRAM DMA is purely linear (no
  tile translation), then rebuilds the *background* from 114 multiplexed 16x32 sprite
  strips, Neo Geo style. Wholesale inversion of normal MD rendering. Irrelevant to
  platformer zones; bank for a possible 3D special stage.
- **5× sprite scaler** (64x32 → 320x160, 60 FPS vertical / 30 FPS horizontal update):
  no implementation details published; noted so we know the ceiling exists if we ever
  want scaling set pieces.

---

## KEEP #8 — HInt register partitioning: zero save/restore interrupt handlers

**What (Puyon boss video):** During the vertical-scaling effect they split the 68k
register file into two static sets: **4 registers permanently owned by the HInt
handler** (which drives per-line vertical scaling), 12 for the main-loop horizontal
scaler. The HInt does **no backup/restore at all** — their claim: save/restore "would
double CPU costs" at their fire rate. The catch, in their words: the moment any
background routine touches the HInt's registers mid-effect it all breaks, "so it has
to be carefully timed."

**Why it matters to us:** The standard prologue/epilogue is pure overhead multiplied
by fire count — at every-4-scanlines rates it dominates the handler body. If Aeon ever
ships an HInt-heavy scene (backlog #2/#19/#20 all trend there), a per-scene register
reservation is the single biggest lever on HInt cost. AS makes this less scary than
their hand-discipline version: a scene-scoped `reg` alias set + a lint/convention that
the reserved registers are untouchable inside the affected loop gets build-time
enforcement of what they enforce by care.

**Caveats:** Only viable when the effect scopes cleanly (their scaler runs during a
choreographed boss sequence, not open gameplay). Engine-wide reservation would tax
every routine; scene-scoped is the only sane shape. VInt still saves/restores normally.

**Where it lands:** Design note for backlog #19's dispatcher when it graduates —
"handlers may declare a reserved register set; the scene that installs them accepts
the constraint."

---

## KEEP #9 — Auto-defragging VRAM allocator with variable slot sizes

**What (Parodius WIP video):** Their dynamic enemy-art region (444 tiles for level 1)
is managed by a **defragmenting allocator**: variable-size slots (fixed slots rejected —
sized for the worst case they'd be too big, leaving too few), and when objects die the
surviving objects' streamed animations are **live-shifted** to compact free space —
visible in their tile-viewer capture as animations physically move. Rationale verbatim:
without defrag "VRAM would become like swiss cheese after a few screens of enemies,"
and "sloppy VRAM management is the achilles heel of GFX diversity in a retro game."
Sizing color: one boss (Catboss) eats 308 of the 444 tiles when on screen; the bomb
effect needs a permanently reserved region because it can trigger anywhere.

**Why it matters to us:** This is the strongest single find of the whole survey for
Aeon's roadmap. Our current answer (fully-resident deduped act pool) deliberately has
no dynamic region — but **art-streaming Phase 2 and the mega-act showcase reintroduce
exactly this problem** (per-zone enemy sets streaming through a shared pool across
zone seams). Their field experience gives us the design constraints up front: variable
slots over fixed, defrag-on-death (amortized, DMA-cheap since it's VRAM→VRAM-sized
moves at known boundaries), reserved regions for trigger-anywhere effects, and
live-shift requiring every consumer to re-resolve tile bases (our objects already
resolve art through per-object art_tile, so a move only needs an owner-notify).

**Caveats:** Defrag moves cost DMA bandwidth in exactly the frames where lots is dying
(explosions everywhere) — needs the same budget-slicing discipline as our tile-cache
fill. Their shmup has no camera-reversal re-entry; our sliding entity window can
re-demand art that defrag just evicted — eviction policy needs the entity window's
lookahead, not just death events.

**Where it lands:** Requirement input for the art-streaming Phase 2 design when it
opens. Cross-link from that plan back here.

---

## KEEP #10 — Sprite-budget offloading: the plane layer as sprite relief

**What:** Three recurring moves across their projects, all the same idea — spend plane
bandwidth to protect the per-line sprite budget:
1. **Player bullets as plane tiles, not sprites** (Stage 1 WIP): all player projectiles
   draw into the scroll plane, freeing the entire sprite budget for enemies.
2. **Boss composites** (Catboss): the huge boss is Plane A + sprites, with face/tail/
   propeller as *plane tile animations*; laser effects relocated to Plane B; the
   waterline over him rebuilt from sprites only where three "planes" must overlap.
3. **Two-tier sprite path** (Lufthoheit engine): only the population that needs
   multiplexing pays for Y-sorting/binning ("MP sprites"); big enemies ride the raw
   unsorted hardware path ("VDP sprites" — "cheaper to use"). Their debug HUD tracks
   the two counts separately, plus WF = worst-frame time *measured in scanlines* (/255).

**Why it matters to us:** (1) is a real trick for any dense set piece: a plane-drawn
projectile field costs tile writes + restore instead of per-line sprite pixels — the
restore cost is the catch, but for slow-moving dense fields it wins. (2) is standard
big-boss craft worth having on the shelf for our own set pieces. (3) validates a
structural choice if we ever adopt multiplexing: split populations, don't tax the
whole SAT build. The WF-in-scanlines metric is exactly our Lag_Frame_Count philosophy
(measure the real deadline, not a proxy) — nice convergent evolution, no action.

**Caveats:** Plane-drawn projectiles need cell-aligned art or shifted variants
(pre-shifted copies cost VRAM), and dirty-cell restore each frame; collision stays in
object space regardless. Boss-as-plane needs the plane free — their Catboss forced
laser effects onto the other plane; we usually have both planes busy (FG + parallax BG).

**Where it lands:** Backlog candidate under "Multi-sprite mega-objects" (#12) as a
composite-boss pattern note; bullets-as-tiles is a set-piece tool, note here suffices.

---

## KEEP #11 — Temporal masking: build-time dead-region analysis for animation buffers

**What (Puyon boss video):** For the scaled boss frames they scripted a build-time
analysis of every animation frame that classifies buffer regions into: never-drawn
(skip entirely), needs-CPU-clear, needs-ROM-copy. "Don't draw nothing to buffer if
nothing is already there." Result: −30 KB ROM (headed for −60 KB) plus CPU savings on
every frame — corners/edges of scaling frames simply stop existing as work.

**Why it matters to us:** Pure philosophy match — this is our "build-time computation
over runtime" rule applied to animation buffers, and a pattern our tools pipeline could
reuse wholesale if we ever stream large composed animations (boss intros, title
sequences): the generator emits per-frame draw scripts instead of uniform blits.

**Where it lands:** No action now; pattern noted for any future big-animation tool.

---

## Video-pass enrichments to earlier items

- **KEEP #4 (multiplexing):** the Madness demo reuses only **20 hardware sprites 22×**
  rather than cycling all 80 — throughput was identical and the code simpler; small
  recycled sets are the recommended shape (matches the 8-sprite Parodius starfield).
  Also two ceilings quantified: ~**3 CRAM colors/line via CPU writes** in the border
  (their first demo; pushing harder = CRAM dot artifacts) vs the 4-5/line the 1013
  demo later achieved **via DMA**; and the VDP can't ingest 68k writes at full speed
  mid-display — write pacing is part of the timing budget.
- **KEEP #3 (CRAM racing):** production Lufthoheit runs "~6 palettes' worth of color
  from 4 palettes" routinely mid-scene — the sustainable game-scale figure, vs the
  demo-scale 22 rewrites of the Madness demo.
- **Production sprite-load reference points:** enemy-hell scenes ship at **210-233
  total sprites around 227-236/255 scanlines** of frame time — i.e., heavily multiplexed
  crowds are playable with ~10% frame headroom on real scenes, engine cap 260.
- **Aimed fire is the cost driver, not sprite count:** their heaviest CPU scenes are
  8-9 shooters all computing player-relative trajectories (LUT angles, no arctan);
  pre-baked trajectories are the budget lever. Matches our no-mulu/divu + LUT doctrine.
- **Their debug workflow** runs two emulators side by side for complementary
  inspectors (BlastEm accuracy + Gens per-line CRAM/sprite panels; later Exodus sprite
  boxing). We hold this position already with oracle's unified MCP inspectors.

---

## Confirmations (no action — we already hold these positions)

- **DMA init overhead is the lever, not transfer rate:** their DMA rewrite made
  initialisation "50% faster," mattering with many slices/frame. This is precisely the
  ultra-dma-queue optimization our queue already carries.
- **Sound driver under heavy DMA:** XGM2 "would slow down at times" under the 3D
  engine's massive DMA load (68k-fed driver starving under bus pressure); they fell
  back to XGM1. Validates our Z80-autonomous driver + DMA-survival DAC design — our
  driver's whole premise is surviving exactly that load.
- **Real-hardware VDP revision variance is real** (VA3/VA4 vs VA6+ debug register
  behavior): supports our standing rule of not shipping undocumented-hardware tricks
  on the critical path.

## Explicitly not for us

- Whole-engine 97%-CPU raster showpieces (1013-sprite demo): demo economics, not
  game economics — their own production scenes budget far below this.
- Software per-pixel transparency at scale: 5120 px/frame brute force is a shmup
  boss-scene luxury; our frame budget already has parallax as its standing cost center.
