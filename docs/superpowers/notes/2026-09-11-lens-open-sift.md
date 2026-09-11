# Lens ledger sift: the 49 open ids, binned (2026-09-11)

Read-only sift of `docs/lens-findings.jsonl` at aeon `8d99deeb` (branch
`sift/lens-open-2026-09-11`, cut from local `master` = `8d99deeb`). No engine, game, tool,
ledger or DEFERRED_WORK file was edited; nothing was built; no emulator was touched.

**Headline:** 49 open ids (100 ids, 147 lines), the controller's figure reproduced exactly.
**A 2 · B 37 · C 5 · D 1 · E 3 · unclassified 1.**

## Method (commands as run)

1. Ledger parse, line-addressed, latest-line-wins, `sweep` handled as string or dict (the
   script never groups on it). The core of it:

   ```python
   recs = [(i, json.loads(l)) for i, l in enumerate(open(path).read().splitlines(), 1) if l.strip()]
   latest = OrderedDict()
   for i, r in recs: latest[r['id']] = (i, r)      # later line overwrites earlier
   opens = [k for k, (i, r) in latest.items() if r.get('state') == 'open']
   ```

   Output: `lines 147`, `bad []` (every line parses), `ids 100`, 43 ids repeat (normal),
   latest state `open 49, fixed 28, holds 12, parked 5, refuted 3, decided 2, unmeasurable 1`.
   A check that the `at` stamps of each id's lines are in line order found no inversion, so
   "latest line" and "latest stamp" agree for every id.

2. Per-id commit search: `git log --format='%h %s' master` (5185 commits) filtered per id with
   a boundary-anchored regex `(^|[^A-Za-z0-9])<ID>([^0-9A-Za-z]|$)` (so `CTRL-1` cannot match
   `CTRL-10`). Result: **43 of 49 ids appear in no commit subject at all.** Hits: V-7 (4),
   BUG-005 (6, all historical instrumentation), CTRL-9 (1, severity correction), EFX-4b (1,
   booking). Landings cite the DEFERRED_WORK `LS-*` row, not the ledger id, so the join that
   works is the ledger's `batch` field to the LS row (that is how B1-1/B2a-1 were found).

3. Cross-reference: `docs/DEFERRED_WORK.md` `# LENS SWEEP 2026-09-06` (Tier 1 `:30105`, Tier 2
   `:30124`, Tier 3 `:30160`, suspicions `:30389`), the ledger sift (`:31619`) and its slice
   reports `docs/superpowers/notes/2026-09-09-ledger-sift-{A,B,C}.md`, the packet
   `docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md`, `docs/decisions.jsonl`,
   `docs/lane-log.jsonl`, and `docs/2026-09-09-BUGS-archived.md` (for the CHAR/EFX/BUG ids,
   which DEFERRED_WORK never names: `grep -n` for each returned nothing).

4. Source re-verification at HEAD: one grep per id (the "HEAD evidence" column below). Every
   line number in this file was read off HEAD `8d99deeb`, not copied from a ledger row or sift.

5. Bin check: every open id asserted into exactly one bin against the parsed open set:
   `open ids in ledger: 49 · ids binned: 49 distinct: 49 · duplicates across bins: [] · open
   but unbinned: [] · binned but not open: []` then `A: 2 B: 37 C: 5 D: 1 E: 3 UNCLASSIFIED: 1`.

## Bin A: open only in the ledger (2)

Both are batch `LS-8`, whose DEFERRED_WORK row (`:30128`) is struck: **CLOSED 2026-09-10,
`parcel/ls8-mask-family-pins`.**

- Merge `c167d932` (2026-09-10 06:23 -0400, "merge(ls8): the mask families were two
  families..."); pin commit `f20f403c`. `git merge-base --is-ancestor c167d932 master` and
  `... f20f403c master` both true; `git branch -a --contains f20f403c` prints `master`.
- The fix is GUARDS, not respelling: the hand-spelled sites still exist (`tile_cache.emp:962`
  `andi.w #$FFF0`, `:1917` `mul_const.w d3, #80, d4`) and are now pinned so that following a
  guard's message no longer leaves siblings green.

| id | fix present in master (file:symbol, HEAD line) |
|---|---|
| B1-1 | `engine/level/tile_cache.emp:48` family ensure `BLOCK_TILE_SIZE - 1 == $F && (~(BLOCK_TILE_SIZE - 1) & $FFFF) == $FFF0 && BLOCK_TILE_SIZE * 2 == 32`, message "RESPELL ALL FIFTEEN SITES"; `:51` blocks-per-section pin; `:54` section-shift pin cross-checked against `SECTION_SIZE_SHIFT - 3`. |
| B2a-1 | stride pins at every site: `tile_cache.emp:132` (`mul_cache_stride`), `:575` (`TileCache_CopyBlockColumn`, the two `((x<<2)+x)<<4` chains), `:1894` (`TileCache_FillRow`); `collision_lookup.emp` `Collision_GetType` (message `:29`); `plane_buffer.emp` `Draw_TileColumn` (`:74`) and `Draw_TileRow_FromCache` (`:345`); `section.emp` `Section_RedrawPlanes` (`:235`). |

**Scope of this A verdict:** I verified the guards are PRESENT on master. That they go RED on the
two replayed experiments (16->32 and 80->84) is the landing's claim (`tools/ls8_pin_redproof.py`
M7/M8, quoted in `:30128`); I did not re-run it (no builds on this lane).

### Proposed ledger lines for bin A (PROPOSALS, not appended)

```json
{"id": "B1-1", "at": "<stamp at append>", "sweep": {"date": "2026-09-06", "packet": "docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md", "sha": "9cfebb72", "pin": "61f22403"}, "seat": "B1", "severity": "high", "title": "Block geometry can be changed, the one guard that fires can be satisfied exactly as it instructs, and the build goes green with a dozen places still using the old size", "state": "fixed", "where": {"path": "engine/level/tile_cache.emp", "symbol": "module head, BLOCK_TILE_SIZE family ensure", "line": 48}, "fixedAt": "c167d932", "batch": "LS-8", "detail": "OPEN ONLY IN THE LEDGER (2026-09-11 sift). Closed by parcel/ls8-mask-family-pins, merge c167d932 (pin commit f20f403c), both ancestors of master. The sites are still hand-spelled; what changed is that the block-tile family (15 sites), the blocks-per-section family (12, a DIFFERENT constant the row's single count would have mis-spelled) and the world-tile-to-section shifts (10) are each pinned across all members, with messages that name every site and what they do not cover. Red-first replay of this row's own experiment (BLOCK_TILE_SIZE 16->32 plus doing what coll_src_row_base's message said) is RED on 3 guards per the landing (tools/ls8_pin_redproof.py M7), not re-run by the sift. The plane-wrap masks are NOT covered and remain open as B1-2 / LS-8a."}
{"id": "B2a-1", "at": "<stamp at append>", "sweep": {"date": "2026-09-06", "packet": "docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md", "sha": "9cfebb72", "pin": "61f22403"}, "seat": "B2a", "severity": "high", "title": "The cache row-stride multiply is open-coded in six places and only two carry a guard", "state": "fixed", "where": {"path": "engine/level/tile_cache.emp", "symbol": "TileCache_FillRow stride pin", "line": 1894}, "fixedAt": "c167d932", "batch": "LS-8", "detail": "OPEN ONLY IN THE LEDGER (2026-09-11 sift). Closed by parcel/ls8-mask-family-pins, merge c167d932, ancestor of master. The population was 8 stride sites, not 6 (two TileCache_CopyBlockColumn shift-add chains contain no literal 80); every one now carries its own pin (tile_cache.emp mul_cache_stride / TileCache_CopyBlockColumn / TileCache_FillRow, collision_lookup.emp Collision_GetType, plane_buffer.emp Draw_TileColumn / Draw_TileRow_FromCache, section.emp Section_RedrawPlanes). Per the landing, TILE_CACHE_COLS 80->84 plus fixing the two originally guarded sites is now RED on 5 guards (tools/ls8_pin_redproof.py M8); not re-run by the sift."}
```

## Bin B: genuinely open, aeon can fix alone (37)

Size S/M/L. Bytes: `zero` = comments / `ensure` / tools / docs only; `ROM` = moves ROM bytes;
`DEBUG` = moves debug-shape bytes only. RT = needs runtime confirmation (controller). EG = touches
an effects-gate-ritual file (`engine/effects/*`, `bg_anim.emp`, `buffers.emp`).

| id | size | bytes | HEAD evidence (still true) | the fix, one sentence |
|---|---|---|---|---|
| S0-2 | S | zero | `DEFERRED_WORK.md:12268` "NOTHING in them is fixed" vs `:12405` "FULLY WORKED", 137 lines apart | Put a forward pointer at `:12268` to the correction (controller's file). |
| A2-1 | S | zero | `core.emp:476` "MUST preserve a0 and d7" / `:479` "Clobbers: d0-d6" on `RunObjects` (`:481`, writes d7 at `:487`); same at `:682`/`:687` for `RunObjects_Frozen` | Rewrite both headers: d7 is clobbered; the a0/d7 rule is the callee contract for object routines. |
| A2-2 | S | zero | `tile_cache.emp:561` "Clobbers: d0-d3, d5, a0, a2-a3" vs `:567` `clobbers(...a2-a4)`, a4 live at `:607` | Add a4 to the header prose. |
| A2-5 | S | zero | `bg_anim.emp:132` "Clobbers: d0" vs `:134` `clobbers(d0/a0)` | Header to d0/a0. EG. |
| B1-2 | S | zero | LS-8a (`:30129`): 9 code sites at HEAD, `section.emp:278,325` (RedrawPlanes), `:708,765,816,861` (UpdateColumns), `plane_buffer.emp:187` (Draw_TileColumn), `:484` `$FFC0` + `:486` (Draw_TileRow_FromCache) | Family `ensure` deriving 63 and `$FFC0` from `PLANE_H_CELLS/PLANE_V_CELLS`, LS-8 style; the VDP reg $10 side is extra. |
| B1-4 | S | zero | `raster.emp:975` `beq.s`, `:1006` `bne.s`, `:1051` `beq.s` in `Raster_VBlank`, unargued | Argue each size in place (or drop to unsized after a byte check). EG. |
| B1-5 | S | zero | 9 hardware mul/div sites unchanged (`parallax.emp:1942,2194`; `math.emp:117,124`; `player_ground.emp:853,856,1041,1044`; `player_glide.emp:226`) | Write the four-point argument at Player_Jump, Ground_Move_Cap, Glide_Move and Parallax_Update (GetArcTan and Step4_Fill are complete); the five `// lint: disable=E002` markers name a lint retired by LS-14. |
| B2a-2 | S | DEBUG | `children.emp` chain assert at `:151` (Normal) and `:449` (Linked) only; Complex `:269` / FlipAware `:341` are `@scaffolding` with zero call sites | Add the same `assert.w` to the two scaffolded procs before a first consumer copies them. |
| B2a-3 | S | zero | `scene_equiv_proof.emp:183-184` `fa & 15` / `(fa >> 4) & 15` character-identical to `scene_dsl.emp:3559-3560` | Re-spell the five packed fields independently in `cfg_band`, as `band_top_plane` already is. |
| B2a-4 | S | zero | `count_bad_nibbles` / `script_display_frames` shape-shared, bodies differ (ledger correction line 136) | Decide share-or-cross-check (LS-9 precedent: move to one module as `pub comptime fn`); an aeon engineering call, not an owner one. |
| B2b-4 | S | zero | three `= 8` decls (`z80_sound_driver.emp:113`, `sound_fm.emp:135`, `sound_sequencer.emp:82`); 13 ensure lines consume it | Make one authoritative and pin the other two to it (check a Z80 module can import the 68k `pub const`; else pub all three and cross-ensure). |
| B2b-5 | S | zero | `constants.emp:1169-1171` `KILLED_BITMASK_OFFSET`/`COLLECTED_MASK_BYTES`, no width pin; twin pinned at `entity_window.emp:95` | `ensure(COLLECTED_MASK_BYTES * 8 == MAX_LIST_ENTRIES, ...)` beside the twin. |
| B2b-6 | S-M | zero | LS-24 left 62 dead `.asm` citations, 24 blocked by the LS-13/LS-19 parcel (closed 2026-09-07, so now unblocked); HEAD token lines: main.asm 11 (5 in engine/sound), song_table.asm 7, constants.asm 5, ram.asm 4, dma_queue.asm 3 (not all dead: some already say "deleted") | Finish LS-24's residual, engine/sound and parallax.emp first. |
| C1a-1 | S | ROM | `sprites.emp:139` loads `Sprite_Band_Counts` into a1, `:166` overwrites, `:170` reloads the same value; `:160` `lsl.w #6` | Increment the count while a1 still holds it and drop the second `lea`. |
| C1a-2 | S | zero | `parallax.emp:3445` "no second free address register" (a0 is dormant per the file's own `.lp_both` note) | Correct the comment; the seat recommends not touching the code (frequency 0 on shipped content). |
| C1a-3 | S | ROM | `dplc.emp:335-336` `lsr.w #8` + `lsr.w #4` | `rol.w #4` + `andi.w #$F`; the seat's own verdict: land only when dplc.emp is open for another reason. |
| C1b-3 | S | ROM | `collision_lookup.emp:55` reloads `Cache_Origin_Row` and halves it per query | Store the halved origin at the two producer writes in tile_cache.emp and read it directly. |
| C2a-5 | S | zero | `dma_queue.emp` pins only `DMA_CRITICAL_SLOTS == 8` (`:327`) and `sizeof(DMAEntry) == 14` (`:332`); `DMA_Queue_End` mark at `ram.emp:393`, no span pin | Link-time `ensure` that each sub-queue span equals its slot count times 14 and the whole equals `DMA_TOTAL_SLOTS * 14`. |
| C2a-6 | S | DEBUG | `sprites.emp:314-315` overflow `bhi .next_object` precedes the H1 staleness assert at `:325` | Move the staleness net ahead of the overflow pre-check. |
| C2b-4 | S | zero | sigil's `z80_clobbers_incomplete` gate still SKIPS green unless `SIGIL_STRICT_GATE=1 AEON_DIR=...` (sift C); no aeon ritual names it | Name it as a landing step (or a `tools/landing_build.sh` stage), mindful of shared-cargo-target hazards. |
| C3a-3 | M | zero | LS-S1 (`:30391`) undischarged; `tools/hblank_window_sweep.py` still holds main-loop phase fixed | Run the written falsifier (vary main-loop phase; exercise the no-spin dense tier). RT. |
| C3a-4 | S | zero | `raster.emp:1423` "a stale fire ALWAYS lands on priming record 0"; `section.emp:239` `move.w #$2700, sr` for the storm | Narrow the interlock's exhaustive claim to the rewind provenance and name the mask-left cursor. RT optional. EG. |
| C3b-2 | M | zero | `Effects_LatchWorldLines` (`raster.emp:2201`) unbracketed; LS-S2 (`:30397`) asks a comptime disjointness ensure | Comptime `ensure` that patch-channel records keep a positive gap under a one-frame camera tear. First establish what `check_intervals` (landed `7fbc0fe2`, 2026-08-15, BEFORE the sweep) already covers: the seat saw it and still wrote "nothing enforces that". EG. |
| C3b-3 | S | ROM | `page_in.emp:391` `jbsr PageIn_EnqueueLanding` precedes `:393` `st.b PageIn_Staging_Busy` | Raise the flag before the enqueue and drop it on the carry (dropped) path. |
| C3b-4 | S | zero | `vblank.emp:368-380` lag-path safety enumeration omits `Vscroll_Write` (called on that path at `:434`) | Add the member with its values-only-tear argument. |
| C4a-2 | M | ROM | `entity_window.emp:1003` `Collected_CheckRing` per candidate, which always runs `Collected_FindSlot` | Hoist the slot lookup to once per window entry. |
| C4a-3 | S | ROM | `entity_window.emp:1465-1469` recomputes `index * 6` per iteration in `EntityWindow_DespawnRings` | Rolling pointer, as `RingCollision` in rings.emp already does. |
| C4a-4 | S | ROM | `entity_window.emp:752`/`:755` `Section_GetSecPtrXY` then `Section_FlatIDXY` back to back; `section.emp:117-125` repeated-add `dbf` with no bound argument | Reuse the product (or at minimum write the missing bound argument, zero-byte). |
| V-5 | S | zero | `build.sh:763` "18 files, ~984 assertions" (108 test files today); `:781` "same rule pytest collects by"; `:800` `find -maxdepth 1 -name 'test_*.py'` | Correct the prose and make the extent count use pytest's own collection rule. |
| CTRL-1 | M | zero | LS-2a (`:30119`) open: Z80 under-declaration has no gate; 68k over-declaration was DELIBERATELY left unguarded by LS-2's closure (`b83204df`) | Build the Z80 under-declare census as a build-fatal tools test, and narrow the row to the Z80 cells. |
| C5-7 | S | zero | `tools/fixtures/s4_listing_excerpt.lst:32` `Game_RAM_End` `FFFFBC02`; untouched since `a4ebf2d1` (2026-08-18); read by `tools/test_s4budget.py`, made by `tools/fixtures/make_listing_excerpt.py` | Regenerate from a fresh listing or retire it with its consumer. |
| CTRL-7 | S | zero | no listing read recorded for C1a-1 (924 c/frame) or C1a-3 (154 c/frame) | Read a listing at a named SHA and re-derive both against the emitted branch forms (controller-side: needs built artifacts, no emulator). |
| CTRL-9 | L | zero | coverage gaps unchanged (C4b never dispatched, six partial surfaces) | Another sweep over exactly those surfaces. |
| CTRL-10 | S | zero | packet has 0 `## Seat B2a` headings; B2b jumps 5 to 8 | Amend the packet to record the sections were never written (recovery is unlikely). |
| CHAR-4 | M | ROM | 0 hits for ceil/roof/ProbeUp in `player_glide.emp` | Add an upward probe to `Glide_Collide`/`Slide_Terrain` per S3K `Knux_DoLevelCollision_CheckRet`. RT (replay cannot reach Knuckles, see CHAR-10). |
| CHAR-6 | S-M | ROM | `PHook_AirEnter` (`player_common.emp:2507`) calls `PHook_EnsureStanding` (`:2508`), bound to Air/Fly/GlideFall (`:2416-2427`) | Skip the 9 px lift on the three mid-air restores, leaving the grounded path untouched. RT. |
| EFX-4b | S | ROM | `raster.emp:1036` `move.w #(RASTER_BUF_SIZE / 2) - 1, d1` in `.copy_program` (`:1023`) | Bound the copy by program length, or pad static programs as patched ones are. EG. |

## Bin C: needs an owner decision (5)

| id | the question |
|---|---|
| CTRL-3 | Does aeon want hosted CI (and what could it run, given the paired sigil binary and emulator-backed lanes), or are the three systemd timers plus `tools/landing_build.sh` the accepted end state? |
| V-8 | Should the four-shape rule be mechanically enforced (a merge hook, or CI per CTRL-3), or is `tools/landing_build.sh` as a ritual the accepted end state? (Partly addressed since the row: LS-1c's `tools/landing_build.sh`, merge `a883cb3c`, IS the four-shape build, but its own row says "a ritual like the effects gate, not a hook".) |
| EFX-2 | Should a shipped preset get a palette cross-fade (a non-zero `transition`; all ten `preset(...)` sites take the default 0, `preset.emp:148`), or should the unreachable cross-fade layer be deleted? |
| B1-6 | Is a tree-wide magic-mask / magic-number lint wanted, given LS-8 chose per-family `ensure` pins and LS-2 / LS-14 set a precedent against heuristic text lints? |
| CHAR-10 | How should a replay fixture select a character (a character byte in the fixture, a boot seed honoured under playback, one fixture per character), given the recorder and fixture format are oracle's? (Booked as "needs a design decision" since the 2026-08-13 sweep, item D2; `Character_ID`'s one writer is still `ojz_scroll_test.emp:1586`.) |

## Bin D: waits on another lane (1)

| id | lane | what is needed | sent? |
|---|---|---|---|
| CTRL-6 | sigil | Stamp a digest of the linked source set into the `.lst` sigil emits, so the 14 `--built-after` consumers can check CONTENT rather than mtime (LS-1a, `:30111`, re-scoped 2026-09-10, whose own recommendation this is). | **NOT SENT** as far as aeon's records show: `grep -n digest docs/DEFERRED_WORK.md` hits only the LS-1a row itself; `docs/lane-log.jsonl` has no line for digest or LS-1a; the sigil-commitments block (`:30664`) and the two-obligations block (`:32921`) do not mention it. |

CTRL-6's other two riders are closed: LS-1c by `tools/landing_build.sh` (merge `a883cb3c`), and
LS-1d by the preset-witness parcel (merge `8862947d`, recorded at `:30452`), although the LS-1d
row at `:30115` is not struck (a DEFERRED_WORK drift; the fix content was not re-verified here).

## Bin E: ruled / parked / refuted in prose, ledger still open (3)

| id | where it was ruled | proposed state |
|---|---|---|
| CTRL-8 | `DEFERRED_WORK.md:30135` (LS-10 closure, merge `fcdde52a`, 2026-09-07): "the folded-vs-`0(a3)` question the sweep left open resolves to **FOLDED**, so 36 is the real figure", derived from shipped release bytes. The ledger row was enrolled 2026-09-09T00:46:54Z, two days AFTER that answer. | left to the controller: NOT `holds`, which this ledger uses only for severity-`clean` rows (lines 9, 15, 31 are examples); `decided` or `fixed` with `fixedAt: fcdde52a` are the candidates |
| C5-5 | Packet `:1553`: "**The seat explicitly did not propose deletion** -- the named consumer (Tails follow + trails) is live work -- and recorded it so nobody re-derives the emptiness". The ledger row's own detail says "recorded rather than proposed for deletion". | `parked` |
| V-7 | `docs/decisions.jsonl:130` (LS-17): the owner was offered `full` ("Add release-shape checks broadly: every file with no net gets one") and chose `crash` (answered 2026-09-09T01:04:18Z, "by": "owner"); the closure note says `full` "was rejected partly on that cost" and puts vblank.emp and boot.emp out of scope. The compression clause is landed (s4lz `805da83c..e793893a`; ZX0R nets `d6ba4d60`) and the one missing piece the latest ledger line names, a firing, was supplied by `d0e47eb9` "witness(V-7): the four release-shape nets RAN on a real boot and none fired" (2026-09-10 06:51:42Z, AFTER that line's 06:11:50Z; poisoned ROM `exit 1 ... FIRED`). | `decided` |

**V-7 contradicts its own ledger line, deliberately flagged:** line 146 says the owner call on the
remaining population was "deliberately NOT filed". My reading is that it was filed, as LS-17's
`full` option, and the owner declined it. If the controller reads "not chosen" as "not yet
asked", V-7 moves to bin C with line 146's question verbatim.

### Proposed ledger lines for bin E (PROPOSALS, not appended)

```json
{"id": "CTRL-8", "at": "<stamp at append>", "sweep": {"date": "2026-09-06", "packet": "docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md", "sha": "9cfebb72", "pin": "61f22403"}, "seat": "controller", "severity": "tagged", "title": "The largest performance finding's number has an optimistic and a pessimistic end, and which one is true is a fact about the emitted code", "state": "<controller's term for an answered TAG>", "detail": "SETTLED IN PROSE BEFORE THIS ROW WAS ENROLLED (2026-09-11 sift). docs/DEFERRED_WORK.md LS-10 closure (merge fcdde52a, 2026-09-07, ancestor of master) derived the loop costs from the shipped release bytes and states: the folded-vs-0(a3) question resolves to FOLDED, so tst.w Sst.code_addr(a3) is 8 cycles and the optimistic end holds. The row was enrolled 2026-09-09T00:46:54Z, two days after that answer existed. Scope: this answers CTRL-8's one addressing mode; CTRL-7 (branch relaxation across the hot loops) is NOT settled by it and stays open. C1b-1 itself is decided (LS-10)."}
{"id": "C5-5", "at": "<stamp at append>", "sweep": {"date": "2026-09-06", "packet": "docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md", "sha": "9cfebb72", "pin": "61f22403"}, "seat": "C5", "severity": "low", "title": "Two player history buffers are written every frame and read by nothing", "state": "parked", "detail": "PARKED BY THE SEAT, NOT A DEFECT TO FIX (2026-09-11 sift). Packet seat C5, finding F5: 'The seat explicitly did not propose deletion -- the named consumer (Tails follow + trails) is live work.' Re-verified at 8d99deeb: the only writer is games/sonic4/player/player_common.emp (the Player_Ring_Index / Player_Pos_Ring / Player_Stat_Ring stores) and no reader exists in engine/, games/ or tools/ (tools/fixtures/make_listing_excerpt.py names the symbols in a listing excerpt, it does not read the RAM). Re-open when the consumer lands or is dropped."}
{"id": "V-7", "at": "<stamp at append>", "sweep": {"date": "2026-09-06", "packet": "docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md", "sha": "9cfebb72", "pin": "61f22403"}, "seat": "V", "severity": "medium", "title": "The guards are dense where the authoring is and absent where the machine runs, and a malformed compressed stream has no net in the release build", "state": "decided", "where": {"path": "docs/decisions.jsonl", "symbol": "LS-17"}, "batch": "Tier 2", "detail": "RULED, AND THE RULING PREDATES THE LINE THAT CALLED IT UNFILED (2026-09-11 sift). docs/decisions.jsonl LS-17 put three options to the owner, including `full` ('Add release-shape checks broadly: every file with no net gets one'), and the owner chose `crash` on 2026-09-09T01:04:18Z; the closure records `full` as rejected partly on cost and vblank.emp / boot.emp as out of scope. The chosen scope is fully landed: s4lz.emp (805da83c..e793893a) and the four ZX0R nets (d6ba4d60), and the firing the 2026-09-10T06:11:50Z line said no lane could prove was witnessed by d0e47eb9 (2026-09-10T06:51:42Z): clean s4.bin and s4.debug.bin boots with 10 page-in completions, and a one-byte-poisoned wrapper that lands in the crash island. The remaining population (sound_sequencer, tile_cache, plane_buffer, sound_psg, collision, vblank, boot) is the `full` option the owner declined. If that is read as not-yet-asked rather than declined, this row belongs open with line 146's owner question."}
```

## Unclassified (1)

- **BUG-005.** Not forced into a bin. There is no fix to size, no decision to put to the owner and
  no lane to wait on: the artefact has never been reproduced, its named suspect was downgraded by
  probe on 2026-08-05, and the DEBUG chain-walk net still stands (per the ledger's own 2026-09-09
  confirmation). Only a reproduction can move it, which is emulator work: **needs runtime
  confirmation (controller).** Keeping it `open` at low, as the ledger does, is the honest state.

## Top 5 recommended bin-B picks (cheap-and-live first, zero-byte first)

1. **B2b-5** (high, S, zero-byte): one `ensure` beside its already-pinned twin
   (`entity_window.emp:95`); guards a silent whole-act corruption (collected ring marks an object
   dead).
2. **C2a-5** (high, S, zero-byte): a link-time span pin on the DMA sub-queues; an inserted field
   today silently programs the wrong VDP registers.
3. **B2b-4** (high, S, zero-byte): pin the three `YM_ADDR_TO_DATA_MIN_T` copies; 13 build-fatal
   cycle guards trust them and a low drift weakens all 13 silently. Check Z80-module import first.
4. **B1-2 / LS-8a** (medium, S, zero-byte): the last unpinned mask family, 9 sites; LS-8's method
   and harness (`tools/ls8_pin_redproof.py`) apply as-is.
5. **A2-1** (medium, S, zero-byte): the engine's two most-called entry points document d7 wrongly;
   bundle A2-2, A2-5, C3b-4, C1a-2 and B1-5 into the same comment parcel (A2-5, B1-5's parallax
   site and C3b-4's neighbours touch EG files, so run the effects ritual if it includes A2-5).

Best byte-moving pick after these: **C3b-3** (S, a lost decode frame from a flag raised after its
enqueue; one reorder in `PageIn_Process`).

## What in the brief turned out wrong or weaker than stated

- The controller's **49 / 100 / 147** reproduced exactly.
- `git log --oneline master | grep -i <id>` is a weak instrument here: 43 of 49 ids appear in no
  commit subject, because landings cite LS rows. The working join is the ledger `batch` field to
  the DEFERRED_WORK LS row (it found both bin-A ids).
- An occurrence count over the plane-mask family reads 12 (`grep -c 'andi.w  *#63\b'` gives 8 in
  section.emp and 4 in plane_buffer.emp) because six LS-8 ensure MESSAGES quote the literal; the
  code sites are 9, matching LS-8a. The same trap V-7's record warns about for `raise_error`.

## Side findings (not ledger ids)

- `DEFERRED_WORK.md:30115` (LS-1d) is not struck although `:30452` records its fix (merge
  `8862947d`); not content-verified here.
- CTRL-8 is the second instance of a row enrolled open after its answer had landed (the 2026-09-09
  sift found C2a-4 the same way).
- Five `// lint: disable=E002` suppressions (`player_ground.emp:853,856,1041,1044`,
  `player_glide.emp:226`) name a lint that LS-14 deleted.

## Controller rulings on this sift (aeon overseer, 2026-09-11T18:44:04Z)

- **Bin E states appended to `docs/lens-findings.jsonl`:** CTRL-8 `decided`, C5-5 `parked`,
  V-7 `decided`. The V-7 call is the controller's, taken on the evidence above: LS-17
  (`docs/decisions.jsonl:130`) offered the owner the broad option (a net in every file that has
  none) and he chose `crash`, the narrow one, on 2026-09-09. That is the question V-7's
  2026-09-10 line said was unfiled. If the owner reads his answer as "not yet" rather than "no",
  V-7 reopens as an owner card carrying that line's question verbatim.
- **CTRL-6 / LS-1a, the ask to sigil, is SENT with this commit** (it had never been sent). The
  ask: stamp a digest of the linked source set into the `.lst` sigil emits, so the 14
  `--built-after` consumers can check content rather than mtime; aeon then builds the one shared
  provenance primitive on top. The recommendation and the family count are LS-1a's own
  (`docs/DEFERRED_WORK.md`, row LS-1a). Recorded here, in the sending repo, before the send.
- **`docs/DEFERRED_WORK.md` is deliberately NOT edited in this pass**, including the LS-1d strike
  the side findings name: the main checkout holds an uncommitted owner-pending edit to that file,
  and a pushed edit to it would block the main tree from fast-forwarding. Reconcile once the
  owner has answered on that edit.
- **Dispatched from bin B:** a zero-byte guard-pins parcel (B2b-5, C2a-5, B2b-4, B1-2 as LS-8a);
  a zero-byte comment-contracts parcel (A2-1, A2-2, A2-5, C3b-4, C1a-2, B1-5); and the one
  byte-mover, C3b-3, alone.

### LS-1a: sigil ACCEPTED, with a counter-shape aeon adopts (2026-09-11T18:49:58Z)

Sigil's answer (their commitment is banked at sigil `docs/superpowers/notes/2026-09-11-aeon-source-digest-ask.md`,
pushed to their origin/master per their message; not yet read here): **yes, queued behind their three
parcels of 2026-09-11**, spelling sent to aeon for review BEFORE it lands.

- **Where:** a new section of the `.lst`, never the deb2 trailer (deb2 is ROM bytes in every shape, so a
  digest there would move every CRC on every source edit). ROM-neutrality to be PROVED by sigil's
  four-shape byte gates at landing, not asserted.
- **Shape:** the section NAMES the set: format version, assembler revision, build config (game, debug,
  target shape, defines), one row per file the build READ (crc32, size, path relative to the aeon root,
  sorted by path bytes; generated files marked), and an aggregate CRC32 over the rows. A lone digest
  cannot be re-checked, which is why aeon adopts this over its own one-line ask.
- **Hash:** CRC32 plus size, aimed at accidental staleness, not adversaries. Aeon accepts.
- **Sigil's risk, stated by them:** a file the build reads that the section omits makes stale read as
  fresh; they derive the set from what the build actually opens, with a planted-unlisted-read control.

**Aeon's answer to their one question** (does any consumer need freshness of files sigil does NOT read?),
read out of the tree at `cd075f2d`, not from memory: **no.** All eleven `--built-after` gates stat
exactly the (`.lst`, `.bin`) pair (the `for p in (lst, rom)` loop beside each `getmtime`/`st_mtime`
comparison in row_remap_gate, anim_frame_bound, editor_palette_golden, band_drift_golden,
plane_base_swap_gate, reels_gate, plane_role_swap_gate, bganim_room, sprite_tilt_gate, instashield_gate,
loop_crossover_gate), and `tools/conftest.py`'s needs_build markers declare only `.lst`/`.bin`
artifacts. Their other inputs are committed fixtures (git-versioned, compared as content). The
editor-to-generated chain is guarded before the build by `tools/level_staleness.py` (content-stamped),
and the generated files it produces are files sigil reads, so they fall inside the section.

**One addition aeon asked for:** the built ROM's CRC32 and size in the same section. `bganim_room.py`'s
PROVENANCE note says "the sigil listing carries no ROM identity", and every gate reads the `.bin` beside
the `.lst`; without it the section proves the listing fresh but cannot tie the ROM to it.

**Sigil amendment, accepted (2026-09-11T19:09:23Z):** the ROM identity in that section is the FULL SHIPPED FILE as
written to `-o` (deb2 appendix included where the shape carries one), the same value sigil's
"built: ... crc=" line prints and its provenance goldens pin, so it matches what our gates hash. Not
circular: the listing is not inside the ROM, and deb2 is built from the in-memory listing. Consequence
on their side: the native build moves its `.lst` write to after the ROM is final, proved byte-neutral
by their four-shape gates at landing. Banked by sigil as an amendment to their
`docs/superpowers/notes/2026-09-11-aeon-source-digest-ask.md` (their word, not read here).

### PENDING BOOKING, held with DEFERRED_WORK.md (2026-09-11T19:09:23Z)

The hub relayed an owner-approved request (empyrean `2341c6f`,
`docs/research/2026-09-11-sound-driver-scout.md`, "For aeon's driver"; owner, verbatim via the hub:
*"Sure write this up and check out those other ones you listed, might as well see what we can find
out."*) to book the scout's seven driver ideas as ONE deferred ideas entry for AFTER REGIONS, not a
queue row: (1) game-driven branching and live track mute (GEMS); (2) echo loop / echo macro;
(3) reverb by release and FM3 slot detune; (4) first/second-ending loops, delayed vibrato,
proportional note-off, grace notes; (5) a background-SFX layer between music and effects;
(6) SSG-EG as a first-class patch parameter; (7) per-track tempo (measure first). **It goes in
DEFERRED_WORK.md's unbuilt-ideas section in the same commit that clears that file's hold.** Checked
here first, at `cd075f2d`: aeon has neither (1) half as a GAME-controlled feature. The only mutes are
the pause's whole-chip mute and the SFX override's internal per-channel mute (`engine/sound/sound_sfx.emp`,
the `Sfx_Restore` un-mute path), and no sequencer command reads a game-written value. That per-channel
override is the building block a live track mute would reuse, and the entry should say so.
