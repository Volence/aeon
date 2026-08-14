# Blanket VDP register restore — the composability unlock

**Date:** 2026-08-14 · **Emulator:** oracle (Exodus-derived) · **Shapes:** plain + `DEBUG=1`, both games
**Reference for every A/B below:** aeon master `b2bb1c5a`, `crc=475fa367` (sonic4 debug)

## What changed

`Flush_VDP_Shadow` wrote only registers whose bit was set in `VDP_Dirty_Mask`. It now writes all
19 shadow registers unconditionally, every VBlank. Three consequences:

1. `VDP_Dirty_Mask` had **zero readers** left, so it is deleted outright — the RAM field plus all
   11 `ori.l` writer sites across `parallax`, `hblank`, `boot`, `demo_state`, `object_test_state`,
   `ojz_scroll_test`.
2. The raster system's per-program **init words** — a frame-top reset word paired with every
   mid-frame `set_reg` — are deleted. The unconditional flush already restores every register at
   frame top, for free.
3. `Set_VDP_Reg` replaces the capability the init words carried: a section that wants a register
   changed *persistently* (e.g. Shadow/Highlight globally on) writes the shadow byte and the flush
   delivers it.

## Why it matters

This parcel is **structural, not performance**. Before it, two independently-authored effect
presets touching the same VDP register had to agree on a reset value or the build hard-failed
(`prog_init`'s disagreeing-resets `ensure`, added earlier the same day as a wrong-pixel fix). That
`ensure` was the composability ceiling. After it, they simply compose.

It also closes a documented latent hazard rather than merely avoiding it. `raster_dsl.emp` used to
warn that `set_reg` bypassing the shadow was "harmless today ... and becomes real the moment
someone `set_reg`s a register that IS shadowed and dirtied: the flush would override this op's
frame-top reset ... and the shadow's idea of the register would permanently diverge from the
hardware's." With the flush unconditional the shadow is authoritative and that divergence is
**unrepresentable**, not merely unlikely.

## ROMs

| shape | before (`b2bb1c5a`) | after |
|---|---|---|
| sonic4 debug | `crc=475fa367 len=711410` | `crc=3278caf9 len=711399` |
| sonic4 plain | `crc=8b3dc951 len=696960` | `crc=532b6e49 len=696855` |
| demo debug | — | `crc=88215437 len=99884` |
| demo plain | — | `crc=4357b3a7 len=95616` |

**Both games are built in both shapes deliberately.** `section.emp`'s z80 bracket is
`with z80_stopped if SOUND_DRIVER_ENABLED == 0`, so with sound ON the region is never planted.
A sonic4-only check passed a tree in this parcel that `demo` rejected outright with
`[context.escape]`. Four shapes, or the check is not a check.

## Emulator A/B — three checkpoints, branch vs master

Captured by holding a direction under free-run rather than frame-counted `press` (the press path
wedges intermittently on the StopSystem race, and press-frame captures drift anyway).

| checkpoint | master | branch | verdict |
|---|---|---|---|
| boot / OJZ act 1 spawn | jungle renders | identical | plane A/B bases, H40, 64x64 plane size, scroll mode, palettes all survive the blanket write |
| section-crossing palette | trunks go red | identical | the per-section palette (effects P1) is unaffected |
| water raster fixture | blue below the waterline | identical | **the fixture whose wire format this parcel changed** |

The second and third are the load-bearing ones. Both looked like corruption on first sight — a
whole-screen palette shift is exactly what a botched blanket restore produces — and both turned out
to be the fixtures rendering correctly. Neither could have been called from the branch capture
alone; the master A/B is what made them readable.

## Zero release cost, CRC-proven

The reg `$0F` invariant (below) is enforced by DEBUG-shape asserts. They are free in release, and
that is proven rather than asserted: adding all three left the plain ROM **byte-identical**
(`crc=8b3dc951` before and after, at the point of measurement). DEBUG grew +98 bytes total across
the three sites, ~55-60 cycles each.

## The reg `$0F` invariant, and its gate

The flush now writes reg `$0F` (autoincrement) every frame. Three in-game routines make mid-frame
`$8F80` autoincrement excursions that bypass the shadow entirely, and they are safe only because
interrupts are masked across them. Previously that safety was *structural* — nothing marked `$0F`
dirty, so the flush provably could not touch it. This parcel spends that guarantee, so it replaces
it with a gate:

```emp
if DEBUG == 1 {
    move.w  sr, d0
    andi.w  #$0700, d0
    assert.w d0, hs, #$0600     // IPL >= 6: no VBlank can land mid-excursion
}
```

**The predicate is IPL >= 6, not == 7,** and that distinction is the whole correctness of the gate.
Main-loop sites mask to IPL 7; `plane_buffer`'s excursion runs in **VBlank context at IPL 6**, set
by hardware and never masked. The main loop idles at IPL 3 (`boot.emp:307`), so `>= 6` still
discriminates exactly. An `== $0700` assert would have false-fired on every frame.

Two placement constraints, both found by building rather than by reading:
- An `assert` may **not** sit inside a `with z80_stopped` body — its raise rail ends in a `jmp`
  modelled as a `TailOut` CFG edge, firing the zero-firing-by-contract `[context.escape]` family.
  Each assert is hoisted just outside the `with`, still inside the masked span.
- `plane_buffer`'s assert sits at the **proc head**, not at the excursion: at the `$8F80` write no
  register is free — `d0`,`d1`,`a0`,`a5`,`a6` are live and that is exactly the proc's `clobbers`
  contract.

None is placed immediately after its proc's own `move.w #$2700, sr`; that would measure the line
above it and be vacuous. Each sits far enough from the mask that a refactor moving either gets caught.

### The fourth site, and why it has no gate

There is a **fourth** `$0F` excursion, and the three-site census above is incomplete without it:
`engine/system/boot.emp:109` writes `move.w #vdp_reg($0F, $01), (a4)` — autoincrement 1, so the
VRAM DMA fill steps byte by byte — and restores it from `AUTO_INC_2_CMD` (`boot_data.emp:184`).

It carries **no assert, on purpose.** It is safe by *context*, not by masking discipline: boot runs
masked at `$2700` from its first instruction, VInt is not enabled in the VDP until `boot.emp:300`
(`move.b #$34, VDP_Shadow_Table + VDP_MODE2_OFF`, flushed at `:303`), and the SR is not lowered to
`$2300` until `:307`. No VBlank handler can run while the excursion is open, so no flush exists to
land in it. An IPL assert here would re-measure the boot mask a few lines above and be exactly the
vacuous check the three placements above were careful to avoid.

It is recorded because of **how it was missed**: the audit grep this parcel inherited
(`move\.w\s+#\$8[0-9A-Fa-f]|#\$9[0-2][0-9A-Fa-f]`) *structurally cannot* find it. The word is
spelled `vdp_reg($0F, $01)` and folded at comptime, so no source line contains `#$8F`. The grep in
`ENGINE_ARCHITECTURE.md` §0.4 now also matches `vdp_reg\(` and `Set_VDP_Reg`, which finds both boot
sites (`boot.emp:109`, `boot_data.emp:94`). A census tool that cannot see a whole spelling class is
worse than no census, because it reads as exhaustive.

## The offset that the pins caught

`WATER_TEMPLATE_ARM0_OFF` moved 6 -> **2**, and the plan said 4. The header goes from
`[mask][init_count][init_word][arm0]` to `[mask][arm0]`; two words removed is 4 bytes, so 6 - 4 = 2,
and byte 4 is now `opc0`.

It was caught by dumping the emitted template out of the built ROM instead of trusting the
derivation — `0004 8A75 0000 ...`, where `$8A75` = `$8A00 | (120-3)` is the priming arm word sitting
at +2. At 4 the water patch's `subq.w #1` would have decremented a record's `op_count` and `dbf`
would have walked ~35k words of ROM as opcodes inside a raw interrupt handler.

The three hand-typed pins (`OJZ_TEST_HAND` 18->16 words, `OJZ_WATER_HAND` 18->16,
`OJZ_VSRAM_HAND` 15->14) are this parcel's real safety net, and each was checked by reading the
emitted bytes back out of the ROM rather than by trusting its own `first_mismatch` ensure.

## The surviving guard was watched to fail

The reg `$0A` ban is about the raster *schedule*, not restore, and had to survive the collapse of
`set_reg`. Probed with `fire(100, [set_reg($8A6D)])`:

```
[Error] set_reg: 35437 writes VDP reg $0A, the HInt line counter the raster SCHEDULE owns —
Raster_HInt writes the record's arm word before running the ops, so this op would overwrite it
and desynchronise every later fire in the frame.
```

Probe reverted; all four ROMs rebuilt byte-identical afterward. (`35437` = `$8A6D`; the `ensure`
interpolates the word as decimal, a pre-existing wart.)

## What this evidence does NOT cover

- **The replay net was not run.** It has no automated runner — `tools/test_replay_fixture.py` checks
  only fixture structure and says so in its own docstring. Running it needs the emulator and a human.
- **The "~200 cycles cheaper" claim from the plan header is UNMEASURED** and is deliberately not
  repeated as fact anywhere in this parcel's commits or docs. It rests on the old loop being
  O(highest dirty bit); when the highest dirty bit is low (parallax alone dirties reg `$0B`) the
  blanket version could be a wash. The parcel's justification is structural regardless.
- **The dense-tier programs have no hand-word twins.** `OJZ_TestGradient` and `OJZ_TestRamp` shrank
  by 2 words each, verified only by reading emitted bytes. A dense-tier pin would be worth adding.
