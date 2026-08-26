# RING SPARKLE — the collect animation for buffer rings

**Date:** 2026-08-26 · **Branch:** `parcel/ring-sparkle` · **Base:** `master` `f4896139`

Owner's ask, verbatim: *"Make rings look better, they're fine but they don't switch to the
sparkle when you pick them up, they kind of disappear. Also if there's anything else we should
do for them animation wise."*

---

## 0. The measured starting point (overseer, in the emulator + source)

- Rings are **not objects**. They are 6-byte entries in the per-act ring buffer
  (`engine/objects/rings.emp`): `RingBuffer_Add` / `RingBuffer_Remove`, `DrawRings` emits raw
  SAT entries with `attr = RING_ART_ATTR + frame*4`, `RingCollision` tests each player's box
  against each entry. On overlap it marks the collected bit, clears the loaded bit, bumps
  `Ring_Counter`, plays the SFX and `RingBuffer_Remove`s the entry — the ring vanishes in the
  overlap frame (measured: `Ring_Count` 7 -> 6 in that frame, nothing spawned).
  `grep -ri sparkle engine games/sonic4` is empty.
- The spin already matches S3K exactly: `RING_ANIM_FRAMES = 4`, `RING_ANIM_SPEED = 8`
  (`engine/system/constants.emp:180-181`) against S3K's `Rings_frame_timer` reset to 7 /
  `andi #3` (`skdisasm/sonic3k.asm:9675-9677`). **Not touched.**

## 1. What S3K does on collect (the reference, cited)

`skdisasm/sonic3k.asm:35405-35470`:

```
Obj_RingCollect:                          ; sonic3k.asm:35439
    addq.b  #2,routine(a0)
    move.b  #0,collision_flags(a0)        ; no second collect
    move.w  #$80,priority(a0)             ; from $100 -> $80 = IN FRONT of the player
    bsr.s   GiveRing
Obj_RingSparkle:
    lea     (Ani_RingSparkle).l,a1
    bsr.w   Animate_Sprite
    bra.w   Draw_Sprite
Obj_RingDelete:
    bra.w   Delete_Current_Sprite
```

`General/Sprites/Ring/Anim - Ring Sparkle.asm`: `dc.b 5, 4, 5, 6, 7, $FC` — duration byte 5,
mapping frames 4..7, then `$FC` (routine bump -> `Obj_RingDelete` next frame).

`General/Sprites/Ring/Map - Ring.asm` frames 4..7 are **one 2x2 piece each, all on the same
four tiles `$A..$D`**, differing only in the flip bits: `0,$A` / `$18,$A` / `$08,$A` / `$10,$A`
(none / both / H / V). The sparkle is four tiles of art shown in four orientations — the
"four extra frames" cost 4 tiles, not 16.

**Timing, derived not copied.** S3K `Animate_Sprite` (`sonic3k.asm:36160-36178`) reloads
`anim_frame_timer` with the duration byte and advances on `subq.b / bcc` borrow, i.e. a
duration byte N shows each frame for **N+1** display frames. Aeon's `AnimateSprite`
(`engine/objects/animate.emp:91`, `subq.b / bpl`) has the identical N+1 semantics
(`games/sonic4/data/animations/dust_anims.emp` header records this). So the S3K sparkle is
**4 frames x (5+1) = 24 display frames**, and writing the same duration byte `5` in an Aeon
script reproduces it exactly. (The brief's "~20" was the naive 4x5; the comptime gate below
pins the derived 24, computed from the script bytes, never a literal.)

## 2. Design

### 2.1 Shape: an engine hook, a game-side fire-and-forget effect

Rings stay buffer entries — turning them into objects for a 24-frame animation would be
the wrong trade (the buffer exists precisely so 128 rings cost 6 bytes each). Instead:

1. **Engine (generic):** `RingCollision` gains ONE `invoke Game.ring_collected` at the collect
   site, after the collect bookkeeping and **before** `RingBuffer_Remove` (the entry's X/Y at
   `+0/+2` are still valid there). The hook is declared in
   `engine/system/game_contract.emp` as
   `hook ring_collected (a3: *u8) clobbers(d0-d2/a1) = empty` with a3 = the ring's buffer
   entry (X.w/Y.w = its engine-space centre at +0/+2). The POINTER is handed over rather than
   the coords loaded engine-side, so an unbound hook (= the demo game) lowers to **zero
   bytes** — the `boot_hook`/`debug_tick` precedent — and the demo ROM stays byte-identical
   (measured: the first cut loaded d0/d1 on the engine side and moved the demo CRC by 4
   dead bytes; the pointer form restored `bf2cdb42` / `62a0019e` exactly).
   The clobber bound is chosen so `RingCollision`'s live registers across the collect path
   (`a3` rolling entry pointer, `d6` index, `d7` player counter, `d4/d5` player X/Y, `a2` player
   SST) all survive; it is the same bound `DustPuff_Spawn` needs.
2. **Game (sonic4):** the hook binds `RingSparkle_Spawn` (`games/sonic4/objects/ring_sparkle.emp`),
   modelled on `DustPuff_Spawn`/`DustPuff_Main` (`games/sonic4/objects/dust_puff.emp`) — the
   engine's cheapest object: `AllocEffect`, fill the SST (code, x/y as 16.16, mappings, art_tile,
   anim_table, `prev_anim/prev_frame = $FF`, render_flags = band), no velocity, no DPLC, no
   parent link, no timer field. `RingSparkle_Main` is `AnimateSprite` then `Draw_Sprite`; the
   script's `AF_DELETE` retires it. Runs from the Effect sweep (effects always execute).
3. **Placement:** x/y = the ring's centre (the buffer stores centres; `DrawRings` subtracts 8
   for the SAT), and the mapping is `centered(half: 8, w: 2, h: 2, ...)`, so the sparkle sits
   exactly on the ring it replaces.
4. **Priority:** S3K raises the collected ring from `$100` to `$80` = one step **in front of the
   player** (S3K's lower value = front). Aeon's bands are inverted (`Render_Sprites` walks 7 -> 0,
   higher = front), so the relationship, not the number, transfers:
   `EFFECT_RING_SPARKLE_BAND = PLAYER_PRIORITY_BAND + 1`, with the same pair of `ensure`s that
   guard `EFFECT_DUST_BAND` (`games/sonic4/config/constants.emp:78-84`).

### 2.2 Exhaustion policy: skip, never stall

`AllocEffect` returns "pool empty" (`NUM_EFFECTS = 16`, `engine/system/constants.emp:81`) and the
spawner returns — **the ring is still collected** (the counter, SFX and buffer removal happened
before the hook). No eviction, no retry, no per-frame counter: dropping the NEW cosmetic is the
unanimous policy across the reference corpus and the one every existing creator uses
(`children.emp:604`, `dust_puff.emp:52-55`).

Worst case is bounded by geometry, not by a counter. Rings sit on a 16-px grid and the player's
standing box is `2*PLAYER_X_RADIUS+1 = 19` by `2*PLAYER_Y_RADIUS+1 = 39` px
(`engine/system/constants.emp:128-129`), so one player can overlap at most
`ceil((19+16)/16) * ceil((39+16)/16) = 3 * 4 = 12` rings in one frame — under 16. Two players
could reach 24; the 24-frame sparkle life means a burst of >16 simply loses its tail sparkles to
the pool cap and the dust competes for the same 16 slots. Accepted: a spill of 20+ rings in one
frame is a level-design event, and "some sparkles missing for 24 frames" is the correct
degradation. Nothing waits, nothing loops.

### 2.3 Art, VRAM, palette

**Art — donor and pipeline.** The ring's spin art in Aeon already comes from
`sonic_hack/art/nemesis/Ring.bin` (Nemesis, 14 tiles), decompressed with
`sonic_hack/tools/nemdec -d` and composed by `games/sonic4/test/compose_ring.py` into
`games/sonic4/test/ring_art.bin` (the 16-tile spin blob; verified: its frame 0 is byte-equal to
donor tiles 0-3). The S2 ring art carries the sparkle as donor tiles **10-13**, in the same 2x2
column-major layout, and the S2 mappings (`sonic_hack/mappings/sprite/Rings.bin`, frames 4-7:
`000a / 180a / 080a / 100a`) are the same four flip variants as S3K's. The sparkle therefore
comes through the SAME script: `compose_ring.py` gains a second output, the 4-tile
`games/sonic4/test/ring_sparkle_art.bin` (= donor tiles 10..13 verbatim, identity palette). The
script is re-run for the spin blob too and must reproduce the committed `ring_art.bin`
byte-for-byte — that is the tool's own regression check.

**Palette.** The donor's sparkle pixels use indices `{5, 6, C, D}` only (measured over the
four tiles: 0:196, 5:24, 6:8, C:10, D:18) — exactly the set the spin frames use, on CRAM line 1
(outline / white / bright gold / dark gold, `OJZ_Palette` line 1). So the sparkle draws with
`vram_art(VRAM_RING_SPARKLE, 1, 1)` — same line, same priority bit as `RING_ART_ATTR`
(`rings.emp:36`) — and needs no remap. A comptime census in the data module pins the claim: every
nibble of the embedded blob must be in `{0,5,6,C,D}`.

**Mappings.** Four single-piece 16x16 frames on the same base tile with the flip bits in the
piece's tile word — `centered(half: 8, w: 2, h: 2, tile: FLIP)` for `FLIP` in
`{0, $1800, $0800, $1000}` (the S3K order none/both/H/V). The render loop ADDS the piece word to
`art_tile` (`sprites.emp` `tile_term`), and the sparkle's own `render_flags` never carry a flip,
so the piece bits land in the SAT unchanged.

**VRAM.** The declared placement contract is `games/sonic4/vram.toml`, generated into
`docs/generated/vram-map-sonic4.md`. The map as read:

| tiles | name | kind | owner |
|---|---|---|---|
| 0-895 | fg_art_pool | arena | engine.level.page_cache |
| 896-911 | dust_puff | window | games.sonic4.dust_puff |
| 912-923 | dust_spindash | window | games.sonic4.dust_spindash |
| **924-959** | **FREE (36)** | | "the page-quantised carve's remainder — future sprite art" |
| 960-991 | character_window | window | games.sonic4.player |
| 992-999 | test_obj | window | games.sonic4.test_objects |
| 1000-1015 | ring_placeholder | window | engine.objects.rings (sigil-D) |
| 1016-1019 | test_marker | window | games.sonic4.player_common |
| 1020-1023 | FREE (4) | | |
| 1024-1471 | bg_region | arena | engine.bg |
| 1472-1491 | sprite_table | table | |
| 1492-1500 | tails_appendage | window | |
| 1501-1503 | FREE (3) | | |
| 1504-1531 | hscroll_table | table | |
| 1532-1535 | FREE (4) | | |
| 1536-2047 | plane_a / plane_b / window | plane | |

The sparkle needs **4 tiles, resident for the act** (concurrent sparkles sit on different
frames, so, like the dust puff, all of them must be live at once — streaming is not an option
and is not needed). Two runs fit: 924-959 (36, explicitly reserved for future sprite art) and
1020-1023 (4, exactly). **Chosen: `ring_sparkle` at 924, 4 tiles**, leaving 928-959 (32) free.
Rationale: it is the run the carve set aside for this purpose, and it keeps the 1020 gap next
to the ring/marker windows untouched for whatever the ring placeholder's successor needs. The
region is declared in the TOML with `const = "VRAM_RING_SPARKLE"`; `tools/gen_vram_map.py`
regenerates the constants block, the Python mirror and the map doc, and
`tools/test_gen_vram_map.py` fails the build if any of the three drift.

**Loading.** The blob is DMA'd once at scene init in `GameState_OJZScroll_Init`
(`games/sonic4/test/ojz_scroll_test.emp`), beside the dust-puff block's identical one-shot DMA
(128 B, `QueueDMA_Critical`). That scene owns the ring art's DMA today, so the sparkle's goes
with it; when the ring art gets a permanent home the two move together.

### 2.4 Files

| file | change |
|---|---|
| `engine/system/game_contract.emp` | `hook ring_collected (a3: *u8) clobbers(d0-d2/a1) = empty` |
| `engine/objects/rings.emp` | `RingCollision`: `invoke Game.ring_collected` (a3 = the entry) before `RingBuffer_Remove` |
| `games/sonic4/config/game.emp` | `hook ring_collected = RingSparkle_Spawn` |
| `games/sonic4/objects/ring_sparkle.emp` | NEW module `games.sonic4.ring_sparkle`, SELF-CONTAINED: `RingSparkle_Spawn`, `RingSparkle_Main`, `Map_RingSparkle` (mapping DSL), `Ani_RingSparkle`, `Art_RingSparkle` (embed), the display-frame / palette-census / size ensures |
| `games/sonic4/player/player_sensors.emp` | the three `probe_core` table pointers pinned to abs.l / immediate (byte-neutral in size; see "the placer finding" below) |
| `games/sonic4/test/poison/poison_ring_sparkle_frames.emp`, `tools/emp_expect_fail.py` | the red-first case for the frame gate |
| `games/sonic4/test/compose_ring.py`, `ring_sparkle_art.bin` | donor extraction (tiles 10-13) |
| `games/sonic4/vram.toml` + generated block/doc/py | `ring_sparkle` region at 924 |
| `games/sonic4/config/constants.emp` | `EFFECT_RING_SPARKLE_BAND` + ensures (hand block) |
| `games/sonic4/map.toml` | one `order` row, `RingSparkle_Spawn`, after the dust objects |
| `games/sonic4/test/ojz_scroll_test.emp` | the one-shot art DMA |
| `docs/DEFERRED_WORK.md`, `docs/ENGINE_ARCHITECTURE.md` §4.9.4 | booking + sync |

**Module registration — measured, no sigil edit needed.** The sigil registry
(`crates/sigil-harness/src/native.rs`) lists modules explicitly, which looked like it would make
every new module a sigil edit (forbidden here). Probed 2026-08-26 in this worktree: a new
`.emp` module reachable through a `use` from a registered module is discovered and elaborated
by the manifest scan; the only thing that stops it is `[map.order-undeclared]`, and a row in
`games/sonic4/map.toml`'s `order` (aeon-side) places it. Build green, the proc landed in the
listing at its declared position, warning totals unchanged (10 / 135). So a new module needs an
`order` row and nothing in sigil. (A `[[table]]` pin row is not needed for a section placed by
order alone — the probe had none.)

**Why ONE module and not the dust's three (the placer finding, measured 2026-08-26).** The
first cut mirrored the dust exactly — `ring_sparkle` (code, object bank), `ring_sparkle_data`
and `ring_sparkle_anims` (data, beside `Map_Dust*` / `Ani_Dust*`). Every shape that made a NEW
data section reachable failed the placer with
`packed layout overlaps at its real bases — a run grew into a declared anchor ... sections
section [0x6E5C,0x72E6) and player_sensors [0x6980,0x6E74) overlap`, in every row position
tried (beside the dust data, after `HeightMaps`, art-only, map-only). The same failure came
from **seven `nop`s added to `RingCollision` on bare master** (E24) — i.e. the tree was one
byte-growth away from this on its own. The pair the message names is the symptom, not the
cause: `player_sensors` measured **24 bytes shorter** in the walk's provisional round than at
its real base, because `probe_core`'s three `lea Table, a1` (x4 instantiations = 12 sites)
are UNSIZED and the width rule encodes them abs.w (4 B) while the tables' provisional
addresses are unknown, abs.l (6 B) once they are — and the walk then places `section` 24 B
into `player_sensors`. Pinning those pointers (`lea (X).l` for the two literal tables; an
immediate `movea.l #{ptable}` for the template argument, since the template cannot spell
`({ptable}).l`) makes the measurement base-invariant and the tree builds with the full
module set — the fix is byte-neutral in SIZE (6 B either way) and identical in cycles. Having
the fix, the sparkle still ships as one section: 192 B of data is not worth three modules,
and the self-contained file is the honest unit. Booked in DEFERRED_WORK as a sigil placer
item (a provisional-round measurement that depends on unknown addresses should not be
trusted as the fixpoint) and in EMP_PITFALLS §11.

### 2.5 Gates

1. **Comptime, derived (red-first):** in the anims module, a comptime fn walks the script bytes
   and computes `frames_shown * (duration+1)`; `ensure(... == S3K_SPARKLE_FRAMES * (S3K_SPARKLE_DURATION+1))`
   where the two S3K constants are the cited bytes (`4`, `5`). Not a literal 20 or 24. Proven
   red by a poison module in the `emp_expect_fail` lane (`games/sonic4/test/poison/poison_ring_sparkle_frames.emp`)
   that feeds a 3-frame script to the same fn — case 36/36, fragment quotes the folded 18.
2. **Palette census, comptime:** every nibble of `Art_RingSparkle` in `{0,5,6,C,D}` — pins the
   "same line as the ring" claim to the bytes; size ensure `== 4 * TILE_SIZE`. Inverted once
   (`== 0` -> `!= 0`): red, message printed the folded 0 — the fn evaluates.
3. **Art provenance, pytest (`tools/test_ring_sparkle_art.py`):** re-runs `compose_ring.py`
   against the donor into tmp and asserts both outputs are byte-identical to the committed
   blobs, plus the index census in Python. Skips loudly (by name) when the donor or `nemdec`
   is absent, exactly as `tools/test_gen_dust.py` does for `AEON_SKDISASM_DIR`.
4. **VRAM registry:** `tools/test_gen_vram_map.py` (already build-fatal) — the regenerated
   block/doc/py must match the TOML.
5. **Existing object/sprite/effects gates** unchanged and must stay green.
6. **Replay fixtures (EMULATOR — tagged for the controller).** `Replay_Hash` folds the Effect
   free-stack OCCUPANCY (`engine/system/replay.emp:274`). The slide fixture collects rings
   (`replay_fixture.emp`: "run right across the section-1 boundary collecting its rings"), so any
   checkpoint landing within 24 ticks of a collect now sees one more live effect slot and its
   recorded hash no longer matches. This is the expected, intended state change — not a
   desync — but the fixtures need a re-stamp (or a re-verification that no checkpoint lands in a
   sparkle window) in the emulator. The standing `Replay_OJZ_Fixture` "never leaves section 0";
   whether it collects rings there was not measured here. Both are the controller's to run.

## 3. "Anything else animation-wise" — Aeon vs S3K

| item | S3K | Aeon today | verdict |
|---|---|---|---|
| (a) spin rate | timer reset 7, `andi #3` -> 4 frames, 8 ticks each (`sonic3k.asm:9675`) | `RING_ANIM_FRAMES = 4`, `RING_ANIM_SPEED = 8` | **equal — untouched** |
| (b) lost-ring scatter on hit | `Obj_LostRings` (bouncing, re-collectable, timed) | **absent**: no scatter code (`grep scatter/lost_ring` in `engine`/`games` is empty). Already booked: `docs/DEFERRED_WORK.md:3073` "Bouncing Loss Rings (Ring Scatter on Damage)", blocked on the player damage system | **report only; not implemented here** — the existing booking is re-pointed at this note |
| (c) ring draw priority vs player | ring `priority = $100`, same bucket as the player (player first in slot order -> player in front); rings draw IN FRONT of every `$180+` object (most badniks/monitors) | `DrawRings` runs **after the band loop** (`sprites.emp:449`) — rings are appended last to the SAT, i.e. BEHIND every object sprite in every band, player included | **matches S3K for the player** (rings behind him) but NOT for other objects (S3K rings overdraw badniks; Aeon rings sit under them). Cosmetic, rarely visible (rings and badniks seldom overlap). **Report only** — moving `DrawRings` into a band is a `Render_Sprites` change with the sprite-cap shortcut caveat at `sprites.emp:517-521`; booked, not done |
| (d) collect sparkle | 4 frames x 6 = 24 frames in front of the player | none — the ring vanishes | **this parcel** |

## 4. Out of scope, explicitly

- Ring scatter (b) and the ring-vs-object draw order (c): reported and booked, not built.
- Moving the ring art out of `games/sonic4/test/` — the sparkle follows the ring's current home.
- Any change to the spin, the SFX, or the collect bookkeeping order.
