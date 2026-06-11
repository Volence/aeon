# Research: Coordinate Rebasing / Level Wrap in Shipped Genesis Engines

Question: when classics wrap level coordinates, what state do they fix up? Is "rebase
coordinates, touch nothing else" the established pattern? (Researched 2026-06-10 for the
§teleport-simplification work.)

## Core finding

The classics never rebase at all — they make the coordinate space itself modular. Wrapping
levels use a power-of-two height ($800 or $1000), and every consumer of a Y coordinate masks
at point of use (`and.w (Screen_Y_wrap_value).w`). There is no "wrap moment": no state shift,
no object pass, no plane redraw. Plane/scroll invariance is exactly the mod-arithmetic no-op
we just proved for our teleports. Our system is the same idea with add/sub $1000 instead of a
mask (because our pair window isn't a power-of-two-sized full space).

## Per-reference findings

### Sonic 3 & Knuckles (`skdisasm/sonic3k.asm`)
- Wrap enable = `Camera_min_Y_pos == -$100` sentinel; `Screen_Y_wrap_value` is the mask.
  Defaults set in `LevelSetup` (102183): mask $FFF, `Camera_Y_pos_mask` $FF0,
  `Layout_row_index_mask` $7C (102203-102205). LevelSizes table (38094+): wrapping levels are
  $1000 tall (MGZ1: `-$100,$1000`) — power of two, confirming mod-invariance is by design.
- Camera: `MoveCameraY` masks the player→camera delta (38442-38444) and wraps camera Y on both
  edges (38535-38539 low side `and.w`; 38560-38566 high side subtracts wrap size). No redraw.
- Player: y_pos masked every frame after movement (21993-21996; 2P variant 21568-21575 also
  masks x_pos for horizontally-looping competition levels).
- Other objects: NOT globally shifted. Free-moving objects opt in individually, masking their
  own y_pos after movement (Tails' birds 35288-35290; 2P items 36406-36418; ~6 more at 24463,
  25714, 26239, 29208, 30437, 32899). Most objects never cross the seam and need nothing.
- Rings: `Render_Rings` masks the (ring_y − camera_y) screen delta (18621-18630). Ring data
  untouched.
- Layout/collision: row lookup masked via `Layout_row_index_mask` in draw (8986, 9036, 9167)
  and collision Find_Tile (17948, 19123, 19149).
- BG/parallax: deformation events mask camera Y with `Camera_Y_pos_mask` (102811+ et al.).
- Plane redraw happens exactly once — when wrap mode is TOGGLED mid-level (modulus changes, so
  existing plane content is stale): ICZ teleporter sets $7FF masks then
  `Reset_TileOffsetPositionActual` + `Refresh_PlaneFull` (110067-110071); same in
  `SOZ2_ScreenInit` (114219-114230, with a 15-row delayed redraw at 114252-114256). The Slots
  bonus stage sets masks at init with no refresh (119052-119056). At actual wrap crossings:
  nothing is redrawn.
- Boundary logic disabled under wrap: Knuckles' climb top-boundary clamp skipped
  ("If the level wraps vertically, then don't bother with any of this", 31122, 31320-31322).

### S.C.E. (`Sonic-Clean-Engine-S.C.E.-/`)
Kept the S3K mechanism verbatim. `Engine/Variables.asm:112-113` ("either $7FF or $FFF");
default $FFF in `Engine/Core/Level Setup.asm:18`; camera delta + both-edge wrap in
`Engine/Core/Move Camera.asm:190-192, 297, 313-319`; object-manager load-range comparisons
masked in `Engine/Core/Load Objects.asm:94-103, 234-262`; sprite-render screen-Y delta masked
in `Engine/Objects/Render Sprites.asm:92, 228, 273`; rings in `Engine/Core/Load Rings.asm:348`;
player y_pos in `Objects/Players/Sonic/Sonic.asm:153-156`.

### sonic_hack / Sonic 2 (`sonic_hack/code/`)
S2 style: hardcoded $7FF (MTZ height $800). `engines/scroll_camera.asm:77-79` masks the
camera delta; 157-165 wraps camera at top — our mod replaced the stock $7FF mask with
"add level height to d1 and (a1)" (an explicit rebase, both candidate and stored camera).
Player y_pos masked: `objects/Sonic.asm:91-93`, `objects/Tails.asm:112-114`. Sprite render
masks screen delta: `engines/build_sprites.asm:64, 135`. Same pattern: no global object shift,
no redraw.

### Others / online
- Batman&Robin/Vectorman/Gunstar/etc.: quick grep found no level-wrap mechanism (expected).
- SPG/community docs confirm wrapping zones (MTZ; MGZ1, ICZ1, SOZ2) use camera-relative
  positions with camera-top = 0. Known S2 bug: jump above the camera top → unsigned delta →
  camera scrolls the long way around; during catch-up the camera-driven object manager
  despawns everything, letting the player clip through objects (level-wrap zips). Lesson:
  guard the camera catch-up path, since our entity window is also camera-driven.
- Classics avoid wrap+water entirely: no wrapping level/segment has water, so absolute-Y water
  checks (`Sonic_Water` vs `Water_level`) never meet the seam. If we ever combine them, water
  level is rebase state.

## Answers

(a) Confirmed. The shipped pattern is even stronger than "rebase, touch nothing": coordinates
are modular, so nothing is ever touched. Plane content, layout lookup, collision, rings,
parallax are all invariant under the modulus. Removing our redraw/cache rebuild matches this.

(b) State checklist at wrap/rebase (classics' handling → our equivalent):
- [x] Camera Y (wrapped) → we rebase camera
- [x] Player position (masked each frame) → we rebase player
- [x] Other objects: NO global shift; per-object mask only for seam-crossers → our entity
      window shift covers loaded entities; verify any persistent/global objects (bosses,
      moving platforms with absolute anchors) outside the window
- [x] Object manager load ranges (masked compares) → our window is slot-mapped, covered
- [x] Sprite render screen deltas (masked) → covered by rebased camera
- [x] Ring render deltas (masked) → ensure ring/collected state is slot-mapped
- [x] Layout + collision lookup (masked) → our slot map
- [x] BG parallax camera copy (masked) → we already snap parallax (§4.2)
- [ ] Water level — classics dodge by design; rebase `Water_level` if wrap+water ever combine
- [ ] World-Y-anchored effects (screen shake anchors, HInt split Y, deformation script state,
      recorded position history `Sonic_RecordPos` buffer) — S3K's Pos_table is camera-relative
      at render so it self-heals; check anything storing absolute world Y across frames
- [x] Plane content — never redrawn at wrap; redrawn only when the modulus itself changes
      (S3K Refresh_PlaneFull on wrap-mode enable), which has no analogue for us
