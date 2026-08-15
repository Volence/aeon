# Parcel W0 — `Effects_World_Y[]` becomes total-bound. Gate evidence.

**Date:** 2026-08-15. **Branch:** `parcel/w0-anchor-total-binding`.
**Shapes:** all four build; `s4` plain `crc=b2a69c77 len=697017` (was `4c4cac75 / 696995`, +22 B).

W0 was split out of Parcel W as its own micro-parcel on a Fable adviser's ruling (2026-08-15):
it fixes a defect that exists **today**, independent of W, so it must not ride on W's success or
die with W's revert. W's design draft is
`docs/superpowers/specs/2026-08-15-effects-p3-parcel-w-design.md`.

---

## 1. The defect, stated

`Effects_World_Y[RASTER_MAX_PATCH]` was seeded **only** inside `Raster_InstallPatched`
(`engine/effects/raster.emp`, the `.seed` loop), which `Effects_InstallPreset` reaches only on the
`ep_patched != 0` branch. So a section whose preset names no patched program never wrote the bank
and silently inherited the previous section's anchors.

That is exactly the semantic Parcel C2 deleted everywhere else — ARCH §7.12: *"a NULL cannot mean
'off' while it also means 'keep'"*. It survived C2 because the bank had a single reader
(`Raster_PatchAll`) that was itself gated on the same condition, so the staleness was invisible.
It stops being invisible the moment a second reader exists that is **not** so gated, which is
precisely what Parcel W adds.

## 2. The defect WITNESSED, before any fix existed

Oracle, `s4.bin` at `crc=4c4cac75` (master, pre-fix). Symbols from `s4.lst`.
`Effects_World_Y` = `$FF8ABA`, `Raster_Patch_Tab` = `$FF8AC2`, `Camera_X` = `$FFA436`.

Input sequence from reset: `start`×180, `right`×400, `right+c`×12 (one jump — the player pushes
against terrain at x=454 and the camera stalls without it), `right`×390.

| where | `Camera_X` | `Effects_World_Y[0..3]` | `Raster_Patch_Tab` |
|---|---|---|---|
| section 0 (spawn) | `$0127` | `00E0 013A 0000 0000` | `000128B8` (live) |
| section 1 | `$08E0` (2272) | **`00E0 013A 0000 0000`** | `00000000` (torn down) |

`SECTION_SIZE_SHIFT = 11`, so `$08E0 >> 11 = 1`: the camera is in section 1.
`OJZ_Preset_Sec1` names no patched program and defaults `ep_patch_world_ys` to `[0,0,0,0]`
(`games/sonic4/data/effects/ojz_effects.emp`). **The bank should read all zeros and reads
section 0's 224/314.** The patch *table* was correctly torn down; only the anchors leaked.

This is the inversion probe, and it was run **before** the fix was written rather than
reconstructed afterwards — the failure mode this repo keeps re-finding is a guard that was never
observed failing.

## 3. The fix

1. `Raster_InstallPatched` loses its `a2` parameter and its `.seed` loop.
2. `Effects_InstallPreset` seeds `Effects_World_Y[]` from `ep_patch_world_ys`
   **unconditionally**, at the top, for every install.
3. **`clr.l Raster_Patch_Tab` precedes the seed**, and that order is load-bearing rather than
   tidiness. `Effects_InstallPreset` runs from the MAIN LOOP at the crossing site, and the palette
   work below it costs thousands of cycles, so a VBlank lands inside that window routinely. In that
   VBlank `Raster_PatchAll` re-derives every arm gap from `Effects_World_Y`, using
   `Raster_Patch_Tab` **alone** as its liveness test — so seeding the incoming section's anchors
   while the outgoing template's table is still live would re-patch the outgoing program's
   boundaries to the new section's world Ys for one frame: a visible one-frame boundary jump at
   every crossing. Clearing first makes that VBlank a no-op instead, and the outgoing program holds
   last frame's arms. `clr.l` is one instruction, so a VBlank sees the old pointer or 0, never a
   torn one.

   This was **not** in the first draft of the fix, which put the clear on the `.no_patch` branch —
   below the palette loads, i.e. below the window it was meant to close. Caught by the adviser.
4. `preset()`'s `patch_world_ys.len` ensure keeps its meaning; its message is re-pointed at
   `Effects_InstallPreset`, and the guard now covers a field **every** preset consumes.

## 4. The fix VERIFIED — same ROM, same input sequence, both directions

Oracle, `s4.bin` at `crc=b2a69c77` (post-fix), identical input sequence from reset.

| where | `Camera_X` | `Effects_World_Y[0..3]` | verdict |
|---|---|---|---|
| section 0 (spawn) | — | `00E0 013A 0000 0000` | **adjacent legal case intact** — the working path still seeds |
| section 1 | `$08EC` (2284) | **`0000 0000 0000 0000`** | **bound** — section 1's own values |

Against the section-1 row of §2 (`00E0 013A`), which is the baseline this is measured against.
Screenshot at the section-1 position shows the scene rendering normally — no corruption, no
palette or raster artefact from the earlier table clear.

**Both halves of the guard standard are present:** the inversion (the defect observed failing) and
the adjacent legal case (section 0, which must keep working and does).

## 5. What this parcel does NOT do

- It does not change the `[0,0,0,0]` default of `ep_patch_world_ys`. Under W's overlay a zero
  anchor would mean `L = -Camera_Y <= 0` — "fully submerged" — which is the wrong safe default;
  a large positive sentinel is the right one. That belongs to W, which introduces the reader that
  gives the value meaning. Today the only reader is `Raster_PatchAll`, gated on a patch table that
  is 0 in exactly those sections, so a zero anchor is inert.
- It adds no reader, no RAM, no op number, and nothing from W's design.
