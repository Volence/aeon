# Deferred Work

Tracks work that was identified during design/implementation but deferred because dependencies don't exist yet. Check this document at the start of each new system's planning phase — items here may now be unblocked.

> **Open defects** (not deferred features) live in **`docs/BUGS.md`**.
> ~~See BUG-001: intermittent section-streaming rendering corruption (garbage tiles + red field) —
> captured live-emulator evidence.~~ **CORRECTED 2026-08-05:** BUG-001 was **RECLASSIFIED
> UNREPRODUCIBLE on the current engine (2026-08-02)** — see `docs/BUGS.md:206`. The banner is kept
> struck-through rather than deleted because the pre-July entries below were written while that
> corruption was believed live, and several of them cite it as motivation.

---

## ⚠ RECONCILIATION BANNER — verified against HEAD `0e1f32c` on 2026-08-05

**This file was re-derived against the tree on 2026-08-05 (parcel `parcel/backlog-reconcile`).
Roughly 20-25% of the entries that read as OPEN were wrong.** The corrections are annotated in
place — every corrected entry keeps its original text beneath a marked correction, because knowing
*why* something was believed is load-bearing in this repo.

**Where the rot is concentrated:**

| stratum | trust |
|---|---|
| pre-July §1 / §2 / §4 entries (Apr-Jun 2026) | **LOW** — many describe deleted subsystems |
| §4 teleport / leapfrog cluster specifically | **DEAD** — 11 entries, subsystem deleted by `eddbbf7` |
| §3 / §4.6 parallax / §4.9 entity entries | mixed — anchors drift, substance mostly holds |
| sound sections (all) | **GOOD** — self-annotating, mostly current |
| 2026-07 and 2026-08 strata | **GOOD** — written under the current conventions |

**Anchor warning — do not chase file:line citations blind.** Pre-July entries were written
against the AS-era tree and cite `.asm` paths and line numbers into files that **no longer exist**:
`main.asm`, `ram.asm`, `constants.asm`, `engine/player/*.asm`, `engine/level/section.asm`,
`engine/sound_*.asm`, `data/sound/fm_patches.asm`. The `.emp` port replaced them (`build.sh:4` —
"`sigil build` IS the build"); the only surviving `.asm` files are the vendored
`engine/debug/debugger.asm` and the two 40-50 line `games/*/game_root.asm` residual roots.
**Re-derive the anchor from the symbol name before acting on any pre-July line number.**

**Three things the file previously said that were flatly inverted, all now fixed below:**
1. The **MDDBG / release-fault** entry described the *opposite* of what ships (owner ruling
   2026-08-04 superseded the 2026-08-05 strip). See the corrected entry near the bottom.
2. The **graph-coloring allocator** was listed as future work *and* as Done in the same file,
   while the allocator is dead code that no longer exists anywhere in the tree.
3. The **VDP `$0B` propagation bug** entry described a live bug that the *same file*, 60 lines
   earlier, records as a **misdiagnosis**.

---

## NOW UNBLOCKED — actionable (compiled 2026-08-05)

Every item here had a stated blocker that **no longer holds**. This is the pick-up list. Ordered
by leverage, not by section. Each links back to its full entry below; read the entry (and its
correction) before planning — several carry caveats that shrink the win.

### 1. §9.7 idle-time deferred work / resumable decode — **✅ RESOLVED — EXECUTED as art-streaming Phase 2 (2026-08-09)**
**Done (`feat/art-streaming-p2`, chains 55→78; merged to master `2f047e3`).** §9.7
shipped as the pre-chunked-pages + VBlank-supervisor-bookmark idle-time path (the user-mode variant
was rejected). The resumable `ZX0R_Decompress` decoder is sliced across idle by a VBlank
register-bank/resume, feeding a VRAM page residency cache. All three items this gated are
discharged: **Art-streaming Phase 2** (the driving consumer) is live; **ZX0 mid-gameplay decode**
now rides the bookmark, never synchronous; **S4LZ Streaming Mode (§2.1)** inherits the identical
pipeline (rescoped in its own entry below). ARCH §9.7 + §2 rewritten in place; see the resolved
full entry below and `plans/2026-08-08-art-streaming-phase2-v2.md`.

### 2. The whole "Engine substrate gaps" gate is satisfied
The stocktake's gate was "execute AFTER the Sigil port". **The port is done** — `build.sh:4`,
no `.asm` code twins remain. Per-item status is annotated on the stocktake itself; summary:
- **SRAM save (item 2)** — mechanically ready, but retains a genuinely unverified dependency
  (oracle SRAM persistence) *and* `3c96265` has since ruled SRAM **is** the persistence
  mechanism (CrossResetRAM ruled out), which raises its priority.
- **Water (item 3)** — unblocked but still wants its own design pass. Not a pick-up-and-go.
- **Engine-default sound bank (item 4)** — mechanically ready, but **must be re-targeted**: the
  contract file it names was deleted. See the corrected item.
- **RNG (item 5)** — folds into design #9, as stated. Not standalone.

### 3. Cheap, self-contained, verification-bounded
- **`yflip`/`xyflip` size+link word merge** (`engine/objects/sprites.emp` `size_link`) — the
  constraint that forced the byte-wise form is recorded as dead. Needs only SAT byte-identity
  verification for the two flipped variants. ~8 cycles/piece.
- **Parallax computed-jump-table unroll** — per-cell HScroll is permanently CLOSED, so this is
  the *only* remaining lever on the ~7.4%-of-frame parallax fill.
- **Variable HScroll DMA — variable-length transfer** — its blocker ("await a confirmed
  performance need") is **DISCHARGED by this file's own measurement**: per-line HScroll is
  896 B/frame, ~20% of the frame, and this file names it "the single biggest lever". Caveat: the
  `Hscroll_Dirty_Start/End` infrastructure it assumed **was deleted** and must be rebuilt.
- **`VInt_Level` header comment** — one-line comment fix, zero byte change (entry at the bottom).

### 4. Object-system items whose §3 blocker is long satisfied
`engine/objects/` is fully built (`load_object.emp`, `animate.emp`, `dplc.emp`, `collision.emp`,
`children.emp`, `sprites.emp`), so these are unblocked *mechanically* — but read the caveats:
- **DPLC Lookahead** (§1.6) — `animate.emp` + `dplc.emp` exist. Clean pick-up.
- **Dynamic VRAM Allocator** + **Refcount-based Art Caching** (§2.2) — `load_object.emp` exists,
  **but the fully-resident deduped art pool may have made the premise moot.** Re-read the design
  before planning; do not assume the 2026-04 framing still applies.
- **Section-aware Streaming / Predictive Preloading** (§2.1/§4.8) — blockers exist, and the
  block-stream half **effectively shipped** (`tile_cache.emp:1001` row scan, `:1093` col scan with
  H3 hysteresis). What remains is the *art* half, which is item 1 above.

### 5. Diagnostics / instrumentation
- **Contract-enforcement trap handler** (68K half, idea-capture section) — its expensive
  prerequisite, the In:/Out: contract grammar, **has landed and is still growing** (HEAD `fa0ae0b`
  made the Z80 bus and the interrupt mask declared contexts). The cheap half of a
  design-for-it-now item is now the only half left.
- **SIGIL ASK (not aeon work) — promote declared-`preserves()` violations to a build-fatal
  dataflow check.** From the T6 art-streaming review. Today `[call.live-clobbered]` is a
  *non-fatal* diagnostic, and that leniency is exactly how the chain-63 `CopyBlockColumn` `a1`
  regression shipped: a coherent-but-wrong render that a fatal check would have caught at build
  time. Ask: sigil should verify, per proc, that the value of each declared-preserved register at
  every `rts` equals its value at entry (dataflow equality across the whole body incl. call
  clobbers), and make a violation **build-fatal** — not a warning. This lives in the sigil repo
  (`/home/volence/sonic_hacks/sigil`), not here; recorded so the ask isn't lost.

- **The replay net has NO automated runner — it is invisible to every gate we own.**
  Discovered 2026-08-13 while re-stamping it (`docs/superpowers/plans/2026-08-13-replay-net-restamp.md`).
  Verified: it is not a pytest, not a cargo test in sigil, not in `test.sh`, and there is no CI.
  The aeon suite's "2 skipped" are `test_s4lint.py` looking for a deleted `main.asm` — **not**
  the replay net. The net fails only when a human runs a manual oracle procedure, which is
  precisely how master stayed red from the Knuckles C4 merge until 2026-08-13 with nothing
  reporting it. `tools/test_replay_fixture.py` now gates fixture *structure* (length, tick
  count, checkpoint ring alignment, and the BUTTON_C spindash runs that prove a re-stamp
  rather than a re-record), but it cannot detect a desync — that needs the emulator.
  Two candidate fixes, neither scoped: (a) a headless oracle runner invoked from `test.sh`,
  (b) a committed re-stamp tool that makes the manual loop cheap enough to run routinely.
  The manual loop currently costs ~7 full playbacks; each one replays from tick 0, and the
  post-spindash section runs well under realtime under host CPU contention.

### 6. Sound package 4 — ✅ EXECUTED 2026-08-10 (historical text below)
**D1, D4, D5, D6, D7** and **E5's 7th RegDelta group** are open, verified against the tree, and do
**not** depend on the unexecuted packages 1/3/5/6. (**D2 is DONE** — corrected below.) This is the
largest cluster of small, well-specified, independent sound work in the file.

### 7. Mega-act ROM layout — OJZ's pre-DAC hole caps in-order act data at ~21 KB slack — 2026-08-09
**Discovered building the P2c Task 11 stress-art fixture.** OJZ's map order places ALL act data
(art pool, block blobs, local maps, the 116 KB `collision_data`/heightmaps) BEFORE the HARD DAC
sample-bank anchor at `$48000` (a Z80 `SetBank` latch — cannot move). `collision_data` alone ends
at `$42D90` canonically, so the in-order act data has only **~21 KB of slack** before the anchor.
A real act whose art/block data exceeds that overruns the anchor and will not link in order.

The stress fixture works around this with **fixture-only relocation** (the growable OJZ sections
move past the sound banks, extending the ROM tail — see `native.rs::relocate_fixture_pool`, gated
by `fixture_placement`). That is fine for an unfrozen throwaway, but the **mega-act's real acts
WILL exceed the hole** and need a real answer, one of:
- **post-sound act-data placement** (make the fixture's relocation a first-class layout for real
  acts — the act data region lives after the sound banks, before the fault island); or
- **a ROM layout rethink** (move the sound/DAC banks higher, or bank the act data) so the pre-DAC
  hole stops being the ceiling.
This is a genuine mega-act blocker, not a fixture quirk — record it now so it is not rediscovered
under the mega-act itself.

---

## CANNOT BE SETTLED STATICALLY — needs an emulator run or an owner ruling

Recorded so nobody burns another pass trying to re-verify these by reading code. Each is
genuinely open; none of them can be closed from the tree alone.

**Needs a live emulator run (oracle):**
- **A2 — two SFX in one 68k frame.** The 8-deep ring shipped; the *runtime* check (jump+ring,
  skid+ring, death+ring-loss in one frame, both SFX reaching the chip) has never been run. Partly
  discharged by the Stage-A fix-3 live debugging, but not formally.
- **FM env attack seam (T8 residual)** — explicitly "awaiting the user's by-ear pass". Not
  visible in rendered A/B at capture scale.
- **Bank-latch desync corrupter** — captured exactly once, did not reproduce deterministically.
  Needs a live watchpoint session on `$6000`-latch writes around a mid-sample DAC retrigger. May
  be an emulator artifact.
- **DAC worst-tick profiling round** — the honest lever for the remaining hold tail; requires
  profiling what dominates the 5-10 ms ticks, not code reading.
- **§2 A.5 T1 — FG tile-flip A/B vs sonic_hack** — requires two emulators paused at the same
  screen comparing VRAM bytes. Build-tool math already verifies correct.
- **oracle SRAM persistence** (substrate item 2's hidden dependency) — likely an oracle-side task,
  not an Aeon one.

**Needs an owner ruling (product decision, not an engineering answer):**
- The **diagonal streaming budget** tradeoff (A: accept the dip / B: cap combined diagonal step /
  C: cut BgAnim bands during fast scroll). Recommendation on file is (A).
- **`test_player` as a unit** — whether the test object set should ship in release at all.
- **Authoring the debug-fly cheat code** — mechanism is shipped and waiting on content.

---

## MAINTENANCE PROTOCOL — in-place annotation is the convention (settled 2026-08-05)

The "How to Use This Document" section at the bottom says to *move* completed items to the Done
section. **That protocol lapsed:** the Done section stops at 2026-06-11, while roughly a dozen
later closures were annotated in place instead (`~~struck~~` headings, `✅ RESOLVED` prefixes,
`DONE <date>` suffixes, inline `**CORRECTION**` blocks).

**Ruling: in-place annotation IS the convention now. Do not move entries to Done.** It preserves
the reasoning chain next to the claim it corrects, which is the property this repo actually wants.
The Done section below is frozen as a historical tail (Apr-Jun 2026); nothing new goes into it.

When you close or correct an entry:
1. Leave the heading where it is; prefix it with `✅ RESOLVED —`, `~~strike~~`, or
   `**CORRECTED <date>**`.
2. State the evidence — commit hash, `file:line`, or the ruling that superseded it.
3. **Keep the original text beneath.** Never silently delete a wrong claim; a wrong statement
   reading as current is the only unacceptable outcome.

---

## Engine substrate gaps — stocktake 2026-07-07 (~~execute AFTER the Sigil port~~ — **GATE SATISFIED 2026-08-05**)

> **✅ GATE SATISFIED (verified 2026-08-05).** The whole section was gated on "execute AFTER the
> Sigil port". **The port is done.** `build.sh:4` reads "THE FLIP (Spec-5 Stage 2, the point of no
> return): `sigil build` IS the build" — asl/p2bin/fixheader have left the pipeline and the `.asm`
> CODE twins are deleted. The only `.asm` survivors are the vendored `engine/debug/debugger.asm`
> and the two ~40-50 line `games/*/game_root.asm` residual roots, neither of which is a twin.
> **The pin-target argument that justified deferring no longer applies.** Per-item status is
> annotated on each item below — three of the five are ready, one needs a design pass, one is not
> standalone.

Gaps with no owning design anywhere (not in the nine design-week specs, not in the sound
packages, not in the engine/game split plan). Deliberately deferred until Sigil finishes
and the code is ported — Sigil verifies by byte-exact pinning against AS output, so new
engine code before then moves the pin target and grows the port surface for no de-risk
(the pin is a stronger port-verification net than any of these features would be).

**Recommended pickup order after the port:**

1. ✅ **RESOLVED 2026-08-02** — **Input layer maturity + demo recording/replay** — SHIPPED
   as the input/replay phase (spec/plan `docs/superpowers/{specs,plans}/2026-08-02-input-replay*`,
   parcels I1-I4, chains 25-30): full 6-button layer (SGDK low-first cadence, two-signature
   per-frame detect, Ext/Pad_Type cells), `Logic_Tick` timebase, the `Input_Tick` replay seam
   (`engine/system/replay.emp`), the committed OJZ fixture + proven checkpoint net
   (evidence: `docs/superpowers/2026-08-02-engine-debts-opener-evidence.md`). Pad-2 was
   already read; a human P2 + the determinism audit shipped with the harness. ORIGINAL
   ENTRY (historical): do FIRST: 6-button read (TH-toggle
   protocol), pad-2 support (a human second player; design #3's Tails AI is input-filter
   based and doesn't need it, a player does), and an input abstraction a record/replay
   harness hooks. Replay's real cost is the determinism audit (RNG seeding,
   frame-count/window-scan-dependent logic must be replay-stable); its payoff is a
   deterministic regression net under every later engine execution (#1/#2/#7-#9).
   `engine/system/controllers.emp` is 62 lines today — 3-button, pad 1.
2. **SRAM save system** — **PORT GATE CLEARED (2026-08-05); hidden dependency still live.**
   68k side is simple; the design is slot format + checksums +
   wear pattern. HIDDEN DEPENDENCY: oracle must emulate SRAM persistence first (verify;
   likely an oracle-side task) — **this one is NOT satisfied and cannot be settled by reading
   the tree.** UI home = design #7's menu screens. The `gameHeader`
   SRAM field (engine/game split plan) already parameterizes the header declaration.
   **PRIORITY RAISED (2026-08-05):** `3c96265` ("CrossResetRAM persistence RULED OUT — design
   deleted, SRAM is the mechanism") makes SRAM the *only* persistence mechanism the engine has.
   It is no longer an optional convenience feature.
3. **Water/underwater engine hooks** — **PALETTE HALF SHIPPED (effects P2, 2026-08-12);
   physics half still deferred.** Two halves: (a) mid-frame underwater palette via HInt —
   **DONE.** The water cluster is a composed preset (a `Variant_Water_Deep` boundary +
   S/H + the `Water_Level` patch slot: `Raster_Buf_B` rebuild + runtime arm recompute via
   `Raster_PatchWaterLine`), built on the raster script engine exactly as this entry
   predicted ("extend it, don't build parallel machinery"). The host now exists and is
   used (`Raster_InstallWater` / `OJZ_WaterRaster`). Two open riders on this half:
   (i) **S/H is visually UNPROVEN** — it dims only low-priority pixels and OJZ art is
   high-priority (baked into generated block data, no engine hook to clear); proving it
   needs low-priority water content, which is out of the effects-P2 parcel's scope. (ii)
   The oracle gate (variant boundary + moving line) is the controller's, not yet run.
   (b) per-section physics-modifier plumbing (engine hooks, game values) — **still
   deferred**, its own design pass when a level needs it.
4. **Engine-default sound bank** — lift the split plan's v1 limitation that `games/demo/`
   can't build with `SOUND_DRIVER_ENABLED` (ship a minimal engine-side bank satisfying
   the soundBankHead contract). **LIVE as of 2026-07-08:** the engine/game split executed
   and `games/demo/` exists — its `build.conf` defaults `SOUND_DRIVER_ENABLED=0` precisely
   because no demo sound bank exists yet (see `docs/ENGINE_ARCHITECTURE.md`, "Engine/game
   contract" section, and `games/demo/build.conf`). Lifting this limitation is now simply:
   author a minimal engine-side (or demo-side) bank that satisfies the `soundBankHead`
   contract (`engine/sound/sound_bank.inc`) — pitch table + SFX window table + song/SFX
   data — and flip the default on.

   > **⚠ CORRECTED 2026-08-05 — THE CONTRACT FILE THIS ITEM NAMES NO LONGER EXISTS.**
   > `engine/sound/sound_bank.inc` was **DELETED** by `1afa9aa` (2026-08-01, "K4 inc-5 Stage 4b —
   > P2 soundBankHead probe: the head is native; sound_bank.inc DELETED"). The `soundBankHead`
   > macro is gone; the head is now emitted natively.
   > **The live contract to satisfy is instead:**
   > - the `sound_bank` anchor declared at **`games/sonic4/map.toml:110`**
   >   (`name = "sound_bank"  # SoundTablesZ80_Head — the MT/SFX phase bank (vma $8000)`), and
   > - the worked reference implementation at
   >   **`games/sonic4/data/sound/soundbankhead.emp`**.
   >
   > Three places still cite the dead path and will mislead the next reader — **all three are
   > out of scope for this doc-only parcel, listed so they get fixed together:**
   > `games/demo/build.conf:2`, `engine/sound/dac_sample_tab.emp:21`, and
   > `games/sonic4/data/sound/soundbankhead.emp:5` (the last is past-tense and least harmful).
   >
   > The item's *substance* is unchanged and the port gate is cleared: author a minimal
   > engine-side or demo-side bank, then flip `games/demo/build.conf`'s
   > `SOUND_DRIVER_ENABLED` default on. Only the target has moved.
5. **RNG** — trivial; fold into design #9 execution (the behavior sequencer is its first
   real consumer), not a standalone task. **(2026-08-05: port gate cleared, but this remains
   NOT standalone — it lands with design #9, not on its own.)**
6. **Dense-tier reserved stream register — FLAGGED, needs user sign-off (effects P2,
   2026-08-12).** `OP_RUN_GRADIENT`'s `.dense_body` ships the CONSERVATIVE model: the
   stream cursor is reloaded from `Raster_Dense_Cursor` (RAM) every line and only
   d0-d1/a1-a2 are saved. The corpus affords a ~26-cycle every-line handler by reserving
   a global stream register and saving zero (Gunstar `a6` / Alien Soldier, survey Ruling
   4c); for a 224-line gradient that difference is ~thousands of cycles/frame. Reserving
   a register engine-wide trades against the contract system and changes register
   conventions across the engine — an irreversible bet, so it is NOT taken without a
   user ruling (`memory/leapfrog_provenance_audit`). Revisit if a dense-tier workload
   measures over budget on oracle. Cycle arithmetic + the two mode-switch transitions are
   documented at `Raster_HInt`'s dense-body comment and `tools/effects_budget_model.toml`.

### ✅ RESOLVED — PAL fixed-timestep — deleted, NTSC-only (ruling B) — 2026-08-02
**Resolution (Volence, 2026-08-02, ruling B):** commit to NTSC-only. The dead PAL
timestep machinery is deleted — `boot.emp` drops the two `Timing_Step` writes and the
`Frame_Accumulator` clear, `ram.emp` drops both fields, `constants.emp` drops
`NTSC_TIMING_STEP`/`PAL_TIMING_STEP`. The region-adaptive DMA budget stays (the drain
reads it). Historical context of the decision follows.
**Surfaced during:** the silent-drop-class doc-reconciliation audit (2026-07-16 review
cross-check). Recorded as an UNFINISHED FEATURE awaiting a product decision, NOT a bug.
**Status (pre-deletion):** `boot.asm:167-174` performed region detection and wrote a
per-region timing step + accumulator, but nothing consumed them:
- `Timing_Step` (ram.asm:79) ← `NTSC_TIMING_STEP=$0100` / `PAL_TIMING_STEP=$0133` (the 6/5
  ratio, constants.asm:83-84). **Zero readers** (grep-verified: only the two boot writes).
- `Frame_Accumulator` (ram.asm:80) ← `0` at boot. **Zero readers.**
- `GameLoop` (game_loop.asm:10-18) runs exactly ONE state tick per `VSync_Wait`,
  unconditionally — no accumulator step, no catch-up ticks. So on PAL hardware the whole
  game (physics, camera, animation) runs at 50 Hz uncompensated (~5/6 speed), and the
  timestep machinery that would drive a fixed-timestep accumulator is dead scaffolding.
  (The region DMA budget `DMA_Budget_Default`, written on the same lines, IS live — the
  drain reads it — so only the *timestep* half is unconsumed.)
**The product decision (either direction is fine; this entry just forces the choice):**
- **(A) Implement PAL support** — consume `Timing_Step` into `Frame_Accumulator` in the
  main loop to run 0/1/2 catch-up ticks per VSync (fixed-timestep), so PAL plays at NTSC
  wall-clock speed. Couples to every frame-rate-sensitive system (physics caps, streaming
  budget, sound tempo — see item 6 above).
- **(B) Commit to NTSC-only** — then `Timing_Step`/`Frame_Accumulator`/`PAL_TIMING_STEP`
  and the PAL boot branch are dead and should be removed for honesty. **← chosen
  (Volence, 2026-08-02); the timestep machinery is deleted.**
**See:** item 6 above (PAL music tempo, the sound half of the same decision).

6. **PAL music tempo** — ✅ DECIDED (Volence, 2026-08-02, by the same NTSC-only ruling B
   that deleted the PAL fixed-timestep): frame-based PAL music slow is accepted as the
   product goes NTSC-only (emulator-only project; classic games shipped frame-based PAL
   music slow). Boot still region-adapts the DMA budget (that IS wired, read by the
   drain); the region timing STEP it used to write is deleted — see the dated
   **"✅ RESOLVED — PAL fixed-timestep — deleted, NTSC-only (ruling B)"** entry below.

---

## ✅ RESOLVED — OJZ section-0 tile-budget overflow — 2026-06-22

**RESOLVED 2026-06-22** via the globally-deduped paged act art pool (OJZ_ACT_POOL_TILES,
page loader), merged to master. The build succeeds and boots — every continuous-scroll
phase since (including Phase 2's on-device oracle verification) has run a bootable ROM.
Historical record retained below.

**Original report — The build failed** (`SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`) at the art-budget
check: `sec0_tiles.bin is 19296 bytes — exceeds Decomp_Buffer capacity (9600)`.
This blocked **all** runtime work — no bootable ROM. Surfaced as "OJZ layout edits
weren't showing in game."

**Root cause is engine-side, not bad level data.** Whole level = 612 distinct tiles
in a 1,536-tile FG VRAM pool (60% empty); user's "shouldn't need so many tiles"
intuition was correct. The per-section streaming + DSATUR color-grouping pipeline
duplicates tiles across two VRAM regions and forces section 0's 603-tile blob
through a 300-tile (`9,600 B`) RAM staging buffer (`Decomp_Buffer`).

**Recommended fix (engine + build tool):** whole-level shared tileset loaded once
(the Sonic 2 model) when total distinct tiles ≤ VRAM capacity — skip color-grouping,
emit one shared tileset, decompress in N≤300-tile passes at level init. Full analysis
+ numbers + the alternative (multi-pass per-section decompress) in
**`docs/research/2026-06-22-tile-budget-deep-dive.md`**.

**⚠ Touches `tools/ojz_strip_gen.py`** — which the auto-commit daemon watches (commits
edits as the user ~60s after change). Coordinate with the user before editing it;
don't edit it autonomously. Needs the user's go-ahead on approach (shared-tileset vs
multi-pass) before implementation.

---

## ✅ RESOLVED — Engine Phase 3 cleanup — 2026-06-23

Behavior-preserving cleanup (branch `cleanup/engine-phase3`). A 114-agent
verified-clean audit confirmed the leapfrog teardown left no dead code paths;
the engine's "orphan" constants are intentional design surface (hardware-register
sets, flag/enum layouts, DEFERRED_WORK-tracked scaffolding), not cruft. Shipped:
- Removed the `SOUND_LOADTEST` debug scaffold (asm block + `build.sh` flag).
- `BG_TILE_CAPACITY` 512→448 reconciled (see the entry below).
- Removed two true vestiges: the `ANIM_BALL` alias and the dead `Sprite_Link_Next`
  write + RAM field.
- Whole-engine comment hygiene (non-sound): stripped historical/lying/task-tag
  comments, kept load-bearing rationale; binary-neutral (ROM byte-identical).
- `ENGINE_ARCHITECTURE.md` reconciled to the shipped paged-dedup pipeline
  (no graph-coloring/DSATUR/`LoadSectionTiles`/per-section art swap; ZX0 act pool;
  §4.2 `Sec` struct corrected to the real 66-byte / `$42` layout); §7 marked PLANNED.
- `CLAUDE.md` pipeline description corrected (graph-color → dedup + spatial paging).

### DEFERRED — Phase 3 follow-ups (not done this pass)
- **Sound-subsystem comment lineage (~151 tags).** `sound_*.asm`,
  `z80_sound_driver.asm`, `sound_constants.asm`, `main.asm`, `game_loop.asm` carry
  dense `(Task N)`/`(Phase N)`/`(Sound 1X)` build-lineage in comments. Deferred to a
  dedicated pass — large, judgment-heavy, on a subsystem not otherwise being
  modified, and many tags sit on otherwise-good descriptions.
- **`CLAUDE.md` "What This Engine Is" residual staleness.** L105 still says
  single-tier "S4LZ compression (level/bulk art)" — it is two-tier now (ZX0 act-pool
  pages + S4LZ runtime block stream). L106 says "Flamedriver sound driver" — the
  shipped driver is the custom sequencer (`engine/sound_*.asm` + the Z80 driver),
  not Flamedriver. **RESOLVED 2026-06-23** — both fixed (L105 → two-tier ZX0 + S4LZ;
  L106 → from-scratch custom Z80-autonomous driver).
- **`ENGINE_ARCHITECTURE.md` §8.1b "Level Editor Tile Budget UI."** Its per-corner /
  4-way-corner-adjacency budget model is the old graph-coloring premise; under the
  global-dedup resident pool the relevant metric is a single global tile cap, not
  per-corner adjacency. Rewrite when the editor budget UI is revisited.

---

## From §5 — Player System

### No bottom death plane — falling past the level bottom leaves the player skimming, not dying — 2026-08-12
**Surfaced during:** Knuckles C4 (glide/slide/climb) oracle verification — the controller
observed a fallen player skimming at y≈5920 (near the OJZ act-1 bottom, world height 6144)
in a **perpetual airborne state** rather than dying/respawning.
**Status (pre-existing engine gap, NOT a C4 defect):** there is no death/respawn system yet.
`Player_LevelBound` (`games/sonic4/player/player_common.emp`) already routes the bottom trip
on `EDGE_KILL` — it sets `Player_Death_Pending` (`st`) — but with the shipped `EDGE_CLAMP`
edge mode it just clamps `y` to the playable bottom and zeros `y_vel`, so the player sits at
the bottom edge airborne. The trigger point exists; the consumer (death → respawn → ring
loss) does not.
**When to revisit:** when the death/respawn system lands — it consumes `Player_Death_Pending`
and this becomes the single trigger. Until then the clamp is the intended placeholder.
**See:** `Player_LevelBound` (`.edge_kill` / `.edge_clamp`), `Player_Death_Pending`
(`games/sonic4/config/ram.emp`), spec §10 edge modes.

### Knuckles' `Disable_wall_grab` (non-grabbable walls) has no counterpart — 2026-08-12
**Surfaced during:** Knuckles C4 Task 11 (climb) research.
**Status:** S3K's `Disable_wall_grab` (`sonic3k.asm:30777`, `:31039`) lets an object mark a
wall non-grabbable so the glide catch / climb refuse it; our engine has no equivalent, so
**every** LRB terrain wall is grabbable. The climb otherwise works; this is only the
object-side opt-out.
**When to revisit:** when an object needs a non-grabbable wall (e.g. a moving platform face,
a scripted no-climb zone). It is an object flag consulted at the wall-catch (`player_climb.emp`
`Knuckles_Gliding_WallCatch`) and the two climb detach points.

### Climb tolerates a 1..3 px wall recess — DELIBERATE S3K divergence — 2026-08-12
**Surfaced during:** Knuckles C4 climb verification (user playtest, reproduced live).
**Status:** SHIPPED as a user-ruled deviation, recorded here so it is never "corrected" back.
S3K freezes the climb on any non-flush, non-ledge wall reading ("If Knuckles has encountered
a small dip in the wall, then make him stop" — `Knuckles_Wall_Climb`, `tst.w d1; bne
.notMoving`). That is safe on S3K's terrain because its climbable walls have FLAT tops, so
the wall distance jumps 0 → ≥4 in one step and the freeze band is never entered en route to
a ledge. **Our terrain has SLOPED grass tops** (ubiquitous), so the face recedes gradually
and the probe walks 0 → 1 → 2 → 3 before reaching the ledge threshold — S3K's rule then
wedges the ascent permanently, ~7 px short of the top, with no eject and no ledge.
Reproduced at the user's ledge: left face x464, frozen at y=561; the platform's top tile is
shape 29 (heights `[9,9,10,10,…,16,16]`, a slope). **The divergence:** a distance of 1..3
means "still on the wall" and the climb continues (normal ceiling gate + 1 px ascent);
freeze is reserved for EMBEDDED (dist < 0), a genuine intrusion. The ledge threshold
(`CLIMB_LEDGE_DIST` = 4) is UNCHANGED, so the ledge still fires by S3K's own test — at
y=560 the gap reads exactly 4. `x_pos` is deliberately NOT hugged toward the wall (that
would drift off `knux_latch_x` and trip the latch-drift detach). The same tolerance is
mirrored in the climb-DOWN path, where S3K's `bne` ejected on a 1..3 recess mid-descent (a
spurious fall rather than a wedge, same cause); a real wall end (≥4 / the +32 sentinel) and
EMBEDDED still detach there exactly as S3K does.
**When to revisit:** only if terrain authoring moves to flat-topped climbable walls, which
would make the divergence inert rather than wrong. See `games/sonic4/player/player_climb.emp`
header and ARCH §5.4.

### Solid object tops are floors for every player state — user principle + S3K divergence — 2026-08-12
**Surfaced during:** Knuckles C4, glide landing on the `TestSolid` platform.
**The ruling (user):** "a solid object's top is a floor and should behave like one" — for
EVERY player state, not just the standing ones. A glide landing on a platform must slide
exactly as it does on flat terrain.
**Status:** HOLDS TODAY across the glide family; recorded so a new airborne state does not
silently break it. Our solid handler (`engine/objects/collision.emp` `.solid_top`) clears
ST_IN_AIR and sets ST_ON_OBJECT **without touching the player state**, so each AIRBORNE
state must observe the bit itself or it keeps running its airborne body while parked on a
platform. The grounded half is enforced in one chokepoint instead: `Player_SensorFloor`'s
ST_ON_OBJECT early-out (`player_sensors.emp`) reports dist 0 / angle 0 / solid.

| State | On a solid-object top | Correct per the principle |
|---|---|---|
| GLIDE | `.on_object` → angle 0 → flat → PSTATE_SLIDE, x_vel preserved | yes — same as its flat-terrain landing |
| GLIDEFALL | `.dead_stop` → GROUND, velocities zeroed | yes — dead-stop IS its terrain landing |
| SLIDE | floor-follow + ledge-drop via `Player_SensorFloor` early-out; drop fires at the platform edge when the bit clears | yes |
| AIR / FLY | `Air_LandOnObject` (shared conversion, gsp = x_vel) | yes |
| CLIMB | ST_ON_OBJECT = DETACH (S3K `:31052`) | yes — deliberate, S3K-faithful |
| LEDGE | no test — mid-clamber is a scripted animation | acceptable; S3K has no test either |

**DELIBERATE S3K DIVERGENCE.** Stock S3K does NOT slide on a platform. Every solid object
routes the landing through `RideObject_SetRide` (`:42047`), which does `bclr
#Status_InAir` and calls `Player_TouchFloor` → `Knux_TouchFloor` (`:32833`), zeroing
`double_jump_flag`. The glide family runs only under mode 2 (Freespace) of `Knux_Modes`
(`:30473`, mode = `status & 6`), so clearing Status_InAir + zeroing double_jump_flag drops
Knuckles out of the glide state machine entirely — he stands up. S3K's glide never tests
Status_OnObj at all (the only two tests in the player region are the climb's detach
`:31052` and the standing/push code `:31805`); the object acts on the player from outside.
Worth noting S3K does not dead-stop him either — `RideObject_SetRide` preserves speed via
`move.w x_vel(a1),ground_vel(a1)`, landing him RUNNING at glide speed.
**When to revisit:** when a new airborne state is added — it must test ST_ON_OBJECT and
route to its own terrain-landing outcome, or it will glide-on-platform.

### Ability agency — cancels and re-entry (the C4 follow-up parcel) — 2026-08-12
**Surfaced during:** Knuckles C4 playtest; the user endorsed prototyping these.
**Status:** DESIGN + PROTOTYPE, not started. Today an ability is committal: once in
flight or a glide there is no voluntary exit but the terminal one. The parcel:
- **Tails: flight cancel** — proposed input down+jump, dropping to a normal fall.
- **Knuckles: re-glide from `PSTATE_GLIDEFALL`** on a fresh jump press, so a bailed
  glide is recoverable instead of a committed drop (S3K does not allow this).
- **Ball-cancel variant behind a DEBUG flag** for feel-testing only, so the two
  candidate feels can be A/B'd on hardware-accurate playback before either ships.
**USER RULING already given:** a cancel lands the player in the **vulnerable fall**
by default (not a curled/invulnerable ball) — the cancel buys agency, not safety.
**When to revisit:** next player-feel parcel. All three are gated on nothing.

### Slope standstill: mirror-symmetry option (abs-before-shift) — 2026-08-12
**Surfaced during:** the "Knuckles drifts off a ledge at rest" investigation, which
closed as AUTHENTIC — our `Player_SlopeResist` matches S3K clause for clause
(standing gate `|factor| >= $D`, `PHYS_SLOPE_WALK $20`, byte-identical sine table).
**Status:** OPTION, needs the user's call. `asr` floors toward −∞, so at 22.5° the
factor is −13 one way and +12 the other: the same slope drifts in one orientation
and holds in its mirror. Exactly **four angles** in the table are decided by this
rounding asymmetry — `$90`, `$91`, `$EF`, `$F0`. The minimal fix is to take the
absolute value BEFORE the shift (`(|sin|)>>3` instead of `|sin>>3|`), which leaves
every symmetric case bit-identical and only affects those four.
**Cost:** it is an S3K divergence and touches shared ground physics, so it needs a
**replay-fixture re-record** (the Sonic fixtures hash the player window).
**When to revisit:** only on a user ruling that mirrored slopes must behave alike.

### Glide / slide / climb SFX are unwired placeholders — 2026-08-12
**Surfaced during:** Knuckles C4.
**Status:** TODO markers at the code. S3K plays `sfx_Grab` ($4A) at the wall catch,
`sfx_GlideLand` ($4C) on the fall landing, and `sfx_GroundSlide` ($7E) every 8
frames while sliding. None exist in our SFX bank yet, so all three sites are
silent with a `TODO(user)` note. Sourcing audio is the **user's** decision.
**When to revisit:** when the user sources the audio; the call sites are already
in place and each is a one-line add.

> **Correction (2026-08-13, character lens sweep, seat A2).** This entry used to
> close with "(the same reason Tails' flight SFX `$BA`/`$BB` are unwired)". That
> was FALSE and has been removed: Tails' flight SFX **are** wired.
> `Fly_TickSfx` (`games/sonic4/player/player_fly.emp:368-381`) plays
> `SFXID_FLYING` / `SFXID_FLY_TIRED` on S3K's 16-frame cadence behind an
> on-screen gate and tail-jumps `Sound_PlaySFX`; `PState_Fly` step 1b calls it.
> `player_fly.emp:16` carried the same false claim ("the three deliberate
> deviations ... and the unwired SFX" — there are two) and is corrected in the
> same pass. A stale "unwired" entry in the doc every planning phase reads first
> is how finished work gets redone.

### REMOVABLE SCAFFOLDS currently in the tree — 2026-08-12
**Status:** live, deliberately. Remove before ship.
- ~~**DEBUG glide test platform** (`4ea60239`)~~ **REVERTED at the merge ritual
  (2026-08-12).** It was 8 `ObjDef_Solid` blocks in OJZ sec0 at x960-1088, top
  y=208, 48 px above the y=256 surface, added because the shipped sec0 solid is
  untestable by construction (16×16, top only 8 px above the surface, crossed in
  ONE frame by a 16 px/frame glide). It did its job — the ruled glide→SLIDE
  behaviour was verified on it and BUG 10 withdrawn — and then the strict suite
  caught why it cannot stay: DEBUG-gating made `entity_data` 48 bytes longer in
  the debug shape, and the harness enforces `debug_len == plain_len` for every
  ported section (`sigil crates/sigil-cli/tests/ojz_run_a_port.rs`). Level DATA is
  expected to be shape-identical, so a **DEBUG-only ENTITY is not expressible**;
  the ungated alternative would have changed release bytes. The invariant was kept
  and the scaffold reverted. TO RE-ADD TEMPORARILY: put the 8 records in
  `data/editor/ojz/act1/section_0.objects.json` so they land in BOTH shapes, run
  `tools/regenerate-level.sh`, and revert before merging — geometry and the
  approach recipe are preserved in the note block in `tools/ojz_entity_gen.py`.
- The replay fixtures and the DEBUG-only object-test scene are permanent test
  infrastructure, NOT scaffolds — do not remove those.

### Min-penetration-axis may misclassify fast-horizontal contacts — 2026-08-12
**Surfaced during:** BUG 10 (withdrawn — the reported case was three measurement
errors, not engine behaviour).
**Status:** DOCUMENTED, not observed in practice. `Touch_Solid` picks the contact
face by minimum penetration axis (`pen_x` vs `pen_y`). A player moving fast
horizontally and slowly vertically — a glide is 16 px/frame against 0.5 px/frame —
can first overlap a narrow platform at its leading EDGE with a tiny `pen_x`, which
classifies as a SIDE hit (push + `clr.w x_vel`, a stall) rather than a top landing.
Whether it bites depends on sub-pixel phase and platform width; on the 128 px test
platform the top landing is reliable, and the ruled glide→slide behaviour was
**verified working on an object top**. A narrow platform plus a fast approach is
the risk case.
**When to revisit:** if a stall-on-edge is ever seen in real level geometry. The
fix direction would be a swept/previous-position test rather than a static AABB —
a shared-collision change needing the user's ruling, not a local patch.

### Cycle Profiler (§8.5) Not Wired — Frame-Budget Measured via Lag Counter — 2026-06-14
**Surfaced during:** §5 Task 10.4 frame-budget pass.
**Status:** The §8.5 raster-bar / lagometer cycle profiler is NOT built.
> **⚠ PARTIALLY CORRECTED 2026-08-05 — the "written NOWHERE" claim is a FALSE NEGATIVE.**
> The `Prof_*` block **IS** written, in `games/sonic4/test/object_test_state.emp:158-195`
> (`Prof_RunObjects`, `Prof_Peak_RunObjects`, `Prof_TouchResponse`, `Prof_Peak_Touch`,
> `Prof_RenderSprites`, …) — landed all the way back in `739143f` (2026-04-25, "combined
> integration + stress test scene with profiling"), i.e. it was already wired when this entry
> was written. What is true is narrower: **the counters are unwired in OJZ gameplay**, which is
> the state the original live read at `0xFF89FC` was measuring. The headline claim ("declared but
> written NOWHERE") is wrong; the conclusion (no profiler on the gameplay path) survives.
> The §8.5 raster-bar/lagometer presentation layer is genuinely not built.

Original text: The
`Prof_*` RAM block (`ram.asm`: `Prof_RunObjects`/`Prof_TouchResponse`/
`Prof_RenderSprites`/`Prof_FrameTotal` + their `Prof_Peak_*`, DEBUG only) is
declared but written NOWHERE — confirmed live: all sixteen bytes at
`Prof_RunObjects` (0xFF89FC) read zero during active gameplay. This matches
spec §9 item 10's own note ("the §8.5 profiler is not built yet").
**Measured instead** via the wired `Lag_Frame_Count` (0xFF89F8, incremented in
`VInt_Lag` whenever the main loop misses VBlank): with the player active on OJZ,
**steady-state gameplay = 0 lag frames over 120 frames** (full game loop —
player physics + camera + render — completes within the ~224-line NTSC
active-display window before VBlank). Spindash launches at $7FA gsp added zero
lag. The only lag observed (+13 frames over a 250-frame run that crossed
terrain) was section-streaming art DMA during teleport/preload — amortized
deferrable DMA by design, not the per-frame player cost. The Task 10 camera
additions (landing lock + spindash freeze) are a few byte-tests + branches,
~10-20 cycles/frame, negligible.
**When to revisit:** Build the real cycle profiler if a future workload (dense
badnik + multi-part boss + heavy parallax) starts producing steady-state lag
frames; until then the lag counter is a sufficient pass/fail budget gate.
**See:** `docs/superpowers/specs/2026-06-12-player-system-design.md` §9 item 10.

### Removed Up-Velocity Cap — Launch-Cap Coupling (§2.1 FEEL DEVIATION) — 2026-06-12
**Surfaced during:** §5 Task 6/7 (commit 04b492b region).
**Status (intentional, shipped):** the classic non-jump airborne up-cap (`y_vel`
clamped to `-$FC0`) is **removed**. Launches are instead bounded by
`PHYS_GSP_CAP = $1000` (the SPG-placement ground-speed tunneling guard). The
`; FEEL DEVIATION` comment lives at the clamp site in
`engine/player/player_air.asm` (`PState_AirShared`, after the fall-cap).
**Coupling — do NOT change in isolation:** if launches ever feel truncated, the
knob is `PHYS_GSP_CAP`, and raising it is a **coupled** change. These must rise
together or the player will outrun streaming / tunnel through geometry:
- `CAM_MAX_Y_STEP` (16 px/frame, the camera-follow clamp the fill relies on),
- `VFILL_ROWS_PER_FRAME` (2 rows/frame — the VBlank-bound streaming contract;
  >2 overflows VBlank into active display, see §4.7),
- the 32px sensor reach (swept collision must cover one frame's travel).
Do not re-add the `-$FC0` cap silently. The separate `$FC0` cap in the
steep-landing conversion is a different, retained mechanism.

### Fall cap `PHYS_FALL_CAP = $1000` — S3K deviation, PARKED with a known 1px hole (§2.1 FEEL DEVIATION) — 2026-08-03
**Surfaced by:** Volence noticed falls feel slower than S3K. Researched + parked
the same day ("doesn't seem like something I want to get into right now") — this
entry exists so the analysis is not re-derived. Sibling of the up-velocity-cap
entry above; the two share the same coupling set.

**Provenance (settled — do not re-litigate from precedent):**
- **S3K has NO fall cap.** `MoveSprite` adds `#$38` to `y_vel` and returns, no
  clamp on the path (`skdisasm/sonic3k.asm:36041`). **S2: none** either.
- **S.C.E. DOES cap at `$1000`** (`Objects/Players/Sonic/Sonic.asm:435-437` air,
  `:508-510` jump) — and our line is a clone of S.C.E.'s, NOT a Sonic-CD import.
- **S.C.E.'s cap has no documented rationale.** Git-archaeology (2026-08-03): it
  was added in `8c6e438` "Big March update" (2024-03-09), a 92-file /
  4,535-insertion omnibus whose message says only "Objects optimization and
  fixes / New level loading header / Other fixes". The lines carry NO comment,
  though every neighbouring velocity clamp in the same routine is commented
  (`; limit upward y velocity exiting the water`, `; reduce gravity by $28`).
  No README/changelog mentions it. The one plausible motive — that it
  accompanied that commit's level-loading/size rework — was checked and does NOT
  hold (those diffs are whitespace-only). **Conclusion: S.C.E. is not evidence of
  an engineering rationale; any future argument for capping must stand on our own
  measured constraints below.**

**Our constraints (these ARE real, and they are ours, not inherited):**
- *Axis A — thin-floor tunneling (camera-irrelevant).* The probe examines two
  16px cells, so max safe per-frame Y step = `min_floor_thickness − 1`. OJZ act 1's
  thinnest floor is 16px → **safe step = 15px**, and 224 pixel-columns are that
  thin. **The shipped `$1000` (16px) is therefore ONE PIXEL HOT**: a frame ending
  with feet exactly on a 16px slab's surface (dist 0 → `bpl .no_land`) plus a full
  16px step skips the slab. Needs 577px of prior fall + exact alignment, so it is
  narrow but real, and it is in the shipped build today.
- *Axis B — collision residency (camera-coupled).* Collision reads
  `Tile_Cache_Collision`, an 80×30-cell RAM ring bounded by `Cache_Top_Row`/
  `Cache_Bottom_Row` which follow the camera; outside it every probe returns air
  (`engine/level/collision_lookup.emp:47-56`). Cells arrive only by decompressing
  block streams (`tile_cache.emp:365-375`) — there is NO directly-indexable
  collision map in ROM. **This is why S3K gets uncapped falls for free and we do
  not: S3K's layout is fully RAM-resident, so its collision is camera-independent.**

**Why a taller collision band is NOT the answer** (asked + answered 2026-08-03):
the band buys a fixed reach, but under gravity the player↔window gap grows
quadratically, so safe fall distance grows only as ~√(band size):

| slack below player | total fall before collision blackout |
|---|---|
| ~188px (today) | ~1,450px |
| ~700px (2× band) | ~2,560px |
| ~1,400px (4× band) | ~3,790px |

Quadrupling RAM buys 2.6× the fall. Fine as margin, cannot be load-bearing —
and it gets weaker exactly as levels get taller (cf. the mega-act goal).

**If it is ever picked up, the real shape is:**
1. **Swept / sub-stepped vertical movement** in `PState_AirShared` (move
   `min(STEP, remaining)` with `STEP <= min_floor_thickness − 1`, probe, repeat).
   Unavoidable for Axis A; cycles are affordable (~8 probes/frame at 48px/f vs 2
   today) — the cost is semantic: class dispatch, wall probes, `jump_headroom`
   consumption and quadrant forcing all currently assume one move per tick.
2. **Speed-scaled vertical fill** for Axis B — raise fill rate with fall speed
   rather than raising the fixed budget. Attractive because a vertical plunge is
   when horizontal streaming is otherwise idle, so the block-decompression budget
   is mostly unspent — **premise unverified, check it before betting on it.**
   Alternative (more expensive): raise `CAM_MAX_Y_STEP` + `VFILL_ROWS_PER_FRAME`
   together, which is the §4 streaming budget.
3. Housekeeping: `player_common.emp:662`'s `ensure(PBOUND_BOTTOM_MARGIN > ...)`
   references the constant and must be re-expressed if it is removed; import
   lists in `player_air.emp:12` / `player_common.emp:25`.

**Cheap option available anytime (NOT taken — user parked the topic):** set
`PHYS_FALL_CAP = $0F00` (15px/f). One-constant change, closes the Axis-A hole,
imperceptible in feel (only reached after ~540px of fall; the act's deepest
floor-terminated drop is 592px). Strictly safer than today.

**Micro-optimisation dead end (checked, do not retry):** the clamp cannot be
replaced by a bitwise op. `ori`/`andi`/`bclr` give WRAP, not saturation —
`andi.b #$0F` on the high byte turns `$1000` into `$0000`, producing a mid-air
sawtooth. Saturation needs a comparison. Branchless forms lose on 68000 (no
conditional move; shifts cost 2 cycles/bit): sign-mask ~68 cyc, `Scc`+merge
~30 cyc, vs 18 for the current `cmpi.w`+`ble`. We already clamp in a register
(S.C.E. clamps in memory, twice — we have ONE site because `PState_AirShared`
is shared). Best remaining win is 2 cycles by inverting the branch; not worth it.

### §5 Deferred Items — Player/Character Follow-Up Work — 2026-06-14 (updated 2026-06-15)
**Status:** §5 (player-system branch) shipped Sonic-only, physics-first, on OJZ
with real collision, the full sensor layer, ground/air/roll/spindash, the loop,
and camera landing lock + spindash freeze. feat/sonic-animations added the full
animation set, speed-scaled timing, and shared spindash. Per spec §1, the
following are deliberately **deferred to follow-up plans** (not bugs):
- ~~**Sonic art / animation / DPLC** — a real sprite set + animation driver beyond
  the placeholder test art.~~ **DONE (feat/sonic-animations):** full ANIM_* contract
  (11 ids, build-time assert), `Player_Animate` read-only classifier, `DUR_DYNAMIC`
  speed-scaled timing in `AnimateSprite`, shared spindash in `player_spindash.asm`,
  `Player_AtLedgeEdge` balance probe, DEBUG anim viewer. Sonic's sprite art DATA is
  the real CUSTOM Sonic set migrated from sonic_hack (`art/optimized/characters/sonic.bin`,
  mappings + DPLC; frame-index layout follows the S2 convention, but the pixels are
  our custom design — NOT stock S2). Still provisional is the VRAM SLOT —
  `VRAM_TEST_SONIC` is a hand-placed test slot, not yet allocated via the build-time
  ~~graph-color allocator~~ (separate art-pipeline task).
  **⚠ CORRECTED 2026-08-05: there is no graph-color allocator.** DSATUR/`color_sections`/
  `compute_adjacency` have zero hits tree-wide; the allocator was superseded by the
  globally-deduped paged act pool (2026-06-22) and removed in the Phase-3 cleanup. The slot is
  still hand-placed and still provisional — but whatever allocates it later, it will not be a
  graph colorer. See the corrected "Build-time Graph Coloring (§2.3)" entry.
- ~~**Spindash shared across all 3 characters** — `PState_Spindash` was in
  `sonic.asm`, blocking Tails/Knuckles.~~ **DONE (feat/sonic-animations):** relocated
  to `engine/player/player_spindash.asm`; resolves `ANIM_SPINDASH` per-character via
  the `ANIM_*` contract. `sonic.asm` now holds only `Sonic_InitAssets`, `Sonic_LoadArt`,
  `PhysTable_Sonic`.
- **In-game get-up trigger** — `ANIM_GETUP` (id 10) is defined and viewer-visible
  but nothing arms it in gameplay. A future pass needs the "just landed after a hurt"
  state to write `ANIM_GETUP` into the classifier path (or a dedicated PSTATE).
  **⚠ NARROWED 2026-08-05 — most of this shipped; only the ARMING is missing.** The classifier
  path the entry asks for **exists**: `PlayerV.getup_timer` is a real field
  (`games/sonic4/player/player_common.emp:84`), it is cleared at init (`:209`), and `:488-492`
  already runs the one-shot — `tst.b getup_timer` / `subq.b #1` / `move.b #ANIM_GETUP, anim(a0)`.
  What is missing is **the writer**: nothing sets `getup_timer` non-zero, because no hurt/landing
  state exists to set it. So this is not "build the get-up trigger" any more, it is "when damage
  ships, poke one byte". Fold it into the shields/damage work rather than planning it separately.
- **Duck / look-up camera pan** — duck and look-up are display conditions computed
  each frame (no new PSTATE); the camera-pan half is NOT implemented. The field
  ~~`_pl_look_offset`~~ is reserved as a zero-valued seam in the `PlayerV` SST overlay
  for the future pass that wires this up.
  **⚠ ANCHOR CORRECTED 2026-08-05:** the field is `PlayerV.look_offset`
  (`games/sonic4/player/player_common.emp:86`, `// camera look/duck pan seam — stays 0 this
  pass`), cleared at `:210`. `_pl_look_offset` has **zero hits** tree-wide — that name never
  survived the port. The substance is unchanged: the seam exists, still zero, still unwired.
- **Balance threshold tuning** — `LEDGE_NO_GROUND` in `player_sensors.asm` is
  flagged as tunable; the current value is a first estimate.
- **Dropdash, instashield** — Sonic move-kit extensions.
- **Super Sonic** — transformation, palette cycle, physics row.
- **Tails** — CPU AI (4-state machine) + position-history-buffer following (the
  `Player_Pos_Ring`/`Player_Stat_Ring` are already recorded for this) + the
  twin-tail appendage child object. **Flight physics are DONE** —
  `games/sonic4/player/player_fly.emp` (`PSTATE_FLY` + `Ability_TailsFlight`,
  S3K-exact bar three flagged deviations); until the appendage object lands, the
  flight pose draws the body without its spinning tails, and the flight SFX are
  unwired because S3K's `$BA`/`$BB` are outside the imported SFX id range.
- ~~**Knuckles** — gliding, climbing, wall detection.~~ **DONE (feat/knuckles-c4,
  2026-08-12):** all five states ship — `PSTATE_GLIDE` / `GLIDEFALL` / `SLIDE`
  (`player_glide.emp`) and `CLIMB` / `LEDGE` (`player_climb.emp`), entered through
  the single `CharDef_Knuckles.cd_ability` → `Ability_KnuxGlide` pointer, plus the
  glide wall-catch. Structure and numbers are S3K's, with two user-ruled
  divergences recorded separately below (the 1..3 px climb recess tolerance; solid
  object tops as floors). Oracle-verified: wall-catch → climb → ledge top-out →
  stand, climb-down landing, glide-land → slide (~440 px travel, dust trailing),
  and slide-off-a-solid → ledge-drop → GLIDEFALL. Remaining Knuckles gaps are the
  SFX placeholders and `Disable_wall_grab` (both tracked separately).
- ~~**Per-character dispatch-table indirection** — the prerequisite refactor for
  Tails/Knuckles.~~ **DONE (character-dispatch C1, merged 2026-08-12):**
  `CharacterDef` (`engine/structs.emp`) is the ROM record and `Player_Chardef` the
  resolved cache; `Player_Init` does the ONE roster resolve. The proof it worked is
  that C4 added a whole third character — five states — with **zero** engine
  changes and no `Character_ID` test anywhere in the frame: one record field and
  two modules. See `ENGINE_ARCHITECTURE.md` §5.4.
- **Shields + damage + loss-rings** — shield objects, hit/invuln response, ring
  scatter (loss-rings is also tracked under §4.9).
- **Water** — and with it the **per-section physics modifier / Lerp system** (the
  RefreshPhysics plumbing shipped with an identity modifier; the modifier tables,
  section references, and boundary Lerp are the deferred half — see
  `ENGINE_ARCHITECTURE.md` §5.2).
- **6-button mappings** — X/Y/Z/Mode gameplay actions (detection exists, §5.1).
- **Forced-roll objects (S-tunnels)** — bypass the roll-start gate, use
  `PHYS_ROLL_FORCE_MIN` at rest; the `stick_convex` full-adherence flag and the
  roll-start gate already have the hook comments.
- **The §8.5 cycle profiler** — unwired (see the Cycle Profiler entry above).

---

## From §1 — Core VDP Pipeline

These subsystems are fully designed in ENGINE_ARCHITECTURE.md §1 but require other systems to exist first.

### Plane_Buffer "complete" guard — TRIED + REJECTED (not viable) — 2026-06-23
**Surfaced during:** continuous-scroll Phase 2 Task 6 gate (the diagonal-corruption fix, commit `b96c861`).
**Status: REJECTED.** Built + oracle-tested on branch `feat/plane-buffer-complete-guard` (commit `fb81809`, left UNMERGED for inspection). The idea was: add a `Plane_Buffer_Complete` flag set after the fill phase, gate `VInt_DrawLevel` on it, and re-add the drain to `VInt_Lag` so lag frames drain a *completed* buffer (killing the sustained-lag stutter) without the mid-fill tear. It IS corruption-safe (diagonal stayed clean across the corner), **but it is a net regression, not an improvement, for two reasons:**
1. **Plane/sprite desync.** The plane buffer completes at `Section_UpdateColumns` (ojz_scroll_test.asm:179) but the sprite table completes later at `Render_Sprites` (:188). A lag-frame drain firing in the window [179,188] commits NEW planes while the sprite table in VRAM is still LAST frame's → the world scrolls one frame ahead of the player sprite. The only desync-free drain point is "whole visual frame complete" = `VBlank_Ready` = exactly `VInt_Level` — i.e. there is NO safe lag-frame drain that also keeps sprites in sync, so the guard cannot deliver its benefit.
2. **+~10% lag.** Re-adding the drain to `VInt_Lag` extends the VBlank handler, stealing main-loop time and pushing borderline frames over: sustained-max-diagonal went 76% → 86% lag (measured).
**Conclusion:** `b96c861`'s whole-frame-defer is the CORRECT design — on a lag frame the screen shows the last *coherent* complete frame (planes+sprites together), which is the classic behavior; the "stutter" is just the framerate drop, not a fixable drain-timing artifact. The real lever for the sustained-diagonal lag is the **diagonal streaming budget** (below), not drain timing. Delete the branch if not inspecting.

### Diagonal streaming budget — ~76% lag at sustained MAX diagonal (§4.7 / §1.1) — 2026-06-23
**Surfaced during:** continuous-scroll Phase 2 Task 6 diagonal stress (PRE-EXISTING — master shows the same lag).
**Status (UPDATED 2026-08-09 — patch-run batching shipped, `perf/patchrun-batch`):** The
per-word `PageCache_PatchWord` primitive (movem-bank + jsr/rts per WORD, ~166 cycles of
bracket overhead before any work — 160 words/frame ≈ 19% of frame at terminal fall) was
replaced by `PageCache_PatchRun_Seq`/`_Col`: one register bank per RUN, map/Page_Table/
Page_Frames hoisted per run, the (only-caller) Ref/Unref bodies inlined per word. Identical
per-word semantics (capture-old-before-write, ref-new-then-unref-old, miss = Request +
stall + skip + continue); DEBUG per-frame refcount audit green through full-map churn.
Measured A/B (oracle, deterministic input replay, OJZ act1):
- **VERTICAL max fall (user-reported "BG slows where FG chunks draw"): FIXED.** Baseline
  had clustered bursts on dense strips — worst 5 lag/30 frames (17%, camera dropped 80px of
  travel that half-second). New: the same strip runs 0 lag at full 480px/chunk; whole-map
  fall 7 scattered lag frames (~1.9%), worst chunk 2/30.
- **Dense-region MAX diagonal (from spawn): improved, still saturating.** Position-matched
  traverse to camera ~1100: 54 lag/120 frames (45%) → 29 lag/90 frames, traverse 25%
  faster wall-clock. Worst dense strips still hit ~40-47% during their crossing.
**The remaining diagonal residual is unchanged in kind** — `TileCache_FillColumn`'s
per-cell copy + `Draw_TileColumn`'s nametable draw at 16px/f (2 cols/frame), plus the
per-line HScroll + BgAnim flat taxes. That is the "horizontal Wave-1 that never happened"
(the FillColumn/Draw_TileColumn hoist+SR, domain-split in campaign-gap-ledger) — now the
top lever on this line item.
**Measured 2026-08-09 (post-batching, oracle profiler, 60-frame average at max
diagonal from spawn, canonical DEBUG):** total frame 127,962/128,000 cycles —
**~100% budget, zero headroom** (lag 0 only because the window preceded the dense
strips; they tip it over). Decomposition of the fill half:
`Tile_Cache_Fill` 72.8k incl (56.9%) = `FillRow` 35.9k + `FillColumn` 28.9k, inside
which `CopyBlockColumn` 20.9k (8 calls, ~2.6k/call — the per-cell copy),
`PatchRun_Seq` 18.6k (11 calls) + `PatchRun_Col` 13.7k (10 calls) (the already-
batched patch cost, M-1-endorsed), `FindStagedBlock` 9.3k (24 calls, ~387/call),
`DecompressBlock` 3.4k (prefetch doing its job). Draw side: `Draw_TileColumn` 5.1k
+ `Draw_TileRow_FromCache` 3.3k. Flat taxes unchanged (HInt 10.8k = 8.5%,
`Parallax_Update` 6.8k, `Section_UpdateColumns` 9.6k).
**Hoist parcel scope (queued):** the copy chain (`FillColumn`/`FillRow` →
`CopyBlockColumn` → per-cell) carries ~50k/frame against the batching precedent —
same shape as patch-run: bank once per column/run, hoist the stage-slot resolve
out of the per-cell path (`FindStagedBlock`'s 24 calls/frame include repeat hits
on the same staged block), and fold the draw's nametable recompute. The P2-merge
revisit condition of the 2026-08-05 owner ruling is now met.
> **BUILT AND MEASURED 2026-08-10 — the premise above is WRONG.**
> `perf/fillcol-hoist` (T1-T5) shipped every lever in that scope and produced
> **NO measurable lag win** (3×90-frame diagonal: baseline 209 ticks/61 lag →
> candidate 207 ticks/63 lag, same 15.9 px/tick) for **+430 B ROM / +138 B RAM**.
> Correctness was clean (both replay fixtures hold with all checkpoint hashes
> matching, refcount audit green, patch runs unchanged within noise), and two
> attributable wins are real but ~1k/frame combined: `Draw_TileColumn` −14%
> (T1's gather unroll) and `FindStagedBlock` 13→11 calls (T5's memo).
> **So the copy chain's call/hoist overhead is NOT the top lever on this line
> item** — the residual is the flat decompress + patch-run + HInt taxes the
> parcel deliberately did not touch.
> **OWNER RULING 2026-08-10: take the clean win, park the rest.** T1 (the
> `Draw_TileColumn` gather unroll — the one unambiguous measured win, -14% on
> that routine, +42 B, no RAM) is cherry-picked to master as `e1367aee`
> (sigil chain 87), gated with both replay fixtures holding. T2-T5 stay on
> branch `perf/fillcol-hoist` (tip `118c184a`) as parked research: built,
> green and correctness-gated, but not worth +388 B / +138 B RAM for no
> measurable lag movement. **Do not delete that branch.** Pick-up notes +
> the re-measure prerequisite:
> `docs/research/2026-08-10-diagonal-scroll-research-parked.md`. Full evidence:
> `docs/superpowers/notes/2026-08-10-fillcol-hoist-ab.md` (+ `-baseline.md`).
> Method caveat for any re-measure: fixed-FRAME windows drift in content
> (the candidate hit ~+3.1k more cold decompress), so drive to a fixed
> camera-X and count frames instead.
**Status (UPDATED 2026-07-16 — unified prefetch shipped):** Sustained MAX diagonal now runs **~42% lag** (oracle, 8/19 frames), down from the ~76% below. The unified direction-aware prefetch (H1 column scan + H2 corner + H3 hysteresis + H4 trailing-lag gate + H5 16 slots + H6 base-lea hoist, `feat/unified-prefetch`) removed the cold-crossing DECOMPRESS spike (A/B: sustained-max-horizontal 44→27 lag, ~40% cut). **The residual is now COPY/DRAW-bound, not decompress** — `TileCache_FillColumn`'s per-cell copy + `Draw_TileColumn`'s nametable draw at 16px/f (2 cols/frame) exceed budget regardless of decompress. That is the "horizontal Wave-1 that never happened" (the FillColumn/Draw_TileColumn hoist+SR, domain-split in campaign-gap-ledger). The pre-prefetch analysis below stands as the decomposition of the remaining fill cost.

**Ruling (owner, 2026-08-05): MARK AND REVISIT — stays OPEN.** Neither accept the dip (A) nor spend on it yet; do **not** silently take (A) despite the recommendation below. Revisit alongside art-streaming Phase 2 (whose budget model touches the same frame window) or when a level actually plays at sustained max diagonal. Full ruling text: "Owner rulings, 2026-08-05" near the bottom of this file.

**Original (pre-prefetch) status:** Sustained MAX diagonal scroll (both axes at CAM_MAX=16px/frame) runs ~76% lag frames (genuine fill cost, not corruption — that's fixed). Profiler: Tile_Cache_Fill ~25% (FillRow+FillColumn+Decompress) + HInt ~24% + Process_DMA_Deferrable ~18% + parallax ~14%. The zero-slack contract `CAM_MAX_Y_STEP == VFILL_ROWS_PER_FRAME*8` was sized for SINGLE-axis motion; diagonal runs BOTH column-fill and row-fill against the shared `BLOCK_DECOMP_BUDGET=6`, roughly halving the effective per-axis budget.
**What:** Investigated 2026-06-23 (read-only profiler + code analysis). The cost is dominated by ESSENTIAL work with no significant redundancy — there is NO clean safe fix:
- `Tile_Cache_Fill` ~25% — column-fill (X) + row-fill (Y) both run, sharing `BLOCK_DECOMP_BUDGET=6`. Corner cells are NOT double-decompressed (`TileCache_FindStagedBlock` hits the staging slot). Clean.
- VBlank/"HInt" ~24% (vs ~4.6% stationary) — the **per-line HScroll DMA**: 896 B/frame (vs 112 B per-cell) queued by `Enqueue_Dirty_Buffers`, drained by `Process_DMA_Critical`. NOT for a shimmer (OJZ's `deformBg=DeformTable_Zero` is all-zeros — no deform); it carries the 4-band BG parallax AND deliberately works around a **live VDP `$0B` shadow→register propagation bug** (see the per-cell entry below). This ~20%/frame is a FLAT tax (same stationary or scrolling), so it's the single biggest lever — but NOT capturable by a config flip (proven below).
- `Process_DMA_Deferrable` ~17.5% — `BgAnim` animated-tile-band DMAs (+ any DPLC); already step-gated, all essential.
- `Parallax_Update` ~7.4% — per-line deform fill; essential.
Safe wins are small AND mostly DON'T help diagonal: an HScroll-DMA dirty-gate is near-useless here (the deform phase animates EVERY frame → buffer always dirty); skipping parallax Step-4a when vscroll is unchanged (~2%) only helps horizontal-only. So a real reduction needs a FEEL/VISUAL tradeoff — the user's call: **(A) accept the dip** (it's gameplay-rare — sustained MAX diagonal across corners; brief diagonals recover instantly; classic Sonic also slows under extreme load); **(B) lower `CAM_MAX` on diagonal** (detect dual-axis motion, cap the combined step — camera follows slightly slower); or **(C) cut non-essential BgAnim bands / parallax deform during fast scroll** (lose some visual flourish). Do NOT raise `CAM_MAX_Y_STEP` 16→24 (diagonal already saturates). Recommendation: (A) accept for now; revisit with (B)/(C) only if aggressive diagonal traversal becomes a design requirement.

### Per-cell HScroll (~20%/frame) — NOT ACHIEVABLE (per-cell can't do pixel-precise band boundaries) — 2026-06-23
**Surfaced during:** diagonal-budget investigation (the per-line HScroll DMA is the biggest single flat cost).
**Status: CLOSED — not achievable for OJZ's parallax.** Root-caused on hardware (VDP-register read, 2026-06-23). The chain:
- **`$0B` is NOT the problem.** With `deformBg` dropped, the VDP register `$0B` reads `$02` (`hscroll_mode: cell`) correctly — per-cell IS active and the shadow→register propagation works fine. The original `DeformTable_Zero` comment's "intermittent `$0B` stuck at `$03`" explanation was a **MISDIAGNOSIS**; a flush-side latch-reset "fix" (`Flush_VDP_Shadow`) was tried and changed nothing (branch `fix/vdp-mode3-propagation`, deleted).
- **The real cause is band-boundary precision.** A BG parallax band's on-screen boundary = `band_top_plane_row*8 − BG_vertical_scroll`. With smooth per-pixel vertical parallax (`vFactorBg`), those boundaries land at ARBITRARY screen lines (measured the per-line table putting one at **line 22**). Per-cell mode can only change scroll at 8-px cell-rows (lines 0,8,16,24…), so it rounds line 22 → 16/24, misaligning each band by up to 7 px → the FG/BG **tears at every band boundary during scroll** (user-confirmed at Cam `$02D0,$019D`; reproduced in free-fly).
**What:** Nothing — per-line (`DeformTable_Zero`) is mandatory for smooth banded vertical parallax and stays. The only way to use per-cell would be to give up smooth vertical scroll (chunky 8-px-stepped vscroll), which is not worth ~20%. Do NOT re-attempt the per-cell switch. Lesson: a settled/at-rest frame HIDES scroll-time tearing — verify under continuous motion ([[feedback_verify_during_motion]]), and read the actual VDP register before theorizing about propagation.

### ✅ STALE/CLOSED — Parallax fill — computed-jump-table unroll (§4.6 perf) — 2026-07-14 — **closed 2026-08-09: the unroll already shipped**
> **2026-08-09 reconciliation:** the premise is stale — `Parallax_Fill_PerLine`'s flat
> (constant-span) path is ALREADY 8×-unrolled (`.lp_flat`: span is always a multiple of 8
> because band tops are cell rows ×8, so eight `move.l d0,(a4)+` per `dbf`). Measured
> (oracle profiler, max fall): the whole per-line fill runs ~3.9k cycles ≈ 3.1% of frame —
> which is exactly the all-flat cost, i.e. OJZ's zero-deform bands already take the cheap
> path and the "224-iteration move.l/dbf with ~2,200 cycles of dbf overhead" this entry
> targeted no longer exists. Remaining micro-levers, noted for completeness and NOT worth
> their complexity today (~0.5% of frame): movem.l 8-register broadcast fill for flat bands
> (Gunstar Heroes precedent, `disasm.asm:4268` — 32 bytes/instruction, ~9.3 c/long vs 12)
> and Batman-style computed-entry unrolled deform bodies for the sampling paths (which OJZ
> does not currently hit). Reference survey: 2026-08-09 fast-copy/fill research pass
> (Batman/Gunstar/Alien Soldier/Ristar findings recorded in the git history of this entry's
> closing commit).
**Surfaced during:** TheBlad768 survey (S.C.E. updated `DeformScroll`, unreleased) — see `docs/research/2026-07-14-theblad768-survey.md`.
**Original text (historical):** `Parallax_Update`'s per-line fill (~7.4% of frame under max diagonal, per the diagonal-budget profile above) runs a 224-iteration `move.l/dbf` loop; the `dbf` alone is ~10 cycles/line ≈ ~2,200 cycles/frame of pure loop overhead. Replace the constant-span inner loop with a computed jump into an unrolled `move.l d1,(a2)+` run (`jmp table(pc,d0.w)`, entry offset `(224-N)*2`) — Duff's-device style, ~448 bytes ROM per body.

### ✅ RESOLVED — BG_TILE_CAPACITY reconciliation (512 → 448) + BG_Init guard (§2 A.5) — 2026-06-23
**Surfaced during:** continuous-scroll Phase 2 Task 5 doc-sync (PRE-EXISTING cross-tool inconsistency the SAT relocation left behind).
**Status:** The SAT was relocated to $B800, making it the BG region's hard ceiling — usable BG space is $8000-$B7FF = **448 tiles**, not the nominal 512 ($8000-$BFFF, which now overlaps the SAT). The value is inconsistent across the pipeline: `tools/inject_editor_bg.py` already uses 448 (correct), but `constants.asm BG_TILE_CAPACITY` and `tools/ojz_strip_gen.py BG_TILE_CAPACITY_PY` still say 512. **PARTIALLY ADDRESSED 2026-06-23 (commit 0aab611):** `engine/level/bg.asm` `BG_Init` now CLAMPS the blob copy to `BG_TILE_REGION_BYTES` ($8000-$B7FF), so it can no longer spray into the SAT (the runtime last-line guard). OJZ is safe today (340 tiles ≤ 448). **RESOLVED 2026-06-23 (Engine Phase 3 Task 2):** both `constants.asm BG_TILE_CAPACITY` and `tools/ojz_strip_gen.py BG_TILE_CAPACITY_PY` now gate at 448; the full build passes at the tightened gate. A too-large BG blob now fails at generation (the `ojz_strip_gen.py` assert) instead of being silently runtime-clamped.
**What:** Reconcile the gate to 448 in `constants.asm` AND `tools/ojz_strip_gen.py` (the latter is auto-commit-daemon-watched — coordinate with the user, do NOT hand-edit autonomously). Add a runtime/build guard in `BG_Init` (or an AS assert) that the BG blob ≤ `VRAM_SPRITE_TABLE - BG_TILE_BASE_VRAM`, so a future >448-tile blob fails loudly instead of silently spraying into the SAT.

### ~~Editor-export Act descriptor format drift (§8 tooling)~~ — **VOID 2026-08-05 (the artifact was deleted)** — 2026-06-23
> **⚠ VOID — the file this entry is about no longer exists.** `46c2e0f` (2026-08-01, "Parcel J:
> delete the parked ojz editor exports (#25/#26/#27)") deleted the parked export directory, so
> `data/editor/ojz/act1/export/act_descriptor.asm` is gone and there is no stale descriptor left
> to drift. The entry additionally cites `main.asm:198` — **`main.asm` itself is deleted** (the
> ROM layout is now the declared sigil map, `games/sonic4/map.toml`).
>
> **What survives as real work:** the *belt-and-suspenders* half at the end of the entry — an
> assert that an emitted descriptor's size equals `Act_len`, so any future hand-written or
> re-exported descriptor fails the build instead of silently mis-parsing. That is still worth
> having and is now the only actionable content here. The exporter-rewrite half is moot until
> an exporter is rebuilt, and the direction of travel recorded elsewhere in this file
> ("editor authors JSON, BUILD generates engine format") says it should not be rebuilt in place.
>
> Historical text below.

**Surfaced during:** continuous-scroll Phase 2 final review.
**Status:** `data/editor/ojz/act1/export/act_descriptor.asm` is git-tracked but NOT in the build include graph (`main.asm:198` includes only `data/levels/ojz/act1/act_descriptor.asm`, which IS correct), and it would not even assemble as-is (e.g. a path where a symbol is expected). So it is no build/runtime risk. But it still emits the OLD Act layout: the removed `cam_min_x/max_x/min_y/max_y` 4-word camera block, no `edge_mode` byte/pad, and pre-paging art fields — mismatched to the current `Act_len=$22`. This dir is auto-commit-daemon-watched (do NOT hand-edit autonomously).
**What:** Update the editor EXPORTER tool to emit the current Act format (no cam bounds, `edge_mode` + pad, `act_art_pool_table`/`pages`) so a future regeneration can never reintroduce the obsolete layout into the build. Coordinate with the user (daemon-watched path). Optional belt-and-suspenders: add an AS assert at the `OJZ_Act1_Descriptor` site that the emitted descriptor size equals `Act_len`, so ANY drifting descriptor (hand-written or exported) fails the build instead of silently mis-parsing.

### yflip/xyflip size+link word merge in the sprite emit loop (§1.2 perf) — 2026-08-03 — **UNBLOCKED, verification-bounded**
> **2026-08-05 reconciliation:** confirmed accurate and confirmed unblocked. `size_link` is live at
> `engine/objects/sprites.emp:568`, called at `:668`; the dead-constraint note is at `:539`.
> Nothing gates the change — the entire remaining cost is **SAT byte-identity verification for the
> yflip/xyflip variants**, which is emulator work. Piggyback it on any session already doing
> SAT-level oracle checking, exactly as the entry says.
**Surfaced during:** sprites H2 quality review (parcel/bug005-sprites-player).
**Status:** H2 merged the size+link SAT write into one word write for unflipped/xflip
(~12 cycles/piece). yflip/xyflip kept the byte-wise form, but the constraint that
forced it (the front-loaded size read) died with the stream-order restructure —
`y_term(1)`'s size peek is now NON-consuming, so the merged form applies to those
variants too (~8 cycles/piece on yflip pieces).
**What:** Switch `size_link(1)` to the merged word form; verify SAT byte-identity for
yflip/xyflip (piggyback on any session that already does SAT-level oracle checking).
**See:** `engine/objects/sprites.emp` `size_link` header comment.

### Static Sub-Sprite Array — Render-Path Optimization (§1.2 / §3.5)
**Surfaced during:** §1.2 multi-sprite implementation Task 8 research (2026-04-27).
**Status:** Implementation shipped with sibling-chain walk per spec; the static-array
optimization is logged here as a real follow-up, not just research backlog.
**What:** Sonic 3K (`s3.asm:29940-30024`) and S.C.E. (`Render Sprites.asm:259-292`)
both use a **static sub-sprite array** (count + per-child X/Y/frame triplets) embedded
in parent's object data, not a sibling-pointer chain. ~10 cycles/child saved (no
null-check, tighter loop) plus simpler render-time logic. Our `sibling_ptr` chain is
already wired to `CreateChild_*` / `DeleteChildren` lifecycle, so the trade-off is:
(a) keep chain for lifecycle + duplicate to a render array (data-sync risk), or
(b) replace chain with array and refactor all `CreateChild_*` / `DeleteChildren`.
**When to revisit:** When we have a real workload showing the per-child cycle cost
matters — multi-part bosses with 6+ children, Tails-tail-style trails, formation
enemies, etc. Premature without that signal.
**See:** `docs/research/sprite-system-§1.2.md` Task 8 for the cross-engine evidence.

### ~~Sprite Rendering Pipeline (§1.2)~~ — DONE 2026-04-27
**Completed in:** §1.2 sprite-system multisprite + piece-overflow plan
**What:** Most §1.2 features (two-phase render, priority bands, overflow cascade, scanline budget, sprite mask, link-order cycling, dirty-flag DMA) shipped during §3 Object System work. Remaining bullets closed in this plan: (a) multi-sprite batching via Approach 1 + semantic C — Draw_Sprite child-skip guard for parents with `RF_MULTISPRITE`; Render_Sprites walks `sibling_ptr` chain after parent emission, indexing parent's `mapping_frame` against each child's own `mappings`; mid-chain overflow skips just the offending child. (b) `sprite_piece_count` byte at SST_$2D for predictive total-piece overflow skip; populated by Load_Object (initial frame) + AnimateSprite (per frame change via new `RefreshSpritePieceCount` helper). (c) `Render_Sprites` factored emission into reusable `Emit_ObjectPieces` subroutine. (d) ENGINE_ARCHITECTURE.md §1.2/§3.5 link-chain doc corrected — "never rebuilt" was a wash on 68000.
**Test:** TestParent + 3 children renders identically with `RF_MULTISPRITE` on (Task 8) vs off (Task 7 baseline). Sprites_Rendered observed at 49 in stress scene; pre-check + per-piece dbeq layered defenses in place.
**See:** `docs/superpowers/specs/2026-04-27-sprite-system-design.md`, `docs/superpowers/plans/2026-04-27-sprite-system-multisprite-and-piece-overflow.md`, `docs/research/sprite-system-§1.2.md`.

### ~~Scroll / Plane Drawing — Core (§1.3)~~ — DONE 2026-04-25
**Completed in:** §4 Phase 1 Level/World System
**What:** Deferred Plane_Buffer (1536 bytes), Draw_TileColumn/Row, VInt_DrawLevel with autoincrement $80 column mode, overflow protection, pre-computed nametable strips.

### ~~Scroll / Plane Drawing — Dual Plane / Row Updates (§1.3)~~ — **DONE / RESCOPE-OR-DELETE 2026-08-05**
> **⚠ CORRECTED 2026-08-05 — every component this entry lists now exists.**
> - `Draw_TileRow` shipped as **`Draw_TileRow_FromCache`** (`engine/level/plane_buffer.emp:219`),
>   called twice from `engine/level/section.emp:628,667`.
> - **Plane B scroll support** shipped — Plane B is owned by `engine/level/bg.emp`.
> - The stated blocker ("vertical section support / §4.2 vertical section teleport") is doubly
>   void: vertical streaming shipped, and **section teleport itself was deleted** (see the
>   teleport-cluster correction under §4).
>
> The only bullet with any life left is "double-update mechanism for fast travel", and that is now
> just a restatement of the streaming budget work tracked under the diagonal-budget entry.
> **Recommendation: delete or rescope this entry the next time §1 is touched — do not plan from it.**
> Original text below.

**Blocked by:** Vertical section support (§4.2)
**What:** Plane B scroll support, Draw_TileRow for vertical section transitions, double-update mechanism for fast travel.
**When ready:** After §4.2 adds vertical section teleport.

### DPLC Lookahead (§1.6) — **✅ UNBLOCKED 2026-08-05**
> **Blocker discharged.** The §3 object system is fully built: `engine/objects/animate.emp` and
> `engine/objects/dplc.emp` both exist and ship, so "AnimateSprite and DPLC tables" — the stated
> dependency — is satisfied. Clean pick-up; the design below still reads correctly against the
> current code. Listed in the NOW UNBLOCKED section.
**Blocked by:** Object System (§3) — specifically AnimateSprite and DPLC tables
**What:** Predictive art loading by peeking at next animation frame's DPLC requirements one frame early. Queue as Important-priority DMA.
**When ready:** After §3 defines animation system with frame scripts and DPLC mappings.

### Adaptive DMA Byte Budget (§1.1)
**Blocked by:** Real workloads from gameplay systems
**What:** Per-frame DMA byte tracking, lag-frame budget reduction, lag recovery 1.5x burst. Self-tuning throughput based on scene complexity.
**When ready:** After enough consumers exist to generate meaningful DMA load (character art streaming, level tile loading, animated tiles).

### ~~Variable HScroll DMA — Infrastructure (§1.1)~~ — DONE 2026-04-25
**Completed in:** §4 Phase 1 Level/World System
**What:** Hscroll_Dirty_Start/End tracking, Hscroll_Update fills 28 per-8-row bands from Camera_X.

### Variable HScroll DMA — Variable-Length Transfer (§1.1) — **BLOCKER DISCHARGED, INFRASTRUCTURE GONE**
> **⚠ TWO CORRECTIONS 2026-08-05, pulling in opposite directions.**
> 1. **The blocker is discharged.** "Confirmed performance need" is exactly what this file's own
>    diagonal-budget entry supplies: the per-line HScroll DMA is **896 B/frame**, measured at
>    **~20% of the frame**, and the file names it "the single biggest lever" and "a FLAT tax (same
>    stationary or scrolling)". It is no longer waiting on evidence.
> 2. **The infrastructure it assumes was DELETED.** The entry (and the `~~DONE 2026-04-25~~`
>    infrastructure entry above it) both key on `Hscroll_Dirty_Start`/`Hscroll_Dirty_End` —
>    **zero hits tree-wide.** Only `Hscroll_Buffer` survives (`engine/ram.emp:195`). The
>    dirty-range tracking has to be **rebuilt**, not merely consumed.
>
> Net: unblocked, but it is a build-it-then-use-it, not a wire-up. **Also read the caveat that
> already killed the neighbouring idea:** the diagonal-budget entry measured an HScroll-DMA
> dirty-gate as "near-useless" under deform, because the deform phase animates every frame so the
> buffer is always dirty. A dirty-*range* transfer is a different mechanism from a dirty-*gate*
> and is not obviously subject to the same objection — but establish that before committing.
**Blocked by:** Confirmed performance need (currently always DMAs full 224-line table)
**What:** Use Hscroll_Dirty_Start/End to DMA only the dirty scanline range instead of all 896 bytes.
**When ready:** When HScroll partial updates become a measurable DMA budget issue.

### Background Work / Cooperative Multitasking (§1.5 → §9.7) — **✅ RESOLVED — EXECUTED as art-streaming Phase 2 (2026-08-09)**
> **RESOLVED 2026-08-09 (`feat/art-streaming-p2`, chains 55→78; merged to master `2f047e3`).**
> §9.7 was designed AND SHIPPED — not as the user-mode cooperative-multitasking split this entry
> named, but as its ratified replacement: the **pre-chunked pages + VBlank supervisor bookmark**
> idle-time path (ARCH §9.7 rewritten in place, D4=A). A resumable stack-flat ZX0 decoder
> (`ZX0R_Decompress`) is sliced across `VSync_Wait` idle by a VBlank register-bank/resume, feeding a
> VRAM page residency cache. All three downstream items this entry gated are discharged: the
> art-page consumer is live; ZX0 mid-gameplay decode rides the bookmark (never synchronous); S4LZ
> streaming (§2.1) inherits the same pipeline (that entry rescoped below). The user-mode variant is
> recorded as **rejected** in ARCH §9.7. Plan: `plans/2026-08-08-art-streaming-phase2-v2.md`.
> **Original entry retained below for provenance.**
>
> **Blocker discharged 2026-08-05.** "When §9.7 is designed and the S4LZ decompressor exists" —
> **both decompressors exist and ship** (`engine/compression/`, S4LZ + ZX0).
>
> **This is the single highest-leverage unlock in the document** because it is the *sole* remaining
> gate on three independent downstream items, each of which names it explicitly:
> - **S4LZ Streaming Mode (§2.1)** — "Blocked by: §9.7 Cooperative Multitasking".
> - **ZX0 needs budgeted decode before any mid-gameplay use** — ~76 KB/s, ~5 frames synchronous
>   for a 6.3 KB blob; the entry's stated resolution is "route them through §9.7".
> - **Art-streaming Phase 2** — binding amendment #1 promotes resumable decode from tunable to
>   *requirement*, and `2026-07-02-art-streaming-phase2-design.md` §3 names the
>   supervisor-bookmark pattern as the vehicle.
>
> Nothing else here unlocks three items at once. Note the design has moved on since this entry was
> written: amendment #1 was superseded on format (ZX0 + raw-direct hybrid, not S4LZ pages), but
> **the resumable-decode requirement survived that supersession and is now format-independent** —
> so read the Phase-2 spec, not this stub, for the shape.
**Blocked by:** Full design of §9.7
**What:** Supervisor/user mode context switching for background S4LZ decompression in leftover CPU time.
**When ready:** When §9.7 is designed and the S4LZ decompressor exists.

### HUD Dirty Flags (§1.4)
**Blocked by:** HUD system (part of §9.13 screen/menu system)
**What:** Per-element dirty flags (score, rings, timer, lives) to skip HUD VDP writes on frames where nothing changed.
**When ready:** After HUD rendering exists.

---

## From §2 — Art & Compression Pipeline

### Art-streaming Phase 2 — binding amendments from the 2026-07-01 loading audit — **✅ RESOLVED (EXECUTED 2026-08-09)**
> **RESOLVED 2026-08-09 (`feat/art-streaming-p2`, chains 55→78; merged to master `2f047e3`).**
> Phase 2 shipped and every binding amendment below is discharged or superseded, as executed:
> (1) resumable decode is a requirement and shipped format-independent as `ZX0R_Decompress` — pages
> are ZX0 + raw-direct hybrid, 64 tiles; the S4LZ-page format half was already superseded 2026-07-02.
> (2) the pool is now a VRAM residency cache capped by ROM not VRAM (`ART_POOL_PAGE_TILES = 64`,
> manifest v2, per-section local→global indices) — the ~700-850-tile ceiling no longer bounds an act.
> (3) stress-validated under sustained max-diagonal on the `--stress-uniquify` 2600-tile / 41-page
> fixture (window ≪ pool): `Lag_Frame_Count = 0` across every leg, zero wrong-tile frames,
> `Dbg_Cam_Clamp_Frames = 10` total; honorable degradation is the camera soft-clamp (Task 10).
> (4) adopted verbatim — B&R per-act art budget word (Task 9), Vectorman dual cap entries+bytes
> (Task 8). (5) the mega-act showcase depends on this plus floating-origin; its remaining blocker is
> the pre-DAC ROM-layout hole (see the NOW-UNBLOCKED item 7 mega-act ROM-layout entry) — not a
> streaming gap. Plan: `plans/2026-08-08-art-streaming-phase2-v2.md`; ARCH §9.7 + §2 rewritten.
> **Original amendments retained below for provenance.**

**Surfaced during:** the 3-agent post-leapfrog loading audit (2026-07-01; best-in-class comparison vs S2/S3K/S.C.E./B&R/Vectorman/Gunstar/Alien Soldier/TF4/Ristar + SGDK/Tanglewood/homebrew). The shipped Phase 1 (fully-resident deduped pool) was ratified correct and best-in-class; these bind the NOT-yet-built Phase 2 (residency cache / streams-past-VRAM) of `docs/superpowers/specs/2026-06-22-act-art-streaming-design.md`:
1. **Mid-game page streaming MUST use small (~64-tile) S4LZ pages + resumable decode; ZX0 stays init-only.** → **FORMAT HALF SUPERSEDED 2026-07-02** by `docs/superpowers/specs/2026-07-02-art-streaming-phase2-design.md` §4: measured on the real deduped OJZ pool, S4LZ pages reach only 86% ratio (vs ZX0 57.8% — global dedup removes the redundancy S4LZ needs), and the supervisor-bookmark resumable decode (spec §3) removes the fits-per-frame premise this amendment was built on. Phase-2 pages are **ZX0 + raw-direct hybrid, small (~64-tile)**; the *resumable decode* requirement stands, now format-independent. Original rationale (for the record) — CPU is the binding constraint, not DMA: one 8KB ZX0 page ≈ ~620K cycles (~5 frames of total CPU) vs ~1 VBlank of DMA — physically impossible at 16px/frame scroll. S4LZ at the measured 510-640 KB/s closes the worst-case envelope at ~17-22% of a frame. Promote from spec-§8 tunable to requirement. Resumable = the S3K V-int bookmark pattern (ARCH §9.7 coop multitasking is the designed vehicle — make it the page-loader contract). Precedent: S2/Sonic 3D stored streamed art uncompressed; S3K time-sliced Kosinski.
2. **Effective FG pool budget is ~700-850 tiles** after BG (448) + character DPLC + HUD/ring/monitor permanents — S3K-maximalist acts (1000-1500 tiles) will NOT fit fully resident. Phase 2 is core roadmap, not an "unlimited levels" garnish.
3. **Stress-validate Phase 2 under sustained MAX DIAGONAL scroll** — parallax (~20%) + dual-axis block fill + art decode contend for the same idle pool (~76% lag already at max diagonal, see §1 diagonal-budget entry). Honorable degradation: S3K-style gate (brief camera soft-clamp at a worst-case seam).
4. **Adopt from the corpus:** B&R's per-act art/DMA byte budget (a descriptor word reloaded per frame, not a global constant); Vectorman's dual cap (entries AND bytes per frame) on the DMA queue.
5. **Motivating showcase (user goal, 2026-07-10): the multi-zone "mega-act" tech demo** — several classic zones (or a whole game's worth) as one seamless act, no score-tally/camera-lock transitions. Zone themes live in separate pool pages; seams are transition corridors built from shared/neutral tiles where page swaps stream behind the player (the S3K PLC-during-transition pattern, corridor-loading style). Depends on: Phase 2 page streaming (this entry) + floating-origin rebase (§4.11) for the coordinate span. Per-section palettes/parallax/entities already scale. Constraint to author around: zones hand off through corridors, never interleave at fine grain.
**All 7 audit bugs were fixed + merged same day** (blank-slot-0 pin, 960 ceiling assert x2, numeric page enumeration, column-guard off-by-4, marker relocation + PIO int-mask, grid $8000 assert). Remaining small backlog: orphaned teleport-era RAM (`Section_Fwd/Bwd_Neighbor_Data`, `Tile_Override_Table`, `Pos_table`, `H_scroll_frame_offset`, `Camera_Lookahead`), dead `Plane_Buffer_Reset`, ~~`Section_RedrawPlanes` PIO without stopZ80 (convention deviation, currently safe)~~, stale comment at `plane_buffer.asm` "Called with Z80 already stopped by VInt_Level / VInt_Lag", Aurora still exporting the dead parity-model `vram_bases.asm` (ROM ignores it; editor schema drift — see the §8 editor-export entry).

> **⚠ BACKLOG LINE CORRECTED 2026-08-05 — one of these six is DONE.**
> **`Section_RedrawPlanes` PIO without stopZ80 is RESOLVED.** The routine now owns its own Z80
> posture in *both* build shapes — flag bracket with sound on, whole-storm bus hold with sound off
> — documented at the call site (`games/sonic4/test/ojz_scroll_test.emp:171`), which explains that
> the call is deliberately BARE because a caller-side hold would be a FALSE lock. Not a convention
> deviation any more.
>
> The other five **remain genuinely open and were re-verified**: `Tile_Override_Table` still exists
> with no writer (`engine/ram.emp:398`, 96 B), the orphan teleport-era RAM is still orphaned, dead
> `Plane_Buffer_Reset` and the stale `plane_buffer.emp` comment both survive, and the Aurora
> `vram_bases.asm` export is still dead. Note the last one's cross-reference now dangles — the §8
> editor-export entry it points at is itself VOID (its artifact was deleted by `46c2e0f`).

### ~~§2 A.5 T2/T3 — Per-Section BG~~ — VERIFIED 2026-04-27
**Engine paths proven end-to-end** via temporary fixtures in OJZ Act 1, then reverted. Production ships pure T1.
**T2 verified:** `sec_bg_layout` ≠ NULL → `BG_RedrawForSection` blits the section's authored layout to Plane B on teleport. Tested with sec1 = byte-identical zone copy (proved redraw doesn't corrupt content) and sec3 = palette-tinted variant (proved swap visually).
**T3 verified:** sec5's BG layout referenced an in-section VRAM slot (color base 0, tile 5) tiled across all 64×32 cells. After A.4 streaming loaded sec5's tile pool, the BG correctly rendered tile 5 from sec5's region — not the shared 1024+ region. Proves `BG_RedrawForSection` works for any tile_index, regardless of source.
**T1 fallback fix:** `BG_RedrawForSection` originally skipped when `sec_bg_layout` was NULL, which meant T2→T1 transitions kept the prior section's BG. Now falls back to `Act.act_bg_layout` so every transition writes the correct content.
**For real T2/T3 use:** author per-section BG layout files, BINCLUDE them, set `sec_bg_layout` in the section descriptor. The build tool's `emit_bg_tile_blob` already accepts a list of nametables and unions their referenced tiles — no CLI flags or stubs needed.
**Plan:** `docs/superpowers/plans/2026-04-26-art-pipeline-phase2-A5-per-section-background.md` (Tasks 7-10 superseded by inline verification).

### §2 A.5 — Section_Check d0-Clobber Bug — FIXED 2026-04-27
**Status:** `preload_fwd` / `preload_bwd` in `engine/level/section.asm` clobber d0 to build a section offset, but `.threshold_check` assumed d0 = Camera_X high word. After preload fired, the threshold check read garbage d0, frequently spurious-triggering BWD teleport (`d0 ≤ $200` accidentally true). Fixed by reloading Camera_X at the top of `.threshold_check`. Was masking BG verification work.

### §2 A.5 T1 — FG Plane A Tile-Flip Mismatch vs sonic_hack — **EMULATOR-GATED (cannot be settled statically)**
> **2026-08-05:** left open deliberately. This entry's own "Needs:" line already says what it
> needs — a live A/B with two emulators paused at the same screen comparing VRAM bytes. It is on
> the CANNOT-BE-SETTLED-STATICALLY list at the top so nobody re-derives the build-tool math a
> fourth time; that half is already verified correct. It blocks nothing.
**Status:** Architectural milestone shipped, but Exodus's Plane A nametable viewer shows tile-orientation differences between our build and sonic_hack's running OJZ. Build-tool math verifies correct (chunk-level X/Y flip per sonic_hack ProcessAndWriteBlock + dedupe canonicalization + strip remap), so the residual gap is likely in Exodus viewer rendering details (CRAM shadow mode, palette auto-selection) rather than build-tool output — but that's not confirmed.
**Needs:** Live A/B diagnostic with sonic_hack paused at OJZ Act 1 + our build paused at the same screen, comparing specific VRAM tile bytes.
**Doesn't block:** anything; T1 architecture is solid and BG renders correctly.

### ~~§2 A.x — FG Strips Have Wrong Content in Upper Rows~~ — RESOLVED 2026-06-11 (re-test)
**Resolution:** Does not reproduce on current master. Live Exodus verification: at camY=0 over sec0/sec1's
empty top chunks, Plane A row 0 is fully transparent across all 64 cells (blank tile $C6, no priority);
where dirt IS rendered (camX=$EB0/camY=$290 → sec1 chunk rows 1-2, cols 9-11), the on-screen content
matches the source layout cell-for-cell (empty sky chunk over 28/$1D ground chunks). Two findings:
(1) hypothesis (b) was half-right — sec1's layout genuinely has dirt chunk $1D across chunk-row 0
cols 7-15 (editor data AND sonic_hack OJZ_1_sec1.bin agree), so "brown in the sky" at world Y<128
in sec1's right half is faithful level data, not a bug; (2) the "all 64 cells filled" misplacement
was a strip-era streaming artifact — the strip pipeline was deleted and replaced by the 2D block
tile cache (2026-06-10 rewrite), which renders correctly.
Original entry (for reference): As Camera_X scrolled into sec1+, Plane A's upper rows rendered
dirt/rock chunk content with priority set (0xC846, 0xC04C — pal 2), filling the sky region; row 0
had all 64 cells filled, not just slot 0's half.

### ~~§2 A.x — BG Tiles Render Black via Palette Index 0~~ — CLOSED 2026-06-11
**Resolution:** Was contingent on the FG-rows bug above ("resolves automatically once the FG-rows bug
is fixed"). With FG rendering verified faithful to source data, remaining black pixel-0 outlines on BG
tiles only appear where the FG is *supposed* to be transparent — that's the authored art, same as
sonic_hack. No engine work to do.



### ~~Generic Perform_DPLC Routine (§2.1 / §3.9)~~ — DONE 2026-04-25
**Completed in:** §3 Object System audit cleanup
**What:** Perform_DPLC with internalized change detection (SST_prev_frame), Important and Deferrable variants. Objects pass a2=DPLC table, a3=art base, d1=VRAM dest.

### Dynamic VRAM Allocator (§2.2) — **UNBLOCKED, BUT THE PREMISE MAY BE MOOT**
> **⚠ 2026-08-05 — blocker discharged, premise questioned.** The stated blocker (§3 Object System,
> `Load_Object` lifecycle) is satisfied: `engine/objects/load_object.emp` exists and ships, as does
> the rest of `engine/objects/`.
> **But do not plan straight from the 2026-04 text.** It was written when art was expected to swap
> per section. The engine now ships a **fully-resident globally-deduped paged act pool** loaded
> once at init, which is exactly the model that made the graph-color allocator (below) dead. Much
> of "section compaction" and the swap-driven pressure this allocator was designed to relieve may
> no longer exist. **Re-read the current art-pipeline design before planning; the honest first
> question is whether this item should be rescoped to object/sprite VRAM only.**
**Blocked by:** §3 Object System (`Load_Object` spawn/destroy lifecycle drives `AllocVRAM`/`FreeVRAM` calls)
**What:** Bump allocator for unified VRAM pool, loaded table tracking, refcount per type_id, lazy reclaim, section compaction.
**When ready:** After §3 defines object RAM layout and the object loop exists.

### Refcount-based Art Caching / Lazy Reclaim (§2.2) — **UNBLOCKED, SAME MOOTNESS CAVEAT**
> **⚠ 2026-08-05:** §3 exists (`load_object.emp`), so the blocker is discharged — but this entry
> is downstream of the Dynamic VRAM Allocator above and inherits its caveat verbatim: under a
> fully-resident deduped pool there may be nothing to refcount. Evaluate the two together, and
> evaluate the premise before the implementation.
**Blocked by:** §3 Object System (refcount increments/decrements tied to object spawn/destroy)
**What:** Freed art stays in VRAM until pool needs space. Re-spawn of same type is free (refcount bump, no decompression).
**When ready:** After §3 and the dynamic VRAM allocator exist.

### ~~Build-time Graph Coloring (§2.3)~~ — **DEAD 2026-08-05: the allocator does not exist and is not coming back**
> **⚠ VOID — this is not deferred work, it is a deleted design.** Verified 2026-08-05: `DSATUR`,
> `color_sections` and `compute_adjacency` have **zero hits** anywhere in the tree.
>
> The approach was **superseded** by the globally-deduped, spatially-ordered, paged act art pool
> (2026-06-22, the OJZ tile-budget resolution) and the machinery was then removed — this file's own
> Phase-3 cleanup entry records `ENGINE_ARCHITECTURE.md` being reconciled to "no
> graph-coloring/DSATUR/`LoadSectionTiles`/per-section art swap", and `CLAUDE.md` being corrected
> from "graph-color" to "dedup + spatial paging".
>
> **The file was contradicting itself:** this entry listed graph coloring as future work while the
> Done section below carries "§2 Phase 2 Layer A.3 — Build-time Graph Coloring — 2026-04-26" as
> shipped. It was both done and not-done and is in fact neither: it shipped, then was deleted.
> Two other entries referenced the allocator as a live dependency (§5's Sonic VRAM slot, and the
> A.5 T1 Done entry's architectural note) — both corrected in place.
>
> **Do not resurrect this without a fresh design.** Historical text below.
**Blocked by:** §4 Level/World (section adjacency graph) + §8 Build Tools (tile deduplication pipeline)
**What:** Non-adjacent sections share VRAM tile indices. Build tool computes coloring from section adjacency graph.
**When ready:** After §4 defines section grid and §8 has flatten/deduplicate pipeline.

### Section-aware Streaming / Predictive Preloading (§2.1/§4.8) — **UNBLOCKED; the block-stream half already shipped**
> **⚠ 2026-08-05 — half of this is already done, and the blocker text is stale.**
> **Blocker discharged, but not as written:** it names "leapfrog loading" and "section transition
> triggers", and **the leapfrog/teleport subsystem was deleted** (`eddbbf7`). What replaced it —
> continuous scroll with a camera-driven streamer — supplies the same dependency better.
> **The block-stream half effectively SHIPPED** as the unified direction-aware prefetch:
> `engine/level/tile_cache.emp:1001` (row scan, vertical, no hysteresis — "gravity is decisive")
> and `:1093` (column scan with H3 direction hysteresis). That is precisely "predictive preloading
> based on camera velocity and direction", for blocks.
> **What genuinely remains is the ART half** — deferrable-DMA streaming of *tile art* — and that is
> art-streaming Phase 2, which gates on §9.7 (item 1 of the NOW UNBLOCKED list). Rescope this entry
> to the art half or fold it into Phase 2; do not plan it as written.
**Blocked by:** §4 Level/World (section transition triggers, camera position, leapfrog loading)
**What:** Deferrable-priority DMA streaming of next section's art based on camera velocity and direction.
**When ready:** After §4 implements section transitions and camera system.

### S4LZ Streaming Mode (§2.1) — **UNBLOCKED — the §9.7 mechanism now ships; adopt the shipped pipeline**
> **RESCOPED 2026-08-09.** The gate (§9.7) is discharged — the pages+bookmark idle-time path shipped
> with art-streaming Phase 2. S4LZ streaming is no longer *blocked*; it is now a straight adoption of
> the shipped `ZX0R_Decompress`-style contract: make the S4LZ decompressor a `@resumable` stack-flat
> proc in the same `[start, __end)` range shape, enqueue it through the same demand/prefetch FIFO,
> and let the VBlank bookmark slice it. The pipeline (private staging buffer → dispatcher DMA enqueue
> → VBlank transfer) is built and proven; only the S4LZ-specific resumable decoder body remains.
> Do this when a payload larger than one block dictionary actually needs mid-gameplay streaming.
**Was blocked by:** §9.7 (now shipped — pages + supervisor bookmark, ARCH §9.7).
**What:** A `@resumable` S4LZ decoder body adopting the shipped bookmark contract + demand/prefetch FIFO.
**When ready:** Now — do it when a larger-than-block payload needs mid-gameplay streaming. Blocking mode handles all current use cases.

---

## From §3 — Object System (Research Phase)

These items were identified during §3 Phase 0 research but require a full SST field audit before committing.

### Boss-system design reference — multi-phase choreography via chained routine pointers (§3) — 2026-07-14
**Surfaced during:** TheBlad768 survey — S3K Epilogue boss objects. Full write-up: `docs/research/2026-07-14-theblad768-survey.md` (KEEP #2).
**Status:** Reference only — no boss system is designed yet. Epilogue runs multi-stage fights inside ONE object: HP-threshold swaps the active attack-pattern table (8→4 HP = different 4-pattern set), each pattern a coroutine-style subroutine whose successor address lives in a free object-RAM field and is chained at runtime (mid-attack transitions = pointer swap, no routine-counter ladder, no per-phase object IDs), position-gated pattern entry, child-object attack spawns, HP-keyed palette hit-flash tables.
**What:** When the boss-system design phase opens, cite this as the worked "one object, N phases" example. Maps directly onto objects-v2: chained next-routine pointer in `sst_custom`, pattern-table swap on HP threshold, children system for spawns, palette-line flash via per-line dirty DMA. Related: the same survey doc's KEEP #3 (Sonic Spinball script-VM cutscene/animation architecture, added 2026-07-14) is the companion reference for any cutscene/scripted-sequence system — both replace routine-counter ladders with data-driven control flow.

### SST Field Audit & Size Re-evaluation (§3)
**Note (2026-06-10):** objects-formats-v2 resolved the dead-field/metadata half of this audit — `respawn_index`, `wait_timer`, and the separate priority word are gone; entity-window metadata (`slot_tag`/`entity_section_id`/`entity_list_index`/`layer`) packed at $2A-$2D; `sst_custom` grew to 34 bytes at $2E.
**CLOSED (2026-06-14, §5 player work):** the player overlay fits 34 bytes with room to spare — **`PlayerV_len` = $D (13 bytes)** of the 34 available (`engine/player/player_common.asm`: ground_speed, player_state, status_secondary, move_lock, spindash_charge, flip_angle, air_left, invuln_time, stick_convex, debug_flag; the last five are reserved/debug). The DPLC table and art base are **per-character code immediates** (`lea` in `sonic.asm`), NOT SST fields, so the 9-byte test_player DPLC-in-SST pattern is not carried over. No per-pool stride, no variable SST sizing, no SST growth needed for the player. The general SST-shrink question (below) stays open but is decoupled from the player.
**Blocked by:** Implementation of player subsystem (need real player field pressure)
**What:** Audit every SST field across all object types (player, badnik, platform, effect, boss, system) once subsystems are implemented. Determine actual field usage per type. Evaluate whether the SST can shrink from $50 to $4C or $48.
**When ready:** After §3 Phase 3 (animation) and Phase 4 (collision) are implemented — enough subsystems exist to see real field pressure.

### ~~Word code_addr at $00 (§3)~~ — DONE (superseded by objects-v2, 2026-06-10)
Shipped: SST $00 is a word offset from `ObjCodeBase`, `objroutine()` computes it at build time, and the object bank has a build-time 64KB overflow guard.
**What:** Use a word offset at $00 instead of longword function pointer (sonic_hack pattern). `objroutine function x,(x)-ObjCodeBase` computes offset from a $10000-aligned code bank. Dispatch: `moveq #BANK, d0; swap d0; move.w (a0), d0; movea.l d0, a1; jsr (a1)`. Saves 2 bytes per SST, 20 cycles per dispatch (~1,320 cycles/frame across 66 slots). Constraint: all object code must fit in one 64KB bank.

### Word Mappings Offset (§3)
**Blocked by:** SST field audit
**What:** Use a word offset for `mappings` instead of a longword ROM pointer. All sprite mappings would live within 64KB of a base address. Saves 2 bytes per SST. Combined with word code_addr, that's 4 bytes freed — may enable SST shrink.
**When ready:** During SST field audit. Requires organizing mapping data contiguously.

### Variable SST Sizing — Effect Pool (§3)
**Blocked by:** SST field audit (need to know actual effect field usage)
**What:** Thunder Force IV uses $20/$40/$60 per-type pools. A $20 effect SST (explosions, dust, score popups, debris) shares the $00-$19 prefix with the full SST, enabling shared routines (ObjectMove, Draw_Sprite). Saves ~768 bytes at 16 effect slots. Trade-off: separate RunEffects loop, effects can't use routines that access fields past $19 (e.g., AnimateSprite needs anim_table at $28).
**When ready:** After SST field audit determines which fields effects actually need. May be unnecessary if SST shrinks enough overall.

### ~~Pack collision_resp + width + height for Single-Longword Init (§3)~~ — SUPERSEDED by objects-v2 (2026-06-10)
The burst-copy spawn (`movem.l` of the whole $0A-$21 template block) makes per-field init moot — collision_resp/width/height arrive with everything else in one copy.
**Blocked by:** SST field audit + Load_Object init path performance pressure
**Source:** TheBlad768's S.C.E. and S1-in-S3 collision refactors (`d1e24ee` / `05512e4`) put `collision_type`, `collision_height`, `collision_width` adjacent so spawn init can do `move.b d0,collision_type(a0); swap d0; move.w d0,collision_height(a0)` — three bytes initialized from one ROM longword. Currently `collision_resp` is at $0F and `width_pixels`/`height_pixels` at $18-$19, so they need separate fetches.
**What:** Reorder SST so the type byte is adjacent to the width/height pair (or move both into the $0E neighborhood). Lets objdef tables emit `dc.b coltype, colh, colw, pad` and Load_Object init reads them in one `move.l`. Rough estimate: ~10-20 cycles saved per spawn × spawn frequency. Not free — reorder breaks the current $00-$19 "shared-prefix" boundary that we may want for a future $20 effect SST, so these two items must be evaluated together.
**When ready:** During SST field audit, alongside the effect-pool decision.

### ~~Object Data Macros (`subObjData` family) (§3)~~ — DONE (superseded by objects-v2, 2026-06-10)
Shipped as the `objdef` named-parameter macro (26-byte archetype image) plus `objentry`/`objend` for placement lists — semantic args, build-time validation.
**Blocked by:** Objdef format finalization (currently still raw `dc.b`/`dc.l` in `data/objdefs/test_objects.asm`)
**Source:** S.C.E.'s `subObjData frame,coltype,(colh/2),(colw/2)` macro hides the field layout behind a named-parameter call so reordering SST fields doesn't ripple through every object table. Same idea for child priority data, animation script entries, etc.
**What:** Once the objdef format is stable, wrap the byte/word emission in `function`-and-macro pairs that take semantic args (`coltype`, `colh`, `colw`, `frame`, `priority`, ...) rather than positional bytes. Uses our `function` for any /2 or shift conversion, `struct`/`endstruct` patterns where appropriate. Pure ergonomics — zero runtime cost, but it's the difference between objdef tables that read like data and ones that read like a binary blob.
**When ready:** When more than 2-3 objects exist and the objdef format stops churning.

### Multisprite children vs parent bbox culling (§3.5)
**Surfaced during:** objects-formats-v2 final review (2026-06-10).
**What:** Exact parent-bbox culling governs whole multisprite batches (children
skip independent registration), so a child extending beyond its parent's own
frame bbox can pop at the screen edge earlier than under the old ±32 margin.
No multisprite content exists yet.
**When to revisit:** first boss/multi-part object — either author parent frames
whose bbox covers the chain's extent, or have the generator union child extents.

### SST frame-pointer cache (§3.5)
**Surfaced during:** objects-formats-v2 T8 review (2026-06-10).
**What:** Draw_Sprite and Render_Sprites each resolve mapping_frame → frame data
per object per frame (~46 cycles each). RefreshSpritePieceCount/
PopulateSpawnedPieceCount already run at every mapping_frame write, so caching
the resolved frame POINTER in the SST (one long from sst_custom) has a ready
invalidation contract and saves ~90 cycles per rendered object per frame.
Caveat: the multisprite sibling walk indexes child mappings with the parent's
frame and must keep its inline resolve.
**When to revisit:** when profiling shows object-loop pressure (~20+ on-screen
objects), alongside the §3 SST field audit.

---

## From s4lint — Static Analysis (Phase 1)

### Fall-Through State Carry-Forward
**Blocked by:** Real codebase patterns that use fall-through across global labels during VDP access
**What:** When a routine doesn't end with `rts`/`rte`/`bra`/`jmp`, carry Z80/interrupt state forward to the next global label instead of resetting. Currently all state resets at every global label boundary.
**When ready:** When fall-through patterns appear in engine code that cause false positives on E006/E007/E008.

### Sprite Multiplexing for Particle/Weather Systems (§3.5)
**Blocked by:** HBlank handler infrastructure, weather/particle system design
**What:** Rewrite SAT entries mid-frame via HBlank to display 80+ visual sprites from 3-5 physical SAT entries. Each HBlank updates Y/X/tile for a small set of sprites, scanning them down the screen. 18 bytes/scanline VRAM bandwidth, ~92 68k cycles per HBlank handler. Best for simple, repetitive effects (rain, snow, starfields) where sprites are small and never share scanlines. Too constrained for general Sonic gameplay (diverse objects at varying positions).
**When ready:** When a weather or particle system needs more than 80 simultaneous sprites. Stone Protectors (falling snow, 3 sprites × 8 scanlines) is the reference pattern.

### Object-vs-Object Collision (§3)
**Blocked by:** Real gameplay objects that need it (boulders, boss parts, projectiles)
**What:** Current TouchResponse is player-vs-object only. For object-vs-object cases (two boulders bouncing, boss parts checking each other, shields vs projectiles), add a `CheckObjectPair` helper that takes two SSTs, does the same AABB test, and returns overlap data. Objects call it from their own per-frame routine against specific targets. A full O(n²) object-vs-object pass is overkill — object-side polling is the Sonic-era pattern.
**When ready:** When a gameplay object needs to react to another non-player object.

### W010 Loop Detection Refinement
**Blocked by:** When suggestion-tier noise becomes annoying even with `--no-suggestions`
**What:** W010 (indexed addressing in loops) currently triggers after ANY local label, not just actual `dbf`/`dbra` loop bodies. Should only flag indexed addressing between a local label and the `dbf` that references it. Phase 3 reclassified W010 as a suggestion (not warning), so the noise is lower-priority now.
**When ready:** When the false positive rate is still disruptive even as a suggestion.

---

## From §4 Phase 1 — Level/World System

### ~~Path-B collision content — wire the secondary index through the strip generator (§4.7)~~ — **✅ FULLY CLOSED — design #6 closeout, verified 2026-08-08**
> **⚠ CORRECTED 2026-08-08 — path B is editor-authorable now, and "remaining = path-swapper
> objects" (the assumption the 2026-07-02 editor-collision-authoring-design spec carried into
> this entry) was already stale when that spec was written: `path_swap.emp` shipped
> 2026-06-12, three weeks before the spec's 2026-07-02 date.**
>
> **Production collision has moved off the sonic_hack-donor secondary index entirely.** The
> 2026-08-05 correction below (kept for provenance) describes wiring the real `"OJZ secondary
> 16x16 collision index.bin"` through `bake_cell`/`PATH_A_SOL_SHIFT`/`PATH_B_SOL_SHIFT` — that
> path (`ojz_strip_gen.build_section_collision`) still exists in the tree but is now
> legacy/test-fallback only (see `test_section_collision_sec0`, explicitly commented
> "fallback-mode data"). The LIVE production path (`ojz_strip_gen.generate()`, the "FRESH
> START + flag-based authoring" block) is: **all-air baseline** (`per_section_coll` seeded
> from `air_col`) **+ Aurora's editor overlay** (`apply_editor_collision_overlay`, reading
> `games/sonic4/data/editor/ojz/act1/section_N.collattr.bin` / `.collattrb.bin` — 16-bit
> big-endian cell words, one plane per file) **baked via `collision_pipeline.bake_plane_cell`
> against the imported S&K shape/height/angle bank** (`data/collision/base/`, written by
> `import_sk_collision.py`) **into a shared, sparse interned attr-set** (13/255 combos used
> today, ~242 slots headroom) — only combos actually painted reach the ROM tables.
>
> aeon's half of this (consumption) has needed **zero code changes** since 2026-07-02 (per
> `docs/superpowers/specs/2026-07-02-editor-collision-authoring-design.md` §3). Today's
> design #6 (Aurora, `aurora/docs/plans/2026-08-08-chunk-collision-and-map-clipboard.md`)
> closes the AUTHORING half instead: `ChunkDef.collisionA`/`collisionB` (16-bit cell words,
> same encoding as the section edit planes) now travel with stamps atomically, a map clipboard
> copies/pastes regions with both collision planes, paint defaults to "just here" instead of
> art-identity propagation, and the legacy per-tile nibble plane + `.coll.bin` export + 2-bit
> `ChunkDef.collision` are all deleted. Path B is no longer "copy of A until real secondary
> data is authored" — Aurora authors it directly now (`docs/LEVEL_EDITOR_SPEC.md` corrected
> alongside this entry).
>
> **Path-swapper objects were never the actual gap.** `games/sonic4/objects/path_swap.emp`
> (`PathSwap_Init`/`PathSwap_Main`, writes `Sst.layer` on line-crossing — the collision-layer
> select `engine/level/collision_lookup.emp` reads into `d3.b`) shipped 2026-06-12 ("path-swap
> line object — OJZ loop wired for two-path traversal") and was ported to `.emp` 2026-07-29; a
> real two-path loop is placed in level data (`OJZ_Sec1_Objects`, `entity_data.emp:41`, type 1
> = `ObjDef_PathSwap`, two instances). **No collision-content work remains deferred here** —
> author → bake → consume → runtime swap is closed end-to-end.
>
> Older correction, kept for provenance:
> **⚠ CORRECTED 2026-08-05 — this entry asked for two things and BOTH shipped.**
> 1. **The real secondary index is loaded and baked.** `tools/collision_pipeline.py:301` loads
>    `"OJZ secondary 16x16 collision index.bin"` alongside the primary, and `:172-189`
>    (`bake_cell`) bakes *both* layers per placement, driving path selection off
>    `PATH_A_SOL_SHIFT` / `PATH_B_SOL_SHIFT` (bits 13:12 and 15:14 of the chunk-entry word) with
>    per-path flip handling. The VDP-priority-bit placeholder this entry complains about is gone —
>    and note the pipeline moved: it is `tools/collision_pipeline.py` now, not
>    `tools/ojz_strip_gen.py`.
> 2. **The path-swapper objects exist.** `games/sonic4/objects/path_swap.emp` is implemented and
>    actually placed in level data — `ObjDef_PathSwap` appears as type 1 in
>    `games/sonic4/data/generated/ojz/act1/entity_data.emp:41`
>    (`OJZ_Sec1_TypeTable ... t1: ObjDef_PathSwap`).
>
> Layer B is no longer a byte-copy of layer A. **The RAM-slack note in the entry (910 bytes lower
> RAM, one more `BLOCK_STAGE_SLOTS` fits) is from 2026-06-10 and has NOT been re-measured — do not
> trust that number.** Historical text below.

**Surfaced during:** objects-formats-v2 T7 (2026-06-10).
**What:** Dual-layer collision SHIPPED format-wise (768-byte blocks, two cache planes,
SST_layer select) but layer B is a byte-copy of layer A. The real data exists:
`sonic_hack/collision/OJZ secondary 16x16 collision index.bin` (138 bytes, 122 differ
from primary) — but `tools/ojz_strip_gen.py` derives collision from a VDP-priority-bit
placeholder, not the index files, so wiring block-ID → secondary index → real path-B
bytes is level-pipeline work. Also needed then: path-swapper objects that write SST_layer.
**RAM note:** lower RAM slack is now 910 bytes ($FFFF7C72 → $FFFF8000). One more
BLOCK_STAGE_SLOTS (+768) fits; nothing ≥1KB does without evicting something.
**When to revisit:** when the level pipeline replaces the priority-bit collision
placeholder with real collision data, or when the first loop is authored.



### ~~Tile cache vertical slide is a memmove — circular row origin (§4.7)~~ — DONE 2026-06-10
**Completed:** `Cache_Origin_Row` circular index shipped same day the lag was
observed live (debug-fly turbo descent = up to 3 memmoves/frame ≈ 260k cycles).
VSlide/VSlideUp are now O(1); row-walking consumers use an end-of-buffer
sentinel (~16 cycles/row); single-row consumers remap the index. Origin kept
even so collision stays cell-aligned. Verified in Exodus: 252-row descent →
origin 12 (252 mod 60), 216-row ascent → origin 36 ((12−216) mod 60), terrain
renders clean through 4+ ring wraps in both directions.
Original entry:
**Surfaced during:** tile cache fill rewrite 2026-06-10.
**What:** Columns evict via circular origin (`Cache_Origin_Col`, free), but rows evict by
shifting the whole buffer: `TileCache_VSlide`/`VSlideUp` move ~9.4 KB nametable + ~2.3 KB
collision per 2-row evict ≈ **~47k cycles (a third of a frame) every 16 px of sustained
vertical scroll**. Fine in the light test state; will cause lag frames under real object
load. Fix: add a `Cache_Origin_Row` circular index. Touches every row-indexed consumer —
`Tile_Cache_GetTile`/`GetCollision`, `TileCache_CopyBlockColumn`, `Draw_TileColumn`
(column walks would split into two runs at the wrap, mirroring the existing NT 63/0
split), `Draw_TileRow_FromCache`, `Section_RedrawPlanes`.
**When to revisit:** once gameplay objects + parallax + DMA load share the frame and
vertical traversal shows lag, or §4 vertical work touches these routines anyway.

### FG H-deform vs streaming seam (left-edge draw lookahead)
**Surfaced during:** plane-A scroll lock fix 2026-06-10.
**What:** Plane A is now hard-locked to the camera, but configs that apply an
**H-deform wave to plane A** (e.g. SkyHaze's bottom-band FG haze on Sec2) still
displace FG lines by up to the wave amplitude. A leftward wobble pulls plane
columns left of the camera window into view — those sit at the plane-wrap seam
and may hold ahead-content, exposing up to wave-amplitude pixels of seam at the
screen edge. Mitigation: stream a few extra columns of edge lookahead in
`Section_UpdateColumns` (≥ max FG deform amplitude in tiles) so the seam sits
beyond any FG wobble.
**When to revisit:** before shipping any production config with FG H-deform, or
if Sec2's haze shows edge artifacts during testing.

### ~~§4.9 entity window is X-only — no vertical dimension~~ — DONE 2026-06-11 (vertical entity window)
**Surfaced during:** vertical-axis audit 2026-06-10 (EntityWindow_TeleportShiftY added
for teleport consistency, but the underlying system is 1D).
**What it was:** `EntityScanState` had `ess_origin_x` but no Y origin; ring/object
populate used ROM Y verbatim; only the slot-mapped (upper) sections of each vertical
pair were scanned; `EntityWindow_Scan` advanced on camera X only.
**Fix shipped:** exactly the proposed shape — 2×2 quadrant scan state (4 entries: slot
L/R × row r/r+1, derived from `Slot_Section_Map` by `EntityWindow_BuildEntries`),
per-entry `ess_origin_y` + `ess_entry_idx`, `Entity_Window_Active` validity mask with
SEC_VOID stamping for out-of-grid entries, S3K-style camera-Y spawn band
(ENTITY_LOAD_BUFFER_Y $100) with despawn hysteresis (ENTITY_DESPAWN_BUFFER_Y $180),
128px-coarse vertical re-scan (ENTITY_RESCAN_COARSE_MASK), per-entry loaded bitmasks
making all spawn paths idempotent, ring-buffer high-water + DEBUG-fatal drop diagnostics,
and build-time guards on the band invariants. Teleport mask migration proven a no-op
(disjoint 2-section block moves, table in entity_window.asm). **OEF_ANY_Y is now
honored:** ANY_Y objects spawn on X coverage regardless of camera Y and are exempt
from Y despawn, with the flag mirrored to `SST_slot_tag` bit 7 at spawn. Full 7-check
verification matrix passed in Exodus 2026-06-11. See ENGINE_ARCHITECTURE.md §4.9.3/§4.9.6.

---

## ☠ DEAD CLUSTER — the §4 teleport / leapfrog entries (11 entries, VOID 2026-08-05)

**Every entry marked `[DEAD CLUSTER]` below describes a subsystem that no longer exists.**
`eddbbf7` (2026-06-22, "refactor(level): delete the dead leapfrog subsystem — continuous-scroll
Task 10") removed it wholesale, and the continuous-scroll engine that replaced it does not
teleport at all: it scrolls continuously and rebases the floating origin.

**Grep evidence (2026-08-05, whole tree, source only — every one returns ZERO hits):**
`Section_Check`, `Section_TeleportFwd`, `Section_TeleportBwd`, `Section_TeleportUp`,
`Section_TeleportDown`, `Section_QueueNewSlot`, `Section_Preload`, `SECTION_SHIFT`,
`Slot_Section_Map`, `SyncSlide`, `TeleportShift`.
(`Slot_Section_Map` appears exactly once, in a comment at `engine/system/replay.emp:255`
explicitly noting the name does **not** exist.)

**What `engine/level/section.emp` actually exports today** — the complete list:
`Section_Init`, `Section_FillInitial`, `Section_FlatIDXY`, `Section_GetSecPtrXY`,
`Section_RedrawPlanes`, `Section_UpdateColumns`. No teleport, no preload, no slot map, no
threshold check.

**How to read these entries:** as **historical record only**. They are retained (not deleted)
because they document real reasoning about plane wrap, streaming budgets, landing suppression and
register-clobber contracts, and because the continuous-scroll design was chosen *against* them —
knowing what was rejected is worth keeping. **Do not plan from any of them. Do not "fix" the
defects they describe.** A few contain observations that outlived the subsystem; those are called
out individually.

**The eleven:** Plane A wrap-cycle · Section Preload with S4LZ Deferrable DMA · Section Preload
Velocity-Based Timing · Vertical Section Teleport · Section Null-Neighbor Camera Clamp · Section
rotation cascading work · Plane A fill-in after teleport · Section teleport landing-flag mechanism
· X-BWD clamp-to-zero degenerate slot pair · `Section_TeleportBwd` `.at_start` guard ·
`Section_Check` clobber header understates.

---

### [DEAD CLUSTER] ~~Plane A wrap-cycle visible during scroll (§4.2 streaming polish)~~
> **VOID — see the DEAD CLUSTER banner above.** The whole entry is framed on `SECTION_SHIFT`
> (deleted) and `Section_UpdateColumns`' teleport-era ring math. Its recommended fix — "camera
> teleport per plane-width" — is the opposite of the direction the engine actually took
> (continuous scroll + floating-origin rebase, shipped 2026-06-22/23). Historical text below.
**Surfaced during:** §4.6 polish session 2026-04-28 (after bhi→bhs core fix + Section_Teleport_Guard increase shipped).

**Symptom:** When scrolling right through a single section, foreground (Plane A) terrain appears to "draw from left to right" — chunks of FG content materialize at screen LEFT and seem to fill toward screen RIGHT as the user scrolls. When scrolling left (back), the LEFT chunk disappears first while the RIGHT chunk persists. User confirmed via experiment: stub'ing `Section_UpdateColumns` to `rts` immediately makes all FG content disappear, proving the streaming engine *is* producing the visible artifacts.

**Root cause analysis:**
- Plane A is 64 cells = 512 px wide; screen is 320 px wide
- Section is 4096 px (`SECTION_SHIFT = $1000`); user scrolls through a section across 8 plane-widths
- `Section_UpdateColumns` writes each new section col to plane col `(global_col mod 64)`
- The streaming target is mathematically *correct* — it writes off-screen-right (1 col past visible right edge)
- BUT plane col 0 has a visibility cycle as Camera_X grows: visible at screen LEFT briefly when `Cam_mod_512 ∈ [0,7]`, off-screen for ~190 px, then reappears at screen RIGHT and drifts left
- During this cycle, each plane col gets *overwritten* every 512 px of camera travel with new section data — but the overwrite happens off-screen-right, so the new content enters from screen-right correctly
- **The "drawing from left" perception** is the plane-wrap natural behavior: every 512 px of scroll, the pattern repeats. Content at screen LEFT after each wrap is the LATEST streamed content — user sees it as "appearing on the left."

**Verified facts:**
- HScroll values are correct (uniform `-Camera_X` across all 28 cell rows for Sec0)
- Section_FillInitial fills cols 0..63 correctly at boot
- Section_UpdateColumns advances Right_Col_Written / Left_Col_Written correctly
- Streaming writes target plane col is always off-screen-right at the moment of write
- Plane wrap is mathematically inevitable when plane width (512px) < section width (4096px)

**Possible fixes (all §4.2 architecture work, not §4.6):**
1. **Camera teleport per plane-width**: instead of `SECTION_SHIFT = $1000`, teleport every 512 px so plane wraps land at teleport boundaries (= invisible). Requires reworking section coordinate system, object spawning, collision lookups.
2. **Wider effective plane via VRAM trickery**: not feasible — VDP is hard-limited to 64×64.
3. **Section_UpdateColumns rewrite**: stream content N plane-widths AHEAD so each plane col is written 64+ cols before reaching visibility. Requires more aggressive write-ahead and careful Plane_Buffer budgeting.
4. **Live with it**: accept that plane-wrap pattern is visible. Real Sonic games (S1/S2/S3K) use camera teleport to mask it; we currently don't.

**When to revisit:** Dedicated §4.2 polish session. Don't try to band-aid this in §4.6 territory — it's a section-streaming engine architecture issue. Recommend Option 1 (camera teleport per plane-width) as the proper fix; it matches the technique used in real Sega Genesis Sonic games.

**Additional finding:** `SECTION_SHIFT = $1000` ≠ `SECTION_SIZE = $0800`. Comment claims "uniform shift applied on teleport (pixels)" but the value is 2× SECTION_SIZE. With current values, post-FWD Camera_X = $200 (= cam_min_x = BWD_THRESHOLD), which is what causes the section oscillation that the 30-frame Section_Teleport_Guard patches. The "natural" fix would be `SECTION_SHIFT = SECTION_SIZE = $0800` (so FWD/BWD both land Cam mid-window at $0A00, no oscillation), but this requires recalibrating Right_Col_Written / Left_Col_Written math in Section_UpdateColumns and the Section_FillInitial init values. Worth investigating as part of §4.2 polish — may also resolve the plane-wrap perception issue if the ring rotation is "shorter" per teleport.

### [DEAD CLUSTER] ~~Section Preload with S4LZ Deferrable DMA (§4.2)~~
> **VOID — see the DEAD CLUSTER banner.** `Section_Preload` and `Section_QueueNewSlot*` do not
> exist. **One idea outlived the subsystem:** deferrable-DMA streaming of upcoming *art* is real
> work — it lives on as **art-streaming Phase 2**, gated on §9.7. Plan it from the Phase-2 spec,
> not from this entry.
**Blocked by:** S4LZ art streaming pipeline (§2.1) and section adjacency graph
**What:** When camera crosses Section_FWD/BWD_PRELOAD threshold, queue Deferrable-priority DMA to load next section's tile art into the VRAM pool. Currently Section_QueueNewSlot1/0Cols just writes nametable strips; the art must already be in VRAM.
**When ready:** After §2 art streaming and §4.2 section preload are designed.

### [DEAD CLUSTER] ~~Section Preload — Velocity-Based Timing (§4.2)~~
> **VOID — see the DEAD CLUSTER banner.** No preload threshold exists to make velocity-adaptive.
> **The idea outlived it in shipped form:** direction/velocity-aware prefetch is live in
> `engine/level/tile_cache.emp` (`:1001` row scan, `:1093` column scan with H3 hysteresis) for the
> block stream. What that does not cover is art — again art-streaming Phase 2.
**Blocked by:** Player physics providing ground_speed
**What:** Preload threshold adapts to player ground_speed — trigger earlier at high speed to ensure art arrives before new columns are visible. Currently fires at fixed SECTION_FWD/BWD_PRELOAD constants.
**When ready:** After §3 player physics provides ground_speed to the section system.

### [DEAD CLUSTER] ~~Vertical Section Teleport (§4.2)~~
> **VOID — see the DEAD CLUSTER banner.** `Section_TeleportUp`/`Down` never existed beyond a stub
> and the `Section_Check` that would have hosted them is deleted. **The capability shipped by
> other means:** continuous vertical scrolling + the vertical entity window + vertical tile-cache
> fill, all merged 2026-06-11/23. Multi-row section grids work today without any teleport.
**Blocked by:** Vertical level design and camera Y handling
**What:** Section_TeleportUp / Section_TeleportDown paths (stub exists in Section_Check). Camera Y threshold mirrors the X system. Required for multi-row section grids.
**When ready:** After a level with vertical transitions is designed.

### [DEAD CLUSTER] ~~Section Null-Neighbor Camera Clamp (§4.2)~~
> **VOID — see the DEAD CLUSTER banner.** There is no `Section_TeleportBwd` to add a null check
> to. Note the underlying concern *was* separately addressed in the teleport era via the
> `SEC_VOID` sentinel + camera max-x void clamp (see the grid-edge entry), and the concept
> survives as ordinary act-boundary camera clamping in the continuous-scroll engine.
**Blocked by:** Act descriptor null-section encoding
**What:** When camera approaches a section slot with no neighbour (edge of the level), Camera_X should clamp to the act boundary instead of teleporting. Currently Section_TeleportBwd has a note for zero-clamp but no null check.
**When ready:** After act descriptors encode level boundaries.

### Dynamic Tile Override Table (§4.3)
**Blocked by:** Gameplay objects that need runtime tile patching
**What:** Tile_Override_Table (16 entries × 6 bytes) is allocated in RAM. Needs a writer (object sets col/row/new_tile) and a drain routine (VInt_DrawLevel emits row updates). Used for breakable tiles, activated switches, destroyed terrain.
**When ready:** When a gameplay object needs to modify level geometry at runtime.

### ~~§4.6 lerp accumulator never converges to per-band targets~~ — RESOLVED 2026-06-11 (re-test)
**Resolution:** Root cause was the TestPlayer d7 clobber (fixed 2026-06-10) — garbage object dispatch
was stomping the accumulators between frames, which is why every single-stepped iteration computed
correctly while stored values were wrong. Re-test on current master: Camera_X=608 stable, active config
resolves to ParallaxConfig_OJZ_Caves (factors 1/16,1/16,1/8,1/4,1 — NOT the April-era Default config the
original expectations were computed from), and `Parallax_Current_Scroll_B` reads exactly
[-38,-38,-76,-152,-608] = 608×factors, pixel-perfect. Entries 5-7 stay 0. Mid-pan spot-check at
Camera_X=624 under the same config was also exact ([-39,-78,-156,-624]). Note for future debugging:
the April "expected" values were computed against the wrong config — always derive targets from
`Parallax_Current_Config`'s actual band table, not from the act's default.

Original investigation notes kept for reference:

**Surfaced during:** §4.6 polish session 2026-04-28 (after MCP debug session).

After ~thousands of frames with Camera_X stable at 608, Plane A
entries 0-4 of `Parallax_Current_Scroll_A` converge to -608 (the
FACTOR_1 target — correct). But Plane B entries don't converge to
their per-band targets:

  Expected (steady state with camX=608):
    B[0] cloud (FACTOR_1_8) → -76
    B[1] far_mtns (FACTOR_1_4) → -152
    B[2] mid_mtns (FACTOR_3_8) → -228
    B[3] hills (FACTOR_1_2) → -304
    B[4] ground (FACTOR_1) → -608

  Observed: -542, -551, -608, -608, -608

Entries 5-7 (which the 5-band loop shouldn't touch) read as -608 even
though `Parallax_Init`'s zero loop correctly sets them to 0.

Verified via single-step:
- `Decode_Factor_A` returns -608 for FACTOR_1 ✓
- `Decode_Factor_B` reads correct s1=3 for cloud band's first call ✓
- Band loop iterates 5 times, exits with d5=5 ✓
- `a2`/`a3` advance by 2 per iter, end at entry 5 ✓
- `Parallax_Current_Config = $000104C2` (OJZ_Default) stable ✓
- Camera_X stable at 608 ✓
- `Parallax_Init` runs once at boot, never again ✓

So the lerp's *individual iterations* compute correctly per-band, yet
the steady-state values are wrong. This suggests entries are getting
overwritten BETWEEN frames by something that doesn't appear in the
band loop or Parallax_Update flow. Watchpoints don't fire.

Live MCP debugging hit a wall — the inconsistency between "every
instruction does the right thing" and "the stored values are wrong"
needs **instrumented offline debugging**: dump
`Parallax_Current_Scroll_A/B` to a debug VRAM region every frame, then
inspect the trace to find when/which write produces the wrong value.

**When to revisit:** Dedicated session with code instrumentation. Don't
try live-stepping — too much state, too much MCP-level uncertainty.

---

### ~~§4.6 visual artifacts blocked on root-cause of state clobber~~ — RE-TESTED 2026-06-11, ALL THREE RESOLVED

**Re-test 2026-06-11 (current master, live Exodus):**
1. **3-line race on load / wrong lerp targets** — RESOLVED. Accumulators converge pixel-exact to the
   active config's per-band targets (see the lerp entry below for full numbers). The April "wrong
   targets" were measured against the wrong config (Default instead of the per-section Caves).
2. **FG H-deformed during section transitions** — RESOLVED. FG HScroll words verified uniform at
   -Camera_X across all 224 lines through: a FWD teleport into Sec2, a BWD teleport back, and two
   live config switches (Windy↔Caves). The only per-line FG variation found was SkyHaze's *intentional*
   bottom-band haze on Sec2 (`parallax_combine_split` demo) — by design, not the artifact.
3. **BG warps while stationary** — RESOLVED. Two screenshots ~20s apart with camera idle at
   Camera_X=608 are byte-identical PNGs.

All three derived from the TestPlayer d7 stomp (fixed 2026-06-10). No further §4.6 debugging needed.

**Surfaced during:** §4.6 T12 testing, expanded in T12 polish session 2026-04-27.

Three known visual artifacts in the OJZ scroll test that all derive from
the same upstream state-corruption issue tracked below:

1. **3-line race on load.** Top scanlines lerp from VSRAM=0 to their
   converged target over the first half-second. Snap-on-init
   (32-iter convergence loop in `Parallax_Init`) was added but didn't
   eliminate the visible race. MCP runtime read of
   `Parallax_Current_Scroll_B` after Init shows entries [0]=-542, [1]=-551,
   [2..7]=-608 instead of the expected per-band targets (-76, -152, -228,
   -304, -608). The lerp accumulators are converging toward a *different*
   target than the math would predict — points to either a register
   clobber inside `Parallax_Update` or stale state from a stalled iter.

2. **FG appears H-deformed during section transitions.** When entering
   Sec2 (or otherwise crossing a section boundary), Plane A tiles show
   sine-wave horizontal offsets, even though `pcfg_deform_table_fg=NULL`
   for every shipped config. Possibly a section-streaming race where
   Plane A nametable updates land mid-deform-frame, or a residual
   per-line FG entry left in `Hscroll_Buffer` from a previous config.

3. **BG warps on its own when stationary.** With camera stopped, the
   BG plane keeps animating despite `Parallax_Deform_Phase_FG/BG`
   *never being incremented* by any code path (verified via grep of
   `s4.lst`). The animation source is unidentified — possibly the
   per-line H-deform sample reading garbage past the buffer when
   per-cell DMA mode is active but per-line fill ran.

**Current state:** Workarounds in place make the system not crash and
mostly render correctly. Multi-band horizontal parallax works, sine
deform on clouds is visible, per-section configs resolve. The artifacts
above are polish issues that compound on top of the upstream clobber
documented below; trying to patch them individually keeps producing
new failure modes.

**When to revisit:** When the upstream `Parallax_Current_Config` /
`Camera_Y` clobber (below) is root-caused and fixed, re-test all three
artifacts. If they persist, debug separately with the upstream noise gone.

---

### Parallax effects library — expansion backlog (§4.6)
**Surfaced during:** §4.6 polish session 2026-04-28.
**Where:** `data/parallax/effects/` — each effect is a self-contained file (deform table + parameterised macro + named variants). Two entries shipped so far: `heat_shimmer.asm`, `wave_rocking.asm`.

**Pattern to follow when adding effects:**
1. One file per effect under `data/parallax/effects/`.
2. Header comment: visual description, mechanism, tuning knobs, dependencies.
3. Shared deform table (one in ROM) + a `<effect>_config` macro that takes camelCase params (AS limitation — no underscores in macro args).
4. A few pre-named variants (`_Slow`, default, `_Fast`) for casual use.
5. Add an `include` line to `main.asm` after `ojz_default.asm` (some effects depend on `DeformTable_Zero`).

**Effects to add (ranked by ease/impact):**
- **screen_shake.asm** — short-duration triangle table at high speed. Per-column V or per-line H. Triggered by gameplay events; needs a "fade out over N frames" wrapper. Earthquake / explosion impact.
- **water_surface.asm** — combined per-line H sine + per-column V sine (90° offset). Hydrocity-style ambient water surface. Complex — verify VBlank budget.
- **mirage.asm** — extreme low-amplitude (1 px) high-frequency H-deform on a single mid band. Distant heat haze without affecting near terrain.
- **vortex.asm** — sawtooth H-deform + sawtooth V-column with reversing phase. Boss room / portal swirl.
- **earthquake.asm** — random/noise table V-column at high speed for ~30 frames, then quiesces. Procedural noise table generator helps here (a `deform_table_noise` macro, peer of sine/triangle).
- **banking.asm** — linear V-column ramp whose slope tracks Camera_X velocity. "Tilts into turns." Needs runtime parameter feed (Camera_X velocity → vDeformShiftBg adjustment).
- **falling.asm** — accelerating linear V-column ramp during fall sequences. Pairs with vertical scroll mechanics (§4.2 deferred).

**Deeper effects (need new mechanisms):**
- **raster_perspective.asm** — true 3D pseudo-perspective floor via per-LINE H-scroll programmed by HBlank IRQ. Sonic 2 special stage / S3K bonus stage feel. Different feature, not just a new table — needs HInt handler + per-line H-scroll arithmetic. Tracks as §4.7 task.
- **palette_cycle_band.asm** — recolour a band as the deform phase advances. Combines with existing effects. Needs palette-cycling pipeline.

**When to revisit:** When level design surfaces a specific need ("this zone wants underwater wobble", "the boss room needs a vortex"). Build effects on demand rather than speculatively.

### OJZ scroll-test sky-tint section marker (T15 diagnostic — remove later)
**Surfaced during:** §4.6 T15 testing 2026-04-28.

The `OJZScroll_Update` per-frame logic writes a section-id-keyed color into `Palette_Buffer[0]` (CRAM[0] = backdrop) so the sky tints differently per section: Sec0 black, Sec1 red, Sec2 green, Sec3 blue, Sec4 yellow, Sec5 magenta, Sec6 cyan, Sec7 gray, Sec8 white. The color table is `OJZ_SectionMarkerColors` at the bottom of `test/ojz_scroll_test.asm`. Useful for diagnosing slot rotation and section streaming visually.

**Why deferred:** this is a debug/development aid, not a shipping feature. Remove or gate behind a debug flag once OJZ has real visual content per section (e.g., distinct palettes, tile art, props) that makes the section identity obvious without a marker.

**When to revisit:** once §3 player physics is in and we're playtesting actual gameplay, the diagnostic tint will be confusing. Strip the marker code (~25 lines + the table) and let the per-section palette do the storytelling.

### ~~Section rotation should be block-style, not rolling~~ — DONE 2026-04-28
**Completed in:** §4.6 T15 commit. `Section_TeleportFwd`/`Bwd` now advance both slots by 2 sections per teleport (block-style), matching `SECTION_SHIFT = $1000` and the user's "infinite forward walking" intent. Architecture doc §4.1 still describes the older rolling-leapfrog model and needs updating in T17.

### [DEAD CLUSTER] ~~Section rotation cascading work (§4.2 architectural fix)~~
> **VOID — see the DEAD CLUSTER banner.** Slot rotation, `SECTION_SHIFT`, the RC/LC trackers and
> the preload bandwidth model all went with the subsystem. `Section_UpdateColumns` survives by
> name only — it is now a continuous-scroll column streamer, not a slot-pair ring walker, so its
> "ring-buffer math" bullet does not describe today's routine.
**Surfaced during:** §4.6 T15 testing 2026-04-28.

**State:** The rotation logic itself is now block-style (shipped 2026-04-28). The cascade work below remains.

1. **`Section_UpdateColumns` ring-buffer math.** Currently assumes the rolling model — RC/LC trackers reset to fresh-streaming state and assume slot 1 = next section, slot 0 = continuation. With block-style, both slots are new at teleport, both need cold-fill streaming. Requires `FG_RedrawForSection` sibling to `BG_RedrawForSection` (already a separate deferred entry) so the visible content doesn't streak in over multiple frames after teleport.

2. **Preload bandwidth double-up.** Currently preload only loads slot 1's next section. Block-style needs both slot 0's *and* slot 1's next sections pre-fetched (= up to 2 sections of art queued during the slot 1 traversal). Doubles preload DMA bandwidth requirement; may need bigger preload window or velocity-based timing tightening to avoid mid-teleport stalls.

3. **Landing flag (separately deferred).** With block, post-teleport camera lands at `$200` (start of new slot 0), and walking left immediately fires BWD threshold. The `$0FFF` SHIFT nudge fixes that; the proper fix is sonic_hack's landing flag.

**When to revisit:** §4.2 polish session. Pair with FG_RedrawForSection and landing flag — they're all the same teleport pipeline.

**When to revisit:** §4.2 polish session. Pair with the FG-redraw work and the landing-flag mechanism; they're all the same teleport pipeline. Recommend reading `sonic_hack/code/engines/section_streaming.asm:Section_ForwardTeleport` end-to-end as the reference implementation.

### [DEAD CLUSTER] ~~Plane A "fill-in" after teleport (§4.2 streaming polish)~~
> **VOID — see the DEAD CLUSTER banner.** There is no teleport, so there is no post-teleport
> fill-in. `Section_RedrawPlanes` does survive (it is one of the six real exports) but as the
> synchronous initial plane fill at level start, not as a teleport repair path.
**Surfaced during:** §4.6 T14 testing 2026-04-28.

**Symptom:** Crossing a section teleport boundary (`$1200` FWD or `$200` BWD), Plane A foreground content visibly "runs in" over ~2-3 frames as `Section_UpdateColumns` re-streams the visible 40 columns into the plane. User wants the teleport to be imperceptible — same content visible before and after.

**Why it happens:**
- After `Section_TeleportFwd`/`Bwd`, slot rotation relabels plane cols (slot 0 ↔ slot 1) but does not move data — plane content still has the OLD slot mapping's tiles.
- `Section_Right_Col_Written` / `Left_Col_Written` reset to fresh-streaming state. `Section_UpdateColumns` then gradually re-fills columns from the new slot map.
- `PLANE_BUFFER_SIZE = 1536` bytes only holds ~15 columns of strip data per frame; the visible 40-column window takes 2-3 frames to fully refresh.

**`BG_RedrawForSection` already handles plane B at teleport** (full-section rewrite via dedicated batch path, drains in 1-2 VBlanks). Plane A doesn't have an equivalent — it relies on the per-frame streaming machinery.

**Fix paths (ranked by complexity):**
1. **`FG_RedrawForSection` sibling.** Mirror BG's batch redraw, queueing 64 plane cols of new slot 0 + slot 1 content into `Plane_Buffer` at teleport. Requires `PLANE_BUFFER_SIZE` increase to ~6400 bytes (= ~5KB extra RAM) so the burst fits in one frame. Drains in 1-2 VBlanks via existing `VInt_DrawLevel`. Cleanest but eats RAM budget.
2. **VRAM DMA from staged source.** Pre-build a 4096-byte plane-half template during preload phase, then DMA-fill into VRAM at teleport. Faster than direct writes, doesn't need bigger Plane_Buffer. New infrastructure required.
3. **Brief display-off during teleport.** Disable display, blast plane via direct VDP writes (huge VRAM bandwidth available with display off), re-enable. 1-2 frames of black. Simplest but ugly.
4. **Live with the streaming fill-in.** Current state. ~33-50ms of "running in" content. Tolerable for early demos; not shippable.

**When to revisit:** §4.2 polish session. Path 1 is the most aligned with the current architecture; path 2 is where to head once we're tightening the engine. Reference `BG_RedrawForSection` as the model — Plane A version follows the same structure but writes 32 nametable cols × ~30 rows per slot.

### [DEAD CLUSTER] ~~Section teleport landing-flag mechanism (player-physics polish)~~
> **VOID — see the DEAD CLUSTER banner.** The `SECTION_SHIFT = $0FFF` stopgap it describes, the
> `$200`/`$1200` thresholds, and `Section_Check` are all deleted. The physics concern that
> motivated it (a player flung past a boundary by a spring or terminal fall) is real and
> permanent, but under continuous scroll there is no boundary to be flung past — it degenerates to
> ordinary camera clamping.
**Surfaced during:** §4.6 T14 testing 2026-04-28.

**Current state:** `SECTION_SHIFT = $0FFF` (= FWD - BWD - 1) so post-teleport camera lands 1 px inside the safe zone, preventing idle oscillation between `$200` and `$1200`. Works for the OJZ camera-driven scroll test where camera is bounded directly by `cam_min_x` and user input is at fixed pixel-step.

**Why it's a stopgap:** when player physics arrive, the camera will follow a player position that can be flung past thresholds by springs, knockback, terminal-velocity falls, or other physics impulses. A 1-pixel margin is too narrow for momentum-based crossings — the player may overshoot and re-trigger the opposite teleport before they can move into a safe zone.

**The proper fix (sonic_hack pattern):** state-based suppression rather than geometric margin.
- Add a `Section_Teleport_Landing_Flag` byte to RAM (or reuse a bit in `Section_Preload_Flags`).
- On FWD teleport: set the landing flag.
- On BWD teleport: set the landing flag.
- In `Section_Check`: if the landing flag is set, suppress whichever teleport check is opposite to the most-recent direction. (Or: always suppress until the flag clears, which is symmetric.)
- Clear the flag when camera enters the central safe zone (e.g., `$0400 < camX < $09FF`). User must move into the safe zone before any further teleport can fire.

**Reference implementation:** `sonic_hack/code/engines/section_streaming.asm:Section_Check` lines 1100-1150. They use `ss_flags` bit 4 + `ss_landing_timer` for the same purpose; their thresholds are also asymmetric (FWD inclusive at `$1200`, BWD strict-less-than at `$200`) which complements the flag.

**When to revisit:** when integrating player physics (§3 spec). Restore `SECTION_SHIFT = $1000` at the same time so post-teleport camera lands exactly at the boundary, and the landing flag handles the rest. Until then, the `$0FFF` nudge is a clean equivalent for the camera-driven test setup.

### ~~VDP register $0B (mode_set_3) propagation bug — workaround in place (§4.6)~~ — **MISDIAGNOSIS, CLOSED (corrected 2026-08-05)**
> **⚠ THERE IS NO `$0B` PROPAGATION BUG. This entry asserts a live hardware defect that the same
> file already retracts.** The retraction is ~60 lines earlier, in the per-cell HScroll entry
> (2026-06-23), and is unambiguous:
> > "**`$0B` is NOT the problem.** With `deformBg` dropped, the VDP register `$0B` reads `$02`
> > (`hscroll_mode: cell`) correctly — per-cell IS active and the shadow→register propagation
> > works fine. The original `DeformTable_Zero` comment's 'intermittent `$0B` stuck at `$03`'
> > explanation was a **MISDIAGNOSIS**"
> — and the attempted flush-side fix (`Flush_VDP_Shadow`, branch `fix/vdp-mode3-propagation`)
> changed nothing and was deleted.
>
> **The real cause was band-boundary precision:** smooth per-pixel vertical parallax puts band
> boundaries on arbitrary scanlines (one measured at line 22), and per-cell mode can only change
> scroll at 8-px cell rows, so it tears at every band boundary during scroll. Per-line is therefore
> **mandatory and permanent**, not a workaround.
>
> **The per-frame `$0B` force described here is also gone.** `games/sonic4/test/ojz_scroll_test.emp:70`
> writes the shadow byte and dirty mask **once, at init** — it is not re-forced per frame.
>
> **Do NOT action the four "when to revisit" investigation leads below** (interrupt-time VDP_CTRL
> writes, Z80 bus interaction during shadow flush, boot register ordering, clean-place `$8B02`
> write). They chase a bug that does not exist. The whole entry stands as historical record of a
> misdiagnosis — and, per its own retraction's lesson, as the reason this repo now insists on
> reading the actual VDP register before theorizing, and on verifying under continuous motion.
**Surfaced during:** §4.6 polish session 2026-04-28.

**Symptom:** When `pcfg_deform_table_fg` and `pcfg_deform_table_bg` are both NULL (e.g. ParallaxConfig_OJZ_Default), the parallax pipeline auto-selects per-cell HScroll mode: `Parallax_Fill_PerCell` writes 28 longwords, the per-cell static DMA enqueues 112 bytes, `setVDPReg vdp_mode3 = $02` marks shadow dirty, and Flush_VDP_Shadow writes $8B02 to VDP_CTRL on every VBlank. Visually we expected per-cell HScroll: all 28 cell rows scroll uniformly with the same `-Camera_X`. We observed instead per-line behavior: only scanlines 0-27 (the top 28 px = 3.5 cell rows) scrolled correctly, lines 28-223 stayed pinned to plane col 0.

**Empirical proof of per-line state:** Patching VRAM HSCROLL_TABLE entries 28-223 directly with proper PA values via `mcp__exodus__emulator_write_vram` made the entire screen scroll correctly. This is only possible if VDP register $0B has bits 1:0 = %11 (per-line). VDP shadow byte at offset 11 reads $02 and dirty bit 11 stays set, but the visual proves register $0B is $03.

**What we tried (all failed):**
- `setVDPReg vdp_mode3, #$02` every frame in OJZScroll_Update (shadow + dirty path).
- Direct `move.w #$8B02, (VDP_CTRL).l` with stopZ80 wrap.
- Adding a state-machine reset (`move.w (VDP_CTRL).l, d1`) before the direct write to clear any half-finished 32-bit address command.
- None changed the register's per-line behavior.

**Workaround in place (2026-04-28):**
- `data/parallax/ojz_default.asm` defines `DeformTable_Zero` (256 zero bytes) and adds `deformBg=DeformTable_Zero` to both `ParallaxConfig_OJZ_Default` and `ParallaxConfig_OJZ_Floor`. This forces the entire pipeline (Parallax_Update auto-select, Enqueue_Dirty_Buffers DMA selector, OJZScroll_Update mode_set_3 force) into per-line mode for these no-/V-only-deform configs.
- Cost: ~1500-2000 extra cycles per frame (224-line fill vs 28), 8× HScroll DMA bandwidth (896 vs 112 bytes), 256 bytes ROM for the zero table. With sample = 0 the deform sampling adds 0 to each line — no visual change.
- ParallaxConfig_OJZ_Windy was unaffected (it has a real BG H-deform table and was already per-line).

**When to revisit:** When the per-cell mode is needed for performance budget. Investigation should focus on:
1. Possible interrupt-time VDP_CTRL write that lands between Flush_VDP_Shadow and the next render.
2. Possible Z80 bus interaction during the shadow flush — the Z80 isn't stopped during Flush_VDP_Shadow's individual `move.w` writes.
3. Re-examine whether Boot's initial VDP register write loop properly writes $0B = $00 then OJZScroll_Init's setVDPReg path correctly upgrades it to $02 on first VBlank.
4. Try writing $8B02 to VDP_CTRL in a known-clean place (e.g. immediately after `Flush_VDP_Shadow` returns, with explicit Z80 stop) and observe if behavior changes.

**Bare-minimum reproduction:** Remove `deformBg=DeformTable_Zero` from `ParallaxConfig_OJZ_Default`, build, load OJZ scroll test, scroll right. FG bricks scroll correctly only on top 28 scanlines; rest of the screen shows plane A column 0 stuck.

### ~~Parallax_Current_Config / Camera_Y intermittent clobber (§4.6)~~ — ROOT-CAUSED + FIXED 2026-06-10
**Root cause:** `TestPlayer_Main` read `Ctrl_1_Press` into **d7 — the RunObjects
loop counter** (object routines must preserve a0/d7). Every press edge extended
the player slot loop by the press bitmask value: the dispatcher marched up to
255 slots past `Player_1`, re-running live objects, then executing free-stack
words and arbitrary RAM as `code_addr` offsets into `ObjCodeBase`. Real object
routines invoked on garbage "slots" wrote SST fields through a0 at arbitrary
RAM (the zeroing symptom); level data executing as code produced stray writes
like `$FF71FF71` (the garbage symptom) or ILLEGAL INSTRUCTION (live crash
captured in Exodus 2026-06-10: a0=$FFFF9E14 = Dynamic_Free_Stack, d7=1,
caller RunObjects.always_next, jump target OJZ_SEC2_BLOCKS+$1640).
**Fix:** press bits moved to d4 (`objects/test_player.asm`); debug builds now
assert the a0/d7 loop contract after every dispatch (`Debug_AssertObjLoop`,
`engine/objects/core.asm`). Pointer-validation band-aids removed from
`Enqueue_Dirty_Buffers`, `Parallax_Update`, `Vscroll_Write`, and the OJZ test
mode-set-3 force. Re-test of the three §4.6 visual artifacts done 2026-06-11 —
all three resolved (see the artifacts entry above).

Original investigation notes kept for reference:
**Surfaced during:** §4.6 T12 testing (2026-04-27).
**Symptom:** During §4.6 T12 v2 debugging, multiple MCP reads showed
`Parallax_Current_Config = $00000000` and `Camera_Y = 0` even though
`Parallax_Init` and `Camera_Init` had set them correctly at boot. The
zeroing wasn't caught by Exodus MCP watchpoints, didn't fire the
breakpoint at the only `move.l #0, (Camera_Y).w` instruction
(`object_test_state.asm:34`, never on the OJZ scroll test path), and
no code path in the OJZ scroll test Update flow writes either field.
The corruption is intermittent — repeated single-step sessions sometimes
showed the values intact and Vscroll_Factor lerping correctly.
**Practical workaround in place:** OJZ parallax configs use
`vCenter=0, vOffset=0` so even when `Parallax_Current_Vscroll_BG` ends
up at a wrong negative steady-state value (we observed -59 instead of
the expected 62), the BG plane stays anchored at the top where the
nametable is fully populated. With OJZ being X-only-scroll in §4
Phase 1, this is functionally invisible.
**When to revisit:** When adding vertical camera scroll (§4 Phase 2+),
the parallax math depends on Camera_Y being accurate frame-to-frame.
Suspect candidates to investigate: (a) interrupt-time write through a
stale or corrupt pointer, (b) movem-out-of-bounds on the supervisor
stack at $FFFFFEF8 (lots of save/restore traffic in band loop +
VBlank handler), (c) Exodus MCP watchpoint not actually catching
writes in this build.
**Bare-minimum reproduction:** Build current `master`, load in Exodus,
let it run a few seconds at the OJZ scroll test, MCP-read
`Parallax_Current_Config` and `Camera_Y` repeatedly. Both should be
non-zero; intermittently they read zero.

### ~~OJZ Tile Art Loading — Full Terrain Visibility~~ — DONE 2026-04-26
**Completed in:** §2 Phase 2 Layer A.1 (tile dedupe + nametable remap)
**What:** ojz_strip_gen.py now globally dedupes tile data with hflip/vflip canonicalization across all 16 sections and rewrites strip files to reference the new compact index space. The deduped pool (10 tiles for OJZ act 1's current visible 48-row strip band) loads via Level_LoadArt → S4LZ_Decompress → DMA. Strip tile-index ceiling collapsed from 1856 → 9; nametable at VRAM $C000 is no longer at risk of being clobbered.
**Caveat:** Visible band still capped at strip rows 0-47 (sprite attribute table at VRAM $D800 = nametable row 48). Showing the *full* layout (chunk rows 2-12 of the 16-row OJZ layouts, the actual ground terrain) requires vertical-axis section transitions (still §4 deferred) or relocating the sprite table out of the Plane A nametable region (not currently planned). The pipeline is correct end-to-end; only the camera/strip envelope limits how much of OJZ becomes visible at once.
**Measurements:** see `docs/research/tile-pipeline-measurements.md`.

---

### ~~Chunk/block parsing produces mostly-empty tiles~~ — DONE 2026-04-26
**Completed in:** kos_decompress rewrite
**What:** Root cause was the homegrown Kosinski decoder in `tools/ojz_strip_gen.py` — subtle bit-order / displacement bugs that produced ~5× too much output and ~50% of blocks parsing as all-zero. Hypothesis 1 (multi-stream Kosinski) was wrong; hypothesis 2 (block-ID mask) was wrong. Real bug was the decoder itself. Fixed by porting `sonic_hack/code/engines/kosinski.asm` KosDec literally to Python: LUT bit-reversal of each descriptor byte + `add.b`-style MSB-first reads, exact stream-copy semantics matching the asm.
**Post-fix verification:** chunk 0x3f now references blocks 272-302 (all 4/4 non-zero, real ground data). Block count: 374 (was 2002 garbage). Tile art: 919 tiles (was 322 truncated). 141 unique source tile indices in OJZ act 1 sec0 strips (was 14). With this fix + a related palette-line-1 offset fix in the test state (sonic_hack's `palptr Pal_OJZ, 1` means OJZ palette occupies CRAM lines 1-3, not 0-2), the OJZ scroll test now renders actual OJZ art with correct green palette. Verified via Exodus Plane A viewer.
**Bonus learning:** Investigation revealed I had been over-confidently calling sparse-pixel screenshots "clean rendering" through A.1-A.3 verification. Honest visual ground truth (level editor screenshots from the user) was what surfaced the bug. Process lesson saved as a memory.

## From §7 — Visual Effects (design-stage)

### Palette transition on section crossing (§4.8 / §7.1) — NOT IMPLEMENTED — recorded 2026-08-08
**Surfaced during:** 2026-07-15 alignment audit (ENGINE_ARCHITECTURE.md presented palette-transition-on-crossing as if shipped; zero implementation existed). The doc claims were re-marked honestly (§7 banner, §7.1 shipped-vs-planned split, §4.2 `sec_pal` "descriptor field only", §4.8 blend-sections status) — this entry is the backlog row those pointers land on.
**What:** No section-crossing palette code exists in `engine/level/` (verified 2026-08-08: no palette/CRAM/fade references there at all). `sec_pal` and `sec_pal_cycle` are reserved descriptor fields with no runtime consumer. The shipped palette path is game-poked only: game code writes `Palette_Buffer` + `Palette_Dirty` bits and `Enqueue_Dirty_Buffers` DMAs dirty lines to CRAM (§7.1). The planned design — descriptor-driven palette load on crossing, instant or ~16-frame RGB-lerp cross-fade, per-section cycling, blend cells (§4.8) — is future §7 work.
**Blocked by:** §7 Visual Effects execution (palette-system design phase); nothing technical. The Deep-Forest-BG entry's "per-section palette variants" (below) is the cheap first step and depends on the same mechanism.

---

## From §4.6 — Parallax (post-T17 backlog)

### Per-block linear interpolation deformation format
**Blocked by:** N/A — deliberately not in v1.
**What:** S.C.E.'s block-based deformation table format with high-bit linear-interp flag. Variable-height blocks save ROM (~32 bytes vs ~256 bytes per table). v1 uses full 256-byte time-varying tables — block format is a ROM-saving optimization we don't currently need.
**When ready:** if a section's deformation table waste becomes a real ROM problem (currently affordable — 256 B per shape, shared across sections that use the same shape).

### Per-band deformation table pointers
**Blocked by:** visual demand for different wave shapes per band.
**What:** Each band points at its own 256-byte deform table. Currently single shared table per section (`pcfg_deform_table_fg` / `_bg`) + per-band amplitude/phase via `BAND_DSA/B` and `BAND_PHASE`. Adds 4 bytes per band (table pointer field) + multiple tables per section.
**When ready:** when a section visually requires different shapes per band — e.g., square wave for one band, sine for another.

### Per-band frequency variation
**Blocked by:** visual demand.
**What:** Per-band `phase_increment` byte. Currently only phase OFFSET varies per band (frequency is section-wide via `pcfg_deform_speed_fg/bg`).
**When ready:** when "different speeds per band" surfaces as a clear visual need.

### Plane A per-column V-scroll
**Blocked by:** use case (ground-plane warping is rare in Sonic-style platformers).
**What:** `pcfg_v_deform_table_fg` field is reserved but not wired in v1. Currently the FG plane always uses whole-plane V-scroll; `Vscroll_Write`'s per-column branch only writes the BG word per column-pair from `Parallax_Vscroll_Column_Buf`. Implementation is symmetric to the BG path — ~30 cycles + 80 bytes RAM for an FG column buffer + the fill code in `Parallax_Update`.
**When ready:** when a section needs ground-plane vertical warping (special-stage 3D floors, post-explosion ground sink, banking-platform foreground variants).

### Sprite mask for per-column V-scroll leftmost-partial-column garbage
**Blocked by:** sprite system + zone level data hooks.
**What:** Genesis VDP per-column V-scroll grain is 16 px. With non-zero plane B HScroll, the leftmost screen sliver renders at V-scroll = 0 regardless of VSRAM[0] — silicon-level, no register fix. v1 mitigates either by: locking plane B HScroll to 0 (`FACTOR_0`) which eliminates the partial column, or accepting the artifact. Real games drop a 16-px-wide sprite mask over the left edge to hide it (Sonic 3 Hydrocity boss arena, Streets of Rage banking, etc.).
**When ready:** when a section uses per-column V-scroll *and* wants non-zero plane B HScroll. ~1 sprite/frame overhead from the 80-sprite budget.

## From §4.9 — Section-Local Entity Management

### ~~§4.9.4 Rolling 4-Slot State Tracking (Respawn Memory)~~ — SHIPPED 2026-06-12
**Resolution:** `Ring_Collected_Park` (4 × 33 B rolling park, 134 B total) parks a section's
collected/killed bitmasks when `Collected_UpdateCenter` evicts it from the 3×3 window
(pristine sections skipped) and restores them in `Collected_ClaimSlot` on re-entry.
3×3 window + 4 park = 13 remembered sections — covers OJZ's whole act (zero resurrection);
larger acts degrade classically at long range. Spec: `docs/superpowers/specs/2026-06-12-respawn-memory-design.md`,
commit 235e200. Follow-ups from review (minor): (1) restore-leg verification read only the
collected mask — re-verify the killed mask round-trip plus a live no-respawn census when a
killable object path exists; (2) freed park entries aren't preferentially reused — rolling
overwrite can evict a live entry while a freed slot idles (effective capacity dips under
mixed traffic; spec-compliant, revisit if park pressure appears); (3) natural-eviction
retest needs an act larger than 3×3 — re-run when one exists.

### ~~§4.9.5 Warp-Based Teleport Preview (Entities in Preview Zone)~~ — SHIPPED 2026-06-12
**Resolution:** Visibility-derived window makes preview intrinsic. The despawn envelope overlaps sections ahead of the camera before any teleport fires — those sections are tracked, their entities are in the buffer. No warp coordinates, no coordinate shift, no integration work. Closed by the visibility-window plan (branch `vertical-entity-window`); see ENGINE_ARCHITECTURE.md §4.9.3.

### Bouncing "Loss Rings" (Ring Scatter on Damage)
**Blocked by:** §4.9 ring system + player damage system
**Surfaced during:** §4.9 design session 2026-04-29.
**What:** When the player takes damage, scatter N rings as temporary SST objects (not buffer entries). Each has physics (gravity, bounce), a lifetime timer, and can be re-collected. Uses AllocEffect slots (lightweight). These are separate from level-placed buffer rings — buffer rings are static positions with bitmask state, loss rings are short-lived physics objects.
**When ready:** After player damage/hurt system exists (§3 player physics) and ring collection works.

### Ring Attraction (Magnet Shield)
**Blocked by:** §4.9 ring system + shield system
**Surfaced during:** §4.9 design session 2026-04-29.
**What:** When player has magnet shield, uncollected rings within attraction radius accelerate toward the player. Modifies the per-frame ring collision check to also compute distance and apply pull velocity. Only affects buffer rings within range — loss rings (SST objects) would have their own attraction in their object code.
**When ready:** After shield system exists (§3 player abilities).

## From Teleport-Rebase (2026-06-10)

### ~~CRITICAL: FWD teleport advances slot pair out of a narrow grid~~ — DONE 2026-06-11
**Surfaced during:** teleport-rebase verification 2026-06-10 (pre-existing). **Fixed in:** grid-edge branch.
**What it was:** `Section_TeleportFwd` advanced the pair `(0,1) → (2,3)` but OJZ act1 is a 3×3 grid — sec_x=3 doesn't exist; the entity window built scan state from a garbage Sec pointer → DEBUG assert in `Collected_CheckRing` (release: undefined ring spawns) on walking right past `x=$1200`.
**Fix shipped:** `SEC_VOID` ($FF) sentinel in slot-1 sec_x past the grid; guards in `Section_Check .fwd_check` (sentinel check before the wrapping addq), TeleportFwd's SS_RESIDENT mark, EntityWindow Init/Rebuild slot-1 blocks (skipped; `Entity_Window_Active`=1; the stale entry's section_id stamped SEC_VOID for the despawn exemption), camera max-x void clamp ($8C0 = slot-0 right edge), `TileCache_DecompressBlock` world-edge guard (out-of-grid blocks decompress blank — also fixed the latent bottom-edge Sec-table overread that vertical fills have had since shipping), prefetch sec_x guard. BWD heals the pair (new slot 1 = old slot 0 − 1). Exodus-verified end to end (warp right → pair (2,$FF), objects spawn, camera pins $8C0, BWD returns (0,1)).
**Still open (minor, from review):** `Section_Check` clobber header understates; classic-style player X clamp at camera bounds (player can currently walk past the camera into the void region — level data should wall it, but a bounds clamp matching the classics is worth considering with §3 player physics).

### ~~Per-section BG layout swap at the seam (T2/T3 zones)~~ — SUPERSEDED 2026-06-12
Superseded by the full BG seam-streaming spec ("From Deep Forest BG Work
(2026-06-12)" below). The original observation stands: teleports no longer
run `Section_RedrawPlanes`, all production data is T1, and any per-section
BG needs a non-blocking streaming mechanism, not a synchronous blit.

## From Deep Forest BG Work (2026-06-12)

### SPEC: Per-section background grid with seam streaming
> **Update (2026-08-08):** a full research pass
> (`docs/research/2026-08-08-bg-seam-streaming.md`) corrected four of this
> sketch's assumptions before design: layouts are **64×64/8192 B** (not 64×32 —
> re-derive all byte math); the transport should be the **`Plane_Buffer`** path
> (the purpose-built zero-caller `Draw_BG_TileColumn` already exists there —
> not `QueueDMA_Deferrable` as written below); horizontally there is **no single
> BG camera** (per-band `Parallax_Current_Scroll_B` — the uniform "camX/8 margin"
> math below only holds vertically, which locks in the vertical-first order); and
> the tile ceiling is 448 (the two-half-pool idea stands). That doc carries the
> revised build order + the open user rulings; this sketch remains the component
> inventory.
**Goal:** each section (or section row/column) gets its own background from
the editor's per-section BG assignment, and the engine stitches them into
one continuous world as the player travels — no visible swap, both axes.
User intent: "section below the forest has the darker firefly one, and the
tree one above connects to it."

**Why it works (the headroom argument):** Plane B is 64×64 cells (512×512px)
but the screen shows only 320×224. At the BG's parallax factors the hidden
margin is enormous in camera terms: vertically, 288 hidden px at camY/8 =
2304 camera px (more than one 2048px section row) before an off-screen row
wraps back into view; horizontally, 192 hidden px at camX/8 = 1536 camera px.
Rows/columns that scroll off one edge are rewritten with the NEXT section's
BG via QueueDMA_Deferrable long before they re-enter from the other edge —
the same trick as FG column streaming, applied to Plane B on both axes.
Bandwidth is trivial: one plane row or column = 128 bytes; a few per frame.

**Components:**
1. **BG grid data.** Zone data gains a BG-grid table: section (or section
   row/col band) → {nametable region ptr, tile blob ptr, anim band table
   ptr, palette line variant}. Editor already has per-section BG assignment
   (UI exists, engine unwired); injector emits the grid instead of the
   single zone-wide override.
2. **Seam tracker + row/col streamer.** Engine-side state: which BG region
   each plane row/column currently holds, and a per-frame budgeted streamer
   that rewrites rows/cols in the hidden margin toward the target (derived
   from camera section position + scroll direction). Mirrors the FG
   preview-column scheduler. Teleport rebases are coordinate-invariant on
   the plane (mod 512), same as FG — the streamer keys on world-derived BG
   scroll, not raw camY.
3. **Tile budget across the seam.** Both themes' tiles coexist in VRAM while
   a seam is in transit. Strategy: split the 448-tile BG pool into two
   half-pools (~224 each, minus shared animated slots); the streamer loads
   the incoming theme's blob into the inactive half (deferrable DMA, chunked)
   before its nametable rows reference it. Editor enforces per-theme budget
   (set_bg validator) and a shared-atlas option for themes that intentionally
   share tiles (forest ↔ darker forest).
4. **Animated bands per theme.** BgAnim_Table is per-act today; becomes
   per-theme, swapped when the seam fully clears the screen (bands reference
   fixed VRAM slot ranges, so the safe-swap moment = no on-screen rows from
   the outgoing theme). The table-driven design (driver/rate/dest per band)
   already supports this — needs a "active table ptr" indirection + handoff.
5. **Seam contract in the editor.** Two modes per adjacent BG pair:
   - **connects-to:** the arts' meeting edges are authored to blend (e.g.
     forest bottom rows = firefly zone top rows). Editor feature: edge
     preview of A-bottom against B-top (and A-right against B-left), plus
     a palette-compatibility check.
   - **disconnected:** transition must be masked. Two sanctioned tricks:
     (a) FG occlusion — level geometry covers the full screen height while
     the seam crosses (cave mouth, tunnel, waterfall; classic S3K), with an
     instant region swap while occluded; (b) palette blackout — fade the BG
     CRAM line to black over ~16 frames, swap/stream while black, fade up
     (thematically free for caves; needs the per-section palette mechanism).
6. **Per-section palette variants** (cheap multiplier, can ship first):
   same art, darker/tinted CRAM line per section row, lerped at the seam.
   The harness's per-section sky-tint table is the prototype.

**Constraints / open questions:**
- Vertical wrap vs themes: the current 512px art wraps seamlessly (camY/8 ×
  $1000 rebase = exactly one plane height). With per-row themes, the wrap
  must land on the THEME boundary — keep vFactorBg=3 and make each theme's
  vertical slice 512px (one full plane per section row) or 256px (two rows
  per plane); pick during design.
- Diagonal travel: two seams (X and Y) can be in transit at once; streamer
  must handle a 2D dirty region, or sequence one axis at a time with the
  hidden margin as slack.
- Parallax config per theme: band factors may differ per BG (the Sec3
  LockedClouds incident shows per-section configs + plane-space bands must
  agree); fold parallax config into the theme record so it swaps with the
  art under the same safe-swap rule.
- Budget the streamer against the existing deferrable consumers (BgAnim
  banks, DPLC, section streaming) — the queue is shared.

**Suggested build order:** (a) per-section palette variants (standalone
win), (b) vertical-axis streaming with connects-to seams only (forest →
firefly section: the motivating case), (c) horizontal axis + disconnected
transitions (palette blackout first, FG occlusion as level-design tooling),
(d) per-theme anim-table + parallax-config handoff, (e) editor seam
contracts + budget validation.
**When ready:** next major BG work block; (a) any time.

## From Vertical Entity Window — Task 6 (2026-06-11)

### ~~Teleport keep-range tests pre-shift coords against the post-rebase camera~~ — DISSOLVED 2026-06-12
**Resolution:** The keep-window no longer exists. The visibility-derived window retains all entities across a teleport (shift, no despawn); there is no keep-range test to get wrong. This defect was only relevant under the old TeleportShift keep-window/despawn design, which was deleted in the visibility-window plan.

### ~~No survivor continuity across teleports (per-entry loaded masks can't cover off-window sections)~~ — DISSOLVED 2026-06-12
**Resolution:** The keep-window no longer exists. The visibility-derived anchor is invariant across rebases — the same sections are tracked before and after — so there are no "just-left-the-window survivors" to worry about. The duplicate-spawn risk that blocked the keep-range fix is also gone: teleports never populate, so no re-add can occur. Closed by the same design deletion.

## From Vertical Entity Window — Task 8 closeout (2026-06-11)

### [DEAD CLUSTER] ~~X-BWD clamp-to-zero degenerate slot pair~~
> **VOID — see the DEAD CLUSTER banner under §4.** `Section_TeleportBwd` and its clamp-to-zero
> path are deleted, and there is no slot pair to be degenerate. The `section.asm ~:481` anchor is
> doubly dead (the file is `.emp` now, and the routine is gone). The "revisit if any act starts at
> an odd `sec_x`" trigger can never fire.
**Surfaced during:** Task 8 teleport-table review 2026-06-11.
**What:** From an odd start `sec_x`, `Section_TeleportBwd`'s clamp-to-zero (section.asm
~:481) can produce BOTH slots tracking section 0 — a two-entries-same-section window
state that nothing else can create. The teleport disjointness/no-op argument is
unaffected (the moved block is still disjoint from the old one), but the duplicate-entry
state itself is untested: two scan states + two loaded-mask slots for one section.
**When to revisit:** if any act ever starts at an odd `sec_x`. All current acts start
at `sec_x = 0`.

### SEC_VOID vs flat-id 255 alias
**Surfaced during:** Task 8 closeout review 2026-06-11.
**What:** `SEC_VOID = $FF` lives in the same byte namespace as flat section ids, and on
a 16×16 grid the real bottom-right section has flat id 255 = $FF — a void-sentinel
alias. Separately, `EntityWindow_BuildEntries`' void path stamps the sentinel but does
NOT clear the entry's loaded-mask slot (safe today only because `InitSection`'s
compare-clear wipes it whenever a real section later claims the entry).
**When to revisit:** if act grids ever approach 16×16 (current max is 3×3), or if any
new consumer reads `Entity_Loaded_Masks` for void entries.

### RescanY burst is unbudgeted
**Surfaced during:** Task 8 closeout review 2026-06-11.
**What:** A 128px coarse-row crossing re-walks all 4 entries' ROM lists from index 0 up
to each X ratchet in a single frame. Trivial on test fixtures (≤16 entities), but on
dense production levels (40-50 rings/section × 4 entries, ratchet fully advanced) the
burst could reach tens of K cycles in one frame — same shape as the tile-cache fill
bursts that needed N-way staging + a frame budget (2026-06-10).
**When to revisit:** when real level data lands — watch `Lag_Frame_Count` during fast
vertical traversal (the profiler misses single-frame bursts). Tile-cache N-way staging
is the precedent if budgeting is needed.

### Entity despawner micro-opts — **dead-field half DONE, but the refund is SPENT (corrected 2026-08-05)**
> **⚠ THE PROMISE IN THIS ENTRY IS NO LONGER DELIVERABLE — the struct will NOT shrink.**
> The dead fields `ess_ring_left_idx`/`ess_obj_left_idx` are **gone** (zero hits), so that half is
> done. But `EntityScanState` did **not** shrink to `$16`: it is still declared
> `struct EntityScanState (size: $1A)` at `engine/objects/entity_window.emp:45`, because the four
> reclaimed bytes were **immediately reused** by the trigger caches
> `ess_ring_next_x: u16 @ $16` and `ess_obj_next_x: u16 @ $18` (":engine-X of next ring/object
> entering right; $FFFF = none"). Those are live fields serving the X ratchet.
> **Anyone planning a `$1A → $16` shrink from this entry will find nothing to remove.** Also note
> the module moved: `engine/objects/entity_window.emp`, not `engine/level/`.
>
> **The other two halves are still genuinely open** and were re-verified: the loop-invariant Y
> band-bound hoist in `DespawnRings`/`DespawnObjects` (~3.5k cycles/frame at a full 128-ring
> buffer), and trimming `RescanY`'s defensive d7 save. Those remain the actionable content.
> Original text below.
**Surfaced during:** Task 8 closeout review 2026-06-11.
**What:** `DespawnRings`/`DespawnObjects` recompute the loop-invariant Y band bounds
per entity (~3.5k cycles/frame at a full 128-ring buffer — hoist to registers before
the loop). `RescanY`'s defensive d7 save around the scan calls can likely be trimmed
once the RunObjects d7 contract is re-audited. Also: `ess_ring_left_idx`/
`ess_obj_left_idx` are dead struct fields (cleared at init, never read — the X scan
is a right-edge ratchet; no left scan exists). Removing them shrinks EntityScanState
$1A → $16 and stops tempting docs into describing phantom left scanners.
**When to revisit:** alongside any other §4.9 perf work (e.g. the RescanY budget entry
above) — not worth a dedicated session.

## From Visibility-Window Plan (2026-06-12)

### Slide populate is X-unfiltered
**Surfaced during:** visibility-window plan implementation 2026-06-12.
**What:** `EntityWindow_PopulateSectionRings` (and the object equivalent) offers every entry in the section's ROM list to `TrySpawnRing`/`TrySpawnObject` without an X edge filter. On a rightward slide the newly tracked section can be up to ~$500px beyond the right load edge, so all its in-band rings are added immediately rather than waiting for the ratchet to reach them. Fine at current entity counts; could front-load spawns noticeably on dense production sections.
**When to revisit:** when production entity density lands — watch `Ring_HighWater` after a slide vs a normal X ratchet advance. Perf backlog family (tile-cache N-way staging is the precedent for budgeted populate).

### [DEAD CLUSTER] ~~Section_TeleportBwd .at_start clamp path lacks a SyncSlide-style guard~~
> **VOID — see the DEAD CLUSTER banner under §4.** `Section_TeleportBwd`, `EntityWindow_SyncSlide`,
> `EntityWindow_TeleportShift` and `Slot_Section_Map` are all deleted (zero hits each). There is no
> path to guard and the "add the defense when `Section_TeleportBwd` is next modified" trigger can
> never fire.
**Surfaced during:** visibility-window plan review 2026-06-12.
**What:** `Section_TeleportBwd` calls `EntityWindow_SyncSlide` unconditionally before the camera rebase, then may fall through `.at_start` with the slot map left as-is and still call `EntityWindow_TeleportShift`. Today `.at_start` is only reachable when `sec_x == 0` (already at the left edge of the grid — slot map parity guarantee holds). If that invariant ever breaks, the invariance assert would fire: a second SyncSlide call after an unchanged slot map with an already-shifted camera would re-derive the correct anchor, but the assert would see a mismatch. Add an Up-style guard (`cmpi.b #0, (Slot_Section_Map).w / blo.s .at_start_nop` pattern) when this path is next touched.
**When to revisit:** add the defense when `Section_TeleportBwd` is modified for any reason.

### [DEAD CLUSTER] ~~Section_Check clobber header understates~~
> **VOID — see the DEAD CLUSTER banner under §4.** `Section_Check` does not exist, nor do the
> `Section_TeleportFwd` / `SyncSlide` / `TeleportShift` handlers whose clobbers it understated.
> **Worth noting the concern was structural, not incidental**, and the engine has since gone much
> further in that direction: clobber/preserve sets are now *declared* on every proc
> (`clobbers(...)` / `preserves(...)`) and machine-checked, with declared contexts added as
> recently as HEAD `fa0ae0b`. The class of bug this entry describes is now caught by the language.
**Surfaced during:** grid-edge branch review 2026-06-11 (pre-existing).
**What:** The `Section_Check` routine header documents a narrow clobber set, but its tail-branches (`bra.w Section_TeleportFwd` etc.) enter handler routines that clobber d0–d7/a0–a4 (`SyncSlide` + `TeleportShift` rebuild paths). Any caller that saves only the documented set around `Section_Check` will see unexpected register corruption. Fix the header when opportunistically passing through.
**When to revisit:** opportunistically when touching `Section_Check` or any teleport handler.

### Row-2 seam fixtures — DOWN-direction preview only structurally tested
**Surfaced during:** visibility-window verification 2026-06-12.
**What:** Vertical slide and DOWN teleport paths are structurally exercised (window derives rows correctly, vertical streaming works), but sections 6–8 (row 2 of the OJZ 3×3 grid) have no ring or object content, so the row-2 seam has no visible entities to confirm preview behavior end to end. The structural path is proven; the content test is deferred.
**When to revisit:** when row-2 section content is authored for production OJZ or any zone with ≥3 row sections.

## From Compression Two-Tier (2026-06-11)

### S4LZ DP literal-extension undercharge
**Surfaced during:** compression-two-tier review 2026-06-11.
**What:** The DP cost model doesn't charge the 2-byte lit-count extension word for literal runs ≥ 15 words. Fixing this requires run-length-aware DP state (~16× build time) for a measured ceiling well under 0.5% of the block corpus. Not worth it; recorded so it isn't re-litigated.
**Status:** Won't fix — cost model undercharge is negligible in practice.

### S4LZ decompressor micro-optimizations (audit F4 speed wins)
**Surfaced during:** compression audit 2026-06-11 (cycle analysis in docs/research/compression-audit-2026-06-11.md).
**What:** The decoder runs ~510-640 KB/s realistic mix. Three ranked wins were measured but NOT implemented because current budgets fit (6 blocks/frame ≈ half a frame; vertical scroll protocol +4/512px unchanged with dictionaries on): (1) `move.l` in the unrolled copy tables (guard match path for offset ≥ 4) — pure literals 10.2 → 9.2 c/byte; (2) unroll the extended-count `dbf` loops (currently the SLOWEST path per byte despite being the bulk-copy case) — 22 → ~12.5 c/word; (3) 256-entry token jump table (~1.5 KB ROM) — mixed ~13.7 → ~10 c/byte ≈ 770 KB/s.
**When ready:** when block budgets grow (BLOCK_DECOMP_BUDGET > 6, bigger blocks, or new per-frame consumers) or profiling shows decode pressure.

### ZX0 needs budgeted decode before any mid-gameplay use
**Surfaced during:** compression-two-tier T6 measurement 2026-06-11.
**What:** ZX0 measured ~76 KB/s (5 frames synchronous for a 6.3 KB section blob). Today it runs only at level init (invisible). The §4.2 deferred cold-load design (mid-traversal FWD/BWD section art loads — currently stubbed) would freeze ~5-7 frames if it called `Art_Decompress` on a ZX0 blob synchronously. Before implementing deferred loads: either route them through the §9.7 pages+bookmark idle-time path (now SHIPPED — the resumable `ZX0R_Decompress` sliced across idle, never a synchronous blocking decode), or keep gameplay-streamed art on the S4LZ tier (wrapper version byte already dispatches per blob — the pipeline can mix tiers freely).
**When ready:** with §4.2 deferred cold-load implementation.

### Level editor exporter template is stale (dict fields, .zx0, blob aliases)
**Surfaced during:** compression-two-tier T2/T3 2026-06-11. Editor repo (sonic-level-editor, user-triaged commits only).
**What:** The editor's act-descriptor exporter (`src/core/export/act-descriptor.ts`) still emits the pre-compression-branch shape: `sec_reserved_2C`/pad instead of `sec_block_dict` ($2C) + `sec_block_dict_len` ($46); `OJZ_SecN_Tiles_S4LZ` labels + `.s4lz` BINCLUDEs instead of `OJZ_SecN_Tiles` + `.zx0`; 18 per-section BINCLUDE lines instead of the two generated blob-alias includes (`sec_tile_blobs.asm`/`sec_block_blobs.asm`). Nothing breaks today (the export dir isn't in the ROM build), but the NEXT editor export would hand the engine a NULL dict pointer for dict-compressed blocks. Also: `tools/ojz_strip_gen.py editor_data_available()` hardcodes `ojz/act1/section_0.tiles.bin` instead of deriving from project.json `dataPath` (same config-derivation treatment as the 2026-06-11 chunk-library move).
**When ready:** before the next editor level export; engine-side spec is all on master (structs.asm Sec fields, act_descriptor.asm as reference).
**Update 2026-06-11 (entity exporter):** entities now follow the build-step model —
`tools/ojz_entity_gen.py` generates entity_data.asm from the editor JSONs (X-sort,
validation, per-section minimized type tables, ring-buffer pressure analysis).
Direction decision: editor authors JSON, BUILD generates engine format — the
act-descriptor exporter above should eventually shrink into the same model rather
than be fixed in place. Editor-repo follow-up: placement UI checkboxes for the new
`anyY`/`xflip`/`yflip` object fields (generator already accepts them). Generator
polish backlog (review minors): friendly errors for malformed JSON/float coords,
warn on whole-act-empty dataPath misconfig, duplicate library-id check.

### Streaming polish backlog (consolidated pointers)
**Surfaced during:** vertical-streaming 2026-06-10 (full analysis in that plan's RESULTS + follow-ups).
**What:** (1) Prefetch column cursor — residual +4 vertical / +6 horizontal lag per 512px is block-row/col crossing decompresses; prefetch re-probes only the view-center column, walking the ~6 visible block columns between crossings should reach ~+1. (2) Per-VBlank plane-buffer drain budget — the deeper fix if row payloads ever grow past 2 rows/frame again. (3) DEBUG_FLY_SPEED_FAST is pinned to base speed by the 16px/f camera clamp (turbo is a no-op).
**When ready:** any perf-focused session; all measured groundwork is in docs/superpowers/plans/2026-06-10-vertical-streaming-budget.md.

### Real ring/object art at safe VRAM slots
**Surfaced during:** objects-v2 play-testing 2026-06-10.
**What:** Test objects render placeholder squares; VRAM_TEST_SONIC-era test art sat inside the FG pool (caused the debug-exit tile corruption, since fixed by relocation). Production ring/monitor/object art needs proper slots in the unified pool via the build-time allocator, replacing the placeholders so play-testing reads like a game.
**When ready:** prerequisite satisfied — §4.9 phase 2 (vertical entity window) shipped 2026-06-11; entities now spawn everywhere on both axes. Ready to pick up in any art-focused session.

---

## From Sound Driver Work (Future)

> **STATE-OF-TRUTH (2026-07-03 — supersedes the 2026-07-01 banner):** EVERY open sound entry
> below is now OWNED by a banked package of the 2026-07-03 design-banking session
> (`docs/superpowers/2026-07-03-sound-banking-queue.md`, six packages 0-6, all specs+plans on
> master). Do NOT execute any sound entry from this file directly — execute its owning package
> plan, which embeds the entry's current verified state (several entries below are stale;
> the plans record what was ALREADY fixed). Ownership map:
> - SFX Stage B/C + continuous SFX → **package 2** (`plans/2026-07-03-sfx-fidelity-stage-bc.md`)
> - deep-audit survivors D1/D4/D6/D7/B3/B5/E5-runtime → **package 4** (`plans/2026-07-03-sound-correctness-batch.md`)
> - DAC descriptor insurance + Bank-D hook + drum authoring → **package 3** (`plans/2026-07-03-dac-drum-library-readiness.md`)
> - game-feel gaps (pause/jingle/song-finished/API v2) → **package 1** (`plans/2026-07-03-sound-game-feel-moments.md`) — **EXECUTED 2026-08-09** (`sound-pkg1`; see the closing entry at the end of this file)
> - detune-unison + production features → **package 5** (`plans/2026-07-03-sound-production-suite.md`)
> - GATE articulation, opbias test, $28 guard, cold-boot pan seed, FM env seam, HCZ2 loop
>   residual, bank-latch hunt, boundary-tick check, comment rot, + ALL formal closures
>   (§6.4, Phase-4, defensive-upload, H3, worst-tick) → **package 6** (`plans/2026-07-03-sound-closeout-sweep.md`)
> After packages 5+6 execute, this file's sound sections should contain ONLY closed/annotated
> entries; anything still open then is a process bug. (The 2026-07-01 review pair remains the
> analytical record behind the packages.)
>
> **EXECUTION STATUS as of 2026-08-05 (reconciliation pass):**
> - **Package 2** (SFX Stage B/C) — **EXECUTED + merged 2026-07-07**, annotated on its own entry.
> - **CORRECTED 2026-08-10:** packages **1 (2026-08-09), 3 and 4 (both 2026-08-10)** have
>   all EXECUTED and merged. Only **5 and 6** remain of the banked set. The package-4
>   paragraph below is historical — every item it lists as open has shipped. Note also
>   that packages 5+6 no longer close the sound backlog: the 2026-08-08 triage adopted
>   nine riders (R2, R3, R5-R11) and two ruled-in streams that postdate this banner and
>   have no plans. See `docs/superpowers/2026-08-10-open-work-inventory.md`.
> - **Package 4 has open work that does not need the others.** Verified against the tree:
>   **D2 is DONE** (corrected on its own line below — do not re-plan it), while **D1, D4, D5, D6,
>   D7 and E5's 7th RegDelta group are genuinely open** and are independent of packages 1/3/5/6.
>   If sound work is picked up piecemeal, that cluster is the cleanest entry point.
> - Three sound items **cannot be closed statically at all** and are listed in the
>   CANNOT-BE-SETTLED-STATICALLY section at the top of this file: the A2 two-SFX-in-one-frame
>   runtime check, the FM env attack seam by-ear pass, and the bank-latch desync hunt (plus the
>   DAC worst-tick profiling round).

### Music-expression Task 0 (Z80 code recovery) — follow-ups — 2026-06-24
Task 0 recovered Z80 code headroom (2 → ~1016 B) by **co-locating** the engine lookup tables
at the start of Moving Trucks' streamed ROM bank (window `$8000`), read with the song bank
already in the window — no swap. SFX is covered (its blobs share MT's bank). Verified: MT
renders == pre-banking baseline. Merged on `feat/sound-task0-recovery`. Two follow-ups:
- **Bank-D (DAC) co-location hook — for the first real COPY / FM6=DAC-drum song.** COPY songs
  run with the **DAC sample bank** in the window during their frame, which lacks the tables.
  When a real drum song is authored, emit a **label-free data-only copy** of the engine tables
  at the DAC sample bank start (`main.asm`, after `dac_samples.asm`'s `align $8000`) — needs a
  small generator tweak (`gen_sound_tables.py` + `zyrinx_player.py` to emit a data-only twin,
  since the labels are defined once in MT's bank). The Phase-3 scratch COPY test songs (id 1–5)
  were dropped, so nothing needs this today. The banking model (tables at bank-start in whatever
  bank the window holds) is the general rule; this is just the COPY instance.
  *(Generator twin LANDED `874b260` (package 3, 2026-08-10) — `gen_sound_tables.py::
  emit_emp_z80_data_only()`, byte-equality tested (`TestEmpDataOnlyTwin`); written against the
  CURRENT build-consumed `emit_emp_z80()` emitter, activation path re-anchored to seam-2/embed
  mechanics (the `main.asm` phase-include named above is deleted — see the twin's docstring +
  the DAC spec's authoring runbook step 6). ROM activation still rides the first COPY song.)*
- ~~**Dead 68k table copies.**~~ **✅ DONE — deleted by `a3f2332`** (2026-07-01, "chore: tier-2
  mess cleanup — orphans deleted, references protected, handoff neutralized). Verified 2026-08-05:
  `data/sound/fm_patches.asm` and `data/sound/sound_tables.asm` are gone from
  `games/sonic4/data/sound/`, and **`FmPatchTable` has zero hits tree-wide**. (Original text:
  with the scratch COPY songs gone, `data/sound/fm_patches.asm`
  (`FmPatchTable`) and `data/sound/sound_tables.asm` (the 68k duplicate of the Z80 tables) are
  now **wholly unreferenced** (the runtime uses the Z80 copies). Candidate for removal — left in
  this pass to keep Task 0 scoped to recovery.) **See also the "Dead-but-drift-guarded 68k ROM
  table/patch copies (Plan 1C)" entry further down — same two files, also closed by this commit.**

> **Driver note:** the engine ships a **from-scratch custom Z80-autonomous sound driver**
> (2026-06-16 master sound spec), NOT an imported Flamedriver. Plans **1A** (foundations),
> **1B** (DMA-survival DAC), **1C** (FM+PSG sequencer), **1D** (Moving Trucks FM infra), and
> **Phase 3a** (FM depth — per-frame modulation engine + native Moving Trucks port) are SHIPPED
> (merged to master `c89bea3`, 2026-06-19). The remaining Phase 2 / 3b / 4 / 5 / 6 backlog
> (N-channel DAC mixer, FM extras, adaptive FM6, section-aware banking/fades + SFX, MegaDAW export)
> is tracked at the bottom of this section. References to "Flamedriver upload" below are historical.

### SFX Fidelity Stage B/C (deferred from Stage A, 2026-07-03)
> **EXECUTED 2026-07-07** (`feat/sfx-fidelity-stage-bc`, plan `plans/2026-07-03-sfx-fidelity-stage-bc.md`).
> Shipped + oracle-verified: `sfh_gain` fold (FM TL + PSG atten), per-SFX `sfh_duck` (deepest-active
> wins; global `SFX_DUCK_THRESHOLD`/`SFX_DUCK_DEPTH` retired), non-latching priority (bit 7), authored
> instance caps (oldest-slot kill), continuous-SFX class (tri-state `sx_extend`). `SfxChannel` 64→68.
> Two plan defects fixed in review: (1) `sx_gain` moved off +58 (aliases `sc_detune`, read on SFX ix);
> (2) **bit-7 non-latching flag collided with the 8-bit priority scale → `SFXPRI_*` rescaled to 7-bit
> ($10/$20/$30/$40/$60), bit 7 reserved as the flag, build-fatal + pytest guard added.** Oracle proof:
> spindash stores `sx_priority=$40` (was $00); 4-FM-SFX contention steals lowest (roll $30), death $60
> + spindash $40 survive; cap=1; no duck at defaults. Blobs no longer byte-identical to Stage A (byte[0]
> priority intentionally rescaled; ordering/behavior preserved). **STILL DEFERRED:** H3 (music-relative
> level) + full rendered S3K A/B (below, by-ear-gated); cap>1 on multi-channel SFX (generation tag);
> jingle cross-rule → package 1 (introduces the jingle class); by-ear taste values (gain/duck all 0).

**Surfaced during:** the SFX fidelity phase (spec `2026-07-02-sfx-fidelity-and-mixing-design.md`,
plan `2026-07-03-sfx-fidelity-stage-a.md`, branch `feat/sfx-fidelity`). Stage A SHIPPED: PSG +24
octave fixup removed (jump/skid S3K-exact), retrigger replace-in-place cap 1 (rev escalation kept),
PSG sweep floor clamp, TL-clamp audit + bake test, `SfxHeader` 8 bytes with inert Stage-B fields,
and THREE field-found fixes from the user's by-ear pass (all live-debugged in oracle):
1. **Stopped-sequencer drone** — `Sfx_Restore` gates on `SND_SEQ_ACTIVE` (an SFX ending over
   stopped music re-keyed the dead song's stale-KEYED note into an unkillable tone).
2. **S3K modSet load-point semantics** — S3K's `cfModulation` only retargets the data pointer;
   params load at the next ATTACKED note (`zPrepareModulation` early-outs on no-attack) and
   speed/steps reload THROUGH the pointer. So roll's fade RISES to the end and spindash's holds
   the sweep-top. Our engine's base-pitch snap in `Seq_Op_ModSet` (built on the wrong immediate-
   cancel reading) is DELETED; the transcoder's `_apply_s3k_modset_load_points` pass drops/freezes
   unloaded modSets. Registered-verified: roll sweeps to `$6D9` (S3K-computed exact) through the
   fade; spindash holds `$4F4` after the climb.
3. **SFX-ring byte-cursor-as-word-index** — `Sound_PlaySFX`/`Sound_DrainSfxRing` loaded ring
   cursors with `move.b` but indexed `(a0,dN.w)`; a dirty caller upper byte (spindash release
   leaves `$09xx` in d1) sent the ring write up to `$FF00` bytes astray — the dash SFX vanished
   AND a stray byte hit unrelated RAM. Fixed with `moveq #0` sanitization. A repo-wide audit of
   the same pattern (70+ `(aN,dM.w)` sites) ran 2026-07-03 — see the audit report for verdicts.
The retrigger POLICY DECISION from the 2026-07-01 review findings is CLOSED (replace-in-place, cap 1).
The A2 runtime-verification item (below) is effectively DISCHARGED by fix 3's live debugging —
the ring delivers correctly once the index bug is fixed; jump+ring same-frame pairing was
exercised throughout the phase's captures.

- **Stage B — per-SFX mixing surface (engine wiring for the reserved header fields):**
  `sfh_gain` (authored master attenuation, FM carrier-TL 0.75 dB steps / PSG atten 2 dB steps,
  applied at init), `sfh_duck` (per-SFX duck depth replacing global `SFX_DUCK_DEPTH`; 0 for
  bread-and-butter SFX, deep only for death/ring-loss class), `sfh_cap` (authored instance caps),
  non-latching priority via bit 7 of `sfh_priority` (S2's trick — plays but never raises the floor).
  Spec §5 has the full design. **Roll taste**: S3K's roll is authentically a ~2.2 kHz C#7 with a
  1.4 s authored fade (`smpsFMAlterVol` ×42, register-verified at parity) — if it reads as "too
  high/long" by ear, tame it via `sfh_gain`/the FM taste knob as a DELIBERATE divergence, not a fix.
- **Instance discriminator for cap > 1 on multi-channel SFX** (quality-review note, Task 2): the
  per-slot id table alone can't tell which slots form the OLDEST instance of a multi-channel SFX
  (Dash = FM5+PSG3). cap=1 and cap-N-single-channel work as-is; cap>1 multi-channel needs a
  generation tag or per-instance grouping.
- **Stage C — continuous-SFX class** (S3K extend semantics; header flag `SHF_CONTINUOUS` + engine
  re-ping/loop-counter). None of the current 9 SFX need it; ~30 S3K sounds (wind/fans/rumbles) are
  unportable without it. Existing ARCH §6.7 entry stands.
- **H3 (music-relative SFX level) — deferred pending by-ear:** SFX play at raw authored TL
  (chip-exact). If SFX still feel hot vs music after Stage A, A/B the full music+SFX mix RMS/spectrum
  against real S3K (HCZ2 bed) and fix the MUSIC converter's volume round-trip — do NOT tune SFX.
- **Rendered S3K A/B per SFX — deferred:** Stage A verified register-exact divisors/F-nums/durations
  against skdisasm sources on the same YM core (+ the S3K-source-exact roll fade), which pins pitch
  and duration. A full vgm2wav energy/spectrum A/B vs `skdisasm/sonic3k.bin` sound-test captures
  remains available if by-ear ever disputes timbre/level.
- **Debug-harness START edge**: MCP-driven 3-frame START presses intermittently miss the
  `Ctrl_1_Press` edge (one observed miss, 2026-07-03) — benign for gameplay, noise for scripted
  emulator tests; suspect press/frame alignment in the harness, not the engine.

### Sound Engine Deep Audit (2026-06-21) — Full Bug Backlog + Best-in-Class Roadmap
**Surfaced during:** a 73-agent adversarially-verified correctness audit + a fact-checked frontier
gap analysis (Zyrinx, XGM/XGM2, Echo, MDSDRV, GEMS, Flamedriver, demoscene/MegaPCM). Branch
`feat/sound-phase5a-sfx`. Memory: [[project_sound_audit_2026_06_21]], [[project_sfx_pitch_open]].
**Verdict:** structurally sound — **0 crashes, 0 register/bus-corruption, 0 IRQ bugs**. 40 confirmed
issues, clustered in SFX + DAC + the build pipeline. We are already best-in-class on DMA-survival
DAC cadence, the SFX steal/priority/ducking engine, and the static key-on FM-expression layer.
**Status of Item 1 (IN PROGRESS, branch off this one):** bug B1 (transcoder operator swap) + bug
A1 (SFX steal silence-gap). Everything else below is the durable backlog so nothing is lost.

#### A. Bugs reachable in normal gameplay (fix soon)
- **A1 — SFX steal silences the music voice it stole** (`engine/sound_sfx.asm` ~447/895/920/947).
  Steal's key-off clears `SCF_KEYED` on the music channel; `Sfx_Restore` tests that *same* now-cleared
  bit to decide whether to re-key the held note, so it never re-keys → music voice dropout on every
  steal of a sounding FM/PSG note. **Fix:** stash the music channel's KEYED state at steal, branch
  Restore on the saved bit. (Violates the spec's "no silence gap" criterion.) **→ Item 1.**
- **A2 — two SFX in one 68k frame → only the last survives** (`engine/sound_api.asm` 130; single-byte
  `SND_REQ_SFX`, latest-wins; consumed once/VBlank at `z80_sound_driver.asm` 522). Jump+ring, skid+ring,
  death+ring-loss all drop one SFX, *priority-blind*. The Z80 3-deep queue sits downstream and can't help.
  **Fix:** Flamedriver two-slot post (`zSFXNumber0/1`) or a small 68k-side pending ring. Audio-only (high/med).
  **IMPLEMENTED (af09e83, 8-deep 68k-side ring):** `Sound_PlaySFX` enqueues; `Sound_DrainSfxRing`
  (GameLoop, post-VSync) posts ONE id/frame into the mailbox once the Z80 has cleared it. Lint clean,
  full ROM assembles. The code has long since shipped to master (the OJZ tile-budget build blocker that
  gated boot testing was resolved 2026-06-22). **The dedicated runtime verification item still stands
  (2026-07-01):** exercise jump+ring / skid+ring / death+ring-loss in one frame and confirm both SFX
  reach the chip. Logic hand-traced (enqueue/drain/dedup edge cases) in the interim.

#### B. Build-pipeline / fidelity bugs (the "SFX sounds wrong" root cause)
- **B1 — transcoder swaps physical operators S2↔S3** (`tools/sfx_transcode.py` ~388). Emits S3K op
  order straight through, but our engine maps byte-index k→reg base+k*4 = physical `[S1,S3,S2,S4]`;
  S3K uploads `[S1,S2,S3,S4]`. Every transcoded FM SFX plays with OP2/OP3 transposed → wrong timbre
  (spindash alg-4 swaps the *modulators* = large). **Likely root of [[project_sfx_pitch_open]].**
  **Fix:** emit `[src[3],src[1],src[2],src[0]]` (OP_REORDER=[0,2,1,3]) for the S3K-SFX path only. **→ Item 1.**
- **B2 — by-ear FM octave / spindash-sweep "taste knobs" baked into committed SFX data** (`sfx_transcode.py`
  151-176; `_FM_SFX_OCTAVE`, `_SPINDASH_MOD_SCALE`). Unconverged WIP; likely *compensating* for B1.
  **After B1 lands + regen, re-evaluate — they may collapse toward 0/S3K-faithful.** (Paused 2026-06-21.)
- ~~**B3 — AM-enable bit dropped vs S3K byte** (`sfx_transcode.py` 330-336/390; `_am<<5 & 0x80` always 0).
  Harmless on YM2612 (bit 5 of $60 is a don't-care) but a byte-fidelity divergence + a trap if a real
  AM voice is ever transcoded. Doc or preserve the junk bits.~~
  **DONE 2026-08-10 (package 4, `sound-pkg4`) — but NOT as "preserve the junk bits".** The entry's own
  observation is the reason: bits 6-5 of `$60` are DON'T-CARES, so reproducing the `SourceSMPS2ASM==0` byte
  buys nothing while losing the flag the voice author meant. `smpsVcAmpMod`'s operand is now treated as a
  per-operator AM-ENABLE FLAG and lands on YM2612 **bit 7** — the placement `_smps2asm_inc.asm`'s own comment
  records as correct ("According to several docs, however, it's actually the high bit"). Implemented as a
  NONZERO TEST rather than a shift, so it is right under either SMPS2ASM encoding and under the 2-bit values
  the erroneous assumption could produce. **Zero shipped-content movement:** all nine core SFX `.bin` payloads
  regenerate byte-identical (of all S3K SFX only `9B - Thump Boss` authors AM, and it is not in
  `_CORE_SFX_IDS`), and all four ROM CRCs were unchanged across the commit.
- **B4 — looped-SFX fade tail (`smpsFMAlterVol`) + bare-duration replay — FIXED 2026-06-21** (see
  `docs/BUGS.md` BUG-002 items 1 & 3). The transcoder collapsed S&K's per-pass `smpsFMAlterVol` fade to one
  constant `MEV_VOL` (roll tail held flat then hard-cut) and dropped the SMPS bare-duration "replay previous
  note" idiom (spindash rev-tail collapsed to zero ticks). Fixed transcoder-side (no Z80 growth — driver has
  4 bytes free): AlterVol-bearing `smpsLoop`s are now UNROLLED with a dB-faithful per-pass fade (invert
  `LogVolumeLutZ`), and a standalone duration byte re-articulates the previous note. Packer backstop added.
  **`smpsNoAttack` (the per-pass FM re-key) — DONE 2026-06-21** (was the deferred half). VGM capture proved
  the unrolled tails re-keyed the FM envelope 43×(roll)/26×(spindash) at 30 Hz — the "jingle/higher-pitch"
  the user heard. Fixed in EXACTLY the 4 free Z80 bytes: bit 7 of a NoteDur's pitch operand is a no-attack
  flag; `Seq_Op_NoteDur` does `ld d,a / bit 7,d / ret nz` to skip the note-on hook (no `$28` re-attack AND no
  freq re-write) for a held continuation. The transcoder sets bit 7 on tail passes via `mod_dirty`: the FIRST
  note after a modSet still re-keys (resets the swept pitch to base), the rest hold. Verified on hardware:
  KEY-ON 43→2 / 26→2, tail holds at base fnum, TL fade intact. **Transition re-key (the last residual) —
  FIXED 2026-06-22** (see `docs/BUGS.md` Items 1+3 follow-up #3): `Seq_Op_ModSet` now re-writes `sc_base_freq`
  via `Fm_WriteFreq` (held-note pitch change, no `$28`) for SFX FM channels, so the modSet-off snaps the tail
  to base with no re-key; the transcoder holds ALL tail passes. +18 Z80 bytes reclaimed by folding 6 more
  channel-class tests into `Snd_ChanClass` (`Z80_SOUND_SIZE` `$16EE`, 2 free). Verified: roll/spindash
  KEY-ON 2→1, fades intact, skid/ring/jump/dash no regression. The looped FM SFX tails are now S&K-faithful
  (one key-on, smooth fade to silence). `Snd_ChanClass` has converted 11 of 12 inline channel-class sites;
  the 1 remaining + future reclaim is there if needed. (Historical: that fix left $16EE / 2 free; Task 0
  banking then recovered to $1618 / 216 free, and later phases spent it back to 10 free (2026-07-01);
  the 2026-07-02 budget phase recovered ~790 B and ended at **$175A / $18F0 → $196 (406) free,
  DEBUG=1** after spending on fidelity + portamento — see F1/F5.)
- **B5 — `smpsPSGform $E7` tone-FREQUENCY-TRACKED noise sweep** (refinement; the fixed-rate fix is done — see
  `docs/BUGS.md` BUG-003). The dash `$B6` (and any `smpsPSGform $E7` SFX) is now correctly rerouted to the
  NOISE channel, but plays a FIXED white-noise rate (`$E6`, clk/2048). S&K's `$E7` is white noise whose shift
  rate TRACKS PSG3's tone frequency — so as the channel's tone sweeps (its `smpsModSet`), the noise pitch
  descends (a "pshhew"). Reproducing it needs the engine to drive PSG3's frequency register as the noise clock
  + apply the modulation to it, with the audio on the noise channel — either (a) a `Psg_Noise` `$E7` path that
  writes PSG3's freq from the note+mod, or (b) the transcoder splitting the source channel into a silenced
  tone-clock (PSG3) + a noise channel (the engine + hardware then sync via the `$E7` track bit). Option (b) is
  engine-change-free but adds a 3rd SFX channel + needs the clock pinned to PSG3 (no voice substitution). The
  fixed-rate noise is the right character; the descending sweep is the nuance. Re-evaluate by ear.
  *(Status check 2026-07-01: STILL OPEN for SFX — `tools/sfx_transcode.py` still emits the fixed `$E6`
  approximation. Note the MUSIC path has since shipped tone-tracked noise — `MEV_PSGNOISE` clocks rate-3
  noise from tone-2, S3K-faithful, HCZ2 hi-hats — so the engine mechanism for option (a) now part-exists.)*

  > **STILL OPEN after package 4 (2026-08-10) — the plan's own Step-2B fallback was taken, deliberately.**
  > Package 4's Task 6 required answering, first, whether the shipped music mechanism REACHES SFX. It does
  > not: `Psg_Noise` branches on `Snd_ChanClass` and the rate-3 tone-2 clock (`Psg_EmitNoiseClock`) lives
  > ONLY on the MUSIC arm; the SFX arm is the legacy `$E0 | (note & 7)` path with no `$C0` write. The plan
  > sanctioned the fallback if un-gating cost more than ~12 B. Costed, it is far more than that — THREE
  > coupled changes, not one:
  >
  > 1. **The SFX channel cannot carry a noise-mode byte.** S3K's `$E7` semantics need the note to be a
  >    PITCH plus a cached mode/rate, but `sc_noise_mode` (+57) ALIASES `SfxChannel.sx_priority`, and
  >    `_validate_no_aliasing_ops` rejects `MEV_PSGNOISE` on SFX for exactly that reason. The shared prefix
  >    may not grow (standing sound-banking invariant), so the carrier would have to be a new `sx_kind`
  >    value (+63, SFX-private) plus a tone-clock branch in `Psg_Noise`'s SFX arm — ~18 B before sharing,
  >    ~11 B net if the `SCF_KEYED`/`Psg_EnvCursorReset` prologue is hoisted out of both arms first.
  > 2. **The sweep itself is broken on the noise route.** The dash's descent is a `smpsModSet`, and
  >    `Psg_ApplyMod` re-latches through `Psg_EmitDivisor` -> `Psg_ChBase`, which for `CHROUTE_PSGN`
  >    computes latch `$80|$60` = `$E0` — the NOISE CONTROL register. That is precisely the **D1**
  >    corruption this same package just closed producer-side. A tone-clocked noise SFX therefore ALSO
  >    needs a noise-route special case in `Psg_ApplyMod` that writes tone-3's frequency latch (`$C0`),
  >    plus a carve-out in the brand-new D1 rule so the sweep is legal on exactly that channel shape.
  > 3. Only then does the transcoder change (drop the `$E6` approximation, emit pitch notes + the `$E7`
  >    kind) become meaningful.
  >
  > Estimated ≳ 40 B resident plus a re-plumb of the D1 rule — well past the ceiling, and it re-opens a
  > corruption path the same session closed. **Recommendation: give B5 its own scoped parcel** (it is a
  > `Psg_Noise` + `Psg_ApplyMod` route-shape change, not a transcoder tweak), and sequence it AFTER any
  > log-domain pitch work (triage R3), which changes how modulation reaches the divisor anyway. The
  > fixed-rate `$E6` character remains correct; only the descending nuance is missing.

#### C. DAC sample path — ✅ largely RESOLVED by the DAC-format revision (2026-06-25)
*(The "ONE format revision" this block asked for SHIPPED as the DAC drum phase — see
`docs/superpowers/specs/2026-06-24-dac-drum-format-revision-design.md` + its raw-8-bit amendment.
The multi-sample descriptor table, per-sample banking, and the one-shot state machine replaced the
1C blip path wholesale.)*
- ~~**C1 — one-shot samples never stop**~~ **RESOLVED (DAC drum phase, 2026-06-25):** the shipped
  one-shot state machine (IDLE → PLAYING → DRAINING_TAIL → STOPPING) plays a sample once and cleanly
  stops to DC center — nothing re-loops. (Historical text: `DAC_ACTIVE` only ever set, never cleared
  on exhaustion; FILL-exhaust unconditionally re-looped the blip.)
- ~~**C2 — `Snd_StartSample` ignores `ds_loop_ofs` + `ds_rate`**~~ **SUPERSEDED (DAC drum phase):** in the
  shipped 9-byte descriptor both fields are *deliberately* RESERVED forward-compat (`sound_constants.asm`,
  `DacSample`) — one-shots don't loop and v1 has one rate; multi-sample DAC is live via the descriptor table.
- ~~**C3 — odd `ds_length` runs away ~64KB**~~ **RESOLVED by construction:** the shipped register-resident
  1:1 loop consumes ONE byte per pass (no `-=2` FILL), so odd lengths terminate exactly
  (`tools/dac_encode.py` header notes there is no even-length requirement).
- **C4 — no consumer underrun guard** (old lines 353-363) — **mostly superseded:** the shipped
  DRAINING_TAIL path stops exactly at `lead==0` and DC-centers (no stale-ring replay at exhaust). The
  residual corner is a 68k DMA outlasting the ~200-sample ring lead mid-sample — re-evaluate against the
  shipped loop if a marathon DMA burst is ever added.

#### D. Latent correctness (trust-the-packer / new-content surfaces)
- ~~**D1** PSG pitch-mod has no noise-route gate (`sound_sequencer.asm` 162; `sound_psg.asm` 239) — a noise
  channel carrying `sc_mod_ctrl!=0` corrupts the noise control register. Gate on tone route + reject in transcoder.~~
  **DONE 2026-08-10 (package 4, `sound-pkg4`) — PRODUCER-SIDE, zero Z80 bytes.** The runtime gate stays
  reverted (the note at the `Psg_ApplyMod` call site in `sound_sequencer.emp` now points here instead of
  claiming a convention). Both producers enforce it: `song_packer.py` `ModSet.validate` refuses
  `CHROUTE_PSGN` outright, and `sfx_transcode.py` `_validate_no_modset_on_noise` backstops every SFX
  channel from `pack_sfx`. Rule is absolute, including the all-zero `smpsModSet 0,0,0,0` "mod off" idiom.
  Spec: music-expr format-validity §(d)4. **Deliberately a BACKSTOP, not a re-shape, on the SFX side:** the
  parser already DROPS `smpsModSet` when it reroutes a channel to noise and a shipped test pins that drop, so
  erroring at the emission point would reject real S3K sources we do not control.
- ~~**D2** note before any set-duration reloads from a zeroed `sc_dur_default` → 255-tick stuck note
  (`sound_sequencer.asm` 536; init `sc_dur_default` to 1).~~ **✅ DONE — verified 2026-08-05.**
  The seed-to-1 the entry prescribes is in place at **both** init sites:
  `engine/sound/z80_sound_driver.emp:1276` (`ld (ix+sc_dur_default), 1`, with the rationale
  spelled out in the comment at `:1273` — "seeds to 1 (not 0): a channel that issues a note BEFORE
  any set-duration…") and `engine/sound/sound_sfx.emp:1034`. **Package 4 must not re-plan this
  item;** D1/D4/D5/D6/D7 in the same block are still open.
- ~~**D3** `sc_mod_wait` never restored on note re-arm — 2nd+ modulated note gets zero delay vs S3K
  `zPrepareModulation` (`sound_sequencer.asm` 381; add `sc_mod_wait_raw`).~~ **DONE 2026-07-02
  (budget phase T6):** `sc_mod_wait_raw` + `sc_mod_delta_raw` latched at MODSET, reloaded every
  note-on — capture-verified at ref parity (`docs/research/phase_harness/t6_verification.md`).
- ~~**D4** `Psg_NoteOn` ignores `sc_transpose` (S3K applies it to PSG too) (`sound_psg.asm` 154).~~
  **DONE 2026-08-10 (package 4, `sound-pkg4`, commit `27b3b6a8`) — BYTE-NEUTRAL.** `Psg_NoteOn` now calls
  the new `Fm_TransposeClampChrom` (seeds `FMPITCH_MAX_IDX`, falls into `Fm_TransposeClamp`), which also
  replaced `Fm_NoteOn`'s own 2 B seed — so the 3 B `call` exactly funds itself against the `ld l,a / ld h,0`
  widen it replaces. `FMPITCH_MAX_IDX` legitimately bounds BOTH tables: `FmPitchTableZ` and
  `PsgDivisorTableZ` are one 95-entry note list and `sound_tables_z80.emp` already asserts both emitted
  extents at 190 B. **The bound had to live on the FM side**: seam-1 resolves each resident module's
  constants from a per-module name list baked into the sigil harness (`seam1.rs` `psg_const_names`), and no
  pitch-domain constant is on `sound_psg.emp`'s list. The SFX PSG-tone RESTORE path now folds the MUSIC
  channel's transpose on re-key, matching what the FM restore already did. **Oracle gate owed** (controller):
  spindash-rev PSG pitch-tracking.
- ~~**D5** PSG envelope attack uses a stale `sc_psgenv_out` / lands one frame late vs S3K (`sound_psg.asm`
  106/184; zero `sc_psgenv_out` at cursor-reset).~~ **✅ ALREADY DONE — re-verified 2026-08-10 (package 4).**
  `Psg_EnvCursorReset` (`engine/sound/sound_psg.emp`) zeroes BOTH `sc_psgenv_cur` and `sc_psgenv_out`, with
  the rationale in the comment ("drop the previous note's env tail so the attack's volume emit … starts
  clean, not one frame of the old note's stale attenuation delta"). **Package 4 planned no work here.**
- ~~**D6 (uncertain)** single-level repeat state may carry a stale `sc_repeat_count` across a song loop /
  mid-flight jump (`sound_sequencer.asm` 1042). Watch; add a packer guard if it bites.~~
  **DONE 2026-08-10 (package 4, `sound-pkg4`) — CONFIRMED REAL, then closed from both ends.** The mechanism:
  the song-loop `Jump` target IS the `LoopPoint`, so a `LoopPoint` inside a `RepeatStart..RepeatEnd` span makes
  the loop re-enter the body mid-span; `Seq_Op_RepeatStart` never runs again, and `Seq_Op_RepeatEnd` seeds from
  the operand ONLY when it reads 0, so a stale nonzero count is CONSUMED. Packer: a `LoopPoint` while a span is
  open is a `PackError` (the COMPLETE rule — the `Jump` can target nothing else). Engine: `Seq_Op_RepeatStart`
  re-seeds `sc_repeat_count` to 0 (**4 B**, not the plan's 2 — `ld (ix+d),n` is 4 B on Z80), byte-inert on
  valid content. Spec: music-expr §(c)4.
- ~~**D7** `MEV_REPEAT_END` operand 0 → 255-pass repeat, no runtime clamp (`sound_sequencer.asm` 1022; trust-packer).~~
  **DONE 2026-08-10 (package 4, `sound-pkg4`) — 0 RELEASE BYTES (plain blob + plain ROM CRC unchanged across
  the commit).** `Seq_Op_RepeatEnd` tests `a` at `.have_count` — where it is either an in-progress count
  (nonzero by the preceding test) or the FRESH operand — so `a == 0` there is exactly "the stream authored 0",
  trapped to `Seq_BadOpcode` under `DEBUG == 1` before the wrapping `dec`. **Found while pinning the producer
  side: the rule did not cover SFX at all.** `pack_sfx` encodes events directly and never calls
  `Event.validate`, so `song_packer`'s 1..255 range never reached an SFX stream; the count check now lives in
  `_validate_sfx_repeat`, which `pack_sfx` does call. Spec: music-expr §(c)5.
- ~~**D8** `song_packer.py` accepts expression opcodes the engine silently DROPS on a music route — add a build-time music-legal opcode gate~~ **DONE 2026-06-27 (music-expr merge)** — the packer now enforces a music-legal opcode gate (commits `60524f9` + `da9bb93`, "D8 review"): it errors at build time on any opcode the music route would silently drop, relaxed per-opcode as each un-gates. `MEV_MODSET` vibrato is now music-legal (Phase-1 un-gate); `MEV_PSGENV` since feat/hcz2-import. **STILL OPEN (separate, not the gate):** route PSG note-on through the multipoint `sc_points` arp path (today under `.is_fm` only) for single-channel PSG chords — pairs with D4 (PSG `sc_transpose`).

#### E. Best-in-class — the honest gaps (cross-driver consensus)
**DO NOW (high payoff, seam already exists, ~no pigeonhole):**
- **E-now-1 — continuous/fine pitch + portamento ON MUSIC channels.** Every frontier driver converged
  on this (Zyrinx fine ladder + restoring-division glide `batman_driver_analysis.md`:186-219; MDSDRV 256
  steps/semitone; XGM2 freq-delta; Flamedriver pitch-slide w/ octave-rollover). Our `FmPitchTableZ` is
  strictly chromatic and our continuous-vibrato core (`Mod_Advance`/`sc_base_freq`/`sc_porta_*`) renders
  **SFX channels only** — music gets none. Promote that machinery into the music `SeqChannel` path + add a
  fine-pitch representation. Fields `sc_porta_accum/incr` reserved (`sound_constants.asm` 793). *(This is
  the same as the long-deferred Phase 3a Task 7 portamento + Zyrinx "take-next".)* *(**2026-07-01:** the
  fine-pitch half SHIPPED — `MEV_DETUNE` + music vibrato/`MEV_MODSET` are live on music channels.)*
  *(**DONE 2026-07-02 (budget phase T10):** the PORTAMENTO half SHIPPED — `MEV_PORTA` ($F5) +
  `Porta_Apply` fully RESIDENT, packer event + tests, soak/glide capture-verified
  (`docs/research/phase_harness/t10_verification.md`). This entry is closed.)*
- ~~**E-now-2 — per-frame FM TL volume envelope on music channels**~~ **DONE 2026-06-27 (music-expr merge)** —
  shipped as `MEV_FMENV` ($F7) + `FmEnvUpdate` (per-frame FM-TL carrier volume envelope), reusing the existing
  `Fm_PatchTlGroup` TL-write plumbing; no format change. Supersedes the static `OPBIAS`-only state. (Flamedriver `zDoFMVolEnv`.)
- ~~**E-now-3 — master fade-in/out + global tempo-speedup.**~~ **DONE (music-expr Phase 2):** shipped as
  `Sound_FadeOut`/`Sound_FadeIn` (`SND_REQ_FADE` master TL ramp) + the `MEV_TEMPO` ($F3) global tempo
  scalar with a per-channel accumulator (the 2026-07-01 fix pass repaired the speed-up borrow math).
  `zFadeToPrev`-style fade-to-previous/saved-song-state remains unspec'd — part of the game-feel gap
  (see the 2026-07-01 spec review §3).
- ~~**E-now-4 — sequencer-driven hardware LFO ($22 rate opcode).**~~ **DONE (music-expr Phase 2):**
  shipped as `MEV_LFO` ($F4). ~~**Also fix latent doc
  bug:** comment at `z80_sound_driver.asm` says 3.98 Hz but `$08` = 3.82 Hz.~~ **Doc bug FIXED 2026-06-27**
  (comments at lines 158 & 167 now read 3.82 Hz).

**DESIGN-FOR-IT-NOW, build later (the ONE true pigeonhole + its companions):**
- **E2 — multi-voice PCM mixing on FM6 DAC** — the single architectural decision that forecloses the
  frontier. XGM(4ch)/XGM2(3ch)/MDSDRV(2-3ch)/DualPCM(2ch) sum samples in Z80 RAM; our consumer copies one
  byte, no summing stage, no per-voice volume field (`z80_sound_driver.asm` 353-363; `sound_constants.asm`
  228-234). **Don't build the mixer now — shape the ring consumer + `DacSample` descriptor for N voices now**
  (per-voice volume byte + 16.16 mix cursor so per-sample pitch is free later), ship 1 voice, keep the
  RAM-only equal-cost invariant. This is the "[[feedback_best_of_class_north_star]] design-for-C, build-for-A"
  call — do it **before authoring real DAC content.**
  *(**2026-07-01 update:** the DAC format revision decided AGAINST this — the approved spec
  (`2026-06-24-dac-drum-format-revision-design.md` §2.2) rejects runtime mixing in favor of a single voice
  + pre-mixed composites, and the shipped descriptor has NO per-voice volume/mix-cursor fields. That
  rejection is the one irreversible format bet and was **RATIFIED by the user 2026-07-03** (sound
  design-banking session). The ratification-time ask — the cheap insurance this entry wanted (add
  `ds_vol` + reserved mix-cursor bytes, ~3 B/descriptor, zero code) — is a build item in the banked
  DAC drum-library-readiness package. See the 2026-07-01 spec review §4.)*
  *(Descriptor insurance LANDED `a34c0e1` (package 3, 2026-08-10) — `ds_vol` + `ds_mix_rsvd`
  shipped, 12-byte descriptor, appended so no existing offset moves; v1 engine reads none of the
  new bytes and the resident Z80 blob is byte-count identical (the ×12 stride kept the 8-bit
  Snd_DacLookup form's exact instruction count/length).)*
- **E3 — round out the DAC format in that SAME revision:** loop point (= C2), priority, pan (via $B6),
  auto-bankswitch, `ds_rate` pitch, **+ 4-bit DPCM** (re-adopt our own S3K JMan2050 DPCM, `Flamedriver.asm`
  4321-4442 — halves ROM, producer-side so the 8948 Hz cadence is untouched), and route **sampled SFX** as
  mixer-voice-2 with ducking. (Skip PCM-on-PSG.) Fold the C1-C4 bug fixes in here.
  *(**2026-07-01 update:** the shipped revision landed the C-block fixes, per-sample banking (`ds_bank`),
  and the `$B6` pan door, and RESERVED `ds_codec`/`ds_rate` at zero cost — but chose raw 8-bit over DPCM
  (compression bought ~nothing for once-stored drums and the decode capped the rate; see the spec's
  2026-06-25 amendment) and forecloses sampled-SFX-over-drums with the single-voice bet above.)*
- ~~**E4 — independent per-channel modulation/control stream (dual-stream channels)**~~ **DONE 2026-06-27 (music-expr merge)** —
  the committed seam (`sc_mod_ptr` slot[1], stream-agnostic `ModUpdate`) is now LIVE: slot[1] drives a `MacroTick`
  register-automation stream via `MEV_MACRO` ($F9) — tag grammar `TAG_MAC_*` ($E0–$E3), 2-byte BE loop, `Snd_SongBase`
  rebase. Zyrinx's "feels alive" secret + MDSDRV macro-tracks. *(was Phase 3b "dual per-channel data streams".)*
- **E5 — SSG-EG per-operator looping ($90-$9E)** — cheap buzzy/metallic/AY timbre family. **Load-time half
  DONE 2026-06-27 (music-expr merge):** SSG-EG is now a real per-op patch field — `FmPatch` grew 26→32 bytes
  (`fp_ssg_eg ds.b 4`), loaded at note-on via `SND_REG_OP_SSG_EG` ($90) in `Fm_PatchLoad`; `$00` default = off, so
  existing patches are byte-identical. ~~**STILL OPEN — the runtime 7th-RegDelta-group half:** `MEV_REGDELTA` does
  **not** reach $90 (`RegDeltaGroupBase` is groups 0..5 = $30-$80, `REGDELTA_GROUP_COUNT` = 6, `sound_fm.asm`). Add a
  7th group to sweep SSG-EG per-frame (one reg write/op).~~ **DONE 2026-08-10 (package 4, `sound-pkg4`) —
  E5 FULLY CLOSED, +1 B.** `RegDeltaGroupBase` gained `SND_REG_OP_SSG_EG` as group 6 and
  `REGDELTA_GROUP_COUNT` went to 7; `Fm_RegDelta`'s range check and the RHS-only length ensure both read the
  constant, so no handler changed. Producer: `song_packer`'s mirror -> 7 (build-checked by the existing
  constant-parity test) + `RD_GROUP_SSG_EG = 6`; group 7 still rejected. Spec: music-expr §(d)1.
  **Oracle showcase owed** (controller, optional): a scratch song sweeping group 6 — confirm the
  `$90+op*4+ch` writes land and the timbre audibly buzzes in a rendered capture.

**SKIP / DEFER (and why):**
- **68k-resident sequencer (MDSDRV model)** — explicitly **skip**; our full-Z80 autonomy is the right call
  for a 60fps section-streaming platformer with a busy 68k. Borrow MDSDRV's *techniques* onto the Z80, not
  its CPU placement.
- **CSM mode** — skip; contends with Timer-A (our ~59 Hz sequencer clock).
- **CH3 special mode** (someday; niche, complicates FM3 SFX voice arbitration in `sound_sfx.asm`) and
  **Echo-style adaptive live-inject** (someday; mailbox could grow a direct-event slot — protocol is already
  reentrant/extensible). Build only when a concrete song/boss needs them.

#### F. Hygiene — doc drift, dead code, RAM budget (recovers ~750 B ROM)
- ~~**F1** Z80 RAM-map spec (`docs/superpowers/specs/2026-06-16-sound-z80-ram-map.md`) is STALE~~
  **DONE (budget A.3 repack, 2026-07-02):** the spec was REWRITTEN in full as the live design record —
  new map table (state `$18F0` / ring `$1900` / seq `$1A00` / derived tail / page-aligned derived
  `SND_SFX_BASE` / frozen `$1F00+` mailbox), layout invariants (incl. the `Snd_ChanClass` page-compare
  contract), headroom history, and the complete assert inventory. `sound_constants.asm` stays the
  authoritative values; the spec documents the design + which assert guards which seam.
  ~~**Phase-final headroom (2026-07-02, end of the budget phase): `Z80_SOUND_SIZE` = $175A, ceiling
  `SND_STATE_BASE` = $18F0 → $196 (406) bytes free**~~ — DEBUG=1 figures; plain builds are 126 B
  leaner.
  > **⚠ HEADROOM FIGURE SUPERSEDED TWICE — corrected 2026-08-05.** The `$175A` / 406-free number
  > is from 2026-07-02 and was **spent back down to 86 B DEBUG** by the phases that followed, then
  > **recovered by the wave-4 Z80 reclaim (2026-08-03)** to roughly **317 B DEBUG** (plain
  > 212 B → ~443 B). Source: `docs/superpowers/plans/2026-08-03-wave4-z80-sound-reclaim.md`
  > (header + closing ledger) and this file's own "Sound — deferred follow-ups from the wave-4
  > Z80 reclaim (2026-08-03)" section near the bottom.
  > **Treat the wave-4 section as the current record, not F1/F5.** The *design* content of F1 (the
  > RAM map, layout invariants, assert inventory) is unaffected and still stands; only the
  > headroom arithmetic drifted. Item 25 in the wave-4 section notes a further −71..−94 B is
  > available in the sequencer if more is ever wanted. (A.1 song-buffer delete + A.2 table banking + A.3's +512 ceiling raise recovered ~790 B
  to a peak of 802 free; the phase then spent it on fidelity — rekey −10, mod re-arm +18, porta
  +386, tempo model −8. Full ledger: `docs/research/phase_harness/t12_matrix.md`.) The
  resident-code budget remains the binding sound constraint; data-banking remains the recovery lever
  (code may NOT be banked).
- **F2** `ENGINE_ARCHITECTURE.md §6` still lists SFX deferred + AF_SOUND a stub (update on merge to master).
- **F3** Dead ROM: `dc.l SfxTable` 540 B unused (engine uses its own Z80 `dw` window table); duplicate
  `sfx_NN_patches` banks ~208 B; ~~dead `Snd_TimerA_Program` (`z80_sound_driver.asm` 715)~~. Purge.
  > **⚠ ONE THIRD OF THIS IS WRONG — corrected 2026-08-05.** There is no dead
  > `Snd_TimerA_Program`. The only symbol of that name in the tree is
  > **`Snd_TimerA_ProgramFixed`**, and it is **LIVE — called twice**, at
  > `engine/sound/z80_sound_driver.emp:277` and `:1331` (defined `:1018`, documented `:1013`,
  > cross-referenced from `sound_fm.emp:1134` and `sound_constants.emp:151`).
  > Whatever unfixed-rate twin existed in 2026-06 is gone; **do not purge the survivor.**
  > The other two thirds (`dc.l SfxTable`, duplicate `sfx_NN_patches` banks) were not re-verified
  > in this pass — treat them as unconfirmed rather than established.
  > **2026-08-10 (package 4):** package 4's plan header listed F3 as "verified already fixed — SfxTable is
  > LIVE". That is consistent with the 2026-08-05 correction only for the `Snd_TimerA_Program` third; the
  > `dc.l SfxTable` / duplicate-patch-bank thirds remain UNCONFIRMED and package 4 did **no** work on them.
  > Do not treat F3 as closed.
- **F4** Stale/load-bearing-wrong comments: ISR "ix NOT touched" (it IS, via SfxDispatch — safe by
  construction, but the *reasoning* would license a future bug); `Sfx_Restore` "ret stub" (it's implemented);
  PSG header "never clobbers de" (it does; caller restores it); a0-clobber contracts on Sound_StopMusic/
  PlaySample/Ping/PlayRing (same class just fixed in Sound_PlaySFX — unify to all-preserve-a0).
  > **RE-VERIFIED 2026-08-10 (package 4).** The plan carried F4 as "already fixed"; that is **three
  > quarters true**, and the remaining quarter is not the bug this entry describes.
  > * ISR — **FIXED.** `SndDrv_ISR`'s header now states the opposite of the stale claim ("It does NOT save
  >   ix/iy, and PollMailbox DOES clobber them — SAFE for two reasons…") and the proc's machine-checked
  >   contract is `clobbers(ix, iy)`.
  > * `Sfx_Restore` "ret stub" — **FIXED**; the phrase no longer exists anywhere in `engine/sound/`.
  > * PSG header — **FIXED**; `sound_psg.emp`'s header now reads "They DO clobber `de`, however … the
  >   de=$4001 invariant is re-established by the Timer-A tick CALLER, NOT by PSG code preserving de."
  > * **a0 unification — NOT done, and re-classified.** `Sound_Ping` / `Sound_PlaySample` /
  >   `Sound_StopMusic` still declare `clobbers(a0)` while `Sound_PlayRing` declares `preserves(a0)`. But
  >   these are no longer COMMENTS — they are machine-checked `.emp` contracts, and each is TRUE (every one
  >   of the three does `lea <SLOT>, a0`). So there is nothing load-bearing-wrong left here: what remains is
  >   an **API-ergonomics** choice (uniform preserve-a0 costs a push/pop or a scratch register per call
  >   site), which belongs with the command-API work, not in a stale-comment sweep. **Reduce F4 to that one
  >   ergonomics item.**
- ~~**F5** Z80 blob space TIGHT: ~118 B code headroom… Plan a space recovery (bank FmPitchTableZ/LogVolumeLut/
  MovingTrucks_PitchTable into a $8000-window read)~~ **DONE (music-expr Task 0 banking, 2026-06-24):** the engine
  lookup tables were co-located at the start of Moving Trucks' streamed ROM bank (read with the song bank already
  in the `$8000` window — no swap), recovering Z80 code headroom from ~2 B → ~1016 B. The Phase 1/3
  music-expression features consumed most of that back; music-expr Phase 2 (detune/LFO/tempo/fade) and the
  2026-07-01 review fix pass took the rest. ~~**Phase-final as of 2026-07-02 (budget phase complete):
  `Z80_SOUND_SIZE` = $175A, ceiling `SND_STATE_BASE` = $18F0 → $196 (406) bytes free, DEBUG=1**~~
  **⚠ SUPERSEDED — see the correction under F1 above; the live figure is ~317 B DEBUG after the
  2026-08-03 wave-4 reclaim, having dipped to 86 B in between.**
  (build message / `s4.lst`; plain builds 126 B leaner — the A.1/A.2/A.3 recovery peaked at 802
  free, then portamento + the fidelity fixes spent it back). See F1 above (now DONE — the rewritten
  z80-ram-map spec carries the full headroom history), and the "Music-expression Task 0 (Z80 code
  recovery)" entry above.

### Per-frame pitch / volume envelopes (Phase 3a #2/#3) — DEFERRED, build-on-demand
**Surfaced during:** Moving Trucks missing-effects investigation (2026-06-19).
**Decision: do NOT build for MT; build only when a song's data actually uses them.**
**What:** A `ModUpdate` per-frame pitch-envelope processor (continuous intra-note pitch shape on
plain count==1 notes) and a per-frame volume-envelope/TL processor. A VGM census first *looked*
like MT needed these (oracle wrote freq ~16×/note, TL ~33×/note). **Re-measurement proved that was
an artifact:** the Zyrinx driver re-asserts every register every frame (60Hz full-state refresh) —
**97% of its freq writes and 99% of its TL writes are redundant re-writes of UNCHANGED values.**
Normalized to actual value *changes* per note, ours ≈ oracle (freq 0.92 vs 0.93/note; TL 0.43 vs
0.50/note). Our write-on-change engine already produces the same chip state. Building these now and
applying them to MT would ADD modulation MT doesn't have = over-modulation = WORSE. They remain
legitimate **general** capabilities (many FM tunes use real sweeps/swells) and the modulation layer
(`ModUpdate`, the design-for-C seam) is already architected to host them — so adding them later is a
clean drop-in. **When to build:** when a ported/authored song's command data actually requests
intra-note pitch/volume movement. Tool: `tools/vgm_intranote.py` (intra-note change census) +
`tools/vgm_modulation_diff.py`. LESSON: register write-COUNT is a misleading proxy; measure value
CHANGES. See memory [[project_mt_correct_source]].

### GATE articulation ($1A) — transcoder drops it (Phase 3a #4)
**Surfaced during:** same investigation. **Status:** deferred; only worth doing if percussion
phrasing audibly differs from B&R. **What:** MT uses 340 GATE commands (note-shortening, mostly
ch5/ch3/ch4 percussion). `tools/zyrinx_player.py` currently drops them (the gate-as-note-off model
b4137be/63bfd62 was REVERTED by 78fdfaf), and the engine has no sub-duration note-length field to
receive one. **When to build:** if the user reports percussion still lacks staccato/punch vs the
oracle. Needs BOTH a transcoder re-emit and an engine note-fill/gate-time field — and coordinate
with the reverted commits to avoid repeating whatever broke them.

### opbias-on-carriers fix (commit 05eca4a) — KEPT, carrier path not yet song-verified
**Status:** shipped + kept (correct latent-bug fix). `Fm_SetVolume` now writes carrier
TL = clamp(base + sc_opbias[op] + log), consistent with `Fm_PatchTlGroup`. **Caveat:** MT does not
exercise carrier opbias (FM2 carrier opbias=0), so it's verified by code audit + "doesn't break MT",
not by a song that uses it. **TODO when convenient:** add a synthetic alg5–7 test voice with a
carrier bias and capture-verify the $4x output, to bulletproof the untested path.

### ✅ RESOLVED — Multi-sample DAC loop-restart hardcodes the blip descriptor — by the DAC drum phase (2026-06-25)
**Surfaced during:** Sound 1C pre-merge audit (2026-06-17).
**Status:** **RESOLVED** — the DAC-format revision replaced the 1C looping-blip path wholesale: samples
are one-shots driven by the 9-byte `DacSample` descriptor table + the IDLE→PLAYING→DRAINING_TAIL→STOPPING
state machine; the FILL-exhaust restart branch is gone (`SND_BLIP_*` constants now only populate the
blip's own descriptor-table entry, like any other sample). Historical text below retained for lineage.
**Original status:** Benign in 1C (single DAC sample); **must fix before adding a 2nd DAC sample.**
**What:** The FILL-exhaust restart in `engine/z80_sound_driver.asm` (the rare "sample
exhausted → loop the blip" branch, ~line 399) hardcodes `SND_BLIP_PTR` / `SND_BLIP_LEN`:
```z80
        ld      hl, SND_BLIP_PTR
        ld      (SND_ROM_PTR), hl
        ld      hl, SND_BLIP_LEN
        ld      (SND_ROM_LEN), hl
```
instead of re-reading the **active `DacSample` descriptor's** loop fields (loop ptr / loop
len). In 1C there is exactly one DAC sample (the blip), so the constants and the active
sample agree and the restart is correct. The moment a second DAC sample (e.g. a real drum)
is added, an exhausted non-blip sample would incorrectly restart into the blip's bytes.
**When to fix:** when the DAC gains a 2nd sample (Phase 2 N-channel mixer, or any new drum):
have the exhaust branch reload `SND_ROM_PTR`/`SND_ROM_LEN` from the currently-playing
descriptor's loop fields (the `SND_LOOP_OFS` / per-sample loop machinery already exists in
`SND_STATE_BASE`), not from the fixed `SND_BLIP_*` constants.

### ~~Dead-but-drift-guarded 68k ROM table/patch copies (Plan 1C)~~ — **✅ DONE — resolved as option (b), `a3f2332`**
> **⚠ CLOSED — verified 2026-08-05.** The entry offered two exits: (a) adopt a banked-ROM loader
> so the 68k copies become live, or (b) decide inline-only is permanent and drop them.
> **(b) happened.** `a3f2332` (2026-07-01) deleted `data/sound/fm_patches.asm` and
> `data/sound/sound_tables.asm`; `FmPatchTable` has zero hits tree-wide and the files are absent
> from `games/sonic4/data/sound/`. The `main.asm` includes they rode on are moot — `main.asm`
> itself is deleted. Same closure as the "Dead 68k table copies" bullet in the Task-0 follow-ups
> above; the two entries were tracking the same two files.
**Surfaced during:** Sound 1C pre-merge audit (2026-06-17).
**Status:** Harmless in 1C; candidate for trimming in a later phase.
**What:** The FM writer / sequencer read **inline Z80 copies** of the sound tables and FM
patches (`engine/sound_tables_z80.asm` and `data/sound/fm_patches.inc`, both included into
the `phase 0` Z80 blob). The **68k ROM copies** — `data/sound/sound_tables.asm` and
`data/sound/fm_patches.asm` (the latter `include`s the same `fm_patches.inc`) — are emitted
into ROM (via `main.asm`) but **not read by any 1C code path** (decision: inline for 1C, not
banked). They exist for a future banked-ROM loader. They are **drift-guarded**: the patch
bytes are single-sourced through `data/sound/fm_patches.inc` (a `pbyte` macro picks `dc.b`/`db`
per CPU), and `gen_sound_tables.py`'s generator + its pytest keep the table copies in sync, so
the dead copies cannot silently diverge.
**When to fix:** a later phase that either (a) adopts a banked-ROM song/patch loader (then the
68k copies become live), or (b) decides inline-only is permanent (then drop the unread 68k
`.asm` copies + their `main.asm` includes to reclaim ROM). No urgency — drift-guarded, small.

### Phase 2–6 sound backlog (master sound spec §12)
**Surfaced during:** Sound 1C pre-merge audit (2026-06-17), per the 1C design §2 "explicitly deferred."
**What (each its own plan, per master spec §12):**
- ~~**Phase 2 — DAC powerhouse:** N-channel DAC mixer (quality-adaptive single↔mix), stereo/pseudo-
  stereo PCM, pitch-shifted SFX, half-rate samples, BRR codec (after spike), bank-switch optimization.~~
  **SUPERSEDED (2026-06-24/25 DAC format revision + 2026-07-01 amendment header on the master spec):**
  single voice, raw 8-bit, pre-mixed composites; mixer/BRR/pitch-shifted-PCM/half-rate cut (doors kept
  via `ds_codec`/`ds_rate`); bank-switch optimization SHIPPED (cached `SndDrv_SetBank`). Mixer rejection
  pending user ratification — see ARCH §6.2.
- **Phase 3a — FM depth (SHIPPED, merged `c89bea3` 2026-06-19):** per-frame modulation engine,
  per-song pitch table + pitch envelopes (trills/arps), pan, signed per-op TL bias, voice-stepping
  via build-time register deltas, hardware LFO ($22=$08), note-fill gate articulation, native Moving
  Trucks port. **Deferred build-on-demand within 3a:** **Task 7 portamento** (MEV_PORTA — `sc_porta_*`
  struct fields reserved, not rendered) and the **formal Task 9 verification-harness file**
  (`tools/phase3_verify.py` was never written; MT fidelity was instead verified ad-hoc by rendered-audio
  comparison vs the GD3 rip — see memory [[project_mt_resolved]]).
- **Phase 3b — FM extras (PARTLY SHIPPED 2026-06-27, music-expr merge):**
  ~~dual per-channel data streams~~ DONE (`sc_mod_ptr` slot[1] + `MacroTick` + `MEV_MACRO`, see E4 above);
  ~~SSG-EG~~ load-time DONE (`FmPatch` $90 group — runtime 7th-RegDelta-group still open, see E5);
  ~~full PSG envelopes~~ DONE (`Seq_Op_PsgEnv`/`MEV_PSGENV`, music-legal);
  ~~raw-register escape hatch~~ DONE (`MEV_REGWRITE` $F8, $2A/$2B-guarded).
  ~~true (division-based) portamento~~ DONE (per-note `MEV_PORTA` shipped resident 2026-07-02, budget
  phase T10); ~~broader sequencer-driven LFO use~~ DONE (`MEV_LFO`, music-expr Phase 2).
  **STILL DEFERRED:** Ch3 special/CSM, detune-unison.
- **Phase 4 — Adaptive FM6/DAC slot:** the three content-adaptive modes (full 6th FM voice /
  Batman time-share / permanent N-channel DAC mixer). 1C keeps FM6 permanently the DAC (simple model).
- **Phase 5 — Engine integration & game-feel:** section-aware sound banking, music fade state machine,
  distance attenuation + priority SFX mixing, procedural ambient soundscape, continuous SFX. (These are
  ENGINE_ARCHITECTURE §6.4–6.7, all DEFERRED.)
- **Phase 6 — MegaDAW compiler:** event-list format finalization, MegaDAW export retarget,
  sample/DC-offset encoders. (1C hand-authors the test song; MegaDAW integration + real song-sourcing
  are downstream/user-driven — the engine defines the format contract first.)
**Blocked by:** 1C, Phase 3a, the **SFX engine**, and the **music-expression spine** (Phase 1 + Phase 3) have
all merged to master. SFX now exists (`Sound_PlaySFX`, steal/priority/ducking) — the "no SFX path" gap is
**CLOSED**. The current sound priority is **music-expression Phase 2** (per-note portamento/detune + global
fade/tempo/hardware-LFO). Remaining after that: the DAC format revision (Phase 2 powerhouse — needs user
sign-off, irreversible), Phase 4 content-adaptive FM6, Phase 5 game-feel integration (section-aware banking,
fade state machine, distance attenuation, ambient, continuous SFX), Phase 6 MegaDAW. Each phase is audible +
Exodus-verifiable.
**See:** `docs/superpowers/specs/2026-06-16-sound-driver-design.md` §12; `docs/superpowers/specs/2026-06-17-sound-1c-design.md` §2.

### Defensive Z80 RAM Upload — Verify-and-Retry
**Surfaced during:** Ristar disassembly deep-dive (2026-04-27). Source:
`ristar_disasm/code/disasm.asm` lines 8330–8350 (`$641A` upload routine);
analysis in `ristar_disasm/ANALYSIS.md` § "Sound architecture (CONFIRMED)".
**Blocked by:** N/A for 1C — the from-scratch driver is **assembled inline into the ROM**
(`engine/z80_sound_driver.asm`, `phase 0` blob), so there is no runtime 68k→Z80 byte-by-byte
*driver upload* to wrap. This pattern applies only if a future phase streams driver/data bytes
into Z80 RAM at runtime (it does not today).
**What:** Ristar's Z80 RAM upload routine writes each byte, **reads it
back to verify**, retries up to 16 times on mismatch before giving up.
Most Genesis games trust the write; Ristar's team apparently saw
intermittent bus-contention failures and added the retry loop. The
relevant pattern (paraphrased):

```asm
; In: a0 = src, a1 = z80_dst, d0 = byte count - 1
upload_loop:
    move.b  (a0)+, d1               ; load src byte
    moveq   #15, d3                 ; retry counter
.retry:
    move.b  d1, (a1)                ; write to z80 ram
    cmp.b   (a1), d1                ; verify
    beq.s   .ok                     ; matches → next byte
    dbra    d3, .retry              ; mismatch → retry
    bra.s   .abort                  ; give up after 16 tries
.ok:
    addq.w  #1, a1
    dbra    d0, upload_loop
```

**When ready:** Only if a future phase adds a **runtime** 68k→Z80 RAM byte-copy
(e.g. streaming song/sample data into Z80 RAM, rather than the current inline-in-ROM
driver). Wrap each Z80 byte write with the read-back-verify retry loop. ~30 extra lines
of asm. Not applicable to the inline-assembled 1A/1B/1C driver.
**Why bother:** Cheap insurance against a real-but-rare bug class. Most
runs will hit `.ok` on the first try; the retry only fires when the bus
is contended (probably never on most hardware revisions, but the cost is
~zero when it doesn't fire). Catches write-loss before it manifests as
silent driver failure or audio glitches that are nearly impossible to
debug after the fact.
**See:** `ristar_disasm/ANALYSIS.md`, `ristar_disasm/code/disasm.asm`
lines ~8330–8350.

### Bank-latch desync corrupter — unidentified (2026-07-02)
Captured ONCE on HCZ2 (~44 s in): the Z80's physical $6000 bank latch and the driver's
`SND_CUR_BANK` cache desynced during a mid-sample DAC retrigger window; every $8000-window
read then returned $FF forever, so every music channel read $FF = `MEV_END` and ended
silently — and every subsequent song load stayed SILENT permanently, because
`SndDrv_SetBank`'s cache short-circuit (`SND_CUR_BANK` == requested → `ret z`) meant the
load never reprogrammed the physical latch. The PERSISTENCE half is fixed (Snd_LoadSong now
poisons `SND_CUR_BANK` with the $FF sentinel before its first SetBank, forcing a full
physical latch program on every load); the CORRUPTER itself is still unidentified — it may
even be an emulator artifact rather than real driver state loss. Evidence is preserved in-repo at
`docs/research/wedge_evidence/` (the capture + README with the full analysis; also covers the
related deterministic StopMusic cross-wait wedge found the same day). The
race did NOT reproduce on a deterministic re-run past the loop point — it is
alignment-dependent. **Hunt plan:** live watchpoint session on $6000-latch writes plus
`SND_SONG_BANK`/`SND_ROM_BANK`/`SND_CUR_BANK` around a mid-sample DAC retrigger, to catch
the latch and cache diverging in the act. **Optional second hardening** (deliberately
deferred pending the Task-9 cycle budget): a per-frame uncached re-latch at
`Run_SeqFrame_OnSongBank`'s head, ~8-12 B + ~100-130 cyc/frame, which would bound any
future desync to a single frame instead of one song.

## From Build Pipeline — Future Optimizations

### Pre-Baked Path Tables for Loops / Special Geometry
**Surfaced during:** §4.7 world-space strip cache brainstorm (2026-04-30).
**What:** Define loops, S-tubes, and corkscrews as parametric curves in the editor. Build tool samples the curve and emits a path table: sequence of (x, y, angle) waypoints. At runtime, player snaps to path and interpolates between waypoints — no per-frame collision queries during traversal. Eliminates the most complex and error-prone collision scenarios. Classic Sonic's loops use path-swapping between collision layers with hand-tuned height maps; this approach makes loops reliable by construction.
**Blocked by:** Level editor integration, §3 player physics (need movement system to consume path data).

### Build-Time Collision Validation
**Surfaced during:** §4.7 world-space strip cache brainstorm (2026-04-30).
**What:** Use modern CPU power to simulate player traversal at build time. Verify slopes are traversable (not too steep for physics constants), detect collision gaps, flag unreachable areas, check height profile transitions between adjacent cells for smoothness. Catches level design errors before they hit hardware.
**Blocked by:** §3 player physics (need physics constants and movement model to simulate), §4.7 collision system (need collision data format finalized).

### Animated Tile DMA Scripts
**Surfaced during:** §4.7 world-space strip cache brainstorm (2026-04-30).
**What:** Pre-compute animated tile sequences (waterfalls, conveyors, flickering lights) as table-driven DMA scripts at build time. Each frame entry is a pre-built DMA command (source ROM addr, VRAM dest, length). Runtime just steps through the table — zero computation, zero logic. Build tool handles figuring out VRAM addresses after ~~graph coloring~~ and structuring DMA entries.
**Blocked by:** Animated tile system design (Phase 4), ~~VRAM graph coloring integration~~.
> **⚠ BLOCKER CORRECTED 2026-08-05 — the second blocker cannot ever be satisfied.** There is no
> VRAM graph coloring to integrate with; the allocator is dead (see the §2.3 correction). Read
> both mentions as "after the build tool assigns VRAM addresses", which the **deduped paged act
> pool already does** — so that half of the blocker is effectively discharged, not pending.
> **What genuinely blocks this is the first item only: the animated-tile system design.**
> Note also that a table-driven animated-band mechanism already ships in some form (`BgAnim`
> bands, referenced by the diagonal-budget and Deep-Forest-BG entries); check against it before
> designing from scratch.

---

## How to Use This Document

When starting a new planning phase:
1. Read the **RECONCILIATION BANNER** at the top first — it tells you which strata to trust.
2. Read the **NOW UNBLOCKED — actionable** section. That is the pick-up list.
3. Read through the remaining deferred items; check whether any blockers are now resolved.
4. **Re-derive any pre-July `file:line` anchor before chasing it** — those citations point into
   `.asm` files that no longer exist.
5. If an item is live, include it in the new plan.
6. ~~Move completed items to a "Done" section at the bottom (with the date and the system that
   unblocked them)~~ — **superseded 2026-08-05: annotate closures IN PLACE.** See the
   MAINTENANCE PROTOCOL section at the top. The Done section below is a frozen historical tail
   (Apr-Jun 2026); nothing new goes into it.

---

## Done (FROZEN — historical tail, Apr-Jun 2026)

> **Frozen 2026-08-05.** This section stops at 2026-06-11 and is not being extended. Roughly a
> dozen later closures were annotated in place instead of being moved here, and in-place
> annotation is now the convention (see MAINTENANCE PROTOCOL at the top). Entries below are kept
> verbatim as the record of the Apr-Jun era.
>
> **⚠ One entry in this section is actively misleading:** "§2 Phase 2 Layer A.3 — Build-time Graph
> Coloring — 2026-04-26" records a shipped feature that was **later deleted** (superseded by the
> globally-deduped paged act pool, 2026-06-22). Reading it alongside the §2.3 entry above produced
> the contradiction — the same feature listed as both future work and done — that this pass
> resolved. It shipped, then it was removed. Its sibling A.4 entry already carries a
> DELETED-2026-06-11 note of the same kind; A.3 did not, and now does.

### Strip data emission + streaming decompressor removed (dead format) — 2026-06-11
**Completed in:** compression-two-tier Task 5 (dead-code sweep).
**What:** The 2D block cache replaced column strips entirely; the remaining strip
artifacts are gone. Deleted: `engine/s4lz_stream.asm` (zero callers) + `StreamState`
struct + `S4LZ_Stream_States` RAM; `tools/ojz_strip_gen.py` Pass 5b (wide-strip
`.s4lz` + checkpoint emission); the legacy `OJZ_Sec*_Strips_S4LZ` /
`OJZ_Sec*_Strip_Checkpoints` BINCLUDEs in the act descriptor (~50 KB ROM); orphan
generated files (`sec*_collision.s4lz` — no generator, no references;
`sec*_tiles.s4lz` — replaced by `.zx0`; stale sec9-D leftovers from the 16-section
era). Raw `sec*_strips_a.bin` emission STAYS — it feeds `ojz_block_gen.py` and the
editor (`sec*_strips_source.bin`). Also deleted `Section_StreamArtGroup` +
`STREAMING_BUFFER_A/B` + `Streaming_Active_Buffer` + `SS_STREAMING` (see the A.4
entry note below). The Sec struct never carried strip pointers by this point — no
layout change.

### §2 Phase 2 Layer A.5 T1 — Per-Section Background (Zone-Shared Tier) — 2026-04-26
**Completed in:** §2 Phase 2 Layer A.5 (T1 only — T2/T3 fixtures deferred, see new entry below)
**What:** Plane B per-zone background art end-to-end. New shared-region VRAM block at slots 1280-1535 ($A000-$BFFF, 8 KB) reserved for BG tiles permanently — never overwritten by section transitions. Build tool extended: `load_bg_layout` parses OJZ_1.bin's BG section (16 chunk-rows × 128 cols), `build_bg_nametable_words` samples a 64×32 region, `emit_bg_tile_blob` dedupes + emits `bg_tiles.bin` with a 2-byte length header, `emit_zone_bg_layout` rewrites tile-index fields into the shared region (BG_TILE_BASE_SLOT + canon_idx). `chunk_get_tile_word` now honours chunk-entry X/Y flip flags (bits 10/11 per sonic_hack ProcessAndWriteBlock) — a latent bug uncovered during BG visual diff. Engine: new `engine/level/bg.asm` with `BG_Init` (loads BG tile blob to $A000 + blits zone nametable to Plane B at $E000, both blocking VDP DATA-port writes wrapped in stopZ80/startZ80) and `BG_RedrawForSection` (T2/T3-ready, called from teleport handlers; T1 sections with NULL `sec_bg_layout` skip). New struct fields: Sec.sec_bg_layout (replaces dead sec_strips_b placeholder, $1C, longword), Act.act_bg_layout ($16, longword), Act.act_bg_tiles ($1A, longword), Act struct $1A → $1E. Test scaffold loads dual palette: Pal_BGND (SonicAndTails, CRAM line 0) + Pal_OJZ (CRAM lines 1-3) matching sonic_hack's runtime layout.
**OJZ measurement:** 218 unique BG tiles (well within 256-slot capacity), bg_tiles.bin = 6978 bytes, zone_bg.bin = 4096 bytes, ROM cost ~11 KB. Engine cost: ~1.5 ms blocking at level init (display off), zero per-frame. Drop of 212 KB ROM elsewhere from removing the placeholder strips_b BINCLUDEs.
**Verified visually in Exodus:** Plane B renders OJZ's authentic cloud band (top) + sky transition + grass band (bottom) with magenta/pink/green palette colors, matching sonic_hack's Level_OJZ1_BG reference structure (image-9-style).
**Architectural fix vs spec:** §2.4's "T1 shares FG tiles, zero VRAM cost" claim was unworkable with A.3's per-section graph-colored FG pool — slots 0-1279 swap on every section transition, so BG nametable references can't reliably use them. The shared 256-slot region is the correct architectural fit. See `docs/research/per-section-background.md` Q5.
**See:** `docs/research/per-section-background.md`, `docs/research/tile-pipeline-measurements.md`.

### §2 Phase 2 Layer A.4 — Per-Section Deferrable Streaming — 2026-04-26
**DELETED 2026-06-11 (compression-two-tier Task 5):** `Section_StreamArtGroup` ended up
with zero callers — the union-blob model (color-class sections share one tile blob, so a
neighbor's art is already in VRAM; teleports mark sections `SS_RESIDENT` directly) made
runtime art streaming unnecessary, and the 2D tile cache (§4.7) superseded the preload
design it served. Removed with it: `STREAMING_BUFFER_A/B` (8 KB RAM),
`Streaming_Active_Buffer`, `STREAMING_BUFFER_SIZE`, and the `SS_STREAMING` state (value 1
retired; `SS_IDLE`/`SS_RESIDENT` keep their values). Entry below kept as history.
**Completed in:** §2 Phase 2 Layer A.4 (structural — visual verification blocked on upstream bug below)
**What:** `Section_StreamArtGroup` (engine/level/load_art.asm) decompresses + queues Deferrable DMA for an upcoming section. `Section_Check` extended to fire the preload trigger ~1024 px before the FWD teleport threshold (and ~512 px before BWD). Per-section state machine in `Section_Stream_State` (16 bytes RAM): `SS_IDLE` → `SS_STREAMING` → `SS_RESIDENT`. Two streaming buffers (`STREAMING_BUFFER_A`/`B`, 4 KB each, carved from existing `Decomp_Buffer`) handle fast direction reversals via round-robin. `Section_TeleportFwd`/`Bwd` retain blocking `Section_LoadArt` as a fallback for IDLE-state sections. `Level_LoadArt` reads section IDs from the act descriptor (not `Slot_Section_Map`) so it can be called before `Section_Init`.
**Verified structurally in Exodus:** `Section_Stream_State[0]=[1]=SS_RESIDENT` after Level_LoadArt; forward teleport advanced slot map 0/1 → 1/2 and Section_LoadArt fallback path fired correctly; backward teleport reversed cleanly.
**Visual verification blocked:** the test viewport renders mostly black due to a pre-existing upstream chunk/block parsing bug — see "Chunk/block parsing produces mostly-empty tiles" below.
**Closes the §4 Phase 1 deferred item:** "Section Preload with S4LZ Deferrable DMA" (the engine plumbing).
**See:** `docs/research/section-streaming.md`, `docs/research/tile-pipeline-measurements.md`.

### §2 Phase 2 Layer A.3 — Build-time Graph Coloring — 2026-04-26 — **DELETED SINCE (see note)**
> **⚠ SHIPPED, THEN DELETED.** Annotated 2026-08-05, matching the note its sibling A.4 entry has
> carried since 2026-06-11. The DSATUR coloring, `compute_adjacency`/`color_sections`,
> `assign_section_slots`, per-section tile blobs and `sec_vram_bases.asm` described below were
> **superseded by the globally-deduped, spatially-ordered paged act art pool** (2026-06-22, the
> OJZ tile-budget resolution) and then removed. Zero hits tree-wide for `DSATUR`,
> `color_sections`, `compute_adjacency` as of 2026-08-05; `ENGINE_ARCHITECTURE.md` and `CLAUDE.md`
> were both reconciled away from graph coloring in the Phase-3 cleanup. Kept verbatim as the
> record of what was built and why it was replaced.
**Completed in:** §2 Phase 2 Layer A.3
**What:** Section adjacency graph + DSATUR greedy coloring + per-section VRAM-slot assignment, all at build time. `tile_dedupe.py` gained `compute_adjacency`, `color_sections`, `assign_section_slots`. `tools/ojz_strip_gen.py` emits per-section tile blobs (one per OJZ section) and an auto-generated `sec_vram_bases.asm` constants file. `Sec` struct gained `tile_art_s4lz` longword + `tile_art_vram` word (struct $40 → $48; `Section_GetSlotDef` updated to multiply by $48 = 72 instead of 64). New `Section_LoadArt` decompresses + DMAs one section's blob; `Level_LoadArt` walks the slot map and calls it for both initial slots; `Section_TeleportFwd`/`Bwd` call it for the new section after each teleport. The leapfrog system's adjacency invariant guarantees that the two visible slots always hold sections in DIFFERENT colors → DIFFERENT VRAM ranges → both render correctly simultaneously. A.2's region-1/region-2 fields removed from `Act_Desc` (multi-region packing remains in `tile_dedupe` for future use; A.3's per-section model is the active path; Act struct shrunk back to $16).
**OJZ measurement:** 16 sections in a horizontal chain → 15 adjacency edges → chromatic number 2 (path graph is bipartite; DSATUR optimal). Color bases: [0, 10]. Max simultaneously-resident: 20 tiles (10 per color × 2 colors; per-section blobs include shared tile 0 separately, so total > A.1's 10. Structural regression for OJZ-scale data; structural enabler for any zone that exceeds A.1's 1536-tile ceiling).
**Verified in Exodus:** Default rendering matches A.2 byte-for-byte. Forward teleport updates slot map 0/1 → 1/2 and runs Section_LoadArt for section 2 (Decomp_Buffer confirms section 2's tile data was decompressed and DMA'd). Backward teleport reverses. No nametable corruption, no flicker, rendering correct in both directions.
**See:** `docs/research/section-graph-coloring.md`, `docs/research/tile-pipeline-measurements.md`.

### §2 Phase 2 Layer A.2 — Multi-region VRAM Packing — 2026-04-26
**Completed in:** §2 Phase 2 Layer A.2
**What:** `tile_dedupe.pack_regions` partitions canonical tiles across multiple VRAM regions; `tools/ojz_strip_gen.py` emits per-region pools (`ojz_tiles_r1.bin` / `ojz_tiles_r2.bin`) and supports `--force-region1-cap` for stress testing the spill path. Engine: `Level_LoadArt` calls `LoadArt_S4LZ` once per non-empty region. `Act_Desc` grew with `tile_art_r2_s4lz` longword (struct size $1C → $22). New constants `REGION1_TILE_CAPACITY=1536`, `REGION2_VRAM_BASE=$F800`, `REGION2_TILE_CAPACITY=64` define the layout. Region 2 lives in Plane B's off-screen rows ($F800-$FFFF, 16 rows × 128 bytes, 64 tiles), safe because OJZ's `cam_max_y=128px` keeps the visible bottom at nametable row 44 with a 3-row safety margin.
**Default-OJZ measurement:** 10 tiles fit in region 1; region 2 empty (placeholder S4LZ blob). Verified visually no regression vs A.1.
**Forced-spill (--force-region1-cap=5):** 5 tiles in region 1 (slots 0-4) + 5 in region 2 (slots 1984-1988); rendering matches default Exodus screenshot byte-for-byte. Confirms multi-region remap + dual LoadArt_S4LZ path works end-to-end.
**See:** `docs/research/multi-region-packing.md`, `docs/research/tile-pipeline-measurements.md`.

### §2 Phase 2 Layer A.1 — Tile Dedupe + Nametable Remap — 2026-04-26
**Completed in:** §2 Phase 2 Layer A.1
**What:** Global flip-aware tile dedupe across all 16 OJZ sections, with build-tool nametable strip remap. New `tools/tile_dedupe.py` module (canonical_form + dedupe_tiles + remap_nametable_word, 12 unit tests, lex-smallest of 4 orientations as canonicalization rule per `docs/research/tile-dedupe-canonicalization.md`). `tools/ojz_strip_gen.py` extended with `decompress_full_ojz_art` + `collect_referenced_tiles` and a 3-pass generate flow (build strips → dedupe globally → remap + emit). Engine: new `engine/level/load_art.asm` exposes `LoadArt_S4LZ` (decompress to `Decomp_Buffer`, queue Critical DMA) and `Level_LoadArt` (act-descriptor-driven orchestrator). `Act_Desc` struct gained `tile_art_s4lz` longword + `tile_art_vram` word. `STRIP_TILE_HEIGHT` bumped 32 → 48 to sample first ground band. Build.sh now invokes ojz_strip_gen + s4lz compress. Test state replaces two manual `QueueDMA_Critical` calls with one `Level_LoadArt`. Closes the deferred "OJZ Tile Art Loading — Full Terrain Visibility" item. **Headline:** strip tile-index ceiling 1856 → 9, nametable collisions 2 → 0, VRAM bytes 10,304 → 320 (32× less). Full per-layer metrics in `docs/research/tile-pipeline-measurements.md`.

### VInt_DrawLevel CD-bit Corruption + Section_UpdateColumns Ring-Buffer Tracking (§4.1) — 2026-04-26
**Completed in:** §4 Phase 1 polish
**What:** Two integration bugs uncovered by the synthetic scroll test (`tools/synth_scroll_test_gen.py`).
1. VInt_DrawLevel's `lsl.l #2, d0` encoding leaked d0[31:16] garbage into VDP CD bits, randomly redirecting ~70% of column writes to VSRAM instead of Plane A. Fix: `moveq #0, d0` before reading the VRAM addr each iteration of `.next`.
2. Section_UpdateColumns tracked left/right boundaries independently, ignoring that the 64-col nametable wraps. Fix: clamp the opposite side after each loop so `Right - Left ≤ 63` always represents what's actually correct in VRAM.

### 128KB DMA Boundary Splitting (§1.1 / §2.1) — 2026-04-24
**Completed in:** §2 Art & Compression Pipeline
**What:** `QueueDMATransfer` checks if `source + length` crosses a 128KB boundary and splits into two queue entries. Sub+sub carry-flag approach (~16 cycles common case).

### Build-Time DPLC Tools (§2.1 / §2.6) — 2026-04-24
**Completed in:** §2 Art & Compression Pipeline
**What:** `tools/dplc_layout.py` — contiguous art rearrangement (1 DMA entry per frame change) + DPLC entry merging (3.1 → 1.2 entries average). Sprite art extracted to `art/uncompressed/`, optimized art in `art/optimized/`, DPLC tables in `data/dplc/`.

## Sound — small deferred items from the 2026-07-01 review follow-up

### Cold-boot DAC pan seed (init $B6)
A `SND_REQ_SAMPLE` posted before the FIRST song load plays silent/one-sided (YM
powers on with $B6 L/R=0; the per-sample-start $C0 force was correctly moved to
the song loader so authored DAC pans survive, but `SndDrv_Init` doesn't seed
$B6). Debug-mailbox-only today (every shipped DAC trigger rides a song). Fix =
~10 B part-II seed in init — schedule with the Z80 RAM/ceiling rework.

### Boundary-tick patch pre-loading (generator)
Body-prefix thinning (b48b35e) cut the measure-5 burst 236->86 writes and fixed
the audible stutter, but boundaries with GENUINE multi-channel instrument
changes still cost ~25-35 ms ticks (per-load cost through the banked window).
If one ever turns audible: pre-load the new patch during the preceding gate gap
(the channel is keyed-off there — no audible timbre switch).

### ~~Frame-clock effective-rate tuning~~ — DONE 2026-07-02 (budget phase T11)
~~Timer-A N=136 (nominal ~59.99 Hz) measures ~59.63 Hz effective in Exodus (idle
poll latency). If a finer match to reference cadence is ever wanted, retune N
against MEASURED cadence (and re-pin the build assert) rather than nominal math
— but real hardware latency may differ from Exodus; don't tune to the emulator.~~
**Retuned exactly as this entry prescribed:** measured 59.873 Hz effective under
HCZ2 load at N=136 (deterministic from-start window), re-pinned to the compensated
N=137 (`SND_FRAME_MILLIHZ` 60053) → **59.9227 Hz exactly** over 10,800 frames, dead
center in the ±0.02 gate. `docs/research/phase_harness/t11_verification.md`.

## Sound — deferred follow-ups from the Sound Performance & Budget phase (2026-07-02)

Phase record: `docs/superpowers/specs/2026-07-01-sound-performance-budget-design.md` +
`docs/research/phase_harness/t*_verification.md` + `t12_matrix.md` (final numbers) +
`phase_notes.md` (the accumulated minors).

### Worst-tick shortening — the honest lever for the remaining DAC-hold tail (T9 outcome)
Drum airtime lost to holds sits at 24.1% vs ref's own 21.4%; the gap is a handful of
5-10 ms ticks (~4.6/s vs ref ~1.0/s). In-tick draining (D.2) was measured net-negative
twice and reverted — the remaining lever is SHORTENING THE WORST TICKS themselves:
profile what dominates them (patch-load YM busy-waits, bulk-refill length, event
clusters) in its own profiling round. `docs/research/phase_harness/t9_verification.md`.

### HCZ2 import loop-length residual (~−0.52% tempo vs S3K) — tools-side
The engine tempo model is now S3K-exact (`b342889`); the residual −0.52% drift is an
IMPORT defect: our packed HCZ2 loop runs ~14 event-ticks SHORT per loop vs the SMPS
source — same family as the fixed drum standalone-duration bug. Audit per-channel
packed loop tick counts vs the SMPS source (`tools/smps_import.py`). Related: MT's
tempo is −0.196% by construction (zyrinx rate 2/7 unrepresentable in the 8-bit mod
model; 73/256 is the nearest). `docs/research/phase_harness/t12_matrix.md` H.4.

### Held-envelope resolve cost (T8 review info item — perf backlog)
Sustained/parked env channels still pay id-resolve + cursor walk per frame
(~90-180T FM, up to ~540T PSG worst case `PsgVolEnv_1D`) just to rediscover $81/$83;
a held-sentinel (cursor bit 7) would cut that to ~30T. Needs bytes; the chip-write
elimination (T8) already removed the dominant cost. Revisit with any tick-cost round.

### Small correctness minors swept during the phase (from `phase_notes.md`)
- **$28 REGWRITE guard gap:** `Seq_Op_RegWrite` guards $2A/$2B/$24-$27 but NOT $28 —
  an authored REGWRITE to $28 can desync chip key state from `SCF_KEYED` (which the
  T5 chokepoint's bit-test relies on). ~4-6 B to extend the guard.
- **sc_base_freq steal-latch:** under SFX override, bare-note/NOTE_DUR paths skip the
  `sc_base_freq` latch (`Seq_HookNoteOn` ret nz), so a note change DURING a steal
  restores the pre-steal pitch; NOTE_RAW's pre-gate latch is the model fix. The
  comment at `sound_sfx.asm:1013-1017` oversells the current behavior.
- **Stale comment:** `z80_sound_driver.asm:1290-1292` "once the gates are removed
  (later task)" — the gates were removed in music-expr Phase 1.

### FM env attack seam (T8 residual — by-ear pending)
FM key-on resets the `sc_env_out` shadow to 0 without a TL emit; an FM env body with
leading zeros rides the PREVIOUS note's latched TL for 1-2 frames — after a
rest-silenced note the next attack could open TL-silenced. Not visible in rendered
A/B at capture scale; awaiting the user's by-ear pass. Candidate 0-2 byte fix if
audible: key-on primes the shadow with a never-matches sentinel.
`docs/research/phase_harness/t8_verification.md`.

---

## Sound — deferred follow-ups from the wave-4 Z80 reclaim (2026-08-03)

Parcel record: `docs/superpowers/plans/2026-08-03-wave4-z80-sound-reclaim.md` +
`docs/superpowers/notes/2026-08-03-wave4-sound-ab.md` (A/B evidence) +
`docs/reviews/2026-07-16-emp-port-optimization-review.md` STATUS UPDATE (drops/rejections).
Defect write-ups in `docs/BUGS.md`. The parcel executed review items **23 + 24**; item 25
and the two coverage gaps below are what it deliberately left on the table.

### Review item 25 — sequencer H1-H3 + M-items (≈ −71..−94 B still available)
**Surfaced during:** wave-4 scoping — item 25 was ruled OUT of the parcel by Volence as a
separate follow-on.
**Status:** unstarted. Roughly **−71..−94 B of pure-size, chip-stream-identical work**
remains in `sound_sequencer.emp`; `Porta_Apply`'s ladder factor alone is **−40..55 B**.
Everything in the parcel's ledger was measured, so these estimates are the last unmeasured
ones in the sound tree.
**CORRECTION that must not be inherited (do NOT re-plan on the review's premise):** the
review calls H1's per-channel tempo gate "provably redundant." **It is not.**
`Seq_Op_Tempo` (`$F3`) broadcasts **mid-frame**, from inside channel N's tick, so channels
0..N run that frame's gate with the old modulus and N+1.. with the new — a **permanent
accumulator phase offset**. Hoisting to a global accumulator is *more* S3K-exact but IS a
chip-stream change on that frame, so it cannot ride a PS (pure-size) bar. Dormant only
because no shipped song contains a tempo event. Its advertised "**−2 B/channel RAM**" is
also **not collectable**: `sc_tempo_mod`/`sc_tempo_accum` live in the SeqChannel↔SfxChannel
shared prefix that the `sx_pad+58 == sc_detune` invariant depends on.

### PSG vol-env fold clamp is a SINGLE-BIT test — wrong-channel write hazard
**Surfaced during:** wave-4 Task 9 (comptime hardening), while proving out the
`Psg_SetVolume` `Snd_ChanClass` collapse.
**Status:** contained by a build-time assert, NOT repaired. High-value to record because
the containment is data-side, not code-side.
**What:** the PSG **class** fold clamps with `cp $0F+1` — a real magnitude test. The PSG
**vol-env** fold clamps with `bit 4,a` — a **SINGLE-BIT** test. A fold sum in `$20..$2F`
therefore passes **UNCLAMPED**, and `$20` OR'd into the `$90|(ch<<5)` volume latch corrupts
the **CHANNEL-SELECT bits** — i.e. the attenuation is written to the WRONG PSG CHANNEL.
**Why it is unreachable today:** every authored PSG env body byte is `<= $10`, so the worst
fold is `$10 + $0F = $1F` — exactly one below the cliff. That margin is now **enforced by a
generator assert added in this parcel** (poison-tested: a `$11` byte fails the build).
**Consequences worth keeping together:**
- This asymmetry is also what makes the `Psg_SetVolume` fold-collapse UNSAFE — the
  full-domain enumeration returns **517,440 divergent cases out of 1,048,576**, which is why
  that optimization was rejected while its FM twin (7.6) shipped.
- **Restricted to env `<= $10`, the same reorder enumerates CLEAN (0 / 69,632 divergent).**
  So the −5..7 B optimization becomes available the moment the vol-env fold is made a real
  magnitude clamp (matching the class fold) instead of a bit test. That is the fix to reach
  for if the bytes are ever wanted — it buys the optimization AND removes the hazard.

### YM data→next-address spacing has NO structural coverage
**Surfaced during:** wave-4 Task 9 — the task set out to make the review's hand YM-spacing
audit structural, and got **half** of it.
**Status:** address→data IS covered, at all **9** write sites, by `ensure(cycles(...))`
guards that all pass (`Fm_YmWrite` ×2 = 21 T each, matching the review's hand figure
exactly; the seven DIRECT sites that bypass `Fm_YmWrite` measure 17-24 T). The
**data→next-address floor could not be expressed at any site.**
**Why (two independent blockers, both established by probe, not assumed):**
1. `cycles()` takes **proc-local labels** and carves ONE proc's code buffer. Every
   data→next-address gap starts inside `Fm_YmWrite`, exits through `ret` into the caller,
   and re-enters `Fm_YmWrite` — three procs of straight line.
2. Even the caller-local remainder contains `call nn` / `ret` / `pop af` / `bit n,r` /
   `add a,n`, none of which are in `z80_cycles::instr_cost`'s demand subset, so the span
   bails `[cycles.unknown-op]`.
Splitting the requirement across hand-derived prologue/tail constants was rejected — that is
exactly the hand audit the task existed to retire. A coverage ledger comment above
`Fm_WriteFreq` records the gap instead, and `YM_DATA_TO_ADDR_MIN_T` was deliberately NOT
declared: a constant nothing consumes would advertise coverage that does not exist.
**What would unblock it:** widening the cycle model's demand subset to the caller-local
opcodes above, plus a `cycles()` form that can span a call boundary.
**Unresolved question flagged as a CANDIDATE, not a defect:** several direct-write paths
measure **~20 T** data→next-address by hand, against the **~39 T** figure the review used as
the floor. This is NOT confirmed as a defect — the exact per-register hardware rule was not
verified, and there is no real hardware available here to settle it. Worth resolving before
any future change narrows those gaps further.

---

## On-target diagnostic instrumentation — idea capture 2026-07-20

**Framing (shared across three repos):** we use vladikcomper's Error Handler/Debugger
(and `convsym` from the same suite) as our one significant not-from-scratch tool. It's
excellent, but it's designed as a *drop-in library* for someone with an arbitrary
emulator and no control over their assembler — so it renders crashes to the Genesis
screen, symbolizes PC → nearest label, is post-mortem-only, and is 68K-only. **We are not
in that position: we own the whole stack (sigil assembler + Oracle emulator + MCP + build),
and we have no real hardware, so emulator-substitutes-for-hardware is a first-class goal.**
That changes what "better" means — the leverage is tight integration, not out-engineering
his handler. Emulator-side ideas live in `oracle-next/docs/2026-07-20-diagnostic-tooling-ideas.md`;
assembler-side in `sigil/docs/2026-07-20-diagnostic-instrumentation-ideas.md`. This section
holds the pieces that run **on the 68K/Z80 target itself** (the drop-in-library tier).

These are unbuilt ideas, not committed work. Pick up opportunistically.

- **Structured crash-frame mailbox (highest value; pairs with the Oracle reader).**
  Instead of rendering registers to VDP, a thin exception handler writes a fixed
  crash-frame struct (regs, PC, SR, USP/SSP, fault addr, a few RAM breadcrumbs) to a
  known RAM address and halts. Oracle reads it straight off the MCP socket as structured
  data — no rendering path, works even when the VDP is the wedged thing. ~100-200 B of
  68K + a `struct` def. This is the one piece worth building first because it turns crash
  debugging from "OCR the screen" into "query the crash." Reader half is an Oracle task.
- **RAM poisoning for uninitialized-read detection.** Fill all RAM with a poison pattern
  at cold boot; any value read back as poison = read-before-write. Catches the
  "works after soft reset, not cold boot" class. Debug-build only.
- **Stack high-water canary.** Sentinel pattern below the stack; check how deep it was
  ever eaten. 68K has no frame convention, so silent stack overflow into RAM is a common
  nasty failure — this makes it visible. Cheap.
- **Object-slot leak / use-after-free tracker.** Instrument the 64-byte SST slot allocator
  to flag leaks and reuse of freed slots. Debug-build only.
- **Z80 heartbeat / watchdog.** A counter the Z80 bumps that the 68K samples each frame;
  a stalled counter = silent sound-driver hang, which currently nothing catches (the
  drop-in handler is 68K-only). Small; closes a real blind spot.
- **Contract-enforcement trap handler (the 68K half). — ✅ PREREQUISITE HAS LANDED (2026-08-05).**
  Depends on sigil emitting the
  shadow-check instrumentation (see the sigil note). This repo's In:/Out: contract grammar
  (recent `contract-grammar` commits) is the vocabulary; a DEBUG build traps the exact
  instant a routine clobbers a register it swore to preserve or returns garbage in a
  promised `Out:`. High value because the expensive prerequisite (the contract grammar)
  is already being paid for.
  > **2026-08-05:** "already being paid for" has become "already paid, and still growing".
  > `clobbers(...)`/`preserves(...)` are declared and machine-checked across the tree, and HEAD
  > `fa0ae0b` extended the grammar to **declared contexts** (the Z80 bus and the interrupt mask).
  > The vocabulary this item needs exists and is richer than when the idea was captured. What
  > remains genuinely blocked is the **sigil half** — emitting the shadow-check instrumentation —
  > which is a Sigil-repo task, not an Aeon one. Listed in NOW UNBLOCKED with that caveat.

---

## Synced sprite-art streaming — idea capture 2026-07-29

**Framing:** the engine already streams level art aggressively; sprite art is the last
fully-resident holdout. Devon's SCHG guide ("Dynamically Loading Ring Animation Frames
into VRAM", info.sonicretro.org) shows the trick the classics never used: when every
instance of an object class shows the SAME animation frame (one global clock), keep only
the current frame's tiles in VRAM and DMA the next frame in when the clock ticks. This is
NOT per-object DPLC (which would be redundant per-instance loads) — it's one shared slot
+ one compare + one small DMA per frame *change*, serving every instance on screen. The
headline win isn't the VRAM refund; it's that animation frame count decouples from VRAM
entirely (frames live in ROM, uncompressed, DMA'd on demand).

These are unbuilt ideas, not committed work. Pick up opportunistically.

- **Ring frame swap (the concrete, do-first one).** Today: 16 tiles resident at
  `VRAM_RING_PLACEHOLDER` (4 frames × 2×2), `DrawRings` computes attr = base + frame×4
  (engine/objects/rings.emp:141-149) off global `Ring_Anim_Frame`. Change: shrink the
  slot to 4 tiles, freeze the attr at base (per-ring hot loop gets CHEAPER — attr becomes
  a constant), and in the existing `Ring_Anim_Timer` tick queue a $80-byte DMA of the new
  frame from ROM when the frame byte changes (every 8 frames ≈ 16 B/frame amortized,
  ~0.2% of a VBlank on change frames). Refund: 12 tiles. Unlock: the S1-2013 8-frame
  smooth spin (halve tick period, mask 7) at zero VRAM — the real reason to do it.
  Triggers to pick it up: we want the smooth spin, or the tile-1000 gap comes under
  pressure. Engine-contract note: `VRAM_RING_PLACEHOLDER` shrinks from ">=16 tiles" to
  ">=4 tiles" and the game must provide uncompressed frame-sequential ring art + a frame
  count; update engine.inc contract comment + demo game stub when done.
- **Generalize to "synced art channels" if a second consumer appears.** A small table of
  {clock RAM addr, ROM art base, bytes/frame, VRAM dest, frame mask} walked once per
  frame: compare clock vs shadow, queue DMA on change. Rings become channel 0. Candidate
  future channels: checkpoint orb spin, any globally-clocked hazard loop, animated
  goal-post spin. Don't build the table for one consumer — hardcode rings first
  (clean-not-bolted-on cuts both ways: no speculative scaffolding).
- **Single-instance effect streaming (shields, invincibility, signpost).** Different
  sync story, same economics: objects that exist at most once (per player) with many
  frames need only the current frame resident — a per-object stream, and redundant-load
  objections don't apply at instance count 1. The same SCHG family has a
  "Shield/Invincibility Art" guide in this vein. Evaluate when shields/invincibility get
  built (design queue), not before.
- **Badnik archetype animation lockstep (NOVEL BET — needs user sign-off).** Force each
  badnik archetype's loop animation (wing flap, tread roll) onto a per-archetype global
  clock; all instances of a type then share one streamed slot. Payoff scales with the
  mega-act tech demo (many archetypes resident at once is exactly its VRAM pressure);
  costs: lockstep look (subtle for loops), and state-dependent frames (attack poses)
  break sync so only the common loop streams. Genuinely novel — no classic or reference
  disasm does this; flag before designing (leapfrog-provenance rule).

## Release-shape error handler / MDDBG strip — EXECUTED 2026-08-05, then **SUPERSEDED BY OWNER RULING** (corrected 2026-08-05)

> # ⚠ THIS ENTRY DESCRIBED THE OPPOSITE OF WHAT SHIPS
>
> **The strip executed, and was then reversed. Release ships the FULL 4.2 KB MDDBG island.**
> `ReleaseFault` is **not** the release path — it is the **opt-in `lean`-profile-only** path.
> Anyone reading the text below as current would conclude that release has no crash handler and
> that all 60 fault vectors point at a red-screen freeze. Both are false.
>
> ### What actually ships (verified against HEAD, 2026-08-05)
>
> The deciding axis is **`CRASH_REPORT`**, an ordinary comptime define carried by every profile
> (`1` everywhere except the opt-in `lean` profile). `CODING_CONVENTIONS.md` §1.7 tabulates the
> three shapes:
>
> | shape | flags | debug equipment | crash handler | fault vectors point at |
> |---|---|---|---|---|
> | **debug** | `DEBUG=1`, `CRASH_REPORT=1` | yes | yes | `error_handler` per-class stubs |
> | **release** (default) | `DEBUG=0`, `CRASH_REPORT=1` | **no** | **yes** | `error_handler` per-class stubs |
> | **lean** (opt-in) | `DEBUG=0`, `CRASH_REPORT=0` | no | no | `ReleaseFault` |
>
> The gate predicate everywhere on this axis is **`DEBUG == 1 || CRASH_REPORT == 1`** — never bare
> `DEBUG == 1`, "or the debugger vanishes from release" (§1.7).
>
> ### The superseding ruling, in the code's own words
>
> `engine/system/vectors.emp:16-19`:
> > `── CRASH-REPORT POLICY — OWNER-RULED 2026-08-04, SUPERSEDES THE 2026-08-05`
> > `── RELEASE STRIP (review item 29 part 4)`
>
> …continuing: the release ROM is ~9% of a 4 MB cart, so space is not a 68k-side constraint, and
> **a player's crash must be REPORTABLE**. The MDDBG island and its deb2 symbol appendix are
> **DIAGNOSTICS, not debug EQUIPMENT, and diagnostics SHIP.** The shape-split gates are at
> `vectors.emp:79` and `:123`, both reading `if DEBUG == 1 || CRASH_REPORT == 1`.
> `engine/debug/error_handler.emp:12-17` states the same: the island ships in the DEBUG **and**
> RELEASE shapes; "the only shape without it is the opt-in LEAN profile
> (`sigil build --native --lean`, `CRASH_REPORT=0`), which routes every fault at `ReleaseFault`".
> `build.sh:10-19` says it a third time, and enumerates what release still does *not* carry —
> **equipment**: asserts, `SOUND_DEBUG_HOTKEYS`, `SOUND_DBG_MIRROR`, boot autoplay,
> `CompressionSelfTest`, the sound-debug mirror.
>
> ### Why the ordering looks wrong (it isn't)
>
> The ruling is dated **2026-08-04** and the parcel **2026-08-05**. The ruling is nonetheless the
> later authority: it explicitly names and supersedes the strip. The equipment-vs-diagnostics
> distinction is the whole point — the strip conflated the two, the ruling separated them.
>
> ### What survived the reversal
>
> The parcel's work was not wasted; it was **re-gated**, not reverted:
> - `engine/system/release_fault.emp` / `ReleaseFault` **still exists** and is still the described
>   red-screen freeze — it just serves the `lean` profile instead of release.
> - The vectors shape-split still exists — the predicate widened from `debug` to
>   `debug || crash_report`.
> - `null_interrupt.emp` deletion stands.
> - What reverted is the **placement**: `error_handler.emp` is NOT `debug_only`; it is placed
>   under `debug || crash_report`, so plain does **not** shrink by 4.2 KB.
>
> ### Consequences for anything downstream
>
> The "What ships in release today" table below (`plain_len == debug_len == 0x10B0`, 4,272 B) is
> **once again accurate for the release shape** — it was briefly wrong between the parcel and the
> ruling. Its framing as *a leak to be fixed* is what is wrong now: those bytes ship **by design**.
> Likewise the "Why this is blocked" section's central question ("what should a release build do
> on a bus error?") **has been answered**: release runs the real handler. The `lean` profile is
> where the `bra.s *` freeze answer applies.
>
> **Historical record of the strip parcel follows, retained unaltered.**

Part 4 of review item 29 ("build hygiene / release leaks"). Parts 1-3 landed on
`parcel/item29-build-hygiene`; this half stopped at the design gate — now RULED and
EXECUTED. The owner ruling: RELEASE ships ZERO debug equipment but still HALTS
LOUDLY. Implementation:

- `engine/debug/error_handler.emp` (the 12 exception stubs + the vendored MDDBG v2.6
  blob, ~4.2 KB) is now DEBUG-ONLY — registry `if debug` (native.rs), repin.toml
  `debug_only`, and `debugger.asm` gated behind `__DEBUG__` in both `game_root.asm`s.
- NEW `engine/system/release_fault.emp` — `ReleaseFault`: mask IRQs (`move.w #$2700,sr`),
  reset the VDP command state, set the backdrop red (`CRAM[0]=$000E`), `bra.s *` freeze.
  No stack, no `rte`, no `rts`, no `stop_z80`. RELEASE-ONLY (registry `if !debug`,
  repin.toml `plain_only`).
- `engine/system/vectors.emp` fault cells shape-split: DEBUG → per-class stubs, RELEASE
  → ReleaseFault (all 60). `null_interrupt.emp` DELETED (no referencer since item 27).

Verified: plain vector cells all point at ReleaseFault, MDDBG blob absent in plain /
present in debug, plain shrinks ~4.2 KB. Historical design record below.

### What ships in release today

`ERROR_HANDLER` is resident in **both** shapes — `plain_len == debug_len == 0x10B0`
(4,272 B) — and nothing in `engine/debug/error_handler.emp` is shape-conditional.
The registry places it unconditionally (`sigil/crates/sigil-harness/src/native.rs`,
the `engine.` prefix filter), so `demo.bin` carries it too.

| component | bytes |
|---|---|
| 12 exception-vector stubs | 346 (0x15A) |
| vendored MDDBG v2.6 blob (`ErrorHandlerBlob`) | 3,926 (0xF56) |
| `MDDBG__*` equ table | 0 (link-folded) |

The `MDDBG_ERROR_HANDLER` pin is tagged "debug-shape consumer only", which is
about the *symbol reference*, not the bytes. The bytes ship in release.

`Replay_OJZ_Fixture` is NOT in this region — it is its own 320-byte region
immediately after it. It is referenced by nothing in either shape (playback is
armed by an external poke) and is deliberately last before `EndOfRom` so
re-recording shifts no gameplay address. It is not part of this strip; it only
moves as a downstream address.

### Why this is blocked, not merely unstarted

**The two pre-run rulings pull opposite ways.** Ruling 1 says strip the MDDBG
blob *and the exception stubs* from release. Ruling 2 (item 27) says a spurious
or unexpected interrupt must **halt loudly in BOTH shapes**, because it means a
state the engine does not model and should surface rather than corrupt silently.
A release build with the stubs stripped cannot halt loudly unless something
replaces them.

The likely resolution is "strip the 3,926-byte vendored *debugger*, keep a
minimal loud halt for the fault vectors" — but that leaves a real product
question the code cannot answer: **what should a release build actually do on a
bus error?** `NullInterrupt` (`rte`) is the wrong answer for the fault classes —
an `rte` from a bus or address error re-executes the faulting instruction and
hard-loops. Candidate answers, all defensible: a 2-byte `bra.s *` freeze; a jump
to `EntryPoint` (soft reset); a coloured-border-then-hang so the failure is
visible on a TV. Whatever is chosen becomes the target of 55 vector cells.

### What it costs once ruled

Not mechanical. Following the `compression_selftest` pattern (source-gate every
call site, `if debug` in the registry, `plain_len: 0x0` in `pins.rs`, keep the
name in `map.toml`'s union order) covers the placement, but four things sit on
top:

1. **60 dangling `dc.l` cells.** `engine/system/vectors.emp` currently points 60
   of 64 vectors at handler labels, identically in both shapes; it would need a
   shape split. (Was 55. The item-27 parcel, 2026-08-04, executed ruling 2 and
   repointed IRQ1/2/3/5/7 — $64/$68/$6C/$74/$7C — from `NullInterrupt` to
   `ErrorExcept`, so five more cells now depend on the handler surviving. Those
   five are the NON-fault levels; for them an `rte` replacement is at least
   *safe*, unlike the fault classes. `NullInterrupt` itself is now referenced by
   nothing and is kept deliberately — see the note at the top of
   `engine/system/null_interrupt.emp` — precisely so this parcel has a tolerant
   primitive available if the ruling wants one for those five.)
2. **Four ungated file-scope `equ`s in the vendored `engine/debug/debugger.asm`**
   resolve to `pub equ`s living *inside* `error_handler.emp`. Unplacing the
   module removes them from the plain link. Whether the AS residual prunes them
   (it emits no bytes) or errors on the unresolved extern could not be
   determined statically — it must be settled by building. If it errors,
   `debugger.asm` also has to leave `game_root.asm` in the plain shape, which is
   harmless since it is inert without `__DEBUG__`.
3. **Large pin/golden churn**, in release AND in Config-B (silent, plain shape):
   `ERROR_HANDLER.plain_len` 0x10B0 -> 0, `REPLAY_FIXTURE.plain_base`,
   `EPILOGUE`/`EndOfRom`, `pins::ASSEMBLED_LEN`. `error_handler_port.rs` must
   drop its plain arm. Full byte-changing ritual.
4. **`demo` is in scope** on the same registry filter and carries the same 4,272
   bytes and the same 60 vectors.

### Recommendation

Take the ruling on release-fault behaviour first, then run it as its own parcel.
Sequenced after the ruling it is a day of work with a large, well-understood
blast radius; sequenced before, it is a coin flip on a product decision.

---

## Boot YM2612 key-off race — SPEC'd, deliberately NOT fixed (2026-08-04)

Review item 27, finding 3. The boot key-off block (`engine/system/boot.emp:200-230`)
has two real hardware defects: its six data writes are not busy-paced (most are
dropped on real silicon), and in a **sound build** `stop_z80()` can halt the
running driver between its own YM address and data writes, so the 68k's `$28`
latch steals the Z80's resumed data write (a dual-owner address-latch race).

**Owner ruling (2026-08-04): leave the code byte-for-byte untouched, write the
spec instead** — there is no real hardware here to verify timing against, and a
wrong fix is worse than the documented status quo because it would look
addressed. Done: `docs/specs/boot-ym-keyoff-race.md` carries the mechanism, the
two candidate fixes (key off before the bus release; or drop the block in sound
builds), the moot-today reasoning, and the revisit triggers.

**The dangerous revisit trigger:** the block is redundant only because the
`/IC` reset pulse at `engine/system/boot.emp:143-148` already keys every channel
off. Shorten or remove that pulse and these six unpaced writes become
load-bearing. Anyone touching the pulse must read the spec first.

**Unblocks on:** real hardware, or an emulator that models the YM2612 busy flag
and address-latch contention.

## BG blit posture + column-major transpose — EXECUTED 2026-08-05 (parcel/item28-bg-transpose)

> **EXECUTED.** Owner ruling 2026-08-04: take the transpose, take Tier-1
> `move.l`, **no DMA anywhere** (load_art keeps the queue). Deciding the CPU
> posture first dissolved the coupling below — "column-major forces 64 small
> DMAs" only bites if the init blits become DMA, and they did not.
> Landed as provenance chain entry 40; evidence in
> `docs/superpowers/notes/2026-08-05-item28-bg-transpose-ab.md`. The layout blob
> is column-major (pure permutation, 4,096/4,096 cells exact) transposed at the
> single editor->engine boundary (`tools/inject_editor_bg.py`), so editor-space
> artifacts stay row-major and no dual format exists. Framebuffers byte-identical
> over a 900-frame run including 600 frames of max-speed diagonal; zero
> scroll-lag frames on either build; +1 one-time init lag frame (the 64
> per-column VDP command setups), which is the cost the review itself priced as
> init-only noise.
>
> The analysis below is retained as the historical record of the fork.

The part of review item 28 the item is actually named for. The safe half (the
length-1 VRAM-spray guard, the dispatch inversion, the contract and comment
corrections) landed on `parcel/item28-bg-blit`; this half stopped at the time,
per the overnight run's standing instruction to stop on a design fork rather
than pick.

### Why it is one decision, not three

The review says so itself, three separate times: "decide together with bg.asm's
posture", "decide with load_art", and "column-major forces 64 small DMAs if the
init blits become DMA (decide together)".

1. **bg init blits** — both are CPU word pokes today: nametable 4,096 words
   (~90k cycles), tiles up to 7,168 words (~158k) — about **2 frames with SR
   masked and the Z80 stopped**. The ROM sources make this the conventions §7.2
   zero-copy case. Tier 1 `move.l` + halved `dbf` is a ~3-line change for ~80k;
   Tier 2 is a 4x unroll; Tier 3 is real DMA (~0.3-0.4 frame for all 22 KB) but
   needs 128KB-straddle handling.
2. **load_art posture** — queue+VSync vs direct blocking `stopZ80`/DMA/`startZ80`
   at display-off init. Each page currently pays up to a full frame parked in
   `VSync_Wait`; direct DMA saves an estimated **3-8 frames per act load**.
3. **the BG transpose** — column-major takes `Draw_BG_TileColumn` from ~34 to
   ~22 cyc/word (~380 per strip, and this is a **per-frame** cost at scroll
   speed), plus it unlocks `move.l` pairing. The review's consumer census says
   it needs NO dual format: the two linear consumers adapt via autoinc `$80`
   (row stride 128 fits the 8-bit autoinc register exactly) at ~2-3k cycles per
   blob, init-only noise, and their inner loops stay sequential-source.

The coupling is real: choosing DMA for (1) forces column-major into 64 small
DMAs, which changes the arithmetic on (3); and (2) shares the straddle handling
with (1).

### What the transpose costs beyond the engine

- **The ACT blob must be transposed too.** Production sections ship
  `sec_bg_layout = NULL`, so the act fallback is the common per-frame path — a
  transpose that only covers per-section blobs would miss the case that matters.
- `.emp` twins, `tools/ojz_strip_gen.py` and the editor-library blobs all flip
  **in one commit**, or the format is inconsistent between producer and consumer.
- Verification has to be mid-scroll, not at rest.

### One finding from the safe half, for whoever takes this

**The length-1 guard just added is NOT made redundant by a `move.l` conversion.**
A halved long count underflows identically on a 2-byte blob, so the guard would
be re-derived rather than deleted. The guard and the posture are less coupled
than they look, which is why the guard was safe to land alone.

### Recommendation

Take it as one parcel with a posture ruling in front of it, after measuring the
act-load time that (1)+(2) actually cost today — the review's cycle figures are
estimates and no profiling was run. The per-frame win in (3) is the one with
ongoing value; (1) and (2) are load-time only.

---

## RESOLVED — debug-fly is a CHEAT, gated at runtime (ruled 2026-08-05)

Raised as "debug-fly mode is REACHABLE in the shipped release ROM", found by
re-auditing the `crash-report` parcel's no-debug-equipment claim: `Player_Main` and
`TestPlayer_Main` toggled free-flight on a B press with no gate of any kind, so a
player holding B in the shipped build flew.

**Owner ruling: debug-fly is a CHEAT, not debug equipment.** It is therefore not a
§1.7 violation at all once it is gated the way a cheat is gated. Equipment is gated
at BUILD time and absent from release; a cheat is gated at RUNTIME and present but
unreachable. The payload SHIPS in release deliberately.

**What shipped (parcel `cheat-flag`).** A runtime gate, no build-shape gate:

- `Cheat_Flags` — a `u8` bitfield in game RAM (`games/sonic4/config/ram.emp`; cheats
  are game content, not engine).
- `CHEAT_DEBUG_FLY = 1 << 0` — bit 0 (`games/sonic4/config/constants.emp`).
- Both toggle sites test the bit before doing anything and fall straight through
  when it is clear: `Player_Main` (`games/sonic4/player/player_common.emp:249-270`)
  and `TestPlayer_Main` (`games/sonic4/objects/test_player.emp:76-119`).
- Boot-entry tests the same bit: `Player_Init`
  (`games/sonic4/player/player_common.emp:205-209`) — see below.
- The debug shape arms the bit at the game's one-shot boot init
  (`GameState_OJZScroll_Init`, `games/sonic4/test/ojz_scroll_test.emp`) inside an
  `if DEBUG == 1`. Release/lean write nothing: boot clears all Work-RAM, so the
  default of 0 costs **zero release bytes**.

So `Player_DebugEnter` / `DebugExit` / `DebugMove` / `TestPlayer_Debug` still emit
their bytes in release — that is now intended cheat payload, and all three gate sites
say so in comments for the next auditor.

**Boot-entry rides the same bit (done in this parcel).** `Player_Init` used to end
with an unconditional `jbra Player_DebugEnter` — the player *booted* into free-flight
so the streaming-test workflow started in the yellow square. Gating only the B toggle
would have stranded a release player in free-flight forever, since B is now inert:
strictly worse than the ungated state we started from. No separate ruling was needed,
because "default off, a cheat code turns it on" already means a release player starts
as a normal player. `Player_Init` now tests the same bit and tail-calls
`Player_DebugEnter` only when it is armed; with the bit clear it returns normally
with the slot in `PSTATE_AIR`, which lands on frame 1 — nothing else in the init
sequence was conditional on debug-fly. **The DEBUG shape is unaffected**:
`GameState_OJZScroll_Init` arms the bit before it calls `Player_Init`, so a debug
build still boots into the yellow square exactly as it did, and the dev convenience
survives for free. Only release behaviour changed, which was the intent.

**What remains.** (Item 2 was the follow-on question about the B button; it has since
been ruled and executed, and is kept in place below so the ruling sits next to the
gate it depends on. Items 1 and 3 are the genuinely open ones.)

1. **Author the cheat code that sets the bit.** Nothing else has to change when it
   lands: a button sequence or a menu unlock writes `CHEAT_DEBUG_FLY` into
   `Cheat_Flags` and debug-fly becomes reachable in a release ROM. That is the whole
   point of the runtime-gate shape.
2. **Should B join `BUTTON_JUMP_MASK`? — RESOLVED, and EXECUTED as parcel
   `b-jumps` (ruled 2026-08-05).** Jump was `A|C` only precisely because B was the
   debug-fly toggle; once the toggle went behind `CHEAT_DEBUG_FLY`, B did nothing at
   all in release, which is the classic-wrong behaviour — S3K jumps on all three face
   buttons.

   **Owner ruling: B jumps when `CHEAT_DEBUG_FLY` is CLEAR; B does not jump when the
   bit is ARMED.** Default players get the correct three-button jump; anyone who has
   deliberately enabled the cheat accepts that B is the free-flight toggle instead.
   The gate is a conditional mask, not a static one, because the cheat bit is
   runtime-settable — a future cheat code can arm it on any frame, so anything
   precomputed at init would go stale. Both sites read the bit where they use it.

   **The exit path is what forced the exclusion.** The conflict is not on ENTERING
   free-flight — that returns early through `Player_DebugMove` and never reaches the
   jump code. It is on EXITING: `Player_DebugExit` clears `debug_flag` and falls
   straight through into normal physics, so the very same B press that left
   free-flight would be seen by the jump latch and buffer a jump on that tick.
   Excluding B from the mask exactly while the bit is armed is the whole mechanism;
   a mask that always included B would give every debug-fly exit a spurious jump.

   **Both consumers had to agree, so the mask stopped being duplicated.** The press
   latch (`Player_Main`) and the variable-jump-height HELD check
   (`PState_AirShared`) each carried their own file-local `BUTTON_JUMP_MASK`. If B
   latched a jump but did not sustain it, B jumps would come out with a clipped arc —
   a feel bug that would be miserable to trace. The pair now lives once, in
   `games/sonic4/player/player_common.emp` as `pub const BUTTON_JUMP_MASK`
   (`A|B|C`) and `pub const BUTTON_JUMP_MASK_NO_B` (`A|C`), and `player_air` imports
   both. Both sites run the identical shape: mask `A|B|C` and short-circuit,
   `moveq #CHEAT_DEBUG_FLY, d0` / `and.b Cheat_Flags, d0`, re-mask `A|C` only when
   armed. Cost lands on the cold side — the frames with no face-button press (in the
   latch) or no face button held (in the release-cap check) exit on the first `beq`
   and never probe the cheat byte, so the per-frame cost is unchanged from before.

   **Why the gate is `moveq`/`and` and not `btst`, at all four cheat sites.** A
   `btst #CHEAT_DEBUG_FLY_BIT, Cheat_Flags` shape was written first and assembled
   fine in the full build, but it is unlowerable in a standalone port-test compile:
   `games/sonic4/config/constants.emp` `pub const`s harvest into link EquSyms
   (`harvest_game_constants`), and `Cheat_Flags` is a link symbol too, so both
   operands are symbolic — `[lower.imm-link]`, "a link-time immediate combined with
   another symbolic operand is not yet supported". `andi.b #BUTTON_JUMP_MASK, d1` is
   unaffected because only one operand is symbolic. The `moveq`/`and` pair keeps one
   symbolic operand per instruction, costs the same 6 bytes and the same 16 cycles,
   and is the shape the `cheat-flag` parcel already used at `Player_Init` /
   `TestPlayer_Main`. Caught by `test_p2_player_states_port` under the strict suite,
   not by `build.sh`. **There is deliberately no `CHEAT_DEBUG_FLY_BIT` twin**: a bit
   number and a mask that can disagree is precisely the drift class this run has been
   paying for, and with the mask as the sole representation there is nothing to
   guard.

   **Not in scope: `test_player`.** `TestPlayer_Main` jumps on C only and uses A as
   its free-flight turbo modifier; it is scaffolding with its own input map, not the
   player, and item 3 below already asks the larger question about it.
3. **`test_player` as a unit.** The whole object is scaffolding that ships in release
   regardless of this ruling; whether it should is a separate question about the test
   object set, not about debug-fly.

### Correction: the `Debug_AssertObjLoop` entry that used to be here was WRONG

An earlier version of this entry claimed `Debug_AssertObjLoop`
(`engine/objects/core.emp:564`) shipped its bytes in release. **It does not.** Its body
is already `if DEBUG == 1`-wrapped, so it emits ZERO bytes in the plain shape — the
symbol and `RunObjects_Frozen` share address `$2BEE`, i.e. span 0, and `core_port`'s
`debug_shape_length_diverges` already pins plain = zero bytes. The source comment says
so explicitly.

The claim came from a subagent that read the symbol's ADDRESS out of `s4.lst` and
concluded bytes ship, and it was propagated into this document and into
`docs/superpowers/notes/2026-08-05-crash-report-ab.md` without being checked. **A
symbol in the listing is not emitted bytes** — zero-length labels appear at the address
of whatever follows them. The right measurement is the span to the next symbol, which
is what found the real leak above. Fourth instance of this repo paying for an unverified
claim; the first three were `[closed by <pending mechanism>]` markers.

---

## `VInt_Level` header comment states a stale execution order (found 2026-08-05)

`engine/system/vblank.emp:61-63` documents `VInt_Level` as running "Critical drain ->
VSRAM -> budget -> Important drain". The body (`vblank.emp:91-138`) seeds the frame
budget at the top and charges it **before** the Critical drain. `ENGINE_ARCHITECTURE.md`
§0.10 describes the body correctly, so the doc is right and the **code comment** is the
thing that drifted — the inverse of the usual direction, which is why the §0
reconciliation pass surfaced it.

One-line comment fix, zero byte change. Left out of the §0 doc parcel because that
parcel was deliberately doc-only (no `.emp` touched, so it needed no repin/refreeze).

---

## Owner rulings, 2026-08-05 (backlog reconciliation follow-up)

Four decisions taken after the reconciliation. Recorded here so they stop resurfacing as
open questions.

### Diagonal streaming budget — MARK AND REVISIT (not accepted, not fixed)

**Ruling (Volence):** neither accept the dip nor spend on it yet — mark it and revisit.

So this stays OPEN and is deliberately *not* closed with the on-file "accept the dip"
recommendation. The three shapes remain: (A) accept the dip, (B) cap the combined diagonal
step, (C) cut BgAnim bands during fast scroll. Revisit when there is a reason to — most
likely alongside art-streaming Phase 2, whose budget model touches the same frame window,
or when a level actually plays at sustained max diagonal. Do not re-ask it before then, and
do not silently take (A).

### `children` C1c — band inheritance: IMPLEMENT clear-then-set

**Ruling (Volence):** implement proper inheritance rather than ratifying the refusal.

The existing refusal is sound *for the current idiom* (`CHILD_INHERITED_FLAGS` composes with
`or.b`, and the priority band is a 3-bit VALUE, so `or`-ing 5 and 6 yields 7). The fix is
therefore not "add the band to the inherit mask" — it is a **clear-then-set** idiom: mask
the band bits out of the child's render flags, then OR the parent's band in. This is a
convention change affecting every child-creation site, so it lands as a single templated
change rather than nine hand-edits. **EXECUTED 2026-08-05** (`parcel/defect-batch-8`):
`set_priority_band` comptime template in sst.emp + CHILD_INHERITED_FLAGS gains the band.

### Object-test scene — GATE DEBUG-ONLY

**Ruling (Volence):** the whole scene stops shipping in release.

`GameState_ObjectTest_Init` and its test objects (TestPlayer, TestStatic, TestAnimated,
TestEnemy, TestSolid, TestParticle, TestEmitter, TestChildPart, TestStressEmitter,
TestChurnObj) are pushed unconditionally today (`native.rs` registry, no `if debug`) and are
**unreachable from the game entry point** (`games/sonic4/config/game.emp:23-24` →
`GameState_OJZScroll_Init`). By the `CODING_CONVENTIONS.md` §1.7 rule — a harness you drive
is equipment, and equipment does not ship — they belong in the debug shape only. Same
registry idiom as `CompressionSelfTest`. The OJZ level is unaffected: it spawns the real
Sonic player (`ojz_scroll_test.emp:134 jbsr Player_Init`), not `TestPlayer`.

**Correction worth keeping:** an earlier framing of this decision claimed `test_player` was
"the object driving the test scene". It is not. The yellow square in the OJZ level is
`Player_DebugMove` — the real player's debug-fly. `TestPlayer` is a separate object used
only by the object-test scene (`object_test_state.emp:88, :271`). The two were conflated.

### Debug-fly cheat code — DEFER to design #7

**Ruling (Volence):** defer until the screens/HUD design lands.

The runtime gate (`Cheat_Flags` bit 0, `CHEAT_DEBUG_FLY`) shipped with chain 43 and is
covered by the replay net, so the payload is ready and tested. What is missing is somewhere
to *enter* a code: classic codes live on a title or level-select screen, and screens are
design #7 (banked, unexecuted). Inventing an in-gameplay button sequence now would be
throwaway work replaced when #7 lands. Pick this up as part of #7.

---

## Ledgered by the 2026-08-05 defect batch (`parcel/defect-batch-8`)

### `vdp_stride80` declared context — DEFERRED, with the dead ends pinned

Defect NEW-1 (VInt_Lag trusting the unasserted "autoinc = $02 on exit" ambient) was closed
with the unconditional runtime re-assert (`move.w #$8F02, VDP_CTRL` at the Critical drain
head — 8 bytes, 20 cycles, lag frames only). The STRUCTURAL close — a declared context whose
release half restores `$8F02` — was evaluated and rejected as disproportionate. Pin the
reasons so the next session does not re-walk them:

- Contexts prove bracket PAIRING, not register VALUES. VDP control-port write-sequence
  tracking is an explicit spec exclusion (sigil contract-unification spec §3/§9, the S2-D7
  exclusion). Nothing forces a raw `#$8F80` write into a bracket — there is no inferred VDP
  net analogous to the Z80 `[bus.*]` tier.
- An IRQ is not a CFG edge: a correctly bracketed writer running UNMASKED in the main loop
  when VInt_Lag fires is the real residual failure mode, and `requires(...)` (proc-level,
  conjunctive) cannot spell "only under ints_off OR vblank" at bracket granularity.
- Full closure needs two sigil checker extensions (context-level any-of requires; an
  immediate-$8F-outside-bracket lint) — both emission-neutral, but two new checker semantics
  plus a byte-changing hot-loop adoption to protect one 8-byte invariant.

REVISIT only if a second stride-switching writer ever appears outside the current three
files (plane_buffer / bg / section — full 9-site inventory in the defect-batch scoping
notes). The runtime re-assert stays correct regardless.

### `Palette_Dirty` drop-retained analog — RECORDED, not fixed

The NEW-3 class (a Critical-queue drop retains a dirty flag; IRQ6 then ships a stale
snapshot against a mid-write buffer) exists in principle for `Palette_Dirty` + the palette
buffer: a drop-retained line bit + IRQ6 landing mid-palette-buffer-write ships a torn line.
Narrower than the sprite case (per-line bits, 32-byte lines, no length field to skew, and
palette writers are fade steps — not a per-frame emit loop), so it was left out of the
sprite fix deliberately. If palette corruption during a fade under heavy Critical-queue
pressure is ever reported, this is the mechanism; the fix shape is the same emit bracket.

---

## Ledgered by the 2026-08-08 art-streaming Phase 2 Task 2 review (`feat/art-streaming-p2`)

### `compression_selftest` engine-agnosticism smell — RECORDED, not fixed

The DEBUG boot equivalence walk (`engine/debug/compression_selftest.emp`) proves
`ZX0R_Decompress` byte-identical to `ZX0_Decompress` over every act-pool page. To reach the
pool it hardcodes the game-specific symbol `OJZ_Act1_Descriptor`, behind a
`HAS_ACT_ART_POOL` comptime define (sonic4 family = 1, demo = 0) so the block is discarded
in the game-agnostic demo build. It works and keeps demo green, but it plants a
`games.sonic4.*` reference inside a shared `engine.*` module — the exact engine/game-wall
crossing the restructure exists to prevent. It also forces the engine module's isolation
port test (`compression_selftest_port.rs`) to inject a game symbol as a cross-seam carrier.

**Cleaner shapes when revisited:** (a) bind the current act descriptor through the Game
contract (an engine-visible hook the game supplies), so the self-test walks "the game's act
pool" without naming a sonic4 symbol; or (b) move the act-pool equivalence walk into
`games/sonic4` test scaffolding, leaving `compression_selftest.emp` testing only the engine
golden vectors (fully game-agnostic). Either removes the `HAS_ACT_ART_POOL` define and the
port-test carrier injection. Low urgency — the current form is correct and cheaply
reversible.

### Equivalence walk does not assert `form == ZX0` — RESOLVED by Task 5

The self-test fed each act-pool page to both decoders assuming the page is a ZX0 (version
2) stream past the 4-byte wrapper. **FIXED in Task 5 (P2b format cutover, 2026-08-08):** the
`.eq_page` walk now strides the manifest v2 `PageManifest` records (stride 8), reads the
source from `pm_source` and length from `pm_tiles`, SKIPS `pm_tiles==0` pages, and
equivalence-tests ONLY `pm_form == ART_PAGE_FORM_ZX0` pages — a raw-direct page is skipped
(ZX0-vs-ZX0R equivalence is meaningless there). This was also the crash fix: the old
stride-4 longword walk dereferenced garbage once the table became stride-8 v2 records
(ADDRESS ERROR at `CompressionSelfTest.eq_page`).

## Ledgered by the 2026-08-08 art-streaming Phase 2 Task 3 review (`feat/art-streaming-p2`)

### Bookmark straddle → rare benign single lag frame — KNOWN RESIDUAL, corrected lemma

The sketch §2 lag-impossibility lemma ("the lag path can never bank") is OVER-STATED. The
VBlank hook runs BEFORE the Ready/dispatch split, so it banks the decode on WHICHEVER path
dispatches. Counterexample (reviewer-proven): after `VBlank_Ready := 1`, if the first VBlank
lands during the pre-decoder setup window — the ~150-cycle `PageIn_Resume` restore/push, or
the DEBUG scaffold's page scan — it correctly does NOT bank (PC outside `[ZX0R_Decompress,
.__end)`), runs `VInt_Level`, and clears `Ready`. The decode then runs to the NEXT VBlank
with `Ready = 0`, which dispatches `VInt_Lag` and banks the decode there. This is SAFE (the
main loop is parked in the decoder, so `Plane_Buffer` is already drained and `VInt_Lag`'s
skipped plane drain is a no-op; the banked context survives either path via the movem
round-trip), but it costs one benign lag frame at roughly per-resume probability. The true
invariant is "the bank is safe on whichever path dispatches," not "the lag path can never
bank." The `vblank.emp` hook comment now states the corrected form.

**Task-12 action — ✅ DONE (2026-08-09).** The ARCH §9.7 rewrite landed the CORRECTED lemma, NOT
the draft's "lag path can never bank" phrasing. The draft (invariant 3) was swept and its stale
"the lag path can never bookmark — a mid-decode VBlank always dispatches `VInt_Level`, structurally"
claim was replaced verbatim by "the bank is safe on whichever path dispatches" + the benign single
lag frame. Execution record won over the pre-execution draft, as flagged.

## Ledgered by the 2026-08-09 art-streaming Phase 2 Task 12 closeout (`feat/art-streaming-p2`)

### Sigil isolation-port systemic-inject — the `DMA_Enq_Bytes_Frame` class remains — SIGIL ASK, RECORDED
The Sigil isolation port tests lower ONE engine module standalone against an EMPTY symbol table, so
any cross-seam reference (an `engine.constants` immediate, or now a cross-module RAM word) must be
either kept module-local or injected as a port-test carrier. Two instances of this pattern are now
on the books and it is systemic, not one-off: (a) `bg_anim.emp` keeps a module-local
`BGANIM_MAX_BANDS` mirror with a drift comment because re-homing it to `engine.constants` breaks
`bg_anim_port`'s standalone link (item 30/F, reverted; `bg_anim.emp:40-47`); (b) the T2
`compression_selftest_port.rs` injects a game symbol (`OJZ_Act1_Descriptor`) as a cross-seam carrier
(T2 wall-smell entry above). The T8 dual-cap added `DMA_Enq_Bytes_Frame` (a RAM word charged from
`dma_queue.emp`'s shared enqueue path and reset in `vblank.emp`) — the SAME class of cross-module
reference that a `dma_queue`/`vblank` port test must carry. **Follow-through:** the real single-
authority fix is a comptime path from `ram.emp`/`constants.emp` into a CODE module's consts that
survives standalone lowering (does not exist today, per `bg_anim.emp:45-47`). Until it does, each new
cross-seam RAM/const reference costs a port-test carrier injection or a module-local mirror. This is
sigil-repo work (`/home/volence/sonic_hacks/sigil`), recorded here so the accumulating injections
are seen as one systemic item, not filed one at a time.

### Oracle MCP wedge on repeated long `press` — EMULATOR-SIDE, for the oracle backlog
During the T11 acceptance-matrix bonus sweep (after the matrix itself completed clean), the oracle
MCP wedged: **two consecutive `press` calls each timed out at 1800 s on fresh oracle instances**,
hanging the controller's confidence sweep (abandoned; the matrix evidence was already complete).
This is an emulator-side/MCP-arbiter fault, NOT an Aeon-engine issue — the ROM was fine and the
matrix passed. Pattern to watch: long-duration `press` on a freshly-launched instance can wedge the
arbiter; the workaround was to abandon and rely on the completed evidence. Recorded for the **oracle
backlog** (oracle-repo work, not Aeon). Consequence for Aeon: none remaining — the final oracle
spot-check passed and the T12 merge landed on master (`2f047e3`).

## Ledgered by the 2026-08-09 sound game-feel package 1 execution (`sound-pkg1`)

Package 1 (`plans/2026-07-03-sound-game-feel-moments.md`) EXECUTED: pause/unpause
(music + all scopes, freeze-in-place, pop-free $B4 mute + resume voice re-upload),
jingle push/pop (frozen mid-song resume under a fade-in), the song-finished/comm
status contract (`SND_STAT_SEQ_ACTIVE/COMM/JINGLE/FADE_BUSY`; natural song end now
drops `SND_SEQ_ACTIVE`), composed fade terminals (out+stop / out+pause), the R4
spread-bit fade-rate table (8 speeds from the command byte's rate nibble), the
TimerA-DMA refill guard (user-ruled), and the 68k API v2 wrappers/readers.
`zFadeToPrev`-style fade-to-previous is COVERED by the jingle push/pop model.

Open items this execution creates or leaves:

- **Game-side game-feel flows (spec §7 cookbook)** — act-clear sequencing,
  drowning panic tempo, 1-up jingle wiring, Start-menu pause-all: documented API
  flows consumed by game features (the screens/HUD package, design-week #7).
  Engine work is DONE; these are game-side callers. Owner: the screens/HUD
  package when it executes. Reference: the game-feel spec §7 + `sound_api.emp`'s
  transport/reader block.
- **Spec §6.4 DEBUG transport-exclusivity assert OMITTED (resident ceiling).**
  The both-slots-nonzero (`SND_REQ_MUSIC` + `SND_REQ_JINGLE` in one poll) DEBUG
  assert costs ~20 resident bytes; the debug blob ended 3 B under the `$18F0`
  ceiling. The 68k-side contract ("one transport op per frame") is documented at
  the wrappers. Revisit if a Z80 reclaim opens headroom.
- **Z80 resident headroom is nearly EXHAUSTED** — debug blob 6381/6384 after this
  package (plain 6255/6384). The next resident addition needs its own reclaim
  first (candidates: further init rolling, shared scan helpers). The R9 30 T-state
  bank is a TIME budget, untouched (banked for polyphonic PCM).
- **Fade default duration changed** (R4): the fastest rate is ±1 TL/frame → a
  full $7F fade is ~2.1 s (was ~1.07 s at the old STEP=2). All 8 authored speeds
  are slower-or-equal; if a sub-2s fade is ever needed the step magnitude (not
  the pattern) is the knob.

## Ledgered by the 2026-08-10 DAC drum-library-readiness package 3 execution (`sound-pkg3`)

- **`tools/test_import_sk_collision.py` regenerates committed collision bins
  IN-PLACE with bytes that differ from what is committed** (porter observation,
  reproduced across runs; the porter restored the committed bytes each time and
  committed nothing). Either the committed bake or the tool's default params
  drifted. Until reconciled, running the tools suite dirties the tree — a
  parallel-session hazard (auto-commit daemon could sweep the regenerated bins
  onto a branch). Owner: a small tools session — diff regenerated-vs-committed,
  decide which is truth, and make the test write to a temp path instead of the
  committed location.
- **Sigil table-fold vs placement divergence at unaligned bank-section base** —
  exposed by sound-pkg3's head growth (DacSampleTable 9→12 B/descriptor shifted the
  sound-bank tail parity): the placement chainer **8-aligns** the SFX block's
  section base, but seam-2's sound_layout fold (which bakes the absolute
  `SfxTable` pointer cells into `sfx_bank{,_debug}.bin` and the SfxBlobWinTab
  window pointers) packs contiguously WITHOUT that align — every pointer came out
  **-2** in the plain shape and SFX went totally silent (debug's base happened to
  stay ≡ 0 mod 8, so only plain broke, and no build gate fired). The quantum was
  pinned empirically: a mod-4-only pad still placed **-4** ($5BB0C fold vs $5BB10
  placed), and the old working bases $5BAE8/$5D558 are ≡ 0 mod 8 but ≢ 0 mod 16.
  Worked around by STRUCTURAL 8-alignment of the sfx_bank base via two
  comptime-sized pads inside the seam-2-lowered artifacts (so the fold and the
  chainer both count the bytes): the engine-table head is rounded to ≡ 0 mod 8 at
  its tail (`engine/sound/dac_sample_tab.emp` `DacHeadPad_*`, sized off the
  seeded DAC consts + the four fixed head sizes, walled in `soundbankhead.emp`
  incl. a head-total `% 8 == 0` tripwire), and the MT bank tail is rounded to
  ≡ 0 mod 8 (`games/sonic4/data/sound/mt_bank.emp` `_sfx_align_*`, sized off its
  own blob lengths, before SongTable so the pad lands in the body split-bin) —
  self-adjusting under head growth, song regen, and shape. Plus a link-time base
  wall in `games/sonic4/data/sound/sfx_bank_blob.emp`
  (`ensure((winptr(Sfx_33) & 7) == 0, …)` — placement-side only; the fold's base
  is not expressible repo-side).
  **Second finding, same session**: a source `align` CANNOT express this fix —
  seam-2 lowers these modules at baseline-0/vma positions that differ from final
  placement, so `align` computes the wrong pad count; its D2.29 link-time
  congruence assert catches it loudly ("padding was computed against the
  lowering-baseline address ... final address ..."), which is correct-and-loud
  but means `align` is unusable in any seam-2-lowered module whose placed base
  parity differs from its lowering baseline.
  **Needs a sigil-side fix**: either the fold must model the same alignment the
  chainer applies (and/or lower seam-2 modules at their true placed bases so
  `align` works), or a fold-vs-placement base mismatch must be a BUILD ERROR —
  never silent short pointers. The chainer's 8-quantum should also be stated
  somewhere authoritative instead of reverse-engineered. (Class risk: any OTHER
  seam-2 fold that bakes absolute addresses against a contiguous-pack model
  diverges the same way if its section gains chainer alignment.)

---

## Ledgered by the 2026-08-10 sound correctness-batch package 4 execution (`sound-pkg4`)

Package 4 (`plans/2026-07-03-sound-correctness-batch.md`) EXECUTED. Closed:
**D4** (PSG folds `sc_transpose` — the one live audible defect, byte-neutral),
**D1** (ModSet-on-noise refused in both producers, zero Z80 bytes),
**D6** (LoopPoint-in-repeat-span refused + a 4 B RepeatStart re-seed),
**D7** (DEBUG operand-0 trap, 0 release bytes, plus the missing SFX half of the
producer rule), **B3** (AM-enable bit lands on YM bit 7), **E5-runtime**
(RegDelta group 6 = `$90` SSG-EG, +1 B). Ride-along: **triage R1**, the DAC DRAIN
underrun guard (24 T / 6 B, zero net cycles). **B5 took the plan's own Step-2B
fallback** — see the costed finding on the B5 entry itself. Verification pass on
the plan's "already fixed" list: D2/D3/D5 confirmed done, F4 three-quarters done
and re-classified, F3 NOT closed (two thirds still unconfirmed).

Resident cost: plain 6157 -> 6164, debug 6283 -> 6294 of 6384 (headroom 101 ->
90 B), funded by the Task-0 item-25 reclaim. pytest 897 -> 912 passed / 2 skipped.

Open items this execution creates or leaves:

- **Blob length re-pin owed (controller).** Every package-4 build ran with
  `SIGIL_BLOB_LEN_DRIFT=warn`; `BLOB_LEN_PLAIN` / `BLOB_LEN_DEBUG` and the
  `Z80_SOUND_SIZE` mirrors still expect the pre-Task-0 6255/6381.
- **Oracle gates owed (controller, foreground).** (a) **D4** — force the
  spindash-rev SFX after several rev pings and confirm the PSG component's divisor
  writes now RISE with rev, as the FM component already did. (b) **R1** — if the
  underrun is reproducible (a long 68k DMA burst against a streaming sample),
  capture before/after: the ~72 Hz full-amplitude buzz should become a held level.
  (c) **Rendered A/B on BOTH the plain and debug shapes** — plain-shape SFX
  regressions have bitten this lane before, and D4 changes every PSG note-on.
  (d) Optional: the E5 group-6 SSG-EG showcase sweep.
- **`sfx_transcode._process_lines` is DEAD CODE.** Only `_process_lines_v2` is
  ever called (`_process_lines`'s single call site at its own `smpsJump` handling
  is a self-recursion). The two scans have already DIVERGED — v2 carries the
  `noise_form is not None` ModSet drop and v1 does not — which is exactly the
  hazard a dead twin creates. Package 4 did not delete it (out of scope) and
  closed the risk with a pack-time backstop instead. **Delete the v1 scan** in the
  next transcoder parcel; the divergence is evidence, not speculation.
- **`pack_sfx` does not validate events.** D7 surfaced this: `pack_sfx` calls
  `e.encode()` directly and never `e.validate(route)`, so EVERY `song_packer`
  range/route rule is silently inapplicable to SFX streams. Package 4 patched the
  two rules it owned (`_validate_sfx_repeat` count, `_validate_no_modset_on_noise`)
  but the general hole stands. **Audit which other `Event.validate` rules SFX
  streams need** and either route SFX through a validation pass or mirror the
  needed rules into the `_validate_*` backstops. Class risk: any future packer
  rule is assumed to cover both producers and does not.
- **`Fm_TransposeClampChrom` exists partly to route around a sigil limitation.**
  seam-1 resolves each resident module's constants from a per-module name list
  baked into the harness (`seam1.rs` `psg_const_names` / `fm_const_names` / …), so
  a `.emp` module cannot reference a `sound_constants.emp` constant that is not on
  ITS list, even though every constant is `pub` and evaluated. The D4 fix turned
  out better for it (byte-neutral, one shared clamp entry), but the constraint is
  undocumented and will surprise the next author. **Either document the per-module
  const seam in the engine/game contract reference, or make the lists derive from
  the modules' actual references.**

---

## Ledgered by the 2026-08-10 `characters.emp` module registration (`feat/character-dispatch`)

### Adding a module should not require editing the toolchain — SIGIL ASK, RECORDED (owner-raised)

**Raised by Volence 2026-08-10**, on discovering that moving the character roster into a new
`.emp` module required a commit to the *sigil* repo. The observation, in his framing: adding a
character "should really be as simple as making the new file and calling it where needed in the
actual game code."

**What it costs today.** Adding one module is three edits in two repos:

| edit | repo | correct? |
|---|---|---|
| the `.emp` file itself | game | yes |
| a row in `games/<game>/map.toml` `order` | game | **no** — ceremony |
| a `ModuleSpec` in `crates/sigil-harness/src/native.rs` `registry()` | **assembler** | **no** — wrong repo |

Pins and port tests are **not** in this path — verified this session: `characters` registered with
`DUMMY_REGION` and both shapes built green, because every shipped profile is `SizeSource::Frozen`
and `ModuleSpec.region` is read only from `emp_map_toml`, reachable only from `PinnedBaked`. So the
friction is the registry + the order list, not the pin table.

For a **brand-new game** it is worse: three *sigil* edits (a `GameProfile` literal, a registry
function, and a frozen size table under `crates/sigil-harness/golden/offcanonical_sizes/`). A third
party cannot build their own game on Aeon without committing to the assembler. That is backwards
and it undercuts the engine/game wall the 2026-07-07 split exists to enforce.

**The principle to design to: declare a placement REQUIREMENT, never a placement POSITION.**

Auditing `map.toml`'s ~60-entry `order`, the genuine requirements are about eight facts — object
code bank at `$10000`; the hard-org'd sound banks at `$8000`/`$58000` (the Z80 holds pointers in, so
they never pack); DAC banks at `$48000`/`$50000`; `error_handler` must be the final byte-emitting
section (MDDBG blob-end contract, `check_error_handler_is_last`); the OJZ act island runs stay
contiguous; `Vectors` at 0 and the header at `$100`. Everything else is arbitrary-but-deterministic.
Nothing breaks if `tails` lands before `sonic`; it only has to land *somewhere in the object bank*,
reproducibly.

**Sketch of the end state** — the file declares its own bucket:

```
module games.sonic4.tails in tails @ object_bank
```

sigil auto-places within the bucket in a stable order (sort by module id — stable across machines,
unlike a filesystem walk). `map.toml` shrinks to the memory map: regions, anchors, and the few hard
ordering contracts. You edit it when the *architecture* changes, not when content is added. Adding
a character becomes: write the `.emp`, add the roster row, build.

**Two dependencies that must land with it:**

1. **Inclusion must follow from use.** It cannot today, and this is the hidden reason the registry
   exists at all: cross-module calls resolve as **bare link refs**, so `player_common` calling
   `Player_LoadArt` creates no module-graph edge to `characters`. With no dependency graph to walk,
   `synthetic_entry_src` fabricates reachability by `use`-ing every registry row. Two ways out —
   make bare cross-module refs create real edges (proper dead-code elimination, larger job), or
   scope by directory (`engine/` + `games/<this game>/` are the link set), which is already the
   de-facto rule, just expressed in Rust (`demo_registry`'s `module_id.starts_with("engine.")`).
2. **Shape gating must move into the file.** Debug-only modules are excluded in Rust today, and
   `CODING_CONVENTIONS.md` §"Whole-file gating" is explicit that this is a workaround, not a
   preference: "a module-level comptime `if` wrapping items is not expressible in `.emp`, so the
   file is the gated unit and the exclusion happens in the build registry." Fix the expressiveness
   (`module … requires DEBUG`) and the last reason to open the Rust disappears.

**Known costs, to be priced in the spec, not discovered later:**

- Auto-placement can separate two hot mutually-calling modules far enough to widen branches. `jbsr`
  handles it correctly but spends bytes and cycles. Bucket granularity bounds it; a `near:` hint
  covers the rare case that matters.
- The frozen size tables are a *this-repo* byte-exactness gate, not something a third-party game
  wants. They should degrade gracefully: no frozen table means pure packed layout from the declared
  buckets, and freezing becomes opt-in. Today they are mandatory because sizes are sourced from them.
- One goldens refreeze when the placement algorithm lands. Not per content change — that is already
  true today.

**Treat as ONE design, not three.** The registry, the `order` list, and the frozen size tables are
the same mistake wearing three hats: the toolchain storing positions that should be derived from
declared requirements. K5 already did half of it (the map took `order` authority from the frozen
table, which was explicitly demoted to a "measurement cache"); this is the other half of that
migration, which was never finished.

**Status: NOT STARTED.** Novel, cross-repo, hard to reverse — wants an explicit owner go-ahead and a
written spec before any code. Parked 2026-08-10 at Volence's direction to keep C2/C4 moving.

---

## Ledgered by the 2026-08-10 per-slot player-state split (`feat/character-dispatch`)

### Hoist `Player_Quadrant` out of the sensor stack into a parameter — RECORDED, not fixed

**What:** `Player_SensorFloor` / `Player_SensorCeiling` / `Player_SensorSurface`
(`games/sonic4/player/player_sensors.emp`) read the probe quadrant out of ambient state rather than
taking it as an argument. Before C1 that was a global (`Player_Quadrant`); after C1 it is
`PBLK_QUADRANT(a4)`, the calling slot's PlayerBlock. Either way the dependency is **hidden**: the
wrapper's signature says `a0 = player SST` and nothing in the call expression says the caller must
also have established a4. The fix is to pass the quadrant explicitly (a register argument, or the
block pointer as a declared param) so the contract is on the signature where the compiler and the
reader can both see it.

**Why it is worth doing, beyond tidiness — the latent coupling it closes.** `TestPlayer`
(`games/sonic4/objects/test_player.emp`, DEBUG shape only) borrows `Player_SensorFloor` for its
floor probe. It is not a player, has its own overlay (`TPlayerV`), and wants plain quadrant-0
downward probing — but it has no way to *say* so. Pre-C1 it silently inherited whatever the real
player last wrote to the global, and got away with it only because the object-test scene never runs
the real player, so the boot-zero global happened to mean "quadrant 0". Had the two ever run in the
same scene, TestPlayer's floor probe would have rotated with the real player's terrain angle and
nobody would have suspected the sensor call. With an explicit parameter, TestPlayer states
quadrant 0 honestly and the coupling cannot exist.

**Why it was deferred.** The hoist changes the register contract of three procs that every player
frame runs through, at ~10 call sites in the hot path (`player_ground` ×3, `player_air` ×4,
`player_spindash` ×1, `test_player` ×1, plus the `Player_SensorSurface` fall-through). C1 Task 4
gates this refactor on the **real player being byte-identical under a recorded-input replay**, and a
contract change across the shared sensor stack underneath that gate would make a byte diff
impossible to attribute. Right idea, wrong moment — owner ruling, 2026-08-10.

**What was done instead (option 1 of the two considered):** `TestPlayer_Main` loads slot 0's block
into a4 before its `Player_SensorFloor` call, and says why at the `lea`. That is coherent rather
than a patch — `object_test_state.emp` installs TestPlayer in the `Player_1` slot, so slot 0's block
genuinely is its block. The alternative considered and **rejected** was having TestPlayer call
`Collision_ProbeDown` directly (as `Player_AtLedgeEdge` does): that is *not* behavior-preserving,
because `Player_SensorSurface` runs an **A/B sensor pair** at x±x_rad and keeps the closer hit,
while the bare core is a single centre point — collapsing a 32px-wide box's two foot probes to one
would change how it behaves straddling a ledge edge.

**Pick this up when:** Task 4's replay gate has passed and the byte-identity requirement is
discharged. It closes the last hidden dependency in the player sensor path — post-C1 the quadrant is
not a global any more, it is an *ambient register parameter*, which is why the compiler still cannot
see it. **Do not size this from this paragraph** — it is mechanical but it is not small; the
`MEASURED SCOPE` block immediately below is the estimate, and it concludes ~19 procs plus the
dispatch type, i.e. its own parcel with its own gate.

**MEASURED SCOPE (attempted and reverted 2026-08-10 — read this before estimating).** The obvious
first move is to declare the dependency on the four procs that actually read the quadrant
(`Player_SensorFloor`/`Ceiling`/`Surface` + `Player_SnapToSurface`), the way
`Player_RefreshPhysics (a2: *u8)` does. That was tried. It does **not** build, and the reason is
structural, not cosmetic: `[call.input-undefined]` fires **13 times**. a4 reaches the state machine
*implicitly* — `Player_Main` establishes it, then dispatches through
`jsr (a1,d1.w) as PlayerState`, and `type PlayerState` declares `clobbers(d0-d7, a1-a4)`. The
closure therefore treats a4 as destroyed at the dispatch boundary and cannot carry the definition
into any handler. The 13 firings:

```
Air_CeilingBump, Air_LandState, PState_AirShared,
PState_Ground, PState_Roll (x2)          -> Player_SensorCeiling
Air_FloorLandBanded, Air_FloorLandFlat,
Ground_PostMove, PState_Spindash         -> Player_SensorFloor
Air_TouchFloor, Ground_PostMove,
PState_Spindash                          -> Player_SnapToSurface
```

So the real change is not four signatures — it is an `a4` in-param on roughly **nineteen** procs
spanning `player_ground` / `player_air` / `player_spindash` **plus the `PlayerState` dispatch type
itself**, whose clobber list `Player_Main` brackets. That is the whole player frame's register
contract, which is exactly why it must not ride along underneath the Task 4 byte-identity gate: a
change that broad makes any byte diff impossible to attribute. Budget it as its own parcel with its
own gate. The partial form is not a valid halfway house — it does not compile, so there is no
smaller increment to land first.

---

## Ledgered by the 2026-08-10 Tails palette re-index (`feat/character-dispatch`)

### Knuckles is NOT solvable by index permutation — he needs a real palette swap — RECORDED, not fixed

**Read this before designing Knuckles' art path.** Tails' wrong colours were fixed by re-indexing
his S3K art into our CRAM line 0 ordering at build time
(`games/sonic4/data/characters_staging/gen_characters.py`, `remap_art_indices`). **That fix does not
generalise to Knuckles, and reaching for it will silently corrupt his colours.**

**The measurement.** Our player line is `art/palettes/SonicAndTails.bin`; S3K's is
`skdisasm/General/Sprites/Sonic/Palettes/SonicAndTails.bin` line 0. The two hold the *same colour
set in a different order* — 15 of 16 S3K indices match one of ours exactly. The exception is S3K
index **5 = `$0080`** (dark green), which our line does not carry at any index.

| art | S3K index-5 pixels | permutation lossless? |
|---|---|---|
| Tails body (`Tails.bin`) | **0** | yes — shipped |
| Tails appendage (`Tails tails.bin`) | **0** | yes — shipped |
| Knuckles (`Knuckles.bin`, contiguous `_opt`) | **3,450** | **no** |

3,450 pixels have nowhere to go. Any permutation either drops them onto a wrong colour or needs a
colour our line does not have — so the whole approach is off the table for him, whatever ordering is
chosen. This is not a tuning problem; it is a set-membership one.

**What Knuckles actually needs.** A genuine palette swap: S3K itself swaps `Pal_Knuckles` into
CRAM line 0 when Knuckles is the active character. Both his lines are already staged —
`games/sonic4/data/characters_staging/palettes/knuckles_main.bin` (gameplay) and
`knuckles_ssz_end.bin` (ending) — so the asset side is done; the missing piece is the runtime
decision about **who owns CRAM line 0** and when it is rewritten.

**The consequence that must be designed for, not discovered.** Line 0 is a *shared* resource. Today
it holds the Sonic+Tails colours and both characters render off it simultaneously, which is exactly
what a follower / 2P mode will need. Swapping `Pal_Knuckles` in makes line 0 Knuckles-only: **Sonic
and Knuckles cannot be on screen together on one line.** So the Knuckles design has to answer one of:
- **swap on character select** (simplest; forecloses Sonic-and-Knuckles co-presence), or
- **give Knuckles a second CRAM line** (costs a line the level art currently uses — measured: the
  OJZ act draws its FG on lines 2/3 and its Plane B on lines 2/3, with line 1 the OJZ page-0 line, so
  a fourth character line means taking one back from the level), or
- **re-author Knuckles' art** against a line that unions with Sonic's (an art decision, not an
  engineering one — it changes how he looks).

Pick before writing code; all three are cheap up front and expensive to retrofit.

**How to re-run the measurement.** The generator prints the derived permutation and per-set index
histograms on every run (`./gen_characters.py` from `games/sonic4/data/characters_staging/`), and
hard-asserts that no art it re-indexes uses an unmappable index. It deliberately does **not**
re-index Knuckles — see the comment at his `process_set` call.

---

## Ledgered by the 2026-08-11 Tails appendage object (`feat/character-dispatch`)

### ✅ RESOLVED 2026-08-11 — The appendage's angle-banked roll frames stay at bank 0 — BLOCKED on an engine arctan

**RESOLVED 2026-08-11 (`feat/character-dispatch`).** `GetArcTan` + `ArcTan_Table` shipped in
`engine/system/math.emp` (a faithful port of S3K `s3.asm:3174`, `preserves(d3-d4)`), and
`TailsAppendage_Main` now banks `mapping_frame` and re-derives the flip pair between the
`AnimateSprite` call and the DPLC. The four banks were confirmed present and distinct in the
converted data before the code was written — mapping frames 5-8 / 9-$C / $D-$10 / $11-$14, all 16
DPLC frames distinct, and the VDP size code changes $09 -> $06 between the horizontal and vertical
pairs, so they are genuinely different orientations and not a duplicated cycle.

**TWO CORRECTIONS TO THE ORIGINAL TEXT BELOW — it was wrong on the mechanism, and the error was
load-bearing enough to send a reader down a dead end:**

1. **"S3K's `GetArcTan` is a `$100`-byte table lookup" is FALSE.** It is a **257-entry ratio
   table plus TWO `divu.w`s** (`s3.asm:3193` and `:3202`). `ArcTanTable` is not indexed by x and
   y — it is indexed by the *quotient* `floor(min·256/max)`, so the table converts a ratio to an
   angle and the divide is what produces the ratio. A table lookup therefore does NOT make the
   routine division-free. The blob is 258 bytes: 257 entries (the index is an inclusive quotient —
   equal magnitudes divide to exactly `$100`) plus one even-pad byte.
2. **The rejection of the octant approximation was RIGHT, and now has a number behind it.** The
   ledger rejected a `tan(22.5°) ≈ 7/16` threshold as "not S3K's rounding". Correct:
   `tan(22.5°)·256 = 106.04`, but the table's own crossings are at **q = 103** (entry 15 -> 16) and
   **q = 110** (16 -> 17). A trig-derived threshold of 106 sits between them and disagrees with S3K
   on real inputs.

**A PROVEN-EXACT SHORTCUT EXISTS AND WAS DELIBERATELY NOT TAKEN — do not "discover" it again
without reading this.** The appendage keeps only bits 5-7 of the biased angle (`(a>>3)&$C` is bits
5-6, and the `bpl` flip test is bit 7), i.e. a 45°-sector classifier with a 22.5° offset. Because
`ArcTanTable` is monotonic, each sector boundary is exactly a threshold on the quotient, and
`floor(min·256/max) >= k` is exactly `min·256 >= k·max` — a multiply, not a divide. Deriving the
two `k` from the TABLE rather than from trigonometry makes the result bit-identical by
construction. This was verified, not assumed: **3.77M inputs (all of `|x|,|y| <= 600`, 600K random
full-int16 pairs, every quotient 0-256 at 14 scales, and the exact crossing rows ±1 at ~3000
scales) produced ZERO disagreements** with the full S3K pipeline, filling all 32 classifier
entries. The both-zero case does *not* fold in (it collides with the near-45° key and needs its own
test, exactly as S3K's `GetArcTan_Zero` does).

It was rejected on **measured cost**, not correctness. From the 68000 manual, over the code each
form actually emits: faithful `GetArcTan` + transform = **498 cycles**; the classifier =
**327** multiply-free, **291** with `mulu.w #k`. That is 1.5x, not the ~3x a bare `divu`-vs-`mulu`
comparison suggests, because the classifier must reconstruct by hand all the sign and octant
bookkeeping the fold does implicitly — a saving of **171-207 cycles, ~0.13-0.16% of one NTSC
frame**, on a path that runs once per frame and only while Tails is rolling. Against that it costs
two magic constants that encode the table's ROUNDING (silently wrong if the table is ever
regenerated), a 32-entry classifier table of its own, and it still needs a `mulu` exception unless
you pay 88 cycles for a shift/add chain — so it does not escape the convention question either.
The full derivation, the 32-entry table, and the verifier are recoverable from this entry's
description if the tradeoff is ever re-opened.

**Original entry, preserved:**

`games/sonic4/objects/tails_appendage.emp` ships S3K's tail behaviour with one frame-selection
detail missing, and it is missing because a primitive does not exist yet — not because it was
skipped.

**What S3K does.** When Tails is in ball form his tails render from one of FOUR angle-banked mapping
banks (`AniTails_Tail03`/`04`/`05`/`06` — the same 4-frame cycle drawn at four orientations). The
selection is `sonic3k.asm:29556` (`loc_15A3C`): take the PARENT's `x_vel`/`y_vel`, run them through
`GetArcTan`, mirror the result on the facing bit (`not.b d0` facing right, `+$80` facing left), bias
by `+$10`, then `lsr.b #3` / `andi.b #$C` to get 0/4/8/$C and ADD that to `mapping_frame` after the
script step. The same angle also drives a two-bit render_flags flip.

**What we ship.** `Ani_TailsAppendage.Roll` carries bank 0 (tails_anims.emp deviation 3 says so
explicitly and assigns the offset to the appendage object), and the object does not add anything, so
a rolling Tails' tails spin at the horizontal orientation regardless of travel direction.

**The blocking dependency.** `engine/system/math.emp` is sine/cosine only — there is no arctan
anywhere in the engine (`GetSineCosine` + `Sine_Table` are the whole module). S3K's `GetArcTan` is a
$100-byte table lookup. An APPROXIMATION is available (classify the octant from `|dx|` vs `|dy|`
against a `tan(22.5°) ≈ 7/16` threshold, which is all `>>3 & $C` actually extracts) but it is NOT
S3K's rounding, so it would ship a visible-frame difference against the reference we are measuring
against, and it cannot be A/B'd against S3K without the real table.

**What closing it looks like.** Add `GetArcTan` (table + lookup) to `engine/system/math.emp` as its
own parcel — it is a general primitive several systems will want (projectile aiming, slope-facing
objects, the classic `CalcAngle` the air-state quadrant comment already name-checks) — then the
appendage change is ~10 instructions in `TailsAppendage_Main` between the `AnimateSprite` call and
the DPLC: bank the mapping_frame and re-derive the flip pair. The flight ascend/descend hold, the
OTHER thing tails_anims.emp assigned to this object, is already shipped (DUR_DYNAMIC + the parent's
`y_vel` sign).

### The `mulu`/`divu` convention text and the shipped code disagree — needs a ruling

`CODING_CONVENTIONS.md:247` states the rule absolutely:

> **Rule:** No `mulu`/`muls`/`divu`/`divs` in any code that runs per-frame. Use shifts, adds, or
> lookup tables. The ONLY exception is code that runs once (level load, init).

Two shipped sites are per-frame divides, and neither is "code that runs once":

| Site | Instruction | Why it is there |
|---|---|---|
| `engine/level/parallax.emp:548` | `divs.w d4, d2` | ramp step = `(target − current) / frames_remaining`, so a band transition converges exactly on its last frame. Runs every frame a transition is active. |
| `engine/system/math.emp` `GetArcTan` | `divu.w` ×2 | the arctan table is indexed by the RATIO, so the divide is what produces the index. Runs once per frame while Tails is rolling. |

Both carry a block comment proving the divisor is never zero and the quotient cannot overflow, so
the *practice* looks like **"not casually, and prove the invariants at the site"** rather than the
blanket prohibition the text states. That is a real gap between the law and the code, and the two
are not reconcilable by reading.

**This is a decision for the user, and is deliberately NOT resolved here** — amending
`CODING_CONVENTIONS.md` as a side effect of a feature parcel is exactly the kind of quiet
law-change that should not happen. The options are:

1. **Amend the text** to match practice: divides are permitted where an exact result requires one,
   provided the site documents divisor-non-zero and no-overflow. Both sites already comply.
2. **Keep the text absolute** and mark these two as named, listed exceptions (the text would need
   an exceptions register, since "the ONLY exception is code that runs once" currently excludes
   them).
3. **Remove the divides.** Costed for `GetArcTan` in the entry above and rejected: the divide-free
   form is provably exact but buys only ~0.13% of a frame while adding two rounding-derived magic
   constants — and it needs a `mulu`, which the same rule forbids, so it does not even resolve the
   discrepancy. Not costed for `parallax.emp`.

Note that option 3 does not generally escape the rule: for both sites the divide-free alternative
is a *multiply*, which sits under the same sentence.


### VRAM linker T1 — the packer in sigil's chainer (spec §6)
**Blocked by:** nothing technical; queued behind the T1 plan being written.
**What:** the six sigil asks from `docs/superpowers/specs/2026-08-11-vram-linker-design.md` §6: S-1 vram.toml parser in the harness, S-2 the solver (FFD + lifetime stub + exact fallback, with the fixpoint acceptance test: given the pinned map, reproduce it), S-3 define emission — VRAM names join `emp_defines`, replacing the hand ring-placeholder values across the native.rs profiles (MUST land value-neutral, byte-identical goldens as its gate), S-4 the no-raw-literal lint, S-5 map/budget/diff artifacts + refreeze integration, S-6 (T2) per-act solve outputs.
**Also ledgered with it:** the art_tile hash normalization rider (spec §12 — one re-stamp, unpins the character window for T1 floating); the possible vram.toml/map.toml merge when the user's broader TOML review happens (their stated intent, 2026-08-11).
**When ready:** after the T0 execution note and the T1 plan (task queued).

### Dust plan Task 2 — SUPERSEDED by the VRAM registry carve
`docs/superpowers/plans/2026-08-11-dust-effect.md` Task 2 (the hand
POOL_TILE_CEILING carve) is superseded by the registry
(`games/sonic4/vram.toml`, commit c51a4ff9): VRAM_DUST_PUFF/VRAM_DUST_SPINDASH
now exist from the generated block. Dust Tasks 3-6 resume unchanged otherwise.


### Dust riders (plan Task 6, 2026-08-12)
1. **Knuckles dust art variant** — a second, RAW (unpermuted) 2816 B blob
   selected at Player_RefreshPhysics alongside his palette swap, which must
   also re-DMA the resident puff block (it is palette-specific). Measured: no
   single variant serves both CRAM lines — the three colours the art needs sit
   at disjoint indices, and the lines agree only at 0/10/11, none used by dust
   (dust spec §5.4).
2. **Water splash / water-run dust** — a design task gated on a water system
   existing at all (dust spec §1; no ST_UNDERWATER implementation today).
3. **TF4 round-robin misattribution** — docs/ENGINE_ARCHITECTURE.md (~1118,
   1165, 1955, §3.5) and docs/research/children-particles.md:166 credit
   Thunder Force IV with "round-robin sprite flicker" at $F29A. Verified from
   its disassembly: that address is a global Y-drift accumulator; TF4 has no
   such mechanism, and the doc's claimed TF4 RAM pools are palette/tilemap
   staging. Our per-frame intra-band link-order cycling (sprites.emp:242) is
   real — only the provenance is wrong. Correct in one docs pass.
4. **particle_anims.emp:17 duration comment** — says "duration 4 frames/frame";
   under animate.emp's N+1 rule a duration byte of 4 holds for 5 frames.
5. **Hoist the shared S3K sprite conversion** out of gen_characters.py /
   gen_dust.py into tools/s3k_sprites.py — deferred while gen_characters.py is
   load-bearing on two branches (dust plan, File Structure note).


## Ledgered by the 2026-08-12 Knuckles C4 task 9 + research (`feat/knuckles`)

### The ability collision box does not compose with the enter hooks — BLOCKING Task 10, not yet fixed
Glide, slide and climb all run at 10x10 radii (S3K `sonic3k.asm:32566-32569`) — a
THIRD collision box beside standing and ball, and our box machinery only knows
two. `PHook_EnsureStanding` (`player_common.emp:1014`) keys on `cd_roll_wh`, so
coming from a 21x21 ability box it takes `.keep` and **never restores the
standing box**; `PHook_EnsureBall` (`:1027`) applies the full stand-to-ball
`curl_y_shift` that S3K's wall jump-off does not have (`:31430-31431`). So a
glide or climb detach would leave Knuckles with a 21x21 hitbox for the rest of
the act, and every wall jump-off would drop him 5 px.

Fix (designed, not built): a third registered box `cd_ability_wh` in
`CharacterDef` at `$24`, a `set_ability_size` splice, a `PHook_EnsureAbility`,
and generalising EnsureStanding's guard to "am I not the standing box" with the
y shift derived from the CURRENT height. That closed form is literally S3K's
`y_radius - default_y_radius` and reproduces today's numbers exactly (ball 5,
ability 9 — and 9 is what S3K's slide get-up applies). Sonic and Tails come out
behaviour-identical; ROM changes, RAM does not.
→ §0 of `docs/superpowers/2026-08-12-knuckles-c4-research.md`

### The plan's Task 10/11 text has ~12 substantive errors — CORRECTED IN PLACE
The plan now carries a banner at each task pointing at the research. The ones
that change what gets built: the slide dust cadence is 4, not 8 (8 is the SFX
cadence); the fall-from-glide needs its own PSTATE rather than being a
sub-state; glide needs its OWN terrain pass because `Air_Collide` tail-jumps
into `Player_SetState`; there are three climb detach conditions, not two.

### Task 11 Step 1 is DONE, and the answer is "no sensor work needed"
`player_sensors.emp` already takes fully arbitrary probe points, so the
S3K-to-ours wall-detection mapping the plan calls "the hard part" needs no
extension. The full equivalence table is banked. One genuine gap remains
recorded: the glide wall-catch needs "both sensors flush" and
`Player_SensorPair` returns the NEARER hit — answer is to call the probe cores
twice, the idiom `Player_AtLedgeEdge` already documents.
→ §2 of the research doc

### Glide/slide/climb SFX do not exist in our bank — SCOPE DECISION OWED
S3K uses `sfx_GlideLand $4C`, `sfx_GroundSlide $7E`, `sfx_Grab $4A`. Our SFX
bank has none of them, so Task 10/11 either opens a sound-side parcel (bank
entry + priority-ladder row each) or ships the abilities silent. The plan is
silent about being silent. Same class as, and can ride with, the flight-SFX
range work if that is still open.

### S3K's `Disable_wall_grab` has no counterpart — object-side hook, RECORDED
Two S3K gates (`:30777-30778`, `:31039-31040`) let specific walls refuse a
grab. We have no equivalent, so every wall will be climbable. Register the
object-side hook when the climb lands rather than losing the capability.

### `knux_latch_x` will need the floating-origin shift-list — NOTE AT THE FIELD
The climb latches a WORLD X to detect being pushed off the wall. When the
floating-origin rebase lands, that cell must join the rebase shift-list or every
rebase mid-climb trips the drift guard and drops Knuckles off the wall. Same
class as the `Player_Pos_Ring` note in plan Task 8. Put the note at the field,
not only here.

### `PlayerV` header comment says "22 of 30" and is stale — it is 20 of 30
`player_common.emp:78`. (Plan Task 12 Step 1 already lists a DIFFERENT stale
figure, "18 of 34", whose text no longer exists at the cited line.) Fix in
whichever task gets there first.

### The `.emp` language cannot express the ability-scratch UNION — SIGIL ASK, RECORDED
`player_common.emp:104-110` states the design intent that Knuckles' ability
bytes re-use Tails' `fly_fuel`/`fly_thrust`, since exactly one character is
resident per slot. The language has no way to say it: every
`vars X: Sst.sst_custom` overlay in the tree starts at `$30`, none uses
offset-anchored placement, and both characters share the single `PlayerV`
overlay. Costs 2 bytes of a 30-byte window today (26 of 30 after climb), so it
is not urgent — but the comment should be amended to read as a BUDGET principle
rather than a byte-sharing one until the language grows an offset-anchored view.

### The ROM-tail character-art exile has now happened TWICE — relayout pressure
Knuckles' 0x226C8 of art took the same exile Tails' 132 KB took, for the same
reason (Art_Sonic ends at $4277E, the `dac_banks` org anchor is at $48000). The
plain ROM is 676 KB against 414 KB before Tails, and each exile costs a
frozen-table hand ruling in five shapes. The parked "banks late, data unbounded"
relayout retires the whole friction class; a fourth character, or any further
character-scale art, pays the tax again.

### Palette variant DEBUG guard — CONSIDERED AND BANKED, not an oversight (2026-08-13)
`fix/palette-variant-derive` gated the variant derive on `PAL_ACT_VARIANT_STALE`,
which makes "the palette engine is the sole runtime writer of `Palette_Buffer`
lines 1-3" a CORRECTNESS dependency rather than a tidiness one: an outside
runtime writer of those lines would leave `Pal_Variant_Stage` stale with nothing
to notice. A DEBUG-only guard was designed (checksum the `v_lines` bytes at
derive time, re-check on a skipped frame) and deliberately NOT built.

The audit that made it optional — every writer of `Palette_Buffer` in the tree:

| Writer | Lines | When |
|---|---|---|
| `player_common.emp:517` character resolve | **line 0** | **every frame** |
| `ojz_scroll_test.emp:112` BGND | line 0 | init |
| `ojz_scroll_test.emp:119` OJZ_Palette | **lines 1-3** | init, before first compose |
| `ojz_scroll_test.emp:390` backdrop tint | line 0 | runtime |
| `object_test_state` / `demo_state` | line 0 | init |
| `palette.emp` compose layers | lines 1-3 | per frame |

So today the invariant holds: the only non-engine writers of lines 1-3 are
init-time (and covered anyway, since binding sets the stale bit), and every
runtime outside writer touches line 0, which no variant can cover (`v_lines` is
bits 1-3 by construction).

**If the guard is ever built, it must cover ONLY the `v_lines` lines.** A
whole-buffer checksum fires on every character resolve — a guard that cries wolf
each frame gets deleted, and takes the real invariant with it. Cost if built: one
debug-only RAM cell (moves debug pins) plus ~400 cyc/frame in the debug shape.

### Palette variant LUT (design lever C) — deferred until real content exists
Lever A took the STATIC-frame derive to zero, but a frame whose source actually
moved still pays the full **19332 cyc** (48 entries at ~403, measured) — 3 lines
x 16 entries, each doing three variable-shift + branch-clamped channel rebuilds
with six loop-invariant descriptor bytes re-read from memory per entry.

The fix is not another gate, it is the arithmetic: each channel is 3 bits, so
build three 8-entry word tables at BIND time, pre-shifted into channel position
(`clamp((c >> shift) + bias, 0, 7) << {1,5,9}`). 48 bytes per slot. The inner
loop becomes three extract-and-index sequences plus two `or`s — est. 3-4x. This
is the house idiom (CODING_CONVENTIONS: tables over runtime arithmetic), and
`variant_word(c, v)` already exists as a `comptime fn` computing exactly this
mapping, so the builder can be gated at build time against its `ensure` vectors
rather than tested by hand.

Deferred because the only scene that exercises it has no continuous cycling, so
any measurement today would be on a garish test fixture rather than real content
— the same caveat that already qualifies the dense-tier reserved-register ruling.
Revisit when a section runs cycling or a fade continuously.
