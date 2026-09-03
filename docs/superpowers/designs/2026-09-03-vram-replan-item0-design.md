# Item 0 — the VRAM re-plan: where a spare nametable comes from

**Status:** DESIGN DRAFT, decision-ready. No engine code, no `.emp` touched.
**Branch:** `design/vram-replan`, based on `origin/master` `5cdc5c19`.
**Unblocks:** EFFECTS-W1 items 10 and 11, and nothing else in the queue.
**Author's constraint:** every number below is derived from a file at a cited line. Where a
number is inferred rather than read, it says so. Where the brief this was written from was
wrong, §9 says which claim and what the tree actually says.

---

## 0. The one fact that reframes the whole problem

**The unit of the question is not tiles. It is *alignment slots*.**

`engine/vdp.emp:102-110` (`vdp_base_granule`) declares the granule of each of the five VDP
base registers, and `engine/vdp.emp:112-118` (`vdp_base_reg`) refuses a base that is not a
multiple of it:

| register | region | granule (H40) | shift |
|---|---|---|---|
| `$02` | Plane A nametable | **`$2000`** | 10 |
| `$03` | Window nametable | **`$1000`** | 10 |
| `$04` | Plane B nametable | **`$2000`** | 13 |
| `$05` | Sprite attribute table | `$400` | 9 |
| `$0D` | HScroll table | `$400` | 10 |

A plane nametable base is therefore only expressible at one of **eight** addresses in the
whole 64 KB of VRAM — `$0000 $2000 $4000 $6000 $8000 $A000 $C000 $E000` — and a window
nametable base at one of sixteen `$1000` boundaries. This is a hardware encoding, not a
convention: the register carries only the address bits above the granule and the VDP drops
the rest.

> **All five of the engine's shift/granule pairs are now independently confirmed against an
> external reference — which closes a caveat the `DEFERRED_WORK` entry left open.** That entry
> notes the two H40 ignored-bit rules (the `$1000` window granule and the `$400` SAT granule)
> were *"the half not cross-checked against a reference"*, because no base in either s2disasm
> or skdisasm distinguishes them from the looser `$800`/`$200` field granularity. Genesis Plus
> GX's register-write handler (`core/vdp_ctrl.c`) does distinguish them, and it agrees with
> `engine/vdp.emp` line for line: `case 2: ntab = (d << 10) & 0xE000` · `case 3: (reg[12] & 1)
> ? ntwb = (d << 10) & 0xF000 : ntwb = (d << 10) & 0xF800` (the H40/H32 split, explicit) ·
> `case 4: ntbb = (d << 13) & 0xE000` · `case 5: satb = (d << 9) & sat_base_mask` with
> `sat_base_mask` = `0xFC00` in H40 / `0xFE00` in H32 · `case 13: hscb = (d << 10) & 0xFC00`.
> Charles MacDonald's `genvdp.txt` states both forcings in prose — *"In 40-cell mode, A11 is
> always forced to zero"* (reg `$03`) and *"In 40-cell mode, A09 is always forced to zero"*
> (reg `$05`). Plutiedev's register reference agrees. **The stricter reading was the correct
> one, not merely the safe one.** (One documentation trap for a successor: `genvdp.txt`'s reg
> `$04` line has a typo — it says bits 2-0 correspond to "A15-A11", a 3-bit field spanning 5
> bits. It is A15-A13, `$2000`, as Plutiedev and GPGX both have it.)

Against today's map (`games/sonic4/vram.toml`, byte ranges derived as `tile × 32`):

| bytes | tiles | occupant |
|---|---|---|
| `$0000-$6FFF` | 0-895 | `fg_art_pool` (896 tiles) |
| `$7000-$7FFF` | 896-1023 | the sprite/character window band (dust, sparkle, insta-shield, `character_window`, ring placeholder, markers) + 5 free tiles |
| `$8000-$B7FF` | 1024-1471 | `bg_region` (448 tiles) |
| `$B800-$BA7F` | 1472-1491 | `sprite_table` |
| `$BA80-$BBFF` | 1492-1503 | `tails_appendage` + 3 free |
| `$BC00-$BF7F` | 1504-1531 | `hscroll_table` |
| `$BF80-$BFFF` | 1532-1535 | free (4) |
| `$C000-$DFFF` | 1536-1791 | `plane_a` (64×64) |
| `$E000-$FFFF` | 1792-2047 | `plane_b` (64×64), with `window_plane` aliasing `$F000-$FFFF` |

**All eight `$2000` slots are occupied.** Four are inside `fg_art_pool`, two inside
`bg_region`, two are the planes. That is the real statement of item 0 — sharper than "there
are 12 free tiles", and it explains why the 12 free tiles were never going to help: they are
not merely too few, they are at unusable addresses (957, 1022, 1501, 1532 — none is a
multiple of 32 tiles, let alone 128 or 256).

**Corollary that decides the recommendation:** a run of free tiles is only a candidate if it
*starts* on a `$1000` (window) or `$2000` (plane) boundary. Almost every way of freeing tiles
in this map frees them at the wrong address.

---

## 1. Sizes, derived

- One nametable cell is 2 bytes; one VRAM tile is 32 bytes (`TILE_SIZE`).
- **64×32 plane** = 2048 cells = `$1000` bytes = **128 tiles**.
- **64×64 plane** = 4096 cells = `$2000` bytes = **256 tiles**.
- We ship **64×64 on both planes**: `BootData_VDPRegs` reg `$10` = `$11`
  (`engine/system/boot_data.emp:186`), and `engine/level/parallax.emp:546-548` derives
  `PLANE_B_SPAN = PLANE_B_CELL_ROWS(64) * 8 = 512` with an `ensure` pinning it.
- Reg `$10` is **one register for both planes** (H-size bits 0-1, V-size bits 4-5). There is
  no way to make Plane A 64×64 and Plane B 64×32. Any plane-size change hits both.
- The window nametable is 64 cells wide in H40 regardless of reg `$10`, so a full-height
  window is 64×32 = **128 tiles** — which is exactly `window_plane.tiles` in the TOML.

---

## 2. What items 10 and 11 actually need — and they are NOT the same ask

Read from the DoD spec itself (empyrean `origin/main`
`docs/superpowers/specs/2026-08-29-effects-definition-of-done.md`, items 10-11), not from the
queue summary. **The two items decompose into five sub-features, and three of the five need
zero new VRAM.**

| # | sub-feature | what it actually needs | new VRAM |
|---|---|---|---|
| 10a | **reels** ("per-strip vertical scroll content") | per-column VSRAM, which **already ships**: `engine/level/parallax.emp:723` `VSCROLL_COL_PAIRS = SCREEN_WIDTH/16 = 20`, with a per-column V-scroll buffer and `VSCROLL_COL19_BG_OFF = 78` | **none** |
| 10b | **plane-role swap** ("background on Plane A for a set-piece") | swap reg `$02` ↔ reg `$04`. **Both target addresses already exist and are already legal bases** (`$C000` and `$E000` are both `$2000`-aligned). The work is re-plumbing the scroll feeds (HScroll table is A/B-interleaved per line; VSRAM even/odd) and the plane-buffer write targets — code, not tiles | **none** |
| 10c | **window as a third layer** | a window nametable that is not aliasing Plane B, based on a `$1000` boundary. **⚠ but see §2.1 — the window is not additive** | **yes** |
| 11a | **mid-frame base change, as a mechanism** | re-point reg `$02` (or `$04`) partway down the frame at an address that already holds a valid nametable — e.g. point Plane A at `$E000` at scanline S so the bottom of the screen draws Plane B's map in the Plane-A layer. **This is Batman's trick, the op that delivers it already ships (§2.0), and it is demonstrable today with zero tiles and zero new engine code.** | **none** |
| 11b | **frame swap / Plane Z** (a *distinct third picture*, "a 48-px strip in a spare nametable shown by re-pointing Plane B's base at a scanline") | a `$2000`-aligned base (for reg `$02`/`$04`) holding content nothing else owns. The *delivery* is `SetReg` / `Set_VDP_Reg`, both shipped (§2.0) — only the **content** is missing | **yes** |

**So the split is real and it is worth acting on.** Item 10 is two-thirds free today. Item 11's
*mechanism* is not merely free — it is already built (§2.0); only its *content* costs. And
critically:

> **10c wants a `$1000`-aligned base. 11b wants a `$2000`-aligned base. A `$2000`-aligned base
> is also `$1000`-aligned. One 128-tile run starting at a `$2000` boundary satisfies both.**

That is the single procurement this design has to make.

**The register bytes, derived** (`base >> vdp_base_shift`, so a later parcel does not have to
re-derive them and cannot transcribe them wrong):

| target | reg `$02` (Plane A) | reg `$04` (Plane B) | reg `$03` (Window) |
|---|---|---|---|
| `$C000` (today's Plane A) | **`$30`** ✓ shipped | `$06` | — |
| `$E000` (today's Plane B) | `$38` | **`$07`** ✓ shipped | — |
| `$F000` (today's Window alias) | — | — | **`$3C`** ✓ shipped |
| **`$6000`** (Option P's freed run) | `$18` | `$03` | `$18` |
| `$5000` (Option P's second run, window only) | — | — | `$14` |

Note what the first two rows say: **10b's plane-role swap is `$30`↔`$38` on `$02` and
`$07`↔`$06` on `$04`, and 11a's mid-frame proof is one write of `$38` to reg `$02`.** Every
byte those two sub-features need already has a legal target in today's map.

### 2.0 The delivery mechanism for items 10b/11a/11b already ships. Only the content is missing.

This was not expected and it changes the sequencing more than anything else in this document.
The engine already has both halves of "write a VDP base register at a chosen moment":

- **Mid-frame.** `engine/effects/raster.emp:118` defines `OP_SET_REG` — a sparse HInt raster op
  whose whole argument is *"`dc.w $8xxx` — one VDP register word"* (`raster.emp:80`), written
  straight to `VDP_CTRL` from `Raster_HInt`'s `.op_set_reg`. It is exposed to authoring as
  `RasterOp.SetReg(int)` (`engine/effects/raster_dsl.emp:131, 207`) and it is the **cheapest op
  in the dispatcher** — `OP_SET_REG == 0` is load-bearing so the op fetch's own `move.w` decides
  it on the Z flag with no compare at all (`raster.emp:111-120`).
- **Per-frame (settled).** `Set_VDP_Reg` (`engine/system/vdp_init.emp:114`) writes the shadow;
  `Flush_VDP_Shadow` (`:73`) re-blits it at VBlank.

And the register in question is shadowed. `engine/structs.emp:373-393` — `VdpShadow` covers all
19 registers `$00`-`$12` by name, **including `vdp_plane_a` (`$02`), `vdp_window` (`$03`),
`vdp_plane_b` (`$04`), `vdp_plane_size` (`$10`) and `vdp_window_h`/`vdp_window_v`
(`$11`/`$12`)**. Two consequences, both good:

1. **A mid-frame base change self-restores at frame top, for free.** `raster.emp:61-68` states
   the design: programs used to carry paired reset words, and that mechanism was *deleted*
   because *"Flush_VDP_Shadow now re-blits ALL 19 shadowed VDP registers from VDP_Shadow_Table
   unconditionally every VBlank, which restores every register a mid-frame op touched … without
   the program having to name it. Deleting the mechanism is what lets two independently-authored
   effects touch the same register and simply compose."* A per-band `SetReg($8238)` is therefore
   already safe and already composable with every other authored effect.
2. **The two halves of item 11 use different doors, and the file already says which.**
   `raster.emp:68-69`: *"A register change meant to SURVIVE the frame is settled state, not a
   raster op: `Set_VDP_Reg` … writes the shadow and the flush delivers it."* So item 11's
   *frame* swap is a `Set_VDP_Reg` call and its *mid-frame* swap is a `SetReg` op. Neither is
   new work.

**Cost check.** A `SetReg` is one `move.w` to `VDP_CTRL`. The engine's HBlank write window is
measured at **122.9 cycles** (`docs/benchmarks/scanline-p2/HBLANK-WINDOW-SWEEP-RESULTS.md`,
2026-08-19 sweep), and the deadline Genesis Plus GX models for a same-line base change is ~860
master cycles ≈ 122 68000 cycles (§10.1). *These two figures are not independent evidence of
each other* — both are essentially "how long HBlank is in 68000 cycles" — but a single register
write is an order of magnitude inside either, so the budget is not the constraint. The
per-fire ceiling is 4 ops (`raster_dsl.emp:415`) and *"the richest fire anything has ever run is
two ops."*

**So item 11 is not blocked on a strip streamer or a new opcode.** It is blocked on one thing
only: a base address holding a picture nothing else owns. That is what §3 buys, and it is why
§4 recommends proving 11a *first*, on `$E000`, with an op that already exists.

### 2.1 ⚠ The window is not a third layer. It is a region-exclusive substitute for Plane A.

This is the single most important correction in this document, because it changes whether item
10c is worth buying at all, and the DoD's own wording (*"the window plane as a third layer"*)
invites the wrong expectation.

Charles MacDonald's `genvdp.txt`, verbatim:

> *"The window plane operates differently from plane A or B. It can be thought of a
> **'replacement' for plane A** which is used under certain conditions. That said, **plane A
> cannot be displayed in any area where plane W is located, it is impossible for them to
> overlap.**"*
> *"In terms of priority and intensity calculation for shadow / hilight mode, plane W is
> treated _exactly_ the same as plane A."*

md.railgun.works agrees ("the window plane essentially takes its place in areas that they
overlap"), and Kabuto's debug-register notes label the hardware slot `A = Tilemap plane A
(shared with window plane)` — one plane slot, not two.

**So inside the window band you get W + B + sprites: the same three layers you already have
everywhere else.** The window buys you a *non-scrolling map source* in a band, not a fourth
composite. That is still genuinely useful — a fixed panel, a set-piece band whose map is
independent of camera scroll, a title/transition strip — and it is what the DoD's
"top/bottom window" wording is really describing. It is **not** a way to put a third parallax
layer behind the action.

**The consequence for procurement:** if what the owner actually wants from item 10c is a third
*scrolling* layer, the window cannot deliver it and no amount of VRAM changes that. The
technique that does deliver a genuinely extra map on screen is **item 11's mid-frame base
swap** (§2, 11a/11b) — time-multiplexing one of the three base registers across raster bands.
That reorders the value of the two items: **11 is the one that buys new capability; 10c buys a
fixed band.**

### 2.2 How much of a nametable do the consumers actually fetch?

Two size reductions are available and both are worth knowing before buying tiles.

- **A top-anchored window band is cheap.** The VDP indexes the window nametable by *absolute
  screen cell position* (`row × 64 + col`), so a window covering only screen rows 0..N-1 only
  ever fetches the first `N × 128` bytes = `N × 4` tiles. An 8-row (64 px) top band is
  **32 tiles**, not 128. A **bottom**-anchored band gets no such discount — a window at rows
  20..27 still reads at offset `$A00`, so the region must extend that far. The DoD already
  prefers top/bottom over left ("a top/bottom window avoids the left-window scroll bug Oracle
  models as R9" — Oracle models exactly this at
  `oracle/crates/oracle-core/src/render.rs:1272`: *"the first 16 px of plane A right of a
  *left* window"*), so **top** is the free-est of the two.
- **Plane Z's 48-px strip is 6 rows = 24 tiles** of a 64×64 plane's `$2000` span. Re-pointing
  Plane B at a base with only 24-32 valid tiles behind it means plane rows past the strip
  fetch whatever else lives there. Whether that is harmless depends on whether those rows are
  ever on screen at the moment the base is re-pointed. **⚠ TAGGED FOR RUNTIME CONFIRMATION
  (§8, Q1).**

The design below still buys a full 128 tiles, because the marginal cost of the full run over
32 tiles is zero at the cheapest source (§3, Option P) — the quantum forces it either way —
and 128 tiles is what turns "a top band" into "a real third layer".

---

## 3. Where the tiles come from — four options, priced

### Option P — take it from `fg_art_pool`: `POOL_TILE_CEILING` 896 → 768 ✅ RECOMMENDED

`fg_art_pool` is `$0000-$6FFF`. Cutting it to 768 tiles leaves it at `$0000-$5FFF` and frees
**`$6000-$6FFF`, 128 tiles, at tile 768** — and `$6000` is a multiple of `$2000`, so it is
simultaneously a legal **Plane A base** (reg `$02` = `$6000 >> 10` = `$18`), a legal **Plane B
base** (reg `$04` = `$6000 >> 13` = `$03`) and a legal **Window base** (reg `$03` = `$18`).
It is the only free-able run in the map that is `$2000`-aligned at a cost anyone would pay.

**Why 768 and not 832:** `quantum = 64` (`games/sonic4/vram.toml:15`) and
`ensure(PAGE_FRAMES * ART_POOL_PAGE_TILES == POOL_TILE_CEILING)`
(`engine/system/constants.emp:285`). 832 frees `$6800-$6FFF`, which is `$800`-aligned and
therefore useless to every base register. 768 is the next legal step down and it lands exactly
on `$6000`. The quantum does the alignment for us.

**Cost, stated as the owner would picture it:** the FG art residency cache goes from
**14 page-frames to 12**. Nothing on screen changes. What shrinks is headroom for future acts.

**What it does NOT cost, and the tree says so explicitly:**
- **It does not move RAM.** `engine/system/constants.emp:287-301`: the `PAGE_FRAMES` /
  `PAGE_FRAMES_MAX` split (user style ruling 2026-08-11) exists precisely so this knob is
  VRAM-only. Verbatim: *"The arrays are now sized by this fixed capacity and PAGE_FRAMES is
  just the live count, so POOL_TILE_CEILING is a genuinely VRAM-only knob."* `PAGE_FRAMES_MAX`
  is a literal 15; lowering the count to 12 only widens the deliberate slack.
- **It does not re-stamp a fixture.** `character_window`'s base (960) is untouched; nothing
  below tile 896 is addressed by a baked `art_tile` word.
- **It has been done before, at this exact knob.** The 960 → 896 cut is recorded in the TOML's
  own comment as *"safe post-prep-parcel: no RAM moves, no fixture re-stamp"*
  (`games/sonic4/vram.toml:14-21`), and the linker spec §8 names it as the migration's first
  deliberate layout change.

**Does OJZ act 1 still fit?** Yes, with margin. `OJZ_ACT_POOL_PAGES = 10`,
`OJZ_ACT_POOL_TILES = 612`
(`games/sonic4/data/generated/ojz/act1/ojz_act_pool_manifest.emp:7-8`). 10 ≤ 12, so the cache
stays in its degenerate fully-resident mode (`engine/level/load_art.emp:6,40`) and never
evicts. Headroom drops from 4 pages to 2.

**The floor, and it is a hard one.** The linker spec §7.4 states the prerequisite in its own
words: *"C4-3 (the famine capacity fix) must land before any act runs with `granted` near
`floor` — the STRESS_EVICT famine is measured evidence that tight-cache mode has an open
defect. Until C4-3, floors are conservative (full residency for acts that fit)."* So the pool
may not go below **640 tiles / 10 frames** for act 1 until C4-3 lands. Between 640 and 896
there are 256 tiles of legally spendable pool. **Option P spends half of them and leaves the
other half as a second `$1000`-aligned run at `$5000`** should item 11 later want a second
window frame to flip between (§6).

**Blast radius (files, no code written here):** `games/sonic4/vram.toml` `tiles = 896 → 768`;
regenerate (`tools/gen_vram_map.py` rewrites the generated block in
`games/sonic4/config/constants.emp`, `tools/vram_map.py:27`, and
`docs/generated/vram-map-sonic4.md`); `engine/system/constants.emp:712`
`POOL_TILE_CEILING = 896 → 768`; the two paired `ensure`s
(`games/sonic4/config/constants.emp:420`, `games/demo/config/constants.emp:49`) and
**`games/demo/vram.toml:10`, which follows the engine-global value** — the demo game must move
with it or its `ensure` fails the build by name. `tools/test_gen_vram_map.py` asserts the
generated artifacts are in sync and will catch a skipped regenerate. New `[[region]]` for the
spare nametable, or a `[[free]]` run if the parcel that consumes it lands later.

**Mechanically validated, not just reasoned.** Option P was run through the real generator on a
scratch copy of the TOML (pool `tiles = 768`, plus a 128-tile `kind = "plane"` region at base
768). `python3 tools/gen_vram_map.py --game sonic4 --toml <trial> --map-doc <out>` reports
`sonic4 OK — 18 regions, 12 free tiles`, exit 0: coverage stays complete, no overlap is
introduced, the quantum check passes, and the four existing free runs are untouched. **No
engine file was modified to establish this** — the generator takes `--toml` and `--map-doc` as
explicit paths, so the trial ran entirely in the scratchpad.

**⚠ A GAP FOUND WHILE VALIDATING, and it is exactly the class the fold in §7 was built to
close.** The negative control — the same trial TOML with the pool at 832 and the spare
nametable at base **832** (byte `$6800`, illegal for *every* plane and window base register) —
also reports `sonic4 OK — 18 regions, 12 free tiles`, exit 0. **`tools/gen_vram_map.py` does
not check base-register alignment.** Its documented checks are bounds, coverage, overlap,
quantum, reserve and authority (`tools/gen_vram_map.py:12-30`); alignment is not among them,
and the `register = "vdp:0x0N"` field is *"documented in the map only"* at T0 — spec §7.3 defers
register emission to T2. So the only thing standing between a misaligned plane region and a VDP
pointed at the wrong address is `vdp_base_reg`'s `ensure`, **and that only fires if somebody
remembers to route the new region's base through it.** A spare nametable whose base is only
ever written by a runtime `move.w #$8200|…` would bypass the wall entirely.

**Rider (not this parcel, but it should ride the parcel that consumes the region):** teach
`gen_vram_map.py` the granule table — a region with `register = "vdp:0x02"`/`0x03`/`0x04`/
`0x05`/`0x0D` must have `base * 32` a multiple of the register's granule. It is ~10 lines, it
duplicates `vdp_base_granule` in a second language *on purpose* (the two-runner pattern
`DEFERRED_WORK` already argues for at this exact register family), and it moves the check to
the file where the decision is actually made.

**Stale comment found while deriving this, worth fixing in the same parcel:**
`engine/system/constants.emp:282-284` still reads *"POOL_TILE_CEILING(960) /
ART_POOL_PAGE_TILES(64) = 15 frames"* and line 284's trailing comment says `// 15`. The
constant has been 896 since the dust carve, so `PAGE_FRAMES` is **14**, not 15. The prose is
one relayout behind the code — exactly the drift class this design has to be careful of.

---

### Option B — take it from `bg_region`: capacity 448 → 384 (the band reserve, not the art)

**⚠ I wrote this option wrong the first time and the correction is the interesting part.** The
first draft said the BG blob *"ships packed to 448/448"* and concluded Option B *"cannot be
taken today at all"*. That came from restating `games/sonic4/vram.toml`'s own comment about the
2026-07-21 import. **I then measured the blob, and it is 320 tiles, not 448.**

`games/sonic4/data/generated/ojz/act1/bg_tiles.bin` is 10,242 bytes. Its format is a 2-byte
big-endian blob length followed by the blob (`tools/inject_editor_bg.py:797-799`,
`f.write(struct.pack('>H', len(blob)))`); the header word reads **10,240**, and 10,240 / 32 =
**320 tiles exactly** — which is precisely the *static budget* the generated map already prints
for this region (`band_reserve: 128 (static budget 320)`). **So 128 tiles of `bg_region`,
`$A800-$B7FF`, hold nothing in VRAM today.** The TOML comment is describing the destroyed
2026-07-21 configuration, not the shipped one, and read as present tense it is misleading.

**What that changes:**

`bg_region` is `$8000-$B7FF` (448 tiles) with a 320-tile blob at `$8000-$A7FF`. Cutting the
capacity to **384** ends the region at `$AFFF` and frees **`$B000-$B7FF` = 64 tiles at a
`$1000` boundary**. The blob still fits with room to spare, so:

- **It costs zero shipped art.** No re-import, no re-generation, no art pass. It is a TOML edit
  plus a regenerate, exactly like Option P.
- **It costs zero static-art budget for the next import, either.** The static budget is
  `capacity - band_reserve`: today `448 - 128 = 320`; after, `384 - 64 = 320`. **Unchanged.**
- **The entire cost is the BgAnim band reserve: 128 → 64 tiles.** In the reserve comment's own
  units that is the difference between one full-size 32×4 animated band (128 slots, the size of
  the destroyed art's larger band) and a 16×4 one (64). It halves the animation headroom the
  next art pass can spend.

**Why it still is not the recommendation.** `$B000` is `$1000`-aligned but **not**
`$2000`-aligned, so Option B can serve item 10c (a 16-row / 128 px top window band — 64 tiles is
16 rows × 4, and §2.2's top-anchored discount is what makes 64 enough) and **cannot ever serve
item 11b's Plane Z.** Getting a `$2000`-aligned slot out of the BG region means freeing
`$A000-$BFFF`, which requires relocating the SAT *and* the HScroll table into the vacated space
— and §10.4 records that relocating the SAT is a one-way boot-time move because the VDP's
internal sprite Y/size/link cache is not invalidated by a base change. Cutting the capacity to
**320** (reserve 0) frees `$A800-$B7FF` = 128 tiles, but `$A800` is `$800`-aligned and therefore
worth **nothing** to any base register: the usable base is still `$B000` and the extra 64 tiles
are stranded.

**It is, however, a real and cheap alternative if the owner wants item 10c and not 11b** — and
it is genuinely complementary: taking B *and* P later yields both a window band at `$B000` and a
Plane-Z slot at `$6000`, with the costs falling on two different budgets (BgAnim reserve, pool
frames) instead of both on one. That is worth knowing before either is spent.

**One thing it does collide with.** `band_reserve = 128` is recorded as *"the owner's number to
set at the next art pass"*, chosen deliberately from the generous side, and the reserve exists
because it once reached zero and destroyed two bands (`docs/BUGS.md` TOOL-01). Halving it is a
decision in the owner's own stated territory. Two facts make it easier than it sounds: band
*insertion* is already blocked until an art-side pass regardless of the reserve, and *promotion*
(converting existing static tiles, blob length unchanged) is the working route today and needs
none of it. **But it is the owner's dial, so §11 asks rather than assumes.**

**Verdict:** cheap and available today, but it buys strictly less than P — it cannot serve item
11b at any price — so it is not the recommendation as a *replacement*. It is a strong second
purchase, and it is the option to prefer if the owner would rather spend animation headroom than
FG-pool frames.

---

### Option C — shrink both planes to 64×32 (reg `$10` `$11` → `$01`)

Superficially the best deal in the file: it frees `$D000-$DFFF` **and** `$F000-$FFFF` — two
`$1000`-aligned 128-tile runs, 256 tiles, at **zero cost to art or to the pool**, and it
dissolves the `window_plane`/`plane_b` overlay for free (the window keeps its `$F000` base and
simply stops aliasing anything).

**It is a trap, and the build says so by name.**

Halving the plane height halves `PLANE_B_SPAN` from 512 to 256, and that number is load-bearing
in three places that fail loudly:

1. `engine/level/parallax.emp:548` — `ensure(PLANE_B_SPAN == 512, "PLANE_B_SPAN drifted from
   the 64x64 Plane-B geometry Step 4a's `and.w #PLANE_B_SPAN-1` masks against")`. Step 4a's
   band rotation masks against this modulus.
2. `engine/level/parallax.emp:573` — `VSCROLL_BG_MAX = PLANE_B_SPAN - SCREEN_HEIGHT` collapses
   from **288 seam-free V-scroll origins to 32**. The clamp that was added on 2026-08-29
   (PARALLAX-SCROLL-CLAMP) exists because crossing the wrap seam produces an artifact that
   *"reads as somebody else's bug"*. At 32 origins the BG effectively cannot scroll vertically
   at all.
3. `engine/level/parallax.emp:706-708` — the vertical bob's amplitude ladder goes **empty**,
   and its `ensure` message predicts this exact cause verbatim: *"Either the plane geometry
   shrank (PLANE_B_SPAN / SCREEN_HEIGHT) or the table's amplitude did — with no legal shift
   left, scene()'s bob_shift guard admits nothing and the feature is unauthorable."* That is
   **EFFECTS-W1 item 7**, built on 2026-08-30. Option C deletes a shipped item of the same
   wave to unblock two later ones.

It also reverses deliberate prior work: `engine/system/constants.emp:396-397` records that the
SAT was *"relocated from `$D800` to free plane rows 48-63"* and the HScroll table *"relocated
from `$DC00` (was inside Plane A 64x64 nametable)"*. Someone already paid to make these planes
genuinely 64 rows tall. `engine/level/bg.emp:27` closes it: *"ALL 64 ROWS ARE LIVE (NEW-5
close, 2026-08-05)."*

**Verdict: rejected.** It is free in tiles and expensive in the one currency the engine's
stated goals are denominated in (vertical transitions, the mega-act). Recording it because it
*looks* like the answer and the next person to open the file will find it too.

---

### Option D — relocate the SAT / HScroll table, or shrink the HScroll table

The two tables occupy `$B800-$BF7F` (48 tiles used of the 64-tile band `$B800-$BFFF`). Both
have `$400` granules, so they are the most *movable* things in the map — but moving them frees
tiles only in a band that is boxed between `bg_region` below and `plane_a` above, and the band
is 64 tiles at `$B800`, which is not `$1000`-aligned. Shrinking the HScroll table from per-line
to per-cell would recover ~24 tiles, but per-line HScroll is **unconditional** since 2026-08-26
(`engine/level/scene_dsl.emp:199`: *"its 896-byte DMA and reg `$0B` = `%11` are UNCONDITIONAL
now — the per-cell path the bit selected is deleted"*), so that saving is not available and
buying it back would undo a deletion.

**Verdict: not a source on its own.** It is a *combinator* — Option B-at-192-tiles needs it —
and it is the reason Option B's `$2000`-aligned variant is as expensive as it is.

---

## 4. Recommendation

**Take Option P: `POOL_TILE_CEILING` 896 → 768, and declare the freed `$6000-$6FFF` (tiles
768-895, 128 tiles) as the spare nametable region.**

The reason, in one sentence: **it is the only option that yields a `$2000`-aligned base — the
alignment item 11b needs, that item 10c also accepts, and that a run of free tiles almost never
has.** One purchase then covers both items instead of two purchases covering one each.

The runner-up is closer than it first looked, and the honest version of the comparison is worth
stating rather than hiding: **Option B is also cheap, also available today, and also costs no
shipped art** (§3 — that took a measurement to establish, after a first draft got it wrong from
a stale comment). What separates them is not cost, it is reach: `$B000` can never hold a plane
nametable, so B buys item 10c and stops. **If item 11b were dropped, B would be the better
buy** — it spends a reserve that is currently unusable anyway rather than pool frames that are
live headroom. Both costs are small and they fall on different budgets, so this is a question
worth putting to the owner (§11 Q4) rather than settling by a table.

The full comparison:

| | P (pool 896→768) | B (bg cap 448→384) | C (planes 64×32) | D (tables) |
|---|---|---|---|---|
| tiles freed | 128 | 64 | 256 | ~24 |
| base offered | **`$6000` — `$2000`-aligned** | `$B000` — `$1000` only | `$D000`, `$F000` — `$1000` only | none usable |
| serves item 10c (window) | ✅ full 64×32 | ✅ 16-row top band only | ✅ two full windows | ❌ |
| serves item 11b (Plane Z) | ✅ | ❌ wrong alignment | ❌ wrong alignment | ❌ |
| cost | 2 pool page-frames (14→12) | BgAnim band reserve 128→64. **Zero shipped art, zero static budget** | `PLANE_B_SPAN` 512→256 | undoes a deletion |
| breaks a shipped feature | no | no (blob is 320 tiles, measured) | **yes — item 7's vertical bob, by named `ensure`** | per-line HScroll |
| moves RAM | **no** (`constants.emp:287-301`) | no | no | no |
| re-stamps a fixture | **no** | no | no | no |
| available today | **yes** | **yes** | yes | no |

**Sequencing that follows from §2:** do not wait for this parcel to start items 10 and 11.

1. **Now, zero VRAM and zero new engine mechanism:** 10a (reels — the per-column VSRAM buffer
   already exists), 10b (plane-role swap — both bases are already legal), 11a (mid-frame base
   change, authored as a `RasterOp.SetReg($8238)` on a shipped opcode, §2.0). Three of five
   sub-features, no tiles spent, and 11a is the *mechanism* both items are actually about —
   proving it early is cheap and it de-risks the expensive half.
2. **Then Option P**, one TOML edit plus a regenerate plus two engine constants.
3. **Then** 10c and 11b, against the new region.

This ordering means a failure to agree on the VRAM spend stops one sub-feature, not two items.

---

## 5. What each option breaks, named

Specifics, so nobody has to re-derive them:

- **`character_window` (base 960) is not touched by any option above, and that is deliberate.**
  Its base is baked into the player's `art_tile` word which the replay hash covers, so moving
  it re-stamps two fixtures (`games/sonic4/vram.toml:83-88`; linker spec §4.1 spells the same
  rule and adds that *growing* it in place is free). Option P frees tiles **below** 896; every
  region from 896 upward keeps its base. **No fixture re-stamp in the recommended option.**
- **Option P breaks nothing at runtime** but does move the `POOL_TILE_CEILING` value that four
  `ensure`s and three generated artifacts cross-check by name. Skipping any one of them fails
  the build with a message naming the file — including `games/demo`, which is the one people
  forget (`games/demo/vram.toml:10-16`, `games/demo/config/constants.emp:49`).
- **Option P costs the pool half its legal slack.** Between the 640-tile floor (§3) and today's
  896 there are 256 spendable tiles; P spends 128. A second 128-tile run remains at `$5000`
  (`$1000`-aligned, window-only), and after that the pool is at its floor until C4-3 lands.
- **Option B breaks nothing today.** `inject_editor_bg.py:764` asserts
  `len(tiles) <= BG_TILE_CAPACITY`, and the shipped blob is **320** tiles (measured from
  `bg_tiles.bin`'s own 2-byte length header), so a capacity of 384 clears it by 64. What it
  spends is the BgAnim band reserve, 128 → 64.
- **Option C breaks `engine/level/parallax.emp`'s bob ladder by build-fatal `ensure`**, deletes
  the seam-free scroll range, and reverses the SAT/HScroll relocation that bought rows 48-63.
- **Precision on which options touch a base register.** Option P by itself touches **none** of
  the five: the pool has no base register, so cutting it changes no VDP byte. It touches one
  the moment the freed run is *used* — rebasing `window_plane` to `$6000` changes reg `$03`
  from `$3C` to `$18`. Options B and C both move a base register outright. In every case the
  byte now follows the constant automatically and a misencodable base fails the build (§7),
  which was **not** true before `parcel/item15-static-pair` closed the entry on 2026-09-03.

---

## 6. The existing `overlay_with`, and what it would cost to end it

`window_plane` (base 1920, 128 tiles) declares `overlay_with = ["plane_b"]` and aliases
`$F000-$FFFF`, which is **Plane B's rows 32-63** (`$F000 - $E000 = $1000`, and a 64-wide
nametable's row stride is `64 × 2 = 128` bytes, so `$1000 / 128` = row 32). It is safe today
only because the window is disabled: `boot_data.emp:187-188` sets regs `$11`/`$12` to `$00`,
and the file's own comment says it outright — *"there is NO free window space anywhere in this
VRAM map. Enabling the window means first re-planning the VRAM layout, not just writing
`$11`/`$12`."*

Ending the overlay means giving `window_plane` a `$1000`-aligned base of its own. Under
Option P that base is `$6000` and reg `$03` becomes `$18` (derived: `$6000 >> 10`). The TOML
change is: `window_plane.base = 1920 → 768`, drop `overlay_with`, and `plane_b` reverts to
being the sole owner of `$E000-$FFFF`.

**Two consequences worth stating before anyone budgets this:**

1. The overlay's disappearance is itself worth something independent of item 10 — right now
   the map's coverage check is passing *because* an overlap is declared, and a declared overlap
   is a standing invitation to enable the window and corrupt the background.
2. If item 11's frame-swap later wants **two** window pictures to flip between, the second one
   comes from the pool's remaining slack at `$5000` (pool 768 → 640, its floor). That is a
   decision to make when the effect is authored, not now — it spends the last of the pool's
   legal headroom and it is not reversible once act content is baked against a 10-frame pool.

---

## 7. The VDP base-register fold — confirmed in place, as instructed

The `DEFERRED_WORK.md` entry *"BASE-RESIDUE ASSUMPTIONS WITHOUT AN `ensure` ARE INVISIBLE TO
THE ALIGNMENT DECLARATION"* names a VRAM relayout as its exact trigger. **Confirmed closed on
the aeon side, and confirmed present at `5cdc5c19`:**

- `engine/vdp.emp:112-118` — `pub comptime fn vdp_base_reg(b: VdpBase, base: int) -> int`
  folds the byte as `base >> vdp_base_shift(b)` and carries
  `ensure(dropped == 0, …)` where `dropped = base & (vdp_base_granule(b) - 1)`. The message
  names the granule and tells the reader to move the base *"in the game's vram.toml AND
  engine.constants"*.
- `engine/system/boot_data.emp:125-129` — all five rows are folds
  (`VDP_REG_PLANE_A/WINDOW/PLANE_B/SPRITES/HSCROLL`), not literals; the comment records that
  they fold to `$30/$3C/$07/$5C/$2F` on the shipped map, which is what the literals said.
- `engine/system/boot_data.emp:137` — a second `ensure` pins `VRAM_PLANE_B == VRAM_PLANE_B_BYTES`,
  closing the split-spelling hole that would let a relayout move one and not the other.
- Two independent runners guard it: `games/sonic4/test/poison/poison_vdp_base_residue.emp` (+
  its row in `tools/emp_expect_fail.py`) proves the `ensure` fires; `tools/test_vdp_base_registers.py`
  proves the rows stay *derived* — the half the `.emp` guard structurally cannot cover.

**What this means for this design:** the granules in §0 are not a table this document invented,
they are the ones the build enforces, and an option that proposed a misaligned base would fail
the build by name rather than silently point the VDP somewhere no consumer writes. Option P's
`$6000` satisfies every granule in the table. **This design is built on the fold, and the fold
is there.**

One caveat inherited from that entry and repeated here so it is not lost: the five *shifts* are
cross-checked against two reference disassemblies, but the **H40 ignored-bit rules behind the
`$1000` window granule and the `$400` SAT granule come from hardware documentation and are the
stricter reading**. A wrong choice there can only refuse a base that would have worked, never
admit one that would not. `$6000` is a multiple of `$2000` and therefore satisfies the loose
and strict readings alike.

---

## 8. TAGGED FOR RUNTIME CONFIRMATION (no emulator was used in this design)

Per the constraint, nothing below was checked on hardware or in Oracle. Each is a *design
assumption whose failure changes a cost, not the recommendation*.

- **Q1 — Plane Z's out-of-strip rows.** Re-pointing reg `$04` at `$6000` makes Plane B a 64×64
  plane spanning `$6000-$7FFF`, of which only `$6000-$6FFF` is ours; rows 32-63 would fetch the
  sprite/character band at `$7000-$7FFF`. Does the 48-px strip use-case ever put those rows on
  screen? Determined by the VSRAM value at the moment of the swap. **If it does, Plane Z needs
  a full 256-tile `$2000` slot and Option P is not sufficient for 11b** (10c is unaffected).
  Cheap to answer: point reg `$04` at `$6000` in a scratch build and look.
- **Q2 — mid-frame base-register latch timing.** ~~Does a reg `$02`/`$04` write during HBlank
  take effect on the next line?~~ **Largely answered by §10.1 — the bases are not latched at
  all, they are re-read per nametable fetch.** What remains for the runtime lane is the
  *engine-local* question: does our HBlank handler's existing write window (the derived spin
  count, row N+1 convention) land inside the ~860-master-cycle deadline that Genesis Plus GX
  models for a same-line effect? Does not change any tile count.
- **Q3 — the R9 left-window artifact does not apply to a top band.** Oracle models the bug at
  `oracle/crates/oracle-core/src/render.rs:1272` as specific to a **left** window. The DoD
  already assumes top/bottom avoids it. Worth confirming against Oracle's golden
  (`crates/oracle-core/tests/golden_frames.rs:184-206`) before committing to a top band.
- **Q4 — plane-role swap's scroll plumbing.** Swapping reg `$02`/`$04` swaps which nametable
  is front, but the HScroll table's per-line A/B word pair and VSRAM's even/odd entries are
  addressed by *plane*, not by *content*. Confirm the swap needs a matching swap of the scroll
  feeds (expected: yes) — this is a code cost on 10b, which this design prices at zero *tiles*,
  not zero *work*.

---

## 9. Claims in the brief this design was written from — confirmed and corrected

Stated plainly, because being contradicted was asked for.

**Confirmed:**
- The free runs total **12 tiles** at bases 957 (3), 1022 (2), 1501 (3), 1532 (4). Exactly
  right — `docs/generated/vram-map-sonic4.md` ends with *"Free: 12 tiles across 4 runs."*
  (I initially read a stale copy from the main worktree, which sits at `73b07a4f` and lacks
  `debug_readout`; the brief was right and my first read was wrong.)
- `window_plane` already declares `overlay_with = ["plane_b"]` and aliases Plane B's tail with
  the window disabled (regs `$11`/`$12` = 0). Confirmed, and the brief is right that it is the
  most interesting line in the file — though for a reason the brief does not state: the alias
  is at `$F000`, which is Plane B **rows 32-63**, so enabling the window today would corrupt
  the bottom half of the background.
- The `character_window` pin and its two-fixture re-stamp. Confirmed at
  `games/sonic4/vram.toml:83-88` and linker spec §4.1.
- The VDP base-register entry is closed and the fold is in place. Confirmed — §7.
- Items 10 and 11 are both `blocked` on this, on the same "item 0". Confirmed at
  `docs/DEFERRED_WORK.md:16989-16990` and §"⚠ ITEM 0" at :17205.

**Wrong, and it matters:**

1. **"`POOL_TILE_CEILING` … drives `PAGE_FRAMES` and sizes two RAM arrays, so it moves RAM."**
   **This was true and is no longer.** `engine/system/constants.emp:287-301` records the
   2026-08-11 prep parcel that split `PAGE_FRAMES` (the live count) from `PAGE_FRAMES_MAX`
   (the fixed capacity that sizes the arrays), *because* a 960 → 896 change had previously
   *"slid every debug cell below the scratch array by -2, moved 126 pins, and desynced the
   replay fixtures on a behaviour-identical build."* The comment's own conclusion:
   `POOL_TILE_CEILING` is **"a genuinely VRAM-only knob."** The brief flagged this as
   unverified and asked for it to be checked; it was, and the note it came from is one parcel
   out of date. **This correction is what makes the recommended option cheap** — under the old
   reading Option P would have owed the pin/goldens ritual and Option C would have looked
   competitive.

2. **"A nametable is 256 tiles for a 64×32 plane, 128 for the window."** The *numbers* match
   what we ship, but the *reason* is wrong and the error is a factor of two. 64×32 cells × 2 B
   = `$1000` = **128** tiles. Our planes are 256 tiles because they are **64×64**
   (`boot_data.emp:183`, reg `$10` = `$11`), not because 64×32 costs 256. This matters
   downstream: it is why "shrink a plane to 64×32" (Option C) *appears* to free 128 tiles per
   plane and actually does — and equally why a *window*, at 128 tiles, is a full 64×32 table
   and not half of one.

3. **"`bg_region`'s comment calls `tiles` a hard VRAM boundary … so this one may be immovable
   upward by construction — check whether that is truly a hardware boundary."** Checked: **it
   is not a hardware boundary.** The SAT's base register `$05` has a `$400` granule
   (`engine/vdp.emp:107`) and is freely relocatable; `engine/system/constants.emp:396` records
   that it has *already been relocated once*, from `$D800` to `$B800`. `bg_region`'s ceiling is
   a **consequence of the current layout** — it is bounded above by the SAT only because the
   SAT is there, and the SAT is there because Plane A starts at `$C000` and Plane A's base has
   nowhere else `$2000`-aligned to go. The binding constraint is the plane alignment, not the
   SAT. The TOML comment overstates it, and the overstatement is load-bearing in the wrong
   direction: it makes the BG look immovable when what is actually immovable is the plane.

4. **"A nametable is 256 tiles … so the room does not exist and something has to give."**
   Something does have to give, but the framing hides the cheaper half of the answer: **three
   of the five sub-features in items 10 and 11 need no new VRAM at all** (§2), including the
   nametable-base-change *mechanism* that item 11 is named for. The brief treats item 0 as
   strictly upstream of both items; it is upstream of two sub-features out of five.

**Also worth flagging, found while deriving:**

- `engine/system/constants.emp:282-284` still describes the pool as 960 tiles / 15 frames. It is
  896 / 14. A comment one relayout behind the code, in the file this design proposes to edit
  next.
- **`games/sonic4/vram.toml`'s `band_reserve` block reads as present tense and is not.** Its
  *"The 2026-07-21 import packed to 448/448"* describes the destroyed configuration; the shipped
  blob is 320 tiles. I restated it and got Option B wrong until I measured `bg_tiles.bin`
  (§3). Two documents in the same repo, both a relayout behind, both in files this parcel
  touches — the tell is that both are prose beside a number rather than a derivation *of* it,
  which is the same failure the `vdp_base_reg` fold (§7) was built to end for registers. **The
  reserve block deserves the same treatment or at least a dated "as of" line.**

---

## 10. Research — what the hardware documentation and the reference games actually do

### 10.1 The mid-frame base swap is documented, shipped, and named after the exact game the DoD cites

Item 11's "Batman mid-frame base swap" is not folklore. Eke-Eke, SpritesMind thread 972
(*"Adventures of Batman & Robin (glitch during 2nd Boss)"*), verbatim:

> *"what happens is the game is writing **VDP register #4 during HBLANK to modify Plane B
> nametable address from that line**. … it means that **planes nametable registers are not
> latched at the start of the line and can probably be modified anytime during a line**. As I
> see it, **VDP regs #2 #3 and #4 are read by VDP before reading each pixel data block from
> VRAM**."*

Genesis Plus GX implements it with the game named in a source comment, and the guard states the
timing budget explicitly: the write must land within the first **~860 master cycles** of the
line (≈122 68000 cycles at 7.67 MHz) for that line to pick it up.

```c
case 4: /* Plane B Name Table Base */
  reg[4] = d;  ntbb = (d << 13) & 0xE000;
  /* Plane B Name Table Base changed during HBLANK (Adventures of Batman & Robin) */
  if ((v_counter < bitmap.viewport.h) && (reg[1] & 0x40) && (cycles <= (mcycles_vdp + 860)))
    render_line(v_counter);
```

The same guard exists for `case 2` and `case 3`. Kabuto's fetch-pattern notes give the physical
reason: the H40 line pattern is `Hssss AsaaBsbb ((A~aaBSbb)*3 AraaBSbb)*5 …` — **one HScroll
fetch at line start, then A and B nametable fetches interleaved through the line**, so the base
registers are consulted per fetch rather than per line.

**One constraint this hands item 11, and it is a real design input, not trivia: the HScroll
value is fetched ONCE per line and is not re-read.** Kabuto: if the slot is missed *"the VDP
will just keep on using the previously fetched HScroll value."* So a band boundary placed
mid-*line* gets a new map but shares the line's horizontal scroll. **Band boundaries must be
line boundaries if the two bands need different scroll.** That is a cheap thing to know before
building a strip streamer and an expensive thing to discover after.

### 10.2 The window's own registers are cheaper than expected

`genvdp.txt` on reg `$11`: *"This register can be modified with changes taking effect
immediately at any point in the display frame."* Combined with reg `$03`'s `$1000` granularity,
that means the window's **map source and extent are both per-band steerable** — a fixed-position
band layer whose map changes per raster band, at `$1000` per map and half the alignment
scarcity of a plane. It does not scroll (§2.1), which is the whole trade.

The left-window column bug is documented and its trigger is narrow — `genvdp.txt`: it fires
only when the window is *partially* covering from the **left** and *"the lower four bits of the
horizontal scroll value for the current scan line are nonzero"*, in which case column WHP+1
fetches its attributes from WHP+2. A **top or bottom band spanning the full line width does not
trigger it**, which is what the DoD's top/bottom preference is for and what Oracle's R9 model
(`render.rs:1272`, *"right of a **left** window"*) already encodes. **Q3 is effectively answered
in the affirmative by the primary source**; the Oracle golden check remains worth doing as a
cross-check of our model, not of the hardware.

### 10.3 The plane-size table, and why 128×32 is not a way out

`genvdp.txt`: *"The name table size cannot exceed 8192 bytes, so while a 64x64 or 128x32 name
table is allowed, a size of 128x128 or 64x128 is invalid."* Reg `$10`'s size field `10b` is
**invalid** and degenerates to *"the first row of the name table is shown for every line"*.

| plane size | cells | bytes | tiles |
|---|---|---|---|
| 32×32 | 1024 | `$800` | 64 |
| 64×32 | 2048 | `$1000` | 128 |
| **64×64** (ours) | 4096 | **`$2000`** | **256** |
| 128×32 | 4096 | `$2000` | 256 |

So 128×32 costs exactly what 64×64 costs and buys horizontal width we do not need at 320 px
wide. **32×N is not available in H40** (32 cells = 256 px, narrower than the screen). The only
size reduction available to us is 64×64 → 64×32, which is Option C, and Option C is rejected
in §3.

### 10.4 Moving the SAT is a one-way, boot-time decision — a hazard for Option B's `$2000` variant

Option B's `$2000`-aligned variant requires relocating the sprite attribute table. **Do not
treat reg `$05` like reg `$02`/`$04`.** Kabuto, verbatim:

> *"The VDP has an internal sprite cache that caches the Y and size/link fields of each sprite
> … the moment a write to VRAM occurs the VDP checks whether it goes to the current location of
> the sprite table … **And this is the only way of updating the cache, moving the sprite table
> address will NOT update cache contents** (so contents of the cache and underlying memory will
> differ)."*

Charles MacDonald reports the observed symptom in SpritesMind 666: after a base change, sprites
*"pick up h-pos values from the new tables but not v-pos changes."* Our SAT has already been
relocated once (`engine/system/constants.emp:396`), at boot, which is safe; relocating it again
is also fine **at boot**, but the technique must never be used as a runtime effect and the
design of any future relayout must not assume it can be.

### 10.5 Cell scroll does not shrink the HScroll table — Option D's saving does not exist

Worth recording because a plausible-sounding secondary source says otherwise. md.railgun.works
describes cell scroll as *"every longword … every 8-pixel row"*, which reads as 28 consecutive
longwords = 112 bytes. **The entries are not consecutive.** Genesis Plus GX's mask table is
`{0x00, 0x07, 0xF8, 0xFF}`, indexed `base + ((line & mask) << 2)`, so cell scroll reads offsets
`$000, $020, $040 … $360` — **the same `$380` span as line scroll, sampled every 8th longword.**
Only full-screen scroll mode (`$0B` = `%00`, one longword read) genuinely frees the block, and
we cannot use it: per-line HScroll is unconditional since 2026-08-26
(`engine/level/scene_dsl.emp:199`). §3's Option D verdict stands on primary evidence.

### 10.6 What the reference games actually do about plane pressure

- **Thunder Force IV**, the obvious candidate for "how do I get more layers": *it does not use a
  third nametable.* Its celebrated stage-1 parallax is **line-scroll banding on the existing two
  planes**, arranged so the bands never overlap — rasterscroll, on the same stage: *"the near
  foreground and the background **actually never overlap since they are the same layer**."* Five
  apparent layers, two nametables, zero extra VRAM. **This is the cheapest technique in the
  whole survey and it is the one we should reach for before spending tiles.**
- **The Adventures of Batman & Robin** is the one game that genuinely time-multiplexes a base
  register per raster band (§11.1) — i.e. it is the only reference that does what item 11 asks
  for, and it does it on reg `$04`, plane B, exactly as the DoD's "Plane Z" description says.
- **Titan Overdrive 2** does not add a plane. Kabuto: its effects use the undocumented debug
  register at `$C0001C`, bits 7-8 of which *"force one plane permanently active"* — a
  blending/masking trick, not an extra layer, and explicitly fragile across VDP revisions
  (*"stability of the debug registers mostly affects 1st generation VDP chips"*). **Given the
  standing no-real-hardware constraint, this is the one MD technique where emulator agreement
  is worth the least, and it should stay off our list.**
- **No source found describes a genuine fourth map on screen.** The VDP has three name tables,
  W substitutes for A, and the only way to exceed three is to time-multiplex a base across
  raster bands. That is item 11, and it is why item 11 is the item that buys capability.

*(Sources: `genvdp.txt` v1.5f · Plutiedev VDP register reference and Kabuto hardware-notes
mirror · md.railgun.works VDP · SpritesMind threads 972, 666, 2604 · Genesis Plus GX
`core/vdp_ctrl.c` / `core/vdp_render.c` · rasterscroll.com. A reported claim that Thunder Force
IV's top four rows are a window came from a search summary only and is **unverified**.)*

---

## 11. Open for the owner

1. **Approve Option P** (pool 896 → 768) — or say which cost you would rather pay.
2. **Ruling asked by the DoD and not yet given: HUD = sprites.** The DoD folds the HUD decision
   into item 0 and aeon has already concurred (`DEFERRED_WORK.md`, "HUD = sprites — CONCUR"),
   with the cost recorded: a sprite HUD spends SAT entries and per-line sprite budget that the
   set-pieces of items 10/11 also want. **If the HUD is ever to be the window instead, the
   window nametable stops being available as a third layer** and item 10c dies. Confirming
   "sprites" here is what makes the `$6000` region spendable on effects.
3. **Do items 10a/10b/11a get started before this parcel?** §4 says they can, and §2.0 says
   they need no new engine mechanism to do it. That is a sequencing call, not a technical one.
4. **Would you rather spend the BgAnim band reserve than FG-pool frames?** Option B is real,
   available today, and costs no shipped art (§3, corrected by measurement). It buys a 16-row
   top window band at `$B000` and can never buy item 11b. If item 10c is what you want and 11b
   can wait, B is the cheaper purchase and P stays available for 11b later, with the two costs
   landing on different budgets. **The reserve is your dial and the doc does not spend it for
   you.**
5. **Is the freed run declared as a `[[region]]` now, or as `[[free]]`?** Declaring it as a
   named region immediately makes the map self-documenting and reserves the address against the
   next person looking for 128 tiles; declaring it `[[free]]` keeps the parcel to one knob and
   defers the naming to whoever consumes it. Either passes the generator (both were run, §3).
   The recommendation is a named region with `owner = "engine.system.boot"` and no `register`
   field until a consumer wires one, because an unnamed run is exactly how the BG band reserve
   reached zero (`docs/BUGS.md` TOOL-01, the precedent the TOML's own comment cites).
6. **Item 10c after §2.1 — do you still want it?** The window is a region-exclusive substitute
   for Plane A, not a fourth layer. It buys a non-scrolling band. If what you pictured was a
   third parallax layer, item 11b is the sub-feature that delivers it and 10c can be dropped —
   which would not change the procurement (one `$2000`-aligned run serves either) but would
   change what gets built on top of it.
