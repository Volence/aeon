# P-1 famine reach: does the pinned-capacity famine reach real content? (2026-09-28)

Research and measurement parcel for `P1-FAMINE-PINNED-CAPACITY` (docs/DEFERRED_WORK.md). No
engine edit. Branch `research/p1-famine-reach`, base origin/master `2f3e7992`. The measurement
script is research-only, not a gate:
`docs/research/2026-09-28-p1-famine-reach/measure_famine_reach.py`.

## Answer

**No. The famine does not reach any real act, and it cannot while acts go through the current
bakes.** Every bake already counts the bound the booking named, with every pinned page
resident, against `PAGE_FRAMES`, and refuses an act that exceeds it. It also drops any pin
candidate that would push a window over. The famine happens only in the `STRESS_EVICT` fixture.
That fixture runs the committed OJZ tree, whose pins were chosen against 12 frames, with the
runtime clamped to 9 frames. So the fixture breaks the bake's contract; the engine is not at
fault.

Of the ten clip acts, six stream (more pages than frames). All six are at or under 12 of 12
frames with every pin resident, with 0 windows over budget. Four sit exactly at 12. A runtime
flight through `s2_woven`'s 12-of-12 band did not halt (predicted no halt, observed no halt),
and a demand injected at a full window in that same ROM did halt. So in that ROM the detector is
live and the no-halt result has meaning.

## The code that already enforces the bound (MEASURED by reading, lines at `2f3e7992`)

* The count: `tools/fg_page_order.py:584-594`, `window_needed`:
  `needed = sums["unpinned"] + len(pinned)`. Every pinned page is counted in every window,
  whether or not the window names it. That is `|all pins| + unpinned pages in the window`, the
  booking's bound taken at its worst case.
* The pin rule is already frame-aware: `fg_page_order.py:597-611`, `frame_aware_pins`. The 75%
  rule (`ojz_strip_gen.mark_pinned_pages`, `ojz_strip_gen.py:1100`, `PIN_SECTION_FRACTION = 0.75`
  at `:250`) only proposes candidates. Each candidate is kept only if it pushes no window from
  `<= F` to `> F`. `pin_and_count` (`:700`) passes `F = c["PAGE_FRAMES"]`.
* The refusals:
  * clip acts: `tools/clip_act_bake.py:1018-1019` (`fpo.refuse_over_budget(v1, ...)`, with
    `refuse_budget=True` by default at `:957`), reached from every `S2CLIP` build through
    `tools/clip_rom_bake.py:2874`. N2, a recount off disk, has to agree with it (`:1004`).
  * OJZ act 1: `tools/ojz_strip_gen.py:2520` at bake time, and `build.sh:1209`
    (`fg_page_order.py check`) on every canonical build, recounting the committed tree.
  * STRESS_ART: `ojz_strip_gen.stress_pin_pass` (`:1129`), with the same pin pass and refusal.
* The gap: every one of these uses `PAGE_FRAMES`. None uses `PAGE_FRAMES_CLAMP`. The clamp
  differs from `PAGE_FRAMES` only under `STRESS_EVICT` (`engine/system/constants.emp:552-553`),
  and `build.sh` refuses `STRESS_EVICT` together with `S2CLIP` or with any game other than sonic4.

## Per-act table (MEASURED)

Command: bake each clip to a scratch directory, then run the measurement script over OJZ and
over each baked tree.

```
for c in <every dir under games/sonic4/data/clips/>; do
  python3 tools/clip_act_bake.py bake games/sonic4/data/clips/$c/clips.json --out $S/$c; done   # all rc 0
python3 docs/research/2026-09-28-p1-famine-reach/measure_famine_reach.py --ojz $S/<each clip>    # rc 0
```

(The donor trees were copied from the main checkout and left uncommitted; they are gitignored.)
The scratch bake of `s2_woven` has the same `placement` block as the one the `S2CLIP=s2_woven`
build made. The only difference is its `seconds` field.

"Need" is `|all pinned pages ∪ pages the window names|`, in page frames. It is counted over every
distinct 80x60 tile-cache window a camera in the act can hold (`fg_page_order.camera_windows`).
"Over" is the number of windows with need > 12. The camera coordinates are the first worst window
in row-major order, using `budget_verdict`'s own formula.

| act | pages | streams? | pins (rule → kept) | windows | worst need / 12 | windows at worst | over 12 | first worst camera (x, y) px |
|---|---|---|---|---|---|---|---|---|
| s2_woven | 49 | yes | [0, 48] | 599,511 | **12** | 673 | 0 | (4648, 2352) |
| s2_woven_2d | 23 | yes | [0] | 257,367 | **12** | 2,816 | 0 | (3448, 832) |
| s2_mtz_cpz | 16 | yes | [0] | 257,367 | **12** | 2,792 | 0 | (3448, 832) |
| s2_two_clip | 17 | yes | [0] | 48,471 | **12** | 682 | 0 | (1880, 208) |
| s2_ehz_cpz | 17 | yes | [0] | 722,007 | 11 | 4,631 | 0 | (14856, 880) |
| s2_two_clip_pins | 13 | yes | [0, 4] | 48,471 | 10 | 1,771 | 0 | (3496, 624) |
| s2_wfz_solo | 10 | no (fully resident) | [0] | 257,367 | 10 | 1,555 | 0 | (5312, 432) |
| s2_ehz_boot | 8 | no | [0] | 443,223 | 8 | 5,059 | 0 | (4392, 256) |
| s2_ooz_solo | 8 | no | [0] | 257,367 | 8 | 13,432 | 0 | (1408, 0) |
| s2_hpz_solo | 5 | no | [0] | 257,367 | 5 | 3,618 | 0 | (1864, 944) |
| ojz/act1 (committed) | 10 | no at 12; yes at the STRESS_EVICT clamp of 9 | [0, 1, 7, 8, 9] | 257,367 | 10 | 3,366 | 0 (3,366 over **9**) | (744, 0) |

In every clip act the 75% rule's candidates and the kept pins are the same set. The frame-aware
pass dropped nothing. The rule proposes only page 0 except in `s2_woven` (page 48) and
`s2_two_clip_pins` (page 4).

**A correction to the brief:** the solo clips (`s2_ooz_solo`, `s2_wfz_solo`, `s2_hpz_solo`) and
`s2_ehz_boot` do NOT stream. They have 8, 10, 5 and 8 pages, all within 12 frames.

### Over-count at smaller frame budgets (for the C4-3 floor question, MEASURED, same run)

Windows over F, first with every pin resident, then (in brackets) with only the pins the window
names:

| act | F=11 | F=10 | F=9 |
|---|---|---|---|
| s2_woven | 673 [673] | 9,421 [4,657] | 37,995 [16,765] |
| s2_woven_2d | 2,816 | 9,746 | 14,261 |
| s2_mtz_cpz | 2,792 | 9,632 | 13,218 |
| s2_two_clip | 682 | 2,155 | 3,573 |
| s2_ehz_cpz | 0 | 4,631 | 14,019 |
| s2_two_clip_pins | 0 | 0 | 1,771 |
| s2_wfz_solo | 0 | 0 | 1,555 |
| ojz/act1 | 0 | 0 | **3,366 [0]** |

These are counts for the placement as baked at F = 12. At a smaller F the bake would re-place
and re-pin, and that re-bake was not run. So they are not what the acts would need after a
re-bake at that budget.

## Question 3: all pinned pages resident, or only those demanded so far?

At runtime, the pinned pages that are resident depend on history. A pinned page takes a frame
permanently the first time it is published, whether a demand or a prefetch brought it in
(`PageCache_Publish` applies `pm_flags` whatever the request class). The 2026-08-10 root-cause
note saw pages 8 and 9 arrive by prefetch. So the true need is `|pins published so far ∪
window|`. It lies between two counts: pins counted only where the window names them (the best
case) and every pin counted (the worst case, which is what the bakes use).

How pessimistic the worst case is (MEASURED, same run):
* **Clip acts:** the peak is the same either way in every act. In `s2_woven` the two counts
  differ in 135,892 of 599,511 windows, by at most 1 page, and never at the peak. In
  `s2_two_clip_pins` they differ in 13,710 windows, by at most 1. In the other acts the only pin
  is page 0, which is bulk-loaded at init and resident from frame 0, so the worst case is exact.
* **OJZ under the STRESS_EVICT clamp of 9:** with every pin counted, 3,366 windows are over 9.
  With only named pins, 0 are over. So the fixture's famine comes entirely from history: once
  page 9 is resident (the OUT leg), its frame is never freed.

A worst case you can reach after visiting (or prefetching) each pin once is the right bound for
a streaming act, because nothing stops a route from doing that. The bakes use it.

## The transient: a fill mid-step (MEASURED count, INFERRED model)

When the tile cache steps one column, it overwrites the ring column that the departing column
held. When it steps rows, it does two rows at a time (the window top is even-rounded). A
demand-stalled fill resumes at the stalled cell (`tile_cache.emp`, `Cache_Art_Stall`). So at any
instant the named set is inside the union of the old window and one step of the new one, per
axis. That is an 81x60, 80x62 or 81x62 window (INFERRED from the fill's structure; the per-cell
write order was not traced). Counted with every pin resident at the same window population:
**every act, every shape: 0 windows over 12, and the peak is unchanged.** To show the count can
tell these cases apart, `s2_woven` gives 0 over at 81x60 but 429 over at 88x60 and 2,498 at
96x76.

Not covered, as `fg_page_order` says: object and sprite art, the BG plane and animated tiles
(these do not use FG page frames). There is only one in-flight decode at a time: the page-in
FIFO has a single staging slot, per the `page_in.emp` header, so a detached in-flight frame is
always the one the current request allocated.

## Runtime confirmation (MEASURED, headless oracle-aether subprocesses, no MCP)

No act is over budget, so there was no predicted halt to confirm in real content. Instead, one
at-budget act was flown, together with the fixture as the control.

1. **Real content, predicted no halt: `s2_woven`**, the only streaming clip with a non-zero pin.
   `S2CLIP=s2_woven DEBUG=1 ./build.sh` gave rc 0 and `s4.s2clip.debug.bin` crc32 `0b8c65d7`.
   Then:
   `python3 tools/prefetch_full_window_witness.py --rom s4.s2clip.debug.bin --lst s4.s2clip.debug.lst --baked games/sonic4/data/clips/s2_woven/baked`
   gave rc 0 (`finished=2`). The route it derives from the bake: 673 windows need 12 of 12, and
   the flight runs at camera y 2528, x 4392..7480 (the band is 4648..7416), holding RIGHT one
   frame in 3.
   * Arm A: 580 frames with **no halt**. 32 frames had every one of the 12 frames named (a full
     window), 30 prefetches were dropped for want of a frame, and there were 0 residency-invariant
     violations.
   * Arm B: a DEMAND was injected at the first full window (frame 52, camera x 4680), and the
     ROM **halted** on `PageCache_AllocFrame: no free/evictable frame (thrash bug)`. So in this ROM
     the demand detector fires, and Arm A's missing halt is real evidence rather than a blind
     spot.
2. **Control: the fixture, predicted halt, halt observed.** `STRESS_EVICT=1 ./build.sh` gave
   rc 0 and `s4.stress.bin` crc32 `5863cf9d`. Then `python3 tools/evict_witness.py
   --famine-probe` gave rc 0. It predicted the famine at camera x 1376 (window [0, 2, 3, 4, 5, 6, 7]
   plus pins [0, 1, 7, 8, 9] = 10 pages for 9 frames) and **HALTED** at camera (1376, 144) while
   demanding page 5. At the halt, frames 0/1/2/7/8 held pinned pages 0/1/9/7/8, frames 3..6 held
   pages 2/4/3/6, and the nametable named frames [0, 3, 4, 5, 6, 7]. This is identical to the
   booking, which was measured at `7e677683`.
3. **The fixture with the frame-aware pin pass run at 9 instead of 12, predicted no halt.**
   `frame_aware_pins` with F=9 over the committed OJZ grid keeps pins [0, 1, 7, 8] and drops 9,
   giving a worst need of 9 of 9 and 0 over (MEASURED, a one-off script over `fg_page_order`).
   As a throwaway, page 9's `pm_flags` was set to 0 in `ojz_act_pool.emp`, together with its
   sidecar entry, because `verify_level_bin` refuses a flag that disagrees with the sidecar.
   Nothing else changed. `STRESS_EVICT=1 ./build.sh` gave rc 0 and crc32 `49750c7f`. The
   unmodified `--famine-probe` predicted nothing and did not fly. A scratch copy of
   `evict_witness.py`, modified only to force the famine flight, flew left to camera x 0: **no
   halt**, 5 evictions in total, and page 9 evicted by the end. Both files were restored with
   `git show HEAD:<path> > <path>` and the scratch copy was deleted. The tree is clean apart from
   this note.

## Design options (written, not built)

**O1. Close the entry for real content and do nothing in the engine.** The bound is already a
bake-time refusal on every act path (clip bake N1/N2, OJZ Pass 4 plus `fg_page_order check` on
every build, STRESS_ART Pass 4c), and the pin rule already respects the budget. That is the
2026-08-10 root-cause note's option 1 ("build-time bound emission"), and it is built. Cost: none.
What it fixes: the question itself. What stays open: only the fixture.

**O2. Make the STRESS_EVICT fixture honour its own clamp: run the pin pass at
`PAGE_FRAMES_CLAMP`.** Measured above: this drops pin 9 and removes the famine (static count 9
of 9, runtime no halt to x 0). Two ways to build it:
* O2a: make STRESS_EVICT a re-bake shape like STRESS_ART, with a `--pin-frames` argument passed
  to `frame_aware_pins`. About 20-40 lines across `ojz_strip_gen.py` and `build.sh`, 0 canonical
  bytes, and a small extra re-bake in the stress shape (the cached `regenerate-level.sh` is
  about 1 s).
* O2b: have the generator emit a pin that fits at `PAGE_FRAMES` but not at the clamp as a
  comptime flag (`pm_flags: 1 - STRESS_EVICT`), and teach `verify_level_bin`'s sidecar check the
  same rule. 0 canonical bytes, 1 byte in the stress ROM, no new shape.

Side effect for both: `evict_witness --famine-probe` then predicts nothing. The P-1 famine stops
being a behaviour of the fixture, and the probe has to be retired or re-aimed (for example, as
a red-first mutation that restores the pin).

**O3. A guard with no fix: count against `PAGE_FRAMES_CLAMP` in the STRESS_EVICT shape.** Run
`fg_page_order check` at the clamp there. Today it would REFUSE the fixture (3,366 windows over
9), so O3 cannot land without O2. It is the guard that keeps O2 honest if the pins or the clamp
move again. The clamp was calibrated against 4 pins (the `constants.emp` comment at
`:516-520`), and the committed tree now has 5. About 10 lines in `build.sh` and
`fg_page_order.py`.

**O4. Engine: demote a pin under demand pressure.** When a DEMAND finds no candidate, fall back
to the oldest pinned frame no cache word names. This changes `PageCache_PickVictim`: about 10-20
instructions, a few dozen ROM bytes, 0 RAM. It would fix the fixture and any future
bake/runtime mismatch. But it changes what "pinned" means, duplicates a guarantee the bake
already gives, and adds a path that no real act can reach, so it could not be tested except by
the fixture. Not recommended.

**The DEBUG raise on a demand: keep it, it is a bug detector.** The bake guarantees `|all pins ∪
window| <= PAGE_FRAMES` (and the one-step transient union, measured above). So a demand that
finds no frame means that guarantee was broken, which is either a contract violation (today,
only the fixture) or a wrong model. Arm B shows it is live. Release re-queues the demand every
frame. That is INFERRED to be a permanent camera hold while the window stays put, because nothing
frees a frame. Changing that path is only worth doing if O4 is.

**Is the `vram.toml` C4-3 floor (640 tiles / 10 frames) this bound? No.** The floor's comment
(`games/sonic4/vram.toml:23-26`) justifies it as "tight-cache mode has an open defect (the
STRESS_EVICT famine)". Measured here, that "defect" is the fixture breaking the bake's contract.
The real bound is per act, and every bake enforces it at whatever `PAGE_FRAMES` is. What limits
lowering `PAGE_FRAMES` is content: as placed today, 4 of the 6 streaming acts need 12 frames
(over at 11: 673 / 2,816 / 2,792 / 682 windows), and at 10 frames five of the six are over. A
re-bake at the lower budget might fit some of them; that was not measured. Recommendation for
the owner: rewrite the comment's reason as "the streaming clip acts need 12 frames as placed"
(or re-measure with re-placement) instead of citing a defect. This is a comment in a file this
parcel does not own, so it was left alone.

## Recommendation

**O1 for real content (close it: not reachable), plus O2b and O3 together for the fixture.**
Reasons: the real-content guarantee already exists and runs on every build path, so no engine
work is justified. The only place the famine exists is a fixture that clamps frames without
re-pinning, and the cheapest honest fix is to pin at the fixture's own budget (O2b: 0 canonical
bytes, no new build shape). O3 then turns any future clamp/pin drift into a build refusal rather
than a nightly halt. For the mega-act, the guard that keeps real content safe is already loud:
`fg_page_order._known_acts` raises on an act the committed-tree decoder does not know, and a
clip act is refused by its own bake. Any new act generator has to go through `place_pool` (or
`place_fixed_pool`) and `refuse_over_budget`. That one sentence belongs in the generator
checklist. The code already does it.

## Files and numbers

* Research script (not wired, exit 0 measured / 2 unmeasurable, with a built-in control that
  fails loudly if the booked famine window is not over 9):
  `docs/research/2026-09-28-p1-famine-reach/measure_famine_reach.py`.
* ROMs (gitignored, not committed): `s4.s2clip.debug.bin` `0b8c65d7`; `s4.stress.bin`
  `5863cf9d` (control) and `49750c7f` (the throwaway with page 9 unpinned; that is the
  `s4.stress.bin` left on disk in the worktree, while the source tree is restored).
