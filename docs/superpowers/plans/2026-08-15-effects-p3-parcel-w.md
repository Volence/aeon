# Parcel W Implementation Plan — one world anchor, two readers

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`)
> syntax. **Subagents must NEVER touch oracle MCP** — it deadlocks. Every emulator step in this plan
> is done by the controlling session, foreground, one instance (`pgrep -a oracle_gui`).

**Goal:** make a palette boundary and a shimmer boundary land on the same scanline, both driven by
one act-space world anchor, without touching the deform wave's phase anchoring.

**Architecture:** the parallax pipeline gains a second reader of `Effects_World_Y[ch]`. Each frame,
Step 4a's rotated shadow band view is post-processed: the band containing the anchored screen line is
SPLIT at that line, and every band from the split down has its deform shifts overwritten with the
config's anchored shifts. Bands keep their own scroll factors, so structure below the surface
survives. Zero added bytes — three spare `parallax_config` pad bytes carry the channel and the two
shifts.

**Spec:** `docs/superpowers/specs/2026-08-15-effects-p3-parcel-w-design.md` (revision 2, adjudicated).
Read §3 and §3.1 before Task 3, and §5 before Task 5.

**Tech stack:** sigil `.emp` (68000), oracle MCP for behavioural gates, sigil golden/pin harness for
byte gates.

**Prerequisite, already shipped:** W0 (`Effects_World_Y[]` total-bound), aeon `7f60f728` / sigil
`b14564d3`, chain 121. Do not re-litigate it.

---

## Environment (every task)

```bash
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
cd /home/volence/sonic_hacks/aeon
git checkout -b parcel/w-world-anchor-overlay   # once, at Task 1
```

## File structure

| file | responsibility | tasks |
|---|---|---|
| `engine/level/parallax.emp` | the flat-fill tail, the shadow-view unit change, the overlay | 1, 2, 4 |
| `engine/effects/raster.emp` | `Raster_GetChannelBand` — the clamp band, read from the patch table | 3 |
| `engine/structs.emp` | `pcfg_anchor_ch` / anchored shifts claim the three pad bytes | 4 |
| `games/sonic4/data/parallax/configs.emp` | `hdr()` gains the anchor params; the fixture config | 4 |
| `games/sonic4/data/effects/ojz_effects.emp` | the fixture preset that binds `ep_parallax` | 4 |
| `engine/system/buffers.emp` | the twin HScroll-DMA-length key learns about anchoring | 4 |
| `docs/benchmarks/effects-p3-w/GATE-EVIDENCE.md` | the gate record | 5 |

**A note on why the tests look like this.** `crates/sigil-cli/tests/parallax_port.rs` is a *byte*
gate — it asserts the region's bytes equal a reference window. There is no harness that *executes*
68000 code, so behavioural proof is oracle measurement, done foreground by the controlling session.
Comptime `ensure`s cover authoring errors. Plan accordingly: byte-neutral tasks are proved by hash
and golden comparison, behavioural tasks by oracle reads.

---

### Task 1: `.lp_flat` gets a remainder tail

**Why first:** the flat fill is 8× unrolled on a documented invariant that every band span is a
multiple of 8. The overlay breaks that invariant, and the failure is not cosmetic — a span of 1..7
makes `lsr.w #3` yield 0, `subq.w #1` yield `$FFFF`, and `dbf` write 65,536 × 8 longwords past
`Hscroll_Buffer`. This must land before anything can produce an arbitrary span.

**Honest sequencing note:** today every span IS a multiple of 8, so this task's own gate can only
prove **neutrality**. The tail's arbitrary-span behaviour is proved in Task 5, whose gate is
REQUIRED to sweep anchored lines covering `L mod 8 == 0..7`. If Task 5 ships without that sweep,
Task 1 is unproven — say so rather than quietly dropping it.

**Files:**
- Modify: `engine/level/parallax.emp:1049-1071`

- [ ] **Step 1: Capture the neutrality baseline**

Build master's ROM and record the `Hscroll_Buffer` contents at a fixed scene position.

```bash
git checkout master && ./build.sh
```

Then, foreground on oracle: reload `s4.bin`, load `s4.lst`, reset, `start`×180, `right`×400,
`right+c`×12, `right`×390. Read `Hscroll_Buffer` (896 bytes, per-line mode) in two 448-byte reads
and save the hex to `/tmp/.../hscroll-before.txt`.

- [ ] **Step 2: Write the tail**

Replace `parallax.emp:1049-1071` with the version below. The comment change is part of the task —
the retired invariant must not keep asserting itself at the next reader.

```
// --- FLAT: same longword for every line of the band (8x unrolled + tail) ---
    // Band line spans USED to be guaranteed multiples of 8 (tops were Plane-B cell
    // rows scaled x8), and this path was a bare `span >> 3` unroll with no tail.
    // Parcel W's world-anchored overlay splits a band at an ARBITRARY scanline, so
    // that guarantee is gone. Without the tail a span of 1..7 yields `lsr #3` = 0,
    // `subq #1` = $FFFF, and dbf writes 65536 x 8 longwords from Hscroll_Buffer
    // forward — the frozen-VDP spray the Step-4a clamp at :618-622 exists to stop.
    // d2/d3/d6 are dead on this path (they are the deform paths' phase/shift/base),
    // so the remainder counter is free.
    .lp_flat:
        move.w  d5, d1
        sub.w   d4, d1
        ble     .band_done                          // empty/malformed band
        move.w  d5, d4                              // line index jumps to band end
        move.w  d1, d2
        andi.w  #7, d2                              // d2 = remainder lines 0..7
        lsr.w   #3, d1                              // d1 = whole groups of 8
        beq     .fl_tail                            // span < 8: tail only
        subq.w  #1, d1
    .fl_line:
        move.l  d0, (a4)+
        move.l  d0, (a4)+
        move.l  d0, (a4)+
        move.l  d0, (a4)+
        move.l  d0, (a4)+
        move.l  d0, (a4)+
        move.l  d0, (a4)+
        move.l  d0, (a4)+
        dbf     d1, .fl_line
    .fl_tail:
        // ZERO REMAINDER MUST BRANCH AROUND, not fall into a dbf: `subq #1` on 0
        // gives $FFFF and re-creates the exact 65536-iteration bug this tail fixes.
        tst.w   d2
        beq     .band_done
        subq.w  #1, d2
    .fl_rem:
        move.l  d0, (a4)+
        dbf     d2, .fl_rem
```

- [ ] **Step 3: Build and confirm it assembles**

```bash
./build.sh 2>&1 | grep -E "^built|error"
```
Expected: `built: sonic4 plain native ROM — crc=<new>`, no error lines.

- [ ] **Step 4: Prove neutrality on the real buffer**

Repeat Step 1's exact oracle sequence against the new ROM; save to `hscroll-after.txt`.

```bash
diff /tmp/.../hscroll-before.txt /tmp/.../hscroll-after.txt && echo "NEUTRAL"
```
Expected: `NEUTRAL`. Any difference means the tail changed output on multiple-of-8 spans, which is a
defect in the tail — the whole-group path must be bit-identical to the old unroll.

- [ ] **Step 5: Commit**

```bash
git add engine/level/parallax.emp
git commit -m "fix(parallax): remainder tail on the flat band fill

The 8x unroll assumed every band span is a multiple of 8 — true while tops were
cell rows x8, false the moment W's overlay splits a band at an arbitrary
scanline. A span of 1..7 wrapped the dbf counter to \$FFFF and sprayed ~2MB
past Hscroll_Buffer. Neutral on multiple-of-8 spans, proved by an identical
Hscroll_Buffer at a fixed scene position."
```

---

### Task 2: the shadow band view measures in screen lines

**Why:** an 8-px-quantised boundary cannot agree with a scanline-exact palette boundary. The shadow
view is RAM rebuilt every frame and read by exactly two routines, so the unit change is contained.
ROM data is untouched.

**Files:**
- Modify: `engine/level/parallax.emp:659-677` (rebase), `:915` (per-line reader), `:1104` (per-cell
  reader), and the `band_top_cell_next` neighbourhood at `:60-62` for the alias.

- [ ] **Step 1: Add the unit alias**

After `band_top_cell_next` (`parallax.emp:62`), add:

```
// band_top_line — the SAME byte as band_top_cell, at the same offset, named for the
// unit it carries in the SHADOW VIEW. ROM entries hold Plane-B cell rows 0..63;
// Step 4a's shadow copies hold SCREEN LINES 0..224 (both fit a byte). One name
// meaning two units is how the next reader gets it wrong, so the offset is spelled
// twice and grep separates the two populations.
const band_top_line      = offsetof(band_entry, band_top_cell)
const band_top_line_next = offsetof(band_entry, band_top_cell) + sizeof(band_entry)
```

- [ ] **Step 2: Rebase writes lines, keeping the clamp in cells**

In `parallax.emp:672-677`, the clamp stays at 28 CELLS (it is what stops the filler overrunning
`Hscroll_Buffer`); only the stored value changes unit:

```
    .clamp_top:
        cmpi.w  #28, d3
        ble     .write_top
        moveq   #28, d3                     // off-screen — zero-length fill
    .write_top:
        lsl.w   #3, d3                      // cells -> SCREEN LINES (0..224, fits a byte)
        move.b  d3, -sizeof(band_entry)(a4)
```

- [ ] **Step 3: The per-line filler drops its shift**

`parallax.emp:909-917` becomes:

```
    .next_band:
        // --- end_line for this band: next band's top (ALREADY screen lines), or 224 ---
        move.w  #224, d5
        subq.w  #1, d7
        beq     .have_end                           // last band
        moveq   #0, d5
        move.b  band_top_line_next(a1), d5
    .have_end:
```

- [ ] **Step 4: The per-cell filler gains one**

`parallax.emp:1102-1107` — `.last_band_end`'s `moveq #28` is ALREADY in cells and STAYS
(`224 >> 3 == 28`); only the peeked top converts:

```
        moveq   #0, d4
        move.b  band_top_line_next(a1), d4
        lsr.w   #3, d4                      // shadow lines -> cells
        jbra    .have_end
    .last_band_end:
        moveq   #28, d4
```

- [ ] **Step 5: Build, then prove neutrality on BOTH fill modes**

```bash
./build.sh 2>&1 | grep -E "^built|error"
```

Per-line mode is what the OJZ default uses (`DeformTable_Zero` is non-NULL). Repeat Task 1's oracle
sequence and diff `Hscroll_Buffer` against Task 1's `after` capture. Expected: identical.

Per-cell mode has no fixture in the scene. Prove it by inspection instead, and say so in the commit:
the only per-cell reader is `:1104`, and `lsr #3` exactly inverts the `lsl #3` added at Step 2 for
every value the clamp permits (0..28 cells → 0..224 lines → 0..28 cells).

- [ ] **Step 6: Commit** (its own commit — Task 5's hash attribution depends on this one being
      isolated)

```bash
git add engine/level/parallax.emp
git commit -m "refactor(parallax): shadow band tops measure in screen lines

Prerequisite for a scanline-exact anchored boundary. ROM entries keep cell rows;
only the per-frame shadow view changes unit, via a band_top_line alias at the
same offset so the unit is in the identifier at each site. Output-neutral."
```

---

### Task 3: `Raster_GetChannelBand` — the clamp, read from the patch table

**Why:** the raster patcher clamps every patched fire to its record's authored band
(`raster.emp:895-901`), load-bearing because a negative inter-record gap stores `$FF` = the park
word. If the overlay clamped differently, the two boundaries would separate outside that band —
reachable on the shipped fixture (`ojz_effects.emp:557`). Reading the raster table makes the clamp
ONE fact instead of two authored numbers.

**Files:**
- Modify: `engine/effects/raster.emp` (new `pub proc` next to `Raster_PatchAll`)
- Modify: `games/sonic4/test/ojz_scroll_test.emp` (a call site — an uncalled `pub proc` cannot pin
  its contract; this is the `Effects_SetWorldY` precedent from P-b §6)

- [ ] **Step 1: Write the accessor**

Table format, from `raster.emp:863`: a WORD count, then per record
`[arm_off][line_src][band_lo_fl][band_hi_fl]`, with a patchable record's channel in `line_src`'s low
bits and its high bit SET (`:889-890`).

```
// -----------------------------------------------
// Raster_GetChannelBand — return the fire-line band [lo, hi] the live patched program
// declares for a channel, so a SECOND consumer of the same world anchor clamps exactly
// where Raster_PatchAll does (:895-901). Without this the palette boundary pins at its
// band edge while a parallax boundary keeps following the camera, and the two separate —
// the defect Parcel W exists to remove. Reading the table rather than duplicating the
// band into parallax data keeps it ONE fact: change `patchable`'s band and both move.
//
//   d0.w = channel
// Out: Z SET   -> no band (no table, or no patchable record for this channel);
//                 the caller must NOT clamp — [0,224] is correct there
//      Z CLEAR -> d1.w = lo fire line, d2.w = hi fire line
// -----------------------------------------------
pub proc Raster_GetChannelBand (d0: u16) -> (d1: u16, d2: u16) clobbers(d0-d2/a0) {
        move.l  Raster_Patch_Tab, a0
        move.l  a0, d1
        beq     .none                       // liveness: the TABLE, same test as Raster_PatchAll
        andi.w  #RASTER_MAX_PATCH-1, d0
        ori.w   #$8000, d0                  // a patchable line_src has the high bit SET
        move.w  (a0)+, d2                   // record count (a WORD)
        subq.w  #1, d2
    .entry:
        addq.l  #2, a0                      // skip arm_off
        move.w  (a0)+, d1                   // line_src
        cmp.w   d0, d1
        beq     .found
        addq.l  #4, a0                      // skip the two band words
        dbf     d2, .entry
    .none:
        moveq   #0, d1
        move.w  d1, d2                      // Z set
        rts
    .found:
        move.w  (a0)+, d1                   // band_lo_fl
        move.w  (a0), d2                    // band_hi_fl
        moveq   #1, d0
        tst.w   d0                          // Z clear
        rts
}
```

- [ ] **Step 2: Verify the encoding claim against the emitter before trusting it**

The `ori.w #$8000` above assumes `patchable` records store `line_src` with the high bit set and the
channel in the low bits. Confirm in `engine/effects/raster_dsl.emp` (`patch_table` / `RasterFire.Patch`)
and in `raster.emp:887-891`, which does `bpl .static` then `andi.w #RASTER_MAX_PATCH-1, d2`.
If the encoding differs, fix the accessor, not the comment.

- [ ] **Step 3: Add the call site**

In `games/sonic4/test/ojz_scroll_test.emp`, beside the existing `Effects_SetWorldY` hotkey block
(`:403-423`, DEBUG-only, input-gated so a replay that never presses the chord is bit-identical),
clamp the nudge to the channel's own band:

```
        // Clamp the nudge to channel 0's declared raster band, so the hotkey cannot
        // drive the anchor somewhere Raster_PatchAll would silently clamp anyway —
        // and so Raster_GetChannelBand has a caller. An uncalled `pub proc` assembles
        // either way; what it cannot pin is its CONTRACT (P-b §6, fx_tint_band).
        move.w  d1, -(sp)
        moveq   #0, d0
        jbsr    Raster_GetChannelBand
        move.w  (sp)+, d1
        beq     .anchor_no_clamp            // no band declared: leave the nudge alone
```

(then clamp `d1` — which is world Y — against `lo/hi + Camera_Y + 1`, converting fire line to world
space; spell the conversion once, here, and reference `raster.emp:894`.)

- [ ] **Step 4: Build both shapes**

```bash
./build.sh 2>&1 | grep -E "^built|error"
DEBUG=1 ./build.sh 2>&1 | grep -E "^built|error"
```
Expected: both build; the plain shape's CRC changes only by the accessor's bytes (the call site is
DEBUG-only).

- [ ] **Step 5: Verify on oracle that the accessor returns the authored band**

Boot `s4.debug.bin`, load `s4.debug.lst`. `OJZ_TwoChannel` declares channel 0 band 40..120 and
channel 1 band 130..200 (`ojz_effects.emp:557-558`). Set a breakpoint after the accessor's `rts`
with `d0 = 0` and read `d1`/`d2`; expect the fire-line pair for 40..120. Repeat for channel 1.
Then read with `Raster_Patch_Tab == 0` (cross into section 1) and confirm Z is set.

- [ ] **Step 6: Commit**

```bash
git add engine/effects/raster.emp games/sonic4/test/ojz_scroll_test.emp
git commit -m "feat(raster): Raster_GetChannelBand — the patch band as ONE fact

A second consumer of a world anchor must clamp exactly where Raster_PatchAll
clamps, or the two boundaries separate outside the band — reachable on the OJZ
fixture. Reading the emitted table beats duplicating the band into parallax
data: change patchable's band and both clamps move, with no second author
action possible. Z set means no band declared, and [0,224] is correct there."
```

---

### Task 4: the overlay

**Files:**
- Modify: `engine/structs.emp:161-178` (claim the three pad bytes)
- Modify: `games/sonic4/data/parallax/configs.emp:57-80` (`hdr()` params) + a fixture config
- Modify: `engine/level/parallax.emp` (Step 4a post-pass, inserted after `:693`, before
  `.bands_ready:`)
- Modify: `engine/system/buffers.emp:259-261` (the twin DMA-length key)
- Modify: `engine/effects/preset.emp` (`PATCH_ANCHOR_NONE` default)
- Modify: `games/sonic4/data/effects/ojz_effects.emp` (a preset binding `ep_parallax`)

- [ ] **Step 1: Claim the pad bytes — zero added bytes**

`engine/structs.emp`: `pcfg_pad: u8` → `pcfg_anchor_ch: u8`; `pcfg_pad2: [u8; 2]` →
`pcfg_anchor_dsa: u8`, `pcfg_anchor_dsb: u8`. `sizeof(parallax_config)` MUST stay 28 —
`parallax.emp:95-96` ensures it stays even or `copy_band_entry`'s `move.l` run address-errors on
every odd-indexed entry. Both pads have exactly one writer (`configs.emp:72`, `:78`) and zero
readers, verified.

Add beside the struct:

```
// $FF = this config has no world-anchored overlay. Not 0: 0 is a legal channel.
pub const PARALLAX_ANCHOR_NONE = $FF
```

- [ ] **Step 2: `hdr()` gains the parameters, defaulted to "none"**

In `configs.emp:57-80`, add `anchor_ch: int = PARALLAX_ANCHOR_NONE, anchor_dsa: int = 15,
anchor_dsb: int = 15` and write them in place of the pads. Add the live guards — both compare ints
inside a comptime fn that is CALLED from this file, so both evaluate (unlike a `Label`-vs-int
compare, which `preset.emp:105-111` proves is unevaluable and silently always-passes):

```
    ensure(anchor_ch == PARALLAX_ANCHOR_NONE || band_count + 1 <= MAX_PARALLAX_BANDS,
           "parallax hdr(): an anchored config SPLITS a band at runtime, so the shadow view needs band_count+1 entries — {band_count}+1 exceeds MAX_PARALLAX_BANDS ({MAX_PARALLAX_BANDS}) and the split would write past Parallax_Shadow_Bands")
    ensure(anchor_ch == PARALLAX_ANCHOR_NONE || anchor_ch < RASTER_MAX_PATCH,
           "parallax hdr(): anchor_ch {anchor_ch} is not a patch channel — the overlay indexes Effects_World_Y[RASTER_MAX_PATCH]")
```

- [ ] **Step 3: Both mode keys learn about anchoring**

A scanline-exact boundary needs per-line fill. `parallax.emp:699-701` selects the mode and
`buffers.emp:259-261` is its TWIN keying the HScroll DMA length off the same fields; they must
change together or a mode-differing config ships a 112-byte DMA for an 896-byte buffer. In BOTH,
after the `or.l` of the two deform-table pointers, also treat `pcfg_anchor_ch != PARALLAX_ANCHOR_NONE`
as selecting per-line.

Do NOT instead add a comptime ensure requiring a deform table — that is the `Label`-vs-int vacuous
guard (spec §3.5).

- [ ] **Step 4: The overlay itself**

Insert after `parallax.emp:693` (`lea Parallax_Shadow_Scroll_B, a3`), before `.bands_ready:`. At
that point `a0` = config, `d7` = band_count, `a1/a2/a3` = shadow bases, and d0-d6/a4-a6 are dead
(verified: the rotation loop's last use is `dbf d6, .copy_band` at `:690`).

The algorithm, in order — implement it as written and keep the comments:

```
        // --- Step 4b: world-anchored deform overlay (Parcel W) ---
        // The band TOP is anchored to the camera; the wave PHASE is NOT touched. Those
        // are different registers in Fill_PerLine (d5 vs d2/d6), which is why this cannot
        // re-open Harmony defect #2 — see the spec §2.
        moveq   #0, d0
        move.b  parallax_config.pcfg_anchor_ch(a0), d0
        cmpi.w  #PARALLAX_ANCHOR_NONE, d0
        beq     .bands_ready                // no overlay: today's path, byte-identical
        move.w  d0, -(sp)                   // channel survives the accessor
        add.w   d0, d0
        lea     Effects_World_Y, a4
        move.w  (a4, d0.w), d1              // authored world Y
        move.w  Camera_Y, d2                // 16.16 -> the integer word (raster.emp:885)
        sub.w   d2, d1                      // d1 = L, signed; may go negative meaningfully
        move.w  (sp)+, d0
        // clamp to the channel's raster band so both boundaries pin together (§3.1)
        jbsr    Raster_GetChannelBand       // Z set = no band; d1/d2 = lo/hi FIRE lines
        beq     .l_clamp_screen
        addq.w  #1, d1                      // fire line -> screen line, the ONE +1
        addq.w  #1, d2
        ... clamp L into [d1, d2] ...
    .l_clamp_screen:
        ... clamp L into [0, 224]; L >= 224 -> jbra .bands_ready (off-screen below) ...
        // find the shadow band containing L, split it there, shift the tail down one slot,
        // and duplicate the parent's scroll words into the new slot (§3.4 — the fillers walk
        // entries and scroll words in lockstep, so an entry inserted without its scroll word
        // makes every band below scroll at its neighbour's rate)
        ...
        // from the inserted entry to the last band, overwrite the deform shifts
        ...
        addq.w  #1, d7                      // the shadow view now has one more band
```

**Register budget is a constraint, not a preference:** `Parallax_Step4_Fill` declares
`clobbers(d0-d7/a0-a6)`, so d0-d6 and a4-a6 are free here, but `d7` (band count) and `a0` (config)
are LIVE and the fillers consume both. `Parallax_Step5_Vscroll` declares `clobbers(d0-d7/a0-a6)` yet
`d7` must survive it — confirm how that already works before adding a second live count.

- [ ] **Step 5: The default anchor becomes an off-screen sentinel**

In `preset.emp`, `preset()`'s `patch_world_ys: array = [0,0,0,0]` becomes
`[PATCH_ANCHOR_NONE; 4]` with `pub const PATCH_ANCHOR_NONE = $7FFF` — large and POSITIVE, so
`L = $7FFF - Camera_Y` stays positive and lands in the `>= 224` off-screen branch with no sign flip.
A zero default would mean `L = -Camera_Y <= 0` = "fully submerged", the wrong safe default (§3.6).

- [ ] **Step 6: The fixture — an authoring surface with a call site**

`ep_parallax` is 0 in EVERY preset in the tree; configs reach the pipeline through
`sec_parallax_config` / the act default. So this binding has never executed, and `fx_tint_band`
shipped broken for two parcels for exactly that reason. Add to `configs.emp` an
`ParallaxConfig_OJZ_Underwater` (the OJZ default's bands, plus `anchor_ch: 0`, `anchor_dsa`/`dsb`
set to a visible shift), and point `OJZ_Preset_Sec0` at it via `parallax:`. Sec0 already declares
`patched: OJZ_TwoChannel, patch_world_ys: [224, 314, ...]`, so channel 0 drives both boundaries.

- [ ] **Step 7: Build all four shapes**

```bash
./build.sh && DEBUG=1 ./build.sh && ./build.sh demo && DEBUG=1 ./build.sh demo
```
Expected: four builds, no errors.

- [ ] **Step 8: Commit**

```bash
git add engine/structs.emp engine/level/parallax.emp engine/system/buffers.emp \
        engine/effects/preset.emp games/sonic4/data/parallax/configs.emp \
        games/sonic4/data/effects/ojz_effects.emp
git commit -m "feat(parallax): world-anchored deform overlay — one anchor, two readers"
```

---

### Task 5: the gate

Spec §5 is the authority; revision 1's gate could not fail and the corrections are the point.

- [ ] **Step 1: Observe VRAM, not RAM**

Read the HScroll table in VRAM (derive the address from `Static_Hscroll_Line`'s DMA descriptor), not
just `Hscroll_Buffer`. An implementation whose buffer is right but whose DMA never lands must fail.

- [ ] **Step 2: Predict L from authored constants**

`Debug_Scene_Freeze` pins the camera (`ojz_scroll_test.emp:307`). With world Y 224 authored and
`Camera_Y` known, `L` is predicted, never read back from `Effects_World_Y` — otherwise the gate is
circular again.

- [ ] **Step 3: Bracket the palette leg in time**

Assert base palette at line `L−1` AND changed palette at `L`, on the CRAM lines the program writes
(`sec_pal` is lines 1-3, never line 0). "Changed by line L" alone passes for any boundary above L.
First verify by hand that `run_to_scanline` + `read_cram` shows the HInt write at all, and whether
the stop lands before or after that line's HInt — CRAM reads are frame-latched and the failure
direction is loud-on-correct-code, not vacuous.

- [ ] **Step 4: Bracket the scroll leg in space and time**

The split entry inherits its parent's scroll, so `L−1` vs `L` differ only by the ripple sample,
which crosses zero. Compare the below-`L` region against a no-anchor control across two consecutive
frames.

- [ ] **Step 5: Sweep `L mod 8 == 0..7` — this is Task 1's proof**

Move the anchor with `Effects_SetWorldY` (C+Up/Down, `ojz_scroll_test.emp:403-423`) to land the
boundary at eight consecutive lines, and assert the buffer is correct at each. This is the ONLY
place the `.lp_flat` remainder tail is exercised. Skipping it leaves Task 1 unproven — record that
plainly if it is skipped.

- [ ] **Step 6: Clamp edges by inversion plus the adjacent legal case**

`L <= 0` (fully submerged, insert at 0), `L >= 224` (shadow untouched), `L = 1`, `L = 223`, and an
`L` outside the raster band proving both boundaries pin TOGETHER.

- [ ] **Step 7: Write the evidence and run the byte ritual**

`docs/benchmarks/effects-p3-w/GATE-EVIDENCE.md`, then: freeze FIRST, then the strict suite, then
`refreeze --check` + `repin --check`, then re-verify CRCs AFTER the freeze (pins feed placement).
Boot all four shapes and look at each — no gate in this parcel looks at a screen, which is how the
release-shape blackout got through once before.

- [ ] **Step 8: Merge as a pair**

aeon and sigil merge together; the sigil registry is global and the pairing can break.

---

## Self-review against the spec

- §3 overlay → Task 4. §3.1 clamp → Task 3 + Task 4 step 4. §3.2 units → Task 2. §3.3 `.lp_flat` →
  Task 1 (+ Task 5 step 5 for its behavioural proof). §3.4 scroll words → Task 4 step 4. §3.5 mode
  keys → Task 4 step 3. §3.6 sentinel → Task 4 step 5. §4 unexercised surface → Task 4 step 6.
  §5 gate → Task 5. §6 order → task order. No spec section is unimplemented.
- Names are consistent across tasks: `band_top_line` / `band_top_line_next` (Task 2, used in Tasks 2
  and 4), `Raster_GetChannelBand` (Tasks 3, 4), `PARALLAX_ANCHOR_NONE` (Tasks 4 steps 1-2),
  `PATCH_ANCHOR_NONE` (Task 4 step 5) — deliberately two different constants: one marks a config
  with no overlay, the other an anchor slot with no anchor.
- **Known incompleteness, stated rather than hidden:** Task 4 step 4's split/shift loops are given as
  ordered algorithm plus register budget, not finished assembly. Writing 80 lines of unassembled,
  unrun 68000 into a plan and calling it complete would be false precision — the register liveness
  at the insertion point is the first thing the implementer must verify, and the spec's §3.4 states
  exactly what the loops must preserve.
