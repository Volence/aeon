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

**Four canonical shapes, both revisions, all exit 0.** Base `57b8a1c3`, after `2e34c9ba`
(this parcel's tip). Wall clock across the runs `up 7:17` to `up 7:58`, load average 4.6 to
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
