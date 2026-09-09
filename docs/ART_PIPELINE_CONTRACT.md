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

### Companion document

`docs/ART_PIPELINE_CONTRACT_ADDENDUM.md` answers four questions this document does not: the
`editor_bg_override.json` schema and the importers' options (§A1), the effects schema pinned
at a named `empyrean` revision (§A2, which discharges one of the gaps in §10 below), whether
a background **tileset** can be replaced between sections as against its **nametable** (§A3),
and what OJZ act 1 allocates today (§A4).

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

**THE MAP IS THE SAME IN EVERY BUILD SHAPE, and that is a design rule rather than a
coincidence.** There is one `vram.toml` per GAME, never per shape. Regions that only
DEBUG writes — the four debug tags — are still RESERVED in release, and their own
comments say why: a VRAM reservation is not a ROM byte, and a shape-conditional region
would make the map mean two different things while `gen_vram_map.py`'s coverage and
adjacency checks run over one 0..2047 span. So "VRAM per shape" has no per-shape axis to
report here: the answer for release and for DEBUG is this table, and the only figure that
moves with a shape is ROM, not VRAM.

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
| 1024–1399 | `$8000`–`$AF7F` | `bg_region` | arena | **shared background tile art, 376 tiles**, `band_reserve = 56` |
| 1400–1447 | `$AF80`–`$B57F` | `waterline_strips` | window | 48 tiles, engine-owned; its base is DERIVED from `BG_TILE_CAPACITY`, so it slides when the BG arena is resized |
| 1448–1471 | `$B580`–`$B7FF` | `spring` | window | 24 tiles, resident — the vertical + horizontal spring sheets (2026-09-07) |
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
totalling 163 tiles (`gen_vram_map: demo OK — 11 regions, 163 free tiles`).

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
literal `PAL_OP_WHITE_FLASH` holds (`engine/effects/palette.emp`, `PAL_OP_WHITE_FLASH`).

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
`engine/objects/dplc.emp`'s module header (the measured-peaks table):

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

---

## 6. Level terrain

### 6.1 The vocabulary is NOT the classic Sonic one — read this first

If you are coming from a Sonic 1/2/3 disassembly, the words do not map across. **There is
no 16×16-pixel block table and no 128×128-pixel chunk table in this engine.**

Positive control, run on this tree: a case-insensitive search for `chunk` across
`engine/**/*.emp` exits 1 (no matches), and the same search across `games/**/*.emp` also
exits 1; a search for `128x128` / `128 x 128` across both exits 1. As a control that the
search machinery works, `BLOCK_TILE_SIZE` returns 12 matches in
`engine/system/constants.emp` alone. The word `chunk` **does** survive in `tools/` — about
twenty files — but always as the *donor* vocabulary: `ojz_common.load_chunk_map` and
`collision_pipeline.bake_cell` parse sonic_hack's Sonic 2 data at import time, and that
shape never reaches the ROM.

What this engine has instead, from `engine/system/constants.emp` and
`tools/ojz_block_gen.py`:

| unit | size | source |
|---|---|---|
| **tile** | 8 × 8 px, 32 B | `TILE_SIZE = 32` |
| **block** | **16 × 16 tiles = 128 × 128 px** | `BLOCK_TILE_SIZE = 16`, `BLOCK_TILE_SHIFT = 4` |
| **section** | **16 × 16 blocks = 256 × 256 tiles = 2048 × 2048 px** | `BLOCKS_PER_SECTION_AXIS = 16`, `SECTION_SIZE = $0800`, `SECTION_SIZE_SHIFT = 11` |
| **act** | a `grid_w × grid_h` grid of sections | `MAX_ACT_SECTIONS = 48` |

So "16 × 16 block" here means **sixteen tiles square**, not sixteen pixels square. The
shipped OJZ act 1 is a 3 × 3 grid = 9 sections (`GRID_W`/`GRID_H` in
`games/sonic4/data/levels/ojz/act1/act_descriptor.emp:111-112`, pinned by
`ensure(GRID_W * GRID_H == 9, …)` at `:363`).

Both act axes are bounded by `ensure((GRID_W << SECTION_SIZE_SHIFT) <= $8000, …)` — the
camera's world coordinates are signed words, so an act may not exceed **32 768 px** on
either axis.

### 6.2 The block record

A raw block is **768 bytes** (`BLOCK_RAW_SIZE`), laid out as
(`tools/ojz_block_gen.py` header, mirrored by `engine/system/constants.emp`):

```
bytes   0-511   512 B nametable   16x16 cells x 2 bytes, ROW-MAJOR
bytes 512-639   128 B collision plane A   16 cols x 8 rows x 1 byte, row-major
bytes 640-767   128 B collision plane B
```

The two collision planes are the two "paths" a Sonic loop needs. A collision **cell** is
therefore **8 px wide × 16 px tall** — `COLL_CELL_W = 8`, `COLL_CELL_H = 16`, both derived
in `engine/system/constants.emp` from the block geometry rather than typed. That derivation
holds only because `Cache_Top_Row` is kept even.

### 6.3 The section file

One file per section, `data/generated/<zone>/<act>/sec{N}_blocks.bin`
(`tools/ojz_block_gen.py`):

```
1024 B   block index table — 256 entries x 4 bytes
         each entry is a BYTE OFFSET from file start
         0            = empty / air block
         bit 31 set   = RAW DIRECT: the offset points at an uncompressed
                        768-byte block inside the dictionary region

dict     K raw 768-byte blocks (K swept 0..3 per section for minimum total).
         Double duty: their own storage AND the LZ window pre-seed for every
         compressed block in the section.

blocks   concatenated S4LZ-compressed blocks, compressed against that dict window
```

Per-section dictionary lengths are emitted as comptime constants into
`sec_block_dicts.emp` (all nine sections are 768 = K = 1 on this tree) and consumed by the
act descriptor. `BLOCK_INDEX_SIZE = 1024`, `RAW_DIRECT_BIT = 0x80000000`,
`MAX_DICT_BLOCKS = 3`.

Measured on this tree: `sec0_blocks.bin` is 8 852 B = 1024 index + 768 dict + 7 060 B of
compressed blocks.

### 6.4 The local tile-index map

`sec{N}_local_map.bin` — a table of big-endian `u16` entries mapping a block nametable
word's **11-bit LOCAL tile index → the GLOBAL VRAM slot**
(`games/sonic4/data/generated/ojz/act1/sec_local_maps.emp` header). The engine translates
local→global at block decode. Identical maps are stored **once** and duplicate sections
alias via a zero-byte `equ` — on this tree section 4 aliases section 2.

This indirection is what lets the act art pool be paged: a block's nametable words are
stable, and the map is what points them at wherever the page currently lives.

### 6.5 Collision — the five ROM tables and the attr byte

Collision is looked up as a **single byte per cell**, read out of the tile cache by
`Collision_GetType` (`engine/level/collision_lookup.emp`): X is `>> 3`, Y is `>> 3` then
`>> 1`, and `d3` selects plane A or B. **0 = air** (`CTYPE_AIR = 0`).

That byte is an index into a **256-slot shared collision vocabulary** — five ROM tables,
all addressed by the same byte, embedded by
`games/sonic4/data/collision/collision_data.emp`. Measured file sizes:

| table | bytes | shape |
|---|---|---|
| `heightmaps.bin` | 4 096 | 256 slots × 16 height bytes (one per block column) |
| `heightmaps_rot.bin` | 4 096 | the rotated (horizontal-probe) twin |
| `angles.bin` | 256 | one angle byte per slot |
| `solidity.bin` | 256 | `SOLID_NONE 0 / SOLID_TOP 1 / SOLID_LRB 2 / SOLID_ALL 3` |
| `crossover.bin` | 256 | the loop-crossover mark: `XOVER_NONE 0 / TO_A 1 / TO_B 2` |

`PROFILE_LEN = 16`, `MAX_PROFILES = 256` (`tools/collision_pipeline.py`). Slot 0 is
reserved as air.

**How visual tiles bind to solidity and angle: they do not.** The block record carries the
nametable and a *parallel* per-cell attr plane; nothing derives collision from the tile a
cell displays. An author paints art and collision independently, and the bake interns the
result.

### 6.6 The S3K-derived import

`tools/import_sk_collision.py` reads Sonic & Knuckles' `Height Maps.bin`,
`Height Maps Rotated.bin` and angle table from an out-of-repo `skdisasm` checkout and
writes the **base bank** at `games/sonic4/data/collision/base/`. That bank is the stable
shape vocabulary the editor's palette shows. Every non-air base shape gets solidity
`SOL_ALL` (3); the editor picks per-cell solidity and the bake resolves it.

This is a **manual re-bake tool — `build.sh` does not run it**. Its refusal when the donor
is absent, verbatim from the source:

```
import_sk_collision: skdisasm donor not found at {SK}. This is a MANUAL re-bake
tool (tools/regenerate-level.sh); set AEON_SKDISASM_DIR to your skdisasm
checkout. The build does NOT run this — it uses the committed collision tables
under games/sonic4/data/collision/.
```

The runtime tables under `games/sonic4/data/collision/` are then **overwritten** by the
per-section bake (`ojz_strip_gen` / `tools/gen_collision_data.py`) with the *sparse
interned* set — only the shape/flip/solidity/crossover combinations actually painted reach
the ROM. The committed bytes are the baked ones.

### 6.7 The authoring cell word

The editor writes one 16-bit **big-endian** word per 8 px cell, per plane, into
`data/editor/<zone>/<act>/section_N.collattr.bin` (plane A) and `…collattrb.bin` (plane B).
Measured: each is 131 072 B = 256 × 256 × 2, and `section_N.tiles.bin` is 131 072 B on the
same grid. Bit layout (`tools/collision_pipeline.py::bake_plane_cell`):

| bits | meaning |
|---|---|
| 9:0 | base-bank shape index |
| 10 | X flip |
| 11 | Y flip |
| 13:12 | **this plane's** solidity (bit 12 = top, bit 13 = lrb) |
| 15:14 | crossover mark |

⚠ **The same two top bits mean something different in the donor word.** In the Sonic 2
donor chunk-entry word that `bake_cell` consumes, bits 15:14 are path-B solidity. The two
constants share a value and deliberately do not share a name. Do not carry a donor word
into the per-plane space.

A 16 px collision row samples the **top tile row** of the pair (even rows only).

Two hard refusals in that bake, both raising rather than warning:

* **`XOVER == 3` is reserved and raises.** 3 is the value a producer that *clamps* into a
  2-bit field lands on, so it is made the loudest value rather than the quietest.
* **A self-mark raises** — a plane-A word carrying `XOVER_TO_A`, or plane-B carrying
  `XOVER_TO_B`, provably does nothing (you must already be on a plane to read its mark),
  so it is treated as authoring intent that silently fails.

If `section_N.collattr.bin` is the wrong length the bake **warns and ignores the editor
collision for that section** rather than failing:

```
  WARNING: {path_a} is {len}B, expected {expect}; ignoring editor collision for sec {N}
```

That is a soft failure and worth knowing about: wrong-sized collision does not stop a
build, it silently reverts a section to air.

### 6.8 Objects and rings

Per section, generated by `tools/ojz_entity_gen.py` into `entity_data.emp`:

* **object list** — packed 3-word records `{ x, y, flags | (type << 8) | subtype }`,
  terminated by `$FFFF`. `type` indexes the section's own minimized type table.
* **type table** — a count byte, a pad byte, then `count` `ObjDef` pointers (`dc.l`), so
  the first pointer sits at even offset 2.
* **ring list** — `dc.w X, Y` pairs, **X-sorted**, terminated by a longword 0.

Capacity, from the generator's own emitted stats block: **128 rings per section ring
buffer**; the shipped act's worst 2×2-block pressure is 20.

### 6.9 The act descriptor

`games/sonic4/data/levels/ojz/act1/act_descriptor.emp` builds one `Act` record naming the
grid, the start position, the act-wide BG blob and tile blob, the parallax config, the
paged art pool table, the per-section local maps, an edge mode and a per-act art byte
budget. Each of the nine sections is a `Sec` record (`engine/structs.emp:145`):

```
$00 sec_block_index      *u8   the 256-entry block index table
$04 sec_objects          *u8   object list ($FFFF-terminated)
$08 sec_rings            *u8   X-sorted ring entries
$0C sec_parallax_config  *u8   0 = defer to the preset / act default
$10 sec_bg_layout        *u8   0 = use the act-wide BG
$14 sec_type_table       *u8   count, pad, then ObjDef pointers
$18 sec_block_dict       *u8   raw dict region (LZ pre-seed)
$1C sec_effects          *u8   EffectsPreset* — REQUIRED, no default
$20 sec_block_dict_len   u16   dict bytes (768 x K, K <= 3)
```

`sec_effects` is required deliberately: `Effects_InstallPreset` dereferences it without
testing, and the only null test is inside `if DEBUG == 1` — so an omitted binding would
compile clean, ship, and send the release build into the 68000 vector table. Dropping the
default makes the omission a build error in every shape at zero ROM cost.

---

## 7. The build: compression, generators, registration, and what a wrong asset does

### 7.1 Compression formats and where each is required

| format | where it is required | decoder |
|---|---|---|
| **ZX0** (modern / V2, `salvador` default) | the act art pool's 64-tile pages, `pm_form = ART_PAGE_FORM_ZX0 (0)` | `engine/compression/zx0_resume.emp` (resumable, sliced across idle time) |
| **raw direct** | a page the per-page election found not worth compressing, `pm_form = ART_PAGE_FORM_RAW (1)` — DMA'd straight from ROM | none |
| **S4LZ v3** | the per-section block stream, with per-section dictionaries | `engine/compression/s4lz.emp` |
| **none** | all sprite art, all palettes, both nametable blobs, all collision tables | — |

Every compressed art blob starts with a **4-byte wrapper**
(`engine/system/constants.emp:341-346`):

```
u16 BE  uncompressed size
u8      flags
u8      version   ART_VER_S4LZ = 1, ART_VER_ZX0 = 2
```

`ART_HDR_SIZE = 4`. Note the runtime dispatches art pages on the manifest's `pm_form`
byte, **not** on the wrapper version.

**S4LZ v3 stream format** (`engine/compression/s4lz.emp:14-33`) — word-aligned throughout,
read with word fetches only:

```
header (4 B)  $00.w uncompressed size (BE, bytes)
              $02.b flags (bit 0 = tile-delta)
              $03.b version (1 = v3; this decoder is v3-ONLY)

per sequence  token WORD = [token.b][offmark.b]
              token high nibble = literal word count (0-14, 15 = extension word)
              token low  nibble = match   word count (0-14, 15 = extension word)
              token == $00 = end of stream (so the EOS word is $0000)
              offmark.b = match_offset/2 for byte offsets 2..510 (short form),
                          $00 = long form (a u16 BE offset word follows the literals)

order         token word, [literal count word], literals,
              [offset word — long form only], [match count word]
```

Match offsets must stay below `$8000` because the decoder's `suba.w` sign-extends:
destination buffers ≤ 32 766 bytes plain, and `dest_written + dict_len ≤ 32 766` on the
dictionary entry. The deepest shipped use is a 768-byte block slot plus a 2 304-byte dict
= 3 072.

**Art pool paging.** `ART_POOL_PAGE_TILES = 64`, so a page is
`ART_POOL_PAGE_BYTES = 2048` bytes. The manifest is a stride-`sizeof(PageManifest)` array
(`engine/structs.emp:71`):

```
$00 pm_source  *u8   page blob pointer (ZX0 wrapper, or raw payload)
$04 pm_tiles   u16   decompressed tile count (landing DMA length = tiles * 32)
$06 pm_form    u8    ZX0 = 0, RAW = 1
$07 pm_flags   u8    bit 0 = PINNED (never evicted)
```

Measured on this tree, from
`games/sonic4/data/generated/ojz/act1/ojz_act_pool_manifest.json` and the emitted
`ojz_act_pool.emp`: **10 pages, 612 pool tiles**, pages 0/1/7/8/9 pinned, page 9 short at
36 tiles, every page `pm_form = 0` (ZX0). Compressed sizes range 682–1 466 B against the
2 048 B raw page.

⚠ **Page blobs are padded to even length at generation** (one dead byte past the ZX0 end
marker). An odd blob once landed the manifest table at an odd address and boot took an
address error. `sigil` does not auto-align data declarations.

### 7.2 The generators and where their outputs land

`tools/regenerate-level.sh` orchestrates the level bake. The pieces:

| tool | reads | writes |
|---|---|---|
| `tools/import_sk_collision.py` | out-of-repo `skdisasm` (`AEON_SKDISASM_DIR`) | `data/collision/base/*.bin` + defaults in `data/collision/` |
| `tools/gen_collision_data.py` | the attr-set pipeline | the five `data/collision/*.bin` tables |
| `tools/ojz_strip_gen.py` | editor `section_N.{tiles,collattr,collattrb}.bin`, editor `<zone>/<act>/palette.bin`, sonic_hack donor | `sec{N}_strips_a.bin`, `act_pool_page{N}.bin`, the pool manifest, `zone_bg.bin`, `ojz_palette.bin` (a MIRROR of the authored palette — the donor only SEEDS it when absent), `sec{N}_local_map.bin` |
| `tools/ojz_block_gen.py` | the strip files | `sec{N}_blocks.bin`, `sec_block_dicts.emp` |
| `tools/ojz_entity_gen.py` | editor `section_N.{rings,objects}.json`, `data/editor/objects.json` | `entity_data.emp` |
| `tools/png_to_bg_override.py` | a PNG | `editor_bg_override.json` |
| `tools/inject_editor_bg.py` | `editor_bg_override.json` | overwrites `zone_bg.bin` + `bg_tiles.bin`, and emits `bg_anim.emp` + `bg_anim_banks.bin` |
| `tools/effects_gen.py` | editor scene/preset documents | `effects_scenes.emp` |
| `tools/sfx_transcode.py` | `skdisasm` SMPS SFX sources | `data/sound/sfx/sfx_NN.asm`, `sfx_NN_patches.asm`, `sfx_table.asm` |
| `tools/salvador` (vendored, built by `build.sh`) | a raw page | the `.zx0` bitstream |

Everything under `games/<game>/data/generated/` is **auto-generated and committed**; every
such file carries a `DO NOT EDIT` banner naming the tool that owns it.

`build.sh` gates on level-data staleness (`tools/level_staleness.py`): a canonical build
**fails** and names `tools/regenerate-level.sh`; `FAST=1` auto-re-bakes.

`tools/sfx_transcode.py` is the one worth calling out for an asset producer even though it
is audio: **reserved channels (FM1, FM2, FM6, DAC) may NOT appear**; any SFX targeting them
raises a build error, as do unknown coord-flag bytes and unknown voice sub-macros.

### 7.3 How a resource is registered and loaded

Three steps, all of them source edits:

1. **Embed it.** A `.emp` data module declares
   `pub data Name = embed("games/<game>/data/…/file.bin")`. Where the length is a
   contract, annotate the type — `pub data X: [u8; N] = embed(…)` — and a wrong-sized file
   becomes an `array length mismatch` at build time. That is the single cheapest guard
   available to you and it is used sparingly today.
2. **Point something at it.** A `Sec` field, an `Act` field, an `EffectsPreset` field, a
   `CharacterDef` field, or an `ObjDef` literal.
3. **Place it.** `games/<game>/map.toml` is the declared ROM placement contract, consumed
   by the sigil chainer: section order, island anchors, the `boot_data` hole, the
   object-bank budget. Placement is *declared*, not discovered.

One placement invariant that will bite anyone appending to the ROM: **the fault-handler
island must remain the final byte-emitting section in every shape that carries it**
(`games/sonic4/map.toml`). The vendored MD Debugger blob locates its symbol appendix
through PC-relative displacements baked into opaque blob bytes that assert
"symbol table == blob end"; anything placed between the blob and `EndOfRom` silently breaks
every backtrace. There is a hard build guard for this in sigil's chainer.

### 7.4 What a wrong asset does — the refusal, verbatim

Most asset contracts in this engine are enforced by `ensure(...)` — a comptime assertion in
a `.emp` module that costs zero ROM bytes and fails the build with its own message. This is
what one looks like when it fires. Produced on this tree by building with the poison module
`games/sonic4/test/poison/poison_cram_four_words.emp` named as an extra entry, exit **1**:

```
warning: 14 warnings, module.path-mismatch 14; SIGIL_WARNINGS=full to list
error: native build (sonic4 plain): build_program: 1 error(s);
  [Error] stream_cram: 4 colours exceeds RASTER_BURST_MAX_CRAM (3) — the per-fire CYCLE
  budget for the CHEAP burst class, not a FIFO limit. […] @ Span { source: SourceId(11),
  start: 19879, end: 20899 }
```

Recognise: `error: native build (<game> <shape>): build_program: N error(s);` followed by
one `[Error] <the guard's own message> @ Span { … }` per failure.

**A second failure road exists and looks nothing like that one.** An `ensure` whose
condition contains `extern(...)` — every cross-namespace constant mirror and every
RAM-reservation span, 135 sites — is lowered to a link assert, evaluated after layout, and
reported as:

```
declared-chain drift guard FIRED: N error(s); first Some(Diagnostic { .. })
```

with **no `[Error]` token anywhere** (`tools/emp_expect_fail.py`, which documents both
formats because the difference silently voided a whole test family). If you are grepping a
build log for failures, grep for both.

Guards you will meet as an asset producer, and what each does *not* cover — each of these
states its own limits in its message, and the limits are as load-bearing as the check:

| guard | where | catches | explicitly does NOT catch |
|---|---|---|---|
| mappings/DPLC frame-count equality | `collision_data.emp`, `tails_data.emp`, `knuckles_data.emp` | one table shorter than the other | whether the animation script's frame bytes reach either count; whether corresponding frames describe the same art |
| `empty_frame_mismatches == 0` | same | a drawn frame whose DPLC loads nothing, and the reverse | whether a non-empty pair agrees on *how much* |
| `art.len % TILE_SIZE == 0` | same | a sheet truncated mid-tile | a sheet truncated by a whole number of tiles — those frames DMA whatever the link put after the art |
| even-length blob guards | same | an odd blob putting the next label on an odd address | alignment of the first label (a link-time fact) |
| `dplc_peak_entries + 2 <= 12` | same | a frame needing too many DMA slots | a `$20000` ROM straddle, which splits an entry in two at link time — `tools/dplc_straddle.py --gate` measures that |
| `anim_frame_bound` | build lane, post-link | a script byte at or above the mappings table's frame count | the DPLC table; the *other* shape's tables |
| `gen_vram_map` bounds/coverage/overlap/quantum | build | a malformed VRAM map | base-register alignment; whether a region fits its art |
| BG layout length annotation | `act_assets.emp` | a wrong-sized `zone_bg.bin` | which of the two generators wrote it |
| `check_tile_budget` | `png_to_bg_override.py` | BG art over the static tile budget | anything about the art's quality |
| collattr length | `ojz_strip_gen.py` | — | **it WARNS, it does not fail**: a wrong-sized collision file silently reverts the section to air |

---

## 8. The parallax and raster effects system

Sources for this whole section: `engine/effects/` (5 modules — `palette_dsl.emp`,
`palette.emp`, `preset.emp`, `raster_dsl.emp`, `raster.emp`), `engine/level/parallax.emp`,
`engine/level/parallax_dsl.emp`, `engine/level/scene_dsl.emp`, and the scene/preset data
under `games/sonic4/data/effects/` and `data/generated/ojz/act1/effects_scenes.emp`.

### 8.1 What an effect *is*, as data

There is no single "effect object". A section binds **one `EffectsPreset`**, and that
record is the total binding — every channel arrives through it
(`engine/effects/preset.emp:57`, `struct EffectsPreset (size: 46)`):

```
$00 ep_pal            *u8    REQUIRED — the preset CARRIES the base palette
$04 ep_parallax       *u8    0 = defer to the act default (the one legal 0);
                             a non-zero Sec.sec_parallax_config outranks it
$08 ep_raster         *u8    static raster program; 0 is ILLEGAL — use
                             Raster_Program_None
$0C ep_patched        *u8    patched template (water / world-anchored gradient);
                             0 = none
$10 ep_cycle          *u8    palette-cycle script; 0 ILLEGAL — use Pal_Cycle_None
$14 ep_variants       [*u8; 2]        PAL_MAX_VARIANTS; unused slots 0
$1C ep_patch_world_ys [u16; 4]        one authored world Y per patch channel
$24 ep_transition     u16             cross-fade arm
$26 ep_patch_motion   [u16; 4]        one packed SWEEP word per patch channel
```

`RASTER_MAX_PATCH = 4` (`engine/effects/raster_dsl.emp:2131`) is what sizes the two
4-entry arrays. The two inline arrays are inline, not pointers, deliberately: a `Label`
carries no length, so an `ensure` comparing one against an integer is unevaluable and
passes silently.

The three data shapes an effect lowers into are:

1. a **`parallax_config`** — a 30-byte header plus N × 10-byte `band_entry` records (§4.7)
2. a **raster program** — a word-oriented schedule of per-scanline VDP work (§8.3)
3. a **palette script / variant descriptor** (§3.5)

### 8.2 The section and band model

* **Section** is the binding unit: crossing a section boundary installs that section's
  preset (`Effects_InstallPreset`), which swaps the palette, the parallax config, the
  raster program and the cycle script together.
* **Band** means two different things, and confusing them is easy:
  * a **parallax band** is a horizontal slice of the *plane* (`band_top_plane`, 0..511)
    with its own scroll factors — up to `MAX_PARALLAX_BANDS = 16`;
  * a **raster band** is a pair of fires on *screen* lines — an ON edge and an OFF edge —
    built by `band(top:, bot:, on:, sh:)` in `engine/effects/raster_dsl.emp:689`. Its two
    records carry a comptime-only band id derived as `top * 128 + sa`, never authored, so
    an ownerless OFF edge is refused by name.

### 8.3 The raster program wire format

`engine/effects/raster.emp`'s module header (the wire-format block, keyed on
`dc.w pal_dirty_mask`). A compiled raster program is **data**; both the
`raster_dsl` constructors and the editor compile to exactly this:

```
header      dc.w pal_dirty_mask     bits 0-3: palette lines Raster_VBlank re-asserts
                                    into Palette_Dirty EVERY frame, so mid-frame CRAM
                                    writes are transient
fire records, in FIRE ORDER (the first two are priming no-ops)
            dc.w arm_word           $8A00 | delta — written at THIS fire, schedules the
                                    gap after NEXT;  RASTER_ARM_PARK ($8AFF) on the last
                                    two real records
            dc.w op_count           0 = priming / no-op
            op_count x { dc.w op; args... }
terminator
            dc.w RASTER_ARM_PARK
            dc.w RASTER_OPS_END     ($FFFF)
```

Two facts about scheduling that an outside compiler must get right, both stated in that
header:

* The VDP reloads its line counter from reg `$0A` **at the instant of underflow**, before
  the handler executes anything. So an arm word written in handler *i* schedules the gap
  from *i+1* to *i+2*, not the gap it sits in. Naive `next_line - cur_line - 1` is off by a
  whole event.
* A program opens with **two priming records**, because `Raster_VBlank` leaves reg `$0A` =
  0. Real events therefore start at line ≥ 2, and **fire lines are one line early by
  construction** — an effect authored to begin at screen line M is scheduled at fire line
  M−1. The comptime constructors own that −1 so authors think in screen lines.

Bounds: `RASTER_MIN_FIRE_LINE = 3`, `RASTER_MAX_FIRE_LINE = 223`,
`RASTER_BUF_SIZE = 128` bytes = 64 words (`engine/effects/raster.emp:363, 1718-1719`).

Opcodes (`engine/effects/raster.emp`), with their argument layouts:

| op | value | body |
|---|---|---|
| `OP_SET_REG` | 0 | `dc.w $8xxx` — one VDP register word. **Its value is load-bearing**: 0 lets the op fetch's own `move.w` set Z and dispatch with no compare at all |
| `OP_CRAM` | 2 | `dc.l` VDP command longword, `dc.w count-1`, `dc.w colour[count]` |
| `OP_PAL_REGION` | 4 | same 3-word shape, but colours come from a variant's RAM staging |
| `OP_RUN_GRADIENT` | 6 | dense: `dc.l` command, `dc.w` line count L, `dc.l` ROM stream of L × 3 colour words |
| `OP_RUN_RAMP` | 8 | dense: `dc.l` command, `dc.w` L, `dc.l` 16.16 start, `dc.l` 16.16 signed step |
| `OP_PAL_RESTORE` | 10 | `dc.l` command, `dc.w count-1`, `dc.w addr` — a band's OFF edge |

`RASTER_DENSE_WORDS_PER_LINE = 3`.

**A program carries NO frame-top register words.** It used to; `Flush_VDP_Shadow`'s
unconditional re-blit made them unnecessary, and deleting them is precisely what lets two
independently-authored effects touch the same register and compose without agreeing on
anything.

**A section takes one tier or the other.** The sparse tier (event lines) is authorable as
a word array; the dense tier (`OP_RUN_GRADIENT` / `OP_RUN_RAMP`) carries a link-time
symbol, which a `[u16; N]` array cannot hold, so a program mixing sparse events with a
dense run is deliberately not authorable even though the wire format permits it.

### 8.4 The ladders

**The row-remap ladder** (`tools/row_remap_ladder_gen.py`, and the H = 16 instantiation
`row_remap_ladder16()` in `engine/level/parallax_dsl.emp:396`).

A ladder is **(H+1) rows of H bytes**. Row `r` is selected each frame as `r = H − |p|`,
where `p` is the perspective quantity — the separation, in screen lines, between the
background's image of a surface and the foreground's truth about it. Screen line `i` of
the band takes the plane-B scroll word that belonged to line `ladder[r][i]`.

The model is **chosen, not fitted**:

```
entry(H, r, i) = i + (i*i*p) // (H * (H-1)),    p = H - r
```

Every property the runtime depends on falls out of the algebra: `entry[i] >= i`, strictly
increasing, `entry[i] <= 2i`, row H is the identity, row 0 saturates at exactly `2(H-1)`,
monotone in `r`. Because the table is `[u8]` and the largest entry is `2*(H-1)`, the
ceiling is **H ≤ 128**, derived rather than typed.

`row_remap_ladder16()` returns `[u8; 272]` = 17 × 16 — verified from the signature.

⚠ **S3K's own tables cannot be used directly**, and this was measured rather than assumed
(`--donor`, 2026-09-04): HCZ's `9312 B = 97 × 96` and LBZ's `4160 B = 65 × 64` are both
`(H+1)×H`, and both satisfy `entry[i] >= i` and non-decreasing with zero violations — but
`entry[i] <= 2i` is violated by **5 871 of 9 312** HCZ entries and **2 603 of 4 160** LBZ
entries, because their table indexes a 192-row source image and the selected row is a
96-row window into it.

**HSHIFT** is the band height, and it is a *shift*: `SceneRemap.Ladder(table, plane_y,
hshift)` and the runtime consumes `H = 1 << brm_hshift`. So **H must be a power of two**.
That is why S3K's H = 96 is a height this engine cannot name. Today's shipped H is 16.

The `waterline_strips` VRAM region is sized by the same H:

```
tiles = 2 strips x 2 tile-columns x (H / 8 rows-per-tile) = H / 2

H       8    16    32    64   [96]   128
tiles   4     8    16    32   [48]    64
```

The region is 48 tiles — the owner-sanctioned spend, not the derived need. At today's
H = 16 only **8** of them carry art, and the region's own ceiling is H = 64. The ROM-side
source image is separate and larger: `waterline_strip_art16()` returns `[u8; 512]`
(= 32 × H bytes), because the gather permutes source rows into the smaller VRAM run.

### 8.5 The live nudges and the warp mailbox

**Both are DEBUG-shape instruments, not an authoring surface.**

* The "live nudges" are controller chords in
  `games/sonic4/test/ojz_scroll_test.emp` — `C + UP/DOWN` moves patch channel 0's world
  anchor by one pixel per held frame, clamped to that channel's declared raster band. They
  exist so the owner can find a value on screen, and they write RAM, not data.
* The **warp mailbox** is the DEBUG camera-teleport path
  (`tools/warp_mailbox_gate.py`). A bare camera poke *tears*: everything downstream latches
  per-frame deltas off the camera, so a teleport-sized jump mis-latches the prefetch
  direction and leaves the tile-cache window describing the old locality, where every plane
  write outside it is silently dropped. Measured, engine-side, at +30 frames: **698**
  visible-window plane-A nametable words wrong for a bare poke, **0** through the mailbox.
  It self-heals (699 → 437 at +120 frames → 0 at +150), which is why the negative control
  asserts *bounded* wrongness at a fixed early sample rather than permanence.

Neither belongs in an asset file. If an outside tool wants to move the camera, it is asking
for the mailbox, and the mailbox is not in the release shape.

### 8.6 VBlank ordering

From `engine/system/vblank.emp:157-209`, in order:

```
Raster_VBlank            <-- MUST precede the flush
Flush_VDP_Shadow
Enqueue_Dirty_Buffers    (palette + sprites + HScroll)
VInt_DrawLevel           (drain the plane buffer to VDP)
Process_DMA_Critical     (drains palette + sprites + HScroll)
Vscroll_Write            (VSRAM — AFTER the HScroll DMA)
Process_DMA_Important
Process_DMA_Deferrable
Read_Controllers
```

`Raster_VBlank` **must** precede `Flush_VDP_Shadow` for two independent reasons stated at
the call site: `HBlank_Install` arms reg `$0A` *through the shadow*, so the arm only
reaches hardware on this frame's flush (a post-flush position would delay every arm by a
frame); and it ORs the program's `pal_dirty_mask` into `Palette_Dirty`, which
`Enqueue_Dirty_Buffers` must then see.

`Palette_Compose` runs in the **game loop**, not here — it is arithmetic, and it must land
before the next VBlank's `Enqueue_Dirty_Buffers` reads the dirty mask.

### 8.7 What is authorable from outside vs. engine-fixed

**Authorable** (this is the surface an outside tool writes):

* scene files → `scene()` / `layer()` calls: band tops, scroll factors, deform tables and
  amplitude shifts, per-band phase, curves, drift, vertical splits, row-remap ladder
  attachment, left-column-mask policy
* preset documents (`presets/<id>.json`) → whose `bands` key lowers to a raster program
* palettes, palette cycles, palette variants
* the per-section `sceneRef` sidecar (`section_N.meta.json`), and the act-level
  `sceneRef` in `project.json`

The consumer's exact field list is `tools/EFFECTS_CONSUMER_CONTRACT.md` §2 — **normative,
and `tools/effects_gen.py` reads exactly that and nothing more.** ⚠ That document
enumerates field *names*; the schema in the `empyrean` repo owns their *values*. Inferring
a value from the name list has already shipped two defects (the absent spelling is the
string `"none"`, **not** JSON null; `precision` / `transition` / `left_column_mask` are
lowercase enum strings, not `.emp` constants).

**Engine-fixed** (an asset cannot change these):

* the plane geometry, the VRAM map, the HScroll mode, the VBlank order
* the raster opcode set and the two priming records
* the per-fire burst ceilings and the arithmetic that sets them
* `Flush_VDP_Shadow`'s unconditional re-blit — a raster register write is always transient
* CRAM line 0

**Validation posture, stated by `tools/effects_gen.py` itself and worth adopting in any
peer tool:** the generator validates *shape* — schema version, id, unknown keys — and
refuses rather than guessing; authored *values* are validated by `sigil` when the generated
`.emp` calls the real `scene()` / `layer()` constructors, and those `ensure` messages are
the error surface. A type is shape, a range is value. Never grow a value check that
duplicates a constructor guard: two sources for one rule is how they drift.

### 8.8 Budgets an effect must stay inside

| bound | value | source |
|---|---|---|
| parallax bands | 16 | `MAX_PARALLAX_BANDS` |
| a 16-band scene's cost | `4664 + 15 × 854 = 17 474` cyc = 13.7 % of a 128 000-cycle NTSC frame | the `MAX_PARALLAX_BANDS` block |
| raster program buffer | 128 bytes = 64 words | `RASTER_BUF_SIZE` |
| fire lines | 3 .. 223 | `RASTER_MIN_FIRE_LINE` / `RASTER_MAX_FIRE_LINE` |
| CRAM words per fire | 3 | `RASTER_BURST_MAX_CRAM` |
| region/restore words per fire | 3 | `RASTER_BURST_MAX_DEEP` |
| measured HBlank window | **122.9 cycles** | 2026-08-19 sweep, quoted in the `stream_cram` guard |
| palette variants live at once | 2 | `PAL_MAX_VARIANTS` |
| palette-cycle channels per script | 4 | `PAL_CYCLE_MAX_CHANNELS` |
| patch channels | 4 | `RASTER_MAX_PATCH` |
| BgAnim bands per act | 4 | `BGANIM_MAX_BANDS` |

The burst ceilings are a **cycle budget, not a FIFO limit** — a CRAM write outside
horizontal blanking paints a visible dot, so the ceiling is what keeps the writes inside
the window. Four CRAM words *was measured and refused*: the arithmetic admits it (78 + 30
against 122.9), but the spin quantises to whole `dbf` iterations and the nearest one leaves
the first write 0.9 cycles inside the early margin, against an estimator whose own standard
error is 2.0.

A full 16-colour line therefore **cannot swap in one fire**. A full-line palette region is
authored as consecutive `OP_PAL_REGION` fires on successive lines, taking `ceil(N/3)` lines
to complete.

The machine-readable budget model is `tools/effects_budget_model.toml`, gated by
`tools/effects_budget_check.py` against the `[symbols]` table at its foot. Read its status
key before quoting a row: `fixed` rows are hardware/architecture constants, `code-derived`
rows are gated against the shipped `.emp`, and **`NEEDS-MEASUREMENT` rows are placeholders
and say so.** Every cycle row that came off the emulator is an *ideal-cycle* figure — bus,
VDP and DMA stall reach the wall clock and never reach a cycle row.

---

## 9. Traps an asset producer will hit

### Trap 1 — a `mark` is not zero-byte, and neither is renaming a label

`build.sh` appends the `convsym` **deb2 symbol table into the ROM image**, past
`EndOfRom`, in **every shape — including both shipped release ROMs.** Measured appendix
sizes at `0d64f534`: s4 `0xa773`, s4.debug `0xd5cd`, demo `0x6845`, demo.debug `0x80f7`
(`tools/test_deb2_appendix.py`, `tools/deb2_probe.py`).

The appendix opens with a **Huffman code table built over the CHARACTERS of every symbol
name**. So adding a symbol that emits no bytes still moves ROM bytes, and *which* ROMs it
moves is not derivable by argument. The measured instance: adding
`mark Sound_Dbg_Mirror_End` took demo.debug's `'b'` from 336 to 337, breaking its exact tie
with `'k'` at 336; the two 7-bit codes `0x004D` and `0x005C` exchanged owners, every name
containing a `b` or a `k` re-encoded, **953 appendix bytes changed with the total length
unchanged**, plus the header checksum word at `$18E`. The same edit left the other three
ROMs byte-identical, because `'b'` was untied in those corpora.

Over 35 trial names: s4 moved for 20, s4.debug for 17, demo for 30, demo.debug for 32, and
`AAAAAAAAAAAAAAAAAAAA` moved all four *and* changed their lengths. Holding the name fixed
and moving the mark to four different anchors changed nothing; holding the address fixed
and varying the name moved every shape.

**The rule is not about `mark`.** Any edit that changes the set of symbol *names* without
emitting a byte moves the appendix the same way — renaming a local label, adding one,
dropping one. If you are generating `.emp` and your symbol names are not stable, your ROM
checksums are not stable either. `tools/deb2_probe.py` answers "would this name move this
shape?" in 0.1 s against an existing listing instead of a three-minute build.

### Trap 2 — the two sonic4 shapes do not ship the same tables

`s4.debug` ships **ten** animation tables; `s4` (release) ships **nine**. The whole
`TestParticle` / `TestEmitter` / `TestStressEmitter` / `TestChurnObj` / `TestAnimated`
family is absent from the release image, and `Ani_Particle` with it.

Measured on this tree, with a positive control:

```
grep -c TestEmitter s4.lst   -> 0   (exit 1)
grep -c Ani_Particle s4.lst  -> 0   (exit 1)
grep -c Ani_Sonic s4.lst     -> 50  (exit 0)   <- the control
```

Consequences for a tool:

* **Symbol presence is per shape.** Do not infer from one listing what the other contains.
* A gate that measures the release image says nothing about a table that only ships in
  debug, and vice versa. `tools/anim_frame_bound.py` reports such a table by name and skips
  it rather than folding it in — *"`Ani_Particle` (DECLARED) is not in this image — nothing
  to bound for this shape."*
* An asset reachable only from a test object is not in the shipped game, however green the
  debug build is.

### Trap 3 — demo artifacts must never be written by a sonic4 build

A sonic4 `./build.sh` assembles the *demo* game to evaluate its link-time guards (some
`ensure`s are gated `when = "sound_off"` and are dead in every sonic4 shape). That assemble
writes to **a scratch path, deliberately** (`build.sh:818-860`).

The reason is a false-pass mechanism worth understanding: writing real demo artifacts there
would give `demo.bin` / `demo.lst` a fresh mtime **from a sonic4 invocation**, and the
post-build lanes' `--artifacts-built-after` rule would then read them as legitimately
produced. `tools/needs_build_lane.py` declares `demo.debug.lst` as *deferred* today
precisely *because* no sonic4 build makes it; a side-effect write turns an honest deferral
into a false pass.

If you write a tool that touches this tree: **never emit an artifact for a game you were
not asked to build.** A green run of a cross-game check does not mean the other game's ROM
was built, its lanes were run, or anything at all about its bytes.

### Trap 4 — a build can be green and unverified

`FAST=1 ./build.sh` skips every verification lane and prints a loud banner at both ends.
The ROM it produces is byte-identical to the canonical one — but nothing checked that. Any
number quoted from a `FAST=1` build is unverified; re-run the canonical build before
quoting one. In particular, `tools/loop_crossover_gate.py` (the only evidence the crossover
table is read at all) is skipped there, so **a fast build is not evidence about that
table.**

### Trap 5 — generated files are committed, and staleness is a build failure

Everything under `games/<game>/data/generated/` is generated *and* checked in. `build.sh`
gates on `tools/level_staleness.py`: a canonical build **fails** and names
`tools/regenerate-level.sh`. Do not hand-edit a file carrying a `DO NOT EDIT` banner —
edit the editor source and re-bake.

---

## 10. What this document could NOT establish

Listed so you ask rather than infer:

* **The VDP's hardware per-line sprite count and per-line pixel budget.** No constant in
  this tree names them (§5.5). The engine's own `SCANLINE_SPRITE_LIMIT = 24` is a soft
  internal budget that deliberately undercounts, and is not the hardware figure.
* **Any bound on a mappings frame's piece count.** `Sst.sprite_piece_count` is a byte; I
  found no build-time guard.
* **The full `scene()` / preset JSON schema.** `tools/EFFECTS_CONSUMER_CONTRACT.md` §2
  enumerates the field *names* the aeon consumer reads; the *values* live in the `empyrean`
  repo (`docs/AURORA_EFFECTS_SCHEMA.md` and
  `contract/schema/aurora-effects-scene.schema.json`), which is outside this repo and which
  I did not read. Read them at a committed revision.
* **What the off-canonical build profiles (`config_a`, `config_b`, `lean`) place.**
  `games/sonic4/map.toml` says so itself: they are gated by their own goldens and nobody has
  re-verified them since the 2026-08-04 crash-report ruling. Do not infer their contents
  from the two canonical shapes.
* **The sound/SFX blob formats** beyond `tools/sfx_transcode.py`'s docstring summary. Not
  in scope here, and not derived.
* **Whether `crossover.bin`'s read path has ever run in a real loop.** It has been proven by
  *executing the ROM's bytes* under `tools/loop_crossover_gate.py`, not by driving a player
  through a loop — no loop exists in OJZ act 1. Those are different claims and only the
  first has evidence.

### One discrepancy found between this repo's docs and its source

`tools/EFFECTS_CONSUMER_CONTRACT.md` §1.1 describes `inject_editor_bg.py`'s `tiles` key as
`len(tiles) <= BG_TILE_CAPACITY` **"(448, imported from the vram_map mirror `:24`)"**. Both
halves are wrong on this tree: the mirror (`tools/vram_map.py`, generated from
`games/sonic4/vram.toml`) gives `BG_TILE_CAPACITY = 400`, and the import is at
`tools/inject_editor_bg.py:36`, not `:24`. The *mechanism* the sentence describes — one
authority, imported from the generated mirror — is correct and is what the code does. This
is exactly the failure mode this document's opening rule exists to avoid: read the mirror,
not the sentence about the mirror.
