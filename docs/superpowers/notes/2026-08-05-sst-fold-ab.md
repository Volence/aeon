# SST fold (parcel/sst-fold) — A/B evidence — 2026-08-05

Owner-directed (morning follow-up to the overnight run): `frame_off` moves from
its H1 bolt-on position at $50 into the engine block at $2E; the custom window
becomes $30-$4F (32 bytes, `SST_interact` in its tail word $4E — game-usable
30); the record shrinks $52 → $50. "The longer we wait the more there will be
to do."

## What it buys

- −132 bytes of RAM (66 slots × 2); Object_RAM_End falls accordingly.
- The record is long-divisible again: DeleteObject's clear is an exact
  20-longword loop — the "$52 is NOT long-divisible" special case and its
  explicit tail-word clear are deleted.
- Engine fields are one contiguous $00-$2F block; the window is the record
  tail; `interact_off()` returns to `sizeof(Sst) - 2`.

## The replay hash re-cut (the delicate half)

The map's entity span now ENDS at frame_off ($2A..$2E, same four fields), and
the 30-byte window hashes as 7 longs + a NEW word fold at $4C; interact stays
at $4E. Accounting: 64 hashed + 16 excluded = $50, all ensures re-derived.
Because Replay_Hash is a rotate-and-add fold, the WALK change alters checkpoint
values even though the covered state is identical — the fixture's 33 curated
hashes required re-stamping.

**Harvest method (probe ROM, never committed):** the checkpoint `bne .desync`
was flipped to an unconditional branch into a 16-byte logger hand-assembled
over the desync handler's exception blob — every checkpoint appends its
freshly computed hash to the (playback-unused) `Replay_Check_Log` ring and
continues on the normal path. One replay run harvested all 33 hashes (cursor
arithmetic confirmed exactly 33). The first attempt at register-sampling via a
breakpoint at the compare failed: the oracle's async pause SKIDS past the
breakpoint (PC landed mid-next-Replay_Hash with a partial accumulator in d0) —
the in-ROM logger is the reliable pattern; recorded here for next time.

The fixture was re-packed with the SAME raw input stream, SAME ticks
(0..2048 step 64), SAME core_hash (still consumer-less, ledger stands), new
hash values — round-trip decode-verified before writing.

## Verification (oracle; every loaded ROM CRC-verified against its fresh build)

1. Boot on the folded layout: clean (RAM layout changed → runtime-boot rule).
2. C1b cascade re-check on the folded layout: object-test scene reaches the
   30-object clean end state, no trap (the re-cut clear ritual zeroes whole
   slots correctly).
3. **Determinism proof on the FINAL unpatched ROM (debug crc 6C296656):
   Replay_Done = $FF, zero desyncs across all 33 checkpoints / 2059 ticks,**
   final frame byte-identical to the canonical pass capture — the fold is
   behaviorally invisible and the re-stamped fixture is the new truth.

## Toolchain note

Mid-parcel the shared sigil target/ carried a stale mid-lane binary from the
parallel session (it rejected `preserves(sr.mask)` — "expected `)`, found
Dot"); a forced rebuild at sigil HEAD (which ADDED dotted-endpoint support in
its sr-split work) cleared it. The sigil-side `SST_interact` harvest mirror
(`frame_off - 2`, correct only while frame_off was the record tail) is fixed to
`layout.size - 2` in the same parcel.
