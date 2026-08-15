# DESIGN DRAFT — the HBlank schedule: local removal

**Date:** 2026-08-16
**Status:** DRAFT. Owner sign-off required before any code (work order 2026-08-16, queue item 0 —
this changes the raster program's wire format, which is a STOP-and-brief row of the standing rules).
**Queue item:** 0 / 2 (they are the same item; the ruling took the schedule work as the vehicle).
**Acceptance criterion (from the work order, not negotiable):** it must unblock the DRY direction
entry in `docs/DEFERRED_WORK.md`, and both boundaries — palette and parallax — must change together.

---

## 1. The defect, stated exactly

`Raster_PatchAll` (`engine/effects/raster.emp:959-993`) CLAMPS a patchable record's fire line into
the record's authored band. It cannot suppress the record, because the arm words are RELATIVE gaps
and the handler's cursor advance is IMPLICIT — record `k` is left behind only by having been walked.
So:

- **Below the screen.** OJZ channel 0 is banded `3..214`. With the water anchor at screen line
  `>= 224` the fire pins at 214 and paints rows 214-223 wet in a world that is entirely dry. Ten
  rows, sustained, on the ordinary scroll path.
- **`PATCH_ANCHOR_NONE` is a lie.** `$7FFF` is documented as the inert anchor, and it is inert only
  because it lands in a branch nobody reaches. A program carrying a record on a channel a preset
  parked would pin that record at `hi` forever.
- **The parallax side is deliberately wrong in the same direction** (`parallax.emp:801-812`): the
  `cmpi.w #224` exit exists and is unreachable, because the band clamp above it caps `L` at `hi`.
  It is written that way on purpose so the two boundaries are wrong TOGETHER.

The general statement, which is the thing worth fixing: **Aeon can add a record to a frame's
schedule but cannot remove one.** Everything above is a symptom of that.

---

## 2. What the corpus settles

Verified against the disassemblies this session, not from memory:

| source | anchor above screen | anchor below screen | how a schedule is chained |
|---|---|---|---|
| **Ristar** `$00D3BA-$D410` | clamp the line to **0** (whole screen takes the effect) | `d0 = $FF` -> writes `$8AFF` (**park**) AND clears the arm flag `$ea92` | each node writes its own successor into the RAM vector `$ea72` (`move.l #$be14,$ea72.w`, `:14556-14595`) and its own gap into `$8Axx` |
| **Ristar node body** `$00E142` | — | — | `tst.w $ea92 / beq.w <rte>` — a disarmed effect costs exception entry + 3 instructions; the flag is ONE-SHOT (`move.w #0,$ea92` on fire), and a second independent flag `$e5b4` gates a second payload in the same node |
| **S3K** `:8489-8499`, `HInt5 :1064-1108` | `Water_full_screen_flag` + counter `-1` (park) | `cmpi.w #$DF,d0 / move.w #$FF,d0` — **park**, not clamp | one installed handler, swapped by pointer (`H_int_addr`) |
| **S.C.E.** `Water Effects.asm:29-42` | `st Water_full_screen_flag` + `st H_int_counter` | `moveq #-1,d0` — **park** | one handler |
| **Sonic 2** `:5280-5292` | `Water_fullscreen_flag` + counter 223 | **clamp to 223** — the defect above, verbatim | one handler |
| **Gunstar / Alien Soldier** (survey Q4, ruling 4a) | — | — | counter reprogrammed from inside the handler; Alien Soldier parks with `$8AFF` so the interrupt fires exactly once per frame |
| **Batman & Robin** (survey ruling 1a) | — | — | self-modifying RAM handler, ~26 cycles, saves nothing |

**Three of four Sonic-family engines DISARM below the screen. Only Sonic 2 clamps, and Aeon
inherited Sonic 2's answer without inheriting its excuse** — S2 has exactly one HInt effect, so
parking costs it nothing.

**The corpus's chaining idiom is not a data structure.** Ristar's "linked list" is a chain of CODE
nodes, each rewriting the RAM vector to its successor. Aeon's equivalent of that vector is
`Raster_Cursor`, and its equivalent of a node is a record. The property worth importing is not the
spelling — it is that **a node's successor is a value somebody chooses**, rather than a consequence
of having walked the previous node's body.

**Modern framing, because it changes which option looks natural.** What Aeon does today is a
RETAINED display list: build once, patch in place forever. What Ristar does per frame — and what
every command-buffer renderer since has done — is RE-RECORD the list each frame from the live state.
The retained form is the one that makes removal hard, in exactly the way it always has.

---

## 3. Options

All three fix the acceptance criterion. They differ in where the cost lands and how much of the
format moves.

### Option A — a NEXT link per record (Ristar-faithful)

Record becomes `[arm][opc][ops...][link]`, `link` a self-relative byte displacement to the successor.
Handler's `.advance` becomes `adda.w (a1),a1 / move.l a1,Raster_Cursor`. Suppressing record `k` is
one store into record `k-1`'s link.

- **Cost:** ~+12 cycles per fire, on the ~60-cycle HBlank budget — the scarcest budget in the engine.
- **Blast radius:** EVERY program, static ROM ones included; every hand twin; `raster_words`;
  `arm_word_index`; the dense-tier program structs; docs. The handler changes.
- **Why the corpus does it this way:** its nodes are code, so there is no cursor to recompute.

### Option B — an armed flag tested by the handler (Ristar's `$ea92`, literally)

The handler tests a per-record flag and skips the payload. **It does not work here without Option A
anyway:** skipping the payload still has to advance the cursor past the op bodies, and the only
thing that knows their length is a link or a length word. Ristar can do it because its node is code
and its `rte` is its own advance. Rejected on that ground, not on cost.

### Option E — re-record the schedule each VBlank  *(RECOMMENDED)*

`Raster_PatchAll` stops patching bytes in a copy and becomes `Raster_BuildSchedule`: each VBlank it
walks the ROM template's records and EMITS the live ones into `Raster_Buf_B`, computing the arm
words as it goes. A suppressed record is simply not emitted.

- **Handler: completely unchanged.** Zero added HBlank cycles. The emitted program is exactly the
  shape `Raster_HInt` already walks — the same header, the same records, the same terminator.
- **Static ROM programs: completely unchanged.** They never enter this path.
- **Wire format: the record body does not move.** What changes is the PATCH TABLE, which is our own
  descriptor, read by exactly two procs.
- **Cost moves from the interrupt to VBlank**, where it is ~50 words of copy plus per-record
  arithmetic, off the critical path and adjacent to the work this proc already does.
- It is the command-buffer answer, and it makes the two future wins reachable (§7).

**Recommendation: E.** A is faithful to Ristar and buys nothing that E does not, while spending the
one budget the whole effects suite is rationed by. The reference is an input, not an authority
(`feedback_decide_by_best_overall`); the reason Ristar links nodes is that its nodes are code.

---

## 4. Option E in detail

### 4.1 The patch table (the only format that moves)

Today, per record, 4 words: `[arm_off][line_src][band_lo_fl][band_hi_fl]`, where `arm_off` is the
byte offset of the arm word this entry REWRITES (the arm of record `k-2`, pre-resolved).

Proposed, per record, 5 words:

```
[rec_off][rec_len][line_src][band_lo_fl][band_hi_fl]
```

- `rec_off` — byte offset of THIS record's own start inside the template body.
- `rec_len` — its length in bytes, arm word through last op word.
- `line_src`, `band_lo_fl`, `band_hi_fl` — unchanged, still fire-line space.

`arm_off` disappears: under E the builder knows where it wrote each arm word, so no offset history
is pre-resolved into ROM. `rec_off`/`rec_len` are cross-checked at comptime against each other
(`rec_off(k) + rec_len(k) == rec_off(k+1)`, last one against the terminator's offset) — the same
"second independent path" pattern that already holds `arm_word_index` against the emitter.

Header (count word) and trailer position change accordingly: the trailer moves from
`RASTER_BUF_SIZE + 2 + 8*records` to `+ 10*records`. That constant appears in exactly one runtime
site (`Raster_InstallPatched`) and in the hand twins.

`Raster_GetChannelBand` skips `arm_off` today and will skip two words instead of one. Otherwise
untouched.

### 4.2 The builder

```
Raster_BuildSchedule (VBlank, replaces Raster_PatchAll):
  src  = template body (= Patch_Tab - RASTER_BUF_SIZE)
  dst  = Raster_Buf_B
  copy header word + the two priming records          ; 5 words, fixed
  prev_arm[0] = &dst[word 1]   (priming 0)   L_hist[0] = 0
  prev_arm[1] = &dst[word 3]   (priming 1)   L_hist[1] = 1
  for each table entry k:
      line = line_src < 0 ? Effects_Screen_L[ch] - 1 : line_src
      if patchable and line > RASTER_MAX_FIRE_LINE: continue      ; THE REMOVAL
      clamp line into [band_lo_fl, band_hi_fl]
      copy rec_len bytes from src+rec_off to dst
      write $8A00 | (line - L_hist[0] - 1) into prev_arm[0]        ; the two-back slot
      shift the 2-deep history: prev_arm[0]=prev_arm[1]=..., L_hist likewise
  copy the terminator ($8AFF, $FFFF)
  leave the two youngest arm slots at $8AFF (they park by construction)
```

The 2-deep history IS ruling 1b (`arm at record i schedules the fire that lands record i+2`),
expressed as a shift register instead of as a pre-resolved offset. This is the whole of the change.

### 4.3 The suppression rule, and the three-state machine

One rule, one constant, used by every consumer, all reading the SAME latched
`Effects_Screen_L[ch]`:

| latched L | palette fire | parallax split | frame-top ship |
|---|---|---|---|
| `L <= 0` | clamped to band lo (harmless — the ship repaints above it) | split at line 0, band clamp SKIPPED | **ships** (whole screen) |
| `1 <= L <= 223` | fires at L, clamped into the band | splits at L, clamped into the same band | no |
| `L >= 224` | **record not emitted** (NEW) | `.bands_ready` — band clamp SKIPPED (NEW: the test moves above the clamp) | no |

The parallax change is three lines: move its existing `cmpi.w #224 / bge .bands_ready` from after
the band clamp to before it, exactly mirroring the `ble .anchor_top` test that already sits there
for the other direction. **The two sides must land in the same commit** — that is the
DEFERRED_WORK entry's explicit instruction, and shipping either alone converts a consistent error
into a disagreement.

The threshold is a NUMBER shared by both sides (`L >= 224`, i.e. `> RASTER_MAX_FIRE_LINE`), not a
published bit. A published suppression bitmask was considered and rejected: the builder runs in
VBlank and the parallax reader runs in the main loop, so a bit written by the builder is one tick
stale to its reader — the exact cross-camera skew `Effects_LatchWorldLines` exists to prevent.
Deriving from the shared latch keeps both answers on one camera.

### 4.4 What does NOT change

- `Raster_HInt` — not one instruction.
- The emitted program body format, `raster_program`, `raster_words`, every static fixture, both
  dense-tier program structs, `Raster_Program_None`.
- The off-screen ship, its trailer, and its `L <= 0` gate.
- `Raster_CopyPatchedTemplate` is DELETED: the per-frame build subsumes the install-time copy
  (`clean_not_bolted_on` — no dormant second path).

---

## 5. Correctness arguments to be attacked by the lens sweep

1. **A negative gap is impossible.** `check_intervals` (comptime) keeps bands strictly ascending and
   disjoint; removal only ever widens a gap. Formally: the emitted sequence is a subsequence of the
   authored one, and gaps between successive members of a subsequence of a strictly increasing
   sequence are >= the authored gaps. So `$FF`/park-by-accident cannot appear.
2. **Density is only relaxed by removal**, by the same subsequence argument, so the comptime
   `check_density` worst case remains an upper bound.
3. **The last two emitted records park.** The builder writes an arm word only when a record two
   later is emitted; slots never written keep the template's `$8AFF`. To make that structural rather
   than incidental, patched templates should emit `$8AFF` in EVERY record's arm word (all of them
   are recomputed anyway), so an un-overwritten slot is a park by construction, never a stale gap.
4. **Empty schedules work.** If every record is suppressed, priming record 1's arm is never written
   and stays `$8AFF`: two priming fires on lines 0-1, then nothing. That is exactly S3K's parked
   counter.
5. **No cross-frame state.** The schedule is rebuilt from ROM at every frame top, so a frame's
   program never inherits a half-updated predecessor — which is the failure mode the in-place
   patcher's "must run in VBlank" note is guarding against today.

---

## 6. Gates — structural only, and gate the COMPOSITE

Oracle pixel capture is not usable here (work order §"READ THIS FIRST": three protocols each killed
by their own determinism control; `BgAnim_Update` rides the lag-immune `Logic_Tick`, so cross-build
pixel comparison is unsound). Every gate below is structure.

The lesson this parcel inherits is that a gate built around the mechanism you implemented cannot see
the requirement you did not implement. The composite here is **{fire, parallax split, ship}** across
**three anchor states** — so the gate is a 3x3 matrix, not a check that the record vanished:

| | fire | parallax | ship |
|---|---|---|---|
| `L <= 0` | record present, arm chain lands it at band lo | split at 0 | entry queued |
| mid-screen | record present, arm chain lands it at L-1 | split at L | not queued |
| `L >= 224` | **record absent from Buf_B; chain skips it** | no split | not queued |

Instruments, all of which this tree has already proved non-vacuous:

- **Walk the emitted chain in `Raster_Buf_B`** after a forced anchor (`write_memory` into
  `Effects_World_Y`, then one frame): sum the arm gaps from the priming records and assert the
  resulting fire-line set EQUALS the expected set. This is the only gate that sees both halves at
  once — the record's absence AND the surviving records still landing on their lines.
- **A breakpoint at `.op_region`** for the suppressed frame: it must not be hit. (An arm-word
  assertion alone would not catch a record that vanished from the chain but still executed.)
- **`Parallax_Shadow_Bands`** must show no anchored split in the suppressed frame.
- **Poison control in the SAME run**: force `L` back on screen and re-read; every assertion must
  flip. A gate that only ever sees the suppressed state is measuring nothing.
- **Comptime**: hand twins for the new 5-word table entries, plus the `rec_off + rec_len` chain
  ensure, plus `first_mismatch` on the whole patched image (body + padding + table + trailer).
- **A VBlank cost measurement** before/after via the profiler, recorded in the benchmark dir. The
  builder is more work than the byte patcher and the claim "it is free because it is in VBlank"
  must be a number, not an assertion.

---

## 7. What this unlocks, explicitly OUT OF SCOPE for this parcel

Named so the format is not designed in a way that precludes them, and so nobody reads them as
promises:

- **The disjoint-band budget could go.** `check_intervals` exists only because a runtime overlap
  would produce a negative gap. Under E the builder computes the gap and could resolve a collision
  itself (suppress the loser, or enforce a minimum separation), which would let every channel
  traverse the whole screen and would take the residual dry error to zero instead of to ~9 rows.
  It needs a runtime density policy (per-record cost in the table) and a collision-priority ruling,
  so it is its own parcel.
- **Runtime reordering.** The builder emits in whatever order it likes, so world anchors could cross
  without the program being rebuilt. Not needed by any content today.

**The residual this parcel accepts, and the owner should weigh it now:** with the band at `3..214`
and suppression at `L >= 224`, the rows between are still clamped — at `L = 220` the boundary
renders at 214, six rows wrong, and crossing `L = 223 -> 224` flips ten rows at once. The DRY
direction is fixed only in the sense the DEFERRED_WORK entry states (below the screen = dry). If the
owner wants the residual gone, §7's first bullet is the parcel that does it, and it should be
decided BEFORE this one is planned, because it changes whether the bands stay comptime-disjoint.

---

## 8. Traps carried in (from the work order, verified as still live)

- A cross-seam reference is invisible to `build.sh` and breaks sigil port targets. New symbols
  (`Raster_BuildSchedule`) must go into `crates/sigil-harness/repin.toml` AND each `*_port` test's
  carrier table.
- A link-time address cannot enter an emitted image a comptime pin compares. The table stays
  offsets; the builder adds bases at runtime.
- `$8AFF` IS the park word, so any encoding change must still answer what a negative gap means. E's
  answer is that it cannot occur (§5.1) rather than that it is detected.
- Gate the composite, not the op you wired up.
- The byte-moving ritual applies (repin -> refreeze --ab), and both repos merge as a pair.

---

## 9. Open questions for the owner

1. **Option E over Option A?** E is the recommendation; A is the Ristar-faithful spelling and costs
   ~12 cycles of a ~60-cycle HBlank budget forever.
2. **Does §7's band-budget parcel come first, or does this ship with the ~9-row residual?**
3. **Is the 5-word table entry acceptable**, or should `rec_len` be derived from the next entry's
   `rec_off` to hold the table at 4 words (smaller, one less cross-check)?
