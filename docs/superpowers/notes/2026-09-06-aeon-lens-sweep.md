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

