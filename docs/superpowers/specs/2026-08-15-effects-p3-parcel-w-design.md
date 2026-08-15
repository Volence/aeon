# Parcel W — the world anchor gets a SECOND READER (design draft)

**Status:** DRAFT, written 2026-08-15 from the CORRECTED premise. Not yet lens-swept, not planned,
no code. Supersedes the framing in `docs/superpowers/2026-08-16-overnight-work-order.md` §5.

**Entry facts, every one re-derived from the tree today** (docs in this repo drift; specs are INTENT):

| claim | proof |
|---|---|
| the FG deform wave is already layer-anchored | `engine/level/parallax.emp:937-944` folds `Camera_Y` into the sample index |
| the BG deform wave is too | `parallax.emp:957`, `:973` add `Parallax_Current_Vscroll_BG` to the phase base |
| band tops are authored in Plane B cell rows and rotated by BG vscroll each frame | `parallax.emp:611-625`, rebase+clamp at `:659-677` |
| the raster patch channel is act-space world Y, converted once per record | `raster.emp:892-894` (`anchor − Camera_Y − 1` → fire line) |
| `Effects_World_Y[4]` is owner-neutral RAM with four consumers, all in `raster.emp` | `ram.emp:333`; `raster.emp:831`, `:881`, `:923`; test call site `ojz_scroll_test.emp:419` |
| one preset already binds BOTH sides | `preset.emp:56-65` — `ep_parallax` and `ep_patch_world_ys` live in the same 38-byte struct |

---

## 1. What W is NOT

The work order asked for a design that gives the deformation wave a world anchor, citing S3K for the
defect that "a wave keyed to a frame counter slides when the camera moves." **That defect was found
and fixed in this tree before W was proposed** — Harmony study defect #2, `parallax.emp:937-944`. The
wave rides the art. W must not re-litigate it, and any design that changes what the wave's *phase*
is folded from is a regression, not a feature.

## 2. What W IS

A complete underwater section needs a palette boundary **and** a shimmer boundary **at the same
line**. Today the two boundaries are computed in different spaces and cannot be made to agree:

| | raster patch channel | parallax band top |
|---|---|---|
| authored in | act-space world Y | Plane B cell row 0..63 |
| granularity | 1 scanline | 8 px |
| wraps | no | yes, every 512 px |
| follows | `Camera_Y` 1:1 | `Vscroll_BG` = camera × BG factor |

The previous session stopped here and called the last row unfixable. **It is not a conflict, because
the two rows are answering different questions.** "Where does the region start" and "what art does
the wave ride" are independent quantities that this engine already keeps in separate registers: the
band top is `d5` in `Parallax_Fill_PerLine`, the wave phase is `d2`/`d6`. Folding `Camera_Y` into a
band's TOP does not touch the phase fold, so defect #2 survives untouched.

So W's answer to the three open questions:

1. **Which space is authoritative?** Act-space world Y, held in `Effects_World_Y[ch]`, exactly as the
   raster channel already holds it. Plane space stays private to plane-anchored bands. Each consumer
   converts to a **screen line** at read time — screen line is the only space the two genuinely share.
2. **The 8-px granularity mismatch?** Deleted, not tolerated. The shadow band view's top becomes a
   **screen line**, not a screen cell (§3.2). Both boundaries then land on the same scanline.
3. **What does a shared boundary mean when the BG factor is not 1?** The boundary follows the camera
   1:1, because a water surface is a feature of the LEVEL. The art inside the region keeps riding its
   own plane at its own factor, and the wave inside it keeps folding `Vscroll_BG` into its phase.
   Nothing is constrained to factor 1, and defect #2 is not re-opened. The BG art visibly slides
   under the water line as the camera rises — which is correct: they are at different depths.

## 3. The design, in three pieces

### 3.0 W0 — anchors become total-bound (a prerequisite, and a latent-bug fix)

`Effects_World_Y[]` is seeded **only** on the `ep_patched != 0` path (`preset.emp:230-237`, seeding
inside `Raster_InstallPatched` at `raster.emp:831-835`). A section whose preset has no patched
program never writes the bank, so it inherits the previous section's anchors. That is precisely the
stale-channel class Parcel C2 existed to kill — "a NULL cannot mean *off* while it also means
*keep*" — and it survived because the bank had exactly one reader that was itself gated on the same
condition.

W adds a reader that is **not** so gated, so this must be fixed first, and it is a fix either way:

- Move the seed loop out of `Raster_InstallPatched` into `Effects_InstallPreset`, run
  **unconditionally**, before the `ep_raster`/`ep_patched` branch (it must precede
  `Raster_PatchAll`, which `Raster_InstallPatched` tail-calls).
- `Raster_InstallPatched` loses its `a2` parameter and becomes `(a0)` only.
- `preset()`'s `patch_world_ys.len == RASTER_MAX_PATCH` ensure keeps its meaning and gains reach: it
  now guards a field every preset actually consumes.

### 3.1 W1 — the shadow band view measures in SCREEN LINES

The rotated shadow view (`Parallax_Shadow_Bands`) is rebuilt every frame and read by exactly two
routines. Its top byte changes unit from screen cell (0..28) to screen line (0..224) — both fit a
byte, so no storage moves.

- `parallax.emp:659-677` (rebase): clamp in CELLS to 28 as today — the clamp is what stops the filler
  overrunning `Hscroll_Buffer` — then `lsl #3` to lines before the store.
- `Parallax_Fill_PerLine:915`: delete its `lsl.w #3` on the peeked next top.
- `Parallax_Fill_PerCell:1104`: add `lsr.w #3` on the peeked next top; `.last_band_end` 28 → 224 >> 3.
- ROM data is untouched: `band_entry.band_top_cell` stays plane cells 0..63. The field is renamed
  `band_top` with the two units documented at the struct, because a name asserting "cell" on a byte
  that holds lines in RAM is how the next reader gets it wrong.

**This piece is output-neutral by itself** and that is its gate (§5).

### 3.2 W2 — the anchored terminal band

`parallax_config` gains one byte, `pcfg_anchor_ch`: a patch channel 0..`RASTER_MAX_PATCH`-1, or
`PARALLAX_ANCHOR_NONE = $FF`.

When it names a channel, the config carries **one extra `band_entry` after the band array**, at
index `pcfg_band_count` — i.e. `pcfg_band_count` counts only the plane-anchored bands, so the Step 4a
rotation loop never sees the anchored entry and today's rotation is untouched. Its ROM `band_top`
byte is unused (authored `$FF` as a tripwire).

**Runtime, in Step 4a, after the rotation has written the shadow view:**

```
if pcfg_anchor_ch == $FF        -> done; today's path, byte-identical
L = Effects_World_Y[ch] - Camera_Y       (word, may go negative — meaningfully)
if L <= 0    -> the anchored band owns the whole screen: shadow = [anchored @ top 0], count 1
if L >= 224  -> off-screen below: shadow unchanged, count unchanged
else         -> j = first shadow band with top >= L
                shadow count = j; append anchored entry with top = L; count = j+1
```

**The anchored band is TERMINAL — it owns the screen from its line to the bottom.** That is the rule
that makes ordering trivial (truncate, then append: monotonicity cannot be violated) and it is the
shape every real case wants: water, rising lava, a flood line, a fog ceiling inverted. Structure
*below* the surface is not expressible in this parcel, deliberately — see §6.

**Factors.** The anchored band needs its own scroll accumulators, so Step 3 (factor evaluation +
transition lerp) loops `band_count + (anchored ? 1 : 0)` bands, using slot `band_count` for the
anchored one. Its top is irrelevant there; only its factor fields are read. A comptime ensure
requires `band_count + anchored <= MAX_PARALLAX_BANDS` (8).

**Shimmer on exactly at the boundary** then falls out of the data: the plane bands above author
`band_deform_shift_a/b = 15` (off), the anchored band authors a real shift. No new deform mechanism.

**Fill mode.** A scanline-exact boundary requires per-line fill, which is selected today by either
deform table being non-NULL (`parallax.emp:699-701`) and which `engine/buffers` keys the HScroll DMA
length off. Rather than teach that key a second input, a comptime ensure requires an anchored config
to declare at least one deform table. An author who wants an anchored band with no shimmer supplies a
zero table and pays per-line fill honestly.

### 3.3 What the author writes

One anchor, named once, read by both consumers — and the binding already exists, because
`EffectsPreset` carries `ep_parallax` and `ep_patch_world_ys` in the same struct:

```
preset(pal: OJZ_Palette,
       parallax: OJZ_UnderwaterConfig,     // anchor_ch: 0, one anchored band
       patched:  OJZ_TwoChannel,           // channel 0 fires the palette boundary
       patch_world_ys: [224, 314, 0, 0])   // ONE number moves both
```

and at runtime `Effects_SetWorldY(0, y)` — the handle that already exists — moves the palette
boundary and the shimmer boundary together, on the same frame, to the same scanline.

## 4. Why not the alternatives

- **Parallax reads plane space and raster converts into it.** Rejected: it puts a wrapping, 8-px,
  factor-scaled space in charge of a boundary that is a level feature, and every raster consumer
  would need the inverse conversion including a defined answer for the 512-px wrap. It also makes
  the boundary's meaning depend on the BG factor, which is the trap question 3 was pointing at.
- **A third "shared boundary" space both derive from.** Rejected as a name for the thing we already
  have: `Effects_World_Y` IS that space, and it has a public setter and a preset field.
- **One mode flag per band instead of a terminal band.** Rejected: a per-band flag makes the Step 4a
  rotation ordering ill-defined the moment a rotated plane band and a camera-following band interleave.
  Terminate-and-append has no ordering question at all.

## 5. The gate

Three parts, and the first two are numeric and deterministic — no framebuffer capture:

1. **W1 is output-neutral.** Hash `Hscroll_Buffer` over a scripted scroll on a fixture with no
   anchored band, before and after the cells→lines change. Any difference is a defect.
2. **The boundaries agree to the scanline.** With section 0's existing preset (channel 0 = world Y
   224) plus an anchored config, read `Hscroll_Buffer` and find the first line whose FG word departs
   from the band above: it must equal `Effects_World_Y[0] − Camera_Y`, and must equal the raster
   fire line + 1 (`raster.emp:894`'s single conversion). Then `Effects_SetWorldY(0, y)` for several
   y and re-assert. `Debug_Scene_Freeze` (`ojz_scroll_test.emp`) pins the camera so this is
   repeatable.
3. **Clamp behaviour is proved on both edges** by inversion, plus the adjacent legal case: L ≤ 0
   (whole screen anchored), L ≥ 224 (shadow untouched), and L = 1 / L = 223.

Four shapes boot. Freeze first, then the strict suite, then `refreeze --check` + `repin --check`;
this parcel moves bytes (one config byte, one band entry, Step 3/4a code), so pins move.

## 6. What this parcel deliberately does NOT do

- No structure below the anchored boundary (it is terminal). Rising lava and water need nothing more.
- No second anchored band. The mechanism generalises (a list of anchored bands, each terminal until
  the next) without redesign, but nothing needs it today.
- No change to deform phase anchoring. Defect #2's fix is untouched, and the gate in §5.1 proves it.
- No mid-frame writes of anything. Step 4a runs in the main-loop parallax update, exactly where the
  rotation already runs; P-b's VBlank ruling concerns the raster buffer's relative arm words and does
  not reach here.
