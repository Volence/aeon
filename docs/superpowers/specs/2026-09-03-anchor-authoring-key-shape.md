# The anchor mover's authoring key shape — EFFECTS-W1 DoD item 4, step 1 of 4

Status: **SHAPE ONLY. NOTHING HERE IS IMPLEMENTED, AND THE READER MUST NOT BE BUILT YET.**
Date: 2026-09-03. Branch `parcel/anchor-motion-key`, based on `origin/master` `e190297c`.

The engine half of item 4 landed as chain 215 (`094496ca`). This document is the other
half's *first* step: the key shape, written so another lane can act on it verbatim.

---

## 0. Why this is a document and not a patch

Teaching `tools/effects_gen.py` to read a new key is **step 4 of a four-step chain**, and
steps 2 and 3 do not exist yet:

| # | Step | Owner | State |
|---|------|-------|-------|
| 1 | aeon names the key shape | this repo | **this document** |
| 2 | empyrean files the schema CR opening the preset document | the hub | not filed |
| 3 | aurora vendors the schema and writes the key | aurora | blocked on 2 |
| 4 | `effects_gen.py` reads it | this repo | **has no input until 3 lands** |

`contract/schema/aurora-effects-preset.schema.json` is a **closed** schema. Verified
directly in `/home/volence/sonic_hacks/empyrean` on 2026-09-03: `unevaluatedProperties:
false` at the top level (line 58) and at six nested positions (lines 115, 118, 139, 172,
205, 240), with top-level `properties` being exactly `[schema, id, name, bands, cycles,
variants]`. A preset document carrying either key below is **refused at parse today**.

A reader built now would land green and read a key no document can legally contain — a
check that cannot fail. Hence: shape first.

> **Correction of record, attributed to the aurora lane.** The item-4 design's §8.2 (line
> 902 at `094496ca`) says an older Aurora "erases it on the next save round-trip". That is
> **wrong about Aurora and the remedy inverts.** Aurora is conformant and takes the *refuse*
> branch. The failure is therefore not silent loss on save; it is that **every author on a
> tree carrying the key cannot OPEN that preset at all.** Cite §8.2 only with this
> correction.

---

## 1. The blocker, measured rather than inherited

The brief's load-bearing claim was that `tools/effects_gen.py` cannot express a channel's
world Y *at all*. **Still true**, measured on `origin/master` (HEAD `e190297c`, confirmed
`git merge-base --is-ancestor` equal, not a stale checkout):

```
patch_world_ys   0        <- negative
patch_motion     0        <- negative
anchor_sweep     0        <- negative
world_ys         0        <- negative

drift           13        <- POSITIVE CONTROL (item 3's key, landed chain 205)
vsplit           4        <- positive control
cycles          31        <- positive control
variants        30        <- positive control
```

The positive controls matter: they prove the grep and the file path are right, so the four
zeros are absence and not a typo. **This parcel is two keys or it is nothing** — a motion
key alone would let an author say *how* a boundary moves but never *where* it starts, and
`preset()` would default the anchor to `PATCH_ANCHOR_NONE`, i.e. the channel is unused and
the motion is invisible.

---

## 2. THE KEY SHAPE — the verbatim block

**Document**: the *preset* document, `games/sonic4/data/editor/effects/presets/<id>.json`.
**Position**: top level, beside `bands` / `cycles` / `variants`.
**Why the preset document**: `ep_patch_world_ys` and `ep_patch_motion` are `EffectsPreset`
fields (`engine/effects/preset.emp:66`, `:86`), and a preset document is what lowers to a
preset. A *scene* document lowers to parallax layers and has no patch channels.

**Names**: `patch_world_ys` and `patch_motion` — spelled exactly as `preset()`'s own
parameters (`engine/effects/preset.emp:141-148`). This follows the item-3 precedent, where
the document key `drift` matched `layer(drift:)`'s argument name. Minimum translation
distance is the house convention.

### 2.1 Both keys: array shape and the three states

Both are **positional arrays**, index = patch channel, max length `RASTER_MAX_PATCH` = 4
(`engine/effects/raster_dsl.emp:2089`). This mirrors `variants`, whose per-index semantics
the hub already ruled (Q5).

Three states per index, one spelling each:

| State | Spelling | Means |
|---|---|---|
| index absent (short array, or key absent) | — | **keep** the section's hand-authored value |
| `null` | `null` | the engine's **sentinel**, never `0` |
| a value | see below | authored |

`null` maps to `PATCH_ANCHOR_NONE` (`$7FFF`) for `patch_world_ys` and `ANCHOR_MOTION_NONE`
(`0`) for `patch_motion`. **For the world Y it must NOT be `0`**, and this is the sharpest
trap in the whole shape: `raster_dsl.emp:2095-2103` states that the parallax overlay derives
a screen line as `anchor - Camera_Y`, so a `0` anchor reads as *above the screen top* — the
most invasive possible state for a channel nobody asked for. `$7FFF` is the inert answer.
This is the same rule as item 5's `cycles: null -> Pal_Cycle_None, never 0`.

### 2.2 `patch_world_ys[i]` — the seed

```jsonc
"patch_world_ys": [224, 314, null, null]
```

| Property | Value |
|---|---|
| Type | integer (or `null`) |
| **Unit** | **whole pixels**, absolute, in level space |
| Range | `0 … 65535` (the field is `u16`) |
| Reserved | **`32767` (`$7FFF`) must be refused** — it is `PATCH_ANCHOR_NONE`, i.e. "channel unused". Spell that as `null`. |
| **Conversion** | **NEITHER SIDE CONVERTS. 1:1.** |

> ⚠ **Do not carry item 3's habit here.** `drift.rate` is 1/256 px per frame and Aurora
> multiplies by 256 on export. `patch_world_ys` is **whole pixels and neither side scales**.
> A world Y exported ×256 lands 256× down the level, `anchor - Camera_Y` is enormous, and
> the band silently never appears. This is the single most likely cross-contamination
> between the two keys.

### 2.3 `patch_motion[i]` — the motion

Exactly one arm, `sweep` (the `_single_arm` form item 3's `drift` uses):

```jsonc
"patch_motion": [
  { "sweep": { "amp_shift": 4, "period_shift": 1, "phase": 0 } },
  null, null, null
]
```

Lowers to `anchor_sweep(amp_shift: 4, period_shift: 1, phase: 0)`.

| Field | Type | Range | Required | Unit |
|---|---|---|---|---|
| `amp_shift` | integer | **2 … 8** | yes | base-2 log; peak excursion = `256 >> amp_shift` px |
| `period_shift` | integer | **0 … 8** | yes | base-2 log; one cycle = `256 << period_shift` ticks |
| `phase` | integer | **0 … 255** | no, default `0` | sine **table entries**; 0..255 is one full cycle |

**Only `sweep`. There is no `approach` arm, and the schema must not reserve one yet.**
`preset.emp:81-87` scopes it out in as many words: APPROACH has no seed field, its runtime
handle is `Effects_SetTargetY`, and eight bytes per preset of guaranteed-zero target and
rate words would be a dormant scaffold. `anchor_rate_mask()` exists but is *not* reachable
from a preset.

### 2.4 The ladders are QUANTIZED — the Aurora UI consequence

`amp_shift` and `period_shift` are **base-2 logarithms**, not physical quantities. Aurora's
timeline control must convert *down* to a shift on export, and there are only **7 amplitude
rungs and 9 period rungs**. A slider must **snap**; it cannot offer intermediate values, and
rounding the wrong way silently doubles or halves the result. `phase` is the only continuous
field.

Derived from `engine/effects/raster_dsl.emp` (`ANCHOR_SINE_AMP` = `$100`,
`ANCHOR_SCREEN_LINES` = 224, `ANCHOR_SINE_ENTRIES` = `$100`, `ANCHOR_TICK_BITS` = 16),
re-executed independently rather than copied:

| `amp_shift` | peak (px) | peak-to-peak (px) |   | `period_shift` | cycle (ticks) | cycle @60 Hz |
|---|---|---|---|---|---|---|
| 2 | 64 | 128 |   | 0 | 256 | 4.27 s |
| 3 | 32 | 64 |   | 1 | 512 | 8.53 s |
| 4 | 16 | 32 |   | 2 | 1024 | 17.07 s |
| 5 | 8 | 16 |   | 3 | 2048 | 34.13 s |
| 6 | 4 | 8 |   | 4 | 4096 | 68.27 s |
| 7 | 2 | 4 |   | 5 | 8192 | 136.53 s |
| 8 | 1 | 2 |   | 6 | 16384 | 273.07 s |
|   |   |   |   | 7 | 32768 | 546.13 s |
|   |   |   |   | 8 | 65536 | 1092.27 s |

Conversions Aurora owns:

```
amp_shift    = log2(256 / peak_px)                  # peak_px must be a power of two, 1..64
period_shift = log2(cycle_seconds * 60 / 256)       # cycle_seconds snaps to the table above
phase        = round(fraction_of_cycle * 256)       # 0..255, continuous
```

The shipped hand-authored precedent is `OJZ_Preset_Sec0`
(`games/sonic4/data/effects/ojz_effects.emp:1097`): `anchor_sweep(amp_shift: 4,
period_shift: 1)` = 32 px peak-to-peak over 8.53 s, phase 0.

---

## 3. Refusals, and where each bound is enforced

| Violation | Refused by | Site |
|---|---|---|
| unknown top-level key | generator, existing `_check_keys` | `tools/effects_gen.py:586` |
| `amp_shift` outside 2..8 | **engine `ensure`, build failure** | `engine/effects/raster_dsl.emp:2232` |
| `period_shift` outside 0..8 | **engine `ensure`** | `engine/effects/raster_dsl.emp:2234` |
| `phase` outside 0..255 | **engine `ensure`** | `engine/effects/raster_dsl.emp:2236` |
| sweep packing to the `NONE` sentinel | **engine `ensure`** (unreachable while min ≥ 1) | `engine/effects/raster_dsl.emp:2238` |
| array length ≠ 4 at the call site | **engine `ensure`** | `engine/effects/preset.emp:161`, `:167` |
| non-integer / wrong JSON shape | generator, shape check only | step 4 |
| `patch_world_ys[i] == 32767` | **NOTHING TODAY — see §4** | — |
| world Y outside `u16` | **NOTHING TODAY — see §4** | — |

**Posture, inherited from chain 205 and unchanged:** value bounds are enforced by the
engine's `ensure`s at build time, **not** by the generator. The generator checks *shape*
only. `layer()`'s and `anchor_sweep()`'s messages are the field's real documentation — they
state the unit, give the worked conversion and name the corpus max — and a bound copied into
the generator would be a second source that drifts.

---

## 4. Obligations the consumer CANNOT check

Three, and they should be written into `tools/EFFECTS_CONSUMER_CONTRACT.md` at step 4.

**(a) The band fit — the big one.** A sweep's peak-to-peak travel must stay inside its
channel's `patchable(lo, hi)`. Leaving that band upward does not clamp: `Raster_BuildSchedule`
*removes* the record for the frame (`bgt .suppress`), so the band **vanishes** and returns at
the next zero crossing — a flicker that reads as a rendering bug, not as an amplitude anyone
chose. `anchor_sweep()` refuses an amplitude wider than the **screen**, which is necessary
and not sufficient; `lo`/`hi` live in the raster program and `amp_shift` in the preset, and
they are associated by a *pointer* at runtime, so no comptime scope holds both.

> **`tools/test_anchor_sweep_band.py` is that scope — and it reads ONLY
> `games/sonic4/data/effects/ojz_effects.emp`** (`OJZ_EFFECTS`, and `authored_sweeps()`
> scans it alone). **A generator-authored sweep would land in
> `ojz_effects_editor_act1.emp` and be completely invisible to it.** Extending that test to
> the generated file is a **hard prerequisite of step 4**, not a nice-to-have — an author has
> no comptime error to guide them, so they need it *more* than a programmer does. Note the
> scanner must also change shape: the generated form is a chooser body
> (`if sec == N && ch == C { out = anchor_sweep(...) }`), not an array position.

**(b) The capability gate.** `CAP_ANCHOR_MOTION` (`$0100`) must be raised in the game's
`SCANLINE_CAPS`. sonic4 is `$01DE` (raised); demo is `0` (not). The asymmetry matters and is
deliberate: `Effects_InstallPreset`'s **seed is NOT capability-gated** (34 bytes paid by
every game, documented as a measured decision at `preset.emp:333-340`), while the **latch
loop that reads it IS** (`engine/effects/raster.emp:1930`). So in a game without the bit an
authored sweep is seeded into `Effects_Motion[]`, `Effects_Motion_Any` is folded — and
**nothing ever reads it.** The boundary does not move, and nothing says why. Step 4 wants a
refusal here.

**(c) Channel liveness.** A sweep on a channel no `patchable()` call declares is invisible.
`test_anchor_sweep_band.py` already asserts this for hand-authored sweeps and must cover the
generated ones too.

---

## 5. Where step 4 would touch the generator — file:line for the CR to cite

All on `origin/master` `e190297c`.

| What | Site |
|---|---|
| accept the two names | `tools/effects_gen.py:280` (`PRESET_KEYS`) |
| (nothing to un-reserve — only `fires` is reserved) | `tools/effects_gen.py:293` (`PRESET_REFUSED_KEYS`) |
| unknown-key refusal already routes both | `tools/effects_gen.py:586` (`_check_keys(path, preset, ...)`) |
| shape checks, beside `_check_cycles` / `_check_variants` | `tools/effects_gen.py:618` |
| renderers, beside `render_preset_variants` | `tools/effects_gen.py:1389` |
| chooser symbol names, beside `fn_sec_cycle` / `fn_sec_variant` | `tools/effects_gen.py:1648-1649`, `:1690` |
| chooser emission, in block (e) | `tools/effects_gen.py:1971-2010` |
| contract §2.4 | `tools/EFFECTS_CONSUMER_CONTRACT.md` |
| the cross-file band check (see §4a) | `tools/test_anchor_sweep_band.py` |

### 5.1 The lowering step 4 should emit

Follow `fn_sec_variant`, which is already a per-`(sec, slot)` chooser. Two per-`(sec,
channel)` choosers returning `int`:

```
pub comptime fn ojz_act1_sec_patch_world_y(sec: int, ch: int, hand: int = PATCH_ANCHOR_NONE) -> int
pub comptime fn ojz_act1_sec_patch_motion (sec: int, ch: int, hand: int = ANCHOR_MOTION_NONE) -> int
```

called from the hand-authored `preset()` in `ojz_effects.emp`:

```
patch_world_ys: [ojz_act1_sec_patch_world_y(sec: 0, ch: 0, hand: 224), ... ],
patch_motion:   [ojz_act1_sec_patch_motion (sec: 0, ch: 0, hand: anchor_sweep(amp_shift: 4, period_shift: 1)), ... ]
```

Two properties of this shape are worth stating because they are not obvious:

* **It sidesteps `preset()`'s length `ensure` entirely.** The call site writes all four
  elements literally, so `patch_world_ys.len == RASTER_MAX_PATCH` stays true by construction
  no matter what the document says. A generator that emitted an *array* would have to pad,
  and padding is where a short document silently becomes an anchor nobody authored.
* **The defaults are free names and resolve at the CALL SITE**, not here
  (`docs/EMP_PITFALLS.md` §2) — the same rule that makes `hand:` a parameter on the existing
  choosers. `PATCH_ANCHOR_NONE` and `ANCHOR_MOTION_NONE` are both already imported by
  `ojz_effects.emp` via `use engine.effects.raster_dsl.*` (line 137). Confirm that at step 4;
  a game whose effects library does not glob-import `raster_dsl` would need them named.

---

## 6. What is NOT in this parcel

No generator code was written. The scope changed mid-parcel to shape-only, before any reader
existed, so there is nothing held back and nothing to un-land later. This branch is
**documentation only** and changes no ROM byte.
