# Overnight summary — 2026-08-19 (aeon overseer session)

Everything below is MERGED AND PUSHED on both masters unless marked otherwise. Sigil
provenance chain 134 → 141. Master state at writing: aeon `26f965c4`, sigil `7a6111c5` —
aeon pytest **1074 passed / 2 skipped**, effects gates **22/22 exit 0**, four shapes green,
sigil **3731 passed / 2 failed** (the booked `ojz_run_b` pair only). Every byte-moving parcel
landed as an aeon+sigil pair with its own provenance entry and A/B evidence.

## What merged, in order

1. **Item 1b — the HBlank window sweep** (`3a33ea8a`). Clean N ∈ [16,21], **centre 18**;
   `RASTER_STREAM_WORD_CYC = 30` confirmed against the emulator for the first time. The §2
   arithmetic error found and named (84-cyc burst term → 60-cyc first-to-last span). The
   spec's literal fixture was vacuous for two measured reasons (header mask, unsampled CRAM
   address) — both fixed with evidence, spec annotated. A1 determinism PASSED across three
   fresh server processes — the criterion three prior capture protocols failed.
   **Instrument finding:** `emulator/scanlines` resolves to ONE SCANLINE (oracle-core L1);
   the window was measured from line-boundary crossings instead of flip-x. oracle-next
   settled the row convention by construction (write during line N → first visible row N+1),
   pinned at empyrean `112d683`; their A2 restated per our recommendation.
2. **Item 1c — the spin solver** (`4143b58c` ↔ sigil `6882fc09`, chain 135). The three
   hand-fitted spin anchors DELETED; one measured constant (`RASTER_HBLANK_END_CYC = 351`) +
   a position-aware comptime solver + a derived-margin landing ensure. Retired values
   recovered as special cases (reg+region stays 4; restore's 13 = the window's far edge).
   ROM delta: exactly 4 bytes. The leading-stream-op defect item 1 existed for is FIXED.
3. **Scanline P2 Phase 1** (`78d96448` ↔ sigil `5baadc82`, chain 136). Tasks 6–9b:
   bracketing labels, CAP-mask elision ×4, demo witness, span gates, tagging check. sonic4
   code byte-identical throughout (per-proc reconciliation); demo −994 code bytes. The
   **sigil port-harness Game-binding fix** rode in the same pair: Phase 1's new cross-seam
   `Game.SCANLINE_CAPS` refs broke 9 port tests — caught by the full-suite ritual before
   push, fixed by extending the camera_port idiom with values PARSED from aeon source.
4. **CAP_TRANSITIONS** (`14c20b6b`, chain 137). Unblocked by Phase 1's re-derived demo
   frozen tables (Level_LoadArt 0x6430→0x6050). demo −48 more bytes; the gate row flipped
   informational→real differential with zero gate edits.
5. **Palette lsl→add + tail calls** (`96ee84cc`, chain 138). Tier 3 #4 + #5's palette half.
   16 in-place bytes, zero symbol movement, ab_runner ALL EQUAL ×3.
6. **Raster stream word** (`1dcc4440`, chain 139). Tier 3 #1: 30→**26** cyc (the booked 16
   dropped the `dbf`). Sweep-verified boundary asymmetry; solver re-derived every spin;
   centre moved 18→19 tracked unprompted.
7. **Variant-mirror gate** (`93ee955f`, zero bytes). Tier 4/B2: `palette.emp`'s
   "build-time checked" claim made TRUE — `palette_variant_gate` drives the real derive
   path against vectors parsed from the mirror's source. Gates 18→19. Finding: the mirror's
   own vectors are G-blind; the 48-entry sweep carries the gate.
8. **Dispatch chain** (`649b4359`, chain 140). Tier 3 #2: a single leading `beq` (the op
   fetch already sets Z — cheaper than the booked tst.w/beq). OP_SET_REG dispatch 80→10;
   F1 −420 = 6×70 exact; sweep predicted −0.8 N, measured −0.833 mean.
9. **Dense-kind hoist + the dense tier's first instrument** (`26f965c4` ↔ sigil `7a6111c5`,
   chain 141). Tier 3 #3 — **the booking was wrong by 6×**: 354→350 cyc/line, because the
   per-line test's cycles were mostly VDP bus-hold (measured both directions). The real
   deliverable is the instrument: fourth ab_runner scene (first dense), FD1/FD2 cost
   fixtures, dense cost term + fits-in-scanline invariant, gates 19→22.

Also landed on master: the helper-closure scanner now skips all dot-dirs (agent worktrees
were failing every main-tree build — found live, fixed red-first); the nightly backstop
builds the demo fixture (its 04:17 run failed correctly when Phase 1's two-fixture gates
found no demo listing — fixed, re-run green 18/22-era gates).

**Runtime witness held all night:** demo boots on oracle-aether to a frame-300 224-row
scanline SHA that stayed IDENTICAL across all six demo-touching parcels
(`a1a3a829acd4…`), while demo lost 1042 code bytes total.

## Findings worth more than the parcels that produced them

- **Nominal 68000 timings over-predict edits near VDP-port writes** (dense-body cycles were
  absorbed by bus-hold). Every remaining raster cycle figure should be measured, not booked.
- **The 1c solver turns re-timing into arithmetic**: two later parcels changed cycle
  constants and every spin re-derived unprompted, verified by sweep both times.
- **The LEAVE schedule carries TWO trailing fires** (~600 cyc/frame) — a rider bigger than
  the parcel that found it; booked, needs its own non-value-identical parcel.

## Open questions that are YOURS (stated, not guessed at)

1. **Tier 3 #6 — SR push/pop in Raster_HInt** (~30 cyc/fire): needs a sigil-side context
   flavour, paired change AND novel mechanism. PARKED per handoff; sign-off needed.
2. **RASTER_CRAM_MAX 3→4**: after #1, the CRAM class fits 4 words with 1.5 iterations of
   slack; the deep class has 2.9 cyc — statistically zero. Proposal + arithmetic booked in
   DEFERRED_WORK; wants a 4-word sweep fixture before any raise. Two decisions, not one.
3. **`ojz_run_b` (queue E)**: still the deliberate design call (relocate BG_LAYOUT_SIZE /
   companion module / LowerOptions.defines). Unblocked nothing tonight; still PARKED.
4. **Residual ±1 HInt-anchor-phase A/B** (oracle-next offers to run it): deferred until
   authored-line art alignment matters — likely first customer is the OJZ showcase effects.

## Remaining queue (was in flight / next when this was written)

Tier 3 #5's raster half (two tail calls) — in flight. Then item C (frame-epoch flag; its
interrupt-priority reasoning needs EMULATOR confirmation as part of the work), the
two-trailing-fires rider, dense `-4(a2)` rider (instrument now exists), EFX-4b, C5
footprint (a wire-format design change — bigger than "filler"), zero-`assert.*`.
