# Effects P3 Parcel P-a — the encoder — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a raster fire be declared **patchable** at authoring time, and have the DSL emit a self-describing patch table so a runtime patcher never needs a magic offset — with every emitted word proved byte-exactly at build time, before any runtime code trusts it.

**Architecture:** Purely comptime. `RasterFire` gains a `Patch` variant carrying a channel and a screen-line band; `compose` is rewritten to carry that mark through reconstruction; `patched_program` emits the ordinary program padded to `RASTER_BUF_SIZE` and appends a 4-word-per-record patch table at byte 128. Nine build-time guards, each proved by inversion. **No runtime code, no RAM change, no struct change, no deletions** — those are Parcel P-b.

**Tech Stack:** `.emp` (sigil's language), 68000 target, sigil toolchain. There is no unit-test runner for `.emp`: the test discipline is a **failing build**. A guard is written first, proved to fail, then satisfied — and a guard that cannot be made to fail is a defect, not a pass.

**Spec:** `docs/superpowers/specs/2026-08-15-effects-p3-parcel-p-design.md`

---

## Before you start

```bash
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
```

Baseline confirmed 2026-08-15 on aeon `970c4b01` / sigil `ccfc6226`: `./build.sh` → `crc=0fcdcbaa`, `DEBUG=1 ./build.sh` → `50f6ae69`, `./build.sh demo` → `6af0112d`, `DEBUG=1 ./build.sh demo` → `fdc82cc0`.

Work on a branch: `git checkout -b parcel/effects-p3-p-a`.

**The inversion ritual, used in every task.** A guard is only proved by making it fail:
1. edit the predicate so it is false (or feed it bad input),
2. run the build, confirm it FAILS **with your message**,
3. revert the edit, confirm the build passes.
A guard that builds clean in both directions is vacuous — this codebase has a documented ledger of them, and `ensure` comparing an imported DATA symbol to an int always passes silently.

**Two spelling rules, both recorded traps in `engine/effects/raster_dsl.emp`:**
- A comptime fn's free names resolve at the **call site**. Names *imported* into `raster_dsl` (e.g. `RASTER_MIN_FIRE_LINE`) must NOT be spelled inside a fn body — spell the literal and pin it at module level (`raster_dsl.emp:34-59`). Names **defined in** `raster_dsl` ARE injected everywhere and are safe in bodies (`:341`).
- `{...}` in an `ensure` message is an **interpolation**. Interpolate parameters and locals only; spell constant names out in prose.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `engine/effects/raster_dsl.emp` | the entire encoder: variant, constructor, compose, guards, table emission | Modify |
| `games/sonic4/data/effects/ojz_effects.emp` | the `OJZ_TwoChannel` fixture and its hand-word twin | Modify |
| `docs/EFFECTS_AUTHORING.md` | author-facing docs for `patchable` | Modify |
| `docs/ENGINE_ARCHITECTURE.md` §7.12 | the patch-table wire format | Modify |
| `docs/benchmarks/effects-p3-p-a/GATE-EVIDENCE.md` | the parcel's evidence | Create |

No `map.toml` change: every symbol lands in an existing module.

---

### Task 1: The `Patch` variant and its accessors

**Files:**
- Modify: `engine/effects/raster_dsl.emp:89-91` (the enum), `:428-433` (the accessors)

- [ ] **Step 1: Add the variant**

Replace the `RasterFire` enum at `raster_dsl.emp:89-91`:

```
pub comptime enum RasterFire {
    Fire(int, array),                     // (screen line the effect lands on, RasterOp ARRAY)
    // (screen line, channel, band lo, band hi, RasterOp ARRAY) — a fire whose line MOVES at
    // runtime within [lo, hi]. The band is in SCREEN lines, like `line`; the encoder converts
    // to fire lines exactly once, in patch_table.
    Patch(int, int, int, int, array),
}
```

- [ ] **Step 2: Make the two existing accessors two-armed, and add four**

Replace `raster_dsl.emp:428-433`:

```
comptime fn fire_screen_line(f: RasterFire) -> int {
    return match f {
        Fire(m, ops) => m,
        Patch(m, ch, lo, hi, ops) => m,
    }
}
comptime fn fire_ops(f: RasterFire) {
    return match f {
        Fire(m, ops) => ops,
        Patch(m, ch, lo, hi, ops) => ops,
    }
}
// fire_band_lo / fire_band_hi return a STATIC fire's own line, so its interval is the
// degenerate [L, L]. That is what lets check_intervals and check_density run one formula
// over both record classes with no branch — and it is why the density guard automatically
// becomes a worst-case guard (Task 4).
comptime fn fire_band_lo(f: RasterFire) -> int {
    return match f {
        Fire(m, ops) => m,
        Patch(m, ch, lo, hi, ops) => lo,
    }
}
comptime fn fire_band_hi(f: RasterFire) -> int {
    return match f {
        Fire(m, ops) => m,
        Patch(m, ch, lo, hi, ops) => hi,
    }
}
comptime fn fire_is_patch(f: RasterFire) -> int {
    return match f {
        Fire(m, ops) => 0,
        Patch(m, ch, lo, hi, ops) => 1,
    }
}
comptime fn fire_channel(f: RasterFire) -> int {
    return match f {
        Fire(m, ops) => -1,
        Patch(m, ch, lo, hi, ops) => ch,
    }
}
```

- [ ] **Step 3: Prove sigil's exhaustiveness check is really doing the work**

Temporarily delete the `Patch` arm from `fire_ops` only. Run:

```bash
DEBUG=1 ./build.sh 2>&1 | tail -20
```

Expected: FAIL with `[match.non-exhaustive]` naming the missing `Patch` variant. Restore the arm and rebuild to green. (This is the guarantee the spec leans on in §1.1 — but note §1.2: it does NOT cover reconstruction, which is Task 3's whole subject.)

- [ ] **Step 4: Commit**

```bash
git add engine/effects/raster_dsl.emp
git commit -m "feat(raster-dsl): RasterFire::Patch variant + band accessors

A static fire's band is its own line, so every downstream walk runs one
formula over both record classes."
```

---

### Task 2: `RASTER_MAX_PATCH` and the `patchable` constructor

**Files:**
- Modify: `engine/effects/raster_dsl.emp` (constant beside `RASTER_SCANLINE_CYC` at `:555-561`; constructor after `region_boundary` at `:304`)

- [ ] **Step 1: Define the constant here, not in `raster.emp`**

Add beside the other module-defined constants (near `raster_dsl.emp:555`):

```
// RASTER_MAX_PATCH — patchable channels per program. DEFINED HERE on purpose: this module
// is a COMPTIME_HELPERS member, so a name defined here is glob-injected into every module
// (engine.effects.raster and engine.ram included) AND is safe to spell inside a comptime fn
// body. A constant imported FROM raster.emp would be neither — imports do not travel into a
// body, and this codebase has a measured case of that collapsing a range to empty and
// silently emitting zero fires.
//
// FOUR IS NOT A RAM DECISION. The binding constraint is the BAND BUDGET under density:
// disjoint bands over screen lines 3..223 must satisfy sum(hi_i - lo_i + 1) + (N-1) <= 221,
// so four channels each free to traverse the screen is not expressible — one water line with
// 200px of travel spends the budget alone. Raising this without widening the band budget buys
// nothing.
pub const RASTER_MAX_PATCH = 4
// The runtime masks a channel index with RASTER_MAX_PATCH - 1 (Parcel P-b), which is only an
// index bound if this is a power of two. Guard 7.
ensure((RASTER_MAX_PATCH & (RASTER_MAX_PATCH - 1)) == 0,
       "RASTER_MAX_PATCH must be a power of two — the runtime patcher masks the channel index with RASTER_MAX_PATCH minus 1, which only bounds the index for a power of two")
```

- [ ] **Step 2: Write the constructor with guards 1, 3 and 4**

Add after `region_boundary` (`raster_dsl.emp:304`):

```
// patchable — mark a fire as one whose screen line MOVES at runtime, within [lo, hi].
//
// IT TAKES AND RETURNS A FIRE LIST, not a fire, and that is the whole ergonomic point:
// every fx_ preset returns a LIST, so a fire-level spelling would be a type error at exactly
// the call an author reaches for first — patchable(fx_tint_band(...), ...). List-level
// composes with the preset library and feeds straight into compose.
//
// THE CHANNEL IS AUTHORED, not an encoder-assigned ordinal. `ch` selects which
// Effects_World_Y slot drives this fire at runtime (Parcel P-b). Ordinals would leave an
// author counting patchable fires in program order to find their own slot, and the count
// changes under compose merging.
//
// The bounds below are inlined literals per this module's opening note (3 and 223 are held
// by the module-level RASTER_MIN_FIRE_LINE / RASTER_MAX_FIRE_LINE pin near the top of this
// file); RASTER_MAX_PATCH is DEFINED in this module and so is safe to name.
pub comptime fn patchable(fires: array, ch: int, lo: int, hi: int) -> array {
    ensure(fires.len == 1,
           "patchable: got {fires.len} fires — mark exactly one. Marking a multi-fire preset would clamp all of its fires onto one line, because they would share a single world anchor.")
    ensure(ch >= 0 && ch < RASTER_MAX_PATCH,
           "patchable: channel {ch} outside 0..RASTER_MAX_PATCH-1 — the channel selects a runtime world-anchor slot")
    ensure(lo >= 3 && hi <= 223,
           "patchable: band {lo}..{hi} outside screen lines 3..223 (lines 0-2 belong to the priming records)")
    ensure(lo <= hi, "patchable: band {lo}..{hi} is inverted")
    let f = fires[0]
    ensure(fire_is_patch(f) == 0,
           "patchable: this fire is already patchable — marking it twice would silently discard the first band")
    let line = fire_screen_line(f)
    // The authored line is the template's DEFAULT schedule. If it sits outside its own band
    // the shipped template violates the invariant it declares, and the first runtime patch
    // would move the boundary somewhere the author never saw.
    ensure(line >= lo && line <= hi,
           "patchable: the authored line {line} is outside its own band {lo}..{hi}")
    return [ RasterFire.Patch(line, ch, lo, hi, fire_ops(f)) ]
}
```

- [ ] **Step 3: Prove all four guards by inversion**

For each, add the bad call temporarily to `games/sonic4/data/effects/ojz_effects.emp` (anywhere at module scope, e.g. `const P_PROBE = patchable(...)` — note a bare unreferenced `const` is comptime-inert, so instead put the probe inside an `ensure` that consumes it: `ensure(patchable([fire(100,[sh_on()])], ch: 9, lo: 40, hi: 120).len == 1, "probe")`), build, confirm the expected failure, then remove:

| Probe | Expected build failure |
|---|---|
| `ch: 9` | `channel 9 outside 0..RASTER_MAX_PATCH-1` |
| two fires in the list | `got 2 fires — mark exactly one` |
| `lo: 2` | `band 2..120 outside screen lines 3..223` |
| `lo: 130, hi: 180` with an authored line of 100 | `the authored line 100 is outside its own band 130..180` |

Also invert guard 7 by temporarily setting `RASTER_MAX_PATCH = 3`; expected: `must be a power of two`. Restore 4.

```bash
DEBUG=1 ./build.sh 2>&1 | tail -20
```

- [ ] **Step 4: Commit**

```bash
git add engine/effects/raster_dsl.emp
git commit -m "feat(raster-dsl): patchable() + RASTER_MAX_PATCH, four guards proved by inversion"
```

---

### Task 3: Rewrite `compose` so it carries the mark

**Files:**
- Modify: `engine/effects/raster_dsl.emp:331-368`

**Why this task exists at all.** `compose` destructures with the accessors but **reconstructs** every merged fire through `fire(line, ops)`, which returns a `Fire`. Adding `Patch` arms to the accessors satisfies exhaustiveness completely and compose still silently strips patchability from every composed program. Exhaustiveness polices destructuring; the loss is in reconstruction, which no `match` sees.

- [ ] **Step 1: Write the failing guard first — a twin that proves the mark survives**

Add to `games/sonic4/data/effects/ojz_effects.emp` at module scope (temporarily; it becomes part of the fixture in Task 7):

```
// Compose must not strip patchability. This fails BEFORE the compose rewrite.
const P_COMPOSE_PROBE = compose([ patchable([fire(100, [sh_on()])], ch: 0, lo: 40, hi: 120) ])
ensure(fire_is_patch(P_COMPOSE_PROBE[0]) == 1,
       "compose stripped the patchable mark — it rebuilds fires through fire(), which returns a static Fire")
```

- [ ] **Step 2: Run the build and watch it fail**

```bash
DEBUG=1 ./build.sh 2>&1 | tail -20
```

Expected: FAIL with `compose stripped the patchable mark`.

- [ ] **Step 3: Rewrite compose**

Replace the body of `compose` (`raster_dsl.emp:331-368`) — keep the existing doc comment above it and append the paragraph shown after the code:

```
pub comptime fn compose(progs: array) -> array {
    ensure(progs.len >= 1, "compose: nothing to compose")
    comptime var out = []
    for line in 3..224 {
        comptime var ops   = []
        comptime var found = 0
        comptime var is_p  = 0
        comptime var p_ch  = 0
        comptime var p_lo  = 0
        comptime var p_hi  = 0
        for p in progs {
            for f in p {
                if fire_screen_line(f) == line {
                    found = 1
                    if fire_is_patch(f) == 1 {
                        // Guard 9. Two patchable fires merged onto one line become ONE record
                        // and therefore ONE moving boundary, so they must agree on which
                        // channel drives it and how far it may travel. Disagreement is not
                        // reconcilable at runtime: the record has a single arm word.
                        if is_p == 1 {
                            ensure(p_ch == fire_channel(f) && p_lo == fire_band_lo(f) && p_hi == fire_band_hi(f),
                                   "compose: two patchable fires merged onto screen line {line} disagree about channel or band — a merged fire is ONE record with ONE arm word, so it can only have one anchor and one band. Give them the same channel and band, or author them on different lines.")
                        }
                        is_p = 1
                        p_ch = fire_channel(f)
                        p_lo = fire_band_lo(f)
                        p_hi = fire_band_hi(f)
                    }
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
        if found == 1 {
            // fire() FIRST, unconditionally: it is what applies the per-fire ceilings and the
            // mixed-fire ordering rule to the COMPOSITION rather than merely to its parts. The
            // patchable case then re-wraps the same op list, so it inherits every one of those
            // checks instead of quietly bypassing them.
            comptime var merged = fire(line, ops)
            if is_p == 1 { merged = RasterFire.Patch(line, p_ch, p_lo, p_hi, ops) }
            out = out ++ [merged]
        }
    }
    return out
}
```

Append to compose's doc comment:

```
// PATCHABILITY SURVIVES MERGING, and it takes explicit work. This function rebuilds every
// merged fire, so a mark carried only in the input variant is lost by construction —
// exhaustive matching cannot catch it, because the loss is in reconstruction, not
// destructuring. Merging patchable with static yields PATCHABLE (the static op layers onto
// the moving line); merging two patchables requires identical channel and band (guard 9).
```

- [ ] **Step 4: Run the build and watch it pass**

```bash
DEBUG=1 ./build.sh 2>&1 | tail -5
```

Expected: `built: sonic4 debug native ROM — crc=...`

- [ ] **Step 5: Prove guard 9 by inversion**

Temporarily compose two patchable fires on the same line with different channels:

```
const P_CONFLICT = compose([ patchable([fire(100, [sh_on()])],           ch: 0, lo: 40, hi: 120),
                             patchable([fire(100, [vsram(2, [$0043])])], ch: 1, lo: 40, hi: 120) ])
ensure(P_CONFLICT.len == 1, "probe")
```

Expected: FAIL with `disagree about channel or band`. Remove the probe.

- [ ] **Step 6: Commit**

```bash
git add engine/effects/raster_dsl.emp games/sonic4/data/effects/ojz_effects.emp
git commit -m "fix(raster-dsl): compose carries the patchable mark through reconstruction

Exhaustiveness polices destructuring; compose rebuilds fires through fire(),
so the mark was lost with a clean build. Guard 9 covers the merge conflict."
```

---

### Task 4: The interval invariant (guard 2) and worst-case density (guard 8)

**Files:**
- Modify: `engine/effects/raster_dsl.emp:583-595` (`check_density`), and add `check_intervals` beside it

**Why guard 2 is the parcel's most dangerous predicate.** `gap = L[k] - L[k-1] - 1` is stored as a **byte**, and a violated interval yields `gap = -1`, whose byte is `$FF`. `$8AFF` is `RASTER_ARM_PARK`. So a one-line overlap parks the counter and **kills every fire after it**, silently.

- [ ] **Step 1: Write `check_intervals`**

```
// check_intervals — GUARD 2, the invariant every other property rests on. Stated ONCE, in
// FIRE-LINE space, matching fire_lines: each record has a possible fire-line interval, a
// point [L, L] for a static fire and [lo-1, hi-1] for a patchable one, and the intervals
// must be strictly ascending and disjoint. Priming records occupy fire lines 0 and 1, so the
// walk starts at prev_hi = 1.
//
// WHAT A VIOLATION DOES, and why the message says so: the runtime patcher stores
// L[k] - L[k-1] - 1 as the LOW BYTE of an $8Axx arm word. Two records able to reach the same
// fire line make that -1, whose byte is $FF — and $8AFF is RASTER_ARM_PARK. So an overlap of
// a single line does not merely mis-place a boundary, it parks the counter and kills every
// remaining fire in the frame, with no other symptom.
comptime fn check_intervals(fires: array) -> int {
    comptime var prev_hi = 1                     // priming record 1 sits at fire line 1
    for f in fires {
        let lo_fl = fire_band_lo(f) - 1
        let hi_fl = fire_band_hi(f) - 1
        ensure(lo_fl > prev_hi,
               "raster program: the record reachable at fire lines {lo_fl}..{hi_fl} can collide with the previous record, which reaches up to fire line {prev_hi}. Records must occupy STRICTLY ASCENDING, DISJOINT fire-line intervals (a static fire's interval is its own line; a patchable fire's is its band). This is not a tidiness rule: the arm gap is stored as the low byte of an $8Axx word, so two records on one fire line make the gap -1, whose byte is $FF — the PARK word. That kills every fire after it in the frame, silently.")
        prev_hi = hi_fl
    }
    return 0
}
```

- [ ] **Step 2: Rewrite `check_density` to be worst-case**

Replace the `gap` line inside `check_density` (`raster_dsl.emp:587`):

```
            let gap  = (fire_band_lo(fires[i + 1]) - 1) - (fire_band_hi(f) - 1)
```

and append to its doc comment:

```
// IT IS NOW A WORST-CASE CHECK, and that took no branch. The gap is measured from this
// record's HIGHEST reachable fire line to the next record's LOWEST — and because a static
// fire's band is its own line, the formula reduces to exactly the old authored-line
// difference for a program with no patchable records. Bytes for static programs are
// unchanged.
//
// WITHOUT THIS, THE GUARD GOES VACUOUS THE MOMENT A FIRE CAN MOVE. Two channels banded
// 40..120 and 121..200 with authored lines 100 apart pass the AUTHORED-line check trivially
// (gap 100 lines) and then clamp to 120 and 121 at runtime — one scanline apart, two
// 3-word CRAM fires at a measured 526 cycles against a 488-cycle line, which is precisely
// the overrun this guard exists to refuse.
```

- [ ] **Step 3: Call both from `raster_program`**

In `raster_program` (`raster_dsl.emp:685-686`), after `let L = fire_lines(fires)`:

```
    let L = fire_lines(fires)
    check_intervals(fires)
    check_density(fires)
```

- [ ] **Step 4: Prove guard 2 by inversion — with the exact collision case**

Temporarily add to `ojz_effects.emp`:

```
const P_OVERLAP = raster_program([ fire(100, [sh_on()]),
                                   RasterFire.Patch(150, 0, 101, 180, [sh_on()]) ])
ensure(P_OVERLAP.len > 0, "probe")
```

Expected: FAIL with `can collide with the previous record` naming fire lines `100..179` against `100`. (Static fire line 99 for screen 100; band lo 101 → fire line 100 — wait, verify the numbers the message prints and record them in the evidence doc; the point is the guard fires.) Remove the probe.

- [ ] **Step 5: Prove guard 8 by inversion — the case that used to pass**

```
const P_DENSE = raster_program(compose([
    patchable([fire(60,  [pal_region($48, 0, 2, 4, 3)])], ch: 0, lo: 40,  hi: 120),
    patchable([fire(190, [pal_region($48, 0, 2, 4, 3)])], ch: 1, lo: 121, hi: 200),
]))
ensure(P_DENSE.len > 0, "probe")
```

Expected: FAIL with `models at 526 cycles but only 1 scanline(s)`. Confirm that widening the second band to `lo: 130` makes it build, then remove the probe.

- [ ] **Step 6: Confirm static programs did not move**

```bash
./build.sh 2>&1 | grep "^built:"
```

Expected: `crc=0fcdcbaa` — unchanged, because no patchable record exists yet and the density formula reduces to the old one. **If this CRC moved, stop:** the density rewrite changed a static program's legality or the guards emitted something.

- [ ] **Step 7: Commit**

```bash
git add engine/effects/raster_dsl.emp
git commit -m "feat(raster-dsl): guard 2 (disjoint fire-line intervals) + guard 8 (worst-case density)

Density measured band-edge to band-edge, which reduces to the old authored-line
check for static programs — CRC unchanged at 0fcdcbaa."
```

---

### Task 5: `patched_program`, `patched_words`, and the arm-layout guards

**Files:**
- Modify: `engine/effects/raster_dsl.emp` (add after `raster_program`, `:713`)

- [ ] **Step 1: Write the layout function**

```
// arm_word_index — the WORD index of record k's arm word inside the emitted program. The
// header is one word; the two priming records are [arm, opc] pairs at words 1-2 and 3-4; each
// authored record is [arm, opc] plus its op bodies. Records 0 and 1 are the priming pair.
//
// This is the second independent path to a fact raster_program computes while emitting, and
// Task 5's guards cross-check them against each other. A layout function that merely restated
// the emitter would prove nothing.
comptime fn arm_word_index(fires: array, k: int) -> int {
    if k == 0 { return 1 }
    if k == 1 { return 3 }
    comptime var idx = 5
    comptime var j   = 2
    for f in fires {
        if j == k { return idx }
        idx = idx + 2
        for o in fire_ops(f) { idx = idx + op_size(o) }
        j = j + 1
    }
    return idx
}
```

- [ ] **Step 2: Write the table emitter**

```
// patch_table — the self-describing patch descriptor appended at byte 128 of a patched
// template. One entry per authored record, FOUR WORDS each, every field in FIRE-LINE space:
//
//     [arm_off][line_src][band_lo_fl][band_hi_fl]
//
//   arm_off     byte offset into Raster_Buf_B of the arm word this entry rewrites — the arm
//               of record k-2, because arm_at(L,i) schedules the gap that LANDS record i+2.
//               Pre-resolved here so the runtime keeps no offset history.
//   line_src    a literal fire line (high bit clear) for a static record, or $8000|channel
//               for a patchable one.
//   band_lo_fl  the band in fire lines. A static record writes its own fire line into both,
//   band_hi_fl  so every field of every entry is in ONE coordinate system.
comptime fn patch_table(fires: array) -> array {
    comptime var out = [fires.len]
    comptime var k   = 2
    for f in fires {
        comptime var src = fire_screen_line(f) - 1
        if fire_is_patch(f) == 1 { src = $8000 | fire_channel(f) }
        out = out ++ [2 * arm_word_index(fires, k - 2),
                      src,
                      fire_band_lo(f) - 1,
                      fire_band_hi(f) - 1]
        k = k + 1
    }
    return out
}
```

- [ ] **Step 3: Write guard 6 — the arm layout cross-check**

```
// check_arm_layout — GUARD 6. Every arm_off the table hands the runtime must point at a word
// the emitter actually wrote as an arm word, AND at the RIGHT one. Both halves are needed: a
// wrong offset that happens to land on an op_count fails the $8A00 test, while an offset
// landing on a DIFFERENT record's arm passes it — and would corrupt the schedule at runtime
// in a way nothing else here can see. Testing the VALUE against arm_at closes that.
comptime fn check_arm_layout(fires: array, out: array) -> int {
    let L = fire_lines(fires)
    for j in 0..fires.len {
        let w = out[arm_word_index(fires, j)]
        ensure((w & $FF00) == $8A00,
               "patched_program: the word the patch table points at for record {j} is not a VDP reg $0A write. The runtime patcher stores a byte there sight-unseen, so a wrong offset silently rewrites a record's op_count and sends the walker through ROM as opcodes inside a raw interrupt handler.")
        ensure(w == arm_at(L, j),
               "patched_program: the patch table's offset for record {j} points at an arm word, but not that record's — the emitted word does not match the arm the schedule derives for it.")
    }
    return 0
}
```

- [ ] **Step 4: Write the two public entry points**

```
// patched_words — the emitted word count of a patched template: the program padded to
// RASTER_BUF_SIZE, then the table. Use it as the length annotation on the `pub data`.
//
// HONEST SCOPE OF THIS AS A CROSS-CHECK: the body's own word count is checked by
// raster_program's `out.len == raster_words(fires)`, which runs on every call and is the
// independent-path check. Once padded, the body is 64 words by construction, so what THIS
// adds is the table's framing — 1 count word plus 4 per record — and the pin of the declared
// ROM footprint at the linker seam.
pub comptime fn patched_words(fires: array) -> int {
    return 64 + 1 + 4 * fires.len
}

// patched_program — a raster program that a runtime patcher can move. The ordinary program,
// padded to exactly RASTER_BUF_SIZE bytes, then the patch table at byte 128.
//
// WHY THE PADDING IS NOT WASTE. Raster_CopyPatchedTemplate copies a FIXED RASTER_BUF_SIZE
// bytes from every template, so a patched template is already read to +128 — padding makes
// that read defined, which closes the over-read half of EFX-4 for patched templates, and it
// puts the table at a CONSTANT address (+128) so nothing needs a second symbol or a preset
// field to find it. The copy stops exactly at the table boundary, so the table itself is
// never partially copied into Buf_B.
pub comptime fn patched_program(fires: array) -> array {
    comptime var out = raster_program(fires)     // every existing guard, plus 2 and 8
    check_arm_layout(fires, out)
    comptime var pad = 64 - out.len
    ensure(pad >= 0,
           "patched_program: the program body is {out.len} words, which does not fit in the 64-word buffer the runtime copies")
    for i in 0..pad { out = out ++ [0] }
    out = out ++ patch_table(fires)
    ensure(out.len == patched_words(fires),
           "patched_program: emitted {out.len} words but patched_words counted {patched_words(fires)} — the emitter and the length annotation disagree")
    return out
}
```

- [ ] **Step 5: Prove guard 6 by inversion**

Temporarily change `arm_word_index`'s priming case from `if k == 0 { return 1 }` to `return 2`. Build. Expected: FAIL with `is not a VDP reg $0A write` (word 2 is priming record 0's op_count, which is 0). Then change it to `return 3` and rebuild: expected FAIL with `points at an arm word, but not that record's`. Restore `return 1`.

This inversion pair is the point of the task: it proves both halves of guard 6 independently.

- [ ] **Step 6: Commit**

```bash
git add engine/effects/raster_dsl.emp
git commit -m "feat(raster-dsl): patched_program + the self-describing patch table

Guard 6 proved in both halves by inversion: a wrong offset landing on an
op_count fails the \$8A00 test, one landing on another record's arm fails the
value test."
```

---

### Task 6: Helper-closure collision check

**Files:**
- Run only: `tools/emp_helper_closure.py`

`raster_dsl` is a COMPTIME_HELPERS member, so every public name added in Tasks 2 and 5 (`RASTER_MAX_PATCH`, `patchable`, `patched_program`, `patched_words`) is glob-injected into **every module in the tree**. A collision with another helper's export silently changes which name a module resolves — the one way helper membership changes emitted bytes.

- [ ] **Step 1: Run the gate**

```bash
python3 tools/emp_helper_closure.py
```

Expected: exit 0, no collisions reported. If it reports one, rename the new export — do not proceed.

- [ ] **Step 2: Confirm no module changed reachability**

```bash
SIGIL_WARNINGS=full DEBUG=1 ./build.sh 2>&1 | grep module.unreachable | sort > /tmp/unreachable-after.txt
git stash && SIGIL_WARNINGS=full DEBUG=1 ./build.sh 2>&1 | grep module.unreachable | sort > /tmp/unreachable-before.txt && git stash pop
diff /tmp/unreachable-before.txt /tmp/unreachable-after.txt
```

Expected: empty diff. (~14 unreachable for sonic4 and ~40 for demo are BY DESIGN — each evaluates in the target that uses it. A module unreachable in BOTH targets is the anomaly.)

- [ ] **Step 3: Commit (evidence only, if the tool writes anything)**

No commit if both checks are clean; record both outputs for Task 9's evidence doc.

---

### Task 7: The `OJZ_TwoChannel` fixture and its hand-word twin

**Files:**
- Modify: `games/sonic4/data/effects/ojz_effects.emp` (append after the VSRAM fixture)

**Design of the fixture.** Channel 0 is the water-shaped moving boundary (`sh_on` + `pal_region`, 2 ops); channel 1 is a VSRAM band. Bands are `40..120` and `130..200` — disjoint with a 10-line worst-case separation, so guard 8 passes (channel 0 models at 526 cycles against 4880 available). Authored lines are 100 and 160, each inside its own band.

- [ ] **Step 1: Write the fixture and the twin**

```
// ===========================================================================
// OJZ_TwoChannel — the Parcel P-a gate. TWO independently patchable boundaries in ONE
// program, which is exactly what P3 spec §9 declared out of scope for Parcel C ("two
// independently patched effects in one section — Raster_Buf_B is single").
//
// It emits no runtime behaviour in P-a: nothing installs it yet. Its whole job is to be
// compared word-for-word against the hand twin below, so that Parcel P-b's runtime patcher
// inherits a table whose every offset is already proved.
//
// Channel 0 — the water shape: S/H on plus a 3-colour region swap, band 40..120.
// Channel 1 — a plane B vertical scroll split, band 130..200.
// The bands are 10 lines apart at their closest, which is what makes channel 0's modelled
// 526 cycles fit (guard 8 measures band edge to band edge, not authored line to authored
// line).
const OJZ_TC_PROG = compose([
    patchable(fx_tint_band(line: 100, slot: 0, pal_line: 2, entry: 4, count: 3, sh: 1),
              ch: 0, lo: 40,  hi: 120),
    patchable(fx_vscroll_split(line: 160, offset: $0043),
              ch: 1, lo: 130, hi: 200),
])

// THE PIN. Literals on purpose: a pin sharing symbols with the encoder it pins is weaker.
// 72 is pal_stage_off(0, 2, 4) = 0*128 + 2*32 + 4*2.
// Fire lines: priming 0 and 1, then 99 (screen 100) and 159 (screen 160).
//   arm0 = $8A00 | (99 - 1 - 1)  = $8A61
//   arm1 = $8A00 | (159 - 99 - 1) = $8A3B
//   records 2 and 3 park: nothing follows them.
// Table entries, in FIRE lines: ch0 -> arm_off 2 (word 1), src $8000, band 39..119;
//                               ch1 -> arm_off 6 (word 3), src $8001, band 129..199.
const OJZ_TC_HAND = [
    %0100,                      // pal_dirty_mask — CRAM line 2, from the pal_region only
    $8A61, 0,                   // fire 0 — priming; THE word channel 0's patch rewrites
    $8A3B, 0,                   // fire 1 — priming; THE word channel 1's patch rewrites
    $8AFF, 2,                   // fire 2 — channel 0, two ops
      0, $8C89,                 //   OP_SET_REG — S/H on
      4, $C048, $0000,          //   OP_PAL_REGION, command longword split
                 2,             //   count-1
                 72,            //   Pal_Variant_Stage offset
    $8AFF, 1,                   // fire 3 — channel 1, one op
      2, $4002, $0010,          //   OP_CRAM opcode with a VSRAM WRITE command longword
                 0,             //   count-1
                 $0043,         //   the scroll value
    $8AFF, $FFFF,               // park + RASTER_OPS_END
]
ensure(raster_words(OJZ_TC_PROG) == OJZ_TC_HAND.len,
       "OJZ_TwoChannel: DSL counts {raster_words(OJZ_TC_PROG)} body words, the hand program is {OJZ_TC_HAND.len}")
ensure(first_mismatch(raster_program(OJZ_TC_PROG), OJZ_TC_HAND) == -1,
       "OJZ_TwoChannel: DSL body diverges from the hand-authored words at index {first_mismatch(raster_program(OJZ_TC_PROG), OJZ_TC_HAND)}")

// The TABLE twin — the words Parcel P-b's runtime will walk. Checked separately from the
// body so a failure names which half moved.
const OJZ_TC_TABLE_HAND = [
    2,                          // count — two authored records
    2, $8000, 39,  119,         // channel 0: rewrites the arm at byte 2, band 39..119 (fire lines)
    6, $8001, 129, 199,         // channel 1: rewrites the arm at byte 6, band 129..199
]
// NOTE the separate .len ensure is REQUIRED, not belt-and-braces: first_mismatch walks only
// a's indices and returns -1 whenever a is a PREFIX of b, so a table short by a trailing
// entry compares EQUAL. Nothing inside first_mismatch can see that.
ensure(patched_words(OJZ_TC_PROG) == 64 + OJZ_TC_TABLE_HAND.len,
       "OJZ_TwoChannel: patched_words says {patched_words(OJZ_TC_PROG)} but 64 padded body words plus the hand table is {64 + OJZ_TC_TABLE_HAND.len}")

pub data OJZ_TwoChannel: [u16; patched_words(OJZ_TC_PROG)] = patched_program(OJZ_TC_PROG)
```

- [ ] **Step 2: Build and reconcile the twin**

```bash
DEBUG=1 ./build.sh 2>&1 | tail -20
```

Expected: PASS. If a mismatch is reported, the message names the **index**. Decide which side is wrong by hand before editing either — the twin exists to catch encoder bugs, so silently "fixing" the twin to match the encoder destroys the gate. The most likely genuine discrepancy is the VSRAM command longword (`$4002 $0010`): confirm it against `vdp_comm(2, VdpTarget.Vsram, VdpOp.Write)` and against the existing `OJZ_TestVsram` fixture in this file before changing it.

- [ ] **Step 3: Add the table twin to the emitted image check**

The body and table twins above check the two halves separately. Add the whole-image check:

```
// The whole emitted image, body + padding + table, in one comparison. The padding is
// implicit: any mismatch in its length shows up here as a divergence at the first table word.
ensure(first_mismatch(patched_program(OJZ_TC_PROG),
                      OJZ_TC_HAND ++ comptime for i in 0..(64 - OJZ_TC_HAND.len) { 0 } ++ OJZ_TC_TABLE_HAND) == -1,
       "OJZ_TwoChannel: the emitted patched image diverges from the hand twin at index {first_mismatch(patched_program(OJZ_TC_PROG), OJZ_TC_HAND ++ comptime for i in 0..(64 - OJZ_TC_HAND.len) { 0 } ++ OJZ_TC_TABLE_HAND)}")
```

If `comptime for` is not accepted in expression position here, build the padded twin as a named `const` on the line above and reference it — check `OJZ_GradientStream` (`ojz_effects.emp`, the `comptime for i in 0..288` line) for the accepted spelling.

- [ ] **Step 4: Prove the whole-image twin can fail**

Temporarily change one word of `OJZ_TC_TABLE_HAND` (e.g. `39` → `40`). Build; expected FAIL naming the index. Restore.

- [ ] **Step 5: Record the new CRCs**

```bash
./build.sh 2>&1 | grep "^built:"; DEBUG=1 ./build.sh 2>&1 | grep "^built:"
```

Both CRCs **will** have moved — `OJZ_TwoChannel` adds 146 bytes (73 words) of ROM. Record them; they are the numbers the freeze and the evidence doc cite.

- [ ] **Step 6: Commit**

```bash
git add games/sonic4/data/effects/ojz_effects.emp
git commit -m "test(effects): OJZ_TwoChannel — two patchable boundaries, pinned word-for-word

Body, table and whole-image twins, each able to fail. This is the parcel's gate:
P-b's runtime inherits a table whose every offset is proved at build time."
```

---

### Task 8: Documentation sync

**Files:**
- Modify: `docs/EFFECTS_AUTHORING.md`, `docs/ENGINE_ARCHITECTURE.md` §7.12

CLAUDE.md makes this mandatory: "if code diverges from [the architecture doc], one of them is wrong."

- [ ] **Step 1: Document `patchable` in `EFFECTS_AUTHORING.md`**

Add a section beside the existing raster-authoring material covering: the list-in/list-out shape and why (`fx_` presets return lists); the authored channel and what it will select at runtime; the band and the disjointness rule; that guard 8 measures band edge to band edge, so widely-banded channels need real separation; and the worked `OJZ_TwoChannel` example. **Do not** document a runtime API — none exists until P-b.

- [ ] **Step 2: Document the wire format in `ENGINE_ARCHITECTURE.md` §7.12**

Add the table layout exactly as in `patch_table`'s comment, the `+128` constant-address rule and the reason (the fixed 128-byte copy), and a note that a schedule-recompute variant would be a **new table version** because `arm_off` is pre-resolved per entry.

- [ ] **Step 3: Correct the stale reference the roadmap flagged**

`docs/EFFECTS_AUTHORING.md` still calls the VSRAM landing line UNMEASURED while `DEFERRED_WORK.md` records it MEASURED at N+1. Reconcile to N+1, citing `docs/benchmarks/effects-p3/GATE-EVIDENCE.md`, and note the measurement may be reg `$0B`-mode dependent rather than global.

- [ ] **Step 4: Commit**

```bash
git add docs/EFFECTS_AUTHORING.md docs/ENGINE_ARCHITECTURE.md
git commit -m "docs(effects): patchable authoring + the patch-table wire format"
```

---

### Task 9: The ritual — suite, repin, refreeze, evidence

**Files:**
- Create: `docs/benchmarks/effects-p3-p-a/GATE-EVIDENCE.md`
- Modify (sigil): `pins.rs` via `repin`

- [ ] **Step 1: Four shapes build**

```bash
./build.sh 2>&1 | grep "^built:"
DEBUG=1 ./build.sh 2>&1 | grep "^built:"
./build.sh demo 2>&1 | grep "^built:"
DEBUG=1 ./build.sh demo 2>&1 | grep "^built:"
```

Expected: all four succeed. The two demo CRCs must be **unchanged** (`6af0112d` / `fdc82cc0`) — P-a touches no demo-reachable module, and a demo CRC move means a helper injection reached further than intended.

- [ ] **Step 2: Boot all four shapes**

Per the release-shape blackout precedent, boot every shape — no gate here looks at a screen, so a shape that builds and dies is invisible to everything else in this plan. One Oracle instance only (`pgrep -a oracle_gui`).

- [ ] **Step 3: sigil suite**

```bash
cd /home/volence/sonic_hacks/sigil && cargo test --release --no-fail-fast 2>&1 | tail -40
```

Read the **aggregate totals and every failing-target line** — never tail a run and call it green. Baseline is 3716 / 0 across 327 binaries, and it is a **lower bound**: `deep_nesting_aborts` still aborts without printing a `test result` line (booked, user-ruled not to chase).

- [ ] **Step 4: repin and refreeze**

```bash
cd /home/volence/sonic_hacks/sigil
cargo build --release -p sigil-cli -p sigil-harness    # BOTH binaries, always
cargo run --release -p sigil-harness --bin refreeze -- \
  --freeze parcel-p-a --ab "docs/benchmarks/effects-p3-p-a/GATE-EVIDENCE.md"
```

`refreeze --freeze` runs `repin` itself. `pins.rs` is a **gate, not an input** — and P-a moves the `RASTER` region length plus the OJZ effects data, so pins WILL move. Re-verify the ROM CRCs **after** the freeze: fixing a region changes `pins.rs`, and those pins feed placement, so the ROM can move again after the first refreeze. A gate document citing a CRC it did not test is worse than one citing none.

- [ ] **Step 5: Write the evidence doc**

`docs/benchmarks/effects-p3-p-a/GATE-EVIDENCE.md` records, with the actual outputs pasted:
- the four post-freeze CRCs and the two demo CRCs proved unchanged;
- **every inversion proof**: guard, the probe used, the exact failure message, and confirmation the build went green again. Nine guards, and guard 6 has two halves;
- the helper-closure output and the empty unreachable diff;
- the suite totals, stated as a lower bound with the reason;
- what P-a explicitly does **not** prove: no runtime walks the table, so the table's *correctness in use* is Parcel P-b's gate. Say it plainly — a gate document that implies more coverage than it has is the failure mode this ledger exists to prevent.

- [ ] **Step 6: Commit and merge**

```bash
cd /home/volence/sonic_hacks/aeon
git add docs/benchmarks/effects-p3-p-a/GATE-EVIDENCE.md
git commit -m "docs(effects): Parcel P-a gate evidence — nine guards, each proved by inversion"
```

Merge aeon and sigil **as a pair** — the sigil registry is global and an aeon tree must build with sigil binaries whose pin state matches it.

---

## Self-review

**Spec coverage.** §1.1 patchable → Task 2. §1.2 compose → Task 3. §1.3 interval invariant → Task 4. §2 table/padding → Task 5. §3 density → Task 4. §4 P-a scope and gate → Tasks 7, 9. §5 guards 1-9 → Tasks 2 (1,3,4,7), 3 (9), 4 (2,8), 5 (5,6). §5 spelling rules → Task 2 Step 1 and the header. §8 ritual → Task 9. §10 `lo == hi` allowed → `patchable` uses `lo <= hi`, so a degenerate band passes; no task forbids it.

**Deliberately deferred to P-b, and named in the spec:** all runtime code, the seven deletions, `Raster_State` and `EffectsPreset` changes, the OJZ preset conversion, EFX-4/EFX-8 ledger surgery, the `game_loop` pin question, and the `raster_port` vacuous-pin hole.

**Known soft spot.** Task 7 Step 1's twin hard-codes the VSRAM command longword as `$4002 $0010`. Step 2 tells the engineer to verify it against `vdp_comm` and the existing `OJZ_TestVsram` fixture before editing either side, and to reason about which side is wrong rather than reconciling the twin to the encoder — the twin is the gate, and a twin edited to agree is no longer one.
