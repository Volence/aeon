# A/B — P2c Task 11: PageCache_Audit orphan-frame check (chain 77)

## Parcel

`art-streaming-p2c-t11-orphan-audit` — extends the DEBUG-only `PageCache_Audit`
(engine/level/page_cache.emp) with the T7-review **NIT-2** orphan-frame check: after
the refcount / LRU / mapping-bijectivity passes, walk all `PAGE_FRAMES` and
`raise_error` on any frame that is **assigned** (`pf_page != $FFFF`) + **refcount 0** +
**not in the LRU** + **not pinned** + **not the live page-in handoff frame**
(`PageIn_Cur_Frame`). Such a frame has leaked: neither the free list nor the LRU can
ever hand it back to `PageCache_AllocFrame`, a class the existing checks all pass.

The in-flight *decode* frame is UNASSIGNED (`pf_page $FFFF`, soak-fix chain 72), so the
`pf_page` skip already covers it; the one legitimate assigned/rc0/detached transient —
a demand page published but not yet Ref'd by its resuming fill — is `PageIn_Cur_Frame`,
excluded explicitly (NIT-2's "not the in-flight frame").

## Byte impact (the only golden movement)

DEBUG-only: the check sits inside `if DEBUG == 1`, so it moves **only** the DEBUG-shape
goldens; the release goldens are byte-identical.

| shape        | before (size)     | after (size)  | Δ    |
|--------------|-------------------|---------------|------|
| `s4.bin`     | d9e6a30a / 414325 | **unchanged** | 0    |
| `s4.debug.bin` | d21abd9a / 427852 | 427910      | +58  |

- `s4.bin` rebuilt byte-identical (md5 d9e6a30a == committed golden) — proof the check
  never reaches a release shape.
- `s4.debug.bin` grows +58 B (the orphan loop + `raise_error` string); the same delta
  lands in every DEBUG shape carrying `page_cache` (config_a, demo_debug).

## Rides with (golden-neutral, verified separately)

- **`act_descriptor.emp` guard relaxation** (plan Task 5 §2e completion): the stale
  identity-residency `OJZ_ACT_POOL_TILES <= POOL_TILE_CEILING` guard becomes the
  residency page-table cap `OJZ_ACT_POOL_PAGES <= PAGE_TABLE_MAX` (page-in DMAs to an
  allocated frame, so VRAM is frame-bounded regardless of pool size). **Byte-neutral**:
  proven by rebuilding both canonical shapes to identical md5s (d9e6a30a / d21abd9a)
  before this audit change.
- **`--stress-uniquify N` fixture + STRESS_ART build plumbing** (tools/build.sh): a
  throwaway off-canonical DEV shape, no golden, generator flag defaults off — zero
  canonical byte impact.

## Fixture build shape (stress-art) — the fixture_placement waiver PAIR

The `STRESS_ART=1` build (`s4.stressart.bin`, sonic4 DEBUG + uniquified 41-page pool) is an
UNFROZEN throwaway — no golden, no provenance, same class as `s4.stress.bin`. It uses a
FIXTURE-SCOPED derived placement (sigil `--stress-art` -> `stress_art_profile.fixture_placement`),
authorized by the coordinator (ruling B, 2026-08-09). `fixture_placement` gates ONE flag over a
waiver PAIR, both refused for any shipped shape (the CLI rejects `--stress-art` with any
shipped-shape selector; `fixture_placement` is false in every shipped profile; the
`shipped_shapes` gate stays byte-identical):

1. **Packing-guard waiver** (`packed_true_bases`): pack greedily from measured sizes with the
   frozen provisional-base overrun guard and the island-reclassification guard waived; the
   round-0 measure scratch-pins position-independent (pure-DATA) sections so the inflated pool
   never forces the CODE region apart (cross-section conditional branches keep +/-32 KB reach).
2. **Relocation + map-order waiver** (`relocate_fixture_pool` + anchor-aware island gating):
   the stress-GROWABLE OJZ generated sections — the act art POOL, the BLOCK blobs, and the
   local->global MAPS (all reached only through `extern` manifest/descriptor pointers, i.e.
   position-independent by the residency design's own contract) — are relocated as a group to
   just before the fault-handler island. This keeps the 116 KB `collision_data` at its
   canonical position so OJZ's HARD DAC anchor at $48000 keeps its island gap. The relocated
   order is fed to BOTH the packer AND `validate_placement`, and the stay-behind sections'
   spurious prov-gap islands are suppressed unless the base is a DECLARED org anchor — so the
   subsequence / undeclared-island checks pass against the fixture's ACTUAL order, not a blanket
   bypass.

**Invariants verified in `s4.stressart.lst`:** all 41 pages resolve (`OJZ_Act_Pool_Page0` @
$5E796 relocated past the sound banks, `Page40` @ $6B50F, `OJZ_Act_Pool_PageTable` @ $6B884);
org anchors HELD (ObjCodeBase $10000, Dac_Temp_Blip $48000, SoundTablesZ80 LMA $58000); and
`error_handler` remains the LAST byte-emitting section (`BusError` $7C960 / `ErrorHandlerBlob`
$7CABA / `EndOfRom` $7DA10 all after the relocated pool) — the MDDBG deb2 locator invariant
holds in the fixture. Any real anchor overrun still fails loud at `resolve_layout`.

## Fixture clones are PARENT-MATCHED — the visual gate is EXACT from this version on

`--stress-uniquify`'s re-pointing is PARENT-MATCHED (fixed 2026-08-09 after a controller
visual review caught full texture swaps): a block reference to tile T is only ever re-pointed
at a clone OF T — a single-row scratch perturbation of the exact tile that position renders,
with the source flip/pal/pri preserved. A bark cell stays bark, a vine-swag cell stays swag;
the fixture looks like clean OJZ with faint scratches only. (The first cut assigned each
position an arbitrary clone, baking cross-texture swaps that made "wrong-looking"
indistinguishable from actually-wrong.)

Verified end-to-end on REAL OJZ data (`scratchpad/verify_parent_match.py`): of 44,970 non-blank
positions, 1,988 are re-pointed, **0 cross-texture swaps** (every re-pointed tile differs from
its non-stress tile in exactly ONE 8px row) and **0 flip/pal/pri mismatches** — including the
flip-canonicalized references the donor-free pytest can't exercise. The inline pytest
`test_stress_uniquify_parent_matched` asserts the same invariant on fabricated data.

**Gate consequence:** the acceptance matrix's zero-wrong-tiles visual gate is EXACT from this
fixture version on — any full texture swap is a real bug forever after. Earlier acceptance
runs' VISUAL evidence carries the parent-mismatch caveat (the swaps were data-faithful, not
streaming bugs). The non-visual gates (lag / audits / counters / camera-clamp / idle-floor)
were never affected by the mismatch.

This is a generator+fixture change only (`tools/ojz_strip_gen.py`): NO engine bytes, so the
canonical goldens are unchanged (`s4.bin` stays f8561c7c) and no parcel ritual applies; only
the throwaway `s4.stressart.bin` moves (parent-matched data: md5 fd70a058, 41 pages, all
placement invariants held).

## Verification

- `python3 -m pytest tools/ -q` — the four `test_stress_uniquify_*` green (N=2600 →
  41 pages, local tables valid, deterministic).
- `refreeze --check` OK at chain 76 before; fresh canonical rebuilds match the
  committed goldens (878ee831 confirmed byte-neutral) so this refreeze isolates the
  orphan-audit delta.
- Oracle soak observation of the audit firing/not-firing is controller-only.
