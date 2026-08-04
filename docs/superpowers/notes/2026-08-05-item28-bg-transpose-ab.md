# Item 28 (BG transpose + Tier-1 move.l blits) — A/B evidence

Evidence packet for the `item28-bg-transpose` provenance chain entry, per
`sigil/crates/sigil-harness/golden/ab/AB_PROTOCOL.md`. Class: **BA**
(behaviour-adjacent) — a pure data transpose of the BG layout blob plus the
matching consumer/producer rewrites and a Tier-1 `move.l` blit. No player-facing
behaviour should change: the same nametable cells reach the same VRAM addresses;
only the source byte order and the blit instruction mix differ.

This is the deferred half of review item 28 — the coupled design fork the
`item28-bg-blit` parcel STOPPED at. Owner ruling: column-major layout, `move.l`
blits, **no DMA anywhere**.

## What changed

The 8,192-byte Plane B nametable blob (the act-wide fallback BG; every
production section has `sec_bg_layout = NULL`, so this is the common path) flips
from **row-major** (`blob[row*128 + col*2]`) to **column-major**
(`blob[col*128 + row*2]` — each column's 64 rows contiguous, column stride 128).
Producer and all three consumers move in one change set:

- **Producer** — `tools/inject_editor_bg.py` transposes the row-major editor
  layout into column-major at the editor->engine boundary (the editor-space
  library blobs and `editor_bg_override.json` stay row-major).
- **`Draw_BG_TileColumn`** (`engine/level/plane_buffer.emp`) — column gather is
  now a sequential `move.l` run (16 longwords), not a stride-128 word gather.
- **`Section_RedrawPlanes`** Plane B blit (`engine/level/section.emp`) — per
  column, set the VDP address and drain rows 0..31 with autoinc `$80` (one
  `move.l` = two vertically-adjacent cells); skip rows 32..63. 64 command setups,
  init/recovery-only.
- **`BG_Init`** (`engine/level/bg.emp`) — nametable blit same per-column pattern
  (32 `move.l`/column, all 64 rows); tile blit is now a **Tier-1 `move.l`** loop
  with a re-derived length guard (see below).

## Builds compared

| shape | OLD (`master`, post-parcel-7) | NEW (`parcel/item28-bg-transpose`) | Δlen |
|---|---|---|---|
| `s4.bin` | `crc=40ac3e52` / 379,822 | `crc=730a9f99` / 379,822 | 0 |
| `s4.debug.bin` | `crc=b45a553a` / 423,354 | `crc=b3aaa1df` / 423,388 | +34 |
| `demo.bin` | `crc=3bf54b74` / 65,954 | `crc=ea6213bc` / 65,954 | 0 |
| `demo.debug.bin` | `crc=3e28584b` / 93,929 | `crc=18e5ec7f` / 93,963 | +34 |

Plain lengths unchanged — the net code growth (`section` +32 B, `bg` +48 B,
`plane_buffer` -4 B = +76 B) lands in existing pre-data padding. Debug is tighter,
so +34 B propagates to the final length. **Demo moved but authors zero BG data**
(no `act_bg_layout`): its delta is pure engine-code bytes, no data change — plain
demo absorbs it (len 0), debug demo shows +34.

## Result 1 — the transpose is byte-exact (static proof)

`old_blob[row*128 + col*2] == new_blob[col*128 + row*2]` for a set of probes and,
exhaustively, for all 64×64 = 4,096 cells (`FULL 4096-cell transpose exact: True`):

| (col, row) | old offset | new offset | word |
|---|---|---|---|
| (0, 0)   | 0    | 0    | `4c00` |
| (63, 63) | 8190 | 8190 | `45bf` |
| (17, 40) | 5154 | 2256 | `5501` |
| (1, 31)  | 3970 | 190  | `44b1` |
| (63, 0)  | 126  | 8064 | `4c0f` |
| (0, 63)  | 8064 | 126  | `45b0` |

No cell lost, no cell altered — a pure permutation of the same 8,192 bytes.

## Result 2 — the Tier-1 tile-blit guard, re-derived

The parcel-6 word-count guard (`lsr.w #1` / `beq .skip_tiles` / `subq.w #1`) does
not survive the `move.l` translation — a halved-then-halved count underflows on a
different set of lengths. Re-derived as `lsr.w #2` (longword count), guard first:

| len (bytes) | `lsr.w #2` | `beq .skip_tiles`? | `subq.w #1` | dbf iters | copied |
|---|---|---|---|---|---|
| 1 | `$0000` | **skip** | — | — | 0 (guarded before subq) |
| 2 | `$0000` | **skip** | — | — | 0 (guarded) |
| 3 | `$0000` | **skip** | — | — | 0 (guarded) |
| 4 | `$0001` | no | `$0000` | 1 | 4 B — correct |
| 5 | `$0001` | no | `$0000` | 1 | 4 B, trailing byte dropped (benign) |

Lengths 1..3 `lsr#2 -> 0` and `beq` skips **before** the `subq`, so the
`$FFFF`/65,536-longword (256 KB) spray is unreachable — the "last line of
defense" property is preserved. Both counter ops stay hoisted **above** the
`stop_z80` bracket, so a taken guard branch never skips the matching `start_z80`
(the parcel-6 hazard). Real blobs are 32-byte granular
(`inject_editor_bg.py` asserts `len % 4 == 0`), so the drop never fires in
practice.

## Result 3 — build + strict-suite status

- All four shapes build clean; `verify_level_bin: OK`; committed level tree
  regenerated with `tools/regenerate-level.sh` (only `zone_bg.bin` changed, an
  exact transpose).
- Sigil strict suite (`SIGIL_STRICT_GATE=1`): **2,959 passed / 65 failed**. Every
  failure is a stale-pin/golden consequence of a byte-changing parcel — `pins.rs`
  and the frozen golden references are snapshots from the branch point. The 16
  drifted pins map exactly to the three edits (`SECTION` len +0x20, `BG` len
  +0x30, `V_INT_DRAW_LEVEL` -4, all else downstream shift); the grown `section`
  overflows `camera`'s frozen pin slot, which aborts the shared native resolve
  and cascades to the region-vs-reference tests. **Zero logic failures, zero
  unexplained.** Repin/refreeze is the controller's ritual (not run here).

## Dynamic A/B — controller results (oracle, foreground)

**Scene**: reset-deterministic OJZ, `press(right, 300)` then
`press(right+down, 600)` — 900 frames total, the second leg at max-speed
DIAGONAL scroll (the historical worst case; exercises `Draw_BG_TileColumn`
continuously plus the vertical fill).

- **Framebuffer A/B — byte-identical at BOTH checkpoints.** r300 captures md5
  `9cf6ec8b…` on OLD (master @ parcel-7, `b45a553a`) and NEW; r900 captures md5
  `4e8e9ec6…` on both. Captured MID-SCROLL, not at rest. The r300 hash also
  equals the parcel-1 reference capture — the same pixels across three parcels.
- **Lag-frame counter**: OLD 26 / NEW 27 over the full 900-frame run — and the
  split is the finding: read at idle straight after boot, OLD already shows 26
  and NEW 27, so **all lag on both sides is the one-time init storm and the
  entire 900-frame max-speed scroll adds ZERO lag frames on either build**. The
  +1 init frame is the per-column redraw's 64 VDP command setups tipping the
  ~3-frame synchronous `Section_RedrawPlanes` across one more frame boundary —
  one-time, bounded, and exactly the cost the review priced as "init-only
  noise". Steady-state is not-worse (equal, at zero); the transpose's per-frame
  win lands as idle margin rather than lag-count change, since there was no
  scroll lag to remove.
- **Soak**: the 900-frame run ends deep into fresh sections with rendering
  coherent (canopy/trunk/flower layers all intact at r900) and the 68k in the
  normal main loop throughout.
