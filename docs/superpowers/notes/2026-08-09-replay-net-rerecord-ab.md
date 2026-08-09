# Replay-net re-record (P-2 closure) — evidence note

**Parcel:** `fix/replay-net-rerecord` (aeon + sigil), 2026-08-09.
**Why:** P-2 (wave adjudication, second sitting): both standing replay fixtures
desync on post-P2 master. Root cause confirmed at re-verification: the trap
fires at the FIRST checkpoint (tick 2, expected `0x1D3B09A2` vs actual
`0x1D3B0C2A`, screenshot `p2-desync-baseline.png` in the session scratchpad) —
P2 legitimately changed state inside the curated-hash-covered region
(section-stream/page-cache cells), so every checkpoint of both fixtures was
stale. This desync is ALSO the standing "net bites" proof for the new net's
trap path: same build, same trap, deliberately-stale hashes.

## Recording (runbook per 2026-08-02 evidence note, "The standing runbook")

Recording build: `s4.debug.bin` crc32 `0xAD17FC52` (master 01d9d05 + rulings
doc commit; gameplay core identical to the shipped parcel build — the fixture
region sits after all gameplay content). Oracle instance CRC-matched before
every leg. Anchor: persistent bp `GameState_OJZScroll_Init` ($5E00E) BEFORE
`reload_rom`; poke `Input_Source`=2 at the break; drive inputs; dump
`Replay_Record_Buf`/`Replay_Check_Log` over the aether bus (scripted, CRC
cross-checked against `emulator_memory_hash` — no hand transcription);
`tools/replay_pack.py` pack (selftest PASS first).

- **ojz_fixture.bin** — 1,670 ticks / 27 checkpoints / 272 B. Input timeline
  mirrors the old fixture run-for-run (idle soak, B taps, R scroll w/ C jump,
  spindash charges, L reversal w/ A jump, U look, R tail).
- **ojz_slide_fixture.bin** — 1,942 ticks / 31 checkpoints / 288 B. Mirrors
  the 2026-08-07 slide stream: R across the section-1 boundary, L back
  across, debug-fly B-toggle, D across the section-row boundary (two legs),
  U back across, idle tail. **Entity-window coverage re-proven live**: bp
  `EntityWindow_Slide` fired for all four crossing directions at ticks
  155 (R), 315 (L), 1424 (D), 1493 (U) during a RAM-hosted pre-embed replay.

`core_hash` stamp: `0x45FAD65A` = crc32 of the recording build's ROM bytes
[0, Replay_OJZ_Fixture) — the gameplay core. Note the field is still
consumer-less (2026-08-05 ledger) and the shipped build's own core region
CRCs differently because the folded header checksum changes with fixture
content; the stamp identifies the RECORDING build, same convention as before.

## Verification (embedded fixtures, rebuilt shapes)

Rebuilt all four shapes delete-first; debug `0xD13B9F6A` (427,704 B, +8),
release `0x68541559` (413,723 B). Emulator ROM CRC-matched before each leg.

- **Determinism, standing fixture (DEBUG ×2):** net silent both runs;
  `Replay_Done=$FF` at Logic_Tick 1672 both runs; full-WRAM hash at the
  `Input_Tick` `.end` anchor (PC $257A, stepped from the commit-granularity
  stop) IDENTICAL: crc32 `0x9B3947A1` / fnv1a64 `0xAEC3F9019B5AF5B2`.
- **Determinism, slide fixture (DEBUG ×2):** net silent both runs; done at
  tick 1944 both runs; WRAM crc32 `0xB136E9AE` / fnv `0x0341AE67A46A7605`
  identical.
- **Release shape:** standing fixture replay on `s4.bin` — `Replay_Done=$FF`,
  no error screen, live gameplay after (the crash-report-ab pass criterion).

## Sigil lockstep

Discovered en route: the patch-run batching parcel (aeon eb37f5a/01d9d05)
never ran its sigil ritual — `repin.toml`, `pins.rs` and both
`tile_cache_port.rs` seam tables still named the deleted
`PageCache_PatchWord`. Fixed in the paired sigil branch: roster + seams now
carry `PageCache_PatchRun_Seq`/`_Col`; repin regenerated pins (PatchWord
removed, the two PatchRun pins new, remaining deltas = the batching parcel's
±shifts + this fixture swap's island shift — all traced). Full suite +
refreeze recorded in the sigil branch's commits.

## Oracle tool note

Execution-bp stops land a few instructions EARLY of the armed address at
commit granularity (stopped at `Input_Tick`+36/+46 for a bp at `.end`
$2572) — deterministic per-path, but anchor WRAM compares by stepping to a
fixed PC, not by trusting the stop PC. (Ledgered behavior, same family as
the det-serial commit-granularity note from 2026-08-02.)
