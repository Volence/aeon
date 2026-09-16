# Step 3's gate, and the discriminator that stops it being vacuous

Step 3's own report named the weakness in its gate before I could: **BG-NT-IDENTICAL passing is
consistent with the region path never running.** All ten act-1 rows (eleven in DEBUG) omit
`bg_layout:`, so `rg_bg_layout` is 0 everywhere and `Section_RedrawPlanes` falls through to the
same `Act.act_bg_layout` the old `sec_bg_layout == 0` path reached. **If `Region_Resolve` returned
0 every time, the routine takes the same fallback branch and the picture is identical** — the gate
cannot tell the two apart, and nothing static can.

That is the "a green row that never chose its bed cannot fail" shape, caught by the agent that
wrote the code, which is the right place for it to be caught.

## The gate, on the merged tree

```
  before-s4.debug.bin camera (96, 144) -> (4040, 4088) across the warp
  s4.debug.bin        camera (96, 144) -> (4040, 4088) across the warp
  boot         IDENTICAL  (8192 bytes)
  after warp   IDENTICAL  (8192 bytes)
  third leg: AFTER boot picture ==  zone_bg.bin
VERDICT: PASS
```

BEFORE is the frozen control (`846894 B`, md5 `01295a2407078afd9b8a45645e443010`, master
`8756007f`). AFTER is the merged tree's `s4.debug.bin`, `846912 B`.

## The discriminator — what makes that green mean something

The agent named the check: break at the `jbsr Region_Resolve` inside `Section_RedrawPlanes`, step
over, and read `a0`. I ran it, and then ran it a second time from a different camera, because
**one call returning a real row proves the path runs; it does not prove the path RESOLVES.** A
routine that always answered row 0 would pass the first check and be just as broken.

| when | caller (return address on the stack) | `a0` | means |
|---|---|---|---|
| boot, frame 67 | `$73F8` = `Section_RedrawPlanes.pla_next+30` | **`$018A9E`** | `OJZ_Act1_Regions` row **0** — camera at (96,144), region x 0..2047 y 0..2047 |
| after a DEBUG warp to (4200, 900) | `Section_RedrawPlanes.pla_next+30` | **`$018B64`** | row **9** — the night region, x 3400..4799 y 0..2047 |

`$018B64 - $018A9E = 198 = 9 x 22`, so the second answer is row 9 by arithmetic and not by
assertion. **Two camera positions, two different rows, both returned into
`Section_RedrawPlanes`, neither of them 0.** The caller was verified from the return address on
the stack rather than assumed, because `Region_Resolve` is also called by the parallax crossing
each frame and a breakpoint alone cannot say who called it.

## What is still NOT established

- **That any region shows a DIFFERENT picture.** It cannot be, at this pin: every row defaults its
  layout, so the correct behaviour is that all eleven resolve to the act background. The gate
  asserts no-regression and the discriminator asserts the path is live and discriminating; neither
  asserts the feature, which arrives when a row first authors `bg_layout:`.
- **The warp leg still adds no discrimination to the PICTURE comparison** (the warp sample equals
  the boot sample within each ROM, as in step 2) — but it now carries the discriminator's second
  row, which is new and is the reason to keep running it.
- **`Section_RedrawPlanes`' cache-RECOVERY path**, as distinct from the warp's camera jump. Booked
  since step 2 and still open.
