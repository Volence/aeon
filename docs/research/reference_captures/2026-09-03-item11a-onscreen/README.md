# Item 11a on screen: the mid-frame nametable-base change, seen

Closes the residual its own booking tagged for the controller — *"the on-screen half is unrun
(no emulator in that lane)"*. Captured 2026-09-03 on a PRIVATE headless instance
(`tools/aether_instance.py`), never the owner's window.

## Method

`s4.debug.bin` at aeon `origin/master`, warped to OJZ act 1 (`Warp_Req_X/Y` = `$0B80`/`$0B80`)
and settled 40 frames. **Control captured first**, then `Raster_Program` installed by writing
`OJZ_BaseSwap`'s own listing address `$013D1A` into `Raster_Pending` and running 6 frames.
`Raster_Pending` read back as `$00000000` and `Raster_Program` as `$00013D1A`, so VBlank
consumed the mailbox — the install is confirmed at the engine rather than assumed from the
picture.

The control is the SAME emulator instance at the SAME position moments earlier, so the only
variable between the two images is the installed raster program.

## What the pair shows

- `control-no-swap.png` — foreground floor drawn normally to the bottom of the display.
- `swapped-base-at-line-160.png` — identical above the boundary; from roughly screen line 160
  down, the Plane-A layer draws **Plane B's nametable**, so the floor is replaced by a second
  copy of the background map at Plane A's scroll offsets.

**Both predictions in the booking hold.** The duplicated map is horizontally displaced from the
real background, which is the mechanism working rather than a bug (Plane A's scroll values are
not Plane B's). And the top of the frame is unaffected, which is the VBlank shadow flush
restoring reg `$02` with no cleanup code and no accumulation — the booking's §2.0 claim 1,
previously established only by reading `Flush_VDP_Shadow`'s source.

## What it does NOT settle

Design §8 **Q2** — whether the boundary lands on line 160 or 161 — is not answered here. A
single capture cannot separate the two, and the booking states the blanking spin guards only the
CRAM paths, so a bare `OP_SET_REG` may switch partway across the fire+1 line. Q2 stays open.
