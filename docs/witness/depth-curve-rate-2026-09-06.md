# The depth showcase: the A/B, its numbers, and why the confound is NOT closed

Recorded 2026-09-06T15:29:33Z because these figures **travelled in mail as if they were citeable and were
not in any revision of this tree.** The aurora lane's agent went looking for them, could not
find them in any aeon revision it could reach, and said so. They were right: the A/B build
lived in an uncommitted worktree and the measurements existed only in messages. This file is
the artifact they should have been able to cite.

## What was compared

One authored value, in `games/sonic4/data/editor/effects/ojz_act1_depth.json`, layer
`world_y: 160`: `curve.to` **`FACTOR_1` -> `FACTOR_5_8`**. Nothing else changed. Both ROMs
built canonically (`DEBUG=1 ./build.sh`), warped through the ordinary debug mailbox to the
same place, Camera_X **2840** on both.

| | shipped (`crc32 3b542111`) | one value changed (`crc32 0c354c82`) |
|---|---|---|
| lines with a step > 8 px | **66 of 223** | **3 of 223** |
| median non-zero step | **22 px/line** | **6 px/line** |
| total BG travel over 224 lines | 2,559 px | 1,593 px |
| steepest smooth step | 178 px/line | 178 px/line |

## ⚠ WHAT THIS DOES AND DOES NOT ESTABLISH

**It supports RATE as the better account of the visible break.** The rate columns separate the
two builds decisively (66 -> 3, 22 -> 6) while the travel column does not: both stay far above
the 512 px plane width, so a reader shown only travel would conclude the change did nothing.

**IT DOES NOT SEPARATE SPAN FROM RATE AND MUST NOT BE READ AS DOING SO.** Changing a curve moves
excursion and per-line rate **together**. This is one variable moved, not two variables
separated. **The discriminating fixture is still unbuilt** and is named in
`docs/witness/curve-desc-2026-09-06.md`: one scene, two curve bands of span **64 and 192 at the
same per-line rate**.

**The travel-vs-192 model is SUPERSEDED as the account of the visible break** — it remains true
as geometry and is no longer the better-supported explanation. That correction was already made
by the curve-desc parcel this morning; this lane then reached for the superseded model anyway
when describing the fix to the owner, and had to correct it in front of him.

## Why this file exists at all

**A hedge is the first thing a summary drops.** This lane's position — *rate is better supported,
the two are not separated* — reached the aurora lane through a relay as *"the confound is
resolved"*, and they retracted their hedge to an agent in writing on the strength of it before
the original wording came back. **Three hops, each faithful, and the claim strengthened at every
one.** The number in a finding survives a relay; *"this is evidence for, not proof of"* does not.

**So the hedge has to live in a committed artifact, not in the sentence that carries the number.**
That is what this file is for.
