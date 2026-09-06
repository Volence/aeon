# Aeon whole-repo Lens Sweep — 2026-09-06

**Review pin: aeon `61f22403`**, worktree `/home/volence/sonic_hacks/.aeon-lens-pin`, clean at pin time.
Roster A with the ratified x2 seat doubling, every seat a fresh subagent on the pinned tree, read-only.
**No fixes during the sweep.** Adjudication by the aeon overseer, after return.

**Corpus:** `engine/**/*.emp` + `games/**/*.emp`, 76,111 lines.
**OUT OF SCOPE and recorded UNEXAMINED, NOT CLEARED:** `tools/` (its own Roster B panel, queued),
vendored `engine/debug/debugger.asm`, `games/*/data/generated/**`.

**DO-NOT-RE-LITIGATE carried into every seat:** `RASTER_FIRE_BASE_CYC` omitting the 44-cyc IRQ4
entry (`raster_dsl.emp:991`) is REFUTED; 302 derives from fixture F0's absolute measured 572 cyc.

---

## Step 0 — the sweep's own instruments, before any seat ran

### S0-1. The self-test that cannot fail the build — CONFIRMED, controller-run

`python3 tools/ojz_entity_gen.py test` exits **1** on the pinned tree:
`AssertionError` on `assert "dc.b    0, 0" in text`.

It is invisible to `build.sh` because the pytest lane sweeps `test_*.py` **files**, and these are
`test_*` **functions** inside a generator module that is not named like a test file. So the
generator ships a self-test, the self-test is broken, and no runner is looking at it.

**This is the same class the repo already booked as "verified vacuous gates" and it was not in
that list** — because that list was built from the names of gates, and this one has no gate name.
Enumerating by name cannot contain the case that has no name.

### S0-2. A correction placed where no reader walks — CONFIRMED, controller-re-derived

`docs/DEFERRED_WORK.md:11926` heads the tools-packet section with
**"Landing them made them discoverable; NOTHING in them is fixed."**
`docs/DEFERRED_WORK.md:12063` says
**"THE TOOLS PACKET IS NOW FULLY WORKED — D1 through D10 all closed 2026-08-18."**

The correction is **137 lines below** the claim. A reader who greps the packet filename lands on
the first line and stops. Both located by CONTENT, not by the coordinates the seat reported —
the seat's own line numbers did not land, which is itself the coordinate-rot pattern.

**Ruling: the correction goes at the head, not the tail.** Put the correction where the WRONG
path leads.

---

## Seat A2 — comment TRUTH

Method: extracted `Clobbers:`/`In:` prose and the `clobbers()`/`preserves()`/`out()` attributes
for all **579** procs and compared; 269 carry both. 54 contradictions read by hand.
Field-offset sweep over 62 structs (29 fully sized) came back **0 drift with a red-first control
that flagged exactly one row**. `In:`-vs-parameter sweep over 316 procs: 1 flag, a false positive.

The governing rule is `CODING_CONVENTIONS.md:492` — *"These are compiler-verified (tranche-3
ruling, §10). The header comment's `Clobbers:` line explains MEANING; the attribute is
authoritative and the two must not contradict."*

### The seat's own closing tag, and its resolution

The seat flagged that **its entire severity ranking rested on that "compiler-verified" sentence,
which it had not seen run** — it cannot build, the enforcement lives in sigil, and
`games/sonic4/test/poison/` has 30+ cases and **none** mentions `clobbers`. It tagged the
question for the controller rather than assuming either answer. That was the right call and the
answer is asymmetric.

**Controller measurement, three builds on a detached `61f22403` worktree, `FAST=1 DEBUG=1`:**

| run | mutation, quoted back from disk | exit | verdict |
|---|---|---|---|
| control | none | **0** | clean tree builds |
| under-declare | `moveq #7, d5` added to `BgAnim_Init`, declared `clobbers(d0/a0)` | **1** | `error: [proc.clobber-undeclared] closure firings, 1 firing(s); this family is zero-firing by contract` + `contract closure gate FAILED` |
| over-declare | `clobbers(d0/a0)` widened to `clobbers(d0/d5/a0)`, body unchanged | **0** | **built green, silently** |

**So the convention's sentence is true in ONE direction and false in the other.**
Writing MORE than you declared is build-fatal. Declaring more than you write is unchecked.

Three further facts the same runs establish:

- **The clean control already carries 72 `proc.clobber-undeclared` warnings** — 70 in
  `engine/level/page_cache.emp`, 1 in `engine/system/boot.emp`, 1 in
  `games/sonic4/player/player_common.emp`. The build passes because the gate is a **bidirectional
  ratchet against a frozen baseline** (`build.sh:770-776`: a firing outside the baseline fails,
  *and so does a baseline row that stops firing*). That is a sound design, and the raw count of 72
  is not the alarm it first reads as. **It is also not "72 clean procs."**
- **The diagnostic self-describes as `heuristic lint, full register dataflow is deferred to
  S2-D6`.** "Compiler-verified" overstates it.
- **It has demonstrable false positives:** `EntryPoint writes a7` — the stack pointer, which any
  push writes.

### Consequence for the seat's five contract findings — they SPLIT

| # | site | shape | after the measurement |
|---|---|---|---|
| 1 | `engine/objects/core.emp:468,616` — `RunObjects`, `RunObjects_Frozen`: prose says `d0-d6`, both write `d7` on their first instruction; attribute correctly says `d0-d7` | prose narrower than attribute | **doc defect.** The machine is guarded. The parenthetical `(object code may clobber freely except a0/d7)` is the *callee* `ObjRoutine` contract sitting on the caller's `Clobbers:` line, where it reads as the exact opposite of what the proc does. Highest-traffic entry points in the engine. |
| 2 | `engine/level/tile_cache.emp:539` — `TileCache_CopyBlockColumn` prose omits `a4`, which the body writes live | prose narrower | **doc defect**, machine guarded |
| 5 | `engine/level/bg_anim.emp:132` — `BgAnim_Init` header omits `a0`, contradicted eight lines below by the body's own correct note | prose narrower | **doc defect**, machine guarded, low blast radius |
| 3 | `engine/objects/collision.emp:110,114` — `TouchResponse`. Body genuinely saves/restores `a4`; attribute over-declares `a0-a4`; and the in-body comment at `:114` asserts *"the clobbers(a0-a3) caller contract is unchanged"* — **a contract that does not exist** | attribute WIDER than body | **LIVE AND UNGUARDED.** Over-declaration is the direction nothing checks. The `:114` comment exists precisely to stop a reader from deleting the `movem` pair as dead weight, and it names the wrong contract, so it will not. |
| 4 | `engine/objects/entity_window.emp:1185` — `EntityWindow_TrySpawnObject`. Body restores `a0/a1/a3` on every path; attribute licenses clobbering them; only the prose promises they survive | attribute WIDER than body | **LIVE AND UNGUARDED**, same direction |

**The split is the finding.** Two seats' worth of severity ordering turned on a sentence in the
conventions, and the sentence is half true. Findings 3 and 4 were ranked BELOW 1 and 2 by the
seat; after measurement they are the two that nothing can catch.

### A2's sixth: five citations to a file deleted 19 days ago, all exactly 31 lines stale

`engine/level/scene_dsl.emp:1585,1589,1595,1748,2308` cite
`games/sonic4/data/parallax/configs.emp` in the present tense. That file was deleted by `92fafc3e`
(2026-08-18). All five coordinates match the file as it stood at `560a47be` (2026-08-15), a
uniform +31 offset from its state at deletion — **the seat predicted the offset from the first two
rows and then confirmed all five**, which is what makes it a derivation rather than a fit.

A reader who recovers the file the obvious way (at the deletion commit) and follows `:2308` lands
on `ParallaxConfig_OJZ_Windy`, not the `ParallaxConfig_Haze` the prose describes.
**Every substantive claim at those five sites is TRUE** — the seat checked each against the
recovered file. Only the coordinates are wrong, which is why it ranks below the contract findings.

**The contrast that makes this a defect rather than a convention:**
`games/sonic4/test/scene_equiv_proof.emp` cites the same dead file 20+ times, is exact on every
one, and says at `:16-20` where to recover it. Same referent, two files, one rebased its numbers
and told the reader where to look.

### A2's denominator, stated plainly

Exhaustive by extraction: the 579-proc contract sweep, the 316-proc `In:` sweep, the 62-struct
offset sweep, and 241 `file:line` citations.
**Sampled, not swept — the honest gap:** of 217 `the only`/`sole`/`nothing else` universals it
read ~35 (6 true, 1 false); the wider 1,846 `always`/`never`/`cannot`/`guaranteed` population is
essentially untouched. 33 structs whose sizes its sizer could not resolve are **unchecked, not
clean**. The Z80 comment surface was not swept at all — and `DEFERRED_WORK:8098` already records
a live known-bad there, which suggests that is where the residual density sits.


---

## Seat B1 — construct / idiom discipline

Machine-scanned exhaustively across all 193 `.emp` files: `mulu`/`muls`/`divu`/`divs` in code
position (**two independent instruments**, an anchored grep and a comment-aware Python scan, which
agree on 9); every sized branch mnemonic; every `struct`, `region` and `vars` declaration;
`@as_compat` occurrences (**zero in the whole corpus**); adjacent foldable immediates; hardcoded
VDP command longwords. `andi` numeric masks exhaustive over `engine/` only — **`games/` sampled,
so a magic-mask twin of F1/F2 could still be there.**

### B1-F1 — block-alignment masks spelled two ways, and the guard that fires sends you to the wrong fix

`engine/level/tile_cache.emp` aligns blocks with a hand-rolled `andi.w #$FFF0` at **8 sites**
(931, 1518, 1671, 1794, 1817, 1964, 2060, 2138) and the complementary `andi.w #$F` at **9**
(65, 68, 816, 818, 1784, 1790, 1933, 1966, 2062) — while the **same file** spells the blessed
derived form `andi.w #~(BLOCK_TILE_SIZE-1)` **13 times**. Identical today only because
`BLOCK_TILE_SIZE = 16` (`constants.emp:957`).

`constants.emp:957-981` is written as a tunable geometry authority — `BLOCK_NT_SIZE`,
`BLOCK_COLL_ROWS/COLS`, `COLL_CELL_W/H` all fold from `BLOCK_TILE_SIZE` — and carries an
`ensure(1 << BLOCK_TILE_SHIFT == BLOCK_TILE_SIZE, …)`. **That guard binds the shift. Nothing binds
the masks.** The seat looked for a pin and found none, with a positive control proving its grep
was not blind to the construct.

**Controller ran the experiment the seat named, and the result is worse than the seat predicted.**
Detached `61f22403` worktree, `BLOCK_TILE_SIZE 16 → 32`, `BLOCK_TILE_SHIFT 4 → 5`, quoted back
from disk:

| step | state | exit |
|---|---|---|
| 1 | geometry doubled, nothing else touched | **1** — two errors, **both** `coll_src_row_base assumes BLOCK_COLL_COLS=16 (lsl #4); update the shift` |
| 2 | did exactly what that message says: `lsl #4` → `lsl #5`, its `ensure` moved to 32 | **0 — GREEN** |

**The seat's falsifier — any build error naming one of the 17 mask sites — did not appear at
either step.** So the geometry can be doubled, the single guard that fires can be satisfied by the
two-character edit **its own message instructs**, and the build then goes green with all 17 sites
still aligning on a 16-tile grid: a tile cache staging and copying the wrong blocks.

**This is the "helpful artifact worse than absence" shape.** A refusal that names an INCOMPLETE fix
reads as a complete one. A reader who follows `update the shift` has followed the tree's own
instruction, seen it go green, and is done. Silence would have left them looking.

`docs/superpowers/notes/2026-08-07-lane-b-packet.md:29` already ruled this constant tunable and
records that an `ensure` was added. The ensure covers the shift; the mask population was never
enumerated.

**B1's second open item, also measured rather than expected:** neither `tools/s4lint.py` nor the
sigil lint registry carries any magic-mask or magic-number lint. Nothing outside the corpus
catches this class.

### B1-F2 — plane-wrap masks, the same split, lower severity and argued as such

Hand-rolled `#63` at `section.emp:272,319,698,755,806,851` and `plane_buffer.emp:140,434`, plus
`plane_buffer.emp:432 andi.w #$FFC0`; the blessed `#PLANE_H_CELLS-1` / `#PLANE_V_CELLS-1` forms
appear 7 times in the same two files. `PLANE_H_CELLS = PLANE_V_CELLS = 64`.

The seat ranked this **below F1 and gave its reason**: the plane dimension is anchored in VDP
register $10, so a change is a far larger and more visible edit than a constant bump. Recorded
with that ranking intact.

### B1-F3 — `engine/objects/animate.emp:81,85`: the comment's arithmetic is wrong, in the direction a reader would follow

`andi.b #$06, d0  // $06 = RF_XFLIP|RF_YFLIP` — but `RF_XFLIP = 1` and `RF_YFLIP = 2` are **bit
numbers**, so `RF_XFLIP|RF_YFLIP` is `3`, not `6`. `$06` is `(1<<1)|(1<<2)`. Line `:81` repeats the
error: "`$F9 = ~(RF_XFLIP|RF_YFLIP)`" — `~3` is `$FC`, not `$F9`. The blessed form
`#(1<<RF_XFLIP)|(1<<RF_YFLIP)` is spelled correctly three times elsewhere
(`load_object.emp:64`, `sprites.emp:390,462`).

**Why it is a trap and not a typo:** it is the exact instruction a reader follows when converting
the magic to the named form, and following it produces `#$03`/`#$FC` — flip propagation then
copies the wrong bits. Drift in the underlying constants *is* caught, but by
`load_object.emp:25`'s ensure, whose message is about the `rol.w #4` placement-flip fold — so
anyone renumbering the RF bits is pointed at a different module and has no reason to open
`animate.emp`. Two-character fix.

### B1-F4 — three unargued explicit `.s` in `Raster_VBlank` (975, 1006, 1051)

`@as_compat` appears **zero** times in the corpus and the file contains no `align` item, so neither
of §1.4's applicable exceptions covers them — while the same file argues its *other* `.s` pins
explicitly (`:1249` prices the encoding at 16/18 cycles). **Severity low and the seat said so:** a
stale `.s` fails loud at link, it cannot mis-execute. Flagged as an unargued departure, not a defect.

### The `mulu`/`divu` census — 9 sites, scored against the conventions' own four points

Two independent instruments agree on the population. §2.1 requires: divisor non-zero structurally ·
quotient cannot overflow · alternative named and rejected · cost **and** executions per frame.

| site | complete? | missing |
|---|---|---|
| `math.emp:117`, `:124` (`GetArcTan`) | **all four** — and it pre-empts the obvious reply by name (the table is indexed by the *ratio*, so a lookup is not division-free) | — |
| `parallax.emp:1882`, `:2134` | points 1, 2 solid | **no cost figure and no execution count — and `:1882` sits inside the per-band loop**; alternative not named |
| `player_ground.emp:853`, `:856` | point 3 weak | overflow bound absent; no cycle figure |
| **`player_ground.emp:1041`, `:1044` (`Player_Jump`)** | — | **all three applicable points.** Its entire argument is *"one-shot event, classic Sonic_Jump does exactly this"*, and §2.1's own **"What does not count"** list disposes of that in two clauses |
| `player_glide.emp:226` | count present | cycle figure absent; overflow bound absent |

**The seat found the concrete gap inside the generic one.** `muls.w` into a long cannot overflow —
which is presumably why nobody wrote a bound — but the overflow-capable step is the **narrowing two
instructions later**, `asr.l #8` then `move.w` into a word field. At `:853` that is provable in one
line locally (`d2` capped to `±PHYS_GSP_CAP` ~25 lines above, `|cos| ≤ $100`). At `:1041` the
operand is `PBLK_JUMP_FORCE(a4)`, a ROM physics value read through the block **with no bound stated
anywhere at the site** — the one place in the census where the missing point is missing about
something a reader cannot reconstruct locally.

`mul_const`/`mul_bounded` are healthy: 26 call sites across 9 files, no hand-rolled shift-add chain
where they were available.

### B1's verified-clean, recorded so the next seat does not re-walk it

- **`PBLK_*` is closed, not open.** 21 duplicated offset consts across 8 files, every one bound by
  an `ensure(PBLK_X == offsetof(PlayerBlock, x))` in its own file; the two apparent exceptions in
  `player_common.emp` are `= <guarded base> + 2` and cannot drift independently. A prior sweep is
  recorded at `player_fly.emp:51`.
- **`game_debug.emp`'s 16 explicit `.s`/`bsr.w` are argued**, by a STRUCTURAL WIDTH PIN block at
  `:68` naming the mechanism. The seat flagged this on its first pass and then withdrew it.
- **Jump-table `bra.w` argued at all three sites**, `dma_queue` additionally pinned by
  `ensure(sizeof(DMAEntry) == 14)`.
- **RAM layout clean:** 4 `region`s, 15 `vars` blocks, **zero** hand-placed `$FFFFxxxx` addresses.
- **VDP commands clean:** zero hardcoded command longwords; `vdp_comm` used 71 times across 10
  modules.
- **No runtime computation of a comptime-known value** across 22 candidate sites, all read.


---

## Step 0 addendum — the CI question the hub asked, and aeon's answer is worse than "we have none"

**Asked by the hub after oracle's sweep found its GitHub CI red since 2026-07-22, unread for 46 days.**

**aeon has no GitHub CI.** No `.github/workflows` on `origin/master` or in any tree;
`gh api repos/Volence/aeon/actions/runs --jq .total_count` → **0**, with `gh auth status` confirming
an authenticated account, so the zero is an answer and not an auth failure.

**But aeon has the equivalent surface, and it has been down for nine consecutive nights.**
`aeon-effects-gates.timer` is the systemd user timer CLAUDE.md names as the backstop half of the
2026-08-18 effects-gate ruling — *"the half that fires when the ritual gets skipped."*

| | |
|---|---|
| timer state | **alive**, fired 09:17 UTC today, next in 14h — nothing wrong with the scheduler |
| service result | `Result=exit-code`, `ExecMainStatus=2` |
| last SUCCESSFUL run | **2026-08-28** |
| consecutive failures | **9** — 08-29, 08-30, 08-31, 09-01, 09-02, 09-03, 09-04, 09-05, 09-06 |
| outcome tally in its own log | **10 × `COULD NOT RUN`**, 0 failures, 0 passes since |

`exit 2` is `COULD NOT RUN` in **every** branch of `tools/nightly_effects_gates.sh` — the script's
own header says *"a lane FAILURE and a lane that COULD NOT RUN are both loud — a backstop that
silently can't run is the vacuous-gate pattern this exists to prevent."* It was loud. Nine
`notify-send -u critical` desktop notifications fired and nothing was done, which is oracle's
second half exactly: **the red stopped being read.**

### The mechanism — a self-perpetuating deadlock, not a broken master

Measured, not inferred:

1. `build.sh` runs the **tool-suite pytest lane at line 613**; the sigil ROM build is at **line 786**.
   **The gate runs before the thing it inspects is built.**
2. `tools/test_effects_gates_segments.py::test_segmented_parent_checks_the_row_set_it_aggregated`
   reads `s4.debug.lst` and `demo.debug.lst` **from the working tree**.
3. `.aeon-nightly`'s listings are dated **2026-08-28 04:18** — the last successful run.
4. So every night since, the lane has been asking a 2026-08-28 listing about the day's master.
   It fails (`effects_gates: FAIL — 6 of 15 rows`, sonic4 resolving `[]` symbols against five
   expected), `build.sh` exits 1 at line 614, **the ROM and listings never rebuild**, the artifacts
   stay at 2026-08-28, and the next night is identical.

**The loop cannot break on its own.** Nine different master SHAs produced the identical failure
because none of them was ever actually built.

**Master is not broken:** the full tool suite on `61f22403` is **2599 passed, 3 skipped, 0 failed,
exit 0** (aggregate, unpiped).

### And the same test is a three-state guard, which is the part worth booking

Measured on three trees at the same content:

| tree | listings | result |
|---|---|---|
| `.aeon-lens-pin` (`61f22403`, clean, no artifacts) | absent | **SKIPPED** — exit 0 |
| main `aeon` (`61f22403`, artifacts present) | fresh | **PASSED** |
| `.aeon-nightly` (`ab5dfc68`) | **9 days stale** | **FAILED** |

So it is vacuous when the artifacts are missing, correct when they are fresh, and **false-red when
they are stale** — and the false red is the state that jams the loop. A skip and a pass are not the
same result, and only one of them was ever going to be noticed.

**This is the hub's "guards that exist only to shout when a corpus is missing" in its third form:**
here the guard shouts when the corpus is *stale*, and shouting is what keeps it stale.

**Booked as an owner-facing row.** The one-line fix is for the nightly to clear its artifacts before
building (or for the lane to refuse a listing older than the checkout), but the ordering question —
a listing-reading gate running 173 lines before the listing is produced — is the real defect and is
not mine to settle inside a sweep that lands no fixes.


---

## Seat B2b — cross-file duplication, DATA-FIRST walk

Machine-swept exhaustively over 185 non-generated `.emp` files: all **62** structs (offsets
recomputed from field types and compared against every `// $HH` comment); all **2,102**
`const`/`equ` declarations, with every multi-site name enumerated and both values compared (24
found); all `[T; N]` literal-length arrays in `engine/ram.emp`; all 4 `region`/`vars` blocks and 11
`Sst.sst_custom` overlays; all **1,296** `ensure()` sites grepped by subject for each fact booked
as unguarded. **89 struct-offset comments across 9 fully-resolved structs: zero mismatches.**

### B2b-1 — `sizeof(Sec)` is 34; the file that declares it says 66 — and the controller closed its follow-up

`engine/structs.emp:2` opens *"Sec (the **66-byte** section descriptor)"*. Computed from the field
types at `:133-158`: 7 × `*u8` + `*u8` + `u16` = **34**. Two `ensure(sizeof(Sec) == 34)` pin the
value (`section.emp:42`, `tile_cache.emp:36`); nothing reaches the prose. The 2026-09-04 nine-dead-
fields deletion took it 66 → 34 and updated ENGINE_ARCHITECTURE and DEFERRED_WORK but not the
declaring module's own first sentence. Sharp-edged: the same sentence's four other sizes are all
correct (Act 40, DMAEntry 14, parallax_config 30, VdpShadow 19 — all re-derived).

**The seat named its own highest-value follow-up and could not run it** — `structs.emp` calls itself
*"the SOLE AUTHOR of these layouts"* and names three out-of-assembler readers carrying their own
copy of the stride, all in `tools/`, out of seat scope. **Controller ran it. The result is clean in
the direction that matters and dirty in a new one:**

| reader | executable stride | prose |
|---|---|---|
| `tools/boot_override_gate.py` | **`SEC_SIZE = 34`** ✓ | `:144` — *"66 → 34 on 2026-09-04, painted-regions audit row 3"* ✓ **correct, because it recorded the transition rather than the value** |
| `tools/preset_lab_witness.py` | **`SEC_SIZE = 34`** ✓ | `:61` — *"`Act.sec_grid_ptr` + cursor \* **66**"* ✗ **stale, and contradicted by its own code 70 lines below** |
| `tools/parallax_crossing_gate.py` | no stride constant — refers to `sizeof(Sec)` symbolically | ✓ |

**So no wrong stride is executing anywhere.** The defect is entirely in prose, and it is in **two**
files. The one file that got it right is the one that wrote down *the change* instead of *the
number* — which is the same lesson as step 0's misplaced correction, arrived at from the opposite
direction.

### B2b-2 — `Sound_Dbg_Mirror` is described twice, with two different layouts, and it is an external-consumer surface

`engine/ram.emp:1063-1065` says *"**5 SeqChannel slots** … 64 + 78 + 32 = **174** <= 176"*.
`engine/debug/sound_debug.emp:19-51` says *"3 slots is the window"*, `SEQ_MIRROR_CHANNELS = 3`,
and spells the layout out: header `[64..71]`, ch0 `[72..91]`, ch1 `[92..111]`, ch2 `[112..131]`,
trace ring `[132..163]` — re-derived as 64 + 8 + 3×20 + 32 = **164**. The code side is internally
consistent. `ram.emp`'s 174 implies five 14-byte slots, **a layout nothing in the tree emits**, and
its stated 2-byte margin is really 12.

**Why it matters more than a comment usually would:** the field exists to be read from *outside the
assembler*. A consumer decoding by `ram.emp`'s description reads five 14-byte slots from +64; the
bytes are three 20-byte slots from +72 with the ring at +132, not +142.

**And the guard cannot catch it.** `sound_debug.emp:59`'s `ensure` bounds the code side against a
**hand-copied literal 176**, not against the reservation — there is no `Sound_Dbg_Mirror_End` mark,
so the `extern()` span idiom this tree uses everywhere else (`Raster_State`, `Palette_State`,
`Parallax_State`) was unavailable and a literal was copied instead. Shrinking the `[u8; 176]`
leaves that guard green.

### B2b-3 — `PlayerV` "spends 26" of 30; it spends 27

`player_common.emp:119` states the budget for the next ability author. Accumulated from the overlay
at `:93-152`: `ground_speed`(0) … `instashield`(26) = **27**. `instashield: u8` was added after the
sentence. **Headroom is 3 bytes, not 4.** Two stale riders in the same block: `even_pad` no longer
makes the overlay even (27 is odd — harmless, it is a view not an array stride), and `xover_cell`
cites a *"24-byte stride"* where the real slot stride is `sizeof(Sst)` = `$50`. An actual overflow
is build-fatal; the stated **headroom** is guarded by nothing.

### B2b-4 — the Z80 value mirrors: 10 pairs, comment-only, and the tree already has the mechanism it did not apply

Seam-1 injects a fixed const list, so `z80_sound_driver.emp` and `sound_sequencer.emp` genuinely
**cannot** `use` the authority — both files say so at length. The tree's answer for the *address*
mirrors is a two-sided absolute pin (`ensure(SND_PAUSED == $1CD3 && …)` on both the mirror and the
authority, `sound_constants.emp:79`). **That pattern was not extended to the value mirrors.** Ten
pairs, all agreeing today, none pinned on either side.

**The sharp one is `YM_ADDR_TO_DATA_MIN_T`** — the YM2612 address→data spacing floor in Z80
T-states, consumed by **twelve build-fatal `ensure(cycles(a,b) >= YM_ADDR_TO_DATA_MIN_T)` guards**
across three modules. A copy that drifted *low* would not fail; it would make that module's twelve
guards **silently accept insufficient hardware spacing** — an always-green guard reached through
duplication rather than through a bad comparison.

`MEV_EXT` is doubly loose: the authority pins nearly every neighbour absolutely (`MEV_TEMPO`,
`MEV_LFO`, `MEV_PORTA`, `MEV_DETUNE`, `MEV_MACRO`, `MEV_PAN`, `MEV_OPBIAS`) and skips the one
constant that has a mirror.

### B2b-5 — the collected/killed bitmask width is unpinned while its identical twin one block away is pinned

`COLLECTED_MASK_BYTES` = 16, `MAX_LIST_ENTRIES` = 128; 16 × 8 = 128 ✓ today, stated nowhere,
checked by nothing. Its twin over the same index space **is** pinned:
`entity_window.emp:95 ensure(ENTITY_LOADED_OBJ_OFFSET*8 == MAX_LIST_ENTRIES)`.

**Symptom, spelled out:** lower `KILLED_BITMASK_OFFSET` and `bset d1, COLLECTED_BITMASK_OFFSET(a0,d0.w)`
overflows the collected mask into the killed mask — a collected ring silently marks an object dead,
a killed object silently un-spawns a ring, for the whole act. The DEBUG
`assert.w d1, lo, #MAX_LIST_ENTRIES` on the same lines cannot see it: it bounds the index against
`MAX_LIST_ENTRIES`, which is precisely the number that got out of step. And `COLLECTED_SLOT_SIZE`
being correctly *derived* is what makes the failure a short mask inside a correct-looking slot
rather than an overrun the layout would catch.

### B2b-8 — ~90 comments cite `.asm` authorities that do not exist

`engine/system/constants.emp` opens by saying `engine/constants.asm` no longer defines these, then
says *"(mirrors engine/constants.asm)"* over **10** of its own blocks (`:21,30,44,48,62,87,94,144,320,493`).
That file is absent. Corpus-wide: `engine/constants.asm` ×14, `ram.asm` ×13, `main.asm` ×11,
`player_common.asm` ×7, plus ~30 more. The only `.asm` that exist are the two `game_root.asm` and
the vendored debugger. (`sonic3k.asm` ×92 is the legitimate S3K reference.)

These read as *"there is a second copy, keep it in step."* There is not.

### B2b's verified-clean, and the mechanism worth copying

`PBLK_*` (19 declarations, every one `offsetof`-pinned) is the best mechanism found.
`VRAM_PLANE_B` vs `VRAM_PLANE_B_BYTES` is held by a guard whose message names the exact failure.
The anchor-sweep ladder pins are **property re-derivations, not copies** — each brackets against
the real constant, so it stays correct whichever literal moved. `COLLECTED_PARK_*` at four sites,
both engine mirrors `extern()`-pinned. All 16 `SceneCfgN` identity pins present.

**The seat's own honesty about its limits, recorded:** it executed no harness and ran no red-first,
so every *"this IS guarded"* rests on reading the guard rather than seeing it fail — and every
credited `ensure` is contingent on **reachability** (EMP_PITFALLS §3: a guard in a module outside
the target's `use` closure is dead, silently). It said so rather than letting the greens stand
unqualified.

---

## Seat C1a — instruction-level performance, HOT-PATH-FIRST

Every cycle figure priced against **sigil's own `crates/sigil-isa/src/m68k_cycles.rs`** at
`ebc3d17e` — the table `CODING_CONVENTIONS.md` §2.1 names as the authority — with each cell read
out of that file rather than from memory, and listed in the report. Frame denominator **128,010
cycles**, the codebase's own figure.

### C1a-1 — `Draw_Sprite` band-slot arithmetic, 14 cycles per registered object

`engine/objects/sprites.emp:156-170`. Two independent costs: a `lea Sprite_Band_Counts, a1`
**reloading the value `a1` already holds** on both entries to `.band_has_room` (the code clobbers it
itself, then pays 8 to put it back), and `lsl.w #6` doing one bit too much — `band*64 + count*2` is
`(band*32 + count)*2`, and with `band ≤ 7`, `count ≤ 31` the intermediate is ≤ 255 and the doubled
result ≤ 510, **bit-identical to the current ceiling**. 82 → 68 cycles; the only reordering is
between two writes to different arrays that nothing reads in between.

**Frequency, established from `constants.emp:88-91`:** ceiling is the object population
2+40+8+16 = **66**, and band capacity 8×32 = 256 so nothing caps earlier. Worst case ≈ **924
cycles/frame (0.72%)**; ~350 at a typical 25 objects. **Real, not absorbed** — register arithmetic
and two RAM writes, long before the SAT ships.

### C1a-2 — `Parallax_Fill_PerLine .lp_both`: 44 cycles/line available, the stated blocker is refutable, and the frequency is ZERO today

`parallax.emp:3323-3348`. The two single-channel loops were already converted to pointer walks; this
one still pays 30 cycles of index recomputation per channel per line (60/line, against a ~132-cycle
body). **The module's stated reason for not converting it — *"no second free address register"* —
does not hold:** the walk pointers can be `a5`/`a6` themselves, since the bases they hold are only
needed at the 256-byte wrap, and at that instant the walking pointer *is* `base + 256`, so the base
is recovered by `suba.w #256` with no register at all.

**And then the seat checked the frequency and refuted its own finding's value.** `.lp_both` needs a
band with both deform pointers non-NULL and both `dsa`/`dsb` != 15. Every layer in the four
generated act-1 scenes and in `Scene_OJZ_Default` is `dsa: 15, dsb: 15` with no `deform_fg`/`deform_bg`.
**`.lp_both` executes on 0 lines in the shipped act; cycles×frequency = zero.**

It then named what would have falsified that, and found the loaded gun: `Scene_WindyHaze`
(`ojz_scenes.emp:926-944`) has five layers at `dsa: 3`, `dsb: 0..3` with both tables attached —
**one section binding away** from putting 224 lines through this loop at **≈ 9,900 cycles/frame
(7.7%)**.

**Recommendation adopted as the seat gave it:** do not restructure on cycles-today. **Do correct the
comment**, which currently asserts an impossibility that is not one — the kind of note that stops
the next person from looking.

### C1a-3 — `perform_dplc` entry decode, and the seat's own "not worth it"

`lsr.w #8` + `lsr.w #4` (36 cycles) does what `rol.w #4` + `andi.w #$F` does in 22. 14 cycles per
DPLC entry, +2 bytes. Peak ~11 entries/frame from the module header's own measured figures →
**154 cycles/frame (0.12%)**, zero on most frames. **The seat classified this itself as the
"measurable but not worth it" case** by the codebase's own bar, and recommended landing it only if
`dplc.emp` is open for another reason. Recorded with that verdict.

### C1a's rejected list — the part that saves the next walker time

- **`Emit_ObjectPieces` per-piece SAT cap** looked like the largest single line item (640 cycles/frame)
  and is **a wash**: the hoist costs ~28 cycles per call × ~20 calls ≈ 560 against 640 saved, net
  **0.06%**, in exchange for moving a live correctness backstop out of the loop — and the per-piece
  check is load-bearing because the pre-check uses a cache its own comment says is 0 for uncached
  objects.
- **`VInt_DrawLevel` drain loops** — **the confound case, correctly identified.** The destination is
  the VDP data port during blanking, so the loop is FIFO-bound and any instruction removed is a
  cycle spent waiting. **Absorbed. Do not optimize.**
- **`Render_Sprites` step-from-stack** — 160 cycles/frame available, buys a DEBUG/release register-
  allocation divergence in the engine's tightest register budget. Declined.
- **`.band_loop`'s `lea`** is **not** loop-invariant work left in a loop: `a1` is genuinely clobbered
  inside the band body. Correct as written.
- **Instruction-selection smells: zero.** Corpus-wide greps for `move.w #small` where `moveq`
  reaches, `addi/subi #1..8` where `addq/subq` reaches, and `cmpi #0` where `tst` reaches returned
  **zero** for the latter two and six trivial hits for the first.

### C1a's own stated blind spot, which I am recording rather than smoothing over

**It did not open `engine/sound/` at all (~6,500 lines, and the 68k side runs every frame), nor
`player_common/air/sensors/climb/fly/instashield` (~5,300 lines of per-frame code).** Its closing
sentence — *"I would not read this report's silence about them as a clean bill"* — is the correct
reading and is carried into the packet as such.

It also flagged that **every cycle count assumes sigil emits the mnemonic the source spells**, and
that a bare `bcc` relaxed to `.w` costs 12 not-taken rather than 8, which several hot loops are full
of. The pin has no build artifacts, so it could not check. **Controller TAG: read `s4.lst`.**


---

## Seat C2a — gate-blind hazards, FORWARD walk

Guard census, obtained by counting rather than by impression: **1,341 `ensure()` sites across 128 of
187 `.emp` files**; **59 files with zero `ensure`** (including `games/sonic4/config/ram.emp` 515 L,
`engine/objects/children.emp` 696 L, `engine/level/plane_buffer.emp` 660 L,
`engine/objects/collision.emp` 581 L, `engine/system/vblank.emp` 477 L); **77 `assert.<sz>` across 28
files, all zero-byte in release**; **25 Python gates invoked by `build.sh`**; **84 pytest files**;
**52 expect-fail rows over 42 poison modules**; and — the number that matters —
**0 sigil warnings inspected by the build.**

The seat's framing is the right one and I am adopting it: *"this tree's guard density is genuinely
high, so the blind spots are not 'nobody wrote a guard' — they are guards that check a hand-typed
restatement of the thing instead of the thing."*

### C2a-H1 — a per-object VRAM window is spelled three times, nothing binds any pair, and TWO live spellings are over-permissive

Three independent spellings of "this object's art fits its VRAM window": the TOML→generated wall
(a **literal**), the object's own hand-typed tile constant, and a **blob-derived**
`dplc_peak_tiles(...)` guard whose ceiling is **hand-chosen**. None is pinned to another.

**H1a — `games/sonic4/data/characters/tails_data.emp:100`.** The blob-derived guard's ceiling is
`VRAM_HSCROLL_TABLE / TILE_SIZE` = tile **1504**. The real next allocation is
`VRAM_DEBUG_BGANIM_TAG` = **1501**. Three tiles of permitted overlap. Symptom: the appendage's DPLC
DMA writes over the BG-anim debug glyphs whenever Tails is on screen.

**H1b — `games/sonic4/player/player_instashield.emp:469`.** Ceiling `VRAM_TEST_SONIC` = **960**;
real next allocation `VRAM_DEBUG_PRESET_READOUT` = **957**. Same three-tile shape.

**Every constant the seat derived checks out exactly** — controller re-read all five from
`constants.emp:494-501`.

**And the file asserts the opposite in prose.** `tails_data.emp:87-88`: *"Both bounds are read from
their owners … so moving either neighbour re-checks these automatically."* **That sentence is
false.** The ceiling was correct when written and became wrong silently when `gen_vram_map`
allocated `debug_bganim_tag` into the gap. A reader auditing this allocation reads that sentence
and stops looking.

**CONTROLLER RAN TAG-1, AND THE ANSWER CAME WITH A THIRD OUTCOME THE SEAT DID NOT PREDICT.**

Pointing each ceiling at its real neighbour, on a detached `61f22403` worktree:

| step | result |
|---|---|
| 1. tighten both ceilings, nothing else | **exit 1** — `unknown name VRAM_DEBUG_BGANIM_TAG`, `unknown name VRAM_DEBUG_PRESET_READOUT` |
| 2. add both names to the two modules' `use` lines, ceilings still tight | **exit 0 — GREEN** |

So the seat's binary — green means latent, red means live — resolves **GREEN: H1a and H1b are
latent, today's DPLC peaks fit the tight bound, and the fix is free.**

**But step 1 is the more interesting result, and it explains the defect rather than just measuring
it.** The correct ceiling names are **not in either module's import closure**. `tails_data.emp:27`
imports `{VRAM_TEST_SONIC, VRAM_TEST_OBJ, VRAM_TAILS_APPENDAGE}` and `VRAM_HSCROLL_TABLE` — and the
guard reached for `VRAM_HSCROLL_TABLE`, **a name that was in scope**, rather than the true
neighbour, which was not. The `.emp` import closure made the wrong symbol the convenient one.

**That changes the fix.** It is not "name the right symbol" — it is that the generator emits
adjacency constants into a namespace the guards that need them cannot see without an explicit
import, so the path of least resistance is a wrong ceiling. The seat's own suggested home for the
real fix (have `gen_vram_map.py` emit the blob-derived cross-pins) is correct and is a `tools/`
parcel.

### C2a-H1c — the clean green-and-corrupt case

`RING_SPARKLE_TILES` has a self-consistent triangle with its blob length and byte length, and
**nothing ties it to the TOML's `4`.** Re-export a 6-tile sparkle, the blob-length ensure fires, the
author makes the obvious repair, **build goes green**, and `ojz_scroll_test.emp:656` DMAs 192 bytes
to tile 924 → tiles 924..929, clobbering insta-shield tiles 928-929. The sparkle looks right; the
**insta-shield's first two tiles** render as sparkle pixels, visible only when the shield is used,
arbitrarily far from the edit. Same shape at `dust_data.emp:34`, where a hand-typed `12` stands in
for `VRAM_RING_SPARKLE - VRAM_DUST_SPINDASH`.

### C2a-H2 — Map↔DPLC frame-count binding exists for exactly ONE asset in the tree

`player_instashield.emp:456-463` is the complete pattern — map frame count, DPLC frame count, zero
mismatches, last-frame pieces — on a 16-frame asset. **Sonic's own pair has none of it.** Six
ensures on Sonic's data, every one about offset range, VRAM window, entry budget or tile ceiling;
**not one binds `_map_sonic`'s frame count to `_dplc_sonic`'s**, and nothing binds `Ani_Sonic`'s
frame bytes to either. Same for Tails, Knuckles, dust, particle, spring, appendage. The helpers
exist but are private to `player_instashield.emp`.

**Symptom traced through the code:** `animate.emp:105-108` accepts any frame byte 0..$F6 with no
upper bound; `frames.emp:59-66` then reads an offset word from *past* the offset table — i.e. from
mapping piece data — and takes an arbitrary byte as the piece count. Garbage sprites at garbage
coordinates.

**Severity amplifier the seat found inside its own finding:** `sprites.emp:312`'s SAT overflow
pre-check reads the **cached byte** `Sst.sprite_piece_count`, while the emit loop at `:336` reads
the **full word** freshly. Under valid data they agree; under a corrupt frame header the guard that
exists to stop a SAT overrun is reading a truncated copy of the number the loop will use.

### C2a-H3 — the mechanism that makes every `ensure` real is a manual ritual with no automation

EMP_PITFALLS §3: an `ensure` outside its target's `use` closure **never evaluates**. The prescribed
check is a `SIGIL_WARNINGS=full` grep. **`build.sh` contains zero occurrences of `SIGIL_WARNINGS`,
`module.unreachable` or `clobber`; no gate tool reads the warning stream either.** The doc's own
baseline history (25 → 45 → 50 modules, ending *"nobody re-baselined it"*) is the record of it
having gone quiet once already.

**And this compounds H1 and H2:** the natural repair for either — put the missing cross-pins in a
new module — has a live failure mode that produces no signal, because a `map.toml` `order` row is
**not** reachability.

### C2a-H4 — DMA sub-queue contiguity is comment-only, and the guard note names a deleted file

`Init_DMA_Queue` unrolls 32 slots × 14 bytes = 448 bytes from `DMA_Queue`, assuming one contiguous
block in one order. **No `ensure` binds `DMA_Queue_End - DMA_Queue` to `DMA_TOTAL_SLOTS *
sizeof(DMAEntry)`.** Insert any field between `DMA_Critical` and `DMA_Important` — a per-queue
counter placed next to the queue it counts, which is where anyone would put it — and every
Important/Deferrable slot's pre-laid VDP register markers shift out of alignment, so the drain
writes transfer parameters **into the wrong VDP registers**.

**The guard note is worse than absent:** `dma_queue.emp:26-27` says *"LOCKSTEP: dma_queue.asm spells
this as a `rept` unroll — the byte gates are the guard."* **`engine/system/dma_queue.asm` does not
exist**, and no tool references `Init_DMA_Queue`, `fill_slot_markers` or `DMA_TOTAL_SLOTS`. A
developer changing a slot count reads "the byte gates are the guard," concludes it is covered, and
stops. Two more instances of the same stale claim at `core.emp:41-43` and `:35`.

### C2a-H5 — the sprite-cache staleness net is DEBUG-only AND behind a filter the failure trips

All **12** direct writers of `mapping_frame`/`mappings` are compliant today — the seat enumerated
them. The only enforcement is inside `if DEBUG == 1`, so **`s4.bin` has no net at all**; and the
assert sits **downstream of the piece-count pre-check**, so if the stale count is large enough to
trip `bhi .next_object` the object is skipped *before* reaching its own staleness assert. **The
detector is unreachable in exactly the sub-case where the staleness is most damaging.**

---

## Seat C2b — gate-blind hazards, Z80-AND-SEAM-FIRST walk

Seam census: **78 crossings enumerated, 62 individually assessed + 16 as a class; 3 verified
findings, 3 characterised suspicions.** The seat's own headline: *"this is the most carefully-guarded
seam code I have walked in this tree … Three things got through, and all three are of the same
species: a rule that was written down correctly and then applied to some of its sites but not all."*

### C2b-V1 — an IRQ6 landing in `Sound_PlayMusic`'s bus-hold spin deadlocks the 68k

`sound_api.emp:210-215`. The file states its own invariant at `:5-8`: every transaction holds the
bus **with interrupts masked**. Every other hold in the file honours it — `Sound_PostByte`,
`Sound_PlayMusic`'s own param post, `Sound_ReadStat` via `with ints_off`; `Sound_Init` and
`Sound_DrainSfxRing` via `move.w #$2700, sr`. **`.await_slot` at `:211` has neither.**

**The interleaving, spelled out.** `z80_bus.emp:26-33` puts the request write *outside* the poll
loop. Mainline writes `$0100` and spins. IRQ6 fires; `VInt_Level` runs `with z80_stopped { … }`,
whose exit writes `$0000` — and **the hold is a latch, not a counter** (`z80_bus.emp:8-10` says so:
*"an inner release frees the outer hold"*). The outer request is cancelled. `rte`. Mainline resumes
at `.wait_z80`, reads bit 0 = 1, branches back — **and nothing below the label re-issues the
request. Infinite spin.**

**The watchdog cannot save it:** `SPIN_WATCHDOG_LIMIT` decrements on the **outer** `.await_slot`
iteration while the hang is inside the context's spliced `.wait_z80`, one level below the counter's
granularity. **The shape that exists to make this loud is exactly the shape that stays silent.**

**Shape scoping, and the seat stated it honestly against its own finding:** both callers are gated
behind `SOUND_DEBUG_HOTKEYS && SOUND_DRIVER_ENABLED`, so **this is NOT reachable in canonical
`s4.bin` / `s4.debug.bin`.** It lives in the off-canonical `config_a` profile — which is the only
shape that can play music, i.e. the listening-test shape, under a hotkey a person presses
repeatedly. The seat's own reading, which I share: *"the worst place for it rather than a
mitigating one."*

**And it refutes a nearby claim:** `parallax.emp:1715-1721` asserts *"This is the tree's one atomic
Z80 hold that must also stay masked."* `sound_api.emp:211` is a second one.

### C2b-V2 — the 2026-08-09 banked-ROM/DMA ruling was applied to 1 of 3 tick paths

The `$8000` bank window is the Z80's only 68k-bus access. Three paths read through it: the hot-loop
FILL (**guarded**, checked every pass), the bulk refill (**guarded**, fail-closed), and
`Run_SeqFrame_OnSongBank` → `Sequencer_Frame` plus `Snd_PollMailbox_Banked` (**no check anywhere**).
`SND_CTRL_DMA_ACTIVE` has exactly **two** read sites in the whole Z80 corpus.

**Structurally unable to see the flag:** the hot loop's timer poll at `:407` branches to the tick
**before** `.dma_check` at `:414`, so the DMA test is downstream of the timer test.

**Symptom:** the sequencer consumes a corrupt opcode — `SND_SEQ_BADOP`, a wrong note or patch, a
dropped channel, or a stream pointer that walks off into garbage until the next loop point. Timer A
is near but not locked to the display rate, so the tick precesses and parks in the DMA window for a
run of consecutive frames every beat period: **the "it goes wrong for a second every N seconds"
signature.**

**Evidentiary footing, stated by the seat rather than glossed:** the hardware hazard itself is
unverifiable here — the ruling says so, and there is no real hardware in this workspace. What is
being reported is **not a new hardware claim**; it is that a ruling already accepted on this tree's
own terms was applied to 1 of 3 sites, which is a purely static fact, checked exhaustively.

**Adjacent stale comment:** `:1211-1212` still describes the bulk refill as *"runs THROUGH an active
DMA"*. Since the guard landed it does the opposite — it skips. Both halves of the header are
backwards.

### C2b-V3 — "the ONLY 68k bus hold in the sound build" is contradicted eight lines later

`vblank.emp:120-121` and `:283-284` state it twice. `vblank.emp:290` calls `Read_Controllers`, and
`controllers.emp:39` opens `with z80_stopped {` — **unconditional by design**, wrapping both ports'
full 6-button bursts.

**Derived cost:** ≈1000 cycles ≈ **130 µs at 7.67 MHz**, against the DAC FILL pass pinned at 194
T-states = 54.2 µs. So the hold is **~2.4 sample periods, every frame, at 60 Hz** — BUSREQ halts the
Z80 outright, so `$2A` holds its last value and the DAC goes DC-flat for 130 µs once per frame. **A
periodic 60 Hz artefact on every DAC drum, in every sound-ON shape including canonical `s4.bin`.**

**Why it is a finding and not merely a cost:** the unconditional bracket is defensible on its own
terms and `controllers.emp` argues it correctly — `$A100xx` I/O with the Z80 on the bus is genuine
corruption. What is missing is that **nobody wrote the tradeoff down on the audio side.** The two
headers are eight lines apart and disagree; one of them is lying to the next reader either way.

### C2b's suspicion S1 — the Z80 transitive-clobbers gate does not exist in the repo it guards

`[call.clobbers-incomplete]` lives **entirely in sigil** and is **not part of `sigil build`**. So an
aeon-side edit that under-declares a Z80 proc's transitive clobbers **builds green in aeon**, and is
caught only if someone in the sigil repo runs that test with `AEON_DIR` pointed at the right tree
**and** `SIGIL_STRICT_GATE=1` — without which it prints `skip:` and passes green. aeon's docs mention
it **once**, in a path-enumeration table, never as a ritual; `CLAUDE.md`, `CODING_CONVENTIONS.md`
and `DEFERRED_WORK.md` do not mention it at all.

**The population is not hypothetical:** the tree's own history records **8 genuine under-claims found
the day the fixpoint first ran**, over a 7,900-line sound corpus.

### C2b's clean results, which are half its value

`HBlank_Install`/`Uninstall` vector atomicity **holds** (the 68000 samples interrupts only at
instruction boundaries, and the header's claim is correct and load-bearing). `VSync_Wait`'s
test-then-clear is **unreachable-by-timing** — the next IRQ6 is a full frame away — and the
genuinely racy pair one block above is correctly bracketed with its failure mode written out. The
DMA queue's masking, `requires(vblank)` drains and carry-after-SR-restore discipline are correct at
all four exits. The flag brackets balance in all three procs. And **`DEFERRED_WORK:8098`'s PSG
"never clobbers de" known-bad is FIXED** — the seat checked rather than inheriting the brief's
premise, and told me my brief was out of date.

---

## Seat C1b — instruction-level performance, COLD-FIRST walk

**577 procs extracted, 404 of them call-free leaves.** Frame denominator taken from the tree
(`ENGINE_ARCHITECTURE.md:855-858`, 262 × ~488 = **127,856 cycles**), not from the seat.

### C1b-F1 — the 24-slot System+Effect pools are swept THREE times a frame and are ~90% empty. ~2,780 cycles/frame, 2.2%

**This is the finding a hot-path walk structurally cannot see, and it is exactly why the doubling
exists** — the hot walk reads `jbsr RunObjects` as one line.

| loop | per-EMPTY-slot cost | iterations/frame | total |
|---|---|---|---|
| `TouchResponse.fixed_loop` (`collision.emp:160`) — **nested inside the 2-player loop** | 36 | 24 × 2 = **48** | 1,728 |
| `RunObjects.always_loop` (`core.emp:519`) — called for System then Effect | 44 | **24** | 1,056 |

**2,784 cycles/frame ≈ 2.2%**, and real — 68k work nowhere near a DMA or VDP wait.

**The occupancy claim could have failed, and the seat says how.** It enumerated all **7** corpus
references to `System_Slots`; a single non-test writer would have killed the finding. There is none,
and all five test writers sit inside `if DEBUG == 1`. **In release, all 8 System slots are
permanently empty.**

**The engine already ships the cure and applies it to one pool of three:** the Dynamic pool walks
`Dynamic_Live` in both loops, with the comment *"empty slots cost ZERO (never appended)"*. System
and Effect get the naive sweep.

**The seat scoped its own contribution honestly:** extending the live list to Effects is a design
change, not an instruction tweak — *"my seat's contribution is the number and the frequency
derivation, not the design."* The 8 System slots are the cheap half, provably dead in release.

**And it flagged its own lower bound:** `tst.w Sst.code_addr(a3)` at offset `$00` is 8 cycles if
sigil folds the zero displacement and 12 if it emits `0(a3)`. **2,784 is the optimistic end; 3,072
is the other.** Controller TAG: read the `.lst`.

### C1b-F2 — one of three sibling loops builds its bank base before the emptiness test

`core.emp:521-527` pays `moveq`+`swap` (8 cycles) on **every empty slot**; `.culled_loop` and
`.frozen_fixed_loop` in the same file test first and build after. **Three siblings, one out of
step.** ≈ −144 cycles/frame for +2 bytes.

### C1b-F3 — two leaf-local costs in `Collision_GetType` a hot walk sees as one `jbsr`

A per-query re-derivation of a value its producers write **at most twice a frame** (−8/call), and a
`mul_const.w #80` where a 30-entry table bounded by `TILE_CACHE_COLL_ROWS` would be 18 cycles
(−14 to −28/call). **The call chain is the seat's method and its whole advantage:** two call sites →
probe cores → sensor pairs → floor/ceiling/wall per frame × 2 players = **≈8-14 calls/frame**, more
airborne. ≈260-430 cycles/frame. **The seat's own verdict, which I keep:** *"measurable, and I would
not spend 60 ROM bytes plus a new RAM mirror for it on its own."*

### C1b's prohibition — the obvious optimisation here corrupts memory

On `perform_dplc`'s in-loop `movem.l d2-d4/a2` (84 cycles/entry), which it verified **honest** —
all four registers are genuinely live across the call and `QueueDMA_*` really does clobber them:

> **Do NOT narrow this to `movem.w d2-d4`** (a tempting −40). `vdp_comm_reg` opens with
> `lsl.l #2, {reg}` — a **long** shift on d2 — so a word restore that sign-extends a dest with bit
> 15 set produces a wrong VDP command word. **Every value in that set looks like a word; one of
> them is not used like one.**

That prohibition is worth more than most findings, and it is recorded here so the next reader who
spots the same 40 cycles meets it before acting.

### C1b's other clean results

`ObjectMove{,X,Y}` is at the canonical minimum (it costed the alternatives and the shipped form wins
by 28 cycles/axis). `Canopy_Persist`'s over-wide `movem` saves 15 registers the body never writes —
**and is still correct to keep**, being DEBUG-only and once-per-sweep; recorded because "the body
writes no register" is precisely the trigger that should make someone look, and the look comes out
clean. `Section_FlatIDXY`'s repeated-add multiply amortises to **≈14 cycles/frame** and its header's
*"clarity over cycles"* is honest. A **62-site `movem` audit** found no second over-wide save. A
sweep of all **57** `comptime fn -> Code` definitions with exact expansion counts found one
2-byte-per-site reorder and nothing else.


---

## Controller result — C2b's suspicion S1 is now VERIFIED, with a control

C2b suspected that `[call.clobbers-incomplete]`, the fixpoint catching a Z80 proc that
under-declares what its callees destroy, **is not part of aeon's build at all** — it lives in sigil
and runs only if someone there points `AEON_DIR` at the right tree with `SIGIL_STRICT_GATE=1`. It
labelled this a suspicion because it could not run either side. **Both sides were run.**

The mutation is the historical instance C2b named: remove `iy` from `Sfx_Frame`'s `clobbers` set
(`engine/sound/sound_sfx.emp:253`), on a detached `61f22403` worktree, quoted back from disk.

| run | result |
|---|---|
| **aeon `FAST=1 DEBUG=1 ./build.sh` on the mutant** | **exit 0 — GREEN.** No error. No new warning: the summary line is **identical** to the clean tree's, `proc.clobber-undeclared 72` unchanged. Aeon's build cannot see it at all. |
| **sigil `z80_clobbers_incomplete` against the mutant** | **exit 101 — 3 passed, 2 FAILED** (`honest_corpus_no_in_scope_firings`, `dispatch_submachine_is_excluded_but_present`) |
| **CONTROL: the same sigil test against the unmutated pin** | **exit 0 — 5 passed, 0 failed** |

The control was run **because** two tests failed rather than one, and without it I could not have
attributed the second to the mutation. Both flips are mine.

**So the asymmetry is now measured on both axes:**

|  | 68000 | Z80 |
|---|---|---|
| **under-declare** (write more than declared) | **build-fatal** in aeon | **invisible** to aeon; caught only in sigil, under an opt-in env var |
| **over-declare** (declare more than you write) | **green and silent** | **green and silent** |

Three of those four cells are unguarded from inside this repo. And `CODING_CONVENTIONS.md:492`'s
*"These are compiler-verified"* is the sentence every reader is relying on.

**The distribution failure is the finding, not the gate.** Sigil's side is careful — it even ships a
`red_fixture_sfx_frame_iy_underclaim_fires` test for exactly this mutation, and it passed. The gate
exists, works, and lives where the person about to break it is not looking: aeon's docs mention it
**once**, inside a path-enumeration table, never as a ritual, and `CLAUDE.md`,
`CODING_CONVENTIONS.md` and `DEFERRED_WORK.md` do not mention it at all. Over a 7,900-line sound
corpus whose history records **8 genuine under-claims found the day the fixpoint first ran**.

---

## Seat C4a — algorithmic altitude

### C4a-1 — the expensive gate runs before the cheap one, on every entity spawn path

`engine/objects/entity_window.emp`, both spawn sites (`TrySpawnRing:963`, `TrySpawnObject:1187`).
Gate order in both: Y-band compare (cheap, correctly first) → **`Collected_CheckRing`, a 9-slot
linear tag scan** → **`EntityLoaded_Test`, one `btst`**. Both later gates branch to the same
`.gated` label and do nothing else, so the order is free to choose.

**Controller verified the order directly:** in `TrySpawnRing`, `jbsr Collected_CheckRing` is at
relative line 20 and `jbsr EntityLoaded_Test` at line 29 — **nine lines later** — both followed by
`bne .gated`.

**And the architecture doc already describes the other order.** `ENGINE_ARCHITECTURE.md:2964`, read
in full by the controller: *"Loaded bits make this idempotent — already-loaded entities are one
btst+skip."* **That is the intended algorithm, and it is not what the code does.** Fixing the order
makes the shipped code match a sentence already in the architecture doc — which is the cheapest kind
of change to justify.

**Cost:** ≈200 cycles per already-loaded candidate (≈340 through the scan path vs ≈145 through the
`btst`), hand-derived. It multiplies in `EntityWindow_RescanY`, which on every 128 px of camera-Y
travel re-offers every ROM entry up to the X ratchet: ≈8-12 K cycles on shipped OJZ act 1 (**6-9% of
a frame**), and ≈36-54 K (**28-42% of a frame**) at the 40-50 rings/section density **ARCH §4.9
itself states the system is designed for**.

**The cross-reference that makes this worth landing:** `DEFERRED_WORK:7460` has booked *"RescanY
burst is unbudgeted"* since 2026-06-11 **without ever naming a cause**. The seat checked and the
ordering is booked nowhere. This is a candidate cause for a four-month-old open worry.

**Fix: swap two instruction orders.** Nothing new is needed — `EntityLoaded_Test`, the mask, and the
`.gated` convergence are all already called from this exact position. A ring in the buffer is by
construction not collected, so no reachable state distinguishes the orders.

### C4a-2 — `Collected_FindSlot`'s answer is loop-invariant per window entry, recomputed per candidate

The `section_id` handed to the slot scan is **constant for the entire walk of one window entry** —
the three walkers each hold `a1` fixed across their whole loop — so a 9-slot scan is repeated per
candidate for an answer that changes at most 4 times per frame.

**The seat checked stability rather than assuming it:** slots are claimed/evicted only by
`Collected_ClaimSlot`/`Collected_UpdateCenter`, both inside `BuildEntries`/`Slide`; the `Mark`
routines only `bset` inside a slot they found. Nothing during a walk moves a slot.

Hoisting turns `O(candidates × 9)` into `O(4 × 9) + O(candidates × btst)`, and **composes with
C4a-1**: the reorder removes the scan for already-loaded candidates, the hoist removes it for the
rest. Needs no new RAM — the walkers have a free address register. **Land C4a-1 first**; this one
changes three call sites and a callee contract.

### C4a-3 — the despawner recomputes an address its sibling walks with a pointer, and the cure is written down one file over

`EntityWindow_DespawnRings:1428` rebuilds the buffer address from the index every iteration (×6
chain + `lea`); `RingCollision` (`rings.emp:297`) walks the same buffer with the same swap-with-last
semantics using **a rolling pointer**, and its header states the cure verbatim along with the safety
argument — *"swap-with-last removal only rewrites the removed slot from an already-visited HIGHER
index"* — which applies to `DespawnRings` unchanged. ≈30 cycles/ring; ≈600/frame shipped, ≈3.8 K
(3.0%) at buffer capacity.

**The seat did the bookkeeping that stops double-counting:** `DEFERRED_WORK:7470` already books *a
different* invariant in this same loop (the Y band bounds, ~3.5 K cycles at capacity) and does not
mention the address chain. Taking both roughly **doubles that entry's refund** — and the entry's
"not worth a dedicated session" is right for either half alone and weaker for both.

### C4a-4 — a product computed, destroyed, and immediately recomputed with a loop

`Section_GetSecPtrXY` computes `sec_y * grid_w + sec_x`, then overwrites `d0` twice; `BuildEntries`
calls `Section_FlatIDXY` **on the very next line, with the same registers**, to recompute it — via a
repeated-add `dbf` loop costing `24 + 14·sec_y`.

**The sibling inconsistency is the sharper half.** `GetSecPtrXY` carries the full §2.1 four-point
argument for its `mul_bounded`. `FlatIDXY`, computing *the same product in the same file*, carries
**no bound argument at all**, and its loop counter is a `GridY` byte — structurally up to 255
(≈3.6 K cycles). **Nothing lints this, because §2.1 polices the multiply and not the loop that
replaces it.**

**Severity today is low and the seat said so plainly:** `GRID_W = GRID_H = 3`, so this costs ~250
cycles *per slide*. **Reported because it degrades along the roadmap's own trajectory** — the
mega-act tech demo is precisely the thing that raises `grid_h`, and this is the one construct in the
section-id path whose cost is linear in it.

### C4a's design notes, correctly labelled as such rather than smuggled in as findings

**D1 — the ring buffer is walked four times per frame in one phase** (despawn, collision ×2 players,
draw). At capacity the collision pass alone is ~18 K cycles = 14% of a frame. **Any real fix invents
a subsystem** — swap-with-last removal is what makes `RingBuffer_Remove` O(1), and preserving order
costs that — so it is a note. Academic at shipped density; real at the density ARCH designs for. The
seat explicitly declined to offer the cheap constant-factor version because that belongs to the
instruction-level seats.

**D2 — `Decode_Factor_A/B` re-decide per-band-constant branches every frame**, where the cure
pattern (hoist and specialize) is stated in the same file's `Fill_PerLine` banner. **Under 1.5%
either way**, hence a note.

### C4a's verified-clean, which is where an altitude seat earns trust

`TileCache_FindStagedBlock` is **already** a hashed lookup where the bucket is the block index —
the seat's target pattern, already cured. `PageCache_Prefetch` deletes its whole ahead-strip walk
for acts that fit the pool, and the degenerate-regime patch **verifies** the page→frame identity
rather than assuming it. `Render_Sprites` dispatches from insertion-built priority bands, not a
per-frame sort. `Palette_Compose` gates every layer behind a staleness bit, **argued as the same
answer rather than an approximation**. `player_sensors.emp` stamps four specialized probe cores from
one `comptime fn` — the build-time principle correctly applied.

**And it named its own biggest gap:** `tile_cache.emp`'s `Tile_Cache_Fill`/`FillColumn`/`FillRow`,
~800 lines of the engine's single biggest per-frame consumer, read only at its entry points. *"If
one more altitude pass is funded, that is where I would spend it."*

