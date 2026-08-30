# Independent verification of `parcel/dplc-entry-recut` (aa872628) — 2026-08-30

Reviewer's re-derivation, not a restatement. Verified on branch `verify/dplc-entry-recut`
= aa872628 + merge of master 6e2495a5 (merge commit 6f1eccd8; the only conflict was
`docs/DEFERRED_WORK.md`, resolved by keeping master's new left-edge-sighting section
followed by the parcel's CLOSED block; the original `## ⚠⚠ NEW ...` heading was dropped,
as the parcel itself replaced it). Uptime at the build start: `12:23:23 up 5 days, 4:12`.

## Verdict: SOUND WITH RIDERS

Every numeric claim in the commit message reproduces on the merged tree; the riders are
provenance (assembler revision banner) and one "before" figure that is base-dependent.

## Builds (canonical, never FAST=1) — all four exit 0

| shape | exit | pytest lane | ROM | vs main-checkout master build |
|---|---|---|---|---|
| `./build.sh` | 0 | sweeping 58 files; 1801 passed, 6 skipped, 58 subtests | `s4.bin` 719,387 B | same size; 85,490 bytes differ from offset 399 |
| `DEBUG=1 ./build.sh` | 0 | 58 files; 1801 passed, 6 skipped | `s4.debug.bin` 736,391 B | same size; 85,490 bytes differ from offset 399 |
| `./build.sh demo` | 0 | 58 files; 1802 passed, 5 skipped | `demo.bin` 96,476 B | byte-identical |
| `DEBUG=1 ./build.sh demo` | 0 | 58 files; 1802 passed, 5 skipped | `demo.debug.bin` 101,359 B | byte-identical |

Assembler: `SIGIL_BUILD`/`SIGIL_EMIT` = `/home/volence/sonic_hacks/sigil/target/release/{sigil,emit_sound_blob}`
(coordinator-confirmed). Every shape printed
`## WARNING: THE ASSEMBLER MAY NOT MATCH ITS SOURCE (revision)` — binary 8951389a, sigil HEAD
db0a28d8. The commits after 8951389a touch only `crates/sigil-harness/src/test_support.rs`
(two helpers + a test) and `docs/OVERSEER.md`; `sigil-cli` uses `sigil_harness::native` and
`contract_baseline`, not `test_support`. That is an argument from the diff, not a byte
measurement.

Master controls are the main checkout's builds (`/home/volence/sonic_hacks/aeon/s4*.bin`,
`demo*.bin`, timestamps 11:58-12:04 today, sizes matching the brief). I did not build master.

## Peak entries / slots, derived with my own parser

Parser transcribed from `engine/objects/dplc.emp:4-6` (offset table, count word, entry =
`[count-1:4][tile_start:12]`). Split rule from `engine/system/dma_queue.emp:144-150`:
`lsr.l #1,d1` then `sub.w d3,d0 / sub.w d1,d0 / blo .split` — a 16-bit borrow on the word
sum, i.e. `(src mod 0x20000) + len > 0x20000` costs 2 slots. Bases from the `.lst` files.

| blob | base | peak entries (frames) | peak slots (frames) | straddles |
|---|---|---|---|---|
| master (2,368 B), release 0x72530 | | 13 ($C1 $C8) | 13 ($C1 $C8) | $71 |
| master, DEBUG 0x72DF0 | | 13 | 13 | $6B |
| branch (2,244 B), release 0x724B4 | | 10 ($1E $8B $90 $C2 $C7 $DF) | 10 (same six) | $71 |
| branch, DEBUG 0x72D74 | | 10 | 10 | $6C |

The branch's `tools/dplc_straddle.py --gate` reports the identical peaks, frames, straddles
and bar (10 = 12 − 2, from the real assert) on both listings; direct runs exit 0. Agreement.

Deviation from the commit: "the DEBUG shape had no straddle before" was true at base
1cbb6660, but at today's master DEBUG base (0x72DF0) the OLD blob already straddles at $6B.
Base-dependent, harmless (1 → 2 slots on a light frame), does not affect the verdict.

## Producer reproduction

```
python3 tools/dedup_art.py art/uncompressed/characters/sonic.bin games/sonic4/data/dplc/sonic.bin \
    --out-art A --out-dplc D --entry-cap 10
  -> "entry cap 10: peak entries 13 -> 10, 6 frame(s) re-cut: $0E, $BE, $BF, $C1, $C4, $C8"
cmp A art/optimized/characters/sonic.bin            IDENTICAL (101,056 B)
cmp D games/sonic4/data/dplc/optimized/sonic.bin    IDENTICAL (2,244 B)
same command WITHOUT --entry-cap:
cmp A' <master art blob>                            IDENTICAL (97,472 B)
cmp D' <master dplc blob>                           IDENTICAL (2,368 B)
```

Independent frame diff old→new: exactly $0E $BE $BF $C1 $C4 $C8 changed (12/11/11/13/12/13
entries → 2/2/2/2/1/1; 29/17/17/17/16/16 tiles). New art = old art + 3,584 B (112 tiles)
appended, prefix byte-identical. All 224 frames load identical tile bytes old-vs-new AND
raw-vs-new. Max entry reach 3158 = sheet tiles. Raw sheet peak is 16 entries.
`git diff master..HEAD --stat -- games/sonic4/data/mappings games/sonic4/data/sprites` is empty.

## Invariant-8 audit of `tools/test_dplc_recut.py`

- Red-first: flipped byte 0x100 of the committed DPLC (05→04): `4 failed, 6 passed`, message
  "games/sonic4/data/dplc/optimized/sonic.bin is not what `dedup_art.py --entry-cap 10` emits
  from the uncompressed sheet (produced 2244 B, committed 2244 B). Regenerate it rather than
  editing it." Restored with `git checkout --`; status clean; blob == producer output; 10 passed.
- Wired: `build.sh` +9 lines print `sweeping N test file(s)`; the lane collected 58 files and
  ran in all four shapes (build-fatal on failure).
- Cap derived: `wall()` regex-reads `DMA_IMPORTANT_SLOTS` from `engine/system/constants.emp`
  and `DPLC_ENTRY_RESERVE` from `engine/objects/dplc.emp`; no literal 10 in the file.
  (`tools/test_sprite_tilt.py` still carries literals 12/2, pinned by its own
  `test_constants_still_match_their_source`.)
- Non-vacuity: with `entry_cap` monkeypatched to a no-op, 3 tests fail
  (`only_frames_over_the_wall_were_re_cut`, both byte-identity tests).
  `test_the_entry_cap_is_load_bearing` itself passes in that probe — it guards the
  other direction (deduped sheet already fitting), and the byte-identity tests are what
  catch a no-op cap. The commit's phrasing "its load-bearing test asserts the cap is NOT
  vacuous" is accurate only for the suite as a whole.

## Size / room (read from `bganim_room` in the build logs)

- release: `Art_Sonic 0x724B4 + 101056 = 0x8AF74; anchor 0x90000; ROM room 20620 B free`
- DEBUG:   `Art_Sonic 0x72D74 + 101056 = 0x8B834; anchor 0x90000; ROM room 18380 B free`
- ROM files did not grow (719,387 / 736,391 = master's sizes on the merged tree; the
  commit's 719,355 / 736,357 are the pre-step-6 base). Commit said DEBUG room 18,428 B;
  merged tree reads 18,380 B (−48 B from step 6's growth), release 20,620 B.

## Not measured

Runtime behaviour (queue occupancy on $0E/$C4, page-in landing) — no emulator was used;
TAGGED for the controller. Master's own demo builds were not rebuilt here.
