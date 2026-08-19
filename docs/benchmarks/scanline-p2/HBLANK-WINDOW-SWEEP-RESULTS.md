# HBlank window sweep — RESULTS (2026-08-19)

Run of `docs/benchmarks/scanline-p2/HBLANK-WINDOW-SWEEP-SPEC.md`, substrate item 1b.
Driver: `tools/hblank_window_sweep.py` (this branch). Every number below is measured or
derived here; nothing is copied from the spec's prediction tables.

| | |
|---|---|
| ROM | `/home/volence/sonic_hacks/aeon/s4.debug.bin`, 712,772 bytes, mtime 2026-08-19 01:07, md5 `249a3193cfa67ebd31b9894ad059f86a` (master `1185f223`) |
| Listing | `/home/volence/sonic_hacks/aeon/s4.debug.lst`, same mtime |
| Server | `/home/volence/sonic_hacks/oracle-next/target/release/oracle-aether`, mtime 2026-08-19 00:49 (oracle-next `fdb6903`) |
| Session | 2026-08-19 01:31-02:05 local; `uptime` at start `01:31:03 up 1 day, 1:54`, at the last run `01:57:33 up 1 day, 2:21` |
| Per-run wall clock | anchors 4.8 s · content map 28.8 s · full default run (anchors+map+A1+A2+sweep 0..30) 54.1 s · wide sweep 0..200 at 12 rows 71.1 s |

**No capture anywhere in this work returned `source != "raster"`.** The assertion is a hard
failure in the driver and never fired; `mode` was `h40` on every reply. The `stateRender`
failure mode the spec warns about did not occur and is not what limited this measurement.

---

## Headline

1. **A1 (determinism) PASSES.** Three independent server processes, same N, byte-identical
   rows. This is the criterion three prior Aeon capture protocols failed; it now holds.
2. **A2 as literally written FAILS; A2 as a poison PASSES.** N=0 and N=17 render identically
   on all six rows — but they are identical because they sit inside one *quantum* of the
   instrument's resolution, not because the instrument is post-hoc. Scanning N shows four
   distinct pictures.
3. **The spec's own §4 fixture is vacuous on this ROM, for two independent reasons**, both
   measured, both fixed before any sweep number was recorded (§ "Fixture defects" below).
4. **`emulator/scanlines` resolves a landing to ONE SCANLINE, never to a pixel.** Measured
   quantum 490.0 cycles against an arithmetic H40 NTSC line of 488.6 (ratio 1.0029), over
   four independent line boundaries. Confirmed in oracle-core's source: the whole row is
   rendered once per line at the line-start `Scanline` event.
5. **The §6 procedure therefore cannot deliver its answer as written** — its "CLEAN range" on
   this instrument is the quantum, not the window — but the sweep still yields the window,
   from where the picture changes rather than from where a flip sits inside a row:

   > **Upper edge N = 21.5, MEASURED.  Lower edge N = 15.21, DERIVED from the blanking width.
   > Clean N ∈ [15.21, 21.5] → integers 16..21.  CENTRE N = 18.**

   The §3 prediction's centre (17) falls inside the measured window. Its lower edge (15) is
   within a quarter of a spin iteration of the derived 15.21. Its **upper edge (19) is wrong
   by 2.5 iterations**, and the reason is a specific term in §2 — see "Where §2/§3 is wrong".
6. **The px/cyc cross-check is UNOBTAINABLE on this instrument** and no value for it is
   reported. A flip x inside a row is exactly what per-line rendering cannot express.

---

## Instrument assertions and controls

### The `source == "raster"` assertion

Baked into `capture()` as a hard failure, checked on every capture taken in this session —
anchors (5 fixtures × 3 captures), the content map at two masks (42 windows × 2 captures,
twice), A1 (3), A2 (22), and five sweeps. It never fired.
`mode` was checked too (`h40`, 320 columns); it never fired either. The `caveat` field was
never present in any reply.

### A1 — determinism (spec §8) — **PASS**

Three *fresh `oracle-aether` processes* (not three resets in one process), each driven
through the identical schedule with N=17, rows 97-102 read in one call:

```
   boot 1: frame 185  rows [97, 98, 99, 100, 101, 102]  len 11546
   boot 2: frame 185  rows [97, 98, 99, 100, 101, 102]  len 11546
   boot 3: frame 185  rows [97, 98, 99, 100, 101, 102]  len 11546
   -> PASS (byte-identical)
```

The digest compared is the full RGB of all six rows concatenated (11,546 characters), not a
hash of a summary. Determinism is what makes every cross-capture comparison in this document
legitimate; the fixed reset-and-frame-count schedule is what produces it.

### A2 — liveness (spec §8) — literal **FAIL**, generalized **PASS**

Literal form, N=0 vs N=17, on the working fixture (mask `$000E`, CRAM `$50`):

```
      row 97:   0 differing columns
      row 98:   0 differing columns
      row 99:   0 differing columns
      row 100:   0 differing columns
      row 101:   0 differing columns
      row 102:   0 differing columns
   total differing columns across the window: 0  -> FAIL
```

Both captures are recorded verbatim (full RGB per row) in the run's JSON under
`A2.rows_N0` / `A2.rows_N17`.

The literal pair failing is *not* sufficient to rule the instrument blind, and ruling it blind
on that basis would have been wrong. A2's substantive claim is "this is not a post-hoc
render", and a post-hoc render answers identically for **every** N. So the driver also scans
N ∈ {0, 3, …, 57} and counts distinct pictures:

```
   distinct pictures over N in 0..57 step 3: 4   -> PASS
      identical at N [0, 3, 6, 9, 12, 15, 18, 21]
      identical at N [24]
      identical at N [27]
      identical at N [30, 33, 36, 39, 42, 45, 48, 51, 54, 57]
```

N=0 and N=17 are both in the first group. The instrument is coarse, not blind — and the
distance between "coarse" and "blind" is the whole finding here.

**On the same scan with the spec's literal fixture** (CRAM `$4A`, header mask `$0002`) the
generalized form fails too — `distinct pictures over N in 0..57 step 3: 1` — and the driver
stops with BLOCKED, as it should: that fixture genuinely cannot express an answer.

---

## Fixture defects found (both fixed before any sweep number was recorded)

Neither repair moves the fixture toward the §3 prediction; both are the §4 content-trap
repair, applied where the measurement said the trap actually was. The evidence for each is a
measurement, and both are reproducible from the driver's flags.

### Defect 1 — the header `pal_dirty_mask` makes the tint permanent

Word 0 of a raster program is `pal_dirty_mask`; `Raster_VBlank` ORs it into `Palette_Dirty`,
where bit N means "re-ship palette line N to CRAM this VBlank"
(`engine/system/buffers.emp`, the `bclr #0/#1/#2/#3` ladder). The spec's §4 image carries
`$0002` — line 1 only — inherited from `raster_cost_probe.PIN_MASK`, where it is correct for
a *cost* measurement that never reads the picture.

The §4 fixture tints palette **line 2**. With only line 1 re-shipped, nothing ever puts line 2
back: the colour written at line 99 of frame K is still in CRAM at line 0 of frame K+1, so
every frame after the first is uniformly tinted from the top and the landing position is not
expressed in the picture at all.

Measured, with `--only map --mask 0x0002`: **42 three-entry windows across palette lines 1-3,
six rows each — 0 sensitive columns, total, everywhere.**

Fixed by setting word 0 to `$000E` (lines 1-3), which is what `palette.emp` itself ORs in
(`ori.b #%1110, Palette_Dirty`) when a global operator moves the level palette. Held constant
across references, anchors and every N.

### Defect 2 — CRAM `$4A` is not sampled by the art at rows 97-102

§4 fixes the burst at `$4A` and warns in the same breath that the address must be one the art
at those rows references. With the mask repaired so the question is askable at all, the
measured usage at the frozen spawn (`Camera_Y = 144`) is:

| CRAM | palette line 2 entries | r97 | r98 | r99 | r100 | r101 | r102 | total | min/row |
|---|---|---|---|---|---|---|---|---|---|
| `$40` | 0-2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `$42` | 1-3 | 18 | 15 | 8 | 6 | 3 | 8 | 58 | 3 |
| `$44` | 2-4 | 18 | 15 | 16 | 11 | 6 | 8 | 74 | 6 |
| `$46` | 3-5 | 20 | 15 | 16 | 13 | 6 | 11 | 81 | 6 |
| `$48` | 4-6 | 2 | 0 | 8 | 7 | 3 | 3 | 23 | 0 |
| **`$4A`** | **5-7 (the spec's)** | **2** | **0** | **0** | **2** | **0** | **3** | **7** | **0** |
| `$4C` | 6-8 | 165 | 185 | 189 | 172 | 182 | 197 | 1090 | 165 |
| `$4E` | 7-9 | 204 | 207 | 231 | 216 | 229 | 218 | 1305 | 204 |
| **`$50`** | **8-10 (used here)** | **285** | **270** | **285** | **294** | **300** | **275** | **1709** | **270** |
| `$52` | 9-11 | 123 | 92 | 106 | 124 | 120 | 92 | 657 | 92 |
| `$54` | 10-12 | 91 | 89 | 68 | 91 | 75 | 87 | 501 | 68 |
| `$56` | 11-13 | 10 | 26 | 14 | 13 | 4 | 30 | 97 | 4 |
| `$58` | 12-14 | 12 | 28 | 9 | 11 | 12 | 20 | 92 | 9 |
| `$5A` | 13-15 | 5 | 9 | 5 | 0 | 10 | 4 | 33 | 0 |

Every window of palette **line 1** and every window of palette **line 3** measured 0 on all
six rows, which independently confirms R1's note that line 1 is "nearly unused at those rows".

At `$4A` the boundary row and both §6 controls (98, 99, 101) are blind — 7 sampled columns in
total across six rows. `$50` samples 270-300 of 320 columns on every row. The sweep uses
`$50`; the driver's `--addr` defaults to it and the map is what chose it.

---

## Anchors (§6b) — run first, and they earned it

All five with the repaired mask. "sens" = columns whose colour the op changes at all (measured
from two reference captures of the same program fired above and below the read window); "new"
= how many of them show the post-op colour.

| Anchor | first new pixel | verdict @ authored line | verdict @ authored+1 |
|---|---|---|---|
| `reg_set($8C89) + stream_cram($4A,[$000E])` @ 120 | row 121, x=2 (row's leftmost sampled column) | TOO LATE | **CLEAN** |
| same, `stream_cram($50,…)` | row 121, x=0 | TOO LATE | **CLEAN** |
| `pal_restore($48,3)` @ 140, lone (§6b as written) | none | **VACUOUS** | **VACUOUS** |
| `stream_cram($48,tint)`@100 + `pal_restore($48,3)`@140 | row 141, x=46 (row's leftmost sampled column) | TOO LATE | **CLEAN** |
| same at `$50` | row 141, x=0 | TOO LATE | **CLEAN** |

Row detail for the two well-sampled ones:

```
anchor_row119_50   reg_set($8C89) + stream_cram($50,[$000E]), authored line 120
   row 117 sens 304  new   0  old 304
   row 118 sens 304  new   0  old 304
   row 119 sens 304  new   0  old 304
   row 120 sens 320  new   0  old 320
   row 121 sens 320  new 320  old   0   first_new_x 0
   row 122 sens 320  new 320  old   0   first_new_x 0

anchor_r1_band_50  stream_cram($50,tint)@100 + pal_restore($50,3)@140
   row 137 sens 250  new   0  old 250
   row 138 sens 250  new   0  old 250
   row 139 sens 241  new   0  old 241
   row 140 sens 260  new   0  old 260
   row 141 sens 262  new 262  old   0   first_new_x 0
   row 142 sens 258  new 258  old   0   first_new_x 0
```

Three things follow, and all three shaped the rest of the run.

**(a) Both anchors are CLEAN — a perfectly sharp full-row boundary, no partial row anywhere.**
That is §6b's "both CLEAN" row.

**(b) The boundary sits one row past the authored line, on every anchor and on the sweep.**
The driver therefore classifies against an explicit edge row and reports both readings side by
side rather than silently adopting either. The one-row offset is not an artifact of the
instrument's row indexing: the sweep's own boundary measurement (below) places the burst
inside line 100's period at every N in 0..27, never inside line 99's, so for this fire shape
the authored line's own row cannot be the boundary. See "What this says about the defect".

**(c) §6b's second anchor as written is vacuous, and structurally so.** `OP_PAL_RESTORE`
streams from `Palette_Ship_Snap`, this frame's base DMA payload
(`engine/effects/raster.emp`, `.op_pal_restore`), so a lone restore writes the colours already
in CRAM. It changes nothing and can never be an anchor. R1 §7.3's capture was a *band* — a
tint ON above the restore — and reproducing that shape (fourth and fifth rows above) makes the
anchor work. The lone form is kept in the driver so the record shows what the literal fixture
does.

---

## The sweep, N = 0..30 (spec §6's range), full table

Fixture: `program_words([(100, [stream_cram($50, [$0E0E,$0E0E,$0E0E])])])`, header mask
`$000E`, spin poked at `Raster_Buf_A + 20` (readback-verified on every capture). Sensitivity
of the read window, from the two reference captures:

```
   row 97: 285 columns, x 0..319, max gap 3
   row 98: 270 columns, x 0..319, max gap 5
   row 99: 285 columns, x 1..319, max gap 4
   row 100: 294 columns, x 0..319, max gap 4
   row 101: 300 columns, x 0..319, max gap 3
   row 102: 275 columns, x 0..319, max gap 5
```

`flipX` is the first sensitive column reading new; `atLeft` is whether that column is the
row's leftmost sensitive one (§6's "x = 0", read at the resolution the art permits). The last
six columns are how many sensitive columns on each row read new.

```
     N flipRow flipX atLeft  edge 100      edge 101         r97    r98    r99   r100   r101   r102
     0     101     0   True  TOO LATE      CLEAN              0      0      0      0    300    275
     1     101     0   True  TOO LATE      CLEAN              0      0      0      0    300    275
     2     101     0   True  TOO LATE      CLEAN              0      0      0      0    300    275
     3     101     0   True  TOO LATE      CLEAN              0      0      0      0    300    275
     4     101     0   True  TOO LATE      CLEAN              0      0      0      0    300    275
     5     101     0   True  TOO LATE      CLEAN              0      0      0      0    300    275
     6     101     0   True  TOO LATE      CLEAN              0      0      0      0    300    275
     7     101     0   True  TOO LATE      CLEAN              0      0      0      0    300    275
     8     101     0   True  TOO LATE      CLEAN              0      0      0      0    300    275
     9     101     0   True  TOO LATE      CLEAN              0      0      0      0    300    275
    10     101     0   True  TOO LATE      CLEAN              0      0      0      0    300    275
    11     101     0   True  TOO LATE      CLEAN              0      0      0      0    300    275
    12     101     0   True  TOO LATE      CLEAN              0      0      0      0    300    275
    13     101     0   True  TOO LATE      CLEAN              0      0      0      0    300    275
    14     101     0   True  TOO LATE      CLEAN              0      0      0      0    300    275
    15     101     0   True  TOO LATE      CLEAN              0      0      0      0    300    275
    16     101     0   True  TOO LATE      CLEAN              0      0      0      0    300    275
    17     101     0   True  TOO LATE      CLEAN              0      0      0      0    300    275
    18     101     0   True  TOO LATE      CLEAN              0      0      0      0    300    275
    19     101     0   True  TOO LATE      CLEAN              0      0      0      0    300    275
    20     101     0   True  TOO LATE      CLEAN              0      0      0      0    300    275
    21     101     0   True  TOO LATE      CLEAN              0      0      0      0    300    275
    22     101     0   True  FIXTURE BROKEN  CLEAN            0      0      0      0    229    275
    23     101     0   True  FIXTURE BROKEN  CLEAN            0      0      0      0    229    275
    24     101     0   True  FIXTURE BROKEN  CLEAN            0      0      0      0    229    275
    25     101     0   True  FIXTURE BROKEN  CLEAN            0      0      0      0    182    275
    26     101     0   True  FIXTURE BROKEN  CLEAN            0      0      0      0    182    275
    27     101     0   True  FIXTURE BROKEN  CLEAN            0      0      0      0    182    275
    28     102     0   True  FIXTURE BROKEN  TOO LATE         0      0      0      0      0    275
    29     102     0   True  FIXTURE BROKEN  TOO LATE         0      0      0      0      0    275
    30     102     0   True  FIXTURE BROKEN  TOO LATE         0      0      0      0      0    275
```

`FIXTURE BROKEN` in the `edge 100` column is the classifier correctly refusing to grade
against an edge row two rows below where anything happens; the `edge 101` column is the live
one. The §6 classifier's answer, printed verbatim by the driver:

```
   edge row 101: contiguous CLEAN [(0, 27)]   widest N in [0, 27] (28 values)  CENTRE N = 13
```

**That 13 is not the answer and must not be used.** N ∈ [0, 15] are landings inside line 100's
*active display* that this instrument renders identically to a clean one. The next section is
why, and what the real answer is.

### `flipX` is 0 at every single N — that is the finding

Across the 201 captures at N = 0..200, the set of distinct flip x values is exactly `{0}`, and
`atLeft` is `True` at every N. The partial-row landing that §6's TOO EARLY / TOO LATE rows are
built to detect, and that R1 §7.3 measured directly on the GUI oracle at x≈170 and x≈180, is
not expressible here.

`emulator/scanlines` returns the retained per-line frame, and that frame is built by
`System::deliver_event`'s `Scanline` handler, which calls `vdp.render_scanline(line)` **once
per line, at the line-start event**. The whole 320-pixel row is rendered atomically from VDP
state — CRAM included — as it stands at the start of the line. A CRAM write during a line
cannot change that line; it can only change the next. oracle-core states this itself, in
`bus.rs`, as conformance **Limitation L1**.

This is strictly better than the `stateRender` fallback the spec warns about — the surface
does see mid-*frame* effects, which is what A2's generalized form confirms — and strictly
coarser than mid-*line*, which is what this sweep needed.

---

## Where the picture actually changes — the measurement that survives

Widening the read window to 12 rows and sweeping N = 0..200 puts four consecutive line
boundaries in view. The picture changes at exactly twelve values of N, in four tight groups:

```
   boundaries at N = [22, 25, 28, 71, 74, 77, 119, 123, 126, 169, 172, 174]
   groups: [[22, 25, 28], [71, 74, 77], [119, 123, 126], [169, 172, 174]]
   within-group step: [3, 3, 3, 3, 4, 3, 3, 2]  ->  30.0 cycles per burst word (8 intervals)
   between-group step: first-boundary N = [22, 71, 119, 169]  ->  490.0 cycles per sampling
                       period   (one H40 NTSC scanline = 488.6, ratio 1.0029)
```

Both scales fall straight out of the data, and neither was fitted:

* **Within a group: 30.0 cycles, averaged over 8 intervals.** The burst is three
  `move.w (a1)+, VDP_DATA`; each crosses the sampling instant at its own N, and the spacing is
  the per-word cost. This is an independent hardware measurement of
  `RASTER_STREAM_WORD_CYC = 30`, the constant `raster_dsl.emp` ships — arrived at without
  reading that constant.
* **Between groups: 490.0 cycles**, against 3420 mclk / 7 = 488.6 cycles per H40 NTSC line —
  0.29% apart, inside the ±10-cycle quantization of a 10-cycle-per-N sweep. The sampling
  period is one scanline, measured, four times.

The partial-row counts show the same thing from the other side: at N = 22-24 row 101 reads 229
of its 300 sensitive columns new, at 25-27 it reads 182, at 28+ it reads 0 — the three colour
words of the burst dropping past the sampling instant one at a time, in the order they are
written.

### The window

The last word written crosses the sampling instant first (at the smallest N); the first word
crosses last. A burst is clean exactly when the last word still precedes the sampling instant
*and* the first word has not yet preceded the start of blanking.

```
   burst span (first write -> last write): 60 cycles          [measured: 10*(28-22)]
   blanking window: 122.9 cycles                              [3420/7 - 320*8/7, H40 NTSC]
   upper edge  N = 21.5    MEASURED  (group's first boundary 22, ±0.5)
   lower edge  N = 15.21   DERIVED   (first-word crossing 27.5 minus 122.9/10)
   => clean N in [15.21, 21.5]  = integers 16..21   CENTRE N = 18
```

The lower edge is **derived, not measured, and cannot be measured on this instrument**: the
start of blanking is not a sampling instant, so nothing in the picture changes when the burst
crosses it. Everything at N < 15.2 is a landing inside line 100's active display that reads
identically to a clean one.

### Where §2/§3 is wrong

The measured slack is **62.9 cycles (6.29 spin iterations)**, not §2's ~39 cycles (3.9
iterations). The blanking width is not in dispute — 122.9 cycles is the same figure both
arrive at. The disagreement is entirely §2's **"3-word CRAM burst ≈ 84 cycles"** row. What has
to fit inside blanking is the span from the *first* data write to the *last*, which this
sweep measures at **60 cycles** (2 × 30, confirmed 8 ways). 122.9 − 60 = 62.9. §2's 84 counts
a trailing iteration that does not have to complete before the line ends, and that single term
is the whole 2.5-iteration error in §3's upper edge.

§3's lower edge is essentially right: 15 against a derived 15.21. Its **centre, 17, is inside
the measured window**, so the prediction is refined rather than falsified. The centre moves
15 → 18.

### px/cyc cross-check — UNOBTAINABLE

§6 asks for the cycles-per-pixel figure as a by-product of the flip x. There is no flip x that
moves, so there is no fit, and none is reported. For the record: the arithmetic value is
320 px / (2560/7 cycles) = 0.875 px/cyc, which is what R1's 0.875 is too — it is a definition
of H40 pixel clock, not an independent measurement, and this sweep neither confirms nor
disputes it.

---

## What this says about the defect item 1 exists to fix

Fully derived from the measured 27.5 crossing plus the H40 line geometry; independent of any
emulator-internal constant.

The first colour word of the burst crosses the line-101 start at N = 27.5, so it lands
`10 × (27.5 − N)` cycles before that instant. Line 100 spans the 488.6 cycles before it, of
which the last 122.9 are blanking and the first 365.7 are the 320 visible pixels.

At the **shipped `SPIN_CRAM = 4`**, the burst's first write lands 235 cycles before the line
start — i.e. 253.6 cycles into line 100, at pixel **≈ 222 of 320**, mid-active-display. That
is the defect, quantified: a *leading* single-op CRAM at the shipped spin recolours from
roughly two-thirds across the row. R1 measured the same shape on the GUI oracle at x≈170
(reported as row 99 there rather than row 100); same order, ~50 px apart, and the row-index
difference is the one-row offset discussed under the anchors.

A second consequence: at **no** N in 0..27 does the burst land inside line **99**. The
earliest blanking a leading single-op CRAM authored at line 100 can reach is the blanking at
the end of line **100**, which is why every capture in this sweep puts the boundary at row
101. For this fire shape the authored line's own row is not reachable, and that is a property
of the handler's entry latency, not of the spin.

---

## §6b fault assignment

§6b's table is:

| Anchors capture as | Then the disagreement is |
|---|---|
| both CLEAN | the §3 arithmetic — Aeon's, re-derive it |
| either DIRTY | the instrument's raster timing or sampling point |
| both DIRTY | the fixture/harness |

**The evidence supports row 1, "both CLEAN → the §3 arithmetic", and it names the term.**
Both anchors captured CLEAN (once the R1 anchor was given the band shape its own §7.3 capture
had), with sharp full-row boundaries and no partial row. The disagreement with the prediction
is in §2's burst-duration term, and re-deriving it from the measured 30-cycle word cost
reconciles the two: slack 62.9 cycles, not 39.

Two caveats the controller should weigh before treating that as the last word, because §6b's
table pre-dates knowing what the instrument's resolution is:

* Row 1 presumes the anchors could have come out DIRTY. On an instrument that renders a row
  atomically at line start, a *partial* row — the DIRTY signature — is inexpressible. The
  anchors reading CLEAN is therefore weaker evidence than §6b assumes; it excludes a landing a
  whole line off, not a landing inside a row.
* The fixture/harness row is not fully excluded either: two fixture defects were found and
  fixed here (§ "Fixture defects"), and the spec's fixture as written is vacuous. Both are
  fixed with evidence, but the fact that §4's image did not express an answer is itself
  something §6b's table would have mis-attributed.

## For item 1c

* **Centre N = 18** for a leading single-op 3-word CRAM, from a window of [15.21, 21.5].
* The upper edge (21.5) is measured; the lower (15.21) rests on the 122.9-cycle blanking width
  and on the burst span being first-write-to-last-write (60 cycles, measured).
* **`RASTER_STREAM_WORD_CYC = 30` is confirmed against hardware** for the first time, from the
  within-group boundary spacing — 8 independent intervals, all 2-4, mean exactly 3.0 N.
* The window is 6.3 iterations wide, so a solver targeting the centre has ±3 iterations of
  margin — roughly 1.5× what §2's slack figure suggested.

## For oracle-next (this doubled as the acceptance fixture they asked for)

* **A1 passes**, and it is the criterion that matters most here. A3 (rows in one call), A4
  (rendered RGB, S/H applied) and A5 (320 active columns) all hold; bounds are refused, never
  clipped, as documented.
* **A2 needs restating.** As written it names one row and one pair of N, and it fails on a
  working instrument whose landing row is one off or whose quantum happens to contain both
  values. As "scan N, count distinct pictures; blind ⇒ exactly 1" it is a sharp, general
  poison and it passes. Recommend the latter form become the permanent acceptance test.
* **The gap that blocks this sweep's own purpose is Limitation L1**: `render_scanline` runs
  once per line at the line-start event, so a mid-line CRAM write is expressible only on the
  following line. Aeon's raster work needs *sub-line* landing resolution — a landing inside a
  row, i.e. the row rendered from the CRAM state as it evolves across the row. Until then this
  surface can measure a landing to ±1 scanline, which is enough to bracket a window from one
  side and not enough to close it.

## Reproducing

```bash
python3 tools/hblank_window_sweep.py --rom s4.debug.bin --lst s4.debug.lst
python3 tools/hblank_window_sweep.py --only map                    # the content-trap map
python3 tools/hblank_window_sweep.py --only map --mask 0x0002      # defect 1, reproduced
python3 tools/hblank_window_sweep.py --only a2,sweep --addr 0x4A --mask 0x0002
                                                                   # the spec fixture: BLOCKED
python3 tools/hblank_window_sweep.py --only sweep --lo 0 --hi 200 --rows 12
                                                                   # the four line boundaries
```
