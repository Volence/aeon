# A/B evidence — boot table cursor re-anchored on `boot_tail`

**Parcel:** `boot-cursor-section-seam`
**Class:** BA (behaviour-adjacent / hazard-fix) — with an unusually loud positive half:
the release shape went from rendering NOTHING to rendering the level.
**Date:** 2026-08-14 · oracle (`ORACLE_DETERMINISTIC=1`), the project's standard of evidence.

---

## The defect

`boot.emp` copied the Z80 sound blob with `move.b (a5)+,(a0)+` and then kept walking the
SAME `a5` into `boot_tail`'s data — 4 PSG-silence bytes, then the word/long VDP commands.
But the blob ends a *section*, and the chainer aligns `boot_tail`'s base to the largest
power of two in {16,8,4,2} dividing its frozen provisional pin
(`sigil-harness/src/native.rs::packed_align_of`). A pad therefore opens between
`Z80_Sound_End` and `BootData_PostBlob` whose width is a function of the blob's length.

Measured on oracle, breakpoint at `$engine.boot$EntryPoint$silence_psg` (`$292`, the same
address in both shapes), reading `a5` on the first loop iteration (`d2 == 3`):

| shape | `a5` at `.silence_psg` | `BootData_PostBlob` | pad |
|---|---|---|---|
| DEBUG   | `$1C6C` (= `Z80_Sound_End`) | `$1C70` | **4** |
| RELEASE | `$1BEA` (= `Z80_Sound_End`) | `$1BF0` | **6** |

**Both shapes were misaligned** — each read the zero pad as its PSG-silence bytes. Debug's
4-byte skew was survivable: the words still paired up, so the CRAM-write command completed
and the control-port flip-flop ended CLEAR. Release's 6-byte skew put `$0000` in the
auto-increment slot; the VDP takes `$0000` as a command's FIRST word, which strands the
control-port flip-flop, and from that point **no VDP write in the entire ROM ever landed
again**.

ROM bytes at each shape's cursor (`s4.bin` / `s4.debug.bin`, pre-fix):

```
DEBUG    0x1C6C: 0000  <- a5      RELEASE  0x1BEA: 0000  <- a5
         0x1C6E: 0000                      0x1BEC: 0000
         0x1C70: 9fbf  <- PostBlob         0x1BEE: 0000
         0x1C72: dfff                      0x1BF0: 9fbf  <- PostBlob
         0x1C74: 8f02                      0x1BF2: dfff
         0x1C76: c000                      0x1BF4: 8f02
```

## OLD-side symptom (pre-fix release, `s4.bin` crc `abb6777d`)

Reproduced on a fresh `oracle_gui` process AND via in-process reload A/B:

- Whole screen one flat colour. Confirmed to be the **backdrop**: `emulator_write_cram`
  line 0 index 0 -> red turned the entire raster red, so every pixel was colour index 0.
- **VRAM entirely zeros** after 13,000+ frames — checked `$1000` (tile art), `$B800`
  (sprite table, reg `$05`), `$C000` (plane A, reg `$02`), `$E000` (plane B, reg `$04`).
- **CRAM untouched power-on `$0EEE`** on all four lines.
- Game LOGIC unaffected: player object alive and grounded (`x=256 y=573`, status `0`),
  `Process_DMA_Critical` running, `Palette_Dirty` clearing, queue draining.
- A correctly-formed palette DMA entry was stepped through all four sends
  (`9400 9310 977F 96C1 950B C0000080` — length `$10` words, source `$7FC10B` =
  `Palette_Buffer`, dest CRAM `$0000`); CRAM did not change.
- `Flush_VDP_Shadow` verified EXECUTING (breakpoint `$1C12`, `a1 = $00C00004`,
  `d0 = $8014`, `d1 = $12` = 19 registers) with no effect on the VDP.
- Boot's own "Clear CRAM" loop verified INEFFECTIVE: breakpoint at `$2A0`
  (`.clear_cram`, same address in both shapes), step 70, read CRAM.

## The instrument control (this is what makes the OLD-side claim falsifiable)

Same 70-step boot experiment, same address, both shapes:

| shape | CRAM after boot's clear loop |
|---|---|
| DEBUG   | all `$0000` — the clear WORKED |
| RELEASE | all `$0EEE` — untouched |

And a live register probe: poking VDP shadow reg `$0C` (offset 12, `$FFFF801A`)
`$81 -> $00` (H40 -> H32):

| shape | framebuffer |
|---|---|
| DEBUG   | **256x224** — the register reached the VDP |
| RELEASE | 320x224, zero content — it did not |

The poke was read back from RAM intact in both shapes, so nothing was re-running boot or
re-initialising the shadow (a reset loop is ruled out).

## Not a regression

Built the pre-merge commit `b2bb1c5a` (parent of the blanket-restore merge) in a scratch
worktree: its release ROM (crc `249db4d9`) is equally blank. The defect is **pre-existing**
and was invisible only because all verification has been done on DEBUG shapes.

## NEW-side positive observation

Fix: `boot.emp` re-anchors the cursor with `lea BootData_PostBlob(pc), a5` immediately
before `.silence_psg`, so the walk no longer crosses the section seam. The hazard is gone
**by construction**, not by a guard — which matters because `packed_align_of`'s own doc
comment records that a repin can change a section's alignment quantum with no source
change at all (it happened to the SFX section in `2c49f538`).

| ROM | OLD crc | NEW crc | OLD render | NEW render |
|---|---|---|---|---|
| `s4.bin`        | `abb6777d` | `a6efe203` | blank backdrop | **OJZ renders: art, palette, parallax, Sonic** |
| `demo.bin`      | `db3f9b0f` | `8c6abbfe` | blank backdrop | **white 16x16 box on dark blue** (the spec) |
| `s4.debug.bin`  | `c13412fc` | `3cffc29b` | renders | renders, unchanged at spawn |
| `demo.debug.bin`| `7c39eda5` | `fdda99a7` | renders | renders |

Captures: `FIXED_release.png`, `FIXED_demo_release.png`, `FIXED_s4_debug.png`.

Section-2 navigation in the DEBUG shape shows a heavily recoloured screen; this is NOT a
regression — `Raster_Program` reads `$00012F3A` = `OJZ_TestGradient` there, and section 2
also carries the `OJZ_TestPal` fixture. Both are deliberate test fixtures. Confirmed by
reading the installed program pointer rather than by eye.

## Honest limits of this evidence

- Captures are **not frame-anchored** to a fixed `Frame_Counter`. Oracle screenshots are
  known non-deterministic on press-frames in this project, and the OLD/NEW difference here
  is categorical (nothing renders vs. the level renders), not a pixel-level delta, so the
  PS-style byte-identical-region bar does not apply and was not attempted.
- The DEBUG shape's boot was ALSO misaligned before this fix (4-byte pad). The fix
  therefore changes DEBUG boot behaviour too: the PSG now actually receives its
  `$9F/$BF/$DF/$FF` silence bytes instead of four zero pad bytes, and the auto-increment
  write now lands on reg `$0F` instead of reg `$1F`. Both are corrections; neither was
  separately instrumented beyond "debug still renders identically at spawn".
- No real hardware. Oracle is Exodus-derived; the control-port flip-flop semantics
  described above are as oracle models them.
