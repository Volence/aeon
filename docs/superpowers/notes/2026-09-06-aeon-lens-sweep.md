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

