# Effects P3 Parcel C2 — gate evidence

Parcel C's gate (spec §8.1): **behaviour-identical against a declared delta list**,
with the replay net green and the P1/P2 captures re-run. The delta list is
`DECLARED-DELTAS.md` in this directory, and it was committed BEFORE these captures
(`887921b4`) so it grades them rather than describing them.

Paired: aeon `parcel/effects-p3-c2` + sigil `parcel/effects-p3-c2`. Refreeze chain **118**.
Sigil suite **3716 passed / 0 failed / 4 ignored** across 327 binaries.

---

## What the parcel changed

A section used to bind its visual effects through three `Sec` fields, each read by its
own installer, each treating NULL as *"keep whatever the previous section had"*. It now
binds ONE `EffectsPreset` through `Sec.sec_effects`, and `Effects_InstallPreset` writes
every channel on the crossing — **total binding**, with `_None` sentinels for "off".

The keep-current semantics were not a neutral default: they are why water installed in
the spawn area rendered at a stale screen line in sections that never asked for it
(EFX-1). A NULL cannot mean "off" while it also means "keep".

---

## Final artifacts

| shape | crc | length |
|---|---|---|
| `s4.bin` | `0fcdcbaa` | 697033 |
| `s4.debug.bin` | `50f6ae69` | 711656 |
| `demo.bin` | `6af0112d` | 95652 |
| `demo.debug.bin` | `fdc82cc0` | 99998 |

**These are NOT the CRCs an earlier draft of this file carried** (`8af05d8f` etc.), and
the reason is worth recording because it is a trap. Correcting two stale `repin.toml`
REGION spans changed `pins.rs`, and those pins feed placement — so the ROM moved
*after* the first refreeze, with lengths identical and content reordered. Every capture
below was re-run against the ROMs in this table; the earlier ones were discarded rather
than re-labelled. A gate document that cites a CRC it did not actually test is worse
than one that cites none.

---

## Gate 1 — the preset path is genuinely taken (not silently skipped)

The whole parcel is worthless if `sec_effects` reads 0 at runtime, so this was measured
rather than inferred:

- Breakpoint on `Effects_InstallPreset` **hits**, with `a0` = `$16158` = section 0's `Sec`.
- `Sec + $34` reads **`$00012FBE`**; `OJZ_Preset_Sec0` links at **`$12FBE`**. Match.
- The preset decodes correctly at every field (32 bytes):

```
$00 ep_pal           0002233E   OJZ_Palette
$04 ep_parallax      00000000   act default (the one legal 0)
$08 ep_raster        00012F74   OJZ_TestRamp
$0C ep_patched       00000000   none
$10 ep_cycle         00007DC4   Pal_Cycle_None
$14 ep_variants[0]   00012F96   Variant_Water_Deep
$18 ep_variants[1]   00000000   empty slot
$1C ep_patch_world_y 0000
$1E ep_transition    0000
```

- Post-install runtime state matches what `DECLARED-DELTAS.md` predicted in advance:
  `Raster_Program` = `$00012F74` (OJZ_TestRamp, installed via the preset) and
  `Pal_Active` = `$10` (variant-only).

## Gate 2 — crossings install per-section presets

Held right from spawn through two boundaries on `s4.debug.bin`. `Raster_Program` ends at
**`$12F3A` = `OJZ_TestGradient`**, section 2's program — reached through
`OJZ_Preset_Sec2`, not through the deleted `Raster_InstallSection`. The capture
(`gate_sec2_via_preset.png`) is pixel-consistent with the pre-parcel section-2 capture:
`OJZ_TestPal`'s palette snap plus the dense gradient.

**Read that image carefully before calling it corruption.** Section 2 deliberately
carries BOTH a deliberately-wrong test palette and a 96-line CRAM ramp; it is supposed to
look wrong. This is the trap recorded in `docs/BUGS.md` — two earlier "whole-screen red /
whole-screen blue" reports were fixtures rendering correctly.

## Gate 3 — all four shapes BOOT

Not optional, and not a formality: the release shape shipped rendering NOTHING for an
unknown number of parcels precisely because only DEBUG was ever booted (see the
boot-cursor entry in `docs/BUGS.md`).

| shape | result |
|---|---|
| `s4.bin` | OJZ renders — art, palette, parallax, Sonic |
| `s4.debug.bin` | renders; section 0 identical to pre-parcel |
| `demo.bin` | white 16x16 box on dark blue (the spec) |
| `demo.debug.bin` | white 16x16 box on dark blue |

## Gate 4 — replay net

Both committed fixtures PASS on `s4.debug.bin` at every step of the parcel, including
after the preset path went live (Task 12) and after the legacy path was deleted (Task 13):

```
ojz_fixture        PASS — 1721 ticks, Replay_Done=$FF
ojz_slide_fixture  PASS — 2350 ticks, Replay_Done=$FF
```

The runner's negative control (planting `$DEADBEEF` over checkpoint 1) trips correctly,
so these passes are not vacuous.

## Gate 5 — relocation was byte-identical

Task 10 moved 450 lines of effects library out of the parallax config file. Every moved
symbol was verified byte-identical against a pre-move baseline by a padding-independent
content hash, and the checker was negative-probed (it fails on a corrupted baseline) so
it is not a check that only ever passes:

```
OJZ_TestRaster  OJZ_TestPal  OJZ_ShimmerCycle  OJZ_WaterRaster
OJZ_GradientStream  OJZ_TestGradient  OJZ_TestVsram  OJZ_TestRamp
                                          RESULT: all byte-identical
```

All four ROM CRCs were unchanged across that move — the `map.toml` placement put the new
section exactly where the data physically sat.

---

## Deltas observed, against the list declared in advance

| declared | observed |
|---|---|
| **D1** frame-0 un-varianted water | Did NOT manifest as a replay desync. The variant binds on the first `CheckBoundary`, which `Parallax_Init`'s `$FF` sentinels guarantee runs before the first Update frame renders, so the window is narrower than the design feared. |
| **D2** water becomes per-section | Structurally true — no preset sets `ep_patched`, so sections without one get `Raster_Program_None`. |

**Nothing was observed that is not on the list.**

## Honest limits

- **Sections 3-8 were not rendered individually.** Section 0 and section 2 were captured;
  sections 1 and 3-8 are covered by the preset-content verification (each preset's ROM
  bytes decode correctly) plus the replay fixtures crossing them. A per-section visual
  sweep is Parcel D's job, where content actually differs per section.
- **Captures are not frame-anchored.** Oracle screenshots are known non-deterministic on
  press-frames in this project. The claims above are categorical (which program is
  installed, whether a shape boots) rather than pixel-delta claims, so frame anchoring
  does not apply — except Gate 5, which IS a byte comparison and is anchored by content
  hash instead.
- **No real hardware.** Oracle only, by project policy.
