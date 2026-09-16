# Regions part 2, step 5 — steady-state streaming, and the end of four steps of vacuity

Parcel `parcel/regions-p2-step5`, based on aeon `origin/master` `56f6fcb4`.

**WHICH STEP 5.** REGIONS **PART 2**'s, the owner's sequence, applied by the hub and readable at
empyrean `origin/main:docs/OVERSEER.md` ("steps 1 to 6 in order ... **steady-state streaming**,
the wipe"). **NOT** `docs/superpowers/designs/2026-09-09-regions-v1-design.md` §4's step 5
("author one sub-section edge"), which is a different piece of work and is long done. The two
schemes collide, both say "step 5", and the collision has already cost this project time — the
spec itself carries a banner about it. Every "step N" below is part 2's.

Spec: empyrean `origin/main:docs/superpowers/specs/2026-09-14-regions-part-2-design.md` §4.2
("Steady-state streaming") and step-table row 5.

**No emulator was used, and the step's own gate needs one.** BG-TALL's nametable half is
UNMEASURED and TAGGED, with its full procedure and derived expectations booked in
`docs/DEFERRED_WORK.md`. What IS measured is stated as measured; what is arithmetic over ROM
bytes is labelled arithmetic; nothing here claims a picture.

---

## The finding this parcel exists for

**Step 4's ledger handed me a vacuity problem and it was the whole job.** In its words: all ten of
act 1's region rows leave `rg_bg_span` at 0, so the fallback is taken on every frame of every
shipped act and the clamp's observable behaviour is identical to the pre-step-4 code — *and
authoring the honest value would not change that*, because the background map IS the plane, so an
honest span is `PLANE_B_SPAN` = 512, whose ceiling is `512 - 224 = 288`, which is exactly
`VSCROLL_BG_MAX`.

So four steps of machinery — the record's two fields, the row-major flip, `Draw_BG_TileRow`, the
region-aware blits, the derived clamp, the rate clamp — sat on a tree where **no input existed
that could tell the new code from the old.** `Draw_BG_TileRow` had no caller because there was no
row to stream. The clamp had a reader that always took the fallback.

**The centre of this parcel is therefore the 96-row map, not the tracker.** The tracker is ~110
bytes of straightforward arithmetic. The map is what makes any of it measurable, and everything
below is organised around not letting the measurement be fake.

---

## What landed

| what | where |
|---|---|
| `BG_Stream_Update` — the steady-state window tracker; `Draw_BG_TileRow`'s FIRST caller | `engine/level/bg.emp` |
| four derived constants + four `ensure`s, **all four proven red individually** | same file |
| wiring at the three `jbsr Parallax_Update` sites (boot, per-frame, warp) | `games/sonic4/test/ojz_scroll_test.emp` |
| the 96-row DEBUG-only map (12288 B) + its generator with a non-vacuity assert | `tools/gen_tall_bg_test.py`, `games/sonic4/data/generated/ojz/act1/zone_bg_tall_debug.bin` |
| the DEBUG-gated embed, typed by its size | `games/sonic4/data/levels/ojz/act1/act_assets.emp` |
| the DEBUG-only region row, carved out of rows 5 AND 8 | `games/sonic4/data/levels/ojz/act1/act_descriptor.emp` |
| GATE BG-TALL, ROM-side: six legs, **six red-first proofs**, three tests green | `tools/test_bg_tall_map.py` |
| two lanes my own insertion broke, fixed at the FORM | `tools/test_lab_index_lint.py`, `engine/level/parallax.emp`, `engine/ram.emp` |
| a DANGLING citation replaced with a re-verified primary source | `engine/level/plane_buffer.emp` |
| doc sync + three bookings | `docs/ENGINE_ARCHITECTURE.md`, `docs/DEFERRED_WORK.md` |

---

## Research first, per the standing practice

Ten reference disassemblies plus the online sources, dispatched as a read-only sweep. **8 of 10
stream nametable rows; 7 stream rows vertically into a ring.** What I took and what I rejected:

**TAKEN**

* **The stored-tracker-plus-delta trigger**, which is what S3K (`Camera_Y_pos_BG_rounded`,
  `sonic3k.constants.asm:415-417`), S.C.E., Vectorman (`$26(a0)`), Ristar (`$FFF0B4`) and
  Batman & Robin (`$34(a6)`) all use. Confirms `BG_Plane_Top`'s existence was the right call in
  step 3.
* **Full plane width per row entry.** All seven `Draw_BG` call sites in S3K pass `moveq #$20,d6`
  = 32 blocks = 512 px, where the FG streamer passes `#$15` = 352 px. The asymmetry is because
  Plane B's horizontal scroll is per-band and wanders, so a screen-width row is *wrong* for some
  band, not merely wasteful. `Draw_BG_TileRow`'s 132-byte full-width entry is right; do not
  "optimise" it.
* **The band X as a caller-supplied constant.** SSZ1 streams its second background at a constant
  layout X of `$1C00` (`sonic3k.asm:116538`), SSZ2 at `moveq #0,d1` (`:118011`). Step 2's
  deviation from the spec's arity — carrying the X as an argument rather than looking it up — is
  the shipped reference shape. This also let me replace a dangling citation with a real one.
* **A lead, not the entering row.** Universal: S3K/S.C.E. `+$F0`, S2 `+224`, Vectorman `+14 block
  rows`, Ristar `+$100`, SGDK `+ROW_AHEAD`.

**REJECTED, with reasons**

* **S2's 1-bit parity latch** (`eor` bit 4 into `Verti_block_crossed_flag_BG`, `s2.asm:18374`).
  It carries no magnitude: it cannot represent a 2-row frame and silently drops crossings. It is
  only correct because S2's camera clamp makes >16 px impossible. `sonic_hack` inherited it and
  it is dead code there.
* **Gunstar's dirty-flag / TF4's counter triggers**, for the same reason: no magnitude, so they
  cannot distinguish 0, 1, 2 and 64 rows owed — and **0 (a prime) and 64 (a sweep) are exactly
  the two states this engine's RAM already declares fields for.**
* **Recomputing the plane row from the camera with no tracker** (Gunstar, Alien Soldier, S2).
  Works there because their BG position is a pure function of the camera. `Parallax_Current_
  Vscroll_BG` is not: a bob, a lerp, a position clamp and a rate clamp sit between it and
  `Camera_Y`, and it can differ from the camera-derived value for many frames. A recompute would
  fight the rate clamp every frame.
* **S3K's byte-sign delta test.** Its subtraction happens in a `$FF0`-masked space and it picks
  the sign with `tst.b d2` — correct only for `|delta| < $80`, a hazard S.C.E. inherited verbatim
  (`Draw Level.asm:317`). Our scroll is clamped to `[0, span-224]` and never wraps, so a plain
  signed `sub.w`/`cmp.w` is correct with no seam case. Not ported.
* **The `andi.w #$30` double-update shape.** A 2-row cap spelled as a mask; at 3 blocks it
  silently draws the wrong rows.

**Two things our situation makes easier than any reference's, both load-bearing below:** the plane
is 512×512 where every reference's is 512×256, so **36 cell rows are permanently off-screen**
against S3K's 2 — which is what makes a 17-row centred lead affordable; and `PLANE_V_CELLS` is a
power of two, so the ring is `m & 63` and `BG_Plane_Top` serves as both map tracker and plane
tracker (Batman needed two variables and a wrap compare because its plane height is chosen at
runtime).

---

## The tracker

```
want_top = clamp( (vscroll >> 3) - BG_STREAM_LEAD_ROWS,  0,  map_rows - PLANE_V_CELLS )
```

### 1. The ring is free, and it is the only thing worth reading first

The VDP maps screen line `L` to plane line `(L + vscroll) mod PLANE_B_SPAN`, so **the plane row
showing map row `m` is always `m mod PLANE_V_CELLS`** — no rebasing, no mapping table, no seam
case. The whole of streaming is therefore one question: *which 64 consecutive map rows does the
plane hold?* That is `BG_Plane_Top`, which step 3 seeded and this proc is the only mover of.

### 2. ANCHORED, not hysteretic — and reason 2 is the engineering one

A hysteretic tracker ("move only when a visible row falls off the window") has **zero slack in the
direction of travel by construction**: the row it must draw is the row that just became visible,
so one refused entry — plane buffer full that frame — is a garbage row *on screen*. The anchored
form with a centred lead has 17 rows above and 18 below, so a refusal is invisible and self-heals
next frame. It also needs no direction state and has no hysteresis edge cases.

Reason 3 was not in the plan and is worth having: **it absorbs a region crossing.** Crossing into
the tall row makes `max_top` jump 0 → 32 in one frame, so `want_top` can jump by up to the lead at
once. I checked the containment bound at every intermediate `BG_Plane_Top` on the way: entering at
camera Y 2048 the visible rows are 24..52 and the plane holds 0..63, so the catch-up from top 0 to
top 7 is **invisible**, not a tear step 6's wipe has to hide.

### 3. It cannot fall behind, and that is step 4's rate clamp doing this job

`want_top` is monotone in `vscroll` with slope 1/8, and step 4 bounds `|Δvscroll|` by
`BG_VSCROLL_MAX_STEP`. So `|Δwant_top| <= BG_VSCROLL_MAX_STEP / BG_VSCROLL_ROW_PX =
BG_STREAM_MAX_ROWS` — **exactly** the per-frame budget. The tracker never accumulates debt. This
is not "fast enough in practice", it is bounded by construction, and it is why the clamp had to
land before the streamer rather than after. The `ensure` that ties the two together fires if
either constant moves in either direction.

The reference sweep says the same thing in every engine: **every one of them derives its row
budget from its camera speed clamp.** S3K: 24 px/frame ⇒ `andi.w #$30` + one double-update ⇒ 2
rows. S2 and Ristar: 16 px/frame ⇒ 1 row. Sik's advice on SpritesMind is the same sentence: "do
like Sonic and put a cap on the camera's speed."

### 4. The containment proof, which is what the `ensure`s pin

The screen shows map rows `[vrow, vbot]` with `vbot <= vrow + BG_SCREEN_ROWS - 1`; the plane holds
`[top, top+63]`. Containment needs `0 <= LEAD <= PLANE_V_CELLS - BG_SCREEN_ROWS` (= `[0, 35]`
today, and LEAD is 17). At the **low** clamp `top = 0` and `vrow <= LEAD`, so `vbot <= 44 <= 63`.
At the **high** clamp `top = map_rows - 64`, and the largest legal `vscroll` is `span -
SCREEN_HEIGHT`, whose `vbot` is exactly `map_rows - 1 = top + 63`. **The two clamps meet the two
bounds exactly** — the position clamp of step 4 is not merely compatible with the window rule, it
is the same arithmetic from the other end.

### 5. A bug caught in the writing, recorded because it builds green

`moveq` **writes the condition codes.** Both `moveq` must precede the `cmp.w` whose flags the
`beq` and the `blt` read. My first draft had the order

```
        cmp.w   d6, d4
        beq     .done
        moveq   #BG_STREAM_MAX_ROWS, d5
        moveq   #1, d7
        blt     .loop            <-- tests the MOVEQ, not the CMP
```

which assembles cleanly, passes every gate in this parcel, and walks the window the **wrong way**
on every downward traversal. It is fixed and the site carries the reason in three lines so the
next person to reorder those instructions is told what they cost.

### 6. Refusal handling

`Draw_BG_TileRow` returns whether the entry was admitted, which is the one deliberate difference
step 2 built into it. `BG_Plane_Top` advances on a `1` and only on a `1`; a refusal stops the
frame's work with the window where it was. Headroom, measured rather than quoted:
`PLANE_BUFFER_SIZE` is 1536 B (`engine/system/constants.emp:877`) and a BG row entry is 132 B, so
two of them are 264 B.

---

## The map, and why the rectangle is the rectangle

**Two requirements, and only their conjunction is a discriminator.** This is the part I got wrong
first and had to re-derive.

* **THE BACKGROUND MUST MOVE.** Eighteen of the twenty OJZ scenes author `v_factor: 15` — a
  LOCKED plane that ignores the camera entirely. A tall map under a locked scene streams nothing,
  ever: an instrument that cannot produce the answer it claims to look for, which is step 2's and
  step 3's finding-2 shape for the third time. The tall row binds **no** parallax and
  `OJZ_Preset_Plain`, which binds none either, so `Effects_ResolveParallax`'s
  `rg_parallax > ep_parallax > act default` ladder lands on `ParallaxConfig_OJZ_Default` —
  `v_factor 3 / v_center 512 / v_offset 0`, one of only two unlocked configs in the act.
* **THE CAMERA MUST REACH HIGH Y.** With that mapping the scroll is `(camY - 512) >> 3`, so
  beating the OLD ceiling (288) needs `camY > 2816`. **That rules out the whole y 0..2047 band —
  including the DEBUG-only region row that already exists.** My first instinct was to hang the
  tall map on `OJZ_E2_SNAP_ROWS` (x 5600..6143, y 0..2047), which costs no new row and no re-cut
  tiling proof. Its scroll tops out at **191**, below both ceilings, so the two clamps could never
  disagree there and the cheap option was the vacuous one.

So: **a new DEBUG-only row at x 5120..6143, y 2048..6143**, carved out of the right end of rows
5 AND 8 by exactly the mechanism `OJZ_E2_SNAP_ROWS` uses on row 2's.

### ⚠ AND THE FIRST CUT OF IT WAS HALF A TEST, which I found by deriving rather than by trusting a green

The rectangle was `y 2048..4095` at first — one section row, one carve. It reaches raw BG scroll
**192..447**, which is enough to make the two clamps **disagree** (the old ceiling 288 binds, the
new 544 does not), and leg 3 measured that disagreement honestly: 26 window tops against 13.
**But 447 < 544, so the NEW ceiling was never once the thing that stopped the scroll.** Testing a
clamp only where it does not clamp leaves the line that does the clamping ungraded — and that line
is step 4's entire subject. It also left step 4's own BG-RATE gate vacuous for the same reason,
which is the thing this parcel was supposed to end.

Extending to `y 2048..6143` reaches raw scroll **703**, so the new ceiling binds over the last
~1280 px of camera travel while the window tops still sweep 7..32.

| rectangle | raw scroll | old ceiling 288 binds | new ceiling 544 binds |
|---|---|---|---|
| y 2048..4095 (first cut) | 192..447 | YES | **NO** |
| y 2048..6143 (shipped) | 192..703 | YES | **YES**, from camera Y 4864 |

**Leg 3b is kept SEPARATE from leg 3 deliberately.** "The two clamps disagree" and "the new
ceiling actually constrains" are different claims, and the first can be true while the second is
false — which is exactly the state this fixture was in. A single merged assertion would have gone
green on it.

It reuses row 8's shipped `OJZ_Preset_Plain`, so palette, raster program and variants under the
rectangle are a shipped look and the **only** thing that differs from its neighbour is the
background map and its span.

### The row marker is a non-vacuity device, not decoration

The plane is a 64-row ring, so map row `m` is shown by plane row `m mod 64`. A gate that reads the
nametable can only say **which** map row a plane row holds if rows `p` and `p+64` differ — and
over a sky-heavy background, full of identical blank cells, they often would not. Rows 64..95 of
the test map repeat shipped rows 32..63 (real art, real tiles, no new tile budget), and cell 0 of
every row carries tile `1024 + row`. **`tools/gen_tall_bg_test.py` asserts all 96 rows are
pairwise distinct before writing**, and the gate asserts it again on the committed blob. Without
it, "the streamer never ran" and "the streamer ran correctly" could read identical.

### DEBUG-only, checked on bytes

`if DEBUG == 1 { embed(..) } else { [] }` — the shape `OJZ_Preset_NightSnap` uses. Verified: the
blob and a 64-byte probe of its row 64 are **both absent from `s4.bin`**, and no release region
row carries a span.

---

## GATE BG-TALL, ROM-SIDE — six legs, and what each accepts

`tools/test_bg_tall_map.py`. The subject is not "does the streamer work"; it is the prior question
that has been silently answered NO for four steps: **is there anything on this tree that the new
code behaves differently on than the old code would?**

| leg | claim | accepts |
|---|---|---|
| 1 | a DEBUG region row declares `rg_bg_span > PLANE_B_SPAN` | spans in (512, ∞). **Refuses the entire space every earlier tree occupied**, including the "honest" 512 |
| 2 | that row's layout is the committed 12288-byte blob (md5) **and its 96 rows are pairwise distinct** | — |
| 3 | the window tops the tracker visits, computed from the ROM's own bytes, differ between the new and old ceilings | nothing on any earlier tree, where both are `{0}` and equal |
| 3b | the new ceiling is REACHED, i.e. some camera Y in the region drives raw scroll above it | rectangles that reach past the ceiling. **Refuses this parcel's own first cut** |
| 4 | release carries no span and no part of the blob | — |
| 5 | `BG_Stream_Update` is the target of a real `jsr abs.l` **or** `bsr.w` in the image | — |

**Leg 3's measured output, at `s4.debug.bin` crc `936ac15c`:**

```
row 11 [x 5120..6143, y 2048..4095] span 768 (96 rows), cfg 0x134e8
       v_factor 3 v_center 512 v_offset 0, lead 17, max_top 32
  window tops NEW ceiling 544: 7..32 (26 distinct)
  window tops OLD ceiling 288: 7..19 (13 distinct)
  raw vscroll reaches 703; the NEW ceiling 544 BINDS from camera Y 4864 (leg 3b)
```

Twenty-six against thirteen. Leg 5: `BG_Stream_Update` at `0xa6ca`, **3 call sites**.

**Leg 5 counts two encodings on purpose.** `jbsr` is what `.emp` spells and sigil relaxes by
reach, so a checker that knew only `jsr abs.l` would report "never called" on perfectly wired code
the day a section moved. It counts `bsr.w` too.

**WHAT A GREEN DOES NOT SAY, and it is the sentence that matters.** Nothing about the picture.
Every leg reads ROM bytes and arithmetic over them; not one observes the VDP. **A build that
computes the right window and writes it to the wrong VRAM address passes all six.**

### An assertion I wrote and then deleted

Leg 1 originally carried `assertNotEqual(new_ceiling, old_ceiling)`. With `old_ceiling =
PLANE_V_CELLS*8 - SCREEN_HEIGHT` and the leg's own predicate already requiring `bg_span >
PLANE_V_CELLS*8`, the inequality follows by subtraction and **the assertion could never fire.**
Shipping a check that cannot fail *inside the gate against vacuity* would have been the joke
version of this parcel. Deleted, with the derivation left at the site saying why the implication
is the coverage.

---

## Red-first evidence

### The strongest leg: the UNMUTATED gate run against a tree WITHOUT the change

Not a mutation — the real thing. `/home/volence/sonic_hacks/.aeon-p2s5-base`, a detached worktree
at `56f6fcb4`, built with its own `FAST=1` / `FAST=1 DEBUG=1` (s4.bin 820606, s4.debug.bin
846986), with only `tools/test_bg_tall_map.py` and the blob copied in.

```
2 failed, 1 passed
  FAILED test_a_region_declares_a_map_taller_than_the_plane
    AssertionError: [] is not true : NO region row in the DEBUG act declares a background
    map taller than the plane. 11 rows read, spans present: [0] ... PLANE_B_SPAN is 512.
  FAILED test_the_tracker_is_called
    AssertionError: 'BG_Stream_Update' not found in {...}
```

**Leg 4 passes there, correctly** — it is a non-regression leg and the old tree genuinely carries
no tall map. A gate all of whose legs went red on the old tree would have been telling me less,
not more.

### Per-leg mutations, each applied on disk from a COMMITTED baseline and quoted back

| # | mutation | rebuilt? | result |
|---|---|---|---|
| M3 | one byte of the blob flipped (`b[4000] ^= 0xFF`), **NOT** rebuilt | no | leg 2 RED: `'1bdb5d88…' != '05081c3b…'` |
| M2 | blob row 64 := row 0, **then rebuilt** (crc `326fc5ba`) | yes | leg 2 RED: `map rows [(0, 64)] are byte-identical` — and the md5 leg PASSING is what proves the mutation reached the ROM |
| M4 | the three `jbsr BG_Stream_Update` commented out, rebuilt (crc `d35dc887`, len 847138) | yes | leg 5 RED: `0 not greater than or equal to 1 ... NOTHING in the ROM calls it` |
| M5 | `if DEBUG == 1` → `if 1 == 1` on all four gates, release rebuilt (crc `c28c5bdb`, len 820772) | yes | leg 4 RED: `release region rows declare non-zero spans [(10, 768)]` |
| M6 | the tall row's `y1` back to 4095 **and** row 8's carve reverted (the tiling proof needs them together), rebuilt — **crc `936ac15c`, byte-identical to this parcel's own pre-extension build**, which is what proves the mutation reproduced that state exactly | yes | leg 3b RED: `the new ceiling 544 is never REACHED ... the largest raw scroll ... is 447` |

**M5 was run twice and the first attempt is recorded because it nearly passed as evidence.** My
marker comment `//MUT` was appended *inline*, which swallowed the rest of each `.emp` line; the
build **failed with parse errors** and pytest then graded a **stale ROM from M4**, reporting leg 5
red instead of leg 4. The verdict looked like a red-first pass and was an artifact. What caught it
was reading the build output beside the test output rather than only the test's colour. Redone
with the marker on its own line, the build succeeded and the intended leg went red.

### The four new `ensure`s, each proven red individually with its own message

Four `FAST=1 DEBUG=1` builds, mutation quoted from disk each time, tree restored from HEAD between
runs. All four exited 1, and — checked rather than assumed — each fired **its own** text with
correctly computed values:

| mutation | message observed |
|---|---|
| `BG_SCREEN_ROWS + 100` | `the Plane B ring holds 64 rows and the screen can touch 128 ... (BG_STREAM_SPARE_ROWS = -64)` |
| `LEAD = SPARE + 1` | `BG_STREAM_LEAD_ROWS is 36, outside [0, 35]` — **alone**, which is the clean single-ensure firing |
| `MAX_ROWS - 1` | `can move the window 1 row(s) = 8 px a frame, but ... the rate clamp lets the BG scroll move 16 px` |
| `MAX_ROWS = 0` | `... 0 row(s) = 0 px a frame ...` **and** `BG_STREAM_MAX_ROWS is 0 — the streamer is allowed no rows at all` |

Tree restored, rebuilt to crc `936ac15c` — the same CRC as before the campaign.

### The widened lint, proven red on its NEW term specifically

`test_lab_index_lint`'s arity parser accepted `<int> + <NAME>` and the table is now `10 +
OJZ_E2_SNAP_ROWS_LEN + OJZ_TALL_BG_ROWS_LEN`. Widened to one-or-more terms. **This is not a
loosening and I measured it rather than asserting it:** giving `OJZ_TALL_BG_ROWS` a non-empty
`else` branch fails with `` `OJZ_TALL_BG_ROWS` is not the `if DEBUG == 1 { .. } else { [] }` shape
... there is no minimum to bound it by``. N terms need N proofs, and the second one is graded.

---

## Two lanes this parcel broke, and they were mine

Found by **running** the pre-build lane, not by review.

1. **`test_citation_form`.** Inserting `jbsr BG_Stream_Update` pushed two citations of
   `ojz_scroll_test.emp:1207` onto a blank line — `parallax.emp`'s clamp note and `ram.emp`'s
   `Region_Current` note. Both re-cited **by name** ("the `jbsr Parallax_CheckBoundary` stands
   above the `jbsr Parallax_Update` in `GameState_OJZScroll_Update`"), which is what the gate's own
   message and `CODING_CONVENTIONS.md`'s CITE BY NAME rule prescribe. **Step 4's ledger recorded
   this exact class** after its own +28 lines did it to three citations. It is not a coincidence:
   any parcel that inserts lines into a cited file does this, and the only durable fix is the form.

2. **`test_lab_index_lint`**, above.

### And a dangling citation that was NOT mine

`Draw_BG_TileRow`'s header cited `docs/research/2026-09-14-s3k-wide-background-bands.md §5`. **That
file does not exist in this tree and `git log --all --diff-filter=A` finds no commit that ever
added it** (I verified both firsthand before acting on the sweep's report). The *claim* it
supported is correct — re-verified at `skdisasm/sonic3k.asm:103289-103308` — **which is exactly
why nothing caught it: a wrong pointer to a true fact reads as evidence.** `test_citation_form`
cannot see it; that gate reads `X.emp:N`, not doc paths. Replaced with the primary source.

---

## What is NOT closed, named so a green is not misread

* **⚠ BG-TALL's nametable half is UNMEASURED.** TAGGED. Full foreground procedure with derived
  expectations in `docs/DEFERRED_WORK.md`, including the trap: **at the top of the tall region a
  correct streamer and a dead one draw the same picture**, because the blob's first 64 rows ARE the
  shipped background. Sample at the BOTTOM.
* **⚠ Step 4's BG-RATE gate has still never been run**, and this parcel is the first thing that
  makes it non-vacuous — before it there was no region whose clamp could bind. Folded into the
  BG-TALL procedure as leg 3.
* **⚠ BG-PLANE-WINDOW is now a REACHABLE wrong picture, not a future one.**
  `Section_RedrawPlanes` re-seeds the window to row 0 whatever the scroll is, so a cache recovery
  or a DEBUG warp inside the tall region leaves a wrong window the tracker walks back at 2 rows a
  frame — up to 16 frames. **Why I did not close it is a blocker, not a preference:**
  `Parallax_Init` runs *after* both blits and zeroes the scroll, so a window computed at `BG_Init`
  reads a stale value and seeds **wrong** rather than merely stale, which is worse than today. Two
  ways out are booked. The step-5 gate procedure flies and does not warp, and that restriction is
  a symptom of this item.
* **BG-STREAM-VDEFORM's exclusion is a CHOICE, not a necessity** — S3K ships the combination
  (`DrawTilesVDeform2`, LRZ3, 20 per-band trackers). Booked with its price: ~40 B RAM and up to 20
  partial row draws a frame.
* **The step-6 wipe has a shipped precedent nobody had named**: SSZ1 runs an amortized 16-row
  bottom-up repaint on a background theme change (`sonic3k.asm:116570-116580`) **through the
  ordinary row producer, alongside the normal streamer in the same frame**, and it **skips rows
  outside the visible span** rather than drawing all 64 (`:103440-103443`). That is three design
  decisions step 6 does not have to invent.
* **Paired sigil half: NONE.** The paired freeze was retired by the owner on 2026-09-02 and aeon
  lands alone.

---

## Byte and warning accounting

| shape | base `56f6fcb4` | this parcel | Δ |
|---|---|---|---|
| `s4.bin` | 820606 | 820746 | **+140** |
| `s4.debug.bin` | 846986 | 847156 | **+170** |

DEBUG crc `0f3962d8`, release crc `a8d0d512` at the final tip.

**The DEBUG shape grew +170 while gaining a 12288-byte blob, and I chased that rather than
reasoning about it.** The blob IS in the ROM: `OJZ_Act1_BG_Layout_Tall` is at `$29750`, the next
symbol `BgAnim_Table` at `$2C750` (exactly `$3000` = 12288 later), and the 12288 ROM bytes at
`$29750` are **md5-identical to the committed file** — checked, not inferred. Everything after
shifted by `$3016`; the file grew only 170 because a fixed base downstream absorbed the rest, the
same placer mechanism steps 1-4 each measured in one direction or the other. **The symbol span,
not the file size, is what says the data is there.**

**Warnings.** Base and parcel are both `154 warnings, module.unreachable 60` in the DEBUG shape —
byte-for-byte the same unreachable-module list (diffed, 60 vs 60, no additions and no removals).
That matters because an unreachable module means dead `ensure`s, and `bg.emp` is not in it, so the
four new guards are live — which the inversion campaign then confirmed directly.

**One new warning class, reported not hidden:** 7 `[layout.provisional-drift]` in DEBUG (delta
`+0x3b7c`), the expected consequence of adding 12 KB of data. Per `tools/bganim_room.py` these are
a **warning and never a stop** since sigil `b0363140`, and the paired freeze is retired, so they
do not gate this landing.

---

## A second finding, derived while the landing build ran: BG-BAND-PLANE-ANCHOR

`Parallax_Step5_Vscroll`'s Step 4a computes `vs = Parallax_Current_Vscroll_BG &
(PLANE_B_SPAN - 1)` and calls it "the plane LINE at the screen top", then selects the parallax
band containing `vs`. **That is exactly right while the background map IS the plane** — plane line
and map line are the same number — and it aliases the moment the map is taller, because the band
tops stay anchored in PLANE space while the art moves through the ring.

Derived from source (`OJZ_Default`'s four layers at world Y 512/1024/3072/3584 under
`v_center 512 / v_factor 3`, band tops `[0, 64, 320, 384]`):

| BG scroll | masked plane line | band |
|---|---|---|
| 447 | 447 | 3 |
| 511 | 511 | 3 |
| **512** | **0** | **0** |
| 544 | 32 | 0 |

**And step 5's own fixture reaches it**: the scroll sits AT its 544 ceiling for camera Y
4864..6143, so the bottom ~1280 px of the tall region runs with band 0 where the map says band 3.
The horizon snaps. **This is not the streamer and the nametable is correct there** — the BG-TALL
procedure carries the same warning so the foreground runner does not misattribute it.

It predates this parcel (the mask is older than regions) but step 5 is the first thing that can
drive the value past a full turn of the ring, so it is the first time it is observable. Booked
with its fix — band tops in MAP space — and with the note that **step 8 makes it strictly worse**:
a 32-row plane aliases every 256 px. I did NOT shorten the test map to hide it; the height is the
spec's number and the aliasing is information the next two steps need.

---

## Landing evidence

`tools/landing_build.sh` at HEAD **`843f810c`**, detached, polled on a marker I wrote.
**`rc=0` and `finished=0` AGREE.**

```
MY_END_MARKER rc=0 head=843f810c at=11:26:44Z
EXIT_s4=0          size=820746  secs=215
EXIT_s4.debug=0    size=847156  secs=18
EXIT_demo.debug=0  size=103874  secs=3
EXIT_needs_build=0
finished=0
3cff4dff276500386e9ca905635a074b  s4.bin
5e6fd073a665a6a609d9e754b74ee8b3  s4.debug.bin
471080a8cfdc21f94848b565ad92d95e  demo.debug.bin
sigil 0.1.0 (700177b1)
land-gate: STAMP WRITTEN key=28a6e28abb77a656 head=843f810c9a2c
```

Lanes, aggregate totals:

* pre-build `pytest tools -m "not needs_build"` — **2851 passed, 2 skipped, 28 deselected,
  5 warnings, 143 subtests passed**
* `emp_expect_fail` — **56/56 cases (54 comptime + 2 link)**
* other-game link guards — **10 passed, 18 skipped, 2853 deselected, 40 subtests passed**
* `needs_build` lane — **28 cases: 27 ran, 0 deferred, 0 failed, 1 EXEMPTED**
  (`test_deb2_appendix[demo.bin]`, a shape this caller does not build; EXEMPTED is printed as
  exempted, never as passed)

**A FIRST landing_build run of this parcel was KILLED and is not evidence.** I stopped it
mid-lane on purpose: while it was running I derived that the fixture's rectangle never let the new
ceiling bind, and editing during a run would have left the stamp grading a tree I was not about to
land. It wrote no marker and I did not read its partial log as a pass — though its pre-build lane
total (2851) is quoted nowhere except here, as context. Its orphaned `sigil` and `emp_expect_fail`
children were killed by PID after the parent, and checked gone.

**The commits after `843f810c` are documentation only** (this section, the BG-BAND-PLANE-ANCHOR
booking). Proven rather than asserted: both sonic4 shapes rebuilt afterwards to md5
`3cff4dff276500386e9ca905635a074b` and `5e6fd073a665a6a609d9e754b74ee8b3` — identical to the
graded ones.
