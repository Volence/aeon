# System / input / replay / boot — lens-panel adjudication packet

**Review SHA:** `ffe05158` (pinned; worktree `.worktrees/system-lens`, branch `review/system-lens-sweep`)
**Corpus:** `engine/system/**` (~5,185 lines), `engine/debug/**` (826), `engine/{ram,structs,irq,z80_bus,coords}.emp`, `games/sonic4/test/**`, `games/demo/**` — plus the handler-reachable effects code the walks forced open (`engine/effects/raster.emp`, `palette.emp`).
**Panel:** the ratified roster — A · A2 · B1 · B2x2 · C1x2 · C2x2 · C3x2 · C4x2 · C5 · V. 15 read-only seats,
doubled seats on opposed walk orders and mixed models.
**Adjudication:** every load-bearing citation re-verified by the overseer. Verification marked per finding.
No seat reported BLOCKED. Seat V additionally read sigil's source to verify two cited backstops.

---

## 1. Headline

~175 commits landed here since 2026-07-16 with no multi-seat review ever. The layer turns out to be
**the best-defended one we have swept** — and the defects that survived are concentrated in one place
nobody owned.

**The counterweight first, because it is load-bearing.** Seat B1 returned a clean verdict with evidence:
`ram.emp` is 905 lines of `region`/`vars` with **zero hand-placed addresses**; every proc read declares a
register contract; the `z80_stopped` bracket is a compiler-proven context at all 20 sites with no
hand-spelled triad anywhere. Seat A2 measured a **~82% comment true-rate** against the sound layer's 65%
and identified why — this layer's claims are backed by `ensure`, a machine-checked `@budget(cycles:)`, and
the `requires(vblank)`/`grants(vblank)` capability system, so prose cannot drift far from the numbers.
Seat C3b cleared the DMA source-register ordering, the 128 KB split, the 6-button cadence and the boot
VDP-isolation window. Seat C2b **verified three prior review items were genuinely fixed in code**, not
merely marked closed.

**Where the defects are.** Four of the most serious findings live in the **raster/palette effects seam** —
main-loop producers feeding IRQ4/IRQ6 consumers. The Effects P1/P2 audits reviewed the effects code; this
panel reviewed the system code; **neither owned the interaction between them.** That seam is the single
clearest lesson of this sweep.

---

## 2. Confirmed defects, ranked

### S1 — The DMA jump-table stride guard measures a struct, not the emitted slot · HIGH
**Seat:** V · **Overseer-verified: YES**

```
dma_queue.emp:287  ensure(sizeof(DMAEntry) == 14, "the jump-table slot stride is spelled as 14 fixed bytes…")

jt_slot emits:     lea VDP_CTRL, a5       // abs.l -> 6
                   lea DMA_Critical, a1   // abs.w -> 4   <-- RELAXATION OUTCOME, unguarded
                   bra.w {drain}          // pinned STRUCTURAL -> 4      = 14
```
The guard measures the struct; the slot width is a different quantity that happens to equal it. The
`bra.w` is pinned; the middle `lea`'s 4-byte form depends on `DMA_Critical` living in `upper_ram`
(`w_addressable`) and **nothing states or guards that dependency**.

Move the `DMA_Queue` block to `lower_ram` — an ordinary RAM-layout parcel — and the `lea` relaxes to
abs.l, slots become 16 bytes, `sizeof(DMAEntry)` is still 14, `DMA_CRITICAL_SLOTS` is still 8, **both
ensures pass**, and `Process_DMA_Critical` jumps to `.jump_table + 14k`. For k=1 that is the third byte of
a six-byte `lea` — a garbage opcode inside IRQ6, once per frame, whenever the Critical queue is non-empty.

**The cited second wall does not exist.** `dma_queue.emp:319` claims the `targets(.slot_0…8)` clause "say[s]
the same thing". Seat V read sigil's source: `targets` feeds CFG reachability and cycle-budget walks, is
stored as a plain `Vec<String>`, and is **never checked for equidistant placement**.

### S2 — `Pal_Variant_Stage` is streamed to CRAM by IRQ4 while the main loop rewrites it · HIGH
**Seat:** C2a · **Overseer-verified: producer/consumer pair confirmed; runtime interleave not observed**

`Palette_DeriveVariant` writes 128 bytes of `Pal_Variant_Stage` from the main loop at IPL `$2300` — IRQ4
live. `raster.emp:487` (`lea Pal_Variant_Stage, a2`) streams from the same buffer inside `Raster_HInt`.
**No latch, no double-buffer, no mask.** `raster.emp:93` names both sides as a contract: "The derive happens
at frame time … the handler only streams."

Trigger: any armed raster program carrying `OP_PAL_REGION` (the shipped water-cluster shape) on a frame
where a composition layer set `PAL_ACT_VARIANT_STALE` — i.e. exactly the cycling/fade frames a region
effect is authored for. Consequence: the region boundary paints a blend of two variants, recurring every
frame the variant is re-derived. Not a one-off.

**Note the asymmetry:** `raster.emp:79-82` already reasons about this class for the *VDP command latch*
("Every main-loop VDP command pair reachable while a program is armed must sit inside an `ints_off`
bracket"). The RAM-source side of the same handler never got the same treatment.

### S3 — The "dirty flag is set only after a complete write" lemma is false; the palette path lacks the bracket the sprite path has · HIGH
**Seat:** C2a · **Overseer-verified: YES (the asymmetry)**

`vblank.emp:301-306` states both enqueues safe by one lemma. The lemma holds only for the *first* setter of
a bit: `Palette_Compose` runs five layers over the **same** `Palette_Buffer`, each ORing its lines into
`Palette_Dirty` **before the next layer rewrites those lines**.

Verified: `Sprite_Emit_Active` exists (`sprites.emp:206/490/512`) and is honoured (`buffers.emp:242`).
**`Pal_Compose_Active` does not exist** — grep returns nothing. The NEW-3 bracket was reasoned out for
sprites and never carried across.

Cleanest trigger is the brief's own "lag frame during a section crossing": `.base_copy` sets dirty for lines
1-3, `.cycling` then rotates those lines in place, IRQ6 lands mid-rotate, `VInt_Lag` runs
`Enqueue_Dirty_Buffers` **and** `Process_DMA_Critical` — CRAM receives a partially-rotated span. One frame
of torn palette on the crossing frame.

### S4 — The replay net records inputs but not the scenario; Tails and Knuckles are structurally unreachable · HIGH
**Seat:** C4a · **Overseer-verified: YES**

```
ojz_scroll_test.emp:479  tst.b  Input_Source
                  :480   bne    .done      // replaying or recording: stand down
```
and the **only** writer of `Character_ID` anywhere is `:514` — inside that routine. So the net cannot select
a character *by construction*. We had recorded this as a fixture gap; it is not one, and re-recording can
never fix it.

Root cause: everything besides button state — game state, act, character, cheats, spawn — lives outside the
stream. Three consequences fall out: the character block; **no automated runner is possible** (the ROM cannot
arm playback — `Input_Source` is only ever `clr.b`'d, and entry is a documented human oracle-poke recipe);
and pass/fail is not machine-readable (`Replay_Done` is written twice and **read nowhere**; failure is a
crash screen).

### S5 — A second Critical-enqueue path bypasses the byte cap and both drop counters · HIGH
**Seats:** B2a and C4a, independently · **Overseer-verified: YES**

| | `dma_queue.emp` | `buffers.emp:45-62` (`queue_static_dma`) |
|---|---|---|
| byte-cap charge | `:131-136` | **absent** |
| cap rollback | `:233` | **absent** |
| `DMA_Overflow_Count` | `:170`, `:235` | **absent** — bare `ori.b #1, ccr` |
| `Dbg_DMA_Enq_Capped` | `:182` | **absent** |

Seven splice sites (4 palette lines, SAT, both HScroll variants) — up to **1,664 B/frame** of Critical DMA
enqueued without charging, while `ram.emp:219` calls that cell the "running enqueue-side byte" total and
`vblank.emp:138` asserts every enqueue charges it. True by name, misleading about the resource.

Sharper: `buffers.emp:209-210` documents the static drop as *reachable* ("during a fade + heavy art
staging") — and that is precisely the drop that increments no counter. The debug counter is blind on the one
path its own header says will fire.

### S6 — Two half-installed registry rows: a live per-frame reader, a full body, no producer · HIGH
**Seat:** A · **Overseer-verified: YES**

- **`Game_Paused`** (`ram.emp:480`): read every frame at `objects/core.emp:471` to branch into
  `RunObjects_Frozen`, a complete render-only sweep. **Zero writers.** Boot-clear makes the branch
  provably unreachable. `ENGINE_ARCHITECTURE.md` documents a designed pause overlay never built — so this is
  correct pre-built work with no marker saying so, unlike `PlaneMapToVRAM` which carries an explicit
  forward-scaffolding disclaimer.
- **`SpriteMask_Y` / `_Height` / `_After_Band`** (`ram.emp:458-460`): read at `sprites.emp:437/439/754/755`.
  **Zero writers.** The band check runs every band of every frame and always falls through;
  `InsertSpriteMasks` is unreachable. `ram.emp:455-457` documents a write protocol no code performs.

Seat A's full census: of 288 declared cells, **10 have zero references anywhere**, 30 are write-only (19
legitimately — MCP-read debug counters), 6 are read-only with a live reader. Newest orphan: `Raster_Line`,
landed with the P1 raster core, referenced only in the plan doc because the shipped `raster.emp` retired the
line-compare design and the RAM row survived.

### S7 — The Z80 idle body's size is gated by nothing in either shipped shape, and the hole geometry does not fit · MEDIUM
**Seats:** V (registry) + A2 (arithmetic) · **Overseer-verified: YES**

`z80_init.emp:50`'s `ensure(extern("Z80_IDLE_SIZE") == 40)` measures the boot-side literal against a
literal — the body's real span appears nowhere in the condition. Worse, sigil's `native.rs:643` excludes
`z80_init` from the shared registry ("sound-on shapes must not place it"), and both canonical shapes are
sound-on, so **the ensure is never evaluated in either shipped ROM**. The deferred second half — the
whole-ROM anchor gate — is declared `when = "sound_off"`.

And the geometry does not fit: `0x3FE - 0x3D8 = 38`, but a **40-byte** body at `$3D8` ends at `$400`. So
`map.toml:136`'s `at = 0x3FE` — machine-consumed, not a comment — would place post-hole data two bytes
inside the idle body. **Open question, needs build access:** re-derive `at` from the real 40-byte body
rather than patching the stale "38-byte" prose in `boot_data.emp:20` and `map.toml:135`.

### S8 — `Pad_x_Type` was missed by the raw-shadow fix applied to its siblings · MEDIUM (dormant)
**Seat:** C2b

`11dbf25f` (2026-08-13) moved `Ctrl_x_Held`/`Press` to raw-shadow-then-latch because a lag VBlank
overwrote a running tick's input. `Pad_1_Type`/`Pad_2_Type` are written by the same routine on the same
every-VBlank cadence **straight to the published cell** — no shadow, no `VInt_Level`-only latch. Dormant
only because nothing reads them yet. An incomplete fix of a class this codebase already diagnosed once.

### S9 — `.dense_body` omits the blanking delay both sparse CRAM paths carry · MEDIUM (latent)
**Seat:** C3a

`.op_cram` and `.op_region` each burn `EFX_BLANK_DELAY` before their CRAM write — the row-119 fix,
oracle-measured 2026-08-13, and the module's own doctrine says it is "now unconditional". `.dense_body`
(Task 5, the tier that fires *every* line) has no delay and reaches CRAM ~118 cycles earlier. Latent: the
gradient op has no shipping consumer yet. It lands ahead of the feature.

### S10 — `Read_Controllers` holds the Z80 bus ~1,030 cycles every VBlank, contradicting the file's own claim · MEDIUM
**Seat:** C3a

`vblank.emp:119-121` states the flag-bracket byte write is "the ONLY 68k bus hold in the sound build."
`Read_Controllers` wraps the entire two-port 6-button burst in one unconditional `with z80_stopped`
(~1,030 cycles ≈ 134 µs ≈ 2.1 scanlines), on every physical VBlank including lag frames. The Z80 is halted
throughout, so the DAC holds its last sample — a DC hold repeating at exactly 60 Hz.

The engine already owns the fix it did not apply here: `SND_CTRL_DMA_ACTIVE` exists precisely to keep the
Z80 off the 68k bus without halting it.

### S11 — `ReleaseFault` never releases a held Z80 bus · MEDIUM (lean shape only)
**Seat:** C2a

Any fault taken inside a `with z80_stopped` body (reachable: `Read_Controllers`' burst,
`Section_RedrawPlanes`' storm, `BG_Init`'s blit) leaves the Z80 halted for the life of the freeze. The
player gets a red screen with a **permanent DC buzz plus a sustaining chord** — the one failure mode a
"halt loudly" handler should not produce. One `move.w #$0000, Z80_BUS_REQUEST` fixes it and satisfies the
no-stack ruling. The proc is absent from both canonical shapes, so no gate has ever executed one
instruction of it.

---

## 3. The pattern, now at four instances

Add to the sound sweep's three (D8 linker asserts, the `f4b270f8` parity-test claim, the pkg1 DEBUG
exclusivity assert):

**The stack canary.** `ENGINE_ARCHITECTURE.md:3916` specifies a `$DEAD` sentinel below the stack base,
checked once per VBlank. Grep for `$DEAD`/`STACK_GUARD` across the tree: **zero hits** (Seat C5). Designed,
documented, never built — and it is the only runtime tripwire that would catch SP descending into variable
RAM, on the shape whose headroom is thinnest.

Four instances, four authors, four landings. The recommendation stands: a merge-ritual step that greps a
landing's own prose for mechanism claims and requires each to resolve to a `file:line`.

---

## 4. Convergences

- **`VInt_Level` / `VInt_Lag` are one pipeline written twice** — C4a and C4b independently, each citing the
  same three shipped-or-near-shipped bugs as evidence (the `$8F02` autoinc invariant NEW-1, the held/press
  split, the chain-77 art-budget reload). C4a proposes one `comptime fn vint_pipeline(full: bool)`.
- **The DMA byte ledger is reconstructed in VBlank from data the enqueuer already had** — C4a (altitude) and
  B2a (duplication), same target, different lenses. See S5.
- **Four perf items found by both C1 seats on opposed walks:** the `Drain_Budgeted_Queue` RAM round-trip,
  the `VBlank_Handler` `movem` width, the `.charge_critical` loop structure, and the `Replay_Hash`
  `subq/bne` the conventions outlaw.
- **The write-only/read-only RAM census** — A, C4b, C5 and V all reached it independently from four lenses.

**One cross-seat synthesis neither seat could see alone:** both C1 seats found `VBlank_Handler`'s `movem`
saves 15 registers where the reachable union is 11 (~64 cycles/frame, zero bytes), and both correctly
declined to recommend it — the wide list is a deliberate ⊤-bound for future handlers installed via
`VInt_Ptr`. But C4a established `VInt_Ptr` has **exactly one value**, one writer, plus a documented lethal
zero-state race at boot. Retire the indirection and the `movem` narrowing becomes safe by construction.
They are one parcel.

---

## 5. Perf and footprint (estimates, not measured)

**Perf** (C1a/C1b): static sum ~−300 to −450 cycles/frame off a ~4,300-cycle VBlank window. C1a's own
prediction of the *measured* result is **−60 to −140**, citing this codebase's documented 4-5x optimism
history and naming which findings sit next to VDP writes where FIFO back-pressure absorbs the gain. That
calibration is the most honest number in the sweep and should be quoted with any proposal.

**RAM** (C5, measured): ~370 B reclaimable in every shape (9 zero-reference cells), plus ~1,030 B
DEBUG-only — `Replay_Check_Log` is 2x oversized (the record loop's own guard caps checkpoints at 128; the
array is sized 256) and the `DMA_Peak_*` triple is neither written nor read. Nothing touches a hot path.

**Correction to a number we carry:** the "~3.8 KB DEBUG stack headroom" traces to commit `170e43e3`'s own
message, whose cited arithmetic (`$FFFFFF00 − $FFFFE002`) gives **7,934 B**. Re-derivation puts DEBUG at
~7.1-7.6 KB and release at ~17.7 KB. Estimated, not build-verified — but the headroom has never been as
tight as recorded.

---

## 6. Open questions requiring something outside this tree

1. **Re-derive `map.toml`'s `[[hole]] at` from the 40-byte idle body** (S7). Needs a build.
2. **Who owns the effects/system seam?** S2, S3, S9 and S10 all live where main-loop effects producers meet
   ISR consumers. Effects P1/P2 reviewed one side, this panel the other. That seam needs an explicit owner
   or it will keep accumulating.
3. **Does the sound driver tolerate a `z80_stopped` bracket landing in its init handshake?** C3a flagged
   `boot.emp:307` unmasking IRQs before `Sound_Init`, making `VInt_Lag`'s bus request land mid-driver-init —
   a structural sibling of the documented boot YM race, introduced by a newer path than the spec covers.

---

## 7. Verified-clean (recorded so it is not re-litigated)

- `z80_stopped` bracket pairing — compiler-proven context, 20 sites, zero hand-spelled triads (B1, B2b).
- Three prior review items confirmed genuinely fixed in code (C2b): `buffers` bug #1 (dirty bits now cleared
  only on carry-clear), `vblank` bug #3 (`VInt_Lag` re-asserts `$8F02`), `game_loop` B1 (clear/arm pair now
  inside `with ints_off`).
- The deb2 appendix placement claim is exactly as advertised — Seat V read
  `native.rs:3738`'s `check_error_handler_is_last()` precondition plus its positive-control magic check.
  Strongest wall in the layer.
- The boot YM key-off race is correctly scoped: C3b checked every other `z80_stopped` site and every direct
  YM path; `Sound_Init`/`Sound_PostByte` touch only a mailbox byte, so **the dual-owner class does not
  recur**.
- 68000 vector table complete in both arms (64 cells each), all targets resolve, all four shape predicates
  spell `DEBUG == 1 || CRASH_REPORT == 1` (A).
- `games/demo` implements every declared contract member; nothing the engine requires is sonic4-only (A,
  B2b). The agnosticism claim holds.
- The 6-button cadence is correct against the documented protocol on real hardware, not just against the
  oracle's device model — C3a phase-mapped it against the canonical high-first table.
- The `Ctrl_1_Held` "frame-stable" falsehood from the character sweep has **no surviving siblings** (A2).

## 8. Not covered

- No seat ran a build or the emulator (read-only mandate). S1's severity assumes sigil relaxes
  `lea <lower_ram_sym>, An` to abs.l — that follows from `w_addressable` existing at all, but was not
  built to confirm.
- `PageIn_Flush` not freeing a cancelled decode's VRAM frame (C2a, adjacent) belongs to the level lens.
- The Z80 driver's inner loop was not audited, so C3a's F3 (flag-raise with no acknowledgment window) is
  medium-confidence on existence and low on hit rate.
