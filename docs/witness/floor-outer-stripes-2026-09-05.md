# Floor: why the outer stripes point away

His words: *"That floor is actually almost perfect, the first few are good then a few
after get weird and point away, but they continue to move like they should, is this the
art that's the problem?"*

**Yes, it is the art — and specifically one deliberate line in the generator.**

## The mechanism, from `tools/perspective_floor_gen.py:320-332`

```
u = ((x - vx + 256.0) % 512.0) - 256.0
off = abs(u) / p
```

The pattern is keyed on **`|u|`**, not `u`. That makes it even about `u = 0` **and** even
about `u = ±256`. The docstring states the intent plainly: *"even about u=0 and about
u=±256, so the pattern is exactly 512-periodic and the mirror axes sit at the vanishing
point and at the wrap."*

- Evenness about `u = 0` is **correct and wanted**: a fan IS mirror-symmetric about its
  vanishing point. Left of centre leans left, right of centre leans right.
- Evenness about `u = ±256` is the **cost**. Past the wrap axis you are seeing the
  fan's *opposite half* reflected back. Its planks lean the other way — which is exactly
  "get weird and point away".

So the fan is only correct within ±256 px of the vanishing point. Beyond that the viewer
sees a mirrored copy, and the handedness is reversed.

## Why his "they continue to move like they should" is the tell

The motion is driven by the per-row scroll gain, which is unaffected by the fold — that
half was fixed and is right. The fold only decides *which pixels* are drawn at a given u.
So the floor moves correctly and is drawn wrong, which is precisely the split he
described without having the code.

## What the agent said about it, and where I think it under-stated

The parcel's report described the fold as concentrating the closure error in **one plank**
(the one straddling `|u| = 256`, width 0.47x..1.95x its neighbours). That is true about
plank *width*. It does not cover *handedness*: past the axis the whole half is reflected,
not just the straddling plank. His report is about the reflected half, not the odd-width
plank.

## The alternative, not built

Per-row stripe period = one base period times that row's scroll scale, with the periods
chosen to **divide the plane width (512)**. Then the pattern tiles by TRANSLATION and
needs no mirror axis, so it converges at one centre for every camera x. This is the
reverse direction from the last fix: generate the art from the gain table rather than
fitting the gain to the art.

Cost, stated rather than hidden: constraining every row's period to divide 512 quantises
the depth ramp, and the tile budget (121 recycled slots, 320-tile static) is what killed
the richer options last time. Whether the quantised ramp still reads as perspective is a
question for a capture, not for me asserting it here.
