# EHZ diagonal lag regression: bisect and mechanism (2026-09-25)

Research parcel. No engine or game change is landed on this branch. The question: the Sonic 2
clip act's "fly diagonal, Emerald Hill band" leg (camera y < 1024) measured **26/82**
lag/video frames right after the S2CLIP-LAG fix landed (`8939377f`) and **44/100** in the perf
survey (`09185beb`, clip DEBUG crc `c7d567ab`). Which commit did it, and why?

**Answer.** The first bad commit is **`ed48f9a9`**, the S2CLIP-ORIGINAL-BGS **B-2** landing. It
is a **content** change: the bake binds Emerald Hill's region preset to EHZ's own Sonic 2 scroll
record. No engine code changed. That record costs `Parallax_Update` **+8.1k cycles/tick** in the
band (8.8k → 16.9k) and accounts for **+14** of the 18 lag frames on its own (26/82 → 40/96).
The other +4 appear later: +3 at `9acc5120` (CPZ widened to 4,576 px plus rule-B) and +1 at
`64ab0221` (short-tunnel adoption). **Neither of those adds any lag without B-2's record.** On
today's ROM, unbinding the EHZ record (4 bytes) gives exactly **26/82** again, so all 18 frames
depend on it. The camera path is the same at every point (56 logic ticks in the band). The
82 → 100 change in video frames is just the 18 extra lag frames.

A prototype engine fix (an exact, cheaper per-line curve loop) takes today's ROM from **44/100
to 35/91**, with identical HScroll output. It is not landed (see "Fix options").

## Method

- **Probe.** The perf survey's `leg_probe.py` and the S2CLIP-LAG study's
  `lag_flythrough_probe.py`, unchanged except one line: `TOOLS` points at this worktree's
  `tools/`, because the copies ran from a scratch directory. Leg: `--mode fly --dirs right,down
  --frames 2000`, which is the survey's `clipdbg_diag` leg. The EHZ band is the rows with camera
  y < 1024. Each row is one video frame, and band lag = Σ dFrame_Counter − Σ dLogic_Tick over
  those rows (`band.py`). Profiles use `--profile-window 0,<band rows>`, so the profiler covers
  exactly the band. The 64 KiB reader-limit raise is the survey's, reused.
- **Builds.** Each bisect point is a detached `git worktree` under
  `/home/volence/sonic_hacks/.aeon-ehzbis-<L>`. In each one I ran `s2_zone_convert.py convert
  s2disasm@EHZ` and `@CPZ` (0 differing, 0 FAILED at every point) and then `S2CLIP=s2_ehz_cpz
  DEBUG=1 ./build.sh` with today's `SIGIL_BUILD`/`SIGIL_EMIT` (`build_point.sh`). Every point
  built with rc 0. `results/build_<L>.summary` holds the head SHA, CRC and rc.
- **Proof of completion.** Every leg wrote a `.meta` with rc, loadavg and `finished=1` (all 25
  in `results/`). The five `hscroll_*` comparisons ran in the foreground with rc 0, and each
  output ends with its own `finished=1` line. Raw rows and profiles are in `results/leg_json.tar.gz`. Lag counts are
  deterministic, and loadavg does not change them. `.pyc` caches were cleared before each run.
  One headless emulator ran at a time. No emulator MCP tool was used.
- **Control first.** `8939377f` rebuilt to crc **`84fe49d0`**. That is the exact crc the
  landing log records as the installed post-fix `s4.s2clip.debug.bin`. It measured **26/82**
  with today's probe and today's `oracle-aether`, whose binary was rebuilt at 14:28 −0400,
  after the 26/82 record. The record reproduces, so the regression is not a probe or emulator
  change. At the other end, `09185beb` rebuilt to the survey's crc `c7d567ab` and measured
  44/100. That matches the survey.

## Bisect table (clip DEBUG, fly diagonal, EHZ band)

The points are master's landing merges on the ancestry path `8939377f..09185beb`. The camera
enters the band at (112,144) and leaves at (992,1008) at **every** point, over 56 logic ticks.
Per-tick camera samples differ from `96dcfc8f`'s at no more than 3 of 56 samples, by one
16-px step (`results/pathcmp.txt`). That is read timing on a frame that ends mid-tick, not a
different path.

| point | commit | clip DEBUG crc (size) | band lag / video | band ticks | band exit | whole leg lag / video (ticks, end) | loadavg start→end |
|---|---|---|---|---|---|---|---|
| A | `8939377f` lag fix (control) | `84fe49d0` (849,349) | **26/82** | 56 | (992,1008) | 40/910 (870, (14016,5920)) | 22.5→21.4 |
| E | `96dcfc8f` CPZ +480 landing | `89aac8a7` (914,923) | **26/82** | 56 | (992,1008) | 40/910 (870, (14016,5920)) | 14.9→14.9 |
| F | **`ed48f9a9` B-2 scroll** | `65d216b4` (914,979) | **40/96** | 56 | (992,1008) | 59/929 (870, (14016,5920)) | 14.2→14.2 |
| G | `9acc5120` rule-B + CPZ 4576 | `8c69555a` (947,980) | 43/99 | 56 | (992,1008) | 59/1057 (998, (16064,5920)) | 9.5→9.3 |
| H | `005accdc` shorter-connector (BG DMA sweep) | `9b65fdf1` (948,046) | 43/99 | 56 | (992,1008) | 59/1057 (998, (16064,5920)) | 9.3→9.4 |
| I | `64ab0221` adopt short tunnel | `c7d567ab` (948,046) | 44/100 | 56 | (992,1008) | 60/1058 (998, (16064,5920)) | 9.4→9.1 |
| J | `09185beb` survey base | `c7d567ab` (948,046) | 44/100 | 56 | (992,1008) | 60/1058 (998, (16064,5920)) | 14.2→13.6 |

Not built: `0d782e70` (tunnel) and `8886d1cc` (anchor overlay). They sit between A and E, which
are identical on the band and on the whole leg, so they cannot hold this regression. `e194de54`
(Z80 tap) is tools only. The whole-leg endpoint moves at G because the act became wider: the
diagonal ends at x 16064 instead of 14016. That changes the whole-leg frame count, not the band.

## Mechanism

### B-2 binds EHZ to a heavier scroll record (content)

Before B-2 both zones "scroll with the act default" (`clip_rom_bake.py`: "NOT HERE: parallax").
That is OJZ's `Scene_OJZ_Default`: four world-anchored flat layers at world y 512 and below.
At camera y < 1024 this puts one or two flat bands on screen. B-2 (`tools/clip_bg_scroll.py`)
derives EHZ's record by running `SwScrl_EHZ`. It has **7 plane-locked bands on screen at once**
(v_factor 15):

| plane lines | band |
|---|---|
| 0–21, 101–111 | still |
| 22–79 | camX/64 |
| **80–100** | camX/64 + **static ripple** (a per-line deform band, `dsb 0`, speed 0) |
| 112–127, 128–143 | camX/16, 3camX/32 |
| **144–223** | camX/8 → 3camX/4, a **per-line curve**, 80 lines |

The engine fills every line with its per-line fill (`Parallax_Fill_PerLine`). A flat line is an
unrolled `move.l`, about 13 cycles. A curve line is the Bresenham loop, about 54 to 60 cycles.
A sampled-deform line is about 38 cycles. Each band also pays two `Decode_Factor` calls and
Step 4's per-band work.

### Profile, band window, cycles per logic tick (`pdiff.py`)

| routine | E `96dcfc8f` | F `ed48f9a9` | Δ |
|---|---|---|---|
| work (sample − `VSync_Wait` incl.) | 136,400 (1.067 fr) | 148,545 (1.162 fr) | **+12,145** |
| `Parallax_Update` incl. | 8,815 | **16,913** | **+8,098** (self +7,499) |
| `Decode_Factor_A`/`_B` calls | 3.93/tick | 6.88/tick | 4 → 7 bands |
| `S4LZ_DecompressDict` | 12,226 (1.07 calls) | 14,151 (1.29 calls) | +1,924 |
| `TileCache_DecompressBlock` calls | 1.45 | 1.79 | +0.34 (see below) |
| `PageCache_Prefetch` scan (idle slot, not in "work") | 6,630 | 13,570 | +6,940 |

### Isolating the record with byte patches (no rebuild; `patch_ehz.py`)

Each patch changes the EHZ record inside the built ROM. The byte offsets are asserted against
their old values first. `np` zeroes `OJZ_Clip_Preset_0`'s parallax pointer, so EHZ falls back
to the act default exactly as it did before B-2.

| variant | on `ed48f9a9` (F) | on `09185beb` (J, today) | `Parallax_Update` incl. (on F) |
|---|---|---|---|
| as built | 40/96 | 44/100 | 16,913 |
| `nc`: curve off (band 144–223 flat at camX/8) | 34/90 | 34/90 | 13,066 (**curve = 3.85k**) |
| `nr`: ripple off (band 80–100 no deform) | 37/93 | 37/93 | 16,216 (**ripple = 0.70k**) |
| `nb`: both off (7 flat bands) | 33/89 | 33/89 | 12,369 (**7 flat bands vs the default = +3.55k**) |
| `np`: **EHZ record unbound** | **26/82** | **26/82** | (default record) |

`np` restores 26/82 on **both** ROMs, and the whole leg too (40/910 on F, the same as E). That
settles the attribution: the record B-2 binds is the whole regression. The curve's 3.85k over
80 lines, less the ~630-cycle band cost, is ~40 cycles per line above a flat line. That agrees
with `docs/benchmarks/scanline-p3/CURVES.md` (40.75 cyc/line).

### The later +3 and +1 are interaction, not separate regressions

- **`9acc5120` (+3).** Work in the band rose +1.5k/tick. `S4LZ_DecompressDict` +1.2k and
  `TileCache_FillColumn` +1.3k: 12 more demand block decodes over the band's 56 ticks
  (`FillColumn` 22 → 29, `FillRow` 37 → 42). The act is wider and was re-baked, so its block
  stream changed. I did not decompose it further. Without B-2's record this extra work adds
  nothing: today's ROM with `np` is 26/82. The band is threshold-bound. At ~1.07 frames/tick
  of work the extra 1.5k does not tip whole frames over, and at ~1.16 it does.
- **`64ab0221` (+1).** Work in the band is identical to H (Δ −2 cycles/tick). The one frame is
  VBlank phase: `VSync_Wait` grows by exactly one frame's worth spread over 56 ticks.

### A secondary feedback: lag breeds block decodes

The camera path per tick is the same everywhere, yet block decodes in the band scale with the
lag: 1.45/tick at E, 1.79 at F, 2.00 at G through J. The prototype ROM P (below) is back to
1.45. At F the extra decodes come from `Tile_Cache_Fill`'s own sites (12 → 41 calls over the
band). Fewer come from `FillColumn` (34 → 22). So part of each lag frame's cost is paid again
as decode work. I did not find where in `Tile_Cache_Fill` the late frame changes the decision.
**Not decomposed; a lead, not a finding.**

## Fix options

Every gain below is on this leg's EHZ band (today 44/100). The upper bound (survey: stub
`Parallax_Update`) is 15/71.

| # | option | cost | measured / expected gain | canonical bytes | risk |
|---|---|---|---|---|---|
| 1 | **Engine: exact fixed-point curve loop** (prototype `curve_loop_prototype.diff`, 11+/19−). The hoist computes `frac = ceil(rem·65536/span)` once per curve band per frame (`divu`, ≤140 cyc). The line loop becomes `move.w d0,(a4)+ / move.w d1,(a4)+ / add.w d3,d6 / addx.w d2,d1 / dbf`, 34 cycles instead of ~54–60 | S–M (code small; the landing ritual is the cost) | **MEASURED: 44/100 → 35/91**, `Parallax_Update` 16.9k → 15.3k (−1.65k/tick), decodes back to 1.45/tick. Unrolled ×2 would save ~5 more cycles/line (not measured) | **yes**: sonic4 folds `CAP_FACTOR_CURVE`, and canonical's editor depth scene has curve layers. Output is proven identical, but bytes move | low to medium. Exactness is proven (below). It touches `engine/level/parallax.emp`, so it needs the effects-gates ritual and `landing_build.sh`. The `divu` needs the §2.1 four-point comment. The `bc_rem` / `Parallax_Curve_Carry+2` meaning changes: CURVES.md and `tools/depth_onset_probe.py` (says it never reads `bc_rem`; re-check) need re-reading |
| 2 | **Content: drop the static ripple band** (EHZ band 80–100 flat). The ripple is static today (speed 0, booked engine gap), so it costs 0.7k/tick for a fixed 0–3 px line pattern | XS (clip_bg_scroll option) | MEASURED: 44 → 37 alone | no (clip only) | owner's look: the static ripple is S2's frame-0 shape |
| 3 | **Content: curve as fewer flat steps** (e.g. S2's own hold groups collapsed to ≤9 extra flat bands, since MAX 16) | S | NOT MEASURED. Bounded by `nc` (44 → 34) minus the per-band cost of extra bands (~0.5k each, from `nb`'s +3.55k over ~6 extra bands, estimate) | no (clip only) | owner's look: stepped ramp instead of S2's pair/triple holds |
| 4 | **Content: drop the curve** (band 144–223 flat camX/8) | XS | MEASURED: 44 → 34 | no | it loses EHZ's defining ground ramp. Listed for scale, not recommended |
| 5 | **Engine: cheaper per-band overhead** (7 flat bands cost +3.55k/tick more than the default's 1–2 on screen) | M | NOT MEASURED: at most ~3.5k/tick | yes | medium: effects gates |

Options 1 and 2 stack. Neither alone reaches 26: B-2's record is real work, and the pre-B-2
band scrolled a cheaper, wrong background. The resident-control floor on this band was 21/77
(S2CLIP-LAG residue 2). Max-diagonal free flight is over budget on every act (ARC-CLOSEOUT).

### Prototype exactness evidence (option 1)

- **Arithmetic, exhaustive** (`curve_exact.py`, `results/curve_exact.txt`). For every span
  1..224, every rem 0..span−1 and every line k = 1..224, the carry sequences are identical:
  **5,644,800 cases, 0 mismatches**. Mutation control: `floor` instead of `ceil` gives
  **206,528 mismatches**. Why it holds: frac − rem·65536/span < 1, so over k ≤ 224 lines the
  fixed-point sum runs at most 224 above the exact one. The exact sum sits at least
  65536/span ≥ 292 below the next multiple of 65536, so the carry never comes early. A split
  layer counts k from the layer start and never exceeds 224 lines.
- **In the emulator** (`hscroll_probe.py`). The whole `Hscroll_Buffer` (224 lines × FG/BG) is
  keyed by camera position and compared between ROMs at every position both ROMs saw.
  - The fly leg is **not** sensitive to this change. Its camera x is always a multiple of 16,
    so EHZ's rem is a multiple of 10 and ceil equals floor. The floor mutant also compared
    equal there (`hscroll_J_vs_Pfloor.txt`, 0 differing), so that result is **not evidence**.
  - The physics run (`--run`: B out of free flight, right, jump every 45) is sensitive. The
    floor mutant (`mutate_floor.py`: `D444 5342` → two NOPs at ROM $825A, crc `14dabf3a`) is
    **RED**: 630 of 1,772 common positions differ (`hscroll_run_J_vs_Pfloor.txt`). The
    prototype `P` (crc `5a4fc938`) is **0 of 1,772** (`hscroll_run_J_vs_P.txt`).
  - Scope: this checks the clip ROM's EHZ curve only. Canonical's curve scenes were not run.
    The effects gates would do that at landing.

**Why it is not landed here.** It is an engine change on a research branch. It moves canonical
bytes. Landing it properly needs the effects-gates ritual, `landing_build.sh`, the `divu`
four-point comment, an ARCH §/CURVES.md update, and a check of the curve-carry readers. That
is a parcel of its own. The diff and every piece of evidence are here, ready for it.

## What I could not measure

- **Where `Tile_Cache_Fill`'s late-frame decode feedback comes from.** It is reported as
  observed above and not decomposed.
- **`9acc5120`'s extra demand decodes.** I did not trace which blocks or sections changed with
  the widening.
- **Options 3 and 5, and an unrolled option 1:** estimates only.
- **Any on-screen look** at options 2 to 4 (they change the picture). That is the owner's call.
- **Canonical OJZ with option 1.** Its curve layers would get cheaper too. Not measured.
- **Release shape:** it has no free flight, so this leg does not exist there.

## Files

The tools are in `docs/research/2026-09-25-ehz-diag-regression/`:

- `build_point.sh`, `run_leg.sh` and `run_rom.sh`. They carry absolute scratch paths from the
  run. Edit them before reusing.
- `band.py`, `pathcmp.py`, `pdiff.py`, `patch_ehz.py`, `hscroll_probe.py`, `mutate_floor.py`,
  `curve_exact.py` and `curve_loop_prototype.diff`.

The results are in `results/`:

- per-leg `.txt`/`.meta` files (all `finished=1`);
- `build_<L>.summary`;
- `leg_json.tar.gz` (25 leg JSONs);
- the `hscroll_*.txt` comparisons, `curve_exact.txt` and `pathcmp.txt`.

## Landed: option 1 (parcel/parallax-curve-loop, 2026-09-25)

Option 1 is now production code in `engine/level/parallax.emp` (`.curve_rem_ok`, `.lp_curve`),
with the `divu.w` four-point argument at the instruction. It differs from the prototype in
three ways: `bc_rem` is renamed `bc_frac` (u16), `bc_span` became an unread spare (the span
store is gone; the tail stays 10 bytes so the record stays a multiple of 4), and nothing
borrows `a0` any more. All ROMs below were built on sigil f52609fe. Evidence is in `results/landed/`.

- **Built-bytes exactness** (`curve_rom_exact.py`). It interprets the hoist tail and the fill
  block straight out of each ROM image and checks every BG word against
  `base + floor(k·spread/span)`. Cases: span 1..224 × every remainder × step 0 and −1, at 224
  lines each (50,400 sequences), plus 20,000 random split/continuation cases. Results: today's
  master (canonical `a0e248e7`, clip `c7d567ab`) 0/0; landed (canonical `831cf561`, clip
  `cf8d5d4a`) 0/0; floor mutant (`mutate_floor_final.py`: canonical `3aec5f08`, clip
  `a8aa93eb`) **48,320/50,400 and 6,797/20,000, RED**. The model check `curve_exact.py`
  re-run gives ceil 0/5,644,800 and floor 206,528.
- **HScroll buffer, physics run** (`hscroll_probe.py --run`, today vs landed). Clip: 0 of 394
  common positions differ at 1,100 frames and 0 of 1,476 at 2,200 frames; the floor mutant
  differs at 141 of 394 and 547 of 1,476. Canonical OJZ: 0 of 1,014 and 0 of 1,069 differ;
  the floor mutant differs at 133 of 1,014. On the canonical fly leg, 0 of 359 differ and the
  floor mutant differs at 26 of 359, so canonical's fly leg does reach curve scenes.
- **Lag, fly diagonal.** Clip EHZ band: **44/100 → 35/91**, and `Parallax_Update` drops from
  16,913 to 15,251 cycles per tick. Canonical DEBUG whole leg: 49/412 → 48/411, and
  `Parallax_Update` drops by 871 cycles per tick over the leg.
