# Object-test scene → DEBUG-only (parcel/objtest-gate) — A/B evidence — 2026-08-05

Owner ruling (2026-08-05): the scene stops shipping in release. Executed as the
"ownership move" variant — no duplicated data, DEBUG shape NOT byte-identical
(the alternative substitute-module split would have authored TestArt twice, the
drift class this repo keeps paying for).

## Ruling correction carried into the change

"Ten test objects" over-counted by two: **TestStatic and TestSolid are shipped
PLAIN level content** (OJZ act1 entity_data places ObjDef_Solid in Sec0/1/2 and
ObjDef_Static in Sec2), and `Map_TestObj` + the `TestArt` blob serve the
RELEASE debug-fly cheat marker and the OJZ init DMA. Those stay unconditional.
Gated: the scene (`object_test_state`), its eight scene-only objects
(test_player/enemy/animated/particle/emitter/parent/stress_emitter/churn), and
`particle_anims` — same registry idiom as `CompressionSelfTest` (no in-file
gate; plain simply never links them).

## Ownership moves

- `TestArt`/`TestArt_Square2`/`TestArt_Ring` + the RingArt embed + drift guard
  + `TEST_ART_LEN` moved object_test_state → **ojz_scroll_test** (its consumer
  in the plain shape); the OJZ-side hand-mirror of TEST_ART_LEN is DELETED
  (the drift risk its comment warned about is gone). object_test_state imports
  the const back cross-module.
- `ObjDef_Enemy`/`ObjDef_Parent` + `ENEMY_PATROL_SPEED` moved
  data/objdefs/test_objects → **object_test_state** (sole consumer). NOTE
  planted at both ends: `ojz_entity_gen.py` maps editor type "enemy" →
  ObjDef_Enemy, so a future shipped level placing an enemy fails the PLAIN
  link loudly — that failure is the prompt to author a real shipping objdef.

## Hand ruling (packing)

The plain removals accumulate to ~0x64A in the object bank + data region and
0x5BC in the post-sound-bank tail — both past the packer's 0x400 ANCHOR_GAP
island margin, so the canonical build refused ("[map.undeclared-island] at
0x112EC"). Per the walk's own doc this is a hand ruling: the frozen provisional
table `golden/offcanonical_sizes/s4.txt` was hand-shifted (bank window −cum,
anchored sound islands untouched, tail −0x5BC) to let the packer reach its
fixpoint; `refreeze` then re-derived every value exactly. First attempt
wrongly shifted the $48000/$58000 anchored islands — the align-32768 drift
guard caught it (the machinery's guards held at every step).

## Results

- Plain: 413344 → **411096 B (−2248)**, exactly the predicted savings; gated
  symbols span-checked ABSENT from s4.lst; ruled-live set present
  (TestStatic_Main, TestSolid_Init, Map_TestObj, ObjDef_Static/Solid, TestArt).
- Debug: 423428 → 423480 (+52, the ownership-move relocations).
- Demo shapes: untouched by construction (engine-only registry filter).

## Verification (oracle, loaded-ROM CRCs byte-verified against fresh builds)

1. **Replay determinism proof on the new DEBUG ROM** (F44EAAF7): breakpoint at
   GameState_OJZScroll_Init, poke Input_Source=1 +
   Replay_Ptr=Replay_OJZ_Fixture+20 (0x5E57C), resume. **Replay_Done = $FF, no
   desync, no error screen** — all 33 curated checkpoints across 2,059 ticks.
   The fixture needed NO re-record: Replay_Hash is address-free by
   construction. The header's `core_hash` field was confirmed to have ZERO
   consumers (runtime and harness) — left as-is, ledgered below.
2. **Plain boot** (84A1EB30): OJZ boots, real Sonic spawns, level renders, and
   the debug-fly marker correctly absent (Cheat_Flags clear in release).

## Ledger

- `ojz_fixture.bin` header `core_hash` (0xb212a404) is consumer-less build
  metadata; it now lags the build identity by two parcels. Either wire a
  consumer (compare at replay arm, fail loud) or re-stamp it at the next
  genuine re-record — do not hand-refresh a field nothing reads.
