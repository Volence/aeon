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

---

## 4. Backgrounds and planes

### 4.1 Plane geometry — one setting, both games, every act

Reg `$10` = `$11` in `engine/system/boot_data.emp`'s register table → **both scroll
planes are 64 × 64 cells = 512 × 512 pixels**, for every act and both games. This is a
boot-time setting; there is no per-act or per-game plane size in this engine, and both
`vram.toml` files declare `plane_a`/`plane_b` at the same 256-tile (`$2000`-byte) bases.
`PLANE_H_CELLS = 64` and `PLANE_V_CELLS = 64` (`engine/system/constants.emp:483` and
`:595`) are the engine-side names.

The window plane is declared in the map at `$F000` but is **disabled** (regs `$11`/`$12`
= 0). `games/sonic4/vram.toml` says why it cannot simply be turned on: with 64 × 64
planes, Plane B at `$E000` spans `$E000`–`$FFFF`, so `$F000` lies *inside Plane B*. There
is no free window space anywhere in the map. Enabling the window means re-planning VRAM
first.

### 4.2 Nametable cell format

One 16-bit big-endian word per cell, bit layout as in §2.5 (priority / palette /
V-flip / H-flip / tile index).

### 4.3 The two planes' roles and how each is filled

| | Plane A | Plane B |
|---|---|---|
| role | **foreground** — the playable terrain | **background** |
| art comes from | `fg_art_pool` (tiles 0–767), streamed | `bg_region` (tiles 1024–1423), loaded once at level init |
| nametable content | built per column/row from the tile cache as the camera moves | one act-wide blob blitted once, plus per-section overrides |

Roles can be **swapped at runtime** — `Parallax_Set_Roles_Swapped(d0)` in
`engine/level/parallax.emp`, gated on the scene capability `CAP_ROLE_SWAP` (`$0400`,
`engine/level/scene_dsl.emp:342`). It writes the two base registers through the settled
shadow door (`Set_VDP_Reg`), so it is a whole-frame swap.

### 4.4 The background layout blob

`BG_LAYOUT_SIZE = 64*64*2 = 8192` bytes (`engine/level/bg.emp:52`) — a **full Plane B
nametable**, all 64 rows live. Measured: `games/sonic4/data/generated/ojz/act1/zone_bg.bin`
is exactly 8192 bytes.

**Byte order is COLUMN-MAJOR**: `blob[col*128 + row*2]`; each column's 64 rows are
contiguous, column stride = 64 rows × 2 B = 128 (`engine/level/bg.emp:17-19`). Every
consumer reads it column-wise, using VDP autoincrement `$80` so one `move.l` writes two
vertically-adjacent cells. `tools/inject_editor_bg.py` transposes the row-major editor
layout into this order at the editor→engine boundary.

The blob is **length-typed at the embed site**, which is the guard:

```
pub data OJZ_Act1_BG_Layout: [u8; BG_LAYOUT_SIZE] = embed("…/zone_bg.bin")
```

(`games/sonic4/data/levels/ojz/act1/act_assets.emp`). A wrong-sized blob is an `array
length mismatch` at build time. That annotation exists because two generators write this
file with **incompatible geometry** — `ojz_strip_gen.py` emits 4096 bytes row-major for a
32-row plane, `inject_editor_bg.py` emits 8192 bytes column-major — and the committed
blob is correct only because the injector happens to run second.

### 4.5 The background tile blob

`games/sonic4/data/generated/ojz/act1/bg_tiles.bin`, measured on this tree: **10 242
bytes**. Format (`engine/level/bg.emp:37-38`, verified against the file):

```
2-byte big-endian byte-length header, then raw 4bpp tiles
```

Header word reads `$2800` = 10 240; payload is 10 240 bytes = **320 tiles**. That is
inside `BG_TILE_CAPACITY = 400` with the 80-tile `band_reserve` unspent, which is why a
BgAnim band can be inserted today.

Nametable indices in the layout are **VRAM-absolute**, rebased at generation time by
`BG_TILE_BASE_SLOT = 1024` (`engine/system/constants.emp:609`) — the editor's blob-local
indices are converted by `tools/inject_editor_bg.py`.

`BG_Init` blits the blob clamped to `BG_TILE_CAPACITY * 32 = 12 800` bytes; the clamp is
the *declared capacity*, not the physical `$8000..$B7FF` run, because the top 48 slots are
the `waterline_strips` region. A maximal blob clamped to the physical run would spray over
the waterline art.

### 4.6 Scrolling arrangement actually used

* **Horizontal: per-line HScroll, always.** Reg `$0B` bits 1:0 = `%11`, written
  unconditionally by `engine/level/parallax.emp:1326` and `:1743`. The HScroll table is
  the full 224-line form: 896 bytes DMA'd from `Hscroll_Buffer` to `VRAM_HSCROLL_TABLE`
  every frame (`engine/system/buffers.emp`, the sixth static DMA entry). The per-cell
  (`%10`) 112-byte variant was **deleted** on 2026-08-26 — it was writing stride 4 where
  the VDP indexes at stride 32, so it only ever fed cell rows 0–3.
* **Vertical: whole-plane by default, per-column when a scene asks.** Reg `$0B` bit 2 goes
  up for exactly the configs that attach a per-column V-deform table. VSRAM is 80 bytes =
  40 word entries; in per-column mode entry `2n` is plane A and `2n+1` is plane B for the
  n-th 16-pixel column, in full-screen mode only entries 0 and 1 are read
  (`engine/effects/raster_dsl.emp`, the `stream_vsram` banner).
* **VSRAM is written at frame top by `Vscroll_Write`, after the HScroll DMA** — the order
  is asserted in `engine/system/vblank.emp:206-209`.

### 4.7 Splitting a background across planes and bands

The background is not split across planes — Plane B carries it all. It is split **into
horizontal parallax bands** within Plane B, up to `MAX_PARALLAX_BANDS = 16`
(`engine/system/constants.emp`, the `MAX_PARALLAX_BANDS` block; raised from 8 on
2026-08-27). A scene declares bands as `layer(world_y:, fa:, fb:, …)` records; each lowers
to a 10-byte `band_entry` (`engine/level/parallax.emp`):

```
band_top_plane      u16   first PLANE LINE of the band (0..511)
band_factor_a_s1    u8    Plane A shift1  (15 = whole-factor zero, "locked")
band_factor_a_s2    u8    Plane A shift2  (15 = single-term factor)
band_factor_b_s1    u8    Plane B shift1
band_factor_b_s2    u8    Plane B shift2
band_factor_ops     u8    bit 0: plane A 0=ADD/1=SUB;  bit 1: plane B
band_deform_shift_a u8    Plane A deform amplitude shift (15 = none)
band_deform_shift_b u8    Plane B deform amplitude shift
band_phase_offset   u8    0..255, added to the deform sample index
```

A scroll **factor** is therefore not a multiplier — it is a pair of shift amounts and an
add/subtract op, evaluated with shifts only. Sentinel 15 means "this term is absent".

**Cost, measured, so you can size a scene:** a scene using all sixteen bands pays
`4664 + 15 × 854 = 17 474` cycles = **13.7 % of the 128 000-cycle NTSC frame**; a scene
that does not use the extra bands pays **zero** for the raised ceiling, because every
per-frame walk is bounded by the live band count, not by the constant.

### 4.8 Animated background bands (BgAnim)

Up to `BGANIM_MAX_BANDS = 4` independent animated strips per act
(`engine/level/bg_anim.emp:93`). A band is a periodic pattern held in a contiguous range
of BG tile slots, rotated in place by re-pointing at one of 8 pre-shifted art banks
(1 pixel per bank). The table is emitted by `tools/inject_editor_bg.py` into
`data/generated/<zone>/<act>/bg_anim.emp` as a word band count followed by 44-byte
records:

```
$00 driver      u16   0 = Camera_X, 1 = Camera_Y, 2 = Logic_Tick (lag-immune)
$02 rate_shift  u16   step = driver_value >> rate_shift
$04 step_mask   u16   pattern period along the axis in px, minus 1
$06 col_shift   u16   log2 of the ROTATION UNIT in bytes
$08 tile_count  u16
$0A vram_dest   u32   VRAM byte address of the band's first slot
$0E banks       [*u8; 8]   bank0..bank7, pre-shifted art, 1 px per bank
```

Verified against the shipped generated file: `_BgAnim_Band0_hdr` is
`[0, 4, 63, 7, 32, $8000]` — driver `Camera_X`, rate shift 4, period 64 px, rotation unit
128 bytes, 32 tiles, VRAM `$8000` (BG slot 0). The struct is pinned by
`ensure(sizeof(bganim_band) == 44, …)` at `engine/level/bg_anim.emp:115`.

**The act boots with BG animation OFF**: the generated `BgAnim_Table` band count is `0`
in the shipped file. The three alternate view tables in that file are `DEBUG`-only and
emit zero bytes in the release shape.

---

## 5. Sprites

### 5.1 The mapping blob

Format, from `engine/objects/mapping_dsl.emp`, `engine/objects/frames.emp` and the
comptime parsers in `engine/objects/dplc.emp`:

```
offset table    one big-endian WORD per frame — byte offset from FILE START to that
                frame's data.  The first word is therefore 2 x frame_count, and
                offset_table_frames(t) = ((t[0]<<8) | t[1]) >> 1
                                              (engine/objects/dplc.emp:257)

frame record    x_min  i8    signed bounding box, FAR EDGES
                x_max  i8
                y_min  i8
                y_max  i8
                piece_count  u16
                piece_count x 8-byte pieces

piece (8 B)     y_off  i16   offset from the object's ORIGIN
                size   u8    (w-1) << 2 | (h-1),  w,h in 8px cells, each 1..4
                link   u8    PAD — the SAT writer overwrites it with its own
                             chain counter; author it as 0
                tile   u16   ADDED to the object's art_tile (so flip bits and a
                             palette override belong in here)
                x_off  i16
```

Byte offsets `FRAME_BBOX_X_MIN..Y_MAX = 0..3`, `FRAME_PIECE_COUNT = 4`,
`FRAME_PIECES = 6` (`engine/system/constants.emp`, the sprite-frame block).

**Frame origin / hotspot**: the origin is the object's `x_pos`/`y_pos`; every piece
carries a signed offset from it. There is no separate hotspot field. The convenience
constructor `centered(half:, w:, h:, tile:)` builds the symmetric case
(bbox `-half..+half`, piece offset `-half`); `piece(x:, y:, w:, h:, tile:)` is the
general form, wanted whenever art does not sit centred (a spring's squash frame sinks 4 px
and its extend frame lifts 12 px off the same origin).

The size-byte packing is pinned by two independently-spelled `ensure`s in
`engine/objects/mapping_dsl.emp` — `(w-1)` in bits 3:2, `(h-1)` in bits 1:0. **Four cells
is the VDP's maximum piece width**, which is what fixes the debug lab's name tags at four
characters (`games/sonic4/vram.toml`, `debug_lab_name`).

**Measured frame counts** (first word of each shipped blob, this tree):

| asset | mappings | DPLC | frames |
|---|---|---|---|
| Sonic | `data/mappings/sonic.bin` 7 296 B | `data/dplc/optimized/sonic.bin` 2 244 B | **224** |
| Knuckles | `data/mappings/knuckles.bin` 7 592 B | `data/dplc/knuckles.bin` 2 400 B | **251** |
| Tails | `data/mappings/tails.bin` 7 152 B | `data/dplc/optimized/tails.bin` 1 658 B | **251** |
| Tails' tails | `data/mappings/tails_tail.bin` 712 B | `data/dplc/optimized/tails_tail.bin` 268 B | 45 |
| insta-shield | `data/mappings/insta_shield.bin` 200 B | `data/dplc/insta_shield.bin` 30 B | **8** |

**One `mapping_frame` byte indexes BOTH tables.** Emit the pair or neither. The guard, in
`games/sonic4/data/collision/collision_data.emp`, verbatim:

> `Map_Sonic declares {…} frames and DPLC_Sonic {…} — one mapping_frame byte indexes BOTH, so the shorter table is read past its end and a byte of the blob placed after it is taken as a frame offset. Re-export the PAIR (tools/dedup_art.py), never one half. DOES NOT COVER: whether either count matches what Ani_Sonic's frame bytes reach — AnimateSprite bounds no frame byte at all (engine/objects/animate.emp, LS-9a) — nor whether corresponding frames describe the same art`

A second guard catches the half-empty case: a drawn frame whose DPLC loads nothing renders
whatever the character window last held (so it reads as a stutter, not as corruption), and
a loaded frame that draws nothing spends DMA slots on tiles no piece references
(`empty_frame_mismatches(...) == 0`).

Two size ceilings, both `ensure`d in the same file: `_map_sonic.len <= $7FFF` and
`_dplc_sonic.len <= $7FFF`, because the offset tables are **signed** word offsets.

### 5.2 The animation script

Source: `engine/objects/animate.emp:1-31` (the format header) and its dispatch at `:116`.

```
AnimTable:  dc.w Anim0-AnimTable, Anim1-AnimTable, ...
Anim0:      dc.b duration, frame0, frame1, ..., control_code [, arg]
            even
```

Byte 0 of a script is the **duration** (the timer reload). Bytes from index 1 are either
mapping-frame indices or control codes. The classifier is a single test —
`cmpi.b #AF_SET_FIELD, d0 / bhs` — so:

**Frame bytes are `$00`–`$F6`. Control codes are `$F7`–`$FF`.** An `$80`+ frame byte is
data, not a command.

| code | name | arguments |
|---|---|---|
| `$FF` | `AF_END` | — restart from the first frame |
| `$FE` | `AF_BACK` | 1 byte: rewind count. **N = 0 loops forever inside one frame** (a DEBUG rail catches it) |
| `$FD` | `AF_CHANGE` | 1 byte: new anim ID. **Must not name the current animation** — it silently fails to restart and the object freezes on that frame |
| `$FC` | `AF_ROUTINE` | — increment the routine counter by 2 |
| `$FB` | `AF_DELETE` | — delete the object |
| `$FA` | `AF_CALLBACK` | 3 bytes: target_hi, target_lo, 0 |
| `$F9` | `AF_SOUND` | 1 byte: sound id |
| `$F8` | `AF_COLLISION` | 1 byte: collision type |
| `$F7` | `AF_SET_FIELD` | 3 bytes: sst_offset, value, 0 |

Events (`$FA`–`$F7`) execute inline and reading continues; several can chain before a
frame byte. **Every event consumes an even number of bytes** — a format invariant scripts
may rely on, and what keeps an `even`-terminated script stable.

A duration byte equal to `DUR_DYNAMIC` substitutes the caller's speed-scaled hold instead
of a static count.

### 5.3 The frame-byte upper bound — **strictly less than**, and several assets sit at zero margin

`AnimateSprite` writes any byte `$00`–`$F6` straight into `Sst.mapping_frame` and
**nothing at runtime compares it against the mappings table's frame count**. A table of N
frames has valid indices `0..N-1`, so the bound is

```
max reachable mapping_frame  <  offset_table_frames(mappings)
```

**Strictly less than.** `tools/anim_frame_bound.py` (landed 2026-09-07) enforces it
post-link against the built ROM and listing. Its docstring explains why the direction
matters: several assets legitimately use their last frame, so written `<=` the gate would
be green on a real overrun, and written `<` on a wrongly-derived maximum it would be red
on correct art. Its `--selftest` proves both directions per table.

Run on `s4.bin` / `s4.lst` from this tree, exit 0:

| anim table | mappings | anims | max script byte | max reachable | frames | **margin** |
|---|---|---|---|---|---|---|
| `Ani_DustPuff` | `Map_DustPuff` | 1 | `$03` | `$03` | 4 | **0** |
| `Ani_DustSpindash` | `Map_DustSpindash` | 1 | `$06` | `$06` | 7 | **0** |
| `Ani_InstaShield` | `Map_InstaShield` | 1 | `$07` | `$07` | 8 | **0** |
| `Ani_Knuckles` | `Map_Knuckles` | 24 | `$DE` | `$DE` | 251 | 28 |
| `Ani_RingSparkle` | `Map_RingSparkle` | 1 | `$03` | `$03` | 4 | **0** |
| `Ani_Sonic` | `Map_Sonic` | 24 | `$C4` | `$C4` | 224 | 27 |
| `Ani_Spring` | `Map_Spring` | 2 | `$02` | `$02` | 3 | **0** |
| `Ani_Tails` | `Map_Tails` | 24 | `$B4` | `$B4` | 251 | 70 |
| `Ani_TailsAppendage` | `Map_TailsAppendage` | 24 | `$28` | `$28` | 45 | 4 |

`Ani_Particle` is a tenth table that ships only in `s4.debug` (see §9, trap 2) and also
sits at margin 0.

**"Max reachable" is not the same as "max script byte."** Three other things write
`Sst.mapping_frame`, and the gate models all three:

* `Player_ApplyTilt` **adds** a ground-angle block (`block << TILT_*_SHIFT`, four blocks)
  to the WALK and RUN rows for all three characters
* `TailsAppendage_Main` **adds** a roll-direction bank of 0/4/8/`$C`
* `Climb_Animate` and the ledge bodies write frames **directly**, bypassing the script
  entirely (Knuckles only)

So a script byte is not the whole story for a player character: adding an animation row
near the top of a sheet can push the *reachable* maximum past the table end even though no
authored byte does.

### 5.4 DPLC — streaming player art

Format (`engine/objects/dplc.emp:1-8`):

```
offset table  one word per frame, offset from file start (same shape as mappings)
frame data    u16 entry_count, then entry_count entry words
entry word    bits 15-12 = tile_count - 1  (so 1..16 tiles)
              bits 11-0  = tile_start      (tile INDEX into the art sheet)
```

`DPLC_TILE_COUNT_BITS = 4`, `DPLC_TILE_START_BITS = 12`,
`DPLC_MAX_TILES_PER_ENTRY = 16`, `DPLC_ADDRESSABLE_TILES = 4096`
(`engine/objects/dplc.emp:103-107`). The 12-bit field is a **hard ceiling on sheet
length**: a sheet with more than 4096 tiles has tiles no entry can point at, and a
generator that tries wraps into the low tiles.

Measured sheet sizes on this tree (uncompressed 4bpp, 32 B/tile):

| sheet | bytes | tiles | headroom to 4096 |
|---|---|---|---|
| `art/optimized/characters/sonic.bin` | 101 056 | 3 158 | 938 |
| `art/optimized/characters/knuckles.bin` | 130 944 | **4 092** | **4** |
| `art/optimized/characters/tails.bin` | 116 320 | 3 635 | 461 |
| `art/optimized/characters/tails_tail.bin` | 8 896 | 278 | |

Knuckles is four tiles under the addressable ceiling. Treat 4096 as a real wall.

**Entry count is a DMA queue-slot cost, and it is the binding constraint.** Each entry is
one enqueue into the Important queue, which has `DMA_IMPORTANT_SLOTS = 12`
(`engine/system/constants.emp`), and `DPLC_ENTRY_RESERVE = 2` slots must be left free for
the art-streaming landing (`engine/objects/dplc.emp:84`). So the wall is
**peak entries + 2 ≤ 12**, i.e. **10 entries**. Measured peaks, from
`engine/objects/dplc.emp:23-27`:

```
optimized/sonic.bin   10 entries    knuckles.bin              5
optimized/tails.bin    2            optimized/tails_tail.bin  1
generated/dust/dplc_dust.bin  1
```

Sonic sits at exactly 10 — the wall, and it was re-cut to get there. What happens above it
is not graceful: at 13 entries the 13th enqueue returns carry-set, the handler bails
**before** committing `prev_frame`, and every subsequent frame re-enqueues all 12 and drops
the 13th **forever**. That entry's tiles never load.

⚠ **The comptime wall cannot see the whole cost.** A transfer whose ROM source straddles a
`$20000` boundary is split by the queue into two entries, so a frame really costs
`entries + straddles`, and whether an entry straddles depends on where the art *landed* —
a link-time fact no parser of the blob can reach. `tools/dplc_straddle.py --gate` measures
actual slots and runs in `build.sh`; the comptime walls are necessary and not sufficient.

**The character DMA window** is `character_window`, tiles 960–991 = **32 tiles**
(`games/sonic4/vram.toml`; the constant is `VRAM_TEST_SONIC`, with its declared extent
published beside it as `VRAM_TEST_SONIC_TILES`). Every DPLC frame's tiles land there, so
**no single frame may need more than 32 tiles**.

### 5.5 Sprite budgets

Engine-side, from `engine/system/constants.emp`:

| constant | value | what it bounds |
|---|---|---|
| `MAX_VDP_SPRITES` | 80 | SAT entries; the shipped table is 20 tiles = 640 bytes at `$B800` |
| `VDP_SPRITE_X_OFFSET` / `_Y_OFFSET` | 128 / 128 | the VDP's coordinate bias |
| `PRIORITY_BANDS` | 8 | render bands; `render_flags` bits 5–7 carry the band, so 0..7 is structural |
| `SPRITES_PER_BAND` | 32 | objects queued per priority band |
| `SCANLINE_BANDS` | 7 | 224 / 32 = seven 32-scanline bands |
| `SCANLINE_SPRITE_LIMIT` | 24 | max sprite **pieces** charged per 32-line band |

`SCANLINE_SPRITE_LIMIT` is **a soft heuristic that undercounts by design**
(`engine/objects/sprites.emp:363-386`, stated there): the early-out skips the commit too,
so the first 24 sprites in a frame are never charged, and multi-sprite children bypass the
budget entirely. That comment is explicit that the VDP drops excess per-line sprites in
hardware regardless — the budget only shapes *which* sprites drop.

**The hardware per-line sprite count and per-line pixel limits are NOT ESTABLISHED HERE.**
No constant in this tree names them, and `engine/objects/sprites.emp` refers to the
hardware drop without quoting a figure. Take them from a VDP hardware reference, not from
this document.

Per-frame piece count per object is stored in `Sst.sprite_piece_count`, a **byte**
(`engine/objects/sst.emp`), refreshed from the frame's own count word. I found **no
build-time guard bounding a frame's piece count**.

### 5.6 Art size and alignment guards

Every character data module carries these, and their messages are worth knowing because
they are what you will see:

* `ensure((_art_sonic.len % TILE_SIZE) == 0, "Art_Sonic is not a whole number of tiles")` —
  with its own stated limit: *"A sheet truncated by a whole multiple of TILE_SIZE passes
  this and every other guard in this file, and the frames whose runs fell off the end DMA
  whatever the link put after Art_Sonic."*
* an even-length guard on each of the three character blobs — an odd-length blob leaves
  the label after it on an odd address, and the 68000 takes an address error.

Character art is **uncompressed**. There is no sprite-art compression format in this
engine: Nemesis, Kosinski, Enigma and UFTC have all been removed.
