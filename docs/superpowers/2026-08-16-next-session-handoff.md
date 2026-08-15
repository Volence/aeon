# NEXT-SESSION WORK ORDER — 2026-08-16

Supersedes `2026-08-16-overnight-work-order.md` for queue purposes. That file's standing rules
(how to use a Fable adviser, what to decide vs STOP on, the byte-moving ritual) still apply —
read its top third; its queue items 1-5 are all DONE.

---

## State at handoff

**Both repos on `master`, green, pushed, nothing in flight.**

- aeon `2587e986` — Merge parcel/offscreen-ship-setreg: the ship re-issues the whole fire
- sigil `1d89baf9` — refreeze for aeon's set_reg replay (chain 126)
- Verified pair. Suite **3721 / 0** across 329 test-result lines · contract closure **0 firings**
- Four shapes boot and render: s4, s4.debug, demo, demo.debug

```bash
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
```

ROM CRCs: s4 `5acff780` · s4.debug `34078a94` · demo `8bff76d8` · demo.debug `3ccb680c`

---

## What shipped, and the one thing to read before the next effects parcel

**The off-screen frame-top ship.** A patched program carries a trailer at `128 + 2 + 8*records`
describing a frame-top DMA built from the marked fire's OWN `pal_region` op; the runtime ships it
on frames where that channel's latched screen line is `<= 0`. Authored as
`patchable(..., offscreen_ship: 1)`. Plan, before-measurement and gate evidence are in
`docs/superpowers/plans/2026-08-15-water-offscreen-state.md` and
`docs/benchmarks/effects-p3-water-state/`.

### The follow-up owner testing found, and the lesson in it

The ship first shipped covering only the fire's `pal_region`. OJZ's water fire also carries
`sh_on()`, so fully submerged the top rows had the shimmer and the colour tint but **no
Shadow/Highlight** — visibly lighter. Fixed the same day (the trailer carries the fire's
`set_reg` words and `Enqueue_Dirty_Buffers` replays them after `Flush_VDP_Shadow`).

**None of the parcel's own gates could have caught it.** The entry decode, the CRAM poison test
and the enqueue breakpoint all asked *"is the palette right?"*, because that is the mechanism
that got built. **A gate built around the mechanism you implemented cannot see the part of the
requirement you did not implement.** When a parcel re-issues a composite thing — a fire is an op
LIST — gate the composite, not the op you happened to wire up.

### READ THIS FIRST: oracle pixel capture is not a gate here

The planned gate was a screenshot A/B and it was **abandoned mid-parcel**. Three capture
protocols were tried; each was killed by its own determinism control, not by a wrong-looking
result (15,846 px → then 20,834 → then 12,972 between runs of ONE config). Two confirmed causes:

- **`emulator_reset` is DEFERRED.** The same "reset then 180 frames" gave `Frame_Counter` 175,
  319 and 409. Always press ~2 frames and read the counter back to confirm the reset landed.
- **`BgAnim_Update` drives from `Logic_Tick`, the LAG-IMMUNE tick** (`bg_anim.emp:124-140`), so
  two builds — or one build after an emulator relaunch — sit at different animation phases at the
  same frame number. **Cross-build pixel comparison is therefore unsound**; a provably no-op
  refactor still differed by 13,270 canopy pixels.
- **`run_to_scanline` polls at ~16 ms**, a whole frame. A CRAM sample through it appeared to show
  a bug that a breakpoint then disproved.

**Gate on structure: arm words in `Raster_Buf_B`, breakpoints at the code you mean, and CRAM
sampled at a point you can defend — with the poison applied IN THE SAME RUN.** Same-ROM
comparison is sound; cross-ROM is not. This is the second parcel to pay this cost, which makes
queue item 1 below the highest-leverage thing on the list.

### Two traps this parcel paid for

- **A cross-seam reference is invisible to `build.sh`.** Four new ones (`Effects_Screen_L`,
  `Effects_Offscreen_Entry`, `Static_Pal_Ship`, `Build_DMA_Entry`) built green in aeon and broke
  **five sigil port targets**, because a `*_port` test compiles its module standalone. Add the
  symbol to `crates/sigil-harness/repin.toml` AND to each test's carrier table.
- **A link-time address cannot enter an emitted image that a comptime pin compares.** Folding
  `extern("Pal_Variant_Stage")` into the program trailer made the whole image non-comptime and
  broke `first_mismatch(patched_program(...), hand_twin)`. Three spellings, three
  `here.provisional` failures. Carry parameters and add the base at runtime.
  The same rule killed an `extern()` inside a module-scope `ensure` in `raster_dsl.emp` — that
  module is a COMPTIME_HELPERS member, glob-injected everywhere, so the guard evaluates wherever
  the injection lands.

---

## The queue

### 1. `replay_runner` framebuffer dump — now clearly the top item

Unchanged from the previous order's item 2, where its design is fully settled (whole frames as
the dump primitive, a separate `replay_framediff` binary, `--expect-identical` as the control,
no committed golden images, and gates may read the REPORT but never pixels). Repo: `oracle-next`.

Two parcels have now built their gates by hand because it does not exist, and this one had to
abandon its pixel gate outright. The determinism causes above are exactly what a headless,
tick-pinned runner dissolves.

### 2. Ristar's self-rewriting linked-list HBlank schedule

Also unchanged, and it is now load-bearing for a booked defect rather than only an optimisation:
**the DRY direction of a patch channel is blocked on it** (written up in `docs/DEFERRED_WORK.md`
under "The DRY direction of a patch channel"). Aeon cannot disarm ONE patched channel because arm
gaps are relative, so parking a record kills every later fire in the frame. Ristar's nodes write
their own gap AND their own successor (`ristar_disasm/code/disasm.asm:14556-14595`), making
removal local; a disarmed effect costs ~40 cycles instead of its payload.

### 3. Parcel R — mid-screen restore. STILL STOPPED, and its brief still stands

See the previous order's brief. Its recommendation was **(C) defer R until after W**, on the
grounds that R's hard part is ownership of derived state and W was about to answer it. W has now
shipped, and so has this parcel — which added exactly such an owner (`Effects_Screen_L`, one
producer, three readers). **Re-read the brief against that**: the question is whether the latch
pattern generalises to a pre-effect staging buffer, which would collapse R's decision.

### 4. Parcel D — starter pack + content.

### Also open

- Sound packages **5** and **6**; the `STRESS_EVICT` famine root-cause.
- **EFX-2** (cross-fade unreachable) and **EFX-7** (`Raster_Clear` no-op, `HBlank_Uninstall`
  unreachable) — both byte-changing, both deliberately open.
- **Splitting the VSRAM op class** off `RASTER_CRAM_MAX` — only CRAM writes glitch, so `vsram`
  inheriting the 3-word ceiling is pure loss. It only ever makes fires cheaper.
- **Spacing sweep 2/4/8 lines**, to find where the adjacent-`cram` dot disappears.
- `tools/demo_drift_classifier.py` is still **run by nothing** — it is invoked by hand at ritual
  time. Same class as EFX-9 was before Parcel B wired it into `build.sh`. Worth wiring, but note
  it needs a `--changed` list per parcel, so the wiring is not a plain "add it to build.sh".

---

## Residuals this parcel accepted, on purpose

- **The dry direction**: up to ~10 rows wrongly tinted when the anchor is below the screen.
  Blocked on item 2. Both boundaries clamp together, so they are wrong TOGETHER — do not "fix"
  the parallax side alone, that trades a consistent error for a disagreement.
- **The 1..3 window**: with the anchor 1-3 rows below the screen top the boundary still renders
  at screen 3. Both sides agree there, which is the property that matters.
