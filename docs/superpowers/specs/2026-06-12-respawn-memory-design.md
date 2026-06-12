# Respawn Memory (§4.9.4) — Design

**Date:** 2026-06-12
**Status:** Approved (user pre-authorized overnight design decisions 2026-06-11; review on wake)
**Closes:** DEFERRED_WORK "§4.9.4 Rolling 4-Slot State Tracking (Respawn Memory)"

## Problem

Collected/killed state lives in the 3×3 `Ring_Collected_Window` keyed by section id.
When the camera travels far enough that a section leaves the 3×3 neighborhood,
`Collected_UpdateCenter` evicts its slot — collected rings resurrect and killed
badniks come back on a far return. Classic Sonic (S3K) avoids this with a
whole-level respawn table (RAM scales with level size); this engine's philosophy
is bounded RAM, so the fix is a rolling park buffer.

## Design

**Park buffer:** `Ring_Collected_Park` — `COLLECTED_PARK_SLOTS = 4` entries of
33 bytes (1 section-id byte + 16 collected-bitmask bytes + 16 killed-bitmask
bytes) = 132 bytes + index byte + pad = 134 bytes RAM. A rolling write index (`Collected_Park_Next`, byte)
selects the slot to overwrite when parking a new section (oldest-first rollover).

**Park on evict:** in `Collected_UpdateCenter`'s evict path, before stamping
`COLLECTED_EMPTY_TAG`: if the evicted slot has ANY nonzero bitmask bit, park it —
(a) if the park already holds this section id, reuse that park slot; (b) else
write at `Collected_Park_Next` and advance it (mod slots). Pristine sections
(all-zero masks) are NOT parked — restoring nothing equals default state, so
parking them would only waste park capacity.

**Restore on claim:** in `Collected_ClaimSlot`'s claim path, after initializing
the fresh slot: search the park for the section id; on hit, copy both masks back
and free the park entry (stamp its id `COLLECTED_EMPTY_TAG`).

**Init:** `Collected_Init` clears the park (all ids → `COLLECTED_EMPTY_TAG`,
`Collected_Park_Next` → 0).

**Capacity semantics:** 3×3 window (9) + park (4) = 13 sections of remembered
state. For OJZ's 3×3 act this covers the entire act — zero resurrection. Larger
acts degrade gracefully to classic behavior at very long range (oldest parked
state rolls off; its entities resurrect — acceptable and classic-consistent).

**DEBUG:** assert no duplicate section ids in the park after a park operation.

**Interactions:** none with the visibility window (the park is keyed by section
id, derivation-agnostic). Loaded bitmasks are NOT parked — they describe live
buffer/SST state, which legitimately resets when a section despawns (parking
them would go stale; see the Task-6 analysis in DEFERRED_WORK history).

## Verification

1. Collect rings in sec0, travel right until sec0 leaves the 3×3 (and its slot
   parks), return → collected rings STAY collected (read the restored bitmask +
   buffer census).
2. Same for a killed object (poke the killed bit via `Killed_MarkObject` path or
   collect via gameplay if collision permits).
3. Pristine-section eviction does not consume park slots (park ids unchanged).
4. Rollover: dirty 5+ sections (collect ≥1 ring in each of 5 sections across the
   act), confirm oldest parked state rolls off and the 4 newest survive.
5. DEBUG assert silent; DEBUG + release builds clean.
6. §4.9 regression spot-check (boot counts, one teleport continuity check).

## Non-goals

Whole-level persistence (SRAM, act restarts), loss-ring scatter state, parking
loaded bitmasks.
