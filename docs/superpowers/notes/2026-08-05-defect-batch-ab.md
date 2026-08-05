# Defect batch (parcel/defect-batch-8) — A/B evidence — 2026-08-05

Eight defects: the reconciliation's five NEW findings + children C1b/C1c/C1d.
Scoped by five parallel read-only agents; three design calls made under the
owner's overnight delegation (each flagged in the morning summary):

- **C1b → cascade-in-DeleteObject** (not epoch byte): SST fully packed (epoch =
  $52→$54 growth, +132 B RAM, replay re-cut, ~32cy/child/frame in Draw_Sprite);
  the walk is provably complete (every parent_ptr writer chain-links; only
  InitObjectRAM bypasses DeleteObject and kills both sides). Subsumes NEW-2.
- **NEW-5 → widen to 64 rows** (against the owner's initial lean to
  declare-32+guard): the shipped OJZ override carries 2048 nonzero words in
  rows 32-63 and the shipped v_factor_bg wrap puts those rows on screen at
  spawn — the guard would fail on day-one content. Widening is free steady-state
  (Draw_BG_TileColumn: zero callers).
- **NEW-1 → runtime $8F02 re-assert** (not a declared context): contexts prove
  pairing not values (spec §9), no inferred VDP net forces bracket use, IRQ is
  not a CFG edge. Ledgered in DEFERRED_WORK with the dead ends pinned.

## Build identity

Baseline (master 3963e65): plain 413310 B crc 5765985a · debug 423451 B crc ba9bbfe5
Batch head (bf21722):     plain 413344 B crc fdcb4dff · debug 423428 B crc b0befdd6
Net: plain +34 B, debug −23 B (C1d's assert+blob deletion outweighs additions).
Warnings: plain 22 / debug 63 — at-or-below baseline (debug −1: the dissolved
C1d assert's sr-undeclared).

## In-emulator verification (oracle, s4.debug.bin, loaded-ROM CRC byte-verified
0xB0BEFDD6 == fresh build before any probing)

1. **C1c band inheritance** — object-test scene (Game_State poke, paused-write):
   all 16 effect-pool TestParticles read render_flags $C9 → band 6 (band-5
   emitter parent + band-6 particle; the union bug rendered 7). Stress emitters
   $E9 → band 7 (their own), solids/enemies unchanged.
2. **C1b cascade** — fresh scene init: 3 TestParents (slots 15-17) + 9 linked
   TestChildParts (band 3, parent_ptrs $8F96/$8FE8/$903A) observed live at
   t≈+1s; at t≈+5s (past the 180-frame life) ALL parent and child slots
   wholesale-zeroed, zero orphan $119C code words in the full 40-slot dump,
   Dynamic_Live_Count 42→30 (the documented clean end state). This exercises
   the NEW path: TestParent_Main now tail-calls DeleteObject alone — the
   internal cascade freed the children.
3. **NEW-5 boot + motion** — OJZ boots clean; the spawn view shows plane rows
   56-63 (vscroll wrap) rendering real art via the widened RedrawPlanes;
   4 s of held-right scroll shows coherent layers, no torn columns.

NEW-1/NEW-3 are lag-frame-only paths: closed by construction (re-assert /
emit bracket), not exhibited live — both are one-instruction guards whose
absence, not presence, is the untestable state.

## Poke recipe notes (for future sessions)

- Game_State ($FF8008) pokes only take effect written PAUSED (pause → write →
  resume); a live-running write was silently lost twice.
- 68k RAM writes need the 0x prefix on addresses ($FFFFxxxx symbol forms must
  be given as 0xFFxxxx bus addresses).
- oracle object_list class names were garbage against this ROM (symbol table
  stayed at 648 entries across load_symbols) — RAM SST dumps are the ground
  truth; parse code_addr words against the .lst.
