# The Hydrocity waterline — row remap (EFFECTS-W1 DoD item 9)

***DESIGN ONLY, 2026-09-03.** Branch `design/hydrocity-row-remap`, worktree
`/home/volence/sonic_hacks/.aeon-hcz-design`, based on aeon `ddaab282` (`master`). **Nothing is
built, no engine byte moves, no ROM was rebuilt.** Written because DoD item 9 had no design block —
its entire specification was one table row at `docs/DEFERRED_WORK.md:17597` — and because the owner
asked for the effect by name tonight. It blocks nobody; it unblocks parcel 9a.*

*Provenance: every claim about Sonic 3 & Knuckles is cited to a line of
`/home/volence/sonic_hacks/skdisasm` (`sonic3k.asm`, `s3.asm`, `sonic3k.constants.asm`) and was read
firsthand out of the file, never from a summary; the ladder table was decoded by reading
`Levels/HCZ/Misc/HCZ Waterline Scroll Data.bin` directly. Every claim about aeon is cited
`path:LINE` with a symbol name adjacent. Every claim about the other six reference disassemblies is
cited to its own tree. **No emulator was run, no MCP tool was called, and no number in §7 is
measured** — §7.3 says how wrong that has been before, with the precedent.*

*Lineage: follows `docs/superpowers/specs/2026-09-02-moving-bands-anchor-mover-design.md`'s
structure (references-and-what-each-gave before the mechanism; a calibration section beside the cost
table; open questions and a did-not-settle section at the end).*

---

## 0. The one-paragraph answer, and the correction the booking's own name needs

**The item is misnamed, and the misnaming points at the wrong hardware.** "Row remap" reads as a
NAMETABLE remap — rewriting which tile row of the plane map is drawn at which screen row. Sonic 3
& Knuckles' Hydrocity waterline **never writes the nametable, and never writes VSRAM**. It is two
independent remaps that share one index table:

1. **A per-line HORIZONTAL SCROLL TABLE row remap.** `HCZ1_Deform` (`sonic3k.asm:105799`) builds a
   smooth per-source-row background scroll gradient in RAM, then **overwrites a window of that
   gradient by reading it back through a byte index table** — `move.b (a6)+,d3 / add.w d3,d3 /
   move.w (a5,d3.w),(a1)+` (`sonic3k.asm:105866-105871`). Screen row *i* of the band gets the scroll
   value that belonged to row `table[i]`. Rows are reordered, repeated and dropped.
2. **A tile-ART row gather.** `loc_27888` (`sonic3k.asm:53981`) walks **the same table row** and uses
   each byte to pick a 4-byte pixel row out of a 192-row ROM image, assembling 96 rows into a
   staging buffer and DMAing them into a **fixed** VRAM tile run (`sonic3k.asm:54008-54022`). The
   plane map under those tiles is never touched — `AniHCZ_FixUpperBG` / `AniHCZ_FixLowerBG`
   (`sonic3k.asm:54082`, `:54100`) restore the untouched art to the same tile addresses when the band
   leaves.

Both halves index the same table by the same quantity: `d2`, the **parallax discrepancy at the
waterline** — how far the background's image of the water surface has drifted from the foreground's,
because the background follows the camera at a quarter rate. That is precisely the owner's
"depending on your perspective".

**For aeon this lands almost entirely on machinery that already ships.** Half 1 is a seventh
specialised line loop inside `Parallax_Fill_PerLine` (`engine/level/parallax.emp:2689`) — a sibling
of `.lp_curve` — plus a fourth capability-selected `band_record` tail, the exact shape
`band_drift` took six days ago. **It costs ZERO HBlank cycles**, because the whole mechanism lives
in the game loop and reaches the VDP through the one 896-byte static HScroll DMA that already
exists. The 488-cycle scanline budget the brief asked me to price against **is not the budget this
effect spends** (§7.1). Half 2 — the art gather — is **blocked today** on the same wall item 8 hit:
`bg_region` is packed 448/448 and its `band_reserve` binds the next art import, not this one (§6.2).

**Build half 1. Defer half 2 and say why.** §10 is the ladder.

---

## 1. What S3K actually does, in full

### 1.1 The scroll half — `HCZ1_Deform`, `sonic3k.asm:105799`

The routine runs every frame from HCZ act 1's background handler (`sonic3k.asm:105685`, `:105739`,
`:105786` — three call sites, one per background routine state).

**The perspective quantity, `d2`:**

```
HCZ1_Deform:
        move.w  (Camera_Y_pos_copy).w,d0        ; camera Y
        subi.w  #$610,d0                        ; delta from the waterline equilibrium point
        move.w  d0,d1
        asr.w   #2,d0                           ; the BG follows at 1/4 rate
        move.w  d0,d2
        addi.w  #$190,d0
        move.w  d0,(Camera_Y_pos_BG_copy).w
        sub.w   d1,d2                           ; d2 = (delta>>2) - delta = -(3/4) * delta
        move.w  d2,(Events_bg+$10).w            ; PUBLISHED — the art half reads this
```

`d2` is the **parallax discrepancy**: the number of screen lines by which the background's picture
of the water surface has separated from the foreground's, given a quarter-rate background. It is
published in `Events_bg+$10` so the tile-animation half can read the same number without
recomputing it. Its useful range is `(-$60, +$60)`; outside that the routine takes the plain path
(`cmpi.w #-$60,d2 / bgt.s`, `cmpi.w #$60,d2 / bge.s` — `:105819`, `:105845`).

**The buffer being remapped.** `HScroll_table` is `ds.b $200` (`sonic3k.constants.asm:289`),
described there as *"array of background scroll positions for the level"*. It is **one word per
BACKGROUND SOURCE ROW**, not per screen line — the screen-line table is `H_scroll_buffer`,
`ds.b $380` = 224 longwords (`sonic3k.constants.asm:321`), and `ApplyDeformation` (§1.3) is what
projects one onto the other. Its structure, read straight off the writes:

| `HScroll_table` words | bytes | what fills them | what they are |
|---|---|---|---|
| 0..12 | `$00`..`$18` | `loc_50DDA` (`:105898-105930`), a palindrome: `(a1)`&`$18(a1)`, `2(a1)`&`$16(a1)`, … meeting at `$C` | the 13 run-length "held" bands of the far background — a symmetric reflection gradient |
| 13..108 | `$1A`..`$D8` | `loc_50D3A` (`:105827`) or `loc_50E60` (`:105945`) | the 1:1 region above the waterline |
| 109..204 | `$DA`..`$198` | `loc_50D56` (`:105847`), a 96-word linear ramp `d1 -= camX>>7` per row | **the waterline window** — the 96 rows the remap rewrites |

**The remap itself** (`sonic3k.asm:105849-105876`):

```
        lea     (HScroll_table+$0DA).w,a1       ; a1 = write cursor, the window base
        lea     (a1),a5                         ; a5 = READ base, the SAME address
        lea     (HCZ_WaterlineScroll_Data).l,a6
        move.w  d2,d1
        bmi.s   loc_50DAE
        move.w  d1,d3                           ; --- waterline displayed BELOW water ---
        neg.w   d3
        addi.w  #$60,d3                         ; d3 = $60 - d2
        lsl.w   #5,d3                           ; x32
        adda.w  d3,a6
        add.w   d3,d3                           ; x64 more  =>  row stride 96 bytes
        adda.w  d3,a6
        subq.w  #1,d1
        moveq   #0,d3
        lsr.w   #1,d1
        bcc.s   loc_50DA0
loc_50D98:
        move.b  (a6)+,d3
        add.w   d3,d3
        move.w  (a5,d3.w),(a1)+
loc_50DA0:
        move.b  (a6)+,d3
        add.w   d3,d3
        move.w  (a5,d3.w),(a1)+                 ; Apply scroll data
        dbf     d1,loc_50D98
```

Three facts to take from this and nothing else:

- **The read base and the write base are the same address.** The permute is IN PLACE and forward.
  It is safe only because the table's indices satisfy `table[i] >= i` — verified over the whole
  shipped table (every one of the 97 rows is monotone non-decreasing, §1.2), so a line either reads
  a slot it has not written yet or reads its own value back. That invariant is load-bearing and
  aeon's version must either preserve it or write to a separate destination.
- **The band's height is `|d2|`, the perspective quantity itself**, unrolled two-at-a-time by the
  `lsr.w #1 / bcc` Duff device. Perspective simultaneously *selects the ladder row* and *sizes the
  band*. Those are the same number, deliberately — the band grows as it compresses.
- **The above-water arm** (`loc_50DAE`, `:105878`) is the mirror image: `d3 = d1 + $60`, and the writes
  run **backwards** with `move.w (a5,d3.w),-(a1)` from `$D8` downward while the reads still run
  upward from `$DA`. No aliasing at all in that direction.

### 1.2 The ladder table — `Levels/HCZ/Misc/HCZ Waterline Scroll Data.bin`, 9,312 bytes

Read directly (`python3`, this session): **97 rows of 96 bytes**, indexed by `x = $60 - |d2|` ∈
[1, $5F], with rows 0 and 96 as the endpoints. Every row is **monotone non-decreasing**. Row 0 is
the identity `0..95`. Row 96 is `96..191`. Between them the row resamples 96 output lines from a
192-row source with a progressively coarser step and **exactly one large discontinuity** — the
water seam:

| row | step histogram over its 95 deltas |
|---|---|
| 10 | 84×1, 10×2, 1×87 |
| 24 | 70×1, 24×2, 1×73 |
| 48 | 47×1, 47×2, 1×49 |
| 70 | 69×1, 8×3, 17×4, 1×27 |
| 90 | 89×1, 1×7, 5×16 |

Row 48 is a clean 2:1 decimation (`[1,3,5,7,…]`). Rows 70 and 90 are **not** — their step
distributions are nonlinear, which is what makes this a hand-shaped perspective ladder and not
something a Bresenham walk reproduces. That matters for §6.1: it is why the design keeps a table
and does not try to synthesise the curve at runtime.

**Only the first `|d2|` entries of a row are consumed by the scroll half** (the `dbf` count is
`d2`), and those entries never exceed 95, so `(a5,d3.w)` stays inside the 96-word window. The
entries beyond `|d2|` — the ones carrying values up to 191 — exist for the **art** half, which
consumes all 96.

### 1.3 The second, coarser remapper — `ApplyDeformation`, `sonic3k.asm:103662`

This is a general S3K facility, not HCZ's, and it is worth naming because **aeon already has its
equivalent and the design must not rebuild it.** It walks a per-zone *deform array* and projects
`HScroll_table`'s source-row words onto 224 screen longwords:

```
HCZ1_BGDeformArray:
        dc.w $40, 8, 8, 5, 5, 6, $F0, 6, 5, 5, 8, 8, $30, $80C0, $7FFF   (s3.asm:71810)
```

Each word is a segment height in screen lines. `smi d4` (`:103671`) latches the **top bit**: a plain
entry means *hold one source word for this many lines* (`loc_4F130`, `:103729` — read one word,
replicate), a `$8000`-marked entry means *advance the source one word per line* (`loc_4F11E`,
`:103714`). `$7FFF` terminates. So HCZ act 1's background is thirteen constant-scroll strips of
heights 64/8/8/5/5/6/240/6/5/5/8/8/48 followed by one 1:1 run of `$C0` = 192 lines — and the
arithmetic closes exactly: 13 held words + 192 walked words = 205 source words, which is precisely
the `$1A`..`$198` span `HCZ1_Deform` writes.

**That run-length band model is aeon's `band_entry` array**, and aeon's is strictly more general
(§4.1). Nothing needs building here.

### 1.4 The art half — `loc_27888`, `sonic3k.asm:53981`

```
loc_2788C:
        moveq   #0,d1
        move.w  (Events_bg+$10).w,d1            ; the SAME d2
        cmp.w   (a3),d1
        beq.w   loc_2797A                       ; unchanged since last frame -> do nothing
        move.w  d1,(a3)
        ...
        addi.w  #$60,d1
        bcc.w   loc_2797A
        move.w  d1,d0
        add.w   d1,d1
        add.w   d0,d1
        lsl.w   #5,d1                           ; d1 = (d2+$60) * 96 — the SAME row stride
        lea     (Chunk_table+$7C00).l,a4
        lea     (HCZ_WaterlineScroll_Data).l,a5
        adda.w  d1,a5
        move.w  #$60-1,d1                       ; ALL 96 entries, unlike the scroll half
loc_278C6:
        moveq   #0,d0
        move.b  (a5)+,d0
        add.w   d0,d0
        add.w   d0,d0                           ; index * 4 = one 8-px pixel row, 4bpp
        lea     (ArtUnc_AniHCZ1_WaterlineBelow).l,a0
        adda.w  d0,a0
        move.l  (a0),(a4)                       ; column 1's row
        lea     $600(a0),a0
        lea     $180(a4),a4
        move.l  (a0),(a4)                       ; column 2's row
        lea     -$17C(a4),a4
        dbf     d1,loc_278C6
        move.l  #Chunk_table+$7C00,d1
        move.w  #tiles_to_bytes($2DC),d2
        move.w  #$180,d3
        jsr     (Add_To_DMA_Queue).l
```

- **Two 8-pixel columns, 96 rows each** = 12 tiles per column, `$180` bytes per column, DMAd to
  fixed tile runs `$2DC`/`$2E8` (above-water strip) and `$2F4`/`$300` (below-water strip). 48 tiles
  total. The band is 16 px wide and the plane map repeats it horizontally — which is why the whole
  visible waterline costs 48 tiles and not 480. Per-line horizontal scroll shifts the repeated
  pattern, and because the period is 16 px the repetition is invisible.
- **Guarded.** `cmp.w (a3),d1 / beq` — the rebuild happens only on frames where the perspective
  quantity CHANGED. Standing still costs nothing.
- **The nametable is never written.** When the band crosses the water surface, `AniHCZ_FixUpperBG` /
  `AniHCZ_FixLowerBG` DMA plain art back into *the same tile addresses*.

### 1.5 What HCZ does NOT do, stated as a prohibition

- **It does not write the nametable.** Neither half. Not per frame, not on the crossing. The
  booking's name asserts otherwise and is wrong.
- **It does not use VSRAM per-column scroll.** Every VSRAM write in `sonic3k.asm` is a whole-plane
  longword in a VBlank routine (`:526`, `:629`, `:971`, `:1326`, `:102508`, `:104981`); HCZ's
  vertical contribution is the single `Camera_Y_pos_BG_copy`. There is no column table anywhere in
  the zone.
- **It does not run in HBlank.** Both halves run in the game loop and reach the VDP through the
  ordinary per-frame HScroll DMA and the ordinary DMA queue. HCZ's HBlank does nothing for the
  waterline.

### 1.6 Cost of S3K's own version, derived

68000 timings, static:

| loop | body | cyc/line | ×96 lines |
|---|---|---|---|
| scroll remap (`loc_50D98`) | `move.b (a6)+,d3` 8 · `add.w d3,d3` 4 · `move.w (a5,d3.w),(a1)+` 18, `dbf` 10 per 2 lines | ~35 | ~3,400 |
| art gather (`loc_278C6`) | 11 instructions, dominated by two `move.l` (20 each) and four `lea` | ~122 | ~11,700 |

The art gather is ~9× the scroll remap, which is exactly why S3K guards it on a change in `d2` and
does not guard the scroll half. Read these as a shape, not as a pin — they are an instruction-table
derivation with no measurement behind them.

---

## 2. References read, and what each gave — and the two FAMILIES they split into

All seven reference trees in `CLAUDE.md`'s checklist were read. The result reorganises the whole
problem, so it goes before the design rather than after it.

**Every reference that does a genuine "screen row *N* shows source row *M*" remap does it on the
VERTICAL axis, per line, from HBlank, through VSRAM. S3K's Hydrocity does it on the HORIZONTAL
axis, per line, in the frame, through the HScroll table. These are two different families, and the
item's name describes the family S3K is NOT in.**

| | family | what is remapped | where it runs | per-line cost |
|---|---|---|---|---|
| **S3K HCZ / LBZ2** | **A** | the per-line **HScroll** table, in RAM, then one DMA | game loop | 0 HBlank cycles |
| Gunstar Heroes | **B** | per-line **VSRAM** word, arbitrary, from a RAM array | HBlank, every line | 1 long + 1 word + `rte` |
| Thunder Force IV | **B** | per-line **VSRAM**, source row advanced by a **run-length bitmask** | HBlank, every line | 1 word + a bit-scan |
| Ristar | **B** | per-8-line **VSRAM** step of −8 (the same 8 rows repeated down the screen), then a mid-frame flip of reg `$0B` itself | HBlank, every 8 lines | 3 instructions + one 40-word burst |
| Batman & Robin | **B** + plane | per-line VSRAM from a double-buffered RAM table (self-modifying handler), **plus** a mid-frame reg `$04` plane-base swap | HBlank, every line | ~6 instructions |
| Alien Soldier | plane only | mid-frame reg `$02` plane-base change, one split, spin-timed | HBlank, once | n/a |
| S.C.E. | neither | one-shot CRAM swap at the waterline | HBlank, once | n/a |
| Vectorman | — | **nothing usable** — see §2.6 | | |

### 2.1 S.C.E. — no HCZ, and a correction to the corpus (LOAD-BEARING as a negative)

S.C.E. ships DEZ only; `Hydrocity|HCZ` has **zero** hits across its `.asm` tree. Its water is S3K's
**one-shot CRAM swap at the waterline** (`Engine/Core/Interrupt Handler.asm:382` — `HInt` writes
`#$8A00+(screen_height-1)` to disarm itself, then blits 32 longs of `Water_palette` to CRAM), with
the split line computed in `Engine/Core/Water Effects.asm:7` from `Water_level - Camera_Y_pos`.
**Aeon already ships that**, as `fx_tint_band` + `patchable` (`ojz_effects.emp:1501`).

What S.C.E. *does* give is `ApplyDeformation` (`Engine/Core/Deformation Script.asm:150`), the
deform-block builder ARCH §4.6 already names as the multi-band model's foundation — its
`.normal_loop` (`:242`) writes one source value to every line of a block while `.linear_loop`
(`:217`) advances per line, and `.process_block` (`:160`) *skips* source entries for off-screen
blocks. Source-index versus screen-row genuinely repeats and skips there. **But it is HScroll only**
— the horizontal axis, and it is §1.3's routine, which aeon's `band_entry` array already
generalises.

### 2.2 Gunstar Heroes — the minimal per-line VSRAM remap (LOAD-BEARING)

`code/disasm.asm:1238-1245`, a handler template copied into `$FFFFEE00`:

```
        move.l  #$40000010, $c00004.l   ; VSRAM write, addr $0000 = plane A VScroll
        move.w  (a6)+, $c00000.l        ; the next word from the RAM stream
        rte
```

`a6` persists across interrupts and is reset once per frame (`:1150` `lea.l $9600.w,a6`); the array
is refilled from `$9400` at `:1144-1149` (28 longs = 56 per-line words). Arming is Treasure's VDP
shadow framework (`ori.b #$10,$f7d1.w`; `$f7e4/$f7e5` is the `$8Axx` shadow, `#$0` = every line).

**Screen line *N* takes an arbitrary VScroll word from `$FFFF9600 + 2N`. Nothing forces
monotonicity.** This is the purest statement of a vertical row remap in the corpus, and it is
structurally what §5.6's proposal is.

### 2.3 Thunder Force IV — the run-length bitmask, the most compact encoding found (LOAD-BEARING)

`code/disasm.asm:11833-11846`. `d4` is the *source row* for the current screen line and it advances
by a **variable** amount driven by a 32-bit ROM bitmask indexed by a 32-frame counter
(`lea.l $13182.l,a3`, `move.w $e198.w,d0`, `move.l (a3),d7`):

```
loc_00EE3A:
        move.w  d4, (a2)                ; a2 = $C00000 -> plane A VScroll for THIS line
        addq.w  #$1, d5
        moveq   #$0, d3
loc_00EE40:
        btst.l  d5, d7                  ; walk the bitmask
        bne.b   $ee4a
        addq.w  #$1, d5
        addq.w  #$1, d3
        bra.b   $ee40
loc_00EE4A:
        add.w   d3, d4                  ; advance the SOURCE by the RUN LENGTH, not by 1
```

Set bits → the source advances fast (rows dropped); runs of clear bits → the source stalls (rows
repeated). The frame setup writes `#$8f00` — **autoincrement 0**, so every write lands on the same
VSRAM word.

**Four bytes of ROM describe a whole 32-row repeat pattern, and a different mask per frame animates
the squash and stretch.** That is 2,300× denser than §1.2's ladder for the same class of effect.
Whether it is expressive enough for a *perspective* ladder is a real question and §12 Q5 books it.

TF4's ordinary 8-layer parallax (`ANALYSIS.md:16-60`) is unrelated — VBlank-computed HScroll with
`muls`, no remap.

### 2.4 Ristar — and it corrects `docs/research/ristar-techniques.md` twice (LOAD-BEARING)

The existing research note is right about the dispatch mechanism and **wrong about the axis and the
granularity**, checked against the disassembly:

- ✅ **Confirmed, and better than written**: `code/disasm.asm:257-258` patches `#$4ef9` (`jmp abs.l`)
  plus an operand into `$FFFFEA70`, and **the handler re-patches its own operand**, so HInt is a
  chained state machine rather than a per-act hook.
- ❌ **"HSCROLL_base[line] = base + sin(line+t)"** — there is no sine and the axis is vertical. The
  real chain (`code/disasm.asm:14546-14598`) is: arm `$8A` at the split, `#$8b03` (VScroll FULL,
  HScroll per-line) → stage 1 re-fires every 8 lines (`#$8a07`) → **stage 2 does
  `VScroll -= 8` every 8 lines, redrawing the SAME 8 plane rows all the way down the screen** →
  stage 3 flips reg `$0B` *mid-frame* to `#$8b07` (per-column VScroll) and bursts a 20-entry column
  table from `$FFF500`, which is random-walked ±1 and clamped 0..6 each frame.
- ❌ **"cell-scroll (per-8-pixel HScroll) is the workhorse"** — a census of every `#$8Bxx` the file
  writes returns **only `$8B03` and `$8B07`**, both per-LINE HScroll. Cell mode appears nowhere.
  The note's §4 recommendation rests on a fact its own disassembly contradicts.

The mid-frame change of reg `$0B` *itself* is the one technique in this survey aeon has no
equivalent for, and it is worth stealing independently of this item.

### 2.5 Batman & Robin — both halves, and a correction to two sibling ANALYSIS docs

`code/init/vectors.asm:33` → IRQ4 vectors to `$FFFFE560`, i.e. **the handler lives in RAM and is
swapped per effect**. (`gunstar_disasm/ANALYSIS.md:104` and `aliensoldier_disasm/ANALYSIS.md:104`
both assert *"Batman & Robin — N/A (no HBlank)"*. Both are wrong.)

- **A mid-frame nametable-base swap** (`batman.lst:58337`): the frame setup writes `#$8407`
  (Plane B at `$E000`); the split handler writes `#$8406` (Plane B at `$C000`) and then bursts 20
  per-column VScroll words. **The top and bottom bands read two different Plane B tilemaps.** This
  is item 11a's mechanism, already landed here.
- **A per-line handler resident in RAM that patches its own source operand** (`batman.lst:18816`):
  `move.l ($0000).w,$c00000.l` followed by `addq.b #$4,$ffe56b.w` — six instructions, the cheapest
  per-line handler in the survey, double-buffered between `$FFFF9040` and `$FFFF9240`.
- **A per-band `divs` perspective builder** (`batman.lst:58369`): a script of `(repeat, divisor)`
  pairs; each band divides once and **repeats the same value for every line of the band**. That is
  §1.3's held-band model with a divide in it, and aeon's `band_entry` + `.lp_flat` is its
  multiply-free equivalent.

### 2.6 Vectorman — CONTRIBUTED NOTHING, and the negative is worth the space

IRQ4 → `$FFFF9D2E`, but **the installer is not in the disassembly**: `ANALYSIS.md:196` says it is
patched at `$8A0A`, which falls in a range the capstone pass classified as data
(`code/disasm.asm` jumps `loc_00889C` → `loc_008C00`). Grepping the entire file for `9d2e` /
`ffff9d2e` / any copy into `$9Dxx` returns nothing. What *is* visible is a clean scroll-mode
selector with matching VBlank uploaders (`code/disasm.asm:762-786`, `#$8b08` / `#$8b0b` / `#$8b0f`
each installing a different writer pointer) — a nice pattern, and one aeon deliberately does not
need since the d-29 ruling made per-line the only mode. **Negative on evidence.** Recorded so the
next reader does not spend the hour again.

### 2.7 Alien Soldier — the plane-base split, spin-timed

Same Treasure framework, different payload (`code/disasm.asm:877-881`): a timed spin
(`subq.w #$1,$ffff0186.l / bne.b`) to land on an exact pixel, then `move.w #$8228,(a6)` — reg `$02`
= `$28`, Plane A's nametable base moved to `$A000`, once. Reg `$0B` is never written in the whole
file. One split, whole-plane, no table. It is item 11a's mechanism with sub-scanline placement.

### 2.8 What the corpus says about this item, in one sentence

**Nobody does a per-row NAMETABLE remap.** Mid-frame nametable work is always a whole-plane base
register swap (Batman reg `$04`, Alien Soldier reg `$02`) — which aeon shipped this morning as item
11a. Every genuine per-row remap in the corpus is **per-line VSRAM written from HBlank**, and S3K's
Hydrocity — the one this item is named after — is the outlier that does it on the *other* axis and
never enters HBlank at all.

---

## 3. What the effect IS, classified for this engine — the correction, stated once

The brief asked me to state plainly whether this is a nametable row remap, a scroll trick, or a
combination, and told me the item's name is not authority. **The name is wrong.** In full:

1. **It is a combination of two remaps, and NEITHER is a nametable remap.**
2. **The scroll half is a per-line HSCROLL TABLE row remap** — Family A. Not a scroll *trick* in
   the sense of "compute a different value per line"; aeon already does that four different ways
   (§4.1). The remap is an **indirection**: the value written to line *i* is *fetched from* line
   `table[i]`'s slot. That indirection is the only thing aeon cannot currently express.
3. **The art half is a tile-ART row gather with a fixed nametable** — source pixel rows selected by
   index out of a ROM image and DMAd into a *fixed* VRAM tile run. It is BgAnim-adjacent and it is
   **not** a BgAnim band (§6.3).
4. **Nothing in it is VSRAM** (§1.5), which is what separates it from every other reference in the
   corpus (§2.8).
5. **The competing VRAM resource is `bg_region`'s tile arena, not item 0's `spare_nametable`** (§6).
   The half that needs tiles needs BG art tiles; the half that does not need tiles is the half worth
   building.

**And the vertical row remap the name evokes is a real, separate, cheaper thing that four
references do and aeon is one opcode away from.** It is not this item, but pretending it is not
adjacent would be dishonest, so it is designed in §5.6 and sequenced as 9e rather than folded in.

---

## 4. Which existing aeon machinery this reuses

### 4.1 Already shipped, and exactly right — do not rebuild

| S3K piece | aeon equivalent, shipped | citation |
|---|---|---|
| `H_scroll_buffer`, 224 longwords, one static DMA | `Hscroll_Buffer`, 224 longwords, the one 896-byte static DMA entry; reg `$0B` bits 1:0 held at `%11` **always** since the d-29 ruling | ARCH §4.6 "One HScroll mode: per-line, always"; `engine/level/parallax.emp:2689` |
| `HCZ1_BGDeformArray` — run-length bands, held vs 1:1 | `band_entry` array + `pcfg_band_count`, up to `MAX_PARALLAX_BANDS = 16`, with per-band FG/BG factors, per-band deform amplitude and phase | ARCH §4.6; `engine/level/parallax.emp:107` |
| the 1:1 walked segment | `.lp_flat` / `.lp_both` / `.lp_bg` / `.lp_fg` | `parallax.emp:2652-2688` banner |
| `loc_50D56`'s linear per-row ramp (`d1 -= camX>>7`) | **`.lp_curve`** and the `band_curve` tail — a Bresenham BG-scroll ramp across a band, with carry across an anchored split | `parallax.emp:2836-2884` |
| the water-surface split line | **`pcfg_anchor_ch` + Parcel W's world-anchored deform overlay** — `L = Effects_World_Y[ch] - Camera_Y`, the containing band is SPLIT there, additively | ARCH §4.6 "World-anchored deform overlay" |
| `Events_bg+$10` = the parallax discrepancy | **already computable from two quantities the engine keeps** — §4.2 |
| the art half's staging + DMA | the DMA queue and `BgAnim_Update`'s DMA shape | `engine/level/bg_anim.emp` |

**Five of the six pieces already exist.** The missing one is the indirection.

### 4.2 The perspective selector is FREE — aeon already computes both of its terms

S3K's `d2` is "where the background thinks the waterline is, minus where the foreground says it
is". ARCH §4.6 already draws that exact distinction, in the World-Y re-glue section, and calls it
parallax rather than an inconsistency:

> *"**This is NOT the anchor's mapping.** A patch anchor is a level feature and maps 1:1
> (`world_y − Camera_Y`); a static layer top is a BG-art feature and maps through the plane's
> depth. The same authored Y lands on different screen lines, which is parallax rather than an
> inconsistency."*

So:

```
perspective  =  scene_plane_line(anchor_world_y)  as rotated by Step 4a   // the BG's image
             -  (Effects_World_Y[ch] - Camera_Y)                          // the FG's truth
```

Both terms are live in `Parallax_Update`'s frame already — the first is what Step 4a's rotation
produces for a band top, the second is what Parcel W's split line is. **The selector is a
subtraction of two numbers the engine has, not a new derivation, and it needs no new authored
field.** That is the single strongest reason this effect fits here.

### 4.3 The raster interpreter is the wrong machine for family A — and the RIGHT one for family B

For **family A** (the item), `engine/effects/raster.emp`'s HBlank interpreter is wrong
structurally, not budgetarily:

- **HScroll is a VRAM TABLE, not a register.** There is no per-line HScroll register an HBlank
  handler could write; the VDP fetches each line's longword from the table itself. An HBlank program
  cannot remap HScroll rows because there is nothing per-line for it to write.
- The dense tier's targets are CRAM and VSRAM, and §1.5 establishes HCZ touches neither.
- Consequently `RASTER_DENSE_LINE_RAMP_CYC = 304` of 488 is **not this effect's budget** (§7.1).

For **family B** (§5.6) it is exactly the right machine, and the gap is one opcode wide:

| dense body | source | words/line | cost/line, MEASURED |
|---|---|---|---|
| `.dense_body` (`OP_RUN_GRADIENT`) | a ROM cursor, `Raster_Dense_Cursor` | **3**, to `addr`, `addr+2`, `addr+4` (VDP autoincrement) | `RASTER_DENSE_LINE_GRAD_CYC = 316` |
| `.ramp_body` (`OP_RUN_RAMP`) | **computed**, `Raster_Ramp_Acc += Raster_Ramp_Step` (16.16) | 1 | `RASTER_DENSE_LINE_RAMP_CYC = 304` |
| *(the gap)* | a ROM cursor | 1 | — |

Gunstar's handler (§2.2) is precisely "a table cursor, one word per line, to VSRAM". The gradient is
table-driven but writes three *consecutive VSRAM entries* — three column-pairs, not three lines — so
it cannot be that. The ramp writes one word but computes it linearly, so it cannot express a remap.
**Neither existing body can do it, and both are four instructions away from doing it.** That is the
§5.6 proposal, and it is the closest this design comes to item 6's lesson — the mechanism is not
shipped, but its two nearest siblings are, and the new one costs almost nothing because of them.

---

## 5. The mechanism

### 5.1 The shape: a seventh specialised line loop

`Parallax_Fill_PerLine` already dispatches one of **six** specialised line loops per band
(`.lp_both`, `.lp_flat`, `.band_fg_only`, `.lp_bg`, `.lp_curve`, and the flat fallthrough), each
with its own register allocation, all guaranteeing one cross-loop contract: *`d4` = the band's end
line, `a1/a2/a3/a5/a6/d7` untouched* (`parallax.emp:2668-2671`). A row remap is a seventh, added
the way `.lp_curve` was added by P3 Task 10.

**Two candidate placements, and the ruling.**

- **(A) Remap the SOURCE INDEX in the value computation.** Replace the line loop's implicit `+1`
  walk with `table[i]`. Cheapest per line, but it composes with only one of the six loops at a time
  — a product with the FG/BG/curve matrix, which is exactly what `.lp_curve`'s banner says was
  avoided deliberately ("what keeps this ONE new loop variant instead of a product with the
  FG/BG/both matrix").
- **(B) Permute the OUTPUT, in a second pass over the band's longwords.** This is S3K's own shape.
  It composes with **all six** loops and with drift, the anchored split and the deform tables,
  because it operates on what they produced. It costs one extra pass over the band.

**RULING: (B).** The composition property is worth more than the pass. It is also the only one of
the two that inherits S3K's `table[i] >= i` in-place-safety invariant unchanged, and the only one
that can be described to an author as "this band's lines are re-ordered" rather than as a
modification of five different loops' semantics.

### 5.2 The loop

```
        // a2 = &Hscroll_Buffer[band_top].bg      (the band's first BG word)
        // a3 = the ladder row for this frame's perspective
        // a4 = a2                                (the write cursor; forward, in place)
        // d3 = line count - 1
.lp_remap:
        moveq   #0, d1
        move.b  (a3)+, d1                   //  8   the ladder index
        add.w   d1, d1                      //  4
        add.w   d1, d1                      //  4   x4 = the longword stride
        move.w  (a2,d1.w), (a4)             // 18   fetch line table[i]'s BG word
        addq.l  #4, a4                      //  8
        dbf     d3, .lp_remap               // 10
```

**Register budget:** `d1`, `d3`, `a2`, `a3`, `a4`. `.lp_curve` spends every data register and needs
`a0` and `a4`; this loop is by far the cheapest of the seven, which is what makes (B) affordable.

**Only the BG word is touched.** The FG word at `(a4)` − 2 is left exactly as the primary loop
wrote it. Plane A is never remapped, for the same reason it is never lerped and carries no drift
rate: the FG streaming engine draws a camera-anchored 64-column window and any FG scroll offset
drags the plane-wrap seam on screen (ARCH §4.6). **No field should exist for a plane-A remap** —
the mistake should be unspellable, which is the `band_drift` precedent verbatim.

### 5.3 Where the state lives — a fourth `band_record` tail

`parallax_config` is **full**. Its size is 30 bytes and every one of its former pads is spent:
`pcfg_pad` → `pcfg_anchor_ch`, `pcfg_pad2` → `pcfg_anchor_dsa`/`dsb`, `pcfg_pad_29` → `pcfg_bob`
(`engine/structs.emp:199-260`). A pointer field in the header would take `sizeof` 30 → 34 (it must
stay even — it is the band array's base offset and an odd size starts the whole-entry `move.l` copy
on an odd address) and shift the band array behind **all twenty** shipped records.

So the remap goes where `band_drift` went: a **fourth capability-selected tail**.

```
pub struct band_remap (size: 6) {
    brm_ladder:  *u8,   // ROM ptr to the ladder table (97 rows x H bytes, or NULL)
    brm_height:  u8,    // H, the ladder's row width in lines == the band's max remapped height
    brm_flags:   u8,    // bit 0: which side of the anchor grows; bits 1-7 reserved
}
pub const BAND_REMAP_N = 0    // 1 in a game whose SCANLINE_CAPS include CAP_ROW_REMAP
```

appended to `band_record` after `br_drift`, with the matching `BAND_REMAP_BYTES` in
`engine/ram.emp` — the `ensure` at `parallax.emp:412` (`Parallax_Shadow_Scroll_A −
Parallax_Shadow_Bands == sizeof(band_record) * MAX_PARALLAX_BANDS`) is what makes forgetting that a
build error rather than a runtime overrun.

⚠ **`BAND_REMAP_N` is ENGINE-WIDE, not per-game — flipping it to 1 widens `band_record` for `demo`
too and moves every ROM image in the tree.** That is `BAND_DRIFT_N`'s banner verbatim
(`parallax.emp:348-357`) and it is owner-gated there. The mechanism moves no byte; **adoption**
does. Sequence accordingly (§10).

### 5.4 The capability bit

`CAP_ROW_REMAP = $0800`. **Derived, and then verified against the tree**: `scene_dsl.emp`'s bit run
is `$0001` (retired hole, ex-`CAP_PER_LINE`, never re-used) · `$0002 CAP_PER_COL_VSRAM` · `$0004
CAP_DEFORM` · `$0008 CAP_ANCHORS` · `$0010 CAP_TRANSITIONS` · `$0020 CAP_MULTI_DEFORM_TABLE` ·
`$0040 CAP_FACTOR_CURVE` · `$0080 CAP_BAND_DRIFT` · `$0100 CAP_ANCHOR_MOTION` · `$0200
CAP_DENSE_TIER` · `$0400 CAP_ROLE_SWAP`. **`$0800` is the next free bit.**

> ⚠ **A brief correction, recorded because it would have been repeated.** The dispatch brief gives
> `Game.SCANLINE_CAPS` as `$00DE`. It is **`$07DE`** (`games/sonic4/config/game.emp:126`). `$00DE`
> was its value between `a8c85611` and `c4118704`; it grew `$00DE → $01DE → $03DE → $07DE` across
> 2026-09-03 as `CAP_ANCHOR_MOTION`, `CAP_DENSE_TIER` and `CAP_ROLE_SWAP` landed in parallel lanes.
> It is also **not a scanline count** — it is a u16 capability mask and bounds nothing about display
> height. (What bounds scanlines is `SCREEN_HEIGHT = 224`, `RASTER_VBLANK_V = 224`,
> `RASTER_MAX_FIRE_LINE = 223`.) **Re-derive `$0800` again at implementation time**: three bits
> moved in one day, and a value copied out of a design doc written hours earlier is precisely the
> stale-fact class this repo has booked twice.

The mask is **unreadable from a `comptime fn` body or a record-emitting `data` context** —
`unknown name Game.SCANLINE_CAPS`, measured in both `parallax.emp:150-165` and
`ojz_effects.emp:1012-1018`. That is why `BAND_EXT_N` / `BAND_CURVE_N` / `BAND_DRIFT_N` are pinned
literals with two-sided `ensure`s, and `BAND_REMAP_N` must be one too. The safety property is
one-sided (`ensure((SceneRegistry_CapsFolded & ~Game.SCANLINE_CAPS) == 0)`,
`scene_registry.emp:536`): a declared superset only forgoes a specialisation, a declared subset
drops machinery a scene still demands.

Also stale and not to be cited: `game_contract.emp:38-42` still says *"NO ENGINE CONSUMER EXISTS
YET… it lowers to nothing and moves no ROM byte"*. That is P1-era prose; there are 26 gated spans
today.

The bit gates three spans: the tail (`BAND_REMAP_N`), the `.lp_remap` loop and its dispatch leaf,
and the per-frame selector arithmetic. A game that does not declare it emits none of them and pays
nothing per frame — the `band_drift` measurement (68 cyc/band for *declaring* the bit, 0 for not)
is the calibration.

### 5.5 The ladder row selection, per frame

Once per frame, per remapped band, before `Parallax_Fill_PerLine`:

```
p   = plane_line(anchor_world_y) - (Effects_World_Y[ch] - Camera_Y)   // §4.2, two live terms
p   = clamp(p, -(H-1), +(H-1))
row = H - |p|                                                          // S3K's x = $60 - |d2|
a3  = brm_ladder + row * H
d3  = |p| - 1                                                          // the band's remapped height
```

Three properties inherited from S3K rather than invented: the band's height IS the perspective
magnitude; the ladder row is its complement; and `p == 0` means zero remapped lines, i.e. the effect
turns itself off at the equilibrium point with no special case.

### 5.6 Family B — the VERTICAL row remap, which is what the item's NAME describes

Not part of item 9. Designed here because §2 found four references doing it, because it is what a
reader of "row remap" will expect, and because it turns out to be **smaller than family A**.

**The gap, from §4.3:** a dense body that reads ONE word per line from a cursor. `.dense_body` reads
a cursor but writes three consecutive VDP entries; `.ramp_body` writes one but computes it.

**The proposal — `OP_RUN_TABLE`, opcode `12`, and a `.table_body`:**

```
    .table_body:
        move.w  #RASTER_ARM_EVERY_LINE, (a2)    // reg $0A = 0: fire every line
        move.l  Raster_Dense_Cmd, (a2)          // the constant write command
        movea.l Raster_Dense_Cursor, a1
        move.w  (a1)+, -4(a2)                   // == VDP_DATA; one table word
        move.l  a1, Raster_Dense_Cursor
        subq.w  #1, Raster_Dense_Lines
        bne.s   .out
        jbra    .dense_end
```

This is `.dense_body` with two of its three stream writes deleted. It reuses `Raster_Dense_Cmd`,
`Raster_Dense_Cursor`, `Raster_Dense_Lines` and `.dense_end` unchanged; the ENTER body is
`OP_RUN_GRADIENT`'s verbatim. **`Raster_Dense_Mode` is a signed word carrying two facts** (0 = off,
+1 = gradient, −1 = ramp) and a third value needs a third state — that is the only non-trivial
decision in the whole proposal, and `+2` with a `cmpi` before the existing `bmi` keeps both current
bodies' dispatch depth unchanged, which the cost model requires.

**Derived cost:** `.dense_body` measures **316** cyc/line with three `move.w (a1)+,-4(a2)` at 16 cyc
each. Removing two gives **≈ 284 cyc**, against 488. `.ramp_body` measures 304 for one write plus
four accumulator instructions, which brackets 284 from the other side and makes it the cheapest
dense body. **Derived, not measured** — measure it with the FR1/FR2 method (§7.3).

**What it buys, in the corpus's own terms:** Gunstar (§2.2) becomes a stream authored as a table.
Ristar's `VScroll -= 8` every 8 lines (§2.4) becomes a stream with a sawtooth in it. TF4's bitmask
(§2.3) becomes a build-time-expanded stream — aeon expands at build time what TF4 expanded at
runtime, which is this engine's whole posture. **A vertical row remap is then authored data, not
code.**

**Its ROM cost is the honest objection:** one word per line per frame-state. A 96-line run in 32
animation states is 6,144 bytes, which is TF4's 128 bytes doing the same job. If a family-B effect
is ever wanted *animated*, revisit the bitmask; for a *static* remap the stream is right and costs
192 bytes.

**Sequenced as 9e (§10), and only on the owner's ask.** It is a better fit for the item's name than
the item is, and that is exactly why it should not be smuggled in under it.

---

## 6. VRAM, and the competition for `$6000`

### 6.1 The scroll half: ZERO tiles. It does not compete.

Half 1 writes `Hscroll_Buffer` (`engine/ram.emp:347`, 896 B = 224 × 4), which is RAM, shipped by
**one pre-built static DMA entry that already exists** — `Static_Hscroll_Line` (`engine/ram.emp:641`,
built at boot in `engine/system/buffers.emp:149-160`, enqueued on the Critical queue every VBlank
whenever a parallax config is active, `buffers.emp:465-498`) into the existing `hscroll_table` VRAM
region (`games/sonic4/vram.toml`, base 1504, 28 tiles, `VRAM_HSCROLL_TABLE = $BC00`).

**So half 1 costs ZERO new VRAM and ZERO additional VBlank DMA.** The 896 bytes already move every
frame; the remap only changes what is in them. It does not compete with 10c or 11b for
`spare_nametable`'s 128 tiles at `$6000`, nor for the window-only `$5000` run.

Its cost is **ROM**: the ladder. At S3K's dimensions that is `(H+1) x H` bytes = 97 × 96 = **9,312
bytes** per ladder. That is a real number and the design does not hide it. Three levers, in the
order an implementer should reach for them:

- **Author `H` down.** The ladder is quadratic in the band height. `H = 48` costs 2,352 bytes;
  `H = 64` costs 4,160 (which is exactly LBZ2's shipped size, §8). Make `H` an authored key.
- **Share one ladder across bands and sections.** It is a pure function of `H`; nothing in it is
  zone content. One `hcz`-shaped ladder serves every waterline in the game.
- **Do NOT try to synthesise it at runtime.** §1.2's step histograms show rows 70 and 90 are
  nonlinear — a Bresenham walk (which would cost ~390 bytes of parameters) reproduces row 48 and
  gets rows 70 and 90 visibly wrong. If a *generated* ladder is wanted, generate it at BUILD time
  from a perspective formula into the same table shape; that is `tools/`'s job, not the 68000's.

### 6.2 The art half: 48 tiles from `bg_region`, and that arena is FULL today

Half 2 needs a fixed tile run to DMA into. At S3K's dimensions: two 16 px × 96 px strips = **48
tiles**, plus ROM for two 192-row source images (2 columns × 192 rows × 4 B × 2 strips = 3,072 B).

Those tiles come from `bg_region` (`games/sonic4/vram.toml:177` — arena, base 1024, 448 tiles), and
**the shipped BG blob is packed 448/448**. `band_reserve = 128` binds the *next* import and frees
nothing today; `inject_editor_bg.py:200` gates the final blob on `BG_TILE_CAPACITY`, not on the
reserve. This is the identical wall item 8's on-screen half hit, for the identical reason.

**So half 2 is art-blocked, not engine-blocked, and it is blocked on someone else's document.** The
routes, both of which need the owner:

- an art-side re-import that leaves 48 tiles unclaimed (the same pass item 8 is waiting on), or
- **promotion** — converting 48 existing static `bg_region` tiles into the waterline strips, which
  `vram.toml` names as "the working route" for bands. It requires the OJZ background to contain a
  16-px-periodic water surface, which it does not.

### 6.3 BgAnim is the WRONG mechanism for half 2, and the arithmetic says so

BgAnim precomputes **8 phase banks** and rotates between them (`bg_anim.emp`; item 8's block,
`docs/DEFERRED_WORK.md:18078`). The waterline has **97 states**, continuously selected by a camera
quantity. Eight banks cannot express ninety-seven, and widening them is not affordable: at the d-9
ROM-room ceiling of 12,288 B for `ojz_bg_anim`, with the live act at 8,238 B, a new band is capped
at **15 tiles** — the waterline wants 48, and it wants 97 phases rather than 8.

**Half 2's correct mechanism is S3K's own:** a ROM source image, a runtime row-gather into a staging
buffer, one DMA into a fixed run, guarded on a change in the perspective quantity. ROM cost 3,072 B
against BgAnim's `8 × 48 × 32` = 12,288 B for a strictly worse result. Book that ruling now so the
implementer does not spend a day trying to make it a band.

---

## 7. Cost, priced

### 7.1 The referent, said before the numbers — and the brief's budget is the wrong one

**This effect spends ZERO HBlank cycles.** The brief asked for a price against
`RASTER_DENSE_LINE_RAMP_CYC = 304` of 488 cycles per scanline. That constant prices
`Raster_HInt`'s `.ramp_body` — the HBlank interpreter. §1.5 and §4.3 establish that the waterline
touches neither the interpreter nor VSRAM, and §4.3 explains why it structurally cannot: **per-line
horizontal scroll is a VRAM table the VDP fetches for itself, not a register an HBlank handler
writes.** There is no per-line work to do at all.

The budget this effect spends is the **frame** budget: 128,000 cycles per NTSC frame, of which the
walker allowance after `SB_AXIS1_RESERVATION` is ≈ 104,000 (back-derived from ARCH §4.6's own
sixteen-band row: 17,474 cyc = 13.7% of 128,000 = 16.8% of the allowance).

**A design that does not fit is a finding, not a failure — and so is a design that was asked to fit
the wrong budget.** This is the second.

### 7.2 Derived per-frame cost

68000 static timings, `.lp_remap` as written in §5.2:

| term | cyc |
|---|---|
| `moveq #0,d1` | 4 |
| `move.b (a3)+,d1` | 8 |
| `add.w d1,d1` ×2 | 8 |
| `move.w (a2,d1.w),(a4)` | 18 |
| `addq.l #4,a4` | 8 |
| `dbf` (taken) | 10 |
| **per line** | **56** |

| band height | cyc/frame | % of 128,000 | % of the ≈104,000 walker allowance |
|---|---|---|---|
| 48 | 2,688 | 2.1% | 2.6% |
| 96 (S3K's) | 5,376 | 4.2% | 5.2% |

Plus a per-frame constant for §5.5's selector — three loads, a subtract, an `abs`, a clamp and a
scaled index, ≈ 60-90 cycles, once per remapped band.

Comparison for scale, using the tree's own measured numbers: a sixteen-band scene costs 17,474
cyc/frame, i.e. **a 96-line remap is about the cost of five extra parallax bands.**

**A pre-scaled WORD ladder** (indices already ×4) removes the `moveq` and both `add.w`, taking the
line to **44 cyc** (4,224 cyc/frame at H=96) at the price of doubling the ladder to 18,624 bytes of
ROM. Priced here so the implementer can make the trade with both numbers in hand; the byte table is
the recommended default.

### 7.3 ⚠ How wrong these numbers are likely to be

**Low, and possibly very low.** The precedent is six days old and in this repo: the anchor-mover
design (`docs/superpowers/specs/2026-09-02-moving-bands-anchor-mover-design.md`, its own ⚙ BUILT
note item 2) priced its loop term at 236 cyc and measured **370** — **57% low** — and priced an idle
term at 12 against a measured 22. The stated causes were pairs of instructions counted as one and a
`tst.w (xxx).W` costed as a register test.

Applying that calibration honestly: **56 cyc/line could be 88; 5,376 cyc/frame could be 8,400**, or
**6.6% of the frame / 8.1% of the walker allowance** at H = 96. **It still fits, comfortably,** and
that is the useful form of the answer: the conclusion survives the worst historical error in this
tree.

**What would make it NOT fit:** a band height above ~200 lines at the pessimistic rate, or running
more than two remapped bands in one scene. Neither is a shape anyone has asked for. If an
implementer finds themselves wanting either, re-measure before building.

**Measure it the way item 6 measured the dense tier**: `tools/raster_cost_probe.py`'s FR1/FR2
method — two fixtures identical apart from line count (8 vs 40), so every shared prologue and
epilogue cancels and the slope is one loop body. The parallax twin is
`tools/parallax_cost_probe.py`, which is what produced band drift's 68-cyc/band figure. **This
design ran no emulator and pins no measured number.**

---

## 8. Zone-specific, or general? — the booking's claim is REFUTED by S3K itself

The DoD row says *"Zone-specific by the survey's own estimate"*. S3K disagrees, in its own source
tree:

- **`LBZ2_Deform` (`sonic3k.asm:111651` onward) is the same mechanism with different parameters.**
  Same three-instruction remap kernel (`move.b (a6)+,d3 / add.w d3,d3 / move.w (a5,d3.w),(a1)+`,
  `:111674-111680`), same in-place forward permute, same above/below arms. What differs is
  arithmetic: `$40` instead of `$60` for the clamp and the row base, `lsl.w #6` (×64) instead of
  HCZ's ×32-plus-×64 (×96), a window at `HScroll_table+$09E` instead of `+$0DA`, and its own table —
  `LBZ Waterline Scroll Data.bin`, **4,160 bytes = 65 rows × 64**, exactly the `(H+1) × H` shape
  §6.1 predicts at `H = 64`.
- **Both halves travel.** LBZ2 has `ArtUnc_AniLBZ2_WaterlineBelow` / `Above` and its own art gather
  (`sonic3k.asm:54696`, `:54732`).

So the shipped game has **two** zones, at **two** different band heights, on **one** parameterised
mechanism. "Zone-specific" describes the *ladder table and the art*, which are content, and not the
mechanism, which is a band property with two numbers in it.

**And it generalises past water.** The mechanism is "a band whose output lines are re-fetched
through a viewpoint-selected index ladder". Water is one reading. A receding floor, a heat-haze
horizon, a mirror, or a cylinder seen edge-on are the same operation with a different ladder. The
`band_remap` tail of §5.3 names nothing aquatic, deliberately.

**Update the DoD row.** The size estimate (**L**) survives — §10's ladder is four parcels — but the
justification does not.

---

## 9. How an author and a reviewer SEE it

The owner's complaint tonight was legibility: *"there's like 6 in 1 section and I don't know what
I'm looking for."* And tonight's reels demo was bound to a scene where per-column vertical scroll is
off, so the hardware discarded every value it wrote. Both apply here directly.

### 9.1 Four preconditions, and what asserts each

| # | precondition | why | what asserts it |
|---|---|---|---|
| 1 | **The remapped band's source values must NOT be constant.** | **Remapping a constant is the identity.** A flat band (`.lp_flat`, one broadcast value) remapped by any ladder produces byte-identical output. The effect is then *structurally invisible* — not subtle, not faint, absent. | A comptime `ensure` in `layer()`: a `rowRemap` requires the same layer to carry a `curve` **or** a live `deform` amplitude. **This is the single most important assertion in the design** and it is exactly tonight's reels class. |
| 2 | The scene must declare an anchor (`pcfg_anchor_ch != PARALLAX_ANCHOR_NONE`) and the channel must be seeded (`patch_world_ys[ch]` not `$7FFF`). | §5.5's selector reads `Effects_World_Y[ch]`. An unseeded channel is `$7FFF` = 256 lines down the level; the remap would sit permanently clamped at zero height. | `scene()`-level `ensure`; the generator refuses a `rowRemap` without an anchor. |
| 3 | The band must be a **Plane B** band. | §5.2 — only BG words are remapped, by refusal, not by omission. | No field exists to say otherwise (`band_drift`'s pattern). |
| 4 | **The bound section must permit vertical camera travel across the anchor line.** | The effect is a function of camera Y *only*. In a section the camera crosses horizontally, it is a still picture. Nobody will find it. | Not machine-checkable — it is a binding-review question. It goes in the gate's OUTPUT as a printed line, not as a pass/fail. |

Precondition 1 is the one that would otherwise be discovered on hardware after a day of work.

### 9.2 The static tell — what a gate can read

A remapped band's `Hscroll_Buffer` BG words have a property no other loop can produce: **a repeated
value adjacent to a skipped one.** `.lp_flat` produces all-equal, `.lp_curve` produces strictly
monotone with a bounded step, `.lp_both`/`.lp_bg` produce a bounded-amplitude wave around a base.
Only a remap produces a run where `bg[i] == bg[i-1]` **and** elsewhere `|bg[j] - bg[j-1]|` exceeds
the band's own curve step.

`tools/row_remap_gate.py` should, on every canonical sonic4 build:

1. read the emitted ladder out of the built ROM via the `.lst` and assert it is (a) the declared
   `(H+1) × H` size, (b) monotone non-decreasing per row, and (c) **`table[i] >= i` for every entry
   of every row** — §1.1's in-place-safety invariant, which is a correctness property and not a
   style one;
2. assert every band carrying a `band_remap` tail also carries a curve or a live deform amplitude
   (precondition 1, checked in the ROM rather than only at comptime);
3. **print** which section each remapped band is bound to and whether that section's camera path is
   vertical — informational, for precondition 4.

Steps 1 and 2 need no emulator. Step 3 is a binding report.

### 9.3 The motion tell — what the reviewer does

**Stand still and it is a photograph. That is correct behaviour and it is also how this effect
disappears from a review.** The reviewer instruction has to be a *verb*:

> Enter the section and move the camera **vertically** through the anchored line. The background's
> horizon should compress toward the waterline as you approach it, hold at the crossing, and expand
> again on the far side. If it looks like a normal parallax band that simply scrolls, one of §9.1's
> four preconditions is unmet — check precondition 1 first.

A witness (`tools/row_remap_witness.py`, the `sec5_band_witness.py` shape) can automate the
discrimination without a human: run N frames with the camera driven vertically, hash
`Hscroll_Buffer`'s BG window each frame, and assert (a) the hash changes, and (b) at at least one
frame the window contains a repeat. Both are things a plain band cannot do. Note the lesson
`reels_witness.py` learned today: **derive the expected frame count from `Lag_Frame_Count`, not from
the number of frames requested.**

### 9.4 Composition — how this coexists with the existing writers of the same buffer

The brief's warning about `OJZ_Reels_Fill` clobbering `Parallax_Update`'s column-19 borrow is a
live bug, **confirmed structurally in this pass**: `OJZ_Reels_Fill`
(`games/sonic4/data/effects/ojz_effects.emp:1739-1773`) is called from `ojz_scroll_test.emp:1300-1316`
*immediately after* `Parallax_Update`, and its `.col` loop runs all 20 pairs, writing pair 19's BG
word at buffer offset **78** — which is exactly `VSCROLL_COL19_BG_OFF`
(`parallax.emp:735`, pinned `== 78`), the slot `Parallax_Step5_Vscroll`'s `.col19_borrow_normal`
(`parallax.emp:2554-2566`) had written `camY` into a few instructions earlier. The file
*acknowledges* the artifact at `:1728-1731` but frames it as "not participating" rather than as
destroying a repair that had already been made.

The design's answer is to **not be in that position**:

- The remap writes `Hscroll_Buffer` (per-line HScroll), **not** `Parallax_Vscroll_Column_Buf`. It is
  not a writer of the buffer the reels bug is about, so it does not inherit that hazard.
- Within `Hscroll_Buffer` it is **inside `Parallax_Fill_PerLine`**, as a band's own second pass —
  not a later, outside pass that overwrites what the pipeline produced. That is the structural
  difference between `.lp_remap` and `OJZ_Reels_Fill`: one is a stage of the pipeline, the other
  runs after it and does not know what it is undoing.
- **Do not implement half 1 as a post-pass over `Hscroll_Buffer` from outside `parallax.emp`.** It
  would work, it would be shorter, and it would be the reels bug again.

---

## 10. Parcel ladder

| # | parcel | size | bytes | notes |
|---|---|---|---|---|
| **9a** | Engine: `band_remap` tail, `CAP_ROW_REMAP`, `.lp_remap`, the §5.5 selector, hand-authored on one OJZ section behind DEBUG | **M** | **yes, and NOT zero** — `BAND_REMAP_N` 0→1 is engine-wide and widens `band_record` for `demo` too; every ROM moves | Pairs with sigil. Land the mechanism at `BAND_REMAP_N = 0` first if the two can be separated, per `band_drift`'s banner: *"the mechanism moves no byte, adoption does."* |
| **9b** | `tools/gen_row_remap_ladder.py` + `tools/row_remap_gate.py` (§9.2) | **S** | no | The gate's invariant checks are worth more than the generator; write the gate first and hand-check one ladder against it. |
| **9c** | Authoring: the `rowRemap` layer key in `tools/effects_gen.py` + the hub schema CR (§11) | **M** | data only | Blocked on the hub CR the same way items 3 and 5 were. |
| **9d** | **DEFERRED — the art half** (§6.2, §6.3) | **L** | — | **Blocked on `bg_region` at 448/448 and on OJZ having no water art.** Same wall as item 8's on-screen half. Do not start it; book it against the next art pass. |
| **9e** | **NOT ITEM 9 — family B, `OP_RUN_TABLE` (§5.6)** | **S** | yes | The vertical row remap the item's *name* describes, and the one four references actually do. ~284 cyc/line derived, 4 instructions, reuses the whole dense-tier state. **Only on the owner's ask** — it is a different effect wearing this item's name. |

**What I would build first:** 9a, hand-authored, on the one OJZ section that already has an anchor
channel — with §9.1 precondition 1's `ensure` written *before* the loop, because that is the
assertion that decides whether anyone can see the result.

**What I would defer:** 9d, without hesitation, and 9c until the hub has ruled. The effect is worth
shipping with only its scroll half: §1.6's costing shows the scroll half is 30% of S3K's own work
and the parallax compression is the part that reads as perspective. The art half is what makes the
*surface* recede; the scroll half is what makes the *world behind it* recede.

---

## 11. The author-facing document, proposed

### 11.1 It is a SCENE key, not a preset key — and that is a real ruling

The hub's `aurora-effects-preset.schema.json` has a top-level `oneOf` over `bands | ramp |
base_swap`, and its own description gives the reason: *"all three lower into the same
`EffectsPreset.ep_raster` channel and no combinator exists"*. **A row remap lowers into
`parallax_config`'s band array, not into `ep_raster`.** Putting it in the preset document would
either break that `oneOf`'s invariant or join a mutual exclusion it has no reason to be part of.

It belongs in `aurora-effects-scene.schema.json`, as a **layer** key, beside `drift` and `fb`.

### 11.2 The shape

```json
{
  "top": 1216,
  "fb": "FACTOR_1_4",
  "curve": { "...": "required — see the MUST below" },
  "rowRemap": {
    "ladder": "waterline_96",
    "height": 96,
    "anchor": 0
  }
}
```

| key | type | meaning |
|---|---|---|
| `ladder` | string, `^[a-z][a-z0-9_]{0,31}$` | names a **generated** ladder artifact (`tools/gen_row_remap_ladder.py` → `games/sonic4/data/generated/`). Not an inline array: it is 9,312 bytes and no author types it. |
| `height` | integer | the band's maximum remapped height in lines, and the ladder's row width. The generator refuses a `height` that disagrees with the named ladder's own width — one number, two consumers, checked once. |
| `anchor` | integer 0..3 | the patch channel supplying the waterline. The same index space as `patch_world_ys` in the preset document. |

**Three states, the house rule** (`variants`/`patch_world_ys` precedent): key absent = no remap and
the section keeps whatever it had; `null` = explicitly off; object = authored.

**The MUST, and it is the one that matters:** *a layer carrying `rowRemap` MUST also carry `curve`
or a live `deform` amplitude.* §9.1 precondition 1 — remapping a constant is the identity, and the
schema is the one refusal an author meets. State it in the schema **and** re-state it as an aeon
`ensure`, because the schema cannot see a hand-authored scene.

**What the schema must NOT offer:** a per-line index array. `band_remap` carries a ladder pointer
and a height; there is no field a per-line list could reach, and a control offering one would write
what the engine cannot honour — the exact sentence the hub wrote for `ramp`.

**Gating**, stated because `ramp` and `base_swap` differ here and nobody should assume by analogy:
a `rowRemap` renders only in a game whose `Game.SCANLINE_CAPS` declares `CAP_ROW_REMAP`, so the
generator MUST re-emit that `ensure` at the call site (`.emp` free names resolve where a `comptime
fn` is CALLED — `docs/EMP_PITFALLS.md` #2/#9, the trap item 6 hit before it read the file).

**This document proposes; it does not edit.** `empyrean` and `aurora` are read-only here.

### 11.3 ⚠ A STRUCTURAL DOOR THAT IS ALREADY CLOSED, found in this pass

**The only OJZ section with live patch channels is section 0, and section 0 CANNOT bind an editor
document.** `ojz_effects.emp:1345-1360`: a preset document must carry a raster channel, and
`preset()` asserts `ep_raster == 0 || ep_patched == 0` (`engine/effects/preset.emp:153-154`) — NULL
cannot mean "off" while it also means "keep" (ARCH §7.12). Section 0 binds `patched:`, so it has no
free `ep_raster`.

§9.1 precondition 2 requires an anchor. **So a document-authored, anchor-driven water band cannot,
today, be bound to the one section that has an anchor.** Three ways out, none of them free:

1. Seed a patch channel on a section that binds `raster:` instead — the anchor seed
   (`ep_patch_world_ys`) is installed unconditionally and is independent of the raster/patched
   choice, so this may already work. **Check it first; it is the cheap answer if true.**
2. Hand-author the `rowRemap` scene (parcel 9a's route) and skip the document entirely for the first
   binding — which is what item 11a did before its authorable half.
3. A combinator that lets one preset carry both `raster:` and `patched:`. That is a hub-scale change
   and is out of scope for item 9.

This is exactly the "an effect can be structurally invisible where it is bound" hazard the brief
warned about, found one layer earlier than usual: here the binding is not merely ineffective, it is
**unspellable**. 9a lands hand-authored for this reason; 9c must resolve it before it starts.

---

## 12. Open questions

1. **Can the mechanism land at `BAND_REMAP_N = 0`?** `band_drift` did — mechanism first, adoption
   later — and it is the difference between a zero-byte parcel and one that moves every ROM. Needs a
   look at whether the `.lp_remap` dispatch leaf can be gated without the tail existing.
2. **Is `CAP_ROW_REMAP = $0800` still free?** Two lanes claimed bits on this ladder today. Re-derive.
3. **Where exactly does §5.5's selector run?** `Parallax_Update`'s band loop (like drift's
   accumulator) or Step 4b (like the anchored split)? The split already computes `L`; sharing it is
   probably free, but Step 4b runs after the shadow copy and the ladder row must be known before
   `Parallax_Fill_PerLine` dispatches.
4. **Does the anchored split interact with the remap's height?** S3K's band height IS `|d2|`; aeon's
   band top comes from the split. Two sources for one boundary is the kind of thing that produces a
   one-line-off bug (P3 Task 7's whole subject). Rule it before implementing.
5. **Ladder generation formula.** §1.2 shows S3K's is nonlinear and hand-shaped. A build-time
   generator needs *a* perspective model; nothing here says which. Fitting S3K's own table is a
   legitimate starting point and cheap to check (97 × 96 comparisons).
6. **Should the ladder be shared engine-side rather than per-game data?** It is a pure function of
   `H` with no zone content in it (§8). A single `engine/`-side generator with per-game `H` would
   halve the authoring surface.

## 13. Claims in the brief this design was written from — confirmed and corrected

| the brief said | verdict |
|---|---|
| *"the water surface region is drawn by re-ordering, repeating and/or dropping background rows from a table"* | **CONFIRMED, and it is two tables' worth of remap, not one** (§1.1, §1.4). |
| the item's name, *"Hydrocity row remap"* | **CORRECTED. Not a nametable remap** (§1.5, §3). The name describes family B (§2, §5.6), which HCZ is not in. |
| *"price your design in cycles per line and say whether it fits [the 488-cycle scanline]"* | **THE WRONG BUDGET, and that is a finding.** Family A spends zero HBlank cycles (§7.1). Priced against the 128,000-cycle frame instead; it fits with ≈ 95% of the frame to spare even at the tree's worst historical estimation error. |
| *"`RASTER_DENSE_LINE_RAMP_CYC = 304` … the measured cost of the existing dense tier"* | **CONFIRMED** (`raster_dsl.emp:1897`; FR1 3732 / FR2 13460 / slope 304.0 across three boots). Not applicable here; applicable to §5.6. |
| *"10c and 11b are already competing for that one run [`$6000`]"* | **CONFIRMED**, and this item joins neither queue: family A needs zero tiles, the art half needs `bg_region` tiles (§6). |
| *"`Game.SCANLINE_CAPS` is `$00DE`"* | **CORRECTED — it is `$07DE`**, and it is not a scanline count (§5.4). |
| *"Zone-specific by the survey's own estimate"* (the DoD row) | **REFUTED by S3K itself** — LBZ2 runs the same kernel at a different band height with its own `(H+1) × H` table (§8). |
| *"`OJZ_Reels_Fill` overwrites … destroying the column-19 borrow"* | **CONFIRMED structurally**, offset 78 = `VSCROLL_COL19_BG_OFF` (§9.4). Not inherited: this design writes a different buffer, from inside the pipeline. |
| *"an effect can be structurally invisible where it is bound"* | **CONFIRMED and extended.** §9.1 precondition 1 (remapping a constant is the identity) is this design's instance, and §11.3 found a harder one — the only anchored section cannot bind an editor document at all. |
| *"check the tree's existing design-doc convention"* | `docs/design/` **does not exist**; the convention is `docs/superpowers/specs/<date>-<slug>-design.md`, which is where this file is. |

## 14. What this document did NOT settle

- **No emulator was run and no number in §7 or §5.6 is measured.** §7.2's cycle table is a static
  68000 instruction-table derivation; §7.3 gives the calibration (a sibling design was **57% low**
  on exactly this kind of term six days ago) and the FR1/FR2 method that would settle it.
- **Nobody has seen this effect in aeon.** Every claim about how it *looks* is transferred from S3K
  and from the s3unlocked write-up, neither of which is this engine.
- **The art half (9d) was priced and ruled OUT of BgAnim, but not designed.** §6.2/§6.3 name the
  blocker and the correct mechanism; they do not specify the gather, the staging buffer or the DMA
  budget it needs.
- **`demo`'s price for `BAND_REMAP_N = 1` is asserted by analogy with `band_drift`, not measured.**
  Whether the mechanism can land at `BAND_REMAP_N = 0` (§12 Q1) is the difference between a
  zero-byte parcel and one that moves all four ROM images.
- **§11.3's way out #1 is untested.** Whether a section binding `raster:` can carry a seeded patch
  channel is a ten-minute check that would decide 9c's shape, and this pass did not run it.
- **The ladder generation formula is not chosen** (§12 Q5). §1.2 shows S3K's is nonlinear and
  hand-shaped, and shows a Bresenham walk is not enough — it does not say what is.

## 15. Doc sync — what this design would change if 9a lands

Named now so a later parcel does not have to guess, and **nothing below is done in this pass**:

- **`docs/DEFERRED_WORK.md`** — item 9's one-line table row is replaced by a real block in this
  commit (the design's own deliverable). A landing parcel appends its own `## ALL-CAPS CLAIM` block
  under it with the four-shape byte totals.
- **`docs/ENGINE_ARCHITECTURE.md` §4.6** — one paragraph after "Band drift", in that section's
  established shape: the tail, the loop, the selector's two terms, the capability bit, and the
  precondition-1 refusal. §4.6 is the source of truth for the parallax runtime and a seventh line
  loop belongs in its loop roster.
- **`engine/level/parallax.emp:2652-2671`** — the "IT WAS FOUR UNTIL P3 TASK 10" banner and the
  five-loop roster. That comment already carries a warning about a stale count in a banner being
  read as a measurement; a seventh loop must update it in the same commit.
- **`tools/EFFECTS_CONSUMER_CONTRACT.md` §2** — the `rowRemap` key's obligations, if 9c lands.
- **NOT touched:** `empyrean`'s schemas and `aurora`'s tree. §11 proposes; the CR is the hub's.
