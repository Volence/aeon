# Aeon art & data pipeline contract

**Audience:** an outside tool that has never seen this engine and cannot run its build.
Everything here is what the *loaders* expect: formats, budgets, and the guards that
refuse a wrong asset.

## How to read this document

**Every number and format below was derived from source or from a built artifact, and
the source file is named beside it.** Nothing here was copied out of this repo's own
prose documentation. That is a deliberate rule, not a style: a review sweep of this tree
on 2026-09-06/07 found a stated RAM span of 556 bytes that measured 820, a structure
documented at 66 bytes that is 34, a debug surface described as 5 slots that emits 3,
and roughly a hundred stale file citations. `docs/ENGINE_ARCHITECTURE.md`,
`docs/LEVEL_EDITOR_SPEC.md` and `docs/EFFECTS_AUTHORING.md` are good places to find a
*mechanism*; they are not sources for a *number*.

Order of authority used here, and the one you should use if you ever need to check a
figure yourself:

1. the emitted artifact — the built ROM, `s4.lst`, the files under `data/generated/`
2. the source that produces it — a `.emp` module, a `.toml`, a generator in `tools/`
3. prose

Where something could not be established, this document says **NOT ESTABLISHED HERE**
rather than reconstructing a plausible answer. Treat those as questions to ask, not as
gaps to fill in with a guess.

Where a limit is enforced by a specific guard, the guard is named. Where a convention is
enforced by *nothing*, that is said too — those are the ones an outsider will violate,
because there is no feedback.

### One sentence of context, then never again

Aeon is one repo in a suite (Empyrean) that also holds the assembler (`sigil`), an
editor, an emulator and a DAW; nothing about that topology matters to an asset producer,
and it is documented in the `empyrean` repo if you ever need it.

### The two ROMs

`./build.sh` produces `s4.bin` (release) and `DEBUG=1 ./build.sh` produces
`s4.debug.bin`. `./build.sh demo` / `DEBUG=1 ./build.sh demo` produce `demo.bin` /
`demo.debug.bin` for a second, minimal game. **The two sonic4 shapes do not ship the
same tables** — see §9, trap 2. Sizes and checksums change constantly; never pin them.

---

## 1. The hardware surface this engine actually configures

Source: `engine/system/boot_data.emp` (`BootData_VDPRegs`, the positional VDP register
table walked by `engine/system/boot.emp`), plus `engine/system/constants.emp`.

The boot register table writes VDP registers `$00`–`$17`. The values that constrain art:

| reg | boot value | meaning |
|---|---|---|
| `$01` | `$14`, later `$34` then `$74` | display off at boot; `$34` = VInt+DMA+mode 5, display still off (`engine/system/boot.emp:320`); `$74` = display on, set by the game state (`games/sonic4/test/ojz_scroll_test.emp:908`, `games/demo/demo_state.emp:54`). Bit 3 stays 0 → **V28, 224 visible lines**. |
| `$0A` | `$FF` | HInt counter — raster programs rewrite this per fire (§8) |
| `$0B` | `$00` at boot | **at runtime the engine writes `%11` (per-line HScroll) unconditionally**, plus bit 2 for per-column VSRAM when the scene attaches a column table — `engine/level/parallax.emp:1326` and `:1743` |
| `$0C` | `VDP_REG_0C_BOOT = $81` (`engine/system/constants.emp:554`) | **H40, 320 px wide**, no interlace, shadow/highlight off |
| `$0F` | `$02` | autoincrement 2 |
| `$10` | `$11` | **scroll planes are 64 × 64 cells** (512 × 512 px) |
| `$11`/`$12` | `$00` | **window plane disabled** |

Screen: `SCREEN_WIDTH = 320`, `SCREEN_HEIGHT = 224`
(`engine/system/constants.emp:483-484`).

**Shadow-register invariant that matters to anyone authoring an effect.**
`Flush_VDP_Shadow` (`engine/system/vdp_init.emp`) re-blits *every* shadowed register
`$00`–`$12` from `VDP_Shadow_Table` unconditionally at every VBlank. So a mid-frame
register poke is self-undoing and needs no paired reset word; and a register change meant
to *survive* the frame must go through the shadow (`Set_VDP_Reg`), not straight to the
port.

---

## 2. Tiles and the VRAM budget

### 2.1 Tile format

8 × 8 pixels, 4 bits per pixel, **32 bytes per tile** — `TILE_SIZE = 32`
(`engine/system/constants.emp:690`). VRAM is 64 KB = **2048 tiles**
(`TOTAL_TILES = 2048`, `tools/gen_vram_map.py:39`).

Pixel index 0 is the transparent index on this hardware. Where every layer is
transparent the VDP shows the backdrop colour, which this engine leaves at reg `$07` =
`$00` — palette line 0, entry 0 (`engine/system/boot_data.emp`, `BootData_VDPRegs`).
The background importer therefore treats the BG as opaque and **excludes index 0 from
background art** (`tools/png_to_bg_override.py` header: "BG is opaque (index 0
excluded)").

### 2.2 The declared VRAM map

**Placement is declared, not discovered.** Each game carries a `vram.toml` that is the
single placement authority: `games/sonic4/vram.toml` and `games/demo/vram.toml`.
`tools/gen_vram_map.py` reads it, verifies it, and emits three artifacts from it: the
`GENERATED` block inside `games/<game>/config/constants.emp`, the Python mirror
`tools/vram_map.py` that the build tools import their budgets from, and
`docs/generated/vram-map-<game>.md`.

The sonic4 map, read directly from `games/sonic4/vram.toml` (all figures in **tiles**;
byte address = tile × 32):

| tiles | bytes | region | kind | who owns it |
|---|---|---|---|---|
| 0–767 | `$0000`–`$5FFF` | `fg_art_pool` | arena | engine page cache — the streamed foreground act art, 64-tile pages |
| 768–895 | `$6000`–`$6FFF` | `spare_nametable` | plane | reserved `$2000`-aligned run, nothing points at it yet |
| 896–911 | `$7000`–`$71FF` | `dust_puff` | window | resident, 4 anim frames live at once |
| 912–923 | | `dust_spindash` | window | the charge dust's DPLC target |
| 924–927 | | `ring_sparkle` | window | one 2×2 piece, 4 flip orientations |
| 928–956 | | `insta_shield` | window | **streamed**, 29 = the peak DPLC frame |
| 957–958 | | `debug_preset_readout` | window | reserved in every shape, written only in DEBUG |
| **959** | | **FREE** | | **the map's only free tile** |
| 960–991 | `$7800`–`$7BFF` | `character_window` | window | **the player's DPLC target — 32 tiles** (`VRAM_TEST_SONIC`) |
| 992–999 | | `test_obj` | window | |
| 1000–1015 | | `ring_placeholder` | window | |
| 1016–1019 | | `test_marker` | window | |
| 1020–1023 | | `debug_lab_name` | window | 4 contiguous tiles = one 4×1 sprite piece |
| 1024–1423 | `$8000`–`$B1FF` | `bg_region` | arena | **shared background tile art, 400 tiles**, `band_reserve = 80` |
| 1424–1471 | `$B200`–`$B7FF` | `waterline_strips` | window | 48 tiles, engine-owned |
| 1472–1491 | `$B800`–`$BA7F` | `sprite_table` | table | **the sprite attribute table**, reg `$05` |
| 1492–1500 | | `tails_appendage` | window | |
| 1501–1503 | | `debug_bganim_tag` | window | 3 contiguous tiles = one 3×1 piece |
| 1504–1531 | `$BC00`–`$BF7F` | `hscroll_table` | table | **the HScroll table**, reg `$0D`, 896 bytes |
| 1532–1535 | | `debug_raster_tag` | window | 4 contiguous tiles = one 4×1 piece |
| 1536–1791 | `$C000`–`$DFFF` | `plane_a` | plane | **Plane A nametable**, reg `$02` |
| 1792–2047 | `$E000`–`$FFFF` | `plane_b` | plane | **Plane B nametable**, reg `$04` |
| 1920–2047 | `$F000`–`$FFFF` | `window_plane` | plane | declared `overlay_with = ["plane_b"]`; the window feature is **disabled**, so this deliberately aliases Plane B's tail |

`games/demo/vram.toml` declares the same engine regions at the same bases (`fg_art_pool`,
`spare_nametable`, `bg_region`, `waterline_strips`, `sprite_table`, `hscroll_table`,
`plane_a`, `plane_b`, `window_plane`); it replaces the sonic4 game regions with one
`demo_obj` (992, 4 tiles) and a 1-tile `ring_placeholder`, and declares 4 `[[free]]` runs
totalling 139 tiles (`gen_vram_map: demo OK — 11 regions, 139 free tiles`).

**Which regions are fixed vs. pooled vs. reserved:**

* **Fixed by the VDP** (a base register points at them, so they cannot move without
  re-planning the map): `plane_a`, `plane_b`, `window_plane`, `sprite_table`,
  `hscroll_table`. These carry a `register = "vdp:0x0N"` line in the TOML.
* **Pooled / streamed**: `fg_art_pool` (act art, paged in and evicted at runtime) and
  `bg_region` (a per-act blob loaded once at level init).
* **Reserved, no art**: `spare_nametable` (an address reservation), the `debug_*` tags
  (declared in every shape, **written only in DEBUG**), and the 959 free tile.
* **DMA windows** (art streamed in per animation frame, see §5.4): `character_window`,
  `insta_shield`, `dust_spindash`, `tails_appendage`.

`character_window` at tile 960 is **pinned deliberately**: its base is baked into the
player's `art_tile` word, which the replay hash covers, so moving it re-stamps two
fixtures. Growing it (raising `tiles` with the base held) is not moving it.

### 2.3 What `gen_vram_map.py` actually checks — and what it does not

From the docstring and `verify()` in `tools/gen_vram_map.py`, all build-stopping:

* **bounds** — every region and every `[[free]]` run inside tiles 0..2047
* **coverage** — *every tile* must be either a region or a declared `[[free]]` run; a gap
  is an error. Free space has to be intentional.
* **overlap** — two regions may not share tiles unless one names the other in
  `overlay_with`
* **quantum** — a region with `quantum = N` must have `tiles % N == 0`
  (`fg_art_pool` has `quantum = 64`)
* **reserve** — `band_reserve` must be an int in `0..tiles`, and may appear only on
  `bg_region`
* **authority** — `engine-bytebase:NAME` / `engine-tiles:NAME` / `engine-endtiles:NAME`
  each emit a comptime `ensure` cross-checking the TOML against the engine constant

**It does NOT check:** VDP base-register alignment (a nametable region at a non-`$2000`
boundary passes with exit 0 — the TOML says so itself), whether a region is big enough
for the art it holds, DMA queue-slot cost, or runtime residency/lifetime overlap.

### 2.4 Budget breaches — the actual refusal text

Produced by running `tools/gen_vram_map.py` against deliberately broken copies of
`games/sonic4/vram.toml` (2026-09-07, this tree). All exit **1**.

Overlap — `dust_puff` grown from 16 to 20 tiles:

```
gen_vram_map: regions 'dust_puff' and 'dust_spindash' overlap at tile 912 and neither declares overlay_with the other
```

Coverage gap — `test_obj` shrunk from 8 to 4 tiles:

```
gen_vram_map: tiles 996..999 are neither a region nor a declared [[free]] run — declare them (free space must be intentional)
```

Quantum — `fg_art_pool` set to 800 tiles:

```
gen_vram_map: region 'fg_art_pool': tiles=800 violates quantum 64
```

A successful run prints, to stdout:

```
gen_vram_map: sonic4 OK — 22 regions, 1 free tiles
```

The **background tile budget** has its own refusal, in the importer rather than the map
generator. `tools/png_to_bg_override.py::check_tile_budget`, run at
`BG_STATIC_TILE_BUDGET + 1` on this tree:

```
ERROR: 321 unique tiles > 320 static budget.
  bg_region holds 400 tiles, of which band_reserve = 80 are withheld
  for BgAnim band art, leaving 400 - 80 = 320 for this import.
  Simplify the art by 1 unique tiles (flatter / more repetitive),
  or lower band_reserve in games/sonic4/vram.toml and regenerate — that is
  the animation-vs-detail trade, and spending it here costs band space.
```

Those three numbers come from `tools/vram_map.py`, generated from the TOML:
`BG_TILE_CAPACITY = 400`, `BG_BAND_RESERVE = 80`, `BG_STATIC_TILE_BUDGET = 320`.

### 2.5 Reuse and flips

Tile reuse is the entire budget strategy. The background importer dedupes
**flip-canonically** — for each 8×8 tile it takes the minimum over the four flip variants
as the key (`tools/png_to_bg_override.py`, `canonical()` / `flip_variants()`), so a tile
and its mirror cost one tile and differ only by attribute bits.

In a plane nametable cell / sprite tile attribute word:

| bit | meaning |
|---|---|
| 15 | priority |
| 14–13 | palette line (0–3) |
| 12 | V flip |
| 11 | H flip |
| 10–0 | tile index |

Flip bit values verified from `engine/objects/sprites.emp:646-668`: X flip toggles
`$0800`, Y flip toggles `$1000`, both `$1800`. The packing helper is
`vram_art(tile, pal, pri) = (pri << 15) | (pal << 13) | tile`
(`engine/objects/objdef.emp`), with compile-time refinements `pal: 0..3`,
`pri: 0..1`, `tile: 0..$1FFF` — note the `tile` bound is deliberately wide enough to
carry the two flip bits in the same field, it is not a claim that 8192 tiles are
addressable.

---

## 3. Palettes

### 3.1 The four lines and who owns each

CRAM is 4 lines × 16 entries × 1 word = 128 bytes. Ownership, from
`engine/effects/palette.emp` (the "LINE-0 INVARIANT" block) and
`games/sonic4/data/levels/ojz/act1/act_descriptor.emp`:

* **Line 0 — the character.** Written by `Player_ApplyCharacter` from
  `CharacterDef.cd_palette`. **The level must never write it.** A section load that
  touched line 0 would revert the active character's colours on every boundary crossing.
* **Lines 1–3 — the level.** A section palette is exactly **96 bytes = lines 1–3**.
  `engine/effects/palette.emp` is the single runtime writer of these three lines.

This is not merely tidy — it is load-bearing. The palette-variant derive is gated on a
staleness bit that each compose layer sets for itself, so a *runtime* writer of lines 1–3
outside `engine/effects/palette.emp` silently staleness the variant staging image.

### 3.2 On-disk format

A palette file is a flat array of **big-endian 16-bit CRAM words**, 16 words per line, no
header. Measured on this tree:

| file | bytes | words | lines |
|---|---|---|---|
| `games/sonic4/data/generated/ojz/act1/ojz_palette.bin` | 96 | 48 | 3 (CRAM lines 1–3) |
| `art/palettes/SonicAndTails.bin` | 32 | 16 | 1 |
| `art/palettes/sonic.bin` | 32 | 16 | 1 |
| `art/palettes/knuckles.bin` | 32 | 16 | 1 |

Word layout, stated in `engine/effects/palette_dsl.emp:28` and
`engine/effects/palette.emp:126`:

```
0000 BBB0 GGG0 RRR0
```

— **three bits per channel, 9 bits of colour**, each channel's value in bits 3–1 of its
nibble, top nibble zero, bit 0 of every nibble zero. Entry 0 of a line is transparent
where transparency applies.

I verified all four shipped palette files against that mask: **0 of 96 words violate it**
(`w & 0xF111 == 0` for every word). Black is `$0000`; full white is `$0EEE`, which is the
literal `PAL_OP_WHITE_FLASH` holds (`engine/effects/palette.emp:87`).

### 3.3 What an illegal colour word does — **nothing checks it**

Positive control: I searched `tools/`, `engine/` and `games/` for any mask literal of the
form `0x…111` / `$…111` (the shape a legality check would take) — the search returns hits
(`$A11100`, demo art data, the error handler's hex table), so the search works, and
**none of them is a colour-word validator**. `stream_cram` in
`engine/effects/raster_dsl.emp:252` range-checks the CRAM *address*, the odd/even parity,
the line-0 prohibition and the burst count — and does not look at the colour values at
all.

So: a word with bits set outside `0000 BBB0 GGG0 RRR0` is written to CRAM as-is. The VDP
ignores the bits it does not implement, so the practical result is a **silently different
colour**, not an error. Emit canonical words.

### 3.4 The live path

`Palette_Compose` (`engine/effects/palette.emp`) runs once per frame **from the game loop,
not from VBlank** — it is arithmetic, not VDP work — and composes, in this fixed order:

```
base (the section's 96 bytes) -> cycling -> cross-fade -> global operators -> variants
```

* **base** — loaded into `Pal_Base` on a section-boundary crossing
* **cycling** — rotates spans of CRAM entries in place each period
* **cross-fade** — 16-frame per-channel lerp `Pal_Base -> Pal_Target`
  (`PAL_FADE_FRAMES = 16`)
* **operators** — `PAL_OP_FADE_BLACK` / `FADE_WHITE` / `WHITE_FLASH` / `NEG_FLASH`
  (values 1–4, `engine/effects/palette.emp:81-85`). They act on the **level** palette
  only; a full-screen fade that also dims the character is the character system's job.
* **variants** — up to `PAL_MAX_VARIANTS = 2` cheap per-channel transforms of the live
  composed palette, derived into a RAM staging buffer

The compose writes straight into `Palette_Buffer` and ORs a dirty mask
(`Palette_Dirty`, at most `%1110` — bits 1–3, i.e. lines 1–3). CRAM is then rebuilt from
RAM by four pre-built static DMA entries, one per line, 32 bytes each, built once at boot
by `BuildStaticDMA` (`engine/system/buffers.emp:107-137`) and drained every VBlank by
`Process_DMA_Critical`.

So the shipping model is: **CRAM is a mirror of RAM, refreshed every frame.** Anything a
raster program writes to CRAM mid-frame is transient by construction — the next frame's
flush restores the base.

### 3.5 Palette animation

Two mechanisms, both driven from the section's `EffectsPreset`
(`engine/effects/preset.emp:57`):

* `ep_cycle` — a palette-cycle script; up to `PAL_CYCLE_MAX_CHANNELS = 4` channels per
  script (`engine/effects/palette.emp:76`)
* `ep_variants` — a `[*u8; 2]` array of variant descriptors, unused slots must be 0

Both fields are **required, not defaulted**: `ep_cycle` "0 illegal, use `Pal_Cycle_None`".
