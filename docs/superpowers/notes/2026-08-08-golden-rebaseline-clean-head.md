# Golden re-baseline — chain-65 was frozen against a dirty tree (2026-08-08)

**A/B evidence for sigil provenance chain entry 66 (re-baseline, no code change).**

## Why

The chain-65 goldens do not reproduce from committed aeon HEAD. A clean build from
`a1195a5` (the docs-only successors of chain-65's `bb0667c`) with the chain-65 frozen
toolchain diverges from `golden/s4.bin` in 6829 bytes, in a contiguous block from
`0x2624e` (the `HeightMaps` / collision-data region). The committed `heightmaps.bin`
(identical `bb0667c..HEAD`) is **not present anywhere in `golden/s4.bin`** — proof the
chain-65 goldens were captured against an UNCOMMITTED collision/OJZ working-tree state
(a concurrent art/collision session's WIP, present at ~20:45 capture, since reverted).
The chain-65 goldens therefore correspond to no committed aeon state.

## What this entry does

Re-anchors all seven golden shapes to CLEAN committed aeon HEAD. The multi-KB anchor
motion here is the collision/OJZ data drift between the dirty chain-65 capture and the
honest committed tree — it is NOT a code change and must be attributed to this
re-baseline, not to any subsequent parcel. The frozen toolchain is byte-identical to a
fresh build of sigil master (`998b54ca` / `75d73523`), so the captured goldens agree
with the native gates that recompile from source.

## Bar

- A: chain-65 goldens (dirty-tree capture).
- B: rebuilt-from-committed-HEAD goldens, all seven shapes.
- Proof: `refreeze --check` green against the fresh blobs; the strict gate surface
  (`native_full_rom`, `native_offcanonical_full`, `native_offcanonical_rom`,
  `pins_rs_is_current`) green. No aeon code changed in this entry.
