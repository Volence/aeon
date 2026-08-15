# DESIGN — the HBlank schedule: local removal

**Date:** 2026-08-16
**Status:** REVISION 2, post-lens-sweep. Owner sign-off required before any code (work order
2026-08-16 queue item 0 — this changes a wire format, which is a STOP-and-brief row).
**Reviewed at:** master `9884783d` by three adversarial seats (hardware/timing, correctness/state,
gate vacuity) plus a Fable adviser on scope. §11 records what the sweep changed.
**Acceptance criterion:** unblock the DRY direction entry in `docs/DEFERRED_WORK.md`, with the
palette boundary and the parallax boundary changing together, in one commit.

---

## 1. The defect, stated exactly

`Raster_PatchAll` (`engine/effects/raster.emp:959-993`) CLAMPS a patchable record's fire line into
the record's authored band. It cannot suppress the record, because arm words are RELATIVE gaps and
the handler's cursor advance is IMPLICIT — a record is left behind only by having been walked. So:

- **Below the band.** OJZ channel 0 is banded `3..214`. Once the water anchor passes screen line
  214 the fire pins there and paints rows 214-223 wet in a world that is dry below the anchor. Up
  to ten rows, sustained, on the ordinary scroll path.
- **`PATCH_ANCHOR_NONE` is a lie.** `$7FFF` is documented as the inert anchor and is inert only
  because nothing reaches the branch. A program carrying a record on a channel a preset parked
  would pin that record at `hi` forever.
- **The parallax side is deliberately wrong in the same direction** (`parallax.emp:801-812`): its
  `cmpi.w #224 / bge .bands_ready` exit is unreachable, because the band clamp above it caps `L`
  at `hi`. Written that way on purpose so the two boundaries are wrong TOGETHER.

The general statement, which is the thing worth fixing: **Aeon can add a record to a frame's
schedule but cannot remove one.** Everything above is a symptom of that.

---

## 2. What the corpus settles

Verified against the disassemblies this session and re-checked by the timing seat:

| source | anchor above the boundary's reach | anchor below it | how a schedule is chained |
|---|---|---|---|
| **Ristar** `$00D3BA-$D410` (disasm `:16180-16204`) | `moveq #0,d0` — clamp the line to **0**, whole screen takes the effect | `move.w #$ff,d0` -> `$8AFF` (**park**) AND `move.w #0,$ea92` (**clear the arm flag**) | each node writes its own successor into the RAM vector `$ea72` (`move.l #$be14,$ea72.w`) and its own gap into `$8Axx` |
| **Ristar node** `$00E142` (`:16970-17018`) | — | — | `tst.w $ea92 / beq.w $00E1D0` (a bare `rte`) — a disarmed effect costs exception entry + 3 instructions; the flag is ONE-SHOT (cleared at `$00E14A`); a second flag `$e5b4` gates a second payload in the same node |
| **S3K** `loc_6C8E`, `sonic3k.asm:8509-8515` | `Water_full_screen_flag` + counter `-1` | `cmpi.w #$DF,d0 / move.w #$FF,d0` — **park**, not clamp | one handler, swapped by pointer (`H_int_addr`) |
| **S.C.E.** `Water Effects.asm:29-45` | `st Water_full_screen_flag` + `st H_int_counter` | `moveq #-1,d0` — **park** | one handler |
| **Sonic 2** `s2.asm:5280-5292` | `Water_fullscreen_flag` + counter 223 | **clamp to 223** — Aeon's behaviour, verbatim | one handler |
| **Gunstar / Alien Soldier** (survey Q4, ruling 4a) | — | — | counter reprogrammed inside the handler; Alien Soldier parks with `$8AFF` so the interrupt fires exactly once per frame |

Cite `loc_6C8E`, **not** `HInt5`: HInt5's own header says "Seems to be unused"
(`sonic3k.asm:1061-1062`). The live twin makes the same point without citing dead code as shipped
practice.

**Three of four Sonic-family engines disarm rather than clamp. Only Sonic 2 clamps, and Aeon
inherited Sonic 2's answer without inheriting its excuse** — S2 has exactly one HInt effect, so
parking costs it nothing.

**The corpus's chaining idiom is not a data structure.** Ristar's "linked list" is a chain of CODE
nodes, each rewriting the RAM vector to its successor. Aeon's equivalent of that vector is
`Raster_Cursor` and its equivalent of a node is a record. The property worth importing is not the
spelling — it is that **a node's successor is a value somebody chooses**, rather than a consequence
of having walked the previous node's body.

**Modern framing, because it decides which option looks natural.** Aeon today keeps a RETAINED
display list: build once, patch in place forever. Ristar — and every command-buffer renderer since
— RE-RECORDS the list each frame from live state. The retained form is the one that makes removal
hard, in exactly the way it always has.

---

## 3. Options

### Option A — a NEXT link per record (Ristar-faithful)

`[arm][opc][ops...][link]`, `link` a self-relative displacement. `.advance` becomes
`adda.w (a1),a1 / move.l a1,Raster_Cursor`. Suppression is one store into the predecessor.

- **Cost:** ~+12 cycles per fire on the ~60-cycle HBlank budget — the scarcest budget in the engine.
- **Blast radius:** every program including static ROM ones, every hand twin, `raster_words`,
  `arm_word_index`, both dense-tier structs, the handler.

### Option B — an armed flag tested by the handler (Ristar's `$ea92`, literally)

Does not work here without Option A anyway: skipping the payload still has to advance the cursor
past the op bodies, and only a link or a length word knows how far. Ristar can do it because its
node is code and its `rte` is its own advance. Rejected on that ground, not on cost.

### Option E — re-record the schedule each VBlank  *(RECOMMENDED)*

`Raster_PatchAll` becomes `Raster_BuildSchedule`: each VBlank it walks the ROM template's records
and EMITS the live ones into the inactive raster buffer, computing arm words as it goes, then swaps
buffers. A suppressed record is simply not emitted.

- **`Raster_HInt` is untouched — zero added HBlank cycles.** The emitted program is exactly the
  shape it already walks.
- **Static ROM programs are untouched.** They never enter this path.
- **The record body format does not move**, so `check_arm_layout`, every static fixture and every
  body pin survive. What changes is the PATCH TABLE — our own descriptor.
- Cost moves to VBlank (§4.6 is honest about where in VBlank).
- It is the command-buffer answer, and §8's follow-on becomes reachable.

**Recommendation: E.** A is faithful to Ristar and buys nothing E does not, while spending the one
budget the whole effects suite is rationed by. The reference is an input, not an authority
(`feedback_decide_by_best_overall`): Ristar links nodes because its nodes are code.

---

## 4. Option E in detail

### 4.1 The patch table (the only format that moves)

Today, per record, 4 words: `[arm_off][line_src][band_lo_fl][band_hi_fl]`, `arm_off` being the byte
offset of the arm word this entry REWRITES (the arm of record `k-2`, pre-resolved).

Proposed, per record, 5 words:

```
[rec_off][rec_len][line_src][band_lo_fl][band_hi_fl]
```

- `rec_off` — byte offset of THIS record's own start (its arm word) inside the template body.
- `rec_len` — its length in bytes, arm word through last op word.
- the other three unchanged, still fire-line space.

`arm_off` disappears: the builder knows where it wrote each arm word, so no offset history is
pre-resolved into ROM.

`rec_len` stays EXPLICIT rather than derived from the next entry's `rec_off` (the draft's old open
question 3, ruled by the adviser): deriving it deletes the thing being checked.

Table header and stride: `[count]` then `10 * count` bytes. The trailer therefore sits at
`RASTER_BUF_SIZE + 2 + 10*records` — note the `+2`, the count word. Three runtime sites read the
table, not two: `Raster_InstallPatched` (`raster.emp:852`, currently `lsl.w #3` for the 8-byte
stride), the builder, and `Raster_GetChannelBand` (`:1049`, `addq.l #2` -> `#4`). Ten is not a
shift and `mulu` is forbidden: the stride is `lsl.w #3` plus twice the index, spelled once.

### 4.2 The builder

```
Raster_BuildSchedule (VBlank only):
  src = template body (= Raster_Patch_Tab - RASTER_BUF_SIZE)
  dst = the INACTIVE buffer (§4.4)
  copy header word + the two priming records          ; 5 words, verbatim
  arm_slot[0] = &dst[word 1]      (priming record 0's arm)
  arm_slot[1] = &dst[word 3]      (priming record 1's arm)
  prev_line   = 1                 (priming record 1 fires on line 1)
  for each table entry k:
      if line_src >= 0:  fl = line_src                        ; static record
      else:              L  = Effects_Screen_L[ch]            ; SCREEN space
                         if L > band_hi:  continue            ; THE REMOVAL (§4.3)
                         fl = clamp(L - 1, band_lo_fl, band_hi_fl)
      copy rec_len bytes from src+rec_off to dst
      store $8A00 | (fl - prev_line - 1) into arm_slot[0]     ; ONE-back line, TWO-back slot
      arm_slot[0] = arm_slot[1]; arm_slot[1] = &this record's arm
      prev_line   = fl
  copy the terminator ($8AFF, $FFFF)
  store $8AFF into arm_slot[0] and arm_slot[1]                ; park, BY CONSTRUCTION
  swap the active buffer; Raster_VBlank rewinds the cursor into it
```

**The arm slot is two records back; the line delta is ONE record back.** Ruling 1b says the word
written at record `i` schedules `gap(L[i+1] -> L[i+2])` — so the value is a delta against the
*previous* line while the *slot* is two back. The shipped runtime is the twin (`raster.emp:967`
seeds `prev = 1`; `:985-987` computes `line - prev - 1`), and the hand pin proves the number:
`arm0 = $8A00 | (99 - 1 - 1) = $8A61` (`ojz_effects.emp:639-640`).

**The two youngest arm slots are parked explicitly, and that is what makes park structural.** A
record's arm is written only when a record two later is emitted, so the last two emitted slots are
never written by the loop. Parking them at the end means the template's own arm words are never
load-bearing — no all-park template variant, no fork of `check_arm_layout`, no hand-twin churn. It
also makes the empty schedule correct for the right reason: with zero records emitted the two
slots ARE the priming records, both parked, two no-op fires on lines 0-1 and nothing after.

### 4.3 The suppression rule, and the three-state machine

**Suppress a record when its latched screen line is past the band it can reach: `L > band_hi`.**

One rule, one coordinate (SCREEN space), one authority (the record's own band words, which
`Raster_GetChannelBand` already serves to the parallax side). It subsumes `L >= 224`, since
`band_hi <= 223` always.

| latched L | palette fire | parallax split | frame-top ship |
|---|---|---|---|
| `L <= 0` | clamped to `band_lo` — harmless, the ship repaints above it | split at line 0, band clamp SKIPPED | **ships** (whole screen) |
| `band_lo <= L <= band_hi` | fires at `L` | splits at `L` | no |
| `L > band_hi` | **record not emitted** (NEW) | **no split** (NEW: the test moves above the clamp) | no |

**Why the rule is `L > band_hi` and not the shared constant 224.** The two directions are not
symmetric. Clamping UP at `band_lo` is safe because something else covers the uncovered rows — the
frame-top ship, which is Ristar's clamp-to-0 in a different spelling. Clamping DOWN at `band_hi`
covers nothing: it paints rows wet that the world says are dry, which is a lie rendered on screen.
Making that state unrepresentable means every remaining error is in the INERT direction (a row that
should be wet renders dry), which is the direction all three disarming references chose.

It also removes a defect the sweep found in revision 1, where §4.2 tested a fire line against a
screen constant: at exactly `L = 224` the record was still emitted and clamped, painting the full
ten-row stripe, while parallax and the ship had already gone dry — the disagreement
`DEFERRED_WORK.md:4600-4604` explicitly forbids, on the one row the parcel exists to fix.

**The residual, honestly.** For `band_hi < L < 224` the boundary renders nowhere instead of near the
screen bottom: at `L = 215` with `band_hi = 214`, nine rows render dry that should be wet. Clamping
is closer to the truth below ~219 and suppression is closer above it; neither dominates, and the
crossover is not a number worth encoding. What actually shrinks this is the band, and the adviser
found the cheap half: OJZ channel 1 is a gate fixture whose position is explicitly negotiable
(`ojz_effects.emp:599-603`), so re-banding it to the bottom two lines lets channel 0 reach ~220 and
takes the worst case from nine rows to about three, inside the existing disjoint-band rule. §8 is
what takes it to zero.

**Parallax must apply the same rule from the same table.** It already calls
`Raster_GetChannelBand`; the change is to test `L > band_hi` BEFORE clamping and take
`.bands_ready`, mirroring the `ble .anchor_top` test that already sits there for the other
direction. **Both sides land in one commit** — that is the DEFERRED_WORK entry's explicit
instruction, and shipping either alone converts a consistent error into a disagreement.

A published suppression bitmask was considered and rejected: the builder runs in VBlank and the
parallax reader in the main loop, so a bit written by the builder is one tick stale to its reader —
the cross-camera skew `Effects_LatchWorldLines` exists to prevent. Deriving from the shared latch
plus the shared table keeps both answers on one camera.

### 4.4 Double-buffered, not patched in place

The builder writes the INACTIVE buffer and swaps `Raster_Active_Buf` + `Raster_Cursor` when it is
done. `Raster_Buf_A` is free for the whole lifetime of a patched program (`Active_Buf` is Buf_B
today), and P1 reserved the pair "for exactly this".

This is not tidiness. Building in place would move records under a `Raster_Cursor` left over from
the previous frame — today the buffer's LAYOUT is a frame invariant and only arm bytes change, so a
stale cursor always points at a record boundary; under compaction it would not. Double-buffering
makes "no cross-frame state" true instead of merely argued, and it is what lets the install path
drop its main-loop rebuild (§4.5).

### 4.5 Lifecycle — the five paths, stated

The sweep's first blocker was that revision 1 deleted `Raster_CopyPatchedTemplate` as if it were a
copy loop. It is also the install half of the patched path: `Raster_Active_Buf`, `Raster_Program`
(nonzero is what makes `Raster_VBlank` process anything) and `clr.l Raster_Pending` — the last of
which another file's guard is written around (`preset.emp:129-130`: whichever installs last wins
destructively, and that clear is what kills a staged static program). Those three stores MIGRATE
into `Raster_InstallPatched`; only the copy dies.

| path | `Raster_Program` | `Active_Buf` | `Patch_Tab` | `Pending` | `Offscreen_Entry` |
|---|---|---|---|---|---|
| install patched | -> live buffer | -> live buffer | -> table (FIRST) | cleared | from trailer, or cleared |
| patched -> patched | as above, rebuilt next VBlank | swapped by the builder | new table | cleared | re-derived |
| patched -> static ROM | set by `.copy_program` | -> Buf_A | **cleared** | consumed | **must be cleared** (see below) |
| explicit clear | 0 | untouched | cleared | consumed | **must be cleared** (see below) |
| no program | 0 | untouched | 0 | 0 | 0 |

Two of those cells are a live latent defect this parcel should close while it is here: neither
`Raster_VBlank`'s clear path (`:497-504`) nor `.copy_program` (`:505-517`) clears
`Effects_Offscreen_Entry`, so a torn-down patched program's ROM trailer would keep shipping as a
frame-top palette DMA (`buffers.emp:279-315`) on every frame its stale anchor reads `L <= 0`.
Unreachable today; this is the parcel that makes the third consumer's state machine explicit.

`Raster_InstallPatched`'s tail call `jbra Raster_PatchAll` (`:874`) is DROPPED. Under E it would be
a full mid-frame rebuild of the live buffer while `Raster_HInt` may be walking it — and it is
unnecessary, because an install already takes effect at the next `Raster_VBlank` by contract. The
comment at `preset.emp:245` that justifies `Effects_LatchWorldLines`' placement by that tail call
moves with it. (Dropping it also removes a pre-existing hazard: today the install-time 128-byte
copy blats the live buffer from the main loop.)

### 4.6 Cost, and where in VBlank it lands

`Raster_VBlank` runs inside the sound-ON DMA-flag / sound-OFF `z80_stopped` bracket, before
`Flush_VDP_Shadow` and every DMA drain, on BOTH `VInt_Level` and `VInt_Lag` (`vblank.emp:157`,
`:289-291`). So builder cycles (a) delay the drains inside the blanking window `DMA_Budget_Default`
was tuned against, (b) lengthen the window the Z80 DAC drain has to survive — the "Z80 headroom
tight" invariant — and (c) land twice per logic tick on lag frames, which are the frames already
over budget.

Estimated ~250-350 cycles per record plus a fixed 5-word copy, i.e. ~1.2-2.3k cycles for a 4-6
record program: roughly 2.5-4.5 scanlines of the ~38-line NTSC VBlank, and something like 5-10x the
`Raster_PatchAll` it replaces. That is an ESTIMATE and is written here as one. It is still obviously
the right trade against Option A's +12 cycles inside a per-fire ~60-cycle budget, but §7's
measurement must be scoped to the bracket and the lag path, not to the proc's own duration.

**Register budget is a design constraint, not an afterthought.** `Raster_PatchAll` declares
`clobbers(d0-d4/a0-a2)` and its own comment explains why that is a ceiling: `VInt_Level` and
`VInt_Lag` declare only through `d4`, and `Raster_BuildShipEntry`'s note records that saving a
register does not buy back its declaration. The builder wants a table cursor, a destination cursor,
a source cursor, an `Effects_Screen_L` base and two arm-slot back-pointers against three address
registers. It is solvable (hold the two arm slots as word offsets packed in one data register via
`swap`; re-`lea` the latch base per iteration, as `.op_region` re-`lea`s `VDP_CTRL`) but the
allocation belongs in the plan with a cycle number beside it.

---

## 5. Correctness arguments

1. **A negative gap is impossible.** `check_intervals` keeps authored bands strictly ascending and
   disjoint from `prev_hi = 1`; the emitted list is a SUBSEQUENCE of the authored one, and gaps
   between successive members of a subsequence of a strictly increasing sequence are >= the
   authored gaps. The seats attacked this with a static record interleaved among patchables, a
   suppressed first record, a suppressed last record and an all-suppressed program; none produces a
   negative gap. Corollary worth stating: a record clamped to `band_lo = 3` yields fire line 2 and
   gap `2 - 1 - 1 = 0` — `$8A00`, the every-line word — which is correct (a reload of 0 fires the
   next line) and reachable by ordinary arithmetic.
2. **The 8-bit arm ceiling survives removal.** Gaps only grow; the widest constructible is priming
   line 1 to fire line 222 = 220 <= 255.
3. **Density is only relaxed.** `check_density`'s worst case is pairwise between band edges, cost
   is per-fire, and removal only widens the gap: `cost(k-1) <= gap(k-1->k)*488 <= gap(k-1->k+1)*488`
   because bands strictly ascend.
4. **Park is structural, not inherited** (§4.2): the builder writes `$8AFF` into the two youngest
   arm slots itself, so no template byte is load-bearing and the empty schedule parks correctly.
5. **No fire can race the build.** The internal counter reloads from reg `$0A` on every line during
   VBlank (survey Q1), so no underflow occurs there; and the build targets the inactive buffer
   anyway (§4.4).
6. **What this does NOT fix, stated so it is not assumed:** two patchable records on ONE channel at
   different lines are legal today (`compose`'s guard 9 only refuses two patchables merged onto the
   same LINE), and `Raster_GetChannelBand` returns the FIRST match. At `L` past the first record's
   band, parallax clamps to that record while a second record on the same channel sits elsewhere —
   a disagreement with both sides reading the same latch. Either `raster_program` grows a
   one-record-per-channel guard (cheap, recommended) or this is an accepted residual named beside
   the ~3-9 row one. It does not block the parcel; leaving it unstated would.

---

## 6. Blast radius

**`engine/effects/raster.emp`** — `Raster_PatchAll` replaced by the builder (its `d0`-as-prev-line
seed, `subq.w #1` screen->fire conversion and `move.b d0, 1(a1,d1.w)` low-byte store all go);
`Raster_GetChannelBand:1049` stride; `Raster_InstallPatched:852` stride, `:866` the call to the
deleted proc, `:874` the tail call, plus the three migrated stores; `Raster_CopyPatchedTemplate`
deleted; the `PATCHED TEMPLATES` header `:762-778` and the `Raster_PatchAll` doc block `:920-958`
are both now wrong; `RASTER_MIN_FIRE_LINE`'s comment names a runtime twin that moves.

**`engine/effects/raster_dsl.emp`** — `patch_table` (5-word entries), `patched_words` (`4*` ->
`5*`), the new per-record content check (§7), `arm_word_index`'s remaining role, `ship_trailer`'s
offset prose, `raster_program`'s 128-byte ensure message (names the deleted proc), and the optional
one-record-per-channel guard.

**`engine/level/parallax.emp`** — the band-clamp/threshold reorder (§4.3).

**`games/sonic4/data/effects/ojz_effects.emp`** — `OJZ_TC_TABLE_HAND` to 5-word entries, the
`patched_words` length ensure, the whole-image pin. Every migrated twin keeps its separate `.len`
ensure: `first_mismatch` returns -1 when `a` is a PREFIX of `b`, and a twin short by a trailing
entry compares EQUAL — a defect this tree shipped once already.

**Elsewhere** — `preset.emp:126,130` (the exclusivity message names the deleted proc),
`ojz_scroll_test.emp:379-393`, `docs/ENGINE_ARCHITECTURE.md`, `docs/EFFECTS_AUTHORING.md`,
`docs/BUGS.md` (EFX-4's over-read half is stated against the fixed 128-byte copy),
`docs/DEFERRED_WORK.md:4575-4604`, `tools/effects_budget_model.toml`, and on the sigil side
`crates/sigil-harness/repin.toml` plus each `*_port` carrier table for any new cross-seam symbol,
then the repin/refreeze `--ab` ritual since every patched template's table changes length.

---

## 7. Gates — structural only, and the composite is PAYLOAD, not just lines

Oracle pixel capture is unusable here (work order: three protocols each killed by their own
determinism control; `BgAnim_Update` rides the lag-immune `Logic_Tick`, so cross-build pixel
comparison is unsound). Everything below is structure.

**The blind spot the sweep found in revision 1.** Every gate in the old §6 was phrased in FIRE-LINE
space — did the right lines get reached, did the wrong ones not. Option E introduces a byte-copying
builder, so the new failure class is a record that lands on exactly the right line carrying the
WRONG BYTES. That is last parcel's lesson reappearing in a new place, and it is the fourth axis the
3x3 matrix did not have.

| | fire line | fire PAYLOAD | parallax | ship |
|---|---|---|---|---|
| `L <= 0` | at `band_lo` | record's own ops, byte-identical | split at 0 | queued |
| mid-band | at `L-1` | as above | split at `L` | not queued |
| `L > band_hi` | absent from the chain | — | no split | not queued |

Instruments:

- **Walk the emitted chain** in the live buffer after forcing an anchor (`write_memory` into
  `Effects_World_Y`, one frame): sum arm gaps from the priming records and assert the resulting
  fire-line set EQUALS the expected set.
- **Read the emitted PAYLOAD back** in the same run and diff each surviving record's bytes against
  its expected op words. This is the gate revision 1 did not have.
- **A watchpoint on the destination address** the suppressed record would have written — NOT a
  breakpoint on `.op_region`, which is shared dispatch: it is unique to channel 0 on the OJZ
  fixture only by coincidence, and on any program with two `pal_region` channels the gate cannot
  distinguish suppressed-correctly from not-suppressed-at-all.
- **Cross-compare the two boundaries against EACH OTHER** in one frame — the fire line recovered
  from the buffer versus the split line `Parallax_Shadow_Bands` actually wrote — rather than each
  against a hand constant derived from the same formula. Otherwise a wrong shared threshold yields
  two wrong answers that agree.
- **Poison control in the same run**: force `L` back into the band and re-read; every assertion
  must flip.
- **Comptime**: hand twins for the 5-word entries (each with its own `.len` ensure), the whole-image
  `first_mismatch`, and a per-record CONTENT check — for every record, the emitted image words at
  `[rec_off/2, rec_off/2 + rec_len/2)` must EQUAL the body re-derived from `fires[k]`, with
  `out[rec_off/2]` an `$8Axx`-class word and `rec_off + rec_len` landing on the next record's arm or
  the terminator. The `rec_off(k) + rec_len(k) == rec_off(k+1)` identity alone is TAUTOLOGICAL: both
  fields come from one walk over `op_size`, so a uniform base error or a mispriced op telescopes
  consistently and the check never fires. `check_arm_layout` is the precedent — it indexes the
  emitted image and compares a VALUE.
- **A budget-model row** for the builder's VBlank cost in `tools/effects_budget_model.toml`, gated
  the way `raster_state_bytes` is. `tools/effects_budget_check.py` IS wired into `build.sh:191`
  (EFX-9 closed 2026-08-15 — verified, `docs/BUGS.md:56`), so this row re-runs on every build
  instead of being a number in a prose file that drifts, which is exactly how EFX-5 went stale.
- **A re-baseline, called out as work.** Under suppression OJZ channel 1 (anchor 314, band 216..223)
  vanishes whenever `Camera_Y < 91` instead of pinning at 223. That is the correct new semantics,
  but it changes what the shipped fixture renders across a large part of the camera range, so the
  P-a/P-b/W evidence captures are no longer reproducible and the "two channels coexist" proof shows
  one channel for much of the act.

**Known limitation, booked rather than hidden:** every runtime gate above is a foreground oracle
ritual that nothing re-runs. Encode the expected per-state fire-line and payload sets as a data
table in the fixture and script the session so re-running is one command; the durable answer is
queue item 1 (`replay_runner`), and this parcel is its second data point.

---

## 8. What this unlocks, explicitly OUT OF SCOPE

Named so the format is not designed to preclude them, and so they are not read as promises. The
adviser ruled scope **(c)**: rule the policy now in an addendum, ship local removal alone.

- **The disjoint-band budget could go.** `check_intervals` exists only because a runtime overlap
  would make a negative gap, and `$8AFF` IS the park word. Under E the gap is computed at runtime,
  so the builder can resolve a collision itself. The crux the adviser settled: this does **not**
  need per-record cost in the table. The fatal property (park-by-accident) needs ONE runtime
  compare — every emitted line strictly greater than the previous — and no cost model at all;
  density is merely cosmetic (`raster_dsl.emp:840-843`: an overrun does not drop the next fire, it
  pushes writes into active display) and can be closed with a single program-wide minimum
  separation in the header, derived at comptime from the existing `fire_cost_cycles`. What makes it
  a real parcel is the PRIORITY ruling (who yields) and the parallax-agreement contract, plus
  re-proving §5.1-5.3, which all rest on the disjointness it deletes.
- **Runtime reordering.** The builder emits in whatever order it likes. No content needs it today.

---

## 9. Traps carried in

- A cross-seam reference is invisible to `build.sh` and breaks sigil port targets silently: any new
  symbol goes into `repin.toml` AND each `*_port` carrier table.
- A link-time address cannot enter an emitted image a comptime pin compares. The table stays
  offsets; the builder adds bases at runtime.
- `$8AFF` IS the park word: §5.1 answers that a negative gap cannot occur, not that it is detected.
- Gate the composite. Here the composite is the payload, not the line.
- The byte-moving ritual applies, and both repos merge as a pair.

---

## 10. Open questions for the owner

1. **Option E over Option A?** E is the recommendation; A costs ~12 cycles of a ~60-cycle HBlank
   budget forever.
2. **Suppression at `L > band_hi` (recommended, §4.3) or at the screen edge `L >= 224`?** The former
   makes the wet-lie unrepresentable and errs inert; the latter keeps the boundary visible longer
   near the screen bottom but renders a lie above `band_hi` and pops ten rows at the edge.
3. **Take the free half of the residual?** Re-banding the OJZ channel-1 fixture to the bottom two
   lines costs nothing and takes the worst case from ~9 rows to ~3.
4. **Add the one-record-per-channel comptime guard** (§5.6), or book it as a named residual?

---

## 11. What the lens sweep changed (revision 1 -> 2)

Three seats plus an adviser, all against `9884783d`. Confirmed independently by three of them:

- **The arm arithmetic was wrong.** Revision 1 paired the two-back arm SLOT with the two-back LINE;
  the delta is one-back. Worked to a wrong answer in three rows by two seats and caught by the
  adviser from the hand pin. Every fire would have landed late, compounding down the frame.
- **The suppression threshold was stated in two coordinate systems** (fire-line in §4.2, screen in
  §4.3), leaving `L = 224` clamped-and-wet while the other two consumers had gone dry. Replaced by
  a single screen-space rule against the record's own band (§4.3).
- **Deleting `Raster_CopyPatchedTemplate` orphaned three install stores**, one of which another
  file's guard is written around. Now a five-path lifecycle table (§4.5).

Also adopted: park the two youngest arm slots in the builder (which kills the proposed all-park
template variant entirely, saving `check_arm_layout` and every hand twin); double-buffer into the
inactive buffer; drop the main-loop tail call; the tautological cross-check replaced by a content
check; the payload axis added to the gate matrix; the watchpoint replacing the shared-label
breakpoint; the boundary cross-comparison; the VBlank cost scoped to the DMA/Z80 bracket and the
lag path; the register budget promoted to a design constraint; the S3K citation corrected off dead
code; the fixture re-baseline named as work; the same-channel-two-records gap stated (§5.6).
