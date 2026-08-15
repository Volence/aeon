# The off-screen frame-top ship — GATE EVIDENCE

**Date:** 2026-08-15 · **Shape:** `s4.debug.bin` · **Branch:** `parcel/water-submerged-state`
**Before-measurement:** `BEFORE-EVIDENCE.md` beside this file.

---

## 0. THE PIXEL GATE WAS ABANDONED, AND THAT IS THE MOST IMPORTANT LINE IN THIS FILE

The plan's gate was a screenshot A/B: submerged vs dry, assert rows 0..1 go from identical to
differing. **It was abandoned mid-gate because oracle pixel capture could not be made reproducible
here**, and the evidence below is structural instead.

Three protocols were tried, and each was killed by its own determinism control rather than by a
result looking wrong:

| protocol | control result |
|---|---|
| freeze the scene, poke anchors, capture | **15,846** px between two captures of ONE config |
| + anchor both captures to a fixed frame count after `reset` | 0 once, then **20,834** on a later build |
| + verify the reset landed, + pin `Frame_Counter` to an absolute target | 0 twice, then **12,972** after an emulator relaunch |

Two independent causes, both confirmed: `emulator_reset` is **deferred** (the same "reset then 180
frames" gave `Frame_Counter` 175, 319 and 409 on different runs), and `BgAnim_Update`
(`engine/level/bg_anim.emp:124-140`) drives its bands from `Camera_X` / `Camera_Y` / **`Logic_Tick`
— the lag-immune tick**, so two builds, or one build after a relaunch, sit at different animation
phases at the same frame number.

A fourth caution, learned the same way: **`run_to_scanline` polls at ~16 ms granularity — a whole
frame.** A CRAM sample taken through it appeared to show the ship firing while the boundary was on
screen. It was not; the sample had landed in the next frame's active display, past the fire line.
That reading is what the breakpoint test in §3 exists to overrule, and it would have been reported
as a bug if the breakpoint had not been run.

**The rule this leaves for the next effects parcel:** an oracle screenshot is a LOOK, not a gate.
Gate on arm words, on breakpoints, and on CRAM sampled at a point you can defend. This is exactly
the pain the `replay_runner` framebuffer-dump parcel exists to remove, and it is now the second
parcel to pay for it.

---

## 1. The entry the install builds — verified against an independent derivation

`Static_Pal_Ship` after booting the water section, read off the machine:

```
9400 9303 977F 96C5 95ED C048 0080
```

| field | bytes | means | expected |
|---|---|---|---|
| length | SizeH $00, SizeL $03 | 3 words | `count: 3` on the fire ✓ |
| source | $7F / $C5 / $ED = `$7FC5ED` | address `$FF8BDA` | `Pal_Variant_Stage` ($FF8B92) + 72 ✓ |
| command | `$C0480080` | CRAM $48, DMA | pal line 2, entry 4 ✓ |

The expected source was derived from a **separate** symbol lookup of `Pal_Variant_Stage`, not from
the encoder — so this checks the install-time builder against the authored arguments rather than
against itself. 72 is `pal_stage_off(0, 2, 4)`.

`Effects_Offscreen_Entry` reads `$00013154`, a ROM pointer into the program's trailer.

## 2. It ships exactly when the boundary is off the top — breakpoint at the enqueue

Breakpoint at `$223C`, the `lea Static_Pal_Ship, a2` inside the ship's `queue_static_dma` splice
(`Enqueue_Dirty_Buffers+246`). It is past the queue-full test, so it fires **only when the ship
actually enqueues**.

| `Effects_Screen_L[0]` | camera | breakpoint |
|---|---|---|
| -176 | 400 | **HIT** — submerged ships |
| **0** | 224 | **HIT** — the threshold is inclusive |
| **1** | 223 | silent | 
| 80 | 144 | silent over ~240 frames — an on-screen boundary never ships |

Rows 2 and 3 pin the threshold at exactly `L <= 0`, which is the number the parallax side's
`ble .anchor_top` must agree with. If either side moves, the palette and shimmer boundaries
separate in the 1..3 window — the defect Parcel W exists to remove.

**Trap for whoever repeats this:** after writing `Camera_Y` while paused, the latch has NOT re-run
— `Effects_Screen_L` still holds the previous camera's answer, and a breakpoint hit immediately
after resuming is the OLD state. Advance frames and read the latch back before arming. The first
run of the `L = 1` case reported a false HIT for exactly this reason.

## 3. The palette actually changes — CRAM at frame top, poisoned in the same run

Sampled after the VBlank DMA drain and before the next frame's fire, submerged:

| | CRAM line 2, entries 4/5/6 |
|---|---|
| ship live | `0224 0224 0446` — **the water stage** |
| `Effects_Offscreen_Entry` zeroed by hand, same run | `0248 026A 048C` — **the base** |

Base and water read independently from `Palette_Buffer+72` and `Pal_Variant_Stage+72`. Poisoning
in-place on ONE run is what makes this sound: no reset, no reboot, so none of the nondeterminism in
§0 is in play, and the only thing that changed is the mechanism under test.

## 4. Build-time guards, each proved by inversion

| guard | inverted to | result |
|---|---|---|
| `offscreen_ship` is 0 or 1 | `offscreen_ship: 2` | build fails, own message |
| a shipped fire needs exactly one `pal_region` | flag set on the vscroll channel | build fails, own message ("this fire has 0") |
| at most one shipping fire per program | flag set on both channels | build fails, own message |
| the trailer's framing | the OJZ hand twin | caught the count word and the entry, both directions |

**The adjacent legal case builds:** the same argument shape refused on channel 1 is accepted on
channel 0, which carries a `pal_region`. That is the half that stops a guard from being one that
refuses everything.

`ensure` does not short-circuit, so the two-channel inversion printed the `pal_region` message as
well; the `n <= 1` message was present and was briefly missed because a `sort -u | head -4` in the
harness cut it. Read the whole list.

## 5. What is NOT claimed

- **No pixel evidence.** The visual result was looked at and is consistent, but no screenshot in
  this parcel meets a standard worth citing (§0).
- **The dry direction is unchanged and still wrong** by up to 10 lines. Suppressing a fire needs
  per-record parking; blocked on the Ristar linked-list schedule. Both boundaries clamp together
  today, so they are wrong TOGETHER — the consistent error is the deliberate choice.
- **The 1..3 window** still renders the boundary at screen 3 when the world says 1..3. Accepted,
  same class as the dry side, and both sides agree there.

---

## 6. The byte-moving ritual

| step | result |
|---|---|
| `repin` | 312 pins moved; `PAL_VARIANT_STAGE` +0xC, the object family +0x40 plain / +0x50 debug, `SOUND_API` +0xC0/+0xD0 |
| `refreeze --freeze offscreen-frame-top-ship --ab <this file>` | **chain 125** |
| sigil suite (`--workspace --no-fail-fast`) | **3721 passed / 0 failed**, 329 test-result lines, exit 0 |
| contract closure | **0 firings** |
| four shapes boot | s4 (release), s4.debug, demo, demo.debug — all render |

CRCs: s4 `6c2a1d9d` · s4.debug `9ed5fcea` · demo `f2a37230` · demo.debug `d9896c6f`

### The suite failed first, and what it caught was real

Nine tests across five targets went red on the first run: `buffers_port`, `parallax_port`,
`raster_port`, `raster_negative_probes` and `repin_pins`. Every one was the **cross-seam port
trap** — a port test compiles its module STANDALONE, so a new reference to a symbol owned by
another seam stops resolving. This parcel added three (`Effects_Screen_L`,
`Effects_Offscreen_Entry`, `Static_Pal_Ship`) plus one outbound call (`Build_DMA_Entry`).

They are declared now, in `repin.toml` and in each test's carrier table. Worth carrying forward:
the aeon build was GREEN through all of this. Nothing in `build.sh` knows about the port oracles,
so a cross-seam reference is invisible until the sigil suite runs.

### The demo drift gate

`tools/demo_drift_classifier.py` failed at **20,285 unclassified bytes**, because it modelled
RAM-only growth and this parcel adds engine CODE. Ruled by a Fable adviser to extend the tool in
this parcel rather than declare the parcel out of class. With categories (iv) code relocation and
(v) declared edit spans:

| run | unclassified |
|---|---|
| `demo` + full declaration | **0 — PASS** |
| `demo.debug` + full declaration | **0 — PASS** |
| one declared span dropped | 203 — FAIL |
| no declarations at all | 851 — FAIL |

The last two rows are the non-vacuity proof: the gate still refuses an undeclared edit, which is
the guarantee the retired "demo CRCs unchanged" criterion carried.

Declared spans: `BuildStaticDMA`, `Build_DMA_Entry`, `Enqueue_Dirty_Buffers`,
`Effects_LatchWorldLines`, `Raster_PatchAll`, `Raster_InstallPatched`, `Raster_BuildShipEntry`,
`Effects_InstallPreset`, `Parallax_Step4_Fill`.
