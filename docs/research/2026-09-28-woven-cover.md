# Woven act cover: what hides the backgrounds in tunnels and shafts, how small it can get, and whether zone foreground fits

**Date:** 2026-09-28. **Branch:** `research/woven-cover`, base aeon `origin/master`
`d128c8f56521ac215cfb47f766a65a57d9b36719`. **Status:** sizing research. No engine, tool or act
data was changed. Scratch variant manifests were baked and flown in this worktree and the tree
was restored after each one (`git status` clean apart from this note and its directory). No
emulator MCP was used; the two emulator numbers come from headless `tools/crossing_witness.py`
subprocess runs.

**Tags.** **MEASURED** (a command in §8 printed it), **READ** (file:line), **INFERRED**
(reasoning on read or measured facts; the sentence says which).

**The owner's words** (banked at empyrean `f3ce9f1f`). Asked "flat tunnels only, or the tall
shafts too?" he said: "Tall shafts t oo I think, at least get ridd of the thing hiding
backgrounds as minimal as possible, but having some fg from the zone your in would be good".

---

## 0. The answer for the owner, in plain words

- **What the covering is.** Every tunnel and shaft is painted solid, edge to edge, in colours
  from Sonic's own palette line. Tunnels use grey Chemical Plant plating. The three Wing Fortress
  shafts are a flat blue "sky" with red ledges. The other shafts are grey stone. Around every zone
  piece there is also grey stone "fill". Behind all of it the real background is still drawn; you
  just never see it there.
- **Why it exists.** Two zones can never share one screen (your ruling), because the screen holds
  only one zone's colours at a time. When you cross from one zone to the next, the colours flip in
  one frame and the background is rebuilt over the next 3 to 9 frames. The covering is what is on
  screen while that happens.
- **How small it can get.** At the moment the zone switches, **the whole screen still has to be
  covering**. So even with every engine change bought, a tunnel can never be shorter than about
  one screen width (320 to 352 px), and a shaft never shorter than about one screen height (224
  to 256 px). With today's engine the minimums are 416 to 608 px for tunnels and 320 to 512 px
  for shafts.
  - **Flat tunnels are already at the minimum today.** Nothing spare can be cut.
  - **Three shafts have spare length** that no rule needs: Wing Fortress to Emerald Hill 192 px,
    Wing Fortress to Metropolis 320 px, Emerald Hill to Hidden Palace 240 px.
- **Can a connector show foreground from the zone you are in? Partly.**
  - **Yes, in the zone's real colours, only in the spare length.** Measured, it works only where
    that zone's own map has rows to show. Today none of the three shafts with spare length qualify:
    - Wing Fortress would need an engine change to its background scrolling (every try was refused);
    - Emerald Hill, Hidden Palace and Metropolis have no map rows there.
    - With the route fix, the Wing Fortress to Chemical Plant shaft gets spare length. Its bottom
      128 px can then open onto Chemical Plant's own sky and background. That was built and flown:
      0 glitch frames.
  - **Yes, in Sonic's colours, anywhere in a tunnel.** The tunnel can be drawn from the zone's own
    rock instead of Chemical Plant plating. Emerald Hill's rock recoloured was built and flown in
    the first tunnel: 0 glitch frames, 20 more tiles. Picture:
    `docs/research/2026-09-28-woven-cover/c5_ehz_art_line0.png`. Drawing each half from its own
    zone is a small tool change.
  - **In real colours near a tunnel's ends: only with new tools.** Only the last 32 to 128 px at
    each end of a tunnel could use real zone colours, and only if solid (no see-through gaps).
- **Cost.**
  - **Small:**
    - recoloured zone rock per half (tool change);
    - Chemical Plant's sky in its shaft (builder constants; route-fix geometry only).
  - **Medium, each:**
    - real-colour solid ends on tunnels;
    - marking drop shafts one-way, to trim 128 px off two shafts (risky once springs exist);
    - the engine fix that would let Wing Fortress's own sky fill its shafts.
  - **Large:** a faster background switch, which would shorten every connector between zones
    that use different backgrounds.
- **Watch out: the route fix makes shafts longer.** It adds about 960 px of all-covering shaft
  travel (§4). That is the opposite of this wish, so decide the two together (§4).
- **One question back** is in §6. It asks which covering you meant, pointing at three places.

---

## 1. What "the thing hiding backgrounds" is, measured

### 1.1 What the player sees, per connector type

| Where | Plane A (what you see) | Plane B (the real background) | Why | Source |
|---|---|---|---|---|
| **Flat tunnel** (C5, C6, C7, C11) | A 512-px-tall rectangle, every pixel painted, all on **CRAM line 0**. The ceiling and floor are the `wall_src` texture: CPZ plating at donor (768, 784), recoloured to the nearest line-0 colours. The 96-px bore is the `back_src` texture at half brightness. Donor transparent pixels are painted $0222. | Drawn, never visible | "the tunnel to transition has to be like an FG hiding the bg" (owner 2026-09-25) | **READ** `tools/clip_manifest.py:194-215`, `:629-638`; manifest `corridors[*].tunnel.art` |
| **Cloud shaft** (C1, C2, C3, under Wing Fortress) | The lane is EHZ's `back_src` (4096, 0), undimmed, with transparent pixels painted the line-0 colour nearest $0E66. The source is empty sky, so **the whole lane is one flat blue**. Red-brown ledges every 64 px. Walls either side are grey stone. | Drawn, never visible | Every pixel is painted so no background shows ("the tunnel's rule on its side") | **READ** `clip_manifest.py:300-311`, `:1382`; **MEASURED** render `c2_today.png` |
| **Rock shaft** (C4, C8, C9, C10) | The lane is mortar colour, the walls are grey stone course, with ledges on C4, C9 and C10 | Drawn, never visible | as above | **READ** `clip_manifest.py:300-311` |
| **Fill** (everywhere between pieces) | One grey stone tile on line 0, solid on both collision planes | Drawn, never visible | No void between zones, and no pit falls out of the act | **READ** `clip_manifest.py:261-279` |

**Why line 0** (**READ** `clip_manifest.py:600-610`): a zone preset palette is 96 bytes, lines
1-3. Line 0 is the one line no region install writes. So covering drawn on line 0 looks the same
before, during and after the one-frame palette snap. Zone foreground cannot be: it is on lines
1-3, which flip at the crossing.

**Shafts are narrower than the screen** (192 or 256 px against 320). So while you are in a
shaft, the sides of the screen are always fill. In a shaft you see flat blue or grey in the
middle and grey stone at the sides.

### 1.2 How big it is, in screen terms

The screen is 320 x 224 = 71,680 px. **MEASURED** by `cover_measure.py` over the SCREEN check's
own reachable-camera model (`tools/clip_camera.py`), §8 m1:

| Connector | Type | Length | Camera travel with a **100% covered** screen | Mean share of the screen that is cover, camera inside |
|---|---|---|---|---|
| C5 ehz_to_mtz | flat, blobs A to M | 608 | 296 px | 83.9% |
| C6 mtz_to_cpz | flat, same blob | 416 | 104 px | 79.4% |
| C7 cpz_to_mtz | flat, same blob | 416 | 104 px | 79.2% |
| C11 hpz_to_ooz | flat, A to O, tall entry | 560 | 248 px | 86.7% |
| C1 wfz_to_ehz | cloud shaft, same blob | 512 | 296 px | 89.1% |
| C2 wfz_to_mtz | cloud shaft, A to M | 832 | 616 px | 93.3% |
| C3 wfz_to_cpz | cloud drop, A to M | 512 | 296 px | 89.1% |
| C4 ehz_to_hpz | rock shaft, same blob | 560 | 344 px | 90.0% |
| C8 cpz_to_ooz | rock drop, M to O | 464 | 248 px | 87.9% |
| C9 mtz_to_ooz | rock shaft, M to O (dead) | 464 | 248 px | 90.0% |
| C10 hpz_to_mtz | rock shaft, A to M, tall entry | 512 | 296 px | 89.7% |

- **The whole act:** 10.3% of the average reachable screen is cover.
- **With the camera outside every connector:** 6.7%. That is the fill alone, seen at the pieces'
  edges. 13.3% of in-zone screens are at least a quarter fill. Hidden Palace east, the 304-px strip,
  averages 22.4%.

---

## 2. The minimum, from the crossing model

### 2.1 The model (READ)

- **Where the switch happens.** The crossing `c` is where the camera CENTRE enters the next zone's
  region. At that frame the palette snaps and the background starts to switch
  (`clip_rom_bake.py:1336` `connector_crossings`, `:1299` `crossing_frames`).
- **What each side needs.** Each side of `c` needs `HALF + STEP x f`:
  - HALF is 160 (x) or 112 (y) (`engine/system/constants.emp:587-588`);
  - STEP is the camera cap, 16 on both axes (`engine/level/camera.emp:26`, `constants.emp:1196`);
  - `f` is the frames that crossing takes, the larger of:
    - the palette: SNAP_FRAMES = 1, a CRAM DMA that can slip one VBlank (`clip_rom_bake.py:994`);
    - the background:
      - the visible-row wipe, ceil(29 rows / 14 rows a frame) = 3 frames, inside a blob;
      - plus the blob's 1,824-B overwrite chunks, across blobs. That is 9 frames into blob A
        {EHZ, HPZ, WFZ} or M {CPZ, MTZ}, and 6 into O {OOZ}.
      - Sources: `engine/level/bg.emp:528,590,600`. **MEASURED** blob bytes 9,984 / 10,048 / 3,744.
- **Tall-region entry costs nothing extra today.** The woven-tall-entry parcel made entering a
  tall zone (HPZ, WFZ) snap the scroll and DMA-sweep the window, so it takes the same frames. Its
  measured slack is +2 frames on C10 and +7 on C11 (**READ** `docs/DEFERRED_WORK.md:39017-39040`).

### 2.2 Splitting the need into what is structural and what is margin

Every connector reads outwards from `c` as three bands:

| Band, each side of `c` | Width | What may be drawn there | Why |
|---|---|---|---|
| **Core** | HALF + STEP x SNAP_FRAMES = **176 x / 128 y** | **Only line-0 cover.** No cell of either zone. | At the crossing the palette flips. A cell of the zone just left shows in the wrong colours, and a cell of the zone entered can show one frame before its palette lands. |
| **Margin** | STEP x (f - 1) = 32 (same blob), 128 (into A or M), 80 (into O) | Line-0 cover, **or a cell of that side's zone that is fully opaque** | Its palette is up, but its background is still being overwritten or repainted, so a transparent pixel would show garbage |
| **Slack** | length - need | Anything of that side's zone, see-through included | Its background has settled before the camera can bring it on screen |

**MEASURED** per connector (§8 m1):

| Connector | Length | Need (before / after) | Core, each side | Margin (before / after) | Slack (before / after) |
|---|---|---|---|---|---|
| C5 | 608 | 304 / 304 | 176 | 128 / 128 | 0 / 0 |
| C6, C7 | 416 | 208 / 208 | 176 | 32 / 32 | 0 / 0 |
| C11 | 560 | 304 / 256 | 176 | 128 / 80 | 0 / 0 |
| C1 | 512 | 160 / 160 | 128 | 32 / 32 | **96 / 96** |
| C2 | 832 | 256 / 256 | 128 | 128 / 128 | **160 / 160** |
| C3 | 512 | 256 / 256 | 128 | 128 / 128 | 0 / 0 |
| C4 | 560 | 160 / 160 | 128 | 32 / 32 | **112 / 128** |
| C8, C9 | 464 | 256 / 208 | 128 | 128 / 80 | 0 / 0 |
| C10 | 512 | 256 / 256 | 128 | 128 / 128 | 0 / 0 |

- **The structural floor is 2 x HALF: 320 px across, 224 px down.** At the crossing frame the
  whole screen must be cover. That follows from "two zones never on one screen" plus a palette
  that flips in one frame, and no cut below changes it.
- **The minimum per connector type, as the model stands:**
  - flat same-blob: 416 (today 416);
  - flat A/M cross: 608 (today 608);
  - flat into O: 560 (today 560);
  - same-blob shaft: 320 (today 512 and 560);
  - A/M shaft: 512 (today 512 and 832);
  - M/O shaft: 464 (today 464);
  - tall-region entries use their blob pair's numbers.

### 2.3 What each cut costs

| # | Cut | Saves | What has to change | Re-derived by | Risk if wrong | Measured? |
|---|---|---|---|---|---|---|
| 1 | **Slack** (C1 192, C2 320, C4 240) | all of it | Nothing in the model. It is left-over geometry: one Wing Fortress piece spans three shafts, and one paste offset per zone (SC0, `clip_rom_bake.py:2556-2572`) forbids moving parts of a zone separately (**INFERRED** from the builder's position chain) | the bake (Z2, SCREEN, K7/K10) + crossing_witness | none from the model | Filling it: §3 |
| 2 | **Margin as opaque zone art** in the zone's own palette | 32 px a side (same blob); 128 or 80 (cross blob) | A connector art mode drawn from zone art, holes painted in a zone colour. A new cell class ("opaque zone") in SCREEN, Z1 and Z2. crossing_witness learning opacity: today it counts any zone cell as a glitch while the background is in flight ("CONSERVATIVE for the background", **READ** `tools/crossing_witness.py:38`) | new bake checks + a witness leg | one see-through pixel shows background garbage for up to 6-9 frames at the cap | No (needs the tools) |
| 3 | **SNAP_FRAMES 1 to 0**: guarantee the crossing tick's CRAM DMA | 16 px a side, every connector | Engine: the palette line must never be refused by the Critical queue on the crossing tick (`buffers.emp`, so the effects-gate ritual applies). Canonical bytes likely move (**INFERRED**) | crossing_witness `--scan` | one frame of a zone edge in the wrong colours | No |
| 4 | **Faster background switch** (fewer overwrite frames across blobs) | up to 96 px a side on every cross-blob connector (f 9 to 3) | Engine: a larger arena, or loading the next blob ahead. The woven plan's "W2" | the Z2 frames model reads the constants itself | as today | No (L, not sized here) |
| 5 | **One-way drop shafts** (C3, C8 have no ledges; nothing can go up them without objects) | the upper side's margin, 128 px each | Tooling: a declared `one_way` per shaft, with Z2 and SCREEN placing `c` asymmetrically. The builder print with C3 at 384 (DROP_D = -128) makes C1 384, C2 704, C3 384, so **all three Wing Fortress shafts shrink by 128** (**MEASURED** §8 b6). C8 cascades into C10, which is already at its minimum (**INFERRED**, builder chain) | bake + a drop witness | a spring under the shaft (S2CLIP-OBJECTS) makes an upward crossing, which glitches up to 8 frames | **Not measured.** The bake balances `c` in the middle, so the scratch 384-px C3 (margin set to report) split 192/192 and printed -64 px both sides. That tests the wrong split (§8 b6). |
| 6 | **Camera cap below 16** | would scale every margin | Not cuttable. A roll at gsp $1000 is 16 px a frame. At that speed the first tunnel has exactly 1 frame of slack (**MEASURED** §8 w1). At a 6-px run it has 16 to 17 | | a visible glitch at top speed | Yes (w1) |

---

## 3. Zone foreground inside a connector

### 3.1 The rules that decide it

- **Two zones never on one screen / one palette per screen.** The core must be pure line 0.
  Zone foreground in its real colours may sit only in that zone's margin (opaque) or slack
  (anything). §2.2.
- **The switch point moves.** The bake balances `c` between the two mouths. Extending one zone by
  `e` px moves `c` by `e / 2`, so one side can take at most the whole slack. **MEASURED:** C3's
  `c` moved 1824 to 1760 for e = 128 (§8 b5).
- **SC0, one paste offset per zone.** An extension must be the next rows of the same Sonic 2 map
  at the same offset. Metropolis's rows above y 0 exist only as Sonic 2's vertical wrap (donor
  y 1792..2047, level box ymin -256). They would be a second offset, so SC0 refuses them.
- **Whether the map has rows there** (**MEASURED** §8 d1, d2, level sizes):

  | Zone | Rows available | Next to which shaft |
  |---|---|---|
  | Wing Fortress | donor y 1792..2047 below the deck. 100% empty sky at C1's and C2's columns. C3's columns are solid hull down to 1791 | C1, C2 (C3 has no slack today) |
  | Emerald Hill | none: its clip is donor y 0..1024, its whole camera box | C1 (above), C4 (below) |
  | Hidden Palace | none above y 0 | C4 |
  | Chemical Plant | donor y 0..127 above its clip, 100% empty sky (CPZ_Y0 = 128, trimmed as empty) | C3 |

- **Wing Fortress's background refuses any extension.** A Wing Fortress clip that reaches lower
  moves the screen tops its tall background must cover past Sonic 2's deck-bottom view. Past it,
  the band chain needs a second layout whose band 0 drifts at 128 where the first's drifts at 0.
  The engine keeps `Parallax_Drift_Acc` per band index, so the bake refuses: "the clouds would
  jump" (**READ** `tools/clip_bg_scroll.py:1587-1592`). **MEASURED** at 32, 64, 128 and 256 px
  over C2 and 64 px over C1 (§8 b2, b3).
  - **INFERRED:** even with that fixed, a Wing Fortress region reaching `c` shows screen tops
    about 400 px past Sonic 2's own camera box. The background would hold still vertically
    there (the engine clamps at the map end).
- **Pages, collision, arena.** None bit in the passing variants:
  - worst camera window 12 of 12, unchanged;
  - collision 250 of 255, unchanged;
  - empty zone rows add no tiles.
  - Adding **new** tiles near C6 would bite, because the window at (4648, 2352) is 12 of 12 with
    no spare page (touch-ups note §3.3).
- **Music, R3.** A zone's clips must name the same song, so an extension carries its zone's music
  key. The first scratch bake was refused for this (§8 b5).
- **Seams, K6 and K10.** A shaft's mouth must be open across the lane, which empty sky is. A
  tunnel extension must meet the floor flush on both planes. The touch-ups note §3.1 measured
  this refusing most tunnel rectangles.

### 3.2 The tunnel example: C5 (Emerald Hill to Metropolis) drawn from Emerald Hill's own rock

`tunnel.art` already names any zone the act uses (**READ** `clip_manifest.py:226`, K5). The
scratch variant sets C5's `wall_src` to EHZ (6144, 448) and its `back_src` to EHZ (6336, 416).
Both are fully opaque 32 x 32 squares (**MEASURED** `find_opaque.py`). They are recoloured to
line 0 like today's plating. Nothing else changes.

| Check (**MEASURED**, §8 b4, w1) | Today | EHZ rock |
|---|---|---|
| Bake | rc 0 | rc 0 |
| Corridor sheet | 37 tiles | 57 tiles |
| Pool | 2,894 tiles, 49 pages | 2,905 tiles, 49 pages |
| Worst camera window | 12 of 12 at (4648, 2352) | same |
| Collision | 250 / 255 | 250 / 255 |
| SCREEN mixed / wrong / void | 0 / 0 / 0 | 0 / 0 / 0 |
| crossing_witness `ehz_to_mtz`, 6 runs | 0 glitch ticks, worst slack 1 (landing record) | **0 glitch ticks, worst slack 1 frame** |

**Pictures:** `c5_today.png` and `c5_ehz_art_line0.png`.
- In these renders, magenta marks where a zone's own background shows. The tick marks along the
  edges are `c` (white), the core's ends (red) and the need's ends (yellow).
- Emerald Hill's orange rock survives line 0 well. Its greens would not: line 0 is Sonic's palette
  (**INFERRED** from the render).

**What it would take to get "the zone you are in" on both halves.**
- **Each half from its own zone, still line 0: S.** Give `CorridorTunnel` an `art` per side of
  `c`, and split the painter at `c`. `c` is computed later, in the bake, so the split would be at
  the rounded midpoint the bake uses, or the bake would pass `c` in.
- **Real colours in the 128-px margins: cut 2 of §2.3, M.** The zones' own cells there are mostly
  see-through: only 34% (EHZ side) and 45% (MTZ side) of cells are fully opaque (**MEASURED**
  §8 m1). So the strip must be synthesised from zone art with holes painted, not pasted from the
  map.

### 3.3 The shaft examples

**(a) Wing Fortress's own sky over C2 and C1: refused.**
- Donor rows 1792..2047 under the hull are empty at both shafts' columns (**MEASURED** §8 d1).
  Shown, they would be Wing Fortress's real moving clouds instead of the flat blue lane.
- Every depth tried (32 to 256 px) is refused by the band-chain rule (§3.1).
- **Price:** an engine change to how cloud drift survives a band-layout switch (drift accumulators
  keyed by drift rate, or re-seeded at the switch). Then the bake cuts WFZ's rows at the new
  chain. **M, engine.** Canonical bytes move if `parallax.emp` changes (**INFERRED**).
- **Gain:** up to 192 px of C1 and 256 px of C2 open to the real sky.

**(b) Chemical Plant's own sky at the bottom of C3, on the route-fix geometry: built and flown.**
- Today C3 has no slack. Under the route fix it is 832 px with 160 / 160 slack.
- The variant (`manifest_routefix_cpz_sky.json`) adds CPZ donor (8320, 0, 256, 128) directly above
  Chemical Plant's clip, at C3's lane. It is the same paste offset, the same song, and empty sky.
- The shaft becomes 704 px.

| Check (**MEASURED**, §8 b5, w2) | Route fix | Route fix + CPZ sky |
|---|---|---|
| Bake | rc 0 | rc 0 |
| C3 length, split | 832, 416 / 416 (need 256 / 256) | 704, 352 / 352 |
| Collision | 250 / 255 | 250 / 255 |
| Pool | 2,846 tiles, 48 pages | 2,846 tiles, 48 pages |
| Worst camera window | 12 of 12 | 12 of 12 |
| SCREEN | 0 / 0 / 0 | 0 / 0 / 0 |
| crossing_witness `wfz_to_cpz` (2 drops) | not run here | **0 glitch ticks, slack 8 and 9 frames** |
| Anchors | STALE (as the touch-ups note) | STALE (same ritual) |

- **Pictures:** `c3_routefix.png` and `c3_routefix_cpz_sky.png`.
- **What the owner sees:** the last 128 px of the fall into Chemical Plant open onto its real
  background, instead of flat blue.
- **INFERRED:** screen tops there are above Sonic 2's own CPZ camera box (donor y < 0). So CPZ's
  background holds still vertically for up to 224 px of camera travel. This was not measured by
  a scroll witness.
- **Cost: S.** It is one builder knob (CPZ's top row at C3's lane) inside the route-fix parcel.

---

## 4. Interaction with the route fix

`route_fix_builder.patch` (`MTW_W=1024 OOZ_DX=496 DROP_C9=1 EHZ_FLOOR=960 MTZ_WEST_FLOOR=256
DROP_D=320`) was applied to a scratch copy of the builder. With every knob at its default, the
copy reproduces the committed manifest byte for byte (**MEASURED** §8 b1).

| Shaft | Today: length / slack / full-cover travel | Route fix |
|---|---|---|
| C1 wfz_to_ehz | 512 / 192 / 296 | 448 / 128 / 232 |
| C2 wfz_to_mtz | 832 / 320 / 616 | **1,152 / 640 / 936** |
| C3 wfz_to_cpz | 512 / 0 / 296 | **832 / 320 / 616** |
| C4 ehz_to_hpz | 560 / 240 / 344 | **944 / 624 / 728** |
| flat tunnels | unchanged | unchanged |

**MEASURED** (§8 m2): the route fix raises the shafts' fully covered camera travel from 1,552 to
2,512 px. The whole act's cover share goes from 10.3% to 11.2%.
- **Why it happens** (**READ** the patch and builder):
  - `DROP_D = 320` lowers everything under Wing Fortress, so C2 and C3 each gain 320.
  - `EHZ_FLOOR = 960` raises Emerald Hill 384 px against Metropolis, so C4 gains 384 and C1
    loses 64.
- **No mechanical conflict.** Nothing here changes the patch, and the patch does not break
  anything measured here.
- **It pulls against the new wish.** It adds cover the owner just asked to minimise. It is also
  what creates the one no-engine opening measured in §3.3 (b).
  - Most of the new slack sits next to rows that have no map: EHZ below 1024, HPZ above 0, and
    WFZ, which is refused. So it can only be closed by moving pieces.
  - That is the touch-ups sweep again, and its rows were already constrained: DROP_D 160 left C1
    too short.

**Recommendation: two parcels, route fix first.**
1. **The route fix, as measured.** It is the only way into the act from the start.
   - Optionally fold §3.3 (b) into it: the same builder file and the same re-verification set,
     once the owner says yes to it.
   - Its report should state the shaft growth above, so it is not a surprise.
2. **The cover work.** Whichever of §2.3's cuts and §3's art options the owner picks. Each is its
   own tooling or engine change, and each re-derives connector lengths, so each is sized on the
   route-fix geometry, not today's.

Doing the cover work first would size it on shafts the route fix then lengthens (**INFERRED**).

---

## 5. The hub's reading, tested

- **"Include the tall shafts": consistent** with "Tall shafts too I think".
- **"Make whatever hides the backgrounds in tunnels and shafts as small as possible":
  corrected.**
  - **Flat tunnels have nothing spare to cut.** They can only get "smaller" by being redrawn
    (§3.2) or by buying an engine or tooling cut (§2.3).
  - **Shafts can lose only their slack.** Measured, today nothing from the neighbouring zones'
    maps can fill it without the Wing Fortress engine change.
  - **"Hiding" may include the fill.** The reading assumes the covering means the connectors. The
    grey fill at every piece's edge also hides backgrounds (6.7% of in-zone screens, §1.2), and
    the owner's words do not say "tunnel".
- **"Show foreground from the zone the player is in, instead of the covering": true only outside
  the core.** For about a screen around the switch, the player is in neither zone's colours. There
  the best available is the zone's art recoloured into Sonic's palette (§3.2).
- **A reading the hub did not consider.** "Get rid of the thing hiding backgrounds" may mean he
  wants to **see the backgrounds** in connectors, not a smaller wall. For example, a shaft open
  to the sky like a Sonic 2 vertical passage. That is possible only in slack (§3.3), and it is
  exactly what the flat blue Wing Fortress shafts deny today.

---

## 6. The question for the owner

**"Which covering did you mean? Fly to these in the debug build and tell me the letter (or read
me the x, y):**
- **A.** The flat blue lane inside the Wing Fortress shafts: stand in one at **(4064, 1800)**
  (shaft x 3968..4159, y 1408..2239).
- **B.** The grey walls of a flat tunnel: **(2864, 2450)**, the middle of the first tunnel.
- **C.** The grey stone at the edges of a zone: Emerald Hill's top-left corner at
  **(164, 1924)**. There the top half of the screen is stone where Sonic 2 would show sky.

**And when it goes, do you want to see that zone's real background there (open sky), or its
foreground, like rock or machinery?"**

---

## 7. Files

In `docs/research/2026-09-28-woven-cover/`:

| File | What it does |
|---|---|
| `cover_measure.py` | the §1.2 / §2.2 tables. Reads the manifest, the donors and the engine constants through the bake's own functions |
| `cover_today.txt`, `cover_routefix.txt` | its output on the committed act and on the route fix |
| `donor_rows.py` | empty / opaque share of donor rows (§3.1) |
| `find_opaque.py` | fully opaque 32 x 32 art squares (§3.2) |
| `cover_variant.py` | scratch manifest variants: `wfz_c1:N`, `wfz_c2:N`, `cpz_c3:N`, `art:...`, `report` |
| `bake_variant.sh` | copies a variant over `clips.json` and bakes it (no `--keep`). The caller restores `clips.json` |
| `render_connector.py` | the five PNGs |
| `manifest_routefix_cpz_sky.json` | the §3.3 (b) variant, kept as the record |
| `witness_c5_ehz_art.txt`, `witness_c3_routefix_cpz_sky.txt` | crossing_witness outputs |

## 8. Commands and results

Everything was run from the worktree root. The donor trees and `tools/bin/salvador` were copied
in from the main checkout (they are gitignored). Build env:
`SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil`,
`SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob`.

**Bakes.** `python3 tools/clip_rom_bake.py bake games/sonic4/data/clips/s2_woven/clips.json --allow-dirty`.

- **b0, the committed act:**
  - rc 0;
  - collision 250 / 255;
  - N1 worst window 12 at camera (4648, 2352);
  - 2,894 pool tiles, 49 pages;
  - SCREEN 0 / 0 / 0 over 419,120 centres;
  - the Z2 line per connector (the §2.2 needs).
- **b1, the route-fix builder copy.** `patch` of `route_fix_builder.patch` onto a scratch copy of
  `build_woven_act.py`:
  - defaults: `cmp` IDENTICAL to the committed `clips.json`;
  - the route-fix knobs print C1 448, C2 1152, C3 832, C4 944.
  - The scratch copy and its two data files were deleted.
- **b2, WFZ over C2** (`cover_variant.py ... wfz_c2:N`), N = 32, 64, 128, and with `wfz_c1:192`,
  256: all rc 1, `ClipScrollError: WFZ: band 0 drifts at [0, 128] across the chain's configs`.
- **b3, WFZ over C1, `wfz_c1:64`:** rc 1, the same error.
- **b4, C5 EHZ art** (`art:ehz_to_mtz:EHZ:6144,448:6336,416`):
  - rc 0;
  - KEYED corridor sheet 57 tiles;
  - 2,905 pool tiles, 49 pages;
  - N1 worst 12 at (4648, 2352);
  - collision 250;
  - SCREEN 0 / 0 / 0.
- **b5, route fix + `cpz_c3:128`:**
  - the first try was refused, R3: the new clip had no music key; the variant now copies it;
  - then rc 0;
  - `Z2 wfz_deck -> cpz_over_wfz_to_cpz ... at y=1760; 352 px ... before it and 352 after,
    256 / 256 needed`;
  - collision 250;
  - N1 worst 12 at (4288, 2688);
  - 2,846 pool tiles, 48 pages;
  - SCREEN 0 / 0 / 0 over 412,676.
- **b6, one-way test:** the builder copy with `DROP_D=-128` prints C1 384, C2 704, C3 384. With
  `report`:
  - rc 0;
  - `Z2 SHORTFALL ... 192 px above / 192 px below and the rule needs 256 / 256`;
  - SCREEN `0->3 slack -64 px; 3->0 slack -64 px`.
  - Not flown: it is not the asymmetric split cut 5 needs.

**Measurements:**
- **m1.** `python3 docs/research/2026-09-28-woven-cover/cover_measure.py games/sonic4/data/clips/s2_woven/clips.json`,
  saved as `cover_today.txt`.
- **m2.** The same on the b1 route-fix manifest, saved as `cover_routefix.txt`.
- **d1.** `donor_rows.py s2disasm WFZ 3456 3648 1664 2048` and `... 1536 1792 ...`: rows
  1792..2047 are 100% empty. `... 5888 6144 ...` (C3's columns, donor x 5872..6127): 1664..1791 are 100% opaque hull.
- **d2.** `donor_rows.py s2disasm CPZ 8320 8576 0 256`: 100% empty.
- **Level sizes.** `s2_donor.level_size`: WFZ camera y 0..1824, EHZ 0..800, MTZ -256..2048,
  CPZ 0..1824, HPZ 0..1824, OOZ 0..1664.

**Witnesses.** Each build was
`FAST=1 DEBUG=1 S2CLIP=s2_woven ./build.sh` with the variant as `clips.json`, followed by
`python3 tools/crossing_witness.py --rom s4.s2clip.debug.bin --lst s4.s2clip.debug.lst --manifest games/sonic4/data/clips/s2_woven/clips.json --corridor <id>`.
- **w1, b4's ROM** (crc `c01ef69d`, 1,195,438 B, build rc 0), `--corridor ehz_to_mtz`:
  - rc 0; 6 runs, 0 faulted, 0 glitch ticks, worst slack 1 frame;
  - at gsp $1000 the background settles +10 and MTZ reaches the screen +11;
  - at gsp $0600, +8 and +25.
- **w2, b5's ROM** (crc `285e4182`, 1,195,526 B), `--corridor wfz_to_cpz`:
  - rc 0; 2 drops, 0 glitch ticks, slack 9 and 8 frames.
  - The build itself exited 1 **only** on the clip_anchors STALE lane: packed end 0xE4B82, rule
    now 0x100000. That is the touch-ups note's §4 ritual. The ROM was written and its provenance
    reported FRESH.

**Restore.** After every variant: `git checkout -- games/sonic4/data/clips/s2_woven/clips.json`.
The generated tree was never kept: bakes ran without `--keep`, and the build restores it itself.
The variant ROMs, listings and anchor measurements were deleted.
