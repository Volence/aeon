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

## Verification

- `python3 -m pytest tools/ -q` — the four `test_stress_uniquify_*` green (N=2600 →
  41 pages, local tables valid, deterministic).
- `refreeze --check` OK at chain 76 before; fresh canonical rebuilds match the
  committed goldens (878ee831 confirmed byte-neutral) so this refreeze isolates the
  orphan-audit delta.
- Oracle soak observation of the audit firing/not-firing is controller-only.
