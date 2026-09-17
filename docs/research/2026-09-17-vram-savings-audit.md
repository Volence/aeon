# VRAM savings audit: everything except the two priced levers (2026-09-17)

**Branch:** `research/vram-savings-audit`, based on aeon `de9c72e7`.
**Question (owner):** "Are there any other ways in our engine we could save VRAM?"
**Out of scope, cited only in totals:** the foreground art cache 12 -> 10 frames
(REGIONS-P2-STEP7, being researched by another agent) and the 64x64 -> 64x32 scroll
planes (REGIONS-P2-STEP8).
**Nature:** research only. No engine file, no ROM byte, no tool committed. The
measurements below were made with throwaway scripts in the session scratchpad over
committed data files; each figure names the file it came from so it can be re-derived.

Labels: **MEASURED** = computed from a committed build input or generated artifact
in this session. **DERIVED** = arithmetic over measured or declared values, no
runtime assumption. **INFERRED** = rests on a claim about runtime behaviour that
this lane did not observe (no emulator; see the runtime tags at the end).

---

## 0. Short answer

1. **There are about 62 tiles that are cheap and cost nobody anything the owner has
   asked for**, and about **84 more** that each spend an owner dial (the BG band
   reserve, the waterline height ceiling) or carry a runtime risk. That is small
   next to the two excluded levers (384), but it is not zero, and **every item is
   independent of both excluded levers.**
2. **Two of the three hypotheses in the brief are wrong:**
   - `spare_nametable` is **not** a nearly free win. The owner already declined it on
     2026-09-10 (card `VRAM-FOR-OBJECTS`, option `everything`), because it has three
     claimants: the window as a third layer, Plane Z, and a software-render window
     borrowing up to 64 tiles. And shrinking the planes does not release it for
     Plane Z (section 3.1).
   - Taking the debug tags out of RELEASE frees **nothing objects can use**: the
     owner plays DEBUG builds, so any object that needs those tiles has to fit in the
     DEBUG shape too. The version that works in both shapes is to let the tags
     borrow `spare_nametable` space in DEBUG (candidate F, 13 tiles).
   - Object-art residency (loading object art per region instead of fixed slots)
     **saves 0 tiles on today's content** (MEASURED: act 1 places three object
     types, two of them test placeholders). It changes how VRAM cost grows as
     object types are added: with fixed slots the cost is every type's art added
     together, and with residency it is only the art of the types on screen at
     the same time. I cannot give a tile figure for it until an act with real
     badniks exists. So it is the biggest *future* lever, not the biggest *today*.
3. **Take first:** the ring-frame window (C, 12), the unreachable waterline tail (D,
   16), the Tails-tail / insta-shield overlay (A, 9) and the debug-tag borrow (F, 13).
   Together that is 50 tiles with no owner dial spent. Then ask the owner about the
   BG band reserve (E, 56).

---

## 1. What I read

- `games/sonic4/vram.toml` (all region comments), `tools/gen_vram_map.py` (header
  and checks), `docs/generated/vram-map-sonic4.md`, `games/demo/vram.toml` (names
  only).
- `docs/research/2026-08-11-vram-allocation-brief.md`,
  `docs/research/2026-08-11-vram-linker-reference-survey.md` (all nine trees). The
  internal audit and toolchain prior-art files from the same date were not re-read:
  the registry supersedes the audit, and I did not need the prior art.
- `docs/research/2026-09-09-plane-size-lever.md` (parts 3-4),
  `docs/DEFERRED_WORK.md` `VRAM-NEIGHBOURHOOD` (incl. WORKING-SET, OBJ-ART, REF-DOCS),
  and `bg_region OCCUPANCY IS 320/448` (~line 25657).
- `docs/ENGINE_ARCHITECTURE.md` §2.2-2.4 and §9.9.
- `docs/decisions.jsonl` card `VRAM-FOR-OBJECTS` (both versions), `docs/OVERSEER.md`
  (the ruling that places the recut inside regions), `docs/lane-status.json`
  (REGIONS-P2-STEP7/8 rows), handoffs 19 and 20.
- `docs/research/2026-09-09-object-art-tier.md`: only through its DEFERRED_WORK
  summary (OBJ-ART). I did not re-read its body.
- Source: `engine/system/constants.emp` (VDP geometry), `engine/system/buffers.emp`
  (the HScroll DMA site), `engine/objects/dplc.emp` (`dplc_peak_tiles`),
  `engine/objects/rings.emp`, `engine/level/bg_anim.emp` and
  `engine/level/parallax_dsl.emp` (the waterline geometry),
  `games/sonic4/objects/dust_spindash.emp`,
  `games/sonic4/player/player_instashield.emp` (header),
  `games/sonic4/objects/path_swap.emp`, `games/sonic4/player/player_common.emp`
  (debug-fly), `games/sonic4/test/ojz_scroll_test.emp` (art load sites, test art,
  vprobe band).
- **Note on the brief:** `REGIONS-P2-STEP7` / `REGIONS-P2-STEP8` are not sections of
  `DEFERRED_WORK.md`. They exist only as rows in `docs/lane-status.json` and as
  mentions in handoffs 19/20. I priced against the card and the plane-size doc.

---

## 2. The map as it stands, with measured occupancy

`gen_vram_map.py --game sonic4` exits 0 on the committed toml ("23 regions, 1 free
tiles"), and regenerating into the scratchpad gives byte-identical copies of the
committed `vram-map-sonic4.md`, `tools/vram_map.py` and the generated block in
`config/constants.emp`. So the map below is the one the build uses.

| tiles | region | declared | occupied / used (label, source) | notes |
|---|---|---|---|---|
| 0-767 | `fg_art_pool` | 768 | 612 tiles in 10 pages (MEASURED, `act_pool_page*.bin`) | **excluded lever** |
| 768-895 | `spare_nametable` | 128 | **0** (MEASURED: no engine/game reference outside the registry and a comment) | three claimants, see 3.1 |
| 896-911 | `dust_puff` | 16 | 16 resident (MEASURED, `art_dust.bin` tiles 72-87) | 4 frames live at once |
| 912-923 | `dust_spindash` | 12 | peak 12 (MEASURED, `dplc_dust.bin`) | live only in `PSTATE_SPINDASH` |
| 924-927 | `ring_sparkle` | 4 | 4 (MEASURED) | |
| 928-956 | `insta_shield` | 29 | peak 29 (MEASURED, `dplc/insta_shield.bin`: 3 frames of 23, 3 of 29) | Sonic only, about 6 visible frames per use |
| 957-958 | `debug_preset_readout` | 2 | written in DEBUG only | |
| 959 | FREE | 1 | | |
| 960-991 | `character_window` | 32 | peak **29** (Sonic 29, Knuckles 29, Tails 24; MEASURED, DPLCs) | one character at a time |
| 992-999 | `test_obj` | 8 | 2 solid squares x 4 tiles | test placeholder; level places 3 Solid + 1 Static |
| 1000-1015 | `ring_placeholder` | 16 | 16 (4 frames x 4) | all rings share one global frame |
| 1016-1019 | `test_marker` | 4 | one solid colour x 4 tiles | RELEASE debug-fly cheat uses it |
| 1020-1023 | `debug_lab_name` | 4 | written in DEBUG only | |
| 1024-1399 | `bg_region` | 376 | act default blob **320**, DEBUG showcase blob 118 (MEASURED, `bg_tiles*.bin` headers) | `band_reserve` 56 unresident |
| 1400-1447 | `waterline_strips` | 48 | **8** written (DERIVED: `WATERLINE_H` 16 -> H/2 tiles) | see D |
| 1448-1471 | `spring` | 24 | 24 (MEASURED, `art_spring.bin`) | |
| 1472-1491 | `sprite_table` | 20 | 640 B = `MAX_VDP_SPRITES` 80 x 8 | H40 hardware size |
| 1492-1500 | `tails_appendage` | 9 | peak 9 (MEASURED) | Tails only |
| 1501-1503 | `debug_bganim_tag` | 3 | written in DEBUG only | |
| 1504-1531 | `hscroll_table` | 28 | 896 B = 224 lines x 4 | per-line, NTSC |
| 1532-1535 | `debug_raster_tag` | 4 | written in DEBUG only | |
| 1536-1791 | `plane_a` | 256 | all used | **excluded lever** |
| 1792-2047 | `plane_b` | 256 | all used (plane-size doc) | **excluded lever** |
| (1920-2047) | `window_plane` | overlay | disabled, overlaps the end of Plane B, costs 0 | |

**By category (DERIVED, sums to 2048):** FG cache 768 · nametables 512 + spare 128 ·
VDP tables 48 · BG arena 376 · waterline 48 · object and character art **154**
(of which 12 are test placeholders) · debug tags **13** · free **1**.

What changed against the 2026-09-07 note: `bg_region` is 376, not 388. The spring's
second sheet took 12 more. The objects figure of "~128" was really 154 once the
spring (24) and the Tails appendage (9) are counted. The region BG switch (landed
2026-09-16) added no VRAM: it overwrites the same arena.

---

## 3. Candidates

### 3.1 Checked and rejected (0 tiles, or not free)

- **K. SAT and HScroll sizing: 0 (MEASURED/DERIVED).** The SAT is 640 B =
  `MAX_VDP_SPRITES` 80 x 8, the H40 maximum. Shrinking it lowers the sprite cap,
  and objects need more sprites, not fewer. HScroll is 896 B = 224 x 4 per-line,
  which parallax uses (`buffers.emp` enqueue comment). Per-tile HScroll mode does
  not help: the VDP still reads the table at a 32-byte stride across the same span
  (the deleted per-cell path failed for exactly that reason, per the same comment).
  **The alignment gaps are already used.** Base granularity (plutiedev, confirmed
  2026-09-17): Plane A and B `$2000`, window `$800` (`$1000` in H40), SAT `$200`
  (`$400` in H40), HScroll `$400`. Rounding the two tables up to `$400` leaves 12 +
  4 = 16 tiles over, and `tails_appendage`, `debug_bganim_tag` and
  `debug_raster_tag` sit in exactly those 16 tiles. S3K does the same thing,
  putting art in the gaps between `$F000`, `$F800` and `$FFFF`
  (`sonic3k.asm:1344` register table).
- **PAL note, not a saving:** 240 lines x 4 = 960 B = 30 tiles. If V30/PAL is ever
  turned on, the HScroll table would run 2 tiles into `debug_raster_tag`. No V30
  mode is set anywhere in `engine/` or `games/` (grep), so this is dormant.
- **L. Folding the BG arena into the FG pool to dedupe tiles: 0 on OJZ (MEASURED).**
  After flip-canonical comparison, none of the 320 BG tiles appears in the 612
  FG pool tiles, and the DEBUG showcase blob shares 2 of its 118 tiles with the act
  background. So deduping across the two saves nothing on this act.
- **J. Flip-dedupe inside object sheets: 8 tiles, not worth it (MEASURED).** The ring
  goes 16 -> 10 unique under flips and the spring 24 -> 22. The dust puff and the
  sparkle have no duplicates, and no tile is shared between sheets. Getting any of
  it means splitting 2x2 pieces into flipped halves, which doubles sprite pieces
  per ring against the 80-sprite and per-line limits. C beats it for rings.
- **M. Reclaiming `spare_nametable` outright: 128, and not free.** Priced to the
  owner as option `everything` and declined 2026-09-10. Its claimants are the
  window as a third layer, Plane Z, and the software-render window's 64-tile
  borrow. **A correction to `2026-09-09-plane-size-lever.md` §3.3**, which counts
  it in a "384" on the grounds that at 64x32 "that purpose is met by [the planes']
  own freed tails". That holds for the **window** claimant only. The freed tails
  are at `$D000` and `$F000`, and Plane A/B bases step in `$2000`, so neither tail
  can hold a Plane Z. (`$F000` is a legal window base in H40.) Any 64x32 layout
  with three plane-capable nametables still spends 3 x 128 = 384 tiles on them, so
  the 128 is released only if Plane Z is dropped. The owner's card is
  self-consistent: its "384" is cache 128 + planes 256, and the spare is priced
  separately. Only the plane-size doc double-counts.
- **N. Object-art residency tier: 0 today (MEASURED), unmeasurable for the future
  (BLOCKED).** The only object types in `entity_data.emp` are Spring, Solid and
  Static. Every resident object sheet is either always live (rings, sparkle,
  puffs) or already streamed per frame (character, insta-shield, charge dust).
  With nothing to evict, a residency pool frees nothing. Its value is that adding
  object types stops adding tiles linearly (OBJ-ART). The number it depends on is
  "the worst camera envelope in this act needs N tiles of object art", and that
  needs OBJ-ART step 1 (unbuilt) run on an act with real badniks. **BLOCKED, not
  0.** It also still has OBJ-ART's open palette problem: all four palette lines
  are spent.

### 3.2 Candidates that return tiles

Ranked by tiles per unit of cost. "Conflicts" means conflicts with the two
excluded levers. None of the items below conflicts with them.

| # | candidate | tiles | label | cost / risk / what it constrains | size |
|---|---|---|---|---|---|
| **C** | **Ring frame window.** All rings draw one global `Ring_Anim_Frame` (`rings.emp`, `RING_ANIM_SPEED` 8), so only the current frame's 4 tiles need to be in VRAM. DMA the frame into a 4-tile window when the counter ticks, instead of keeping 16 tiles resident. This is level animated-tile streaming applied to an object. | **12** | DERIVED | 128 B every 8 frames (~16 B/frame average) on a DMA budget already in deficit (OBJ-ART: residual 2,944 B vs 2,976 solo). Put it on Deferrable: a dropped write shows the previous ring frame for one tick. `art_tile` stays constant, so the replay hash is unaffected. A future lost-ring or collect animation with its own counter would need its own 4-tile window. | S |
| **D** | **Waterline tail that can never be written.** Strip tiles = H/2 and `brm_hshift` can only name powers of two. H=64 needs 32 tiles and H=128 needs 64, which the region cannot hold, so tiles 32..47 are unreachable at every height the engine can express. (S3K's H=96 cannot be named here.) | **16** | DERIVED | None to behaviour. Moves `VRAM_SPRING`'s neighbourhood (a byte change) and needs the owner's OK on a sanctioned number. **Owner dial on top:** cap H at 32 (frees another 16) or at today's 16 (another 24). | S |
| **F** | **Debug tags borrow `spare_nametable` in DEBUG.** The 13 tag tiles are written only in DEBUG. Declare them as an overlay on unused spare-nametable tiles, the way the software-render window's borrow was granted. | **13** (both shapes) | DERIVED | Vacated when a spare consumer lands (Plane Z / window layer), so the tags would have to move again. Uses 13 of the 128 alongside the 64-tile render borrow (77 ≤ 128). Needs `gen_vram_map.py` to accept a declared borrow overlay: today it takes only "statically-safe overlays", which is a small tool change. **Not** the release-only version, which frees nothing usable (§0). | S |
| **A** | **Tails appendage shares the insta-shield window.** Only Sonic has the insta-shield and only Tails has the appendage, so the two cannot be live together while one character is on screen. Set `VRAM_TAILS_APPENDAGE = VRAM_INSTA_SHIELD` (9 ≤ 29). Precedent: sonic_hack puts Sonic and Knuckles in the same slot at `$780` (`VRAM_Layout.asm:48-49`), and S3K streams the insta-shield into the one `ArtTile_Shield` window its elemental shields use (`sonic3k.asm:34579`). | **9** | DERIVED; exclusivity INFERRED | A character switch while a flash is live would stream tail art over it, and the switch is a DEBUG cycle. **A sidekick breaks it:** with Sonic and Tails on screen together they need separate windows again, plus 24 for the follower body (memory: 29+24+9 = 62). | S |
| **I** | **Solid-colour test art as one tile per colour.** `test_obj` (two squares x 4 identical tiles) and `test_marker` (4 identical tiles) become 3 single tiles drawn as 4 one-tile pieces each. | **9** now, **12** when the placeholders retire | MEASURED (the art is literal solid fills) | More sprite pieces per test object. The marker is used by the RELEASE debug-fly cheat, so it has to stay somewhere. | S |
| **G** | **Character window 32 -> 29.** No character frame needs more than 29. | **3** | MEASURED | Removes the headroom for a heavier frame on a future character; the build's `dplc_peak_tiles` ensures would catch that. Hold the base: it is baked into the replay hash. | S |
| **E** | **BG band reserve 56 -> 0.** The arena holds a 320-tile act blob. The reserve is animation headroom nothing uses today. | **56** | MEASURED | **Owner dial**, already carved twice for the waterline and the spring. Takes away the room to insert a BgAnim band without redrawing the BG smaller (promotion inside the 320 still works). **Aurora vendors `BG_TILE_CAPACITY` and must be notified first** (the 18-hour red precedent in VRAM-NEIGHBOURHOOD). A region blob larger than 320 would then no longer fit. | S |
| **B** | **Charge dust shares the accessory window with the insta-shield.** Layout inside the 29-tile window: tail 0..8, dust 9..20, insta-shield 0..28. The charge dust exists only in `PSTATE_SPINDASH` (`dust_spindash.emp` polls it), and the insta-shield can only be triggered from `PSTATE_JUMP`/`ROLLJUMP`. | **12** (on top of A) | INFERRED | **The trigger states are exclusive, but a flash that is already playing is not tied to them.** It keeps animating after the player lands, so jump, insta-shield, land, crouch and charge inside the flash's life would put two streams on one window. Needs a runtime check or an engine rule (retire the flash on landing, or refuse the dust while it lives). | M |
| **H** | **Recut character frames to their unique tiles.** Peak tiles loaded per frame is 29, but the peak count of distinct tiles in a frame is 25 for Sonic and Knuckles and 22 for Tails. Blank tiles (up to 7 in a Sonic frame) and duplicates are there only to keep pieces contiguous. | **up to 4** beyond G | MEASURED (upper bound) | More sprite pieces per frame. Re-runs the character art optimizer, which is a data parcel. | M |
| **O** | **One elastic pool for the FG cache and the BG arena** (the allocation brief's elastic-pool idea extended to BG): slack flows between them instead of sitting in two reserves. | 0 on OJZ | INFERRED | BG layout blits do not take part in page refcounts, and the region BG overwrite writes a fixed arena. This is a large engine change. It only pays off with an act whose BG working set is smaller than its blob. | L |
| **P** | **A rule for future one-shot art** (title card, results, signpost, game over): it borrows a region whose owner is provably idle at that moment. It does not get a permanent window. | 0 today (no such art exists) | DERIVED | Precedent: S2 declares these shares as equal-valued constants (`TitleCard = Animal_1`, `Signpost = Spikes`, `Game_Over = Invincible_stars`; reference survey §3). S2's HTZ-over-Continue bug is the failure mode: a queued DMA outliving the state that owned the region. **Needs the registry's T2 lifetime overlays to be safe.** | M |

---

## 4. What objects could get

**Today's object and character art: 154 tiles** = 121 in the 896..1023
neighbourhood (its 128 minus the 2 debug readout cells, 4 lab-name cells and the
free tile) + spring 24 + Tails appendage 9. The card's "152" is a different cut
of the same map: the whole 128-tile neighbourhood + the spring, without the
appendage.
The rows below count **tiles freed for new object art**, labelled as in §3.

| scenario | arithmetic | freed |
|---|---|---|
| Tier 1: no owner dial, no runtime risk | C 12 + D 16 + F 13 + A 9 + I 9 + G 3 | **62** |
| Tier 1 + Tier 2 (dials and risk) | 62 + E 56 + D's H≤32 cap 16 + B 12 | **146** |
| same, with D capped at today's H=16 instead | 146 + 8 | 154 |
| + H (character recut, upper bound) | 146 + 4 | 150 |
| **Excluded levers alone** (card `VRAM-FOR-OBJECTS`) | cache 128 + planes 256 | **384** |
| Excluded + Tier 1 | 384 + 62 | **446** |
| Excluded + Tier 1 + Tier 2 | 384 + 146 | **530** |
| For comparison, the declined `everything` option | + spare_nametable 128 (and F's 13 then comes from it) | 530 + 128 - 13 = 645 |

As object-plus-character totals: 154 today -> 216 (Tier 1) -> 300 (Tiers 1+2) ->
538 (excluded levers only) -> 600 (excluded + Tier 1) -> 684 (excluded + both tiers).

**These tiles are scattered.** Tier 1 frees tiles in four places: the
neighbourhood (A, C, F, G, I), 1432-1447 (D), and inside the BG arena's tail (E).
Getting one contiguous run needs a deliberate recut that moves windows. That
changes bytes, and `character_window` should not move (its base is in the replay
hash; grow or shrink it with the base held).

**Claims already queued against these tiles, which a planner should subtract:** a
sidekick (+24 body, +9 tail, and it undoes A), elemental shields (0 extra if they
share the insta-shield window the way S3K does), a HUD, lost rings (+4 with C,
+16 without), and a palette line for per-region object sets, which is not a VRAM
cost but gates OBJ-ART.

---

## 5. Recommendation

1. **One small recut parcel with C + D (16) + A + F + G + I = 62 tiles.** None of
   these touch an owner dial except D's sanctioned 48, which is dead space above
   the reachable 32. Do it after STEP7's cache decision so VRAM is carved once.
   That is the same reason STEP7/8 are held, and this parcel should ride with them
   rather than land ahead.
2. **Put E (band reserve) and the waterline height cap to the owner as dials**,
   priced here, with the Aurora notice in the same change.
3. **Do not spend `spare_nametable`** beyond F's borrow without an owner ruling
   that drops Plane Z.
4. **Build OBJ-ART step 1 (the per-envelope object-art figure) when the first real
   badnik set exists.** That is what turns "residency is the biggest future lever"
   from an inference into a number.
5. B and H only if 1-2 are not enough.

## 6. Still open

- **N's real size** (BLOCKED on badnik content plus OBJ-ART step 1).
- **Whether `gen_vram_map.py`'s overlay check can express F's borrow** without
  making the rule "statically safe overlays only" meaningless. That needs a
  tool-owner decision.
- **The plane-size doc's 384** should be corrected to say the spare is released
  only if Plane Z is dropped (§3.1). Not edited here; this report records it.
- **Stale comments found, not fixed (docs-only lane):**
  `games/sonic4/test/ojz_scroll_test.emp:4334-4340` still says `bg_region` is 448
  tiles with `band_reserve = 128` and "slots 1344..1471 are reserved and NO OTHER
  WRITER TOUCHES THEM". Today 1400-1447 is the waterline strips and 1448-1471 is
  the spring. The probe's header (`[2, 3, 31, 6, 8, $A800]`) *reads* like a
  2 x 3 = 6-tile band at slot 1344, which would stay inside the 56-tile reserve,
  but **I did not verify the field meanings**. Also the `spring` region's comment
  in `vram.toml` still opens with "20 tiles RESIDENT" while the region and blob
  are 24.

## 7. Runtime-confirmation tags (for the controller; this lane ran no emulator)

- **[RUNTIME-A]** In DEBUG, cycle the character while an insta-shield flash is
  live and check that no tail art is streamed over it. Only needed if A is taken.
- **[RUNTIME-B]** Jump, insta-shield, land, and spindash as fast as possible. Does
  the flash object still exist on the frame the charge dust spawns? This decides
  B.
- **[RUNTIME-C]** With the ring window built, force a Deferrable drop on a ring
  tick and check the visible result is one stale frame and nothing worse.
- **[RUNTIME-F]** Confirm that no RELEASE frame ever writes the four debug tag runs.
  A write watchpoint over 957-958, 1020-1023, 1501-1503 and 1532-1535 in `s4.bin`,
  the same method as LS-10a. Today this rests on the `vram.toml` comments plus
  LS-10's listing observation that the release `Debug_*` procs collapse to one
  address.
