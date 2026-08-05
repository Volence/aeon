# Engine-wide Optimization Review — 2026-07-16

Static optimization review of the ENTIRE codebase, in four waves (29 independent reviews).
**Wave 1** (hot per-frame .emp ports): `plane_buffer`, `tile_cache`, `entity_window`,
`sprites`, `core`, `collision` + `collision_lookup`, `animate` + `rings`.
**Wave 2** (remaining .emp): `section`, `sound_api`, `dplc`/`load_object`/`frames`/
`objdef`/`sst`, `hblank`/`game_loop`/`controllers`/`math`/`vdp_init`/`types`, `aabb` +
test objects, and the data/definition files (`structs`/`constants` twins + game data).
**Wave 3** (hot .asm with no .emp twin — NO lockstep constraint on these): `parallax`,
`vblank`/`dma_queue`/`buffers`, `camera`/`bg_anim`/`s4lz_decompress`,
`player_ground`/`air`/`spindash`, `player_common`/`sensors` + `sonic.asm`,
`children` + `macros`.
**Wave 4** (everything else — full coverage): `boot`/`vectors`/`z80_init`,
`zx0_decompress`/`load_art`/`bg`, `ram`+`constants`+game configs (alignment audit),
debug cluster (`debugger`/`error_handler`/selftests/`game_debug`), game shell
(`main`/`ojz_scroll_test`/`object_test_state`/demo), game test objects (+`path_swap`),
and the Z80 sound driver: core (`z80_sound_driver`+`dac_sample_tab`+`sound_constants`),
`sound_sequencer`+opcode table, `sound_sfx`, `sound_fm`+`sound_psg`+`sound_tables_z80`.

**STATUS (CORRECTED 2026-07-17):** ⚠ The prior STATUS line ("the correctness bugs in the
roll-up below have been FIXED") was INACCURATE. Only a specific, self-contained subset was
fixed by the two merged batches:
- **sprites branch** (`fix/sprites-pb1-pb2`): **PB1** (Sprites_Rendered frozen-ghost),
  **PB2** (scanline-band index unbias).
- **wave-2 batch**: **B1** (VSync_Wait torn-drain SR mask), **C1** (Read_Controllers second
  TH-settle nop), **D1** (dplc_layout.py 16-tile merge cap + overflow assert — the review's
  dplc D4 build hole), **E1** (section adda.w ≤496 mega-act ensure), **P1a** (parallax
  deformShiftDefault=15), **P1b** (camera/player mega-act ceiling — found ALREADY
  transitively guarded; site comments only), **H-1** (Sound_PlayMusic repost gate — MUSIC
  slot only).

**Everything else in the roll-up REMAINS OPEN.** A doc-reconciliation pass (2026-07-17)
found the review's own **buffers bug #1** (Palette_Dirty/Sprite_Table_Dirty cleared on a
silently-dropped enqueue) was never fixed, and Fable verified it live — including that
**Sprite_Table_Dirty has the identical shape** and that **load_art's ignored
QueueDMA_Critical carry** (line ~380) is the same silent-drop class. The definitive
remaining-functional-bugs table is the **"REMAINING FUNCTIONAL BUGS (2026-07-17 audit)"**
section immediately below; the silent-drop class is being fixed under the
`fix/silent-drop-class` parcel. A separate newly-surfaced doc-writer finding — the **PAL
timestep is written at boot but has zero readers** (boot.asm:167-174; GameLoop runs one
tick per VSync unconditionally) — is recorded in `docs/DEFERRED_WORK.md` as an unfinished
feature awaiting a product decision (PAL support vs NTSC-only), NOT a bug.

Execution order for what remains: **(1) the Sigil diagnostics tier (next section) → (2) the
performance items**, with the correctness bugs in the table below triaged and scheduled per
their listed disposition. The diagnostics come first deliberately — several performance
items are register/contract surgery (movem trims, register-resident rewrites, drain
restructures) that the diagnostics make safe to perform and impossible to regress.

All cycle figures are estimates (68000 cycle tables / Z80 T-state tables); no emulator
profiling was run. The cross-file priority list and bug roll-up below cover ALL FOUR
waves. Coverage is complete: every engine and game source file has been reviewed.

## STATUS UPDATE (2026-08-03) — wave-4 items 23 + 24 EXECUTED

**Item 23 (sound bug-fix batch) and item 24 (Z80 size-reclaim campaign) are EXECUTED**, on
`parcel/wave4-z80-sound-reclaim`. Plan:
`docs/superpowers/plans/2026-08-03-wave4-z80-sound-reclaim.md`. A/B evidence:
`docs/superpowers/notes/2026-08-03-wave4-sound-ab.md`. Defect write-ups: `docs/BUGS.md`.

- **Item 23** — all five listed defects fixed, plus three extras approved at plan time
  (sequencer B1 PSG glide underflow, FM bug 11 patch-load pan clobber, PSG M5 unguarded
  detune fold), plus two build-time nets (sequencer B2 env assert, SFX B4 alias ensures).
  Driver B2 was dropped, not fixed — see below. Cost **+28 B** (planned +20).
- **Item 24** — reclaimed **−231 B** net across SFX, driver core, FM, PSG and a sigil-side
  dense-pad mode. Resident blob **6172 → 5941 plain**, **6298 → 6067 debug**; DEBUG headroom
  against the `$18F0` ceiling **86 B → 316 B**. The review hoped to "roughly triple" the
  86 B; the measured result is 3.7×.
- Frozen as provenance chain entry 33.

### Dropped or REJECTED during execution (with reasons)

| Item | Disposition | Reason |
|---|---|---|
| **driver B2** (Snd_LoadSong repost race, +8 B) | **DROPPED** | The corruption half is already closed by **H-1** (slot clear moved ahead of the last param read) plus the 68k's pre-write gate — it spins on `MUSIC_SLOT == 0` *before* writing, and all params post under one bus hold. What remained was 68k spin latency only, which **driver M1** (`.seq_clr` → `LDIR`) buys for **−1 B** instead of +8. |
| **SFX S4** (DrainQueue 3-way max) | **DROPPED** | Review scored −15..25 B; the actual unroll **measures +3 B**. `Sfx_QueueEntryPtr` cannot be deleted (three other callers). Cycle-only win, no bytes. |
| **SFX S1** (evict 3 lookup tables to the banked window) | **DROPPED** | Its precondition — "append a sixth banked head without disturbing the existing pins" — is FALSE, proven by bytes: the five head artifacts concatenate to exactly `$607` with **zero slack**, so a sixth head moves **8 pinned regions**, and **three of those are hardcoded as literals** that `repin` cannot fix. Cost far beyond "register a symbol" (new banked module, new seam-2 emitter, new layout field, artifact write, embed + size ensure) for **36 B**. Not worth destabilising the bank layout. |
| **FM micro** — delete the two `nop`s in `Fm_YmWrite` | **REJECTED** | 2 B for the **only** change in the entire campaign that NARROWS YM address→data spacing (≈21 T → ≈17 T). |
| **sequencer M2** (cache `sc_flags` in a register) | **REJECTED** | Real saving is **−5..12 T**, not the reviewed −40..60. |
| **`Psg_SetVolume` `Snd_ChanClass` collapse** (the PSG twin of FM 7.6) | **REJECTED** | Exhaustive offline enumeration found **517,440 divergent cases out of 1,048,576**. The FM reorder is safe; the PSG one is not, and the reason is a real latent hazard — see the PSG vol-env clamp entry in `docs/DEFERRED_WORK.md`. |
| **plan item 7.7's transform** (`PatchOpGroup` invariant hoist) | **replaced** | Measures **EXACTLY ZERO** bytes — the Z80 has no `add a,(nn)`. Replaced with a different −10 B change in the same routine. |
| **−5 B `DacSampleTable` variant** (page-aligned `Snd_DacLookup`) | **replaced** | Its page-alignment premise is **FALSE**: seam-2 places `DacSampleTable` at `$85AD`, not on a page boundary. Took the −1 B shift form instead. |

### Factual corrections to this review

- **(a) The YM-spacing audit rested on a false premise.** It assumed every YM write funnels
  through `Fm_YmWrite`. **SEVEN of nine write sites BYPASS it** (Timer-A `$24`/`$25`/`$27`,
  `Snd_StartSample` `$28`/`$2B`, `SndDrv_Sample.stop` `$2B`/`$28`, `Sequencer_StopAll`
  `$28`) and were therefore effectively unaudited. All nine now carry structural
  `ensure(cycles(...))` guards on the address→data floor and all nine pass (`Fm_YmWrite`
  ×2 = 21 T each, matching the review's hand figure exactly; the direct sites 17-24 T). The
  data→next-address floor could **not** be expressed at any site — see the entry in
  `docs/DEFERRED_WORK.md`.
- **(b) The Tier-4 blob-evenness item was marked closed by a mechanism that never shipped.**
  "No build-time evenness assert on either Z80 blob (odd blob = boot address error)" carried
  a `[closed by D8 linker asserts — do not hand-fix]` marker; D8 was never built, and the
  first parcel to change the blob length by an odd number took the boot ADDRESS ERROR for
  real. Hand-fixed in `5526113` (`align 2` + evenness `ensure`). Full write-up in
  `docs/BUGS.md`. **Process lesson:** a `[closed by <pending mechanism>]` marker is not a
  closure — it is an open item wearing a closed label until the mechanism actually lands.

### Carry-forward correction for item 25 (the follow-on parcel)

The review calls sequencer H1's per-channel tempo gate "provably redundant." **It is not.**
`Seq_Op_Tempo` (`$F3`) broadcasts **mid-frame**, from inside channel N's tick, so channels
0..N run that frame's gate with the old modulus and N+1.. with the new — leaving a
**permanent accumulator phase offset**. Hoisting to a global accumulator is *more* S3K-exact
but IS a chip-stream change on that frame. It is dormant only because no shipped song
contains a tempo event. Its advertised "**−2 B/channel RAM**" is also **not collectable**:
`sc_tempo_mod`/`sc_tempo_accum` live in the SeqChannel↔SfxChannel shared prefix that the
`sx_pad+58 == sc_detune` invariant depends on. Do not re-plan item 25 on the original
premise.

## STATUS UPDATE (2026-08-04) — wave-4 items 25-30 EXECUTED (five landed whole, two halves blocked)

Overnight hardening run. Plan:
`docs/superpowers/plans/2026-08-04-hardening-overnight-run.md`. Six sequential
parcels, one branch each, each merged to master only when verified. A/B evidence
per parcel in `docs/superpowers/notes/2026-08-04-item*.md`. Frozen as provenance
chain entries 34-38.

| item | parcel | outcome |
|---|---|---|
| 26 | `item26-game-shell` | MERGED — chain 34 |
| 25 | `item25-sequencer-reclaim` | MERGED (scoped subset) — chain 35 |
| 29 | `item29-build-hygiene` | MERGED (parts 1-3; part 4 BLOCKED) — chain 36 |
| 30 | `item30-ram-constants` | MERGED (byte-neutral, no chain entry) |
| 27 | `item27-boot-hardening` | MERGED (ruling-4 subset) — chain 37 |
| 28 | `item28-bg-guard` | MERGED (safe half; posture STOPPED) — chain 38 |

**The single biggest find was not in the review:** the deb2 symbol table was
shipping in RELEASE ROMs — 29,198 bytes, **7.1% of `s4.bin`**, and 21 KB of
`demo.bin`. The review's anchor for it (`build.sh:130-134`, convsym) was stale
(build.sh no longer calls convsym; sigil absorbed it and ran it unconditionally),
and a first pass nearly cleared it as already-fixed by grepping the ROM for ASCII
`deb2` when the appendix magic is the **binary word `$DE $B2`**.

The other headline: **`BG_Init` could spray 128 KB across all of VRAM.** A
length-1 tile blob gave `lsr` -> `$0000`, `subq` -> `$FFFF`, and `dbf` then wrote
65,536 words through the SAT, both planes and the HScroll table.

### Corrections to this review, found by executing it

- **Item 26's High finding had the wrong mechanism.** "Fix engine-side (stopZ80
  inside `Section_RedrawPlanes`)" would starve the DAC for ~3 frames. HEAD
  already used the correct posture under sound (the `SND_CTRL_DMA_ACTIVE` flag
  bracket). The real defects were a caller-side stop_z80 acting as a FALSE LOCK
  (the routine's own internal `start_z80` released it on the way in — stop/start
  is not a counting lock) and a sound-OFF shape with no Z80 management at all.
- **Item 26's `Camera_Init` clamp and direct `$8B` write were already closed** or
  superseded at HEAD.
- **Item 27's vector premise never existed.** It described a shape split
  (`NullInterrupt` in release, `ErrorExcept` under `__DEBUG__`) that was never
  implemented — `vectors.emp` has no `if DEBUG` at all. The real inconsistency
  was WITHIN the table.
- **Item 27's cross-reset RAM finding is void** — `grep -r CROSS_RESET` over
  `engine/` and `games/` returns nothing. It described the pre-`.emp` tree.
- **Item 28's prescribed one-line guard fix would have introduced a second bug** —
  placed after the `lsr`, the skip target sits past the matching `start_z80`, so
  a taken guard branch strands the Z80 bus for the rest of the level.
- **Item 28's `load_art` clobber claim is stale** — d7 IS clobbered now. The real
  defect was d5: declared, written by nothing.
- **Item 30 was largely already closed** by a 2026-07-22 sigil pass
  (`Spawn_Count`, `MAX_SPAWNS_PER_FRAME`, and most of the dead-defs list).
  `PHYS_ROLL_FRICTION` is under a standing ratified DO-NOT-DELETE ruling despite
  zero readers.
- **Item 29's `RaiseError`/`Console` leak is not a leak** — both are AS macros
  with zero call sites, inert in a residual that emits no bytes in release.

**The `[closed by <pending mechanism>]` pattern claimed another one:** item 29
carried `[closed by D10 flag algebra — do not hand-fix the flag-gating half]`.
D10 never shipped, and the release leaks were entirely open. That is the second
time a pending-mechanism marker has hidden live work (after the D8 blob-evenness
marker, which took a boot ADDRESS ERROR for real on 2026-08-03).

### UPDATE (2026-08-05): the two blocked halves were RULED and EXECUTED overnight

Both received owner rulings on 2026-08-04 and landed as parcels 7-8 (provenance
chain entries 39-40):

- **Item 29 part 4** — `parcel/item29-mddbg-strip` (chain 39): error_handler is
  DEBUG-only; release faults route to the 46 B `ReleaseFault` (mask, display
  off, red backdrop, freeze). Release ROMs −4,226 B. The oracle induced-fault
  test caught the ruled handler being invisibly quiet (planes cover the
  backdrop) — the display-off write was added because of it. Same probe on
  debug lands in the full MDDBG screen.
- **Item 28's fork** — `parcel/item28-bg-transpose` (chain 40): BG layout
  column-major (pure permutation, 4,096/4,096 cells exact), Draw_BG_TileColumn
  sequential move.l, per-column autoinc-$80 blits, Tier-1 move.l tile blit with
  a re-derived guard. NO DMA; load_art untouched. Framebuffers byte-identical
  over 900 frames incl. max diagonal; zero scroll-lag frames both sides.

With these, **every item of the 2026-07-16 review is closed.** The dropped
sub-items (25's H1/H2/M3) remain deliberate rejections with recorded reasons.

### The pre-ruling BLOCKED write-ups (historical, superseded above)

- **Item 29 part 4 — the release-shape error-handler / MDDBG strip.** 4,272 bytes
  ship in BOTH shapes, `demo` included. Ruling 1 ("strip the exception stubs")
  is in tension with ruling 2 ("halt loudly in BOTH shapes"), and the code cannot
  answer what a release build should do on a bus error (`rte` is actively wrong
  for the fault classes — it re-executes the faulting instruction). Costs beyond
  placement: 60 dangling `dc.l` cells, four ungated `debugger.asm` equs that
  resolve into the module, large pin/golden churn including Config-B.
- **Item 28 — the blit posture and the BG column-major transpose.** A coupled
  three-way fork (bg posture <-> load_art direct-DMA <-> transpose) the review
  itself says three times must be decided together.
- **Item 25 H1** (global tempo accumulator) and **H2** (page-aligned opcode
  dispatch) were dropped with reasons; **M3** was dropped because wave-4 already
  took DEBUG headroom 86 -> 316 B, inverting its bytes-for-cycles trade.

## REMAINING FUNCTIONAL BUGS (2026-07-17 audit)

Definitive cross-reference of this review's correctness roll-up against the two merged fix
batches (sprites PB1/PB2 + wave-2 B1/C1/D1/E1/P1a/P1b/H-1). Everything below is a genuine
functional/behavioral defect (runtime- or hardware-visible, incl. latent) that the two
batches did NOT address. "Why out of scope" = why it wasn't in those two batches. Severity:
High = reachable corruption/crash/gameplay-break; Med = visible glitch or reachable-but-rare
corruption; Low = latent (condition not hit today) or hygiene. Cited lines are as-of the
review; re-derive against current HEAD before fixing.

### ⚠️ RECONCILED AGAINST HEAD (2026-08-05) — READ THIS BEFORE THE TABLES

Every row below was re-derived line-by-line against the code at HEAD by the
`parcel/backlog-reconcile` verification pass. **The tables as originally written are badly
stale: they present 19 rows (3 Tier-1 + 16 Tier-2) with zero FIXED markers, and only 3 are
genuinely open.**

- **16 of 19 closed.** 15 were fixed by later parcels (each row now carries the fixing
  commit); 1 (`vblank` #3) was never a reachable defect and is reclassified.
- **3 open** — `children` C1b, C1c, C1d. All three are conditional: none is reachable in a
  shipped code path today. One of them (C1c) is a **documented deliberate refusal awaiting a
  design ruling**, not an unfixed oversight.
  **→ ALL THREE CLOSED 2026-08-05** by `parcel/defect-batch-8` (C1b cascade-in-DeleteObject,
  C1c clear-then-set inheritance per the owner ruling, C1d splice) — see the row verdicts.
- **Six rows were real but MIS-DESCRIBED.** The mechanism corrections are listed below the
  open table, because in every one of those cases the mechanism matters more than the label —
  two of them prescribed fixes that would have introduced new defects.

The original row text is preserved verbatim in the tables (it is the historical record); a
**Verdict** column carries the current disposition. Rows are otherwise in their original
order — read the STILL OPEN table first.

#### ~~⚠️ STILL OPEN (3 — all `children`, all conditional)~~ — ALL THREE FIXED 2026-08-05 (`parcel/defect-batch-8`; table kept as the mechanism record)

| Row | Why it is still open | What holds it shut today | What it needs |
|---|---|---|---|
| `children` C1b — stale `parent_ptr` on parent-slot recycle | **Latent, no mechanism.** No generation/epoch anywhere: `Sst` carries a bare `parent_ptr: u16 @ $26` (`sst.emp:59`). `DeleteObject` zeroes only the freed slot (`core.emp:297-307`) and never walks `sibling_ptr`. `Draw_Sprite` dereferences the raw word with **no liveness check** (`sprites.emp:60-63`). | **Caller discipline only** — `entity_window.emp:1538` calls `DeleteChildren` before `DeleteObject` at :1544 (the BUG-004 cascade fix). Nothing structural prevents a future caller from skipping it. | A generation/epoch tag on the slot, or a parent-side chain walk in `DeleteObject`. Design work, not a drive-by. |
| `children` C1c — children never inherit a priority band | **Deliberate documented refusal, NOT an oversight.** `CHILD_INHERITED_FLAGS = (1 << RF_COORDMODE)` (`children.emp:62`) is applied with `or.b`, and a band is a 3-bit VALUE in bits 5-7 — so inheriting it via `or` UNIONS the bands (band-5 parent + band-6 child → band 7), which is strictly worse than the band-0 default. Rationale documented at `children.emp:52-61`, restated :188-196. | The refusal itself: band 0 is a correct-if-suboptimal default, the union would not be. | **An owner design ruling, not a code fix.** A real fix needs a clear-then-set child-side idiom, i.e. a game-wide convention change (every `ori.b #N<<RF_PRIORITY_SHIFT` site). |
| `children` C1d — `CreateChild_Linked` orphans a pre-existing chain | **Open in release, DEBUG-asserted, ZERO call sites.** The head overwrite is real (`children.emp:504-505` writes the new head with no read or free of the old one — contrast the three prepend creators at :147, :262, :344). DEBUG rails at :437-438 and :444-446 catch it. | Severity zero today: the proc is `@scaffolding` and nothing calls it. | Free-or-splice the old head before the overwrite, at the same time as anyone makes the proc live. |

#### Mechanism corrections — the row was REAL but the description was WRONG

These six matter more than their FIXED/OPEN labels, because two of them prescribed fixes
that would have shipped new defects and two inverted the direction of the finding.

1. **`parallax` B2 — the mismatch window is ONE FRAME, not "≤16 frames."** The row's
   "≤16 frames mode/length mismatch" is wrong by an order of magnitude: after `7482ebf`
   there is a single selector (`Parallax_Active_Config`, `parallax.emp:251-259`), and the
   shell stages at `ojz_scroll_test.emp:288` and rebuilds at :306 — a one-frame residual,
   not a whole transition's worth.
2. **`parallax` B3 — the "convergence comment is wrong" half is INVERTED.** The lerp
   defect was real and is fixed (`f4d6aea`: horizontal lerp is now exact, `divs.w` by
   frames-remaining, `parallax.emp:500-506`). But the `>>4` shift **legitimately survives**
   for BG VERTICAL scroll (:677-682), terminated by `.v_snap` (:675-686) — it is not a
   leftover — and the convergence comment at `engine/system/constants.emp:405-414` is now
   **CORRECT**. Do not "fix" either.
3. **`player` G9 — the review UNDERSTATED it.** The row says "0 today only because d7=0",
   i.e. dormant. Entry `d7` was in fact observed as **1**, so the word-width consumption
   was **live**, not latent. Also: the §2.5b sweep it was deferred to did NOT land as a
   one-off audit — it landed as a **permanent lint**, `tools/s4lint.py` W026 with taint
   tracking (:471-475, :1639-1691, `6677e21`). Fix itself: `moveq #0,d7` before the byte
   load, `player_ground.emp:665-669` (`c49e5b8`).
4. **game-shell `Section_RedrawPlanes` — THE PRESCRIBED FIX WAS WRONG.** The row says
   "engine-side fix (stopZ80 inside RedrawPlanes)". That would **starve the DAC for ~3
   frames** — the storm is a ~3-frame direct-VDP poke run. The real defects were different:
   (a) a caller-side `stop_z80` acting as a **FALSE LOCK** (the routine's own internal
   release frees it on the way in — a bus request is not a counting lock, so the caller ran
   the rest of the storm believing it held a bus it did not), and (b) a sound-OFF shape with
   no Z80 management at all. Fixed in `7660d1f`: sound-ON raises/lowers `SND_DMA_ACTIVE_SLOT`
   inside its own `$2700` mask (`section.emp:228-233`, :432-433) so the Z80 keeps running on
   its DRAIN path; sound-OFF uses `with z80_stopped if SOUND_DRIVER_ENABLED == 0` (:233). The
   header now states the posture as a contract: "**THIS ROUTINE OWNS IT; DO NOT WRAP THE
   CALL**" (`section.emp:187-201`).
5. **`vblank` #3 — the OBSERVATION is true but the CONSEQUENCE is unreachable.** `DMAEntry`
   really has no `$0F` byte, and neither `Process_DMA_Critical` nor `dma_send_entry` writes
   `$8Fxx`. But `VInt_DrawLevel` runs one call earlier in the same VBlank
   (`vblank.emp:109` → :139) and **unconditionally** exits `$8F02` (`plane_buffer.emp:481`),
   including on the empty-buffer path (a5 is set up before the `beq .done` at :428-429).
   Every other `$8F80` writer restores inside `$2700`. This is an **ambient-invariant note,
   not a corruption bug** — reclassified, not fixed. (Hardened by F-4 in `822c79a`. But see
   NEW finding 1 below: the invariant is unasserted, and `VInt_Lag` depends on it.)
6. **game-shell sprite cull — the reordering half was deliberately REJECTED.** Reordering
   `RunObjects` after `Camera_Update` is gameplay-timing-visible and was ruled out; the
   margin arm shipped instead (`7660d1f`): `SPRITE_CULL_MARGIN = 32`
   (`engine/system/constants.emp:493`, rationale :484-492), applied on all four sides in
   `sprites.emp:96,101,110,115`. The row should not be read as an outstanding ordering
   decision.

### Tier 1 — silent-drop class (`fix/silent-drop-class` parcel, being fixed now) — **ALL THREE FIXED**

| Site | Class | Sev | Why out of the two batches | **Verdict (2026-08-05)** |
|---|---|---|---|---|
| `buffers.asm` Enqueue_Dirty_Buffers (Palette_Dirty clear) | enqueue-result-ignored, state cleared | High | buffers untouched by either batch; the `queueStaticDMA` macro silently no-ops on full and the caller clears the dirty bits unconditionally → stale palette persists through a fade (reachable: fade + heavy Critical art staging both fill Critical) | **FIXED** `bd91b48`, `.emp` port `c45e525`. `queue_static_dma` is a comptime template that now emits `ori.b #1,ccr` on the drop arm (`buffers.emp:59`) and `andi.b #$FE,ccr` on success (:56); all four callers `bcs` **over** the `bclr` (:217-219, :223-225, :229-231, :235-237), so a full queue leaves the dirty bit armed for retry. |
| `buffers.asm` Enqueue_Dirty_Buffers (Sprite_Table_Dirty clear) | same shape | High | identical pattern one routine down; Fable-verified same class → stale SAT persists | **FIXED** `bd91b48`. Same file :240-252 — `.no_spr` sits past the `clr.b`, so a drop retains the flag. (Introduced a documented residual — see NEW finding 3.) |
| `load_art.asm:79` (QueueDMA_Critical carry ignored) | enqueue-result-ignored, state assumed | Med | review names it "same silent-drop class as the buffers bug"; runs display-off at init (extended VBlank drains each VSync → queue-full unlikely) but on a full Critical queue a page's art DMA is dropped and never retried → permanently wrong tile page for the act | **FIXED** `c1449b9`, `.emp` `8f4615d`. `load_art.emp:128-129` `bcs .drop_page`; the handler at :148-154 raises under DEBUG and, in release, does `VSync_Wait` + retries the SAME page. |

### Tier 2 — other functional bugs (runtime/hardware-visible; each needs its own fix or ruling)

**Verdict roll-up: 12 FIXED · 1 never existed as a reachable defect · 3 OPEN (tabled above).**

| Site | Class | Sev | Why out of the two batches | **Verdict (2026-08-05)** |
|---|---|---|---|---|
| `vblank` #3 — Critical DMA entries never set autoinc ($8F); drain inherits stride from prior frame | corruption (stride) | Med | bundled with vblank H1/H2 perf reorder (the `$8F02` write goes at the Critical drain head) → deferred to the perf phase, not a wave-2 correctness item | **NEVER EXISTED as a reachable defect** — observation true, consequence unreachable (`VInt_DrawLevel` exits `$8F02` unconditionally one call earlier). Reclassified as an ambient-invariant note; see correction 5 and NEW finding 1. |
| `vblank` H1 — Critical DMA bytes + CPU plane-copy uncharged by frame budget; worst case ~1.7× the ~18.5k window | timing/overrun | Med | budget-accounting restructure → perf phase | **FIXED** `6fab3eb`. Budget seeded at `vblank.emp:96`; CPU plane copy charged :107-108; Critical DMA charged by `.charge_critical` :116-129; floored :134-137; `Drain_Budgeted_Queue` honours it (`bmi .out_of_budget`, `dma_queue.emp:340-343`). |
| `parallax` B1 — re-crossing current config's section mid-transition doesn't cancel the staged transition | wrong-config persists | Med | needs a transition-logic design pass, not a drive-by (excluded by design from wave-2) | **FIXED** `1fc0897`. `parallax.emp:171-174` `cmpa.l Parallax_Current_Config,a0 / beq .recross_current`; `.recross_current` (:217-229) zeroes target + frames and sets snap-pending. |
| `parallax` B2 — builder/DMA-length/VSRAM-mode consumers disagree on "active" config mid-transition (≤16 frames mode/length mismatch); overlaps the game-shell direct-`$8B`-write §3.4 tear | visual tear | Med | same design pass | **FIXED** `7482ebf` — single selector `Parallax_Active_Config` (:251-259). **Description corrected: the residual window is ONE FRAME, not ≤16** (correction 1). |
| `parallax` B3 — 16-frame `>>4` lerp ends ~36% short of target → end-of-transition pop | visual pop | Med | same design pass (+ constants.asm:319 convergence comment is wrong) | **FIXED** `f4d6aea` — horizontal lerp exact (`divs.w` by frames-remaining, :500-506). **The parenthetical is INVERTED: the `>>4` legitimately survives for BG vertical (:677-682, snapped at :675-686) and the convergence comment is now CORRECT** (`constants.emp:405-414`) — see correction 2. |
| `children` C1a — effect spawned by an RF_MULTISPRITE parent is NEVER rendered | rendering | Med | bundled with children M1 spawn-flag rework (rendering-model change), not wave-2 | **FIXED** `559b6ce`. `CreateEffect_Normal` no longer writes `parent_ptr` (`children.emp:604-613`); the multisprite skip is now driven only by the spawned object's own pointer (`sprites.emp:60-64`). |
| `children` C1b — stale parent_ptr on parent-slot recycle can silently hide children | rendering | Med | same bundle | **FIXED 2026-08-05** (`defect-batch-8`). The cascade is DeleteObject's own mechanism now (front-guards + DeleteChildren; caller-side cascades deleted). Chosen over an epoch byte: SST is fully packed (growth = +132 B RAM + replay re-cut), the epoch charges the Draw_Sprite hot path, and the walk is provably complete (every parent_ptr writer chain-links). Also subsumes NEW finding 2. |
| `children` C1c — children never inherit a priority band (always band 0 = backmost) | rendering | Med | same bundle | **FIXED 2026-08-05** (`defect-batch-8`, per the owner ruling): CHILD_INHERITED_FLAGS gains RF_PRIORITY_MASK and the child-side idiom becomes the `set_priority_band` clear-then-set template (sst.emp) — one edit in test_obj_prolog + five direct-site swaps. |
| `children` C1d — CreateChild_Linked orphans a pre-existing chain | dynamic-slot leak | Med | same bundle | **FIXED 2026-08-05** (`defect-batch-8`): the old head is parked in d5's high word and both exits splice it onto the appended run's tail; the childless-parent constraint + assert dissolve. Also fixes the partial-run orphan the constraint never covered. |
| `player` G10 — move_lock never ticks while standing on a solid object → frozen input forever (only jump escapes) | gameplay | Med | not in either batch; needs fix + solid-object-landing test | **FIXED** `a8e2b5b` (merged `ec8a1cc`, emulator-confirmed `7d3dd18`). `player_ground.emp:199-201` ticks the lock on the `ST_ON_OBJECT` exit. Repro recipe in `docs/BUGS.md`. |
| `player` G9 — Ground_Move:620 byte-loads probe into d7, consumed at WORD width (high byte = caller residue; 0 today only because d7=0) | latent §2.5b | Low | latent; same class as shipped Sound_PlaySFX; deferred to the §2.5b sweep / diagnostics tier | **FIXED** `c49e5b8` (`moveq #0,d7`, `player_ground.emp:665-669`). **Row UNDERSTATED it — d7 was observed as 1, so this was LIVE, not latent; and the sweep landed as a permanent lint (`s4lint.py` W026), not a one-off.** See correction 3. |
| `player` A7 — landing always uncurls with no clearance check while the roll path guards the same wall-clip hazard | needs ruling | Med | design ruling (parity decision), not a drive-by | **FIXED** `0f8aead` — and the ruling exists: `docs/superpowers/plans/2026-08-02-bug005-sprites-player-parcel.md:15` ("A7: GUARD IT"). All landings funnel through `Air_LandState` (`player_air.emp:474`); the guard at :486-493 uses the identical threshold as the roll path (`player_ground.emp:473-475`). |
| `camera` P2 / game-shell — Camera_Init doesn't clamp; whole OJZ init ladder seeds from the unclamped value → one negative-camera frame into cache at edge starts | init glitch | Med | P1b only guarded the mega-act WORD-WIDTH ceiling, NOT the init clamp; game-shell ordering decision | **FIXED** `a79256f` (merged `ec8a1cc`). `Camera_Init` now ends with `clamp_camera_axis` on both axes. |
| game-shell — Section_RedrawPlanes Z80-safety asymmetry: per-frame path (via runtime Section_Plane_Dirty cache recovery) does direct VDP writes with the Z80 live | hardware bus / crash risk | High | engine-side fix (stopZ80 inside RedrawPlanes); game-shell ordering batch | **FIXED** `7660d1f` — **but the prescribed fix in this row was WRONG and must not be re-attempted** ("stopZ80 inside RedrawPlanes" starves the DAC ~3 frames). See correction 4 for the real defects and the shipped posture. |
| game-shell — sprite culling uses LAST frame's camera (RunObjects before Camera_Update; zero cull margin, 16px/frame) | edge pop-in | Med | needs ordering-or-margin decision; game-shell ordering batch | **FIXED** `7660d1f` via the margin arm; **the reordering arm was deliberately REJECTED** as gameplay-timing-visible. `SPRITE_CULL_MARGIN = 32` (`constants.emp:493`, rationale :484-492), four sides (`sprites.emp:96,101,110,115`). See correction 6. |
| `bg.asm` — a length-1 tile blob sprays 64K words across all of VRAM past the existing guard | corruption (malformed data) | Med | bg blit-posture batch | **FIXED** — safe half `f6458a0`, re-derived for the `move.l` blit in `7b6f55b`. `bg.emp:122-124` takes the longword count FIRST (`lsr.w #2` / `beq .skip_tiles` / `subq.w #1`), so lengths 1-3 fold to 0 before the `subq` underflow; both counter ops sit ABOVE the `with z80_stopped` bracket deliberately (:114-121), because `.skip_tiles` is past the bracket's release. (Left a ledgered gap — see NEW finding 4.) |

### NEW (2026-08-05 reconciliation) — five defects in these areas that are in NO register

Found by the verification pass, **not** by the original review, and not tracked anywhere else
(not in this table, not in `docs/BUGS.md`, not in `DEFERRED_WORK.md`). Listed here because
they live in exactly the code the rows above cover.

1. **FIXED 2026-08-05** (`defect-batch-8`): VInt_Lag re-asserts `$8F02` at its Critical
   drain head — the declared-contexts close was evaluated and rejected (values out of scope
   by spec §9; IRQ is not a CFG edge), ledgered in DEFERRED_WORK. Original finding:
   **`VInt_Lag`'s Critical drain rests on an UNASSERTED ambient invariant.** `vblank.emp:206-225`
   deliberately skips `VInt_DrawLevel` on a lag frame (draining a torn `Plane_Buffer` is worse),
   so on a lag frame **nothing re-asserts reg `$0F=$02` in-frame** before `Process_DMA_Critical`.
   It is correct today only because every `$8F80` writer restores before yielding. No build-time
   check and no runtime guard enforces that. A future `$8F80` writer that returns without
   restoring breaks Critical DMA **on lag frames only** — a nearly untestable failure mode. This
   is the live residue of the reclassified `vblank` #3 row: the observation was right, it just
   points at an invariant rather than at a bug. Cheapest close: a `$8F02` write at the Critical
   drain head, or an assert on the shadow.
2. **FIXED 2026-08-05** (`defect-batch-8`): subsumed by the C1b cascade — DeleteObject
   itself frees a dying parent's chain, so this site needs no change. Original finding:
   **`animate.emp:201-202` (`.cc_delete: jbra DeleteObject`) orphans a parent's child chain.**
   An anim-script `AF_DELETE` on a parent bypasses `DeleteChildren` entirely — the **same
   permanent Dynamic-pool leak as C1d and BUG-004**, arriving from a path nobody flagged. No
   shipped parent object uses `AF_DELETE` today, and nothing prevents one from doing so. Same
   root shape as C1b: the safety is caller discipline, not mechanism.
3. **FIXED 2026-08-05** (`defect-batch-8`): `Sprite_Emit_Active` bracket (consumes the
   RAM pad) — the enqueue skips the sprite ship while Render_Sprites is mid-emit, keeping
   the drop-retry and the hidden-terminator edge ship. Original finding:
   **`buffers.emp:244-251` — a torn-ship residual INTRODUCED by the Tier-1 fix itself**
   (self-documented at the site). Retaining `Sprite_Table_Dirty` on a drop is correct for
   retry, but if IRQ6 then lands mid-`Render_Sprites` on a lag frame, the PREVIOUS length
   ships against a mid-emit buffer; post-H3 the short-length variant can also reference
   un-shipped entries for one frame. Pre-existing class, newly reachable — ledgered in code,
   registered nowhere.
4. **FIXED 2026-08-05** (`defect-batch-8`) — and the ledger text below was WRONG-BY-OMISSION:
   the credited assert lives in `inject_editor_bg.py`, which runs only when an editor override
   exists; the UNCONDITIONAL producer `ojz_strip_gen.py` had no assert. It does now. Original:
   **`BG_Init` silently drops a sub-longword tail.** `bg.emp:109-121` — for lengths ≥4 it
   copies `floor(len/4)` longwords and drops the remaining 1-3 bytes with **no assert**. The
   assert was omitted deliberately: the DEBUG expansion would push `.skip_tiles` past
   short-branch reach and force shape-dependent width pins. Real blobs are 32-byte granular
   (`inject_editor_bg.py` asserts `len%4==0`), so it never fires in practice. **Ledgered, not
   guarded** — a build-tool-side assert is the free close.
5. **FIXED 2026-08-05** (`defect-batch-8`): both maintainers widened to 64 rows. Two premise
   corrections mattered: `Draw_BG_TileColumn` has ZERO callers (cost of widening = 0 steady-state),
   and "the injector zero-pads rows 32-63" is FALSE for shipped content — the OJZ override
   carries real art there, and the shipped full-plane vscroll wrap puts those rows on screen,
   which is why declare-32-the-limit was rejected. Original finding:
   **BG nametable rows 32-63 are INIT-ONLY.** `bg.emp:27-41` — `BG_Init` is the only writer
   that fills all 64 rows. `Section_RedrawPlanes` (`section.emp:414-419`) and
   `Draw_BG_TileColumn` (`plane_buffer.emp`, 32-word strips, header `$8000|31`) both top out
   at 32. So any BG art using the advertised 512px vertical headroom **silently half-reverts**
   the moment a per-section redraw or a streamed column runs — invisible today only because
   the injector zero-pads rows 32-63 to blank. The 512px headroom is documented as live in the
   shape but is not. Any BG work that reaches for it must widen both runtime maintainers FIRST.

### Tier 3 — Z80 sound cluster (real, but oracle-invisible; deferred to the sound bug-fix batch + rendered-audio A/B)

> **FIXED 2026-08-03** by `parcel/wave4-z80-sound-reclaim` (item 23) — every row below
> EXCEPT **sound_api PB-2** (the non-MUSIC mailbox slots; 68k-side, out of that parcel's
> scope) and **driver B2**, which was DROPPED as already-closed (see the STATUS UPDATE
> above). Three defects not listed here were folded in as extras: sequencer B1, FM bug 11,
> PSG M5. Per-defect mechanism/reachability/fix write-ups: `docs/BUGS.md`.

| Site | Class | Sev | Note |
|---|---|---|---|
| driver B1 — SfxChannels+duck bytes are power-on garbage until first Snd_LoadSong; Sfx_Frame walks garbage (possible wild chip/bank writes) | uninit state | High | net-zero fix (init → `call Sfx_StopAll`); emulators zero RAM so oracle can NEVER show it |
| SFX B1 — Sfx_DuckRamp resurrects a stopped song's PSG channels (no SND_SEQ_ACTIVE gate) → drone until next song | stale key-on | Med | +5-byte gate |
| PSG #1 — Psg_ApplyMod exact-zero divisor passes to the chip (contradicts its own comment; reachable, top 13 pitch entries divisor 1) | zero-divisor | Med | +5-byte clamp |
| Sequencer B1 — PSG portamento down-glide 16-bit underflow evades the overshoot snap | glide underflow | Med | sound batch |
| Sequencer B2 — vol-env body starting `$80` (Loop) wedges the driver inside the Timer-A tick | driver wedge | Med | zero-byte fix = generator build-time assert |
| sound_api PB-2 — ping/fade/tempo/sample mailbox slots share the read→handle→clear latest-wins-violated shape | lost/torn request | Med | H-1 fixed the MUSIC slot ONLY; the other slots still need the same gate |
| SFX — queue arbitration compares RAW priority (bit7 would add +128 weight) | latent drift | Low | 2-byte fix |
| Fm_PatchLoad clobbers sc_pan on mid-song patch change | latent | Low | verify sequencer-side |

### Tier 4 — boot / hardware-risk (functional on real hardware; oracle can't verify — separate boot-hardening batch)

- PSG silence writes race the in-flight VRAM DMA fill (~2× implicit margin, no enforcement) — free reorder fix.
- YM key-off block: no busy-wait + address-latch race vs the already-running Z80 driver.
- z80_init leaves SP=0 (future push lands in the 68k bank window); EntryPoint doesn't reload SP (jmp-reset unsupported); spurious-interrupt vector policy inconsistent (crash in release); `ld bc` operand parse trap.
- No build-time evenness assert on either Z80 blob (odd blob = boot address error). ~~**[closed by D8 linker asserts — blob alignment becomes a link-time invariant; do not hand-fix]**~~ **MARKER WAS WRONG — D8 never shipped, and this fired for real on 2026-08-03 (boot ADDRESS ERROR as soon as the reclaim made the blob odd). HAND-FIXED in `5526113`: `align 2` inside the `Z80_Sound_Start`/`_End` brackets + `ensure((Z80_SOUND_SIZE & 1) == 0)`. See `docs/BUGS.md`.**

### Tier 5 — latent guards / data-width (condition not reached today; add asserts or width fixes)

> **⏳ pending-mechanism markers:** items tagged `[closed by <D-check>]` will be made
> impossible STRUCTURALLY by a pending diagnostics-tier mechanism — do NOT hand-fix these in
> a future parcel; they are waiting customers for that mechanism, not standalone work.

- `section` B1 (RedrawPlanes right-edge tracker unclamped), B3 (hardcoded `lsl.w #8` no guard).
- `math` B1 — Sine_Table declared `[u8]` but word-read; evenness accidental → latent address-error. **[closed by D8 typed data tables — a word-read of a `[u8]` table is a type error; do not hand-fix]**
- `aabb` #3/#4 — missing `ensure(cdim != delt)` + read-only `apos` guards (same miscompile class as the two shipped `stmp` ensures).
- `objdef` O1 — `vram_art` tile refine `0..$1FFF` permits flip-bit bleed ($800..$1FFF).
- `frames` F1 / `dplc` D5 — offset-table words sign-extend; mappings/DPLC ≥32KB index backwards (build-tool fatal check).
- `bg_anim` — no `band_count ≤ 4` guard (malformed table corrupts RAM past BgAnim_LastStep).
- `macros` sprSize (PB3) — w/h swap confirmed at `macros.asm:21` AND CODING_CONVENTIONS.md:25; latent (sprites.emp hand-codes correct constants) until the first non-square `sprSize` use — fix both places together.

### Tier 6 — build/release hygiene + test-template scaffolding (not gameplay; separate batches)

- Release leaks: convsym appends the full symbol table to release ROMs (unconditional); `SOUND_DEBUG_HOTKEYS=1` without `DEBUG=1` builds hotkeys+autoplay into release; MDDBG blob + exception stubs ship in release; RaiseError/Console not DEBUG-gated. **[closed by D10 flag algebra — DEBUG-implication/exclusion becomes a checked build-flag relation; do not hand-fix the flag-gating half]**
- Template/test bugs: AnimateSprite called with uncontrolled d3 under DUR_DYNAMIC (anim rate = register garbage); test_parent self-destruct never fires (parent immortal); "idle" is actually ANIM_RUN; magic art_tile `$A0FA` aliases the level art pool; path_swap single-player hardwired.

### Excluded (NOT counted as functional bugs here)

- **Contract-header / clobber understatements** — collision #11 (d5), lookup #8 (d3), rings (d0), core #11 (d7 RunObjects/RunObjects_Frozen), animate Sound_PlaySFX re-verify, s4lz preservation contract undocumented, bg_anim header a3-a4. These document the contract surface; they become *errors* only once the contract-grammar D1a net lands, and are not live misbehavior today. Tracked by the diagnostics tier, not this table.
- **Pure comment/doc mismatches and dead code** (Hscroll_Dirty dead range, cost-comment errors, dead constants, orphaned RAM, ARCH doc figure drifts) — tracked in the per-file sections.
- **Minor state-hygiene / DEBUG-only** — core #12 (AllocDynamic rollback leaves a stamped slot_tag byte), core #14 (`bne` where `blo` fails-closed), entity_window #3 (Collected_ClaimSlot failure silently ignored — wants a DEBUG assert), tile_cache #1 (spurious frame-1 lag flag).

---

**Z80 apply-rules (wave 4):** Z80 resident headroom is ~86 bytes DEBUG — SIZE reductions
are wins in themselves and code-growing changes are near-forbidden. The DAC stream loop's
195-cycle balance is correctness (pitch), not perf — any change there must re-prove the
balance and A/B the $2A cadence. All audible-behavior changes need rendered-audio A/B
(VGM → wav, energy+spectrum vs mt_ref.vgm / S3K refs), never register streams; SFX testing
needs SOUND_DEBUG_HOTKEYS=1 builds (and byte-verify ROM vs .lst — the daemon plain-rebuilds
mid-session). **Combined size ledger from the four sound reviews: roughly −180 to −230
bytes of resident Z80 code reclaimable with behavior-identical refactors** (driver core
−45..50 net incl. the +8 race fix, SFX −80..110, FM/PSG −55..70) — i.e. the ~86-byte
headroom can be roughly tripled.

**THE #1 ITEM OVERALL (wave 3, parallax H1):** the production OJZ config pays the full
per-line BG sampling loop on a table of zeros — ~21,000 cycles/frame computing `base + 0`,
because `ojz_default.asm` uses `DeformTable_Zero` to force per-line mode but the `band`
macro's `deformShiftDefault=4` prevents the flat-path shortcut. A ONE-LINE DATA CHANGE
(`deformShiftDefault=15`, mode selection keys only on table non-NULL so per-line mode is
retained) recovers an estimated **~16,000 cycles/frame ≈ 13% of the frame budget** at zero
visual change. See the parallax section for the verifier checklist.

**Mega-act ceiling cluster (flag for the floating-origin plan):** three independent
word-width ceilings were found that all break at large act sizes — `section.emp:232`
(`adda.w` flat×66 caps at ≤496 sections/act), `camera.asm:133-137/245-247` + `Camera_Init`
(clamp math wraps at grid_w ≥ 32 sections), `player_common.asm:641-659`
(`Player_LevelBound` word truncation, same threshold). None is guarded. Any mega-act work
hits all three; add build asserts now, fix properly in floating-origin Phase 4.

## Global constraints for whoever applies any of this

- **Twin lockstep:** every `.emp` file here is a byte-identical port of its `.asm` twin.
  Any change lands on BOTH sides together, and moves the shape-length byte gates. Check the
  tranche porting rules first.
- **Measure with the lag-frame counter** during max-speed diagonal scroll (the historical
  worst case). Producer-side costs eat the main-loop frame budget; VBlank-side costs eat the
  ~18,500-cycle NTSC VBlank window. Attribute wins to the right budget. A
  `Prof_TouchResponse` harness already exists at `games/sonic4/test/object_test_state.asm:109-116`.
- **Preserve the VInt_Lag race fix** (b96c861): terminator semantics and Plane_Buffer_Ptr
  reset ordering are load-bearing.
- Cycle numbers below are **estimates** — verify against real timings before claiming savings.

## Cross-file priority order (by expected value)

1. **tile_cache #1** — FillRow per-tile loop → precomputed contiguous segments.
   ~10–25k cycles per vertical-scroll frame (est.). The single biggest item; directly the
   historical lag path.
2. **tile_cache #2** — per-slot staging data pointer: empty blocks point at a shared zero
   ROM block (~5.8k/block), raw blocks point straight at ROM (~4.0k/block), up to 6/frame.
3. **plane_buffer #1/#4** — row-fill and column-fill segment restructures (same pattern as
   tile_cache #1); plus **#2/#3** drain-side wins (move.l column drain, producer-precomputed
   VDP command words).
4. **collision_lookup #1–3 fused rewrite** — span-check fusion + cached biases + ×80 row
   table: ~30% off every terrain sensor lookup (~600–2,000/frame). Plus **collision #1**
   fixed-sweep skip counter (~1.5–1.9k/frame).
5. **sprites H1 + H2** — cached frame offset in SST (~1.5–2k/frame) + emit-loop stream-order
   restructure with size+link word merge (~1–1.9k/frame in the hottest loop). **H3** patches
   the sprite-table DMA length to `Sprites_Rendered*8` (up to ~480 B of Critical VBlank DMA
   budget back).
6. **rings R2 + R3** — cull-side camera-bias fold (~2.5k/frame at full buffer) + hoisted
   player dims in RingCollision (~3k/frame). **animate A2+A3** — dirty-check + tail-call
   around RefreshSpritePieceCount (~60/expiry, big for static looped objects).
7. **entity_window High #1** — per-section next-entity-X trigger cache (reusing the two
   *dead* `ess_*_left_idx` fields), ~500–650/frame; **High #3/#4** despawn-loop invariant
   hoists (~1.3–2k/frame with many live entities).
8. **core #1** — register-cached camera + branchless window cull (~200–350/frame, scales
   with object count); **#2** O(1) delete backpointer (only if delete storms show on the
   lagometer).
9. **section H1/H2/H3** — idle early-out for `Section_UpdateColumns` (~500–600/frame on the
   majority of frames), delete the contract-contradicting `movem` pair (~180/frame, every
   frame incl. lag frames), build-time act boundary constant (~50/frame + kills a drift
   trap). **H4** — hoist the per-cell wrap compare out of the redraw loop (~57k cycles off
   the init/recovery stall).
10. **hblank H1** — replace the dispatch wrapper with a RAM `jmp` trampoline BEFORE any real
    raster handler is written: ~116 cycles/line of pure wrapper ≈ ~26k cycles/frame once
    per-line HInt is active (OJZ parallax end-state). Zero handlers exist yet — this is the
    cheap moment.
11. **aabb #1** — split the template into three composable comptime pieces (byte-neutral
    today); unblocks the rings pre-combined-dims variant (~24+ cycles/ring) and the
    collision coarse-reject variant as pure recompositions.
12. **dplc D1 + load_object L1** — both `movem` pairs save registers their callees
    contractually preserve (~575 cycles per Sonic frame change; ~76/spawn, matters in
    entity-window spawn storms). **dplc D3** — hoist the frame-unchanged check into callers
    (~65 cycles/frame/DPLC character).
13. **vdp_init M1** — `Flush_VDP_Shadow` is per-VBlank, NOT init-only: early-exit shift walk
    saves ~600 VBlank cycles on register-dirty frames.
14. **section M1** — build-time per-act row-pointer table for `GetSecPtrXY`/`FlatIDXY`
    (~50–200/frame, grows with mega-act grid heights). **M2** — drop the double
    caller/callee checks between section and plane_buffer producers (~100–250 on max-scroll
    frames; keep the CALLER's check — the tracker desyncs if the callee's is kept instead).
15. Everything filed Medium/Micro in the per-file sections, opportunistically.

Wave-3 additions (merged by expected value — parallax H1 above outranks everything):

16. **s4lz H1** — extended-run copy loops run at 11 cycles/byte vs 5.6 achievable with 4×
    move.l chunking (remainder via the EXISTING unroll table); offset-2 matches (word-RLE,
    flat tiles) become a 3-cycles/byte long-fill. ~4,000 cycles per near-incompressible
    block, up to ~24k/frame at 6 staged blocks. MUST stay within d0-d3/a2-a3 (see s4lz H2
    register freeze).
17. **vblank H1+H2** — unify the frame budget (Critical bytes + CPU plane-copy currently
    uncharged; worst case overruns the ~18.5k window ~1.7×) and reorder Critical DMA before
    the CPU plane drain (+ explicit $8F02 at Critical drain head, which also closes the
    lag-frame autoinc bug).
18. **player G1 + sensors H3** — jump-press frame probes the ceiling pair twice
    (~900–1,600/jump); `Player_AtLedgeEdge` probes the same point twice every grounded idle
    frame (~500–1,000/frame) — found independently by BOTH player reviewers. Plus the
    sensors review's caller-side map for engine lookup #4 (extensions are ~HALF of all cell
    evals; single swap point in `.cell`; a1 free to carry the pointer; ~600–1,500/frame).
19. **camera H1+H2 / player M3** — act-invariant bounds precomputed at init (~130/frame
    camera, ~120/frame LevelBound) + keep Camera_X/Y in registers through the update
    (~60–80/frame); same pattern as section H3.
20. **children M1 + C1** — six creators oversave around Alloc (44–116 cycles/child of pure
    waste; `_Linked`/`_Simple` need NOTHING saved); replace the per-frame parent_ptr deref
    in Draw_Sprite with a child-side flag set at spawn (~28 → ~10 cycles per child/effect
    per frame, and it fixes two rendering bug shapes).
21. **dma_queue H1 + buffers H1** — register-resident budget in the drain loop
    (~480/frame worst case) + a `Static_Pal_All` fast path for the all-lines-dirty fade
    case (~560/fade frame + frees 3 Critical slots).
22. **s4lz M1-M3, parallax H2/H3/M1-M5, bg_anim M1, spindash S1-S2** and the rest —
    opportunistically per the per-file sections.

Wave-4 additions (merged by expected value):

23. **[EXECUTED 2026-08-03 — `parcel/wave4-z80-sound-reclaim`; +28 B, three extra defects
    folded in, driver B2 dropped as already-closed. See the STATUS UPDATE section.]**
    **Sound bug-fix batch** (before any sound optimization): driver B1 boot-window fix
    (net-zero bytes), SFX B1 DuckRamp gate (+5 B), PSG zero-divisor clamp (+5 B),
    sequencer B2 env assert (0 Z80 bytes, generator-side), driver B2 PlayMusic snapshot
    (+8 B) — total ≈ +18 bytes, paid for many times over by:
24. **[EXECUTED 2026-08-03 — same parcel; MEASURED −231 B net, blob 6172→5941 plain /
    6298→6067 debug, DEBUG headroom 86→316 B. SFX S1 and S4 dropped, the `Fm_YmWrite` nop
    micro rejected. See the STATUS UPDATE section.]**
    **Z80 size-reclaim campaign** (−180..230 B behavior-identical): SFX S1-S6 (−80..110),
    FM/PSG dedups + ChanClass single-calls + WriteFreq rewrite (−55..70), driver H1-H4 +
    M1 (−50..60). Most are lst-diff-verifiable (chip-stream identical); H3 (nop→jr pads)
    is cadence-sensitive — recount + VGM A/B.
25. **Sequencer H1-H3** — global tempo accumulator (smaller + faster + more S3K-exact),
    page-aligned opcode dispatch (−30 T/op), Seq_ContinueFetch retarget (free).
    **CORRECTION (2026-08-03): H1's per-channel tempo gate is NOT "provably redundant" and
    its "−2 B/channel RAM" is not collectable — see the carry-forward correction in the
    STATUS UPDATE section before planning this. Tracked in `docs/DEFERRED_WORK.md`.**
26. **Game-shell ordering decisions** — sprite-cull camera skew (ordering or margin),
    kill the per-frame direct $8B write, clamp in Camera_Init, stopZ80 inside
    Section_RedrawPlanes.
27. **Boot hardening batch** — PSG-after-fill reorder, YM key-off before bus release,
    Z80 blob evenness asserts, cross-reset RAM decision, EntryPoint SP reload.
28. **bg.asm blits → move.l/DMA** (~2 frames off act load) + the **BG column-major
    transpose** (per-frame Draw_BG_TileColumn win; decide together with the blit posture);
    load_art carry check + optional direct-DMA posture (~1 frame/page of load time).
29. **Build hygiene** — gate convsym on DEBUG, make SOUND_DEBUG_HOTKEYS imply/require
    DEBUG, decide the MDDBG-in-release question, delete dead DEBUG_* flags + fix
    conventions §1.7, template fixes (d3/DUR_DYNAMIC, test_parent lifetime, ANIM ids).
30. **RAM/constants cleanup** — implement-or-delete Spawn_Count guard, add the
    CAM_MAX_Y_STEP build guard, computed pads, dead constants, act_descriptor
    SECTION_SIZE_SHIFT migration.

## Correctness findings surfaced by the review (not optimizations — triage these)

- **sprites PB1 (real bug):** `InitSpriteSystem` zeroes `Sprites_Rendered` every frame, so
  `Render_Sprites`' `.empty_table` had-sprites→none trigger is dead — the hidden terminator
  is never written and the previous frame's SAT persists in VRAM (**frozen ghost sprites**).
  Same in the `.asm` twin.
- **sprites PB2 (real bug):** scanline-budget band index is computed from *biased* Y
  (screenY+128) but treated as raw screen Y — bands shifted by +4, budget heuristic
  effectively non-functional over most of the screen. Comment stale post camera-bias fold.
- **sprites PB3:** `sprSize` w/h swap in `engine/macros.asm:21` **confirmed still present**
  (matches the standing stray-fixes memory). `sprites.emp` itself does NOT inherit it
  (hand-coded constants are correct); latent until the first non-square `sprSize` use.
- **entity_window bug #1:** `ess_ring_left_idx`/`ess_obj_left_idx` are dead state — cleared,
  never read/written anywhere (grep-verified). Delete or repurpose as the trigger cache.
- **entity_window bug #2:** mixed signed/unsigned X comparisons pin a silent world-X < $8000
  assumption — flag against the mega-act/floating-origin work.
- **entity_window bug #3:** `Collected_ClaimSlot` failure silently ignored at
  `BuildEntries:772` — wants a DEBUG assert on Z.
- **tile_cache bug #1:** first-fill lag-skip contradicts its own comment (spurious
  `Cache_Pfx_Lag_Flag` on frame 1 if init took frames). **#3:** `Tile_Cache_GetTile` has
  zero call sites (dead export). **#2:** no DEBUG guard on out-of-window hot lookups.
- **core #11:** `clobbers` on `RunObjects`/`RunObjects_Frozen` omit d7 (both write it).
  **#12:** `AllocDynamic` `.latch_full` rollback leaves a stamped `slot_tag` byte in a freed
  slot. **#14:** full-count check uses `bne` where `blo` fails closed.
- **collision #11:** `touch_test_target` header understates clobbers (d5 written on overlap
  path). **#13:** `Touch_Solid` exact-center tie resolves as "player below".
  **lookup #8:** d3 clobber contract disagreement between `Collision_GetType` and
  `Tile_Cache_GetCollision`.
- **animate:** RF_* comment expressions misuse bit numbers as masks (`$06` ≠
  `RF_XFLIP|RF_YFLIP` as literally written); `.cc_back` has no over-rewind DEBUG rail;
  `Sound_PlaySFX` clobbers-only-d0 license needs re-verification post-SFX-Stage-B/C.
- **rings:** `EntityWindow_EntryForSection` clobber list omits d0 (its own output).

Wave-2 additions (details in the per-file sections):

- **sound_api H-1 (real race, cross-file):** `Sound_PlayMusic` has no "previous request
  consumed" gate — a repost landing while the Z80 is mid-`Snd_LoadSong` tears the 6-byte
  param block AND loses the new request (the Z80 clears `SND_REQ_MUSIC` at load END). The
  SFX slot's drain gate is the correct pattern; music + ping/fade/tempo/sample slots lack
  it (PB-2: latest-wins claim is violated by the read→handle→clear poll shape). Needs a
  cross-file design pass, not a drive-by.
- **game_loop B1 (corruption-class, rare):** `VSync_Wait`'s clear-flag/set-Ready window
  (`vblank.asm:174-176`) lets an unluckily-timed IRQ6 run a full game tick with
  `VBlank_Ready=1` → next VBlank runs full `VInt_Level` incl. the plane drain against a
  possibly mid-fill buffer — the exact torn-drain hazard VInt_Lag exists to prevent. Fix ≈
  mask interrupts around the pair (~34 cycles/frame), which also makes Lag_Frame_Count exact.
- **controllers B1 (hardware-only, unfalsifiable in oracle):** single TH-settle `nop` where
  every reference (S1/S2/S3K, SGDK, plutiedev) uses two. Add the second nop (16 cycles/frame
  total); no emulator models settling, so this can never be caught by testing here.
- **dplc D4 (build tool, live hole):** the 2026-06-17 stray-fix overflow guard was NEVER
  re-applied to `tools/dplc_layout.py` — `write_dplc` silently masks counts, and the
  `--merge-only` path merges runs past 16 tiles with no split → silent art corruption.
  Runtime entry-splitting on the main path IS in place.
- **section B4:** `adda.w` sign-extension caps flat×66 at 32767 → **≤496 sections per act**,
  unguarded — directly relevant to the mega-act goal. **B1:** `RedrawPlanes` right-edge
  tracker unclamped (latent if cache margins grow). **B3:** hardcoded `lsl.w #8` encodes
  SECTION_SIZE_SHIFT−3 with no guard.
- **math B1:** `Sine_Table` declared `[u8]` but word-read — evenness is accidental, not
  enforced; latent address-error.
- **aabb #3/#4:** missing `ensure(cdim != delt)` and read-only guards on `apos` — same
  miscompile class the two shipped `stmp` ensures were added for. **#7:** the "two branch
  widths pinned" comment contradicts the code (only one is pinned).
- **structs/constants twins:** drift-guard coverage verified 100%; `act_descriptor.emp`
  still carries a duplicate local `SECTION_SIZE_SHIFT` mirror that should import the shared
  twin; `test_objects.emp`'s four unguarded mirrors lose all protection when the .asm twin
  dies (Spec-5 pattern).
- **objdef O1:** `vram_art` tile refinement `0..$1FFF` silently permits flip-bit bleed
  ($800..$1FFF); tighten to `0..$7FF` or document.
- **hblank:** ENGINE_ARCHITECTURE.md:1136 understates the no-effect HInt cost ~8×.
- **frames F1 / dplc D5:** offset-table words sign-extend — mappings/DPLC files ≥ 32KB
  index backwards; belongs as fatal checks in the build tools.

Wave-3 additions (details in the per-file sections):

- **buffers bug #1 (real, corruption-class):** `Palette_Dirty`/`Sprite_Table_Dirty` are
  cleared even when `queueStaticDMA` silently dropped the enqueue (Critical queue full — 
  reachable during a fade + heavy art staging, which also queues Critical). Stale palette
  persists indefinitely. Fix: report drop via carry, clear bits only on success.
- **vblank bug #3:** DMA entries never set autoinc ($8F) — Critical drains inherit it from
  the PREVIOUS frame's VInt_DrawLevel exit; on a lag frame a main-loop transient autoinc≠2
  interrupted mid-setup corrupts the CRAM/sprite DMA stride. One `move.w #$8F02,(a5)` at
  the Critical drain head closes it permanently.
- **vblank H1 (budget hole):** Critical DMA bytes and the CPU plane-copy are uncharged by
  the frame budget (reset AFTER Critical drains) — worst case exceeds the ~18.5k-cycle
  window ~1.7×. Also: CODING_CONVENTIONS §3.3/§8.1's "~4,300 cycles" VBlank figure is
  wrong ~4× (the engine's own DMA_BUDGET_NTSC=7200 bytes ≈ 17k cycles of halt time proves
  the ~18.5k window). VInt_Level's header comment documents the exact ordering §3.4
  forbids (code is right, comment is wrong).
- **parallax B1/B2/B3 (transition logic):** re-crossing back into the current config's
  section mid-transition doesn't cancel the staged transition (wrong config persists);
  builder/DMA-length/VSRAM-mode consumers disagree on which config is "active" during a
  smooth transition (up to 16 frames of mode/length mismatch for cell↔line pairs); the
  16-frame >>4 lerp ends with ~36% of the delta remaining → visible end-of-transition pop
  (the constants.asm:319 convergence comment is mathematically wrong). Also: the
  Hscroll_Dirty range mechanism is written but never read (dead), and the file's "~410
  cycles/frame" cost comment is off ~50×.
- **children C1 (rendering bugs):** an effect spawned by an RF_MULTISPRITE parent is
  NEVER rendered (skipped as batch-rendered but not in the sibling chain); stale
  parent_ptr on parent-slot recycling can silently hide children; children never inherit
  a priority band (always band 0 = backmost); `CreateChild_Linked` orphans a pre-existing
  chain (dynamic-slot leak).
- **macros B1 (sprSize, expanded):** the w/h-swapped formula is ALSO the canonical example
  in CODING_CONVENTIONS.md:25 — fix both together or it comes back. All in-file evidence
  (SPRITE_MASK_SIZE, CellOffsets_XFlip, SAT format doc) confirms the macro is the
  wrong-way-round party. Also: the clearLoadedRing/Obj "expand once per scope" comment is
  false for AS (7 expansions in one scope build fine today); DEBUG_DMA/_VRAM/_OBJECTS/
  _COLLISION flags are dead and §1.7's subsystem-gated ifdebug was never built.
- **player G9 (latent §2.5b violation):** `Ground_Move:620` byte-loads the probe code into
  d7 then consumes it with WORD ops (`move.w d7,d2` / `tst.w d7`) — high byte is caller
  residue (0 today only because d7 = player counter 0). Same bug class that shipped in
  Sound_PlaySFX. Fix: `moveq #0,d7` before the load.
- **player G10:** `move_lock` never ticks while standing on a solid object — a slipped
  player landing on a solid keeps frozen input forever (only jump escapes).
- **player A7 (needs a ruling):** landing always uncurls with no clearance check while the
  roll path guards the identical wall-clip hazard — classic parity vs the codebase's own
  hazard-class spec; decide, don't drive-by fix.
- **s4lz H2/P1/P2:** the routine's real preservation contract (d4-d7/a5-a6 + a4/d4 for
  load_art; tile_cache's a5/a6 hoist is load-bearing) is written nowhere in the file —
  doc-fix before ANY register change; TileDelta_Undo's a1-exit contract holds only by
  construction; the dict-hit debug assert reads garbage d4 on the plain entry.
- **camera P1/P2:** word-width ceiling (see mega-act cluster in the header); Camera_Init
  doesn't clamp — a start position near the world edge feeds one negative-camera frame
  into cache population.
- **bg_anim M1/P1:** header claims a3-a4 clobbered while the movem preserves them (one is
  wrong — per the declared contract the movem is dead weight); no band_count ≤ 4 guard
  (malformed table corrupts RAM past BgAnim_LastStep).
- **game_loop/vblank note:** the robust VSync_Wait fix is spinning on Frame_Counter
  change (monotonic, no consume-side clear) rather than reordering the two flag stores —
  reordering alone opens the mirror race.
- **player misc:** `Player_LevelBound` word truncation (mega-act cluster); stale "spindash
  lives in sonic.asm" comments; `PHYS_ROLL_FRICTION` constant is dead and misleading;
  `Player_AtLedgeEdge`/`Player_Display`/`Player_Init` clobber headers understate.

Wave-4 additions (details in the per-file sections):

SOUND (Z80) — real bugs:
- **Z80 boot-window garbage (driver B1, real):** on sound builds the RAM-clearing idle
  program never runs (blob loads INSTEAD of it) — the 7 SfxChannels + duck bytes are
  power-on garbage from boot until the first Snd_LoadSong; `Sfx_Frame` walks the garbage
  channels every frame (possible wild chip/bank writes). Oracle can NEVER show it
  (emulators zero RAM). **Net-zero fix:** replace init's queue-cnt store with
  `call Sfx_StopAll`.
- **`Sfx_DuckRamp` resurrects a stopped song's PSG channels (SFX B1, high confidence):**
  the held-note re-assert walk has no `SND_SEQ_ACTIVE` gate (unlike the fixed
  `Sfx_Restore`) — StopMusic + a ducking SFX un-silences a stale-KEYED PSG channel at its
  stale tone; it drones until the next song load. +5-byte fix (gate the walk, not the ramp).
- **`Psg_ApplyMod` zero-divisor (PSG #1, likely real):** clamps only negative sums; an
  exact-zero divisor passes and is written to the chip, contradicting its own comment.
  Reachable (top 13 pitch entries have divisor 1). `Psg_EmitNoiseClock` does it right.
- **Sequencer B1:** PSG portamento down-glide 16-bit underflow evades the overshoot snap →
  glides through wrapped space up to ~65536/rate frames. **B2:** a vol-env body starting
  `$80` (Loop) wedges the driver inside the Timer-A tick — zero-byte fix = build-time
  assert in the table generator.
- **PlayMusic race, Z80-side evaluated (driver B2):** snapshot-and-clear-early is sound;
  concrete shape costs ≈ +8 bytes (affordable with the size reclaims); snapshot-first
  ordering shrinks the lost-repost window ~1000×. Cheaper zero-byte fallback: clear-early
  alone (self-heals a torn load next poll).
- **YM2612 write-spacing audit: PASS** — single primitive, worst-case gaps 1.3–5× hardware
  requirements, more conservative than shipped SMPS. `Fm_PatchLoad` clobbering `sc_pan` on
  mid-song patch changes is the one latent hazard to verify sequencer-side.
- **Sequencer H1:** the per-channel tempo gate is provably redundant (all accumulators in
  lockstep forever) — ONE global accumulator is smaller, faster, AND more S3K-exact.
- **SFX invariants verified INTACT** (7-bit priorities, sx_pad alias, StopAll gotcha still
  latent at source but patched at Sfx_Restore — DuckRamp is the missed second consumer).
  Queue arbitration compares RAW priority (bit7 would add +128 weight — latent drift, 2-byte
  fix). Alias fields (sc_noise_mode/sx_priority, sc_detune/sx_pad) protected only by
  transcoder convention — add python-side asserts ($F2/$F6 never in SFX streams).

BOOT — hardware-risk items (oracle can't verify most of these):
- **Cross-reset RAM mechanism is dead scaffolding:** warm boot falls into the cold path and
  wipes it; `CROSS_RESET_MAGIC` is written but never read anywhere. Implement or delete.
- **PSG silence writes race the in-flight VRAM DMA fill** (~2× implicit timing margin, no
  enforcement) — free fix: move them after `.wait_fill`. Hardware-only effect.
- **YM key-off block:** no busy-wait AND can hit the address-latch race against the
  already-running Z80 driver (stopZ80 can halt it between its own addr/data writes) — do
  the key-off before the bus release, or drop it in sound builds.
- **No build-time evenness assert on either Z80 blob** — the known "blob must be even"
  memory invariant is unenforced; an odd blob = boot address error.
- z80_init leaves SP=0 (a future push lands in the 68k bank window); `ld bc,(...)-...`
  operand parse trap; spurious-interrupt vector policy inconsistent (crash in release);
  EntryPoint doesn't reload SP (jmp-reset unsupported).

68K SHELL / TEST / DEBUG / DATA:
- **Sprite culling uses LAST frame's camera** (RunObjects before Camera_Update in the only
  camera-moving state; zero cull margin, 16px/frame step) — edge pop-in; needs an ordering
  or margin decision.
- **OJZ direct `$8B` VDP write** applies a new HScroll mode a frame before its data (§3.4
  tear), unconditionally every frame — the setVDPReg shadow path alone is correct.
- **`Camera_Init` doesn't clamp** and the ENTIRE OJZ init ladder (spawn, trackers, cache,
  redraw, entity scan, parallax prime) seeds from the unclamped value.
- **`Section_RedrawPlanes` Z80-safety asymmetry:** init call site stopZ80-wraps it, the
  bare per-frame call site can reach it via runtime `Section_Plane_Dirty` (cache recovery)
  → direct VDP writes with the Z80 live. Fix engine-side (stopZ80 inside RedrawPlanes).
- **Release-build leaks:** convsym appends the FULL symbol table to release ROMs
  (build.sh:130-134, unconditional); `SOUND_DEBUG_HOTKEYS=1` without `DEBUG=1` builds a
  release ROM with hotkeys + boot autoplay ("requires DEBUG" enforced nowhere); MDDBG blob
  + exception stubs ship in release (decide + document); `RaiseError`/`Console` are not
  DEBUG-gated (call-site discipline only).
- **Template bugs:** `AnimateSprite` called with uncontrolled d3 while anims use
  DUR_DYNAMIC (test_player + test_animated — animation rate is register garbage);
  test_parent's self-destruct never fires (swing phase reloads the lifetime counter —
  parent immortal); "idle" is actually ANIM_RUN; magic art_tile `$A0FA` aliases the level
  art pool. path_swap itself is clean (speed-independent, correctly armed) but
  single-player hardwired — reserve per-player state before Tails.
- **load_art ignores the QueueDMA_Critical carry** (same silent-drop class as the buffers
  bug); **bg.asm:** a length-1 tile blob sprays 64K words across all of VRAM past the
  existing guard; both init blits are ~2 frames of CPU word-pokes (move.l/DMA territory).
- **Transpose question ANSWERED (bg reviewer):** column-major BG layout works with NO dual
  format — linear consumers adapt via autoinc $80 (row stride fits the autoinc register
  exactly); Draw_BG_TileColumn drops ~34 → ~22 cyc/word. Act blob must be transposed too
  (production sections have sec_bg_layout = NULL → act fallback is the common case).
- **RAM alignment audit: CLEAN** across all four build shapes; +256 B trivially available
  (~19.4 KB upper-half margin). `Spawn_Count`/`MAX_SPAWNS_PER_FRAME` is dead scaffolding;
  `CAM_MAX_Y_STEP ≤ VFILL_ROWS_PER_FRAME*8` sits at exact equality with NO build guard;
  several dead constants (HEIGHT_MAP_SIZE, CTYPE_FLAT_SOLID, SF_*, ST_P*_PUSHING…);
  fragile fixed pads that should be computed. The conventions "4,300 cycles" is the CPU
  budget figure and it's the stale one — constants.asm is consistent.
- **ZX0 verified byte-faithful to upstream** (Emmanuel Marty V2) — keep untouched; latent
  dbf word-count ceiling safe by construction (document it).

---
---

# SIGIL DIAGNOSTICS TIER — compile-time nets for the bug classes this review found

**ADJUDICATION (2026-07-16): ENDORSED with amendments — this section is now the EVIDENCE
BASE, not the build source.** The build source is the **contract-grammar spec** (Fable
drafting), which merges D1b (declared inputs) + D2 (must-use carry outputs) + the
pre-existing typed-register-signature ask into one grammar. Amendments folded into the
spec that this section does not cover:
- **extern-proc contract declarations** — the .asm-callee trust boundary D1a needs (an
  .emp caller of an unported .asm routine gets a declared, checkable contract instead of
  an unverifiable hole in the call-graph closure);
- **indirect-call contract bounds** — jump tables, `VInt_Ptr`/`HBlank_Handler_Ptr`,
  object dispatch, animate's `.evt_callback`: the indirect site declares the contract
  BOUND every installable target must satisfy;
- **scaffolding annotation** — ratified zero-caller keeps (e.g. `Plane_Buffer_Reset`'s
  forward reset hook) marked so D7's dead-symbol analysis doesn't nag them; unmarked dead
  symbols still fail.

**Sequencing (adjudicated):** pass-2 streaming perf runs PARALLEL to the diagnostics
build; **pass-3 contract surgery waits for D1a/D2** to land.

**Phase-order rationale (original, still valid):** the contract-surgery perf work (movem
trims, register-resident budgets, drain restructures, caller-side hoists) is exactly what
these diagnostics protect. Land the nets, then cut.

Scope note on .emp vs .asm: the full mechanisms are Sigil-compiler-tier and apply to .emp.
The .asm tree is not endgame, but it shares every bug class — the interim strategy is:
**s4lint grows lint-tier approximations** of D1/D3/D7/D11 for .asm (best-effort, warning
level), while Sigil enforces the real thing on .emp (error level). Anything ported gains
the strong guarantees automatically; nothing waits on the port.

Each mechanism below cites the actual findings from this review that it would have caught
(the evidence base — see the bug roll-up above and per-file sections).

## D1. Verified register contracts (the biggest single net — ~2 dozen findings)

Four sub-checks, in order of value:

- **D1a — write-set verification, transitive.** Compiler computes each proc's write set
  INCLUDING callee effects (call-graph closure) and errors on any mismatch with the
  declared `clobbers()`/`preserves()`. This is S2-D6b finished and made transitive.
  *Would have caught:* core's d7 omissions (RunObjects/RunObjects_Frozen), Vscroll_Write's
  d0/a0 (a prerequisite for the ISR movem trim), load_art's phantom d6, bg_anim's
  header-vs-movem contradiction, touch_test_target's d5, Player_Display/Init/AtLedgeEdge
  headers, sound_debug's d1, every stale template header.
- **D1b — declared inputs.** `in(reg: name)` parameters; a call site where the input
  register has no reaching definition = error (def-use over the caller body).
  *Would have caught:* the AnimateSprite d3/DUR_DYNAMIC bug in test_player AND
  test_animated (animation rate driven by register garbage — shipped in two templates).
- **D1c — caller-side liveness.** Holding a live value in a register across a call whose
  verified clobber set includes it = error; relying on a register not in `preserves()` =
  error. *Would have caught / prevents:* the fragile d6-across-Parallax_CheckBoundary
  pattern; makes every "trusting the callee's contract" hoist (the perf items) safe.
- **D1d — dead-save lint** (perf tier, warning): a save/restore pair for registers the
  callee provably preserves. *Evidence:* dplc D1 (~575 cyc/frame-change), load_object L1
  (~76/spawn), children M1 (44-116/child ×6 creators), test_parent's GetSineCosine movem,
  test_churn's a0 dance, zx0's cosmetic movem. This lint IS a chunk of the perf backlog.

## D2. Must-use error results (cheapest catch-per-effort on the list)

Carry-typed (or flag-typed) declared outputs: `out(carry: dropped)` on QueueDMA_* /
queueStaticDMA / RingBuffer_Add; a call site that neither branches on nor explicitly
discards the result = error ([[nodiscard]] semantics).
*Would have caught:* **Palette_Dirty cleared-on-drop** (buffers bug #1) and **load_art's
ignored Critical carry** — both real silent-corruption bugs from this review.

## D3. Width/sign dataflow (§2.5b as a compiler pass)

Track value width+signedness through registers. Byte-loaded value consumed by a word op
(index, compare, tst) without zero/sign-extension = error. Narrowing/sign-reinterpretation
(`adda.w` of a value whose declared range can exceed $7FFF; word compare of long math) =
error unless an explicit range `ensure` discharges it — powered by refinement types on the
source fields (Act.grid_w etc.).
*Would have caught:* player G9 (d7 byte-load/word-use — the Sound_PlaySFX bug class),
the marker_id byte-compare/word-index, AND the entire **mega-act ceiling cluster**
(section ≤496 cap, camera word wrap, LevelBound truncation) at the moment a big act
descriptor is first authored.

## D4. Static worst-case cycle counting + budget/balance asserts (the differentiator)

68000/Z80 timing is deterministic — Sigil can compute worst-case cycles per path at build
time (loops need bounds; the hot loops have compile-time bounds). Three assert forms:
- `budget(cycles <= N)` on a proc — build fails on regression.
- `ensure(cycles(pathA) == cycles(pathB))` — **the DAC loop's 195/195/194 balance becomes
  a build-time proof instead of a comment**, making the nop→jr size reclaim safe forever.
- Link-time budget over a call graph — the VBlank ISR worst case vs the real ~18.5k
  window; the unbudgeted-Critical overrun class becomes a build failure.
*Would have caught (indirectly but loudly):* the parallax "~410 cycles" comment vs the
~23,000 reality — a budget assert at any sane value would have flagged the zero-table
waste the day it became the default path. Kills lying cycle comments as a category. No
other retro toolchain has this; it is a genuine Crucible differentiator.

## D5. Hardware-state effects (the catchable half of the races)

A small typestate set threaded through the call graph: Z80 bus (stopped/running), SR mask
level, VDP autoinc value, current ROM bank, display on/off, DMA-fill-in-flight. Procs
declare `requires`/`ensures` on these; plus a **pairing check** (every path from stop_z80
reaches start_z80 before return — lock discipline as a CFG check).
*Would have caught:* the lag-frame **autoinc inheritance** bug (drain `requires
autoinc=2`), **Section_RedrawPlanes reachable per-frame without stopZ80**, boot's
**PSG-vs-DMA-fill race** (fill-active conflicts with PSG writes), and it mechanizes the
stop/start pairing that sound_api currently passes only by hand-audit.

## D6. Shared-state context ownership (the 68k-internal race net)

Tag RAM symbols with writer contexts (`main` / `vblank_isr` / `z80-shared`). Rules: a
multi-instruction read-modify-write of ISR-shared state from main context outside a
masked region = error (single-instruction RMW like `ori.l` passes); cross-CPU cells
declare read/write/clear roles per side, and a same-side violation (writing a cell the
other side clears, without a declared consumed-gate) = warning.
*Would have caught:* the **VSync_Wait clear/set race** outright. The warning tier would
have made the PlayMusic mailbox asymmetry visible (SFX slot gated, music slot not) even
though the full cross-CPU race needs protocol design, not types.

## D7. Whole-program dead-write / dead-symbol analysis

Sigil owns the link: RAM written-never-read, RAM read-never-written, pub with zero
consumers, const with zero consumers — all natural lints.
*Would have caught:* Spawn_Count/MAX_SPAWNS_PER_FRAME, CROSS_RESET_MAGIC (written, never
read — the dead cross-reset mechanism), ess_ring/obj_left_idx, Hscroll_Dirty_Start/End
(the dead dirty mechanism), Tile_Cache_GetTile, the dead constants list from the wave-4
audit, the DEBUG_* flags. This mechanizes "clean, not bolted-on".

## D8. Typed data + layout asserts

- Typed tables: `[i16; N]` is even by construction — kills the Sine_Table class.
- Typed RAM slices (already the .emp direction) make the alignment audit a non-event.
- Linker size/evenness asserts: the Z80 blob evenness invariant (currently unenforced,
  boot finding #4) is one declaration.
- Computed pads (`(N)&1`) required where a pad depends on a constant — kills the fragile
  fixed-pad class from the RAM audit.

## D9. comptime unit tests for pure functions

Build-time test blocks next to `fn`s so writing golden asserts is frictionless:
`ensure(sprSize(4,1) == <expected>)`. *Evidence:* the sprSize w/h swap survived because no
non-square value was ever computed anywhere — one golden assert kills the whole class
(and the conventions doc can cite the test instead of restating the formula wrong).

## D10. Build-config flag algebra

Declared implications in the manifest: `SOUND_DEBUG_HOTKEYS requires DEBUG`,
`SIGIL_EMP_TEST_OBJECTS forbidden unless game==sonic4`. *Would have caught:* the
release-ROM-with-hotkeys-and-autoplay leak; enforces the comment claims build.sh currently
makes and ignores.

## D11. Local-mirror ban + drift-guard completeness

A file-local const equal in value to a reachable `extern`/shared twin symbol without an
`ensure(extern(...))` guard = lint; `use` imports preferred over mirrors once a shared
home exists. *Would have caught:* act_descriptor's duplicate SECTION_SIZE_SHIFT,
test_objects' four unguarded mirrors (whose byte-gate protection dies with the .asm twin),
ENEMY_PATROL_SPEED's two homes.

## s4lint growth list (the .asm interim tier)

Idiom lints implementable today without the compiler: clr-on-memory RMW; move.w #imm
where moveq fits; adda.w #imm where lea fits; **loop-invariant memory operand inside a
dbf loop** (catches the despawn-loop hoists, FlatIDXY's grid_w, camera reloads — a large
slice of the Medium perf findings); byte-load-then-word-use heuristic (D3-lite);
ifdebug-prefixed setup followed by a release-side flag consumer (the CCR-divergence
hazard); RaiseError/Console outside an __DEBUG__ gate.

## Explicitly NOT catchable (so nobody over-promises)

Algorithmic redundancy (double ceiling probe, AtLedgeEdge duplicate, per-tile wrap checks)
— semantic. Intent bugs (parallax transition non-cancel, DuckRamp's missing gate, children
priority-band inheritance) — design decisions, though typestate can stretch to some
("SeqChannels valid only while SND_SEQ_ACTIVE"). Hardware electrical reality (TH settling
nops) — only a hardware loop catches that. Cross-CPU protocol races in full — D6's
warning tier surfaces the asymmetries; the fix is protocol design.

## Recommended implementation order

1. **D1a-c** (finish + extend verified contracts) — largest catch count, unblocks the
   perf surgery.
2. **D2** (must-use results) — two real bugs for a day of work.
3. **D3** (width/sign dataflow) — the shipped-bug class + the mega-act cluster.
4. **D7** (dead-write analysis) + **D11** (mirror ban) — cheap, linker-side.
5. **D4** (cycle counting) — the big one; start with straight-line `budget()` +
   two-path `ensure(cycles==)` (enough for the DAC balance), grow to call-graph budgets.
6. **D5** (hardware-state effects) + **D6** (context ownership) — the race nets.
7. **D8/D9/D10** — small, fold in opportunistically.
8. **s4lint growth list** in parallel at warning level for the .asm tree.

---

# Per-file reports (verbatim from the review agents)

## 1. engine/level/plane_buffer.emp

### Process constraints (read first)

- Twin parity: this `.emp` is a byte-isolated port of `plane_buffer.asm`. Any optimization
  must be applied to both twins together (or deferred until the `.emp` is authoritative).
- Preserve the VInt_Lag race fix (b96c861): terminator-word semantics and the order of
  `Plane_Buffer_Ptr` reset vs. drain are load-bearing against mid-fill drain corruption.
- Measure with the lag-frame counter during max-speed diagonal scroll. Producer cost eats
  the main-loop frame budget; `VInt_DrawLevel` cost eats the VBlank window.

### High-impact, conceptual

**1. `Draw_TileRow_FromCache` inner loop — restructure from per-column checks to precomputed
segments.** The current loop does clamp-check, physical-col wrap check, W-cursor wrap check,
and an indexed load *per plane column* (~60+ cycles × 64 ≈ ~3,800 cycles/row). But the
W-walk is fully deterministic up front: W runs `A..R` then `R−63..A−1`, both monotonic, and
the `< Cache_Left_Col` zero region is a prefix of the second run. So the whole row
decomposes into **at most ~5 contiguous segments** (each W-run splits ≤2 ways at the
`TILE_CACHE_COLS` physical wrap, plus one zero-fill segment), computable before the loop.
Each segment becomes a straight `move.w (a0)+,(a2)+` (or `move.l`/unrolled) copy. Estimated
~3,800 → ~1,000 cycles per row. Rows fire during vertical scroll, exactly where lag lived.
**Top candidate for this file.**

**2. Column drain in `VInt_DrawLevel` can use `move.l`.** With autoinc `$80`, a `move.l` to
the data port is two word writes, each autoincremented — two column cells per instruction.
`.drain_col` currently does `move.w`+`dbf` (~18 cycles/word); longword pairs + one trailing
word for odd counts roughly halves the iteration count. Caution: an accidental extra word
past row 63 lands at `$E000` (Plane B), so odd-count handling must be exact.

**3. Precompute the VDP command longword in the producers.** The `lsl.l #2 / addq.w #1 /
ror.w #2 / swap` shuffle runs per entry inside VBlank, twice-duplicated. If producers stored
the ready-made command longword in the entry header (4 bytes instead of a 2-byte VRAM addr),
the drain heads become a single `move.l (a0)+, (a5)` — moving ~26 cycles/entry out of the
VBlank window. Buffer grows 2 bytes/entry (negligible vs. 1536). Also lets the count word be
stored bare (drops the `andi.w #$7FFF`). Interacts with the noted `vdp_comm_reg`
shared-module consolidation.

**4. `Draw_TileColumn` copy loops — hoist the circular-wrap check out.**
`.pA_data`/`.pB_data` do `cmpa.l`+branch **every** iteration (~16 cycles/iter of pure
wrap-checking, up to 64 iterations ≈ ~1,000 cycles/column). Rows-until-physical-wrap is
computable up front from the starting physical row: split into two check-free runs, each a
tight `move.w (a0),(a2)+ / lea 160(a0),a0 / dbf`. Combine with 2–4× unrolling.

**5. Consider DMA drain instead of CPU drain — Aeon-specific opening.** Classic Sonic
engines drain plane buffers with the CPU because VBlank DMA bandwidth is consumed by art
streaming. Aeon's art pool is **fully resident at init**, so runtime DMA budget is
comparatively idle. A 128-byte column via DMA ≈ ~100 cycles setup + ~300 cycles of
bus-frozen transfer, vs. ~700–1,150 cycles of CPU drain. The engine already has a DMA queue.
Trade-offs to verify: queue-slot pressure, per-entry setup dominating for small entries, and
whether total VBlank *time* actually improves. An option to measure, not a directive.

### Medium

**6. `Draw_BG_TileColumn` — build-time transpose of the BG layout.** The strip copy reads
column-major from a row-major 64×32 array (~30 cycles/word × 32). Stored column-major at
build time, the strip is a sequential 64-byte copy — roughly 3× cheaper. Verifier must check
all other consumers of `sec_bg_layout`/`act_bg_layout` (e.g. the initial Plane B fill in
`bg.asm`) before flipping the layout. Short of that: `adda.w #128,a1` → `lea 128(a1),a1`
saves 4 cycles/iter for free.

**7. Zero-fill rows in `Draw_TileColumn` — are they necessary?** When the cache's 60 rows
don't cover the 64-row plane, zero words are buffered AND drained to VRAM every column. If
those cells are truly never visible, clamping the entry count to the cached rows shrinks
buffer usage and VBlank drain. But if the zeros do stale-tile clearing during vertical
transitions, they're load-bearing. Determine empirically (sentinel-overwrite test).

**8. `clr.w (a2)+` in the zero-fill loops is a read-modify-write (12 cycles).** `move.w`
from a pre-zeroed data register is 8 cycles, and `move.l` pairs halve iterations.

### Micro

- `move.w #64,d5`, `move.w #TILE_CACHE_ROWS,dN`, `move.w #PLANE_H_CELLS-1,d2` → `moveq`.
- `Draw_TileColumn`'s `move.w d0,-(sp)` / `(sp)+` pair: d3–d5 are free — use a register.
- `.done: move.w #$8F02,(a5)` restore is only needed after a col entry; row entries rewrite
  `$8F02` even when autoinc is already 2. Marginal; fold into note 3 if done.
- All drain/copy loops are unroll candidates (dbf ≈ 10 cycles/iter overhead).

### Checked and already fine

`lea 160(a0),a0` stride advance optimal; ×160 and ×80 shift-add decompositions correct;
row drain already `move.l`; buffer-full checks reserve terminator space; VDP FIFO won't
stall these writes during VBlank; worst-case buffer occupancy (~11 columns at 136 B) fits
1536 comfortably.

---

## 2. engine/level/tile_cache.emp

### High-impact conceptual

#### 1. `TileCache_FillRow` per-tile loop should be restructured into precomputed contiguous segments
`tile_cache.emp:1415-1464`. The inner `.fr_col_loop` runs **per tile** and re-does, every
iteration: world-col reconstruction (~16c), Head check vs memory (~20c), Left/width clip
(~32c), circular column wrap (~30c), indexed source read (14c), stack-relative row-offset
reload (~36c even on rows with no collision), and double-indexed writes (~14-22c each).
Estimated **~180-250 cycles per tile**; a full 80-tile row ≈ 14-20k cycles, and with
`VFILL_ROWS_PER_FRAME = 2` a vertical-scroll frame spends roughly **30-40k cycles** here
before any decompression — the dominant per-frame cost in the file.

Everything the loop checks is deterministic once the block is known: the intra-col range
that survives Left/Head clipping is computable at block entry, and the circular wrap splits
the destination into **at most 2 contiguous runs**. Source tiles within a block row are
contiguous (`a0 + 2*col`), and so is each dest run. Restructure per block into: compute
`[col_start, col_end)` + wrap split → tight `move.w (a0)+,(a2)+ / dbf` (~22c/tile), with
`move.l` pairing (~13c/tile) when both cursors are long-aligned, and two loop *variants*
selected once per row (collision vs no-collision) instead of the per-tile `2(sp)` test.
Collision bytes are likewise contiguous both sides → `move.b (a0)+,(aX)+` runs.

**Estimated saving: ~5-8× on the copy portion — order 10-25k cycles per vertical-scroll
frame.** Budget-out only happens at `.fr_block_loop` head, so the resume contract
(`Cache_Fill_RowResume_Col` = block-start world col) is unaffected by segmenting within a
block. Verifier must check: wrap split arithmetic vs `Cache_Origin_Col` (off-by-one at the
seam), the transient case where `Head − Left < COLS − 1` during left-fill, odd/even dest
alignment before using `move.l`, and that the collision odd-row gate (`btst #0` at 1329)
still selects the right variant after resume mid-row.

#### 2. Empty blocks pay a ~5,800-cycle zero-fill that a pointer indirection makes free
`tile_cache.emp:343-350`. `.empty_block` writes 768 bytes with `clr.l (a0)+` × 192 (~30c/iter
≈ **5.8k cycles per empty block**). Empty blocks recur at world edges and blank regions —
exactly where max-speed scroll runs.

Because consumers only ever *read* staged data through the slot base returned in `a1`, the
staging system can hold a **per-slot data pointer in RAM** (16 × 4 bytes) written at claim
time instead of always resolving through the ROM `BlockStage_PtrTable` (`:189`). Then:
- **empty block** → point the slot at a single shared 768-byte all-zero ROM block: ~0 cost;
- **raw-direct block** (`:321-341`) → point the slot straight at the uncompressed ROM block,
  deleting the 24-burst movem copy (**~4.0k cycles per raw block**);
- compressed blocks still decompress into the RAM slot as today.

**Estimated saving: ~5.8k/empty, ~4.0k/raw** — up to `BLOCK_DECOMP_BUDGET`(6) × per frame
worst case. Verifier must check: nothing writes through a staged-block pointer
(`CopyBlockColumn` and `FillRow` only read); `FindStagedBlock:213-214` must switch from the
ROM table to the RAM pointer array; slot reuse must overwrite the pointer unconditionally;
ROM block must be `even`. Fallback if indirection is rejected: pre-zeroed `movem.l` bursts
(~3.5k saved per empty block), which also clears the conventions §2.5 `clr.l (a0)` violation.

#### 3. `TileCache_FindStagedBlock` linear probe + per-frame prefetch re-probing
`tile_cache.emp:198-220` and scan sites `1073-1089`, `1165-1183`. Probe ≈ ~250c average hit,
~390c miss. The steady-state prefetch scans re-probe every block col/row of the target line
**every frame even when fully staged** (`:1133-1136` confirms intentional): ~1.5-2.5k
cycles/frame of pure probing in steady scroll, plus the same again from demand probes.

Options, in order of preference:
- **Memoize completed scan targets** (behavior-preserving): when a scan walks the whole
  target row/col with all hits, record (target, Left/Head or Top/Bottom,
  staging-generation). Skip while the memo matches. Invalidate by bumping a generation word
  in `DecompressBlock`'s claim path. Saves nearly the whole steady-state probe cost for ~30
  cycles of check. Verifier: generation must bump on *every* claim including empty/raw; memo
  must die on `InvalidateStaging` and on Left/Head/Top/Bottom movement.
- **Direct-mapped staging** (hash low bits → slot): O(1) probe (~40c) but conflict-eviction
  thrash risk; needs the lag-counter A/B.

#### 4. No DMA opportunity in this file — stated for the record
Every copy targets **68K work RAM**; VDP DMA can only write VRAM/CRAM/VSRAM. The DMA
leverage point is downstream (plane buffer → VRAM).

### Medium

#### 5. `TileCache_CopyBlockColumn` — per-iteration wrap check on a wrap that happens at most once
`:407-414` (NT loop) and `:445-454` (collision loop). Each iteration pays `cmpa.l a3,a2` (6)
+ `blo` (10, common case is the **taken** branch — inverted fall-through per §2.2). The wrap
row is fully deterministic: split into ≤2 tight `dbf` segments — saves ~16c × (≤16 NT rows +
≤8 coll rows) ≈ up to ~380c per call, ~1.5-2k per newly-filled column, plus opens 2×/4×
unroll (rows are even by contract, `:365-368`). Verifier: segment-length math at the seam
row (59→0 NT, 29→0 collision); the plane-B displacement trick (`:440-444`) holds inside each
segment (it does — displacement is position-independent).

#### 6. Hot-lookup arithmetic in `Tile_Cache_GetCollision` (tail-called per collision sensor)
`:156-182`; hot via `collision_lookup.emp` tail call. Whole routine ≈ **200 cycles**. Two cuts:
- **`mul_cache_stride` uses the 40-cycle form when a 32-cycle form exists** (`:111-119`).
  `((x<<2)+x)<<4` (the file's own form (b), `:396-397`) = 32c with the same one-scratch
  requirement. The macro should just BE form (b). Even better: a build-time row-offset table
  (`add.w d1,d1; move.w RowTab(pc,d1.w),d1` ≈ 18c, 30/60 words of ROM) — saves ~22c/lookup.
  Verifier: `ensure(TILE_CACHE_STRIDE==80)` guard moves accordingly.
- **Fold `Left/Origin` and `Top/Origin` into cached biases.** `Cache_Col_Bias = Origin_Col −
  Left_Col` collapses two RAM reads to one. The row side folds too: both `Cache_Top_Row` and
  `Cache_Origin_Row` are kept even, so `((row−Top)>>1) + (Origin>>1) = (row +
  (Origin−Top))>>1` exactly — one bias read + one shift replaces sub/lsr/move/lsr/add (~46c
  → ~22c). Combined ≈ **45-50c/GetCollision (~25%)**. Verifier: bias updated at *every*
  mutation site — `HSlide`, `VSlide`, `VSlideUp`, left-fill origin retreat (`:874-879`),
  `Init`, `Reinit`; recommend a DEBUG assert recomputing from primaries.

#### 7. Prefetch/warmup scans reload loop-invariant act fields every iteration
`.pfx_scan` (`:1077-1080`), `.cs_scan` (`:1170-1172`), `WarmupBelowRow .scan` (`:691-693`):
`movea.l Current_Act_Ptr,a0` + grid loads re-executed per block (~30c/iter). Hoist into a
register that survives `FindStagedBlock` (clobbers only d3-d4/a1). ~180c/frame; trivial.

#### 8. `TileCache_DecompressBlock` sec-id add-loop and ×66 stride
`:283-298`. The `grid_w × sec_y` add-loop is ~14c × sec_y, up to 6×/frame. A build-time
per-act row-pointer table removes the loop; padding `Sec` to a power of two is the stronger
fix (62 bytes ROM per section). Low urgency. Verifier: `section.emp` shares the struct.

### Micro

- **`cmpi.w #$FFFF` after a flag-setting `move.w` → `bmi`** — sites `:749-751`, `:780-782`,
  `:1192-1197`, `:1455-1456` (last one per-tile until finding #1 deletes it). ~8c each.
- **`TileCache_InvalidateStaging` `:230-231`**: `move.l #-1,(a0)+` × 16 → `moveq #-1,d1` +
  `move.l d1,(a0)+`: ~128c, cold. Requires widening `clobbers`.
- **`TileCache_FillAll` zero loops `:527-536`**: `clr.l (a0)+` × 3,600 ≈ 108k cycles at init;
  `movem.l` bursts cut ~3×. Init-only (display off) — conventions-compliance more than lag.
- **Round-robin wrap `:257-261`**: → `addq.w #1,d5; andi.w #BLOCK_STAGE_SLOTS-1,d5` (~10c per
  decompress). Add `ensure` power-of-two.
- **`Tile_Cache_Fill` recomputes Camera swap+shift twice each axis** (`:802-804` vs
  `:813-815`; `:890-892` vs `:903-905`): ~24c/frame each. Trivial.
- **Wrap checks branch-taken on the common case** in `GetTile`/`GetCollision`: 2-4c/lookup;
  only while editing per finding #6.
- **`FillRow` redundant width check `:1429-1430`**: unreachable if `Head − Left ≤ COLS−1`
  invariant holds — verify with a DEBUG assert first, then remove (~16c/tile).

### Possible bugs / comment mismatches

1. **First-fill false lag-skip contradicts its own comment.** `Tile_Cache_Init:496` claims
   "no false skip on frame 1", but `Tile_Cache_Fill:721-735` recomputes from
   `Frame_Counter − Cache_Fill_Last_Frame − 1` with the `$FFFF` sentinel: on first fill the
   flag is set spuriously if any frames elapsed during init (~10 frames documented, `:658`).
   Harmless (one lost prefetch frame), but comment or gate is wrong.
2. **No out-of-window guard on the hot lookups.** GetTile/GetCollision silently read
   adjacent RAM for out-of-window inputs. Conventions §7.7 wants a DEBUG assert/CHK.
3. **Dead export: `Tile_Cache_GetTile` has zero call sites** (grepped whole repo).
   Deletion candidate under "clean, not bolted-on".
4. Header/attribute contracts spot-checked — consistent. The raw-copy cycle comment
   (`:335-337`) checks out.
5. **Load-bearing invisible dependency, self-flagged:** the a5/a6-survive-`DecompressBlock`
   hoist (`:1345-1354`) is one decompressor swap away from silent corruption; endorse the
   checked-clobbers lint the file itself asks for.

### Checked and already fine

Stack balance in `Tile_Cache_Fill` (all paths traced); circular-wrap single-subtract
correctness; `FindStagedBlock` low-word slot arithmetic under 16-bit wraparound;
`.fr_budget_out` resume granularity; `dbeq` probe semantics; sec-id add-loop trip count;
×66 shift pair vs `sizeof(Sec)` ensure; screen+rounding constants; movem burst register
choice; VSlide/VSlideUp/HSlide already O(1) origin-move; frame-budget accounting overhead
(~30c per block-unit) not worth register-threading.

**Priority:** #1 first (measure with lag counter during diagonal scroll); #2 biggest
per-decompress; #3/#6 steady-state trims; rest polish.

---

## 3. engine/objects/entity_window.emp

### High-impact conceptual

#### 1. Per-frame X-scan calls have no cheap "nothing entering" gate
`:901-911` (section loop) + `:1030-1062` / `:1237-1271` (walkers). Every frame, per valid
entry (≤4), the code jsr's into `ScanRingsRight` **and** `ScanObjectsRight`; each call loads
the ROM ptr, ratchet, re-derives the entry cursor, reads the first entry, compares against
the edge, exits. ~150-200c per section per frame (~600-800c/frame) doing nothing most
frames.
**Proposed:** cache "next entity engine-X" per section per list — walker writes the engine-X
of the entry at the ratchet (or `$FFFF` at terminator) into the scan state on exit; the
section loop does `cmp.w cached,d7 / bcs` and skips the call when the edge hasn't reached
it. The two **dead** `ess_ring_left_idx`/`ess_obj_left_idx` fields (see bugs #1) are
perfectly placed storage. `InitSection` clearing them to 0 naturally forces the first scan.
**Est. ~500-650c/frame steady-state.**
Verifier: cache written on *every* walker exit path (`update_idx` and ptr==0 early-out) and
by `PopulateSectionRings` (`:1104` sets the ratchet without running the walker); `RescanY`
doesn't move ratchets; ratchet semantics unchanged; unsigned-compare wrap identical to
today's `bhi`.

#### 2. `Collected_UpdateCenter` re-divides an id its callers just multiplied
`:456-473`, callers `:831-841` and `:1625-1638`. Both callers hold `sec_x`/`sec_y`, call
`Section_FlatIDXY`, and `Collected_UpdateCenter` then reconstructs center x/y from the flat
id by repeated subtraction (up to `grid_h` × ~22c). Widen the contract to take center x/y;
delete the `.div_center` loop. Cold path but free (~350c/slide) and less code.

#### 3. `DespawnRings` recomputes loop invariants per live ring — up to 128 iterations/frame
`:1383-1418`. Per iteration: `lea Ring_Buffer,a0` **inside** the loop (~8c/iter); rebuilds
`index×6` (~16c/iter) + indexed field reads (+6c/access); rebuilds the Y despawn band from
scratch (`:1411-1415`, ~28c/iter).
**Proposed:** walk `a0` backward with `subq.l #6,a0` (keep d5 for `RingBuffer_Remove`);
hoist the two Y band bounds into free registers. **Est. ~50-70c per live ring per frame →
~1,000-1,400c/frame at 20 rings; several thousand worst case.**
Verifier: swap-with-last removal + backward iteration with a walking pointer (swapped-in
entry comes from a higher, already-visited index — pointer must NOT advance past it; walking
backward this holds); `RingBuffer_Remove` clobbers vs hoisted regs.

#### 4. `DespawnObjects`: Y band rebuilt per live object
`:1499-1506`. Same pattern: hoist both band bounds before `.loop` (d6/d7 free). **Est.
~28-36c per live object per frame (~300-700c/frame).** Verifier: the `.despawn` movem window
(`:1510`) — hoisted regs inside a preserved set or re-derived after `DeleteObject`.

### Medium

1. **`Collected_CheckRing`/`Killed_CheckObject` save d0 needlessly around `FindSlot`** —
   `:192-194`, `:239-241`: `movem.l d0-d1` (~52c round trip) but `Collected_FindSlot`
   clobbers d1 only. Save just d1.w (~20c). ~30c per spawn attempt. Verify: d0-preservation
   becomes a contract — document it on FindSlot.
2. **Cache the claimed collected/killed slot pointer per window entry** — every candidate
   funnels through `Collected_FindSlot`'s 9×34-byte linear scan (worst ~300c incl. call).
   Slots are claimed once in `BuildEntries` (`:768-773`) and never move — store the slot ptr
   (or 0) in `EntityScanState`. ~200-300c per spawn attempt. Verify: eviction can't touch a
   window section (2×2 ⊆ 3×3, currently *unchecked* — bugs #3); ClaimSlot failure → cached 0
   → same semantics; `Collected_MarkRing`/`Killed_MarkObject` still FindSlot unless also
   routed through the cache.
3. **`clear_slot_bitmasks` uses `clr.l d16(An)` — conventions §2.5 violation** — `:119-131`
   (expanded `:146`, `:315`, `:515`). ~40-70c per slot clear; cold-ish but codified rule.
4. **`EntityWindow_InitSection` `.clear_mask` uses `clr.l (a2)+`** — `:643-644`, 8 iters.
   Same rule; ~8c/iter. Clobbers widen — check callers' live regs.
5. **`EntityWindow_Init` clears scan state byte-at-a-time** — `:814-818`: 104 × `clr.b
   (a0)+` ≈ 2,300c → 26 long stores ≈ 570c. Init-only. `:815` also fits moveq. Verify:
   word alignment of `Entity_Scan_State`.
6. **`Collected_UpdateCenter` per-slot division loop** — `:487-493`: up to 9 × 16 × ~22c ≈
   3,000+c on a slide frame (the lag-risk frames). Option: stash grid (x,y) in the slot's
   existing pad byte at claim time (x:4|y:4 works for grids ≤ 16×16); compare directly.
   Verify: grid ≤ 16 assert; pad byte unclaimed; park/unpark copies start at offset 2 so the
   byte isn't preserved across park — re-stamped at claim, which is when it's derived.
7. **`EntityWindow_MigrateMasks` re-derives entry×26 per iteration** — `:1550-1561`: d3
   iterates 0-3 sequentially — a stepped pointer deletes the decomposition and is *also*
   clearer. Cold; low priority.
8. **`EntityWindow_Scan` slide gate calls `DeriveWindow` every frame** — `:886`. ~130-150c/
   frame to conclude "unchanged" on ~99% of frames. Store the anchor cell's raw pixel
   trigger bounds at slide/build time; gate on 2-4 raw `cmp.w Camera_X/Y`. ~100c/frame.
   Verify: world-origin clamp (`:688-696`) baked into stored thresholds; recomputed on every
   anchor change (BuildEntries).

### Micro

1. `:877-879` movem of d5/d7 around `RescanY` — d5 save is dead (DeriveWindow clobbers d5
   anyway). Save only d7. ~24c on rescan frames.
2. `:145`, `:154` (`:514` evict path): `move.b #$FF,(a0)` (12c) in loops → hoisted `moveq
   #-1,d0` + `move.b d0,(a0)` (8c).
3. `DespawnObjects` reads `Sst.slot_tag` twice (`:1482`, `:1497`). Load once; tests must
   stay ordered ($FF has bit 7 set). ~8-12c per live tagged object. Verify d1 liveness.
4. `Collected_ParkSlot` `:358-365`: pointer step vs ×33 decomposition is near-wash — the
   *comment's rationale* is wrong, not the code (see mismatches #4).
5. `EntityLoaded_Test/Set/Clear` `:544-586`: ~36c call overhead on ~60c bodies, jbsr'd from
   every spawn attempt and despawn-clear. Inline as comptime fn at ~6 sites; ~100 bytes ROM.
   Only bundled with a broader spawn-path pass.

### Possible bugs / comment mismatches

1. **`ess_ring_left_idx` / `ess_obj_left_idx` are dead state** — declared `:59`/`:61`,
   cleared `:656`/`:658`, **never read or written anywhere else** (grep-verified across
   .asm+.emp; `structs.asm:246,248` matches). No left-edge walker exists. Delete (struct
   shrink — coordinate twins + drift guards `:98,:100`) or repurpose as the trigger cache
   (High #1).
2. **Mixed signed/unsigned X comparisons — latent 16-bit world-extent constraint** — walkers
   use unsigned `bhi` (`:1050`, `:1260`, `:1099`); `DespawnRings` uses signed `blt/ble`
   (`:1393-1395`). Both fine today; `d7 = Camera_X + $4A0` wraps unsigned past `Camera_X ≈
   $FB60`, signed despawn breaks past X = $7FFF. Assumes world X well below $8000 — assert
   or pin to the floating-origin dependency.
3. **`Collected_ClaimSlot` failure silently ignored** — `BuildEntries:772` never tests Z; on
   failure the section runs with no collected/killed tracking. Should be impossible
   (2×2 ⊆ 3×3) but that invariant lives only in a comment (`:447-449`). DEBUG assert wanted.
4. **`Collected_ParkSlot` comment overstates the multiply cost** — `:357`: ×33 is a 2-op
   decomposition; comment gives a wrong rationale.
5. **`TrySpawnRing` buffer-full drop window** — `:1006`: on `RingBuffer_Add` carry, the
   ratchet has passed the ring; retry only on the next 128px coarse-Y crossing or slide. A
   ring can stay missing indefinitely on a flat run with a full buffer. Interacts with any
   despawn-staggering change.

### Checked and already fine

Despawn tail call (`:914-915`); X-sorted early exit in walkers (O(entering), not O(list));
ratchet/loaded-bit idempotency sound; `DespawnObjects` walks the live list (empty slots
zero); movem frame offsets verified; static-camera despawn skip considered and rejected
(objects move themselves out of the band; a ring/object despawn *stagger* is the only
variant worth escalating — needs user sign-off); asr flooring / world-origin clamp /
SEC_VOID / single-axis slide assert all match code; index-register hygiene clean; ×6/×26
decompositions fine.

**Priority:** High #1 (trigger cache, reusing dead fields) → High #3/#4 (despawn hoists) →
Medium #1/#2 (spawn path) → High #2 + Medium #6 (slide frames) → rest opportunistically.

---

## 4. engine/objects/sprites.emp

### High-impact conceptual

#### H1. Frame-data resolution done twice per object per frame — cache the frame offset (and bbox) in the SST
`:77-81` (Draw_Sprite) and `:273-277` (Render_Sprites) — identical resolve chains (~46c
each, ~92/object/frame combined); third copy in the sibling walk (`:361-365`). The caching
infrastructure already exists (`Sst.sprite_piece_count` cached at spawn, refreshed on frame
change via `RefreshSpritePieceCount`). Extending that refresh to also cache the resolved
**frame-data word offset** (2 bytes in SST) makes both hot paths one `move.w
cached_off(a0),d0` + `adda.w d0,a3` (~20c). Caching the 4 bbox bytes too removes
Draw_Sprite's mapping deref entirely on the cull path.
**Est. ~50-70c/object/frame (~1,500-2,000c/frame at 30 objects).**
Verify: SST free bytes near `$25`; every `mapping_frame`/`mappings` mutation goes through
the refresh; stale-cache behavior on mid-frame changes.

#### H2. Emit loop: restructure to stream order; merge size+link into one word write
`emit_piece_loop` `:590-607` + term helpers `:485-581`. Unflipped piece ≈ 136c. The copy
can't be `move.l`-batched (3 of 4 SAT words need per-piece arithmetic), but:
1. **Stream-order processing** — stop front-loading all 4 reads and parking tile/X in a6/a1;
   process each field as read. Flip variants still work (yflip reads Y then size before
   computing; xflip's width re-read via `-6(a3)` still lands on size). **−8-12c/piece**, and
   frees **a1 and a6** (see M2).
2. **size+link word merge** — the mapping's pad byte occupies exactly the link position:
   `move.w (a3)+,d1` / `addq.b #1,d5` / `move.b d5,d1` / `move.w d1,(a4)+` (~24c) replaces
   the ~36c byte sequence. **−12c/piece** for unflipped/xflip (yflip keeps its form).
**Est. combined ~20-24c/piece → ~1,000-1,900c/frame at 50-80 pieces. Hottest loop in file.**
Verify: byte-identical SAT for all four flip variants; pad byte genuinely don't-care;
a1/a6 not live across `Emit_ObjectPieces` (contract `:627-629` says clobbered — they are).

#### H3. Sprite-table DMA is a fixed 640 bytes every dirty frame — patch length to `Sprites_Rendered * 8`
Consumer: `engine/system/buffers.asm:69-72` (`dmaLength(640)`), enqueued on
`Sprite_Table_Dirty` (`buffers.asm:150-153`), set by `Render_Sprites` (`:433`). 640 B of
Critical VBlank DMA (~8.5% of budget) even at 20 live sprites (160 B). Partial DMA is safe —
the link chain terminates at the last written entry. `Render_Sprites.done` patches the
length to `d5<<3` (~20 CPU cycles; saves up to ~480 B critical DMA).
Verify: `Static_Sprite_DMA` layout tolerates runtime length rewrite; had-sprites→none frame
still DMAs the 8-byte terminator (**fix PB1 first**); halved-word-count semantics.

#### H4. Dirty-tracking / static-frame skip is foreclosed by the every-frame link-order flip
`:230-241` — the B2 fairness choice (reverse intra-band order every frame) means the SAT
differs every frame; `Render_Sprites` + full DMA can never be skipped even on static frames.
Design tension only: gating flicker-cycling on "band count > 1" would let static frames
reuse the previous SAT (~10-20k cycles + DMA). **Needs Volence's call — B2 was signed.**

### Medium

- **M1. Drop the per-piece SAT-cap compare by pre-clamping the loop count** — `:603-604`
  (~8c/piece). Pre-clamp `d4 = min(d4, MAX-d5)` (~20c once), plain `dbf`. Strictly safe
  (doesn't trust the cached count). ~200-400c/frame. Verify dbeq→dbf per variant; d5 still
  incremented per piece.
- **M2. Step direction lives on the stack — move to a register freed by H2** — `:236,241`
  push, `:250` `adda.w (sp),a2` (~12c/object), `:408`/`:458` pops. Hold in a6: ~4c/object +
  ~160c/frame, and `.band_limit_pop`'s stack-balancing hazard disappears. Verify a6 across
  `Emit_ObjectPieces` (post-refactor), `InsertSpriteMasks`, `DrawRings` (a6 safe).
- **M3. Fuse `move.w (aN,d0.w),d0` + `lea (aN,d0.w),aN` → `adda.w (aN,d0.w),aN`** — three
  sites (`:80-81`, `:276-277`, `:364-365`), ~8c each; ~16c/object/frame. Subsumed by H1.
- **M4. Draw_Sprite: reorder band-count increment to kill a redundant `lea`** — `:150-155`;
  a1 already holds Counts at `:123`. ~8c/registered object. Verify cascade path (a1 =
  Counts — it is).
- **M5. `lea CellOffsets_XFlip(pc),a0` loaded for all four variants, used by two** — `:632`,
  ~8c/object wasted for unflipped/yflip. Move into xflip instantiations; or drop the table:
  width = `andi.w #%1100,d1` + `add.w d1,d1` + `addq.w #8,d1` (~16c vs ~30c) — faster AND
  frees a0 + 16 bytes ROM.

### Micro

- `:333-337` + `:286` — `render_flags` read 3× per rendered object; one load + `btst #n,Dn`
  saves ~12-20c but register pressure — bundle with a bigger refactor only.
- `:233` — `btst` of cycle-counter parity per band; acceptable, note only.
- `:684-685` (`InsertSpriteMasks`) — `move.w #0,(a4)+` ×2 → zeroed reg; `addi/subi` →
  moveq'd reg. Masks rare — cosmetic.
- x_term X=0 fixup (`:566-570,576-579`) — branchless `seq/sub.b` saves ~2c/piece; fold into
  H2 only.
- `:431` — fine as-is (correctly avoids `clr.b` RMW).

### Possible bugs / comment mismatches

- **PB1. `.empty_table` edge trigger is dead — `InitSpriteSystem` zeroes `Sprites_Rendered`
  every frame** (`:39` vs `:441-442`). Init runs at top of every frame (confirmed in all
  three states), so the had-sprites→none transition never writes the hidden terminator and
  never sets dirty: **previous frame's SAT persists in VRAM — frozen ghost sprites**, the
  exact failure the comment claims to prevent. No other reader of `Sprites_Rendered` exists.
  Same in the twin. Fix direction: remove the init clear (Render_Sprites writes it on every
  path) or a dedicated prev-frame flag. Verify first-frame-ever (both 0 → `.still_empty`,
  fine — VRAM SAT starts cleared).
- **PB2. Scanline-budget band index computed from *biased* Y — bands shifted +4, budget dead
  for the lower 128 screen lines** (`:318-323`). `d3 = screenY + 128` but treated as raw
  screen Y; `lsr.w #5` yields band+4. Sprites at screenY ≥ 96 are never budget-checked;
  0-95 charge the wrong counters; hang-in-from-above sprites escape the `bmi` guard. Soft
  heuristic (B1) effectively non-functional. Twin identical. Looks like a regression from
  retrofitting the camera-bias fold; `subi.w #VDP_SPRITE_Y_OFFSET,d0` or fold −128 into the
  band compare bounds restores it.
- **PB3. `sprSize` w/h swap — still present in `engine/macros.asm:21`, but this file does
  NOT inherit it.** `SPRITE_MASK_SIZE` (`:16`) and `CellOffsets_XFlip` (`:469-474`) use the
  correct hardware interpretation. Current `sprSize` users are all square — latent until the
  first non-square use.
- **PB4.** Minor: `:27` pad wording; `:319` "screen-relative Y" factually wrong post-fold
  (see PB2); `.band_limit_pop` note names DrawRings but mask insertion is also skipped
  (currently harmless).

### Checked and already fine

Index-register hygiene clean throughout; emit dispatch fall-through ordering optimal
(unflipped first); per-piece loop fully unrolled per flip variant, zero JSR per piece —
architecture right, H2 is refinement; camera bias fold good (modulo PB2); d5 byte
increments word-clean; stack balance on empty-band path verified all routes; word-stored
SST addresses correct; SAT overflow impossible (d5 capped at 80 across pieces+masks+rings);
scanline counter 8-byte clear over 7-byte array is explicit pad; a5 as band counter is the
right trade; register contracts hold (Draw_Sprite preserves a0/d7; attributes match bodies).

**Top 3 by expected value: PB1 (correctness), H2, H1. Fix or re-document PB2 before anyone
tunes budget constants.**

---

## 5. engine/objects/core.emp

### High-impact conceptual

**1. `.run_culled` reloads `Camera_X`/`Camera_Y` from absolute RAM for every live entry, and
the abs-value cull is branchy — `:497-511`.** ~50c/axis × 2 × every live dynamic entry.
Fixes: (a) cache camera in d5/d6 at entry, reload only after each `jsr (a1)` — culled
entries (the majority) pay `sub.w d5,d0` (4c) vs 12c; (b) branchless window check: `sub.w
d5,d0` / `addi.w #CULL_DISTANCE_X,d0` / `cmpi.w #2*CULL_DISTANCE_X,d0` / `bhi` — kills the
`bpl/neg` pair. **~10-12c/axis per live entry → ~200-350c/frame at 20-25 objects, scaling
with count.** Verify: camera only moves via dispatched object code (reload-after-jsr
preserves semantics); window math at 16-bit wraparound (same trick as S3K
`Check_Object_Range`); `Sst.x_pos` word read at +2 unchanged.

**2. `DeleteObject` zeroes the live-list entry by linear scan — `:241-273`.** Up to 40
words (~18c/entry → ~720c worst) + 8 pending. "Deletes are rare" per frame on average, but a
delete storm (boss, despawn sweep, multi-badnik explosion) is O(n·m): 20 deletes ≈ 7,000+c
in one frame. Alternative: store the slot's live-list index (tag bit for pending) in a spare
SST byte at append time → O(1) delete. Compact/Drain rewrite the backpointer as they move
entries (~8c/kept entry). Verify: backpointer correct across the latch path
(pending→live), LIFO same-frame realloc, and the §6 "exactly once" invariant (the DEBUG
sweep at `:374-396` rails exactly this). Only if delete storms show on the lagometer.

### Medium

**3. `.run_always` builds the bank word before testing for an empty slot — `:458-462`.**
44c/empty slot; reorder to test-first saves 8/empty at +8/occupied. At ~18 empty / ~8
occupied ≈ ~80c/frame net. Verify flag dependence (beq must test the loaded word).

**4. `RunObjects` sweeps System and Effect pools as two `.run_always` calls (`:429-437`)
while `RunObjects_Frozen` already merges them (`:596-598`), adjacency link-enforced by the
ensure at `:22`.** Merge in RunObjects too: ~54c/frame, and consistency. Verify: only
address-order dependency (preserved); update the ensure message (`:17-22`) which scopes
adjacency to Frozen only.

**5. Missed tail calls (conventions §2.8):** `:451-454` — second `jbsr` + rts → `jbra
DrainDynamicPending` (~24c on reconcile frames; keep the `.no_reconcile` rts); `:598-599` —
`jbsr .frozen_fixed / rts` → `jbra` (~24c per frozen frame).

**6. `ObjectMove`/`ObjectMoveX/Y` as jsr targets — `:619-657`.** ~100-130c bodies behind a
34c jsr/rts — ~25-30% call overhead per moving object per frame. An `.emp` inline macro for
hot object code removes it. Caller-side change; noted for the record.

**7. `DrainDynamicPending` append loop uses indexed addressing + per-entry abs RMW counter —
`:359-365`.** Cursor + register count + one `add.w` after the loop saves ~20+c/entry.
Latch ≤8 entries, drains only on saturated frames — low absolute value, but it's the
conventions' own §2.7 BAD pattern. Verify: count not read mid-loop (it isn't); DEBUG block
sees final count.

### Micro

**8. `move.w #imm,dN` → `moveq`:** `:421` (=1), `:431` (=7), `:436` (=15) per-frame ×3 ≈
12c/frame; `:570`, `:597` frozen; `:58,68,377` init/debug. If pools merge (finding 4), 23
also fits. d7 upper word never read.
**9. `clr.w` RMW on memory — `:253, 271, 368`.** d0 dead at the hit sites — `moveq #0,d0` +
`move.w d0,-(a1)`. Rare paths; consistency.
**10. `DeleteObject` pool-detection branch order — `:206-217`.** Dynamic deletes pay 3
cmpa+branch (~34c) before `.dynamic_pool`. If profiling shows dynamic dominating, reorder
(test System_Slots first, `bhs .upper_half`). ~12c per dynamic delete. Not blind.

### Possible bugs / comment mismatches

**11. `clobbers` omit d7 on both dispatch procs** (`:412`, `:567`) — both write d7
(`:421,431,436`; `:570,597`). Should be `d0-d7/a0-a6` or documented; per conventions §10 the
attribute is compiler-verified from the write set — either the verifier has a gap or these
were grandfathered.
**12. `AllocDynamic` `.latch_full` rollback leaves a stamped `slot_tag` byte in a freed
slot** (`:107` vs `:143-146`) — breaks the "freed slot is all-zeros" state on this rare
path. Harmless today; move the `slot_tag` write after the full-count checks.
**13. `Debug_AssertObjLoop` comment overstates the check** (`:532-534, 550-553`) — rail only
verifies a0 ∈ Object_RAM and d7 < NUM_DYNAMIC, not "a0 = own SST"; a repointed a0 skews the
sweep silently. Fix comment or strengthen rail (DEBUG-only saved-copy compare).
**14. `:120` full-count check uses `bne`, not `blo`** — `blo` is same cost and fails closed
into the latch if the count is ever corrupted past NUM_DYNAMIC.
**15. Header byte counts (`:6`, plain 0x1C4 / debug 0x2EC)** unverifiable in a no-build
review — re-check against the gates when touching the file.

### Checked and already fine

Dynamic walk via spawn-order live list (empty slots cost zero; mid-walk hazards correctly
reasoned + DEBUG-railed); O(1) LIFO free-slot stacks with correct rollback (modulo #12
cosmetic byte); a2 save/restore around dispatch is the cheapest shape given the contract;
`moveq #0` + move for Spawn_Count; `ObjectMove` 16.16 apply is canonical minimum
(fraction-word carry chain forbids the split); `movea.w` sign-extension build-guarded
(`ram.asm:486-487`); `InitObjectRAM` fine (init-only); `clear_longs` comptime unroll
near-optimal within its clobber contract; quiet-frame reconcile gate O(1); frozen pass
already merged-sweep + preserve-contract-exploiting.

---

## 6. engine/objects/collision.emp + engine/level/collision_lookup.emp

(Terrain lookup reviewed together with its tail target `Tile_Cache_GetCollision`.)

### collision.emp — High-impact conceptual

**1. The system+effect fixed sweep scans 24 slots per player even when zero are
collidable.** `:166-172`. ~40c/empty slot × 24 × 2 players ≈ **~1,900c/frame** in the common
case. Maintain a `Fixed_Collidable_Count` word (inc/dec at spawn/delete of system/effect
slots with nonzero `collision_resp` — cold paths in core), skip the segment with
`tst.w`+`beq` when zero. Or a second small live-list. **~1.5-1.9k/frame.** Verify: every
spawn/delete/`collision_resp`-mutation path updates the counter (incl. `Object_ClearAll`style resets); no object clears `collision_resp` in place without bookkeeping.

**2. The `tst.w Sst.code_addr(a3)` gate in the dynamic segment is likely redundant.**
`:40-41` spliced at `:159`. Delete's dynamic path zeroes both the list entry and the SST,
and the walk already null-guards the entry — but `CompactDynamicLive` defends against
"dead-code_addr entries", implying a path that clears code_addr without list-zeroing.
**If handlers may delete OTHER objects mid-walk, the gate protects exactly that case and
must stay — verify before touching.** If removable: ~20c × live candidates × players ≈
~480c/frame at 12 objects. Needs a comptime segment flag on `touch_test_target` (keep gate
for fixed, where it IS the empty-slot filter).

**3. Not-a-finding: the scan is O(players × candidates), not O(N²).** No object-vs-object
pairing; bucketing infrastructure would cost more than it saves at ≤64 candidates ×2
players. No change.

### collision.emp — Medium

**4. Player width/height reloaded from RAM per candidate** (`:47`, `:57`) — loop-invariant
per player, 16c/dimension/candidate. Load once per player into a5/a6 (handlers already must
preserve them). ~300-400c/frame at ~25 candidates, minus one movem save/restore (~60c).
Verify: loads go through a data reg (`moveq #0`+`move.b`+`movea.w`) so 0-255 widths are
safe; update clobbers + twin lockstep.

**5. Coarse delta-first rejection before width loads** (`:46-51`) — reject far candidates in
~48c instead of ~80c, +24c for near ones. Win only if most candidates are far — **measure
first** (§8.2). Template is shared with `rings.asm` — must not silently change ring
behavior.

**6. Segment-shared template prevents per-segment gate tuning** — fixed sweep's discriminant
is `code_addr==0`; dynamic's is `collision_resp`. Comptime segment flag; ~20c per
non-collidable live object. Fallback if finding 2 is void.

### collision.emp — Micro

**7.** `:126` `move.w #NUM_PLAYERS-1,d7` and `:167` (=23) → moveq.
**8.** `:142` `clr.w interact_off()(a2)` RMW → hoisted zero reg (conventions consistency).
**9.** `:40`/etc. `tst.w Sst.code_addr(a3)` — offset 0: check the .lst whether the zero
displacement folds to `(a3)` (8c vs 12c); if both twins already emit `(An)`, non-finding.
**10.** Dispatch double-jump (`:82-85` + bra.w table `:191-205`) costs +10c/overlap — the
stride is declared load-bearing ABI; **not worth changing**, noted for completeness.

### collision.emp — Possible bugs / mismatches

**11.** `touch_test_target` header (`:34`) says "clobbers d0-d4, a0-a1" — overlap path also
writes **d5** (`:92`, the Y-cache reload, by design). Comment fix.
**12.** Unused import: `NUM_DYNAMIC` (`:7`). Lint-level.
**13.** `Touch_Solid` exact-center tie (`:271-273`): `delta_y == 0` resolves as "player
below" (snap under, y_vel untouched). Stub-era; decide the `beq` tiebreak when Touch_Solid
becomes real. Flag only.
**14.** Documented `delta == -32768` `neg.w` hazard inherited from aabb template
(`aabb.emp:63-66`) — unreachable via current callers; re-check for any future unbounded
caller.
**15.** a4 saved via single move.l pair, invisible to the movem-based S2-D6b preserves
check. Correct as declared; noted.

### collision.emp — Checked and already fine

Live-list dynamic walk (empty slots zero; entity window is the spatial prune — right
design); d4/d5 player-position caching with fresh-cache fast path; `movea.w` stashes of
combined_w/delta_x; jump-table dispatch; AABB math shift-based, no mulu/divu; movem fires
only on overlap; dbf loops + correct fall-through senses on the hot rejection path;
unrolling the 24-slot sweep considered and rejected (finding 1 removes the loop instead);
Touch_Solid integer-word writes into 16.16 coords correct.

### collision_lookup.emp (+ Tile_Cache_GetCollision) — High-impact

Current per-lookup ≈ **~322c** (~114 in `Collision_GetType`, ~208 in the tail). At 6-20
calls/frame ≈ 2-6.5k cycles/frame.

**1. Fuse `Collision_GetType` with `Tile_Cache_GetCollision`** — the four-compare bounds
check (`:23-36`, ~80c) re-reads what the tail re-derives (`tile_cache.emp:157-167` re-reads
`Cache_Left_Col`/`Cache_Top_Row`), plus the `jbra` (10c). Replace with the unsigned-span
trick producing the window-relative coordinate as a side effect:

```
lsr.w #3, d0
sub.w Cache_Left_Col, d0
cmp.w Cache_Col_Span, d0        ; span = Head-Left+1, maintained at fill/slide
bhs .cgt_air                    ; negative → huge unsigned → rejected too
```

then continue straight into wrap+index with d0/d1 already relative. Eliminates ~40c of
compares/branches + ~24c duplicate subs + 10c jbra. Combined with #2-3: **~80-100c/call
(~30%) → ~600-2,000c/frame.** Cost: `Cache_Col_Span`/`Cache_Row_Span` RAM words written at
every edge-var commit site (`Tile_Cache_Init`, per-column/row commits at
`tile_cache.emp:844,873,944,985`, H/VSlides). Verify: ALL writers found (fill commits
mid-frame); `Tile_Cache_GetCollision` has no other callers (grep found none — re-verify);
`Tile_Cache_GetTile` same treatment or consciously left; twins + byte gates; DEBUG-boot
self-tests.

**2. Precompute the halved collision-row origin** — `tile_cache.emp:165-167` does
`move/lsr/add` (24c) per call on a value that changes only at V-slides/init: store
`Cache_Origin_Coll_Row` (= origin>>1). **~12c/call**, frees d2. Verify: every
`Cache_Origin_Row` writer updates it (`Init:479`, VSlide, VSlideUp).

**3. Replace ×80 shift-add with a build-time row-offset table** — `mul_cache_stride` (40c) →
`add.w d1,d1; move.w Row80Tbl(pc,d1.w),d1` (18c; 120 bytes ROM shared with GetTile).
**~22c/call**, and removes the scratch-register requirement (the reason layer rides in d3).
Conventions §1.8/§2.1. Verify PC-relative reach; CopyBlockColumn's inline ×80 is loop-setup —
leave it.

**4. Caller-side caching: the extension probe repeats the entire lookup for a cell one step
away** — `player_sensors.asm:83-121`: up to 2 calls/probe at exactly ±16px, ~330c each.
Options (API change, game-side file): (a) pointer-return variant — `out(a0)` = resolved cell
byte address; extension cell is ±TILE_CACHE_STRIDE or ±2 bytes away (~14c) **when no
wrap/window seam is crossed** — the seam fallback is the hard part and the thing to prove
(naive offset walks off the circular buffer); (b) cheaper/safer: pass the already-shifted
tile col/row between the two calls. **~300c per extension call — the biggest number in the
pair if the seam handling is right; also the riskiest.**

### collision_lookup — Medium/Micro

**5.** Layer plane-select branch (`tile_cache.emp:175-178`): carry the layer as a pre-scaled
word (0 / TILE_CACHE_COLL_SIZE) via a 2-entry table at probe setup → single `add.w d3,d1`
(~10-16c/call). Touches the register convention + every d3 producer — only bundled with #1.
**6.** `lea Tile_Cache_Collision,a0` is absolute-long because the buffer lives in the
`$FFFF0000` phase — unavoidable; noted so nobody "fixes" it to `.w` and crashes.
**7.** Wrap-branch sense: current shape already cheapest for an 80-column buffer. No change.

### collision_lookup — Possible bugs / mismatches

**8.** `Collision_GetType` declares `clobbers(d1-d3/a0)` but neither it nor the tail writes
d3 (deliberate contract reservation, but the callee's attribute disagrees — make them
consistent; conventions §10 sources attributes from the write set).
**9.** Evenness invariant (`Cache_Top_Row`/`Cache_Origin_Row` even) is load-bearing and
enforced only by convention — DEBUG asserts at the write sites recommended.
**10.** Signed `blt/bgt` on world tile coords — fine while world pixel X < $8000; re-check
in the mega-act/floating-origin work.

### collision_lookup — Checked and already fine

Shift-based, no multiply; `jbra` tail call; air-reject ordering (all four compares fall
through in-window); single conditional subtract for circular wrap (verified against
constants: max 158 < 160, max 58 < 60); indexed final fetch at the leaf is the right trade;
`moveq #CTYPE_AIR`; layer-in-d3 rationale matches code.

### Suggested priority (both files)

1. Fixed-sweep skip counter (collision #1) — biggest guaranteed win, smallest risk.
2. Lookup fusion + span vars + row table + halved origin (lookup #1-3) — one coordinated
   rewrite of the hot leaf, ~30%/call.
3. Player dim caching in a5/a6 (collision #4).
4. Extension-probe pointer caching (lookup #4) — largest potential, needs careful seam
   design; after #2 settles the leaf's shape.
5. Rest micro or conditional on verification (code_addr gate, delta-first reorder — measure
   first).

---

## 7. engine/objects/animate.emp + engine/objects/rings.emp

### rings.emp — High-impact conceptual

**R1. The priority-1 question — layout scan is already incremental. No finding.** Spawning
is the entity window's ratchet; collected rings are removed immediately (swap-with-last) so
they cost zero afterward. This is the sorted-layout + persistent-cursor O(delta) design.
Worst case at the 128 cap ≈ ~10k (DrawRings) + ~10k (RingCollision, 1 player) ≈ 17% of frame
(est.) — acceptable; R2/R3 cut a meaningful slice.

**R2. `DrawRings` — the camera-bias fold is on the wrong side: fold for the CULL, not the
SAT write.** `:177-217`. The fold (comment `:171-176`) makes `sub.w d6,d2` yield final SAT
X — then `:206-207`/`:214-215` spend `move.w d2,d0` + `addi.w` **per ring per axis** to undo
it for the cull, which runs for EVERY scanned ring; the SAT write only for visible ones.
Invert: bias d6/d7 by `Camera − RING_WIDTH/2` so d2 is directly the cull value (cmpi
constants unchanged), convert to SAT only on the emit path. Strictly non-negative;
**~12-24c/ring, up to ~2.5k/frame at a full buffer.** Verify: (a) cmpi bounds literally the
same; (b) the X=0 sprite-masking test (`:226`) must move AFTER the SAT conversion; (c)
update the fold comment, which currently argues the opposite tradeoff.

**R3. `RingCollision` — loop-invariant player dimensions reloaded per ring.** `:283-295`.
~20c of setup per iteration + template `add.w`s — player width/height and the ring's 16px
are constant across the whole loop. Precompute combined dims once per player, pass as
pre-combined `cdim`. **~24c/ring/player on X, ~24 more on X-passers; ~3k/frame at 128
rings.** Needs an `aabb_axis_test` variant taking `cdim` preloaded (current template
consumes adim/bdim, `aabb.emp:15-17`). Register plan: d3/d0 combined dims, d1 delt, d2 stmp;
collect path clobbers d0-d3 → re-derive after collect (rare, ~30c), reload section/list from
`4(a3)/5(a3)`. Verify: aabb alias ensures (`aabb.emp:52-53`); collect path reloads
everything; twin lockstep.

### rings.emp — Medium

**R4.** Sprite-cap check at loop top for every ring incl. culled (`:196-197`, ~16c/ring) —
move to just before the SAT write. Behavior change: at cap, remaining buffer is
scanned-and-culled instead of abandoned (already an overflow frame). Verify against
`sprites.emp:451-457` (B2): the invariant is "no EMIT at cap", not "no scan at cap" —
preserved.
**R5.** Pack size+link into one word write via a biased d5 (`:222-224`): d5 carries
`$0500|count`; pair becomes `addq.b #1,d5` + `move.w d5,(a4)+`. ~12c/emitted ring −16 fixed;
wins from 2 visible rings. Verify: d5 is in-out shared with `Render_Sprites` (`-5(a4)`
fixup + `Sprites_Rendered` at `sprites.emp:428-432`) — unbias on EVERY exit path incl. early
`.done`; link semantics unchanged.
**R6.** `RingBuffer_Add` `andi.b #$FE,ccr` (20c) → `moveq #0,d4` (4c) clears C too; must sit
after the branch join exactly where the andi is (the `.not_record` path arrives with C
possibly set from `cmp.b/bls`). `.full`'s `ori.b #1,ccr` (20c) → `moveq #-1,d4; add.b d4,d4`
(8c), cosmetic. Spawn-time.

### rings.emp — Micro

- `:68-69` count RMW + reload → d4 still holds old count: `addq.b #1,d4; move.b d4,Ring_Count`
  (~8-12c). Spawn-time.
- `:56-58` ×6 via stack (24c) vs RingCollision's register chain (16c) — needs one more
  scratch (widens `clobbers(d4,a0)` — both entity_window call sites tolerate it).
- **Entry stride 6 → 8**: every ×6 chain becomes shift+add and entries long-align — but the
  per-frame loops walk by pointer (`addq #6` = `addq #8`), so this buys ~40c per
  spawn/collect, not per frame. +256 B RAM; the `ensure` pair at `:33` makes the change
  loud. Only if RAM is free — check `ram.asm` end margin.
- `:109-123` `RingBuffer_Remove`: compute `(last − remove) × 6` once, derive `a1 = a0 +
  delta` (~20c). Collect-time.
- `:160` timer reset → moveq; `:186` `lsl.w #2,d4` → `add.w d4,d4` ×2; `:259` player count →
  moveq. Once/frame each.
- `:204,212,233` buffer reads → post-increment with split skip paths (~4c/ring reaching Y
  test); only if touching the loop for R2.

### rings.emp — Possible bugs / mismatches

- `:249` header cites `EntityWindow_EntryForSection` as "d1/a0" — it also writes **d0** (its
  output, `entity_window.emp:605,608`), and its own `clobbers(d1,a0)` omits d0 despite the
  tranche-3 rule. Harmless here (d0 dead); fix both the citation and the contract.
- `RingBuffer_Remove` leaves the vacated last slot stale (`:125-126`) — all consumers bound
  by `Ring_Count` (verified incl. the DEBUG nodup scan); noting for future whole-buffer
  debug tools.
- Cull boundary inclusive-by-one (`bhi` at `:209,217`): one sprite of slack at the exact
  edge — standard classic-engine behavior, documented not bugged.

### rings.emp — Checked and already fine

Buffer-only design + immediate collect removal (the R1 concern); global spin timer + attr
computed once per frame; rolling a3 + backward iteration vs swap-with-last removal verified
(removal only rewrites an index ≥ cursor, already visited; both-players case re-derives
count); `tst.w code_addr(a2)` correct (word field at Sst+$00); x_pos integer-word extraction
correct; aabb $8000 note bounded by the window; dbf/moveq/pointer-walk/X=0 guard per
convention.

### animate.emp — High-impact

**A1. No script re-parsing per frame — steady state lean (~100c/object); pointer re-derived
only on expiry (~34c).** Caching a script pointer in SST would buy little. **However:** the
common *static looped object* (single-frame script) pays ~150+c per expiry to change
nothing. A2/A3 = the cheap 80% fix; the 100% fix (static-art objects don't call
AnimateSprite, or a "held" sentinel parks the timer) is a game-side authoring pattern —
docs note, not engine change.

**A2. Dirty-check `mapping_frame` before `RefreshSpritePieceCount`.** `:100-102`.
`.set_frame` unconditionally writes + calls Refresh (~60-70c) even when the frame is
unchanged — every expiry of a single-frame loop, every same-frame `AF_BACK`. `cmp.b
Sst.mapping_frame(a0),d0; beq.s <rts>` costs ~14 when changed, saves ~60 when not. Verify:
`prev_frame` ($24) is the DPLC field, NOT what Refresh keys on; confirm nothing relies on
`sprite_piece_count` being rewritten when the frame value is unchanged (an object poking
`mappings` mid-anim would now miss a refresh; check `player_common.asm:718`).

### animate.emp — Medium

**A3. Tail-call `RefreshSpritePieceCount` from `.set_frame`** (`:100-104`) — textbook §2.8
tail call; split labels (timer path's `bpl .done` keeps its own rts). ~24c per
frame-advance. Combine with A2.
**A4. Event handlers RMW `anim_frame` in memory, then `.after_event` reloads it**
(`:213,226,232,249 → :252-254`) — d1 already holds the pre-event frame: `addq.w #N,d1` per
handler, one write-back in `.after_event`. ~16c/event. **Exception:** `.evt_callback` (the
callback may clobber d0-d2) keeps the memory form. Verify: scripts < 256 bytes so word addq
can't diverge from byte semantics; every handler exits through the write-back.

### animate.emp — Micro

- `:85-86` timer check: `bmi .expired` + inline rts makes the common not-expired path
  not-taken (2c/object/frame); only with the A3 restructure.
- `:123-124` `neg.b` → `not.b` maps $FF→0, drops the `-4` displacement; cycle-neutral,
  2 bytes smaller. Cosmetic.
- `:270-271` null check idiom is correct as-is (movea doesn't set flags).
- The five duplicated fetch-and-dispatch blocks are deliberate speed-over-size — do not
  common up.

### animate.emp — Possible bugs / mismatches

- **RF_* comment expressions misuse bit numbers as masks** (`:74`, `:77`, header `:73-75`):
  `RF_XFLIP|RF_YFLIP` = 3 as literally written (bit numbers 1,2), not $06. Code correct;
  comments should read `(1<<RF_XFLIP)|(1<<RF_YFLIP)`. Better: derive the masks via
  `function`/const from the bit numbers (both twins).
- **`.cc_back` has no over-rewind rail** (`:161-166`) — N > anim_frame+1 wraps toward $FF
  and the next fetch reads up to 255 bytes past the script. DEBUG-rail backlog / typed-script
  DSL item. Do not fix in this pass.
- Known documented hangs (frameless `.cc_end` loop `:145-150`; AF_CHANGE-to-self `:176-182`)
  already ledgered in-file.
- **`.evt_sound` exhaustive-license comment** (`:220-223`) claims `Sound_PlaySFX` clobbers
  ONLY d0 — NOT independently verified; the 2026-07-03 SFX work resized SfxChannel and moved
  contracts. Re-confirm before applying anything here.

### animate.emp — Checked and already fine

Control-code dispatch already a pc-relative jump table with pinned 4-byte `bra.w` slots;
index-register hygiene clean at all five fetch sites + `.evt_set_field` railed;
`reload_anim_timer` template correct with lockstep note; `.evt_callback` bank-address build
and `$xx00` tst.w comment correct; flip propagation unconditional-copy is cycle-neutral vs
all alternatives costed; `AnimateSprite` clobber declaration matches the write set.

### Suggested priority (both files)

1. **R2** (cull-side fold) — per-frame, strictly non-negative, one routine.
2. **R3** (hoist player dims) — largest per-frame save; aabb variant + twin care.
3. **A2+A3** (dirty-check + tail-call) — big for static looped objects.
4. **R4, A4** — small trims.
5. Comment fixes (RF_* masks, clobber lists) — zero-risk.
6. Micro, opportunistically.

---
---

# WAVE 2 — per-file reports (verbatim from the review agents)

## 8. engine/level/section.emp

### High-impact conceptual

**H1. `Section_UpdateColumns` has no idle early-out — full four-edge pass every frame**
(`section.emp:474-693`). On a frame where the camera didn't cross a tile boundary and no
streaming is pending, the routine still executes the 10-register movem save/restore (~180c,
see H2), camera loads, the act-boundary clamp, three clamp chains per horizontal edge, two
per vertical edge, four loop-entry checks, and four cross-clamp blocks — **~500-600c/frame
doing nothing**. Conventions §7.6 applies. *Proposed:* a convergence gate — after a pass
where all four `Section_*_Written` trackers equal their needed values, set
`Section_Stream_Converged`; clear it when (a) camera tile coords change (~30c compare),
(b) tile_cache commits a new Head/Left/Top/Bottom (one `sf` at each commit site —
cross-file hook), or (c) `Section_Plane_Dirty` fires. Gate check sits AFTER the dirty
check. ~450-550c on every idle/sub-tile-scroll frame (majority of gameplay); zero on
max-scroll frames — buys headroom, doesn't move the lag counter. *Verifier:* a
camera-tile-only compare is INSUFFICIENT — a pass that exits early on the buffer-full
checks (`:531`, `:583`, `:626`, `:666`) with the camera then stopping would stall streaming
forever under a naive gate; convergence must be trackers==needed. Teleport/rebase paths
must dirty the gate.

**H2. The `.not_dirty` `movem.l d2-d7/a0-a3` contradicts the declared contract and burns
~180c/frame** (`:490`, `:691`; twin `section.asm:357/558`). The proc declares
`clobbers(d0-d7/a0-a3/a5-a6)` — every caller already treats those regs as dead — yet the
common path pays save+restore ≈ 180c/frame preserving registers nobody is entitled to. a3
is saved but never used anywhere in the routine. *Proposed:* delete the movem pair.
*Verifier:* every call site for register liveness (the only per-frame caller,
`ojz_scroll_test.asm:187`, has none); consistent register state between dirty/not-dirty
paths.

**H3. Act-boundary clamp recomputed per frame from the Act struct** (`:501-508`) —
~60c/frame for a per-act constant. *Proposed:* build-time `Act.max_tile_col` word in the
descriptor (or cache to RAM at `Section_Init`). ~45-55c/frame and kills the hardcoded-shift
drift trap (B3). *Verifier:* Act struct layout consumers (structs.emp wall, generators);
teleport/act-switch re-read.

**H4. `Section_RedrawPlanes` inner loop pays a per-cell wrap compare that is loop-invariant
per redraw** (`:345-353`, `:382-389`). ~14c × 4096 Plane-A cell writes ≈ **57k cycles
(~0.45 frame)** off the ~3-frame synchronous stall; the wrap point is fully determined by
`Cache_Origin_Row`, constant across all 64 columns. Hoist segmentation out: (seg1, seg2)
counts once per redraw, two straight `move.w (a1),(a6) / lea stride(a1),a1 / dbf` loops per
part with a single `suba.w` between segments; optional 2× unroll adds ~20-30k more. Fires
at level init and cache recovery — user-visible hitch. *Verifier:* segment math for every
start_nt_row/origin_row combination incl. origin_row=0 (seg2 empty); Part A→B pointer
continuation across the seam; `.pla_next` skip paths; verify by redraw-triggered screenshot
diff, not lag counter.

### Medium

**M1. `Section_GetSecPtrXY` / `Section_FlatIDXY` — repeated-add multiply + ×66 chain
replaceable by build-time row table** (`:180-243`). GetSecPtrXY: sec_y × 14c + stack pair
(20c) + ×66 decomposition (~30c); called per frame from `entity_window.emp:747` and
`parallax.asm:79`. FlatIDXY keeps the memory operand INSIDE the loop
(`add.w Act.grid_w(a2),d0` ≈ 22c/iter, `:187-188`); called ≥2×/frame from entity_window.
Tiered: (cheap) hoist grid_w to a register in FlatIDXY (~8c/iter); (better) build-time
`Act.row_pitch = grid_w*66`; (best) per-act row-pointer table → fully O(1). ~50-200c/frame,
grows with mega-act grid heights. *Verifier:* `sizeof(Sec)==66` ensure moves with stride
changes; FlatIDXY's d2/d3/a2-preserved contract (entity_window relies on it); out-of-grid
Z protocol unchanged (entity_window void-cell logic depends on it).

**M2. Redundant double-checking between `Section_UpdateColumns` and the plane_buffer
producers (cross-file).** Per streamed column the caller checks buffer headroom (`:531`)
and clamps to cache bounds (`:511-515`, `:562-566`); `Draw_TileColumn` then re-checks BOTH
(`plane_buffer.emp:79-87`). ~50-60c/column of re-verification; ~200+c/frame at max diagonal
scroll on exactly the lag-measured frames. Same for `Draw_TileRow_FromCache`. *Proposed:*
a trusted entry point (checked public wrapper falling into an unchecked body). *Verifier:*
every other producer call site; **keep the CALLER's check and drop the CALLEE's** — the
tracker (d5) desyncs past a dropped column the other way round.

**M3. Duplicate camera-derived values inside one pass** (`:497-498` vs `:568-570`; `:517-518`
vs `:558`) — `(Camera_X+327)>>3` and `Camera_X>>3` each computed twice; d4 (never used) and
others free. ~40-50c/frame, pure CSE. *Verifier:* register lifetimes across
`jbsr Draw_TileColumn` clobbers.

**M4. Plane B blit loop unrolling** (`:438-440`) — `move.l (a1)+,(a6) / dbf` ×1024 ≈ 31k;
unroll ×8 saves ~9k off the redraw stall. Cold; bundle with H4. *Verifier:* 4096 % 32 == 0;
autoinc $02 at that point (`:435`).

**M5. `RedrawPlanes` per-column stack traffic + VDP-command rebuild** (`:304`, `:326-332`,
`:365-370`, `:407`) — column offset pushed/re-read/popped (~30c/col) though a3/a4 are
declared clobbered and unused; the `vdp_comm_reg` splice (~40c) up to twice per column
could be a swap+`move.w #const` build (~15c). ~2-3k, cold; only inside H4's rewrite.
*Verifier:* moving to a register removes the `.pla_next` stack-balance trap entirely.

### Micro

- **µ1.** `:502` dead `moveq #0,d0` before word-sized uses. −4c/frame (subsumed by H3).
- **µ2.** `:187` memory operand in the `.fxy_mul` dbf loop — hoist (part of M1 cheap tier).
- **µ3.** `:539-542` (+3 siblings) per-column push/pop pair ~24c/col — disappears if
  `Draw_TileColumn` preserved the world col; cross-file API change, bundle with M2.
- **µ4.** `:478` `clr.b Section_Plane_Dirty` → `sf` (house idiom). Cosmetic.
- **µ5.** `:337-340` `moveq #TILE_CACHE_ROWS` silently breaks past 127 rows; add
  `ensure(TILE_CACHE_ROWS <= 127)`. Robustness, zero cycles.

### Possible bugs / comment mismatches

**B1. `RedrawPlanes` Out-doc vs actual d7** (`:262-263` vs `:456`): header says
"start_world_col + 63"; code sets `move.w Cache_Head_Col,d7` unconditionally — no clamp,
asymmetric with d5's left clamp. Safe today only by 80-col cache geometry; if margins grow,
`Section_Right_Col_Written` claims aliased columns as written. Fix header at minimum,
ideally add the min-clamp.
**B2.** Stale comment `:561` "clamp to cache and act bounds" — no act clamp exists there.
**B3.** Hardcoded `lsl.w #8` (`:504`) encodes SECTION_SIZE_SHIFT−3 with no derivation or
guard (file imports the constant and uses it properly elsewhere, `:421`). Derive or
`ensure(SECTION_SIZE_SHIFT - 3 == 8)`; H3 removes the site. Twin shares the trap.
**B4. `adda.w d0,a0` caps flat×66 at 32767 → ≤496 sections per act, unguarded** (`:232`).
`adda.w` sign-extends. No build-time grid-area ensure exists. Mega-act makes large grids
plausible — add a data-gen/`ensure` guard.
**B5.** Contract-vs-body: `UpdateColumns` declares clobbers yet movem-preserves on the
common path (H2 resolves); `RedrawPlanes` declares a3/a4 clobbered but never writes either.
**B6.** `Section_FillInitial` seeding comment (`:148-150`) implies a symmetry that isn't
literal; coverage is correct and gapless. Cosmetic.

### Checked and already fine

No mulu/divu; zero-fill correctly avoids `clr.w` on the VDP port and says so; buffer
reservation math exactly matches Draw_TileColumn's documented worst case; cache-miss
columns skipped before the VDP address is set (stale content survives instead of flashing —
deliberate); dbf everywhere; lea-stride in hot cell loops; Part A/B stack discipline
balanced on all paths; Plane B `vdp_comm` comptime; `cmpa.w #0` null checks correct;
interrupt masking + autoinc restore in redraw matches the VInt cleanup contract.

### Cross-file notes
M2 + µ3 need `Draw_TileColumn`/`Draw_TileRow_FromCache` API decisions — coordinate with the
plane_buffer findings. H1's gate needs one-line `sf` hooks at tile_cache's edge-commit
sites. `Draw_TileColumn` recomputes the full cache-origin pointer per call
(`plane_buffer.emp:91-103`) — identical math to `RedrawPlanes:306-322`; a shared helper or
batched multi-column entry would amortize teleport-refill bursts.

---

## 9. engine/sound/sound_api.emp

### High-impact conceptual

**H-1. `Sound_PlayMusic` has no "previous request consumed" gate — a repost landing
mid-`Snd_LoadSong` both tears the param block and silently loses the new request.**
`sound_api.emp:205-221` writes the 6-byte param block + trigger under one bus hold; the
comment (`:171-173`) claims the Z80 can't read a half-updated block — but that only covers
a Z80 that hasn't STARTED reading. The Z80 handler reads the param block throughout the
load (`z80_sound_driver.asm:1125`, `:1166`, `:1169-1171`, `:1183`) and clears
`SND_REQ_MUSIC` only at the very END (`:1373-1374`). A `PlayMusic(B)` while the Z80 is
mid-`Snd_LoadSong(A)` (a window of order-of-ms) → mixed A/B block (garbage stream) AND the
end-of-load clear wipes B's trigger — the new song never plays. Reachable with two calls
~1 frame apart with unlucky phase. The file already contains the correct pattern for SFX:
`Sound_DrainSfxRing`'s `tst.b SFX_SLOT / bne .dr_done` gate (`:320-321`) is immune.
*Proposed (cross-file, flag for design sign-off):* (a) Z80 side — `Snd_LoadSong` snapshots
the 6-byte block into driver-local RAM and clears `SND_REQ_MUSIC` immediately at entry;
(b) 68k side — `Sound_PlayMusic` spins (bus-held probe, Sound_Init pattern) until
`MUSIC_SLOT == 0` before writing. With (a), (b)'s spin is bounded by the ~20-instruction
snapshot. Either half alone shrinks but does not close the window.
*Verifier:* every `SND_MUSIC_PARAM_*` read moves to the snapshot; the mid-drum
`SND_ROM_BANK` guard (`:1125-1135`) reads the snapshot bank; the 68k spin releases the bus
between probes; latest-wins preserved for posted-not-started.

### Medium

**M-1. `Sound_Init` probe loop starves the Z80 during the boot handshake** (`:132-142`) —
~22 cycles between release and next stop-request gives the Z80 a handful of instructions
per probe; boot handshake stretched ~1-2 orders of magnitude (~0.1s scale, boot-only,
forward progress guaranteed). Insert a short delay (~500c spin) after `start_z80`. Cost:
one clobbered register (currently `clobbers()`). *Verifier:* nothing times boot against a
prompt return; keep the release-between-probes anti-deadlock shape.

### Micro (cold/lukewarm; mirror in the twin)

- **µ-1.** `z80_bank` (`:89-96`): ~66c → `move.l/add.l/swap` ≈ 16c (consumer reads only .b;
  ROM ≤ 4MB). ~50c, cold.
- **µ-2.** `z80_window` (`:97-103`): `(x & $7FFF) | $8000` ≡ `x | $8000` on low 16 bits and
  both consumers use only .b/.w → `move.w/ori.w` ≈ 12c vs ~36. Document dirty high word.
- **µ-3.** `Sound_PlayRing` toggle (`:344-346`): move/eori/move (~32c) → `bchg #0,mem`
  (~20c) with branch flipped to `bne .left` (bchg Z = OLD bit; old=1 ⇒ new=0 ⇒ LEFT —
  matches `ram.asm:411`). Warmest path in the file (ring bursts).
- **µ-4.** `Sound_StopMusic` (`:363`): `move.b #SND_MUSIC_STOP,d0` → `moveq #-1,d0`
  (PostByte writes only d0.b). Also fixes the misleading comment (CM-3).

### Possible bugs / comment mismatches

- **PB-1.** The mid-load repost race — see H-1. Latent; needs the cross-file design pass.
- **PB-2. Lost-command race on all `Sound_PostByte`-class slots (ping/fade/tempo/sample).**
  Z80 poll is read → call handler → clear: a 68k post landing between read and clear is
  wiped — contradicts the stated latest-wins model (`:9`). Cheap Z80-side fix: clear the
  slot immediately after the read (handler works from the copy in `a`). SFX immune; music
  is PB-1.
- **PB-3.** Unstated single-producer/main-loop-only invariant on the SFX ring — verified
  all current callers are main-loop; a future ISR caller would race. One header line wanted.
- **CM-1.** "once/VBlank consume" (`:229`, `:296`) is stale — poll also runs from the
  Timer-A tick during DAC streaming. Conclusions hold; wording should say "once per driver
  frame".
- **CM-2.** `engine/sound_constants.asm:23` still annotates `SND_REQ_SFX` "reserved
  (Phase 1C)" — live SFX mailbox since Phase 5a. Adjacent file, load-bearing slot map.
- **CM-3.** "`$FF` (out of moveq's signed range)" (`:24`, `:363`) — misleading;
  `moveq #-1` puts $FF in d0.b, which is all PostByte consumes.
- **Recency check:** no stale claims found from the SfxChannel-68/7-bit-priority work; the
  "3-deep priority queue" claim matches current `sound_sfx.asm`; `$33/$34` mirrors are
  ensure-guarded.

### Checked and already fine

Z80 stop/start pairing on EVERY path (no early-out leaks a held bus); interrupt masking
around every hold, and the vblank stopZ80 pairs can't nest; grant spin hardware-bounded;
stop-duration already minimized (all derivation before the hold; hold covers 7 byte
writes); param-first/trigger-last matches the Z80's LE reads; byte-only Z80 RAM access;
`Sound_PlaySFX` index hygiene exemplary + data-before-pointer commit + DEBUG flag-threading
correct; drain gate closes SFX races; ring plumbing matches RAM layout; `andi.l #$FF`
sanitizer needed; all ensure guards cover the mirrors; no banked in-frame 68k code.

---

## 10. engine/objects/dplc.emp + load_object.emp + frames.emp + objdef.emp + sst.emp

### dplc.emp

**D1 (high).** Per-entry `movem.l d2-d4/a2-a3` save/restore ≈ ~100c/entry — but
`QueueDMA_Important/Deferrable` clobber only d0-d4/a1-a2, so loop state can live in
preserved regs (cursor a2→a4, dest d2→d5, count d4→d6) and the movem disappears: **~96c/
entry, ~575c per 6-entry Sonic frame change**. Widens the clobber contract to d5-d6/a4 —
legal under the object contract (everything but a0/d7); verify player-path callers
(`sonic.asm:28`, `test_animated.asm:46`, `test_player.asm:259`), update headers + attrs +
twins, confirm carry reaches `bcs` untouched, oracle-soak ObjectTest + Sonic cycling.
*Zero-risk fallback:* drop a3 from the movem set (QueueDMA preserves it) — ~16c/entry, no
contract change.

**D2 (medium).** Entry decode: count extraction + later `lsl.w #5` ≈ 60c → direct byte
length via `andi.w #$F000 / lsr.w #7 / addi.w #$20` ≈ 40c (bits 15-12 = count−1 →
(entry&$F000)>>7 = (count−1)×32; +32 = count×32). ~20c/entry. Boundary-test count 1 and 16.

**D3 (medium, caller-side).** `Sonic_LoadArt` pays full pointer setup + call every frame;
the frame-unchanged early-out fires inside the callee (~100c/frame/character on the
no-change path). Hoist the `mapping_frame != prev_frame` compare into callers via a
comptime template (~65c/frame/DPLC character); the in-callee check stays (drop-retry
semantics depend on it and survive — stale prev_frame keeps the caller's check true).

**D4 (BUG, build tool — the standing overflow-guard question ANSWERED).** The historical
entry-splitting fix IS present (`tools/dplc_layout.py:29-33`, applied at `:205`). The
2026-06-17 stray-fix guard (build-fatal on count>16 / start>4095) is ABSENT: `write_dplc`
(`:146`) silently masks. Worse: `merge_adjacent_entries` (`:120-122`) merges past 16 tiles
with no cap, and the `--merge-only` CLI path (`:190-198`) writes that straight through with
NO split — a 20-tile merged entry wraps to 4 tiles → silent art corruption. Re-add the
raise in `write_dplc` AND cap the merge or split its output.

**D5.** `adda.w (a2,d0.w),a2` (`:43`) sign-extends — DPLC file ≥ 32KB rebases backwards.
Make it a fatal check in the emitting tools.
**D6.** Partial-enqueue commit via the 128KB-split edge (inherited, documented in
dma_queue): a split with one free slot enqueues half and returns carry clear → prev_frame
commits with half the art stale for one frame. Documented out-of-scope; on the record. The
retry design re-enqueues already-delivered entries (idempotent, bounded, doubles that
frame's DMA bytes).

*Fine:* prev_frame committed only after all entries enqueue with per-entry carry checks
(the historical stale-art bug correctly fixed); comptime single-sourcing of the two
priority variants; clobber attr matches body; `andi.l`+`lsl.l` source math optimal.

### load_object.emp

**L1 (high).** The `movem.l d0-d2/a1` around AllocDynamic ≈ ~84c/spawn — but AllocDynamic
is `clobbers(d0) out(a1)`: d1/d2 SURVIVE. Two register stashes (`movea.l a1,a2` +
`move.w d0,d3`) replace it: **~76c/spawn**, ~300-450c in an entity-window spawn-storm
frame. Fail-path note: today `.alloc_fail` restores a1=template; header promises nothing
and no consumer reads a1 on fail — MUST re-verify before dropping the restore. Also verify:
AllocDynamic's write set after any core.emp change; entity_window's documented
"Load_Object preserves d4-d7/a0" survives (restructure touches d0-d3/a1-a3 only); twins;
oracle-verify list spawn + edge-crossing storm + pool-exhaustion fail.

**L2 (micro).** `Load_ObjectList` loop rotation removes an unconditional 10c branch per
entry. Init-time; opportunistic.
**L3.** List-data bits 13-15 trusted by comment only — a DEBUG assert on
`d2 & $E000 == 0` for the list path would check it. Low severity.

*Fine:* 6×`move.l` burst copy optimal (movem alternative ~equal + 6 regs);
swap/clr/move.l position seeding minimal; `rol.w #4` flip fold ensure-guarded; inline
piece-count init deliberately cheaper than calling Refresh (frame always 0 at spawn);
fall-through success paths.

### frames.emp

**F1.** The `{off}.w` index sign-extends — mappings ≥ 32KB indexes backwards. Fatal check
belongs in the mappings build tool. Otherwise fine (3 lines, comptime single-source of the
+4 offset, spawn/frame-change only).

### objdef.emp

**O1.** `vram_art` tile refinement `0..$1FFF` (`:35`) already permits $800..$1FFF silently
setting the H/V flip bits (tile index is bits 0-10; comment only claims palette-bit bleed
above $1FFF). Tighten to `0..$7FF` (engine has 2048 tiles) or document baked-flip intent.
Stricter than the AS twin either way. Otherwise fine: pure comptime emitter; priority
refinement reproduces the macro's fatal; 26-byte ObjDef non-power-of-two irrelevant
(direct pointers, never index math).

### sst.emp

**S1 (micro).** `ObjDef.pad` = 2 dead ROM bytes per archetype buying the clean 6×move.l
copy — correct tradeoff; leave it.
*Fine (verified in detail):* every word/long field at even offset, byte fields packing the
odd slots, `sst_custom` starts even ($2E) with even size; `code_addr` at offset 0 makes the
hottest read in the engine (`tst.w (a0)` per slot per frame) zero-displacement; size $50
non-power-of-two harmless (no runtime index×sizeof anywhere); the 30-entry extern
drift-guard chain + burst-copy ensures are the right build-fatal posture; comments verified
against consumers (dispatch bank build, RF bit map, TEMPLATE_COPY_SHIFT math).

---

## 11. engine/system/ — hblank, game_loop, controllers, math, vdp_init, types

### hblank.emp

**H1 (high).** Dispatch wrapper costs ~116c/line on top of irreducible interrupt cost
(`:18-22`: movem push 3 regs + movea.l abs.w + jsr (a0) + handler rts + movem pop). Null-
handler line ≈ 180c; at per-line HInt (the stated OJZ end-state) ≈ **40k cycles/frame ≈ 33%
of budget with the handler doing nothing**; the wrapper alone ≈ 26k/frame. *Proposed:* ROM
vector → fixed 6-byte RAM `jmp <handler>.l` trampoline patched at install (S3K pattern);
handlers become rte-terminated and save exactly what they use; `HBlank_Null` becomes a bare
rte (180 → 76c/line; a 2-reg handler saves ~56c/line ≈ 12.5k/frame). Also dissolves the
rigid d0-d1/a0 contract. **Zero handlers exist yet (only HBlank_Null at boot) — now is the
cheap moment.** *Verifier:* vector table emits trampoline address; patch atomic w.r.t. IRQ
(single move.l or IE1 off); demo+s4 boot; raster-bar profile once a real effect exists.

**H2.** Future install API must gate IE1 + reg $0A with the pointer swap — 224 null
interrupts/frame ≈ 40k cycles if a null handler is left enabled.

*Bugs/mismatches:* ENGINE_ARCHITECTURE.md:1136 claims ~20c no-effect return — understated
~8× (dispatch ≈ 160c more). No enforcement of the survive-contract on handlers (acceptable;
moot under H1). *Fine:* preserves() matches the movem pair; restore order; rte; pointer
initialized before interrupts enabled.

### game_loop.emp

**B1 (corruption-class, rare).** `VSync_Wait` (`vblank.asm:174-176`) clears `VBlank_Flag`
BEFORE setting `VBlank_Ready`. IRQ6 in that ~16c window: VInt_Lag runs (+1 lag count), sets
the flag; VSync_Wait sees it set and returns immediately → a full game tick runs with
Ready=1 → next VBlank dispatches full VInt_Level including the plane drain against a
possibly mid-fill Plane_Buffer — the exact torn-drain hazard documented at
`vblank.asm:126-136`. Fix direction: mask interrupts around the clear/set pair
(~34c/frame), which also makes the lag count exact. Desk-check all three IRQ landing
positions.
**B2.** `Lag_Frame_Count` exists only in DEBUG builds (`vblank.asm:156-158`) — confirm
deliberate; it's the engine's stated ground-truth metric.
**B3.** The .emp hard-mirrors sonic4's `gameDebugTick` expansion while the .asm twin
expands whichever game's macro is in scope (demo's is empty) — silent divergence if a
game's macro body changes; wants a kill-list assertion tied to the macro body.
*Fine:* lag accounting otherwise sound (Ready cleared on every IRQ → VBlanks landing in the
game-tick span correctly take VInt_Lag); honest clobbers; ~60c/frame loop overhead.

### controllers.emp

**B1.** Single TH-settle `nop` where S1/S2/S3K, SGDK, and plutiedev all use two (`:39,42`).
~1.0µs vs ~1.5µs settle; marginal on worn/third-party/6-button pads. **Emulators don't
model settling — oracle can never falsify this**; the project has no hardware loop. Add the
second nop per transition (16c/frame total). This is a missing-delay flag, not an
optimization target.
**B2 (observation).** TH left low between frames — harmless now; comment the idle-state
assumption when 6-button lands.
*Fine:* edge derivation correct and matches the vblank accumulate/latch protocol; port
control initialized; undriven bits masked; no stopZ80 needed around joypad reads (the
classic pattern is cargo cult — omitting is correct); L+R/U+D guard not worth touching.

### math.emp

**B1.** `Sine_Table: [u8; $280]` (`:37`) is word-read by `GetSineCosine` (`:25,27`) — even
today only by accident of preceding code length; an odd-length blob added earlier in the
section → address error. Retype `[i16; $140]` (also documents signedness) or ensure
evenness. Size check vs sine.bin (640 bytes) correct.
*Fine:* GetSineCosine is the canonical best idiom (S2 CalcSine shape); andi index hygiene;
add.w d0,d0; pc-relative reads; the addi/subi #$80 pair is required (d8 reach + clobbers()
contract both preclude the alternatives). Overlap math verified to the last word ($27E).

### vdp_init.emp

**Scope correction:** NOT init-only — `Flush_VDP_Shadow` (`:44-64`) runs every VBlank
(`vblank.asm:58`, `:124`) inside the ~4,300c VBlank budget.
**M1.** Dirty path walks all 19 slots even for one dirty bit (~38c/clean iteration →
~700+c ≈ 16% of the VBlank budget on any register-touching frame; clean fast path ~20c is
the common case — hence Medium). *Proposed:* shift-walk with early exit (`lsr.l #1,d1` /
`bcs` write / loop while d1≠0) — a lone reg-1 change goes 19 → 2 iterations (~600c). Write
order stays ascending; the btst-mod-32 ensure stays valid. Conceptual alternative if ever
critical: pending ring of ready `$8rvv` words → O(dirty) flush. *Verifier:* ascending write
order unchanged; mask cleared once; demo+s4 boot; lagometer under register churn.
*Micro:* indexed read in the loop is a wash vs (a0)+ with skip-path addq — M1 is the fix.
*Fine:* `clr.l VDP_Dirty_Mask` race-free (Flush is ISR-context; setVDPReg's ori.l is one
RMW instruction); the ≤32 ensure is the right guard; mask comment matches.

### types.emp

Pure-type module, zero bytes emitted — no alignment hazards possible here. Newtype claims
cross-check against consumers; sizes consistent. One unverified doc claim: the HitboxDim
full-dimension rationale (`:43-46`) cites aabb semantics not independently re-derived —
unverified comment, not a suspected error.

### System-cluster priority
1. hblank H1 (decide before any raster handler is written), 2. game_loop B1,
3. controllers B1, 4. vdp_init M1, 5. math B1.

---

## 12. engine/objects/aabb.emp + games/sonic4/objects/test_solid.emp, test_particle.emp

### aabb.emp

**1 (high).** Split the template into three composable comptime pieces (`combine_dims`,
`delta_abs2`, `dim_compare`) with `aabb_axis_test` becoming their byte-identical
composition (byte gates stay green; zero change at today's call sites). This cleanly serves
BOTH wave-1 consumer requests: (a) pre-combined `cdim` variant = delta_abs2 + dim_compare —
rings hoists ~24c/ring/frame on the X test alone (~35% of the reject path), ~24 more per
X-passer; collision X can't use it (target width varies) — exactly why it's a variant.
(b) coarse delta-first variant = delta_abs2 + `cmpi #bound` — collision moves the ~32c dim
setup behind the coarse gate (84 → 52 per coarse-rejected candidate, +4c for passers).
*Verifier:* default composition byte-identical (re-pin gates); variant adoption diverges
from the gate-off AS twins — mirror variant macros into aabb.inc in lockstep or defer
adoption to the Spec-5 twin kill (the split itself is safe now); the stmp-carries-2|delta|
contract between coarse and fine documented + ensure'd.

**2 (option, ABI-breaking).** Branchless interval form `unsigned(2d + c) < 2c`
(add/add/add/cmp/bhs): saves ~6-8c/test, kills the bpl, and ELIMINATES stmp (frees a
register at every splice site, deletes both ensure hazards). Costs: boundary shifts by one
at 2d = −c (not byte-lockable), destroys cdim/delt (breaking the handler ABI — though
Touch_Solid immediately halves them, so a 2×-native ABI is not absurd). Deliberate
decision, not a drop-in.

**3 (medium, correctness).** Missing `ensure(cdim != delt)` — that alias assembles clean
and compares garbage; same failure class as the two shipped stmp guards.
**4 (medium, correctness).** Missing read-only guards on `apos` (`stmp != apos`,
`delt != apos`) — `delt == apos` silently destroys the caller's cached player coordinate
IN the cache register.
**5.** The documented `$8000` edge can become a one-flag variant: `bvs.s {mlab}` after the
double (`:68`) rejects ALL |delta| ≥ $4000 including −32768, 8c not-taken, as a
`guard: bool = false` comptime param. Verify the add's V covers every case; no current
caller enables it (bytes unchanged).
**6 (micro).** Register-`bpos` variant hook — no caller exists; folds into the item-1 split.
**7 (mismatch).** `:24-28` says "the TWO branch widths stay PINNED .s" — `:62` `bpl .aov`
is unsized (only `:70` bhs.s is pinned); the .inc twin spells `bpl.s`. Bytes identical
today (reach forces .s). Amend the comment to "the mlab branch" or re-pin — the file
currently contradicts itself.
*Fine:* reject-as-taken-branch is the floor for an inline template (§2.2 can't apply);
abs shape optimal when delt must survive; lead_move conditional emission correct; boff-0
collapse is a real 4c save rings already gets; instruction ordering cycle-neutral inline.

### test_solid.emp

**1 (micro).** `TestSolid_Main` is a pure per-frame trampoline (~10c/instance/frame to
reach Draw_Sprite). If the dispatcher offset can encode an engine-side target, Init could
store it directly and Main disappears — verify dispatcher signedness + reach + any
"code_addr targets inside the object bank" invariant. Defensible as a teaching template;
add a comment so cloners don't cargo-cult trampolines into heavier objects (that's this
file's real job).
*Fine:* falls_into Init→Main (frame 1 draws without redispatch); clobber declarations
verified against Draw_Sprite; mem-to-mem subtype copy init-only; bare-label-difference .w
dispatch store is the house pattern.

### test_particle.emp

**1 (medium).** Two RMWs on the same byte in Init (`:29,32`) — RF_COORDMODE is bit 3,
priority bits 5-7, no overlap: one
`ori.b #(6<<RF_PRIORITY_SHIFT)|(1<<RF_COORDMODE), render_flags(a0)` replaces both (~20c +
6 bytes per spawn; particles spawn in bursts). More importantly this is the template new
effects clone — split RMWs on one byte is the pattern not to propagate. Verify constant
($C8) and final value in oracle.
**2 (medium, engine gap).** No `ObjectMoveAndFall`: `:47` `addi.w #GRAVITY,y_vel(a0)` RMW
then ObjectMove immediately re-reads y_vel (~15-20c/particle/frame). The file's pattern is
the best available today; every falling effect will repeat it — log the combined routine
(classic S3K shape) as engine work.
**3-5 (micro).** width/height adjacent at $16/$17 → one move.w; x_vel/y_vel adjacent at
$0A/$0C → one move.l; prev_anim($20)/prev_frame($24) NOT adjacent — the two #$FF stores
can't merge (worth knowing so cloners don't assume).
*Fine:* clobber union claim verified exact against all three callees (including the note
that the old set over-declared); jbsr/jbsr/jbra tail; clr.b on RAM fine; anim/subtype
correctly not merged.

---

## 13. Data/definition files (structs.emp, constants.emp, game data)

### engine/structs.emp — CLEAN
All Act/Sec offsets verified 1:1 against the .asm twins; drift wall complete (every named
field guarded; anonymous pad covered by the sizeof guard); no alignment hazards; grid_*_lo
placement correct per the BOUNDARY rule with the <256 claim holding transitively via
act_descriptor's ensure. Struct layout quality moot on 68000 (d16 displacement flat).

### engine/system/constants.emp
- **Consolidation claim vs reality:** `:88-91` says SECTION_SIZE_SHIFT consolidated on its
  3rd consumer — but `act_descriptor.emp:21` still carries its own local mirror + duplicate
  guard (`:26`) instead of `use engine.constants`. Migrate it or fix the claim.
- Stale line reference `:80` (ring constants now at constants.asm:446-448).
- Guard coverage 100% (all ~53 pub consts audited name-by-name); no dead definitions
  (19 sampled, all consumed); spot-checked values all match.

### act_descriptor.emp
- Duplicate SECTION_SIZE_SHIFT mirror (above).
- `:34-35` comment overstates the $8000 failure boundary — the CHECK (`<= $8000`) is
  correct (camera clamp math verified); reword so nobody "fixes" the ensure to `<`.
- The nine `ojz_sec` calls spell each blocks-symbol twice (blocks: + dict: extern) — a
  copy-paste mismatch compiles clean and fails at runtime; the Tier-3 computed-name
  extern() deferral would kill the class. The one convention-held invariant with no ensure.
- Grid-area/section-count ensure verified present (`GRID_W*GRID_H == 9`).

### test_objects.emp
Four local mirrors (VRAM_TEST_OBJ, COLLISION_SOLID/HURT, ENEMY_PATROL_SPEED) carry NO
extern drift guards — rationale is the objdef_port byte gate, which dies with the .asm
twin (Spec-5 pattern). All four values verified correct today. Add four one-line ensures
or document the guard's lifetime.

### Animation data — CLEAN
All 11 sonic script lengths hand-counted correct; AF_BACK rewind matches; ordinal drift
wall complete vs ANIM_*; even-total claims verified; particle single script + terminator +
align verified. One over-specific adjacency comment (sonic_anims `:59-60`) — each file
self-terminates with align 2, so the claim is moot regardless of link order.

### Sound data — CLEAN with two notes
- dac_samples blip bank: 2880-byte placeholder alone in a pinned 32KB window ≈ ~29.7KB ROM
  slack — known-temporary; cleanup candidate when it retires.
- mt_bank SONG_DRUMTEST/SONG_HCZ2 unguarded mirrors have a documented sound rationale
  (ifdef-gated equs); the SongTable order invariant (entry[id-1]) is comment-only — the one
  place a future computed-index ensure would pay.
- Every byte-count claim in all three files verified exact against on-disk blobs (drum-bank
  sum 30908; MT_PITCHTAB_OFFSET equals the actual blob length — the detune guard is armed;
  odd/even blob claims all check out; SFX key range/row count/zero-length banks confirmed).

---
---

# WAVE 3 — hot .asm files (no .emp twins; NO lockstep constraint)

## 14. engine/level/parallax.asm

### High-impact conceptual

**H1. Production OJZ pays the full per-line BG sampling loop on a table of zeros —
~21,000 cycles/frame computing `base + 0`.** `parallax.asm:745-764` (`.lg_line`), driven by
`ojz_default.asm:25-28` (`DeformTable_Zero`) + the macro default `deformShiftDefault=4`
(`parallax_macros.inc:120-133`). ojz_default deliberately uses the zero table to force
per-line VDP mode (mandatory, documented) — but because BAND_DSB defaults to 4 (not 15),
every band fails the `shift_b == 15 → .lp_flat` test (`:683-685`) and runs the ~94-cycle/
line sampling loop instead of the ~22-cycle flat path. **Fixes:**
- *Data-only (zero engine risk):* `deformShiftDefault=15` in the `parallax_section`
  invocation. Mode selection (per-line fill, 896-byte DMA, reg $0B) keys ONLY on table
  non-NULL (`parallax.asm:427-429`, `buffers.asm:160-162`, `parallax.asm:149-152`) — so
  per-line mode is retained and every band drops to `.lp_flat`.
- *Cleaner (engine):* a pcfg "force per-line" flag (a pad byte exists at offset 11) so the
  256-byte zero table isn't needed — must update fill dispatch, $0B shadow, AND DMA enqueue
  in lockstep; miss one and mode/length/content disagree.
**Est. ~16,000 cycles/frame (~13% of budget), zero visual change. #1 item overall.**
Verifier: data-only variant must produce no code change in s4.lst; mid-scroll max-speed
capture — band boundaries pixel-clean at arbitrary lines; reg $0B still $03; 896-byte
HScroll DMA still enqueued; re-measure with lag counter.

**H2. Flat-band fill (`.fl_line`, `:768-776`) — band spans are guaranteed multiples of 8
lines** (tops = cell×8, `:643-644`; end = 224), so an 8× unroll needs no remainder
(~22 → 13.25 cyc/line), or a movem-fill via 6 copies of d0 (~9.3/line). **~2,000-2,800/
frame** on the (post-H1) production path. Verifier: sentinel-fill Hscroll_Buffer, confirm
all 896 bytes overwritten; mid-scroll band-tear check; disabled-first-band inheritance
seed path (`:261-266`).

**H3. Everything rebuilds every frame; the dirty mechanism is dead.** `:440-446` writes
`Hscroll_Dirty_Start/End` — **nothing reads them**; `Enqueue_Dirty_Buffers`
(`buffers.asm:155-167`) enqueues unconditionally. Cheapest meaningful fix: whole-buffer
skip — compare (camX, BG vscroll, deform phases, transition state) against last frame; if
unchanged skip fill + DMA. ~5-23k cycles + 896 B DMA on idle frames; 0 at max scroll.
Either wire it or delete the dead writes. Verifier: first moving frame after idle must
regenerate (off-by-one staleness is the classic failure); deform-animated scenes never
take the skip.

### Medium

- **M1.** `Decode_Factor_A/B` call overhead + stack-borrowed scratch (`:287,292`,
  `:543-603`): d3/d4 are dead at the call sites — inline both (single caller) with d3/d4
  as scratch. ~350-580/frame at 5 bands.
- **M2.** Sampling line loops (`.lb_line` `:698-721` ~152 cyc/line; `.lg_line` ~94):
  (1) byte-cursor phase (`addq.b #1` wraps free — the Step-5 `.col` loop already does
  this, `:520,530`) −12/line; (2) dbf instead of addq/cmp/blo −8/line; (3) freed d4 holds
  the FG base, killing the swap-dance −8/line. `.lb_line` ~152 → ~110 (~9,400/frame
  full-screen); `.lg_line` ~94 → ~64. Optional: bake amplitude shift into per-band table
  copies at build time (256 B ROM each, drops ext+asr ≈ 18/line/channel). Verifier: A/B
  windy/haze scenes mid-scroll — phase, amplitude, per-band desync exact; phase+line
  crossing $FF.
- **M3.** Step 4a shadow rebuild recomputes source addresses per band (`:375-418`,
  ~220/band): three running pointers advanced with lea/addq, reset at the wrap (`:414-417`
  already detects it). ~400-500/frame. Verifier: vshift≠0 mid-vertical-scroll AND the
  wrap case; tops still clamp to 28 (crash-class if broken, `:340-344`).
- **M4.** `Vscroll_Write` (`:196-199`): 20 longs via displacement (24 cyc) vs (a5) direct
  (20) — point a5 at VDP_DATA. ~80 VBLANK cycles. Verifier: autoinc must be 2 when this
  runs (check Process_DMA_Critical exit state).
- **M5.** `Parallax_Fill_PerCell` inner fill (`:824-829`, ~38 cyc/cell) → count+dbf
  (~22/cell). Low priority — production forces per-line.

### Micro

`:315`/`:832` `adda.l #imm` → lea (the `:779` twin already uses lea); `:233`/`:140`
`move.l #0,mem` → zeroed reg; `:141-142` two adjacent byte stores → one move.w; `:509`
redundant `and.w #$FF` RMW — delete; `:440-446` dead dirty writes; `:37-38`
bsr+rts → bra (init).

### Possible bugs / comment mismatches

- **B1.** Re-crossing back into the current config's section mid-transition doesn't cancel
  the staged transition (`:120-121` new==Current → no-op while Target counts down →
  promotes the WRONG config while the camera sits in the old section). Fix: when
  new==Current and Target≠0, clear Target/frames. Verify by boundary ping-pong mid-scroll.
- **B2.** Builder uses Target_Config during smooth transitions (`:235-237`) but DMA length
  keys on Current (`buffers.asm:157-163`) and Vscroll mode keys on Current (`:188-192`) —
  cell↔line transition pairs get up to 16 frames of buffer/DMA/mode disagreement (stale
  VRAM rows ≥28). One shared "active config for mode decisions" resolver. Verify with a
  deliberate cell↔line pair, watching VRAM HScroll rows ≥28.
- **B3.** 16-frame >>4 exponential lerp ends with ~36% of the delta remaining → snap pop.
  `constants.asm:319`'s "~95% convergence" claim is mathematically wrong (that needs ~46
  frames). Lengthen frames, shrink shift, or run until delta < ε.
- **B4.** Clobber contracts wrong: `Parallax_Update` (`:217`) omits a5/a6 (clobbered at
  `:369-370`, `:632-633`); `Vscroll_Write` (`:170`) claims a5 only but clobbers d0/a0 —
  runs in the VBlank handler, MUST be fixed before trimming the ISR movem.
- **B5.** Stale comments: `:206/:211` "per-cell only" (code does per-line/transitions/
  Vscroll/per-column); `:214` "~410 cycles" (actual ~23,000 — dangerously misleading for
  lag triage); `:166` "T12 adds per-column" (it exists 8 lines down); `:629-630`/
  `:798-799`/`ram.asm:164-165` claim a vshift=0 fast path that doesn't exist (`.bands_ready`
  is a dead label); duplicated banner `:788-792`; `ram.asm:143` says ~126 bytes, actual 244
  (still /4-safe for the init wipe).

### Checked and already fine

Index hygiene clean throughout; `.lp_both` shift-register dance traced correct; Step 4a
wrap/clamp math proven (ascending tops, ≤28 clamp); Step-5 `.col` already uses the cheap
byte-wrap cursor; VSRAM emit already unrolled + §3.4 ordering honored at both call sites;
branch sizing + tail call at `:93` correct; no mulu/divu — factor decomposition matches
conventions exactly.

---

## 15. engine/system/vblank.asm + dma_queue.asm + buffers.asm

### The real budget constraint (verified)

Real NTSC VBlank window ≈ 38 lines ≈ **~18,500 cycles**. CODING_CONVENTIONS §3.3/§8.1's
"~4,300 cycles" is stale/wrong (~4× off): the engine's own `DMA_BUDGET_NTSC = 7200` bytes
(`constants.asm:123`) ≈ 35 lines ≈ ~17,100 cycles of 68k-halted DMA — only fits an ~18.5k
window. 68k→VDP DMA HALTS the CPU, so DMA bytes and CPU cycles are additive in one window.

### VInt_Level worst-case cycle inventory (estimates)

| Phase | Typical | Worst |
|---|---|---|
| IRQ entry + movem d0-a6 | 172 | 172 |
| Ready test + dispatch | ~60 | ~60 |
| Z80 flag-bracket open | ~90 | ~190 |
| Flush_VDP_Shadow | ~40 | ~1,000 |
| Enqueue_Dirty_Buffers | ~300 | ~800 |
| VInt_DrawLevel (CPU copy) | ~800 | 3,000+ |
| Process_DMA_Critical CPU | ~300 | ~650 |
| — Critical DMA halt | ~1,900 | ~4,000+ (UNBUDGETED) |
| Vscroll_Write | ~60 | ~640 |
| Important/Deferrable CPU | ~100 | ~2,900 |
| — budgeted DMA halt | small | ~17,100 |
| Z80 bracket close + controllers + tail | ~720 | ~820 |
| **Total** | **~4,500** | **~10,300 CPU + ~21,000 halt ⇒ can exceed the window ~1.7×** |

### vblank.asm

**H1. The budget only counts Important/Deferrable bytes** (`:69`, `dma_queue.asm:236-240`)
— Critical bytes (pal + sprite + hscroll + art-staging Critical from `load_art.asm:79`)
and VInt_DrawLevel's CPU time ride free. Charge everything against one budget: reset at
top of VInt_Level; Enqueue subtracts build-time constants; pre-charge the plane copy from
`Plane_Buffer_Ptr` (bytes × ~11 cyc → DMA-byte equivalents). ~50 cycles of accounting buys
an actual invariant. Verifier: DEBUG-count charged-total > budget frames vs Lag_Frame_Count
under max-scroll streaming.

**H2. CPU plane drain runs BEFORE the Critical DMA drain** (`:62` vs `:64`) — CRAM/sprite
DMA are the artifact-visible transfers if they slip past VBlank end; the drain can burn
3,000+ cycles first. Reorder: Flush → Enqueue → Critical → Vscroll_Write → VInt_DrawLevel
→ budgeted. Caveat: Critical currently inherits autoinc=2 from the PREVIOUS frame's
VInt_DrawLevel exit — add `move.w #$8F02,(a5)` before the Critical drain (~12 cyc), which
also permanently closes bug #3. Verifier: mid-fade + max-streaming frame; no CRAM-dot
flicker; VSRAM still after hscroll DMA.

**H3. ISR movem saves 15 regs; actual clobber union is 10** (d0-d3/a0-a3/a5-a6). Trim ≈
~80 cyc/frame — but VInt_Ptr is a game-facing seam: state the handler contract first, fix
Vscroll_Write's understated clobbers first (buffers bug #3), audit DEBUG+sound paths.

*Medium:* common case pays `bra.s .done` — put lag out-of-line (~10/frame); factor the
duplicated Level/Lag tail (ROM + drift-proofing; split point before the press latch);
Z80 flag brackets (~180-380/frame) are the price of the MegaPCM-2 model — recorded so
nobody "optimizes" them away.

*Bugs/mismatches:* **(1)** header `:33-35` documents "shadow flush → VSRAM → enqueue →
Critical" — the exact order §3.4 forbids; code is right, comment wrong, VInt_DrawLevel
omitted. **(2)** VSync_Wait race (already reported): the robust fix is spinning on
Frame_Counter change (monotonic, incremented by both handlers `:99/:153`, no consume-side
clear) — reordering the two stores alone opens the mirror race. **(3)** No DMA entry sets
$8F — lag-frame Critical drains inherit main-loop transient autoinc; closed by H2's
explicit write. **(4)** stale "Z80 already stopped" claims (`buffers.asm:123`,
`plane_buffer.asm:330`) — the safety model is the flag bracket now.

*Fine:* lag-frame plane-drain skip + rationale; press-accumulator latch asymmetry
deliberate and correct; VBlank_Ready clear no-race; §3.4 honored on both paths.

### dma_queue.asm

**H1.** `Drain_Budgeted_Queue` keeps the budget in RAM through the loop (`:236-240`,
~24 cyc/entry round-trip) — register-resident with write-back at the three exits: **~480/
frame worst case** in the VBlank-critical drain. Verifier: all three exits write back;
signed `ble` semantics preserved (budget legitimately goes negative on overshoot).

*Medium:* per-entry drain cost is at its floor (movep-interleaved format, zero massaging);
16-byte DMAEntry variant is marginal — only if the struct is touched anyway.
Check-before-subtract lets one entry overshoot by its full size (deliberate soft budget;
revisit only with vblank H1). *Micro:* enqueue carry plumbing and stubs fine; the
interrupt-masked enqueue span (~250-350 worst) is required and acceptable.

*Bugs/mismatches:* `:148` "~64 cycles/entry, ~514 all 8" understates (real ~72/entry,
~650 total) and duplicates a line; Important/Deferrable headers over-claim clobbers on the
empty path (harmless superset); the 128KB-split single-slot edge is known — added
observation: any future fix must ROLL BACK the first half-entry, not just report carry
(caller may recycle the dirty source on carry-clear).

*Fine:* 128KB boundary borrow math incl. exact-boundary case; vdpCommReg sanitization
traced; movep write order (clobber-then-overwrite) correct; slot-var-last enqueue ordering;
trap #0 jump-table padding; carry contract honored on all exits; init verified.

### buffers.asm

**H1.** Fade frames (`Palette_Dirty == $0F` common) enqueue 4 separate 32-byte DMAs
(`:131-146`): add a fifth static entry `Static_Pal_All` (128 B, CRAM 0) + `cmpi.b #$0F`
fast path — **~560 cycles/fade frame** and frees 3 Critical slots (mitigating bug #1).
**H2.** Sprite DMA length patchable in place with one `movep.w d3,DMAEntry_SizeH(a0)` from
the renderer (implements wave-1 sprites H3; up to ~500 B ≈ 1.2 scanlines on sparse frames).

*Medium:* HScroll mode select re-derives from the parallax config every VBlank (`:157-162`,
~60 cyc) — cache the chosen static-entry address, written by parallax config-set/transition
(event-driven); natural hook for the missing hscroll dirty gating (currently enqueued
unconditionally, even fully static frames).

*Bugs/mismatches:* **(1) real bug** — dirty flags cleared even when `queueStaticDMA`
silently dropped (Critical full: 4 pal + sprite + hscroll = 6 of 8 slots, PLUS main-loop
art staging queues Critical) ⇒ **stale palette persists indefinitely**. Make the macro
report drop via carry; clear bits only on success. Verifier: DEBUG-assert Critical
headroom at Enqueue entry; oracle test = fade during heavy art streaming. **(2)** stale
"Z80 already stopped" precondition. **(3)** `Vscroll_Write` clobber header (see vblank).
*Micro:* `queueStaticDMA` drops silently with no DEBUG counter (dma_queue counts — add the
same under __DEBUG__); `:126` "(d0 zeroed as side effect)" only true on the dirty path;
PlaneMapToVRAM one-shot — leave.

*Fine:* static entry layout matches DMAEntry + drain pattern; tail-call fall-through of
the last static entry into `.build_entry` (don't append below it); sprite link chain;
enqueue order pal → sprite → hscroll keeps §3.4 satisfied regardless of in-queue order.

---

## 16. engine/level/camera.asm + bg_anim.asm + engine/compression/s4lz_decompress.asm

### s4lz_decompress.asm

Baseline shape: short literal ≈ 96 cyc/token + 6 cyc/byte copy; short match ≈ 136/token;
**extended runs (≥15 words) = 22 cyc/word = 11 cyc/byte** (`:162-164`, `:173-175`);
TileDelta_Undo ≈ 8.5 cyc/byte second pass.

**H1. Chunk the extended-run loops.** Literals: 4× `move.l (a0)+,(a1)+` per dbf (≈5.6
cyc/byte), remainder via the EXISTING `.lit_end` unroll table (zero extra ROM). Matches:
gate on offset — `offset == 2` (word-RLE, flat tiles) becomes load-once + long-fill =
**3 cyc/byte** (the single fastest path, and flat tiles are exactly this pattern);
`offset ≥ 4` chunks as literals. Near-incompressible 768-byte block: ~8,450 → ~4,400
cycles — **~4,000/block, up to ~24k/frame at 6 blocks**. Word alignment guaranteed by the
format; move.l on word-aligned is full speed. Verifier: golden self-test byte-exact; add
test streams (odd-remainder extended literal, offset-2 match, offset-4 match, dict-tail
match); a0/a1 exit values unchanged; NO new register use outside d0-d3/a2-a3 (H2).

**H2. The register-preservation contract is real, load-bearing, and only half-written-down
— effectively freezes ALL of d4-d7/a5-a6.** Header declares `Clobbers: d0-d3, a2-a3`
(body verified matching; dict entry also a4). Stacked implicit dependencies: tile_cache's
a5/a6 hoist (`tile_cache.asm:1316-1323`, self-declared LOAD-BEARING & INVISIBLE);
`load_art.asm:20-21` keeps a4/d4 live across the plain entry; the narrow clobber license
means callers may legally rely on d5-d7. **Doc-only fix:** add an explicit `Preserves:`
line naming both dependents. Any H1 work must live in d0-d3/a2-a3 (it can).

*Medium:* M1 — `bra.w .token_loop` at every sequence end (~10 × 30-60 sequences/block):
restructure so the token fetch sits below `.match_end` and the common path falls through.
M2 — `lsr.w #8,d0` nibble extraction (22 cyc/matching token) avoidable via the `rol.w #4`
already done at `:80`; needs d2 freed (flags byte → stack, 8 cyc once). M3 — read
flags+version as one word (~16/call).

*Bugs/mismatches:* P1 — the a1-out contract survives the tile-delta path only by
construction (TileDelta_Undo happens to end with a1 at buffer end) — one comment line.
P2 — the dict-hit debug assert (`:129-131`) reads d4, which is caller garbage via the
plain entry — note "dict entry only". `:83`'s .w-reach comment verified accurate.

*Fine:* short-run unrolled dispatch structure right (d8 reach verified); word-ascending
match copy overlap-correct for all offsets ≥2; the per-match window check is load-bearing
for the dominant (dict) caller; TileDelta_Undo at its practical floor (batching collides
with the H2 freeze for ~6%); EOS/token-edge/pad semantics match the docs.

### camera.asm

**H1.** Both clamps re-derive act-invariant bounds every frame (`:124-137`, `:236-247`,
~62 cyc each): precompute `Camera_Max_X/Y` at Camera_Init → **~120-130/frame**, and a0
stops being clobbered mid-routine (removes the second `lea Player_1`).
**H2.** Camera_X does a RAM round-trip between apply and clamp (`:115` add.l to mem, `:125`
reload, `:140-142` store): single-pass in-register per axis → **~60-80/frame** combined.
Verifier: `.no_move`/`.clamp_y` stay valid entry points for freeze/hold; d4 freeze-flag
reservation honored.

*Medium:* M1 — `ext.l + lsl.l #8 ×2` (52 cyc) → `swap + clr.w` (8) per applied axis
(the conventions' own §2.6 idiom); M2 — Y-deadzone `moveq/neg/cmp` dance → `cmpi.w #±32`
(deletes a cross-block register coupling).
*Micro:* `:94` dead tst.w; `:78/:147` lea+displacement → direct absolutes; `:42` clr.w;
`:72` bra.w may come into .s range post-restructure.

*Bugs:* **P1 (mega-act cluster)** — all camera math is word-width; grid_w ≥ 32 sections
wraps the low word (max-clamp negative → camera pinned at 0; init loses the carry). Add a
build/debug assert now; floating-origin is the real fix. **P2** — Camera_Init doesn't
clamp: a start position near the world edge feeds one negative-camera frame into cache
population (init order: Camera_Init → cache populate → first Update). One clamp at init.

*Fine:* freeze semantics match the long comment; jump-lock d3/y_vel logic verified against
both game configs; fraction word provably zero; branch sizings reach-correct.

### bg_anim.asm

**High-impact: none** — the change-detection design (skip unchanged bands, event-driven
DMA) is exactly right; ~60 cyc/band/frame steady state. Not a cost problem.

*Medium:* M1 — header (`:51`) declares a3-a4 clobbered but `:54/:130` movem-preserve them;
per the declared contract the movem is dead weight (~52/frame) — delete it and fix the
header to d0-d7/a1-a2, or keep and fix the header. Sole caller (ojz_scroll_test.asm:278)
doesn't rely on a3/a4.
*Micro:* `:85` and.w → andi.w (consistency); the 3-word stack round-trip at `:96-98` is
genuinely necessary (verified — no free register) — listed so nobody "optimizes" it into
a clobber bug.
*Bugs:* P1 — no `band_count ≤ BGANIM_MAX_BANDS` guard: a malformed generated table walks
past `BgAnim_LastStep` and `.commit` corrupts adjacent RAM (ifdebug assert or a check in
tools/inject_editor_bg.py). P2 — a bad table can queue a zero-length DMA (violates
QueueDMA's input contract); same fix venue.
*Fine:* partial-failure retry policy correct (carry contract real — dma_queue was fixed
specifically for this caller); record-offset arithmetic all verified; driver-select branch
chain optimal for 3 drivers.

---

## 17. games/sonic4/player/player_ground.asm + player_air.asm + player_spindash.asm

Sensor cost model: probe core ≈ 450-800 cyc; a floor/ceiling PAIR ≈ 900-1,600 cyc.
Grounded moving ≈ 3 cores; airborne vertical ≈ 4; airborne horizontal ≈ up to 5;
jump-press frame ≈ 5+. Classic-parity structure — **no same-cell duplicate probe found
within a frame** except the two items below.

**G1 (high). Jump-press frame probes the ceiling twice.** `player_ground.asm:74` (roll
twin `:329`) runs the full headroom pair, then `Player_Jump` tail-runs the air body the
same frame (`:783`) whose mostly-up class re-probes walls AND the ceiling pair again
(`player_air.asm:220-222`); the headroom clearance in d0 is discarded. Carry the clearance
across Player_Jump and skip/reuse in the mostly-up class. **~900-1,600 per jump press.**
Verifier: jump under a 6-7px ceiling still rejects (buffer live); slanted-ceiling bump on
the press frame; ROLLJUMP radii; on-object jump unaffected.

**G2 (high). `GetSineCosine` computed twice on the same angle every slope frame** (`:93`/
roll `:347`, then `.project_slope` `:581` — angle can't change between them). ~80 cyc/
slope frame; textbook recomputed-derivation shape. Stash sin/cos in d5/d6 with a validity
marker for the skip paths. Verifier: flat fast path untouched; roll keeps the RAW pair
(it mangles d0 into the 5/4-shift form).

*Medium:* G3 — snap window computed before the embedded/convex checks that bypass it
(`Ground_PostMove:176-194`) — reorder, free on the normal path. G4 — idle-frame floor pair
memo (~900-1,600/idle frame) — design decision, needs sign-off (dynamic terrain, classics
probe every frame); flag only. G5 — duplicated slope preamble; fold into G2's shape.
*Micro:* G6 — SlopeRepel reads SST_angle 3× (`:247,264,271`); G7 — gsp reload after write
(`:469`, awkward due to shared entry — note only); G8 — magic button bits vs named
constants elsewhere.

*Bugs/mismatches:*
- **G9 (latent, §2.5b violation):** `Ground_Move:620` byte-loads the probe code into d7,
  then `:646/:664` `move.w d7,d2` and `:657/:691` `tst.w d7` consume it as a WORD — high
  byte is caller residue (0 today only because Player_Main dispatches with d7 = player
  counter = 0). player_sensors documents this exact hazard on ITS side and clamps; Ground_
  Move's own word uses are unguarded. Fix: `moveq #0,d7` before the load (4 cyc). Same bug
  class that shipped in Sound_PlaySFX 2026-07-03.
- **G10 (latent):** `move_lock` only decrements in Player_SlopeRepel (`:239-243`), and the
  on-object path rts's before it (`Ground_PostMove:161-164`) — a slip-locked player landing
  on a solid object keeps frozen input forever (friction zeroes gsp; only jump escapes).
  Tick the lock on the on-object exit or hoist to Player_Main.
- G11 — stale "PState_Spindash lives in sonic.asm" comments (`:4`; also
  player_common.asm:407). G12 — `PHYS_ROLL_FRICTION` (constants.asm:251) is dead and
  misleading (roll deliberately derives friction/2 from the phys table).

*Fine (verified in detail):* all physics constants check against S3K/SPG (accel/decel/
friction/top/gravity/jump/air/slip band/roll thresholds; the $D standing-slope gate ≈24°);
slope shift forms exact + build-asserted; the btst-preserves-N trick correct; turnaround
carry/borrow edges; wall-probe gating (cardinals always, $41-$BF skipped, gsp==0 early-out
already present); the two muls.w are lint-annotated variable×variable on slope/jump frames
only (legitimate); $FC0 steep-landing cap confirmed classic (s2.asm:37604-37606); dispatch
shape already the recommended structure.

### player_air.asm

**A2 (high, needs sign-off).** Both-wall probing in the vertical classes (`:214-215`,
`:220-221`) — 2 cores (~900-1,600) every mostly-down/up frame even at x_vel==0. Classic
parity (S2/S3K do it); any gate (probe toward nonzero x_vel only) is a behavior decision —
crushers/shaft spawns/moving walls lean on the both-sides sweep. Declining is defensible.
*Medium:* A3 — mostly_right/left duplicated tails (ROM only); A4 — banded-landing steep
path memory churn (~20, steep landings only).
*Micro:* A5 — release cap read twice; A6 — clr.b on RAM fine, leave.
*Bugs:* **A7 (needs a ruling)** — landing uncurl has no clearance check
(`Air_LandState:392` + PHook_EnsureStanding's +10px rise) while PState_Roll's unroll path
guards the IDENTICAL wall-clip hazard (`player_ground.asm:436-438`). Classic parity vs the
codebase's own hazard-class spec — decide, don't drive-by fix (if guarded: return ROLL when
the ceiling pair says blocked; costs a pair on curled landings only).
*Fine:* drag band inclusive edge exact-classic; integrate-then-gravity order; banded
landing masks byte-identical to s2.asm 37570+; d4 lifetime verified (consumed before wall
probes clobber it); FloorLandFlat's y_vel≥0 early-out already present; CeilingBump in
horizontal classes is required + classic; airborne quadrant=0 invariant holds.

### player_spindash.asm

No high/medium findings — one floor pair on charge (classic parity), no redundant sensors.
*Micro:* S1 — release SFX movem pair deletable by reordering (SFX first, then moveq)
(~50 cyc + 8 bytes); S2 — rev clamp does 3 memory ops on _pl_spindash → route through a
register (~20-30, tap frames).
*Bugs/notes:* S3 — self-contradicting header comments (shared-ability vs character-state;
the inner one predates the relocation); S4 — spindash charge not move_lock-gated
(self-resolving, unlike G10 — comment it if G10 is fixed).
*Fine:* decay-then-rev order classic; release closed form no-mulu, range verified; floor
window = ground formula at speed 0; buffered-press drop logic verified.

---

## 18. games/sonic4/player/player_common.asm + player_sensors.asm + sonic.asm

### player_sensors.asm — the probe census (caller-side map for engine lookup #4)

Cost model: **L** (full lookup) ≈ ~330 cyc; **T** (solidity/angle/height chain on solid)
≈ ~170; one `.cell` eval ≈ 375-500; one core ≈ 600-1,000; one pair ≈ 1,300-2,100.

| Mode | Cores | .cell evals | Est. cycles |
|---|---|---|---|
| Ground running flat | 3 | 5-7 | ~2,400-3,300 |
| Ground + buffered jump frame | 5 | 9-11 | ~4,400-5,400 |
| Ground idle (gsp=0, + ledge probe) | 4 | 6-8 | ~3,200-3,500 |
| Rolling fast | 3 | 5-7 | ~2,400-3,300 |
| Rolling slow (+ unroll clearance) | 5 | 9-11 | ~4,400-5,400 |
| Spindash charging | 2 | 3-5 | ~1,500-2,300 |
| Air mostly right/left | 5 | 8-10 | ~4,300-5,000 |
| Air mostly down | 4 | 7-8 | ~3,600-4,300 |
| Air mostly up (jump-launch frame: 6) | 4 (6) | 7-8 (11-12) | ~3,600-4,300 (~5,600) |

Sensors ≈ 2-4.5% of frame budget per player, worst case airborne-horizontal.

**Key structural fact: the extension probe is the COMMON case** — every open-air probe
takes `.empty_fwd`, every flush-solid probe takes `.full_back`; roughly HALF of all `.cell`
evals per frame are extensions. Each converted to a relative fetch saves ~300 cycles ⇒
**~600-900/frame grounded, ~1,200-1,500/frame airborne** (est.).

**H2 — landing plan for the pointer-return variant:**
1. Single swap point: `.cell`'s `bsr.w Collision_GetType` (player_sensors.asm:133), inside
   the probeCore macro — all four stamps inherit one edit.
2. Extension delta is compile-time per stamp: Down/Up = ±TILE_CACHE_STRIDE (80) bytes
   (with COLL_ROWS wrap); Right/Left = ±2 bytes (with COLS wrap). Pass as a macro arg;
   each stamp gets its own seam test.
3. **a1 is untouched** between primary and extension `.cell` calls on both paths — the
   variant returns the cell byte address in a1 with zero extra saves. d3 is dead until
   probeSub for the seam-safe indicator.
4. Only L is saved, not T: split `.cell` into `.cell_full` and `.cell_chain` (attr in d0)
   so the fast extension does `move.b delta(a1),d0` → `.cell_chain`.
5. The cross-axis coordinate is invariant across the extension (pcolreg never changes) —
   state it in the variant's contract.
6. Phase-2 seam (flag only): a pair's two sensors share the probe-axis coordinate — a
   row-base-return variant could make sensor B's primary a relative fetch too (~300 more/
   pair); `Player_SensorPair` (:193) is the natural holder. Do after lookup #4 proves out.

**H3 — `Player_AtLedgeEdge` probes the same point twice** (`:483-486`): `.single` sets
B = A and runs the identical core twice, comparing the result with itself — **~500-1,000
wasted cycles every grounded at-rest frame** (balance check). Fix: call
`Collision_ProbeDown` directly, skip the pair wrapper. (Independently confirmed by the
player-movement reviewer as the largest genuinely-duplicate sensor call in the player
tick.) Optional verdict-cache keyed on x_pos+facing is NOT sound alone (streaming/crumbling
terrain) — the duplicate-call fix is the safe win.

*Medium:* M1 — three `lea (table).l` per solid `.cell` eval (`:138,144,150`, 36 cyc):
co-locate SolidityTable/AngleTable at build time, one lea + fixed displacement
(~50-100/frame; add a build assert on the layout). M2 — SensorSurface recomputes the
cardinal after the pair (`:325-328`) when it was in d2 at `:274-277` — stash (~20).
*Micro:* probe cores already minimal; `andi.w #3,d2` hygiene clamp is correct — keep.
*Bugs:* `Player_AtLedgeEdge` header omits d6 (`:419` vs moveq at `:468`) — doc fix; probe
core stack discipline and `.full_back` distance algebra verified correct.
*Fine:* macro-stamped cores with assembly-time direction resolution; pair tie rule matches
comment; ST_ON_OBJECT short-circuit zeroes pair cost on solids; angle post-processing
cheap and matches S.C.E. references.

### player_common.asm

*Medium:* M3 — `Player_LevelBound` re-derives act extents every frame (`:639-659`,
~180-200 cyc): precompute at act init (~80 cyc), which also removes the truncation trap.
M4 — DUR_DYNAMIC hold computed up front every frame (~40) but consumed only by ball/walk
exits — move to a shared stub (marginal).
*Micro:* history-ring input word (`:245-247`, ~38 cyc) → single `move.w (Ctrl_1_Held).w`
(Held/Press are adjacent in that order, ram.asm:85-86) — IFF even-aligned; add an
alignment assert (AS does not auto-align). SnapToSurface branch chain and quadrant
derivation already minimal.
*Bugs:* **LevelBound word-truncation** (`:641-643,659`) — long math, word compare: grid_w
≥ 32 sections truncates the right bound → player clamps at the left margin forever
(mega-act cluster; assert now). `Player_Display` header understates clobbers (balance path
trashes d5-d6 as Animate's own header admits); `Player_Init` header omits the SetState
hook contract's d2/a2.
*Fine:* Ground_PostMove's N-flag trick verified; Player_Main's d7 save necessary and
scoped; history rings (256-alignment assert exists, low-byte wrap sound); EnsureStanding/
EnsureBall idempotent pattern + ST_ROLLING repair correct incl. debug-16 case; hook
dispatch + table-sync asserts fine; distToFix minimal.

### sonic.asm

Adjacent to dplc D3: the frame-unchanged early-out should sit BEFORE Sonic_LoadArt's two
`lea (X).l` + `move.w #imm` (~28 cyc, `:25-27`) — key on `mapping_frame` vs `prev_frame`;
the invalidation path already exists (DebugEnter/Exit reset prev_frame to $FF,
player_common.asm:127,733). `Sonic_InitAssets` "Clobbers: none" verified true. PhysTable
copy init-only, size-asserted. Nothing else per-frame.

---

## 19. engine/objects/children.asm + engine/macros.asm

### children.asm

**C1 (high — per-frame tax + two rendering bug shapes).** `CreateEffect_Normal` (`:423`)
and `CreateEffect_Simple` (`:473`) set `parent_ptr` "so effect can reference parent" — no
effect code reads it. Cost: `Draw_Sprite`'s child-skip guard (sprites.emp:56-60) derefs
parent_ptr + btsts the PARENT's render_flags for every object with nonzero parent_ptr,
every frame (~28 cyc each). Bugs: (a) **an effect spawned by an RF_MULTISPRITE parent is
skipped as batch-rendered but is NOT in the sibling chain → never rendered at all**;
(b) nothing clears parent_ptr when the parent dies — slot recycling by a multisprite
object silently hides orphans. Fix: stop writing parent_ptr on effects (dead store);
replace the parent-deref guard with a child-side "RF_BATCHED" bit set at spawn (~10 cyc,
no dangling deref). Constraint to document: parent must have RF_MULTISPRITE before
spawning children (true today — objdef template). Verifier: spawn effect from multisprite
parent → currently invisible (confirms bug); grep effect code for parent_ptr reads;
multisprite children still skip self-registration; orphans still render.

**C2.** `sibling_ptr` is overloaded (children-list head on the parent / next-sibling on
children) → nesting is impossible and undocumented; a child calling CreateChild_* corrupts
the grandparent's chain, and DeleteChildren is non-recursive. Minimum: header comment +
DEBUG assert (parent must not itself be a linked child). Structural fix (separate
first_child/next_sibling) only if nesting is ever needed.

**C3.** Cascade delete = N × core's linear live-list scan + full SST zero ≈ **~600 cyc/
child + ~110 overhead → 8-child cascade ≈ 5,700 cycles in one frame**. Bursty-acceptable
today; a `DeleteChildren_Batch` (ONE live-list pass zeroing all chain members) turns N
scans into 1 but touches core's §6/§9 invariants — design review, not a casual fix.
Verifier: lag counter during a max-children cascade.

*Medium:* **M1 — all six creators oversave around Alloc** (AllocDynamic/AllocEffect
clobber d0 + out a1 ONLY): Normal/Complex save d3/a0-a1 (should be a1 alone, ~44 waste);
FlipAware d3-d4/a0-a1 (~60); **_Linked saves d1-d5/a0 — none of which the callee touches —
the entire ~116-cycle pair is unnecessary**; Effect_Normal a0-a1 → a1; Effect_Simple
d2-d3/a0 → nothing. Note a1 DOES need saving where it's the descriptor cursor (the
latch-full fail path clobbers a1 too). Verifier: re-read Alloc contracts in BOTH core
twins (lockstep); run test_parent/test_stress_emitter/test_churn.
M2 — PopulateSpawnedPieceCount saves a1 it never touches (~16/spawn); its ~120-cyc
call overhead wraps a ~40-cyc payload; header claims mapping_frame "already set" — no call
site sets it (frame is always 0 here). M3 — DeleteChildren's per-iteration movem
(~56/child) avoidable by holding parent in a2 / next in d2. M4 — fail-path descriptor
skip-walks are dead work (a1 is a declared clobber; nothing reads it) — replace with
immediate rts, ×4 routines. M5 — chain head rewritten every iteration (`:82,163,253`) —
hoist to one unconditional write of d3 after the loop (correct even when the first alloc
fails).

*Micro:* offset-to-16.16 pattern ~10/axis cheaper via high-word add; PopulateSpawnedPiece
Count's movea/move.l/beq → move.l/beq/movea; FlipAware tests tst.w d4 3×/child (branch to
a flipped/unflipped loop pair, ~60 bytes ROM); first PopulateSpawnedPieceCount bsr may be
.s-reachable; `:358` move.w #0 vs clr.w is a wash.

*Bugs:* **(1) `CreateChild_Linked` orphans a pre-existing chain** (`:330-331` overwrites
the head; Normal/Complex/FlipAware deliberately prepend via d3) — slot leak until
entity-window despawn; fix by seeding the last child's sibling_ptr with the old head, or
document + DEBUG-assert childless-parent. **(2) children never inherit a priority band**
(slots zeroed; render_flags not copied) — every independently-rendered child registers in
band 0 (backmost); high-priority parents' debris draws behind everything. Inherit bits 5-7
or take a band parameter — decide before the first real multi-part badnik. (3) = C1's
shapes. (4) PopulateSpawnedPieceCount header mismatch (M2). (5) cosmetic: two fail-skip
loop shapes differ (M4 deletes both).

*Fine:* AllocDynamic's code_addr-before-next-alloc invariant honored by every creator;
DeleteChildren reads next before deleting; chain termination via zeroed slots correct in
all five builders; _Linked stack discipline balanced on both exits; 14-byte descriptor
arithmetic incl. fail-path lea correct; branch sizes explicit; no mulu/divu.

### macros.asm — per-macro verdict table

| Macro | Verdict |
|---|---|
| vdpComm, vdpReg, vram_art, vram_bytes | correct (bit-exact verified) |
| **sprSize** | **BUG (confirmed, latent)** — see below |
| bytesToLcnt | correct; silently floors n%4≠0 (note in header) |
| vdpCommDelta | correct; undocumented $4000-window carry constraint |
| planeLoc, dmaSource, dmaLength, objroutine | correct (dmaSource comment loose) |
| objvarsCheck, objdef, objentry, objend | correct (objend IS alive — generated data uses it) |
| stopZ80, startZ80, disableInts | correct |
| enableInts | correct at its single boot site; hardcodes IPL3 — unsafe as a general undo |
| setVDPReg | correct; all 8 sites event-driven — fine |
| vdpCommReg | correct, near-optimal (canonical transform + tas.b trick verified) |
| queueStaticDMA | correct; no DEBUG drop counter (dma_queue has one — add) |
| clearLoadedRing/Obj | correct; header scoping claim is FALSE (see B3) |
| collSrcRowBase | correct; keep as-is (form expresses the parity argument) |
| DEBUG_ALL/_DMA/_VRAM/_OBJECTS/_COLLISION | **DEAD** — zero consumers |

**B1 — sprSize (macros.asm:21), expanded:** hardware wants width in bits 3-2, height in
bits 1-0; the function emits `((h-1)<<2)|(w-1)` — swapped. Three in-repo references
contradict it, all correct (sprites.emp:16 SPRITE_MASK_SIZE, the SAT format doc at
sprites.emp:172, CellOffsets_XFlip at sprites.emp:469). **Aggravators:** (a) the swapped
formula is ALSO the canonical example at CODING_CONVENTIONS.md:25 — fix both together or
it comes back; (b) the `<<8` is a wart — all 4 call sites immediately `>>8` it for a dc.b;
drop it. All current users square → latent. Verifier: swap to `((w-1)<<2)|(h-1)`; update
the conventions doc; drop `<<8` + update 4 sites; add a NON-SQUARE test mapping and
confirm on oracle it renders 32×8 not 8×32; re-grep for hand-written size bytes that
compensated (none found — re-check).

**B2** — the four DEBUG_* subsystem flags are dead AND the block's comment points at an
`ifdebug` that takes no subsystem argument; conventions §1.7's two-layer scheme was never
built. Implement or delete + reconcile §1.7.
**B3** — clearLoadedRing/Obj's "expand at most once per global-label scope" claim is false
for this assembler: queueStaticDMA expands 7× in one scope (buffers.asm:133-166) and
stopZ80 2× in one scope (vblank.asm:116,147), both with fixed internal labels — asl scopes
macro symbols per-expansion unless {GLOBALSYMBOLS}. The stale comment actively misleads.
**B4** — vdpCommDelta: state "total advance must not cross a $4000 VRAM boundary".
**B5-B7** — bytesToLcnt floor note; dmaSource comment precision (the load-bearing effect
is keeping DMD1 zero for $FFxxxx RAM); enableInts "boot only" note.

*Medium:* setVDPReg sets the dirty bit even when the value is unchanged — fine today (all
sites event-driven); revisit only if it ever enters a per-frame path. queueStaticDMA's
14-byte copy shape is the floor; if VBlank pinches, pre-slot the static entries at
build time rather than micro-optimizing.

*Fine:* vdpComm verified bit-exact for all 6 combos; vdpCommReg verified against the
encoding incl. the tas.b lone-CD5 case and both dma_queue call sites' clr choices;
objentry guards coherent (flags overlap, type/sub ranges, monotonic-X, MAX_LIST_ENTRIES);
objdef's AS size-suffix quirk is real and properly dodged; stopZ80 polarity correct; no
macro computes at runtime what function could do at build time.

---
---

# WAVE 4 — boot, remaining 68k, debug, shell, data audits

## 20. engine/system/boot.asm + vectors.asm + z80_init.asm

### Correctness / hardware-risk findings

**1. Cross-reset RAM contract is violated — the clear wipes it every boot and the magic is
never read.** `ram.asm:493-499` documents CROSS_RESET_RAM as soft-reset-surviving, but
`Warm_Boot` falls straight into `Cold_Boot` (`boot.asm:22`) and the clear loop
(`boot.asm:86-91`) clears the full 64KB on both paths. `CROSS_RESET_MAGIC` (`:197`) has
zero readers (grep). Dead scaffolding contradicting its docs — implement the
warm-boot-preserving clear or delete the mechanism. Oracle CAN verify.

**2. PSG silence writes race the in-flight VRAM DMA fill.** Fill triggered `:52-55`,
waited on only at `:101-104`; the PSG writes `:93-97` land while the fill may run (the PSG
lives inside the VDP — plutiedev-documented hazard). Latent (~2× implicit timing margin,
computed) but unenforced. Free fix: move the 4 writes after `.wait_fill`. Race-window
liveness oracle-checkable; the corruption effect is hardware-only.

**3. YM2612 key-off block: no busy-wait + address-latch race vs the running driver.**
`:124-137` writes ~22 cycles apart with no busy poll (real silicon drops writes) — mostly
moot because the reset pulse at `:79-83` already keyed everything off. Sharper: in sound
builds the Z80 driver has been running since `:84`; `stopZ80` can halt it BETWEEN its own
YM addr/data writes → the 68k latches $28 → the Z80's resumed data write lands on $28
(dual-owner latch race). Fix: key-off before the bus release (Z80 not yet running), or
drop the block in sound builds.

**4. No build-time evenness assert on either Z80 blob.** Copy at `:74-76` + data stream
resuming at `align 2` (`:274`): an odd `Z80_SOUND_SIZE` desyncs the a5 stream (pad byte
eaten as a PSG value; noise never silenced) then `move.w (a5)+` at `:107` address-errors.
The "blob must be even" memory invariant has NO enforcement — `if (SIZE&1) fatal` both
blobs.

**5. Warm-boot VDP read precedes TMSS** (`:17-20` vs `:32`) — safe only by the S1/S2
inherited precedent ($A14000 latch survives reset button). Cheap hardening: unconditional
TMSS write before the DMA wait. Hardware-only; low priority.

**10 (vectors). Spurious-interrupt vector ($60) → ErrorExcept** (`vectors.asm:32`): a
transient IPL glitch hard-crashes a retail build; IRQ5 (`:37`) already takes the tolerant
NullInterrupt stance — the table is internally inconsistent about glitch policy. Suggest
NullInterrupt in release, ErrorExcept under __DEBUG__. Hardware-only.

**11 (z80_init). Final `ld sp,hl` leaves SP=0** (`z80_init.asm:25-27`) — a future push
wraps to $FFFF = the 68k bank window. Inert today; the idle blob is the template people
copy. One instruction fixes it.

### Medium

- **6.** Window nametable $F000 overlaps Plane B $E000-$FFFF (`:243-244`, 64×64 planes) —
  harmless (window disabled) but with this VRAM map there is NO free window space; comment
  the constraint.
- **7.** `EntryPoint` doesn't reload SP — `jmp EntryPoint` soft-reset would run the RAM
  clear on a stale stack then `bsr` through garbage. One `lea (SYSTEM_STACK).l,sp` closes
  it (S2/S3K do this).
- **8.** Interrupts live during CompressionSelfTest/Sound_Init/gameBootHook (`:194` →
  `:199-210`) — VInt_Lag must be safe against fully-zeroed RAM (it is today); implicit
  invariant, comment it.
- **9.** No boot checksum verification — consistent with the skip philosophy and arguably
  safer; record as intentional in ENGINE_ARCHITECTURE.

### Micro / mismatches

`:98` dead `align 2` mid-code; `:143` redundant disableInts (comment it); `:174`
`move.w #0` → clr.w (+ redundant after RAM clear); `:70` comment "word count" is WRONG —
it's a byte count (a reader "fixing" the loop to words would halve the copy); `:196` "cold
boot complete" executes on warm boots too; `vectors.asm:33` "IRQ1 (external)" mislabel
(external = IRQ2/$68); z80_init `ld bc,(…)-…` operand-parse trap (hoist to a named
constant); z80_init header "clears Z80 RAM" → "above the program".

### Checked and already fine

TMSS handshake canonical; VDP command-latch reset; all 24 VDP register values verified
against hardware constraints (no nametable/sprite/hscroll overlap modulo the window note;
128K mode clear); DMA fill protocol exact (autoinc 1 → fill → status poll via control port
→ autoinc 2 restore) and the fill/Z80-load/RAM-clear parallelization is genuinely good
init design; Z80 reset/busreq dance canonical incl. the verified 264 ≥ 192-cycle YM hold
(re-derived, not trusted); RAM clear covers the entire 64KB incl. both phases; register
clear via `movem.l (RAM_Start).w,d0-a6` legal and correct; PSG silence values correct
(placement is finding 2); YM key-off VALUES correct ({00,01,02,04,05,06}, skipping
03/07); interrupt-enable ordering airtight (handlers + pointers before any interrupt);
region handling correct (V28-on-PAL letterbox is a decision, not a bug); controller init
correct and is exactly what makes warm-boot detection work; warm/cold detection
S1-identical; all 64 vectors present/even, every target symbol exists, gameHeader
placement correct; the generated debug "vectors.asm" is a pure NAME COLLISION
(compression-selftest payloads, not CPU vectors — resolved, no issue); z80_init arithmetic
verified exact (clear range, pops-read-zeros, $E9 self-trap; byte-wise 68k copy correct).

---

## 21. engine/compression/zx0_decompress.asm + engine/level/load_art.asm + engine/level/bg.asm

### zx0_decompress.asm

**Verified instruction-by-instruction against Emmanuel Marty's upstream `unzx0_68000.S`
V2 — byte-faithful (mnemonic spellings only), as the header claims. Keep it untouched**:
the diff-against-upstream property answers every future correctness question. Optional 2×
unroll of the byte-copy loops (~20-25% of decompress time) ONLY if measured load time is a
problem — it erodes the provenance note; word copies are NOT safe (byte-granular format,
arbitrary parity). Latent: elias values accumulate in d0.l but the copy loops count with
dbf (word) — safe by construction (u16 wrapper size), document with one comment line.
Bit-queue idiom, d2 upper-word invariant, shared-rts trick all verified upstream-exact.

### load_art.asm

- **The `QueueDMA_Critical` carry return is ignored** (`:79`) — a drop means the page's
  art never reaches VRAM AND the next iteration overwrites the staging buffer: permanent
  corrupted act art, zero diagnostics. Can't realistically fire today (one entry/VSync,
  Critical drained unconditionally) but it's conventions §7.7 silent failure. Minimum:
  `bcc.s .queued` + DEBUG RaiseError.
- **Consider direct blocking DMA instead of queue+VSync** (`:79-80`): display-off init,
  each page pays up to a full frame parked in VSync_Wait — direct stopZ80/DMA/startZ80
  saves est. 3-8 frames per act load and removes the drop hazard structurally. Judgment
  call; decide together with bg.asm's posture (below).
- Dispatch fall-through favors S4LZ over the common ZX0 case (`:24-29`) — invert (§2.2).
- **Clobber header contradicts the code** (`:36` "d0-d7, a0-a3"): d6 is saved/restored
  (NOT clobbered), d5/d7 never touched. Actual set: d0-d4/a0-a3. Fix header or drop the
  dead d6 save.
- Fine: a4/d4-across-decompress is sound on both paths; size peek even by construction;
  empty-page skip advances the VRAM cursor correctly; the callee-contract table at
  `:50-53` is accurate.

### bg.asm

- **Both init blits are CPU word-pokes** (`:83-85` nametable 4,096 words ≈ 90k cycles;
  `:68-70` tiles up to 7,168 words ≈ 158k — **~2 frames with SR masked + Z80 stopped**).
  ROM sources = the conventions §7.2 zero-copy case. Tier 1: `move.l`+halved dbf (3-line
  change, ~80k saved). Tier 2: 4× unroll. Tier 3: real DMA (~0.3-0.4 frame for all 22KB)
  — needs 128KB-straddle handling; decide with load_art.
- **THE TRANSPOSE QUESTION (from wave-1 plane_buffer note 6) — ANSWERED:** bg.asm consumes
  the layout strictly row-major as one flat 8,192-byte stream (autoinc 2). Full consumer
  census: Draw_BG_TileColumn (column gather, stride 128 — the transpose target),
  Section_RedrawPlanes Plane B blit (row-major linear), BG_Init (row-major linear), and
  the build side (ojz_strip_gen.py:1336 + editor export blobs). **Column-major works with
  NO dual format**: the two linear consumers adapt via autoinc `$80` (row stride 128 fits
  the 8-bit autoinc register exactly) — 64 command setups ≈ 2-3k cycles per blob,
  init-only noise — and their inner loops stay sequential-source. Payoff:
  Draw_BG_TileColumn ~34 → ~22 cyc/word (~380/strip, per-frame at scroll speed), plus
  move.l pairing unlocked. CRITICAL: the ACT blob must be transposed too — production
  sections have `sec_bg_layout = NULL`, so the act fallback is the common per-frame path.
  Caveats: column-major forces 64 small DMAs if the init blits become DMA (decide
  together); .emp twins + ojz_strip_gen.py + editor-library blobs flip in one commit;
  verify mid-scroll.
- **Bugs:** header `:3-4` claims the region is $A000-$BFFF — actual $8000-$B7FF (the
  `:22-25` comment is the correct one). **A length-1 (or odd) tile blob survives the
  clamp: `lsr` → 0 → `subq` → $FFFF → dbf sprays 65,536 words across ALL of VRAM** — the
  "last line of defense" guard has this hole; `beq.s .skip_tiles` after the lsr closes it.
  Cross-file: bottom 32 plane rows are init-only (RedrawPlanes/Draw_BG_TileColumn maintain
  32 rows; bg.asm writes 64 and advertises 512px vertical headroom) — consistent today
  only via injector zero-padding; record the runtime 32-row limit.
- Fine: interrupt masking correctly motivated; NULL checks full-width; autoinc set before
  each command; Z80 released between the two copies (kind to the driver); clamp
  byte-length units consistent.

---

## 22. engine/ram.asm + engine/constants.asm + game configs (alignment + defs audit)

**ALIGNMENT AUDIT: CLEAN.** All four layout shapes walked (engine release/DEBUG ×
sonic4/demo): every ds.w/ds.l lands even; Engine_RAM_End/Lower_RAM_End/Game_RAM_End even
in all shapes. Parity chains documented for every non-obvious region (VDP shadow pad, DMA
queue, parallax odd-byte pairs, 36-byte-even DEBUG profiler block, SST 5280, ring stride,
collected window 306+2, SFX ring, live-pending DEBUG/release byte pair, game-slice align
256 + &$FF guard). Overflow guards all present; no lower-half symbol is `.w`-addressed.

**RAM MARGIN: +256 B trivially available** — upper half has **19,454 bytes free** to
SYSTEM_STACK (identical DEBUG/release; align 256 absorbs the debug delta); lower half
6,078 free. Total ~40KB/64KB used. (Answers the wave-1 ring-stride question; note an odd
stride would break parity — 8 is fine.)

**Findings:** (1) `Spawn_Count`/`MAX_SPAWNS_PER_FRAME` is dead scaffolding — written zero,
never incremented/compared; implement or delete. (2) **Missing build guard on the
load-bearing streaming contract `CAM_MAX_Y_STEP ≤ VFILL_ROWS_PER_FRAME*8`** — currently at
exact equality (16 = 2×8, zero slack), conventions §1.6 requires the `if`. (3)
`VFILL_ROWS_PER_FRAME` comment says "4 = catch-up headroom" but the value is 2 — verify
intent. (4) `ram.asm:25` stale "9216 (12×768)" — slots are 16 now (12,288). (5) game-slice
pad comment claims to protect an engine symbol (pre-split leftover). (6) Parallax_State
"~126 bytes" → actual 244. (7) two comments overstate DEBUG/release layout invariance
(the profiler block shifts addresses by 36). (8) `RING_BUFFER_ENTRY_SIZE`/
`COLLECTED_SLOT_SIZE` are engine-owned formats duplicated in both game configs — derive
engine-side; only counts are game knobs. (9) demo's COLLECTED_WINDOW_SLOTS=4 vs the "3×3 =
9" contract comment — benign (no rings) but unasserted. (10) `BgAnim_LastStep: ds.w 4`
hardcodes BGANIM_MAX_BANDS with a comment, not an assert.

**Dead defs (grep-verified):** PHYS_ROLL_FRICTION (confirmed), HEIGHT_MAP_SIZE,
ANGLE_TABLE_SIZE, CTYPE_FLAT_SOLID, MAX_OBJECT_TYPES, MAX_SPAWNS_PER_FRAME, all four
SF_* flags, ST_P1/P2_PUSHING (leftovers of exactly what the comment above them says not to
bring back), SECTION_TILE_WIDTH/HEIGHT (the tool re-defines 256 as an independent
literal). **Fragile fixed pads:** `:270` assumes SCANLINE_BANDS odd; `:249` relies on
PRIORITY_BANDS even; `:398`/`:19` pads are spurious (already even) with wrong comments —
use computed `&1` pads like `:402` does.

**Cross-checks:** PARALLAX_LERP_SHIFT comment confirmed wrong ((15/16)^16 ≈ 36% remaining;
~95% needs ~46 frames) — and conventions §2.6's lerp table has the SAME ~3× error (the
comment faithfully mirrors a wrong table). DMA figures: 4,300 is the §3.3 CPU-cycle figure
(itself suspect vs the real ~17-18k window); 7200 is the §8.1 DMA-bytes row — constants
file is internally consistent; the staleness lives in CODING_CONVENTIONS.md. Guards
verified present: SECTION_SIZE sync, Y-band invariants, SFXPRI 7-bit, PSTATE ordering;
SFX_TABLE_LEN/COLLECTED_SLOT_SIZE/KILLED_BITMASK_OFFSET/Sound_Dbg_Mirror math all check.

---

## 23. Debug cluster (debugger, error_handler, sound_debug, compression_selftest, game_debug, generated vectors)

### The three actionable items

1. **Plain-build leakage that exists TODAY:** (a) the MDDBG blob + exception stubs ship in
   every release ROM — possibly intended, undocumented (decide + record); (b) **convsym
   appends the FULL symbol table to release ROMs** (`build.sh:130-134`, `-OLIST`
   unconditional) — size + reverse-engineering giveaway; gate on DEBUG; (c)
   **`SOUND_DEBUG_HOTKEYS=1` without `DEBUG=1` builds successfully** and ships a release
   ROM with the hotkey harness AND the boot-time MT autoplay — the "requires DEBUG=1"
   claims (build.sh:52, game_loop.emp:5-6) are enforced NOWHERE. One line in build.sh.
2. **Macro contract asymmetry:** `assert`/`ifdebug`/`KDebug` are __DEBUG__-gated;
   `RaiseError`/`Console` are NOT — only call-site discipline (currently correct at both
   production sites) prevents release bytes. Gate, name-convention, or lint.
3. **Conventions §1.7 is fiction — confirmed:** the subsystem-gated two-layer
   ifdebug/debugend was never built; DEBUG_DMA/_VRAM/_OBJECTS/_COLLISION are read by
   nothing; DEBUG_ALL=0 contradicts the doc's example. Build it or delete + rewrite §1.7.

### Rail-correctness results (the good news)

- **`assert` verified flag-transparent and release-zero-cost**: push SR → cmp/tst → Bcc
  (doesn't touch CCR) → pop SR; condition-code operand order verified against usage. The
  REAL hazard is `ifdebug`-prefixed SETUP instructions (clobber a register + CCR in DEBUG
  only) — all three live sites audited safe (s4lz ×2, tile_cache ×1); lint the pattern.
- **`assert` with stack-relative operands is off-by-2** (SR pushed first) — no current
  usage; comment/lint it. `_assert` (no CCR save) has zero users — document "never in
  flag-sensitive code" or remove.
- **compression_selftest fails loudly — verified** (checksum + word-exact compare + $A5A5
  poison defeats no-op AND short-write decodes; failure PC identifies the vector). Gaps:
  no OVERRUN guard (one poisoned word past the end closes the last silent mode); runs with
  interrupts live (safe today; pin the assumption). Does NOT rely on the S4LZ narrow
  clobber license (wave-3 concern unfounded — verified).
- **sound_debug**: clean gating (triple), correct copy math; header clobber list omits d1;
  `ram.asm:426-433`'s mirror description is two generations stale (the MCP-facing map
  lives in two places, one updated). Nested-bus-bracket invariant is comment-enforced —
  lint candidate.
- **error_handler**: ints masked first (good); movem onto the crashed SP means an odd-SP
  crash double-faults to a black screen (upstream limitation — document); Z80 never
  stopped (correct — port writes only) but a crash mid-stopZ80-bracket leaves the Z80
  frozen (cosmetic, document). Include ordering honors the "no data after" warning.
- **game_debug**: edge detection + masks verified; SFX cycle logic clean incl. the
  align 2 after the odd table; engine game_loop.emp hard-mirrors this game's hook and
  names a game symbol in an engine module — acknowledged debt, track until a per-game
  hook seam exists.
- **generated/vectors.asm**: release-clean only via its include site — add a
  self-defensive `ifndef __DEBUG__ fatal`.

---

## 24. Game shell — main.asm, ojz_scroll_test, object_test_state, demo

### OJZ per-frame order (mapped): InitSpriteSystem → RunObjects (draws sprites) →
Camera_Update → Tile_Cache_Fill → EntityWindow_Scan → Section_UpdateColumns →
TouchResponse → RingCollision → Render_Sprites (+DrawRings) → FlatID/marker diagnostics →
mode-set force → Parallax_Update → BgAnim_Update. Init ladder mapped at `:9-143`.

### Ordering findings

- **Ghost-sprites bug root cause CONFIRMED as engine contract**: all three states call
  InitSpriteSystem at frame start per the engine's own documented contract
  (sprites.asm:13) — fix once engine-side (separate prev-frame latch or stop clearing
  `Sprites_Rendered` in init), not per state.
- **Sprite culling uses LAST frame's camera** — `Draw_Sprite` culls against `Camera_X`
  inside RunObjects (step 2) with zero margin; `Camera_Update` runs after (step 3);
  positioning uses the post-update bias. At CAM_MAX_X_STEP=16, objects within 16px of the
  leading edge cull one frame late/early → edge pop-in. Either Camera_Update before
  RunObjects (accepting 1-frame camera-vs-player lag) or a ≥16px cull margin — needs a
  deliberate decision; today it's an accident of ordering.
- **Direct `$8B` write (`:263-273`) is a §3.4 state-before-data inversion**: applies the
  new HScroll MODE a full frame before its matching table reaches VRAM (per-cell↔per-line
  crossing = the documented one-frame tear), violates §3.1 rule 5, and runs
  unconditionally every frame (stopZ80 round-trip for nothing on ≥99% of frames). The
  setVDPReg shadow at `:262` alone is the correct shape.
- **Init consumes unclamped Camera_X/Y** — Camera_Init has no bounds clamp; player spawn,
  Section_FillInitial trackers, Tile_Cache_Init, the synchronous redraw, entity-window
  initial scan, and the primed Parallax_Update ALL seed from it. A descriptor start within
  160px/112px of an act edge snap-clamps on frame 1 with trackers/cache seeded around the
  wrong origin. Cheapest fix: clamp inside Camera_Init.
- **`Section_UpdateColumns` Z80-safety asymmetric**: init call stopZ80-wrapped
  (`:110-113`); the bare per-frame call (`:187`) reaches the redraw path via runtime
  `Section_Plane_Dirty` (cache recovery) → direct VDP writes with the Z80 live (§3.1 rule
  3). Fix engine-side (stopZ80 inside Section_RedrawPlanes); future states clone the bare
  call.
- 1-frame spawn latency (entities load after RunObjects) is load-bearing on
  ENTITY_LOAD_BUFFER — fine, worth knowing.

### Medium/micro + mismatches

`.marker_id_ok` byte-compares a word then word-indexes (§2.5b shape, safe at 3×3,
hardcodes 9); d6 held across a jsr on a comment contract (fragile in a template);
redundant `VInt_Ptr` write at `:140` (boot set it; demo omits it — pick one); OJZ never
calls Init_SpriteTable while object_test/demo do (all rely on boot — pick one); `:97`
"fills nametable over 3 VBlanks" stale; tile_cache.asm:628 references a renamed routine;
`:169-172` tombstone comment. object_test: DEBUG profiler subtracts a non-monotonic V
counter (VBlank-spanning samples permanently pollute Prof_Peak maxima — add a discard
guard); `GameState_ObjectTest_Init` should adopt Churn_Init's entity-window/ring idle
(stale Ring_Buffer draws over the scene if entered after OJZ ran); header "35+ slots" vs
the (correct) ":269 33+9" math. demo: same InitSpriteSystem inheritance (THE template);
TouchResponse-without-player is safe but un-commented. main.asm manifests: all seven
GLOBALSYMBOLS macros verified against engine.inc's MACRO LAW; MT-bank layout guards
exemplary; BUT sonic4's `gameDataIncludes` carries ~30 lines of inline BINCLUDEs (demo
keeps data in demo_data.asm — the divergence is the drift risk; move to a data include);
the six sigil pin `org`s have no AS-side `if * > $XXXX` drift guards.

### Checked and already fine

Tile_Cache_Init/Section_Init dependency order; Section_UpdateColumns after Camera_Update
(contract honored); EntityWindow_Scan after camera with DEBUG freeze covering both;
despawn-after-registration safe via the Render_Sprites NULL guard; RingCollision placement
(same-frame collect + collide); Parallax→BgAnim order per contract; marker-tile VRAM copy
correctly bracketed with the failure-mode comment; player spawn-before-Init contract;
GameLoop's engine-owned VSync/SFX-drain placement correct in all states; churn's
deliberate scan placement documented; object_test stack discipline + AllocDynamic Z-checks
consistent.

---

## 25. Game test objects (test_player, test_parent, path_swap, small ones)

### path_swap.asm (real machinery — reviewed hardest): CLEAN with two notes

Speed-independent edge trigger (sign-relation, not proximity — a 16px/frame player cannot
skip it); arming/idempotency matches S.C.E. semantics incl. the walk-around-and-return
case; teleport-rebase-safe (both X's shift equally); culling can't eat a crossing; §7.8
compliant. Notes: (1) **single-player hardwired** and the SST layout can't hold a second
arming byte without a data-format break — reserve `prev_side ds.b NUM_PLAYERS` before
Tails, or comment the deliberate deferral; (2) vertical band gate samples post-move Y (≤
~16px sampling error at speed) — document "size bands with ≥16px margin". Micro: clobber
header says d0-d2/a1 but the Draw_Sprite tail makes it d0-d3; `sgt` on-the-line = left
(un-commented tie rule).

### test_player.asm

- **`AnimateSprite` called with uncontrolled d3 while all three anims are DUR_DYNAMIC**
  (`:245-253`; the hold is read from d3, `animate.asm:54-58`) — at the call site d3 is
  sensor leftovers or a physics constant: **animation rate is garbage-driven**. Fix:
  `moveq #hold,d3` (same bug in test_animated.asm:41).
- Headers claim `Clobbers: d0-d7, a0-a6` — contradicting the a0/d7 dispatch rule the file
  itself cites (code IS compliant; headers lie; templates clone headers).
- "idle" (`:51,:251` anim 1) is actually **ANIM_RUN** (ANIM_IDLE=5). Magic art_tile
  `#$A0FA` (`:82`) indexes the level art pool — the debug square renders by accident;
  use `vram_art(...)`.
- Dead `:104` status snapshot (d5 never read — either the on-object landing logic was
  never written or it's leftover; d5 is also the natural home for a status-in-register
  rewrite, ~60-100 cyc/frame); dead `:118` bclr (bit already cleared at `:105`); 16.16
  conversion via double `lsl.l #8` (52c) → the conventions' own swap+clr.w idiom (8c).
- Fine: d4-not-d7 controller read with the incident writeup; d7 save around the sensor;
  physics ladder clean and classic-correct.

### test_parent.asm

- **The self-destruct is dead code — the parent is immortal**: `:187` reloads
  `_parent_life_timer` with PARENT_LIFETIME at the end of every left swing, so the
  `bne.s .move` at `:162` never falls through and the DeleteChildren/DeleteObject cascade
  (`:165-166`) — the file's stated purpose — never executes. Separate the swing counter
  from the lifetime.
- **The orphan check is false security** (`:84-86`): nothing ever zeroes a child's
  parent_ptr — a parent deleted via bare DeleteObject leaves a stale pointer into a
  recyclable slot. Children that outlive parents must validate liveness (check the
  pointed slot's code_addr) or parents must always cascade.
- Over-wide movem around GetSineCosine (preserves all but d0/d1) — re-fetch a1 instead
  (~165 cyc/frame across 3 children). `:28` "~90°/sec" comment: actual ≈ 337°/sec.
- Fine: child descriptor format exact; orbit math exact, no multiply; RF_MULTISPRITE
  usage matches the sprites contract.

### Small ones

test_churn: the a0 save/peek/pop around AllocDynamic is dead weight (AllocDynamic
preserves a0 on all paths — and the comment teaches the wrong contract); `jsr
DeleteObject / rts` → `jmp` tail. test_enemy: `ENEMY_PATROL_SPEED` defined in two places
with the step counter silently assuming 1px/frame — add the build-time check; `.draw`
label unreferenced. test_emitter banner names the wrong label. Init-falls-into-Main
clobber-header convention inconsistent across all templates — pick one. test_animated:
same d3/DUR_DYNAMIC bug as test_player. Fine: stress-emitter vs objdef-loaded
PopulateSpawnedPieceCount asymmetry is real and correctly commented; DplcV ifndef guards
follow §4.1 verbatim; test_static/demo_box nothing to do.

---
---

# WAVE 4 — Z80 sound driver (all T-state/byte figures are estimates)

## 26. engine/sound/z80_sound_driver.asm + dac_sample_tab.asm + sound_constants.asm

### High-impact (SIZE — ordered for the ~86 B headroom)

- **H1. Factor the 7× "clear slot + bump ack" mailbox tail** (sites :554-556, :576-578,
  :593-595, :604-606, :615-617, :640-642, :1375-1377) into a resident helper —
  **−23..−28 B**, cold path. hl dead at every site (verified).
- **H2. SndDrv_SetBank rept 8 → djnz loop** (:868-871) — **−10 B**, +~100 cyc per real
  switch (≤2/frame, absorbed by the ring lead like the documented 200-cyc bound). Caller
  b-audit done for the known sites; re-audit sound_sfx callers before landing.
- **H3. DRAIN/DRAINING nop pads → `jr $+2` chains** (:459-462 19 nops; :407-409 21 nops)
  — **−13 B, cycle-IDENTICAL if counted right** (76/84 T totals must be preserved
  exactly). CADENCE-SENSITIVE: re-derive the balance comment, VGM $2A histogram under
  heavy DMA, rendered A/B.
- **H4. Snd_StartSample descriptor walk** (:796-807): sequential inc-walking replaces
  push/pop + two ld de/add hl — **−6 B**, cold.

### Medium

- **M1. `.seq_clr` byte loop → LDIR** (:1105-1113): −1 B and halves the ~660-byte wipe
  (~27.7k → ~13.9k cyc) — directly widens the mid-drum song-load margin the :1045 comment
  leans on. Verify mid-drum load, ring lead ≥ 0.
- **M2.** Timer-A bulk-refill inner loop ~108 cyc/byte — restructure would help worst-case
  refills but GROWS code; not recommended now, logged as a lever if sustained-DMA
  wow/flutter is ever measured.
- **M3.** `.chan_init` push/pop bc looks removable (−2 B) — needs a body-write proof +
  comment guard.

### Micro

`jp z,.music_stop` → jr (−1 B); shared silence stub option (~−6 B); DacLookup 8-bit ×9
(−1..2 B, needs a `count*9 ≤ 255` assert). **DO NOT touch the hot loop** (:352-388) —
every instruction is load-bearing in the 195-cycle balance; the shadow-de′ FILL idea
CHANGES the sample clock (+~149 cents) — deliberate-retune-only, not an optimization.

### Possible bugs / mismatches

- **B1 (REAL, oracle-invisible): boot-window garbage.** boot.asm loads the sound blob
  INSTEAD of the RAM-clearing idle program, so SfxChannels ×7, duck bytes, and SeqChannels
  are power-on garbage until the first Snd_LoadSong. `Sequencer_Frame` jumps to `.run_sfx`
  even with SND_SEQ_ACTIVE=0 → **Sfx_Frame walks 7 garbage channels every frame from the
  first tick** (garbage SCF_ACTIVE ⇒ stream interpretation over random pointers — chip and
  bank-latch writes possible); garbage duck folds into every pre-song volume write.
  Exposure: boot → first PlayMusic. **Net-zero fix:** replace init's
  `ld (SND_SFX_QUEUE_CNT),a` (:205) with `call Sfx_StopAll` (clears active bits,
  priorities, queue cnt, both duck bytes; returns a=0; pre-ei). Also fix the header
  comment ("over the idle program" → "instead of").
- **B2. Snd_LoadSong repost race — Z80-side shape for snapshot-and-clear-early:** all five
  param reads move to entry; bank→SND_SONG_BANK and ptr→Snd_SongBase survive the wipe
  (0 net); PATCHPTR must stage via push/pop (+2 B — SND_SEQ_PATCHTAB is INSIDE the wiped
  region, the exact bug :1101-1104 records); FLAGS stashes via SND_FM6_ADAPTIVE (+6 B);
  clear moves to entry AFTER the snapshot (snapshot-first residual window ~1000× smaller
  than today's). **Net ≈ +8 B** — pay from H1/H2. Zero-byte fallback: clear-early alone
  (fixes the swallowed-repost half; a torn load self-heals next poll, SH_CHCOUNT clamp
  bounds one garbage frame).
- **B3.** Snd_LoadSong header claims ISR-only reach (":1042 the DAC loop is PAUSED") —
  false since the Timer-A tick services the mailbox (the file contradicts itself at
  :1122). Replace with the tick-context safety argument. Same stale phrasing at :734.
- **B4.** :496-497 describes the deleted per-iteration-ei design. **B5.** :1439/:1452
  "main.asm's phase block" → the soundBankHead macro (sound_bank.inc) is the contract now.

### sound_constants.asm audit

Stale/wrong: :23 SND_REQ_SFX "reserved (Phase 1C)" (live mailbox); :836-838 sfh_priority
bit7 "RESERVED (Stage B)… keep < $80" (Stage B/C LANDED — bit 7 is the live non-latching
flag, the guidance is now wrong); :841-849 sfh_gain/sfh_cap "INERT in Stage A" (both read
live); :96 vs :98 LFO-rate self-contradiction (:98 still says the value :96 explicitly
corrects); :62 SND_SAMPLE_TEST dead + stale label; request-slot list silently skips +$04
(placeholder comment wanted); SND_SEQ_TEMPO legacy note accurate (first byte to reclaim if
needed). Everything else verified: Timer-A pin + retune tripwire, SND_LOOP_CYC matches the
verified loop, the derived-chain asserts complete, SeqChannel/SfxChannel shared-prefix +
(ix+d) range asserts, MEV opcode-space asserts exhaustive.

### dac_sample_tab.asm

Banked (zero headroom cost); 5 dead bytes/descriptor are deliberate forward-compat —
don't resident-ize without touching Snd_DacLookup's ×9. Size assert present; ids/offsets
verified vs the constants and Snd_StartSample's reads. :12 same soft-stale main.asm
pointer.

### Checked and already fine

**Cycle-balance proof re-derived and matches exactly** (FILL 195 / DRAIN 195 / DRAINING
194; exx preserves flags so the post-exx jp z is correct). No code executes from the
$8000 window (data-only, stated + honored). Timer-A mailbox reach paths + spill/reload
bracketing correct; PollMailbox_Banked restores the possibly-NEW sample bank in the right
order. SetBank 9th-bit xor fix correct. Ring math safe (PRIME 128 ≤ TARGET 200 < 256; WR
can never lap RD; page-wrap sound under the 256-align assert). `.stop` ordering matches
the click-avoidance rationale. Idle-loop ei window genuinely catches the /INT pulse. Blob
even-pad + code-ceiling asserts correct.

**Landing order (size ledger):** H1 −23..28 → H2 −10 → H3 −13 (cadence-audit) → H4 −6 →
B1 ±0 (bug fix) → B2 +8 (race fix) → M1 −1 ⇒ **net ≈ −45..−50 B**.

---

## 27. engine/sound/sound_sequencer.asm + seq_opcode_tab.asm

**Per-tick worst case ≈ 35,000 T ≈ 58% of the Z80 frame** (10 channels, note-ons, 2 patch
loads); held-note frames ≈ 6,100 T ≈ 10% — the write-on-change discipline genuinely works.

### High-impact

- **H1. The per-channel tempo gate is provably redundant** (:94-97): the loader seeds all
  channels identically and the only other writer broadcasts one value — all accumulators
  are in lockstep forever. Real S3K uses ONE global TempoWait — a global gate is MORE
  S3K-exact. Compute once per frame, test per channel. **−40 T/ch/frame (~−400 @10ch),
  −15..25 B resident, −2 B/channel RAM.** Verify: no per-channel writer (checked: none);
  A/B onset timing vs mt_ref.vgm/S3K refs; SFX Sfx_Frame separate (spot-check).
- **H2. Page-align SeqOpcodeTable + high-byte-constant dispatch**: move the table to FIRST
  in soundBankHead (the phase block is align $8000 → page-aligned for free). Dispatch
  ~114 T → ~84 T, 13 B vs 17 B. **−30 T per coord op, −4 B.** Verify: no consumer assumes
  sound_tables_z80 starts at exactly $8000; lst check `& $FF == 0`; golden self-test.
- **H3. `jp Seq_ContinueFetch` double-jump → retarget to `Sequencer_NextOpcode.fetch`**
  (~14 handlers, 3 B either way) — **−10 T per zero-tick op, zero size**. Keep the
  trampoline for the four `jr` users.

### Medium

- **M1.** `sc_porta_incr` high byte is 0 by construction (both writers force it) — drop
  the `or (ix+…+1)` from 4 gate sites: −19 T/ch/frame, **−up to 12 B**.
- **M2.** Cache `sc_flags` in a register through ModUpdate (4-6 separate bit (ix+d) tests
  @20 T) — −40..60 T/ch/frame; HAZARD: Fm_NoteOff mutates the flags mid-routine — reload
  after mutating calls or restrict to the pre-notefill gates.
- **M3.** Factor Porta_Apply's EIGHT near-identical 16-bit compare ladders (~11 B each)
  into one helper — **−40..60 B resident** at +28 T/call (glide frames only). The single
  biggest clean size recovery in the file.
- **M4.** Seq_HookNoteOn/SetVol operand hoists — −5..8 B.

### Micro

`.multipoint`/OpBias pointer-math folds (−4 B, −20 T each, arp-hot); PitchEnv tail reload
→ `dec c/ret nz` (−2 B); inline the dec-gate = +5 B → REJECT under the space regime;
all-channels-ended songs keep walking (an active-count fold would save ~500 T/frame in
that state, +bytes, optional).

### Possible bugs / mismatches

- **B1. PSG portamento down-glide 16-bit underflow evades the snap** (:332-346): rate >
  current divisor wraps to $FFxx, the overshoot test reads it as still-above, stores a
  garbage divisor, keeps gliding through wrapped space up to ~65536/rate frames. Trigger:
  high note (top 13 divisors are 1!) + fast glide down. FM shielded by FnumApplyDelta
  (verify). Fix: snap on the borrow (`jr c,.psg_snap` off the sbc).
- **B2. A vol-env body whose byte 0 is $80 (Loop) hangs the driver** (Psg :701-706 / Fm
  :779-783): loop→cursor 0→$80→infinite loop inside the Timer-A tick (DAC starves).
  Hand-authored bodies, no packer between author and driver. **Zero-Z80-byte fix:
  build-time assert in the table generator (first body byte < $80).**
- **B3.** Mod_Advance FM pack can bleed into block bits at the extremes (block 7 +
  fnum+accum ≥ $800; single-step correction skipped) — likely unreachable with authored
  deltas; document or clamp.
- **B4/B5.** Stale reserved-opcode range comment (:1785 vs the table's actual $F1,
  $FA-$FE); stale line refs (:1842; sound_constants :999 claims sc_last_pan is the
  largest offset — it's sc_detune +58, the assert is what actually protects it).
- **B6.** Sequencer_StopAll leaves SCF_KEYED/SCF_ACTIVE stale (known) — see the SFX
  review's B1 for the missed consumer; add the contract comment.

### Checked and already fine

Dispatch idiom right given hl-must-survive; banked-table/resident-handler split honored +
asserted; zero-tick fetch keeps hl live with documented push/pop invariants; channel walk
add-ix-de with offsets < +127 asserted; write-on-change enforced at every render seam;
MacroTick's unmasked part byte safe (Fm_YmWrite tests bit 0 only); timer/DAC guards in
both raw-write doors; RepeatEnd edges verified; ModSet no-ordering-hazard; no iy in
per-tick paths, no mul/div, djnz where it fits.

---

## 28. engine/sound/sound_sfx.asm

### Invariant status (B0 — the three load-bearing Stage B/C invariants)

1. **7-bit priorities + bit7 flag: INTACT at source** (build-fatal guard confirmed;
   runtime masks correctly) — but see B2 for queue drift.
2. **SfxChannel=68 / sx_pad+58 stays 0: INTACT** (struct assert; full-struct wipe on every
   allocation; no +58 writers; transcoder never emits MEV_DETUNE) — but protected only by
   transcoder CONVENTION (B4).
3. **StopAll/SCF_KEYED gotcha: STILL LATENT at source; Sfx_Restore carries the fix — but a
   second consumer was missed** (B1).

### Possible bugs

- **B1 (HIGH confidence, audible). `Sfx_DuckRamp` re-asserts volume on a STOPPED song's
  channels** (:358-383): the held-note re-assert walk gates on per-channel
  ACTIVE/OVERRIDE/KEYED only — **no SND_SEQ_ACTIVE gate** (unlike Sfx_Restore:1069).
  StopMusic → stale KEYED PSG channel → any ducking SFX → the ramp's "changed" path walks
  the dead song's channels → Psg_SetVolume un-silences the channel at its stale latched
  tone → **drones until the next song load** (Psg_SilenceAll writes attenuation only,
  never tone). FM side benign. Fix (+5 B): gate the WALK on SND_SEQ_ACTIVE after `.store`
  (the level must still update). Verify: hotkey build, StopMusic mid-note + ducking SFX,
  listen + oracle-read PSG latches; rendered A/B.
- **B2 (latent drift).** Queue arbitration compares RAW priority (SfxDispatch:572 enqueues
  unmasked; drain max-scan + overflow eviction compare it) — a future bit7 SFX would get
  +128 queue weight, contradicting the 7-bit model. 2-byte fix (`res 7,b`).
- **B3 (design note).** Continuous-SFX pings consume the one-per-frame drain — a per-frame
  ping at priority P starves lower-priority queued SFX until pings stop. The 5b
  dispatch-stage extend (consume pings before the queue) is the fix; concrete reason to
  prioritize it.
- **B4.** Alias fields (sc_noise_mode≡sx_priority, sc_detune≡sx_pad) protected only by
  "the transcoder drops those ops" comments — add python-side asserts ($F2/$F6 never in
  SFX streams) + a test: zero Z80 bytes.
- **B5.** Stale comment z80_sound_driver:590 ("resolve blob + init slot 0 + steal voice" —
  SfxDispatch only enqueues since Task 9).

### High-impact (SIZE): S1-S6 ≈ −80..110 B total

S1 merge the duplicated id→blob resolve preamble (Dispatch vs BeginSound, ~35 B each) —
−25..30 B. S2 build-time SfxSlotKind table collapses the slot→kind double table chase —
−13..20 B net + cycles. S3 page-fit assert on the 29-byte contiguous table block → drop
the carry-propagate triplet at ~7 sites — −16..24 B, drift-proofed by the assert. S4
restructure DrainQueue's scan to the fixed-address 3-way max the enqueue overflow path
already proves — −15..25 B (preserve the earlier-slot tie rule). S5 slot wipe 16-bit
counter → djnz or LDIR — −3 B + ~1,000 T per SFX start (add `len ≤ 255` assert). S6
dedupe the two identical channel-record stride blocks — −8..12 B (or stash iy in the
unused-by-5a SND_SFX_QUEUE_HEAD/TAIL pair — zero new RAM).

### Medium / Micro

M1 steady-state de hoist = +3 B (code-growing — only after headroom recovers). M2 scan
RAM re-reads (small). M3 worst-case trigger frame ≈ ~15k T ≈ 25% of a Z80 frame (2-ch FM
steal ×2) — trigger-frame only; steady-state idle ≈ 0.6k T; the drain-one-per-frame
design already amortizes bursts. M4 Sfx_Frame banks SFX_BLOB_BANK every frame — cached
no-op today via the same-bank assert; keep it load-bearing. Micro: QueueEntryPtr header
over-claims a; drain tie comment "FIFO" only true absent overflow; Stage-C countdown
tri-state correct (verified) — add the "inc = $FF test" comment.

### Checked and already fine

Override-gate coverage COMPLETE for current content (ModUpdate early-return, RekeySingle
pending-arm, RegDelta consume-skip, PsgNoise latch-skip, MacroTick gates; RegWrite's
deliberate non-gate documented with its growth condition). **FM restore completeness
verified**: patch re-upload + op-bias, pan shadow zeroed for MEV_PAN refire, volume
re-fold with live duck, re-key from sc_base_freq via NoteOnFreqExact (avoids both the
NOTE_RAW wrong-note trap and double-detune), keyed-off-between-notes symmetric. PSG/noise
restore on-change + rate-3 clock re-emit + no-music silencing all correct.
MusicKeyOffKeepKeyed's flag-safe KEYED snapshot verified against both NoteOffs.
Arbitration ordering correct (MinActiveKind before own ACTIVE; victim restore before slot
re-init). Queue overflow semantics match the documented model; StopAll drains the queue +
resets duck; Snd_LoadSong calls it. Bank discipline correct incl. the cold-boot no-song
case. The `:1278-1299` edge-case audit block re-verified — none of its four claims has
drifted.

---

## 29. engine/sound/sound_fm.asm + sound_psg.asm + sound_tables_z80.asm

### ⓪ YM2612 write-spacing audit — **VERDICT: PASS** (every path spaced by construction)

No busy-poll by design; every YM write funnels through `Fm_YmWrite` (:59-72). Traced every
caller against conservative hardware numbers: address→data 21 T ≥ ~8 T ✓ (even without
the nop it matches shipped SMPS); data→next-address tightest path ~50 T ≥ ~39 T ✓; no
path reaches a second write in under ~50 T. $28 always part I ✓; $A4-before-$A0 everywhere
✓; single-threaded vs DAC (every YM-touching entry terminates in Fm_ReparkDac — verified
at all 8 sites); no $2B write exists in either file ✓. Caveat: 68k-side YM writes
(init/error) are uncoordinated — fine while they only happen with the driver stopped
(see boot finding 3).

### sound_fm.asm

High: **1.** Fm_WriteFreq's scratch round-trip is dead weight in the hottest path
(:942-968, per-frame vibrato/porta): Fm_YmWrite preserves bc — keep ch/part in registers,
delete 4 loads + 2 stores: **−14 B, −80 T per modulated channel per frame** (no external
scratch readers — grepped). **2.** Fm_SetVolume calls Snd_ChanClass TWICE for mutually
exclusive folds (:358, :410) — one call dispatches both: **−5 B, −65 T per volume write**
(fires per note AND per duck/fade frame). **3.** Factor the 4× RoutePart+stash prologue —
**−13..20 B**.
Medium: PatchOpGroup re-reads invariants per op (hoist base+ch: ~−900 T/patch load,
size-neutral); the fold-clamp block repeats 3× (~−12..15 B); PatchLoad header-write
scratch reloads (−10 B).
Micro: the two nops in Fm_YmWrite are removable (−2 B, −8 T per write — every write in
the driver; 17 T still exceeds the ~8 T requirement and matches shipped SMPS; keep only
as insurance); Fm_NoteOff header over-claims de.
Bugs: **10.** stale "INLINE, not banked" header (:21-26) — the tables ARE banked-window
data (the per-use comments are correct; fix the header + the twin claims in psg/tables).
**11.** Fm_PatchLoad writes $B4 from the patch (:179-186) — clobbers sc_pan on mid-song
patch changes unless the sequencer re-asserts pan after MEV_PATCH; verify sequencer-side
or source the $B4 byte from sc_pan. **12.** FnumApplyDelta block-bit bleed at extremes
(block 0/7 corrections skipped) — unreachable with current ±127 detunes; document.
Fine: part I/II pairs + chsel gap correct; RegDelta extraction matches the build-asserted
constants; FM6/DAC keyon gate at the single chokepoint covers all producers (ungated FM6
TL/freq/pan writes while DAC owns ch6 are harmless); EG retrigger discipline correct;
CarrierMaskTableZ correct for the physical op order; TransposeClamp + the alg-5+ opbias
fix verified.

### sound_psg.asm

High: **1 (likely REAL bug).** `Psg_ApplyMod`'s floor guard doesn't match its own comment
(:299-308): "clamp to 1, not 0" but the code clamps only NEGATIVE sums — an exact-zero
divisor (top 13 table entries have divisor 1; accum −1 reaches it) passes and writes
divisor 0 to the chip (chip-ambiguous). Psg_EmitNoiseClock does it right (:373-377) —
copy that clamp (+5 B). Behavioral → rendered A/B. **2.** PsgVolEnv_Resolve /
FmVolEnv_Resolve are byte-identical except three constants — merge: **−17 B resident,
zero cycles — the single biggest headroom win in these files.** **3.** Single
Snd_ChanClass in Psg_SetVolume (+ deletes a push/pop): **−9 B, −90 T per PSG volume write**
(hot via PsgEnvUpdate).
Medium: Psg_VolToAtten rewrite (`cpl/and $7F/srl×3` — provably identical for all 256
inputs): −3 B, frees b; **5.** Psg_NoteOn's detune fold has NO range guard (negative
detune on divisor-1 notes wraps to $FFxx — same failure family as finding 1); **6.** no
pitch clamp on the PSG note path (note > 94 reads past the table into LogVolumeLutZ) —
verify upstream clamping or comment the asymmetry vs FM's TransposeClamp.
Micro: env-fold clamp is one table away from a channel-select-corrupting wrap (max delta
$10 + max atten $0F = $1F exactly — a future env byte ≥ $11 ORs into the latch channel
bits): generator-side assert. Dead labels `.skip_base_latch`/`.skip_rearm`; contradictory
hl comments; stale banked-claim header.
Fine: no-PSG-delay is correct on MD (VDP wait-states the Z80); mute values correct;
noise discipline matches the deliberate S3K-faithful MEV_PSGNOISE design; volume order
gain→env→duck with per-stage clamps; ch<<5 via rrca×3 valid; ix-preservation holds.

### sound_tables_z80.asm

**1.** Header flatly wrong about placement ("no $8000-window banking" — sole include site
is INSIDE the bank-head phase block); fix in tools/gen_sound_tables.py's header emission.
Consequence worth knowing: the tables cost ZERO resident headroom. **2.** No size asserts
on the four core tables (FmPitchTableZ/PsgDivisorTableZ 190 B each, LogVolumeLutZ 256,
CarrierMaskTableZ 8) — FMPITCH_MAX_IDX currently trusts a comment; generator-emit the
asserts. Fine: pitch table 95 entries, block-0 octave = FNUM_LO exactly, little-endian
matches the read order; divisor clamps ($3FF floor, 1 ceiling — which is what makes the
PSG findings live); log LUT monotonic; env ctl bytes match the S3K-exact format with the
S3K relative-jump bug deliberately not replicated.

**FM/PSG size ledger: ~55-70 B reclaimable, chip-stream-identical except the Psg_ApplyMod
fix (the only rendered-A/B-required change).**
