# Aeon overseer handoff 20 (2026-09-16, evening)

**The resume anchor for the next aeon session.** Read `docs/lane-status.json` first. **Fetch origin before reading master.**

## Landed this session (all pushed, each re-verified on the merged tree)
- **M-B** (`3e0f48e5`): foreground cache window page set over real stitched S2/S3K zones. `docs/research/megaact-bg-streaming/08-m-b-window-page-set.md`, tool `tools/megaact_window_pageset.py`.
- **Region background switch** (`7dc737ec`): `Region.rg_bg_tiles`; chunked Deferrable overwrite at 1824 B (liveness bound vs the non-Deferrable worst; controller ruling); completion keyed to arena-writing entries; repaint suspended until then; sync redraw uploads region tiles. Gate `bg_switch` in `effects_gates`. Cost doc `region-bg-switch-cost.md`. Plan `docs/superpowers/plans/2026-09-16-region-bg-switch.md`.
- **Showcase classic BG** (`24500c97`): the DEBUG region (x 1024-2047, y 2048-4095) shows S2 Oil Ocean's BG in its own colours. **The owner flew it and confirmed it works** (DEBUG crc `8d3d92a0`). To take him there: warp via `Warp_Req_X/Y/Flag` on his window socket `/run/user/1000/oracle.sock` (announce first).
- **Page order research** (`f7911e96`): `refined_zonesplit` order puts every M-B population at <= 12 pages; nothing fits 10. `docs/research/megaact-bg-streaming/09-page-order-candidates.md`, tool `tools/megaact_page_order.py`.

## Owner answer this session
- **FG-CACHE-10-VS-WHOLE-GAME-ACT: hold-and-research** (verbatim: "yeah I agree, research would be best"). REGIONS-P2-STEP7 (cache 12 -> 10) stays held until the research reports.

## START HERE: FG-CACHE-10-RESEARCH
Can the stitched S2/S3K populations fit **10** frames? Levers named in 09 and not built: a pin rule aware of the frame count (CNZ1 alone pins 9 of 12), smaller window margins (the 80x60 window vs the screen), 32-tile pages, per-region pools. Measure with the existing tools on the same populations; OJZ act 1 must not regress. Tool-only; no ROM bytes. Also note: 12 has no margin (54,237 windows in the S3K row sit exactly at 12), and M-E (confirm the release soft-lock at runtime) is still owed.

## Then
- **STITCHED-ACT-PAGE-ORDER wiring**: adopt the chosen order in `ojz_strip_gen` Pass 4 for multi-zone acts only, plus a build check refusing any window over budget. Its budget depends on the research above.

## Held / still the owner's
- REGIONS-P2-STEP7/8 held (above). LS-13b open. SP-6 spring sound A/B still waits on his ear.

## Booked this session (DEFERRED_WORK.md)
STITCHED-ACT-PAGE-ORDER; REGION-BG-TILES-AUTHORING, REGION-BG-COVER-WARNING, REGION-BG-CAMERA-HOLD (owner option), REGION-BG-PER-REGION-BANDS, REGION-BG-SYNC-DISPLAY, REGION-BG-RESPAWN-CONTRACT, REGION-BG-STREAMER-SUSPENSION-UNGRADED. Also the OJZ pinned-page prose (4 vs 5) at `constants.emp:470` / `ENGINE_ARCHITECTURE.md:5488`.

## Cross-lane
- Sigil booked `BG_Bands_Hold` for `bg_anim_port.rs` at sigil `91993841` (not live until their aeon pin passes `7dc737ec`). Nothing owed.

## Lessons worth keeping
- The land gate treats a new `tools/*.py` as code: it needs a `landing_build.sh` stamp, and any argv-dispatch tool must be rostered in `test_cli_dispatch_refuses.py`.
- Agents that "wait for a background task notification" are usually alive: their own waits wake them. Check the branch and processes before intervening.
- The owner's window may rebuild the ROM when it launches; compare CRCs rather than assume.
