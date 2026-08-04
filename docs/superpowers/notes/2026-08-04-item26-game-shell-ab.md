# Item 26 (game-shell ordering) — oracle A/B evidence

Evidence packet for the `item26-game-shell` provenance chain entry, per
`sigil/crates/sigil-harness/golden/ab/AB_PROTOCOL.md`. Class: **BA**
(behaviour-adjacent) — the sprite-cull margin deliberately changes which objects
register as on-screen near the screen edges, so value-identity is not the bar.
The two Z80-posture changes and the `$8B` gate are value-identical by
construction.

## Builds compared

| side | tree | plain ROM | debug ROM |
|---|---|---|---|
| OLD | `master` @ `5810960` | `crc=e4e55c84` / 413238 | `crc=6ee92ea7` / 423391 |
| NEW | `parcel/item26-game-shell` @ `7660d1f` | `crc=d585979e` / 413246 | `crc=2b9aa464` / 423383 |

The OLD debug `crc=6ee92ea7` reproduces the wave-4 A/B note's NEW-side debug ROM
exactly, so the baseline is confirmed continuous with the previous parcel rather
than assumed.

Third shape built and exercised: `demo` debug (`crc=d4c00097` / 93929), the
`SOUND_DRIVER_ENABLED == 0` build. It is the only shape that compiles the new
`else` arm, which is why it is part of this packet.

## Result 1 — the sound-OFF Z80 bracket, verified at byte level

The defect being fixed is invisible in a sound-on build (the arm compiles out),
so it is verified by disassembling the demo ROM rather than by observation.
`Section_RedrawPlanes` prologue in `demo.debug.bin`:

```
4bf9 00c00004        lea     $C00004,a5          ; VDP_CTRL
4df9 00c00000        lea     $C00000,a6          ; VDP_DATA
40e7                 move.w  sr,-(sp)
46fc 2700            move.w  #$2700,sr
33fc 0100 00a11100   move.w  #$0100,$A11100      ; <- stop_z80, the new else arm
0839 0000 00a11100   btst    #0,$A11100
66f6                 bne.s   -10                 ; bus-grant wait
3abc 8f80            move.w  #$8F80,(a5)         ; storm begins
```

Bus-request writes across the whole routine, scanned for the `$A11100` write
pairs:

```
STOP  @ +0x12
START @ +0x190
```

Exactly one pair, bracketing the entire poke storm. An unbalanced hold here
would wedge the Z80 permanently, so the pairing is the load-bearing check.

## Result 2 — driver state identity (sound ON)

Z80 mailbox/status block `$1F00..$1F13`, both runs, after reset + a 120-frame
right-scroll:

```
OLD  00 00 00 00 01 00 00 00 00 00 00 00 00 00 00 00 5A 00 00 57
NEW  00 00 00 00 01 00 00 00 00 00 00 00 00 00 00 00 5A 00 00 FC
```

Byte-identical across `$1F00..$1F12`: same alive marker (`$5A`), same request
slots, same DMA-window flag. Only `$1F13` (`SND_STAT_TICK`) differs — the
free-running per-frame counter sampled at different wall-clock moments, which is
the tolerance the wave-4 packet documented.

## Result 3 — framebuffer identity under motion

Deterministic scene: reset, then `press(['right'], 300)` — no human input
timing, reproducible from reset as the protocol requires. Captured on both
sides through the same emulator session.

```
9cf6ec8be34ed8f8f0df0f3564ff8428  master_r300.png
9cf6ec8be34ed8f8f0df0f3564ff8428  branch_r300.png
```

**Byte-identical framebuffers.** Captured mid-scroll, not at rest — an at-rest
capture would hide exactly the tearing/pop-in class these changes touch.

This is the expected result rather than a contradiction of the BA class: the
cull margin only changes behaviour for objects within 32 px of a screen edge,
and the OJZ scroll scene has none in that band at this point. It demonstrates
no regression; it does not by itself demonstrate the margin working.

## Result 4 — soak

1300 further frames of continuous right-scroll (300 + 1000) on the NEW debug
ROM: rendering stays coherent (parallax layers, ring row, terrain all intact),
and the 68k stays in the normal main loop — PC in `Process_DMA_Critical`, never
in `ErrorHandlerBlob`. This exercises the section-streaming and
plane-redraw paths the Z80-posture change lives on.

## Observation recorded, NOT fixed here (pre-existing)

`SND_CTRL_DMA_ACTIVE` (`$1F04`) samples as `1` persistently in the OJZ scroll
state, in free-run, on both sides. It is **identical on master**, so it is not
introduced by this parcel and was deliberately left alone.

It is likely benign: the wave-4 A/B ran the `config_a` music shape for 38 s with
100% chip-stream onset identity, which proves the flag does clear in a shape
where the Z80 must fetch banked data. The plausible reading is that the OJZ
state's per-frame VDP work keeps the VBlank flag-bracket window open across most
sample points. Worth a deliberate look during a sound-side parcel; it is out of
scope for a game-shell ordering item, and guessing at it would risk the
already-verified sound path.

## Not covered here

- **The cull margin's positive effect** (an object that used to pop in at the
  screen edge no longer does) is not demonstrated. The OJZ scroll scene has no
  object crossing the leading edge during the fixture, and authoring one would
  change the recorded scene. The change is argued from the geometry: the cull
  box is widened by 32 px on all four sides against a worst-case camera step of
  16 px/frame on both axes, so an object can no longer leave the cull box
  between the cull test and the camera update that follows it.
- **Real-hardware bus behaviour.** The Z80-posture fix is a hardware-class
  correctness item and there is no real hardware in this project; the emulator
  cannot exhibit the bus contention being prevented. Verified structurally
  (byte-level bracket pairing) plus no-regression in emulation.
