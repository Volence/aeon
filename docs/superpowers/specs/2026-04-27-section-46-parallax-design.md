# §4.6 Parallax — Multi-Band HScroll, Vertical Parallax, Per-Column V-Scroll

**Date:** 2026-04-27
**Scope:** Engine §4.6. Replaces the placeholder half-speed Plane B fill in `engine/level/hscroll.asm` with the full per-section parallax system: 8-band horizontal parallax, FG/BG H-deformation, vertical parallax with section anchors, per-column V-scroll, and section-boundary transition smoothing.

## Background

The §4 Phase 1 ship (2026-04-25) wired section streaming, camera, and a stub `Hscroll_Update` routine that fills a 28-band per-cell HScroll buffer with a single half-speed Plane B value (`asr.w #1, d1`). Today the routine is **never called and never DMA'd to VDP** — the placeholder fill sits in RAM, dormant. Plane B's visible "parallax" in current builds comes only from VRAM authoring; nothing dynamic happens.

Vscroll handling is similarly minimal: `Vscroll_Factor` (4 bytes) is written each VBlank but never updated from `Camera_Y`. Sections cannot configure parallax; the architecture doc's §4.6 commitments are unimplemented.

This spec brings the system online and finishes everything in §4.6 of `docs/ENGINE_ARCHITECTURE.md` plus three additions surfaced during brainstorming research:

1. **Multiply-free per-section factor tables** (replacing the doc's `factor = -(layer*2-7)` formula)
2. **Per-band Plane A factor split** (locked horizon strips, boss-arena Plane A pinning)
3. **Per-column V-scroll (VSRAM column mode)** (vertical analog of per-cell H-scroll)

## Research summary

Brainstorming research covered the 7 reference disassemblies plus online sources (plutiedev, md.railgun.works, Kabuto, SpritesMind, modern homebrew). Key findings that shaped the design:

- **Per-cell HScroll (28 entries, 112 B/frame)** is sufficient for layered band parallax; per-line (224 entries, 896 B/frame) only earns its keep when deformation is active. Mode is selected per section.
- **No commercial Genesis game uses ROM-resident time-varying deformation tables** — this engine's approach is more sophisticated than current homebrew. SGDK and Megarunner-style projects all build buffers per-frame from camera state.
- **HScroll DMA must drain before VSRAM write** in VBlank; reverse order causes a one-frame tear (SpritesMind t=1482).
- **Combining 2-cell V-scroll with non-zero HScroll garbles the leftmost partial column** — Vectorman, Batman, Contra:HC, Gynoug all mask this with sprites.
- **VRAM_HSCROLL_TABLE = $DC00 is inside Plane A's 64×64 footprint** (row 56), safe today because vertical section streaming doesn't exist yet, but a future build-time assertion is required to keep authored Plane A content out of rows 48-63.
- **The architecture doc's `factor = -(layer*2-7)` formula** could not be verified in the actual TF4 disasm; the citation is "inspired by", not "exact match". Formula generates non-power-of-2 factors that need `muls`, contradicting CODING_CONVENTIONS — replaced with shift-add encoding.
- **S.C.E.'s block-based deformation table format** (variable-height blocks with linear-interp flag) is a ROM-saving optimization; with 256 bytes/table affordable, full per-line tables are simpler. Block format dropped.

Full research artifacts in conversation log; key links:
- [SpritesMind HScroll Tile mode](https://gendev.spritesmind.net/forum/viewtopic.php?t=3149)
- [SpritesMind tearing thread](http://gendev.spritesmind.net/forum/viewtopic.php?t=1482)
- [SpritesMind 2-cell VScroll bug](https://gendev.spritesmind.net/forum/viewtopic.php?t=737)
- [plutiedev VDP registers](https://plutiedev.com/vdp-registers)
- [md.railgun.works VDP](https://md.railgun.works/index.php?title=VDP)
- [Kabuto hardware notes](https://plutiedev.com/mirror/kabuto-hardware-notes)
- [Mark Wrobel — Amiga sine shifting](https://www.markwrobel.dk/post/amiga-machine-code-letter12-wave/)

## Goals

- Per-section parallax configuration (factor tables, deformation, layer mask, transition behavior).
- Up to 8 horizontal bands per section, each with independent Plane A and Plane B factors.
- Plane A and Plane B horizontal deformation (separate tables, speeds, accumulators).
- Per-band deform amplitude (`deform_shift`) and per-band phase offset for desynchronized waves.
- Vertical parallax: per-section center anchor + V-factor + base offset.
- Per-column V-scroll for Plane B (pseudo-3D floors, water columns, lean effects).
- Smooth scroll-factor lerp across section boundaries (8-frame default).
- HScroll/VSRAM mode bits ($8C, $0B) flow through the existing VDP shadow.
- Build-time validation via AS macros and `function`s — bad authoring fails the build, not the runtime.
- Authoring API ergonomic enough that level designers write fractions like `1/8` and `3/8` directly.

## Non-Goals

- **Per-block linear interpolation flag** (S.C.E. block-format deformation). Deferred.
- **Per-band deformation table pointers** (different wave shapes per band). Single shared table per section.
- **Per-band frequency variation.** Only amplitude + phase vary per band; frequency is section-wide.
- **Plane A per-column V-scroll** (`v_deform_table_fg`). Reserved struct field but not wired in v1.
- **Sprite mask for leftmost-partial-column garbage.** Authoring convention; engine doesn't auto-place a mask.
- **Variable-length HScroll DMA** based on dirty range. Already in DEFERRED_WORK §1.1.
- **Mid-frame VDP register changes via HInt** (palette swap at horizon, plane-base swap for "extra" Plane B layers). §7.2 raster engine territory.
- **Build-time assertion that Plane A nametable rows 48-63 stay empty.** Tied to vertical section streaming (§4 deferred); blanket today's design that doesn't have vertical sections.

## Decisions made (during brainstorming)

| # | Decision | Rationale |
|---|---|---|
| 1 | Full architecture-doc scope (not pragmatic MVP) | Top-of-line engine target; surface area is bounded (~230 lines asm + ~126 B RAM); test fixtures auth-able as plan deliverables |
| 2 | Shift-add factor encoding, multiply-free | Matches CODING_CONVENTIONS no-`muls` rule; covers any p/q with q a power of 2 in ≤2 terms; ~6 cycles/band/frame vs 70+ for `muls` |
| 3 | Per-band deform amplitude (decoupled from scroll factor) | Sky can wave hard at 1/8 factor while ground stays still; one extra byte per band |
| 4 | Per-band phase offset (1 byte, 0-255) | Closes the "all bands wave in lockstep" gap without needing per-band tables |
| 5 | Per-band Plane A + Plane B factor split | Unlocks locked horizon strips, boss-arena Plane A pinning, Hydrocity-style above/below splits — capability no Sonic engine offers |
| 6 | Vertical parallax in §4.6 (not deferred) | Symmetric with H-axis; cheap (~8 B/section); essential for the "world feels real" payoff |
| 7 | Per-column V-scroll in §4.6 (not deferred) | Vertical analog of per-cell H-scroll; pseudo-3D depth, water columns; symmetric with H-deform via same triplet pattern |
| 8 | Transition smoothing: lerp scroll values only, hard-swap deformation | Scroll lerp is the dominant visual effect; deform-table snap is barely perceptible |
| 9 | Per-section single deformation table (not per-band) | 80% of visual variety achievable via amplitude + phase; per-band tables are clean v2 upgrade |
| 10 | Per-block linear interp dropped | Full 256-byte table per section is cheap; block format is a ROM-saving optimization we don't need |

## Architecture

### Data structures

#### Band entry (10 bytes per band, ROM)

```asm
band_entry struct
    band_top_cell        ds.b 1   ; first cell row of band (0..27)
    band_factor_a_s1     ds.b 1   ; Plane A shift1 (15 = whole-factor zero, "locked")
    band_factor_a_s2     ds.b 1   ; Plane A shift2 (15 = single-term factor)
    band_factor_a_op     ds.b 1   ; bit 0: 0=ADD second term, 1=SUB
    band_factor_b_s1     ds.b 1   ; Plane B shift1
    band_factor_b_s2     ds.b 1
    band_factor_b_op     ds.b 1
    band_deform_shift_a  ds.b 1   ; Plane A deform amplitude shift (15 = no FG deform on band)
    band_deform_shift_b  ds.b 1   ; Plane B deform amplitude shift
    band_phase_offset    ds.b 1   ; 0..255, added to deform sample index for desync
band_entry endstruct
```

Factor encoding examples (resolved by `factor_decompose` at assembly time):

| Fraction | s1 | s2 | op | Resolved expression |
|---|---|---|---|---|
| `0` (locked) | 15 | 15 | 0 | `0` |
| `1/8` | 3 | 15 | 0 | `camX >> 3` |
| `1/4` | 2 | 15 | 0 | `camX >> 2` |
| `3/8` | 2 | 3 | 0 (ADD) | `(camX>>2) + (camX>>3)` |
| `1/2` | 1 | 15 | 0 | `camX >> 1` |
| `5/8` | 1 | 3 | 0 (ADD) | `(camX>>1) + (camX>>3)` |
| `3/4` | 0 | 2 | 1 (SUB) | `camX - (camX>>2)` |
| `7/8` | 0 | 3 | 1 (SUB) | `camX - (camX>>3)` |
| `1` | 0 | 15 | 0 | `camX` |

#### Parallax config (per-section, ROM)

```asm
parallax_config struct
    pcfg_band_count        ds.b 1
    pcfg_v_factor_bg       ds.b 1   ; whole-plane Plane B vshift (used when v_deform_table_bg = 0)
    pcfg_v_factor_fg       ds.b 1   ; RESERVED — v1 pipeline always sets fg_vscroll = camY (unused)
    pcfg_layer_mask        ds.b 1   ; bit per band; 1 = active. Disabled bands inherit prev band's scroll.
    pcfg_v_center_y        ds.w 1   ; section's "natural" camera Y
    pcfg_v_offset          ds.w 1   ; vscroll BG value at center_y
    pcfg_transition        ds.b 1   ; 0 = smooth lerp (default), 1 = instant snap
    pcfg_deform_speed_fg   ds.b 1   ; FG H-deform table phase increment per frame
    pcfg_deform_speed_bg   ds.b 1   ; BG H-deform table phase increment per frame
    pcfg_pad               ds.b 1
    pcfg_deform_table_fg   ds.l 1   ; ROM ptr to 256-byte signed FG H-deform table (0 = no FG deform)
    pcfg_deform_table_bg   ds.l 1   ; ROM ptr to 256-byte signed BG H-deform table (0 = no BG deform)
    pcfg_v_deform_table_bg ds.l 1   ; ROM ptr to 256-byte signed BG V-column shape (0 = whole-plane V)
    pcfg_v_deform_speed_bg ds.b 1   ; 0 = static column shape, >0 = animated
    pcfg_v_deform_shift_bg ds.b 1   ; amplitude shift on V-column samples
    pcfg_pad2              ds.b 2
    pcfg_bands             ds.b ?   ; band_entry × pcfg_band_count, inline
parallax_config endstruct
```

28-byte header + N × 10 bytes bands. 5-band typical section ≈ 78 bytes. ROM cost per section: ~78-614 bytes depending on H-deform + V-deform usage and table sharing.

#### Section descriptor change

`Sec_Desc` gains one field:

```asm
sec_parallax_config  ds.l 1   ; ROM ptr to parallax_config (0 = inherit from previous section)
```

The architecture doc's prior `sec_scroll`, `sec_deform_table`, `sec_deform_speed`, `sec_layer_mask`, `sec_transition_type` fields collapse into this one indirection.

#### Runtime state

```asm
Parallax_State:
    .deform_phase_fg       ds.w 1   ; (frame_counter * speed_fg) & $FF for FG sampling
    .deform_phase_bg       ds.w 1
    .v_deform_phase_bg     ds.w 1   ; for animated per-column V-scroll
    .current_scroll_a      ds.w 8   ; lerp accumulators, Plane A per band (16 B)
    .current_scroll_b      ds.w 8   ; Plane B per band (16 B)
    .current_vscroll_bg    ds.w 1   ; Plane B vscroll lerp
    .current_config        ds.l 1   ; ptr to active parallax_config
    .target_config         ds.l 1   ; ptr to incoming config during transition
    .transition_frames     ds.b 1   ; frames remaining; 0 = stable
    .pad                   ds.b 3
    .vscroll_column_buf    ds.b 80  ; 40 VSRAM entries × 2 bytes (used when per-column V-mode active)
```

**~126 bytes total Parallax_State.**

The existing `Hscroll_Buffer` (896 bytes, allocated for per-line capacity) and `Vscroll_Factor` (4 bytes) stay as-is. The new `vscroll_column_buf` (80 bytes) is the per-column V-mode shadow.

### Per-frame pipeline (main loop)

`Parallax_Update` runs once per frame after camera/object updates and before `VBlank_Ready` is set:

```
let cfg = current_config (fields: pcfg_*)
let camX = (Camera_X high word, signed)
let camY = (Camera_Y high word, signed)
let mode_per_line = (cfg.deform_table_fg != 0) OR (cfg.deform_table_bg != 0)

1. Advance deform phases:
     deform_phase_fg   = (deform_phase_fg   + cfg.deform_speed_fg)   & $FF
     deform_phase_bg   = (deform_phase_bg   + cfg.deform_speed_bg)   & $FF
     v_deform_phase_bg = (v_deform_phase_bg + cfg.v_deform_speed_bg) & $FF
2. Update transition state:
     If transition_frames > 0: transition_frames -= 1
     If transition_frames == 0 and target_config != NULL:
       current_config = target_config
       target_config  = NULL
3. For each band b in 0..cfg.band_count-1:
     If (cfg.layer_mask >> b) bit clear:
       current_scroll_a[b] = current_scroll_a[b-1]   ; inherit previous (or 0 if b == 0)
       current_scroll_b[b] = current_scroll_b[b-1]
       continue
     target_a = decode_factor(camX, band[b].factor_a_s1, factor_a_s2, factor_a_op)
     target_b = decode_factor(camX, band[b].factor_b_s1, factor_b_s2, factor_b_op)
     current_scroll_a[b] += (target_a - current_scroll_a[b]) >> PARALLAX_LERP_SHIFT
     current_scroll_b[b] += (target_b - current_scroll_b[b]) >> PARALLAX_LERP_SHIFT
4. Fill HScroll buffer:
     IF NOT mode_per_line:                             ; per-cell mode (28 longwords)
       for each band b:
         for each cell c in [band[b].top_cell, band[b+1].top_cell):
           Hscroll_Buffer[c] = (-current_scroll_a[b] << 16) | (-current_scroll_b[b] & $FFFF)
     ELSE:                                              ; per-line mode (224 longwords)
       for each band b:
         let phase = band[b].phase_offset
         let dsa = band[b].deform_shift_a   ; 15 = no FG deform on this band
         let dsb = band[b].deform_shift_b
         for each line y in [band[b].top_cell*8, band[b+1].top_cell*8):
           sample_fg = cfg.deform_table_fg ? sign_extend_byte(cfg.deform_table_fg[(deform_phase_fg + y + phase) & $FF]) : 0
           sample_bg = cfg.deform_table_bg ? sign_extend_byte(cfg.deform_table_bg[(deform_phase_bg + y + phase) & $FF]) : 0
           offset_fg = (dsa != 15) ? (sample_fg >> dsa) : 0
           offset_bg = (dsb != 15) ? (sample_bg >> dsb) : 0
           Hscroll_Buffer[y] = (-(current_scroll_a[b] + offset_fg) << 16) |
                               (-(current_scroll_b[b] + offset_bg) & $FFFF)
5. Compute Vscroll:
     fg_vscroll = camY
     target_bg  = ((camY - cfg.v_center_y) >> cfg.v_factor_bg) + cfg.v_offset
     current_vscroll_bg += (target_bg - current_vscroll_bg) >> PARALLAX_LERP_SHIFT
     IF cfg.v_deform_table_bg == 0:                    ; whole-plane V
       Vscroll_Factor = (fg_vscroll << 16) | (current_vscroll_bg & $FFFF)
     ELSE:                                              ; per-column V (20 column-pairs × 16 px = 320 px)
       for c in 0..19:
         sample = sign_extend_byte(cfg.v_deform_table_bg[(v_deform_phase_bg + c) & $FF])
         offset = sample >> cfg.v_deform_shift_bg
         vscroll_column_buf[c*2]   = fg_vscroll                       ; FG word
         vscroll_column_buf[c*2+1] = current_vscroll_bg + offset      ; BG word
6. Set Hscroll_Dirty_Start = 0, Hscroll_Dirty_End = mode_per_line ? 223 : 27
```

Notes:
- HScroll values are **negated** before VDP write — VDP scroll registers use `-camera` convention (matches the existing `Hscroll_Update` stub at `engine/level/hscroll.asm:14`).
- `current_vscroll_bg` is also lerp'd, so transition-smoothing covers vertical parallax at boundaries (e.g., section transitions where v_center_y or v_offset changes).
- `decode_factor(camX, s1, s2, op)`: returns 0 if s1 == 15; else `(camX >> s1) [+/-] (camX >> s2)` with s2 == 15 meaning single-term.
- **VSRAM layout in per-column mode:** 40 word entries × 2 bytes = 80 bytes total, organized as 20 column-pairs (each 16 px wide), word 2c = Plane A column-pair c, word 2c+1 = Plane B column-pair c. The architecture doc's "40 columns × 4 bytes = 160 bytes" note is a transcription error; actual size is 80 bytes covering 20 column-pairs across 320 px screen width.

#### Cycle estimates (NTSC, ~70K cycles/frame budget)

| Mode | Step 1-4 | Step 5 (buffer fill) | Step 6 (vscroll) | Total |
|---|---|---|---|---|
| Per-cell, whole-plane V | ~120 | ~280 | ~10 | **~410** (~0.6%) |
| Per-line, H-deform on, whole-plane V | ~120 | ~3,200 | ~10 | **~3,330** (~4.7%) |
| Per-line, H+V deform | ~120 | ~3,200 | ~600 | **~3,920** (~5.6%) |

### VBlank pipeline (revised order)

The current `VInt_Level` writes Vscroll_Factor first thing in VBlank, before any DMA processing. Research found this causes a one-frame tear when combined with HScroll updates — HScroll DMA must complete before the VSRAM write.

New order in `engine/vblank.asm`:

```
VInt_Level:
    stopZ80
    Flush_VDP_Shadow              ; includes $0B vmode + $8C hmode if section transitioned
    Enqueue_Dirty_Buffers         ; queues palette + sprites + HScroll into Critical
    VInt_DrawLevel                ; Plane A nametable column drain
    Process_DMA_Critical          ; drains palette + sprites + HScroll
    Vscroll_Write                 ; NEW: writes Vscroll_Factor (4B) or column_buf (80B)
    move.w (DMA_Budget_Default).w, (DMA_Budget_Remaining).w
    Process_DMA_Important
    Process_DMA_Deferrable
    startZ80
    Read_Controllers
    addq.w #1, (Frame_Counter).w
    move.b #1, (VBlank_Flag).w
    rts
```

`Vscroll_Write` branches on `Parallax_State.current_config.pcfg_v_deform_table_bg`:
- NULL → write `Vscroll_Factor` (4 bytes) to VSRAM $0000 — current behavior.
- non-NULL → write 80 bytes from `vscroll_column_buf` via direct loop (~320 cycles).

`VInt_Lag` mirrors the same reorder but skips Important/Deferrable.

### DMA wiring

Two static descriptors for HScroll, one selected per frame by `Enqueue_Dirty_Buffers` based on whether either H-deform table is non-NULL:

```asm
Static_Hscroll_Cell:
    static_dma source=Hscroll_Buffer, dest=VRAM_HSCROLL_TABLE, length=112, type=VRAM

Static_Hscroll_Line:
    static_dma source=Hscroll_Buffer, dest=VRAM_HSCROLL_TABLE, length=896, type=VRAM
```

Both sit in the Critical queue (always sent, even on lag frames). DMA bandwidth (NTSC 7200 B/VBlank budget):
- Per-cell mode: 112 B (1.6%)
- Per-line mode: 896 B (12.4%)

### VDP register management

Two register changes flow through the existing shadow on section transitions:

| Register | Bits | Effect |
|---|---|---|
| $0B (Mode Set 3) | bit 2 | 0 = whole-plane V-scroll, 1 = per-column V-scroll |
| $8C (Mode Set 4) | bits 1-0 | 10 = per-cell HScroll, 11 = per-line HScroll |

`Section_Check` writes the new values into the shadow when `sec_parallax_config` differs from previous section's. `Flush_VDP_Shadow` applies them atomically with the new buffer/VSRAM data.

### Transition smoothing flow

When `Section_Check` detects a parallax_config change:

```
On section transition:
  IF new_config.pcfg_transition == 1 (instant):
    Parallax_State.current_config = new_config
    Hard-snap current_scroll_a/b to target values
    transition_frames = 0
  ELSE (smooth, default):
    target_config = new_config
    transition_frames = 8       ; 8-frame lerp (>>3 converges to ~95%)
    current_config stays as old until first lerp tick converges
```

Per-frame in `Parallax_Update`, when `transition_frames > 0`:
- Use `target_config` for factor decoding (target_scroll computation)
- Lerp `current_scroll_*[band] += (target - current_scroll_*[band]) >> 3`
- Decrement `transition_frames`; when reaches 0, swap current = target, target = NULL

Deformation tables, deform speeds, layer mask, and BG layout (handled separately by `BG_RedrawForSection`) all hard-swap at the boundary. Only band scroll values are smoothed.

### Layer mask semantics

`pcfg_layer_mask` is a bitmask: bit N set = band N is active.

When a band's bit is **clear**, the buffer-fill step:
- Skips the lerp for that band (no current_scroll update)
- Inherits the previous (active) band's `current_scroll_a`/`b` for its cells/lines
- Visually: the disabled band "joins" the band above it; e.g., disabling the cloud band makes mountain art visually extend upward to fill the cloud space

Costs ~3 cycles per skipped band — tiny.

### Per-column V-scroll caveat

Per-column V-scroll combined with non-zero HScroll garbles the leftmost partial column (16-px wide) — a documented VDP behavior affecting Vectorman, Batman, Contra:HC, Gynoug. v1 documents this as an authoring convention: sections using per-column V-scroll should place a 16-px black sprite at column 0 to mask the artifact. The engine doesn't auto-place a mask; that's a §3 sprite-system concern.

## Authoring API

### Top-level macros

```asm
; -- Per-section parallax config --
parallax_section [LAYER_MASK=$FF, V_FACTOR_BG=3, V_FACTOR_FG=0,
                  V_CENTER=0, V_OFFSET=0, TRANSITION=0,
                  DEFORM_FG=0, DEFORM_BG=0, DEFORM_SPEED_FG=1, DEFORM_SPEED_BG=1,
                  V_DEFORM_BG=0, V_DEFORM_SPEED_BG=0, V_DEFORM_SHIFT_BG=4,
                  DEFORM_SHIFT_DEFAULT=4]
    band ...
    band ...
parallax_section_end

; -- One band --
band TOP=<cell>, FACTOR_A=<frac>, FACTOR_B=<frac>,
     [DEFORM_SHIFT_A=<n>, DEFORM_SHIFT_B=<n>, PHASE=<0..255>]
```

### Deformation table generators

```asm
; 256-byte sine wave, signed
deform_table_sine AMPLITUDE=<peak>, PERIOD=<frames per cycle>, [PHASE=<0..255>]

; 256-byte triangle wave
deform_table_triangle AMPLITUDE=<peak>, PERIOD=<frames per cycle>

; 256-byte custom from raw byte list (assembler validates length)
deform_table_custom 0,1,2,3,...

; 256-byte pseudo-3D perspective ramp (for v_deform_table_bg)
v_column_perspective FOCAL=<center>, MAX_OFFSET=<edge>

; 256-byte static column array (40 unique values, padded)
v_column_static 0,0,1,2,4,...  ; 40 entries
```

### Internal `function` (build-time fraction decomposer)

```asm
factor_decompose function p,q,encode_internal(p,q)
    ; runs at assembly time
    ; returns 24-bit packed: bits 0-3=shift1, 4-7=shift2, 8=op
    ; fatals on:
    ;   - q not power of 2
    ;   - p > q without OVERSHOOT flag
    ;   - p/q reduces to >2 shift terms
```

### Authoring example

```asm
; -- data/parallax/ojz_sec1.asm --

ParallaxConfig_OJZSec1:
    parallax_section LAYER_MASK=$1F, V_FACTOR_BG=3, V_CENTER=128, V_OFFSET=0, \
                     DEFORM_BG=DeformTable_OJZ_Calm, DEFORM_SPEED_BG=1, \
                     DEFORM_SHIFT_DEFAULT=4
        band TOP=0,  FACTOR_A=1, FACTOR_B=1/8, PHASE=0      ; clouds
        band TOP=4,  FACTOR_A=1, FACTOR_B=1/4, PHASE=64     ; far mountains
        band TOP=10, FACTOR_A=1, FACTOR_B=3/8, PHASE=128    ; mid mountains
        band TOP=14, FACTOR_A=1, FACTOR_B=1/2, PHASE=192    ; hills
        band TOP=20, FACTOR_A=1, FACTOR_B=1                  ; ground (FG-sync, no deform)
    parallax_section_end

DeformTable_OJZ_Calm:
    deform_table_sine AMPLITUDE=4, PERIOD=128
```

## Build-time validation

| Check | Where | Failure |
|---|---|---|
| Fraction denominator is power of 2 | `band` macro via `factor_decompose` | `"parallax: factor 1/3 — denominator must be power of 2"` |
| Fraction decomposes to ≤2 shift terms | `band` macro | `"parallax: factor 7/16 needs 3 terms, max 2"` |
| Factor ≤ 1 (or explicit `OVERSHOOT=1` flag) | `band` macro | `"parallax: factor > 1 requires OVERSHOOT flag"` |
| Band TOP strictly ascending | `band` macro | `"parallax: band 3 TOP=10 not after band 2 TOP=12"` |
| Band TOP in 0..27 | `band` macro | `"parallax: band TOP=28 out of range"` |
| Band count ≤ 8 | `band` macro | `"parallax: more than 8 bands"` |
| Last band top_cell ≤ 27 | `parallax_section_end` | `"parallax: last band TOP=29 exceeds visible cells"` |
| Deformation table sized exactly 256 B | `deform_table_*` generators | `"deform_table: size 240, expected 256"` |
| `LAYER_MASK` bits within band count | `parallax_section_end` | `"parallax: LAYER_MASK=$FF but only 5 bands"` |

Build-tool also emits per-band wrap analysis as INFO/WARN messages:

```
INFO  ParallaxConfig_OJZSec1: 5 bands, layer_mask=$1F, BG H-deform=Calm
INFO    band 0 (rows 0-3)   factor_b=1/8  wraps at 4096 px ✓
INFO    band 1 (rows 4-9)   factor_b=1/4  wraps at 2048 px ✓
INFO    band 2 (rows 10-13) factor_b=3/8  wraps at 1365 px ✓
WARN    band 3 (rows 14-19) factor_b=1/2  wraps at 1024 px — verify seamless tile edges
WARN    band 4 (rows 20-27) factor_b=1    wraps at 512 px — must be Plane A or streamed
```

## Components

| Area | File | Change |
|---|---|---|
| RAM layout | `ram.asm` | Add `Parallax_State` block (~126 B). Existing `Hscroll_Buffer` and `Vscroll_Factor` reused as-is. |
| Constants | `constants.asm` | Add `MAX_PARALLAX_BANDS = 8`, `PARALLAX_TRANSITION_FRAMES = 8`, `PARALLAX_LERP_SHIFT = 3` |
| Section descriptor | `structs.asm` | Repurpose `sec_scroll` ($14, currently "parallax layer table — Phase 4" stub) as `sec_parallax_config`. Mark `sec_deform_table` ($2C), `sec_layer_mask` ($3C), `sec_deform_speed` ($3E), `sec_transition_type` ($3F) as reserved pad bytes — do not remove offsets, struct stays $48 bytes to avoid touching every existing section descriptor. |
| Parallax config struct | `structs.asm` (new) | Define `parallax_config` struct + `band_entry` struct |
| Macros | `engine/parallax_macros.inc` (new) | `parallax_section`, `parallax_section_end`, `band`, `deform_table_sine`, `deform_table_triangle`, `deform_table_custom`, `v_column_perspective`, `v_column_static`, `factor_decompose` function |
| Main-loop update | `engine/level/parallax.asm` (new) | `Parallax_Update` (~250 lines): per-frame pipeline steps 1-7. Replaces stub `Hscroll_Update` in `engine/level/hscroll.asm` (which gets removed). |
| Section transition hook | `engine/level/section.asm` | `Section_Check` calls `Parallax_StartTransition(new_config)` when `sec_parallax_config` changes between active sections |
| VDP shadow updates | `engine/level/section.asm` | Section transition writes $0B (vmode bit) and $8C (hmode bits) into shadow based on new config |
| VBlank reorder | `engine/vblank.asm` | Move `Vscroll_Write` from first-thing to after `Process_DMA_Critical`. Add `Vscroll_Write` routine that branches on `current_config.v_deform_table_bg`. |
| HScroll DMA descriptors | `engine/buffers.asm` | Define `Static_Hscroll_Cell` and `Static_Hscroll_Line`. `Enqueue_Dirty_Buffers` enqueues correct one per current mode. |
| Game-loop integration | `engine/game_loop.asm` | Call `Parallax_Update` in main loop after camera/object updates |
| Initial setup | `engine/level/load_art.asm` | After `BG_Init`, call `Parallax_Init` with the act's first section's parallax_config |

### Test fixtures

| F# | Fixture | Files | Effort |
|---|---|---|---|
| F1 | Multi-band OJZ BG art | `art/ojz/bg_layout_v2.bin` (4096 B), tile pool extension if needed | Medium (~1-2 hrs art work) |
| F2 | Sine deform table macro | `engine/parallax_macros.inc` (`deform_table_sine`) | Low |
| F3 | OJZ "windy" section variant | `data/parallax/ojz_sec_windy.asm` | Low |
| F4 | Section-pair (transition test) | Two parallax configs + Exodus manual teleport | Trivial |
| F5 | FG-deform test section | `data/parallax/ojz_sec_fgwave.asm` | Low |
| F6 | Layer-mask test | One section with `LAYER_MASK=$0F` | Trivial |

## Tear-prevention test

Verify VBlank ordering via Exodus MCP:
1. Set up an OJZ section with H-deform enabled (per-line mode) + whole-plane V-scroll.
2. Pause emulator at scanline 1 (just past VBlank end).
3. Read VRAM `$DC00..$DFFF` (HScroll table) and VSRAM `$00..$03` (Vscroll).
4. Confirm both reflect the current frame's parallax state (no stale-VSRAM tear).
5. Repeat at high scroll velocity (camera moving 8+ px/frame) for 100 frames; no visible tear.

## Architecture-doc revisions required

`docs/ENGINE_ARCHITECTURE.md` §4.6 needs:

1. Replace `factor = -(layer_index * 2 - 7)` formula description with shift-add factor-table model.
2. Drop "16 muls per frame ≈ 1,120 cycles" budget note. Replace with shift-add cost (~50 cycles for all 8 bands' factor decoding).
3. Drop "per-block linear interpolation flag" feature.
4. Add per-band Plane A factor split (factor_a + factor_b, 10-byte band entry).
5. Add per-band phase offset (1 byte).
6. Add vertical parallax (per-section center anchor + V-factor + V-offset).
7. Add per-column V-scroll (Plane B; symmetric with H-deform via `v_deform_table_bg` triplet).
8. Update RAM cost note: ~126 B `Parallax_State` (includes 80-byte `vscroll_column_buf`); existing `Hscroll_Buffer` (896 B) and `Vscroll_Factor` (4 B) are reused, not added.
9. Note that TF4 attribution is "inspired by", not "exact formula match" — could not verify formula in disasm.
10. Note that the `Foundation: S.C.E.'s HScroll_Deform deformation script` line should be revised — we use a unified buffer-fill approach, not S.C.E.'s block format.

## Deferred work entries

To be added to `docs/DEFERRED_WORK.md` under "From §4.6 — Parallax":

- **Per-block linear interpolation deformation format** (S.C.E. block-based table). Variable-height blocks with high-bit linear-interp flag. Not in v1; full 256-byte tables used. Revisit if a section's deformation table waste becomes a real ROM problem.
- **Per-band deformation table pointers**. Different wave shapes per band. Not in v1; single shared table per section + per-band amplitude/phase. Revisit if a section visually demands different shapes per band.
- **Per-band frequency variation** (`phase_increment`). Not in v1; only phase offset varies per band. Revisit if "different speeds per band" becomes a clear visual need.
- **Plane A per-column V-scroll** (`v_deform_table_fg`). Reserved struct field; v1 always uses whole-plane V-scroll on Plane A. Revisit when a section needs ground-plane warping.
- **Sprite mask for per-column V-scroll leftmost-partial-column garbage**. v1 documents the artifact; sections using per-column V-scroll author a 16-px black sprite at column 0 manually. Auto-placement deferred to §3 sprite system if real workloads surface.
- **Variable-length HScroll DMA based on dirty range**. Already in DEFERRED_WORK §1.1.
- **Mid-frame VDP register changes via HInt** (palette swap at horizon, plane-base swap for "extra" Plane B layers). §7.2 raster engine territory; clean hook via existing VDP shadow.
- **Build-time assertion that Plane A nametable rows 48-63 stay empty**. Tied to vertical section streaming (§4 deferred).
- **Plane B vertical extent extension to 64×64** (currently 64×32 with $F000-$FFFF reserved for Window). If Window plane gets repurposed, extends vertical parallax range.
