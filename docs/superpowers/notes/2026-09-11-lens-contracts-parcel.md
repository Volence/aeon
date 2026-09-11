# Lens contracts parcel: six zero-byte findings (2026-09-11)

Branch `parcel/lens-contracts-0911`, cut from `origin/master` `cd075f2d` (which contains
`f7406b97`). Six open lens-sweep ids from the bin-B table of
`docs/superpowers/notes/2026-09-11-lens-open-sift.md`: **A2-1, A2-2, A2-5, C3b-4, C1a-2,
B1-5**. Every change is a comment or a documented contract; no instruction was changed.
Every claim below was re-derived from the code at the branch base, not copied from the old
prose, the ledger or the sift. No emulator was run and `tools/effects_gates.py` was not run.

**Effects-gate file touched: `engine/level/bg_anim.emp` (A2-5).** The controller owes the
effects ritual at landing. `engine/level/parallax.emp`, `engine/system/vblank.emp` and the
rest are not on the ritual's list.

## Zero bytes, measured

Base = the four shapes built by `tools/landing_build.sh` at `cd075f2d` before the first
edit (`finished=0`, exit 0). `cksum`:

| artifact | base (`cd075f2d`) |
|---|---|
| `s4.bin` | `3393750122 821103` |
| `s4.debug.bin` | `4112900988 847367` |
| `demo.bin` | `755353563 97051` |
| `demo.debug.bin` | `4271321717 103335` |

The tip CRCs come from the same script run at the parcel's tip commit, which is the commit
that adds this file. Writing them here would need a later commit, and then the measured
tree would no longer be the tip. They are in the parcel's landing report beside the tip SHA.

Independent of the CRCs: a script that strips `//` comments from every changed `.emp` line
of `git diff origin/master` and compares the remaining code as a multiset reports the
added and removed code lines identical. The only code lines touched are the five
`muls.w` lines whose trailing `// lint: disable=E002` comment was replaced.

## Per id: what the code does, what the comment said

### A2-1 `engine/objects/core.emp`, `RunObjects` / `RunObjects_Frozen`

Register enumeration, from the bodies:

- `RunObjects` writes **d7** (`move.w #NUM_PLAYERS-1, d7`, the System and Effect counts, and
  `Dynamic_Live_Count` in `.run_culled`), **a0** (slot cursor; `movea.w d0, a0` in the culled
  walk), **a2** (live-list cursor, saved around the dispatch), **d0** (entry and
  code-address assembly), **a1** (dispatch target). Callees: object routines through the
  `ObjRoutine` type, declared `preserves(a0, d7.w)` and nothing else, so they may write
  d0-d6, a1-a6 and d7's high word; `CompactDynamicLive` `clobbers(d0-d1/a0-a2)`;
  `DrainDynamicPending` `clobbers(d0-d2/a0-a1)`; a paused frame tail-branches to
  `RunObjects_Frozen`. **Caller-visible set: d0-d7/a0-a6**, equal to the declared
  `clobbers(d0-d7/a0-a6)`.
- `RunObjects_Frozen` writes **d0, d7, a0, a2**; `Draw_Sprite` is `clobbers(d0-d3/a1)`.
  **Written set d0-d3/d7/a0-a2**; declared d0-d7/a0-a6.

Old prose: "Object routines MUST preserve a0 and d7" (true, but it is the callee contract)
followed by "Clobbers: d0-d6, a0-a6" on both procs (false: d7 is the loop counter). Now:
both headers say d0-d7/a0-a6, and RunObjects spells out the two contracts separately, with
the callee one citing `ObjRoutine`'s `preserves(a0, d7.w)`. Also corrected, same header:
Frozen's "26 slots" is 26 only in DEBUG; a release shape sweeps 2 + 16 = 18 (the System
sweep is compiled out).

### A2-2 `engine/level/tile_cache.emp`, `TileCache_CopyBlockColumn`

Body writes d0, d1, d2, d3, d5, a0, a2, **a4** (`movea.l a1, a4`, the staged-base mirror for
the collision copy), and a1 (pushed at entry, popped at the single exit, so it is
`preserves(a1)`). d4, d6, d7, a5, a6 are read or untouched. Callees:
`PageCache_PatchRun_Col` is `clobbers(d0) inout(a0, a1) preserves(d1-d7/a2-a6)`;
`coll_src_row_base` is an inline comptime template writing only its argument (d5).

Old prose: "Clobbers: d0-d3, d5, a0, a2-a3". Attribute: `clobbers(d0-d3/d5/a0/a2-a4)`. Now:
the prose matches the attribute. **Side finding:** **a3 is declared by both but written by
nothing.** It is a harmless over-declaration; I left it in the attribute because changing
the attribute is not a comment edit.

### A2-5 `engine/level/bg_anim.emp`, `BgAnim_Init` (EFFECTS-GATE FILE)

The plain body writes d0 only (`moveq #-1, d0`). In the DEBUG shape, `lea BgAnim_Table, a0`
adds a0. The attribute `clobbers(d0/a0)` is declared in both shapes on purpose, as the body
note explains. Old prose: "In: none. Clobbers: d0". Now it says d0/a0, declared in both
shapes, with a0 written only in DEBUG.

### C3b-4 `engine/system/vblank.emp`, `VInt_Lag`

The lag-path safety enumeration argued palette and sprite (flag-gated) and HScroll (static
entry) but left out `Vscroll_Write`, which the same bracket calls after
`Process_DMA_Critical`. Derived from `Vscroll_Write` (`parallax.emp`) and its producers:

- **Destination and length come from code.** `Vscroll_Write` points the VDP at VSRAM
  address 0 with an immediate command word. It then CPU-writes 1 longword
  (`Vscroll_Factor`) or 20 (`Parallax_Vscroll_Column_Buf`), depending on the branch. 20
  longwords is 80 bytes, all of VSRAM. No DMA queue is involved.
- **Values can tear.** `Vscroll_Factor`'s one writer is a single `move.l` in
  `Parallax_Step5_Vscroll`, so an interrupt always sees it whole. The column buffer is
  filled a word at a time by Step 5's column loop and column-19 borrow store, and by
  `OJZ_Reels_Fill`. All of these are main-loop code, reached from
  `GameState_OJZScroll_Update`. The result is at worst one frame of mixed V-scroll values,
  which the next `VInt_Level` rewrites.
- **The branch choice** reads `Parallax_Active_Config`, whose LS-5 publish order keeps it
  off the NULL pair mid-transition. A NULL would only take the one-longword arm.

**Also fixed, separate commit, not a ledger id:** the `VInt_Lag` header's clobber union
omitted `Raster_VBlank` (`clobbers(d0-d4/a0-a2)`) and gave `Flush_VDP_Shadow` d0-d3 where its
attribute says d0-d1/a0-a1. The union re-derived from the six callee attributes is
d0-d4/a0-a2/a5, which equals the declared set.

### C1a-2 `engine/level/parallax.emp`, `Parallax_Fill_PerLine .lp_both` note

Address registers at `.lp_both`: **a0 dead** (the config pointer, set fresh only by
`.band_fg_only`, `.lp_bg` and `.lp_curve`, and restored by the exit `movem`); a1-a3 are the
cross-loop contract; a4 is the output cursor; a5/a6 are the curve bases, indexed and never
advanced; a7 is sp. Every data register is in use (d7 is the band countdown).

Old comment: "two sampled channels need two walk pointers and there is no second free
address register". **The literal count is right**: a0 is the only dead address register.
What is wrong is the implied impossibility. The sweep seat's refutation is that a5/a6 can
walk themselves. Each base is needed only at its own 256-byte wrap, where the walker is
exactly base + 256, so `suba.w #256` recovers it. Now the note says the reason is not
registers. It records what a conversion would owe (a three-run split, since the two phases
wrap on different lines, and restoring a5/a6 at band exit). It says frequency is an
authoring fact the file may not pin, and attributes the sweep's 44 cycles/line and 9,900
cycles/frame figures to the sweep, not re-measured.

### B1-5 the hardware multiply/divide sites

**Enumeration, grep over `engine/` and `games/` (`.emp` and `.asm`, case-insensitive,
comment-only lines excluded): 9 instruction sites.** This matches the sift's nine. The
vendored `engine/debug/debugger.asm` has none.

| site | instruction | points before | now |
|---|---|---|---|
| `engine/system/math.emp` `GetArcTan` | `divu.w` x2 (exclusive branches) | 1, 2, 3, and 4 without a per-frame count; 2 said "always < $100", false on the diagonal | all four; 2 corrected to "at most $100, exactly $100 on \|x\| == \|y\| (hence 257 entries)"; 4: at most 1 call a frame in DEBUG, 0 in release (only spawner is the DEBUG hotkey); dropped a citation of a superseded §2.1 rule |
| `engine/level/parallax.emp` `Parallax_Update` | `divs.w` | 1, 2 (with a loose range: said 1..16, is 1..15; said \|gap\| <= $7FFF, gap can be -$8000) | all four; 1 now names the byte's writers (all main-loop); 3 costs the reciprocal table (about 100 vs 162 cycles, saves at most about 60 per enabled band on transition frames) and the fixed-shift lerp (never lands exactly); 4: at most 16 divides, 2,528 cycles, on at most 15 frames per crossing |
| `engine/level/parallax.emp` `Parallax_Step4_Fill` | `divs.w` | 1, 2 (\|spread\| <= $7FFF loose) | all four; 3: reciprocal needs a second multiply for the Bresenham remainder, lands at or above 158; 4: at most 16 divides a frame, every frame a curve layer is installed |
| `games/sonic4/player/player_ground.emp` `Ground_Move_Cap` | `muls.w` x2 | a weak 3, no overflow bound, no cycle figure | 2: \|trig\| <= $100 (measured, all 320 words of `sine.bin`) and gsp clamped to +-$1000, so the result is within +-$1000; 3: runtime x runtime, quarter-square costed (about 90 vs 70 cycles, about 17 KB); 4: <= 188 cycles, at most once per player per frame |
| `games/sonic4/player/player_ground.emp` `Player_Jump` | `muls.w` x2 | none ("one-shot event, classic does this") | 2: jump_force is block-copied from the character physics row ($680 / $600), with no named store elsewhere; 3: a per-force impulse table is a real multiply-free form, rejected on design (RAM field meant for modifiers) and on the size of the saving; 4: <= 188, at most once per player per frame, exclusive with Ground_Move_Cap's pair |
| `games/sonic4/player/player_glide.emp` `Glide_Move` | `muls.w` | a count, no overflow bound, no cycle figure | 2: the glide's own writers keep gsp in 0..$1803 (the soft cap is $17FF + 4, not $1800); 3: as Ground_Move_Cap; 4: <= 94, at most NUM_PLAYERS a frame |

The five `// lint: disable=E002` markers are gone. `git log -S 'E002' -- tools/` shows the lint
deleted by `6ee64536` (LS-14, 2026-09-07). `CODING_CONVENTIONS.md` §2.1 was updated to
match: the GetArcTan and Parallax_Update worked-example rows, and a line recording that no
site carries the pragma any more.

**Points argued, but on a rough count and not measured (flagged, not papered over):**

- Parallax_Update point 3: the reciprocal alternative is rejected on price and scope. The
  roughly 100-cycle figure is an instruction-count estimate, not a built and timed
  sequence.
- Ground_Move_Cap point 3: the quarter-square figure of about 90 cycles is also an estimate.
- Player_Jump point 3: the rejection is a design judgement (jump_force is a RAM field
  meant for modifiers), not a cycle loss. The table form would be cheaper.
- GetArcTan point 4 and the players' "at most NUM_PLAYERS" counts are caller censuses. They
  are true at this base and go stale when a character select or a sidekick lands.

**Outside the nine, and outside §2.1's four-point rule by its own text:** `mul_bounded` sites
(`section.emp` `Section_GetSecPtrXY`, `tile_cache.emp` `TileCache_DecompressBlock`,
`ojz_scroll_test.emp` `Debug_LabCycleHotkey`, each `mul_bounded.w ..., #MAX_ACT_SECTIONS`) may lower
to a real `mulu` by build-time election. §2.1 names that construct as the argued answer for
multiplies, so no site-level argument is owed. A grep for the mnemonic cannot see them.

## Proposed ledger lines (PROPOSALS, not appended; `fixedAt` is the merge)

```json
{"id": "A2-1", "at": "<stamp at append>", "sweep": {"date": "2026-09-06", "packet": "docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md", "sha": "9cfebb72", "pin": "61f22403"}, "seat": "A2", "severity": "medium", "title": "The engine's two most-called object entry points document a register as preserved that they overwrite immediately", "state": "fixed", "where": {"path": "engine/objects/core.emp", "symbol": "RunObjects / RunObjects_Frozen headers"}, "fixedAt": "<merge>", "detail": "parcel/lens-contracts-0911, commit cbff0f9a, zero-byte. Both headers now say Clobbers: d0-d7, a0-a6, equal to clobbers(). Re-derived: RunObjects writes d7/a0/a2/d0/a1 itself and dispatches ObjRoutine (preserves(a0, d7.w) only), CompactDynamicLive, DrainDynamicPending; Frozen writes d0/d7/a0/a2 plus Draw_Sprite's d0-d3/a1. The a0/d7 rule is kept as the callee contract, citing the ObjRoutine type. Also corrected Frozen's '26 slots' (18 in release)."}
{"id": "A2-2", "at": "<stamp at append>", "sweep": {"date": "2026-09-06", "packet": "docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md", "sha": "9cfebb72", "pin": "61f22403"}, "seat": "A2", "severity": "low", "title": "A cache routine's header omits a register its body uses as a live pointer", "state": "fixed", "where": {"path": "engine/level/tile_cache.emp", "symbol": "TileCache_CopyBlockColumn header"}, "fixedAt": "<merge>", "detail": "parcel/lens-contracts-0911, commit 22abda0a, zero-byte. Prose now a2-a4 like clobbers(). Re-derived: body writes d0-d3/d5/a0/a2/a4 (a1 saved and restored); PageCache_PatchRun_Col preserves d1-d7/a2-a6. Side finding recorded in the header: a3 is declared by both prose and attribute but written by nothing (harmless over-declaration, attribute left alone)."}
{"id": "A2-5", "at": "<stamp at append>", "sweep": {"date": "2026-09-06", "packet": "docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md", "sha": "9cfebb72", "pin": "61f22403"}, "seat": "A2", "severity": "low", "title": "An init routine's one-line header is contradicted by its own body comment eight lines below", "state": "fixed", "where": {"path": "engine/level/bg_anim.emp", "symbol": "BgAnim_Init header"}, "fixedAt": "<merge>", "detail": "parcel/lens-contracts-0911, commit 9113e4e4, zero-byte. Header now Clobbers: d0/a0, declared in both shapes, a0 written only in DEBUG. Effects-gate file: the landing ran tools/effects_gates.py (controller)."}
{"id": "C3b-4", "at": "<stamp at append>", "sweep": {"date": "2026-09-06", "packet": "docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md", "sha": "9cfebb72", "pin": "61f22403"}, "seat": "C3b", "severity": "low", "title": "A tearing consumer is missing from the very list that argues why tearing is safe on that path", "state": "fixed", "where": {"path": "engine/system/vblank.emp", "symbol": "VInt_Lag lag-path enumeration"}, "fixedAt": "<merge>", "detail": "parcel/lens-contracts-0911, commit 7cdf8955, zero-byte. Vscroll_Write added with its argument: immediate VSRAM-0 command, 1 or 20 longwords by branch (20 = 80 bytes = all of VSRAM), no DMA queue, so destination and length come from code; values can tear (Vscroll_Factor is one move.l; the column buffer is word-filled by Parallax_Step5_Vscroll and OJZ_Reels_Fill, main loop); one frame of mixed values, rewritten by the next VInt_Level. Companion commit 92adc154 corrects the same proc's clobber-union prose (Raster_VBlank was missing, Flush_VDP_Shadow overstated)."}
{"id": "C1a-2", "at": "<stamp at append>", "sweep": {"date": "2026-09-06", "packet": "docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md", "sha": "9cfebb72", "pin": "61f22403"}, "seat": "C1a", "severity": "low", "title": "A parallax loop's stated reason for not being optimised does not hold, but the loop never runs on shipped content", "state": "fixed", "where": {"path": "engine/level/parallax.emp", "symbol": "Parallax_Fill_PerLine single-channel banner, .lp_both paragraph"}, "fixedAt": "<merge>", "detail": "parcel/lens-contracts-0911, commit ce7e8122, zero-byte, no code touched (seat recommendation). The note no longer claims a register blocker. The literal count was right (a0 is the one dead address register at .lp_both); the conclusion was not, because a5/a6 can walk and be recovered by suba.w #256 at the wrap. The note records the conversion's real obligations (a three-run split, restoring a5/a6) and leaves frequency to authoring; sweep figures attributed, not re-measured."}
{"id": "B1-5", "at": "<stamp at append>", "sweep": {"date": "2026-09-06", "packet": "docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md", "sha": "9cfebb72", "pin": "61f22403"}, "seat": "B1", "severity": "medium", "title": "The convention requiring a four-point argument for hardware multiply is unmet at every hand-written site", "state": "fixed", "where": {"path": "games/sonic4/player/player_ground.emp", "symbol": "Player_Jump, Ground_Move_Cap; also player_glide.emp Glide_Move, parallax.emp Parallax_Update / Parallax_Step4_Fill, math.emp GetArcTan"}, "fixedAt": "<merge>", "detail": "parcel/lens-contracts-0911, commit fe22ab95, zero-byte. All 9 hand-written sites (grep re-derived; matches the sweep's 9) now carry all four points, each derived at the site. Corrected three wrong bounds while there: GetArcTan's quotient is at most $100 (exactly $100 on the diagonal), not < $100; Parallax_Update's divisor is 1..15, not 1..16; both divs gaps can be -$8000, not <= $7FFF (quotients still fit). The five lint: disable=E002 pragmas are replaced (lint deleted by 6ee64536, LS-14); CODING_CONVENTIONS.md §2.1 rows updated to match. Three point-3 rejections rest on rough instruction counts or a design judgement, flagged in the parcel note."}
```
