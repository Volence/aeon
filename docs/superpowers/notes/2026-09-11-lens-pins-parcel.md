# Lens pins parcel, 2026-09-11 (`parcel/lens-pins-0911`)

Four zero-byte guard pins from bin B of `docs/superpowers/notes/2026-09-11-lens-open-sift.md`:
B2b-5, C2a-5, B2b-4, B1-2 (LS-8a). Branch base `cd075f2d` (origin/master at dispatch;
`f7406b97` confirmed an ancestor). This is a RECORD: line numbers below were read on this branch
and are frozen with it. No emulator was used; nothing here needs runtime confirmation (every
guard is a build-time check, proven by building).

## Commits

| sha | what |
|---|---|
| `0c6c8b5d` | B2b-5 pins (entity_window.emp) |
| `eda5acbf` | C2a-5 pins (dma_queue.emp) |
| `d16e6e35` | B2b-4 test + comment corrections (tools/test_ym_floor_single_authority.py, three sound files) |
| `f3664087` | B1-2 / LS-8a family pins (section.emp, plane_buffer.emp) + reg $10 pin |
| `4a3a8074` | red-first harness extension (tools/ls8_pin_redproof.py) |
| `cae58661` | FIX: my pins broke the canonical build (citation gate); cited lines restored, reg $10 name moved to constants.emp |
| `686d6ff3` | FIX: three defects in my own red-first harness |
| `22bb44ac` | FIX: the reg $10 pin runs first and hides the family; messages now say so; LS-8 messages no longer call the family unpinned |
| `87c289f6` | harness M22/M23 (follow the reg $10 pin's instruction, the family must fire) |
| this note | evidence |

## Zero bytes

Four canonical shapes built at the base BEFORE the first edit (each shape exit 0):

```
3393750122 821103 s4.bin
4112900988 847367 s4.debug.bin
755353563  97051  demo.bin
4271321717 103335 demo.debug.bin
```

Tip: see "Landing build" below (the four ROMs `tools/landing_build.sh` wrote).

## B2b-5: the collected/killed mask width

Re-derived at the branch base: `engine/system/constants.emp` declares `COLLECTED_BITMASK_OFFSET = 2`,
`KILLED_BITMASK_OFFSET = 18`, `COLLECTED_MASK_BYTES = KILLED - COLLECTED` (16) and
`MAX_LIST_ENTRIES = 128`; the loaded-mask twin is pinned in `engine/objects/entity_window.emp`
(`ENTITY_LOADED_OBJ_OFFSET*8 == MAX_LIST_ENTRIES`). The finding stands as written.

Enumerated by what TOUCHES the mask width, not by the one name:
- index-to-byte sites (`lsr.w #3` then `btst`/`bset` off the mask base, no release bound):
  Collected_CheckRing, Collected_MarkRing, Killed_CheckObject, Killed_MarkObject. Their DEBUG
  `assert.w ..., lo, #MAX_LIST_ENTRIES` bounds the index by the list size, which is the number
  that drifts, so it cannot see this;
- HAND-UNROLLED 16-byte sites: `clear_slot_bitmasks` (8 x `clr.l`), `Collected_ParkSlot`'s
  emptiness test (`move.l` + 7 x `or.l`);
- loops on `COLLECTED_MASK_BYTES` (the ParkSlot / UnparkSlot copies) and derived sizes
  (`COLLECTED_SLOT_SIZE`, `COLLECTED_PARK_ENTRY_SIZE` in the engine and both game configs):
  follow the constant, need nothing.

Guards (both in `entity_window.emp`):
- **P1**, beside the twin: `ensure(COLLECTED_MASK_BYTES * 8 == MAX_LIST_ENTRIES, ...)`.
- **P2**, at `clear_slot_bitmasks`: `COLLECTED_MASK_BYTES == 4 * 4` plus word-even
  `COLLECTED_BITMASK_OFFSET`, `KILLED_BITMASK_OFFSET` and `COLLECTED_SLOT_SIZE` (a `.l` at an odd
  offset is an address error).
Why two: satisfying P1 by widening the mask (its own instruction) leaves the unrolled sites
clearing and testing 16 bytes. Mutation M11 does exactly that and P2 stays red.
NOT covered, said in P1's message: `tools/ojz_entity_gen.py` carries its own
`MAX_LIST_ENTRIES = 128` that no build step compares with the engine constant. Proposed follow-up:
a pytest reading both.

## C2a-5: the DMA queue's RAM spans

Re-derived: `dma_queue.emp` pinned only `DMA_CRITICAL_SLOTS == 8` and `sizeof(DMAEntry) == 14`; the
layout is `engine/ram.emp`'s `mark DMA_Queue` .. `mark DMA_Queue_End` with a `_End` mark per
sub-queue. The second half of the finding's title ("the note that says otherwise names a deleted
file") was ALREADY corrected before this parcel: the `fill_slot_markers` header reads
"HISTORICAL, NOT A LIVE LOCKSTEP" (2026-09-07). The missing guard was still missing.

Readers of the layout, none checking it at runtime: `Init_DMA_Queue` (pre-fills register numbers
for `DMA_TOTAL_SLOTS` slots as ONE run from `DMA_Queue`); `QueueDMA_Critical/Important/Deferrable`
and `buffers.emp`'s `queue_static_dma` (the full test is EQUALITY of the cursor with a `_End`
mark); `Process_DMA_Critical`'s jump table (byte offset from `DMA_Critical`).

A span pin alone would NOT have caught the finding's own scenario. ram.emp DECLARES each array as
`SLOTS * sizeof(DMAEntry)`, so a span can only go wrong through a field between an array and its
`_End` mark. A field BETWEEN two sub-queues leaves every span correct and moves the next queue off
the pre-filled markers. So there are four guards over `extern()` marks (the `raster.emp` precedent), at the END of
`dma_queue.emp`:
- **P3** `DMA_Critical == DMA_Queue` and its span is `DMA_CRITICAL_SLOTS * sizeof(DMAEntry)`;
- **P4** `DMA_Important == DMA_Critical_End` and its span;
- **P5** `DMA_Deferrable == DMA_Important_End` and its span;
- **P6** `DMA_Queue_End - DMA_Queue == DMA_TOTAL_SLOTS * sizeof(DMAEntry)` (with P3-P5 green, this
  catches a field before `DMA_Queue_End`).
One shared does-not-cover list sits in the comment above them: the DMAEntry layout inside a slot,
the `w_addressable` dependence of the `.w` spellings, the `Static_*` copies, the Critical count,
and runtime occupancy.

## B2b-4: the YM floor, and why the pin is a test

Probe builds before choosing the route (aeon `cd075f2d`, `FAST=1 ./build.sh`, sonic4), each
restored with `git checkout --` and the tree shown clean:

| probe | driver's `YM_ADDR_TO_DATA_MIN_T` line | exit | reading |
|---|---|---|---|
| T1 | `use engine.sound_fm.{YM_ADDR_TO_DATA_MIN_T}` | 1 | `unknown name` at all 8 consumers; emit_sound_blob fails |
| T2 | `const ... = extern("YM_ADDR_TO_DATA_MIN_T")` | 0 | s4.bin 3393750122, identical to base |
| T3a | `const ... = extern("NO_SUCH_SYMBOL_LENS_PIN")` | **0** | a name that exists nowhere builds green |
| T3b | T2 + authority in sound_fm.emp raised to 100 | 1 | ONLY sound_fm's own 2 guards fired; the driver's 8 passed |

So a const does not cross a `use` between resident modules. Seam-1 turns `use` into extern PROC
stubs built from `pub proc` definitions only (sigil `crates/sigil-harness/src/seam1.rs`,
`import_stub_table` / `use_import_stubs`). And **`extern()` in a resident module is VACUOUS**. No
in-language cross-ensure is expressible; both routes that would make one possible are sigil changes
(a const-carrying `use`, or the name on seam-1's injected list).

The pin is `tools/test_ym_floor_single_authority.py`, in build.sh's build-fatal pre-build pytest
lane. It reads the authority's value off `sound_fm.emp`'s own `pub const` line, requires every other
`.emp` that touches the name in code to declare exactly one literal mirror equal to it, and REFUSES
a non-literal mirror, so the tempting `extern()` respelling fails closed. Consumers: 13 cycle guards
(2 in sound_fm, 8 in the driver, 3 in the sequencer), confirming the sift's count. `FAST=1` and
`NO_LINT=1` skip the lane; the test's docstring and all three declaration comments say so.

## B1-2 / LS-8a: the plane-wrap family

Re-derived by what TOUCHES the plane size (masks, wrap spans, cell counts, the row scale, the
column-write autoincrement), not by grepping `#63`, which six LS-8 pin messages quote. Code sites:

| file | horizontal (PLANE_H_CELLS) | vertical (PLANE_V_CELLS) |
|---|---|---|
| `engine/level/section.emp` | 13: RedrawPlanes plane A `$8F80`, `andi #63`, `lsl #7`, `cmpi #64`, plane B `$8F80`, `cmpi #64`, tracker `addi #63`; UpdateColumns `addi #63`, `andi #63`, `subi #63`, `subi #63`, `andi #63`, `addi #63` | 7: RedrawPlanes `andi #63`, `move.w #64`, plane B `moveq #32-1`; UpdateColumns `andi #63`, `subi #63`, `andi #63`, `addi #63` |
| `engine/level/plane_buffer.emp` | 6: Draw_TileColumn `lsl #7`; Draw_TileRow_FromCache `lsl #7`, `andi #$FFC0`, `andi #63`, `subi #63`; VInt_DrawLevel `$8F80` | 7: Draw_TileColumn `andi #63`, `move.w #64`; Draw_BG_TileColumn `4 + 64*2` x2, `lsl #7`, `(64 - 1)`, `moveq #32-1` |

33 sites; the row's 9 masks are among them. Pinned PER AXIS (P9/P10 in section.emp, P11/P12 in
plane_buffer.emp, each at the end of its file), because both constants are 64 today (the LS-8
two-families lesson). Expectations are derived in each guard (`PLANE_H_CELLS - 1 == 63`,
`(~(PLANE_H_CELLS - 1)) & $FFFF == $FFC0`, `PLANE_H_CELLS * 2 == 1 << 7`,
`PLANE_V_CELLS / 2 - 1 == 32 - 1`), and each message lists its sites by routine and instruction.

**VDP reg $10 (optional in the brief): DONE.** `BootData_VDPRegs`' `dc.b $11` now reads the named
literal `VDP_REG_PLANE_SIZE` (the same byte), declared at the end of `engine/system/constants.emp` in
the `VDP_REG_0C_BOOT` shape and pinned (**P13**) to the encoding of the two constants (VSZ 5:4,
HSZ 1:0; 32/64/128 map to 0/1/3). P13 is evaluated in the RAM-harvest pass and stops the build
before the family pins are reached. Its message says so, and says re-encoding the byte is not the
whole edit (see "broke" item 4).

NOT covered, named in the messages: `engine/level/bg.emp`'s plane-B blit and
`BG_LAYOUT_SIZE = 64*64*2`, which hand-spell the same geometry and are not pinned by this parcel; and
any scroll/parallax arithmetic assuming a 512-px plane, which was not walked.

## Four things that went wrong on the way, and what fixed them

**1. My four pin commits failed the CANONICAL build, and my green check could not see it.** I had
verified them with `FAST=1 DEBUG=1 ./build.sh` (sonic4 + demo, both exit 0), and FAST skips the
pytest lane. The harness's canonical runs each reported `2 failed`: the mutation's own test AND
`tools/test_citation_form.py`, "3 of 371 live `.emp:LINE` citations point at nothing". My inserted
lines had pushed `boot_data.emp:140` (cited by `docs/EFFECTS_AUTHORING.md` and
`engine/effects/raster_dsl.emp`) and `dma_queue.emp:170` (cited by `tools/dma_straddle_exercise.py`)
onto blank lines.

That gate sees only citations landing on a BLANK line, so I enumerated every `name.emp:N` citation
into the files this parcel edited and compared the base text at N with the tree's. **16 LIVE
citations** now pointed at different text, some of them EXACT at base: `tools/depth_onset_probe.py`
at the reg $10 byte; four citers at `Process_DMA_Critical`'s `jmp .jump_table`;
`tools/warp_mailbox_gate.py` at `move.w Cache_Top_Row, d6`. The fix (`cae58661`): no cited line
moves. The family and DMA pins go to the end of their files, and new imports fold into existing
`use` lines. After it, **1** live citation lands on different text, and it is the same line with the
same meaning (`boot_data.emp:186` is still the reg $10 byte, respelled). The other moved citations are
in RECORD files, which the gate freezes by design.

Side finding, NOT fixed here: the three citations the gate flagged were already pointing at the
WRONG text at base. `boot_data.emp:140` was a `// ----` rule line (the citers mean the reg `$0C`
byte, `$8C81`, in `BootData_VDPRegs`), and `dma_queue.emp:170` was `lea ENTRY_LEN(a1), a1` (the citer
means the straddle-reject split). Respelling them by name touches `engine/effects/raster_dsl.emp`,
which triggers the effects-gate ritual, so they belong with the comment-contracts parcel.

**2. A zero-byte const move produced a 6-byte placement overlap between two untouched sections.**
Putting `VDP_REG_PLANE_SIZE` and its pin at the end of `boot_data.emp`, after the `dc.b` that uses it,
turned sonic4 DEBUG FAST red: sections `ojz_scroll_test` [0xBE2D4, 0xC02F2) and `replay_fixture`
[0xC02EC, 0xC054C) overlap. Bisected one file at a time from that tree:

| reverted to its pre-move form | exit |
|---|---|
| none (control) | 1, same overlap |
| dma_queue.emp only | 1 |
| boot_data.emp only | **0** |
| section.emp only | 1 |
| plane_buffer.emp only | 1 |

Mechanism NOT established, and not guessed at. This is **reported for sigil as a measurement**: a
module-local const and ensure placed after their use in `boot_data.emp` changed ANOTHER module's
measured size. The const now lives at the end of `constants.emp`; `boot_data.emp` is back to its
base line count (233), with only its `use` line and the `dc.b` line changed.

**3. My own red-first harness overstated its first run** (fixed in `686d6ff3`). The P7/P8 keys
matched pytest's SOURCE echo, so P8 "fired" on mutations containing no non-literal. The quote-back
printed nothing for multi-line and newline-terminated mutations. No mutation reached P4. All three
were found by reading the per-mutation output and logs, not the summary.

**4. The first FULL harness run left P9-P12 NOT-RED, and the reason was masking, not death.** After
`cae58661`, M18 (`PLANE_H_CELLS` 64 to 128) and M19 (`PLANE_V_CELLS` 64 to 32) each fired P13
alone, and the harness exited 1 with "FULL RUN LEFT A GUARD UNPROVEN". Two readings fitted: the
family pins at the END of section.emp / plane_buffer.emp were dead, or something stopped the build
before they were reached. I discriminated by flipping each pin's OWN predicate (`== 64` to `== 65`
inside the guard, constants untouched, quoted back off disk). **All four fired**, so they are live.
The M18 log names the stop: `ram harvest build_program: 1 error(s)` on P13. P13 lives in
`engine/system/constants.emp`, which the RAM-harvest pass evaluates before the main build reaches
the level modules. On a plane-size change P13 is therefore the only message, and doing what it says
is not the whole edit: the LS-8 failure mode. `22bb44ac` makes P13 say it runs first and hides the
four family pins, and makes P9-P12 say they appear once the byte is re-encoded (they had claimed the
pins fire together). `87c289f6` adds M22 / M23, which follow P13's instruction and expect the
axis's family pins to fire. The same masking already shapes LS-8's own constants.emp pins (its M5
fires E4 alone). While there, the four LS-8 messages that still called this family "a separate
unpinned family (lens-sweep B1-F2, still OPEN)" now say where it is pinned.

## Red-first (tools/ls8_pin_redproof.py, full run, no arguments)

Run at `87c289f6` on a committed-clean tree: `REAL_EXIT=0 finished=1789155198`, **29/29 guards seen
RED** (the 16 LS-8 guards and this parcel's 13), C0 control exit 0 with 0 guards. Every mutation is
applied by exact-string edit, quoted back off disk, built, and restored with `git checkout --` of the
exact paths, with the tree asserted clean before and after. FAST=1 DEBUG=1 unless marked CANONICAL
(DEBUG=1, full lanes). The P13 harness label reads `boot_data`, from before the const moved; the
guard lives in `engine/system/constants.emp`.

| mutation (as read back off disk) | exit | guard(s) red, first line |
|---|---|---|
| M9 `constants.emp:1169: KILLED_BITMASK_OFFSET = 10` (the finding's own scenario) | 1 | P1 "...COLLECTED_MASK_BYTES = 8 bytes each (KILLED_BITMASK_OFFSET 10 - COLLECTED_BITMASK_OFFSET 2), which is 64 bits, but ... MAX_LIST_ENTRIES = 128 entries"; P2 "...hand-unrolled for 4 * 4 = 16-byte masks ... COLLECTED_MASK_BYTES = 8" |
| M10 `constants.emp:1172: MAX_LIST_ENTRIES = 256` | 1 | P1 "...16 bytes each ... 128 bits, but ... MAX_LIST_ENTRIES = 256 entries" |
| M11 M10 + `KILLED_BITMASK_OFFSET = 34` (P1's own instruction) | 1 | P2 alone "...COLLECTED_MASK_BYTES = 32 ... slot stride COLLECTED_SLOT_SIZE = 66" |
| M12 `ram.emp:388: pad(2)` inside DMA_Critical | 1 | P3 "DMA_Critical is no longer the first thing at DMA_Queue, or its span ... = 8 * 14 = 112 bytes"; P6 |
| M21 `ram.emp:389: pad(2)` between Critical_End and Important | 1 | P4 "DMA_Important no longer starts at DMA_Critical_End ... = 12 * 14 = 168 bytes"; P6 |
| M13 `ram.emp:391: pad(2)` between Important_End and Deferrable | 1 | P5 "DMA_Deferrable no longer starts at DMA_Important_End ..."; P6 |
| M14 `ram.emp:393: pad(2)` before DMA_Queue_End | 1 | P6 alone "DMA_Queue .. DMA_Queue_End in engine/ram.emp is no longer ... = 32 * 14 = 448 bytes" |
| M15 CANONICAL `sound_fm.emp:142: YM_ADDR_TO_DATA_MIN_T = 12` | 1 | P7 "engine/sound/sound_sequencer.emp:86: mirror says 8, the authority engine/sound/sound_fm.emp:142 says 12" (and z80_sound_driver.emp:117); pytest `1 failed, 2427 passed` |
| M16 CANONICAL `z80_sound_driver.emp:117: ... = 4` | 1 | P7 "z80_sound_driver.emp:117: mirror says 4, the authority ... says 8"; `1 failed, 2427 passed` |
| M17 CANONICAL `sound_sequencer.emp:86: ... = extern("YM_ADDR_TO_DATA_MIN_T")` | 1 | P8 "mirror is 'extern(\"YM_ADDR_TO_DATA_MIN_T\")', not an integer literal ..."; `1 failed, 2427 passed` |
| M18 `constants.emp:521: PLANE_H_CELLS = 128` | 1 | P13 alone, in the RAM-harvest pass: "reg $10 = VDP_REG_PLANE_SIZE = 17, but ... 128 x 64, which encodes as 19" |
| M19 `constants.emp:633: PLANE_V_CELLS = 32` | 1 | P13 alone: "... 64 x 32, which encodes as 1" |
| M22 M18 + `constants.emp:1216: VDP_REG_PLANE_SIZE = $13` (P13's instruction) | 1 | P9 "PLANE_H_CELLS is now 128, but engine/level/section.emp hand-spells a 64-column plane at 13 sites"; P11 "... plane_buffer.emp ... at 6 sites" |
| M23 M19 + `VDP_REG_PLANE_SIZE = $01` | 1 | P10 "PLANE_V_CELLS is now 32, but engine/level/section.emp hand-spells a 64-row plane at 7 sites"; P12 "... plane_buffer.emp ... at 7 sites" |
| M20 `constants.emp:1216: VDP_REG_PLANE_SIZE = $01` (the byte alone) | 1 | P13 "reg $10 = VDP_REG_PLANE_SIZE = 1, but ... 64 x 64, which encodes as 17" |

Reachability (EMP_PITFALLS section 3): `SIGIL_WARNINGS=full FAST=1 DEBUG=1` for sonic4 and demo,
both exit 0: no `module.unreachable` line names entity_window, dma_queue, section, plane_buffer,
boot_data or constants in either game. Red-first ran in sonic4 only; demo reachability is from
that listing.

## Landing build

`nohup bash -c './tools/landing_build.sh .runlogs/landing.log; echo "REAL_EXIT=$?"' > .runlogs/outer.log`,
launched at 1789155357 on code identical to `87c289f6` (the only later commit is this note, a
docs/superpowers file the citation gate treats as a RECORD). The `[logfile]` argument produced no
file; the complete output is in `.runlogs/outer.log`. Result: **`finished=0`, `REAL_EXIT=0`.**

```
EXIT_s4=0 size=821103
EXIT_s4.debug=0 size=847367
EXIT_demo=0 size=97051
EXIT_demo.debug=0 size=103335
EXIT_needs_build=0
finished=0
```

Every pytest summary line, in order (aggregate totals, none elided):

| lane | s4 | s4.debug | demo | demo.debug |
|---|---|---|---|---|
| pre-build (`-m "not needs_build"`) | 2428 passed, 2 skipped, 14 deselected, 5 warnings, 112 subtests passed | same | same | same |
| post-sigil (`-m needs_build`, per shape) | 5 passed, 9 skipped, 2430 deselected | 6 passed, 8 skipped, 2430 deselected | 1 passed, 13 skipped, 2430 deselected | 1 passed, 13 skipped, 2430 deselected |

The per-shape skips are deferrals the lane itself labels "NOT passes": each needs a shape that build
did not write. The final needs_build lane over all eight artifacts graded them: `14 passed, 2430
deselected`, "14 case(s) in the report: 14 ran, 0 deferred, 0 failed". For contrast, before
`cae58661` every canonical pre-build lane failed on `tools/test_citation_form.py` ("broke" item 1).

**Zero bytes, byte-identical rather than byte-count-neutral.** The four ROMs this run wrote (mtimes
1789155546 to 1789156306, all after launch) against the base, built before the first edit:

| ROM | base `cd075f2d` | tip | equal |
|---|---|---|---|
| s4.bin | 3393750122 821103 | 3393750122 821103 | yes |
| s4.debug.bin | 4112900988 847367 | 4112900988 847367 | yes |
| demo.bin | 755353563 97051 | 755353563 97051 | yes |
| demo.debug.bin | 4271321717 103335 | 4271321717 103335 | yes |

## Proposed ledger lines (the controller appends at landing; `fixedAt` is the merge)

```jsonl
{"id": "B2b-5", "at": "<stamp at append>", "sweep": {"date": "2026-09-06", "packet": "docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md", "sha": "9cfebb72", "pin": "61f22403"}, "seat": "B2b", "severity": "high", "title": "The collected and killed bitmasks have no guard binding their width to the entry count, while an identical twin one block away does", "state": "fixed", "where": {"path": "engine/objects/entity_window.emp", "symbol": "the ensure beside the loaded-mask pin, and the one above clear_slot_bitmasks"}, "fixedAt": "<merge>", "batch": "lens-pins-0911", "detail": "Two guards, not one. COLLECTED_MASK_BYTES * 8 == MAX_LIST_ENTRIES beside the ENTITY_LOADED_OBJ_OFFSET twin (the finding's fix), plus COLLECTED_MASK_BYTES == 4 * 4 with word-even offsets and stride at clear_slot_bitmasks: that template and Collected_ParkSlot's emptiness test are hand-unrolled for 16 bytes, so widening the mask as the first guard instructs is not the whole edit (red-first M11 does exactly that and the second guard stays red). Red-first with the finding's own scenario (KILLED_BITMASK_OFFSET 18 -> 10: both fire). NOT covered: tools/ojz_entity_gen.py's own MAX_LIST_ENTRIES = 128, compared with the engine constant by nothing. Zero bytes; evidence in docs/superpowers/notes/2026-09-11-lens-pins-parcel.md."}
{"id": "C2a-5", "at": "<stamp at append>", "sweep": {"date": "2026-09-06", "packet": "docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md", "sha": "9cfebb72", "pin": "61f22403"}, "seat": "C2a", "severity": "high", "title": "The transfer queue's memory layout is assumed contiguous by a routine, guarded by nothing, and the note that says otherwise names a deleted file", "state": "fixed", "where": {"path": "engine/system/dma_queue.emp", "symbol": "the four extern() span/adjacency ensures at the end of the file"}, "fixedAt": "<merge>", "batch": "lens-pins-0911", "detail": "Four link-time ensures over the ram.emp marks: each sub-queue STARTS where the previous one ends (Critical at DMA_Queue) and spans SLOTS * sizeof(DMAEntry), and the whole run is DMA_TOTAL_SLOTS * sizeof(DMAEntry). The adjacency half is the load-bearing one: ram.emp declares each array as SLOTS * sizeof, so a field BETWEEN two sub-queues (the finding's scenario) leaves every span correct. Red-first with a field inserted at four places, each firing its own guard. The title's second half (the note naming a deleted file) had already been corrected on 2026-09-07 (fill_slot_markers: HISTORICAL, NOT A LIVE LOCKSTEP). Zero bytes."}
{"id": "B2b-4", "at": "<stamp at append>", "sweep": {"date": "2026-09-06", "packet": "docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md", "sha": "9cfebb72", "pin": "61f22403"}, "seat": "B2b", "severity": "high", "title": "The sound driver's timing floor is mirrored as a literal in two modules with no pin on either side", "state": "fixed", "where": {"path": "tools/test_ym_floor_single_authority.py", "symbol": "test_every_mirror_equals_the_authority"}, "fixedAt": "<merge>", "batch": "lens-pins-0911", "detail": "sound_fm.emp's pub const is the authority; the two resident mirrors are held to it by a pytest in build.sh's build-fatal pre-build lane, which refuses a non-literal mirror. NOT an ensure, on measurement (probe builds on cd075f2d): a Z80 `use` of the const is `unknown name` at all 8 consumers; extern(\"YM_ADDR_TO_DATA_MIN_T\") in the driver builds green, so does extern of a name that exists nowhere, and with the authority raised to 100 the driver's 8 guards still passed: extern() in a seam-1 resident module is vacuous. Both in-language routes need sigil. FAST=1 / NO_LINT=1 skip the lane, stated at the test and the three declarations. Red-first: authority raised, one mirror lowered, one mirror respelled as extern: all red. Zero ROM bytes."}
{"id": "B1-2", "at": "<stamp at append>", "sweep": {"date": "2026-09-06", "packet": "docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md", "sha": "9cfebb72", "pin": "61f22403"}, "seat": "B1", "severity": "medium", "title": "Plane-wrap masks are spelled two ways in the same files, with nothing holding them in step", "state": "fixed", "where": {"path": "engine/level/section.emp", "symbol": "the two plane-wrap family ensures at the end of the file (twins at the end of plane_buffer.emp; the reg $10 pin at the end of engine/system/constants.emp)"}, "fixedAt": "<merge>", "batch": "LS-8a", "detail": "Enumerated by what TOUCHES the plane size, the family is 33 hand-spelled code sites in section.emp (13 H, 7 V) and plane_buffer.emp (6 H, 7 V), not the 9 masks the row counted: the rest are #63 wrap spans, #64 / #32-1 / 4+64*2 cell counts, the lsl.w #7 row scale and the $8F80 column autoincrement. Pinned per axis (both are 64 today). The VDP reg $10 side is DONE: BootData_VDPRegs' byte is the named literal VDP_REG_PLANE_SIZE, pinned to the encoding of PLANE_H_CELLS / PLANE_V_CELLS; it is evaluated in the RAM-harvest pass and stops the build before the family pins, and its message says so. NOT pinned: engine/level/bg.emp's plane-B blit and BG_LAYOUT_SIZE = 64*64*2. Red-first: an axis alone fires the reg $10 pin; following its instruction then fires that axis's two family pins; the byte alone fires the reg $10 pin. Zero bytes."}
```

## What the brief got wrong, or weaker than stated

- **B2b-4 asked whether "a Z80-side module can import a 68k `pub const`".** All three declarations
  are in Z80 resident modules; the authority is itself a Z80 module's `pub const` (sound_fm.emp), not
  a 68k one. The real question was Z80 to Z80, and the answer is no (T1). The brief's fallback,
  "pin them with cross-ensures", is not expressible either, because `extern()` there is vacuous
  (T3a/T3b). The pin is therefore a build-fatal pytest, which a FAST loop does not run.
- **B1-2's "about 9 code sites" is the mask count, not the family.** By what touches the plane size
  it is 33 sites in the two files, plus the reg $10 byte, plus bg.emp (unpinned).
- **C2a-5's fix as briefed (each span equals slots x 14, the whole equals the total) would not catch
  the finding's own scenario**, a field inserted BETWEEN two sub-queues: ram.emp declares each array
  as `SLOTS * sizeof(DMAEntry)`, so every span stays right. The adjacency conditions catch it, and
  they are in the guards.
- **"Build with `./build.sh`" for red-first leaves out a distinction that matters.** The LS-8 harness
  builds `FAST=1`, which cannot show a pytest-lane guard. My own FAST green checks missed that my
  commits failed the canonical build (the citation gate, "broke" item 1). The B2b-4 mutations run
  canonically.
- **The B2b-5 ledger row's `where` says `constants.emp` line 1119**; the declarations were at
  1169-1172 at the branch base (the sift had it right).
- Confirmed as stated: `f7406b97` is an ancestor; 13 consuming cycle guards (2 + 8 + 3); the C2a-5
  pins were only `DMA_CRITICAL_SLOTS == 8` and `sizeof(DMAEntry) == 14`; the B2b-5 twin at
  entity_window.emp.
