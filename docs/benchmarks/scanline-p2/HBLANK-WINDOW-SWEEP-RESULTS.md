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
side rather than silently adopting either.

> **SUPERSEDED 2026-08-19 (same night, oracle-next ruling + contract pin):** this paragraph
> originally argued the one-row offset was "not an artifact of the instrument's row indexing".
> That framing is wrong as a dichotomy. oracle-next settled the convention *by construction*:
> a row is an atomic sample at that row's line-start (`system.rs` — the `Scanline` event for
> line N fires at exactly `N*MCLK_PER_LINE`), so a write landing during line N is first
> expressible in row N+1, **always** — their own suite gate asserts the boundary at
> authored+1. Pinned in the contract at empyrean main `112d683` (§6 blockquote); their
> addendum doc is oracle-next `docs/2026-08-19-aeon-acceptance-results.md` (`678ed96`).
> The GUI oracle differs because it renders per pixel clock (a mid-row write recolours the
> tail of THAT row) and, for HV-polled fixtures only, increments V ~15 px earlier. One
> residual stays open on their side: whether the two instruments' HInt anchor *phase* differs
> by a further ±1 line for HInt-dispatched fixtures — settleable by one fixture A/B-booted on
> both, offered by oracle-next as an optional follow-up, **not needed for 1c** (the spin
> arithmetic is relative to HInt entry, where the two instruments already agree within ~1
> spin iteration — §3's GUI-oracle-derived centre 17 vs this sweep's 18). It matters only
> when authored-line art alignment must be pinned to a row on hardware.
> The catalog deliberately does NOT pin the intra-line sampling point normatively, so a
> sub-line server showing a partial row on line N is a permitted difference.

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

---

## Re-run 2026-08-19 — substrate Tier-3 item 1 (the `-4(a2)` burst word)

The sweep above measured the pre-item-1 handler. Item 1 changed `.cram_loop`'s write from
`move.w (a1)+, VDP_DATA` (absolute long, 20 cycles) to `move.w (a1)+, -4(a2)` (a2 still holds
VDP_CTRL, so VDP_DATA is d16(An), 16 cycles), taking a CRAM burst word from 30 cycles to 26.
The same driver, the same fixture and the same flags were re-run against the changed ROM, and
this section is that run. **Nothing here was re-baselined**: the two runs are compared
boundary by boundary, and the value of the comparison is that only one of the two edges was
supposed to move.

```
python3 tools/hblank_window_sweep.py --rom s4.debug.bin --lst s4.debug.lst --only sweep \
        --lo 0 --hi 200 --rows 12
```

| | pre-item-1 | post-item-1 |
|---|---|---|
| boundaries at N | `22, 25, 28 · 71, 74, 77 · 119, 123, 126 · 169, 172, 174` | `23, 26, 28 · 72, 75, 77 · 120, 123, 126 · 170, 173, 174` |
| within-group step | `[3,3,3,3,4,3,3,2]` -> **30.0 cyc/word** (8 intervals) | `[3,2,3,2,3,3,3,1]` -> **25.0 cyc/word** (8 intervals) |
| between-group step | 490.0 cyc/sampling period (line 488.6, ratio 1.0029) | 490.0 cyc/sampling period (identical - the instrument did not move) |
| burst span, first write -> last | 60 cyc | 50 cyc |
| first word's crossing N | 27.5 MEASURED | 27.5 MEASURED |
| upper edge N (last word) | 21.5 MEASURED | 22.5 MEASURED |
| lower edge N | 15.21 DERIVED | 15.21 DERIVED |
| clean N | 16..21, **CENTRE 18** | 16..22, **CENTRE 19** |

### What the boundary-by-boundary delta says

```
old  [22, 25, 28 | 71, 74, 77 | 119, 123, 126 | 169, 172, 174]
new  [23, 26, 28 | 72, 75, 77 | 120, 123, 126 | 170, 173, 174]
d      +1  +1   0 | +1  +1   0 |  +1    0    0 |  +1   +1    0
```

* **The group's LAST boundary did not move in any of the four groups** - 28, 77, 126, 174,
  identical. That boundary is the FIRST burst word crossing the sampling instant, and its
  arrival is fetch + dispatch + pre-burst + spin. Item 1 touched none of those, so the burst
  does not start later, and this is the control that says the change stayed inside the loop.
* **The group's FIRST boundary moved +1 N in all four groups** - that is the LAST word, and
  the burst now ends sooner. Two words at 26 rather than 30 is 8 cycles; the instrument
  resolves 10 cycles per N, so +1 is what an 8-cycle narrowing looks like.
* The middle word moved +1 in three groups of four, which is what a 0.4 N shift looks like
  through an integer-N instrument whose sampling period (48.86 N) drifts against the grid.

### Why the summary statistic reads 25.0 against a derived 26.0

A boundary is localized to +-0.5 N = +-5 cycles, so a two-interval span reads +-10 cycles.
The pre-item-1 run read exactly 30.0 because 3.0 N is a whole number of `dbf` iterations;
2.6 N is not, so the new spacing aliases into steps of 3, 2 and 1 that average low. The
constant is a cycle table and not a fit - MOVE.W with source `(An)+` and destination `d16(An)`
is 16 cycles, `dbf` taken is 10, and no reading of the table produces 25. What the instrument
can and does discriminate is the direction and the rough size, and both are right.

The region and restore burst loops keep the 30-cycle word (their a2 is a source cursor, so
their write has no base register and stays the absolute long form). They are not swept here;
they are pinned as the untouched controls F4 and F8 in `raster_dsl.emp`'s fixture block.

### For a future `RASTER_CRAM_MAX` parcel

The measured clean band is now **[15.21, 22.5]**, i.e. 7.3 iterations wide where it was 6.3.
That extra iteration is the 8 cycles a 3-word CRAM burst stopped spending. A 4-word CRAM
burst would span `3 x 26 = 78` cycles against the 122.9-cycle window, leaving 44.9 for both
margins where the guard wants 30 - so four words is arithmetically placeable for the CRAM
class and NOT for the deep class (`3 x 30 = 90`, leaving 32.9). See `docs/DEFERRED_WORK.md`.

## Re-run 2026-08-19 — substrate Tier-3 item 2 (the zero pre-test)

Item 2 hoisted the OP_SET_REG test out of the compare chain and onto the flag the op fetch
already sets: OP_SET_REG is opcode 0, `move.w (a1)+, d1` sets Z from the word it moved, so
`.op_loop` now decides it with a single `beq.s .op_reg` ahead of the chain. A register write's
dispatch drops from 80 cycles (five failed rungs — it was the fall-through) to 10 (one taken
branch), and **every non-zero op pays 8 cycles** for the same branch not taken.

The swept fixture is a LEADING single-op 3-word CRAM. It carries no register write, so item 2
does exactly one thing to it: **+8 cycles in front of its rung**. Same driver, same fixture,
same flags. Nothing was re-baselined.

```
python3 tools/hblank_window_sweep.py --rom s4.debug.bin --lst s4.debug.lst --only sweep \
        --lo 0 --hi 200 --rows 12
```

### THE PREDICTION, STATED BEFORE THE RUN

The path from the op-walk origin to the burst grew by 8 cycles, and the instrument resolves
10 cycles per N. To place the same write at the same hardware instant the spin must be
`8/10 = 0.8` iterations SHORTER, so **every boundary slides DOWN by 0.8 N** and the band keeps
its width (the width is set by the burst span and the H40 blanking, neither of which item 2
touches). A reported boundary is an integer localized to ±0.5, so each one should read either
−1 or 0, with about four in five reading −1.

| | post-item-1 | predicted (item 2) | measured (item 2) |
|---|---|---|---|
| boundaries at N | `23, 26, 28 · 72, 75, 77 · 120, 123, 126 · 170, 173, 174` | `22.2, 25.2, 27.2 · 71.2, 74.2, 76.2 · 119.2, 122.2, 125.2 · 169.2, 172.2, 173.2` | `22, 25, 28 · 71, 74, 76 · 119, 122, 125 · 169, 172, 174` |
| within-group step | `[3,2,3,2,3,3,3,1]` -> 25.0 cyc/word | unchanged (span untouched) | `[3,3,3,2,3,3,3,2]` -> **27.5 cyc/word** |
| between-group step | 490.0 cyc/sampling period | unchanged | 490.0 cyc/sampling period (identical — the instrument did not move) |
| burst span, first -> last | 50 cyc | unchanged | 60 cyc as reported by the driver's boundary arithmetic |
| upper edge N (last word) | 22.5 MEASURED | 21.7 | **21.5 MEASURED** |
| lower edge N | 15.21 DERIVED | 14.41 | 15.21 DERIVED |
| clean N | 16..22, CENTRE 19 | 15..21, centre 18 | 16..21, **CENTRE 18** |

### Predicted vs measured, boundary by boundary

```
post-item-1  [23, 26, 28 | 72, 75, 77 | 120, 123, 126 | 170, 173, 174]
predicted    [22, 25, 27 | 71, 74, 76 | 119, 122, 125 | 169, 172, 173]   (each -0.8, rounded)
measured     [22, 25, 28 | 71, 74, 76 | 119, 122, 125 | 169, 172, 174]
d(measured)   -1  -1   0 | -1  -1  -1 |  -1   -1   -1 |  -1   -1    0
agree with
prediction    Y   Y    N | Y   Y   Y  |  Y    Y    Y  |  Y    Y    N
```

**Ten of twelve boundaries moved exactly the predicted −1; the other two held.** Both
exceptions are a group's LAST boundary, the one nearest the +0.5 side of its localization
window, which is precisely where a true shift of 0.8 rounds to 0. The mean measured shift is
`(10 x -1 + 2 x 0) / 12 = -0.833 N` against the predicted `-0.800` — a disagreement of 0.033 N
= **0.33 cycles**, which is a fortieth of what this instrument can resolve.

There is no term available to make it anything other than −0.8: a not-taken `beq.s` on a 68000
is 8 cycles, and `dbf` taken is 10.

### The one number that is not a comparison

The driver, given no expectation, printed its own headline:

```
=> clean N in [15.21, 21.5]  = integers 16..21   CENTRE N = 18
```

`raster_dsl.emp`'s solver, deriving from the constants alone, gives the swept shape a spin of
**18**. That agreement is PIN 2, and it is the check that the model's dispatch decomposition
is right and not merely self-consistent: the solver has never seen a boundary.

### Why the summary statistic moved 25.0 -> 27.5 when nothing narrowed the burst

Same aliasing as the item-1 section explains in the other direction. The within-group step is
eight two-boundary intervals each localized to ±0.5 N, and the underlying spacing (2.6 N per
word) is not a whole number of iterations, so which side of the grid each boundary falls on
changes when the whole pattern slides 0.8. The burst span did not change — item 2 does not
touch `.cram_loop` — and the derived word cost is still the cycle table's 26.

### What is NOT swept, and is pinned instead

The register write itself. It carries no burst, so this instrument has nothing to see; its
70-cycle drop is measured on hardware by the cost probe as fixture **F1, 3044 -> 2624 cycles
over six fires** (`tools/effects_gates.py`, cost_model gate, exit 0 with 18/18).

## Run 2026-08-19 — the 4-word CRAM burst (the `RASTER_CRAM_MAX` raise)

Everything above sweeps the burst width the constructors admit. This run sweeps a width they
do **not**, because that is the only way to answer whether they should: `RASTER_CRAM_MAX = 3`
was never a hardware limit, it was Ruling 2a's pre-measurement estimate of "~60 usable
cycles", and the window this document measured at 122.9 is twice that. The proposal in
`docs/DEFERRED_WORK.md` came with arithmetic and an explicit instruction not to raise the
ceiling on the strength of it. This is the fixture that arithmetic asked for.

`--words N` authors the burst directly in wire. The DSL constructors' `ensure` refuses more
than the ceiling, and this driver never calls them — it pokes the program image, exactly as
it already pokes a spin the lowering would never solve.

```bash
python3 tools/hblank_window_sweep.py --rom s4.debug.bin --lst s4.debug.lst --only sweep \
        --lo 0 --hi 200 --rows 12 --words 3     # the control, same ROM, same session
python3 tools/hblank_window_sweep.py ... --words 4    # the subject
python3 tools/hblank_window_sweep.py ... --words 5    # the refusal, measured
```

### The three runs, side by side

All three are the same ROM (`s4.debug.bin`, crc 72ab53aa), the same fixture at `$50` on line
100, the same session. Only the burst width differs.

| | 3 words (control) | **4 words** | 5 words |
|---|---|---|---|
| boundaries at N | `22,25,27 · 70,73,76 · 120,123,125 · 169,171,174` | `19,22,25,28 · 68,71,74,76 · 118,120,122,125 · 166,169,172,173` | `17,20,23,24,27 · 66,68,71,74,77 · 115,117,120,122,125 · 164,166,168,171,174` |
| boundaries per group | 3 | **4** | 5 |
| within-group step | 26.25 cyc/word | **25.83 cyc/word** | 25.62 cyc/word |
| between-group step | 490.0 cyc | 490.0 cyc | 490.0 cyc |
| folded first-word crossing | 26.50 N | **26.50 N** | 26.75 N |
| folded burst span | 52.5 cyc (derived 2x26 = 52) | **77.5 cyc (derived 3x26 = 78)** | 102.5 cyc (derived 4x26 = 104) |
| clean band, folded | N in [14.21, 21.25] | **N in [14.21, 18.75]** | N in [14.46, 16.50] |
| band width | 7.04 N | **4.54 N** | 2.04 N |
| solver's spin for the fixture | 18 | **17** | 15 |
| band that satisfies both margins | [16.21, 20.25] | **[16.21, 17.75]** | [16.46, **15.50**] — EMPTY |
| slack at the landing | 17.9 early / 22.5 late | **7.9 early / 7.5 late** | -14.6 early / 5.0 late |
| verdict | GO | **GO** | **NO-GO** |

### The control is the whole argument

The number that decides this is not the 4-word band; it is that **the first word's crossing
did not move**. A wider burst must not start later — if it did, the extra span would be
partly an artifact of the fixture rather than of the burst, and every comparison in the table
would be measuring two things at once. Folded over four sampling periods the crossing reads
**26.50 N at three words and 26.50 N at four**, identical, which is the same control the
item-1 re-run used (there it was the group's last boundary holding at 28/77/126/174).

With the start pinned, the band's narrowing is entirely the burst's end moving earlier, and
it moves by the amount the cycle table says: the span grows 52.5 -> 77.5 -> 102.5 as the width
grows 3 -> 4 -> 5, against a derived 52 / 78 / 104. Three independent measurements of
`RASTER_STREAM_WORD_CRAM_CYC = 26`, each inside a cycle and a half of the table.

### Why the folded window, and why the single-group headline is not enough here

The headline block every earlier section quotes derives BOTH edges from one integer — group
0's last boundary, less a half. A boundary is the ceiling of a crossing, so that correction is
right on average and off by up to ±0.5 N on any single reading. Five cycles of whole-band
shift is fine for "the centre is 18" and is not fine for a go/no-go on margins of 10 and 20:
the 4-word run's own single-group block reads `[15.21, 18.5]` because its group 0 happened to
round the crossing up to 27.5, and against those edges the solver's N=17 would appear to miss
the early margin by 2.1 cycles.

The driver now also folds. The same crossing is observed once per sampling period, each with
an independent rounding; subtracting the measured period puts them on one estimate:

```
   4 words: per-group crossing 27.50, 26.50, 26.50, 25.50  ->  mean 26.50 N
   3 words: per-group crossing 26.50, 26.50, 26.50, 26.50  ->  mean 26.50 N
```

That is the same arithmetic the item-2 section does by hand when it averages twelve boundary
deltas to −0.833, and it is what makes the two runs comparable at better than half an N. The
single-group block is left printing exactly what it printed before; nothing earlier in this
document is restated.

### The 5-word row is a measured refusal, not an extrapolation

The proposal's table said 5 words is refused on arithmetic — 4 x 26 = 104 against 122.9,
leaving 18.9 for margins that want 30. The instrument says the same thing from the other
side, and more sharply than the arithmetic does: the band that satisfies both margins comes
out **empty**, its lower bound 16.46 above its upper bound 15.50. There is no spin at which a
5-word cram burst is both inside blanking and clear of the sampling instant, and the driver's
own `solver fit` block prints NO-GO without being told what to expect.

`games/sonic4/test/poison/poison_cram_five_words.emp` is the build-time half of the same
fact, and `poison_deep_four_words.emp` the half that keeps the SPLIT honest — a 4-word
*region* burst, which passes the placeability ensure by 2.9 cycles and then fails
`check_landings` because the solver quantizes to whole 10-cycle iterations.

### What was NOT measured, and is therefore not raised

The deep class (`OP_PAL_REGION`, `OP_PAL_RESTORE`). Its burst word is 30 cycles, so a 4-word
deep burst spans 90 and leaves 32.9 for margins wanting 30 — a 2.9-cycle slack, against an
instrument that localizes a boundary to ±5 cycles. **A fixture could not tell that margin from
zero**, so `RASTER_BURST_MAX_DEEP` stays at 3. This is the parcel declining a raise its own
arithmetic nominally permits, and the reason is the standard of evidence rather than the sign
of the number.

## Re-run 2026-08-19 (post-SR) — the 4-word fixture at the moved window phase

The three runs above were taken at `RASTER_HBLANK_END_CYC = 351`. Tier-3 item 6 (the SR round
trip) then moved the anchor to **371**, which shifts every solved spin by +2 and every measured
boundary with it. The whole fixture was re-measured against the post-SR ROM — one pass at the
final base, not a patch to the earlier numbers — and the re-run changed the instrument as well
as the reading.

### The estimator changed, and it had to

The fold introduced above subtracted `measured_cycles_per_sampling_period`, which is the period
measured on the group **first** boundaries — a different statistic from the crossings being
folded. Post-SR the two disagree: the 3-word run read 486.7 there against 490.0 in the 4- and
5-word runs, and subtracting a period that is 0.33 N wrong accumulates a full N of error by the
fourth group. That is what made two runs disagree about a crossing they should measure
identically (28.25 against 28.00).

The fold is now a **least-squares line through (group index, crossing)**, which estimates the
intercept and the period together from one set of observations and reports its own residuals.
The fitted periods come out 48.90 / 48.80 / 48.90 N against the H40 NTSC arithmetic 48.86 —
0.1% — which is the fit validating itself on a quantity it was not aimed at.

### The three widths, post-SR

| | 3 words (control) | **4 words** | 5 words |
|---|---|---|---|
| crossing (intercept) | 27.90 N | **28.30 N** | 28.40 N |
| fitted period | 48.90 N | 48.80 N | 48.90 N |
| residual spread -> s.e. | 1.10 N -> 2.7 cyc | 1.20 N -> **3.0 cyc** | 1.10 N -> 2.8 cyc |
| burst span | 50.0 cyc (derived 52) | **80.0 cyc (derived 78)** | 105.0 cyc (derived 104) |
| clean band | [15.61, 22.90] | **[16.01, 20.30]** | [16.11, 17.90] |
| solver's spin | 20 | **19** | 17 |
| early slack | +23.9 cyc | **+9.9 cyc** | -11.1 cyc |
| late slack | +19.0 cyc | **+3.0 cyc** | -1.0 cyc |
| verdict | GO | **GO** | **NO-GO** |

The controls all still hold: the crossing does not move with width (27.90 / 28.30 / 28.40, a
0.5 N spread against per-run s.e. of ~0.3), the spans track the 26-cycle word, and 5 words is
refused with an empty band exactly as the arithmetic says.

### THE FINDING: the late margin shrank, and not because of the burst

The 4-word fixture cleared the late margin by **7.5 cycles pre-SR and 3.0 cycles post-SR**.
Nothing about the burst changed — the span is still `3 x 26 = 78` and the window is still
122.9 — so the difference is entirely in where the sampling instant is believed to be.

Pooling all twelve groups across the three post-SR widths puts the crossing at **28.20 N**
(period 48.87, max residual 0.70 N, s.e. ~0.2 N). The model's implied crossing is
`(371 - 84) / 10 = 28.7 N`. That is a **5-cycle disagreement, about 3 s.e.** — and it did not
exist at the previous phase, where the measured 26.50 sat against an implied 26.7.

So one of two things is true, and this instrument cannot say which:

* `RASTER_HBLANK_END_CYC = 371` is ~5 cycles high — plausible if it was re-derived from a
  single group's boundary, which carries exactly the +-0.5 N bias the fold removes; or
* the pre-burst path is ~5 cycles longer than the model's `8 + 26 + 36`.

Either way the consequence is the same: **the arithmetic supports a 4-word cram ceiling with
14.9 cycles of slack, and the measurement supports it by one standard error.** That is thinner
than the evidence this parcel refused the DEEP class on (2.9 cycles, "smaller than the
instrument that would have to confirm it"), and the two positions are only consistent if the
anchor disagreement is resolved first.

**Recommended before this ceiling is trusted:** re-derive `RASTER_HBLANK_END_CYC` with the
least-squares fold rather than a single boundary. If it lands near 366, model and measurement
agree, every solved spin moves by at most one iteration, and the 4-word late margin reads the
same in both.

## Re-derivation 2026-08-19 — the anchor was wrong, and this sweep is why

The section above flagged a 5-cycle disagreement between the measured crossing and
`RASTER_HBLANK_END_CYC = 371`. It has a cause, and the cause is this document's own
estimator bug echoing backwards.

**How 371 was reached.** Item 6 had two lines of evidence. The first — every edge boundary
moving +2 — is a *delta* on individual integer boundaries and is sound as far as it goes. The
second is that the driver's derived clean band moved to "CENTRE N = 20", and that "371 is the
only value that reproduces the 20". **That centre came out of the buggy fold** — the one that
estimated the sampling period from the group FIRST boundaries and subtracted it from the group
LAST boundaries. So the constant was validated against a number the instrument was computing
wrongly, and PIN 2 then locked it in: the pin passed at 371 precisely *because* both sides
shared the error.

**The re-derivation.** Pooled least squares over **12 independent groups** (three burst widths
x four sampling periods). A repeat of all three runs returned byte-identical boundary lists, so
the repeats are reproducibility evidence and **not** extra samples — 12, not 24:

```
   crossing N_fw = 28.200 N     period = 48.867 N   (H40 NTSC arithmetic 48.857)
   residual spread 1.40 N = 14.0 cyc  ->  s.e. on the intercept 0.202 N = 2.0 cyc

   RASTER_HBLANK_END_CYC = 70 + 14 + 10 * 28.200 = 366.0
```

**And the delta agrees, which makes this a correction rather than a rival claim.** The same
pooled fold on the pre-SR ROM puts the crossing at 26.50 N, i.e. END = 349. Item 6's real cost
is therefore **+1.70 N = +17 cycles**, and `349 + 17 = 366`. Item 6's own reading was "+2
everywhere" because that method reads integer deltas off individual boundaries and *cannot
express 1.7* — it rounds to 2 by construction. The two measurements never disagreed; one could
only answer in whole numbers.

**PIN 2 is satisfied at 366 and was not at 371.** With the corrected fold the driver's headline
centre for the swept 3-word shape is 19, and 366 is what makes the solver say 19.

Provenance: **351** (1b, single shape, single-group boundary) -> **371** (item 6, single-group
boundary + a mis-folded centre) -> **366** (pooled least squares, 12 groups, period fitted from
the crossings' own spacing and cross-checked against H40 arithmetic).

### What the re-derived anchor does to the 4-word question — it settles it as NO

At 366 the solver's answer for each width, and where that lands it:

| width | solved spin | early slack | late slack |
|---|---|---|---|
| 3 | 19 | **+10.9 cyc** | +30.0 cyc |
| 4 | 18 | **+0.9 cyc** | +14.0 cyc |
| 5 | 17 | -9.1 cyc | -2.0 cyc |

The binding edge flipped. At 371 the late side was tight; at 366 it is the **early** side, and
a 4-word cram burst clears it by **0.9 cycles** against a pooled standard error of **2.0**.

The decision rule was fixed before the number was known: the raise stands only if the binding
margin clears both two standard errors (4.0 cyc) and the 2.9-cycle threshold the DEEP class was
refused on. **0.9 clears neither, so `RASTER_BURST_MAX_CRAM` stays at 3.** The arithmetic still
says 4 fits with 14.9 cycles to spare — and that is exactly the trap: a fit check asks whether
the span *fits*, not where the solver's rounding *puts* it. Necessary, not sufficient.

Everything else this parcel built stands: the three-way constant split, the two poisons, the
5-word refusal, and the estimator fix. The raise is a one-token change whenever a wider window,
a cheaper pre-burst path, or an instrument that can see the early edge arrives.

---

# THE SUB-LINE ERA — 2026-08-19 evening, `bench/sweep-subline-mode`

> **Everything above this line was measured on a LINE-ATOMIC instrument and is not revised
> here.** oracle-next shipped F-SCANLINE-SUBLINE (their `87c8e99` / `ff9e784`; empyrean
> contract §11.15, CR-25) between that work and this, and the surface now resolves a CRAM
> landing to a PIXEL rather than to a scanline. The numbers above remain the correct readings
> of the instrument that produced them; the numbers below are a different instrument's
> readings of the same hardware, and where the two speak to the same quantity the agreement is
> reported as evidence rather than folded in. No historical figure in this document has been
> edited.
>
> The last section above closed with: *"The raise is a one-token change whenever a wider
> window, a cheaper pre-burst path, or **an instrument that can see the early edge** arrives."*
> It arrived. It says no.

| | |
|---|---|
| ROM | `s4.debug.bin`, 713,863 bytes, crc32 `06af0010`, mtime 2026-08-19 19:23 (master `5874ac33`), copied into the worktree so a parallel lane's rebuild could not move it mid-session |
| Listing | `s4.debug.lst`, same build |
| Server | `/home/volence/sonic_hacks/oracle-next/target/release/oracle-aether`, mtime 2026-08-19 14:14; oracle-next HEAD `0b699cb`, with `ff9e784` and `87c8e99` both verified ancestors |
| Driver | `tools/hblank_window_sweep.py` at `362c553c`, sub-line mode |
| Session | 2026-08-19 19:27-19:52 local; `uptime` at the first run `19:27:42 up 1 day, 19:51`, at the last `19:51:25 up 1 day, 20:15` |
| Load | 1-minute load average ranged 1.8-6.4 across the session — a second lane was building on the same box. Every timing below is wall clock with its own `uptime` beside it, and none of the measurements is timing-derived (the emulator is driven by frame counts, which is why the determinism control below passes under that load) |
| Per-run wall clock | wide sweep (N 0..200, 12 rows) 74.2 s · anchors 5.7 s · A1+A2 9.2 s · narrow sweep (0..30, 6 rows) 11.9 s |

**Every capture in this session asserted `source == "raster"` and none failed it.** `mode` was
`h40` throughout; `caveat` never appeared. Every run exited 0.

---

## 1. The instrument changed, and the sweep can tell without being told

`summarize` now detects the row convention from the data and dispatches. The test is the one
bit of picture the two conventions cannot both produce: **does the landing pixel move with the
spin?**

```
== instrument mode: SUB-LINE
   flipX takes 115 distinct values over 201 captures (0..319) -- the landing pixel is a
   function of the spin, so the row splits where the write lands
```

Against the same driver's reading in the atomic era — `flipX` the constant `{0}` across all
201 captures. The line-atomic path is **kept whole** (`atomic_summarize`) because it is still
the correct reading for oracle classic and for any conformant line-atomic server; what changed
is that it is no longer the only one, and it is no longer reached on this server.

**Why the old path had to stop being reached, measured rather than asserted.** Run on the
sub-line server it reads the split rows as one group of ~170 "boundaries", derives a
1990-cycle burst span, and prints `clean N in [187.21, 0.50] -> NO-GO` with a −1702-cycle
early slack. Reproduced twice, byte-identical, before any of this was built.

### The acceptance-run prediction, confirmed

oracle-next predicted `flipX ≈ 222` on this row-100 fixture at the shipped spin, bounded to
roughly [205, 225] by the instruction-granularity limit, with `0` or `319` falsifying the
model. Measured here at spin 4: **`flipX` = 219**, row 100. Their model stands.

---

## 2. The controls, all of them, before any number is used

| Control | Result |
|---|---|
| **A1 determinism (spec §8)** | **PASS.** Three fresh `oracle-aether` processes, N=17, byte-identical rows (digest length 11,546, frame 185 in all three) |
| **A1-style determinism on the WHOLE sweep** | **PASS.** Two independent server processes, 201 captures each at `--words 1`: observation streams byte-identical, **0 differing N**. Every derived quantity identical to six decimals — slope 8.740102, period 48.851490, width 122.386438, both edges, and the re-derived anchor 366.6697 |
| **A2 liveness, spec's literal form** | **PASS — and it FAILED before the amendment.** N=0 vs N=17 now differ on **106 columns of row 100, x 179..319**, and on zero columns of every other row. That is the split row itself; the pre-amendment reading was 0 differing columns everywhere (§ "A2 — liveness" above) |
| **A2 restated (distinct pictures)** | **PASS. 19 distinct pictures over N ∈ 0..57 step 3**, against **4** measured before the change. Only one collision in twenty (N=18 and N=21) |
| **`source == "raster"`** | Asserted on every capture of every run; never fired |
| **Self-diff control on the cross-run comparison** | `w1` vs itself **0** differing N; `w1` vs `w4` **57** differing N. The comparison can both see a difference and report none |
| **Program-survival readback** | Unchanged mechanism, checked on every capture; never fired |

The determinism result is what licenses everything else, and it is worth being precise about
what it covers: not three captures, but **402 captures across two processes**, every one of
which had to agree with its twin for the fit below to be attributable to N.

### The anchors, re-run under the new mode — all five unchanged

Each is printed in **both** conventions now, because an anchor's job is to calibrate the edge
row and the amendment explicitly kept that (*"the first WHOLLY recoloured row is still N+1"*).

| Anchor | first new pixel | atomic @ authored / +1 | sub-line @ authored / +1 |
|---|---|---|---|
| `reg_set($8C89) + stream_cram($4A,[$000E])` @ 120 | row 121, x=2 | TOO LATE / **CLEAN** | TOO LATE / **CLEAN** |
| same at `$50` | row 121, x=0 | TOO LATE / **CLEAN** | TOO LATE / **CLEAN** |
| `pal_restore($48,3)` @ 140, lone | none | VACUOUS / VACUOUS | VACUOUS / VACUOUS |
| `stream_cram($48,tint)`@100 + `pal_restore($48,3)`@140 | row 141, x=46 | TOO LATE / **CLEAN** | TOO LATE / **CLEAN** |
| same at `$50` | row 141, x=0 | TOO LATE / **CLEAN** | TOO LATE / **CLEAN** |

**Identical to the atomic-era table above, first-new-pixel columns included** (x=2 and x=46
reproduce exactly). These anchors carry solved spins, so their bursts land in blanking and no
split is expected — and none appears. The edge row survives the instrument change, which is
what lets every classification in this document stay comparable across it.

---

## 3. Measure the window at ONE word — the fixture the new mode needs

Every sensitive column samples **exactly one** of the written entries (`neither` is 0 at every
N in every run, which is that claim measured rather than assumed). So on a multi-word burst
`flipX` is the first column sampling the **first** entry, and the bracket that debiases it
cannot be taken over the whole sensitive set. Width and period survive that — a constant
offset cancels out of both — but the **absolute edges do not**, and the absolute edges are
what the ceiling question needs.

Measured drift, across the four widths run in this session: the recovered early edge slides
16.028 → 15.949 → 15.897 → 15.869 N as the burst widens 1 → 3 → 4 → 5, i.e. **downward, by
1.6 cycles over four words**, exactly the direction an upward-biased `flipX` predicts. The
width does not move with it (below). `--words 1` is therefore the window fixture, and the
wider runs are cross-checks.

### The fit

`--words 1`, N = 0..200, 12 rows read. One straight line per row, **slope and period fitted
together**, covariance propagated to every reported quantity. Neither H40 constant is an input
anywhere in the estimator, which is what makes their agreement below evidence rather than
tautology.

```
149 bracketed landings across 5 rows
   row 100: 16 pts, x 186..314      row 103: 35 pts, x   8..302
   row 101: 36 pts, x  11..318      row 104: 26 pts, x   8..219
   row 102: 36 pts, x   9..319
residual rms 3.17 px, max |r| 6.6 px      (the art's own column spacing is the floor)
```

| Quantity | Fitted | Arithmetic | Agreement |
|---|---|---|---|
| pixel clock | **0.8740 ± 0.0027 px/cyc** | 0.8750 (8 mclk/px ÷ 7 mclk/cyc) | 0.4 s.e. |
| sampling period | **488.51 ± 0.25 cyc** | 488.57 (3420/7) | 0.2 s.e. |
| active span | **366.13 cyc** | 365.71 (2560/7) | +0.42 cyc |
| **blanking width** | **122.39 ± 1.07 cyc** | 122.86 (860/7) | **−0.47 cyc = 0.44 s.e.** |

**The 122.9 this whole document has leaned on is now MEASURED, and it holds.** It has been an
arithmetic value in every earlier section — the derived lower edge, the placeability ensures,
`RASTER_HBLANK_WIDTH_X10` — and until this instrument nothing could check it. It survives at
under half a standard error. That is a confirmation and it is reported as one; had it
disagreed, the disagreement would have been the finding and no constant would have moved on
the strength of it.

### Both edges, for the first time

```
EARLY edge  N = 16.028 ± 0.070   (0.70 cyc)   the first write leaves row 100's active display
LATE  edge  N = 28.267 ± 0.076   (0.76 cyc)   the write reaches row 101's active display
```

The early edge is the point of the parcel. Every previous reading of it in this document is
labelled `DERIVED` and carries the standing caveat *"the start of blanking is not a sampling
instant, so nothing in the picture changes when the burst crosses it."* On a sub-line server
something does: the landing pixel walks off the right edge of the active window. The
asymmetric guard margins (early 20, late 10) were built around that asymmetry of evidence; the
asymmetry no longer exists.

### The plateau control — and where it goes blind

A plateau is the run of spins for which the edge row came back **wholly** recoloured, i.e. the
whole burst landed in blanking. It needs no fit and no bracket, which makes it a control
rather than a second version of the fit. The fit predicts both of its ends.

| words | plateaus (N) | predicted end | observed end (folded) | verdict on the control |
|---|---|---|---|---|
| 1 | 16-28, 65-77, 114-126, 162-174 | floor(28.27 − 0.00) = 28 | 27.97 | **−0.03 N — holds** |
| 3 | 16-23, 65-73, 115-121, 163-169 | floor(28.25 − 5.20) = 23 | 23.26 | **+0.26 N — holds** |
| 4 | 16-23, 65-74, 114-120, 163-170 | floor(28.14 − 7.80) = 20 | 23.48 | **+3.48 N — VACUOUS** |
| 5 | 16-23, 65-67, 114-116, 163-165 | floor(28.19 − 10.40) = 17 | 19.46 | **+2.46 N — VACUOUS** |

**The last two rows are §4's content trap, one entry further along than §4 looks, and the tool
now names it rather than leaving a reader to notice.** `flipX` is measured at the burst's
FIRST entry, which the content map chose for being the best-sampled address on these rows; the
LAST entry gets no such guarantee. Adding a fourth and a fifth word adds only **+2 observable
columns each** to row 101 (302 and 304, against 300 at three words), so a trailing word
landing a few pixels into active changes nothing any column can report and the plateau does
not shrink. A reader comparing plateaus across widths would conclude the burst span had
stopped growing at three words. It has not — the instrument stopped watching.

Nothing downstream consumes a plateau. The window's edges come from the first word's march and
the burst span from the cycle table, which three independent runs in the section above already
confirmed to within a cycle and a half.

The plateau **start** is a different matter and is explained rather than flagged: it runs
early by however much of the previous row the art leaves unobservable at its right end. Row
100's last sensitive column at one word is 314, so its last **5 px = 0.57 N** are blind and a
landing there reads as though blanking had already begun. Predicted start `ceil(16.03) = 17`,
observed 15.97 — the 0.6 N gap is that blind tail, measured independently.

---

## 4. `RASTER_HBLANK_END_CYC`, re-derived from a measured edge

The conversion is the model's own decomposition, every term read out of `raster_dsl.emp` by
the driver rather than transcribed into it:

```
prologue = OP_FETCH(8) + DISPATCH_ZERO_MISS(8) + RUNG(16)*DEPTH_CRAM(0) + HIT(18) + PRE_CRAM(36) = 70
END      = 70 + spin_cyc(0)=14 + 10 * 28.267  =  366.67 ± 0.76 cyc
OPEN     = 70 + 14             + 10 * 16.028  =  244.28 ± 0.70 cyc
```

| | measured | shipped / modelled | disagreement |
|---|---|---|---|
| window close (`RASTER_HBLANK_END_CYC`) | **366.67 ± 0.76** | **366** | +0.67 cyc = **0.88 s.e.** |
| window open | **244.28 ± 0.70** | 243.1 (= 366 − 122.9) | +1.18 cyc |

**The shipped 366 is confirmed, and the confirmation is worth more than the agreement.** 366
was reached in the atomic era by pooled least squares over twelve boundary groups, on an
instrument that could only watch the late edge — itself a correction to the 371 that a
single-group boundary plus a mis-folded centre had produced. A direct measurement of that same
edge now lands 0.67 cycles away from it. The provenance chain **351 → 371 → 366** closes here
at **366.7 measured**, and the 371 that PIN 2 once passed at is settled as ~4.3 cycles high.

**No stop-and-report.** The parcel's stop condition was the anchor moving outside a guard
margin, which would mean every shipped spin is mis-centred against the better instrument. The
tighter margin is the late one at 10 cycles; the anchor is off by 0.67. **Nothing shipped is
mis-placed, and no constant in this parcel was touched.**

### Four independent runs agree about the anchor

Each width is a separate 201-capture sweep and re-derives the anchor on its own:

| | 1 word | 3 words | 4 words | 5 words |
|---|---|---|---|---|
| blanking width (cyc) | 122.39 ± 1.07 | 122.96 ± 1.31 | 122.46 ± 1.23 | 123.18 ± 1.21 |
| early edge (N) | 16.028 ± 0.070 | 15.949 ± 0.088 | 15.897 ± 0.082 | 15.869 ± 0.080 |
| late edge (N) | 28.267 ± 0.076 | 28.245 ± 0.095 | 28.142 ± 0.088 | 28.187 ± 0.086 |
| **re-derived END** | **366.67** | **366.45** | **365.42** | **365.87** |

Mean 366.10, total spread 1.25 cycles across four runs — smaller than one run's own standard
error. The width is stable across widths (spread 0.79 cyc) exactly as the estimator's design
predicts, because a constant sampling bias cancels out of a difference of two edges; the
absolute edges drift by ~1.6 cycles, exactly as the bracket caveat predicts. **Both halves of
the design reasoning are visible in the data.**

---

## 5. THE PARKED 4-WORD QUESTION, re-asked against the measured window

The decision rule is the one fixed before any of these numbers were known, restated without
softening: **the binding margin must clear BOTH two standard errors AND the 2.9-cycle
threshold the DEEP class was refused on.**

From the `--words 1` window, N ∈ [16.028, 28.267], cram word 26 cyc, margins early 20 / late
10 — all read out of the sources by the driver rather than typed into it:

| words | solved spin | early slack | late slack | **binding** | 2 s.e. | verdict |
|---|---|---|---|---|---|---|
| 1 | 22 | +39.72 | +52.67 | +39.72 | 1.41 | GO |
| 2 | 21 | +29.72 | +36.67 | +29.72 | 1.41 | GO |
| **3** | 19 | +9.72 | +30.67 | **+9.72** | 1.41 | **GO** — the shipped ceiling |
| **4** | 18 | **−0.28** | +14.67 | **−0.28** | 1.41 | **NO-GO** — the parked question |
| 5 | 17 | −10.28 | −1.33 | −10.28 | 1.41 | NO-GO |

### RECOMMENDATION: `RASTER_BURST_MAX_CRAM` HOLDS AT 3

**The verdict is unchanged and the evidence for it is now first-class.** The atomic-era
refusal read **+0.9 cycles of early slack against a 2-s.e. bar of 4.0** — a positive margin
too small to trust, on an edge that was *derived* and an error bar that came from quantizing a
crossing at the *other* edge. The direct measurement reads **−0.28 cycles against a bar of
1.41**: the error bar shrank 2.8×, and the margin it was measuring turned out not to be
positive at all.

The binding edge is the **early** one, and it is now the measured one. Repeated across all
four runs the 4-word binding margin reads **−0.28 / +0.51 / +1.03 / +1.31** cycles against
2-s.e. bars of **1.41 / 1.76 / 1.64 / 1.60** and a fixed threshold of **2.9**. It fails both
bars in every run, on both signs of the estimate. There is no reading of this session in which
four words is placeable.

The arithmetic still admits it — `3 × 26 = 78` of burst plus 30 of margins against a window
now measured at 122.4, i.e. 14.4 cycles nominally to spare. That gap between "the span fits"
and "the solver's rounding puts it there" is the same trap the atomic-era section named, and
the measurement lands on the same side of it: `solve_spin` quantizes to whole `dbf` iterations
and the nearest one puts the first write a quarter-cycle *inside* the early margin.

**The 5-word row is refused twice over**, on both edges simultaneously (−10.28 early, −1.33
late), where the atomic era could only show it as an empty band.

**What would change the answer**, stated so the next reader does not have to re-derive it: a
pre-burst path ~3 cycles cheaper would move the solved spin off its unlucky rounding and hand
four words a real margin; so would an early guard margin re-derived downward now that it no
longer has to cover a *derived* edge — 20 cycles was two iterations of slop bought against an
edge nobody could see, and that edge is now measured to 0.70. **Neither is proposed here.**
This parcel measures and books; it changes no constant and no ceiling.

---

## 6. Reproducing

```bash
# the window fixture — both edges, the anchor, and the ceiling recommendation
python3 tools/hblank_window_sweep.py --rom s4.debug.bin --lst s4.debug.lst \
        --only sweep --lo 0 --hi 200 --rows 12 --words 1 --json w1.json

# the cross-checks: same fixture, wider bursts
python3 tools/hblank_window_sweep.py ... --words 3   # plateau control still valid
python3 tools/hblank_window_sweep.py ... --words 4   # plateau control goes vacuous, and says so
python3 tools/hblank_window_sweep.py ... --words 5

# controls
python3 tools/hblank_window_sweep.py --only anchors  # five anchors, both conventions
python3 tools/hblank_window_sweep.py --only a1,a2    # determinism + liveness

# every number in sections 3-5 above, re-derived with NO emulator and NO ROM
python3 tools/hblank_window_sweep.py --replay w1.json

# the analysis's own tests — synthetic landings from a window they chose
python3 -m pytest tools/test_hblank_subline.py -q    # 14 passed
```

**Zero ROM bytes.** `s4.debug.bin` crc32 `06af0010` before and after; this parcel touches
`tools/` and `docs/` only. Wire pins 39/39 — the driver consumes the encoder, it does not
change it. Full suite **1106 passed / 2 skipped**, against a 1092/2 baseline (the 14 new tests
are the difference).
