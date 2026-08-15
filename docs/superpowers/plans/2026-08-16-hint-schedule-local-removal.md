# HBlank Schedule Local Removal — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a patchable raster record removable from a frame's schedule, so a boundary whose world anchor has passed below the band it can reach stops rendering instead of clamping and painting rows the world says are dry — with the parallax boundary agreeing in the same commit.

**Architecture:** `Raster_PatchAll` (an in-place arm-byte patcher) is replaced by `Raster_BuildSchedule`, which re-records the whole schedule each VBlank from the ROM template into the INACTIVE raster buffer and then swaps. A record is removed by simply not emitting it. `Raster_HInt` is untouched, so no HBlank cycles are added; the patch table gains `rec_off`/`rec_len` and loses `arm_off`.

**Tech Stack:** 68000 assembly in `.emp` (sigil), comptime `ensure`/hand-twin pins, oracle MCP for structural gates.

**Design:** `docs/superpowers/specs/2026-08-16-hint-schedule-local-removal-design.md` (revision 2, owner-signed-off 2026-08-16). Owner rulings folded in: suppression rule is `L > band_hi`; the OJZ channel-1 fixture gets re-banded.

**Entry state:** aeon `950c7206`, sigil `1d89baf9`. `s4.bin` CRC `5acff780`. Suite 3721/0.

```bash
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
```

---

## Vocabulary, so the tasks below are readable

- **record** — one fire in the emitted program: `[arm][op_count][ops...]`. Records 0 and 1 are the
  PRIMING pair that fire on lines 0 and 1; the authored ones follow; a terminator ends the program.
- **arm word** — `$8Axx`, written to VDP reg `$0A`. The word written at record `i` is consumed at
  the NEXT fire and schedules the gap that lands record `i+2` (survey ruling 1b). So the SLOT is
  two records back while the LINE delta is one record back. Getting this backwards is the single
  most likely way to break this parcel; it is what the lens sweep caught in the design draft.
- **fire line vs screen line** — an effect authored to land on screen line `M` fires at `M-1`.
  Table fields `band_lo_fl` / `band_hi_fl` and everything inside the builder are FIRE lines;
  `Effects_Screen_L[]` is a SCREEN line. Exactly one conversion (`subq.w #1`) sits between them.
- **live buffer / inactive buffer** — `Raster_Buf_A` and `Raster_Buf_B`. `Raster_Active_Buf` names
  the one `Raster_HInt` walks; the builder writes the other one and swaps.

---

## File Structure

| file | responsibility after this parcel |
|---|---|
| `engine/effects/raster_dsl.emp` | comptime: emits the program body (unchanged), the 5-word patch table (changed), and the new per-record content check |
| `engine/effects/raster.emp` | runtime: `Raster_BuildSchedule` (new, replaces `Raster_PatchAll`), `Raster_InstallPatched` (absorbs the deleted copy proc's stores), `Raster_GetChannelBand` (stride only), `Raster_HInt` (UNTOUCHED — if a task edits it, that task is wrong) |
| `engine/level/parallax.emp` | runtime: the anchored overlay tests `L > band_hi` before clamping |
| `games/sonic4/data/effects/ojz_effects.emp` | data: the hand twins for the new table, and the re-banded channels |
| `docs/benchmarks/effects-p3-removal/` | new: gate evidence |

---

## Task 1: The 5-word patch table (comptime only)

**This task leaves the ROM non-functional on purpose.** The table changes shape here and the
runtime readers catch up in Task 2. Build it, do NOT boot it. Say so in the commit message.

**Files:**
- Modify: `engine/effects/raster_dsl.emp` — `patch_table` (:1039-1052), `patched_words` (:1162-1164), new `record_words` + `check_rec_layout`
- Modify: `games/sonic4/data/effects/ojz_effects.emp` — `OJZ_TC_TABLE_HAND` (:664-670) and the pins around it

- [ ] **Step 1: Write the failing pin — the hand twin for the new table**

The twin is the test. Replace `OJZ_TC_TABLE_HAND` (`ojz_effects.emp:664-670`) with the 5-word form.
Field order is `[line_src][band_lo_fl][band_hi_fl][rec_off][rec_len]` — `line_src` FIRST, because the
builder must decide whether a record is suppressed before it needs anything else, and
`Raster_GetChannelBand` then finds its key without a skip.

`rec_off` is the byte offset of the record's OWN arm word inside the emitted body, and `rec_len` is
its byte length. From the pinned body at `ojz_effects.emp:642-656`: the header is 1 word, the two
priming records are 2 words each, so record 2's arm sits at word 5 = byte 10. Record 2 is
`[arm][opc][0][$8C89][4][$C048][$0000][2][72]` = 9 words = 18 bytes, so record 3's arm is at byte 28,
and record 3 is `[arm][opc][2][$4002][$0010][0][$0043]` = 7 words = 14 bytes.

```emp
const OJZ_TC_TABLE_HAND = [
    2,                          // count — two authored records
    $8000, 2,   213,   10, 18,  // channel 0: band 2..213, record at byte 10, 18 bytes long
    $8001, 215, 222,   28, 14,  // channel 1: band 215..222, record at byte 28, 14 bytes long
]
```

- [ ] **Step 2: Run the build to verify the pin FAILS**

```bash
./build.sh 2>&1 | tail -20
```

Expected: FAIL, `OJZ_TwoChannel: patched_words says ... but 64 padded body words plus the hand table
and trailer is ...` — the length ensure at `ojz_effects.emp:705-706` fires first because the twin is
now 11 words where the encoder still emits 9.

- [ ] **Step 3: Add `record_words` beside `arm_word_index` in `raster_dsl.emp`**

Put it directly after `arm_word_index` (`:1024`), because the two are read together.

```emp
// record_words — the WORD length of record k's emitted form: its arm word, its op_count, and
// its op bodies. The builder copies exactly this many words, so this number and
// arm_word_index's are the two halves of "where is this record and how big is it".
comptime fn record_words(f: RasterFire) -> int {
    comptime var n = 2                      // arm word + op_count
    for o in fire_ops(f) { n = n + op_size(o) }
    return n
}
```

- [ ] **Step 4: Rewrite `patch_table`**

Replace the body of `patch_table` (`:1039-1052`). Note `arm_word_index(fires, k)` — the record's OWN
index, where the old code passed `k - 2` to name the arm it rewrote.

```emp
// patch_table — the self-describing patch descriptor appended at byte 128 of a patched template.
// One entry per authored record, FIVE WORDS each:
//
//     [line_src][band_lo_fl][band_hi_fl][rec_off][rec_len]
//
//   line_src    a literal fire line (high bit clear) for a static record, or $8000|channel for a
//               patchable one. FIRST because the builder decides emit-or-suppress from it before
//               it needs anything else, and Raster_GetChannelBand matches on it.
//   band_lo_fl  the band in fire lines. A static record writes its own fire line into both, so
//   band_hi_fl  every field of every entry is in ONE coordinate system.
//   rec_off     byte offset of THIS record's own arm word inside the emitted body.
//   rec_len     the record's byte length, arm word through last op word.
//
// THERE IS NO arm_off ANY MORE. It named the arm word this entry REWRITES — the arm of record
// k-2, pre-resolved into ROM because the in-place patcher kept no offset history. The builder
// emits records itself and therefore knows where it put every arm word, so the pre-resolution
// has nothing left to buy.
comptime fn patch_table(fires: array) -> array {
    comptime var out = [fires.len]
    comptime var k   = 2
    for f in fires {
        comptime var src = fire_screen_line(f) - 1
        if fire_is_patch(f) == 1 { src = $8000 | fire_channel(f) }
        out = out ++ [src,
                      fire_band_lo(f) - 1,
                      fire_band_hi(f) - 1,
                      2 * arm_word_index(fires, k),
                      2 * record_words(f)]
        k = k + 1
    }
    return out
}
```

- [ ] **Step 5: Fix the table's word count in `patched_words`**

At `raster_dsl.emp:1162-1164` the table contributes `1 + 4 * fires.len`; it is now `1 + 5 * fires.len`.
Read the function and change the multiplier only.

- [ ] **Step 6: Add `check_rec_layout` — the CONTENT check**

Put it beside `check_arm_layout` (`:1142`). This is the guard the lens sweep demanded: the identity
`rec_off(k) + rec_len(k) == rec_off(k+1)` is a TAUTOLOGY (both fields come from one walk over
`op_size`, so a uniform base error or a mispriced op telescopes consistently and it never fires).
This one indexes the EMITTED IMAGE and compares values, exactly as `check_arm_layout` does.

```emp
// check_rec_layout — GUARD 10. For every record the table describes, the emitted image at
// [rec_off, rec_off+rec_len) must BE that record: an $8Axx-class arm word, the op_count, and the
// op bodies, and the span must end exactly where the next record's arm word begins.
//
// WHY IT INDEXES `out` AND NOT JUST THE OFFSETS. Under the builder a wrong rec_off/rec_len does
// not misplace one byte — it copies a MISALIGNED SLICE of the template into the live program, and
// the handler then reads an op payload word as an opcode, falls through the compare chain to
// OP_SET_REG, writes an arbitrary word to VDP_CTRL from inside a raw interrupt handler, and walks
// arbitrary bytes for the rest of the frame. An offset-only cross-check cannot see any of that.
comptime fn check_rec_layout(fires: array, out: array) -> int {
    comptime var k = 2
    for f in fires {
        let off = arm_word_index(fires, k)
        let len = record_words(f)
        ensure((out[off] & $FF00) == $8A00,
               "raster program: record {k}'s rec_off points at word {off}, which holds {out[off]} — not an $8Axx arm word. The builder copies rec_len bytes from here into the live program, so a misaligned rec_off feeds the HInt handler an op payload word as an opcode.")
        ensure(out[off + 1] == fire_ops(f).len,
               "raster program: record {k} at word {off} declares {out[off + 1]} ops but the fire has {fire_ops(f).len}")
        comptime var body = []
        for o in fire_ops(f) { body = body ++ op_words(o) }
        comptime var i = 0
        for w in body {
            ensure(out[off + 2 + i] == w,
                   "raster program: record {k}'s emitted body diverges from the fire at word {off + 2 + i} — image has {out[off + 2 + i]}, the fire says {w}")
            i = i + 1
        }
        ensure(off + len == arm_word_index(fires, k + 1),
               "raster program: record {k} spans words {off}..{off + len} but the next record's arm word is at {arm_word_index(fires, k + 1)} — rec_len and the emitted layout disagree, so the builder would copy a misaligned slice")
        k = k + 1
    }
    return 0
}
```

- [ ] **Step 7: Call it from `patched_program`**

`patched_program` (`:1174`) already calls `check_arm_layout`. Add `check_rec_layout(fires, body)`
immediately after it, passing the same emitted body array that `check_arm_layout` is given.

- [ ] **Step 8: Run the build to verify the pins now PASS**

```bash
./build.sh 2>&1 | tail -20
```

Expected: `built: sonic4 plain native ROM`. The whole-image pin at `ojz_effects.emp:715-717` is what
proves the table twin and the encoder agree.

- [ ] **Step 9: Commit**

```bash
git add engine/effects/raster_dsl.emp games/sonic4/data/effects/ojz_effects.emp
git commit -m "effects(table): 5-word patch entries with rec_off/rec_len — ROM NOT BOOTABLE until the builder lands"
```

---

## Task 2: `Raster_BuildSchedule` replaces the patcher

**Files:**
- Modify: `engine/effects/raster.emp` — replace `Raster_PatchAll` (:959-993); update `Raster_GetChannelBand` (:1037-1069) and `Raster_InstallPatched`'s trailer stride (:852)
- Modify: `engine/effects/raster.emp` — `Raster_VBlank`'s call site (:526)

- [ ] **Step 1: Fix `Raster_GetChannelBand` for the new entry shape**

`line_src` is now the FIRST word of an entry, and the two trailing words are `rec_off`/`rec_len`.
Replace the loop body (`:1048-1054`):

```emp
    .entry:
        move.w  (a0)+, d1                   // line_src — first word of the entry now
        cmp.w   d0, d1
        beq     .found
        addq.l  #8, a0                      // skip band_lo, band_hi, rec_off, rec_len
        dbf     d2, .entry
```

and `.found` (`:1064-1068`) reads the two band words that immediately follow:

```emp
    .found:
        move.w  (a0)+, d1                   // band_lo_fl
        move.w  (a0), d2                    // band_hi_fl
        moveq   #1, d0
        rts
```

- [ ] **Step 2: Fix the trailer offset in `Raster_InstallPatched`**

At `raster.emp:851-853` the stride is `lsl.w #3` (8 bytes/entry). Entries are 10 bytes now, and 10 is
not a shift; `mulu` is forbidden by `CODING_CONVENTIONS.md`. Replace those lines with:

```emp
        move.w  (a1), d0                    // record count
        move.w  d0, d1
        lsl.w   #3, d0                      // 8n
        add.w   d1, d0                      // 9n
        add.w   d1, d0                      // 10n — the table's byte length
        addq.w  #2, d0                      // past the count word itself
```

- [ ] **Step 3: Write the builder**

Delete `Raster_PatchAll` entirely (`:919-993`, doc block included) and put this in its place. Keep
the surrounding comment discipline: the notes below are load-bearing, not decoration.

```emp
// -----------------------------------------------
// Raster_BuildSchedule — RE-RECORD the frame's schedule from the ROM template into the INACTIVE
// buffer, emitting only the records that are live this frame, then swap.
//
// It replaces Raster_PatchAll, which rewrote one arm BYTE per record in the live buffer. The
// patcher could move a boundary but could never REMOVE one: arm words are relative gaps and the
// handler's cursor advance is implicit, so a record is left behind only by having been walked.
// Emitting the schedule instead makes removal a matter of not copying it.
//
// THE ARM SLOT IS TWO RECORDS BACK; THE LINE DELTA IS ONE RECORD BACK. Ruling 1b: the word written
// at record i is consumed at the next fire and schedules the gap that LANDS record i+2. So the
// value is `this fire line - the previous fire line - 1` while the slot it goes into belongs to
// the record two back. Pairing the two-back slot with the two-back LINE is the mistake this design
// was drafted with and the lens sweep caught; the hand pin is the witness
// (games/sonic4/data/effects/ojz_effects.emp: arm0 = $8A00 | (99 - 1 - 1) = $8A61).
//
// PARK IS BY CONSTRUCTION. A record's arm is written only when a record two later is emitted, so
// the two youngest slots are never written by the loop — this proc parks them explicitly at the
// end. That is what keeps the TEMPLATE's own arm words entirely non-load-bearing: they are copied
// and then either overwritten or parked, so no patched template needs a special all-park emitter
// and check_arm_layout keeps proving what it proves for static programs. It also makes the empty
// schedule correct for the right reason: with every record suppressed the two youngest slots ARE
// the priming records, both parked.
//
// IT WRITES THE INACTIVE BUFFER AND SWAPS. Building in place would move records under a
// Raster_Cursor left from the previous frame. Today the buffer's LAYOUT is a frame invariant (only
// arm bytes change), so a stale cursor always points at a record boundary; under compaction it
// would not. Raster_Buf_A is free for the whole lifetime of a patched program, and P1 reserved the
// pair for exactly this.
//
// VBLANK ONLY, and that is inherited rather than new: the arm words are RELATIVE, so a half-built
// schedule walked by Raster_HInt desynchronises the whole tail of the chain. The install path used
// to tail-call the patcher from the main loop; it no longer does (see Raster_InstallPatched).
//
// STACK SCRATCH, DELIBERATELY. The two arm-slot back-pointers live in an 8-byte stack frame rather
// than in registers or RAM: this proc runs under Raster_VBlank, whose callers VInt_Level and
// VInt_Lag declare clobbers reaching only d4 and a2, and Raster_BuildShipEntry's note records that
// saving a register does not buy back its declaration. Two longwords on the stack cost two memory
// accesses per record in VBlank and no contract change anywhere.
// -----------------------------------------------
proc Raster_BuildSchedule () clobbers(d0-d4/a0-a2) {
        move.l  Raster_Patch_Tab, d0
        beq     .none                       // liveness: the TABLE, never Active_Buf
        subq.l  #8, sp                      // (sp) = arm slot two back, 4(sp) = one back
        movea.l d0, a0                      // -> the patch table
        // --- destination = whichever buffer is NOT live ---
        move.l  Raster_Active_Buf, d3
        lea     Raster_Buf_A, a1
        cmpa.l  d3, a1
        bne     .dst_ready
        lea     Raster_Buf_B, a1
    .dst_ready:
        // --- header word and the two priming records, verbatim ---
        movea.l d0, a2
        lea     -RASTER_BUF_SIZE(a2), a2    // the template body sits before its table
        move.w  (a2)+, (a1)+                // pal_dirty_mask
        move.l  a1, (sp)                    // priming record 0's arm word
        move.l  (a2)+, (a1)+                // [arm][op_count]
        move.l  a1, 4(sp)                   // priming record 1's arm word
        move.l  (a2)+, (a1)+
        moveq   #1, d0                      // prev fire line = 1 (priming record 1)
        move.w  (a0)+, d4                   // record count (a WORD)
        subq.w  #1, d4
    .entry:
        move.w  (a0)+, d2                   // line_src
        bpl     .have_line                  // high bit clear -> a literal fire line
        andi.w  #RASTER_MAX_PATCH-1, d2     // channel index
        add.w   d2, d2                      // -> word offset
        lea     Effects_Screen_L, a2
        move.w  (a2, d2.w), d2              // the LATCHED screen line; may be negative
        subq.w  #1, d2                      // -> fire line. ONE conversion, here.
        cmp.w   2(a0), d2                   // band_hi_fl
        bgt     .suppress                   // past the band it can reach: REMOVE the record
        cmp.w   (a0), d2                    // band_lo_fl
        bge     .have_line
        move.w  (a0), d2                    // clamp UP — the frame-top ship covers what is above
    .have_line:
        addq.l  #4, a0                      // past the two band words
        // --- this record's gap goes into the slot TWO records back ---
        move.w  d2, d3
        sub.w   d0, d3
        subq.w  #1, d3                      // gap = L[k] - L[k-1] - 1
        movea.l (sp), a2
        move.b  d3, 1(a2)                   // the low byte IS the counter (every arm word is $8Axx)
        // --- shift the slot history, then remember where THIS record's arm lands ---
        move.l  4(sp), (sp)
        move.l  a1, 4(sp)
        move.w  d2, d0                      // prev = this record's fire line
        // --- copy the record body out of the template ---
        move.w  (a0)+, d3                   // rec_off
        movea.l Raster_Patch_Tab, a2
        lea     -RASTER_BUF_SIZE(a2), a2
        adda.w  d3, a2                      // adda.w, NOT add.w: add.w dN,aM mis-encodes
        move.w  (a0)+, d3                   // rec_len, in BYTES
        lsr.w   #1, d3                      // -> words
        subq.w  #1, d3
    .copy:
        move.w  (a2)+, (a1)+
        dbf     d3, .copy
    .next:
        dbf     d4, .entry
        // --- terminator, emitted rather than copied: nothing in the template holds it ---
        move.w  #RASTER_ARM_PARK, (a1)+
        move.w  #RASTER_OPS_END, (a1)+
        // --- the two youngest arm slots have no record two later, so they park ---
        movea.l (sp), a2
        move.w  #RASTER_ARM_PARK, (a2)
        movea.l 4(sp), a2
        move.w  #RASTER_ARM_PARK, (a2)
        addq.l  #8, sp
        // --- swap: the buffer just built becomes the one Raster_HInt walks ---
        move.l  Raster_Active_Buf, d3
        lea     Raster_Buf_A, a1
        cmpa.l  d3, a1
        bne     .swap
        lea     Raster_Buf_B, a1
    .swap:
        move.l  a1, Raster_Active_Buf
    .none:
        rts
    .suppress:
        addq.l  #8, a0                      // band words, rec_off, rec_len
        jbra    .next
}
```

- [ ] **Step 4: Point `Raster_VBlank` at it**

`raster.emp:526` reads `jbsr Raster_PatchAll`. Change to `jbsr Raster_BuildSchedule`. Its
surrounding comment (`:519-525`) explains why the derive must happen here and before the cursor
rewind; that reasoning is unchanged, but the sentence naming "one byte per record" is now wrong —
rewrite it to say the schedule is re-recorded and the buffer swapped.

- [ ] **Step 5: Point `Raster_InstallPatched`'s tail call at it, for now**

`raster.emp:874` is `jbra Raster_PatchAll`. Make it `jbra Raster_BuildSchedule` so this task builds
and boots; Task 3 deletes the tail call entirely. Doing it in two steps keeps this task's gate
honest — it must produce a ROM whose behaviour is IDENTICAL to master.

- [ ] **Step 6: Build and boot**

```bash
./build.sh && DEBUG=1 ./build.sh
```

Expected: both succeed. Then launch oracle (kill any stale instance first — `pgrep -a oracle_gui`,
one instance only) with `s4.debug.bin` and confirm the OJZ section renders with the water boundary
where master put it.

- [ ] **Step 7: GATE — the emitted buffer must be byte-identical to master's patched buffer**

This is the strongest cheap gate in the parcel: with nothing suppressed the builder must reproduce
exactly what the patcher produced.

**Do NOT expect `OJZ_TC_HAND`'s arm words.** That twin is the TEMPLATE, authored at screen line 100
for channel 0; the live buffer carries the RUNTIME lines, which come from the world anchors. At
spawn (`Camera_Y = 144`, anchors 224 and 314, `ojz_effects.emp:561-571`) channel 0 latches
`L = 80` -> fire line 79, and channel 1 latches `L = 170` -> fire line 169, which is BELOW its band
floor and therefore clamps UP to fire line 215. Only the OP BODIES are the same as the twin.

Pin the inputs instead of reading whatever the camera happens to be doing:

1. `emulator_lookup_symbol` for `Raster_Buf_A`, `Raster_Buf_B`, `Raster_Active_Buf`,
   `Effects_World_Y`, `Camera_Y`, `Debug_Scene_Freeze`.
2. Freeze the camera (`Debug_Scene_Freeze` skips `Camera_Update`, so a written `Camera_Y` stays
   put — `ojz_scroll_test.emp`), set `Camera_Y = 144`, and write `Effects_World_Y[0] = 244` and
   `[1] = 380` so both records sit mid-band: `L0 = 100` -> fire 99, `L1 = 236`... which is past
   channel 1's band and would SUPPRESS under Task 4. For this task pick `[1] = 360` -> `L1 = 216`
   -> fire 215, inside the band. **Derive both fire lines from the values you actually wrote and
   show the arithmetic in the evidence file** — a gate whose expectation was copied rather than
   derived is how the last two parcels shipped an off-by-one.
3. Read `Raster_Active_Buf`, then `emulator_read_memory` 46 bytes at that address.
4. Expected, for fire lines 99 and 215: `arm0 = $8A00 | (99 - 1 - 1) = $8A61`,
   `arm1 = $8A00 | (215 - 99 - 1) = $8A73`, records 2 and 3 both `$8AFF` (parked — nothing follows
   them), terminator `$8AFF $FFFF`, and every op word identical to `OJZ_TC_HAND`'s bodies.
5. **Cross-ROM control:** build master's ROM into a scratch path, run it with the SAME frozen camera
   and the SAME written anchors, and read the same 46 bytes. The two buffers must be byte-identical.
   This is sound in a way pixel comparison is not — the buffer is a pure function of (template,
   anchors, camera), all three of which are pinned here.

If the arm words differ, the arithmetic is wrong — re-read the "TWO records back / ONE record back"
note before changing anything else. `$8A62`/`$8A74` specifically means the two-back LINE was used.

- [ ] **Step 8: Commit**

```bash
git add engine/effects/raster.emp
git commit -m "effects(raster): re-record the schedule each VBlank instead of patching arm bytes"
```

---

## Task 3: Install path — rehome the stores, delete the copy, drop the tail call

**Files:**
- Modify: `engine/effects/raster.emp` — `Raster_InstallPatched` (:816-875), delete `Raster_CopyPatchedTemplate` (:795-814)
- Modify: `engine/effects/preset.emp` — the exclusivity ensure's message (:126-130)

- [ ] **Step 1: Move the three install stores into `Raster_InstallPatched`**

`Raster_CopyPatchedTemplate` is not just a copy loop. Three of its stores are the install half of the
patched path and NOTHING else does them:

```emp
        move.l  a1, Raster_Active_Buf       // :806
        move.l  a1, Raster_Program          // :807 — nonzero is what makes Raster_VBlank act
        clr.l   Raster_Pending              // :808 — kills a staged static program
```

The third is load-bearing in another file: `preset.emp:129-130`'s guard is written around
"whichever installs last wins DESTRUCTIVELY", and that clear is the mechanism. Drop it and a
`Raster_Pending` staged earlier is consumed by `Raster_VBlank:496 .copy_program`, which repoints
`Active_Buf` at Buf_A and clears `Raster_Patch_Tab` — tearing down the patched program on its first
VBlank, silently, with the preset's ensure still passing.

In `Raster_InstallPatched`, replace `jbsr Raster_CopyPatchedTemplate` (`:866`) with:

```emp
        // The install half of what Raster_CopyPatchedTemplate used to do. The COPY is gone — the
        // builder re-records the whole schedule from the ROM template at the next VBlank — but
        // these three stores are not the copy and nothing else performs them. Buf_B is named here
        // only as a starting side; the builder swaps buffers from this frame on.
        lea     Raster_Buf_B, a1
        move.l  a1, Raster_Active_Buf
        move.l  a1, Raster_Program          // nonzero -> Raster_VBlank processes it
        clr.l   Raster_Pending              // a staged static program loses (preset.emp's guard)
```

- [ ] **Step 2: Delete `Raster_CopyPatchedTemplate`**

Remove `:795-814` in full, including its doc block. Grep for stragglers:

```bash
grep -rn "Raster_CopyPatchedTemplate" engine games docs tools
```

Expected hits to fix, not leave: `engine/effects/preset.emp:126,130` (the ensure MESSAGE names it as
the thing that clears `Raster_Pending` — rewrite to name `Raster_InstallPatched`), and
`engine/effects/raster_dsl.emp:996-997` (the 128-byte ensure message names it — rewrite to name the
builder's fixed-size copy).

- [ ] **Step 3: Drop the main-loop tail call**

`Raster_InstallPatched` ends `jbra Raster_BuildSchedule` (Task 2 Step 5). Under the builder that is a
full mid-frame rebuild of a buffer `Raster_HInt` may be walking — and it is unnecessary, because an
install takes effect at the next `Raster_VBlank` by contract. Replace the tail call with `rts` and
add:

```emp
        // NO TAIL CALL INTO THE BUILDER. Raster_PatchAll used to be invoked from here, i.e. from
        // the MAIN LOOP, which was survivable while it wrote one byte per record and is not now:
        // the builder re-records the entire buffer, and Raster_HInt walks that buffer during
        // active display. The install lands at the next Raster_VBlank, which is the contract this
        // proc always had ("it takes effect at the next Raster_VBlank, so an install can never
        // tear a frame mid-walk"). This also removes a PRE-EXISTING hazard: the deleted copy blatted
        // 128 bytes over the live buffer from the main loop.
        rts
```

- [ ] **Step 4: Move the comment that justified the tail call**

`preset.emp:245` explains `Effects_LatchWorldLines`' placement by "Raster_InstallPatched below
tail-calls Raster_PatchAll, which reads Effects_Screen_L". That reason is gone. The placement is
still correct for the reason `Effects_LatchWorldLines`' own doc gives (one derivation, one camera,
read by the builder in VBlank and the overlay in the main loop) — rewrite the comment to say that.

- [ ] **Step 5: Build, boot, re-run Task 2's byte gate**

```bash
./build.sh && DEBUG=1 ./build.sh
```

Then repeat Task 2 Step 7 exactly. The buffer contents must still equal `OJZ_TC_HAND`. Additionally
check the FIRST frame after a section crossing: run to the OJZ section 0 -> 1 boundary and confirm
`Raster_Active_Buf`, `Raster_Program` and `Raster_Patch_Tab` are all non-zero and mutually
consistent (the table pointer is `Active_Buf`-independent; it points into ROM).

- [ ] **Step 6: Commit**

```bash
git add engine/effects/raster.emp engine/effects/preset.emp engine/effects/raster_dsl.emp
git commit -m "effects(raster): rehome the install stores, delete the template copy, drop the main-loop rebuild"
```

---

## Task 4: Suppression, on both boundaries, in ONE commit

The acceptance criterion is that the palette boundary and the parallax boundary change together.
`docs/DEFERRED_WORK.md:4601-4604` says so explicitly: fixing one side alone trades a consistent
error for a disagreement. **Do not split this task.**

**Files:**
- Modify: `engine/level/parallax.emp` (:766-812)
- Verify: `engine/effects/raster.emp` — the builder's `.suppress` path already exists from Task 2

- [ ] **Step 1: Confirm the raster half is already live**

The builder's `bgt .suppress` on `band_hi_fl` (Task 2 Step 3) IS the raster half. Read it back and
confirm the comparison is against `2(a0)` (`band_hi_fl`) and that `.suppress` skips 8 bytes. No code
change here; this step exists so the two halves are verified as a pair.

- [ ] **Step 2: Move the parallax threshold ABOVE the band clamp**

In `Parallax_Update`'s anchored-overlay block, the `cmpi.w #224, d0 / bge .bands_ready` test
(`parallax.emp:801-812`) currently sits AFTER the band clamp and is therefore unreachable — the
clamp caps `d0` at `hi`. Move the test up so it mirrors the `ble .anchor_top` early test that
already handles the other direction, and make it compare against the record's own band rather than
a screen constant.

After `move.w (a4,d0.w), d0` (`:750`) and the existing `tst.w d0 / ble .anchor_top` (`:763-764`),
the band lookup at `:771-787` gains an early exit. Replace the clamp block's `.anchor_lo_ok`
sequence so the HI test suppresses instead of clamping:

```emp
        addq.w  #1, d1                              // fire line -> screen line, both bounds
        addq.w  #1, d2
        cmp.w   d2, d0
        bgt     .anchor_off_below                   // past the band it can reach: NO SPLIT
        cmp.w   d1, d0
        bge     .anchor_unclamped
        move.w  d1, d0                              // clamp UP: the ship covers what is above
    .anchor_unclamped:
        movea.l (sp)+, a0                           // config back, on EVERY path below
```

and add the exit beside `.bands_ready`, restoring the saved `a0` first:

```emp
    .anchor_off_below:
        // THE DRY DIRECTION. The channel's anchor has passed below the band its raster record can
        // reach, so Raster_BuildSchedule does not emit that record at all and the palette boundary
        // is gone this frame. Splitting the scroll bands here would leave the two boundaries
        // disagreeing across the rows the palette no longer covers — the exact defect Parcel W
        // exists to remove, and the reason DEFERRED_WORK says never to change one side alone.
        // The threshold is the RECORD'S OWN band, read from the same table Raster_BuildSchedule
        // clamps against, so the two cannot drift apart by editing one number.
        movea.l (sp)+, a0
        jbra    .bands_ready
```

**KEEP the `cmpi.w #224, d0 / bge .bands_ready` pair at `:801-802`.** It stops being the water
channel's path but it does NOT become dead: the no-band-declared route (`beq .anchor_unclamped` at
`:778`, taken when `Raster_GetChannelBand` reports no live table or no record for the channel) still
falls through to it with `L` unclamped, and there below-screen is the only threshold available.
What DOES go is its 11-line comment about the knowingly-unfixed DRY direction — that comment is the
thing this task closes. Replace it with one line naming its real remaining job.

- [ ] **Step 3: Confirm both routes end somewhere correct**

Read the block from `.anchor_unclamped` (`:788`) to `.bands_ready` and confirm two things by
tracing, not by assumption: (a) the band-found route now exits at `.anchor_off_below` before it can
reach the clamp, and (b) the no-band route still reaches the `224` test with `a0` restored. `a0`
holds the caller's config pointer and is popped on EVERY path — a missed pop is a corrupted
parallax config, not a wrong boundary.

- [ ] **Step 4: Build and boot**

```bash
./build.sh && DEBUG=1 ./build.sh
```

- [ ] **Step 5: GATE — the three-state matrix, in one oracle session, with poison controls**

Oracle, foreground, one instance. `Debug_Scene_Freeze` (in `ojz_scroll_test.emp`) is the pinned-camera
instrument: it skips `Camera_Update`, so a written `Camera_X/Y` stays put. For each state below,
write `Effects_World_Y[0]` (via `emulator_write_memory` — VALUE IS DECIMAL) to place channel 0's
latched `L`, advance one frame, and read back:

| state | `L` | expected in the live buffer | expected in `Parallax_Shadow_Bands` |
|---|---|---|---|
| above | `<= 0` | record 2 present, arm chain lands it at fire line 2 (`band_lo`) | split at line 0 |
| mid | 100 | record 2 present at fire line 99 | split at 100 |
| **below** | 230 | **record 2 ABSENT**; the chain's first authored fire is channel 1's | **no anchored split** |

For each state assert BOTH of:
1. **Chain walk** — sum the arm gaps from the priming records and compare the derived fire-line set
   against the expectation. The set is the gate, not any single word.
2. **Payload** — for every record still present, its emitted bytes equal that record's op words
   (`OJZ_TC_HAND`'s record bodies). This is the axis the design's first draft was blind to: a
   byte-copying builder can land a record on exactly the right line carrying the wrong bytes.

Then the **poison control, in the same run**: set `L` back to 100 and re-read. Every assertion above
must flip back. A gate that only ever observes the suppressed state is measuring nothing.

Use a **watchpoint on the CRAM destination** ($C048's write) rather than a breakpoint on
`Raster_HInt`'s `.op_region` label: that label is shared dispatch, and it is unique to channel 0 on
this fixture only by coincidence. (Oracle watchpoints re-trigger on resume and survive
`breakpoint_clear` — expect that.)

- [ ] **Step 6: GATE — the two boundaries against EACH OTHER, not against a constant**

In ONE frame per state, read the fire line recovered from the buffer AND the split line
`Parallax_Shadow_Bands` actually wrote, and assert they are equal to each other. Deriving both
"expected" values from the same formula would let a wrong shared threshold produce two wrong answers
that agree with the tester.

- [ ] **Step 7: Commit**

```bash
git add engine/level/parallax.emp
git commit -m "effects: suppress a patch record past its band, on both boundaries together"
```

---

## Task 5: Lifecycle holes this parcel is standing in front of

**Files:**
- Modify: `engine/effects/raster.emp` — `Raster_VBlank` (:491-552)
- Modify: `engine/effects/raster_dsl.emp` — `raster_program` (:970-1001)

- [ ] **Step 1: Clear `Effects_Offscreen_Entry` on both teardown paths**

Neither `Raster_VBlank`'s explicit-clear path (`:497-504`) nor `.copy_program` (`:505-517`) clears it,
so a torn-down patched program's ROM trailer would keep shipping as a frame-top palette DMA
(`buffers.emp:279-315`) on every frame its stale anchor reads `L <= 0`. Add `clr.l
Effects_Offscreen_Entry` beside the existing `clr.l Raster_Patch_Tab` on BOTH paths, with:

```emp
        // The ship entry dies with the program that declared it, exactly as the patch table does.
        // Enqueue_Dirty_Buffers tests only this pointer, so a stale one keeps queueing a dead
        // program's trailer as a frame-top DMA whenever the (also stale) anchor reads L <= 0.
        clr.l   Effects_Offscreen_Entry
```

- [ ] **Step 2: Add the one-record-per-channel guard**

`compose`'s guard 9 refuses two patchable fires merged onto the same LINE, but two patchable records
on the same CHANNEL at different lines are legal — and `Raster_GetChannelBand` returns the FIRST
match and stops, so past that record's band the parallax overlay would clamp to it while a second
record on the same channel sits elsewhere. Add to `raster_program`, after `check_intervals(fires)`:

```emp
    // GUARD 11 — one patchable record per channel. Raster_GetChannelBand answers with the FIRST
    // record matching a channel, so a second record on the same channel is invisible to the
    // parallax overlay: past the first record's band the scroll boundary would pin to a band the
    // palette boundary is no longer using. The runtime cannot disambiguate two answers to "where
    // is channel N", so this is refused at build time rather than resolved at runtime.
    comptime var ch_seen = [0, 0, 0, 0]
    for f in fires {
        if fire_is_patch(f) == 1 {
            let c = fire_channel(f)
            ensure(ch_seen[c] == 0,
                   "raster program: two patchable records both drive channel {c}. Raster_GetChannelBand returns the first match, so the parallax overlay would follow one record while the palette follows the other. Give them separate channels.")
            ch_seen[c] = 1
        }
    }
```

`[0, 0, 0, 0]` is written out rather than built from `RASTER_MAX_PATCH` because a comptime array
literal is what the evaluator takes here; pin it:

```emp
    ensure(ch_seen.len == RASTER_MAX_PATCH,
           "raster program: the channel-seen array is {ch_seen.len} wide but RASTER_MAX_PATCH is {RASTER_MAX_PATCH}")
```

- [ ] **Step 3: Build — the guard must not fire on shipped content**

```bash
./build.sh && DEBUG=1 ./build.sh
```

Expected: both succeed. OJZ's two channels are 0 and 1, so nothing shipped trips it.

- [ ] **Step 4: Prove the guard is not vacuous**

Temporarily edit `OJZ_TC_PROG` (`ojz_effects.emp:629-634`) so both `patchable` calls say `ch: 0`,
build, and confirm the build FAILS with guard 11's message. Then revert the edit and rebuild green.
Paste both outcomes into the evidence file. A guard nobody has seen fire is a guard nobody knows is
wired.

- [ ] **Step 5: Commit**

```bash
git add engine/effects/raster.emp engine/effects/raster_dsl.emp
git commit -m "effects: clear the ship entry with its program, and refuse two records on one channel"
```

---

## Task 6: Re-band the OJZ channels (owner ruling)

**Files:**
- Modify: `games/sonic4/data/effects/ojz_effects.emp` (:586-670)

- [ ] **Step 1: Move channel 1 to the bottom two lines and give channel 0 the room**

Channel 1 is a gate FIXTURE whose position the file itself calls negotiable (`:599-603`). Moving it
to `222..223` lets channel 0 reach `220`, which takes the worst-case dry-side residual from ~9 rows
to ~3. Edit `OJZ_TC_PROG`:

```emp
const OJZ_TC_PROG = compose([
    patchable(fx_tint_band(line: 100, slot: 0, pal_line: 2, entry: 4, count: 3, sh: 1),
              ch: 0, lo: 3,   hi: 220, offscreen_ship: 1),
    patchable(fx_vscroll_split(line: 222, offset: $0043),
              ch: 1, lo: 222, hi: 223),
])
```

- [ ] **Step 2: Update the prose that explains the bands**

The note at `:589-612` states the budget arithmetic and the 72-rows-to-10 history. Rewrite the
budget line: `(220-3+1) + (223-222+1) + 1 = 218 + 2 + 1 = 221`, still exactly the disjoint-band
allowance. Add why the change happened now: suppression makes the below-band state honest, so the
remaining error is the band's REACH, and the fixture was spending 8 lines of it.

- [ ] **Step 3: Update the hand twins**

Channel 1's fire line moves from 219 to 221, so `OJZ_TC_HAND`'s arm words change:
`arm1 = $8A00 | (221 - 99 - 1) = $8A79`. The table twin's channel-0 band becomes `2..219` and
channel 1's `221..222`. Recompute both from the formulas in the comments rather than from the old
numbers — the whole point of the twins is that they are derived independently.

- [ ] **Step 4: Build**

```bash
./build.sh && DEBUG=1 ./build.sh
```

Expected: green. If `check_density` fires, the two bands are now closer than channel 0's modelled
526 cycles allows — report it and STOP rather than widening the guard; that is the guard doing its
job and it changes the owner's ruling.

- [ ] **Step 5: GATE — re-run Task 4 Step 5's matrix with the new numbers**

The expected fire lines move; the assertions do not. Also capture the state at `L` in `221..223`,
which is newly reachable and is where the remaining residual lives.

- [ ] **Step 6: Commit**

```bash
git add games/sonic4/data/effects/ojz_effects.emp
git commit -m "effects(ojz): re-band the fixture to the bottom two lines, freeing the water to reach 220"
```

---

## Task 7: Evidence, the budget row, and the re-baseline

**Files:**
- Create: `docs/benchmarks/effects-p3-removal/GATE-EVIDENCE.md`
- Modify: `tools/effects_budget_model.toml`

- [ ] **Step 1: Write the evidence file**

Collect, verbatim, with the ROM CRC and the oracle session's frame numbers beside each: Task 2 Step
7's byte-identity read; Task 4 Steps 5-6's three-state matrix including both poison controls and the
boundary cross-comparison; Task 5 Step 4's guard-fires-then-passes pair; Task 6 Step 5's re-run.
State plainly which assertions are structural reads and which are prose observations — this tree has
been burned by evidence that read as a measurement and was a screenshot.

- [ ] **Step 2: Measure the builder's VBlank cost, scoped correctly**

`Raster_VBlank` runs inside the sound-ON DMA-flag / sound-OFF `z80_stopped` bracket, before
`Flush_VDP_Shadow` and every DMA drain, on BOTH `VInt_Level` and `VInt_Lag`. So the number that
matters is not the proc's own duration but the bracket's. Use `emulator_set_profiler` /
`emulator_get_profiler_frames` on master and on this branch, same camera, same section, and record
BOTH the proc and the enclosing bracket, plus a lag frame if one can be provoked.

- [ ] **Step 3: Add a budget-model row**

Add the measured VBlank cost to `tools/effects_budget_model.toml` in the code-derived section, so
`tools/effects_budget_check.py` re-checks it on every build. That checker IS wired into
`build.sh:191` (EFX-9, closed 2026-08-15) — verify by running `./build.sh` and seeing the checker's
OK line, rather than assuming. A number in a prose benchmark file drifts; a gated row does not,
which is exactly the EFX-5 lesson.

- [ ] **Step 4: Book the fixture re-baseline**

Under suppression, OJZ channel 1 vanishes whenever its latched line passes its band instead of
pinning — correct new semantics, but it means the P-a / P-b / W evidence captures are no longer
reproducible and the "two independently patched channels coexist" proof shows one channel over part
of the camera range. Add a note to the evidence file and a line to `docs/BUGS.md` if any prior
entry's evidence is now unreproducible.

- [ ] **Step 5: Commit**

```bash
git add docs/benchmarks/effects-p3-removal/GATE-EVIDENCE.md tools/effects_budget_model.toml
git commit -m "docs(effects): gate evidence and the builder's VBlank budget row"
```

---

## Task 8: Documentation sync

**Files:**
- Modify: `docs/DEFERRED_WORK.md` (:4575-4604), `docs/ENGINE_ARCHITECTURE.md`, `docs/EFFECTS_AUTHORING.md`, `docs/BUGS.md`

- [ ] **Step 1: Close the DEFERRED_WORK entry**

"The DRY direction of a patch channel" is what this parcel closes. Rewrite it as CLOSED with the
date, the mechanism (records are emitted, not patched, so removal is local), and the RESIDUAL that
survives: for `band_hi < L < 224` the boundary renders nowhere rather than near the screen bottom,
about 3 rows after the re-band. Do not delete the entry — this tree reads closed entries.

- [ ] **Step 2: Fix every stale description of the patcher**

```bash
grep -rn "Raster_PatchAll\|arm_off\|one arm BYTE\|patches one byte" engine games docs
```

Every hit is either the builder now or wrong. Particular attention: `raster.emp`'s `PATCHED
TEMPLATES` header (`:762-778`), `RASTER_MIN_FIRE_LINE`'s "runtime twin" note (`:786-791`),
`docs/EFFECTS_AUTHORING.md` (11 hits), `docs/ENGINE_ARCHITECTURE.md` (15 hits).

- [ ] **Step 3: Update `docs/BUGS.md` EFX-4**

Its over-read half is stated against `Raster_CopyPatchedTemplate`'s fixed 128-byte copy, which no
longer exists. The builder copies exactly `rec_len` per record plus a fixed 5-word prologue, so the
over-read is gone; say so and close that half, or say precisely what remains.

- [ ] **Step 4: Update `docs/ENGINE_ARCHITECTURE.md`'s raster section**

The architecture doc is the source of truth and must describe the schedule as re-recorded per frame
into the inactive buffer, with the three-state anchor machine (`L <= 0` ship, mid-band fire,
`L > band_hi` removal) written out.

- [ ] **Step 5: Commit**

```bash
git add docs/
git commit -m "docs: the schedule is re-recorded per frame; close the DRY direction entry"
```

---

## Task 9: Ship it

- [ ] **Step 1: Full suite, both repos**

```bash
cd /home/volence/sonic_hacks/sigil && cargo test --workspace --no-fail-fast 2>&1 | tail -40
```

Report AGGREGATE totals and every failing target line — never a tail of the log. Full green is
3667/0 on sigil's side plus aeon's contract closure at 0 firings.

- [ ] **Step 2: Register any new cross-seam symbol**

`Raster_BuildSchedule` replaces a symbol the port tests may carry. A cross-seam reference is
invisible to `build.sh` and breaks sigil port targets silently:

```bash
grep -rn "Raster_PatchAll" /home/volence/sonic_hacks/sigil/crates
```

Every hit becomes `Raster_BuildSchedule` in `crates/sigil-harness/repin.toml` AND in each `*_port`
test's carrier table.

- [ ] **Step 3: The byte-moving ritual**

Repin, then `refreeze NAME --ab REF` with prose emulator evidence. `--check` is NOT the goldens.
Both repos merge as a PAIR.

- [ ] **Step 4: Build all four shapes and boot each**

```bash
./build.sh && DEBUG=1 ./build.sh && ./build.sh demo && DEBUG=1 ./build.sh demo
```

Boot EVERY shape — the release-shape blackout of 2026-08-14 happened because a gate looked at a
debug build only.

- [ ] **Step 5: Merge to master and push**

```bash
git branch --show-current          # verify BEFORE committing anything
git checkout master && git merge --no-ff <branch> && git push
```

---

## Self-review against the design

- §4.1 table format -> Task 1. §4.2 builder -> Task 2. §4.3 suppression + parallax -> Task 4.
  §4.4 double buffer -> Task 2 Step 3. §4.5 lifecycle -> Tasks 3 and 5. §4.6 cost -> Task 7 Step 2.
- §5.6's same-channel gap -> Task 5 Step 2 (the owner's fourth question answered by building it).
- §7's gates: chain walk (Task 4 Step 5), payload (same), watchpoint not breakpoint (same),
  boundary cross-comparison (Task 4 Step 6), poison control (Task 4 Step 5), comptime content check
  (Task 1 Step 6), budget row (Task 7 Step 3), re-baseline (Task 7 Step 4).
- §8's follow-on parcel is deliberately absent from every task.
- Owner ruling on the fixture re-band -> Task 6.

**Naming consistency:** `Raster_BuildSchedule` (not `Raster_Build`, not `Raster_PatchAll`) in every
task; `record_words` and `check_rec_layout` as defined in Task 1; `rec_off`/`rec_len` field order
`[line_src][band_lo_fl][band_hi_fl][rec_off][rec_len]` everywhere.
