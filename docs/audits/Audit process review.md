---
kind: review
status: awaiting-owner
description: "Keep the audit, change it before rollout: the pilot's findings are real, but it was a VBlank audit more than a whole-frame audit, its measurements cover 2 of 7 legs in the shipped build, and nobody checks the lead. Do not restart the engine; rewrite the failing systems beside the old ones."
---
# Audit process review (pilot: frame architecture)

Independent review of the pilot audit process, written 2026-11-16. I read the template, the board, the orchestration script, the four stage reports, the merged page and the two context docs, then checked claims against the source at `aeon` master `936439fa` (clean tree, last code commit 2026-09-28). I ran no emulator and built nothing. I did not re-fetch the research stage's web sources.

## Verdict

> [!verdict] Keep the process, change it before rollout
> - **The findings are real.** I checked 16 claims in code and in the raw measurement files. 12 hold exactly, 3 hold with a wrong label or a missing qualifier, and 1 is wrong (and the lead caught it).
> - **The depth is uneven.** The VBlank handler was read line by line. The tick itself (the order of work inside the game state) was barely read, so the "whole-frame review" half of the pilot is not done.
> - **The measurements are thinner than they look.** In the release build, 2 of the template's 7 fixed legs produced usable data.
> - **Independence worked for breadth, not for the verdict.** Each reviewer found about four things the other missed. Both missed the one known defect that no prompt mentioned.
> - **The cost is fair for the pilot and too high as a unit to repeat 15 times unchanged.** About a third of the reviewer output restates the research and measurement stages.
>
> Make changes 1 to 4 below before wave 1. Do not restart the engine on this evidence.

## How thorough it really was

### Spot-check table

| # | Claim | Stage | My check | Result |
|---|---|---|---|---|
| 1 | The lag path still queues and sends sprites and HScroll | A, B, lead | `vblank.emp:362`, `:456`; `buffers.emp:464-473`, `:505-507` | Holds |
| 2 | The tile-row drain runs before the must-ship transfers | B | `vblank.emp:176` then `:206` | Holds |
| 3 | A full VBlank overwrites the press byte and clears the accumulator | B | `vblank.emp:304-312` | Holds |
| 4 | Flight fuel reads `Frame_Counter` | A | `player_fly.emp:271` | Holds |
| 5 | `Parallax_Update` writes register `$0B` directly from the main loop | B | `parallax.emp:2025-2051` | Holds. The visible effect is still unproven |
| 6 | Palette is flagged ready before the fade is applied; raster re-flags it every VBlank | B, A | `palette.emp:413-426`; `raster.emp:1097-1098` | Holds |
| 7 | The lower queues stop at the first entry that does not fit | A | `dma_queue.emp:466-469` | Holds |
| 8 | `DMA_Peak_Critical`, `DMA_Peak_Deferrable`, `DMA_Bytes_ThisFrame` are never written | B, stage 2 | grep over `engine/` and `games/` | Holds |
| 9 | `GameState_Idle`, `Game_State_ID`, `Region_Flags`, `Hardware_Region`, `PlaneMapToVRAM` have no reader | A | grep | Holds |
| 10 | `Set_VDP_Reg` has no caller | A | `parallax.emp:1914`, `:1917`, `:1921`, `:1924` | **Wrong.** Four callers. A trusted the routine's own header. B and the lead had it right |
| 11 | `TouchResponse` runs after `Camera_Update` | lead | `ojz_scroll_test.emp:1117`, `:1211` | Holds. Neither reviewer examined it |
| 12 | S3K lag handling, PAL delay loop, Kos bookmark, 2P comment | research | `sonic3k.asm:515-519`, `:528-531`, `:620-624`, `:2818` | Holds |
| 13 | Vectorman's 54-entry and 2,880-byte caps; TF4's RAM-patched HBlank | research | `vectorman_disasm/ANALYSIS.md:114`, `:120`; `thunderforce4_disasm/ANALYSIS.md:190` | Holds, but these are our own summary notes, not the disassembly |
| 14 | 18 lag frames; 10 inside `Parallax_Update` with the sprite table ready | stage 2 | raw `analysis.txt`: 10 + 6 + 2, phases and interrupted PCs listed | Holds |
| 15 | "The camera had moved 6 to 16 px" on those 10 frames (labelled MEASURED) | stage 2, lead finding 1 | `analyse.py:74-86`: the probe latches the camera at `Parallax_Update` entry, so those 10 frames read **0,0**. The 6 to 16 px figures belong to the 4 frames inside `Render_Sprites` | **Mislabelled.** The size is right by inference (one tick of camera travel). It was not measured on the frames it is quoted for |
| 16 | "Worst VBlank used 97% of the window"; "about 12,000 pictures" | stage 2, lead finding 2 | stage 2 tables; sum of frames run | **Missing qualifiers.** 97% is the DEBUG build (18,052, MEASURED); release is 82% (15,242, MEASURED). Frames run total 10,939 (MEASURED from the leg table), of which 6,000 are the stuck run leg |

### Where the reading went

Distinct `file:line` citations per reviewer (MEASURED by grep over the two reports; a crude count, since diagrams cite lines without the file name):

| File | Lines | Reviewer A | Reviewer B |
|---|---|---|---|
| `engine/system/vblank.emp` | 553 | 32 | 24 |
| `engine/system/buffers.emp` | 510 | 9 | 3 |
| `engine/system/dma_queue.emp` | 657 | 6 | 5 |
| `engine/effects/raster.emp` | 2,426 | 5 | 2 |
| `games/sonic4/test/ojz_scroll_test.emp` (the shipped tick) | 4,570 | 2 | 2 |
| `engine/system/replay.emp`, `controllers.emp` | 551 | 4 | 0 |
| `engine/sound/z80_sound_driver.emp` | n/a | 0 | 0 |

> [!finding] It was a VBlank audit
> The handler that commits the picture got 56 citations. The 4,570-line file that holds the real order of a tick got about seven lines of attention from each reviewer, all of them call sites. The scope statement says "every cross-file interaction that order creates". Only the interactions that end in a VDP commit were traced.

### The measurements

| Template leg | DEBUG | Release (the shipped shape) |
|---|---|---|
| Idle | ran | ran |
| Run | ran, but stuck at camera x ≈ 1046 | ran, same fault |
| Top speed | ran (free flight) | did not run |
| Diagonal fall | ran (free flight) | did not run as such; the spindash leg stands in |
| Spindash | ran | ran |
| Object-heavy | did not run | did not run |
| With a sidekick | did not run | did not run |

- **Completeness is proven** for the legs that ran: return codes, `finished=` stamps, and two probes agreeing on lag counts and camera paths. This part is good.
- **Coverage is thin.** Release has two valid legs. 16 of the 18 lag frames are DEBUG. The headline "10 of 18" rests on three legs.
- **Tooling.** The emulator core is an archived build (`549dc4f`, 2026-09-26). No report records the aeon commit, only ROM CRCs. Nothing cross-checks the core's DMA stall timing against a second emulator, and finding 2 depends on that timing.
- **Wall clock.** All 16 probe runs took 2 minutes 5 seconds (MEASURED from `legs.meta`). Emulator time is not the limit. The harness's reach is.

### The research

- Local citations I checked are real and say what the report says (rows 12 and 13).
- The stage ran for about 8 minutes (MEASURED from file times). It leaned on our own `ANALYSIS.md` summaries. In its scorecard the lag-commit cell reads "not documented" or "—" for Treasure, TF4 and Batman. That is the cell the audit's main verdict turns on.
- It contradicts itself on novelty. Its conclusion says nobody commits a snapshot of the previous complete frame. Its own table says Vectorman drains "the previous complete list" with no torn-state risk. The "beyond anything shipped" label on the all-or-nothing publish was carried into the merged page without a primary-source check of what Vectorman double-buffers.
- Its binding order (DMA bytes first) and its CPU-copy cost (5 cycles a byte, ESTIMATED) were both overturned by the reviewers using stage 2 (cycles bind; about 8.75 cycles a byte, MEASURED). That is the process working.
- Not covered against the repo's own research checklist: sonic_hack, Hidden Palace prototypes, the Amiga demoscene.

### Independence

| Found by | Items |
|---|---|
| Both | Mixed lag frame; byte budget does not bound time; tile-cache spike; single VBlank handler; stale docs; no lag instruments |
| A only | `Frame_Counter` in game logic; oversized entry blocks its queue; raster route to a half-built palette; frame order lives in a test file |
| B only | Direct `$0B` write; must-ship data after the drain; 30 Hz loses presses; HScroll gated on parallax; dead peak counters; TF4 doc conflict |
| Neither | Solids after the camera (known); everything under "What it missed" |

- **Worth the cost for breadth.** A single reviewer would have dropped four or five real findings.
- **Not independent on the verdict.** Both read the same stage 1 and stage 2, and stage 2's prompt named the suspected lag defect. Both then "confirmed" it. The one known frame-order defect that no prompt named, both missed. So the reviewers reliably cover what the inputs point at.
- **Wasted overlap.** Both wrote sections 3, 4 and 5 as "I accept stage 1 / stage 2" plus a restated table. Both rebuilt the section 2 inventory by hand, and one got a caller count wrong.

### The merge

Mostly faithful. The lead settled five disagreements in code and was right on each one I checked. Three problems:

- **Softened.** The verdict says "the lag itself is not a frame-design problem". Reviewer B said the opposite in so many words: nothing in the main loop is admitted against a deadline, and that is a frame-architecture fact.
- **Inflated by omission.** The 97% figure appears without "DEBUG". The 6 to 16 px figure appears as measured.
- **Dropped.** Stage 2's sound and Z80 runtime item, reviewer A's HBlank priming-fire check, reviewer B's partial-art findings (F6f, F6g), and A's silently stale HScroll on a full Critical queue did not reach the merged page.

Nobody reviews the lead. The controller's verification is the only check, and it is not in the script.

## What it missed

> [!finding] 1. The tick's own order was not reviewed
> `RunObjects` (`ojz_scroll_test.emp:1109`), `Camera_Update` (`:1117`), `Tile_Cache_Fill` (`:1132`), `TouchResponse` (`:1211`), `Render_Sprites` (`:1263`). Nobody asked what each step reads that a later step changes. Solids after the camera is one instance. The pilot was meant to close process change 5 (whole-frame review). It closed the commit half.

> [!finding] 2. The engine already throttles on lag, and no stage mentions it
> `Tile_Cache_Fill` keeps a trailing-lag flag from the `Frame_Counter` delta and skips one frame of speculative fill after a lag (`tile_cache.emp:1068-1083`, `:1584-1592`). `PageIn_Process` keeps its own lag latch and prefetch budget (`page_in.emp:105-118`). Finding 3 and change 8 propose deadline admission as if nothing existed. Both reviewers quoted the comment three lines above the gate and did not describe the gate.

> [!finding] 3. Streaming decisions depend on lag, and lag differs by build
> Those gates read `Frame_Counter`, as do the page-cache age stamps (`page_cache.emp:529`, `:709`, `:758`, `:1334`). DEBUG and release lag differently (6 against 2, MEASURED). So what is cached, and when, differs by build. Whether that can reach game logic (collision reads the cache) is unexamined. Finding 5's lint covers only `games/*/player` and `games/*/objects`.

> [!finding] 4. The overrun finding and the sound verdict contradict each other
> The DAC ring holds a lead of 128 to 200 samples, about 7 to 11 ms at 18,356 Hz (`sound_constants.emp:206-212`, constants; the comment says it "outlasts any real 68k DMA stall"). Reviewer B's overrun case freezes the 68000 for about 84,000 cycles, which is about 11 ms (ESTIMATED from B's figure). The flag stays raised for all of it. If finding 2 is right, sound does not "keep playing through video transfers" on that frame. No stage read `z80_sound_driver.emp`. The "best known" rating for sound rests on the 68000 side only.

> [!note] Smaller gaps
> - Level load, the first frame after boot, and state changes (`VInt_Ptr` swaps) were not walked.
> - The error handler and debugger inside a frame were not looked at.
> - Stack depth with HBlank, VBlank and the decoder bookmark nested was not looked at.
> - PAL and a streaming act are on the live-run list, which is honest, but it means the idle decoder, the feature the frame was built around, has zero measured calls.

## What it got right

- **Stage separation.** Research and measurement did not judge code, and reviewers challenged both with evidence.
- **Labels and "did not run".** Every stage used them, and stage 2 reported the stuck leg and the missing legs instead of hiding them. The two label slips above are the exceptions.
- **Proof of completeness per leg**, and a second witness for lag in each build.
- **Tests that fail first.** Most findings come with one. That is the difference between this audit and the 2026-11-13 review.
- **The dropped list.** It stops "charge tile rows at the true rate" from being proposed a third time.
- **A named non-Sonic game.** It produced the two best reuse findings (HScroll gated on parallax, 30 Hz input loss).
- **Reviewers checked doc claims one by one.** Thirteen claims each, with results.

## Changes before rollout

Ranked. Cost and depth effects are ESTIMATED unless marked.

| # | Change | Why | Cost | Depth |
|---|---|---|---|---|
| 1 | **Fix the harness and stress content once, before wave 1.** A stress shape with spawned objects and a second player, a streaming act, a PAL boot, a working run leg, a release top-speed leg, a probe for the line where VBlank ends, and a pinned fresh emulator build. Record the aeon commit in every report | Every later audit hits the same "did not run" wall. Section 5 is the only part of the audit that cannot be argued with | One-off, about one audit's worth | Release legs go from 2 of 7 to 7 of 7. Most "needs a live run" items disappear |
| 2 | **Add a mechanical inventory stage and delete section 2 from the reviewers.** One agent, mostly grep and the listing: call order of the tick and both handlers, caller counts for every routine in scope, readers and writers of each shared variable, the doc-claim list, footprint | Two reviewers rebuilt it by hand and one got it wrong. A reader/writer table would have exposed the lag gates and the `Frame_Counter` readers | Saves about 15% of reviewer tokens | Higher. Inventory errors go away |
| 3 | **Reviewers write sections 1, 6, 7 and 8 only, and must fill a coverage table**: every file in scope, lines read, "finding" or "read, nothing". Give each a different mandatory walk: one walks VBlank landing at every point of the tick; the other walks the tick's logic order and ports the named game onto the engine on paper | Removes the restated sections 3 to 5. Forces the 4,570-line file to be read. Keeps independence where it paid | Saves about 15 to 20% | Broader for the same money |
| 4 | **Add a checker between the reviewers and the lead, one bounded round.** It re-opens every cited `path:line`, checks every number's label and build shape against the raw files, checks the coverage tables for unread files, and holds the known-defect list from earlier reviews. Gaps go back to the reviewers once | Would have caught rows 10, 15 and 16, the solids miss, and the four dropped items. Keeps reviewers blind while still closing known defects | Adds about 10% | The largest gain in accuracy per token |
| 5 | **Research rules.** No "not documented" in the scorecard cell the verdict depends on: read the disassembly. A "nobody ships this" claim needs a primary-source check. Write section 4 (hardware limits) once into a shared page and cite it | The floor comparison and the novelty claims rest on summaries | Slightly more per audit, less overall after the shared page | Verdicts become defensible |
| 6 | **Lead rules.** State DEBUG or release on every number. Never restate a reviewer's verdict in softer words. Carry every needs-runtime item or say why it was cut. At most five owner decisions, ranked | The three merge problems above; 8 decisions per audit is about 120 across the rollout | None | Trust in the merged page |
| 7 | **Fix between waves.** Run wave 1, land the cheap fixes, then run wave 2 on the fixed tree. Skip sections 5 and 7 for any system already marked for replacement | Audits go stale as soon as code changes. Measuring a tile cache that the block rework will delete is waste | Saves most of one audit per replaced system | Same |
| 8 | **Add the idiom check** described under "Restart or improve in place" to section 7 | The owner's port-residue concern needs evidence per system | Small | New evidence for the restart question |

**The unit.** One system, 8 sections, is right. Five agents becomes six (inventory, research, measurement, two reviewers, checker) plus the lead, at roughly the same token cost (ESTIMATED: about 1.0M to 1.1M, against 1.06M MEASURED by the controller for the pilot), because the reviewers write half as much.

**The system list.**

| Issue | Detail |
|---|---|
| Missing | Compression (a system in the 2026-11-13 review, absent from the board). The level bake tools and build gates. RAM map as a cross-cutting resource. The tick's logic order: give it its own short pass now, do not wait for the collision audit |
| Overlapping | Tile streaming + art pool, VRAM layout and DMA queue share one budget. Object system, object interaction and collision + physics share one loop. Camera and background + effects share parallax. Name one owner audit for each shared item |
| Mis-scoped | The pre-build row (HUD, saves, water, lives) lists systems that do not exist. Those are design reviews: sections 1, 3, 4 and 8 only, no reviewers needed twice |
| Order | The frame audit deferred work to the tile-cache, collision, sound and engine/game contract audits. Three are in wave 1. Move collision up, or its part of the frame order stays open |

## Restart or improve in place

> [!verdict] Do not restart. Rewrite the failing systems natively, beside the old ones
> It is early: one audit of sixteen is done, on one of the healthier systems. But the evidence so far points one way, and the choice between the three options does not need to wait.

### Is the frame code port-shaped?

I read about a dozen files, not the engine. Within them: **the guards are idiomatic, the structure is ported.**

| | Evidence |
|---|---|
| **Idiomatic** | `with z80_stopped`, `with ints_off`, `requires(vblank)` / `grants(vblank)`, `ints_off_until_rte` in `Raster_HInt`, `irq_frame.pc` and `ZX0R_Decompress.__end` for the bookmark (`vblank.emp:70-76`), `ensure(cycles(.loop, .exhaust) == 195)` in the Z80 driver, `invoke Game.debug_tick`. These are real uses of the language, and they catch real bugs |
| **Ported structure** | The VBlank step order is a hand-written call sequence, and three docs restate it by hand, all stale. A native design would declare the stages once as data and generate the handler, the doc and the budget from it |
| | The budget is a literal with its derivation in a comment (`constants.emp:759-771`), not a `comptime fn` over lines, rate and measured fixed cost |
| | `VInt_Level` walks the Critical queue at run time to sum bytes (`vblank.emp:183-196`) though the entries are static |
| | Raw structure offsets where the conventions demand a `struct`: `6(a2)`, `8(a2)`, `10(a2)` (`buffers.emp:420`, `:454`, `:456`) |
| | Hand-kept flag protocols (`VBlank_Ready`, `VBlank_Flag`, `Sprite_Table_Dirty`, `Sprite_Emit_Active`) whose rules live in comments |
| **Residue** | Comments echoing AS operand syntax, such as `// (Palette_Dirty).w`: 79 in `ojz_scroll_test.emp`, 22 in `dma_queue.emp` (MEASURED by grep). Comments describing deleted `.asm` twins (`dma_queue.emp:27-30`, `:292`). Twelve "widths pinned" workaround notes in 20 lines (`vblank.emp:304-322`) |
| **Accretion** | Comment share: `raster.emp` 74%, `ojz_scroll_test.emp` 67%, `vblank.emp` 65% (MEASURED). Dated history lines: 39, 47 and 11 |

The residue is cosmetic and cheap to strip. The ported structure is the real cost: it is why the docs drift and why frame-order bugs live between files. But none of the pilot's findings is caused by the port. Each is a design decision that would have been made the same way in native `.emp`.

### The three options

| Option | Throws away | Gains | Risk |
|---|---|---|---|
| **A. Full restart in native `.emp`** | The systems rated at or past best known (DMA queue, sound bus handling, input and replay, raster, paged art pool). The proofs and gates. The level bake pipeline's assumptions. Months of hardware lessons that today exist only in comments | One idiom throughout. Frame phases and data formats designed in from the start | High. The 2026-11-16 process doc blames the process, not the code: gates checked intent, features ran ahead of a game. A restart under the same process rebuilds the same problems. And there is no second engine to test against while the new one is empty |
| **B. Per-system native rewrite beside the old one** | Only the systems an audit rates below the floor for a structural reason | Native idiom where it pays. The old system stays as the behaviour oracle, the suite's proven pattern (sigil beside asl, oracle beside oracle-old). The game keeps booting throughout | Medium. Needs each system to have a stated interface first, which is what the engine/game contract audit is for |
| **C. Patch in place** | Nothing | Cheapest per fix | Structure never improves. Correct for healthy systems, wrong for the tile cache |

**Recommendation: B where an audit says "below the floor, structural", C everywhere else.** From the two reviews so far:

- **Rewrite beside (B):** tile cache and block format (four copies per tile, about five times S3K per tick; a replacement design already exists), the level data format with it, the sound driver if the hybrid is approved, and a new engine-owned frame-phase skeleton that the existing routines plug into.
- **Patch (C):** lag policy (about 20 lines), commit order (swap two blocks), budget, `Frame_Counter` in logic, DMA queue slots, docs.
- **Strip everywhere, mechanically:** dated history, AS-echo comments, references to deleted twins.

### What would change this answer

1. Wave 1 (level data format, tile streaming, engine/game contract) each returns "replace", **and** the replacements break the interfaces the healthy systems rely on (the transfer entry, the RAM map, the object record), so more than about half the engine's code lines must change anyway.
2. The idiom check shows the healthy systems are also port-shaped, and defects traced to that shape (stale hand-spelled pins, drifted literals) are a large share of their findings.
3. The frame-phase skeleton cannot be introduced without rewriting every state and every producer.
4. The vertical slice cannot be built on the current engine in a bounded time.

If two of these hold after wave 1, a restart becomes the cheaper path, and by then the audits will have written its specification.

### Idiom check to add to section 7

Per system, counted by script where possible, with `file:line` for each hit:

| Check | What counts |
|---|---|
| Run-time work that is known at build time | loops or sums over static tables; literals whose derivation is in a comment |
| Layout literals | raw `n(aN)` offsets, raw plane or stride numbers, where a `struct` field or constant exists |
| Hand-spelled pins | `ensure` lines guarding a literal that could be derived, so the pin exists only because the value is not computed |
| Facts stated more than once | step orders, sizes or budgets repeated in comments or docs instead of generated |
| Protocols kept in comments | flags or ordering rules with no type, capability or `ensure` behind them |
| Port residue | AS-syntax echoes, references to deleted `.asm`, sized branches, workaround notes for assembler gaps |
| Comment load | comment share and dated-history lines per file |
| Verdict | one of: **native**, **native guards on ported structure**, **transliteration**. With one sentence on whether any finding in section 6 is caused by it |

The last line matters most. Residue that causes no defect is a cleanup task. Residue that causes defects is evidence for a rewrite.

## Controller notes: agree / disagree

Read after everything above was drafted.

| Controller note | My view |
|---|---|
| 1. Archived emulator core; run leg stuck | **Agree.** I add: no report records the aeon commit, and nothing validates the core's DMA stall timing, which finding 2 depends on |
| 2. No object-heavy or sidekick leg | **Agree, and it is wider.** Release has 2 valid legs of 7. No streaming act either, so the idle decoder has zero measured calls |
| 3. Solids after the camera examined by neither reviewer | **Agree on the fact. Partly disagree on the cause.** Blindness was not the cause. Both reviewers found the lag defect because stage 2's prompt named it. They missed solids because nothing pointed at the tick's logic order and nothing forced them to read the state file |
| 4. Live-run items; the overrun is arithmetic | **Agree.** The merged page lists 10, not 11. I add that the same arithmetic contradicts the sound verdict (the DAC ring's lead is about the length of the overrun) |
| 5. `$0B` write is real and deliberate; redraw case only on DEBUG warps | **Agree** on `$0B` (I checked it). Reviewer A says the redraw also runs at level start |
| 6. Cost 1.06M tokens, 28 minutes | **Agree** on wall clock (file times 12:29 to 12:57). Fair for a pilot. About a third of reviewer output was restatement |
| Lead: give both reviewers the earlier review | **Disagree.** It anchors them, and the earlier review's first round made three confident wrong calls. Give the known-defect list to the checker (change 4), which sends unexamined items back |
| Lead: add a stress leg; build the emulator first | **Agree.** This is change 1, and it should happen once, before wave 1, not per audit |
| Controller: add a completeness critic | **Agree, with limits.** Make it mostly mechanical (coverage table, citation re-check, label check, known-defect list) and allow one round only. A free-form critic will produce more prose, not more coverage |

**Found beyond the notes:** the mislabelled 6 to 16 px figure; 97% quoted without "DEBUG"; reviewer A's wrong caller count; the lag-feedback gates nobody described; lag-dependent streaming state; the overrun against the DAC ring; the research stage's reliance on summary notes and its self-contradiction on novelty; the lead softening one verdict and dropping four items; duplicated sections 2 to 5.
