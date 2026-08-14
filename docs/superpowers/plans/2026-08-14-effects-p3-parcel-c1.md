# Effects P3 Parcel C1 — composable, parameterised effect presets

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make raster effects behave like SMPS instruments — a small library of parameterised presets that COMPOSE into one program at build time, with a measured density guard that refuses schedules the hardware cannot service.

**Architecture:** Presets are comptime functions returning a *fire list* (`array` of `RasterFire`); the language already supports this, so no new type is needed. `compose()` merges N fire lists into one by walking screen lines in ascending order, concatenating same-line ops with every `SetReg` in a prefix, and re-running `fire()` on each merged result so all existing per-fire ceilings apply to the composition rather than only to its parts. A cost model calibrated on the 2026-08-14 adjacent-fire measurement gates the merged schedule.

**Tech Stack:** `.emp` comptime (sigil), existing `engine/effects/raster_dsl.emp`. **Zero ROM bytes, aeon-only, no sigil pairing, no repin, no refreeze.** Gate is the Parcel-A gate: all seven goldens green with no rebaseline.

**Why this is split from Parcel C proper:** C as spec'd (`specs/2026-08-13-effects-p3-design.md`) also does `EffectsPreset`, the `sec_effects` rename, `Effects_InstallPreset` and all data relocation — every one of which moves bytes. This parcel is the comptime half, it delivers a usable authoring surface on its own (presets bind through the existing `raster:` field), and it honours the codebase's one-layout-mover-per-parcel rule. The byte-moving half becomes Parcel C2.

**Scope note:** the preset library lands in `engine/effects/raster_dsl.emp` rather than a new module, deliberately. A new module needs a `COMPTIME_HELPERS` registration in sigil (`crates/sigil-harness/src/native.rs`), which would make this a paired parcel and forfeit the zero-byte gate. Relocating the library to `engine/effects/fx_presets.emp` belongs in C2, where a paired registration is being paid anyway.

---

## File structure

| File | Responsibility | Change |
|---|---|---|
| `engine/effects/raster_dsl.emp` | The sparse-tier vocabulary. Gains `compose()`, the cost model, the density guard, and the starter preset library. | Modify |
| `games/sonic4/data/parallax/configs.emp` | Game-side fixtures. Gains the composition proof fixture. | Modify |
| `docs/EFFECTS_AUTHORING.md` | Authoring doc. Its six-consecutive-fire recommendation is now refused by the guard and must be corrected. | Modify |
| `tools/effects_budget_model.toml` | Budget model. Carries the two false-provenance rows. | Modify |

---

## Task 1: The measured density cost model and its guard

The 2026-08-14 measurement (`docs/benchmarks/effects-p3/DENSITY-EVIDENCE.md`) established two points: a 1-word VSRAM fire costs **454 cycles**, a 3-colour CRAM fire costs **526**, and an NTSC scanline is **~488**. Those two points determine the line `cost = 418 + 36 × words` per CRAM-class op (check: 1 word → 454, 3 words → 526).

**Files:**
- Modify: `engine/effects/raster_dsl.emp` (add constants + two comptime fns near `arm_at`, call the guard from `raster_program`)

- [ ] **Step 1: Add the model constants and the cost function**

Insert immediately above `comptime fn arm_at` in `engine/effects/raster_dsl.emp`:

```emp
// ---- the measured density model (docs/benchmarks/effects-p3/DENSITY-EVIDENCE.md) ----
// Two measured points, 2026-08-14 on oracle, as DIFFERENTIALS within one shape so the
// instrument's constant terms cancel:
//     1-word vsram fire   454 cyc        3-colour cram fire   526 cyc
// Those two determine a line in the number of CRAM-class words: 418 + 36*words.
// An NTSC scanline is 128000/262 = 488.5; 488 is used, floored, so the comparison is
// conservative in the direction that admits rather than refuses.
//
// IT ALSO LUMPS VSRAM IN WITH CRAM, WHICH IS KNOWN TO BE PESSIMISTIC. The corpus sweep
// (2026-08-14) found that only CRAM writes glitch: a CRAM write during rasterisation
// recolours the pixel being drawn, while VRAM, VSRAM and register writes produce no
// mid-line artifact at all (Nemesis, SpritesMind t=291). If that holds here, `vsram`
// inheriting EFX_BLANK_DELAY and the RASTER_CRAM_MAX ceiling is pure loss — Ristar
// writes 42 VSRAM words in ONE fire. Splitting the op class is booked, byte-changing,
// and out of scope for this parcel. It only ever makes fires CHEAPER, so the model here
// stays conservative and no schedule this admits becomes illegal under the split.
//
// WHAT THIS MODEL DELIBERATELY DOES NOT COUNT: OP_SET_REG. Its dispatch cost is
// UNMEASURED — the fire-ceiling comment above notes it is the compare chain's
// fall-through and therefore the most expensive op to dispatch, but no number exists.
// Rather than invent one, a set_reg contributes ZERO here, so the model UNDER-states
// cost and the guard fires only on evidence. A set_reg-only fire is unmodelled and
// never refused. Say so out loud wherever this model is cited.
pub const RASTER_FIRE_BASE_CYC  = 418
pub const RASTER_CRAM_WORD_CYC  = 36
pub const RASTER_SCANLINE_CYC   = 488
ensure(RASTER_FIRE_BASE_CYC + RASTER_CRAM_WORD_CYC * 1 == 454,
       "density model drifted from the measured 1-word vsram fire (454 cyc)")
ensure(RASTER_FIRE_BASE_CYC + RASTER_CRAM_WORD_CYC * 3 == 526,
       "density model drifted from the measured 3-colour cram fire (526 cyc)")

// fire_cost_cycles — modelled cost of one fire. Each CRAM-class op pays its own
// dispatch AND its own EFX_BLANK_DELAY spin, so the base is per-op, not per-fire.
comptime fn fire_cost_cycles(f: RasterFire) -> int {
    comptime var c = 0
    for o in fire_ops(f) {
        if op_is_set_reg(o) == 0 {
            c = c + RASTER_FIRE_BASE_CYC + RASTER_CRAM_WORD_CYC * op_cram_words(o)
        }
    }
    return c
}
```

- [ ] **Step 2: Add the schedule-level guard**

Density is a property of the SCHEDULE, not of one fire, so this cannot live in `fire()`. Add directly below `fire_cost_cycles`:

```emp
// check_density — a fire must finish before the next one is due. The budget between two
// fires is the number of scanlines between them; overrunning does not DROP the next fire
// (the counter is already armed) but pushes its writes into active display, which is
// measured as a visible mid-row colour change (DENSITY-EVIDENCE, rows 111-113 at
// x = 232/248/294 of 320). The last fire has nothing after it and is unconstrained.
comptime fn check_density(fires: array) -> int {
    comptime var i = 0
    for f in fires {
        if i + 1 < fires.len {
            let gap  = fire_screen_line(fires[i + 1]) - fire_screen_line(f)
            let cost = fire_cost_cycles(f)
            ensure(cost <= gap * RASTER_SCANLINE_CYC,
                   "raster program: the fire at screen line {fire_screen_line(f)} models at {cost} cycles but only {gap} scanline(s) = {gap * RASTER_SCANLINE_CYC} cycles remain before the fire at {fire_screen_line(fires[i + 1])}. MEASURED 2026-08-14: a 3-colour CRAM fire costs 526 cycles against a 488-cycle line, so consecutive colour fires overrun and paint a visible mid-line colour change. Either space these fires further apart, or move per-line colour work to the DENSE tier (raster_gradient_program), which stays inside ONE interrupt instead of paying an exception entry per line — that is how S3K writes 3 colours per line at 484. Note this model does not count OP_SET_REG at all, so the real cost is higher than the number above.")
        }
        i = i + 1
    }
    return 0
}
```

- [ ] **Step 3: Call the guard from `raster_program`**

In `raster_program`, immediately after the existing `let L = fire_lines(fires)` line, add:

```emp
    check_density(fires)
```

- [ ] **Step 4: Build and verify the shipped fixtures still pass**

```bash
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
DEBUG=1 ./build.sh 2>&1 | grep -E "built:|error"
```

Expected: `built: sonic4 debug native ROM — crc=eb607681 len=711314` — the exact CRC of master. Every shipped fixture is a single fire or widely spaced, so none is refused.

- [ ] **Step 5: Negative-probe the guard — it MUST refuse the adjacent-CRAM case**

Append to `games/sonic4/data/parallax/configs.emp`:

```emp
// TEMPORARY NEGATIVE PROBE — two adjacent 3-colour CRAM fires. Measured at 526 cyc
// against a 488-cyc line, so this MUST be refused.
const PROBE_DENSITY = [
    fire(112, [ cram($48, [$000E, $000C, $000A]) ]),
    fire(113, [ cram($48, [$010E, $010C, $010A]) ]),
]
pub data ProbeDensity: [u16; raster_words(PROBE_DENSITY)] = raster_program(PROBE_DENSITY)
```

Run: `DEBUG=1 ./build.sh 2>&1 | grep -c "models at 526 cycles"`
Expected: `1` — the build FAILS naming the cost. If it builds green, the guard is vacuous; stop and fix before continuing.

- [ ] **Step 6: Probe the admitted case — spacing 2 must PASS**

Change the probe's second fire line from `113` to `114`:

```emp
    fire(114, [ cram($48, [$010E, $010C, $010A]) ]),
```

Run: `DEBUG=1 ./build.sh 2>&1 | grep -E "built:|error"`
Expected: builds green. 526 ≤ 2 × 488 = 976. This proves the guard discriminates rather than refusing all CRAM work.

- [ ] **Step 7: Remove the probe and confirm byte-identity**

Delete the `PROBE_DENSITY` / `ProbeDensity` block, then:

```bash
DEBUG=1 ./build.sh 2>&1 | grep "built:"
```
Expected: `crc=eb607681 len=711314`, identical to master.

- [ ] **Step 8: Commit**

```bash
git add engine/effects/raster_dsl.emp
git commit -m "feat(effects): a density guard calibrated on the adjacent-fire measurement

Refuses schedules whose modelled cost exceeds the scanlines available before the
next fire, using the two points measured 2026-08-14 (1-word vsram 454 cyc,
3-colour cram 526 cyc, NTSC line 488). Negative-probed both ways: adjacent
3-colour CRAM fires are refused naming the cost, the same pair at spacing 2 is
admitted. The model does not count OP_SET_REG, whose dispatch is unmeasured, so
it under-states cost and fires only on evidence. Zero bytes."
```

---

## Task 2: `compose()`

**Files:**
- Modify: `engine/effects/raster_dsl.emp` (add below `region_boundary`)

- [ ] **Step 1: Write the composition function**

```emp
// compose — merge N fire lists into one program's fire list. THE point of the preset
// library: presets that do not combine force a combinatorial pile of hand-merged
// variants, which is the thing a preset library exists to avoid.
//
// Walks screen lines in ascending order rather than sorting, which gets three
// properties for free and without a sort's off-by-ones:
//   - the result is in strictly ascending line order, which fire_lines requires;
//   - two presets firing on the SAME line become ONE fire rather than a duplicate-line
//     error, which is what "layer these two effects" has to mean;
//   - every SetReg is emitted before every CRAM-class op, so the ruling-14 prefix
//     invariant holds by construction for merged fires.
// Each merged op list is passed back through `fire`, so the per-fire ceilings (ops,
// CRAM-class ops, CRAM words) apply to the COMPOSITION and not merely to its parts —
// composing two legal presets into an illegal fire is a build error, not a surprise.
pub comptime fn compose(progs: array) -> array {
    ensure(progs.len >= 1, "compose: nothing to compose")
    comptime var out = []
    for line in RASTER_MIN_FIRE_LINE..RASTER_MAX_FIRE_LINE + 1 {
        comptime var ops   = []
        comptime var found = 0
        for p in progs {
            for f in p {
                if fire_screen_line(f) == line {
                    found = 1
                    for o in fire_ops(f) {
                        if op_is_set_reg(o) == 1 { ops = ops ++ [o] }
                    }
                }
            }
        }
        for p in progs {
            for f in p {
                if fire_screen_line(f) == line {
                    for o in fire_ops(f) {
                        if op_is_set_reg(o) == 0 { ops = ops ++ [o] }
                    }
                }
            }
        }
        if found == 1 { out = out ++ [fire(line, ops)] }
    }
    return out
}
```

- [ ] **Step 2: Build to confirm it compiles unused**

Run: `DEBUG=1 ./build.sh 2>&1 | grep -E "built:|error"`
Expected: `crc=eb607681`. An unreferenced `comptime fn` is inert and emits nothing.

- [ ] **Step 3: Commit**

```bash
git add engine/effects/raster_dsl.emp
git commit -m "feat(effects): compose() — merge preset fire lists into one program

Walks screen lines ascending instead of sorting, which yields ascending order,
same-line merging, and the SetReg-prefix invariant by construction. Merged op
lists go back through fire(), so the per-fire ceilings bind the composition
rather than only its parts."
```

---

## Task 3: The starter preset library

Three presets, each a parameterised comptime fn returning a fire list. They live in `raster_dsl.emp` (already a `COMPTIME_HELPERS` member) so authors call them with no import, which is what makes the library feel like a library.

**Files:**
- Modify: `engine/effects/raster_dsl.emp` (add below `compose`)

- [ ] **Step 1: Write the three presets**

```emp
// ---- the starter preset library ---------------------------------------------
// A preset is a comptime fn returning a FIRE LIST, so presets compose (see `compose`)
// and take parameters. The `fx_` prefix is a namespace: these names are glob-injected
// into every module in the tree, and tools/emp_helper_closure.py is the collision gate.

// fx_sh_below — Shadow/Highlight ON from `line` down, H40 base restored at frame top.
// The cheapest dramatic effect the hardware has: one register write, zero CRAM traffic,
// and it darkens everything below the line including sprites.
pub comptime fn fx_sh_below(line: int) -> array {
    return [ fire(line, [ sh_on() ]) ]
}

// fx_vscroll_split — plane B's vertical scroll snaps to `offset` from `line` down, so
// the background stops tracking the camera below it. Vertical scroll BANDING.
// PICK THE OFFSET AGAINST THE ART: a shift equal to the background's vertical repeat
// period is pixel-invisible (the OJZ trunks repeat every 64 px, and a $0040 shift showed
// literally nothing — that cost a session on 2026-08-14).
pub comptime fn fx_vscroll_split(line: int, offset: int) -> array {
    return [ fire(line, [ vsram(2, [offset]) ]) ]
}

// fx_tint_band — swap `count` colours of a staged palette variant into CRAM at `line`,
// optionally turning Shadow/Highlight on at the same line. This is the water-boundary
// shape, generalised: `slot` names the variant, and the CRAM destination is DERIVED from
// pal_line/entry rather than asked for twice.
// The variant bound to `slot` must cover `pal_line` in its `lines` mask, or the staging
// line is never derived and this streams whatever the staging buffer holds. That cannot
// be checked here — binding is a runtime call (Palette_SetVariant) — and it is booked.
pub comptime fn fx_tint_band(line: int, slot: int, pal_line: int, entry: int,
                             count: int, sh: int) -> array {
    return [ region_boundary(line, pal_stage_off(0, pal_line, entry) & $7F,
                             slot, pal_line, entry, count, sh) ]
}
```

- [ ] **Step 2: Verify `fx_tint_band`'s derived address against the shipped water fixture**

The shipped water cluster in `games/sonic4/data/parallax/configs.emp` hand-supplies a CRAM address alongside `pal_line` and `entry`. Read that fixture and confirm the address `fx_tint_band` derives (`pal_line * 32 + entry * 2`) equals it for the same arguments. If it does not, the derivation is wrong — fix the derivation, not the fixture.

```bash
grep -n "region_boundary\|pal_region" games/sonic4/data/parallax/configs.emp | head
```

- [ ] **Step 3: Build**

Run: `DEBUG=1 ./build.sh 2>&1 | grep -E "built:|error"`
Expected: `crc=eb607681`.

- [ ] **Step 4: Run the helper-closure collision gate**

These names are injected into every module in the tree; a collision against a module-local name is silent.

```bash
python3 tools/emp_helper_closure.py . /home/volence/sonic_hacks/sigil/crates/sigil-harness/src/native.rs
```
Expected: `emp_helper_closure: OK — <N> names across 14 helpers, no collisions` with N grown by the number of new public names (was 427 before this parcel).

- [ ] **Step 5: Commit**

```bash
git add engine/effects/raster_dsl.emp
git commit -m "feat(effects): the starter preset library — fx_sh_below, fx_vscroll_split, fx_tint_band

Presets are parameterised comptime fns returning fire lists, so they compose and
take arguments; the language already supported this and only compose() was
missing. fx_tint_band derives its CRAM destination from pal_line/entry instead
of asking the author for the same fact twice. Helper-closure gate clean."
```

---

## Task 4: Prove composition by re-expressing a shipped fixture byte-identically

This codebase's standard for a new authoring path is: re-express something that already ships, prove the bytes are identical, *then* extend. `first_mismatch` exists for exactly this.

**Files:**
- Modify: `games/sonic4/data/parallax/configs.emp`

- [ ] **Step 1: Add the equivalence proof beside `OJZ_TestVsram`**

The shipped VSRAM fixture is one fire at line 112 writing `$0043` to VSRAM byte 2. `fx_vscroll_split(112, $0043)` must produce exactly that, and composing it with nothing must not change it.

```emp
// COMPOSITION EQUIVALENCE PROOF. The preset path must reproduce the hand-authored
// program EXACTLY before anything is built on it. Paired with a length check because
// first_mismatch returns -1 whenever the first list is a PREFIX of the second.
const OJZ_VSRAM_VIA_PRESET = compose([ fx_vscroll_split(OJZ_VSRAM_LINE, OJZ_VSRAM_OFFSET) ])
ensure(raster_words(OJZ_VSRAM_VIA_PRESET) == raster_words(OJZ_VSRAM_PROG),
       "preset path emits {raster_words(OJZ_VSRAM_VIA_PRESET)} words, hand-authored is {raster_words(OJZ_VSRAM_PROG)}")
ensure(first_mismatch(raster_program(OJZ_VSRAM_VIA_PRESET), raster_program(OJZ_VSRAM_PROG)) == -1,
       "preset path diverges from the hand-authored program at word {first_mismatch(raster_program(OJZ_VSRAM_VIA_PRESET), raster_program(OJZ_VSRAM_PROG))}")
```

- [ ] **Step 2: Build — the ensures must PASS**

Run: `DEBUG=1 ./build.sh 2>&1 | grep -E "built:|error|diverges"`
Expected: `crc=eb607681`. Both ensures silent. `OJZ_VSRAM_VIA_PRESET` is a `const`, so it emits nothing — the ROM is unchanged.

- [ ] **Step 3: Negative-probe the equivalence proof**

An equivalence check that cannot fail proves nothing. Temporarily change the preset call to `fx_vscroll_split(OJZ_VSRAM_LINE, $0044)`.

Run: `DEBUG=1 ./build.sh 2>&1 | grep -c "diverges from the hand-authored program"`
Expected: `1`. Then restore `OJZ_VSRAM_OFFSET` and rebuild to `crc=eb607681`.

- [ ] **Step 4: Add a real two-preset composition fixture**

This is the parcel's actual demonstration: two independently authored presets, one program, bound to a section.

```emp
// COMPOSITION DEMONSTRATION — two independent presets, one program. Shadow/Highlight
// from line 96 down, and plane B's vertical scroll banding at 140. Neither preset knows
// the other exists; compose() merges them and the per-fire ceilings bind the result.
// Spacing is 44 lines, far inside the density budget.
const OJZ_COMPOSED_PROG = compose([
    fx_sh_below(96),
    fx_vscroll_split(140, $0043),
])
pub data OJZ_TestComposed: [u16; raster_words(OJZ_COMPOSED_PROG)] = raster_program(OJZ_COMPOSED_PROG)
```

- [ ] **Step 5: Bind it to a free section and build**

`games/sonic4/data/levels/ojz/act1/act_descriptor.emp`: add `OJZ_TestComposed` to the `use` list on line 20, and add `raster: OJZ_TestComposed,` to the **section 4** entry (sections 4-8 are free).

Run: `DEBUG=1 ./build.sh 2>&1 | grep -E "built:|error"`
Expected: builds green with a **new** CRC (this adds a `pub data` — the first byte-moving step in the parcel).

> **STOP.** This step moves bytes and therefore forfeits the zero-byte gate. If you want the parcel to stay zero-byte and unpaired, do Steps 4-5 as a **separate follow-on commit** and let the parcel merge without them, or defer the fixture to Parcel C2 where a refreeze is already being paid. Confirm the intended choice before proceeding — do not silently make the parcel byte-changing.

- [ ] **Step 6: Commit**

```bash
git add games/sonic4/data/parallax/configs.emp games/sonic4/data/levels/ojz/act1/act_descriptor.emp
git commit -m "test(effects): prove the preset path reproduces the shipped program byte-identically

compose([fx_vscroll_split(112, \$0043)]) equals the hand-authored OJZ_TestVsram
word for word, paired with a length check because first_mismatch returns -1 on a
prefix. Negative-probed by perturbing the offset. Adds the two-preset composition
demonstration."
```

---

## Task 5: Correct the documentation the measurement invalidated

`docs/EFFECTS_AUTHORING.md` prescribes six consecutive single-line fires for a full-line palette swap. That schedule is now **refused by the guard from Task 1**, because a 3-colour CRAM fire measures 526 cycles against a 488-cycle line. The doc must not keep recommending something the build rejects.

**Files:**
- Modify: `docs/EFFECTS_AUTHORING.md`
- Modify: `tools/effects_budget_model.toml`

- [ ] **Step 1: Find every place the six-fire idiom is recommended**

```bash
grep -n "six\|consecutive\|ceil(16/3)\|full.line" docs/EFFECTS_AUTHORING.md
```

- [ ] **Step 2: Rewrite those passages**

Replace the recommendation with the measured position: consecutive colour fires overrun the scanline and paint a visible mid-line colour change; per-line colour work belongs in the **dense tier** (`raster_gradient_program`), which stays inside one interrupt rather than paying an exception entry per line — which is how S3K writes 3 colours per line at 484 cycles. Sparse adjacent fires are for ops that fit under a scanline, such as `vsram` at 454. Cite `docs/benchmarks/effects-p3/DENSITY-EVIDENCE.md`.

- [ ] **Step 3: Document `compose()` and the preset library**

Add a section covering: presets are comptime fns returning fire lists; `compose()` merges them; same-line fires merge into one; every ceiling applies to the composition; and the density guard bounds the schedule. Include the working two-preset example from Task 4 Step 4.

- [ ] **Step 4: Correct the budget model's false provenance**

In `tools/effects_budget_model.toml`:
- `full_line_fire_cost = 6` is a LINE COUNT (`ceil(16/3)`), not a cost. Rename to `full_line_fire_lines` and keep it `code-derived`.
- `sparse_tier_cycles_per_frame = 8358` was `VBlank_Handler + Raster_HInt` under oracle's interrupt-bucket bug (it buckets on handler entry PC vs `0x78`, and Aeon's IRQ6 vector is a ROM address). Mark it superseded and add the measured rows: `sparse_fire_vsram1_cycles = 454`, `sparse_fire_cram3_cycles = 526`, `ntsc_scanline_cycles = 488`, each tagged as measured-differential and citing the evidence note.
- Add an `[instrument]` note recording the bucket bug and that the correct reading is the `HBlank_Vector_Slot` routine row, so the next person does not re-derive it.

- [ ] **Step 5: Verify the budget checker still passes**

```bash
python3 tools/effects_budget_check.py 2>&1 | tail -5
```
Expected: passes. If it gates on the renamed key, update the checker in the same commit.

- [ ] **Step 6: Commit**

```bash
git add docs/EFFECTS_AUTHORING.md tools/effects_budget_model.toml
git commit -m "docs(effects): retire the six-consecutive-fire recommendation; document compose()

The measurement refuses it: a 3-colour CRAM fire is 526 cycles against a
488-cycle line, so consecutive colour fires overrun and paint a mid-line colour
change. Per-line colour work belongs in the dense tier. Also corrects the budget
model's two false-provenance rows and records oracle's interrupt-bucket bug."
```

---

## Task 6: Parcel gate

- [ ] **Step 1: Build both shapes**

```bash
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
./build.sh 2>&1 | grep "built:"
DEBUG=1 ./build.sh 2>&1 | grep "built:"
```
Expected, if Task 4 Steps 4-5 were deferred: `crc=8bbd7bec` and `crc=eb607681`, both identical to master.

- [ ] **Step 2: Confirm no golden moved**

```bash
cd /home/volence/sonic_hacks/sigil && git status --short
```
Expected: **empty**. A non-empty tree means bytes moved and the parcel needs the refreeze ritual and sigil pairing — reassess before merging.

- [ ] **Step 3: Full strict suite**

```bash
cd /home/volence/sonic_hacks/sigil
AEON_DIR=/home/volence/sonic_hacks/aeon SIGIL_EMIT=$PWD/target/release/emit_sound_blob \
  SIGIL_BUILD=$PWD/target/release/sigil cargo test --workspace --no-fail-fast 2>&1 \
  | grep -E "^test result" \
  | awk -F'[.;] ' '{gsub(/[^0-9]/,"",$2); gsub(/[^0-9]/,"",$3); p+=$2; f+=$3} END {print "TOTAL passed:", p, " failed:", f}'
```
Expected: `TOTAL passed: 3711  failed: 0`. Report aggregate totals — never tail a test run; a tail once hid 16 failures here.

- [ ] **Step 4: Helper-closure gate**

```bash
cd /home/volence/sonic_hacks/aeon
python3 tools/emp_helper_closure.py . /home/volence/sonic_hacks/sigil/crates/sigil-harness/src/native.rs
```
Expected: `no collisions`.

- [ ] **Step 5: Merge**

```bash
git checkout master
git merge --no-ff parcel/effects-p3-c1 -m "Merge parcel/effects-p3-c1: composable parameterised effect presets

compose() plus a three-preset starter library, and a density guard calibrated on
the 2026-08-14 adjacent-fire measurement. Presets are comptime fns returning fire
lists, so they take parameters and combine; merged fires go back through fire(),
so the per-fire ceilings bind the composition rather than only its parts.

The preset path is proven to reproduce OJZ_TestVsram word for word, and that
equivalence check is itself negative-probed. Zero bytes, seven goldens green with
no rebaseline, sigil tree untouched, strict suite 3711/0."
```

---

## Self-review

**Spec coverage.** This parcel covers the composition and parameterisation half of the owner's ruling. It deliberately does NOT cover: `EffectsPreset`, the `sec_effects` rename, `Effects_InstallPreset`, `Preset_None`/`Pal_Cycle_None`, data relocation, deleting the imperative install, or EFX-1/2/3/6 — all byte-moving, all Parcel C2. The runtime-varying half (patchable fires) is parcel P in the crown roadmap and is not in scope here.

**The composability limit this parcel does NOT remove, and must say so.** Two presets that
both touch the same VDP register with different frame-top resets are a **build error** —
`prog_init` keys its dedupe on the register and requires the resets to agree (closed
2026-08-14 as a wrong-pixel defect: the later reset silently won and left reg `$0C` with
interlace on permanently). That is correct behaviour, but it means composition is a
*negotiation* between presets whenever registers overlap, which is exactly what a preset
library should not require. The corpus answer is a **blanket register restore**: Gunstar
re-blits regs `$01`-`$12` from a RAM shadow every VBlank in ~290 cycles
(`gunstar_disasm/code/disasm.asm:636-655`), which is why both Treasure engines clobber
registers mid-frame with no per-effect cleanup obligation at all. Adopting that would
delete the `reset` parameter from `set_reg` outright and let presets touch registers
without agreeing. It is byte-changing (VBlank + shadow table), so it is its own parcel —
booked in the crown roadmap. **Do not design around the current limit as if permanent.**

**Known gaps, named rather than hidden.**
- `fx_tint_band` cannot verify that the variant bound to `slot` covers `pal_line`; binding is a runtime call. Booked as review §5 item 1.
- The cost model ignores `OP_SET_REG`, so a set_reg-heavy fire is unmodelled. Stated at the constants, in the guard's message, and in the doc.
- The model is two measured points and a line through them. `pal_region`, mixed fires and the two-CRAM-op shape were never measured; the spacing sweep that would find where the dot disappears is owed and listed in DENSITY-EVIDENCE.

**Type consistency.** `compose` takes and returns `array`; presets return `array`; `raster_program`/`raster_words` take `array` — consistent with the existing `OJZ_*_PROG` constants. `fire_cost_cycles` and `check_density` take `RasterFire` and `array` respectively, matching `fire_screen_line`/`fire_ops`/`op_cram_words`/`op_is_set_reg` as they exist today.
