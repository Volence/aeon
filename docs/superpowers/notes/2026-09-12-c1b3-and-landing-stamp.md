# C1b-3 (collision origin half) and the landing_build env stamp

Two independent branches, each cut from `origin/master`. The worktree agent delivered
them; the controller merges and lands them. Written 2026-09-12 UTC.

| branch | tip | closes |
|---|---|---|
| `parcel/c1b3-origin-half` | see "Tips" at the end | lens ledger `C1b-3` (ledger line NOT appended; the controller does that) |
| `parcel/landing-build-env-stamp` | `0fef6d85051679609d19dfa7a18a15a96dbaa47c` | `docs/DEFERRED_WORK.md`, side findings of the 2026-09-11 lens-tools parcel, item (b), struck in its commit |

Bases: branch 1 was cut at `7577daee`, branch 2 at `35f54923`. origin/master moved twice
while this ran (another session fetched into the shared refs). The byte control for both is
four ROMs built at `6763a402`. `6763a402..7577daee` is one docs file (`docs/OVERSEER.md`),
so that control is exact for branch 1. For branch 2, see its byte picture.

Assembler for every build here: `sigil 0.1.0 (af35fa56)`, `md5(SIGIL_BUILD)=49ecc532e0b133ab0eab9447e071805c`,
unchanged from dispatch to the last build.

---

## Branch 1: `parcel/c1b3-origin-half`

### What changed

`engine/level/collision_lookup.emp` `Collision_GetType`, the row half. Old:

    sub.w  d2,d1                  ; L = row - Cache_Top_Row
    lsr.w  #1,d1                  ; L/2
    move.w Cache_Origin_Row,d2
    lsr.w  #1,d2                  ; O/2
    add.w  d2,d1                  ; floor(L/2) + O/2

New:

    sub.w  d2,d1                  ; L
    add.w  Cache_Origin_Row,d1    ; L + O
    lsr.w  #1,d1                  ; floor((L + O)/2)

`floor((L+O)/2) = floor(L/2) + O/2` for every L when O is even, and `Cache_Origin_Row` is
kept even (ENGINE_ARCHITECTURE.md §4.7; the old form's own comment already relied on it).
Both forms compute the same value, so the wrap test that follows is unchanged.

### The brief is contradicted here, deliberately

The brief offered two outcomes: store the halved origin in place (if every reader could
take it), or decline because a new RAM mirror would be needed. The enumeration below rules
out the first, and the second is what the sweep packet's fix is. Neither is shipped: a third
option makes the per-query halving of the origin disappear with **no representation change,
no RAM, and no reader touched**, and it is strictly cheaper than both. The row's own
wording ("store the halved origin at the two producer writes") is not what landed.

### Enumeration: every site that touches the value

Found by symbol (`git grep Cache_Origin_Row`), then by what could touch the word without
naming it: bulk RAM clears, struct copies, and listings read by tools.

| # | site | kind | form it uses |
|---|---|---|---|
| W1 | `engine/level/tile_cache.emp` `TileCache_Init` (`clr.w Cache_Origin_Row`) | writer | 0 (same in either form) |
| W2 | `tile_cache.emp` `TileCache_VSlide` | read-modify-write | unhalved: `+rows`, wrap at `TILE_CACHE_ROWS` |
| W3 | `tile_cache.emp` `TileCache_VSlideUp` | read-modify-write | unhalved: `-rows`, wrap at `TILE_CACHE_ROWS` |
| W4 | `engine/system/boot.emp` `.clear_ram` (all of work RAM) | writer, unnamed | 0 |
| R1 | `tile_cache.emp` `Tile_Cache_GetTile` | reader | unhalved |
| R2 | `tile_cache.emp` `TileCache_CopyBlockColumn` | reader | unhalved |
| R3 | `tile_cache.emp` `TileCache_FillRow` | reader | unhalved (halves the PHYSICAL row afterwards for the collision row) |
| R4 | `engine/level/plane_buffer.emp` `Draw_TileColumn` | reader (x2) | unhalved: `x160` stride, and `TILE_CACHE_ROWS - O` rows before the wrap |
| R5 | `plane_buffer.emp` `Draw_TileRow_FromCache` | reader | unhalved |
| R6 | `engine/level/section.emp` `Section_RedrawPlanes` | reader | unhalved: `x160` stride |
| R7 | `section.emp` `Canopy_Fire` (DEBUG only) | copy into `Canopy_Rec_OrgRow` | unhalved, printed by `tools/canopy_record.py` |
| R8 | `engine/level/collision_lookup.emp` `Collision_GetType` | reader | **the ONLY halved reader** |
| T1 | `tools/tile_cache_fill_gate.py` | reads RAM, models `phys = O + (row - Top) mod ROWS` | unhalved |
| T2 | `tools/loop_crossover_gate.py` | writes 0 in its World, lists the name in `NEED_SYMS` | 0 |
| T3 | `tools/test_gate_fixtures.py` | asserts the name resolves in the cut | name only |
| T4 | `tools/warp_mailbox_gate.py` | snapshots it (`STATE_WORDS`) | reads, no arithmetic |
| T5 | `tools/fixtures/loop_crossover_cut.json` | its address, per shape | address only |

No struct offset, `movem` block or partial clear writes it; the only bulk writer is boot's
whole-RAM clear.

### What each alternative would cost (derived, not measured)

- **Store the halved form in place.** One reader saves 12 cycles (the same saving as the reorder).
  Seven engine sites and one tool pay for it:
  - R1/R2/R3/R5 each turn `add.w O,dN` (12c, 4B) into `add.w H,dN` twice (24c, 8B), or into
    `move.w H,dX` / `add.w dX,dX` / `add.w dX,dN` (20c, 8B, plus a scratch register), which is
    +8..12c and +4B each;
  - R4 and R6 need `x320` in place of `x160`, and R4's `ROWS - O` needs the doubled value;
  - W2 and W3 halve the row count first (+8c, +2B each);
  - T1's model and R7's printed meaning change.

  That is net ROM of roughly +20B against the -4B at R8. **Rejected.**
- **New RAM mirror (the packet's fix).** +2B RAM, plus a halving store at W1-W3
  (roughly `move.w`/`lsr.w`/`move.w` each, rare), for the same 12c at R8 that the reorder
  gets for nothing. **Not shipped**, as the brief directed for this case; the reorder makes
  it moot anyway.
- **The reorder.** 0 RAM, -4B ROM, -12c per in-cache call, no other site touched. **Shipped.**

The 2026-07-16 port review (`docs/reviews/2026-07-16-emp-port-optimization-review.md`,
item 6) proposed folding `Origin - Top` into one cached bias. That is also a new RAM word
with an update at every mutation site. It is out of scope here and was not attempted.

### Cycles, per instruction (MC68000UM tables; DERIVED, not measured)

The operand is absolute-short: `Cache_Origin_Row` is `$FFFFADCA`, and it is emitted as
`3438 adca` / `d278 adca`.

| form | instruction | encoding | cycles |
|---|---|---|---|
| old | `sub.w d2,d1` | `9242` | 4 |
| old | `lsr.w #1,d1` | `e249` | 6 + 2x1 = 8 |
| old | `move.w $ADCA.w,d2` | `3438 adca` | 4 + 8 (abs.w) = 12 |
| old | `lsr.w #1,d2` | `e24a` | 8 |
| old | `add.w d2,d1` | `d242` | 4 |
| | **old total** | 12 bytes | **36** |
| new | `sub.w d2,d1` | `9242` | 4 |
| new | `add.w $ADCA.w,d1` | `d278 adca` | 4 + 8 (abs.w) = 12 |
| new | `lsr.w #1,d1` | `e249` | 8 |
| | **new total** | 8 bytes | **24** |

-12 cycles on every call that passes both window checks; 0 on the air exits, which never
reach these lines. At the packet's ≈8-14 calls/frame (its call-chain count, not re-derived
here) that is ≈96-168 cycles/frame, 0.08-0.13% of a 127,800-cycle NTSC frame, and an upper
bound (off-cache calls save nothing). The packet wrote -8/call. That number equals the
removed `lsr` alone; the packet does not say how it was reached.

**Independent cross-check.** `tools/loop_crossover_cost.py` sums cycles from the encodings the
build actually emitted, run through the gate's micro-CPU. Before the change (baseline
s4.debug) its table matched the committed cost note row for row, so the tool is a valid
control. After the change:
- every one-probe row drops by exactly 12 (798 to 786, 834 to 822, 918 to 906, 754 to 742, ...);
- the two-probe rows drop by 24 (1352 to 1328, 1598 to 1574);
- the steady state (106) and the off-cache air exit (584) are unchanged.

`Player_LoopCrossover`'s cost note in `games/sonic4/player/player_common.emp` has been
re-run to these figures.

### Equivalence evidence

- **Differential over the emitted bytes** (scratch script, not a committed gate). Both ROMs'
  `Collision_GetType` (baseline 104 B, branch 100 B) were run in `loop_crossover_gate`'s own
  micro-CPU. The sweep covered every EVEN `Cache_Origin_Row` in 0..58, rows `Top-1..Top+60`,
  `Top` in {0, 2, 1000, 8000}, both planes, and columns {0, 79}: **29,640 cases, 0
  disagreements between old and new, and both matched an independent address model.**
  **Control:** the same sweep over ODD origins (the invariant broken) gives **14,400
  disagreements**, so the comparison can see a difference.
- **The build's own gate is blind to this.** `tools/loop_crossover_gate.py` executes
  `Collision_GetType` 441 times per shape and passes. But its World seeds
  `Cache_Origin_Row = 0`, where the two forms agree trivially, so a green gate here says
  nothing about origin arithmetic. That observation is recorded, not booked. A gate that
  varied the origin would have caught a real mistake in this exact edit; the controller may
  want it booked.
- The gate refused the stale committed cut with "Collision_GetType: the routine's LENGTH
  changed (cut 104 B, live 100 B)". `tools/fixtures/loop_crossover_cut.json` was regenerated
  for both shapes (`--write-fixture`), and the gate is OK on both after that.

### Byte picture per shape (branch tip vs the `6763a402` baseline)

| shape | size (both) | differing bytes | baseline md5 | branch md5 | symbols moved |
|---|---|---|---|---|---|
| s4 | 821123 | 11399 | `0b93e768b265dc5c218d24f3967b8bdd` | `89eb4c58034022ff1bb924903d2f263a` | 646 of 2217 by -4 |
| s4.debug | 847389 | 18708 | `49d28ff5e2806e71ace1a4786466bb66` | `36698a407ee7fb2381a3671d58c742e7` | 802 of 2701 by -4 |
| demo | 97075 | 7412 | `93e46e149bc8546e7ee3daa03f461311` | `f19f1c1072d285cff5874cd4c37c6910` | 410 of 1209 by -4 |
| demo.debug | 103359 | 14074 | `754ca219d55e2c4cab2a026f181e51c8` | `ac76243c596a832a0b376f9413ad33d7` | 549 of 1455 by -4 |

The pattern is the same in every shape, and it was measured from the two listings, not
inferred:
- Everything from `Collision_GetType.row_nowrap` up to `$010000` moves by -4. The exception
  is a handful of fixed-address symbols the listing carries inside that range
  (`SoundTablesZ80_Head` at `$8000`, the pitch tables, `SfxBlobWinTab`, `SeqOpcodeTable`,
  `DacSampleTable`), which do not move.
- `ObjCodeBase` (`$010000`) through `EndOfRom` is unmoved in all four shapes. The fixed
  `$10000` placement absorbs the 4 bytes as padding, which is why no ROM size changed.
  `GameState_OJZScroll_Init` (sigil's `boot_port` `frozen_symbol()` pin) is in the unmoved
  region.
- The differing bytes before `Collision_GetType` are absolute operands that point at moved
  symbols (`jsr`/`lea` in VBlank, GameLoop, entity_window, and so on), plus the header
  checksum word at `$18E`. The clusters past `EndOfRom` are the deb2 symbol appendix.
- **The symbol NAME set is identical in all four shapes**: 0 names only in the baseline,
  0 only in the branch. So no new cross-module name exists, and the deb2 appendix changes
  only because addresses changed.

### Landing evidence

`./tools/landing_build.sh` at `66a1c821`, run detached: **`finished=0`, exit 0**. `EXIT_s4=0`,
`EXIT_s4.debug=0`, `EXIT_demo=0`, `EXIT_demo.debug=0`, `EXIT_needs_build=0`.
- Tools pytest lane, per shape: 2436 passed, 2 skipped, 14 deselected, 112 subtests passed.
- Post-sigil lanes: 5, 6, 1 and 1 passed, the rest skipped by shape.
- needs_build: 14 ran, 0 deferred, 0 failed.

The commit that adds this note is docs plus one comment; its own run is reported in the handoff.

### TAGs (for the controller)

- **RT.** No emulator was used. Runtime confirmation is still open: collision correctness
  while `Cache_Origin_Row` is non-zero, i.e. after vertical scrolling has evicted rows.
  Everything above is static timing plus a micro-CPU execution of the emitted bytes.
- **BYTE-MOVER.** All four shapes change, and the landing needs the sigil side of the
  byte-moving ritual wherever sigil pins these ROMs. `boot_port`'s frozen symbol is
  unmoved, per the table above.
- **REBASE.** Branch 1 is cut at `7577daee`. Master has since taken the lens-z3 parcel
  (`raster.emp`, `animate.emp`, `dplc.emp`, `ring_sparkle.emp`, `player_instashield.emp`,
  `emp_expect_fail.py`, `test_z80_clobbers_census.py`, docs), and after that the spring-coil
  landing (`0b1cd022`: `art_spring.bin`, `gen_spring.py`, `knuckles_data.emp`,
  `test_solid.emp`, `spring_line0_gate.py`, `DEFERRED_WORK.md`, `ENGINE_ARCHITECTURE.md`).
  Spring coil MOVES bytes. None of it overlaps this branch's files, but a merged tree needs
  its own four-shape run, and a fresh `--write-fixture` if `loop_crossover_gate` reports
  the cut stale. Branch 2 also edits `docs/DEFERRED_WORK.md`, in a different region from
  spring coil's edits.
- **Gate blind spot**, as above: `loop_crossover_gate`'s World pins the origin at 0.

---

## Branch 2: `parcel/landing-build-env-stamp`

### What changed

`tools/landing_build.sh`: the two `: "${VAR:?...}"` lines are now explicit tests. An unset
or empty `SIGIL_BUILD` or `SIGIL_EMIT` prints `landing_build: COULD NOT RUN: <VAR> is unset
...` and then `finished=2`, and exits 2.

The exit contract was confirmed, not assumed. The script's own lane comment ("widens the
script's exit set from {0,1} to {0,1,2}") and CLAUDE.md ("0 green · 1 a shape or a marked
test FAILED · 2 COULD NOT RUN") both say so. Before this change the path exited 1, which is
the FAILED code, and printed no stamp.

### Test

`tools/test_landing_build_logfile.py` gets two new rows. They use the sandbox pattern the
file already had: a copy of the script beside a stub `build.sh` and a stub needs_build
lane, so nothing can reach the real build (item (c)'s recursion hazard).
- Each variable, unset and empty, runs through the logfile path.
- Each variable, unset, also runs with no argument.
- Every case asserts exit 2, `finished=2` as the last line of stdout (and of the log), the
  variable named, and that the stub build never ran.
- `_env` now reads `None` as "remove this variable".

- **Red first, in the real tree**, with the test on disk and the script unfixed: **2 failed,
  7 passed**. Both failures read `(1, '... line 59: SIGIL_BUILD: SIGIL_BUILD is unset ...')`,
  i.e. exit 1 and no stamp.
- **Green** after the fix: **9 passed**.
- **Mutation after the commit.** Only the `SIGIL_EMIT` block's `echo "finished=2"` is
  deleted, so the EMIT rows have to fail on their own; the red-first run above only ever
  reached the BUILD path. Result: **2 failed, 7 passed**. Both new rows fail with
  `SIGIL_EMIT is unset ...` as the last line where `finished=2` was expected. The script was then restored with
  `git checkout -- tools/landing_build.sh` from the committed tip and re-run green.
- Runner: build.sh's pre-build tools pytest lane, build-fatal.

### Byte picture per shape

All four shapes are **byte-identical** to the `6763a402` baseline (`cmp -s`):

| shape | md5 (baseline = branch) |
|---|---|
| s4 | `0b93e768b265dc5c218d24f3967b8bdd` |
| s4.debug | `49d28ff5e2806e71ace1a4786466bb66` |
| demo | `93e46e149bc8546e7ee3daa03f461311` |
| demo.debug | `754ca219d55e2c4cab2a026f181e51c8` |

Branch 2 is based on `35f54923`. Between the baseline and that base sits the lens-z3 parcel,
which touched `raster.emp`, `animate.emp`, `dplc.emp`, `ring_sparkle.emp` and
`player_instashield.emp` and claimed zero bytes. This one result proves both claims at
once: z3 moved no byte, and this branch moves no byte. A difference would have been
ambiguous between the two. There was none.

### Landing evidence

`./tools/landing_build.sh` at `0fef6d85`, run detached: **`finished=0`, exit 0**.
`EXIT_s4=0`, `EXIT_s4.debug=0`, `EXIT_demo=0`, `EXIT_demo.debug=0`, `EXIT_needs_build=0`.
- Tools pytest lane, per shape: 2444 passed, 2 skipped, 14 deselected, 112 subtests passed.
  That is 8 more than branch 1's 2436. Branch 2's base also carries the lens-z3 test file,
  so this note does not attribute the 8 beyond this file's 2 new rows.
- Post-sigil lanes: 5, 6, 1 and 1 passed.
- needs_build: 14 ran, 0 deferred, 0 failed.

That run executed the FIXED script end to end with both variables set, which is the green
path's real-world control.

### TAGs

- None beyond the item. Item (c)'s hazard is respected, and the new rows never call the
  real `build.sh`.

---

## Tips

- `parcel/c1b3-origin-half`: the commit that adds this note, which sits on the change
  `66a1c8214980f68aa3e04696b08173fcbb23a2ad`. A commit cannot name its own SHA; the
  handoff report does, together with that tip's own landing run.
- `parcel/landing-build-env-stamp`: `0fef6d85051679609d19dfa7a18a15a96dbaa47c`

`git merge-base --is-ancestor <tip> master` tells a landed branch from a lost one.
