# Regions part 2, step 4 — the derived-scroll clamp

Parcel `parcel/regions-p2-step4`, based on aeon `origin/master` `57b8a1c3`.
Spec: empyrean `origin/main:docs/superpowers/specs/2026-09-14-regions-part-2-design.md`
§4.4 and step-table row 4.

**No emulator was used.** The step's gate, BG-RATE, needs one. The witness is written, wired
into `tools/effects_gates.py` and committed, and it has **never been run**. What it asserts,
what it *cannot distinguish on this tree*, and the two mutations that must make it red are
all stated below and are not claimed as results.

## What landed

| what | where |
|---|---|
| the position ceiling becomes `rg_bg_span - SCREEN_HEIGHT` from the CURRENT REGION, `VSCROLL_BG_MAX` on a 0 | `engine/level/parallax.emp`, `Parallax_Step5_Vscroll` |
| the rate clamp, 16 px, applied to the STEP and not the destination, immediately before the store | same site |
| `BG_VSCROLL_ROW_PX` / `BG_VSCROLL_MAX_STEP_ROWS` / `BG_VSCROLL_MAX_STEP` + two `ensure`s, both proven red | `engine/level/parallax.emp`, beside `VSCROLL_BG_MAX` |
| `Region.rg_bg_span` gains its FIRST reader; `Region_Current` gains its first ENGINE reader | `engine/structs.emp`, `engine/ram.emp` — both comments corrected |
| GATE BG-RATE: four legs, two of them discriminators, one of those a ROM poke | `tools/bg_vscroll_rate_witness.py`, gate `bg_vscroll_rate` in `tools/effects_gates.py` |
| the `Parallax_Step5_Vscroll` size pin, re-derived +50 before the build | `tools/demo_specialization_witness.py` |
| doc sync + three bookings | `docs/ENGINE_ARCHITECTURE.md`, `docs/DEFERRED_WORK.md` |
| eight stale `parallax.emp:N` citations re-cited BY NAME | `tools/test_parallax_hscroll_probe.py`, `tools/perspective_floor_gen.py` |

## The coordinator's hypothesis, TESTED — and it holds, for a reason stronger than caching

The brief proposed that the clamp site can reach the current region without re-resolving,
because `Parallax_CheckBoundary` "already resolves one per crossing and could cache the
pointer". **It does not need to cache it: it already writes it.**
`Parallax_CheckBoundary` stores the resolved `Region*` into `Region_Current` on every
crossing (`move.l a0, Region_Current`), and has since painted-regions v1. The clamp reads that
cell.

The interesting question was staleness, and the answer is stronger than "the cache is warm":

* **The pointer is refreshed EARLIER IN THE SAME FRAME, not merely at some past crossing.** On
  the one shipped init/update ladder, `games/sonic4/test/ojz_scroll_test.emp` calls
  `Parallax_CheckBoundary` at line 1207 and `Parallax_Update` at line 1382. `Parallax_Update`
  tail-chains into `Parallax_Step5_Vscroll`. So every frame the clamp runs, the crossing test
  for THAT frame's camera has already run. The clamp is not reading a cache; it is reading this
  frame's answer.
* **The one window that does exist, named rather than waved at:** `Parallax_CheckBoundary`
  leaves `Region_Current` alone when `Region_Resolve` returns 0 (no row contains the centre).
  That is its documented robustness net; an act whose rows tile it cannot produce the case
  (the act constructor proves the tiling), and the cost if it ever did is one frame of the
  neighbouring row's ceiling — which the rate clamp bounds anyway.
* **Null is handled and means the same as zero.** `Parallax_Init` clears `Region_Current`, so
  before the first crossing the clamp takes the act default, which is also what `rg_bg_span`
  = 0 means.

So: read, not re-resolved. A fourth private `Region_Resolve` here would have been both the
defect step 3 existed to delete AND slower — a linear scan over the act's rows, every frame,
for a value the crossing already computed.

**The one comment this makes false has been corrected.** `engine/ram.emp` said of
`Region_Current`: "ENGINE LOGIC NEVER READS IT: it is the observable the crossing gate and
the witnesses poll." It is now on a per-frame engine path, and the replacement says so and
says what that means for anyone moving the cell.

## Findings, in the order they matter

### 1. ⚠ THE POSITION CLAMP IS LIVE AND NOTHING ON THIS TREE EXERCISES IT

All ten of act 1's region rows (eleven in DEBUG) leave `rg_bg_span` at 0, so the fallback is
taken on **every frame of every shipped act** and the clamp's observable behaviour is
identical to the pre-step-4 code.

**And authoring the honest value would not change that.** The background map IS the plane
today, so an honest `rg_bg_span` is `PLANE_B_SPAN` = 512, whose ceiling is
`512 - 224 = 288` — exactly `VSCROLL_BG_MAX`. There is **no authored value that distinguishes
the two clamps** until a map is a different height from the plane, which is step 5/6/8's
business.

This is the live vacuity risk the brief named, and it is real. Consequences, both acted on:

* The witness says so in its own header and prints it as a FINDING on **every** run (R0),
  so a future reader cannot take a green from legs C/D/W as evidence about change (a).
* Leg S exists: it pokes a region row's `rg_bg_span` in the emulator's ROM image to a
  **derived** value and asserts the scroll settles at the poked ceiling rather than at
  `VSCROLL_BG_MAX`. Zero ROM bytes. If the server refuses the write, the readback disagrees
  and the tool exits 2 with the reason printed — never 0.
* The alternative — a DEBUG-only eleventh region row with a non-zero span — is **costed and
  rejected** in `docs/DEFERRED_WORK.md`, not silently skipped: it costs 22 B plus
  `act_region_count`, it has to keep the act's tiling proof true, and it would make the DEBUG
  and release region geometries differ in a way every other region gate would have to be
  taught about — to buy what a free ROM poke already buys. Revisit only if the poke is refused.

### 2. `Parallax_Step5_Vscroll`'s snap test is DEAD, and was before this parcel

`tst.b Parallax_Snap_Pending / bne .v_snap` at the top of the BG arm can never be taken. The
proc has **exactly one caller** — the `jbra` at the foot of Step 3's band loop — and the
instruction immediately above that `jbra` is `clr.b Parallax_Snap_Pending`.

Step 3 DOES honour the flag (it reads it per band before clearing), so a warp still snaps the
per-band scroll words. What is lost is the whole-plane BG scroll's snap: with
`CAP_TRANSITIONS` declared (sonic4's mask is `$0FDE`), Step 5 falls through to the transition
test and **lerps** if a transition is in flight on the same frame as a camera jump.

**This matters to step 4 as the reason the rate clamp has no prime exemption.** The obvious
"this frame is a prime" signal is exactly that flag, and it is not available at the site.
Rather than invent a private one — a second authority for a question step 6 will answer
properly — the consequence is left visible: a DEBUG warp's scroll now ratchets at 16 px a
frame, up to 18 frames of slide on a full-height jump, while the plane itself is still
re-primed synchronously. Booked as **BG-RATE-PRIME-EXEMPTION** and **PARALLAX-STEP5-SNAP-DEAD**,
the second with its two candidate fixes and why neither is obviously right.

### 3. The bytes, DERIVED before they were measured, and they agree exactly

**ESTIMATE from the spec: +20 to +30 ROM bytes at the one site. MEASURED: +50 bytes of CODE
at the one site, and +74 / +80 bytes of ROM FILE, which are different numbers for the reason
step 3's note recorded.**

I derived +50 instruction by instruction from the source change **before opening a listing**,
and the measurement agreed exactly in both games. 18 B of old position clamp out; 68 B of
region-derived ceiling plus rate clamp in. The instruction table is in the RE-DERIVATION LOG
in `tools/demo_specialization_witness.py`. The spec's 20-30 was low mostly because it did not
count the fallback ceiling: the clamp now loads a ceiling into a register through a
two-condition ladder (null pointer, zero span) before it can compare anything.

**Four canonical shapes, both revisions, all exit 0.** Base `57b8a1c3`; the AFTER shapes were
built at `e8e68224` (the last commit that touches anything the assembler reads — everything
after it is `tools/` and `docs/`, which move no bytes; that is asserted below, not assumed). Wall clock across the runs `up 7:17` to `up 7:58`, load average 4.6 to
18.1 (several parallel sessions on this box), so elapsed times are context, not a benchmark.

| shape | base size | base md5 | after size | after md5 | Δ |
|---|---|---|---|---|---|
| `s4.bin` | 820532 | `9a3bdf176246b8c95d6360dcb7e153a3` | 820606 | `dff00bfc3ddb7556ea39d743ff7d111e` | **+74** |
| `s4.debug.bin` | 846912 | `63980e7ef62c80ce7928b1b13da3629c` | 846986 | `dfb82e955cd2ba1673c755a8b85a0b5b` | **+74** |
| `demo.bin` | 97229 | `4876455d3fa63cc8455079999601c22a` | 97303 | `a02346137cfa766279ccfe2d2a905a23` | **+74** |
| `demo.debug.bin` | 103662 | `9f5d490cbef277e186e015dd80c98524` | 103742 | `e79a18502b52bd0bb20111b4b4be7568` | **+80** |

The four base figures are my own rebuild of `57b8a1c3` in a sibling worktree and are
**byte-identical to step 3's landed figures**, which is the check on the base.

**By symbol span, both games, full head-to-next-head differential — exactly TWO non-zero rows
per game, and the second is not code:**

| game | row | base | after | Δ |
|---|---|---|---|---|
| sonic4 debug | `Parallax_Step5_Vscroll` | 362 | 412 | **+50** |
| sonic4 debug | `Sound_GetComm` | 17772 | 17722 | −50 (placer pad absorbing it) |
| demo debug | `Parallax_Step5_Vscroll` | 120 | 170 | **+50** |
| demo debug | `CSelf_Expected` | 29680 | 29630 | −50 (ditto) |

**`EndOfRom` is byte-for-byte identical in BOTH games** — `$0C1254` sonic4, `$01121A` demo.
The 68000 image is exactly the same length; the +50 of code was absorbed by placer padding at
a fixed base, the same mechanism steps 1, 2 and 3 all measured.

**So the whole file growth is the deb2 symbol appendix**, and it is +3 SYMBOLS and nothing
else: 3159 → 3162 listing symbols in sonic4 debug, 658 → 658 top-level (the three are
LOCALS). Named: `.v_have_ceiling`, `.v_rate`, `.v_rate_lo`, `.v_rate_add` added,
`.v_pack_store` removed. Appendix 55788 → 55862 (+74) in sonic4 debug and 33492 → 33572
(+80) in demo debug — the two shapes differ because deb2 prefix-compresses and their symbol
tables differ. **A parcel that adds a local label grows every shipped ROM**, which is the
same direction as step 3's "a parcel that adds RAM symbols grows the release ROM whatever it
does to the code".

**Sigil warnings: identical in every category, both sonic4 shapes** — 167 (debug) and 154
(plain) before and after, same per-category breakdown. No new `module.unreachable`, no new
`proc.clobber-undeclared`.

**The doc, tool and citation commits moved ZERO bytes**, proven rather than asserted: the
sonic4 md5s from the build round BEFORE those commits (`dff00bfc…`, `dfb82e95…`) are
identical to the final round's.

### 4. Eight stale citations, and the shape of the rot

My +28 source lines pushed three live `parallax.emp:N` citations onto blank lines and bare
delimiters, failing `test_citation_form`. **All three were already pointing at unrelated
content at `57b8a1c3`** — `:963` at `VSCROLL_COL_SHIFT`, `:1352` at
`Parallax_StartTransition`'s store-ordering note, `:1962` at the band-drift accumulator.

Then I made the same mistake inside the fix: my re-citation notes KEPT the old
`parallax.emp:963-983` spelling inside the sentence explaining it was stale. The gate does not
read English, it reads `X.emp:N` — so a note saying "this citation is stale" IS a stale
citation. That cost one whole four-shape build round.

Fixing that properly, I swept the same file and found **five more** that were already wrong
and passing, because they happened to land on code:

| citation | claimed | actually points at |
|---|---|---|
| `:695-778` | Step 4a | the module's constant block |
| `:895-1001` | Step 4b | ditto |
| `:810-893` | `resolve_anchor_line` | ditto |
| `:825-838` | the palette-side anchor rule | the vertical bob's `BOB_SINE_*` constants |
| `:858-859` | fire lines -> screen +1 | a bob `ensure` message |

**The gate cannot see these and is not meant to** — its own docstring says it is
content-invariant, asserting that a pointer has a referent and not that the referent is right.
So a citation that is merely WRONG is invisible; only one that is wrong AND lands on
whitespace is caught. All eight are now cited by symbol name with what each had drifted onto
recorded at the site.

⚠ **And then a ninth, which I nearly shipped a false claim about.** This note originally said
`engine/ram.emp:277` in the same file "was checked and left: this parcel's `ram.emp` edit is at
~565, so 277 is untouched". The first half was reasoning, not checking. Line 277 of
`engine/ram.emp` is `Cache_Spec_Blocked`; `Hscroll_Buffer` is at 425, and the citation was
already wrong at `57b8a1c3`. My arithmetic about not having moved it was correct and completely
beside the point — a citation can be stale without anybody moving it. Re-cited by name with
that recorded at the site. **Nine for nine: every `.emp:N` citation in this file was wrong.**
The line-number form does not decay slowly here; it is already gone.

## Both new `ensure`s proven RED by inversion, CONTROL run LAST

Mutations applied on disk (`git diff --stat` naming the file, and the mutated line quoted back
from disk), restored from the COMMITTED baseline that contains the ensures:

| mutation | line on disk | result |
|---|---|---|
| `BG_VSCROLL_ROW_PX = PLANE_B_SPAN / (PLANE_B_CELL_ROWS * 2)` | `743:pub const BG_VSCROLL_ROW_PX        = PLANE_B_SPAN / (PLANE_B_CELL_ROWS * 2)` | **RED**, exit 1: *"PLANE_B_SPAN 512 over PLANE_B_CELL_ROWS 64 is 4 px a row, not the 8 a VDP nametable cell is"* |
| `BG_VSCROLL_MAX_STEP_ROWS = 0` | `744:pub const BG_VSCROLL_MAX_STEP_ROWS = 0` | **RED**, exit 1: *"BG_VSCROLL_MAX_STEP is 0 px, outside 1 .. SCREEN_HEIGHT-1 (224)"* |
| **CONTROL**, unmutated, run LAST | — | **GREEN**, exit 0, `crc=25754148 len=846986` |

## Guard and lane totals

| lane | base | after |
|---|---|---|
| `pytest tools -m "not needs_build"` | 2753 passed, 2 skipped, 16 deselected, 143 subtests | **2753 passed, 2 skipped, 16 deselected, 143 subtests, exit 0** |
| `emp_expect_fail` | OK — 56/56 (54 comptime + 2 link) | **OK — 56/56, unchanged** |
| the four canonical shapes | exit 0 | **exit 0, all four** |
| `tools/demo_specialization_witness.py` | — | **OK — span absence + image differential, 28/28 sonic4 spans, 0 demo spans, exit 0** |
| sigil warnings | 167 / 154 | **167 / 154, same per-category breakdown** |

The pre-build lane found two real defects on the way, both this parcel's own and both
recorded above: the three stale citations my +28 lines exposed, and then my own re-citation
notes being live citations themselves. Each cost a four-shape build round.

⚠ **`tools/landing_build.sh` was NOT run.** The four shapes were built individually so that
base and after could be measured with the same script; the landing script's `needs_build`
lane and its `finished=` stamp are the controller's to collect.

## GATE BG-RATE — WRITTEN, WIRED, NEVER RUN

`tools/bg_vscroll_rate_witness.py`, gate `bg_vscroll_rate` in `tools/effects_gates.py`.
It samples `Parallax_Current_Vscroll_BG` once per logic tick at the
`GameState_OJZScroll_Update` entry over four legs and asserts:

| | |
|---|---|
| **A1** THE GATE LINE | no tick moves the value by more than `BG_VSCROLL_MAX_STEP` |
| **A2** | the value never leaves `[0, ceiling]`, ceiling derived per sample from the region `Region_Current` names |
| **A3** | the WHOLE clamp modelled: on every non-transition tick the value equals `clamp_model(target(camY), previous, ceiling)`, target computed from the ACTIVE `parallax_config`'s own fields read out of the ROM |
| **A4** the rate DISCRIMINATOR | after a warp whose derived target jump exceeds `2 * BG_VSCROLL_MAX_STEP`, at least two consecutive ticks step EXACTLY the bound |
| **A5** the position DISCRIMINATOR | with a row's `rg_bg_span` poked in ROM, the descent settles at the poked ceiling, not at `VSCROLL_BG_MAX` |

Legs: **C** the crossing route held RIGHT (refuses if it crossed no boundary), **D** a
full-speed descent, **W** the warp ratchet, **S** the poked span.

**"The shaft fall" is leg D, and it is a NEGATIVE CONTROL, not a discriminator.**
`tools/plane_buffer_peak_probe.py`'s route catalogue already settled what a shaft fall means
for a camera-RATE question and its answer is transcribed rather than re-argued: DEBUG free
flight runs at `PLAYER_DEBUG_FLY_SPEED` = 16 px/frame, which IS `CAM_MAX_Y_STEP`, so a physics
fall cannot beat a held DOWN. At the shipped `v_factor` that is about 2 px of BG scroll a
frame against a 16 px bound, so leg D is *expected* not to bind. Its value is saying the clamp
does not fire in ordinary play. **A4 is what says it exists at all.**

Every expectation is evaluated from source: `emp_consts()` parses the `const NAME = <expr>`
declarations and EVALUATES them (three of the four numbers are derived in source —
`BG_VSCROLL_MAX_STEP` is `ROWS * ROW_PX`, and `ROW_PX` is `PLANE_B_SPAN / PLANE_B_CELL_ROWS`);
`pcfg_offsets()` reads `parallax_config`'s own `// $XX` comments and cross-checks them against
the declared field order; `step5_shape_check()` refuses to model a `Parallax_Step5_Vscroll`
whose instructions no longer read the way `clamp_model()` transcribes them.

### ⚠ TAGGED for the controller's foreground emulator run

1. **Run it.** `python3 tools/bg_vscroll_rate_witness.py --rom s4.debug.bin --lst s4.debug.lst`
   (or the whole lane, `--only bg_vscroll_rate`). It has never executed; a first run may well
   find a route or an API detail I got wrong by reading. One is already fixed that way — leg C
   originally stopped on "the centre passed the last row's `x1`", which the camera clamp makes
   unreachable.
2. **Red-first, both halves.** The MUTATIONS block at the foot of the witness spells the two
   one-line reverts and which leg each must break, including the prediction that reverting the
   POSITION clamp leaves legs C/D/W **green** — that is the vacuity being demonstrated rather
   than explained. Until both have been watched to fail, this is an untested instrument.
3. **Does the Rust core honour a ROM write?** Leg S's whole value rests on it. The witness
   verifies by readback and exits 2 with the reason if not, so this is safe to just try.
4. **The existing crossing gate.** The step line also asks that `parallax_crossing_gate` stays
   green. Not run here.
5. **Watch a DEBUG warp.** BG-RATE-PRIME-EXEMPTION predicts a visible 16 px/frame slide of the
   background after a warp. If it looks worse than "cosmetic, DEBUG only", that booking should
   be promoted rather than deferred to step 6.

## Open / not done here

* **BG-RATE is UNMEASURED.** Nothing here claims the clamp behaves correctly on hardware.
* **The position clamp is untested by anything that ran.** See finding 1.
* **`PARALLAX-STEP5-SNAP-DEAD` is booked, not fixed** — found here, not introduced here, and a
  different parcel's subject.
* **PAIRED HALF NOT DONE.** This parcel moves ROM bytes in all four shapes, so sigil's goldens
  no longer match. Nothing here touches sigil and sigil's suite was not run.
* **Not cross-seam by name.** `Region_Current`, `Region.rg_bg_span` and the three new
  `BG_VSCROLL_*` constants are all engine-side; nothing in `map.toml`, either
  `game_root.asm`, or `debugger.asm` names any of them. The byte change is the sigil pairing
  obligation, not a name.

## ADDENDUM — the first live run, 2026-09-16 (controller ran it; this lane still saw no emulator)

BG-RATE refused at setup on its first execution, exit 2, no leg run:
*"warping x=5984 from y=0 to y=2047 moves the target BG scroll by only 0 px"*.

### The 0 was CORRECT, and settling that came before re-aiming

Re-aiming first would have hidden a modelling bug behind a passing leg, so the question was
answered before anything moved. **`target_scroll` is right.** It transcribes
`Parallax_Step5_Vscroll`'s `cmpi.b #15 / beq .v_locked` arm: at `pcfg_v_factor_bg == 15` the BG
scroll IS `v_offset`, camera-independent, by design. A jump of 0 over 2047 px of camera travel
is the correct answer *about that config*.

Read out of the built ROM (`s4.debug.bin`), OJZ act 1's eleven rows resolve to:

| rows | effective config | v_factor | derived jump over the row's camera-Y travel |
|---|---|---|---|
| 0, 4, 7, 8 | `$1486e` / `$1492c` / `$149ea` / `$14a68` | **15 (lock)** | **0 — correct** |
| 1, 2, 9, 10 | act default `$134e8` | 3 | 241 |
| 3, 5 | `$134e8` / `$13586` | 3 | 255 |
| 6 | `$134e8` | 3 | 242 |

### The actual defect was a MIXTURE, not just an inherited column

The leg read the **active config at the inherited camera position** — the bottom-right, row 8,
locked — while taking the **y endpoints from a different row** (`region_at(rows, wx, 0)` = row
10). It priced a config the warp would never install. And x = 5984 lands in the DEBUG-only
`OJZ_Preset_NightSnap` row, so the leg's discriminating power was being decided by an E2 snap
artifact with nothing to do with step 4 — your point 1, and it is worse than "inherited": the
comment claiming "derived, not picked" was true of the y and false of the x, which is exactly
the shape of comment that stops a reader looking.

### What replaces it

`plan_vertical_leg()` walks the act's rows in table order, computes each row's **camera-Y**
window (the row's span shifted by `HALF_H`, because `Region_Resolve` tests the CENTRE,
intersected with the engine's own `Camera_Y_Max`) and a probe column at the row's middle clamped
to `Camera_X_Max`, warps there, and then **asks the engine** which config is live
(`Parallax_Current_Config` / `_Target_Config` out of RAM). `Effects_ResolveParallax`'s rungs are
**not** restated — a witness that restated them could disagree with the ROM and call it a pass.
First qualifying row wins; the scan is reported; if none qualifies it raises naming **every**
candidate and why, because "this act has no vertically responsive region" is a finding about the
act, not a tool giving up.

On this act the live scan probes row 0 (rejected, LOCKED, with that word in the message) and
row 1 (CHOSEN, jump 241 > 32) and stops. Leg S's derived poke in row 1: reach 177, span 368
(rounded down to the 8-px grid `ojz_region()` requires), ceiling 144 — comfortably inside
`(0, 288)` and 33 px below the reach.

### Legs are now independently blockable, and a blocked run says what it is not

Your ruling taken. `SetupError` = the instrument is wrong, abort everything. `LegBlocked` = one
leg, named with its reason, others still run, **still exit 2**. C and D need nothing from W or
S; W and S share one precondition and are coupled to each other only. A blocked run now prints
which legs ran *and* the sentence that stops them being read as evidence: **A1/A2/A3 over
ordinary motion produce identical numbers on a tree with the rate clamp removed**, because in
ordinary play the target never moves more than the bound. `--skip-poke` now exits 2 rather than
passing with a note.

### The aim is now testable without an emulator, and red-proven

`tools/test_bg_vscroll_rate_aim.py`, 9 tests. The aim became two **pure** functions
(`candidate_window`, `jump_verdict`) precisely so it could be; the untestable middle step is
"ask the engine", deliberately. Eight synthetic tests pin the decision rules — including that
the lock arm gets its **own** message and is not lumped in with "too small", because the two
diagnoses have opposite fixes. One `needs_build` test reads the real act table and pins that the
population contains **both** locked rows and a qualifying one, which is exactly the asymmetry
that makes a table scan necessary. **It would have caught the original defect without an
emulator.**

Red-proven, control run LAST (green, 9 passed):

| mutation | result |
|---|---|
| the LOCK arm deleted (`if False`) | RED — `test_the_lock_sentinel_is_named_and_not_lumped_in_with_too_small` |
| the window becomes the ROW's, not the CAMERA's | RED — `test_the_window_is_the_cameras_not_the_rows` |
| the threshold loosened `<=` → `<` | RED — `test_the_threshold_is_strict_and_derived` |
| every row rejected on geometry | RED — 3 tests **including the real-act arm**, which proves that arm asserts |

### ⚠ And I walked into the trap I wrote down in step 3's note

My first red-proof attempt restored between mutations with
`git checkout HEAD -- tools/bg_vscroll_rate_witness.py` — and HEAD did not yet contain the
rewrite, so the restore **deleted the whole thing**. Step 3's note says, in my own words:
*"Commit the artifact BEFORE red-proving it; 'restore from a committed baseline' is only a
restore if the baseline contains the work."* Third instance of applying a rule outward and not
inward. Worse, the control in that first attempt was **also** red and I nearly read it as a
finding rather than as the tell that the tree had been gutted — a control that fails the same
way as every mutation is not a control, it is a wrecked bed. The work was reconstructed and
re-verified; the re-aim was committed **before** the second, successful red-proof.

### Lanes after the re-aim

`pytest tools -m "not needs_build"`: **2761 passed, 2 skipped, 17 deselected, 143 subtests,
exit 0** (was 2753/16 — the 8 new synthetic tests, and the real-act one deselected as
`needs_build`). Nothing here touched a `.emp` file, so the ROMs are unchanged from the figures
above.

## ADDENDUM 2 — the second live run: leg S's live poke is impossible, and that is a better answer

The controller ran the re-aimed witness. **The aim works** — and leg S then died on the question
I had tagged: *"does the Rust core honour a ROM write? It fails loud, so it is safe to try."*

```
[-32004] 0x00018AC8: only the work-RAM window ($E00000-$FFFFFF) is writable;
         ROM and I/O writes are refused
```

It was safe to try, and it does not. `$18AC8` is inside the region table, which is ROM.

### 1. It failed loud but not CLASSIFIED, and the guard was one line too late

My readback guard sat *after* the write, so a designed-for refusal arrived as an unhandled
traceback — bypassing the whole LegBlocked/SetupError vocabulary I had just built to make "which
legs ran" readable. **I did not move the guard one line up.** `run_leg` now catches `BusError`
alongside `LegBlocked`, so any bus refusal in any leg becomes a named COULD NOT RUN row carrying
the bus's own message. A guard that only covers the refusal I happened to hit is the same defect
one call site along.

### 2. The rejection of the DEBUG-extra-region alternative was void, and re-deriving it found my
### own argument was partly wrong

That rejection rested on "leg S's poke is free". The poke does not exist, so the arithmetic was
void. Re-costed from scratch in `DEFERRED_WORK`, three routes:

| route | cost | buys |
|---|---|---|
| A. live poke | — | **impossible**, refused by design |
| B. DEBUG-only extra region row | +22 B, `act_region_count` +1, a re-cut tiling proof, a fixture baked into game data, DEBUG-shape only | a discriminator, in DEBUG only |
| C. patch a ROM copy on disk | ~30 lines, one extra headless boot, zero ROM bytes, zero act edits | a discriminator on any shape and any row |

**C taken; B stays booked as the fallback if C ever fails.** And the part worth carrying: my
original argument against B claimed it "would make the DEBUG and release tables differ in a way
every other region gate would have to be taught about". **The DEBUG table already differs** —
`OJZ_E2_SNAP_ROWS` adds row 10 in DEBUG only — and every region gate already reads the table out
of the ROM it is handed and copes. That cost was largely imaginary. B's real costs were the
other three, and they were enough on their own; the one I leaned on was not. A right conclusion
resting partly on a wrong premise survives until somebody re-derives it, which is precisely what
happened here.

### 3. Route C is not a workaround — it is stronger evidence, by more than was claimed for it

`AetherInstance.start()` already runs `assert_cart_matches_disk` with `CART_WINDOW = 0x400000`:
it reads the **whole 4 MB cart** back off the bus and byte-compares it against the file, on every
spawn. So the patched word is proven present in the emulator's cart by a full-image comparison,
for free — where the live poke would have had a single-word readback. Leg S also reads the word
back by its own address so the verdict can name it, and it runs in its **own instance**, because
its subject is a different act and running C/D/W against the patched cart would move the ceilings
A2 and A3 assert against.

**The two blockers, checked rather than hoped:**
* **Checksum** — `Checksum` at `$18E` is a data word in `games/sonic4/config/header.emp`, folded
  by sigil post-pipeline. No engine code reads it; this ROM does not verify itself at boot, so a
  two-byte data patch boots exactly as the pristine image does.
* **Provenance** — the spawn check compares against the path passed in, not a canonical name, so
  a patched temp file verifies against itself. The deb2 appendix is past `EndOfRom` and untouched;
  the `.lst` is untouched, so every symbol still resolves.
* **Address == file offset** — not assumed. Proven by the witness's own static read: the region
  table is read out of the file with `rom[addr:...]` using `Act.act_regions` addresses and yields
  the act's real eleven rows.

### The arithmetic is now tested with no emulator, and red-proven

`test_patching_rg_bg_span_on_disk_hits_exactly_the_right_two_bytes` patches a copy, reads the
table back out of the **patched image** with the witness's own reader, and requires: the chosen
row's span is the patched value, every other row byte-identical, exactly two bytes changed, and
the offset pinned at 20/`$14`. Red-proven, control last (10 passed):

| mutation | result |
|---|---|
| aim at `rg_bg_layout` instead | RED |
| treat the ROM address as if it were not the file offset (+2) | RED |
| patch four bytes instead of two | RED |

### Where step 4 stands, stated plainly

Change **(b)**, the rate clamp, has a discriminator that has not yet run to completion (leg W).
Change **(a)**, the position clamp, has exactly one discriminator in the entire tree (leg S), and
it has never run. A run missing either now says which half went untested, in the output, in those
words. Nothing here claims either half is verified.

## ADDENDUM 3 — both discriminators fired; the red was the instrument, and the proof is conservation

The controller's third run: **A4 and A5 both fired.** Leg W forced the rate clamp to the bound for
nine consecutive ticks; leg S, on a patched ROM copy, settled at 144 = `rg_bg_span - SCREEN_HEIGHT`
rather than at `VSCROLL_BG_MAX` = 288 (which it reaches at 177 unpatched). Route C works and the
lock-sentinel rejection prints as designed. The run was nonetheless **RED on A1/A3**.

### One logic tick, TWO `Parallax_Update` calls

The right axis was neither of the two offered. It is one tick, and two invocations:

* `GameState_OJZScroll_Update` calls `Debug_Warp_Consume` at its **frame top**, inside the same
  logic tick — *"First thing in the frame's game work, before objects, camera follow and every
  streaming step"*.
* `Debug_Warp_Consume` ends with `jbsr Parallax_CheckBoundary` + `jbsr Parallax_Update`; its own
  comment: *"the final Parallax_Update primes HScroll/VSRAM so the first displayed frame at the
  destination already scrolls correctly."*
* The same frame's body then runs both again.

Two correctly clamped 16 px stores; a rig sampling once per tick attributes both to one tick.

### The decisive check is conservation, and it uses only the failing run's own numbers

Target 177. Observed 0 → 32, then **nine** consecutive ticks at exactly 16 = 144. `32 + 144 = 176`,
and the last tick takes the remaining 1. **Every pixel accounted for, none skipped.** A bypassed
clamp lands on 177 in a single store and there is no run of nine to have. That is what separates
"the clamp bound twice" from "the clamp was skipped and 32 happens to look tidy" — and it is
stronger than my reading of the source, because it is arithmetic over data I did not produce.

### The fix TIGHTENS A1; it does not teach the gate to pass

A1 was **not** relaxed to admit 32 on the first tick. Leg W now samples once per
`Parallax_Step5_Vscroll` **invocation** — the thing the clamp actually bounds. A per-tick bound
follows from a per-invocation one but is weaker, so this is a strictly stronger assertion that
happens to also be the correct one. A3 became granularity-aware, because the pairing differs: per
tick `v[i]` pairs with `cam[i]`; per invocation the entry sample reads the *previous* store, so
`v[i]` pairs with `cam[i-1]`.

And the per-tick legs now **prove** they are per-tick: every sample carries `Logic_Tick`, and a
tick-mode leg **blocks** if any interval is not exactly one tick. The question "one tick or two"
is now answerable from data instead of from my reading.

### FINDING D: your guess was right, and the witness now has to say so

Bound steps are classified by whether the region or active config **changed** across them. Leg D's
route crosses rows whose config is the vertical lock, so the target jumps to a fixed `v_offset` and
the clamp does its job. D's finding now reports *n at a change* and *n in steady state* separately,
and only the second would contradict the shipped `v_factor`. A negative control that fires and is
waved through is worth less than no control.

### ⚠ A mutation left a test GREEN — a runner defect, and the second one this parcel has produced

Red-proving the above, the mutation that **emptied** `warp_consumer_shape_check`'s search loop —
making it look at nothing at all — left its test passing. The test called the check and asserted it
did not raise, and **a check that cannot see the tree satisfies that just as well as one that can**.
There was no arm exercising the refusal, so the refusal was never tested.

Both shape checks now take doctored `text` and have a **positive and a negative arm**: the real tree
passes, and source with the mechanism removed **raises**. Each probe asserts its own substitution
matched something first, so a probe that stops probing fails rather than passing quietly. G-D is red
against the fixed tests; control green, run last, 18 passed.

This is the same defect shape as leg S's original vacuity and as BG-NT-IDENTICAL in step 3: *a green
consistent with the mechanism never running*. Three instances in one parcel, in three different
places, found three different ways.

### Where step 4 stands now

| change | discriminator | status |
|---|---|---|
| (b) rate clamp | A4, leg W | **FIRED** — 9 consecutive ticks at the bound, conservation exact |
| (a) position clamp | A5, leg S | **FIRED** — settled at the patched ceiling 144, not at 288 |

Both halves now have real evidence. What is NOT yet done: the A1/A3 red has been diagnosed and the
instrument corrected, but **the corrected instrument has never run** — the next run is the one that
says whether A1/A3 are green at invocation granularity. And the two ROM-side mutations in the
witness's MUTATIONS block (revert the rate clamp; revert the position clamp) remain unrun, so
nothing has yet confirmed the gate goes red when the subject breaks.
