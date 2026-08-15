# Parcel W — one world anchor, two readers (design)

**Status:** DESIGN, revision 2, 2026-08-15. Lens-swept and adjudicated; ready for a plan.
No code beyond W0, which shipped separately (below).

**Review provenance.** Revision 1 was reviewed by three adversarial lenses (two Opus, one Fable)
covering runtime correctness, authoring surface + guard liveness, and premise + gate honesty. They
returned 26 findings, **eight design-changing**, and all three independently found the same fatal
defect (§3.3). Three of revision 1's claims were false and are corrected in place: the consumer
count (§1), "one number moves both" (§4), and "generalises without redesign" (§7). Three decisions
went to a Fable adviser and are recorded at §8. A reference sweep
(`docs/superpowers/notes/2026-08-15-parcel-w-water-anchoring-research.md`) then **replaced the core
mechanism** — see §3.

**W0 already shipped**, as its own micro-parcel by adviser ruling: `Effects_World_Y[]` is now
total-bound. Evidence `docs/benchmarks/effects-p3-w0/GATE-EVIDENCE.md`, aeon `7f60f728` / sigil
`b14564d3`, chain 121. W depends on it and must not re-litigate it.

---

## 1. Entry facts, re-derived against the tree

| claim | proof |
|---|---|
| the FG deform wave is already layer-anchored | `parallax.emp:937-944` folds `Camera_Y` into the sample index |
| the BG deform wave is too | `parallax.emp:957`, `:973` add `Parallax_Current_Vscroll_BG` to the phase base |
| band tops are Plane-B cell rows, rotated by BG vscroll each frame | `parallax.emp:611-625`, rebase + clamp `:659-677` |
| the raster patch channel is act-space world Y, converted once | `raster.emp:892-894` |
| `Effects_World_Y[4]` has **two readers and two writers**, one of them a test | readers `raster.emp:881`, `ojz_scroll_test.emp:419`; writers `preset.emp` (the W0 seed), `raster.emp:923` |
| one preset already binds both sides | `preset.emp:56-65` — `ep_parallax` and `ep_patch_world_ys` in one struct |

The "four consumers, all in `raster.emp`" claim inherited from the stopped brief is **wrong**, and
the distinction matters: W adds a *reader*, and the reader/writer split is what makes W0 a
prerequisite rather than a nicety.

## 2. What W is, and what it is not

**Not:** giving the deformation wave a world anchor. It has one (Harmony defect #2, fixed at
`parallax.emp:937-944`). The work order's supporting citation is also wrong — see §9.

**Is:** making a palette boundary and a shimmer boundary land on the **same scanline**, driven by
one anchor. Today they are computed in different spaces:

| | raster patch channel | parallax band top |
|---|---|---|
| authored in | act-space world Y | Plane B cell row 0..63 |
| granularity | 1 scanline | 8 px |
| wraps | no | yes, every 512 px |
| follows | `Camera_Y` 1:1 | `Vscroll_BG` = camera × BG factor |

**The last row is not a conflict**, which is where the stopped brief went wrong. "Where does the
region start" and "what art does the wave ride" are independent quantities, held in different
registers in the same loop: the band top is `d5`, the wave phase is `d2`/`d6`
(`parallax.emp:898-1082`). Lens C verified this by tracing the sample index — it is
`table[(phase + vscroll + screen_line) & $FF]`, so moving a band's top changes only *which band's*
shift applies to the line that crossed, and never what the wave samples at a given piece of art.
Anchoring a boundary to the camera therefore cannot re-open defect #2.

So the answers to the three questions that stopped this parcel:

1. **Authoritative space:** act-space world Y in `Effects_World_Y[ch]`. Each consumer converts to a
   **screen line** at read time — the only space the two genuinely share. Plane space stays private
   to plane-anchored bands.
2. **The 8-px mismatch:** deleted, not tolerated (§3.2).
3. **BG factor ≠ 1:** the boundary follows the camera 1:1 because a water surface is a feature of
   the LEVEL; the art inside keeps riding its own plane at its own factor, and the wave inside keeps
   folding `Vscroll_BG` into its phase. Nothing is constrained to factor 1.

## 3. The mechanism: an ADDITIVE OVERLAY, not a band

Revision 1 proposed a *terminal anchored band*: truncate the rotated shadow list at the anchored
line and append one band owning the screen below it. **That is replaced.** The reference sweep found
Ristar solving exactly this problem, and solving it better: the water surface is not a list entry at
all but a predicate on the running screen-line counter that **adds** a ripple to the other plane's
word (`ristar_disasm/code/disasm.asm:24648-24657`), driven by one world-Y-minus-camera scalar that
*also* arms the HInt palette split (`:16187-16201`) — one number, two boundaries, which is this
parcel's exact goal.

Truncation was worse on three counts, and one of them was self-contradiction:

- it **discards** the plane bands below the surface, so multi-strata underwater backgrounds (the
  crown roadmap's stated model, HCZ) become inexpressible;
- it forces everything below the surface onto ONE scroll factor, contradicting §2's own answer 3;
- it needed a new band record in the config, which dragged in wrapper shapes, a `band_count`
  ↔ array-length tie, a `pcfg_layer_mask` bit to keep in sync, and an extra Step-3 accumulator —
  three separate lens-flagged hazards.

**The overlay, adapted to Aeon's band pipeline so it costs nothing per line** (Ristar pays a compare
per scanline; we do not have to). In Step 4a, after the rotation has written the shadow view:

```
if pcfg_anchor_ch == $FF             -> done; today's path, byte-identical
L = Effects_World_Y[ch] - Camera_Y   (signed word; may be negative, meaningfully)
clamp L into the channel's legal band (§3.1), then into [0, 224]
if L >= 224 -> off-screen below: shadow untouched
else:
    SPLIT the shadow band containing L into two entries at line L   (insert, not truncate)
    from the inserted entry to the last band, OVERWRITE band_deform_shift_a/b
        with the config's anchored shifts
```

Bands below keep their own scroll factors, so strata survive. The shimmer starts at the
world-anchored **scanline** and runs to the bottom. Fully submerged falls out for free: `L <= 0`
clamps to 0, the insert lands at index 0, every band gets the shift — which is S3K's
`Water_full_screen_flag` state (`sonic3k.asm:8496-8505`) arrived at structurally instead of as a
special case.

**Storage: zero added bytes.** `parallax_config` has exactly three spare bytes and this needs three:
`pcfg_pad` (`structs.emp:171`) takes `pcfg_anchor_ch` (`$FF` = none); `pcfg_pad2` (`:177`) takes the
anchored `deform_shift_a` / `deform_shift_b`. `sizeof(parallax_config)` stays 28, which is required
— `parallax.emp:95-96` ensures it stays EVEN or `copy_band_entry`'s `move.l` run address-errors.
Both pads have one writer (`configs.emp:72`, `:78`) and zero readers.

The split adds one shadow entry, so `Parallax_Shadow_Bands` must hold `band_count + 1`; the live
guard becomes `band_count + 1 <= MAX_PARALLAX_BANDS` (8). `ram.emp:266` reserves
`[u8; BAND_ENTRY_LEN * MAX_PARALLAX_BANDS]`, so a config using all 8 needs the reservation raised or
the guard to bite — the guard is the cheaper answer and it evaluates over ints in `hdr()`.

### 3.1 The clamp is ONE fact, read from the raster table

The raster patcher clamps every patched fire line to that record's authored band
(`raster.emp:895-901`), and that clamp is load-bearing rather than cosmetic: a negative inter-record
gap would store `$FF`, which IS the park word, killing every remaining fire in the frame
(`raster.emp:866-869`). If the overlay clamped only to `[0,224]`, then outside the record's band the
palette boundary would pin while the shimmer kept moving — **the two boundaries separating, which is
the defect this parcel exists to remove.** Not hypothetical: `ojz_effects.emp:557` documents channel
0 clamping "once the camera descends past world Y 184", reachable by ordinary scrolling.

Two authored copies of the band (one in `patchable`, one in the config) were rejected: a shared
comptime const is still two numbers that agree only while every author remembers the const, which is
the failure mode `parallax.emp:64-81` exists to preach against.

**Instead the overlay reads the raster patch table's own band words.** P-a already emits
`[arm_off][line_src][band_lo_fl][band_hi_fl]` per record with the channel in `line_src`'s low bits
(`raster.emp:863`, `:889-890`). A narrow raster-owned accessor — `Raster_GetChannelBand(ch)` —
walks that small table and returns the pair; the overlay clamps `L` to `[lo_fl+1, hi_fl+1]`, with
the `+1` living in `raster.emp` beside `:894`'s `-1` so both conversions are one file's fact.
Changing the band in the raster DSL then moves both boundaries' clamp, always, with no second author
action possible.

Degenerate cases fall out semantically rather than by special case:

- `Raster_Patch_Tab == 0` (an anchored section with no patched program — legitimised by W0) means
  there is no palette boundary to diverge from, so no clamp: `[0,224]` is correct there.
- No record for `ch` in the table: same.
- A section crossing reads the outgoing program's ROM band for one frame — the same accepted
  one-frame class as W0's, and the pointer read is a single `move.l`, so never torn.

**Honest limit:** clamped-at-edge makes the two boundaries *consistent*, not *correct*. Both pinned
at the band edge while the true surface is off-screen is still wrong versus reality; the real fix is
S3K's whole-screen state, and it stays separate future work.

### 3.2 The shadow band view measures in SCREEN LINES

Prerequisite for a scanline-exact boundary. The shadow view is rebuilt every frame and read by
exactly two routines (verified — nothing in `engine/buffers` or elsewhere touches it). Its top byte
changes unit from screen cell (0..28) to screen line (0..224); both fit a byte, so no storage moves.

- `parallax.emp:659-677` (rebase): keep the clamp in CELLS at 28 — that clamp is what stops the
  filler overrunning `Hscroll_Buffer` — then `lsl #3` to lines before the store.
- `Parallax_Fill_PerLine:915`: delete its `lsl.w #3` on the peeked next top.
- `Parallax_Fill_PerCell:1104`: add `lsr.w #3` on the peeked next top. `.last_band_end`'s
  `moveq #28` is already in cells and **stays** (`224 >> 3 == 28`; revision 1 called this a change,
  which was wrong).
- ROM data is untouched: `band_entry.band_top_cell` keeps its name and its plane-cell meaning. The
  shadow readers get a `band_top_line` alias const at the same offset, so the unit is in the
  identifier at each site and grep separates them. (Revision 1 proposed renaming the field to
  `band_top`, giving one name two units — worse than the status quo.)

### 3.3 The fatal defect all three lenses found: `.lp_flat`

`Parallax_Fill_PerLine`'s flat path is 8× unrolled on a **documented invariant that every band span
is a multiple of 8** (`parallax.emp:1049-1054`: *"tops are Plane-B cell rows scaled ×8 … So
`span >> 3` is exact — no remainder tail"*). It does `lsr.w #3` / `subq.w #1` / `dbf`.

An anchored line is an arbitrary scanline, so the band above it gets an arbitrary span — and that
band is exactly the one authored with `deform_shift = 15` (off), which is the condition routing it
into `.lp_flat` (`:926-931`, `:960-966`). Two failures:

- **span 1..7:** `lsr #3` → 0, `subq #1` → `$FFFF`, and `dbf` runs 65,536 times × 8 longwords ≈
  **2 MB sprayed past `Hscroll_Buffer`** — the frozen-VDP crash class the Step-4a clamp comment at
  `:618-622` exists to prevent. Revision 1's own gate case `L = 1` was the crash trigger.
- **span 9..15, 17..23, …:** writes `8·floor(span/8)` longwords while setting `d4 = d5`, so `a4` and
  `d4` desync permanently, every band below lands at the wrong buffer offset, the buffer under-fills
  and the boundary sits up to 7 lines above `L`.

**Fix:** give `.lp_flat` a remainder tail — whole groups through the unroll, then a per-line tail,
with the zero-remainder case branched around (a bare `subq/dbf` on a zero count re-creates the same
65,536-iteration bug). `d2`/`d3`/`d6` are dead on the flat path, so a counter register exists. The
×8 claim in the comment is retired and replaced with why the tail is there.

This lands as its own task with its own test (spans 1..7 and 9..15), **before** anything can produce
an arbitrary span.

### 3.4 The splice must move the scroll words too

Step 4a writes the shadow scroll arrays in rotated source order (`parallax.emp:679-684`), and the
fillers walk band entries and scroll words in lockstep (`addq.l #2,a2 / addq.l #2,a3` beside
`lea sizeof(band_entry)(a1),a1`). Inserting an entry without inserting into
`Parallax_Shadow_Scroll_A/B` at the same index makes every band below the split scroll at its
neighbour's rate. Under the overlay the inserted entry **duplicates its parent's** scroll words,
which is both correct (it is the same band, split) and cheap (one word each).

### 3.5 Mode selection must know about anchoring

A scanline-exact boundary requires per-line fill, selected today by either deform table being
non-NULL (`parallax.emp:699-701`), with a **twin** key on the same fields choosing the HScroll DMA
length (`buffers.emp:259-261`). Revision 1 proposed a comptime ensure "an anchored config must
declare a deform table" — that is the `Label`-vs-int construct `preset.emp:105-111` has already
ruled **unevaluable and silently always-passing**, i.e. a vacuous guard.

Instead both keys also test `pcfg_anchor_ch != $FF`. Unrepresentable beats checked, and the two keys
must change together or a mode-differing config ships a cell-length DMA for a line-mode buffer.

### 3.6 The unseeded-anchor default

`preset()` defaults `patch_world_ys` to `[0,0,0,0]`, and after W0 those zeros are really written. A
zero anchor under the overlay means `L = -Camera_Y <= 0` — "fully submerged" — which is the wrong
safe default. It becomes a large positive sentinel (`$7FFF`, chosen so `L` stays positive and lands
in the `>= 224` off-screen branch without a sign flip). W0 deliberately left this alone because W
introduces the reader that gives the value meaning.

## 4. What the author writes

One anchor value, read by two consumers. The channel is named where each consumer is authored —
the raster program's `patchable(fires, ch, lo, hi)` and the config's `pcfg_anchor_ch` — and
revision 1's claim that this is "ONE number moves both" was **false**: it is one *anchor*, with the
channel named twice. What is genuinely one fact is the anchor value and, after §3.1, the clamp band.

```
preset(pal: OJZ_Palette,
       parallax: OJZ_UnderwaterConfig,   // anchor_ch: 0 + anchored deform shifts
       patched:  OJZ_TwoChannel,         // channel 0 fires the palette boundary
       patch_world_ys: [224, 314, PATCH_ANCHOR_NONE, PATCH_ANCHOR_NONE])
```

`Effects_SetWorldY(0, y)` then moves both boundaries on the same frame, to the same scanline.

**This surface is currently unexercised and that is a build obligation, not a footnote.**
`ep_parallax` is 0 in **every** preset in the tree — configs reach the pipeline through
`sec_parallax_config` / the act default. `fx_tint_band` shipped broken for two parcels for exactly
this reason, so W ships a preset that binds `ep_parallax` and a section that installs it.

## 5. The gate

Revision 1's gate **could not fail** — it read `Hscroll_Buffer` (CPU RAM) and asserted the boundary
equalled `Effects_World_Y - Camera_Y` and the raster fire line + 1, but `raster.emp:893-894` *defines*
the fire line as screen line − 1, so both sides came from one formula in RAM and no pixel was ever
observed. Corrected on four axes:

1. **Observe VRAM, not RAM.** Read the HScroll table in VRAM, so an implementation whose buffer is
   right but whose DMA never lands cannot pass.
2. **Predict `L` from authored constants** (world Y 224, camera pinned by `Debug_Scene_Freeze`),
   never read back from `Effects_World_Y` — otherwise it is the same circularity with extra steps.
3. **Bracket the palette leg in time:** assert the base palette at line `L−1` **and** the changed
   palette at `L`, on the CRAM lines the program actually writes. "Changed by line `L`" alone passes
   for any boundary above `L`. First verify by hand that a mid-frame `run_to_scanline` + `read_cram`
   shows the HInt write at all, and whether the stop is before or after that line's HInt — oracle's
   CRAM reads are frame-latched, and the failure direction is loud-on-correct-code, not vacuous.
4. **Bracket the scroll leg in space and time.** The split entry inherits its parent's scroll, so
   the words at `L−1` vs `L` differ only by the ripple sample, which crosses zero — a single-line
   diff can read 0 on a correct implementation. Compare the below-`L` region against a no-anchor
   control across two consecutive frames.

Plus, unchanged in intent: **§3.2 is output-neutral**, proved by hashing `Hscroll_Buffer` over a
scripted scroll across exactly that commit (so it must be its own commit — bundled with §3.3 the
hashes are not attributable); and the clamp edges proved by inversion plus the adjacent legal case.
Note the neutrality gate passes a no-op by construction: it proves the refactor, never the feature.
The feature's teeth are entirely in the observation gates above.

## 6. Task order

W0 shipped. Then, each its own commit:

1. **`.lp_flat` remainder tail** (§3.3) + span tests. Output-neutral; lands before anything can
   produce an arbitrary span.
2. **Shadow view in screen lines** (§3.2) + the `band_top_line` alias. Output-neutral; its hash gate
   straddles exactly this commit.
3. **`Raster_GetChannelBand`** (§3.1), with no consumer yet — plus a call site, because an
   uncalled `pub proc` cannot pin its contract (the `Effects_SetWorldY` precedent, P-b §6).
4. **The overlay** (§3, §3.4, §3.5, §3.6) + the fixture preset that binds `ep_parallax` (§4).
5. **The gate** (§5).

The risky piece is last and sits behind two proven-neutral refactors.

## 7. What this parcel does NOT do

- **No structure-below-the-surface limitation** — that was revision 1's terminal band, and removing
  it is the main reason the overlay won.
- No second anchored region. Revision 1 claimed the mechanism "generalises without redesign"; for
  truncation that was **false** (terminality was baked into truncate-and-append). For the overlay a
  second region is a second split plus a second shift-overwrite range — genuinely additive, but out
  of scope and unbuilt until something needs it.
- No change to deform phase anchoring. Defect #2's fix is untouched, and §5's neutrality gate is
  what proves it.
- No mid-frame writes. Step 4a runs in the main-loop parallax update where the rotation already
  runs; P-b's VBlank ruling concerns the raster buffer's relative arm words and does not reach here.
- No whole-screen palette state (§3.1's honest limit).

## 8. Decisions taken to a Fable adviser, 2026-08-15

1. **The clamp** — ruled: derive it at runtime from the raster patch table via a raster-owned
   accessor (§3.1), rather than duplicating the band into the config or documenting a hole. Because
   a shared const is still two numbers that agree only by convention, and the "documented hole"
   option ships the separation defect on the fixture's own reachable scroll path — a gate proving
   the divergence would be certifying the defect.
2. **W0** — ruled: its own micro-parcel, merged first, with an inversion probe; and the
   `Raster_Patch_Tab` clear must precede the **seed**, not sit on the `.no_patch` branch, because
   `Effects_InstallPreset`'s palette work sits between them and a VBlank lands in that window
   routinely. Shipped as ruled.
3. **The gate** — ruled: RAM-only observation is vacuous; see §5.
4. **The overlay mechanism** (asked after the reference sweep) — ruled right and explicitly not
   gold-plating, on the grounds that it is simultaneously more capable and cheaper, and that it
   resolves revision 1's internal contradiction between its terminal band and its own §2 answer 3.

## 9. A correction to the work order

The order justifies W with: *"S3K anchors ripple phase to world quantities in three separate places
precisely because a wave keyed to a frame counter slides when the camera moves."* **S3K has no
per-line water ripple at all** — HCZ's waterline is DMA'd tile animation
(`sonic3k.asm:53970`, `:54000`), and the S1 ripple table is a dead leftover the disassembly comments
on (`:33449-33450`). The S1/S2 ripple that does exist is indexed by the frame counter alone
(`s2.asm:15285-15302`), i.e. screen-anchored — it is the defect, not the model. Aeon's camera-folded
phase is ahead of all four Sonic references, and W must not touch it. Full sweep:
`docs/superpowers/notes/2026-08-15-parcel-w-water-anchoring-research.md`.
