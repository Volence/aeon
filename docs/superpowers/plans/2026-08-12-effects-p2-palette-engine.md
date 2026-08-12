# Effects Suite Phase 2 — Palette Engine, Variants/Regions, Dense Raster Tier

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.
>
> **REPO LAW:** `CODING_CONVENTIONS.md` before any code. `.s`/`.w`/`.l` on every branch. Comptime for all build-time math. No `mulu`/`divu`.
>
> **EMULATOR RULE:** oracle work is CONTROLLER-ONLY, foreground, never from a subagent.
>
> **READ FIRST, both are load-bearing:**
> - `docs/research/2026-08-12-raster-hint-survey.md` — the HInt reload lag, the ~60-cycle budget, CRAM-dot mechanics. Phase 2 lives or dies on these.
> - `docs/benchmarks/effects-p1/GATE-EVIDENCE.md` — what P1 actually proved, and the two residuals this phase inherits.

**Goal:** Turn the shipped sparse raster tier into the full visual layer: a palette engine with a deterministic composition pipeline, authorable palette **variants** bound to scanline **regions**, and the dense raster tier (per-scanline gradients, per-column VSRAM). Gate: the OJZ water cluster, hand-authored.

**Architecture:** Per the design suite §5. The palette engine becomes the single writer of `Palette_Buffer`, composing base → cycling → cross-fade → operators → variants each frame. Variants are derived from the *live composed* palette by cheap per-channel transforms, so they never go stale. Water stops being an engine concept: it is a preset composing a variant boundary + S/H + a SAT switch + the `Water_Level` patch slot.

**Tech Stack:** `.emp` (sigil), 68000, VDP HInt/CRAM/VSRAM, oracle MCP.

---

## Inherited state — what P1 left you

**Shipped and verified:** sparse HInt dispatcher in `engine/system/hblank.emp` (build-time arm words, two priming records, IPL-7 entry, `OP_SET_REG`/`OP_CRAM`); `Raster_State` RAM block incl. an unused `Raster_Buf_B`; `Palette_LoadSection` in `engine/system/buffers.emp` consuming `sec_pal`; both consumers wired at `Parallax_CheckBoundary`; `Raster_VBlank` called from BOTH VInt paths **before** `Flush_VDP_Shadow`.

**Inherited residuals (this phase owns both):**
1. **Row 119 partial tint.** The CRAM write lands inside line 119's active display, so pixels drawn after it on that line already carry the new colour, by a varying amount. Water needs a pixel-clean boundary, so pick a fix here (Task 4).
2. **S/H never visually proven.** `OP_SET_REG` executes, but OJZ's art is high-priority and S/H only shadows low-priority pixels. Water content is what makes it observable (Task 7).

**Deliberate debts P1 booked, NOT this phase's job unless they block you:**
- Code lives in `hblank.emp` / `buffers.emp` rather than `engine/effects/*.emp`, because a new sigil section is a circular bootstrap (repin region + generated pins + frozen boundary tables + refreeze). The split is a separate pure code-motion parcel. **If Phase 2's additions make these files unwieldy, do the module split FIRST as its own parcel** — do not let two large files rot.
- Replay-net fixtures were not re-run after P1's RAM insertion (`Raster_State` shifts `Engine_RAM_End` and game RAM, so expect layout-induced hash drift needing a fixture re-stamp).
- P1 is on `feat/effects-p1-raster-core` paired with sigil `9f6b6209` + `feat/effects-p1-registry`, NOT merged. Reconcile before starting (Task 0).

---

## Task 0: Rebase onto a coherent pair, re-verify P1, re-run the replay net

**Files:** none (branch + verification work)

- [ ] **Step 1: Establish the current coherent aeon/sigil pair.** Read `memory/reference_aeon_sigil_pairing.md` first. Check whether the character-dispatch work has merged to aeon master; if it has, sigil master should pair with aeon master again. Verify by building unmodified master:

```bash
cd /home/volence/sonic_hacks/aeon
git checkout master && git log --oneline -1
SIGIL_BUILD=<sigil>/target/release/sigil SIGIL_EMIT=<sigil>/target/release/emit_sound_blob ./build.sh
```
Expected: green WITHOUT `CONTRACTS=0`. If it fails with `no module ... found under the scan root`, the pair is still split — find the pre-coupling sigil commit per the memory note and use a sigil worktree.

- [ ] **Step 2: Rebase P1 onto that master and rebuild both shapes.**

```bash
git checkout feat/effects-p1-raster-core && git rebase master
DEBUG=1 ./build.sh && ./build.sh    # with the paired SIGIL_* vars
```
Fix any conflicts in `hblank.emp` / `buffers.emp` / `parallax.emp` / `configs.emp` / `act_descriptor.emp`.

- [ ] **Step 3: Re-verify the P1 gate has not regressed.** Repeat GATE-EVIDENCE.md's method exactly: oracle, debug ROM, CRC-checked; enter OJZ; hold right ~240-250 frames into section 1; screenshot mid-scroll; count pixels **exactly equal to (238,0,0)** per row.
Expected: zero above row 118, full from row 120. Anything else means the rebase moved something real — STOP and diagnose before building on it.

- [ ] **Step 4: Re-run the replay net and dispose of the drift.** Follow `docs/superpowers/notes/2026-08-09-replay-net-rerecord-ab.md`. Both fixtures. If hashes fail, determine whether it is layout-induced (RAM shifted) or behavioural (the palette/raster consumers changed observable state) — these have different dispositions:
  - layout-induced → re-stamp the fixtures via the probe-ROM logger and record the re-stamp
  - behavioural → a real regression; STOP and report BLOCKED
Report aggregate pass/fail counts, not a tail (`memory/feedback_never_tail_a_test_run`).

- [ ] **Step 5: Commit** the rebase + any fixture re-stamp, with the disposition written out.

---

## Task 1: Palette engine skeleton — one owner, deterministic composition order

**Files:** Modify `engine/system/buffers.emp` (or the new module if you did the split)

The pipeline, composed into `Palette_Buffer` once per frame, in this fixed order:

```
base (sec_pal)  ->  cycling  ->  cross-fade  ->  global operators  ->  variants  ->  dirty-line DMA
```

Phase 2 builds base + cross-fade + operators + variants. Cycling is Task 8.

- [ ] **Step 1: Write the comptime layout + RAM.** Add a `Palette_State` block to `engine/ram.emp` beside `Raster_State`, using the same `mark X, ... mark X_End,` pair, plus a matching `ensure(extern(...) - extern(...) == PALETTE_STATE_SIZE)` span guard in the owning code module. Fields:

```
    mark Palette_State,
    Pal_Base:         [u8; 128],   // the section's palette, unmodified (cross-fade source A)
    Pal_Target:       [u8; 128],   // incoming section's palette (cross-fade source B)
    Pal_Composed:     [u8; 128],   // base after cycling+fade+operators, BEFORE variants
    Pal_Fade_Frames:  u8,          // 0 = stable
    Pal_Op:           u8,          // active global operator (none / white / negative / to-black / to-white)
    Pal_Op_Step:      u8,
    Pal_Dirty_Compose: u8,         // 1 = recompose needed this frame
    mark Palette_State_End,
```

Note the RAM cost (~384 B). Check `Game_RAM_End` headroom before committing to it; if tight, `Pal_Composed` can be elided by composing straight into `Palette_Buffer` and keeping only Base/Target — decide explicitly and write down why.

- [ ] **Step 2: Rewrite `Palette_LoadSection` as the pipeline's base-layer step.** It currently copies `sec_pal` straight into `Palette_Buffer` and sets `Palette_Dirty = $0F`. It must now load into `Pal_Base` (or `Pal_Target` when a cross-fade is armed) and request a recompose. Keep the "NULL = keep current" semantics and the full-128-byte contract (see the §7.1 note — a short or line-offset blob is a verified failure mode).

- [ ] **Step 3: Add `Palette_Compose`,** called once per frame from the main loop (NOT VBlank — it is arithmetic, not VDP work; it must land before `Enqueue_Dirty_Buffers` reads the dirty mask next VBlank). Order exactly as above. Set only the palette lines that actually changed dirty, so a static frame costs one compare.

- [ ] **Step 4: Build + commit.** `DEBUG=1 ./build.sh && ./build.sh`. Expect zero contract-closure firings; widen callers' `clobbers()` as the gate directs (P1 precedent: `Parallax_CheckBoundary` needed `a1` added).

---

## Task 2: Palette variants — authorable per-channel transforms

**Files:** Modify the palette module; add comptime constructors

A **variant** is either a transform of the live composed palette or an explicit palette. The transform vocabulary is deliberately cheap: per-channel `clamp((c >> shift) + bias)` for R/G/B.

- [ ] **Step 1: Comptime constructor + record.**

```
// A variant transform: per-channel shift + bias, applied to the live composed
// palette so it never goes stale under cycling or cross-fade.
// Genesis colour word is 0000 BBB0 GGG0 RRR0 — 3 bits per channel, so shift is
// 0..3 and bias is -7..+7; both are validated here rather than at runtime.
pub struct pal_variant {
    v_shift_r: u8, v_bias_r: i8,
    v_shift_g: u8, v_bias_g: i8,
    v_shift_b: u8, v_bias_b: i8,
    v_lines:   u8,   // bitmask 0-3: which palette lines the variant covers
    v_pad:     u8,
}

pub comptime fn variant(shift_r: int = 0, bias_r: int = 0,
                        shift_g: int = 0, bias_g: int = 0,
                        shift_b: int = 0, bias_b: int = 0,
                        lines: int = %1111) -> pal_variant {
    ensure(shift_r >= 0 && shift_r <= 3, "variant: shift_r {shift_r} outside 0..3 (3-bit channel)")
    ensure(shift_g >= 0 && shift_g <= 3, "variant: shift_g {shift_g} outside 0..3")
    ensure(shift_b >= 0 && shift_b <= 3, "variant: shift_b {shift_b} outside 0..3")
    ensure(bias_r >= -7 && bias_r <= 7,  "variant: bias_r {bias_r} outside -7..+7")
    ensure(bias_g >= -7 && bias_g <= 7,  "variant: bias_g {bias_g} outside -7..+7")
    ensure(bias_b >= -7 && bias_b <= 7,  "variant: bias_b {bias_b} outside -7..+7")
    ensure(lines >= 1 && lines <= 15,    "variant: lines mask {lines} must select at least one of 4 lines")
    return pal_variant{ v_shift_r: shift_r, v_bias_r: bias_r,
                        v_shift_g: shift_g, v_bias_g: bias_g,
                        v_shift_b: shift_b, v_bias_b: bias_b,
                        v_lines: lines, v_pad: 0 }
}
```

- [ ] **Step 2: The runtime derive.** `Palette_DeriveVariant(a0 = pal_variant*, a1 = dest)` walks the composed palette and applies the transform per channel. **No `mulu`/`divu`** — shift and add only, per repo law. Channels must be extracted, shifted, biased, clamped to 0..7, and re-packed; clamping is `tst`/`bmi`/`cmp`-based, not arithmetic tricks that can overflow into a neighbouring channel. Write a comptime test vector: a known colour word through a known variant, asserted with `ensure`, so the packing is proven at build time.

- [ ] **Step 3: Starter variants** as named data — `Variant_Water_Deep` (halve R and G, keep B), `Variant_Water_Murky` (halve B, bias R), `Variant_Poison` (halve R and B, bias G), `Variant_CaveDark` (halve all), `Variant_Dusk` (halve B, small R bias). These are the "give people ideas" seeds from the design.

- [ ] **Step 4: Build + commit.**

---

## Task 3: Scanline regions — `OP_PAL_REGION`

**Files:** Modify the raster dispatcher

A region boundary is a raster op that swaps a whole palette line (or several) to a variant's derived bytes mid-frame.

- [ ] **Step 1: Pre-derive, do not derive in the handler.** The handler has ~60 cycles; a 16-colour derive is far beyond that. `Palette_Compose` writes each active variant's derived bytes into a RAM staging buffer at frame time, and `OP_PAL_REGION` only *streams* them. Budget the staging RAM (one 32-byte line per active variant per region) and set a hard ceiling on simultaneously active variants (start at 2; raise only with measured evidence).

- [ ] **Step 2: Add the op.** `OP_PAL_REGION`: args = a CRAM write command longword + `count-1` + a RAM source pointer. The handler writes the command then streams `count` words from RAM. **`RASTER_CRAM_MAX` = 3 still binds per fire** (a cycle budget, survey Ruling 2a) — a full 16-colour line CANNOT go in one fire. So a region swap must be either spread across consecutive fires (several lines, S3K's actual technique — it writes 3 colours per scanline precisely to push the dots offscreen) or scoped to the few colours that visibly matter. **Decide and write down which**, because it changes what a "region" means to an author: S3K-style spreading means the boundary takes N lines to complete.

- [ ] **Step 3: Extend the op dispatch.** With a third opcode the compare chain is at its limit; reconsider the computed-jump table — but note P1 found a pc-indexed `jmp` defeats the contract-closure dataflow (`proc.clobber-undeclared` is zero-firing by contract). If you reintroduce a table, you must satisfy that gate; otherwise keep the chain and order the compares by frequency.

- [ ] **Step 4: Build + commit.**

---

## Task 4: Kill the row-119 partial tint (pixel-clean boundaries)

**Files:** Modify the raster dispatcher and/or the comptime fire-line helper

- [ ] **Step 1: Pick the approach on evidence, not preference.** Two documented options:
  - **(a) Fire one line earlier** and let the effect establish a line high. Cheap, zero cycles, shifts the artifact to row 118 instead of removing it.
  - **(b) Push the write into blanking** with a cycle-counted delay, S3K's approach (`skdisasm/sonic3k.asm:1018`, `:1038-1039`, with a second variant retuned per region and selected at runtime by measured VBlank length at `:9791-9793`). Removes the artifact; costs cycles inside a ~60-cycle budget and is region-dependent.
- [ ] **Step 2: Measure both** on oracle with GATE-EVIDENCE.md's exact-colour-per-row method. Record the row-118/119/120 counts for each. Choose, and write the rejected option's numbers into the survey doc so it is not re-litigated.
- [ ] **Step 3: Commit** with the measurement in the message.

---

## Task 5: Dense tier — the gradient streamer (`OP_RUN_GRADIENT`)

**Files:** Modify the raster dispatcher

- [ ] **Step 1: A dense run is a MODE, not an op that returns.** For a line range, the handler must switch to firing every line (reg `$0A` = 0) and run a minimal per-line body, then restore sparse delta dispatch at the end of the run. Mind the reload lag at BOTH transitions — entering and leaving a dense run each cost one pipelined arm, exactly like the priming records. Write the schedule out in a comment before writing code.
- [ ] **Step 2: The per-line body must be minimal.** The corpus affords ~26 cycles/line by saving ZERO registers and reserving a stream cursor register globally (Alien Soldier; Gunstar's `a6`) — survey Ruling 4c. Our handler currently saves four registers (a 40-cycle `movem` round trip). For a 224-line gradient that difference is ~3,600 cycles/frame. Decide explicitly whether to reserve a register for the dense path; it trades against the contract system, so it is a design decision needing the user's sign-off if it changes engine-wide register conventions (`memory/leapfrog_provenance_audit` — flag novel/irreversible bets).
- [ ] **Step 3: Pre-computed CRAM stream.** The gradient is a ROM/RAM stream of 3-colour groups, one per line, built at build time (or by `Palette_Compose` when it must follow the live palette). No arithmetic in the handler.
- [ ] **Step 4: Gate on oracle** — a sky gradient across ~96 lines, verified by sampling per-row colour and asserting a monotonic ramp. Profile the frame cost and record it against the budget model.
- [ ] **Step 5: Commit.**

---

## Task 6: Cross-fade + global operators

**Files:** Modify the palette module

- [ ] **Step 1: 16-frame RGB lerp** from `Pal_Base` to `Pal_Target`, armed on a section crossing, stepping per frame in `Palette_Compose`. Per-channel, shift-based (`>>4` per step), no multiply. Cross-fade replaces the P1 instant snap **only when armed** — a section whose config demands an instant change must still snap (mirror `pcfg_transition`'s existing semantics so parallax and palette agree at a boundary).
- [ ] **Step 2: Global operators** — fade-to-black, fade-to-white (S.C.E.'s 22-frame component stepping to `$EEE`), white flash, negative flash (XOR with `$EEE`, flicker every 4 frames). These compose AFTER cross-fade so a flash during a transition still reads as a flash.
- [ ] **Step 3: Gate** — cross a section boundary and capture consecutive frames, asserting the palette moves monotonically from A to B over ~16 frames (read CRAM per frame; do not eyeball).
- [ ] **Step 4: Commit.**

---

## Task 7: THE GATE — the OJZ water cluster, hand-authored

**Files:** `games/sonic4/data/parallax/configs.emp` (or the Phase-3 preset home if it exists by then); OJZ act data

This is the phase's acceptance. Compose, do not special-case: water is a preset.

- [ ] **Step 1: Author the cluster** — a variant boundary at the water line (`Variant_Water_Deep` below), S/H ON below the line, and the `Water_Level` patch slot so the line can move at runtime.
- [ ] **Step 2: Add the patch slot mechanism.** `Raster_Buf_B` exists for exactly this: the main loop rebuilds the back buffer with the current `Water_Level`, `Raster_VBlank` flips. The arm words must be RECOMPUTED when the line moves — that is the pipelined-delta arithmetic P1 moved to build time, so a moving line needs a small runtime recompute for the affected records. Write the recompute as a named proc with the formula in a comment referencing survey Ruling 1b.
- [ ] **Step 3: Give S/H something to shadow.** P1 could not prove S/H because OJZ's art is high-priority. The water surface/body content must be low-priority for S/H to dim it. This is a CONTENT requirement — if OJZ's tiles cannot be made low-priority below the water line, S/H transparency cannot be demonstrated there, and you must say so rather than quietly dropping it.
- [ ] **Step 4: Verify on oracle, MID-SCROLL,** with the exact-colour-per-row method plus a brightness-step measurement across the boundary for S/H (a real S/H dim is a ~2x step in mean row brightness; P1's attempt measured 1.94x in the WRONG direction because art dominated — a valid S/H result must be a step DOWN at the boundary line, isolated from art transitions by choosing a capture where the art is uniform across the line).
- [ ] **Step 5: Move the water line at runtime** and confirm the boundary tracks it without tearing or drift across ≥60 frames.
- [ ] **Step 6: Commit** with the evidence file, following GATE-EVIDENCE.md's structure (method, result table, residuals, and an explicit NOT-verified section).

---

## Task 8: Per-section palette cycling (`sec_pal_cycle`)

**Files:** Modify the palette module; OJZ data

- [ ] **Step 1: Define the script format** — a list of (line, first_index, count, frame_period, entries[]) advanced by `Palette_Compose`. `sec_pal_cycle` is a reserved `Sec` field with no consumer; this gives it one, wired at the same `Parallax_CheckBoundary` hook as `sec_pal` and `sec_raster_table`.
- [ ] **Step 2: Compose BEFORE cross-fade** (the fixed order) so cycling survives a transition rather than fighting it.
- [ ] **Step 3: Gate** — a visibly cycling band, verified by per-frame CRAM reads showing the expected rotation period.
- [ ] **Step 4: Commit.**

---

## Task 9: Docs, budget model, closeout

- [ ] **Step 1: Budget model file.** The design (§8) wants ONE machine-readable budget model that the generator enforces and Aurora displays. Phase 2 is where the numbers become real: cycles per op, the ~60-cycle HBlank window, `RASTER_CRAM_MAX`, max active variants, dense-run per-line cost, RAM ceilings. Write it as data (TOML/JSON under `tools/`), populated from Task 5's measurements, not from datasheet arithmetic.
- [ ] **Step 2: ENGINE_ARCHITECTURE §7** — move the palette engine, variants/regions, and the dense tier from PLANNED to SHIPPED, keeping the banner honest about what remains (sprite-table reflections, frame effects engine).
- [ ] **Step 3: DEFERRED_WORK** — close the water-level entry (its host now exists and is used); open any new riders.
- [ ] **Step 4: Consider the module split** into `engine/effects/{raster,palette}.emp` as its own parcel if these files have grown unwieldy. It is a byte-changing parcel needing the full repin/refreeze ritual, so it must be its own commit with the pair coherent.
- [ ] **Step 5: Merge** via superpowers:finishing-a-development-branch. Both canonical shapes green; replay net green or dispositioned; never leave master broken.

---

## Explicitly OUT of Phase 2
- `raster_dsl` / `palette_dsl` general constructors, the preset format, the starter pack, the dead-data proof → Phase 3
- Sprite-table-switch reflections (§7.6) → its own parcel; needs a second SAT in VRAM
- Aurora anything (Effects Lab, simulator, golden fixtures) → Phases 4-5
- Frame-level effects engine (sequencer, oscillators, shake, hit-stop) → Phase 6
- `sec_anim_blocks` (per-section animated tiles) — a separate DEFERRED_WORK entry, unrelated
