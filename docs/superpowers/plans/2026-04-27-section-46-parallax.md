# §4.6 Parallax Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the placeholder Plane B half-speed fill in `engine/level/hscroll.asm` with the full per-section parallax system from `docs/superpowers/specs/2026-04-27-section-46-parallax-design.md`: multiply-free shift-add factor encoding, 8-band horizontal parallax with FG/BG factor split + per-band amplitude/phase, FG/BG H-deformation, vertical parallax with section anchor, per-column V-scroll, and section-boundary transition smoothing.

**Architecture:** Per-section `parallax_config` ROM records describe band layout, factors, deformation tables, vertical parameters, and per-column V-scroll mode. `Parallax_Update` runs once per main loop tick, builds the HScroll buffer (per-cell or per-line mode auto-selected from config), updates `Vscroll_Factor` (whole-plane) or `vscroll_column_buf` (per-column mode), and applies transition smoothing as a per-band lerp. VBlank order is reorganized so HScroll DMA drains before VSRAM write, preventing the documented one-frame tear.

**Tech Stack:** AS Macro Assembler (`asw`), 68000 assembly, Exodus emulator with MCP for VRAM/RAM/VSRAM inspection, `./build.sh` for ROM builds.

---

## Per-Step Research Discipline (project memory: feedback_research_in_plans)

**Every implementation step's first sub-task is a research pass.** The standard sweep:

1. **All 7 reference disassemblies** — S.C.E., Batman & Robin, Vectorman, Gunstar Heroes, Alien Soldier, Thunder Force IV, sonic_hack. Always check each — different tradeoffs, different lessons.
2. **Online sources** — plutiedev.com, md.railgun.works, Kabuto hardware notes, segaretro.org, SpritesMind forum, GitHub homebrew (Xeno Crisis, Tanglewood, Demons of Asteborg, Project MD, SGDK).
3. **Modern engine techniques** — anything from modern engines that maps to a fixed-cost-per-frame budget.

Listed targets are starting points (memory `feedback_research_breadth`). Cross-reference findings against the spec at `docs/superpowers/specs/2026-04-27-section-46-parallax-design.md` and against ENGINE_ARCHITECTURE.md (memory `feedback_research_before_build`) — don't treat documented designs as from-scratch.

**Per-task output:** append a section to `docs/research/parallax-§4.6.md` (created in Task 1) summarizing findings + the recommendation that informs that task's implementation. If research changes the implementation, update the spec or this plan inline before proceeding.

---

## Files in scope

**Create:**
- `docs/research/parallax-§4.6.md` — Living research doc, appended per task
- `engine/parallax_macros.inc` — `band`, `parallax_section`, `parallax_section_end`, `factor_decompose`, deform-table generators
- `engine/level/parallax.asm` — `Parallax_Update`, `Parallax_Init`, `Parallax_StartTransition`, `Vscroll_Write`
- `data/parallax/ojz_default.asm` — first parallax_config wired into OJZ Act 1 (initial test path)
- `data/parallax/ojz_windy.asm` — F3 fixture (BG H-deform variant)
- `data/parallax/ojz_fgwave.asm` — F5 fixture (FG H-deform variant)
- `data/parallax/ojz_layermask.asm` — F6 fixture (LAYER_MASK=$0F)
- `art/ojz/bg_layout_v2.bin` — F1 fixture (multi-band BG nametable, may reuse existing tile pool)

**Modify:**
- `structs.asm` — Repurpose `sec_scroll` ($14) as `sec_parallax_config`; mark `sec_deform_table` ($2C), `sec_layer_mask` ($3C), `sec_deform_speed` ($3E), `sec_transition_type` ($3F) as reserved pad bytes. Add `band_entry` and `parallax_config` structs.
- `constants.asm` — Add `MAX_PARALLAX_BANDS`, `PARALLAX_TRANSITION_FRAMES`, `PARALLAX_LERP_SHIFT`.
- `ram.asm` — Add `Parallax_State` block (~126 B).
- `engine/vblank.asm` — Reorder `VInt_Level` and `VInt_Lag`: move VSRAM write from first-thing to after `Process_DMA_Critical`. Add `Vscroll_Write` call.
- `engine/buffers.asm` — Define `Static_Hscroll_Cell` and `Static_Hscroll_Line` DMA descriptors. Update `Enqueue_Dirty_Buffers` to enqueue the appropriate one based on current parallax mode.
- `engine/level/section.asm` — `Section_Check` calls `Parallax_StartTransition` when `sec_parallax_config` differs between active sections. Section transition writes $0B (vmode bit) and $8C (hmode bits) into VDP shadow.
- `engine/level/load_art.asm` — After `BG_Init`, call `Parallax_Init` with the act's first section's parallax_config.
- `engine/game_loop.asm` — Call `Parallax_Update` in main loop after camera/object updates.
- `engine/level/hscroll.asm` — DELETE (stub `Hscroll_Update` is unused; new pipeline lives in `engine/level/parallax.asm`).
- `S4.asm` — Adjust `include` ordering to incorporate `parallax_macros.inc` and `parallax.asm`.
- Section descriptors for OJZ Act 1 — Set `sec_parallax_config` to point at `ParallaxConfig_OJZ_Default` initially; per-section variants for F3/F5/F6.
- `docs/ENGINE_ARCHITECTURE.md` — §4.6 revisions per spec section "Architecture-doc revisions required".
- `docs/DEFERRED_WORK.md` — Append "From §4.6 — Parallax" section with all deferred items per spec.

---

## Task 1: Create research doc + add data structures and constants

Pure layout change. Defines the structs and constants that all later tasks depend on. No runtime behavior yet.

**Files:**
- Create: `docs/research/parallax-§4.6.md`
- Modify: `structs.asm` (add `band_entry`, `parallax_config` structs; repurpose `sec_scroll`, retire 4 obsolete fields)
- Modify: `constants.asm` (add `MAX_PARALLAX_BANDS`, `PARALLAX_TRANSITION_FRAMES`, `PARALLAX_LERP_SHIFT`)
- Modify: `ram.asm` (add `Parallax_State` block)

- [ ] **Step 1: Research — verify struct layouts against reference engines**

Targets:
- **S.C.E.** — `Engine/Variables.asm:37` shows `H_scroll_table ds.w 256`. What are S.C.E.'s deformation config struct fields, if any? Find `_Deform_Config_*` data near `Engine/Core/Deformation Script.asm`. How many bytes per band/block? How is layer mask represented?
- **sonic_hack** — `code/engines/scroll_camera.asm` per-zone routines (`Hztl_Vrtc_Bg_Deformation` line 236). Hardcoded jump table; no struct. Confirms why a struct-based per-section approach is more flexible.
- **TF4** (raw disasm) — search for repeated 4-8 byte records near scroll-table allocations.
- **Batman & Robin** — raster command table format from §7.2 reference docs; what's the per-effect field count and byte size?
- **Online**: SGDK's scrolling structures (`vdp_bg.h`); plutiedev's "scrolling" page on per-mode-byte-counts.

Cross-reference the spec's 28-byte `parallax_config` header + 10-byte `band_entry`. Question to settle: should `pcfg_v_factor_fg` (currently RESERVED) be removed entirely or kept for symmetry? Recommendation: keep (one byte of forward-compat).

Append findings to `docs/research/parallax-§4.6.md` under "Task 1 — Struct layout cross-reference."

- [ ] **Step 2: Create the research doc with header**

Create `docs/research/parallax-§4.6.md`:

```markdown
# §4.6 Parallax — Research Notes (per-task appendix)

Spec: `docs/superpowers/specs/2026-04-27-section-46-parallax-design.md`
Plan: `docs/superpowers/plans/2026-04-27-section-46-parallax.md`

This document accumulates research findings during plan execution. Each task
appends a section. If research changes implementation, update the spec/plan
inline before proceeding.

---

## Task 1 — Struct layout cross-reference

[append findings here]
```

- [ ] **Step 3: Add `band_entry` and `parallax_config` structs to structs.asm**

Open `structs.asm`. After the existing `Sec` struct definition (around line 130, after the `Sec_len` assert), add:

```asm
; ----------------------------------------------------------------------
; Parallax band entry — 10 bytes per band, ROM data
; ----------------------------------------------------------------------
band_entry struct
    band_top_cell        ds.b 1   ; first cell row of band (0..27)
    band_factor_a_s1     ds.b 1   ; Plane A shift1 (15 = whole-factor zero "locked")
    band_factor_a_s2     ds.b 1   ; Plane A shift2 (15 = single-term factor)
    band_factor_a_op     ds.b 1   ; bit 0: 0=ADD second term, 1=SUB
    band_factor_b_s1     ds.b 1   ; Plane B shift1
    band_factor_b_s2     ds.b 1   ; Plane B shift2
    band_factor_b_op     ds.b 1   ; bit 0: 0=ADD, 1=SUB
    band_deform_shift_a  ds.b 1   ; Plane A deform amplitude shift (15 = no FG deform)
    band_deform_shift_b  ds.b 1   ; Plane B deform amplitude shift
    band_phase_offset    ds.b 1   ; 0..255, added to deform sample index for desync
band_entry endstruct

    if band_entry_len <> 10
      error "band_entry struct is \{band_entry_len} bytes, expected 10"
    endif

; ----------------------------------------------------------------------
; Parallax config — 28-byte header + N × band_entry, ROM data
; ----------------------------------------------------------------------
parallax_config struct
    pcfg_band_count        ds.b 1
    pcfg_v_factor_bg       ds.b 1   ; whole-plane Plane B vshift (used when v_deform_table_bg = 0)
    pcfg_v_factor_fg       ds.b 1   ; RESERVED — v1 pipeline always sets fg_vscroll = camY
    pcfg_layer_mask        ds.b 1   ; bit per band; 1 = active
    pcfg_v_center_y        ds.w 1   ; section's "natural" camera Y
    pcfg_v_offset          ds.w 1   ; vscroll BG value at center_y
    pcfg_transition        ds.b 1   ; 0 = smooth lerp (default), 1 = instant snap
    pcfg_deform_speed_fg   ds.b 1   ; FG H-deform table phase increment per frame
    pcfg_deform_speed_bg   ds.b 1   ; BG H-deform table phase increment per frame
    pcfg_pad               ds.b 1
    pcfg_deform_table_fg   ds.l 1   ; ROM ptr to 256-byte signed FG H-deform (0 = none)
    pcfg_deform_table_bg   ds.l 1   ; ROM ptr to 256-byte signed BG H-deform (0 = none)
    pcfg_v_deform_table_bg ds.l 1   ; ROM ptr to 256-byte signed BG V-column (0 = whole-plane)
    pcfg_v_deform_speed_bg ds.b 1   ; 0 = static column shape, >0 = animated
    pcfg_v_deform_shift_bg ds.b 1   ; amplitude shift on V-column samples
    pcfg_pad2              ds.b 2
    ; pcfg_bands inline follows: band_entry × pcfg_band_count
parallax_config endstruct

    if parallax_config_len <> 22
      error "parallax_config header is \{parallax_config_len} bytes, expected 22"
    endif
```

- [ ] **Step 4: Repurpose `sec_scroll` and retire obsolete parallax fields**

In `structs.asm`, find the `Sec` struct (around line 107). Edit the field definitions:

Replace this line:
```asm
sec_scroll          ds.l 1          ; $14 — parallax layer table (Phase 4)
```
with:
```asm
sec_parallax_config ds.l 1          ; $14 — ROM ptr to parallax_config (0 = inherit)
```

Replace these lines:
```asm
sec_deform_table    ds.l 1          ; $2C — deformation table (Phase 4)
```
with:
```asm
sec_pcfg_pad_2C     ds.l 1          ; $2C — RESERVED (was sec_deform_table; now in parallax_config)
```

Replace:
```asm
sec_layer_mask      ds.b 1          ; $3C — parallax layer enable (Phase 4)
sec_camera_lookahead ds.b 1         ; $3D — lookahead pixels (0 = zone default)
sec_deform_speed    ds.b 1          ; $3E — deformation rate (Phase 4)
sec_transition_type ds.b 1          ; $3F — transition type (Phase 4)
```
with:
```asm
sec_pcfg_pad_3C     ds.b 1          ; $3C — RESERVED (was sec_layer_mask)
sec_camera_lookahead ds.b 1         ; $3D — lookahead pixels (0 = zone default)
sec_pcfg_pad_3E     ds.b 1          ; $3E — RESERVED (was sec_deform_speed)
sec_pcfg_pad_3F     ds.b 1          ; $3F — RESERVED (was sec_transition_type)
```

Verify the `Sec_len` assertion (around line 132) still expects `$48`.

- [ ] **Step 5: Add constants to constants.asm**

Open `constants.asm`. Find the §4 region (search for `; Section streaming` or similar). Add:

```asm
; -----------------------------------------------
; Parallax (§4.6)
; -----------------------------------------------
MAX_PARALLAX_BANDS         = 8
PARALLAX_TRANSITION_FRAMES = 8     ; default boundary lerp duration
PARALLAX_LERP_SHIFT        = 3     ; >> 3 ≈ 8-frame convergence to ~95%
```

- [ ] **Step 6: Add Parallax_State block to ram.asm**

Open `ram.asm`. Find the existing `Hscroll_Buffer` declaration around line 103. After `Vscroll_Factor` (line 107), add a new section:

```asm
; -----------------------------------------------
; Parallax state (§4.6)
; -----------------------------------------------
Parallax_State:
Parallax_Deform_Phase_FG:    ds.w 1     ; (frame_counter * speed_fg) & $FF
Parallax_Deform_Phase_BG:    ds.w 1
Parallax_V_Deform_Phase_BG:  ds.w 1     ; for animated per-column V-scroll
Parallax_Current_Scroll_A:   ds.w MAX_PARALLAX_BANDS  ; lerp accumulators, Plane A
Parallax_Current_Scroll_B:   ds.w MAX_PARALLAX_BANDS  ; Plane B
Parallax_Current_Vscroll_BG: ds.w 1
Parallax_Current_Config:     ds.l 1     ; ptr to active parallax_config
Parallax_Target_Config:      ds.l 1     ; ptr to incoming during transition
Parallax_Transition_Frames:  ds.b 1     ; frames remaining; 0 = stable
Parallax_Pad:                ds.b 3
Parallax_Vscroll_Column_Buf: ds.b 80    ; 40 VSRAM entries × 2 bytes
Parallax_State_End:
```

Confirm the block lands within the existing low-RAM budget (verify by reading `ram.asm` end-of-file `phase`/`dephase` if present, or by build).

- [ ] **Step 7: Build clean to confirm layouts assert**

```bash
cd /home/volence/sonic_hacks/s4_engine && ./build.sh -pe
```

Expected: build succeeds. The `band_entry_len` and `parallax_config_len` asserts confirm exact byte counts; `Sec_len` assert (existing) confirms the section descriptor still totals $48.

- [ ] **Step 8: Commit**

```bash
git add structs.asm constants.asm ram.asm docs/research/parallax-§4.6.md
git commit -m "$(cat <<'EOF'
feat(§4.6): parallax data structures — band_entry, parallax_config, RAM

Adds band_entry (10 B) and parallax_config (22 B header + bands inline)
structs. Repurposes Sec.sec_scroll ($14) as sec_parallax_config; retires
sec_deform_table, sec_layer_mask, sec_deform_speed, sec_transition_type
as reserved pad bytes (Sec stays $48). Adds Parallax_State block (~126 B
including 80-byte vscroll_column_buf shadow). No behavior yet — pure
layout for subsequent tasks.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Authoring macros — `band`, `parallax_section`, `factor_decompose`

Build-time machinery. After this task, an author can write `band 4, FACTOR_1, FACTOR_1_4` and the assembler emits the correct 10 bytes. Pure assembly-time; no runtime behavior.

**Files:**
- Create: `engine/parallax_macros.inc`
- Modify: `S4.asm` (include the new file)

- [ ] **Step 1: Research — AS Macro Assembler `function` and macro patterns** (RESOLVED via pre-flight spike, 2026-04-27)

Spike performed before plan execution (`tools/factor_spike.asm`, `tools/factor_spike2.asm`). Findings:

1. **AS evaluates `1/8` at substitution time as integer division (= 0).** `band TOP=0, FACTOR_B=1/8` is unworkable — the fraction collapses to 0 before the macro can inspect it.
2. **`function f(p,q, expr)` works correctly when called with explicit positional integer args** — e.g., `f(1,8)` evaluates `expr` with `p=1, q=8` and proper multiplication ordering. So `packed(0,15,0)` etc. work as compile-time constants.
3. **Named-equate fractions are the cleanest UX.** Pre-define `FACTOR_1_8`, `FACTOR_3_8`, etc. as integer equates at the top of `parallax_macros.inc`. The author writes `band 0, FACTOR_1, FACTOR_1_8` (positional args) and the macro reads the integer values.
4. **`fatal` cannot fire from inside a `function`** — it's expression-only. Validation lives in the `band` macro's `if` checks against the resolved integer.
5. **Section-open state** is tracked via global `set` variables (`parallax_section_band_count`, `parallax_section_last_top`).

This task implements that decision.

Append the spike artifacts and findings to `docs/research/parallax-§4.6.md` under "Task 2 — Macro spike results."

- [ ] **Step 2: Create `engine/parallax_macros.inc` with `packed` function + FACTOR_* equates**

```asm
; engine/parallax_macros.inc — Authoring API for §4.6 parallax
;
; Usage:
;   ParallaxConfig_Foo:
;     parallax_section LAYER_MASK=$1F, V_FACTOR_BG=3, ...
;       band 0,  FACTOR_1, FACTOR_1_8        ; top_cell, factor_a, factor_b
;       band 4,  FACTOR_1, FACTOR_1_4
;     parallax_section_end
;
; Factor encoding (24-bit packed):
;   bits 0-3:  shift1 (0..14, 15 = "term zero", whole factor = 0)
;   bits 4-7:  shift2 (0..14, 15 = "single-term factor")
;   bit  8:    op    (0 = ADD second term, 1 = SUB)

; ----------------------------------------------------------------------
; packed — build-time factor encoder (used to define FACTOR_* equates)
; ----------------------------------------------------------------------
packed function s1,s2,op, ((op&1)<<8) | ((s2&15)<<4) | (s1&15)

; ----------------------------------------------------------------------
; Pre-defined factor equates — fractions p/q where q is a power of 2
; and decomposition uses ≤2 shift-add ops.
; ----------------------------------------------------------------------
FACTOR_LOCKED equ $0FF                  ; s1=15 → factor = 0 ("locked layer")
FACTOR_0      equ FACTOR_LOCKED         ; alias
FACTOR_1      equ packed(0,15,0)        ; camX
FACTOR_1_2    equ packed(1,15,0)        ; camX>>1
FACTOR_1_4    equ packed(2,15,0)        ; camX>>2
FACTOR_1_8    equ packed(3,15,0)        ; camX>>3
FACTOR_1_16   equ packed(4,15,0)        ; camX>>4
FACTOR_1_32   equ packed(5,15,0)        ; camX>>5
FACTOR_3_4    equ packed(0,2,1)         ; camX - camX>>2
FACTOR_3_8    equ packed(2,3,0)         ; camX>>2 + camX>>3
FACTOR_3_16   equ packed(3,4,0)         ; camX>>3 + camX>>4
FACTOR_5_8    equ packed(1,3,0)         ; camX>>1 + camX>>3
FACTOR_5_16   equ packed(2,4,0)         ; camX>>2 + camX>>4
FACTOR_7_8    equ packed(0,3,1)         ; camX - camX>>3
FACTOR_7_16   equ packed(1,4,1)         ; camX>>1 - camX>>4
FACTOR_15_16  equ packed(0,4,1)         ; camX - camX>>4

; (Add more as needed. Custom fractions outside this set must be authored
; as raw `packed(s1,s2,op)` calls inline.)
```

Verified in pre-flight spike: each FACTOR_* equate resolves to its expected integer; passing them as macro args works because macro substitution is purely textual and AS doesn't pre-evaluate them.

- [ ] **Step 3: Add `parallax_section` / `parallax_section_end` / `band` macros**

Append to `engine/parallax_macros.inc`:

```asm
; ----------------------------------------------------------------------
; parallax_section — open a parallax_config record
; ----------------------------------------------------------------------
parallax_section macro
    ; defaults
    if "LAYER_MASK" = ""
LAYER_MASK := $FF
    endif
    if "V_FACTOR_BG" = ""
V_FACTOR_BG := 3
    endif
    if "V_FACTOR_FG" = ""
V_FACTOR_FG := 0
    endif
    if "V_CENTER" = ""
V_CENTER := 0
    endif
    if "V_OFFSET" = ""
V_OFFSET := 0
    endif
    if "TRANSITION" = ""
TRANSITION := 0
    endif
    if "DEFORM_FG" = ""
DEFORM_FG := 0
    endif
    if "DEFORM_BG" = ""
DEFORM_BG := 0
    endif
    if "DEFORM_SPEED_FG" = ""
DEFORM_SPEED_FG := 1
    endif
    if "DEFORM_SPEED_BG" = ""
DEFORM_SPEED_BG := 1
    endif
    if "V_DEFORM_BG" = ""
V_DEFORM_BG := 0
    endif
    if "V_DEFORM_SPEED_BG" = ""
V_DEFORM_SPEED_BG := 0
    endif
    if "V_DEFORM_SHIFT_BG" = ""
V_DEFORM_SHIFT_BG := 4
    endif
    if "DEFORM_SHIFT_DEFAULT" = ""
DEFORM_SHIFT_DEFAULT := 4
    endif

    ; track band count (set at parallax_section_end via the bands' offset)
parallax_section_band_count := 0
parallax_section_last_top   := -1
parallax_section_start      := *

    ; emit header (band_count placeholder = 0; rewritten at section_end)
    dc.b 0                                              ; pcfg_band_count
    dc.b V_FACTOR_BG, V_FACTOR_FG, LAYER_MASK
    dc.w V_CENTER, V_OFFSET
    dc.b TRANSITION, DEFORM_SPEED_FG, DEFORM_SPEED_BG, 0
    dc.l DEFORM_FG, DEFORM_BG
    dc.l V_DEFORM_BG
    dc.b V_DEFORM_SPEED_BG, V_DEFORM_SHIFT_BG
    dc.b 0, 0
endm

; ----------------------------------------------------------------------
; band — emit one band_entry record
; Positional args: top_cell, factor_a, factor_b
; Optional per-band fields read from globals (set via :=):
;   BAND_DSA, BAND_DSB (default = BAND_DSA_DEFAULT / BAND_DSB_DEFAULT, set by parallax_section)
;   BAND_PHASE (default 0, set by parallax_section)
;
; Author may override per-band:
;   BAND_PHASE := 64
;   band 4, FACTOR_1, FACTOR_1_4
; ----------------------------------------------------------------------
band macro top, factor_a, factor_b
    if parallax_section_band_count >= MAX_PARALLAX_BANDS
        fatal "parallax: more than \{MAX_PARALLAX_BANDS} bands"
    endif
    if (top) < 0 | (top) > 27
        fatal "parallax band: TOP=\{top} out of range 0..27"
    endif
    if (top) <= parallax_section_last_top
        fatal "parallax band: TOP=\{top} not strictly after previous band's TOP=\{parallax_section_last_top}"
    endif
parallax_section_last_top := (top)

    dc.b top
    dc.b (factor_a) & 15                        ; s1
    dc.b ((factor_a) >> 4) & 15                 ; s2
    dc.b ((factor_a) >> 8) & 1                  ; op
    dc.b (factor_b) & 15
    dc.b ((factor_b) >> 4) & 15
    dc.b ((factor_b) >> 8) & 1
    dc.b BAND_DSA
    dc.b BAND_DSB
    dc.b BAND_PHASE

parallax_section_band_count := parallax_section_band_count + 1
endm

; ----------------------------------------------------------------------
; parallax_section_end — close a parallax_config record
; ----------------------------------------------------------------------
parallax_section_end macro
    if parallax_section_band_count = 0
        fatal "parallax: section has no bands"
    endif

    ; patch band_count back into the header
    save
    org parallax_section_start
    dc.b parallax_section_band_count
    restore
endm
```

Also append to the macros file: defaults for `BAND_DSA` / `BAND_DSB` / `BAND_PHASE` (set inside `parallax_section` to the section-wide default; author can override per-band before invoking `band`):

```asm
; Set inside parallax_section opening (using DEFORM_SHIFT_DEFAULT and 0)
;   BAND_DSA := DEFORM_SHIFT_DEFAULT
;   BAND_DSB := DEFORM_SHIFT_DEFAULT
;   BAND_PHASE := 0
```

(parallax_section macro implementation should set these via `:=` so that subsequent `band` invocations within the section pick them up. Author may override before any specific `band` to vary phase/amplitude.)

- [ ] **Step 4: Include `parallax_macros.inc` in `S4.asm`**

Open `S4.asm`. Find the existing `include "structs.asm"` line. After all struct/constant includes, add:

```asm
include "engine/parallax_macros.inc"
```

The macros must be defined before any data file uses them.

- [ ] **Step 5: Add a build-only test invocation to verify macros assemble**

Create a minimal test file inline at the bottom of `engine/parallax_macros.inc` (guarded so it doesn't bloat the ROM):

```asm
    ifdef __PARALLAX_MACRO_SELFTEST__
ParallaxConfig_SelfTest:
    parallax_section LAYER_MASK=$0F, V_FACTOR_BG=3, V_CENTER=0, V_OFFSET=0
        band 0,  FACTOR_1, FACTOR_1_8
        band 4,  FACTOR_1, FACTOR_1_4
        band 10, FACTOR_1, FACTOR_3_8
        band 14, FACTOR_1, FACTOR_1_2
        band 20, FACTOR_1, FACTOR_1
    parallax_section_end

    ; Expected size: 22 (header) + 5 × 10 (bands) = 72 bytes
    if (* - ParallaxConfig_SelfTest) <> 72
        error "parallax_section selftest size mismatch: got \{*-ParallaxConfig_SelfTest}"
    endif
    endif
```

Build with self-test enabled:

```bash
cd /home/volence/sonic_hacks/s4_engine && asw -D __PARALLAX_MACRO_SELFTEST__ -P S4.asm 2>&1 | tail -20
```

Expected: build emits ParallaxConfig_SelfTest at exactly 72 bytes; no errors.

No fallback needed — the FACTOR_* named-equate form is verified working via the pre-flight spike.

- [ ] **Step 6: Run normal build to confirm no regressions**

```bash
cd /home/volence/sonic_hacks/s4_engine && ./build.sh -pe
```

Expected: build succeeds; ROM unchanged from Task 1's commit (no functional difference; the selftest is gated by `__PARALLAX_MACRO_SELFTEST__`).

- [ ] **Step 7: Commit**

```bash
git add engine/parallax_macros.inc S4.asm docs/research/parallax-§4.6.md
git commit -m "$(cat <<'EOF'
feat(§4.6): authoring macros — band, parallax_section, factor_decompose

Build-time machinery for §4.6 parallax. factor_decompose decomposes p/q
fractions to shift-add encoding (max 2 terms), fatals on unsupported
fractions. band macro emits 10-byte band_entry records with cross-band
validation (strictly ascending TOP, count limits, in-range checks).
parallax_section opens a 28-byte header + N inline band entries; the
section_end patches band_count.

Self-test gated by __PARALLAX_MACRO_SELFTEST__ verifies a 5-band record
emits exactly 72 bytes.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Deformation table generator macros

256-byte sine, triangle, custom, and per-column variants. All build-time. Independent of runtime — verifiable by inspecting emitted bytes.

**Files:**
- Modify: `engine/parallax_macros.inc`

- [ ] **Step 1: Research — sine/triangle table generation in AS**

Targets:
- **AS docs** — does AS have built-in `sin()`, `cos()`? Or does it need a build-time enumeration? (Older AS versions don't have transcendental functions.)
- **S.C.E.** — `Engine/Variables.asm` references `H_scroll_table ds.w 256`. Is the table pre-baked binary or generated by macro?
- **sonic_hack** — `data/` for any pre-baked sine tables; `code/` for any in-code emission.
- **SGDK** — `tools/sintab/` has a sine-table generator (Python). Could we adopt the same approach (generate `.bin` at build time via Python)?
- **CODING_CONVENTIONS.md** — "build-time computation over runtime" rule. Does this apply to ROM data generation too?

Decision points:
- If AS lacks `sin()`, generate via a host-side Python script in `tools/` and `BINCLUDE` the result. Add to build pipeline.
- If AS has it (or with a polynomial approximation macro), emit inline.

Append to research doc under "Task 3 — Build-time table generation strategy."

- [ ] **Step 2: Add `deform_table_sine` macro (or Python generator + BINCLUDE)**

If AS supports build-time sine via `function`s (verify in Step 1):

Append to `engine/parallax_macros.inc`:

```asm
; ----------------------------------------------------------------------
; deform_table_sine — emit 256-byte signed sine table
; Args: AMPLITUDE=<peak> (1..127), PERIOD=<frames per cycle, must divide 256>
; PHASE=<0..255> optional starting offset
; ----------------------------------------------------------------------
deform_table_sine macro
    if "AMPLITUDE" = ""
        fatal "deform_table_sine: AMPLITUDE required"
    endif
    if "PERIOD" = ""
        fatal "deform_table_sine: PERIOD required"
    endif
    if (256 # PERIOD) <> 0
        fatal "deform_table_sine: PERIOD=\{PERIOD} must divide 256"
    endif
    if "PHASE" = ""
deform_phase := 0
    else
deform_phase := PHASE
    endif
    ; emit 256 entries: sample = round(AMPLITUDE * sin(2π * (i + phase) / PERIOD))
    ; Use a fixed lookup ROM table or Taylor approximation function;
    ; details depend on AS capability (see Step 1 research).
    ; ... emit dc.b values ...
endm
```

If AS lacks sine, create a Python generator instead:

Create `tools/gen_deform_sine.py`:

```python
#!/usr/bin/env python3
import math, sys
amp = int(sys.argv[1])
period = int(sys.argv[2])
phase = int(sys.argv[3]) if len(sys.argv) > 3 else 0
for i in range(256):
    v = int(round(amp * math.sin(2 * math.pi * (i + phase) / period)))
    v = max(-128, min(127, v))
    sys.stdout.buffer.write(bytes([v & 0xFF]))
```

Then redefine the macro:

```asm
deform_table_sine macro AMPLITUDE,PERIOD,PHASE
    BINCLUDE "build/deform_sine_\{AMPLITUDE}_\{PERIOD}_\{PHASE}.bin"
endm
```

And add to `build.sh` — generate the .bin file before assembly.

(Either approach works. Decide based on Step 1 research; document choice in research doc.)

- [ ] **Step 3: Add `deform_table_triangle` and `deform_table_custom`**

Triangle is trivially expressible via shift-add at build time (no transcendentals), so always inline:

```asm
deform_table_triangle macro
    if "AMPLITUDE" = ""
        fatal "deform_table_triangle: AMPLITUDE required"
    endif
    if "PERIOD" = ""
        fatal "deform_table_triangle: PERIOD required"
    endif
    if (256 # PERIOD) <> 0
        fatal "deform_table_triangle: PERIOD=\{PERIOD} must divide 256"
    endif
    ; emit 256 entries: triangle wave from -AMPLITUDE to +AMPLITUDE over PERIOD samples
deform_tri_i set 0
    rept 256
deform_tri_x := deform_tri_i # PERIOD
        if deform_tri_x < (PERIOD/2)
            dc.b ((deform_tri_x * AMPLITUDE * 2) / (PERIOD/2)) - AMPLITUDE
        else
            dc.b AMPLITUDE - (((deform_tri_x - PERIOD/2) * AMPLITUDE * 2) / (PERIOD/2))
        endif
deform_tri_i set deform_tri_i + 1
    endm
endm

deform_table_custom macro
    ; user passes a list of bytes; macro validates count = 256
    ; (use AS's variadic argument support)
endm
```

(Note on `deform_table_custom`: AS's variadic macro syntax depends on version. Research strategies:
1. Take a label argument that the user pre-defines: `deform_table_custom DATA=mytable`.
2. Read 256 args via `_arg_count`/`_arg_n` if AS supports them.
The simpler path for v1: skip the custom macro entirely — users who need a custom table author it as raw `dc.b` data. Document accordingly.)

- [ ] **Step 4: Add per-column V-scroll table generators**

```asm
; ----------------------------------------------------------------------
; v_column_perspective — pseudo-3D floor ramp
; Args: FOCAL=<column index where shift = 0>, MAX_OFFSET=<peak shift at edges>
; Emits 256 bytes; first 40 are used as one shape, repeat for animation if speed>0
; ----------------------------------------------------------------------
v_column_perspective macro
    if "FOCAL" = ""
        fatal "v_column_perspective: FOCAL required"
    endif
    if "MAX_OFFSET" = ""
        fatal "v_column_perspective: MAX_OFFSET required"
    endif
    ; emit 256 entries: for column c (0..39 effective), offset = ((c - FOCAL) * MAX_OFFSET) / 20
    ; columns 40..255 fill with last column's value
v_persp_i set 0
    rept 256
        if v_persp_i < 40
            dc.b ((v_persp_i - FOCAL) * MAX_OFFSET) / 20
        else
            dc.b ((39 - FOCAL) * MAX_OFFSET) / 20
        endif
v_persp_i set v_persp_i + 1
    endm
endm

; ----------------------------------------------------------------------
; v_column_static — static shape from explicit byte list
; Pad list to 256 entries with the last value (for animation invariance).
; ----------------------------------------------------------------------
; (Skip v_column_static for v1 — same rationale as deform_table_custom.
; Users author static shapes as raw `dc.b` if needed.)
```

- [ ] **Step 5: Add self-test for table generators**

Append to `engine/parallax_macros.inc`:

```asm
    ifdef __PARALLAX_MACRO_SELFTEST__
TestSineTable:
    deform_table_sine AMPLITUDE=4, PERIOD=128
TestSineTable_End:
    if (TestSineTable_End - TestSineTable) <> 256
        error "deform_table_sine selftest: got \{TestSineTable_End-TestSineTable} bytes, expected 256"
    endif

TestTriangleTable:
    deform_table_triangle AMPLITUDE=8, PERIOD=64
TestTriangleTable_End:
    if (TestTriangleTable_End - TestTriangleTable) <> 256
        error "deform_table_triangle selftest: got \{TestTriangleTable_End-TestTriangleTable} bytes, expected 256"
    endif

TestPerspectiveTable:
    v_column_perspective FOCAL=20, MAX_OFFSET=12
TestPerspectiveTable_End:
    if (TestPerspectiveTable_End - TestPerspectiveTable) <> 256
        error "v_column_perspective selftest: got \{TestPerspectiveTable_End-TestPerspectiveTable} bytes, expected 256"
    endif
    endif
```

- [ ] **Step 6: Build with self-test enabled**

```bash
cd /home/volence/sonic_hacks/s4_engine && asw -D __PARALLAX_MACRO_SELFTEST__ -P S4.asm 2>&1 | tail -20
```

Expected: all three tables emit exactly 256 bytes. No errors.

- [ ] **Step 7: Verify generated values match expectation**

If using inline triangle generator, hand-spot-check: at AMPLITUDE=8, PERIOD=64, expected values:
- index 0: 0 - 8 = -8 (low byte 0xF8)
- index 16: peak = 8 (low byte 0x08)
- index 32: 0 (low byte 0x00)
- index 48: -8 (low byte 0xF8)

If using Python sine generator, run: `python3 tools/gen_deform_sine.py 4 128 0 | xxd | head -4` — confirm signed values cycle through 0, 1, 2, ..., 4, 3, 2, ..., 0, -1, ..., -4, ..., 0 across 128 entries, then repeat.

- [ ] **Step 8: Commit**

```bash
git add engine/parallax_macros.inc tools/gen_deform_sine.py build.sh docs/research/parallax-§4.6.md
git commit -m "$(cat <<'EOF'
feat(§4.6): deformation table generators — sine, triangle, perspective

Build-time generators for parallax deformation tables. deform_table_sine
emits 256-byte signed sine via [chosen approach: inline AS function /
Python helper + BINCLUDE]. deform_table_triangle is pure AS using
shift-add. v_column_perspective emits a pseudo-3D floor ramp for per-column
V-scroll. All gated by self-tests confirming 256-byte output.

deform_table_custom and v_column_static deferred — users author raw dc.b
data if needed (rare).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `Parallax_Init` + first parallax_config wired to OJZ + scaffolding

The minimum runtime path: `Parallax_State` initialized at level load with a known parallax_config. No per-frame work yet. Verifiable via Exodus MCP — `Parallax_State.current_config` should equal `&ParallaxConfig_OJZ_Default` after boot.

**Files:**
- Create: `data/parallax/ojz_default.asm`
- Create: `engine/level/parallax.asm` (skeleton — `Parallax_Init` only)
- Modify: `engine/level/load_art.asm` (call `Parallax_Init` after `BG_Init`)
- Modify: OJZ section descriptors to set `sec_parallax_config = ParallaxConfig_OJZ_Default`
- Modify: `S4.asm` (include the new files)

- [ ] **Step 1: Research — initialization sequence ordering**

Targets:
- **S.C.E.** — when does parallax/scroll state get initialized? Order vs BG load, palette load, plane buffer init?
- **sonic_hack** — `code/engines/scroll_camera.asm` Init paths.
- **TF4** — first-frame scroll setup.
- **s4_engine current** — `engine/level/load_art.asm`, `engine/level/section.asm:Section_Init`. What runs before `BG_Init`? After?

Question: should `Parallax_Init` run before or after `BG_Init`? After is cleaner (BG must exist before parallax operates on it). But VDP register $0B + $8C should be set before BG draw — verify by tracing the existing init sequence.

Append to research doc under "Task 4 — Init order."

- [ ] **Step 2: Create `data/parallax/ojz_default.asm`**

```asm
; data/parallax/ojz_default.asm — Default parallax config for OJZ Act 1 (initial test path)
;
; 5 bands, no deformation, whole-plane V-scroll. This is the bootstrap
; configuration that the engine uses while later tasks add deform variants.

ParallaxConfig_OJZ_Default:
    parallax_section LAYER_MASK=$1F, V_FACTOR_BG=3, V_CENTER=128, V_OFFSET=0
        band 0,  FACTOR_1, FACTOR_1_8       ; clouds
        band 4,  FACTOR_1, FACTOR_1_4       ; far mountains
        band 10, FACTOR_1, FACTOR_3_8       ; mid mountains
        band 14, FACTOR_1, FACTOR_1_2       ; hills
        band 20, FACTOR_1, FACTOR_1         ; ground (FG-sync)
    parallax_section_end
```

- [ ] **Step 3: Create skeleton `engine/level/parallax.asm` with `Parallax_Init`**

```asm
; engine/level/parallax.asm — §4.6 parallax pipeline
;
; Public:
;   Parallax_Init(a0=parallax_config*) — initialize Parallax_State at level load
;   Parallax_Update                    — main-loop per-frame builder (Task 5+)
;   Parallax_StartTransition(a0=new)   — section boundary handler (Task 8+)
;   Vscroll_Write                      — VBlank VSRAM emitter (Task 6+)

; ----------------------------------------------------------------------
; Parallax_Init — wipe Parallax_State and seed current_config
; In:  a0 = parallax_config* (must be non-null)
; Out: none
; Clobbers: d0, a1
; ----------------------------------------------------------------------
Parallax_Init:
        lea     (Parallax_State).w, a1
        moveq   #(Parallax_State_End-Parallax_State)/4-1, d0
        moveq   #0, d1
.zero:  move.l  d1, (a1)+
        dbf     d0, .zero

        move.l  a0, (Parallax_Current_Config).w
        ; Target_Config stays NULL (no transition in progress)
        ; Transition_Frames stays 0
        rts

; (Other routines stubbed in later tasks)
```

(Note: the `dbf` zero-loop assumes `Parallax_State_End-Parallax_State` is a multiple of 4. If not, pad `Parallax_State` accordingly in Task 1 — it currently is, since 80-byte column buf + 4-byte aligned other fields = multiple of 4.)

- [ ] **Step 4: Wire `Parallax_Init` into `Level_LoadArt`**

Open `engine/level/load_art.asm`. Find where `BG_Init` is called. Immediately after `BG_Init` returns (BG is drawn, palette loaded), add:

```asm
        ; -- §4.6 parallax init --
        movea.l (Current_Act_Ptr).w, a0
        ; Section 0 is the start section; pull its parallax_config
        movea.l Act_act_sections(a0), a0   ; a0 -> Sec_Desc[0]
        ; ... actually need to follow Act struct's section table to start_sec_x/y;
        ; for OJZ Act 1 with 1×1 grid this is just the first entry.
        movea.l sec_parallax_config(a0), a0
        bne.s   .have_pcfg
        ; No parallax_config — fall through (defaults to zero-fill, engine inert)
        suba.l  a0, a0          ; ensure a0 = NULL
        bra.s   .pcfg_done
.have_pcfg:
        bsr.w   Parallax_Init
.pcfg_done:
```

(Adjust the Act/Sec lookup to match the actual struct layout — verify with `grep "Act_" structs.asm`.)

- [ ] **Step 5: Wire OJZ Act 1 section descriptor to `ParallaxConfig_OJZ_Default`**

Find OJZ Act 1's section descriptor file (likely `data/levels/ojz/act1_sections.asm` or similar). Locate the section descriptor's `sec_parallax_config` field (offset $14). Set it to `ParallaxConfig_OJZ_Default` for all sections. For the bootstrap, just set sec0's; later tasks add per-section variants.

Example (exact form depends on existing section-descriptor authoring style):

```asm
OJZSection_0:
    dc.l ojz_strips_a              ; sec_strips_a
    dc.l 0                          ; sec_objects
    ...
    dc.l ParallaxConfig_OJZ_Default ; sec_parallax_config (was sec_scroll = 0)
    ...
```

- [ ] **Step 6: Include new files in S4.asm**

Open `S4.asm`. Add includes after existing engine includes:

```asm
include "data/parallax/ojz_default.asm"
include "engine/level/parallax.asm"
```

Order: `data/parallax/...` must come AFTER `parallax_macros.inc` (Task 2) and BEFORE the section descriptor file that references `ParallaxConfig_OJZ_Default`. `engine/level/parallax.asm` after.

- [ ] **Step 7: Build and verify in Exodus**

```bash
cd /home/volence/sonic_hacks/s4_engine && ./build.sh -pe
```

Load `s4.bin` in Exodus. Boot to OJZ. Use MCP:

```
emulator_pause
emulator_lookup_symbol "Parallax_Current_Config"
# read 4 bytes at that RAM address
emulator_read_memory <addr> 4
emulator_lookup_symbol "ParallaxConfig_OJZ_Default"
# verify the read value equals the symbol's ROM address
```

Expected: `Parallax_Current_Config` contains the ROM address of `ParallaxConfig_OJZ_Default`. If 0, init didn't run — debug.

- [ ] **Step 8: Commit**

```bash
git add data/parallax/ojz_default.asm engine/level/parallax.asm engine/level/load_art.asm S4.asm data/levels/ojz/<section_file>.asm docs/research/parallax-§4.6.md
git commit -m "$(cat <<'EOF'
feat(§4.6): Parallax_Init scaffold + ParallaxConfig_OJZ_Default

Engine boot now zero-fills Parallax_State and seeds Current_Config from
the start section's sec_parallax_config. ParallaxConfig_OJZ_Default
declares a 5-band layout (clouds/far/mid/hills/ground at factors
1/8, 1/4, 3/8, 1/2, 1) with no deformation. Verified via MCP that
Parallax_Current_Config holds the ROM address after boot.

No per-frame parallax behavior yet — Parallax_Update is empty.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: `Parallax_Update` — per-cell mode, no deform, no transition

The first per-frame compute. Implements pipeline steps 1-4 of the spec: phase advance (no-op when speeds are 0), transition state (passthrough when no transition), band scroll computation, per-cell HScroll buffer fill. No deformation sampling, no per-line, no V-scroll updates yet (those are Tasks 7, 9, 10, 12). HScroll buffer is built but **not yet DMA'd** — that's Task 6.

**Files:**
- Modify: `engine/level/parallax.asm` (add `Parallax_Update`)
- Modify: `engine/game_loop.asm` (call `Parallax_Update`)

- [ ] **Step 1: Research — main-loop scroll-update placement and buffer-fill pattern**

Targets:
- **S.C.E.** `MainGameLoop` ordering — where does scroll/parallax build relative to camera, objects, sprites?
- **sonic_hack** main-loop sequence in `code/level/level.asm` or similar.
- **TF4 / Vectorman / Batman** — scroll computation in main loop or interrupt? (Most engines: main loop.)
- **CODING_CONVENTIONS.md** — register-allocation and macro patterns for tight inner loops.

Cycle target for Parallax_Update Step 1-4 + per-cell fill: ~410 cycles (per spec). Verify the loop structure can hit that — band-scroll computation is 8 bands × ~10 cycles = 80 cycles; per-cell fill is 28 cells × ~10 cycles = 280 cycles; overhead ~50 cycles.

Append to research doc under "Task 5 — Main-loop placement and per-cell fill cost analysis."

- [ ] **Step 2: Read existing `engine/game_loop.asm` to find call insertion point**

```bash
cat engine/game_loop.asm
```

Find where camera/object updates run. `Parallax_Update` must run AFTER camera updates (it reads Camera_X/Y) and BEFORE `VBlank_Ready` is set (so the new buffer is ready for VBlank's DMA enqueue).

- [ ] **Step 3: Implement `Parallax_Update` per-cell path**

Append to `engine/level/parallax.asm`:

```asm
; ----------------------------------------------------------------------
; Parallax_Update — per-frame parallax buffer build
; In:  none (reads Camera_X, Camera_Y, Frame_Counter, Parallax_State,
;            Current_Config)
; Out: Hscroll_Buffer filled, Hscroll_Dirty_Start/End set,
;      Vscroll_Factor updated (Task 7+)
; Clobbers: d0-d7, a0-a3
; ----------------------------------------------------------------------
Parallax_Update:
        movea.l (Parallax_Current_Config).w, a0
        cmpa.w  #0, a0
        beq.w   .no_config              ; no parallax config; skip

        ; --- Step 1: phase advance (deform speeds; placeholder for Task 9+) ---
        ; (no-op when speeds = 0 from default OJZ config)
        moveq   #0, d0
        move.b  pcfg_deform_speed_fg(a0), d0
        add.w   d0, (Parallax_Deform_Phase_FG).w
        and.w   #$FF, (Parallax_Deform_Phase_FG).w

        move.b  pcfg_deform_speed_bg(a0), d0
        add.w   d0, (Parallax_Deform_Phase_BG).w
        and.w   #$FF, (Parallax_Deform_Phase_BG).w

        move.b  pcfg_v_deform_speed_bg(a0), d0
        add.w   d0, (Parallax_V_Deform_Phase_BG).w
        and.w   #$FF, (Parallax_V_Deform_Phase_BG).w

        ; --- Step 2: transition state (Task 14 fills this in; passthrough for now) ---
        ; (no transitions yet)

        ; --- Step 3: compute per-band target scrolls + lerp ---
        move.l  (Camera_X).w, d7
        swap    d7                       ; d7.w = camX in pixels (signed)

        moveq   #0, d6                   ; band index
        moveq   #0, d5
        move.b  pcfg_band_count(a0), d5  ; band count
        beq.w   .no_config

        lea     pcfg_bands(a0), a1       ; a1 = first band entry
        lea     (Parallax_Current_Scroll_A).w, a2
        lea     (Parallax_Current_Scroll_B).w, a3
        moveq   #0, d4                   ; layer mask iterator
        move.b  pcfg_layer_mask(a0), d4
        moveq   #0, d3                   ; previous-band scroll A (for inheritance)
        moveq   #0, d2                   ; previous-band scroll B

.band_loop:
        btst    d6, d4
        beq.s   .band_disabled

        ; -- target_a = decode_factor(camX, factor_a) --
        move.w  d7, d0                   ; d0 = camX
        bsr.w   Decode_Factor_A          ; uses a1, returns d0 = target_a
        ; lerp: current_a += (target - current_a) >> PARALLAX_LERP_SHIFT
        move.w  (a2), d1                 ; current_a
        sub.w   d1, d0                   ; delta
        asr.w   #PARALLAX_LERP_SHIFT, d0
        add.w   d0, d1
        move.w  d1, (a2)                 ; updated current_a
        move.w  d1, d3                   ; remember for next-band inheritance

        move.w  d7, d0
        bsr.w   Decode_Factor_B          ; returns d0 = target_b
        move.w  (a3), d1
        sub.w   d1, d0
        asr.w   #PARALLAX_LERP_SHIFT, d0
        add.w   d0, d1
        move.w  d1, (a3)
        move.w  d1, d2
        bra.s   .band_done

.band_disabled:
        ; Inherit previous band's scroll (or 0 if first band)
        move.w  d3, (a2)
        move.w  d2, (a3)

.band_done:
        addq.l  #band_entry_len, a1
        addq.l  #2, a2
        addq.l  #2, a3
        addq.w  #1, d6
        cmp.w   d5, d6
        blo.s   .band_loop

        ; --- Step 4: fill HScroll buffer (per-cell mode for Task 5; per-line in Task 9) ---
        ; Mode = per-cell when both deform_table_fg AND deform_table_bg are NULL
        move.l  pcfg_deform_table_fg(a0), d0
        or.l    pcfg_deform_table_bg(a0), d0
        bne.s   .skip_per_cell           ; per-line mode (Task 9)
        bsr.w   Parallax_Fill_PerCell

.skip_per_cell:
        ; Mark dirty range (Task 6 reads these for variable DMA)
        move.b  #0, (Hscroll_Dirty_Start).w
        move.b  #27, (Hscroll_Dirty_End).w  ; per-cell: 28 cells, last index 27

.no_config:
        rts

; ----------------------------------------------------------------------
; Decode_Factor_A — return Plane A scroll value for a band
; In:  d0.w = camX, a1 = band_entry*
; Out: d0.w = -((camX >> s1) [+/-] (camX >> s2)) for VDP convention
;      (s1 = 15 → result = 0, "locked")
; ----------------------------------------------------------------------
Decode_Factor_A:
        move.b  band_factor_a_s1(a1), d1
        cmp.b   #15, d1
        beq.s   .locked
        move.w  d0, d2
        asr.w   d1, d2                   ; first term
        move.b  band_factor_a_s2(a1), d1
        cmp.b   #15, d1
        beq.s   .single
        move.w  d0, d3
        asr.w   d1, d3                   ; second term
        tst.b   band_factor_a_op(a1)
        bne.s   .sub
        add.w   d3, d2
        bra.s   .negate
.sub:
        sub.w   d3, d2
.negate:
        neg.w   d2
        move.w  d2, d0
        rts
.single:
        neg.w   d2
        move.w  d2, d0
        rts
.locked:
        moveq   #0, d0
        rts

Decode_Factor_B:
        ; Same shape as Decode_Factor_A but reads band_factor_b_* fields.
        move.b  band_factor_b_s1(a1), d1
        cmp.b   #15, d1
        beq.s   Decode_Factor_A.locked   ; reuse the locked tail
        move.w  d0, d2
        asr.w   d1, d2
        move.b  band_factor_b_s2(a1), d1
        cmp.b   #15, d1
        beq.s   Decode_Factor_A.single
        move.w  d0, d3
        asr.w   d1, d3
        tst.b   band_factor_b_op(a1)
        bne.s   .sub
        add.w   d3, d2
        bra.s   Decode_Factor_A.negate
.sub:
        sub.w   d3, d2
        bra.s   Decode_Factor_A.negate

; ----------------------------------------------------------------------
; Parallax_Fill_PerCell — emit 28 longwords from current_scroll arrays
; In:  a0 = parallax_config*, d5 = band_count
; Out: Hscroll_Buffer filled
; Clobbers: d0-d4, a1-a3
; ----------------------------------------------------------------------
Parallax_Fill_PerCell:
        lea     (Hscroll_Buffer).w, a3
        lea     pcfg_bands(a0), a1
        lea     (Parallax_Current_Scroll_A).w, a2
        moveq   #0, d6                   ; current band index
        moveq   #0, d4                   ; current cell index = 0
        move.b  band_top_cell(a1), d3    ; first band's top (should be 0)

.next_band:
        ; Compute end_cell = next_band's top OR 28 if last band
        addq.w  #1, d6
        cmp.w   d5, d6
        bhi.s   .last_band
        addq.l  #band_entry_len, a1
        move.b  band_top_cell(a1), d2    ; next band's top
        subq.l  #band_entry_len, a1      ; rewind to current band
        bra.s   .have_end
.last_band:
        moveq   #28, d2
.have_end:

        ; Pack scroll value: (-current_scroll_a << 16) | (-current_scroll_b & $FFFF)
        move.w  (a2), d0                 ; current_a (already negated by Decode_Factor)
        move.w  (a2,8.w), d1             ; (Parallax_Current_Scroll_B - Parallax_Current_Scroll_A) = 16 bytes; wait, recheck
        ; ...

        ; Detail: scroll values are stored as already-negated (VDP convention).
        ; Pack into longword: high word = Plane A, low word = Plane B.
        swap    d0
        move.w  d1, d0                   ; d0 = (A << 16) | B

        ; Fill cells [d3..d2)
.fill:
        move.l  d0, (a3,d3.w*4)          ; Hscroll_Buffer[cell] = packed
        addq.w  #1, d3
        cmp.w   d2, d3
        blo.s   .fill

        ; Advance to next band
        addq.l  #band_entry_len, a1
        addq.l  #2, a2
        cmp.w   d5, d6
        blo.s   .next_band
        rts
```

(Note: the addressing for current_scroll_b in `Parallax_Fill_PerCell` needs to use the actual offset between `Parallax_Current_Scroll_A` and `Parallax_Current_Scroll_B`. From `ram.asm`, that's `2*MAX_PARALLAX_BANDS = 16` bytes. Use that constant or compute via `Parallax_Current_Scroll_B-Parallax_Current_Scroll_A`. Verify in implementation; the pseudo-code above is illustrative — the engineer should write tight 68000 that produces the correct (A_neg, B_neg) longword per cell.)

- [ ] **Step 4: Wire `Parallax_Update` into the main loop**

Open `engine/game_loop.asm`. Find where camera updates run. After all camera + object updates, before `VBlank_Ready` is set, insert:

```asm
        bsr.w   Parallax_Update
```

- [ ] **Step 5: Build and verify buffer contents via MCP**

```bash
cd /home/volence/sonic_hacks/s4_engine && ./build.sh -pe
```

Load in Exodus. Boot to OJZ. Pause emulator with camera at a known position (e.g., scroll right ~512 px so Camera_X = $200). Use MCP:

```
emulator_lookup_symbol "Hscroll_Buffer"
emulator_read_memory <addr> 112    # 28 cells × 4 bytes
```

Expected layout (with camX = $200 = 512):
- Cells 0-3 (band 0, factor 1/8): A=-512 (0xFE00), B=-(512>>3)=-64 (0xFFC0)
- Cells 4-9 (band 1, factor 1/4): A=-512, B=-(512>>2)=-128 (0xFF80)
- Cells 10-13 (band 2, factor 3/8): A=-512, B=-(128+64)=-192 (0xFF40)
- Cells 14-19 (band 3, factor 1/2): A=-512, B=-256 (0xFF00)
- Cells 20-27 (band 4, factor 1): A=-512, B=-512 (0xFE00)

Verify a few sample cells. If wrong, debug Decode_Factor / fill loop.

- [ ] **Step 6: Commit**

```bash
git add engine/level/parallax.asm engine/game_loop.asm docs/research/parallax-§4.6.md
git commit -m "$(cat <<'EOF'
feat(§4.6): Parallax_Update — per-cell band fill + factor decoding

Per-frame parallax compute. Reads Camera_X, decodes per-band factor via
shift-add (no muls), lerps current_scroll_a/b toward target, fills 28-cell
HScroll buffer with negated A/B values per band. Layer mask handled via
previous-band inheritance. Per-line mode + deformation deferred to Task 9.

HScroll buffer not yet DMA'd to VDP (Task 6). Verified buffer contents
via MCP at known camX positions for the 5-band OJZ config.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: HScroll DMA wiring + VBlank reorder — visible parallax

Connects the buffer to the VDP. Static DMA descriptor for per-cell mode (per-line + dynamic-mode-switching come in Task 9). VBlank order reorganized so HScroll DMA drains before VSRAM write. After this task, **OJZ visibly parallaxes** when the camera moves.

**Files:**
- Modify: `engine/buffers.asm` (add `Static_Hscroll_Cell` descriptor; update `Enqueue_Dirty_Buffers`)
- Modify: `engine/vblank.asm` (reorder, add `Vscroll_Write` stub call)
- Modify: `engine/level/parallax.asm` (add `Vscroll_Write` stub — just writes Vscroll_Factor as before)
- Delete: `engine/level/hscroll.asm` (placeholder stub no longer needed)
- Modify: `S4.asm` (remove the deleted file's include)

- [ ] **Step 1: Research — DMA descriptor and queue patterns**

Targets:
- **s4_engine current** — `engine/buffers.asm:Static_Pal_Line0` etc., `engine/dma_queue.asm:queueStaticDMA`, `Process_DMA_Critical`. How are descriptors structured? How does `queueStaticDMA` work?
- **S.C.E.** DMA queue patterns.
- **CODING_CONVENTIONS.md** — DMA + VBlank rules.

Specific question: can `queueStaticDMA` accept a runtime-selected descriptor (e.g. branch and queue different ones), or must the call site be statically known? Read the macro implementation.

Append to research doc under "Task 6 — DMA descriptor patterns."

- [ ] **Step 2: Add `Static_Hscroll_Cell` DMA descriptor**

Open `engine/buffers.asm`. Find the existing static DMA descriptors (`Static_Pal_Line0`, etc.). Add:

```asm
Static_Hscroll_Cell:
        static_dma source=Hscroll_Buffer, dest=VRAM_HSCROLL_TABLE, length=112, type=VRAM
```

(Look up the actual `static_dma` macro syntax in `engine/dma_queue.asm` and match the existing descriptors' form.)

- [ ] **Step 3: Update `Enqueue_Dirty_Buffers` to enqueue HScroll DMA**

In `engine/buffers.asm`, modify `Enqueue_Dirty_Buffers`. After the existing palette + sprite enqueues, before the `rts`, add:

```asm
        ; -- §4.6 HScroll DMA --
        ; v1: always per-cell. Per-line + mode-select in Task 9.
        movea.l (Parallax_Current_Config).w, a1
        cmpa.w  #0, a1
        beq.s   .no_hscroll
        queueStaticDMA DMA_Critical_Slot, DMA_Critical_End, Static_Hscroll_Cell
.no_hscroll:
```

- [ ] **Step 4: Reorder `VInt_Level` and `VInt_Lag`**

Open `engine/vblank.asm`. Replace `VInt_Level` (currently lines 29-54):

```asm
VInt_Level:
        ; --- VDP work (Z80 stopped) ---
        stopZ80

        bsr.w   Flush_VDP_Shadow

        bsr.w   Enqueue_Dirty_Buffers       ; queues palette + sprites + HScroll

        bsr.w   VInt_DrawLevel              ; drain Plane_Buffer to VDP (§4.1)

        bsr.w   Process_DMA_Critical        ; drains palette + sprites + HScroll

        ; -- §4.6: Vscroll write must come AFTER HScroll DMA to avoid tear --
        bsr.w   Vscroll_Write

        move.w  (DMA_Budget_Default).w, (DMA_Budget_Remaining).w
        bsr.w   Process_DMA_Important
        bsr.w   Process_DMA_Deferrable

        startZ80

        ; --- Non-VDP work ---
        bsr.w   Read_Controllers
        addq.w  #1, (Frame_Counter).w
        move.b  #1, (VBlank_Flag).w
        rts
```

Replace `VInt_Lag` similarly:

```asm
VInt_Lag:
        stopZ80

        bsr.w   Flush_VDP_Shadow
        bsr.w   Enqueue_Dirty_Buffers
        bsr.w   VInt_DrawLevel
        bsr.w   Process_DMA_Critical
        bsr.w   Vscroll_Write

        startZ80

        bsr.w   Read_Controllers
        addq.w  #1, (Frame_Counter).w
        move.b  #1, (VBlank_Flag).w

    ifdef __DEBUG__
        addq.l  #1, (Lag_Frame_Count).w
    endif
        rts
```

- [ ] **Step 5: Add `Vscroll_Write` stub to parallax.asm**

Append to `engine/level/parallax.asm`:

```asm
; ----------------------------------------------------------------------
; Vscroll_Write — emit Vscroll_Factor (whole-plane) or column buffer (per-column)
; In:  none (reads Parallax_Current_Config, Vscroll_Factor or column buf)
; Out: VSRAM written
; Clobbers: d0, a0
;
; v1 (Task 6): always whole-plane, just writes Vscroll_Factor.
; Per-column path added in Task 12.
; ----------------------------------------------------------------------
Vscroll_Write:
        move.l  #vdpComm(0, VSRAM, WRITE), (VDP_CTRL).l
        move.l  (Vscroll_Factor).w, (VDP_DATA).l
        rts
```

- [ ] **Step 6: Delete `engine/level/hscroll.asm` and remove its include**

```bash
git rm engine/level/hscroll.asm
```

Open `S4.asm`. Find and remove the `include "engine/level/hscroll.asm"` line.

- [ ] **Step 7: Build and verify visually in Exodus**

```bash
cd /home/volence/sonic_hacks/s4_engine && ./build.sh -pe
```

Load in Exodus. Boot to OJZ. Use the controller to scroll right. **Expected visual: Plane B shows different scroll speeds in horizontal bands.** With the current single-layer OJZ BG art (one Z-flat layout), the bands all look the same artistically, but they SCROLL at different rates — verifiable by:

```
emulator_pause
emulator_lookup_symbol "Hscroll_Buffer"
emulator_read_memory <addr> 112
# Verify cell 0 (clouds) Plane B value scrolls slower than cell 27 (ground)
```

Or visually: scroll a known distance, observe Plane B's apparent shift relative to Plane A.

Verify VBlank ordering via VRAM read:
```
emulator_run_to_scanline 1   # just past VBlank end
emulator_read_vram $DC00 4   # first HScroll table entry
# Should match Hscroll_Buffer[0]
emulator_read_vsram 0 4
# Should match Vscroll_Factor
```

If HScroll_Buffer values are NOT in VRAM $DC00 after VBlank, debug DMA wiring.

- [ ] **Step 8: Commit**

```bash
git add engine/buffers.asm engine/vblank.asm engine/level/parallax.asm S4.asm docs/research/parallax-§4.6.md
git rm engine/level/hscroll.asm
git commit -m "$(cat <<'EOF'
feat(§4.6): HScroll DMA wiring + VBlank reorder — visible parallax

Static_Hscroll_Cell descriptor (112-byte VRAM DMA) added to Critical
queue. VBlank reordered: Vscroll write moved from first-thing to after
Process_DMA_Critical (per research finding — HScroll DMA must drain
before VSRAM write or one-frame tear). Stub Vscroll_Write retains
existing whole-plane behavior; per-column path lands in Task 12.

Deletes the unused engine/level/hscroll.asm placeholder; new pipeline
lives in engine/level/parallax.asm.

OJZ visibly parallaxes when camera moves, verified via VRAM \$DC00 read
matching Hscroll_Buffer post-VBlank.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Vertical parallax (whole-plane)

Implement spec pipeline Step 5 whole-plane branch: `Vscroll_Factor` updated each frame from `Camera_Y` and the section's V-anchor parameters. Per-column V-scroll deferred to Task 12.

**Files:**
- Modify: `engine/level/parallax.asm` (add Step 5 to `Parallax_Update`)

- [ ] **Step 1: Research — vertical parallax in reference engines**

Targets:
- **S.C.E.** `Engine/Core/Camera*.asm` and `Deformation Script.asm` for vertical scroll handling. How is the Y-anchor offset applied?
- **sonic_hack** — `Hztl_Vrtc_Bg_Deformation` (already familiar from Task 1 research). Hardcoded per-zone, but the Y-math is the same idea.
- **TF4** — vertical parallax in stage 5 (descent stage). How is camera Y mapped to BG vscroll?
- **Vectorman** — vertical parallax usage with 64×64 plane.
- **plutiedev / md.railgun** — VSRAM whole-plane semantics.

Settle: should the section's `V_CENTER` be in pixel space (matching `Camera_Y`'s pixel-high-word units)? Yes per spec.

Append to research doc under "Task 7 — Vertical parallax math."

- [ ] **Step 2: Implement Step 5 (whole-plane only) in `Parallax_Update`**

Open `engine/level/parallax.asm`. After Step 4 (per-cell fill) and before the dirty-mark + `rts`, add:

```asm
        ; --- Step 5: compute Vscroll (whole-plane only; per-column in Task 12) ---
        movea.l (Parallax_Current_Config).w, a0
        move.l  pcfg_v_deform_table_bg(a0), d0
        bne.s   .v_per_column           ; per-column path (Task 12)

        ; -- whole-plane V-scroll --
        move.l  (Camera_Y).w, d0
        swap    d0                       ; d0.w = camY in pixels (signed)
        move.w  d0, d1                   ; d1 = camY (FG = camY directly)

        sub.w   pcfg_v_center_y(a0), d0  ; d0 = camY - center_y
        moveq   #0, d2
        move.b  pcfg_v_factor_bg(a0), d2
        asr.w   d2, d0                   ; >> v_factor_bg
        add.w   pcfg_v_offset(a0), d0    ; + v_offset
        move.w  d0, d2                   ; d2 = target_bg

        ; lerp current_vscroll_bg toward target_bg
        move.w  (Parallax_Current_Vscroll_BG).w, d0
        sub.w   d0, d2
        asr.w   #PARALLAX_LERP_SHIFT, d2
        add.w   d2, d0
        move.w  d0, (Parallax_Current_Vscroll_BG).w

        ; pack into Vscroll_Factor: (FG_word << 16) | BG_word
        ; Note: VDP scroll is positive-into-tilemap; camera convention is positive-rightward;
        ; check existing Hscroll convention — we negate there too.
        ; For VSCROLL: a positive value scrolls the plane DOWN. Convention from
        ; existing Vscroll_Factor write (engine/vblank.asm:36) — verify the sign
        ; matches the existing camera math.
        swap    d1
        move.w  d0, d1
        move.l  d1, (Vscroll_Factor).w
        bra.s   .v_done

.v_per_column:
        ; Task 12 — placeholder, falls through to whole-plane for now
        bra.s   .v_done                  ; remove when Task 12 lands

.v_done:
```

(Note on sign convention: review Hscroll's negation — the existing `Hscroll_Update` stub did `neg.w d0` because VDP scroll is negative of camera position. Verify VSCROLL behaves the same — read the Vscroll_Factor's existing write order and any documentation in `engine/vdp_init.asm`.)

- [ ] **Step 3: Build and visually verify**

```bash
cd /home/volence/sonic_hacks/s4_engine && ./build.sh -pe
```

Load in Exodus. Boot to OJZ. Move camera up/down (if level allows). Plane B should shift vertically at fractional rate.

For OJZ Act 1 with camY = 0 fixed (no vertical movement yet), this is hard to test in-game. Alternative MCP test:

```
emulator_pause
emulator_write_memory <Camera_Y_addr> 4 00010000      # camera_y = $0001 high word = 1 pixel
# step one frame
emulator_step
emulator_lookup_symbol "Vscroll_Factor"
emulator_read_memory <addr> 4
# Verify FG word = 1, BG word ≈ 0 (1 pixel >> 3 = 0)

emulator_write_memory <Camera_Y_addr> 4 00800000      # camera_y = $0080 = 128 pixels
emulator_step
emulator_read_memory <addr> 4
# Verify FG word = 128, BG word = 0 (128 - 128 (V_CENTER)) >> 3 + 0 = 0
```

- [ ] **Step 4: Commit**

```bash
git add engine/level/parallax.asm docs/research/parallax-§4.6.md
git commit -m "$(cat <<'EOF'
feat(§4.6): vertical parallax — whole-plane Vscroll from camera_y

Parallax_Update Step 5 now computes Vscroll_Factor per frame:
  fg_vscroll = camY
  bg_vscroll = ((camY - v_center_y) >> v_factor_bg) + v_offset (lerp'd)

Section's V_CENTER + V_OFFSET act as the BG anchor; camera deviation from
center_y drives BG at v_factor_bg/8 of camera Y rate. Per-column V-scroll
path stubbed (falls through to whole-plane); implemented in Task 12.

MCP-verified Vscroll_Factor matches expected math at scripted Camera_Y
positions for the OJZ default config (V_CENTER=128, V_FACTOR_BG=3).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Section transition hook (instant snap)

Adds the per-section parallax_config swap on section transition. **Instant snap only** (transition_type = 1 path). Smooth lerp transitions land in Task 14. Also writes VDP $0B and $8C mode bits via shadow when crossing sections that change H/V mode.

**Files:**
- Modify: `engine/level/parallax.asm` (add `Parallax_StartTransition`)
- Modify: `engine/level/section.asm` (`Section_Check` calls into parallax on config change; shadow $0B + $8C)

- [ ] **Step 1: Research — section transition state-swap patterns**

Targets:
- **s4_engine current** — `engine/level/section.asm:Section_Check` and the existing teleport paths (`Section_TeleportFwd`, `Section_TeleportBwd`). When does new section state become "active"?
- **S.C.E.** `Engine/Core/Sections.asm` (or equivalent) — does it swap parallax-related state per-section?
- **sonic_hack** — does the per-zone hardcoded approach swap on level boundaries?
- **CODING_CONVENTIONS.md** — VDP shadow write timing.

Specific question: at what point in `Section_Check`'s flow should `Parallax_StartTransition` fire? Before or after `BG_RedrawForSection`?

Append to research doc under "Task 8 — Section transition state ordering."

- [ ] **Step 2: Add `Parallax_StartTransition` (instant-snap only)**

Append to `engine/level/parallax.asm`:

```asm
; ----------------------------------------------------------------------
; Parallax_StartTransition — handle parallax_config change at section boundary
; In:  a0 = new parallax_config* (NULL = inherit from previous, no-op)
; Out: Current_Config swapped (instant snap path); transition state cleared.
;      Updates VDP shadow for $0B (vmode) and $8C (hmode).
; Clobbers: d0, a1
;
; v1 (Task 8): instant snap regardless of pcfg_transition. Smooth lerp
; (transition_type = 0) lands in Task 14.
; ----------------------------------------------------------------------
Parallax_StartTransition:
        cmpa.w  #0, a0
        beq.s   .no_change                ; inherit / no-op

        cmpa.l  (Parallax_Current_Config).w, a0
        beq.s   .no_change                ; same config; nothing to do

        move.l  a0, (Parallax_Current_Config).w
        move.l  #0, (Parallax_Target_Config).w
        move.b  #0, (Parallax_Transition_Frames).w

        ; -- Update VDP shadow $0B (Mode Set 3) bit 2: 0=whole-plane V, 1=per-column V --
        move.l  pcfg_v_deform_table_bg(a0), d0
        seq     d1                        ; d1 = $FF if zero (whole-plane), $00 if non-zero
        ; ... read current shadow value, mask bit 2, set to NOT d1
        ; (Use the existing VDP shadow-write helper — see engine/vdp_init.asm or
        ; structs.asm for the shadow byte name. Likely vdp_mode3 in VDP_Reg_Shadow.)

        ; -- Update VDP shadow $8C (Mode Set 4) bits 1-0: 10=per-cell, 11=per-line --
        move.l  pcfg_deform_table_fg(a0), d0
        or.l    pcfg_deform_table_bg(a0), d0
        ; d0 nonzero → per-line mode (bits = 11), d0 zero → per-cell (bits = 10)
        ; Update VDP_Reg_Shadow's vdp_mode4 byte accordingly.

.no_change:
        rts
```

(Note: the VDP shadow write code depends on the engine's existing shadow-helper API. Look up `Flush_VDP_Shadow` and the shadow struct in `engine/vdp_init.asm` or wherever it's defined — match the existing pattern.)

- [ ] **Step 3: Wire `Parallax_StartTransition` into `Section_Check`**

Open `engine/level/section.asm`. Find the section-transition completion path (where the new section becomes active — likely at the end of `Section_TeleportFwd` / `Section_TeleportBwd` after `BG_RedrawForSection`). Add:

```asm
        ; -- §4.6 parallax transition --
        movea.l <new_section_ptr_register>, a0
        movea.l sec_parallax_config(a0), a0
        bsr.w   Parallax_StartTransition
```

(Replace `<new_section_ptr_register>` with the actual register holding the new section pointer at that point — probably `a0` or similar; verify by reading the existing teleport code.)

- [ ] **Step 4: Build and verify on a section transition**

For OJZ Act 1, a section transition happens when scrolling past the section boundary. Author OJZ Section 1 with a different parallax_config (a stub that swaps two band factors, e.g., `1/8` for clouds becomes `1/4`). Then in Exodus:

```
emulator_pause
# trigger a section transition by scrolling
# pause again post-transition
emulator_lookup_symbol "Parallax_Current_Config"
emulator_read_memory <addr> 4
# verify it now equals &ParallaxConfig_OJZ_Sec1 (or whatever the new config is)
```

If section descriptors have only one parallax_config wired at this point (`ParallaxConfig_OJZ_Default`), create a temporary minimal `ParallaxConfig_OJZ_Sec1` to test the swap. Remove or repurpose in later tasks.

- [ ] **Step 5: Commit**

```bash
git add engine/level/parallax.asm engine/level/section.asm data/parallax/ojz_default.asm docs/research/parallax-§4.6.md
git commit -m "$(cat <<'EOF'
feat(§4.6): section transition hook — instant snap parallax_config swap

Section_Check now calls Parallax_StartTransition on section boundary.
Current_Config swapped instantly (smooth lerp transitions deferred to
Task 14). VDP shadow updated for register $0B bit 2 (vmode) and $8C
bits 1-0 (hmode) based on new config's deformation table presence.

MCP-verified Current_Config swaps when scrolling across section boundary.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Per-line mode + H-deformation

Adds the per-line buffer fill path with FG/BG deformation sampling. After this task, sections with `DEFORM_FG=` or `DEFORM_BG=` set produce wavy per-line scroll. Also extends DMA wiring to switch between cell and line modes.

**Files:**
- Modify: `engine/level/parallax.asm` (add `Parallax_Fill_PerLine`)
- Modify: `engine/buffers.asm` (add `Static_Hscroll_Line`, mode-switching enqueue)

- [ ] **Step 1: Research — per-line buffer fill optimization**

Targets:
- **S.C.E.** `Engine/Core/Deformation Script.asm:HScroll_Deform` lines 12-26. The cycle-tight inner loop pattern is here.
- **TF4** raw disasm — search for any 224-iteration loops near scroll work.
- **CODING_CONVENTIONS.md** — register usage in tight loops, `dbf` vs unrolled.

Specific question: can the per-line loop be partially unrolled (e.g., 4 lines per iteration) for speed without ROM bloat? Research the cost-benefit.

Append to research doc under "Task 9 — Per-line fill optimization."

- [ ] **Step 2: Add `Parallax_Fill_PerLine` to parallax.asm**

Append to `engine/level/parallax.asm`:

```asm
; ----------------------------------------------------------------------
; Parallax_Fill_PerLine — emit 224 longwords with deformation sampling
; In:  a0 = parallax_config*
;      d5 = band_count
;      Parallax_Deform_Phase_FG/BG already advanced
;      Parallax_Current_Scroll_A/B already lerp'd
; Out: Hscroll_Buffer filled (224 longwords)
; Clobbers: d0-d6, a1-a4
; ----------------------------------------------------------------------
Parallax_Fill_PerLine:
        lea     (Hscroll_Buffer).w, a4
        lea     pcfg_bands(a0), a1
        lea     (Parallax_Current_Scroll_A).w, a2
        lea     (Parallax_Current_Scroll_B).w, a3

        movea.l pcfg_deform_table_fg(a0), a5  ; NULL = no FG sampling
        movea.l pcfg_deform_table_bg(a0), a6  ; NULL = no BG sampling

        moveq   #0, d6                   ; band index = 0

.next_band:
        ; Compute line range [start, end) for this band
        moveq   #0, d3
        move.b  band_top_cell(a1), d3
        lsl.w   #3, d3                   ; * 8 → line index
        moveq   #28*8, d2                ; default end = last line + 1
        addq.w  #1, d6
        cmp.w   d5, d6
        bhi.s   .last_band_end
        addq.l  #band_entry_len, a1
        moveq   #0, d2
        move.b  band_top_cell(a1), d2
        lsl.w   #3, d2
        subq.l  #band_entry_len, a1
.last_band_end:

        ; Pre-compute per-band constants
        move.w  (a2), d0                 ; current_scroll_a (already negated)
        move.w  (a3), d1                 ; current_scroll_b (already negated)

        moveq   #0, d4                   ; phase offset
        move.b  band_phase_offset(a1), d4

        ; Per-line loop
.line:
        move.w  d0, d2                   ; running A scroll for this line
        move.w  d1, d3                   ; running B scroll for this line

        ; -- FG sample (if a5 != NULL and dsa != 15) --
        cmpa.w  #0, a5
        beq.s   .no_fg_sample
        ; index = (deform_phase_fg + line + phase) & $FF
        ; ... sample a5[index], sign-extend, shift by dsa, add to d2
.no_fg_sample:

        ; -- BG sample (similar) --
        cmpa.w  #0, a6
        beq.s   .no_bg_sample
        ; ... add to d3
.no_bg_sample:

        ; Pack and emit
        swap    d2
        move.w  d3, d2
        move.l  d2, (a4,d3.w*4)          ; wait — addressing wrong; use line index

        ; Increment line
        addq.l  #4, a4
        addq.w  #1, d3
        cmp.w   d2, d3
        blo.s   .line

        ; Advance to next band
        addq.l  #band_entry_len, a1
        addq.l  #2, a2
        addq.l  #2, a3
        cmp.w   d5, d6
        blo.s   .next_band
        rts
```

(The pseudo-code has a register-clobber bug — d3 is reused for both line index and band-B value. The engineer implementing this should redo register assignment cleanly. Use a fixed mental model: a4 = output ptr, d4 = line counter, d5 = band count, etc., and document register usage at the top.)

- [ ] **Step 3: Update `Parallax_Update` Step 4 to dispatch on mode**

In `engine/level/parallax.asm:Parallax_Update`, replace the per-cell-only Step 4 with a mode-dispatch:

```asm
        ; --- Step 4: fill HScroll buffer ---
        move.l  pcfg_deform_table_fg(a0), d0
        or.l    pcfg_deform_table_bg(a0), d0
        beq.s   .fill_per_cell
        bsr.w   Parallax_Fill_PerLine
        move.b  #0, (Hscroll_Dirty_Start).w
        move.b  #223, (Hscroll_Dirty_End).w
        bra.s   .fill_done
.fill_per_cell:
        bsr.w   Parallax_Fill_PerCell
        move.b  #0, (Hscroll_Dirty_Start).w
        move.b  #27, (Hscroll_Dirty_End).w
.fill_done:
```

- [ ] **Step 4: Add `Static_Hscroll_Line` and mode-switching enqueue**

In `engine/buffers.asm`, add the line-mode descriptor next to `Static_Hscroll_Cell`:

```asm
Static_Hscroll_Line:
        static_dma source=Hscroll_Buffer, dest=VRAM_HSCROLL_TABLE, length=896, type=VRAM
```

Update `Enqueue_Dirty_Buffers` to switch:

```asm
        movea.l (Parallax_Current_Config).w, a1
        cmpa.w  #0, a1
        beq.s   .no_hscroll
        move.l  pcfg_deform_table_fg(a1), d0
        or.l    pcfg_deform_table_bg(a1), d0
        beq.s   .hs_cell
        queueStaticDMA DMA_Critical_Slot, DMA_Critical_End, Static_Hscroll_Line
        bra.s   .no_hscroll
.hs_cell:
        queueStaticDMA DMA_Critical_Slot, DMA_Critical_End, Static_Hscroll_Cell
.no_hscroll:
```

- [ ] **Step 5: Build and verify with the OJZ default (per-cell, no deform)**

```bash
cd /home/volence/sonic_hacks/s4_engine && ./build.sh -pe
```

Load in Exodus. Boot to OJZ. Verify per-cell mode still works (visible parallax). Default config has no deform tables, so the per-line path isn't exercised yet — Task 11 wires up a deform variant.

MCP check:
```
emulator_lookup_symbol "Hscroll_Buffer"
emulator_read_memory <addr> 112  # confirm cell mode emit
```

- [ ] **Step 6: Commit**

```bash
git add engine/level/parallax.asm engine/buffers.asm docs/research/parallax-§4.6.md
git commit -m "$(cat <<'EOF'
feat(§4.6): per-line HScroll mode + H-deformation sampling

Parallax_Fill_PerLine emits 224 longwords with per-line FG/BG deform
sampling (signed bytes >> per-band amplitude shift, added to band's
base scroll). Mode auto-selected from config: per-cell when no deform
tables, per-line when either FG or BG H-deform is set.
Static_Hscroll_Line (896-byte DMA) used in per-line mode;
Enqueue_Dirty_Buffers switches descriptors per frame.

OJZ default config (no deform) continues using per-cell path; per-line
exercised in Task 11 with the windy fixture.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: F1 — Multi-band OJZ BG art

Author the visual fixture: a 64×32 Plane B layout with 4-5 visually-distinct horizontal bands matching the parallax_config's band boundaries (rows 0-3 sky, 4-9 mountains, 10-13 mid-mountains, 14-19 hills, 20-31 ground). Reuses existing OJZ tile pool where possible; extends if needed.

**Files:**
- Create: `art/ojz/bg_layout_v2.bin` (4096 bytes — full 64×32 nametable)
- Modify: `data/levels/ojz/act1.asm` (or wherever `act_bg_layout` is set) — point at `bg_layout_v2.bin`
- Modify: tile pool / `BG_TILE_*` references if new tiles are needed

- [ ] **Step 1: Research — BG authoring tools and band-aligned layouts**

Targets:
- **sonic_hack** — `mappings/128x128/`, the level editor (SonLVL) workflow for BG layouts.
- **S.C.E.** — BG layout format, tile palette layout, alignment conventions.
- **plutiedev** — VDP nametable cell format (palette/priority/flip/index).
- **s4_engine current** — `art/ojz/bg_layout.bin` (current single-band BG), `engine/level/bg.asm:BG_Init`, `engine/level/bg.asm:BG_LAYOUT_SIZE = 64*32*2`.

Question: do we hand-author bytes, use SonLVL, or write a Python helper? Recommendation: Python helper for v1 — generate from a description like "rows 0-3: tile_pool[sky_tiles] tiled with random variation, rows 4-9: tile_pool[mountain_tiles], ..." Allows quick iteration.

Append to research doc under "Task 10 — BG layout authoring approach."

- [ ] **Step 2: Author or generate `bg_layout_v2.bin`**

Approach (Python helper recommended):

Create `tools/gen_ojz_bg_v2.py`:

```python
#!/usr/bin/env python3
"""Generate art/ojz/bg_layout_v2.bin — 4-band OJZ BG nametable.

Layout: 64 cells wide × 32 rows tall, 2 bytes/cell.
Cell word: priority(1) | palette(2) | vflip(1) | hflip(1) | tile_index(11)
"""
import struct, sys

# Existing OJZ tile pool indices (verify by reading current bg_layout.bin or art docs)
TILE_BLANK     = 0
TILE_SKY_LIGHT = 1
TILE_SKY_MID   = 2
TILE_CLOUD_L   = 3
TILE_CLOUD_R   = 4
TILE_MOUNTAIN_FAR_TOP = 5
TILE_MOUNTAIN_FAR_BODY = 6
TILE_MOUNTAIN_MID_TOP = 7
TILE_MOUNTAIN_MID_BODY = 8
TILE_HILL_TOP = 9
TILE_HILL_BODY = 10
TILE_GROUND_TOP = 11
TILE_GROUND_BODY = 12
# (Adjust to actual tiles in the OJZ tile pool. If existing tiles don't suffice,
#  this task includes adding new tiles — see Step 3.)

PAL_BG = 0  # palette line for BG
def cell(tile, pal=PAL_BG, hflip=0, vflip=0, prio=0):
    return (prio << 15) | (pal << 13) | (vflip << 12) | (hflip << 11) | tile

# Row-by-row band assignments
ROWS = []
# Rows 0-3: sky band with sparse clouds
for r in range(4):
    ROWS.append([cell(TILE_SKY_LIGHT if (c % 8) > 5 else TILE_CLOUD_L if (c % 16) == 4 else TILE_SKY_MID) for c in range(64)])
# Rows 4-9: far mountains
for r in range(4, 10):
    is_top = (r == 4)
    ROWS.append([cell(TILE_MOUNTAIN_FAR_TOP if is_top else TILE_MOUNTAIN_FAR_BODY) for c in range(64)])
# Rows 10-13: mid mountains
for r in range(10, 14):
    is_top = (r == 10)
    ROWS.append([cell(TILE_MOUNTAIN_MID_TOP if is_top else TILE_MOUNTAIN_MID_BODY) for c in range(64)])
# Rows 14-19: hills
for r in range(14, 20):
    is_top = (r == 14)
    ROWS.append([cell(TILE_HILL_TOP if is_top else TILE_HILL_BODY) for c in range(64)])
# Rows 20-31: ground
for r in range(20, 32):
    is_top = (r == 20)
    ROWS.append([cell(TILE_GROUND_TOP if is_top else TILE_GROUND_BODY) for c in range(64)])

with open('art/ojz/bg_layout_v2.bin', 'wb') as f:
    for row in ROWS:
        for c in row:
            f.write(struct.pack('>H', c))

print(f"Wrote {len(ROWS) * 64 * 2} bytes")
```

Run:
```bash
python3 tools/gen_ojz_bg_v2.py
```

Expected output: `art/ojz/bg_layout_v2.bin` is 4096 bytes.

- [ ] **Step 3: If new tiles are needed, extend the tile pool**

If the existing tile pool doesn't include the bands' tiles (e.g., distinct "far mountain" vs "mid mountain" silhouettes), add them to OJZ's tile blob. This may involve:
1. Authoring new 8×8 tiles (use external tool: GIMP, Aseprite, etc.) — out of scope for engineer; ask user for tile data.
2. Extending the tile pool's S4LZ or raw blob.
3. Updating tile-index references in `gen_ojz_bg_v2.py`.

For v1 if no new tiles are authored, **reuse existing tiles with palette tints** — same tile but different palette line gives visual band differentiation cheaply. Adjust `PAL_BG` per row.

- [ ] **Step 4: Wire `bg_layout_v2.bin` into the act descriptor**

Find `data/levels/ojz/act1.asm` (or equivalent). Locate `Act_act_bg_layout` field. Change:

```asm
    dc.l ojz_bg_layout      ; old
```
to:
```asm
    dc.l ojz_bg_layout_v2   ; new
```

Where `ojz_bg_layout_v2` is the BINCLUDE label for the new file. Add the BINCLUDE near the existing one:

```asm
ojz_bg_layout_v2:
    BINCLUDE "art/ojz/bg_layout_v2.bin"
```

- [ ] **Step 5: Build and verify visually**

```bash
cd /home/volence/sonic_hacks/s4_engine && python3 tools/gen_ojz_bg_v2.py && ./build.sh -pe
```

Load in Exodus. Boot to OJZ. Confirm:
- Plane B shows 4-5 visually-distinct bands (sky / mountains / hills / ground)
- Scrolling horizontally → bands move at the configured factors (clouds slowest, ground fastest)

Capture screenshot via Exodus MCP for the spec record.

- [ ] **Step 6: Commit**

```bash
git add art/ojz/bg_layout_v2.bin tools/gen_ojz_bg_v2.py data/levels/ojz/act1.asm docs/research/parallax-§4.6.md
git commit -m "$(cat <<'EOF'
fixture(§4.6): multi-band OJZ BG art (F1)

Replaces single-layer OJZ Plane B with a 5-band layout: sky (rows 0-3),
far mountains (4-9), mid mountains (10-13), hills (14-19), ground
(20-31). Boundaries align with ParallaxConfig_OJZ_Default's band TOP
values, so each band's parallax factor visually corresponds to its
intended depth.

Generated by tools/gen_ojz_bg_v2.py (Python helper); regenerate by re-running
the script. Tile pool reused from existing OJZ blob; if Step 3 found that
new tiles were needed, see the tile-pool diff in this commit.

Visible parallax now shows clouds drifting slowly, mountains at mid pace,
hills near-fast, ground 1:1 with player movement.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: F3 — OJZ "windy" section variant + verify per-line + H-deform

Author a second section's parallax_config that enables BG H-deformation. Verify the per-line mode + deform sampling path lights up correctly.

**Files:**
- Create: `data/parallax/ojz_windy.asm`
- Modify: OJZ Section 1 (or another section) descriptor — set `sec_parallax_config = ParallaxConfig_OJZ_Windy`

- [ ] **Step 1: Research — windy/BG-deform visual references**

Targets:
- **Sonic 3 Hydrocity** — water surface ripple. Visible amplitude, period.
- **TF4 stage 1** — wavy clouds.
- **S.C.E.** demo levels with deformation enabled — what amplitudes/speeds look natural?

Settle: amplitude ±4 px feels gentle, ±8 px feels stormy, ±12+ px is exaggerated. Period 128 frames (~2.1 sec at 60fps) is calm; 64 frames (~1 sec) is energetic.

Append to research doc under "Task 11 — Wave parameter calibration."

- [ ] **Step 2: Author `data/parallax/ojz_windy.asm`**

```asm
; data/parallax/ojz_windy.asm — F3 fixture: BG H-deformation enabled

DeformTable_OJZ_Calm:
    deform_table_sine AMPLITUDE=4, PERIOD=128

ParallaxConfig_OJZ_Windy:
    parallax_section LAYER_MASK=$1F, V_FACTOR_BG=3, V_CENTER=128, V_OFFSET=0, \
                     DEFORM_BG=DeformTable_OJZ_Calm, DEFORM_SPEED_BG=1
        ; clouds — full deform
        BAND_PHASE := 0
        band 0,  FACTOR_1, FACTOR_1_8
        ; far mountains — mid deform
        BAND_PHASE := 64
        band 4,  FACTOR_1, FACTOR_1_4
        ; mid mountains — weak deform via larger amplitude shift
        BAND_PHASE := 128
        BAND_DSB := 6
        band 10, FACTOR_1, FACTOR_3_8
        ; hills — very weak
        BAND_PHASE := 192
        BAND_DSB := 8
        band 14, FACTOR_1, FACTOR_1_2
        ; ground — no deform (DSB sentinel = 15)
        BAND_DSB := 15
        band 20, FACTOR_1, FACTOR_1
    parallax_section_end
```

- [ ] **Step 3: Wire into a section descriptor**

Find OJZ Section 1's descriptor (or wherever a transition can be triggered). Set `sec_parallax_config = ParallaxConfig_OJZ_Windy`.

- [ ] **Step 4: Add includes**

In `S4.asm`, add `include "data/parallax/ojz_windy.asm"` after the default config include.

- [ ] **Step 5: Build and verify**

```bash
cd /home/volence/sonic_hacks/s4_engine && ./build.sh -pe
```

Load in Exodus. Boot to OJZ. Trigger a transition into the windy section. Visible:
- Clouds wave smoothly with amplitude ~4 px
- Mid mountains wave more subtly (shift=6 → amplitude 0.0625 of base = ~0.25 px peak)
- Ground does NOT wave (shift=15)

MCP verification:
```
emulator_pause
emulator_lookup_symbol "Hscroll_Buffer"
emulator_read_memory <addr> 200    # first 50 lines of per-line mode
# Verify:
#   - line 0 (clouds, factor 1/8, deform_shift_b=4): values vary with frame counter
#   - line 100 (between mountain bands): values vary
#   - line 224 (ground): values constant frame-to-frame (no deform)
```

Confirm DMA is now using `Static_Hscroll_Line` (896 bytes) on this section:
```
emulator_lookup_symbol "DMA_Budget_Remaining"
emulator_read_memory <addr> 2
# Should show ~896 fewer bytes than per-cell mode
```

- [ ] **Step 6: Commit**

```bash
git add data/parallax/ojz_windy.asm S4.asm data/levels/ojz/<section>.asm docs/research/parallax-§4.6.md
git commit -m "$(cat <<'EOF'
fixture(§4.6): F3 windy OJZ section variant (BG H-deformation)

OJZ Section 1 now references ParallaxConfig_OJZ_Windy: BG H-deformation
enabled, sine wave at amplitude 4 px / period 128 frames, per-band
amplitude shifts decreasing toward the ground (clouds full, hills weak,
ground no deform). Per-band phase offsets desynchronize the bands so
clouds and mountains don't wave in lockstep.

Exercises the per-line HScroll path (896-byte DMA) and the deform-sample
inner loop. MCP-verified per-line buffer values vary with frame counter
in deformed bands and stay constant in the ground band.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Per-column V-scroll

Implements Step 5 per-column branch: 80-byte VSRAM column buffer fill, direct-write VSRAM in `Vscroll_Write`. After this task, sections with `V_DEFORM_BG=` set produce per-column vertical scroll variation.

**Files:**
- Modify: `engine/level/parallax.asm` (Step 5 per-column path; `Vscroll_Write` per-column branch)

- [ ] **Step 1: Research — VSRAM direct-write timing in VBlank**

Targets:
- **plutiedev** — VSRAM write timing during VBlank, FIFO behavior.
- **Kabuto hardware notes** — VSRAM access slot timing.
- **md.railgun.works** — VSRAM column scrolling behavior. Confirm 40-entry layout (interleaved FG/BG, 20 column-pairs).
- **Vectorman, Batman** — how do they write VSRAM in their VBlank? Direct loop or DMA?
- **CODING_CONVENTIONS.md** — VBlank cycle budgets.

Estimate: 80 bytes via direct word writes ≈ 40 × `move.w (a0)+,(VDP_DATA).l` = 40 × 16c = 640c. Tight loop with `move.l` 4-byte chunks: 20 × 16c = 320c. Either fits VBlank.

Append to research doc under "Task 12 — VSRAM direct-write timing."

- [ ] **Step 2: Implement per-column Step 5 in `Parallax_Update`**

In `engine/level/parallax.asm:Parallax_Update`, replace the `.v_per_column` placeholder with the actual fill:

```asm
.v_per_column:
        ; Build vscroll_column_buf — 20 entries of (FG word, BG word)
        movea.l pcfg_v_deform_table_bg(a0), a1
        moveq   #0, d3
        move.b  pcfg_v_deform_shift_bg(a0), d3

        move.l  (Camera_Y).w, d0
        swap    d0
        move.w  d0, d1                    ; FG vscroll = camY

        sub.w   pcfg_v_center_y(a0), d0
        moveq   #0, d2
        move.b  pcfg_v_factor_bg(a0), d2
        asr.w   d2, d0
        add.w   pcfg_v_offset(a0), d0     ; base BG vscroll

        ; lerp
        move.w  (Parallax_Current_Vscroll_BG).w, d2
        sub.w   d2, d0
        asr.w   #PARALLAX_LERP_SHIFT, d0
        add.w   d0, d2
        move.w  d2, (Parallax_Current_Vscroll_BG).w

        ; Fill 20 column-pairs
        lea     (Parallax_Vscroll_Column_Buf).w, a2
        move.w  (Parallax_V_Deform_Phase_BG).w, d0   ; phase
        moveq   #19, d4                              ; 20 column-pairs - 1

.col:
        ; sample = sign_extend(table[(phase + col) & $FF])
        move.w  d0, d5
        and.w   #$FF, d5
        move.b  (a1, d5.w), d5
        ext.w   d5
        asr.w   d3, d5                    ; >> v_deform_shift_bg

        ; emit (fg_vscroll, bg = current_vscroll_bg + sample)
        move.w  d1, (a2)+
        move.w  d2, d6
        add.w   d5, d6
        move.w  d6, (a2)+

        addq.w  #1, d0                    ; next column index
        dbf     d4, .col
```

- [ ] **Step 3: Implement per-column branch in `Vscroll_Write`**

Replace the existing stub `Vscroll_Write` in `engine/level/parallax.asm`:

```asm
; ----------------------------------------------------------------------
; Vscroll_Write — emit Vscroll_Factor (whole-plane) or column buffer (per-column)
; In:  none (reads Parallax_Current_Config, Vscroll_Factor or column buf)
; Out: VSRAM written
; Clobbers: d0-d1, a0-a1
; ----------------------------------------------------------------------
Vscroll_Write:
        movea.l (Parallax_Current_Config).w, a0
        cmpa.w  #0, a0
        beq.s   .whole_plane              ; no config; default whole-plane
        move.l  pcfg_v_deform_table_bg(a0), d0
        bne.s   .per_column

.whole_plane:
        move.l  #vdpComm(0, VSRAM, WRITE), (VDP_CTRL).l
        move.l  (Vscroll_Factor).w, (VDP_DATA).l
        rts

.per_column:
        move.l  #vdpComm(0, VSRAM, WRITE), (VDP_CTRL).l
        lea     (Parallax_Vscroll_Column_Buf).w, a1
        moveq   #20-1, d0                 ; 20 longwords (FG word + BG word per column-pair)
.write:
        move.l  (a1)+, (VDP_DATA).l
        dbf     d0, .write
        rts
```

- [ ] **Step 4: Build and verify with a temporary per-column section**

Add a temporary V-deform variant to test:

In `data/parallax/ojz_default.asm`, append:

```asm
DeformTable_OJZ_Floor:
    v_column_perspective FOCAL=10, MAX_OFFSET=8

ParallaxConfig_OJZ_Floor:
    parallax_section LAYER_MASK=$1F, V_FACTOR_BG=3, V_CENTER=128, V_OFFSET=0, \
                     V_DEFORM_BG=DeformTable_OJZ_Floor, V_DEFORM_SPEED_BG=0, V_DEFORM_SHIFT_BG=4
        band 0,  FACTOR_1, FACTOR_1_8
        band 4,  FACTOR_1, FACTOR_1_4
        band 10, FACTOR_1, FACTOR_3_8
        band 14, FACTOR_1, FACTOR_1_2
        band 20, FACTOR_1, FACTOR_1
    parallax_section_end
```

Wire to OJZ Section 2 (or create one). Build, load in Exodus.

```bash
cd /home/volence/sonic_hacks/s4_engine && ./build.sh -pe
```

Trigger the section transition. Expected visual: Plane B shows pseudo-3D floor effect — closer to camera, further columns dip more.

MCP verification:
```
emulator_pause
emulator_lookup_symbol "Parallax_Vscroll_Column_Buf"
emulator_read_memory <addr> 80
# Verify 20 column-pairs with BG values varying per the perspective ramp

emulator_read_vsram 0 80
# After VBlank, VSRAM should match the buffer (verify Vscroll_Write per-column branch ran)
```

Note: per-column V-scroll + non-zero HScroll garbles the leftmost partial column (per spec). Document the visible artifact; mask sprite is a future task.

- [ ] **Step 5: Commit**

```bash
git add engine/level/parallax.asm data/parallax/ojz_default.asm docs/research/parallax-§4.6.md
git commit -m "$(cat <<'EOF'
feat(§4.6): per-column V-scroll — VSRAM column buffer + direct-write VBlank emit

Parallax_Update Step 5 per-column branch fills 80-byte vscroll_column_buf
(20 column-pairs × FG/BG words) by sampling pcfg_v_deform_table_bg.
Vscroll_Write per-column branch emits the buffer to VSRAM via 20-longword
direct loop. Mode auto-selected: pcfg_v_deform_table_bg = NULL → whole-plane;
non-NULL → per-column.

Verified pseudo-3D floor effect via temporary ParallaxConfig_OJZ_Floor
fixture using v_column_perspective FOCAL=10 MAX_OFFSET=8. VSRAM contents
match column buffer post-VBlank.

Leftmost-partial-column garbage with non-zero HScroll documented; sprite
mask deferred to §3 sprite system per spec non-goals.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: F5 — FG-deform test section

Author a section with FG H-deformation enabled. Verifies the dual FG/BG deform path. Visible: ground waves while sky stays still.

**Files:**
- Create: `data/parallax/ojz_fgwave.asm`
- Modify: OJZ section descriptor for the FG-deform test section

- [ ] **Step 1: Research — FG deformation visual references**

Targets:
- **Sonic 3 Hydrocity Act 2** — water-line FG drag effect (FG below water deforms).
- **TF4** — earthquake/screenshake bands.
- Anything in S.C.E. dual-deform demos.

Settle: FG deform is rare in Sonic-style games; gameplay is usually steady. Use ±2 px amplitude maximum to avoid making the player feel disoriented.

Append to research doc under "Task 13 — FG deform calibration."

- [ ] **Step 2: Author `data/parallax/ojz_fgwave.asm`**

```asm
; data/parallax/ojz_fgwave.asm — F5 fixture: FG H-deformation enabled
;
; Visible effect: ground tiles wave subtly horizontally as if seen through
; heat haze. Sky stays still (BG no deform).

DeformTable_OJZ_HeatHaze:
    deform_table_sine AMPLITUDE=2, PERIOD=64

ParallaxConfig_OJZ_FGWave:
    parallax_section LAYER_MASK=$1F, V_FACTOR_BG=3, V_CENTER=128, V_OFFSET=0, \
                     DEFORM_FG=DeformTable_OJZ_HeatHaze, DEFORM_SPEED_FG=2
        ; sky / far / mid: no FG deform (BAND_DSA = 15)
        BAND_DSA := 15
        band 0,  FACTOR_1, FACTOR_1_8
        band 4,  FACTOR_1, FACTOR_1_4
        band 10, FACTOR_1, FACTOR_3_8
        ; hills: faint FG deform
        BAND_DSA := 8
        band 14, FACTOR_1, FACTOR_1_2
        ; ground: full FG deform
        BAND_DSA := 4
        band 20, FACTOR_1, FACTOR_1
    parallax_section_end
```

- [ ] **Step 3: Wire into a section descriptor + include**

Set OJZ Section 2 (or another section) `sec_parallax_config = ParallaxConfig_OJZ_FGWave`. Add `include "data/parallax/ojz_fgwave.asm"` to S4.asm.

- [ ] **Step 4: Build and verify**

```bash
cd /home/volence/sonic_hacks/s4_engine && ./build.sh -pe
```

Load in Exodus. Trigger transition into the FG-wave section. Visible:
- Ground (rows 20-31 of Plane A — the tile rows the player walks on) waves with ~2 px amplitude
- Hills (rows 14-19) wave faintly
- Sky (rows 0-3) stays still

MCP verification:
```
emulator_pause
emulator_lookup_symbol "Hscroll_Buffer"
emulator_read_memory <addr> 200    # first 50 lines
# Per-line longword: high word = Plane A scroll (varies for ground rows),
#                    low word  = Plane B scroll (constant per band)
# Verify Plane A scroll at line 0 (sky band) is constant (no FG deform)
# Verify Plane A scroll at line 224 (ground band, last line) varies with frame counter
```

- [ ] **Step 5: Commit**

```bash
git add data/parallax/ojz_fgwave.asm S4.asm data/levels/ojz/<section>.asm docs/research/parallax-§4.6.md
git commit -m "$(cat <<'EOF'
fixture(§4.6): F5 FG-deform test section (ground heat-haze)

OJZ Section 2 now references ParallaxConfig_OJZ_FGWave: FG H-deformation
enabled, ±2 px amplitude / 64-frame period sine wave applied with
per-band shift increasing toward the ground (sky none, ground full).
Visible: ground waves subtly while sky stays still.

Exercises the dual FG/BG deform path. MCP-verified Plane A scroll values
in Hscroll_Buffer vary per-line in the ground band and stay constant in
the sky band.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: Transition smoothing (lerp)

Replace instant snap with proper 8-frame lerp. Spec: when `pcfg_transition = 0`, target_config is staged and current_scroll_a/b lerp toward new factor table over `PARALLAX_TRANSITION_FRAMES` frames.

**Files:**
- Modify: `engine/level/parallax.asm` (`Parallax_StartTransition` smooth path; `Parallax_Update` Step 2 + Step 3 to use target_config during transition)

- [ ] **Step 1: Research — lerp convergence characteristics**

Targets:
- **S.C.E.** — does it have transition smoothing on parallax? `Engine/Core/Sections.asm`.
- **TF4** — section-to-section transitions; instant or smooth?
- **Modern engines** — what's the standard "exponential smoothing" vs "fixed-frame lerp" tradeoff?

Settle: with `>>3` lerp shift over 8 frames, target convergence reaches ~95%. For a 16-frame transition, use shift=4. Spec defaults to `PARALLAX_LERP_SHIFT=3` and `PARALLAX_TRANSITION_FRAMES=8`.

Append to research doc under "Task 14 — Lerp tuning."

- [ ] **Step 2: Update `Parallax_StartTransition` smooth path**

Replace the existing instant-snap implementation:

```asm
Parallax_StartTransition:
        cmpa.w  #0, a0
        beq.w   .no_change
        cmpa.l  (Parallax_Current_Config).w, a0
        beq.w   .no_change

        ; Determine instant vs smooth
        tst.b   pcfg_transition(a0)
        bne.s   .instant

        ; -- smooth: stage target, leave current intact, set frame counter --
        move.l  a0, (Parallax_Target_Config).w
        move.b  #PARALLAX_TRANSITION_FRAMES, (Parallax_Transition_Frames).w
        bra.s   .update_shadow

.instant:
        move.l  a0, (Parallax_Current_Config).w
        move.l  #0, (Parallax_Target_Config).w
        move.b  #0, (Parallax_Transition_Frames).w

.update_shadow:
        ; Update VDP shadow $0B and $8C bits per new config
        ; (existing code from Task 8 Step 2)

.no_change:
        rts
```

- [ ] **Step 3: Update `Parallax_Update` Step 2 + Step 3 for target_config**

In `engine/level/parallax.asm:Parallax_Update`, modify Step 2 (transition state) and Step 3 (band scroll computation) to use `target_config` when transition is active:

```asm
        ; --- Step 2: transition state ---
        tst.b   (Parallax_Transition_Frames).w
        beq.s   .no_transition
        subq.b  #1, (Parallax_Transition_Frames).w
        bne.s   .use_target
        ; transition complete: swap current = target
        move.l  (Parallax_Target_Config).w, d0
        move.l  d0, (Parallax_Current_Config).w
        move.l  #0, (Parallax_Target_Config).w
        bra.s   .no_transition
.use_target:
        movea.l (Parallax_Target_Config).w, a0   ; use target for factor computation
        bra.s   .config_loaded
.no_transition:
        movea.l (Parallax_Current_Config).w, a0
.config_loaded:
        ; ... continue with phase advance and Step 3 using a0 as the source config
```

The lerp in Step 3 is already implemented (current_scroll += (target - current) >> 3). Just confirm a0 is the *target* config during transition so the target_scroll values come from the new factor table.

- [ ] **Step 4: Build and verify smooth transition**

Author OJZ Section 1 with a noticeably-different parallax_config (e.g., ParallaxConfig_OJZ_Caves with all factors 1/16 — much slower BG scroll). Build:

```bash
cd /home/volence/sonic_hacks/s4_engine && ./build.sh -pe
```

In Exodus, scroll across the section boundary at moderate camera speed. Expected visual: Plane B's scroll speed gradually shifts over ~8 frames after the transition triggers, instead of snapping immediately.

MCP verification:
```
emulator_pause
# Just before transition
emulator_read_memory Parallax_Current_Scroll_B 16    # 8 bands × 2 bytes
# Note values

# Trigger transition (scroll across boundary)
emulator_step  # 1 frame post-transition
emulator_read_memory Parallax_Current_Scroll_B 16
# Values should be MOSTLY old values (lerp 1/8 of way to new)

# Step 7 more frames
for _ in range(7): emulator_step
emulator_read_memory Parallax_Current_Scroll_B 16
# Values should now equal new factors' resolved scrolls
```

- [ ] **Step 5: Commit**

```bash
git add engine/level/parallax.asm docs/research/parallax-§4.6.md
git commit -m "$(cat <<'EOF'
feat(§4.6): transition smoothing — 8-frame band-scroll lerp

Section transitions with pcfg_transition = 0 (default) now stage the new
config in target_config and lerp current_scroll_a/b toward target factors
over PARALLAX_TRANSITION_FRAMES (=8) frames. Per-frame: target factors
computed from target_config; current += (target - current) >> 3.
Instant-snap path (pcfg_transition = 1) preserved.

Verified via MCP: scrolls converge to new factor values over 8 frames
post-transition rather than snapping instantly. Visual: BG smoothly
shifts pace across section boundaries.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 15: F4 + F6 — Section-pair transition test + layer mask test

Final two fixtures. F4 uses two sections with distinct configs to verify smooth transition visually. F6 uses LAYER_MASK=$0F to disable bands and confirm the previous-band-inheritance path works.

**Files:**
- Modify: `data/parallax/ojz_default.asm` or new file with section-pair configs
- Create: `data/parallax/ojz_layermask.asm`
- Modify: OJZ section descriptors

- [ ] **Step 1: Research — layer-mask use cases**

Targets:
- Sonic 3 levels with subset of bands active (e.g., underwater levels suppress sky).
- TF4 / Vectorman level transitions where some bands fade out.

Settle: layer mask is mainly used during section transitions or special states (e.g., boss fights with simplified BG). For testing, just toggle bits and verify visual.

Append to research doc under "Task 15 — Layer mask use cases."

- [ ] **Step 2: Set up F4 — distinct configs for transition smoothing test**

`data/parallax/ojz_default.asm` already has `ParallaxConfig_OJZ_Default`. Add a contrasting config:

```asm
ParallaxConfig_OJZ_Caves:
    parallax_section LAYER_MASK=$1F, V_FACTOR_BG=4, V_CENTER=64, V_OFFSET=-16, \
                     TRANSITION=0
        band 0,  FACTOR_1, FACTOR_1_16    ; deep caves: very slow BG
        band 4,  FACTOR_1, FACTOR_1_16
        band 10, FACTOR_1, FACTOR_1_8
        band 14, FACTOR_1, FACTOR_1_4
        band 20, FACTOR_1, FACTOR_1
    parallax_section_end
```

Wire OJZ Sections 0 and 1 to alternate between Default and Caves. F4 verification = scroll across boundary, observe smooth lerp from default factors to caves factors.

- [ ] **Step 3: Author F6 — `data/parallax/ojz_layermask.asm`**

For 5 bands and `LAYER_MASK=$1E` (binary `11110`), band 0 (clouds) is disabled and inherits previous-band scroll = 0 (locked, since band 0 has no previous). Visually: clouds stay still while everything else parallaxes normally.

```asm
; data/parallax/ojz_layermask.asm — F6 fixture: clouds locked via layer mask

ParallaxConfig_OJZ_LayerMask:
    parallax_section LAYER_MASK=$1E, V_FACTOR_BG=3, V_CENTER=128, V_OFFSET=0
        band 0,  FACTOR_1, FACTOR_1_8       ; clouds DISABLED → inherit (none) → 0 (locked)
        band 4,  FACTOR_1, FACTOR_1_4       ; far mountains — active
        band 10, FACTOR_1, FACTOR_3_8       ; mid mountains — active
        band 14, FACTOR_1, FACTOR_1_2       ; hills — active
        band 20, FACTOR_1, FACTOR_1         ; ground — active
    parallax_section_end
```

Adjust comment in the file to match.

- [ ] **Step 4: Wire into a section descriptor + include**

Set OJZ Section 3 `sec_parallax_config = ParallaxConfig_OJZ_LayerMask`. Add `include "data/parallax/ojz_layermask.asm"` to S4.asm.

- [ ] **Step 5: Build and verify**

```bash
cd /home/volence/sonic_hacks/s4_engine && ./build.sh -pe
```

Load in Exodus. F4: scroll across Section 0→1 boundary, observe smooth transition (8 frames).

F6: scroll into Section 3 (or wherever LAYER_MASK is wired). Visible: clouds rows scroll at the same rate as the next-active band's scroll (which is band 1's value 1/4 — but since band 0's "previous" is none, it'll inherit 0 = locked). Verify visually.

MCP:
```
emulator_pause
emulator_read_memory Parallax_Current_Scroll_B 16
# Band 0's slot should hold value matching previous band (or 0 if first band)
```

- [ ] **Step 6: Commit**

```bash
git add data/parallax/ojz_default.asm data/parallax/ojz_layermask.asm S4.asm data/levels/ojz/<sections>.asm docs/research/parallax-§4.6.md
git commit -m "$(cat <<'EOF'
fixture(§4.6): F4 section-pair (transition smoothing) + F6 layer mask

F4: ParallaxConfig_OJZ_Caves added as a contrasting config (BG factors
1/16, deeper V-anchor); paired with default. Crossing the section
boundary visibly lerps over 8 frames.

F6: ParallaxConfig_OJZ_LayerMask uses LAYER_MASK=\$1E to disable band 0
(clouds). The disabled band inherits the previous band's scroll
(none → 0 = locked) per spec layer-mask semantics.

All six §4.6 test fixtures (F1-F6) now in place. Visual + MCP verification
covers band parallax, deformation, transitions, layer mask, FG-deform,
and per-column V-scroll.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 16: Tear-prevention test (Exodus MCP)

Spec section "Tear-prevention test". Verify VBlank ordering is correct: HScroll DMA drains before VSRAM write.

**Files:**
- Create: `docs/research/parallax-§4.6.md` — append test results

- [ ] **Step 1: Research — VDP timing during VBlank**

Targets:
- **plutiedev** — VBlank timing (NTSC ~4300 cycles).
- **Kabuto** — VRAM/VSRAM write slot timing.
- **SpritesMind t=1482** — the original tearing thread.

Verify our reorder addresses the actual root cause.

Append to research doc under "Task 16 — Tear-prevention test methodology."

- [ ] **Step 2: Set up the tear-test scenario in Exodus**

Use OJZ Section 1 (windy section, per-line mode + H-deform).

```bash
# Build with current implementation
cd /home/volence/sonic_hacks/s4_engine && ./build.sh -pe
```

Load in Exodus. Boot to OJZ. Trigger transition into windy section. Set high horizontal scroll velocity (camera moving 8+ px/frame).

- [ ] **Step 3: MCP-driven scanline-1 verification (×100 frames)**

```
# Loop 100 times:
for frame in range(100):
    emulator_run_to_scanline 1   # just past VBlank end
    hscroll_data = emulator_read_vram $DC00, 8     # first 2 HScroll table entries
    vsram_data = emulator_read_vsram 0, 4          # Vscroll values
    expected_hscroll = derived from current Hscroll_Buffer (read RAM at start of frame)
    expected_vsram   = derived from current Vscroll_Factor
    assert hscroll_data == expected_hscroll
    assert vsram_data == expected_vsram
    # advance to next frame
    emulator_resume
    emulator_pause
```

If any frame mismatches, the reorder isn't correct or there's another race.

- [ ] **Step 4: Document results in research doc**

Append to `docs/research/parallax-§4.6.md`:

```markdown
## Task 16 — Tear-prevention verification

Test scenario: OJZ Section 1 (windy, per-line mode), camera scrolling at
8+ px/frame for 100 frames. Sampled HScroll table ($DC00) and VSRAM at
scanline 1 each frame, compared against pre-VBlank RAM values.

Results: record pass count out of 100. If any frames mismatch, capture frame number + observed vs expected HScroll/VSRAM values for diagnosis.

Conclusion: VBlank reorder (HScroll DMA → VSRAM write → other DMA) prevents
the documented one-frame tear in 100/100 sampled frames at high camera
velocity.
```

- [ ] **Step 5: Commit**

```bash
git add docs/research/parallax-§4.6.md
git commit -m "$(cat <<'EOF'
test(§4.6): tear-prevention verification — 100 frames at high velocity

Exodus MCP sweep confirmed HScroll table at \$DC00 and VSRAM both reflect
current-frame parallax state at scanline 1, across 100 consecutive frames
of the OJZ windy section at 8+ px/frame camera scroll. No VBlank-order
tearing observed.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 17: ENGINE_ARCHITECTURE.md + DEFERRED_WORK.md updates

Final task. Sync the architecture doc with what we actually built and append all deferred items per the spec's "Architecture-doc revisions required" + "Deferred work entries" sections.

**Files:**
- Modify: `docs/ENGINE_ARCHITECTURE.md` (§4.6)
- Modify: `docs/DEFERRED_WORK.md`

- [ ] **Step 1: Apply §4.6 revisions to ENGINE_ARCHITECTURE.md**

Open `docs/ENGINE_ARCHITECTURE.md`. Find §4.6 (around line 1904). Apply all 10 revisions from the spec's "Architecture-doc revisions required" section verbatim. The new §4.6 text should describe:
- Shift-add factor encoding (no formula, no muls)
- Per-band Plane A + Plane B factor split
- Per-band amplitude shift + phase offset
- FG/BG H-deformation tables (256 bytes each, sampled per line in per-line mode)
- Vertical parallax (whole-plane and per-column)
- Section transition smoothing (8-frame lerp)
- Per-cell vs per-line auto-mode
- 28-byte parallax_config + 10-byte band_entry struct
- ~126 B Parallax_State RAM

Also update the row 17 summary in the architecture doc's overview table to reflect the new design.

- [ ] **Step 2: Append deferred items to DEFERRED_WORK.md**

Open `docs/DEFERRED_WORK.md`. Add a new section (insert in appropriate location):

```markdown
## From §4.6 — Parallax

### Per-block linear interpolation deformation format
**Blocked by:** N/A — deliberately not in v1
**What:** S.C.E.'s block-based deformation table format with high-bit linear-interp flag. Variable-height blocks save ROM (~32 bytes vs ~256 bytes per table). v1 uses full 256-byte time-varying tables — block format is a ROM-saving optimization we don't currently need.
**When ready:** If a section's deformation table waste becomes a real ROM problem (currently affordable).

### Per-band deformation table pointers
**Blocked by:** Visual demand for different wave shapes per band
**What:** Each band points at its own 256-byte deform table. Currently single shared table per section + per-band amplitude/phase offset. Adds 4 bytes per band (table ptr) + multiple tables per section.
**When ready:** When a section visually requires different shapes per band (e.g., square wave for one band, sine for another).

### Per-band frequency variation
**Blocked by:** Visual demand
**What:** Per-band `phase_increment` byte. Currently only phase offset varies per band (frequency is section-wide via `pcfg_deform_speed_*`).
**When ready:** When "different speeds per band" surfaces as a clear visual need.

### Plane A per-column V-scroll
**Blocked by:** Use case (ground-plane warping is rare in Sonic-style)
**What:** `pcfg_v_deform_table_fg` field is reserved but not wired. v1 always uses whole-plane V-scroll on Plane A. Implementing means symmetric to BG path; ~30 cycles + 80 bytes of work per frame.
**When ready:** When a section needs ground-plane vertical warping (special-stage 3D floors, post-explosion ground sink).

### Sprite mask for per-column V-scroll leftmost-partial-column garbage
**Blocked by:** §3 sprite system support for per-section sprite-mask placement
**What:** When per-column V-scroll combines with non-zero HScroll, the leftmost 16-px partial column shows garbage tiles. v1 documents this as an authoring convention: place a 16-px black sprite at column 0 manually. Auto-placement would require per-section sprite-mask metadata + automatic spawn.
**When ready:** When per-column V-scroll adoption surfaces real-world cases.

### Build-time assertion that Plane A nametable rows 48-63 stay empty
**Blocked by:** Vertical section streaming (§4 deferred)
**What:** `VRAM_HSCROLL_TABLE = $DC00` is inside Plane A's 64-row footprint (row 56). Safe today because the camera doesn't scroll vertically. When vertical streaming lands, a build-time assertion is needed to keep authored Plane A content out of rows 48-63.
**When ready:** With §4 vertical-streaming work.

### Plane B vertical extent extension to 64×64
**Blocked by:** Window plane usage
**What:** Plane B is currently 64×32 ($E000-$EFFF) with $F000-$FFFF reserved for Window plane. Extending Plane B to 64×64 requires repurposing or relocating the Window plane.
**When ready:** When vertical parallax ranges exceed the 256-px wrap of the current 64×32 Plane B.

### Mid-frame VDP register changes via HInt (palette swap, plane-base swap)
**Blocked by:** §7.2 raster command table system
**What:** Per-section palette gradients tied to band boundaries (e.g., horizon-line palette transitions) and plane-base swaps for "extra" Plane B layers via HInt-driven mid-frame VDP register changes. Lives in §7.2 raster engine; clean hook via VDP shadow.
**When ready:** With §7.2 raster engine implementation.

### Variable-length HScroll DMA based on dirty range
**Blocked by:** N/A — already in DEFERRED_WORK §1.1
**What:** Use `Hscroll_Dirty_Start/End` to DMA only changed lines instead of full 896 bytes in per-line mode. v1 always sends the full descriptor.
**When ready:** When HScroll DMA bandwidth becomes a measurable bottleneck.
```

- [ ] **Step 3: Build clean to confirm no asm impact**

```bash
cd /home/volence/sonic_hacks/s4_engine && ./build.sh -pe
```

Expected: build succeeds; doc-only changes don't affect ROM.

- [ ] **Step 4: Mark §4.6 entries done in DEFERRED_WORK if any existed**

Search `docs/DEFERRED_WORK.md` for any pre-existing §4.6 stubs. If present, mark them DONE with reference to this implementation.

- [ ] **Step 5: Commit**

```bash
git add docs/ENGINE_ARCHITECTURE.md docs/DEFERRED_WORK.md
git commit -m "$(cat <<'EOF'
docs(§4.6): sync architecture doc with parallax implementation; deferred items

ENGINE_ARCHITECTURE.md §4.6 revised to match shipped design:
- Shift-add factor encoding (no muls, no formula)
- Per-band Plane A + Plane B factor split
- Per-band amplitude + phase offset
- FG/BG dual H-deformation
- Vertical parallax with section anchor
- Per-column V-scroll
- 8-frame transition lerp
- TF4 attribution corrected to "inspired by"
- Per-block linear interp removed
- RAM cost note updated to ~126 B Parallax_State

DEFERRED_WORK.md §4.6 section added with 9 items (per-block linear
interp, per-band deform tables, per-band frequency, Plane A V-deform,
sprite mask, vertical assertion, 64×64 Plane B extension, mid-frame HInt,
variable HScroll DMA).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Plan complete

All §4.6 features from the spec implemented and verified. ROM ships with:
- Visible 5-band horizontal parallax in OJZ Act 1 (multi-band BG art via F1)
- BG H-deformation in the windy section (F3)
- Per-column V-scroll pseudo-3D floor effect (Task 12 fixture)
- FG H-deformation ground heat-haze (F5)
- Smooth lerp transitions across section boundaries
- Layer mask with previous-band inheritance (F6)
- Architecture doc + deferred work updated
