# BG-NT-IDENTICAL: the warp leg, run

`c2c90854` landed the BG-NT-IDENTICAL gate for regions part 2 step 2 with **one leg open, and
said so**: the warp leg was attempted, the mailbox flag never cleared, and the run was refused
rather than reported — because Plane B is drawn once and never rebased, so *a warp that never
happened and a warp that changed nothing produce the same bytes.* That is the correct call and
it is why this file can exist at all.

This closes it. The warp happens now, the machine demonstrably travels, and the nametable is
still identical.

## What was run

`tools/bg_nt_gate.py`, landed with this note. Both ROMs, both samples, one boot each:

| | |
|---|---|
| BEFORE | the frozen control `.aeon-bgnt-baseline/before-s4.debug.bin`, 846894 B, md5 `01295a2407078afd9b8a45645e443010` (master `8756007f`, the last code state before step 2) |
| AFTER | `s4.debug.bin` built at `c2c90854`, 846856 B, md5 `317e18245cb1ed9eaf9ffd40dab7fe98` |
| region | `$E000`..`$FFFF`, 8192 B, live out of the VDP |
| samples | frame 120 after boot, then after one DEBUG warp to (4200, 4200) |

```
  before-s4.debug.bin camera (96, 144) -> (4040, 4088) across the warp
  s4.debug.bin        camera (96, 144) -> (4040, 4088) across the warp
  boot         IDENTICAL  (8192 bytes)
  after warp   IDENTICAL  (8192 bytes)
  third leg: AFTER boot picture ==  zone_bg.bin
VERDICT: PASS
```

## The two things that made the warp real

1. **`Warp_Req_Flag` is written BYTE-wide.** `Debug_Warp_Consume` does `tst.b` on it, so the
   word write the earlier attempt used leaves the tested byte at `$00` and the consumer branches
   straight to `.done`. The earlier note diagnosed exactly this and it is the fix.
2. **The ack is not the evidence — the CAMERA is.** A cleared flag says the mailbox was consumed,
   not that the machine went anywhere. The tool reads `Camera_X`/`Camera_Y` either side of the
   warp and **refuses the run** if they agree, so the leg cannot pass by standing still. Both
   ROMs travelled (96,144) → (4040,4088).

## The discriminator was self-tested before the subject was measured

A no-regression gate that has never been shown capable of failing is the vacuous-gate shape
wearing a new costume, so all three verdicts were proved reachable against synthetic grids,
control first:

| input | verdict |
|---|---|
| identical grids | `IDENTICAL` |
| full transpose | `DIFFERS, 4032/4096 cells, 4032 of 4032 mirrored` → **names TRANSPOSE** |
| rows 40-43 replaced | `DIFFERS, 256 cells, 0 of 256 mirrored, rows 40..43 contiguous` → **names STREAMING, refuses transpose** |

The transpose case is precisely the failure step 2 could have shipped: arithmetic that composes
wrong and still assembles. The two failure shapes have opposite remedies, which is why the tool
names which one it found instead of printing "differs".

A short VRAM read raises rather than reporting a small difference. That is not theoretical: a
first hand-transcription of these bytes silently lost a quarter of the buffer, which is why the
capture never passes through a transcription step now.

## What is still NOT covered, so the absence is not read as a pass

- **`Section_RedrawPlanes`' cache-RECOVERY path.** `c2c90854` established by breakpoint that the
  routine is reached at frame 65 — before the capture — so the boot sample covers its ordinary
  path. The recovery path stays booked, exactly as that commit left it. The warp exercises a
  camera jump, not a cache eviction.
- **The release shape.** DEBUG only, both sides.
- **That the picture is RIGHT.** Identical-to-before is the whole assertion.
- **Discrimination from this leg, at this pin.** The warp sample equals the boot sample *within*
  each ROM, so this leg currently re-asks the boot leg's question of a second code path rather
  than asking a new one. It stops being free at step 6, when the wipe makes the two samples
  genuinely different — which is when the gate starts earning the warp.

## Why the tool, and not a procedure

Steps 3 to 6 each claim the picture does not change, and the part-2 spec's step table writes
step 3's check as "same gate as step 2". A recipe in a markdown file gets re-derived slightly
differently each time; this one takes two ROMs and two listings and answers in one line.

```sh
python3 tools/bg_nt_gate.py \
  --before-rom <control>.bin --before-lst <control>.lst \
  --after-rom s4.debug.bin --after-lst s4.debug.lst \
  --blob games/sonic4/data/generated/ojz/act1/zone_bg.bin
```

Exit 0 PASS, 1 FAIL, and it raises rather than passing on a short read, an unmoved camera, or a
server that does not advertise the methods it needs.
