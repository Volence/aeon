# WINDOWED-BG-VERTICAL-CLAMP: a clip zone's whole background height, streamed

Research for `docs/DEFERRED_WORK.md` `## WINDOWED-BG-VERTICAL-CLAMP` (booked 2026-09-27,
`parcel/woven-hpz-wfz-prep`). Branch `parcel/windowed-bg-vclamp`. Everything below was read or
run on the tree at `5b5e07d3`; line numbers are that tree's.

## 1. The question

`tools/clip_bg_lower.py` lowers ONE 512-row window of a Sonic 2 zone's background into Plane B;
the engine clamps the BG V-scroll to `0..VSCROLL_BG_MAX` (288) because no clip row authors
`rg_bg_span`. Past the clamp the background stops moving vertically. The booking left open
(READ, not measured) whether the engine could stream a taller map at all.

## 2. Findings, firsthand

**The engine streams a map taller than the plane today. YES, and the lead that said so was
right.** Regions part 2 step 5 built it and every piece is live on the clip act's ladder:

| piece | where | what it does |
|---|---|---|
| the field | `engine/structs.emp` `Region.rg_bg_span` ($14) | the map's height in px; 0 = the plane |
| the clamp | `engine/level/parallax.emp:2994` (Parallax_Step5_Vscroll) | ceiling = `rg_bg_span - 224`, map space |
| the rate clamp | `parallax.emp:3087` | 16 px a frame, only on a map >= `BG_TALL_MAP_MIN_SPAN` (520) |
| the streamer | `engine/level/bg.emp:647` BG_Stream_Update, span read at `:789` | 64-row ring window, lead 17 rows, 2 rows a frame |
| the prime | `engine/level/section.emp:606..658` Section_RedrawPlanes | blits the window the live scroll selects (boot, warp) |
| the ladder | `games/sonic4/test/ojz_scroll_test.emp:1857..1871` | CheckBoundary, Parallax_Update, BG_Stream_Update in one frame |

Two conditions, both read from the code: the span is honoured only on a row that ALSO names its
own `rg_bg_layout` (`section.emp:596-606`: a span with the act default's layout would window a
one-plane blob), and the act default (`Act.act_bg_layout`) must stay exactly one plane (`bg.emp`
ensure at `BG_LAYOUT_SIZE`, because BG_Init runs before the camera). So a tall start zone names
its tall blob on its rows and keeps a one-plane act default for BG_Init; the prime overwrites it
before the first visible frame.

**What the lead missed: the parallax BANDS do not follow a taller map.** Step 4a picks a band by
PLANE line (`parallax.emp:2196`, `and.w #PLANE_B_SPAN-1`), booked as BG-BAND-PLANE-ANCHOR. On a
map taller than 512 lines, rows 512 apart share a band. Per zone, derived by
`clip_bg_scroll.derive_tall`:

* **Wing Fortress** is unaffected. Its cloud rows (BG 512..1919) repeat every 128 rows
  (drift 128/64/32 per 1/256 px), which divides 512, and its rows 256..511 are fully
  transparent (chunk rows 2-3 unpainted), which no hscroll can show. ONE band layout of 12
  bands is exact over every screen top a clip reaches (solo 256..1568, woven 384..1568).
* **Hidden Palace** is affected. Rows 0..127 take camX/2, 240..655 camX/4, 768..1151 camX/2,
  with ramps between: rows 0 and 512 differ. No single layout covers screen tops 0..912. A
  CHAIN of four layouts does (6, 6, 6, 7 bands), each exact over a screen-top interval, each
  pair overlapping by >= 32 rows.
* **Oil Ocean** does not need it: its clips' screen tops reach BG rows 80..288, inside the
  window it has (the booking's "nearly fine" is exactly fine for the rects clipped today).

**The coverage the booking measured, per clip, as screen-top BG rows reached vs held:**

| clip | zone | screen tops Sonic 2 reaches | window holds | tall map |
|---|---|---|---|---|
| s2_hpz_solo | HPZ | 0..912 | 0..288 | BG rows 0..1151 (144 tile rows, 18,432 B) |
| s2_wfz_solo | WFZ | 256..1568 | 896..1184 | BG rows 256..1791 (192 tile rows, 24,576 B) |
| s2_woven | WFZ | 384..1568 | 896..1184 | BG rows 384..1791 (176 tile rows, 22,528 B) |
| s2_woven | HPZ | 0..912 | 0..288 | BG rows 0..1151 (18,432 B) |
| s2_ooz_solo, s2_woven | OOZ | 80..288 | 0..288 | none needed |

Tiles barely move: HPZ 145 -> 155 over the whole map, WFZ 18 -> 18. No RAM, no VRAM: the ring
and the arena are the ones every region already uses.

## 3. What Sonic 2 and S3K do

Sonic 2 streams its background vertically through a SHORTER plane than ours: `VDPSetupArray`
writes `$9001`, "Scroll table size: 64x32" (s2.asm:1450), a 256-line plane, and `Draw_BG1`
(s2.asm:18676) draws a block row above or below the screen on `scroll_flag_bg1_up/down` as
`Camera_BG_Y_pos` moves. HPZ and WFZ are ordinary tall maps there; the "window" is an artefact of
our lowering, not of the source. S3K does the same with `Draw_BG` / `Draw_PlaneVertTopDown`
(sonic3k.asm:103214, 103462). Our BG_Stream_Update is that mechanism with a 64-row ring and a
17-row lead. The band tables of both games are indexed by BG row (HPZ's `TempArray_LayerDef`
through `(BG_Y & $3F0) >> 3`, WFZ's segment array through `BG_Y & $7FF`), i.e. MAP space, which
is exactly what our plane-space band selection cannot say beyond 512 lines.

## 4. Options, priced

1. **Author the span and the full tall map through the existing streamer, plus a per-height band
   chain bound by `rg_parallax` on split region rows** (RECOMMENDED, built). Engine: nothing.
   Bake: `clip_bg_lower.lower(rows=, x_reach=)`, `clip_bg_scroll.tall_extent/derive_tall`, the
   bake emitting `rg_bg_layout`/`rg_bg_span`/`rg_parallax` and splitting a tall zone's rows at
   the chain's switch heights. ROM: +10,240 B per HPZ blob, +14-16 KB per WFZ blob (the map rows
   past one plane). Canonical ROMs: unchanged (clip shapes only). Costs carried: the rate clamp
   now applies inside these regions (16 px a frame; HPZ's scroll moves at most 8, WFZ's 1:1
   scroll up to the camera's 16), so a crossing INTO a tall zone whose scroll differs from the
   zone left slides at 16 px a frame, measured below by the crossing witnesses; and a zone with
   more than one layout switches them INSTANTLY (transition 1), which a clip act with
   `parallax: snap` already does everywhere, and a one-zone act never crosses otherwise.
2. **A second window swapped at a height.** Two one-plane blobs, two region rows. Every swap is
   a full plane WIPE (BG_WIPE_ROWS_PER_FRAME rows a frame) in plain view mid-zone, and still
   needs the band chain. Strictly worse than 1 on the same mechanisms.
3. **Fix BG-BAND-PLANE-ANCHOR in the engine** (band tops in map space). The right end-state for
   the TRACK bands of big levels, but a change to the parallax band model, every scene's
   authored tops and the per-band anchors: a novel engine mechanism, not this parcel. Option 1's
   chain is data, and it retires cleanly the day that lands (one layout per zone).
4. **Accept the hold.** Free; the owner-visible woven act keeps HPZ's background frozen for its
   lower 1,248 px of camera travel and WFZ's for all but 288 px.

## 5. Recommendation

Option 1: it is the engine's own streamer, fed the map Sonic 2 itself streams, with the one
thing the engine cannot say (map-space bands past 512 lines) handled as data on region rows that
already exist. No engine file changes; canonical ROM bytes do not move.

## 6. Outcome (measured after building option 1)

* **Solo clips: closed.** Sonic 2 agreement over every camera top (screen-top BG row and every
  visible non-transparent line's band kind): HPZ 578/1825 -> 1825/1825, WFZ 289/1313 ->
  1313/1313. The ROM: `clip_bg_scroll_witness` exact on every probe (72 HPZ, 16 WFZ) with a new
  nametable leg that checks each visible map row sits in plane row m & 63.
* **The woven act: held back, by measurement.** With HPZ and WFZ tall, `crossing_witness` stays at
  0 glitch ticks on 9 of 11 connectors but counts 29 on hpz_to_ooz and 9 on hpz_to_mtz, both
  crossings INTO Hidden Palace: the tall region's rate clamp slides the scroll 16 px a frame from
  the zone left (up to 32 frames) and its wipe is the CPU sweep, costs that option 1's "costs
  carried" paragraph named and that Z2's model and the woven connectors do not carry. So
  `clip_rom_bake.TALL_JOINED_ZONES = False`: multi-zone acts stay windowed and s2_woven rebuilds
  byte-identical. The remaining fixes (an engine arm for tall entry, or connectors lengthened by
  the modelled cost) are priced in DEFERRED_WORK WINDOWED-BG-VERTICAL-CLAMP's amendment.
