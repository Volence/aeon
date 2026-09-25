# S2-COMPRESSED-ACT row 7: two zones in one act, Emerald Hill then Chemical Plant

Parcel `parcel/s2-two-zone-act`, 2026-09-25. Base `7a48b130`; `origin/master` (`57b75d6c`, which
carries the S2CLIP-BANK-ROOM-GATE fix `79959734`) merged in before the final builds. Asked for
by the owner the same day: *"can we add in chemical plant now and test them together?"* The
staged plan's row 7 is `docs/research/2026-09-17-s2-compressed-act-design.md` §10.

**No emulator was used.** Everything below is a build, a bake or a static check over bytes the
ROM carries. Whether it LOOKS right, and whether the fade FIRES, are runtime claims, TAGGED in
§8 for the owner's own flight.

---

## 0. What the owner gets, in one paragraph

`S2CLIP=s2_ehz_cpz ./build.sh` writes `s4.s2clip.bin` (822,334 B, crc32 `9a3533f1`) and **exits
0 with every gate green**. It is one act, 7 x 3 sections (14,336 x 6,144 px): **all** of Emerald
Hill act 1's painted crop (x 0..10975, so the stretch to the signpost is back), a plain grey
corridor (x 10976..12287), then the first 2,048 px of Chemical Plant act 1 (x 12288..14335). Each
zone is drawn in **its own palette**, and the palette cross-fades at x = 11632, in the middle of
the corridor, where no zone is on screen. `DEBUG=1 S2CLIP=s2_ehz_cpz ./build.sh` writes
`s4.s2clip.debug.bin` (848,912 B, crc32 `441f1db0`) and **exits 1 at one gate, for real**: the
debug shape has 30,900 B of room under the Z80 bank anchor and the rule demands 49,152 — **short
by 18,252 B**. Every other gate of the debug build, before and after that one, is green. Fixing
it is moving the bank anchors, which is a sigil-lane parcel (§6).

## 1. The act, and how to fly it

| x (world px) | what | floor (top surface) |
|---|---|---|
| 0 .. 10975 | Emerald Hill act 1, its whole painted crop, y 0..1023 | spawn lands at y = 671 |
| 4672 .. 4863, 9472 .. 9663 | Emerald Hill's own two bottomless pits (declared, as before) | none: an endless fall |
| 10656 | Sonic 2's own camera limit for EHZ act 1 (its signpost stretch ends about here) | |
| 10976 .. 12287 | the corridor: grey floor on CRAM line 0 | y = 768 (a 4-px step UP from EHZ's 772) |
| 11632 | **the palette crossing** (camera centre, i.e. when Sonic is mid-screen here) | |
| 12288 .. 14335 | Chemical Plant act 1, x 0..2047 of the zone, pasted 256 px lower | y = 768 at its start |
| 12384, 748 | where Sonic 2 itself starts CPZ act 1, in this act's coordinates | |
| 14335 | the act's right edge (camera clamp) | |

- **Spawn:** world (256, 256), unchanged — the descriptor's start fields; he falls onto EHZ's
  ground at y = 671.
- **To reach the corridor:** run right along Emerald Hill. Jump the two pits. Past x 10240 is the
  ground the five-section act used to cut off.
- **The DEBUG shape boots in free flight** (the harness's default); **press B** to drop into
  normal physics before judging anything about ground or slopes.

## 2. The per-cell tileset key on the ROM path (R20 deleted)

`ojz_strip_gen.generate()` loaded ONE tileset and handed `place_pool` a zone grid of zeros. It now
bakes a KEYED project: `clip_rom_bake.stage_project` writes `zones[0].tilesets` (every sheet, in
zone-key order: the donor zones, then the corridor's synthesised sheet), and `clip_act_bake`
writes one `section_N.zonekey.bin` per section (a signed byte per cell, -1 void). The dedupe runs
on the virtual index `(key + 1) * 0x800 + tile`, VOID = 0 = blank — the same arithmetic
`clip_act_bake.dedupe_keyed` has used since row 3. The shipped `project.json` has no `tilesets`,
and its bake is unchanged:

- **CONTROL, measured:** with every clip act baked keyed, `S2CLIP=s2_ehz_boot` built
  `s4.s2clip.bin` 821,708 B crc32 `9ea6d7c2` — byte-identical to the base commit's. (That was
  measured before the palette change below, which deliberately changes that ROM.)
- `tools/regenerate-level.sh --no-cache` on the shipped act changed nothing but
  `DONOR_PROVENANCE.json` (restored).
- **R20** ("exactly one clip") is **deleted**: its reason is gone. In its place:
  - **Z1** (refused at the ROM bake): no tile-cache window — every window
    `fg_page_order.camera_windows` enumerates, 80 x 60 cells — holds cells of two donor zones.
    The row-3 butted fixtures are bake-only and never ROMs, so they keep baking. On
    `s2_ehz_cpz`: **0 of 629,079 windows** mixed; the narrowest gap between the zones is 164
    cells.
  - **K4**: the ROM bake's art pool is byte-for-byte the pool `clip_act_bake` composed. A ROM
    path that loses the key dedupes two zones' equal indices into one entry and lands a SMALLER,
    self-consistent pool that every other lane accepts. On `s2_ehz_cpz`: 14 pages, 28,672 B,
    identical.
- `verify_level_bin`'s bake-fidelity lane resolves each cell against **its own** sheet, and a
  missing key file is a failure, never a fallback to one tileset.

## 3. Each zone in its own colours

Parcel 6 shipped `S2CLIP_PALETTE=shipped` (every clip act in Oracle Jungle's colours) because the
only palette a clip bake could reach was `ojz_palette.bin`, and eight comptime pins in
`ojz_effects.emp` refuse any palette but the shipped act's there. **Row 7 needed neither
option (a) nor (b).** The clip act never writes `ojz_palette.bin`, so the pins keep describing
exactly what they always described. It carries its own palettes and region table instead:

- **`games/sonic4/data/generated/ojz/act1/clip_act.emp`** (module `games.sonic4.ojz_clip_act_act1`).
  The committed file is **neutral**: `OJZ_CLIP_ACT = 0`, no rows, and a chooser
  `ojz_clip_act_regions(hand:)` that returns `hand`. No data and no label, so the canonical ROMs
  are unchanged (measured, §7b). A clip bake overwrites it with `OJZ_CLIP_ACT = 1`, the region
  rows, and a chooser that names the clip act's table. build.sh's EXIT trap restores it.
- **`act_descriptor.emp`** binds `act_regions: ojz_clip_act_regions(hand: OJZ_Act1_Regions)` and
  `act_region_count` through `OJZ_CLIP_ACT`. This is the same always-live binding-function seam
  `ojz_act1_act_default(hand:)` already uses. The clip rows get the descriptor's **own** table
  walk: per-row rules, no overlap, exact coverage.
- **The bytes** go in a delimited `CLIP ACT DATA` block appended to `entity_data.emp`: per donor
  zone its 96 palette bytes and an `EffectsPreset` (`transition: 1`, so the 16-frame cross-fade
  arms on every install and the crossing fades both ways), then `OJZ_Clip_Regions`.
  `entity_data.emp` is regenerated by the clip bake itself (Pass 8), its section is placed by
  a head label the block cannot displace, and no lane holds its text to another generator. **It
  is a vehicle, not a home, and three measured refusals chose it:**
  1. A module of its own `in ojz_effects_editor_act1` (placed by section NAME, so no map.toml
     row): its data landed AHEAD of effects_gen's block, became the section's head label, and
     sigil refused `[layout.undeclared-alignment]`. Sigil keys section alignment by head label,
     and adding a row is a sigil change.
  2. Renaming that module and file to sort after effects_scenes changed nothing. The build refused
     identically, so the order inside a section is not name order.
  3. Appended to `effects_scenes.emp`, the build linked, and build.sh's strict
     `effects_gen.py check` refused the tree as DRIFT. That was correct: the file is
     effects_gen's.

  The proper home is a section of its own (a map.toml row plus a sigil `section_align` row).
  That is booked, not taken.
- **Z2**, the row's second static check, runs over the rows parsed **back out of what was
  emitted** (module rows and data table held identical):
  - every clip lies under its own zone's preset;
  - walking the camera centre from one zone to the next, at every 16-px row the corridor spans,
    installs exactly ONE preset and changes the palette exactly ONCE;
  - the crossing sits at least `CAM_SCREEN_HALF_W + PAL_FADE_FRAMES x CAM_MAX_X_STEP` =
    160 + 16 x 16 = **416 px** inside the corridor from both zones. All three terms are read
    from engine source.

  On `s2_ehz_cpz` the one crossing is at **x = 11632** on all 64 corridor rows, with **656 px**
  of corridor on each side.
- **In the ROM** (read from the built image): `OJZ_Act1_Descriptor + $28` = `OJZ_Clip_Regions`,
  `+$2C` = 2 rows. Rows: x 0..11631 → EHZ's preset, x 11632..14335 → CPZ's, both full act
  height.
- `S2CLIP_PALETTE` / `--palette` are **deleted**. `clip` could only ever fail and `shipped` drew
  every zone in the wrong colours. **`s2_ehz_boot` now shows Emerald Hill in its own colours
  too**, so its ROM changed. It builds: FAST, 821,758 B.

## 4. The corridor

A 1312 x 1024 px rect in the manifest's new `corridors` list (rules K1-K3). The bake
**synthesises** it; nothing comes from a donor:
- **Art on CRAM line 0**, the character's line. The test derives this from `Palette_LoadPal`'s
  own `Pal_Compose_Lines` write, not from a comment: an install touches lines 1-3 only. So the
  corridor is the one thing on screen no region install can recolour, before, during or after
  the fade.
- **Three tiles** of its own sheet: blank; a mid-grey course with a dark mortar line (colours 9
  and 1 of `SonicAndTails.bin`); and a top edge (white over light grey, 6 and 7). The sheet is a
  zone key of its own, so Z1 can tell a corridor cell from a zone cell.
- **The floor** is the bank's full solid block with the odd-angle flag, on both planes, from
  `floor_y` = 768 down to the rect's bottom. The shape is found in the bank, not typed: `base_s2`
  shape 255, angle `$FF`, the shape CPZ's own start floor is made of.
- **How it looks is the owner's call.** It is a plain, legible default and I spent nothing on
  art.

## 5. Budgets — measured, and the one that binds

| act | block stream (unique B) | pool tiles / pages | art pool ZX0 | worst window | attr entries |
|---|---|---|---|---|---|
| `s2_ehz_boot` (base) | 78,030 | 480 / 8 | 6,344 | 8 of 12 | 105 |
| EHZ 10240 + corridor + CPZ 2048 | 95,498 | 872 / 14 | 11,764 | 8 of 12 | 163 |
| **`s2_ehz_cpz`: EHZ 10976 + corridor + CPZ 2048** | **98,884** | **872 / 14** | **11,764** | **8 of 12** | **163** |
| EHZ 10976 + corridor + ALL of CPZ act 1 (10240 px) | 201,182 | 1100 / 18 | 14,958 | 12 of 12 | 220 |

**The binding budget is ROM ROOM, not VRAM, collision or sections.** Every byte a clip act adds
lands in the data region below the Z80 bank anchor `dac_banks` = 0xA8000 (map.toml, BANK PLACEMENT
RULE), and `bganim_room --gate` requires 49,152 B to stay free under it:

| shape | packed data ends | room under the anchor | vs the 49,152 B reserve |
|---|---|---|---|
| plain, `s2_ehz_boot` (base) | 0x92F54 | 86,188 B | +37,036 |
| **plain, `s2_ehz_cpz`** | **0x99CF2** | **58,126 B** | **+8,974: PASSES** |
| debug, `s2_ehz_boot` (base) | 0x999AE | 58,962 B | +9,810 |
| **debug, `s2_ehz_cpz`** | **0xA074C** | **30,900 B** | **−18,252: FAILS, for real** |

The act adds **28,062 B** before `Art_Sonic` in both shapes. Where it goes: CPZ's first 2048 px
is 13,306 B of blocks plus a 1,600 B fringe, CPZ's tiles grow the pool by 5,420 B ZX0, the
corridor section, EHZ's recovered crop, and the palettes, presets, regions and local maps.

- **All of Chemical Plant act 1 does not fit.** It adds about 123 KB of block stream and would not
  even LINK in either shape. That is why CPZ is its first 2,048 px, from its own start. **How much
  more CPZ the act can carry is the owner's call against the anchor move.**
- **Emerald Hill's full crop (row-7 brief, item 6), measured:** +3,386 B of block stream
  (98,884 vs 95,498), and **nothing else moves**: same 872 tiles in 14 pages, same worst window,
  same 163 attr entries. It changes no gate's verdict in either shape. The plain shape passes
  with or without it, and the debug shape fails with or without it, since 18,252 − 3,386 is
  still 14,866 short. I judged that **not a real cost** and took it. It recovers the 736 px
  (416 playable) of S2CLIP-TRUNCATION. That became possible because the act is now wider than
  Emerald Hill, so its clip no longer has to end on a section boundary. If the owner reads
  3.4 KB as real, it is one number in the manifest.
- **`dplc_straddle`** (a warning, not a gate), and how the act moves it:
  - plain: base "sonic can grow +6,093 B (VERDICT A)"; now "nearest forbidden shift **4,179 B
    down** (sonic, VERDICT C)", with sonic able to grow +25,871.
  - debug: the room-gate report's base figure is 3,343 B; now the tightest is **knuckles, 919 B
    up** (VERDICT C), with sonic able to grow +7,253 (A).
  - `dplc_straddle --gate` itself exits 0 in both shapes.
- **Collision:** 163 of 255 attr entries. **VRAM:** worst camera window 8 of 12 frames, Emerald
  Hill's, unchanged. Chemical Plant's first section never needs more. **Sections:** 21 of 48.

## 6. Build results

- **`S2CLIP=s2_ehz_cpz ./build.sh`: exit 0.** Every gate green, among them: the pre-build lane
  (3,234 passed, 3 skipped, 29 deselected), emp_expect_fail 56/56, verify_level_bin all ten lanes
  (21 sections, 1,376,256 nametable words, 27,886 authored non-air collision cells),
  clip_reachability, the FG page budget, effects_gen check, bganim_room (8,974 B above the
  reserve), dplc_straddle, dma_defer_headroom, sprite_tilt_gate, instashield_gate and
  loop_crossover_gate.
- **`DEBUG=1 S2CLIP=s2_ehz_cpz ./build.sh`: exit 1 at `bganim_room`, and the failure is REAL.**
  Its exact text:
  > `room under dac_banks = 0xA8000 - 0xA074C = 30900 B, which is LESS than
  > DATA_GROWTH_RESERVE 49152 B (short by 18252 B).`

  The ROM is still written. It fired on the base `s2_ehz_boot` debug build as well; that was the
  RESERVE+GRACE defect fixed on master. After the fix, `s2_ehz_boot` debug has 9,810 B to spare,
  and this act overruns by **18,252 B**. Every gate before it is green. The five after it, run by
  hand on a re-baked tree whose provenance digests reproduced (FRESH), all exited 0:
  dplc_straddle, dma_defer_headroom, sprite_tilt_gate, instashield_gate and loop_crossover_gate.
  **The gate was not touched.** Per the controller, the remedy is moving both bank anchors, a
  sigil-lane parcel. The other lever is a smaller act, which would mean dropping Chemical Plant
  below its first section.

## 7. Static checks, red-first

Every new gate was proven red by an on-disk mutation. Each mutation was shown as a
`git diff --stat` before its run, run against its named runner, then restored from the committed
baseline and verified with a clean `git status`. The controls were green on the baseline.

| # | mutation | runner | result |
|---|---|---|---|
| M1 | Z1 counts a window as mixed only past TWO zones | test_clip_rom_bake z1_counts | RED |
| M2 | Z1 counts the corridor sheet as a zone | same | RED |
| M3 | Z1 never refuses at the ROM bake | test_clip_rom_bake z1_refuses | RED |
| M4 | the ROM path resolves every keyed cell against sheet 0 (the lost key) | `clip_rom_bake bake s2_ehz_cpz` | RED: **K4** "art pool (9 pages, 18432 B) is not the pool clip_act_bake composed (28672 B)" |
| M5 | verify_level_bin resolves every cell against sheet 0 | verify_level_bin on a kept bake | RED: sec5 2 and sec6 571 word shapes to DIFFERENT pixels |
| M6 | Z2 margin zeroed | test_clip_two_zone fade_can_see | RED |
| M7 | Z2 accepts more than one install | …more_than_one_install | RED |
| M8 | Z2 accepts a snapping preset | …snaps | RED |
| M9 | Z2 compares only the COUNT of checked vs emitted rows | …checked_rows | RED |
| M10 | region rows leave a 16-px strip at the act's bottom, where Z2's walk does not look | `FAST=1 S2CLIP=s2_ehz_cpz ./build.sh` | RED at comptime: "the clip act's region rows do not tile the act" |
| M11 | corridor drawn on CRAM line 1 | …corridor_art | RED |
| M12 | K3 drops the collision-row rule | …corridor_rules | RED |
| M13 | the committed neutral module is hand-edited | …neutral | RED |

M10 also proves the descriptor's clip-table checks are **live**: the module is in the `use`
closure and its ensures fire. Runners: Z1, Z2, K1-K3 and the neutral-module guard run in the
pre-build lane. Z1 (the refusal), Z2, K4 and the keyed verify lane run inside every
`S2CLIP=... ./build.sh`.

Test totals: `tools/test_clip_two_zone.py` is 18 new rows. `test_clip_rom_bake.py` lost the R20
row and gained two Z1 rows, for 20. `test_cli_dispatch_refuses.py` gained `_mode_emit_neutral`
in the roster. The pre-build lane went from **3,214 passed / 3 skipped / 29 deselected** at base
to **3,234 / 3 / 29** after the merge: +1 net in test_clip_rom_bake, +18 here, and +1 from
master's room-gate fix.

**`ground`** on the kept tree now corroborates **every** clip against its donor's own start
position:
- the spawn (256, 256) lands on EHZ's ground at y = 671;
- EHZ's `startpos` (96, 655) puts the player's feet 2 px above the ROM's floor;
- CPZ's `startpos` (96, 492), at act (12384, 748), puts the player's feet at 767 against a floor
  at 768, **1 px**.

Both are inside the derived 0..16 window. A 16-px paste shift misses it.

## 7b. Landing evidence

`tools/landing_build.sh` (at `30e0f0eb`, after the merge) exited **0**, `finished=0`, with the
stamp written (`key=529c3f68ceacc9c1`, `head=30e0f0eb916c`). Its lane figures: pre-build
**3,234 passed / 3 skipped / 29 deselected**, `emp_expect_fail` 56/56, needs_build lane 28
passed / 1 EXEMPTED (`demo.bin`, a shape it does not build). **The canonical ROMs are
byte-identical to the base**, on the same assembler (sigil `d7e6aa15`, md5 `8027e7ba…`):

| ROM | base `7a48b130` | this branch |
|---|---|---|
| `s4.bin` | 821,479 B, crc32 `6d1af7a3` | 821,479 B, crc32 `6d1af7a3` |
| `s4.debug.bin` | 848,075 B, crc32 `62238a15` | 848,075 B, crc32 `62238a15` |
| `demo.debug.bin` | 104,707 B, crc32 `ce922bf7` | 104,707 B, crc32 `ce922bf7` |

(md5 `ae62156a…` / `b15ef259…` / `f740c224…` both times.) `tools/regenerate-level.sh --no-cache`
on the shipped act changed only `DONOR_PROVENANCE.json`, so the keyed strip-gen change is
byte-neutral on the shipped bake as well as on the ROM.

## 8. TAGGED for the owner's runtime look (none of these is claimed)

1. **The picture.** Emerald Hill in Emerald Hill's colours, Chemical Plant in Chemical Plant's,
   and the corridor in grey.
2. **The fade at x = 11632,** both ways. Z2 says it installs once, at a place where only corridor
   and background are on screen. Only a run shows that it fires once and reads as intended.
3. **The BACKGROUND is still Oracle Jungle's** (Plane B, CRAM lines 2 and 3). It is now drawn in
   Emerald Hill's and Chemical Plant's colours, and **will very likely look wrong**. Each zone
   getting its own background is the region-BG-switch machinery's job (`rg_bg_layout` /
   `rg_bg_tiles`, as the Oil Ocean showcase row uses), within the per-region BG tile budget.
   Booked, not built.
4. **At boot, expect a fade of up to 16 frames from Oracle Jungle's colours into Emerald
   Hill's.** The boot state copies `OJZ_Palette` into CRAM, and the first region install arms the
   fade (`transition: 1`).
5. **76 Chemical Plant cells** in its first 2048 px (x 48..2047, y 480..975 of the zone) are
   painted on CRAM line 0 and **will render in Sonic's colours**. The design's open §5.3 decision
   covers them: repaint, hide, or accept.
6. **The 4-px step** from Emerald Hill's ground (772) up onto the corridor (768).
7. **Chemical Plant without its objects.** Tubes, boosters and platforms are absent, so some of
   its geometry may assume an object that is not there. Oracle Jungle's objects and rings still
   appear at Oracle Jungle's section positions (inherited, as before).
8. **The two Emerald Hill pits** are still endless falls. No death exists.

## 9. What is open

- **The debug shape's ROM room (−18,252 B).** Remedy: move both bank anchors, via the sigil
  lane. Until then `DEBUG=1 S2CLIP=s2_ehz_cpz` builds its ROM and exits 1.
- **The clip act's data needs a section of its own** (a map.toml row plus a sigil
  `section_align` row). `entity_data.emp` is the vehicle until then.
- **Wider Chemical Plant:** it waits on the same ROM room.
- **Per-zone backgrounds** (§8.3), the **CPZ line-0 cells** (§8.5), and the **boot fade** (§8.4).

## 10. Reproduce

```bash
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
python3 tools/s2_zone_convert.py convert s2disasm@EHZ s2disasm@CPZ   # the gitignored donor trees
S2CLIP=s2_ehz_cpz ./build.sh                  # exit 0 -> s4.s2clip.bin
DEBUG=1 S2CLIP=s2_ehz_cpz ./build.sh          # exit 1 at bganim_room (room 30,900 < 49,152)
python3 tools/clip_rom_bake.py bake games/sonic4/data/clips/s2_ehz_cpz/clips.json --keep
python3 tools/clip_rom_bake.py ground games/sonic4/data/clips/s2_ehz_cpz/clips.json   # both donors corroborate
python3 tools/clip_reachability.py check games/sonic4/data/clips/s2_ehz_cpz/clips.json
python3 tools/verify_level_bin.py --project games/sonic4/data/clips/s2_ehz_cpz/baked/project.json \
    --bank games/sonic4/data/collision/base_s2
git checkout -- games/sonic4/data/generated/ojz/act1 games/sonic4/data/collision && \
    git clean -fdq -- games/sonic4/data/generated/ojz/act1
```
