# Parcel W — one world anchor, two readers. Gate evidence.

**Date:** 2026-08-15. **Branch:** `parcel/w-world-anchor-overlay`.
**Design:** `docs/superpowers/specs/2026-08-15-effects-p3-parcel-w-design.md` (revision 2).
**Plan:** `docs/superpowers/plans/2026-08-15-effects-p3-parcel-w.md`.
**Prerequisite:** W0 (`Effects_World_Y[]` total-bound), merged separately, chain 121.

| shape | CRC | length |
|---|---|---|
| `s4` | `d4d7c68b` | 697452 |
| `s4.debug` | `3adce11a` | 712382 |
| `demo` | `84c57ec9` | 96047 |
| `demo.debug` | `693ff2e5` | 100396 |

All four boot and render; each was looked at, because no gate in this parcel looks at a screen
and that is how the release-shape blackout got through once before.

---

## 1. The claim, and the measurement that proves it

A palette boundary and a shimmer boundary must land on the **same scanline**, driven by one
act-space anchor. The two are computed by completely separate machinery — the raster patcher
rewrites an arm word in `Raster_Buf_B`; the parallax overlay splits a band in
`Parallax_Shadow_Bands` — so agreement is a real result, not a tautology.

Camera pinned at `Camera_Y = 144` via `Debug_Scene_Freeze`. Anchor written to
`Effects_World_Y[0]`; both sides read back independently:

| anchor | palette side (`Raster_Buf_B` word 1) | → fire line | → screen | scroll side (split top) |
|---|---|---|---|---|
| 184 | `$8A25` (gap 37) | 1+37+1 = 39 | **40** | **40** |
| 264 | `$8A75` (gap 117) | 1+117+1 = 119 | **120** | **120** |

`184 − 144 = 40`. `264 − 144 = 120`. One write moves both. Channel 1's arm was recomputed from
`$8A81` to `$8A31` across the same move, keeping its own boundary at fire line 169 — the chain's
relative gaps stayed consistent while a record between them moved.

**Why the arm word and not CRAM.** Oracle's CRAM reads are frame-latched: `run_to_scanline(20)` +
`read_cram` and `run_to_scanline(60)` + `read_cram` return **byte-identical** palette lines on
correct code. That is the failure direction the design predicted (loud on correct code, not
vacuous), so the CRAM leg was replaced by the arm word, which is numeric, independent of the
scroll side, and is the actual quantity the VDP fires on.

## 2. The shimmer itself

Anchor 224, camera 144 → boundary 80. `Hscroll_Buffer` BG words:

- lines 68..79: `FFD0`, flat, twelve consecutive lines
- line 80: `FFD1` — the first sampled line
- lines 80..103: `FFD1 FFD0 FFD0 FFD0 FFCF FFCF FFCE FFCE … FFCF FFD0 FFD1 FFD2 …`

A ±2 px sine about `FFD0`, which is `deform_shift 2` against `DeformTable_Shimmer`
(amplitude 8, `8 >> 2 = 2`). Bands above the line are untouched.

## 3. The shadow view, decoded

Anchor 264 (boundary 120), 10 bytes per entry:

```
band 0  top   0  dsb 15
band 1  top  48  dsb 15
band 2  top 112  dsb 15
band 3  top 120  dsb  2   <- the SPLIT: band 2's fields, retopped, shift overridden
band 4  top 224  dsb  2   <- old band 3, shifted down one slot, shift overridden
```

Five entries where the config authors four. The split inherits its parent's **scroll factors**
and scroll words and changes only the top and the deform shifts — which is the mechanism that
lets structure below a water surface survive instead of collapsing onto one band.

## 4. Every designed path, exercised

| case | anchor | result |
|---|---|---|
| mid-screen split | 184 / 224 / 264 | split at 40 / 80 / 120; palette agrees at 40 / — / 120 |
| **flat span 1** | 257 | split top 113, band 2 spans 112..113 |
| **flat span 7** | 263 | split top 119, band 2 spans 112..119 |
| fully submerged | 100, no band declared | split at line 0, band 0 zero-length, **every** band overridden |
| off-screen below | 400, no band declared | no split, 4 bands, every shift back to 15 — overlay inert |
| clamp lo | hotkey, falling camera | anchor pinned to `camY + 39 + 1` |
| clamp hi | hotkey, frozen camera | anchor pinned to `camY + 119 + 1`; unclamped it would have reached 1936 |
| no band | `Raster_Patch_Tab` forced 0 | anchor ran unclamped to 1915 |

**The two flat-span rows are Parcel W's proof of a DIFFERENT commit.** `.lp_flat`'s remainder
tail (`b6ac537d`) could not be exercised when it was written, because nothing in the tree
produced a band span that was not a multiple of 8 — its own commit says so and says it would be
unproven without this sweep. Spans 1 and 7 are the two extremes of the range that makes
`lsr #3` yield 0 and `subq #1` wrap the `dbf` counter to `$FFFF`. In both frames the buffer tail,
poisoned with `DEADBEEF` immediately before, came back **fully overwritten with real wobble
values** — no spray, no under-fill. Without the tail those two frames would each have written
65,536 × 8 longwords past `Hscroll_Buffer` into the DMA queues.

The "fully submerged" row is S3K's `Water_full_screen_flag` state
(`skdisasm/sonic3k.asm:8496-8505`) arrived at structurally: `L <= 0` clamps to 0, the split lands
at index 0, and the override walk covers every band. No special case was written for it.

## 5. Output neutrality of the two refactors

Both preparatory commits had to change no output, and the shipped OJZ fixture **cannot show
that** — all four of its bands carry identical factors, so `Hscroll_Buffer` is uniform and an
under-fill or a misplaced boundary is invisible in a plain diff. That is a vacuous instrument and
was discarded.

Instead a temporary diagnostic config was built (distinct BG factors per band, BG vscroll locked
so the rotation is identity), under which the buffer shows four distinct runs:

- boundaries measured at lines **64 / 128 / 192**, exactly the authored cell tops 8 / 16 / 24 × 8
- `Hscroll_Buffer` hashed with and without the units commit: `crc32 0x4C8E8B79`,
  `fnv1a64 0x596CED2A62222925` — **identical**

The diagnostic was reverted; only `parallax.emp` shipped from that commit.

Coverage note kept deliberately: per-cell fill has no fixture in this scene. Its single reader
converts with an `lsr #3` that exactly inverts the rebase's `lsl #3` over the range the cell clamp
permits (0..28 cells → 0..224 lines → 0..28 cells), and that is an argument, not a measurement.

## 6. Contract violations the build gate caught

Both were real, neither was baseline drift, and both are worth recording because they are cheap
to repeat:

1. **`call.live-clobbered`** — `Raster_GetChannelBand` first declared its results in `clobbers()`,
   so the call site read registers the contract said were destroyed. Fixed with an `out()` clause.
2. **`proc.out-unverified`** — a **bare** `out(dN)` claims all 32 bits, which only a `.l` write or
   a `moveq` satisfies; the band words arrive through `move.w`. Fixed by typing the outs `u16`.
   The null-table path also zeroes `d1`/`d2` so the declaration holds on **every** return path,
   not just the interesting one.

## 7. What is NOT proven here

- **The per-cell fill path** — argued, not measured (§5).
- **A second anchored region.** The mechanism extends to one (a second split plus a second
  override range) but nothing needs it and nothing was built.
- **Visual correctness of the tint itself.** The palette boundary's *line* is proven; that the
  colours below it are the intended deep-water variant is inherited from C2's fixtures, not
  re-measured here.
- **Real hardware.** Emulator only, as everything in this project is.
