# Resident acts: bake physical tile words, copy without translating (design, 2026-09-26)

Owner pick `PERF-PICK` = `audit-and-copy` (docs/decisions.jsonl). This is the "copy" half:
candidate 3 of `docs/research/2026-09-25-perf-survey.md`. The survey priced it with a stand-in
plain-copy loop (canonical DEBUG diagonal 34/397 -> 20/383, audit and Canopy off in both) that
put the WRONG art on screen, because it copied section-LOCAL words. This note is the design pass
the survey asked for, written before any engine code. Base: origin/master `91d4119c`.

## The question, restated as the hypotheses to test

1. The engine can tell, per act, that the act is fully resident (survey: `Direct_Map` = `$FF`).
2. For such an act the page -> frame mapping is static and known at build time, so the level tool
   can write the words the copy would have produced.
3. The plain path can be selected per act with no per-word branch.
4. The streaming path is untouched (the Sonic 2 clip act streams and must be unaffected).

Any of 2's premises failing (something remaps frames at runtime) was the stop condition. It did
not fail; the evidence is below, with one hazard found (STRESS_EVICT) that shaped the design.

## What the copy computes today (read, not assumed)

`PageCache_PatchRun_Seq/_Col` (engine/level/page_cache.emp) pick a loop per RUN from
`PageCache_Direct_Map`. Under `PAGECACHE_DIRECT_RESIDENT` ($FF) the loop is
`pc_patch_run_direct`, which per word does:

    local = word & $7FF
    if local == 0            -> store $0000         (attribute bits DROPPED)
    g = map[local]           (map = Cache_Cur_LocalMap, the staged block's SECTION map)
    if g == 0                -> store $0000
    store (word & $F800) | g

The "translation" in this regime is only the section-local -> global map read. The page ->
frame half is already gone (F1, 2026-08-19): `Level_LoadArt` verifies `Page_Table[p] == p` and
then physical == global. So "bake physical words" means: store `attr | global` in the block data
instead of `attr | local`, and make blank words exactly `$0000`.

Measured on the committed OJZ act 1 tree: 589,824 nametable words, 543,613 of them blank, and
**39,443 blank words carry non-zero attribute bits**. The engine never stores those bits (both
loops clear the whole word). So a bake that only swapped the index would put 39,443 different
words into the cache, and in shadow/highlight mode a blank cell's priority bit is visible. The
bake must zero blank words, not just re-index them.

## Hypothesis 1: how the engine knows an act is fully resident — CONFIRMED, with a correction

`Level_LoadArt` (engine/level/load_art.emp) latches `PageIn_Fully_Resident` when
`act_art_pool_pages <= PAGE_FRAMES_CLAMP`, bulk-loads every page, then scans `Page_Table` and
latches `PageCache_Direct_Map = $FF` only if the table is the identity. `$FF` is therefore a
RUNTIME proof, re-derived at every act load (`PageCache_Init` clears it first). The survey read
`$FF` on canonical after boot (`residency_read.py`).

The correction: residency is decided against `PAGE_FRAMES_CLAMP`, and that is **not** a fixed
fact of the act. `PAGE_FRAMES_CLAMP = PAGE_FRAMES - STRESS_EVICT * (...)`
(engine/system/constants.emp): the `STRESS_EVICT` shape builds the SAME committed OJZ tree with
a smaller clamp, and OJZ (10 pages) then streams. So the build tool cannot promise "this act is
resident at runtime"; only the runtime latch can. The design has to stay correct when a
physically-baked act turns out NOT to be resident. That rules out the obvious design.

## Hypothesis 2: is the mapping static and known at build time — CONFIRMED for the latched regime

Every writer of `Page_Table`, enumerated by call site (`grep jbsr` over engine/ and games/):

| writer | reached from | under the resident latch |
|---|---|---|
| `PageCache_Init` | `Level_LoadArt` only | runs before the latch; clears the latch itself |
| `PageCache_Publish` | page-in completion (`PageIn_Process`) | nothing is enqueued after the bulk drain: `PageCache_Request` early-outs on a resident page, `PageCache_Prefetch` early-outs on `PageIn_Fully_Resident`, and the page-in retry paths only re-enqueue a page that is mid-load |
| `PageCache_AllocFrame` (victim path) | page-in only | never reached (as above) |

`PageCache_Audit` (DEBUG) re-checks the identity every `PAGECACHE_AUDIT_INTERVAL` ticks under
the latch and has run clean on every survey leg.

The runtime art swaps the brief named, checked one by one:

- **bg_anim** (`engine/level/bg_anim.emp`): rewrites BG tile PATTERNS in the shared BG region
  by DMA. It changes pixels, never an FG nametable word or a `Page_Table` entry.
- **Region BG switch** (`Region.rg_bg_tiles`, `engine/level/bg.emp`, `section.emp`): loads a BG
  tile blob into the BG region and redraws Plane B from the region's layout. Not the FG pool.
- **Presets / effects** (`Effects_InstallPreset`): palettes, raster programs, VSRAM/HScroll. No
  nametable word passes through them.
- **Palette/priority/flip bits**: the copy sites carry them verbatim (`andi #NT_ATTR_MASK` /
  `or`), in every regime. Nothing between the staged block and `Tile_Cache_Nametable` edits them,
  and `Tile_Cache_Nametable`'s only writers are the two patch runs plus the zero-fill in
  `TileCache_FillAll` (grep of every `lea Tile_Cache_Nametable`).
- **Act reload / warp**: a new act goes through `Level_LoadArt` again (latch re-derived); a
  warp refills the cache inside the same act and does not touch `Page_Table`.

So once `$FF` is latched, physical == global for the rest of the act, and global is exactly what
the level tool already computes (`canon_to_pool`, `ojz_strip_gen.py` Pass 4). Palette/priority/
flip bits are static source data. What is NOT known at build time is whether the latch will be
set at all (STRESS_EVICT above, or any future allocator change that breaks the identity, which
F1 explicitly made cost only the fast path, never correctness).

## The design

### Data: a "physical-form" act (level tool)

`ojz_strip_gen.py` Pass 5 bakes an act in PHYSICAL form when its pool fits the frame budget
(`len(pages) <= PAGE_FRAMES`, read from engine/system/constants.emp like every other budget
constant), else in today's LOCAL form. Physical form means:

1. Every nametable word is `attr | global` (the index the resident copy would have produced),
   and **a blank word (global 0) is `$0000`** — the word the engine stores for it.
2. Every section's local map is the **pool-slot identity**: `map[i] = i` for each real pool slot
   `i`, `0` for a slot in a short page's gap (no word names one), length = last real slot + 1.
   The existing content dedup then stores ONE map for the whole act.
3. A generated `pub const OJZ_ACT_NT_PHYSICAL` (1 or 0) in `sec_local_maps.emp`, which
   `act_descriptor.emp` writes into the Act record.

Point 2 is the reason this survives STRESS_EVICT and every other "not actually resident" case:
with identity maps, the translating loops (general, bounded, direct) produce exactly the same
words from physical-form data as they did from local-form data. The physical form is a valid
input to every loop; the plain copy is merely the one loop that also REQUIRES it. So the level
tool's choice can never be wrong at runtime, only unexploited.

The clip act (`clip_rom_bake.py` runs the same `ojz_strip_gen.generate()`) has 17 pages > 12 and
keeps LOCAL form byte-for-byte; the one-zone resident clip `s2_ehz_boot` gets physical form.
The stress fixture (41 pages) keeps local form.

### Engine: one more latched value

- `Act.pad_21` (a reserved byte) becomes `act_nt_physical: u8 = 0`. Default 0 is the SAFE value
  (local form: every loop translates). No offset moves.
- `PAGECACHE_DIRECT_PLAIN` ($80): a third latched value, negative like `RESIDENT` ($FF).
  `Level_LoadArt` sets it instead of `RESIDENT` exactly when the residency latch would be
  `RESIDENT` AND `act_nt_physical != 0`. Both conditions are needed and both are checked where
  they are decided: residency at runtime, form at build time.
- `PatchRun_Seq/_Col` dispatch: `tst.b Direct_Map / bmi .resident_family` runs BEFORE the
  register bank, and the general/bounded arms keep their exact instruction count (the `movem`
  does not change CCR, so the `bne .bounded` reuses the same `tst`). In the negative family one
  `cmpi.b #PLAIN` picks the plain loop, which needs no bank at all: it touches only d0/a0/a1,
  which the procs' contract already clobbers/advances. The selection is per RUN; there is no
  per-word branch.
- Plain loops: Seq `move.w (a0)+,(a1)+ / dbf`; Col `move.w (a0),(a1) / lea 32(a0) / lea 160(a1) /
  dbf`. Both leave a0/a1 one stride past the run, as the callers require.
- `PageCache_Audit` is NOT touched (another parcel is amortising it): its latched arm is taken for
  any non-zero latch, so PLAIN gets the same three checks as RESIDENT (zero refcounts, no
  dangling frame, identity table) with no edit.

### What the streaming path keeps

Everything. The general loop, the bounded loop and the prefetch scan are unchanged, local-form
data is unchanged, and the dispatch order means a streaming run executes the same instructions
it did (`tst`, `bmi` not taken, `movem`, `bne`, ...) with the same cycle count. Only its code
ADDRESSES move (the new arm sits in the same procs).

### What the plain loop gives up, and where it went

The direct loop's DEBUG per-word bound check (`global < pool tiles`) is gone from the plain
path: a per-word DEBUG check would hand back most of the DEBUG gain the owner flies with. It moves
to build time, where it is stronger: `verify_level_bin.py` (run by the re-bake and by the
canonical build's drift check) refuses a physical-form tree unless every map is the pool-slot
identity, every word's index is a real pool slot, every blank word is `$0000`, and the pool fits
`PAGE_FRAMES`. At runtime the audit still catches a word naming an unassigned frame.

## Rejected

- **Bake global words, keep the per-section maps, trust the build-time residency guess.** Wrong
  on the STRESS_EVICT shape (local maps applied to global words = the stand-in's wrong art), and
  wrong again the day an allocator change breaks the identity latch.
- **Translate once at block decode instead of at copy** (a pass over the 256 staged words after
  `TileCache_DecompressBlock`). Raw-direct blocks are staged zero-copy from ROM
  (`.raw_direct`), so there is no RAM copy to translate; it would re-introduce the copy F-3
  removed, and still pay per decoded block.
- **A second latch byte** (`PageCache_Plain_Copy`) beside `Direct_Map`. Two bytes that must
  agree is one more invariant; a third value of the existing latch cannot disagree with itself,
  and every existing reader tests it by sign or by zero (audit, AllocFrame, EndBoundedRegime).
- **Delete the translating direct loop.** Still live: an unbaked resident act (any act
  built by a tool that does not emit physical form) and the resident clip under a future
  generator both take it, and it is the loop physical-form data falls back to if a latch changes.
- **Unrolled / `move.l` plain loops.** A further ~7 cycles/word on Seq and ~18 on Col is
  available (long pairs; a Duff-style `move.w d16(a0),d16(a1)` column). Not taken: the survey
  priced the simple loop, and the gain is second-order next to removing the ~97-cycle translate.
  Booked as an open item, not built.

## Cost

- RAM: 0 bytes (a new value of an existing byte).
- ROM, engine: two short loops and a changed dispatch (measured at landing, all shapes).
- ROM, OJZ data: the local maps go from 8 distinct tables (3,030 bytes) to one identity table
  (612 entries, 1,224 bytes). The block streams change (global indices, zeroed blanks); their
  S4LZ size is measured at the re-bake and reported, not predicted.
- Build: none measurable (the bake already computes `canon_to_pool`).

## Verification plan (stated before building)

- Nametable identity: before/after ROMs, canonical OJZ, several stop points along the survey fly
  legs, matched by logic tick and camera position; compare the VRAM Plane A and Plane B
  nametables and `Tile_Cache_Nametable`. A screenshot is not a witness.
- Lag: the survey harness, same legs, before/after, canonical DEBUG + release, and the clip.
- DEBUG audit clean across the legs (a raise would halt the leg).
- The new verify rule red-first, mutation on disk, wired into `verify_level_bin.py`'s main.

## Results (measured 2026-09-26, rebased on origin/master `4cd6d7bc`)

Built with `TMPDIR` on disk (`/tmp` was over its quota tonight and failed pytest writes with
EDQUOT; the first baseline DEBUG build's failure was that, not code). Lag counts are
deterministic headless counts; loadavg 6 to 15 during the runs changes wall-clock only.

### ROMs (CRC32 / bytes)

| shape | before (`4cd6d7bc`) | after (parcel tip) |
|---|---|---|
| `s4.bin` | `f4a0adac` / 828,952 | `e97424e6` / 828,874 |
| `s4.debug.bin` | `d91dc2c6` / 855,969 | `c32e27dc` / 855,893 |

`EndOfRom` is `$BF476` in both. The act data itself shrank 10,874 bytes
(`OJZ_Sec_LocalMaps` moved `$2448C` -> `$21A12`): 9 local-map tables (3,030 B embedded) became
one identity table (1,224 B), and the section block blobs went 52,934 -> 42,582 B (blank words
now `$0000`, globals instead of locals). The saving is absorbed before a later fixed-address
placement; which one was not traced. The file-size change is the deb2 appendix.

### The picture: nametable identity (`nt_witness.py`, DEBUG, canonical OJZ act 1)

Three fly legs (right, down, diagonal), 15 stop points each (flown ticks
20..200 step 20, then 240..400 step 40), 45 points total. At each point the input is released
and 30 frames run, then VRAM Plane A, Plane B and RAM `Tile_Cache_Nametable` are dumped. Points
are matched by flown ticks AND camera position (all 45 matched).

- before `$FF` (RESIDENT) vs after `$80` (PLAIN): **45 of 45 points identical** in Plane B, in
  `Tile_Cache_Nametable` (the copy's own output, 9,600 bytes) and in Plane A's visible
  window (41 x 29 cells). 29 points hold content; 16 are all-blank windows (they witness nothing
  and are counted as such).
- Plane A's OFF-SCREEN cells differ at 2 points (10 and 62 cells, diagonal t=120 and t=280).
  That is lag-timing residue (which strips got drawn on the way), not the copy: a **timing-only
  control** (the baseline ROM with `Canopy_Probe` stubbed, identical copy code) reproduces the
  same class (44 off-screen cells at t=280) against the baseline, with visible window and tile
  cache identical.
- **Negative control**: the survey's stand-in plain copy (untranslated local words) on the same
  baseline is DIFFERENT at 33 of 45 points (e.g. t=20: 541 visible cells, 1,876 tile-cache
  words), so the witness can see the failure the stand-in had.
- Release has no free flight, so the witness ran on DEBUG only. The copy code is shared by both
  shapes; release differs only in the DEBUG-only blocks.
- The DEBUG `PageCache_Audit` (now sliced, from master) ran through every leg without a raise:
  every leg reached the same end camera on both ROMs.

### Lag, survey legs (`lag / video frames in motion`), before -> after

| leg | before `d91dc2c6` / `f4a0adac` | after `c32e27dc` / `e97424e6` |
|---|---|---|
| DEBUG fly right | 0/358 | 0/358 |
| DEBUG fly down | 0/363 | 0/363 |
| DEBUG fly diagonal | **43/406** | **14/377** |
| DEBUG physics run | 17/460 (stuck x 1080) | 7/335 (stuck x 1080) |
| DEBUG spindash | 40/1,203 | 5/1,174 |
| release physics run | 49/1,751 | 3/1,295 |
| release spindash | 20/1,182 | 1/1,169 |

Only the fly legs compare like for like (the camera path is fixed by the input). The physics
and spindash legs schedule input per video frame, so a lag change changes the player's path;
they all reached the same end camera, but their before/after is indicative, not a measurement
of the same path.
