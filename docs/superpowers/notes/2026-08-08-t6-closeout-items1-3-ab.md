# A/B evidence — T6 closeout items 1-3 (2026-08-08)

**For sigil provenance chain entry 67.** Three inert-in-shipped-scene engine changes
from the T6 art-streaming review. Net **-56 B**, absorbed at the `org $10000`
object-bank boundary (EndOfRom unchanged both shapes).

## Changes (A -> B)

1. **Delete dead `TileCache_Reinit`** (`engine/level/tile_cache.emp`). Grep-confirmed
   ZERO callers (the proc + its header comment removed; the lone remaining `Reinit`
   mention in `TileCache_WarmupBelowRow`'s Init-only rationale at :696 reworded so the
   deletion orphans nothing). It carried a latent refcount-double-count hazard (its
   `FillAll` re-run bulk-zeroes the nametable, bypassing PatchWord's unref while
   residency persists). Also added a precondition comment on `TileCache_FillAll`
   stating the "all resident pf_refcount == 0" invariant where it lives. **PS class:**
   pure dead-code removal — cannot affect any dispatched path (no caller exists).

2. **Zero-extend hardening** in `PageCache_Publish .not_pinned`
   (`engine/level/page_cache.emp`): `moveq #0,d0` before `move.b d1,d0` feeding
   `LruLinkTail`. **BA-inert:** currently value-range-safe (frame id 0..14, d1 low
   byte only), made structurally safe against a stale upper byte — same class as the
   chain-65 Publish fix. No behavioural change in the shipped scene.

3. **Fold `Page_Queued_Bits` clear into `PageIn_Flush`**
   (`engine/level/page_in.emp`) via eight register-free `clr.l` (preserves the proc's
   `clobbers()` == none; `Page_Queued_Bits` is 32 B / 8 longs, long-aligned).
   `PageCache_Init`'s clear kept (idempotent). **BA-inert in the shipped scene:** today
   `PageCache_Init` is the sole flush caller and always clears the bitset itself right
   after, so end-state is unchanged; the new behaviour (a BARE flush also clears the
   dedupe bits, so a stale queued bit can't block a re-request) has no current caller
   and is the Task-4-anticipated correctness guarantee.

## Bar

- Build-side: edited code builds clean against clean committed HEAD data — no
  `[map.undeclared-island]`, no assembler error, s4lint clean; net -56 B, absorbed at
  `org $10000`, no anchor move, EndOfRom unchanged both shapes. All four canonical
  shapes green; `refreeze --check` + `pins_rs_is_current` + the three native gates.
- Runtime: the controller's oracle boot-verify is the runtime proof (all three are
  inert in the current dispatch, so the shipped scene is expected byte-motion only in
  the engine block).
