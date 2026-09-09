# Ledger sift B — 16 ids re-verified against master, 2026-09-09

Scope: `docs/lens-findings.jsonl`, latest line per id (parsed by script, duplicates resolved
by taking the last occurrence), for exactly these 16 ids:
`C2a-4, C2a-5, C2a-6, C3b-3, C3b-4, C4a-2, C4a-3, C4a-4, C5-5, V-5, CTRL-3, B1-1, B1-2, B2a-1,
B2b-3, B2b-6`.

Method: for each id, the finding's `title`/`detail`/`where` were read from the ledger, then the
named file/mechanism was inspected directly on this worktree's checkout of `master`
(`git rev-parse HEAD` = see report). No build was run (task constraint); "still true" verdicts
that would normally need a build-time reproduction (BLOCK_TILE_SIZE/TILE_CACHE_COLS geometry
changes) are instead supported by exhaustive static evidence that the exact code shape the
controller's original build-time measurement found is unchanged today.

---

## C2a-4 — medium

**Finding:** the mechanism making every build-time `ensure` guard real (a `SIGIL_WARNINGS=full`
grep of the compiler's warning stream for `module.unreachable`) is a manual ritual; `build.sh`
never performs it.

**VERDICT: ALREADY-FIXED**

`build.sh` still contains **zero** occurrences of `SIGIL_WARNINGS`, `module.unreachable`, or
`clobber` as an executed check (`grep -n "SIGIL_WARNINGS\|module.unreachable\|clobber" build.sh`
→ only a comment at line 823). So the row's literal sentence ("build.sh contains zero
occurrences of it") is still true word-for-word.

But the underlying claim — "no automation catches an unreachable `ensure`" — is false today.
`tools/test_extern_guard_reachability.py` (added by commit `ca743b5c`, "gate(LS-16c): a
per-commit runner for the extern()-guard family", 2026-09-08) runs `sigil build --check` with
`env=dict(os.environ, SIGIL_WARNINGS="full")` (`tools/test_extern_guard_reachability.py:199-202`)
across four shapes and asserts `test_every_extern_guard_file_is_reachable_in_some_shape` — this
is exactly the "grep of the compiler's warning stream" the finding says never runs. That test
file carries no `@pytest.mark.needs_build` marker, so it is collected and run by `build.sh`'s
**pre-build** pytest invocation at `build.sh:631` (`python3 -m pytest "${TOOLS}" -q --no-header
-p no:cacheprovider -m "not needs_build"`), i.e. on every build.

Ancestry: `git merge-base --is-ancestor ca743b5cd... HEAD` → **yes** (prints `ANCESTOR: yes`).

**Note on the row's own detail:** the row is not simply stale — its literal sentence about
`build.sh`'s own text remains accurate. What it gets wrong is the conclusion drawn from that
sentence (no automation exists at all); a different file now closes exactly this gap and is
wired into the same script.

---

## C2a-5 — high

**Finding:** `Init_DMA_Queue`'s per-slot marker unroll assumes the three DMA sub-queues are one
contiguous 448-byte block, guarded by nothing; and the in-file note claiming otherwise
("LOCKSTEP … the byte gates are the guard") names a deleted file, `engine/system/dma_queue.asm`.

**VERDICT: STILL-TRUE** (the risk), with the misleading note **ALREADY-FIXED**

The misleading half is fixed. `engine/system/dma_queue.emp:26-37` now reads:

```
// HISTORICAL, NOT A LIVE LOCKSTEP, and the correction is the point of this note.
// It used to read "LOCKSTEP: dma_queue.asm spells this as a `rept DMA_TOTAL_SLOTS`/`set`
// unroll — the byte gates are the guard; a slot-count or layout change must move both
// sides". BOTH halves are gone: the AS dma_queue.asm was deleted with the rest of the
// `.asm` code twins, and no tool in tools/ names it or any byte gate against it
// ...
// `ensure(sizeof(DMAEntry) == 14)` fails loudly if the entry width moves.
```

(landed in commit `85813388`, "docs(lens): LS-24 — the dead .asm citations, enumerated before
they were fixed", 2026-09-07; `git merge-base --is-ancestor 85813388... HEAD` → yes). The
sibling instance in `engine/objects/core.emp:49-51` was corrected the same way. No live
occurrence of "byte gates are the guard" remains outside quoted historical text
(`grep -rn "byte gates are the guard" engine/ games/` → 2 hits, both inside the "it used to
read…" quotation).

The structural risk itself is unfixed. `engine/ram.emp:385-392` still lays `DMA_Critical` /
`DMA_Important` / `DMA_Deferrable` out as three sequential array fields sized from
`DMA_CRITICAL_SLOTS`/`DMA_IMPORTANT_SLOTS`/`DMA_DEFERRABLE_SLOTS`, and `Init_DMA_Queue`
(`dma_queue.emp:53-64`) still unrolls `fill_slot_markers(DMA_TOTAL_SLOTS)` — `DMA_TOTAL_SLOTS`
being the *sum* of those three constants — starting at `DMA_Queue` and walking `sizeof(DMAEntry)`
strides with no gap awareness. No `ensure` binds `DMA_Queue_End - DMA_Queue ==
DMA_TOTAL_SLOTS * sizeof(DMAEntry)`. Inserting a field between `DMA_Critical` and
`DMA_Important` in `ram.emp` (e.g. a per-queue counter, exactly the scenario the finding
names) would compile cleanly and silently desync the pre-laid VDP register markers for every
Important/Deferrable slot. This half of the finding is unchanged.

---

## C2a-6 — medium

**Finding:** the only net catching a stale sprite cache (`Sst.mapping_frame`/`mappings` writers
drifting from `Sst.frame_off`) is `DEBUG`-only and sits *downstream* of the piece-count
overflow pre-check, so a corrupt-but-large piece count skips the object via `.next_object`
before the assert can fire.

**VERDICT: STILL-TRUE**

`engine/objects/sprites.emp`:
- `:303-315` — total-piece overflow pre-check: `move.b Sst.sprite_piece_count(a0), d0 / add.w
  d5, d0 / cmpi.w #MAX_VDP_SPRITES, d0 / bhi .next_object // would overflow — skip whole object`
- `:324-330` (matches the ledger's `where.line: 324` exactly) —
  ```
  if DEBUG == 1 {
  moveq   #0, d0                  // H1 staleness net: live-resolve and
  move.b  Sst.mapping_frame(a0), d0   // compare against the cache
  add.w   d0, d0
  move.w  (a3,d0.w), d0
  move.w  Sst.frame_off(a0), d1
  assert.w d1, eq, d0
  }
  ```

The overflow pre-check runs first and can `bhi .next_object` before control ever reaches the
`DEBUG == 1` assert block — unchanged from the finding's description.

---

## C3b-3 — medium

**Finding:** `PageIn_Staging_Busy` is raised (`st.b`) *after* the landing DMA it guards is
already enqueued, so a VBlank landing between the enqueue and the flag set reads 0, skips its
clear, and the main loop then sets it over an empty queue — costing a lost decode frame.

**VERDICT: STILL-TRUE**

`engine/level/page_in.emp:349-353`:
```
        move.l  #Art_Staging_Buffer, d1         // landing DMA source (RAM staging)
        jbsr    PageIn_EnqueueLanding           // Important staging->VRAM DMA; carry = dropped
        bcs     .land_full
        st.b    PageIn_Staging_Busy             // landing queued -> hold the staging slot until VInt_Level drains it
```
`PageIn_Process` (`page_in.emp:104`) declares no `preserves(sr.mask)` / interrupt bracket around
this region — it deliberately runs with interrupts enabled from `VSync_Wait`'s idle site — so a
VBlank landing between the `jbsr` and the `st.b` is possible exactly as described.

---

## C3b-4 — low

**Finding:** `VInt_Lag`'s in-header enumeration of "why every lag-path consumer is safe" lists
the palette/sprite enqueues (dirty-flag gated) and the HScroll enqueue ("safe by a different,
weaker mechanism … corrupts scroll VALUES only") but omits `Vscroll_Write`/
`Parallax_Vscroll_Column_Buf`, which is filled incrementally by the main loop and shipped whole
on the same lag path — the same class of values-only tear, unlisted.

**VERDICT: STILL-TRUE**

`engine/system/vblank.emp:368-380` enumerates palette/sprite safety and HScroll safety but never
mentions `Vscroll_Write`. `jbsr Vscroll_Write` is called on this same `VInt_Lag` path at
`vblank.emp:434`, immediately after `Process_DMA_Critical`. `Vscroll_Write`
(`engine/level/parallax.emp:1490`) ships `Parallax_Vscroll_Column_Buf`
(`engine/ram.emp:493`, filled incrementally elsewhere in `parallax.emp`, e.g. `:2948/:2951`)
whole to VSRAM via a run of `move.l (a0)+, VDP_DATA_OFF(a5)`. The enumeration still has no entry
for this consumer.

---

## C4a-2 — medium

**Finding:** `Collected_FindSlot`'s answer (a 9-slot bitmask-scan for a `section_id`) is
loop-invariant across the whole walk of one entity-window entry (the walker holds `a1` fixed),
but is recomputed on every candidate.

**VERDICT: STILL-TRUE**

`engine/objects/entity_window.emp:997-1004`, inside `EntityWindow_TrySpawnRing`, called once per
candidate ring from `EntityWindow_RescanY`'s `.loop` (`:1406-1412`, `d4` = candidate index
incrementing, `a1` unchanged across the loop):
```
        // collected on a previous visit?
        move.b  EntityScanState.ess_section_id(a1), d0
        moveq   #0, d1
        move.w  d4, d1                  // list_index
        jbsr    Collected_CheckRing     // clobbers d2, a0
```
`Collected_CheckRing` (`:181`) unconditionally calls `Collected_FindSlot` (`:158`, a 9-slot
`dbf`-loop scan) every time. `ess_section_id(a1)` is the same byte for every iteration of one
window entry's walk. No hoist exists.

---

## C4a-3 — low

**Finding:** `EntityWindow_DespawnRings` rebuilds the ring-buffer entry address from the loop
index every iteration (an `×6` shift/add chain + `lea`), where its sibling `RingCollision`
walks the identical buffer with a rolling pointer and states the cure verbatim.

**VERDICT: STILL-TRUE**

`engine/objects/entity_window.emp` inside `EntityWindow_DespawnRings` (`:1453` onward), the
`.loop` body:
```
        // Compute entry address
        move.w  d5, d0
        add.w   d0, d0
        add.w   d5, d0
        add.w   d0, d0                  // d0 = index × 6
        lea     Ring_Buffer, a0
        move.w  (a0, d0.w), d1          // engine_X
```
recomputes the address from `d5` (the loop index) on every pass. `engine/objects/rings.emp:282-297`
(`RingCollision`) carries the rolling-pointer cure and the swap-with-last safety argument the
ledger quotes ("swap-with-last removal only rewrites the removed slot from an already-visited
HIGHER index"). Unchanged.

---

## C4a-4 — low

**Finding:** `Section_GetSecPtrXY` computes `sec_y * grid_w + sec_x` (via a `§2.1`-argued
`mul_bounded`) and discards it; `BuildEntries` immediately recomputes the identical product via
`Section_FlatIDXY`'s repeated-add `dbf` loop, which carries **no** bound argument at all
(counter is a raw `GridY` byte, structurally up to 255).

**VERDICT: STILL-TRUE**

`engine/objects/entity_window.emp:752-755`:
```
        jbsr    Section_GetSecPtrXY     // a0 = Sec ptr, Z set = out of grid
        ...
        jbsr    Section_FlatIDXY        // d0.w = flat id (d2/d3/a2 preserved)
```
back-to-back. `engine/level/section.emp:117-129` (`Section_FlatIDXY`) uses a `dbf`
repeated-add loop with no §2.1 four-point argument; `section.emp:143-165`
(`Section_GetSecPtrXY`) uses `mul_bounded.w` with the full argument written as a comment
(`:151-158`). The asymmetry and the double computation both persist. Severity is still stated
by the sweep as low today (`GRID_W = GRID_H = 3`) — I did not re-derive current grid dimensions
beyond confirming the code shape is unchanged; this is a static-code verdict, not a
re-measurement of current grid size.

---

## C5-5 — low

**Finding:** `Player_Pos_Ring`/`Player_Stat_Ring`/`Player_Ring_Index` (514 of 588 B of release
game RAM) are written every frame and read by nothing in the tree.

**VERDICT: STILL-TRUE**

`grep -rn "Player_Pos_Ring\|Player_Stat_Ring\|Player_Ring_Index" engine/ games/ --include="*.emp"`
returns only:
- `games/sonic4/config/ram.emp:233-235` — the declarations (`Player_Pos_Ring: [u8; 256]
  @align(256)`, `Player_Stat_Ring: [u8; 256]`, `Player_Ring_Index: u16`)
- `games/sonic4/player/player_common.emp:1308-1318` — the sole writer

No reader exists anywhere in `engine/`, `games/`, or (checked separately) `tools/`.

---

## V-5 — low

**Finding:** `build.sh`'s own comment describing the tool-suite pytest lane's size ("18 files,
~984 assertions") is stale by several times versus the real count, and its BAR-25 "sweep extent"
self-check claims to count "by the same rule pytest collects by" while actually only counting
`test_*.py` at `-maxdepth 1`, missing `*_test.py` and four recursive subdirectories pytest would
also collect.

**VERDICT: STILL-TRUE**

`build.sh:592` (unchanged): `# run-by-nothing gate: 18 files, ~984 assertions, no pytest.ini, no
conftest, no`. Actual count today: `find tools -maxdepth 1 -name 'test_*.py' | wc -l` → **103**
files (up from the sweep's own measured 84 on 2026-09-06 — the staleness has *grown*, not
shrunk). `build.sh:610` still states "the count below is computed by the same rule pytest
collects by," and `build.sh:629` still computes it as
`find "${TOOLS}" -maxdepth 1 -name 'test_*.py' | wc -l` — literally unchanged, still blind to
`*_test.py` and to subdirectories. (Today `find tools -mindepth 2 -name 'test_*.py' -o
-mindepth 2 -name '*_test.py'` and `find tools -name '*_test.py'` both return nothing, so the
self-check's blind spot is currently not producing an actual miscount — but the mechanism making
the equivalence claim false is unchanged.)

---

## CTRL-3 — medium

**Finding:** "This repository has no continuous integration at all" — no GitHub workflows, zero
workflow runs ever with an authenticated client; not a defect by itself, but it means the nightly
systemd timer was the sole backstop, and it was down.

**VERDICT: STILL-TRUE** (core claim), row's supporting **detail is now stale**

Core claim reconfirmed: `find .github -type f` → `error: .github: No such file or directory`
(absence, not an empty-vs-failed grep ambiguity — the tool itself reports nonexistence).
`gh workflow list` → exit 0, no output. `gh run list --limit 5 --json databaseId` → exit 0,
`[]`. `git remote -v` confirms this checkout points at `github.com:Volence/aeon.git`, so this is
an authenticated check against the actual remote, matching the row's own method. No CI service
runs against this repo.

But per the task's explicit instruction to check what actually runs unattended: **three systemd
user timers exist today and are active**, not down:
- `aeon-effects-gates.timer` (enabled, next trigger 2026-09-10 04:17): ran 2026-09-07
  (**succeeded**, "Finished"), 2026-09-08 (**failed**, exit 2/INVALIDARGUMENT), 2026-09-09
  (**failed**, exit 2/INVALIDARGUMENT, 2h before this check).
- `sigil-source-gates.timer` (enabled): ran 2026-09-07 (failed, exit 1), 2026-09-08
  (**succeeded**), 2026-09-09 (**succeeded**).
- `sigil-ref-drift.timer` (enabled): succeeded every day 2026-09-04 through 2026-09-08 (checked
  via `journalctl --user -u <service>`).

So "the nightly timer was down" (singular, past tense, implying total absence of backstop
coverage) is no longer an accurate description of today's state — there are three such timers,
running on schedule, with mixed pass/fail results, and two of the three have been passing on
their last 1-2 runs. The controller should note `aeon-effects-gates.service` is failing again as
of this morning (2026-09-09 04:30, exit 2) — a live, current problem, but a different one than
"no backstop is running at all."

---

## B1-1 — high

**Finding:** changing `BLOCK_TILE_SIZE` 16→32 makes the build red at exactly one guard
(`coll_src_row_base`'s `ensure(BLOCK_COLL_COLS == 16, …)`), whose message says "update the
shift" — and doing exactly that (only fixing that one guard) builds green while 17 mask sites
still align on the old size 16.

**VERDICT: STILL-TRUE** (static evidence; the build-time reproduction itself was not re-run,
per this task's no-build constraint)

`engine/level/tile_cache.emp:931` (exact match to the ledger's `where.line`):
```
        andi.w  #$FFF0, d6                     // align to the first block col
```
This is a **hardcoded** literal mask (`~15`), not spelled via `BLOCK_TILE_SIZE`/
`BLOCK_TILE_SHIFT`, and not covered by any `ensure`. The identical hardcoded pattern recurs at
`tile_cache.emp:1518, 1671, 1794, 1817, 1964, 2060, 2138` — 8 occurrences of `#$FFF0` in this one
file, all unguarded. `engine/level/tile_cache.emp:44` is still the *only* `ensure` mentioning a
block-geometry constant (`BLOCK_COLL_COLS == 16`), and `engine/system/constants.emp:973`'s
`ensure(1 << BLOCK_TILE_SHIFT == BLOCK_TILE_SIZE, …)` only checks self-consistency between the
shift and size constants, not that the literal `$FFF0` masks track either one. This is the exact
code shape the controller's build-time measurement describes; I did not rebuild with
`BLOCK_TILE_SIZE = 32` to reproduce the green-build claim (task forbids building), so the
"builds green" half is inferred from the absence of any guard that would make it red, not
independently re-run.

---

## B1-2 — medium

**Finding:** plane-wrap masks are spelled two ways in the same files (`engine/level/section.emp`,
`engine/level/plane_buffer.emp`) — raw `#63` literals and the symbolic `#PLANE_H_CELLS-1` /
`#PLANE_V_CELLS-1` forms — with nothing tying them together.

**VERDICT: STILL-TRUE**

`engine/level/section.emp:272` (exact match to ledger `where.line`):
```
            andi.w  #63, d6                         // d6 = start_nt_row (preserved)
```
Raw `#63` recurs at `section.emp:319, 526, 674, 698, 708, 732, 755, 765, 806, 816, 851, 861` and
`plane_buffer.emp:183, 477, 478, 483` (plus `plane_buffer.emp:475`'s `andi.w #$FFC0, d0` — the
same magic number as a mask). The symbolic `PLANE_H_CELLS-1`/`PLANE_V_CELLS-1` form is used in
the same two files at `section.emp:305, 614, 1086, 1182, 1195, 1204, 1216` and
`plane_buffer.emp:148, 446, 484`. `PLANE_H_CELLS = PLANE_V_CELLS = 64`
(`engine/system/constants.emp:483, 595`). No `ensure` binds the raw `63`/`$FFC0` sites to
`PLANE_H_CELLS`/`PLANE_V_CELLS`. Both spellings coexist unchanged.

---

## B2a-1 — high

**Finding:** the `TILE_CACHE_STRIDE = 80` row-stride multiply is open-coded in six places and
only two carry a guard; changing `TILE_CACHE_COLS` 80→84 goes red at exactly the two guarded
sites, and fixing both as instructed builds green with four more still striding 80.

**VERDICT: STILL-TRUE** (static evidence; build-time reproduction not re-run, per task
constraint)

Six sites, enumerated:
1. `engine/level/tile_cache.emp:113` (`mul_cache_stride` helper body) — **guarded** by
   `ensure(TILE_CACHE_STRIDE == 80, …)` at `:111`. Called from `:136` and `:1884`.
2. `engine/level/collision_lookup.emp:62` — `mul_const.w d1, #80, d2` — **guarded** by
   `ensure(TILE_CACHE_STRIDE == 80, …)` at `collision_lookup.emp:28`.
3. `engine/level/tile_cache.emp:584-586` — open-coded shift/add
   (`lsl.w #2 / add.w / lsl.w #4` = `×5×16 = ×80`) — **unguarded**.
4. `engine/level/tile_cache.emp:633-635` — same open-coded idiom — **unguarded**.
5. `engine/level/tile_cache.emp:1879` (exact match to the ledger's `where.line`):
   `mul_const.w d3, #80, d4   // collision_row × 80 (d4 = multiply scratch)` — **unguarded**,
   raw literal `#80` with no `ensure` in scope.
6. `engine/level/plane_buffer.emp:385` — `mul_const.w d0, #80, d3   // row × 80 stride` —
   **unguarded**.

Exactly 2 guarded (1, 2 above) and 4 unguarded raw sites (3-6), matching "six places, only two
carry a guard" precisely, and the ledger's cited line (`tile_cache.emp:1879`) is one of the four
unguarded ones.

---

## B2b-3 — low

**Finding:** a stated byte budget for the next ability author ("`PlayerV` spends 26 [of 30]") is
off by one field — `instashield: u8` was appended after the sentence was written, so the real
spend is 27, headroom 3 not 4 — and the stated headroom is guarded by nothing.

**VERDICT: ALREADY-FIXED**

`games/sonic4/player/player_common.emp:127-131` no longer states a number at all — it now
reads: *"The window's game-usable size and PlayerV's spend are BOTH comptime facts, so this
sentence deliberately names neither number... (The sentence used to say 'spends 26'; instashield
was appended after it was written and nothing made the drift loud — the pins are that
mechanism.)"* The mechanism is real: `player_common.emp:216-221`:
```
const PLAYERV_WINDOW = sizeof(Sst) - offsetof(Sst, sst_custom) - 2   // less SST_interact
const PLAYERV_SPEND  = 27
ensure(sizeof(PlayerV) == PLAYERV_SPEND, "PlayerV now spends {sizeof(PlayerV)} of the custom
window's {PLAYERV_WINDOW} game-usable bytes, not the {PLAYERV_SPEND} the ability-scratch budget
note above is written against ...")
ensure(sizeof(PlayerV) <= PLAYERV_WINDOW, "PlayerV is {sizeof(PlayerV)} bytes and the SST custom
window has only {PLAYERV_WINDOW} game-usable ones ... the overlay has overflowed into engine
territory")
```
`PLAYERV_SPEND` is pinned to 27 (the correct current value), and any future drift now fails the
build. Commit `bbeda312` ("docs(lens): LS-21/22/23/25 — decayed prose re-derived, and pinned
where it can be", 2026-09-07) introduced this. `git merge-base --is-ancestor bbeda312... HEAD` →
**yes**.

**Ledger note:** the ledger's *latest* line for B2b-3 (line 101, `at: 2026-09-08T23:50:23Z`)
still says `state: open` — but the fix (`bbeda312`) landed the day *before*, 2026-09-07. The
second "open" stamp postdates the fix and is simply wrong; it appears alongside four other ids
(B1-1, B1-2, B2a-1, B2b-6) re-stamped with byte-identical content at the same later timestamp,
which looks like a mechanical re-open of the whole original batch rather than a re-verified
sweep — worth flagging to whoever runs the ledger tooling.

---

## B2b-6 — low

**Finding:** comments across the engine cite deleted assembler (`.asm`) files as if they still
exist — `engine/constants.asm` named 14 times, `ram.asm` 13, `main.asm` 11, "and roughly 30
more" — reading as "keep this in sync with the other copy" when there is no other copy.

**VERDICT: STILL-TRUE**, row's own numeric **detail is now stale** (substantially improved but
not resolved)

Commit `85813388` ("docs(lens): LS-24 — the dead .asm citations, enumerated before they were
fixed", 2026-09-07, ancestor of HEAD confirmed) enumerated the true population (110 dead
in-repo citations across 46 files, not "~90") and repaired most of them: 65 mechanically
repointed to the live `.emp` module, 3 LOCKSTEP passages rewritten (dma_queue.emp x2 +
core.emp — see C2a-5 above), 11 kept with a recovery pointer, ~27 kept because already phrased
correctly ("deleted"/"former"), **24 explicitly left BLOCKED** (`engine/sound/*` (20) and
`engine/level/parallax.emp` (4), held by a concurrent parcel) — leaving, by the fixing commit's
own count, **62 dead occurrences still in the tree**.

Re-measured today: `engine/constants.asm` citations dropped from 14 to **2** (both now correctly
phrased: *"engine/constants.asm is DELETED (7dc909fe)"*, `engine/system/constants.emp:9`).
`ram.asm` dropped from 13 to **4**. `main.asm` is still **11**, and of those, three
(`engine/sound/seq_opcode_tab.emp:10,27,30`, in the still-blocked `engine/sound/` family) read
as live present-tense claims — *"BANKED at the engine-table head of the song/SFX bank
(main.asm's..."*, *"asserted co-located with this bank in main.asm"* — exactly the misleading
"keep in sync with a file that doesn't exist" shape the finding describes. The row's own
specific counts (14/13/11/"~90") are stale and now overstate `constants.asm`/`ram.asm`, but the
underlying finding — the tree still has live dead-file citations, concentrated in
`engine/sound/*` and `parallax.emp` — remains true.

---

# Summary

| id | severity | verdict |
|---|---|---|
| C2a-4 | medium | ALREADY-FIXED |
| C2a-5 | high | STILL-TRUE (misleading note half already fixed) |
| C2a-6 | medium | STILL-TRUE |
| C3b-3 | medium | STILL-TRUE |
| C3b-4 | low | STILL-TRUE |
| C4a-2 | medium | STILL-TRUE |
| C4a-3 | low | STILL-TRUE |
| C4a-4 | low | STILL-TRUE |
| C5-5 | low | STILL-TRUE |
| V-5 | low | STILL-TRUE |
| CTRL-3 | medium | STILL-TRUE (supporting detail stale) |
| B1-1 | high | STILL-TRUE |
| B1-2 | medium | STILL-TRUE |
| B2a-1 | high | STILL-TRUE |
| B2b-3 | low | ALREADY-FIXED |
| B2b-6 | low | STILL-TRUE (numeric detail stale) |

Counted directly from the 16 sections above (not from memory):
- **STILL-TRUE: 14** (C2a-5, C2a-6, C3b-3, C3b-4, C4a-2, C4a-3, C4a-4, C5-5, V-5, CTRL-3, B1-1,
  B1-2, B2a-1, B2b-6)
- **ALREADY-FIXED: 2** (C2a-4, B2b-3)
- **MOOT: 0**
- **UNDETERMINED: 0**

No item was BLOCKED or left undetermined; every one of the 16 was settled against the current
tree with direct file evidence or commit ancestry proof.
