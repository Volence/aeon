# Side-spring contact: master vs `parcel/solid-touch-reach` (a7f088af)

A **measurement**, not a verdict. The owner looked at commit `a7f088af`
("collide(solids): object contact stops shrinking when the player curls")
against a side-facing spring and said *"looks a little better but still have
this effect"*. Nobody had said what "this effect" IS. This is what it is.

Reproduce:

```sh
python3 tools/spring_clip_ab.py --rom A.bin --lst A.lst --label master --json master.json
python3 tools/spring_clip_ab.py --rom B.bin --lst B.lst --label branch --json branch.json
python3 tools/spring_clip_ab.py --compare master.json branch.json
```

Three ROMs, all `DEBUG=1 ./build.sh`:

| role | commit | sha256 | bytes |
|---|---|---|---|
| control, isolated | `a7f088af^` = `e249d6b3` | `b96de158b097edbc60c80eea609bcd9637b7d0b8d6f29e58cfa66e504f1ccd04` | 846907 |
| subject | `a7f088af` | `0450acd2131c7fc6544165d0f0242b25eb5c335f2895874a691104730eafee88` | 846907 |
| control, master | `25c874ba` | `bb492d964eb30440c27feb0ae7a67a5be875e2a6547325822c03bbee63d13b34` | 846931 |

**The control that means something is the subject's own parent.** `master` was
20 commits ahead of the branch's base, and those commits touch
`collision_data.emp`, `ojz_scenes.emp` and 11 more `.emp` files -- so a
master-vs-branch difference could not have been attributed to `a7f088af` alone.
The isolated pair (`compare_isolated.txt`) reproduces **every number** from the
master pair (`compare.txt`), which is what says the drift did not reach this
measurement.

Note also that the base and subject ROMs are the **same 846907 bytes** and are
completely different builds. Length is not identity here; hash is.

`origin/parcel/solid-touch-reach` is one commit beyond `a7f088af`
(`8ed20bcc`), and it is documentation only -- no code difference.

## What was driven

The LEFT-pointing red side spring placed at world **(360, 584)** in OJZ act 1
section 0 — collision box 16x28, launch vector (-4096, 0) — approached on its
**launching (left) face** along the flat spawn floor, the player resting at
y=573. Two approaches, each at two start offsets one pixel apart (a 2px/frame
walk samples only every other `dx` and cannot resolve a 1px change on its own):

* **walking**, from 60/61 px out, arriving at ground speed $204 (8.8);
* **rolling**, seeded to ground speed $500 and curled with DOWN, arriving at
  $1220 and genuinely wearing the 15x29 ball box on the contact frame.

Plus a static **contact-band sweep**: seat the player at every `dx` from 46 to
6, step one frame, record whether the launch fired. That is the instrument that
resolves the band exactly; the traces are what verify it during motion.

## The finding

The engine's object AABB is `2*|dx| < player_width + object_width`, and the
launch additionally needs `pen_x > 0`. Against this 16px spring that puts the
launch at `|dx| <= floor((W+16)/2) - 1`. Measured, and it agrees with that
formula on all three rows:

| player box | master | branch |
|---|---|---|
| standing, 19 | `|dx| <= 16` | `|dx| <= 17` |
| curled, 15   | `|dx| <= 14` | `|dx| <= 17` |

The spring's **drawn pixels exactly match its collision box** (inked -8..+7
against a 16px box). The player's do not: his running frames ink out to +11..+13
against a 9px collision half-width, and his ball frames to +8..+10 against 7.
So the two silhouettes share a screen column well before the boxes overlap, and
between those two thresholds the player is **visibly touching the spring while
nothing happens**:

| approach | master | branch |
|---|---|---|
| running | dead band `|dx|` 17..21 = **5px** | 18..21 = **4px** |
| rolling | dead band `|dx|` 15..18 = **4px** | 18..18 = **1px** |

That is the residual, and it is a **player art vs player hitbox** mismatch, not
a collision-reach one. Closing it from the reach side would need
`SOLID_TOUCH_W` around **27** (`2*|dx| < W+16` with `|dx| <= 21`), not 21.

## What is NOT an explanation

* **No position discontinuity anywhere.** Every frame's step is within one
  frame of its own velocity; the launch step is exactly -16px against
  `x_vel = -4090`.
* **No sticking and no re-fire.** The AABB overlaps for 0 or 1 frames and the
  spring's animation goes idle(2) -> fire(3) once.
* **The push-out is not involved** on this face — `Touch_Spring`'s side arm
  launches without pushing (engine/objects/collision.emp).

## Not established

One spring (the LEFT one at 360,584), one character (Sonic), one approach
direction (its launching face), on flat ground. NOT measured: the RIGHT-pointing
spring at (520,536), the back/solid face, an airborne approach, Tails or
Knuckles, and whether 4-5px of overlap is what the owner is actually reacting
to. The inked bound is the outermost non-transparent pixel **on a scanline the
spring also draws on** -- rows where only one of them draws are excluded, since
they cannot produce a visible contact. It is still the outermost pixel, which in
a running pose may be a single-pixel limb, so the dead band figures remain an
UPPER bound on what reads as "touching". Restricting to shared rows moved the
idle player's TRAILING edge (-17 -> -13) and left every leading edge and every
dead-band figure above unchanged.
