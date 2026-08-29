# S3K Tails + Knuckles asset staging (design #3 prep)

Staged assets for the per-character dispatch plan
(`docs/superpowers/specs/2026-07-02-character-dispatch-design.md`, §"Asset
sourcing"). This directory is **not referenced by any build manifest** — it costs
zero ROM bytes. The character plan's C2/C4 tasks wire these into
`collision_data.emp` (or wherever character embeds land) and author the `.emp`
animation tables.

Everything here is produced by `gen_characters.py` — deterministic, reproducible,
no dependency on the session that created it. Regenerate with:

```
cd games/sonic4/data/characters_staging
./gen_characters.py [skdisasm_root]   # default /home/volence/sonic_hacks/skdisasm
```

The generator also **ships** the build-consumed Tails trio into the real data
dirs the manifest embeds (`art/optimized/characters/tails*.bin`,
`games/sonic4/data/mappings/tails*.bin`,
`games/sonic4/data/dplc/optimized/tails*.bin`) and prints which of them changed.
That is deliberate: it makes this script the single source of truth end to end,
so a regenerate can never leave the ROM's copy stale. Knuckles is not shipped —
nothing embeds him yet.

> **Reproducibility gate — the expected bytes CHANGED on 2026-08-10.** Tails' art
> is no longer a byte-for-byte S3K copy; it is re-indexed (see below). A
> regenerate against a pre-2026-08-10 checkout of these blobs will therefore
> differ, **deliberately**. The current run is still bit-reproducible against
> itself: two consecutive runs produce byte-identical output.

## Provenance (exact skdisasm sources, read-only)

The spec ruled: assets = **stock Sonic 3 & Knuckles from skdisasm** (S.C.E. carries
zero Tails/Knuckles art — verified). The canonical player objects in
`skdisasm/s3.asm` (`Obj_Tails`, `Obj_Tails_Tail`, `Obj_Knuckles`) load exactly the
files below — **not** the `*_S3` (Sonic-3-lock-on), `*2P` (competition), `SStage`
(special stage), or `Extra` variants, which are out of scope.

| Set | Art | Mappings | DPLC | Anim |
|---|---|---|---|---|
| Tails body | `General/Sprites/Tails/Art/Tails.bin` | `Map - Tails.asm` (`Map_Tails_`) | `DPLC - Tails.asm` (`PLC_Tails_`) | `Anim - Tails.asm` (`AniTails_`) |
| Tails appendage | `General/Sprites/Tails/Art/Tails tails.bin` | `Map - Tails tails.asm` (`Map_Tails_Tail_`) | `DPLC - Tails tails.asm` (`PLC_Tails_Tail_`) | `Anim - Tails Tail.asm` (`AniTails_Tail_`) |
| Knuckles | `General/Sprites/Knuckles/Art/Knuckles.bin` | `Map - Knuckles.asm` (`Map_Knuckles_`) | `DPLC - Knuckles.asm` | `Anim - Knuckles.asm` (`AniKnuckles_`) |

Palettes: `General/Sprites/Knuckles/Palettes/Main.bin`, `.../SSZ End.bin`.

## What was extracted / converted

Per-set counts (from the generator summary):

| Set | Frames | Src art (tiles) | Contiguous art (tiles) | Max tiles/frame | Anim scripts |
|---|---|---|---|---|---|
| tails | 251 | 2858 | 3635 | 24 | 42 |
| tails_tail | 45 | 139 | 278 | 9 | 13 |
| knuckles | 251 | 4092 | 4383 | 29 | 37 |

Frame counts verified against the raw `.asm` pointer tables (251/251 Tails
map+dplc, 251/251 Knuckles, 45 appendage, anim 42/37/13). Mapping and DPLC frame
counts match per set (asserted in the generator).

### Staging tree

```
characters_staging/
  gen_characters.py            reproducible extractor/converter (this dir, not tools/)
  README.md
  tails/
    art/tails.bin              S3K art, RE-INDEXED to our palette order (2858 tiles)
    art/tails_opt.bin          contiguous per-frame layout — BUILD-CONSUMED (3635 tiles)
    art/tails_tail.bin         appendage art, RE-INDEXED (139 tiles)
    art/tails_tail_opt.bin     appendage contiguous — BUILD-CONSUMED
    mappings/tails.bin         Aeon VDP-order mappings + flip-invariant bbox
    mappings/tails_tail.bin    appendage mappings
    dplc/tails.bin             raw S3K-format DPLC (provenance / re-optimizable)
    dplc/tails_opt.bin         1 entry/frame, split <=16 tiles — BUILD-CONSUMED
    dplc/tails_tail.bin        appendage DPLC (raw)
    dplc/tails_tail_opt.bin    appendage DPLC (optimized)
    anim/tails_anims.json      42 raw S3K scripts, decoded (see "Deferred")
    anim/tails_tail_anims.json 13 raw scripts
  knuckles/
    art/knuckles.bin           raw S3K art, byte-for-byte (4092 tiles) — NOT re-indexed
    art/knuckles_opt.bin       contiguous — BUILD-CONSUMED (4383 tiles)
    mappings/knuckles.bin      Aeon VDP-order mappings
    dplc/knuckles.bin          raw S3K-format DPLC
    dplc/knuckles_opt.bin      optimized — BUILD-CONSUMED
    anim/knuckles_anims.json   37 raw scripts
  palettes/
    knuckles_main.bin          Knuckles gameplay palette line (16 colors)
    knuckles_ssz_end.bin       Knuckles Sky Sanctuary ending palette line
```

The trio the build consumes mirrors Sonic exactly (see
`collision_data.emp`: `mappings/sonic.bin` + `dplc/optimized/sonic.bin` +
`art/optimized/characters/sonic.bin`): **`mappings/<name>.bin` +
`dplc/<name>_opt.bin` + `art/<name>_opt.bin`**. The raw `art/<name>.bin` and
`dplc/<name>.bin` are kept for provenance and re-optimization.

## Palette re-indexing — Tails' art is NOT a pass-through

S3K art indexes **S3K's** character palette. Aeon loads a *different ordering of
the same colours* into CRAM line 0 (`art/palettes/SonicAndTails.bin`, the
sonic_hack / S2-era order), and the player draws at palette 0 verbatim
(`Player_InitAssets`: `vram_art(tile,0,0)`). Dropping S3K art in unchanged gave
Tails a grey head and an orange body.

The fix, applied at build time by `gen_characters.py`, is a **colour-lossless
index permutation** of Tails' body art and appendage art. Zero ROM cost, zero
CRAM cost, zero runtime cost, and — the reason this beats a runtime palette swap
or a second CRAM line — Sonic and Tails stay renderable on one line at the same
time, which a follower / 2P mode needs.

| S3K idx | CRAM word | our idx | | S3K idx | CRAM word | our idx |
|---|---|---|---|---|---|---|
| 0 | `$0000` | 0 | | 8 | `$00AE` | 14 |
| 1 | `$0EEE` | 6 | | 9 | `$008E` | 15 |
| 2 | `$0E66` | 5 | | 10 | `$08AE` | 10 |
| 3 | `$0C42` | 3 | | 11 | `$046A` | 11 |
| 4 | `$0822` | 2 | | 12 | `$0ECC` | 4 |
| 5 | `$0080` | **none** | | 13 | `$0CAA` | 7 |
| 6 | `$000E` | 12 | | 14 | `$0866` | 8 |
| 7 | `$0008` | 13 | | 15 | `$0222` | 1 |

Genesis art is 4bpp, 2 pixels/byte, high nibble first; both nibbles of every byte
are permuted. Output length equals input length, so there is **no ROM-size or
placement delta** — only content.

**Why it is lossless.** `$0080` (S3K index 5) is the one colour our line does not
carry, and **Tails' art uses index 5 exactly zero times** — body and appendage
alike. The generator asserts this: `remap_art_indices` refuses (`AssertionError`)
if any index without a counterpart is present, rather than silently painting
those pixels a wrong colour. The permutation itself is **re-derived from the two
palette files on every run** by matching CRAM words, then checked against the
pinned `PALETTE_REMAP_EXPECTED`; editing either palette fails the run loudly.

**A regenerate from raw S3K must go through this step.** Copying
`General/Sprites/Tails/Art/*.bin` in by hand reintroduces the bug. Both the
staged raw `art/tails*.bin` and the contiguous `art/tails*_opt.bin` are emitted
already re-indexed, so either can be re-optimised later without redoing this.

**Knuckles is deliberately NOT re-indexed** and remains a raw copy: his art uses
S3K index 5 for ~3,450 pixels, so no permutation is lossless for him. He needs a
genuine palette swap (S3K itself swaps `Pal_Knuckles` into line 0). Logged in
`docs/DEFERRED_WORK.md`. **Sonic is not produced here at all** — his art is
already in our order and is untouched by any of this.

## Format decisions MADE (pipeline mirrored our Sonic path exactly)

- **Art** — S3K character art is already uncompressed 32-byte 4bpp tiles, so
  there is no transcode (Aeon uses uncompressed sprite art, no Nemesis). Tails'
  art is **re-indexed** into our palette order on the way through (see above);
  Knuckles' is copied byte-for-byte.
- **Mappings** — converted from the S3K **6-byte** piece format
  (`Y.b size.b tile.w X.w`) to Aeon's **8-byte VDP-order** piece
  (`Y.w size.b pad.b tile.w X.w`) with a per-frame flip-invariant bbox header,
  byte-identical to `tools/convert_s2_mappings.py`'s output shape. (S3K's 6-byte
  piece is the only format difference vs S2's 8-byte input; tile attribute words
  and size codes copy straight through.) Spot-checked: emitted Tails frame 1
  matches the S3K source piece-for-piece.
  **One exception, and only one (2026-08-29, owner ruling d-36):** the
  rolling-ball frames' piece `y_off` is shifted so the ball seats flush on the
  collision floor, because stock S3K's balls float/sink against our shared ball
  radius. The shift is DERIVED from `BALL_Y_RADIUS` and the character's `Roll`
  animation row on every run — nothing is typed — and asserted afterwards by
  `tools/test_ball_seating.py`. See `derive_ball_shift` and
  `docs/CHARACTER_BOX_AUDIT.md`. Every other frame is still verbatim.
- **DPLC** — the S3K player-DPLC entry word (bits 15-12 = tile_count-1, bits 11-0
  = tile_offset) is **identical** to S2's, so `tools/dplc_layout.py`'s parser
  applies unchanged. Ran its contiguous-art + one-entry-per-frame optimization,
  then split every run to **<=16 tiles/entry** (the 4-bit count field's hardware
  limit — the June entry-splitting fix). **Asserted in the generator**
  (`assert_dplc_le16`, plus a defensive assert in `write_dplc`); max optimized
  entry is exactly 16 for both 251-frame sets, 9 for the appendage. This is the
  "Tails/Knux need regen" item from memory, now produced through the FIXED path.

## Deferred (format inventions belong to the character plan, not prep)

- **Animation `.emp` tables** — Aeon's `sonic_anims.emp` is a **hand-curated
  11-entry table** (`Ani_Sonic`) whose ordinals ARE the universal `ANIM_*` ids
  (Walk=0 … GetUp=10, `ANIM_COUNT`-asserted). S3K Tails ships **42** scripts and
  Knuckles **37**, in S3K's own order. Reducing/reordering S3K's scripts onto the
  11 universal ids — **plus** authoring the new ability anims the spec adds
  (`ANIM_FLY`/`ANIM_FLY_TIRED` for Tails; `GLIDE`/`SLIDE`/`CLIMB`/`LEDGE`/`GETUP`
  reuse for Knuckles) and re-asserting every table's `ANIM_COUNT` — is a semantic
  authoring decision the character plan (C2/C4) owns. So animations are staged as
  **intermediate JSON** (`*_anims.json`): each script keeps its S3K index/label,
  duration (with `DUR_DYNAMIC` flagged), decoded frame list, decoded terminator,
  and **`raw_hex` as the source of truth**. Aeon's anim control codes ($F7-$FF,
  `engine/system/constants.emp`) already match S3K's, so no byte remap is needed —
  only the id-selection/reordering. Sanity-confirmed: S3K Tails anim 0 (walk) =
  frames `7,8,1-6` and anim 1 (run) = `$21-$24`, byte-identical to Sonic's
  `Ani_Sonic.Walk`/`.Run`.
  - Note: S3K anim scripts are padded with trailing `$FF` to fixed rows; the
    decoder stops at the first terminator and records the padding as
    `trailing_bytes` (informational).

## What the character-dispatch integration tasks still need to do

1. **Author the `.emp` anim tables** (`tails_anims.emp`, `knuckles_anims.emp`,
   `tails_tail_anims.emp`) from the JSON — the deferred decision above — and add
   the new `ANIM_*` ids per spec §5/§7.
2. **Wire the embeds** — add `cd_mappings`/`cd_dplc`/`cd_artbase` in
   `tails.emp`/`knuckles.emp` `CharacterDef`s pointing at
   `mappings/<name>.bin` + `dplc/<name>_opt.bin` + `art/<name>_opt.bin`
   (move/copy these out of `characters_staging/` into the real data dirs the
   manifest reads, matching where Sonic's live).
3. **Palettes.**
   - **Knuckles** has his own 16-color line — `palettes/knuckles_main.bin`
     (gameplay) and `knuckles_ssz_end.bin` (ending). The plan must load the
     Knuckles line into the player palette slot when Knuckles is active.
   - **Tails** has **no separate palette** in S3K — Tails shares the combined
     Sonic+Tails palette, and needs no palette file of his own here. **Resolved
     2026-08-10:** our in-repo `art/palettes/SonicAndTails.bin` carries the same
     colour set as S3K's in a *different order*, which is why Tails first
     rendered wrong; his art is now re-indexed into our order at build time and
     shares CRAM line 0 with Sonic unchanged. See "Palette re-indexing" above.
4. **VRAM budget — the character DPLC window.** Aeon DMAs per-frame character art
   into a fixed window at **tile $3C0 ($7800)**, currently documented/sized for
   Sonic at **"up to 25 tiles"** (`games/sonic4/player/sonic.emp`,
   `docs/ENGINE_ARCHITECTURE.md`). Staged maxima:
   - **Knuckles: 29 tiles/frame** — **exceeds** the current 25-tile window. The
     window must grow to >=29 (or to the max over all playable characters) and
     the surrounding pool layout ($5C0 SAT/HScroll sub-region etc.) re-checked.
   - **Tails body: 24 tiles/frame** fits 25, **but the appendage is a second
     simultaneously-resident object needing its own DPLC window** (max 9
     tiles). Tails therefore needs **body(<=24) + tail(<=9) = up to 33 tiles**
     of character VRAM live at once — a second window must be allocated for the
     appendage (the spec's `CreateChild_FlipAware` tail object with "own DPLC").
   Size the character VRAM region for the worst case before C2/C4 art loads.

## Verification performed

- Frame counts match raw `.asm` pointer tables exactly (251/251/45/251, anim
  42/37/13).
- Mapping frame count == DPLC frame count per set (generator assert).
- **Cross-agreement**: for all 547 frames, every mapping piece's relative tile
  reference stays within that frame's DPLC tile budget (0 violations) — proves the
  independent mapping and DPLC parses agree and tile numbering is DMA-base-relative
  as expected.
- Emitted Aeon mapping binary spot-checked against the S3K source (Tails frame 1
  piece-for-piece; bbox correctly flip-symmetrized).
- Anim decode spot-checked: Tails walk/run == Sonic walk/run frame lists.
- DPLC <=16-tile invariant asserted in-generator; max optimized entry = 16.
- Determinism: two consecutive runs produce byte-identical output.
- **Palette permutation** — derived by matching all 16 CRAM words of
  `art/palettes/SonicAndTails.bin` against S3K's
  `General/Sprites/Sonic/Palettes/SonicAndTails.bin` line 0: 15 of 16 S3K
  indices match exactly one of ours, index 5 (`$0080`) matches none, and our
  line has no duplicate words (so each match is unambiguous). Asserted against
  the pinned table every run.
- **Losslessness** — index histograms over Tails' body and appendage art before
  the remap: index 5 count = **0** in both. Post-remap histograms are the
  before-histograms permuted, population-for-population (checked per index in
  the generator), and byte length is unchanged.
- **Blast radius** — regenerating touches only the four Tails art blobs plus
  their two shipped copies. Mappings, DPLCs, anim JSON, Knuckles, and
  `art/optimized/characters/sonic.bin` are byte-identical across the change.

## Concerns / surprises

- **Knuckles' 29-tile frames** overrun Sonic's 25-tile DPLC window — flagged
  above; must be resolved in the VRAM layout during C4, not silently truncated
  (truncation is exactly the class of bug the <=16 split fix addresses, one level
  up).
- **Contiguous-art overhead**: the optimized art duplicates tiles shared across
  frames (Tails 2858 -> 3635 tiles, Knuckles 4092 -> 4383). This is the same
  trade Sonic makes (1 DMA per frame change); it lives in the sprite-art region,
  not the compressed act pool, so it does not touch the FG budget — but it is real
  ROM. If ROM pressure bites, the raw art + multi-entry raw DPLC (`dplc/<name>.bin`)
  remain available as the un-duplicated alternative.
- The pre-existing `games/sonic4/data/dplc/tails.bin` (+ `mappings`/`art`) is the
  **sonic_hack S2-era Tails**, which the spec explicitly supersedes with this S3K
  extraction. They are NOT identical (S3K Tails has 251 frames incl. S3K-only
  poses). The character plan should replace, not reuse, the S2 Tails staging.
- Scope: only the canonical 1P S&K set + Tails appendage were extracted. `*_S3`,
  `*2P`, `SStage`, `Super Tails birds`, and `Tails Extra.bin` variants exist in
  skdisasm but are out of scope for the base playable characters.
