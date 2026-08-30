# The parallax scroll clamp, looked at (2026-08-30)

The agent that built `parcel/scroll-and-section-clamps` flagged that fix 1 **changes the
picture on a shipped scene, on purpose**, and ran no emulator. This is that check.

## It removes a real artifact. The clamped picture is the correct one.

Measured on `s4.debug.bin`, master `2404d825` vs branch `6516fc68`, same input, same frame:

| | camX | camY | BG V-scroll (`Vscroll_Factor` low half) |
|---|---|---|---|
| master, boot | 96 | 144 | 0 |
| master, after travel | 3872 | 144 | **−46** |
| clamped, boot | 96 | 144 | 0 |
| clamped, after travel | 3872 | 144 | **0** |

−46 is exactly `(camY − v_center_y) >> v_factor_bg` = `(144 − 512) >> 3` for OJZ_Default,
so the agent's derivation reproduces. A V-scroll of −46 on a 512-line plane shows plane rows
466..511 in the screen's top 46 lines and rows 0..177 below — **the bottom of the background
art appears above the top of it**, with a hard discontinuity across the seam.

That is visible, and it is what the clamp removes: in `master-travelled.png` the purple
flowers from the art's bottom edge occupy the top rows (361 purple pixels in rows 0-15, 17 in
rows 16-31, zero below); in `clamped-travelled.png` there are none and the canopy is
continuous.

**Boot shows zero differing pixels** because the BG scroll is still 0 there — the divergence
only appears once the scene's parallax step has run. A reviewer who compared only boot frames
would have concluded the clamp does nothing. Compare after motion.

## ⚠ WHAT IT REVEALS IS AN AUTHORING PROBLEM, AND THAT PART IS THE OWNER'S

The clamp is a legibility fix, not a correctness one — the wrap was arithmetically fine. What
it makes legible is that **OJZ act 1 is about 2,048 px taller than its background budget**
(`PLANE_B_SPAN << v_factor_bg`). Clamped, the background pins at the top of its art for the
act's top 512 px, tracks from act Y 512 to 2,816, and sticks above that.

On flat ground the camera's Y never moves, so nothing is visible in play today. It becomes
visible the moment the showcase has real vertical travel. The options are the owner's: a
different `v_factor_bg`, taller background art (booked as BG-TALL-AND-PAGING), or accepting a
background that stops tracking outside the middle band.

**This is why the clamp is worth landing even though nothing looks wrong today**: the wrap
produced a plausible picture, so the budget overrun had no symptom anyone would chase.

Reproduce: `docs/captures/2026-08-30-scroll-clamp/` was made by driving both ROMs to the same
frame and reading `Vscroll_Factor` directly rather than inferring from pixels.
