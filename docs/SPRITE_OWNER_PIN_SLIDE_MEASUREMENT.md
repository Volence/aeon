# Why `ANIMATE.debug_base` slid +0x46 while the ROM file grew +0x20

Measurement report for aeon parcel `cbd04ba8` ("record which object emitted each
hardware sprite (DEBUG only)"), produced for the sigil lane's `repin_pins.rs`
baseline.

Everything below is measured from built artifacts. Where a causal account is
offered it is labelled INFERENCE and is separable from the numbers.

## Headline

**The +0x46 and the +0x20 are not two views of one quantity, so there is no sum
that should close between them.** They measure different things:

- **+0x46** is how far one *region base* moved inside the assembled image. Total
  code growth was **+0x50 (80 B)**; `AnimateSprite` sits between the +0x46 mark
  and the last +0xA of it, so it inherits 0x46 and not 0x50.
- **+0x20** is how much the *file on disk* grew. The assembled image did not
  change size at all (`EndOfRom` = `0xA7E70` in both). All 32 bytes are growth of
  the appended `deb2` symbol table.

The 80 bytes of code growth cost the image nothing because it all lands upstream
of the `object_bank at = 0x10000` anchor and was absorbed by that section's
existing pad.

So the arithmetic that closes is:

```
  +0x46  ANIMATE.debug_base slide      (code growth AHEAD of AnimateSprite)
+ +0x0A  DrawRings growth              (code growth BEHIND AnimateSprite)
= +0x50  total debug-shape code growth  -> absorbed entirely by pad before 0x10000
                                        -> assembled image size UNCHANGED

  +0x20  file growth = deb2 symbol-table growth, and nothing else
```

`70`, `32`, `33` and `65` were never required to relate. The number that had to
be explained is 0x46 vs 0x50, and it is explained by one 10-byte block landing
downstream of the region under test.

## Provenance

Every number in this document was taken at:

| | |
|---|---|
| Assembler | `sigil` revision `fbf60abd16127e14d02e384aff84c4ed8d1143f9` |
| | (its banner prints `fbf60abd-dirty`; the `-dirty` suffix is the known stale constant, quote the revision) |
| Verified | `$SIGIL_BUILD --version` re-read after the last build; revision unchanged throughout |
| sigil repo | clean working tree; `70562196` when the baseline files were read |
| | (HEAD advanced to `cca40a9c` mid-run — 4 notes/ledger/lane-log commits; `git diff 70562196..cca40a9c` over `pins.rs`, `repin_pins.rs` and `repin.toml` is EMPTY, so every reading below still holds) |
| `SIGIL_EMIT` | `sigil/target/release/emit_sound_blob` |
| `AEON_SKDISASM_DIR` | `/home/volence/sonic_hacks/skdisasm` |
| Emulator | none used, at any point |

Three clean `git worktree` checkouts, each built from scratch with the ROMs
`rm -f`'d first so their existence witnesses a real build:

| tree | commit | s4 | s4.debug | demo | demo.debug |
|---|---|---|---|---|---|
| pre | `b391b821` (parcel's first parent) | `21cc1347` / 718999 | `9732c56a` / 735420 | `3415e3ef` / 96372 | `b6f9759f` / 101080 |
| post | `cbd04ba8` (the parcel) | `21cc1347` / 718999 | `8c01d7ed` / 735452 | `3415e3ef` / 96372 | `7599953e` / 101113 |
| tip | `7511a440` (master) | `21cc1347` / 718999 | `8c01d7ed` / 735452 | `3415e3ef` / 96372 | `7599953e` / 101113 |

All eight CRCs quoted in the brief reproduced exactly.

**Tip == post, byte-identical, all four ROMs and all four `.lst` files.** So a
freeze taken at the tip carries exactly the parcel's numbers. `ANIMATE.debug_base`
at the tip is `0x3C14`, read directly from `wt-tip/s4.debug.lst`.

Instrument: the sigil-canonical `.lst` symbol listing plus the ROM images. See
"Instrument validation" below for the control that establishes the listing is a
faithful stand-in for sigil's own resolve.

## 1. Per-region delta table, DEBUG shape (s4)

Measured by diffing every symbol in `s4.debug.lst`, pre vs post, in address
order. 2709 -> 2711 symbols; 1239 moved.

### 1a. The cumulative-delta profile

Each row is the first symbol at which the running delta changes. The two
"streams" are separated because Z80-space (`phase`) labels share the numeric
range 0x8000+ with main-ROM labels; sorting naively interleaves them.

**Main ROM stream:**

| pre | post | cumulative delta | first symbol at this delta |
|---|---|---|---|
| `0x000000` | `0x000000` | `+0x00` | `Vectors` |
| `0x0037DC` | `0x0037EE` | `+0x12` | `Render_Sprites$band_loop` |
| `0x003920` | `0x003934` | `+0x14` | `Render_Sprites$multi_sprite` |
| `0x00392C` | `0x003942` | `+0x16` | `Render_Sprites$sibling_loop` |
| `0x00399C` | `0x0039B4` | `+0x18` | `Render_Sprites$sibling_advance` |
| `0x003ADE` | `0x003AFE` | `+0x20` | `Emit_ObjectPieces$pieces_xflip` |
| `0x003B1A` | `0x003B42` | `+0x28` | `Emit_ObjectPieces$pieces_yflip` |
| `0x003B56` | `0x003B86` | `+0x30` | `Emit_ObjectPieces$pieces_xyflip` |
| `0x003BA0` | `0x003BD8` | `+0x38` | `InsertSpriteMasks` |
| `0x003BCC` | `0x003C12` | **`+0x46`** | `InsertSpriteMasks$masks_done` |
| `0x0041F6` | `0x004246` | **`+0x50`** | `DrawRings$x_ok` |
| ... | ... | `+0x50` | (holds through `Sound_GetComm` at `0x00AF1A -> 0x00AF6A`) |
| `0x010000` | `0x010000` | `+0x00` | `ObjCodeBase` |

**`AnimateSprite` is at `0x3BCE -> 0x3C14`, i.e. inside the `+0x46` band** — it
sits after the last sprites-module growth and before the DrawRings growth.

**Z80/phase stream** (unmoved, correctly): `SoundTablesZ80_Head` `0x8000`,
`SndDefaultPitchTable` / `MovingTrucks_PitchTable` `0x8357`, `SfxBlobWinTab`
`0x845F`, `SeqOpcodeTable` `0x8571`, `DacSampleTable` `0x85B1`.

### 1b. Growth decomposition (measured, sums exactly)

| site | bytes | hex |
|---|---|---|
| `Render_Sprites` prologue (new label `owner_clear` at post `0x37C6`) | 18 | `+0x12` |
| `Render_Sprites$band_loop` .. `multi_sprite` | 2 | `+0x02` |
| `multi_sprite` .. `sibling_loop` | 2 | `+0x02` |
| `sibling_loop` .. `sibling_advance` | 2 | `+0x02` |
| `Emit_ObjectPieces` unflipped variant | 8 | `+0x08` |
| `Emit_ObjectPieces` xflip variant | 8 | `+0x08` |
| `Emit_ObjectPieces` yflip variant | 8 | `+0x08` |
| `Emit_ObjectPieces` xyflip variant | 8 | `+0x08` |
| `InsertSpriteMasks` mask loop | 14 | `+0x0E` |
| **subtotal, all in `engine/objects/sprites.emp`** | **70** | **`+0x46`** |
| `DrawRings` SAT-write site, in `engine/objects/rings.emp` | 10 | `+0x0A` |
| **total debug-shape code growth** | **80** | **`+0x50`** |

The 10-byte rings figure is independently derivable from the parcel diff: the
DEBUG-fenced block added to `DrawRings` is `move.w d5,d0` (2) + `add.w d0,d0`
(2) + `move.w #1,(a6,d0.w)` (6) = 10 bytes. It matches the measurement.

`git diff --stat b391b821 cbd04ba8` touches exactly three source files:
`engine/objects/sprites.emp` (+121), `engine/objects/rings.emp` (+29),
`engine/ram.emp` (+20). The rings growth is part of this parcel, not a
neighbour's.

### 1c. RAM

| symbol | pre | post | delta |
|---|---|---|---|
| `Sprite_Owner` | (absent) | `0xFFFFE1EE` | NEW, 160 B = `[u16; MAX_VDP_SPRITES]` |
| every debug RAM symbol in `0xFFFFE1EE .. 0xFFFFE226` | | | `+0xA0` |
| `Player_Pos_Ring` `0xFFFFE400` and everything after | | | `+0x00` |

10 RAM symbols moved, all by exactly `+0xA0`. `PLAYER_1` (`0xFFFF8E48`) and
`DYNAMIC_SLOTS` (`0xFFFF8EE8`) are far below the insertion point and did not move.

### 1d. Nothing above the anchor moved — proved, not assumed

| shape | moved symbols | ROM span of movement | any moved ROM symbol >= `0x10000`? |
|---|---|---|---|
| s4.debug | 1239 (1229 ROM, 10 RAM) | `0x37DC` .. `0xAF1A` | **NO** |
| demo.debug | 1036 (1034 ROM, 2 RAM) | `0x1F1C` .. `0x8348` | **NO** |

This is what licenses the claim that every region living wholly above `0x10000`
(the whole game-data and test-scaffolding population) is untouched, including the
manifest entries whose end labels the `.lst` does not carry.

## 2. The reconciliation

### 2a. Why +0x50 of code cost the image zero bytes

`games/sonic4/map.toml`:

```
[[section]]
name = "object_bank"     # ObjCodeBase — the 64KB object code bank
at = 0x10000
```

`at =` is a hard placement anchor. The main code stream's last moved symbol is
`Sound_GetComm` at pre `0xAF1A` -> post `0xAF6A`, and the contiguous ROM byte-diff
region ends at `0xAF72`. Slack ahead of the anchor is therefore about
`0x10000 - 0xAF72 = 0x508E` (~20.6 KB) — three orders of magnitude more than the
80 bytes needing absorption.

`EndOfRom` = **`0xA7E70` in both pre and post**. The assembled image did not
change size. The brief's hypothesis — "slack ahead of a fixed anchor would let a
base slide further than the file grows" — is **confirmed**, and in fact the
stronger form holds: the file did not grow *from code at all*.

### 2b. Where the +0x20 actually comes from

The `deb2` magic sits exactly at `EndOfRom` in both builds (sigil's own
`native_full_rom.rs` asserts this invariant independently):

| | pre | post | delta |
|---|---|---|---|
| s4.debug file | 735420 | 735452 | +32 |
| s4.debug `EndOfRom` (image end) | `0xA7E70` = 688752 | `0xA7E70` = 688752 | **0** |
| s4.debug `deb2` appendix | 47692 | 47724 | **+32** |
| demo.debug file | 101080 | 101113 | +33 |
| demo.debug `EndOfRom` | `0x1121C` = 70172 | `0x1121C` = 70172 | **0** |
| demo.debug `deb2` appendix | 30908 | 30941 | **+33** |

**100% of both files' growth is the symbol table.** The parcel's net symbol
change is +2 (9 new, 7 gone), plus a rename cascade in the anonymous `asmN`
counter.

### 2c. +32 vs +33 between the games

Read from the `deb2` header's big-endian u32 block-offset array (at appendix
offset 4):

**s4.debug**, 8 blocks:

| block | pre size | post size | delta |
|---|---|---|---|
| 0 (`0x506`) | 27684 | 27704 | **+20** |
| 1..6 | 9522 / 2220 / 92 / 56 / 62 / 28 | identical | 0 |
| 7 (last) | 6742 | 6754 | **+12** |
| total | 47692 | 47724 | **+32** |

**demo.debug**, 2 blocks:

| block | pre size | post size | delta |
|---|---|---|---|
| 0 (`0x4FE`) | 24512 | 24532 | **+20** |
| 1 (last) | 5118 | 5131 | **+13** |
| total | 30908 | 30941 | **+33** |

**Measured:** in both games block 0 grows by *exactly* the same +20 — expected,
since both received the identical symbol-set change in the identical engine
module. The entire +32 vs +33 discrepancy lives in the **last block**, which grew
+12 in s4 and +13 in demo. That block is ~30% printable (0.30 in s4, 0.31 in
demo), so it is packed, not a plain string heap.

**Not determined:** the byte-level reason the same 9-new/7-gone name delta packs
to 12 bytes in one game and 13 in the other. That requires convsym's `deb2`
encoding, which is not documented anywhere in the sigil or aeon trees (searched;
only presence/size assertions exist). *INFERENCE, unverified:* a packed/entropy-
coded name heap whose code lengths depend on the whole game's name population
would produce exactly this signature. **Do not write that into a baseline as
fact.** The defensible statement is: one byte, isolated to the final `deb2`
block, game-specific packing.

### 2d. Whether the +0x20 should appear in a pin narrative at all

It should not. `DEBUG_ASSEMBLED_LEN` is `EndOfRom`, which did not move. No pin in
`repin.toml` is a function of the file length. The file-size delta and the pin
slide are disjoint quantities and a ledger term that tries to reconcile them
would be narrating a relationship that does not exist.

## 3. The complete failing-pin set

### 3a. Which assertions actually run

`repin_pins.rs` has three `#[test]` fns:

| line | fn | status |
|---|---|---|
| 34 | `pins_rs_is_current` | live — regenerates and diffs, see §4 |
| 91 | `generated_pins_match_the_hand_typed_baseline` | live — assertions at lines 262-1088 |
| 1100 | `secondary_pin_classes_match_the_hand_typed_baseline` | **`#[ignore]`** — RETIRED by Wave-B B-0; assertions at lines 1103-1286 never run |

This matters for the brief's framing. `assert_eq!` panics on first mismatch
*within a fn*, and there are two live fns, so the red run naming only
`ANIMATE.debug_base` tells you about `generated_pins_match_the_hand_typed_baseline`
only.

### 3b. Live failures — the complete set is THREE

All 29 live assertions evaluated against the tip build. Every one that is not
listed here was checked and passes.

| line | pin | shape | asserted | measured (post/tip) | delta |
|---|---|---|---|---|---|
| 565 | `ANIMATE.debug_base` | debug | `0x3BCE` | `0x3C14` | **+70 (+0x46)** |
| 573 | `RINGS.debug_base` | debug | `0x408E` | `0x40D4` | **+70 (+0x46)** |
| 584 | `RINGS.debug_len` | debug | `0x21A` | `0x224` | **+10 (+0x0A)** |

Verified-passing live assertions (26): `BOOT.{plain,debug}_{base,len}`,
`BOOT_DATA`, `ANIMATE.plain_base`, `ANIMATE.plain_len`, **`ANIMATE.debug_len`**,
`RINGS.plain_base`, `RINGS.plain_len`, `CORE.{plain,debug}_{base,len}`,
`DPLC.{plain,debug}_{base,len}`, `DELETE_OBJECT`, `OJZ_ACT_POOL.{plain,debug}_len`,
`SCENE_REGISTRY.{plain,debug}_len`, `ASSEMBLED_LEN`, `DEBUG_ASSEMBLED_LEN`,
`CC_DELETE_OFF`.

Three of those non-failures are worth stating explicitly, because they are the
ones a hand-written term would most likely get wrong:

- **`ANIMATE.debug_len` holds at `0x2B8`.** The region is `AnimateSprite`..
  `TouchResponse`; both endpoints take the same `+0x46`, so the length is
  invariant. The parcel adds nothing between them.
- **`CC_DELETE_OFF` holds** (`0x104` / `0x15E`). It is animate-region-relative
  and the +0x0A growth is downstream of the whole animate region.
- **`RINGS.debug_len` moves but `RINGS.plain_base/plain_len` do not.** The +0x0A
  is the DEBUG-fenced block inside `DrawRings`, which is inside the rings region
  — so it lengthens that region rather than sliding it.

### 3c. The retired fn, for completeness

If `secondary_pin_classes_match_the_hand_typed_baseline` is ever un-ignored it
fails on its first assertion. Note that four of its literals were **already stale
before this parcel** — they are not this parcel's debt:

| line | pin | asserted | pre | post | moved by this parcel? |
|---|---|---|---|---|---|
| 1103 | `RINGCOL_OFF.plain` | `0x116` | `0x116` | `0x116` | no |
| 1103 | `RINGCOL_OFF.debug` | `0x172` | `0x172` | `0x17C` | **yes, +0x0A** |
| 1264 | `SOUND_API.plain_base` | `0x7A9E` | `0x7EAE` | `0x7EAE` | no — stale before |
| 1265 | `SOUND_API.debug_base` | `0xA330` | `0xAAD0` | `0xAB20` | stale before, AND +0x50 |
| 1272/3 | `SOUND_API.{plain,debug}_len` | `0x2A8`/`0x452` | same | same | no (literal-len region) |
| 1274 | `SOUND_PLAY_SFX_OFF` | `0x126`/`0x28A` | same | same | no |
| 1278 | `MDDBG_ERROR_HANDLER` | `0x5E8F2` | `0xA6F1A` | `0xA6F1A` | no — stale before |
| 1279 | `MDDBG_ERROR_HANDLER_PAGES_CONTROLLER` | `0x5F6B8` | `0xA7CE0` | `0xA7CE0` | no — stale before |
| 1284 | `PLAYER_1` | `0xFFFF8CFA`/`0xFFFF8D88` | `0xFFFF8E48`/`0xFFFF8ED6` | unchanged | no — stale before |
| 1286 | `DYNAMIC_SLOTS` | `0xFFFF8D9A`/`0xFFFF8E28` | `0xFFFF8EE8`/`0xFFFF8F76` | unchanged | no — stale before |

## 4. `pins_rs_is_current` — the other live failure

`crates/sigil-harness/src/pins.rs` as committed holds `ANIMATE.debug_base =
0x3BCE`, the **pre** value. Its last commit is `521956f9` ("refreeze:
band-ceiling-16 (chain 172) ... s4.debug 9732c56a") — and `9732c56a` is the
pre-parcel debug CRC. So `pins.rs` pairs the pre ROM, and after this parcel
`pins_rs_is_current` fails too, reporting the whole changed set at once.

**Consequence worth flagging:** as the sigil tree stands at `70562196`, the
assertion quoted in the brief would *pass*, because `pins::ANIMATE.debug_base`
reads `0x3BCE` from the committed file and the literal is `0x3BCE`. The red run
that produced `left: 15380 (0x3C14)` must have been taken against a **regenerated**
`pins.rs` (i.e. after `cargo run -p sigil-harness --bin repin`). The correct
landing order is therefore: regenerate `pins.rs`, then update the three literals
in §3b.

**74 pin values change pre -> post.** Grouped by delta:

| delta | count | what |
|---|---|---|
| `+0x46` | 7 | `SPRITES.debug_len`, `ANIMATE.debug_base`, `COLLISION.debug_base`, `RINGS.debug_base`, `DRAWRINGS.debug`, `RINGBUFFER_CLEAR.debug`, `RINGBUFFER_REMOVE.debug` — at or before the rings growth |
| `+0x0A` | 2 | `RINGS.debug_len`, `RINGCOL_OFF.debug` — the growth lands *inside* the rings region |
| `+0x50` | 58 | every engine region base and symbol from `ENTITY_WINDOW` through `SOUND_API` — downstream of `DrawRings`, upstream of `0x10000` |
| `+0xA0` | 7 | debug RAM symbols after `Sprite_Owner`: `CHEAT_FLAGS`, `CHARACTER_ID`, `PLAYER_CHARDEF`, `PLAYER_BLOCKS`, `PLAYER_DEATH_PENDING`, `PLAYER_BOUND_RIGHT`, `PLAYER_BOUND_BOTTOM` |

Every one of the 74 is **debug-shape only**. Zero plain-shape pins change, which
is exactly right for a DEBUG-fenced parcel and is corroborated independently by
the release ROMs being byte-identical.

The complete 74 rows, in manifest order:

| pin | pre | post | delta |
|---|---|---|---|
| `SPRITES.debug_len` | `0x4EE` | `0x534` | `+70` (`+0x46`) |
| `ANIMATE.debug_base` | `0x3BCE` | `0x3C14` | `+70` (`+0x46`) |
| `COLLISION.debug_base` | `0x3E86` | `0x3ECC` | `+70` (`+0x46`) |
| `RINGS.debug_base` | `0x408E` | `0x40D4` | `+70` (`+0x46`) |
| `RINGS.debug_len` | `0x21A` | `0x224` | `+10` (`+0xa`) |
| `ENTITY_WINDOW.debug_base` | `0x42A8` | `0x42F8` | `+80` (`+0x50`) |
| `CHILDREN.debug_base` | `0x5010` | `0x5060` | `+80` (`+0x50`) |
| `LOAD_OBJECT.debug_base` | `0x53B0` | `0x5400` | `+80` (`+0x50`) |
| `PLANE_BUFFER.debug_base` | `0x5438` | `0x5488` | `+80` (`+0x50`) |
| `TILE_CACHE.debug_base` | `0x57B0` | `0x5800` | `+80` (`+0x50`) |
| `COLLISION_LOOKUP.debug_base` | `0x68B0` | `0x6900` | `+80` (`+0x50`) |
| `SECTION.debug_base` | `0x6E14` | `0x6E64` | `+80` (`+0x50`) |
| `CAMERA.debug_base` | `0x72A0` | `0x72F0` | `+80` (`+0x50`) |
| `PARALLAX.debug_base` | `0x7480` | `0x74D0` | `+80` (`+0x50`) |
| `RASTER.debug_base` | `0x7E14` | `0x7E64` | `+80` (`+0x50`) |
| `PALETTE.debug_base` | `0x8178` | `0x81C8` | `+80` (`+0x50`) |
| `PRESET.debug_base` | `0x8626` | `0x8676` | `+80` (`+0x50`) |
| `LOAD_ART.debug_base` | `0x86C0` | `0x8710` | `+80` (`+0x50`) |
| `PAGE_IN.debug_base` | `0x8778` | `0x87C8` | `+80` (`+0x50`) |
| `PAGE_CACHE.debug_base` | `0x8BD4` | `0x8C24` | `+80` (`+0x50`) |
| `BG.debug_base` | `0x9A50` | `0x9AA0` | `+80` (`+0x50`) |
| `BG_ANIM.debug_base` | `0x9B90` | `0x9BE0` | `+80` (`+0x50`) |
| `COMPRESSION_SELFTEST.debug_base` | `0x9CE8` | `0x9D38` | `+80` (`+0x50`) |
| `SOUND_API.debug_base` | `0xAAD0` | `0xAB20` | `+80` (`+0x50`) |
| `EFFECTS_INSTALLPRESET.debug` | `0x8626` | `0x8676` | `+80` (`+0x50`) |
| `RASTER_GETCHANNELBAND.debug` | `0x811C` | `0x816C` | `+80` (`+0x50`) |
| `CREATEEFFECT_NORMAL.debug` | `0x5316` | `0x5366` | `+80` (`+0x50`) |
| `CREATECHILD_NORMAL.debug` | `0x503C` | `0x508C` | `+80` (`+0x50`) |
| `DELETECHILDREN.debug` | `0x52F8` | `0x5348` | `+80` (`+0x50`) |
| `SOUND_DRAINSFXRING.debug` | `0xADE6` | `0xAE36` | `+80` (`+0x50`) |
| `DRAW_TILECOLUMN.debug` | `0x5440` | `0x5490` | `+80` (`+0x50`) |
| `DRAW_TILEROW_FROMCACHE.debug` | `0x5594` | `0x55E4` | `+80` (`+0x50`) |
| `ENTITYWINDOW_INIT.debug` | `0x49E4` | `0x4A34` | `+80` (`+0x50`) |
| `CHEAT_FLAGS.debug` | `0xFFFFE1F2` | `0xFFFFE292` | `+160` (`+0xa0`) |
| `COLLECTED_MARKRING.debug` | `0x438C` | `0x43DC` | `+80` (`+0x50`) |
| `ENTITYWINDOW_ENTRYFORSECTION.debug` | `0x486E` | `0x48BE` | `+80` (`+0x50`) |
| `ENTITYLOADED_CLEAR.debug` | `0x47F8` | `0x4848` | `+80` (`+0x50`) |
| `SOUND_PLAYRING.debug` | `0xAE36` | `0xAE86` | `+80` (`+0x50`) |
| `BG_INIT.debug` | `0x9A50` | `0x9AA0` | `+80` (`+0x50`) |
| `DRAWRINGS.debug` | `0x4170` | `0x41B6` | `+70` (`+0x46`) |
| `SOUND_PLAYSFX.debug` | `0xAD5A` | `0xADAA` | `+80` (`+0x50`) |
| `RINGBUFFER_CLEAR.debug` | `0x4162` | `0x41A8` | `+70` (`+0x46`) |
| `RINGBUFFER_REMOVE.debug` | `0x412E` | `0x4174` | `+70` (`+0x46`) |
| `SECTION_GETSECPTRXY.debug` | `0x6E64` | `0x6EB4` | `+80` (`+0x50`) |
| `SECTION_FLATIDXY.debug` | `0x6E4A` | `0x6E9A` | `+80` (`+0x50`) |
| `RINGCOL_OFF.debug` | `0x172` | `0x17C` | `+10` (`+0xa`) |
| `PARALLAX_ACTIVE_CONFIG.debug` | `0x75E4` | `0x7634` | `+80` (`+0x50`) |
| `PAGEIN_BANKREGS.debug` | `0x8AB4` | `0x8B04` | `+80` (`+0x50`) |
| `PAGEIN_FLUSH.debug` | `0x8B84` | `0x8BD4` | `+80` (`+0x50`) |
| `PAGEIN_ENQUEUE.debug` | `0x8B46` | `0x8B96` | `+80` (`+0x50`) |
| `PAGECACHE_INIT.debug` | `0x8BD4` | `0x8C24` | `+80` (`+0x50`) |
| `PAGECACHE_ALLOCFRAME.debug` | `0x8CE8` | `0x8D38` | `+80` (`+0x50`) |
| `PAGECACHE_PUBLISH.debug` | `0x8EA8` | `0x8EF8` | `+80` (`+0x50`) |
| `PAGECACHE_PATCHRUN_SEQ.debug` | `0x8F7C` | `0x8FCC` | `+80` (`+0x50`) |
| `PAGECACHE_PATCHRUN_COL.debug` | `0x91BC` | `0x920C` | `+80` (`+0x50`) |
| `PAGECACHE_AUDIT.debug` | `0x953C` | `0x958C` | `+80` (`+0x50`) |
| `VINT_DRAWLEVEL.debug` | `0x56E6` | `0x5736` | `+80` (`+0x50`) |
| `VSCROLL_WRITE.debug` | `0x75F6` | `0x7646` | `+80` (`+0x50`) |
| `SOUND_INIT.debug` | `0xAAF6` | `0xAB46` | `+80` (`+0x50`) |
| `PLAYER_SENSORS.debug_base` | `0x6920` | `0x6970` | `+80` (`+0x50`) |
| `PLAYER_SENSORFLOOR.debug` | `0x6C8C` | `0x6CDC` | `+80` (`+0x50`) |
| `PLAYER_ATLEDGEEDGE.debug` | `0x6DA6` | `0x6DF6` | `+80` (`+0x50`) |
| `PLAYER_SENSORCEILING.debug` | `0x6CA2` | `0x6CF2` | `+80` (`+0x50`) |
| `PLAYER_SENSORWALLDIR.debug` | `0x6D5C` | `0x6DAC` | `+80` (`+0x50`) |
| `PLAYER_SENSORWALLAT.debug` | `0x6D54` | `0x6DA4` | `+80` (`+0x50`) |
| `COLLISION_GETTYPE.debug` | `0x68B0` | `0x6900` | `+80` (`+0x50`) |
| `CHARACTER_ID.debug` | `0xFFFFE1F4` | `0xFFFFE294` | `+160` (`+0xa0`) |
| `PLAYER_CHARDEF.debug` | `0xFFFFE1F6` | `0xFFFFE296` | `+160` (`+0xa0`) |
| `RASTER_VBLANK.debug` | `0x7E1A` | `0x7E6A` | `+80` (`+0x50`) |
| `PALETTE_COMPOSE.debug` | `0x822C` | `0x827C` | `+80` (`+0x50`) |
| `PLAYER_BLOCKS.debug` | `0xFFFFE1FA` | `0xFFFFE29A` | `+160` (`+0xa0`) |
| `PLAYER_DEATH_PENDING.debug` | `0xFFFFE222` | `0xFFFFE2C2` | `+160` (`+0xa0`) |
| `PLAYER_BOUND_RIGHT.debug` | `0xFFFFE224` | `0xFFFFE2C4` | `+160` (`+0xa0`) |
| `PLAYER_BOUND_BOTTOM.debug` | `0xFFFFE226` | `0xFFFFE2C6` | `+160` (`+0xa0`) |

## 5. Instrument validation

The pins are generated from sigil's own native resolve, not from the `.lst`. To
establish that the `.lst` is a faithful stand-in, every value in the committed
`pins.rs` (which pairs the pre ROM, per §4) was recomputed from the **pre**
listings via `repin.toml`:

| check | result |
|---|---|
| Region bases (84 regions x 2 shapes) | **166 match, 2 mismatch** |
| Symbol `Pin`s (x 2 shapes) | **770 match, 0 mismatch** |
| Total | **936 / 938** |

The 2 mismatches are both `SOUNDBANKHEAD` (`pins.rs` `0xA0000`, listing
`0x8000`) — the documented `phase_bank` region whose pin is the **LMA** while the
listing carries the **VMA** in Z80 space. Expected, and handled by
`native::phase_bank_lmas`, not an instrument defect.

Independent corroboration of individual measurements:

- `AnimateSprite` pre = `0x3BCE` reproduces the hand-typed literal exactly.
- `MDDBG__ErrorHandler` = `0xA6F1A` and `..._PagesController` = `0xA7CE0`
  reproduce `pins.rs` exactly, via the `.lst` `EQU` table.
- The `deb2` magic at `EndOfRom` reproduces sigil's own
  `native_full_rom.rs` invariant.
- The measured rings +10 equals the instruction-by-instruction size of the
  added block.

## 6. Corrections to the framing I was given

1. **"Everything since the parcel is doc-only commits."** Not quite. `cbd04ba8..7511a440`
   changes 8 files, of which 4 are tools, not docs: `tools/effects_gates.py`,
   `tools/evict_witness.py`, `tools/sprite_owner_probe.py` (new, 238 lines),
   `tools/test_effects_gates_segments.py`. The *conclusion* the claim was
   supporting survives intact and was verified directly: all four tip ROMs are
   byte-identical to the parcel's.

2. **"`assert_eq!` panics on the FIRST mismatch, so the red run named exactly
   one, and there may be many more behind it."** Correct, and the count is three
   — but the reason there aren't more is partly that the file's third test fn is
   `#[ignore]`d, which is not visible from the failure output. Without that,
   `SOUND_API`/`MDDBG`/`PLAYER_1` would look like this parcel's fallout when in
   fact they were stale beforehand.

3. **"70 does not equal 32, 33, or 65."** True but the framing invites a search
   for a relationship that does not exist. 70 is a code-layout number; 32 is a
   symbol-table number. The quantity 70 genuinely needed to be reconciled
   against was **80**, and that reconciliation is §1b.

4. **A build-gate note, not a finding about the parcel.** A fresh worktree under
   a scratchpad directory fails `build.sh`'s tool-test suite:
   `tools/emp_helper_closure.py::default_native_rs` locates the paired sigil
   checkout at `<dirname(aeon)>/sigil`, so 4 tests error with `FileNotFoundError`
   before any ROM is produced. Resolved here by placing a `sigil` symlink
   *beside* the worktrees (never inside one). Worth knowing for any future
   out-of-tree build.

## 7. What I could not determine

- The byte-level composition of the `deb2` appendix growth (§2c). Localized to
  one block and one byte of game-to-game difference; the encoding is convsym's
  and is undocumented in these trees. Deliberately left open rather than
  narrated.
- Nothing in this report requires runtime confirmation. No emulator was used and
  none is needed; `Sprite_Owner`'s *runtime* correctness is a separate question
  this measurement does not address.

## 8. Suggested ledger terms

Offered as drafts for the sigil lane to accept, reword, or reject — the numbers
are measured, the prose is not binding.

```
ANIMATE.debug_base  0x3BCE -> 0x3C14
  // +0x46 sprite-owner: sprites.emp's DEBUG-only ownership stamps grow
  // Render_Sprites (+0x12), its three sibling steps (+2 each), all four
  // Emit_ObjectPieces variants (+8 each) and InsertSpriteMasks (+0xE) = 0x46,
  // all of it upstream of AnimateSprite. The parcel's TOTAL code growth is
  // 0x50; the remaining 0x0A is inside DrawRings, downstream of this region,
  // which is why this base takes 0x46 and not 0x50. DEBUG only — plain is
  // byte-identical. The image did not grow: EndOfRom holds at 0xA7E70 and the
  // 0x50 is absorbed by pad ahead of object_bank's `at = 0x10000`.

RINGS.debug_base    0x408E -> 0x40D4   // +0x46 sprite-owner: same upstream slide as ANIMATE
RINGS.debug_len     0x21A  -> 0x224    // +0x0A sprite-owner: the DEBUG-fenced owner stamp
  // inside DrawRings (move.w d5,d0 / add.w d0,d0 / move.w #1,(a6,d0.w) = 2+2+6).
  // It lands INSIDE the rings region, so the region lengthens instead of sliding.
```

Explicitly **not** suggested: any term relating the +0x20 file growth to a pin.
Per §2d there is no such relationship; the file grew only in its `deb2` appendix,
which no pin measures.
