# Effects Phase 3 — Parcel A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `engine/effects/raster_dsl.emp`, `engine/effects/palette_dsl.emp`, and a budget-model
checker, and re-express the two shipped sparse raster fixtures through the DSL **in place** — moving
zero bytes, so all seven golden ROMs stay green with no rebaseline.

**Architecture:** Two new pure-comptime `.emp` modules (no `in <section>`, no registry entry, no pins
region) joined to sigil's `COMPTIME_HELPERS` list. `raster_dsl` owns the sparse-tier encoding
arithmetic — arm schedule, CRAM command splitting, `count-1`, `pal_dirty_mask` derivation, frame-top
init words — expressed as a payload-carrying `comptime enum` descriptor set folded into a flat `[u16]`
with `++`. `palette_dsl` receives `variant`/`cycle_channel` and their comptime derive model unchanged.
The runtime structs (`pal_variant`, `pal_cycle_channel`, `PalCycleScriptN`, `RasterGradientProgram`)
stay in the byte-emitting modules; only constructors and validation move. The dense tier keeps
`raster_gradient_program` — a `[u16; N]` array cannot hold a link-time symbol.

**Tech Stack:** `.emp` (sigil's source language), Rust (sigil harness, `COMPTIME_HELPERS`), Python 3
(`tools/*.py` checkers, `unittest` under `python3 -m pytest`), bash (`build.sh`, `capture_goldens.sh`).

**Spec:** `docs/superpowers/specs/2026-08-13-effects-p3-design.md` — §1 rulings are settled; §2.1, §4.1,
§4.2, §4.3, §4.4, §5.4, §6.1, §8.1 bind this parcel. **Read it before starting.**

**Handoff:** `docs/superpowers/2026-08-13-effects-p3-handoff.md`.

---

## Standing constraints — read before the first command

1. **This parcel moves ZERO bytes.** That is not a nice-to-have, it is the whole gate. If a step is
   about to relocate a `pub data`, add a `data` item, or change an emitted word, **STOP and report
   BLOCKED** — the relocation belongs to Parcel C, and A's byte-compare self-rebaselines into vacuity
   the moment A moves data (spec §2.1).
2. **Never `git add -A` or use path globs.** The auto-commit daemon holds uncommitted work under
   `games/sonic4/data/editor/` and `games/sonic4/data/sprites/`. Enumerate exact paths, then verify
   with `git show --stat HEAD`.
3. **Paired repos.** aeon and sigil change together (spec §2). Merge them as a pair and record the
   verified pair of SHAs. A sigil master coupled to an unmerged aeon branch has already made aeon
   master unbuildable once in this tree.
4. **Rebuild BOTH sigil binaries before any gate run.** A stale binary produces a green run against
   the wrong compiler.
5. **`const` does NOT enforce its declared array length — only `data` does** (spec §6.1). Every length
   guard in this parcel must sit on a `data` declaration or be an explicit `ensure` on `.len`.
6. **A comptime fn's free names resolve at the CALL SITE**, and in struct-literal position a missing
   import degrades *silently* to a label reference (spec §4.4). Constructor bodies in `raster_dsl` /
   `palette_dsl` may name **only** their own parameters, numeric literals, other `raster_dsl` /
   `palette_dsl` items, and existing `COMPTIME_HELPERS` items (`vdp_comm`, `VdpTarget`, `VdpOp`, …).
   Anything imported from `engine.effects.raster` or `engine.effects.palette` must be **inlined as a
   literal and pinned with a module-level `ensure`** — the pattern `engine/effects/raster.emp:585-597`
   established for `water_arm0`.
7. **T-1 is a DENSE-tier fact** (`raster.emp:236-243`). The sparse authorities are `raster_arm` /
   `raster_fire_line` / `water_arm0`. Applying the dense off-by-one to sparse arithmetic fails the
   byte-compare in the most confusing possible direction.
8. **Param type annotations are mandatory; most of them are not enforced.** Measured by Task 1's probe,
   recorded in `docs/superpowers/notes/2026-08-13-parcel-a-capability-probe.md`. An untyped
   `comptime fn` param is a parse error (`expected ':', found RParen`), so every param must carry an
   annotation. What the annotation buys you:
   - **No bind-time range or length check** outside `where LO..HI` refinements
     (`sigil-frontend-emp/src/eval/call.rs:309-318`). In particular **`[T; N]` on a parameter is not a
     checked length** — a 4-element list binds happily to an `[int; 3]` param. This plan therefore
     spells loose array params `array` and does its length checking with explicit `ensure`s on `.len`.
   - **`Reg` and `Label` ARE class-checked**, by exact spelling, on *explicitly supplied* args only
     (`check_arg_class`, `eval/call.rs:446-480`, called at `:545`/`:563`). Defaults skip the check —
     which is exactly why `sym: Label = 0` works as the "is it bound?" idiom. **Do not strip a `Label`
     annotation as decorative**; it is load-bearing, and removing it would destroy the mechanism §5.2's
     witness established.
9. **A glob-imported module must export at least one `pub` name**, so `raster_dsl.emp` carries a
   `pub const RASTER_DSL_PLACEHOLDER = 0` from Task 1. **Task 6 deletes it** once the module has real
   `pub` items.

---

## Environment

Set these once per shell. Every build/gate command below assumes them.

```bash
export AEON=/home/volence/sonic_hacks/aeon
export SIGILR=/home/volence/sonic_hacks/sigil
export SIGIL_BUILD=$SIGILR/target/release/sigil
export SIGIL_EMIT=$SIGILR/target/release/emit_sound_blob
export AEON_DIR=$AEON
```

**Rebuild both binaries** (do this after every sigil source change):

```bash
cd $SIGILR && cargo build --release -p sigil-cli --bin sigil \
                          -p sigil-harness --bin emit_sound_blob
```

**Aeon build** (`build.sh` hard-errors without `SIGIL_BUILD`/`SIGIL_EMIT`):

```bash
cd $AEON && ./build.sh            # release shape -> s4.bin
cd $AEON && DEBUG=1 ./build.sh    # debug shape   -> s4.debug.bin
```

---

## File Structure

| Path | Responsibility | Emits bytes? |
|---|---|---|
| `engine/effects/raster_dsl.emp` | **NEW.** Sparse-tier raster vocabulary: `RasterOp`/`RasterFire` descriptors, their constructors + validation, `raster_words`, `raster_program`. Owns the arm schedule, CRAM command split, `count-1`, mask and init derivation. | No |
| `engine/effects/palette_dsl.emp` | **NEW.** `variant`, `cycle_channel`, `cycle_script1`/`cycle_script2`, the comptime derive model (`clamp07`/`variant_channel`/`variant_word`) and its three build-time proofs. | No |
| `engine/effects/raster.emp` | Sheds the comptime authoring block. Keeps every runtime proc, the opcode consts, `RasterGradientProgram` + `raster_gradient_program` (dense tier), `RASTER_BUF_SIZE`, `RASTER_STATE_SIZE`. | Yes (unchanged) |
| `engine/effects/palette.emp` | Sheds `variant`/`cycle_channel` + the derive model. Keeps `pal_variant`, `pal_cycle_channel`, `PalCycleScriptN`, the `Code`-splice helpers, and the five starter variants at `:824-830` (**data — Parcel C moves those**). | Yes (unchanged) |
| `games/sonic4/data/parallax/configs.emp` | `OJZ_TestRaster` and `OJZ_WaterRaster` re-expressed through the DSL **in place**, each pinned word-for-word against its retained hand-authored twin. | Yes (**byte-identical**) |
| `tools/emp_helper_closure.py` + `tools/test_emp_helper_closure.py` | Enumerates each `COMPTIME_HELPERS` module's post-publicize exported closure and fails on any duplicate name across the set. Cross-checks its helper list against `native.rs`. | n/a |
| `tools/effects_budget_check.py` + `tools/test_effects_budget_check.py` | Resolves each `[symbols]`-declared `.emp` constant and fails on disagreement with the TOML row. | n/a |
| `tools/effects_budget_model.toml` | Gains a `[symbols]` table; header's generator-enforcement claim corrected; `raster_state_bytes` 286 -> 288. | n/a |
| `docs/EFFECTS_AUTHORING.md` | **NEW.** The vocabulary table — the authoring reference. | n/a |
| `sigil/crates/sigil-harness/src/native.rs` | `COMPTIME_HELPERS` gains `engine.effects.raster_dsl` and `engine.effects.palette_dsl`. | n/a |

**Not in this parcel** (spec §2.1, §3.1): moving `palette.emp:824-830`'s five starter variants; moving
`configs.emp:278-453` to `games/sonic4/data/effects/`; `preset.emp`; `EffectsPreset`; `sec_effects`;
`Preset_None`/`Pal_Cycle_None`; deleting the imperative water install; any `docs/BUGS.md` entry beyond
§10 item 5 (the TOML drift this parcel fixes).

---

## Notes on two deliberate scope decisions

**(a) `region_boundary` ships as a thin composite, not the full sketch.** Spec §4.1 sketches
`region_boundary(line:, variant:, sh:)`. Its `variant:` parameter presumes the Parcel-C preset binding
that does not exist yet, so Parcel A ships the primitives (`fire`, `set_reg`/`sh_on`, `cram`,
`pal_region`) plus a `region_boundary` whose parameters are the ones `OJZ_WaterRaster` actually needs.
Parcel D re-shapes its signature when it knows the pack. This is a deviation from a spec *sketch*, not
from a ruling — recorded here so it is not silent.

**(b) The hand-authored twins are RETAINED, not deleted.** Spec §8.1 calls the per-word
`ensure(dsl_output[i] == hand_words[i])` a development instrument. It is kept permanently, because it
is zero bytes (a `const` emits nothing) and it converts a Parcel-C/D regression from "golden ROM
differs" into "DSL diverges at word 11". The twins retire in Parcel D together with the fixtures they
pin (spec §8.2).

---

## The vocabulary table (spec §4.1) — Parcel A's opening obligation

This is the content of `docs/EFFECTS_AUTHORING.md`, written in Task 3 and the reference for Tasks 6-8.

### Sparse program wire format

```
word 0            pal_dirty_mask          DERIVED — OR of (1 << (cram_addr >> 5)) over every CRAM-class op
word 1            init_count N            DERIVED — count of distinct frame-top reset words
words 2..2+N-1    init words              DERIVED — each set_reg op's reset word, first-appearance order, deduped
                  ---- records ----
record 0          arm, 0                  priming, fires on line 0
record 1          arm, 0                  priming, fires on line 1
record 2..k+1     arm, op_count, <ops>    one per authored fire, in ascending screen-line order
record k+2        arm, RASTER_OPS_END     terminator
```

Record `i` carries the arm word for `gap(L[i+1] -> L[i+2])` where `L = [0, 1, M_1 - 1, …, M_k - 1]` and
`M_j` is the authored **screen line** the effect lands on. Past the end, the arm parks at `$8AFF`.
The fire line is `M - 1` (Ruling 1a); `arm = $8A00 | (L[i+2] - L[i+1] - 1)` (Ruling 1b). For a
single-event program at screen line `M` this reduces to `$8A00 | (M - 3)` — the same value
`water_arm0(M)` produces, which is what makes `OJZ_WaterRaster` byte-identical.

### Descriptor set

| Constructor | Parameters | Emits | `op_size` |
|---|---|---|---|
| `set_reg(word, reset)` | `word` = mid-frame `$8xxx` VDP register write; `reset` = the frame-top word restoring the **same** register | `OP_SET_REG, word` | 2 |
| `sh_on()` | none | `set_reg($8C89, $8C81)` — Shadow/Highlight on below the fire, H40 base restored at frame top (`games/sonic4/data/boot_data.emp:140`) | 2 |
| `cram(addr, colours)` | `addr` = CRAM **byte** address; `colours` = 1..3 colour words, inline | `OP_CRAM, cmd>>16, cmd&$FFFF, colours.len-1, <colours>` | `4 + colours.len` |
| `pal_region(addr, slot, pal_line, entry, count)` | `addr` = destination CRAM byte address; `slot`/`pal_line`/`entry` = the `Pal_Variant_Stage` source; `count` = 1..3 | `OP_PAL_REGION, cmd>>16, cmd&$FFFF, count-1, slot*128 + pal_line*32 + entry*2` | 5 |
| `fire(line, ops)` | `line` = screen line 3..223 the effect lands on; `ops` = descriptor array | one record: `arm, ops.len, <bodies>` | `2 + Σ op_size` |
| `region_boundary(line, addr, slot, pal_line, entry, count, sh)` | thin composite | `fire(line, [sh_on()] ++ [pal_region(…)])` when `sh == 1`, else the region alone | as above |
| `raster_words(fires)` | descriptor array | the word count, computed from `op_size` — **independently of** `raster_program`'s concatenation | — |
| `raster_program(fires)` | descriptor array | the flat `[u16]` | — |

`cmd` is `vdp_comm(addr, VdpTarget.Cram, VdpOp.Write)`. `vdp_comm` is a `COMPTIME_HELPERS` member and is
therefore glob-injected at every call site, so naming it inside a constructor body is safe.

### What each guard actually proves

| Guard | Catches | Does **not** catch |
|---|---|---|
| `data X: [u16; raster_words(P)] = raster_program(P)` | header/record **framing** drift between the two independent computations | a wrong word *value* inside a correctly-sized body |
| The retained hand-word twin + `first_mismatch` ensure | any word-value drift in the two shipped fixtures | a fixture the twin does not cover |
| Seven golden ROMs | every emitted byte, everywhere | nothing — this is the parcel's real bar |

Writing `[u16; P.len] = P` instead would be **tautological** and is forbidden: it is the
`gate-measures-the-placer` failure one layer up.

### New correctness the constructors guarantee (ruling 5)

- `set_reg`: the mid-frame word and its frame-top reset must target the **same** VDP register — so a
  mode change can never latch past the frame.
- `pal_region`: the destination CRAM address must name the **same line and entry** as the staging
  source. Hand authoring had no such check.
- `pal_dirty_mask` is derived from the CRAM addresses rather than typed. A mask naming the wrong line
  is the observed P1 bug (`configs.emp:311-315`); it is now unrepresentable.
- `raster_program`: `words * 2 <= RASTER_BUF_SIZE` (spec §10 rider 4 — `Raster_InstallWater` and
  `Raster_VBlank` both copy a fixed 128 bytes).
- Mixed fires: `OP_SET_REG` must be the **first** op (ruling 14, §5.4).

---

## Task 0: Baseline — prove the tree is green before touching it

Parcel A's gate is "goldens green **with no rebaseline**". That is only attributable if the goldens are
demonstrably green *first*.

**Files:** none (measurement only). Records land in Task 12's evidence note.

- [ ] **Step 1: Confirm the working tree and the merge state**

```bash
cd $AEON && git status --short && git log --oneline -3
```

Expected: branch `master`; the only modifications are under `games/sonic4/data/editor/` and
`games/sonic4/data/sprites/` (the auto-commit daemon's). `b7b0f299` (the character lens-sweep merge)
is in the log — spec §"Standing hazard" item 2 is therefore **satisfied**; the character work has
landed and a golden diff during this parcel is attributable.

- [ ] **Step 2: Build both sigil binaries**

```bash
cd $SIGILR && cargo build --release -p sigil-cli --bin sigil \
                          -p sigil-harness --bin emit_sound_blob
```

Expected: `Finished \`release\` profile`.

- [ ] **Step 3: Chain check**

```bash
cd $SIGILR && cargo run -q --release -p sigil-harness --bin refreeze -- --check
```

Expected exactly: `refreeze --check: OK (tip \`character-lens-sweep-postmerge\`, chain len 111)`.

**This is NOT the goldens** — `--check` has gone green with golden ROM tests red before. Step 4 is the
real bar.

- [ ] **Step 4: Fresh-build all seven goldens, read-only**

```bash
cd $SIGILR && crates/sigil-harness/golden/capture_goldens.sh
```

No `--write`. Expected: one `full … / … anchor … / …` line per target, then
`>> restoring canonical aeon s4.bin + s4.debug.bin`. **Record all seven pairs** — these are the numbers
Task 11 must reproduce exactly. The chain tip they must match is at the tail of
`crates/sigil-harness/golden/provenance.toml`: `s4 fedcf197/696836 anchor 202f705f/0xa11f0`,
`s4_debug 3dc20e2c/711298`, `config_a 8cb75de6/711666`, `config_b b860aab0/598846`,
`demo d5ea5776/95615`, `demo_debug 321ad9c6/99783`, `lean 1602cde3/655726`.

- [ ] **Step 5: The seven as in-suite byte gates**

`SIGIL_STRICT_GATE=1` is **mandatory** — without it a missing aeon tree makes these skip *green*.

```bash
cd $SIGILR && SIGIL_STRICT_GATE=1 cargo test --release -p sigil-cli \
    --test native_full_rom --test native_offcanonical_full \
    --test native_offcanonical_rom --test native_rom > /tmp/t0-byte.out 2> /tmp/t0-byte.err
grep -E "^test result" /tmp/t0-byte.out
```

Expected: every `test result:` line reports `0 failed`.

- [ ] **Step 6: Full sigil suite (the port-flip baseline)**

Foreground only, streams separated, never piped through `head`/`tail` (it truncates and returns the
wrong exit code). Raise the tool timeout to 600000 ms.

```bash
cd $SIGILR && SIGIL_STRICT_GATE=1 cargo test --workspace --release --no-fail-fast \
    > /tmp/t0-full.out 2> /tmp/t0-full.err
grep -E "^test result" /tmp/t0-full.out | awk '{p+=$4; f+=$6; i+=$8} END {print "passed",p,"failed",f,"ignored",i}'
```

Expected: `passed 3672 failed 0 ignored 4`. The four ignored are the standing set
(`native_chained_resume.rs:143,163`, `repin_pins.rs:714`, `subcommands.rs:11`).

**Note:** `repin.toml:359-367` declares `tests = ["palette_port"]` but **`palette_port.rs` and
`raster_port.rs` do not exist as test binaries** — `tests = [...]` is a rerun *hint*, not a validated
reference. Parcel A adds no byte-emitting module and therefore no `repin.toml` region, so the port-flip
ritual for this parcel **is** this whole-workspace run. Do not try `--test palette_port`; it fails with
"no test target named".

- [ ] **Step 7: Aeon python suite**

```bash
cd $AEON && python3 -m pytest -q > /tmp/t0-py.out 2>&1; tail -3 /tmp/t0-py.out
```

Expected: `944 passed, 2 skipped`. The 2 skips are `test_s4lint.py` looking for the deleted `main.asm`.

- [ ] **Step 8: Record the replay-net state (NOT this parcel's gate)**

```bash
cd $AEON && git log --oneline -1 dbbb6afc && git show --stat dbbb6afc | head -20
```

`dbbb6afc` books an `ojz_fixture` re-stamp owed by the lens-sweep merge — i.e. spec §"Standing hazard"
item 1 has materialized. **Parcel A does not depend on the replay net** (its gate is the goldens), but
**Parcel C's does**. Record the state so C is not surprised; do not fix it here.

- [ ] **Step 9: Create the paired worktrees**

```bash
cd $AEON   && git worktree add .worktrees/p3a -b feat/effects-p3-parcel-a master
cd $SIGILR && git worktree add .worktrees/p3a -b feat/effects-p3-parcel-a master
```

Then re-point the environment at the worktrees and rebuild:

```bash
export AEON=/home/volence/sonic_hacks/aeon/.worktrees/p3a
export AEON_DIR=$AEON
export SIGILR=/home/volence/sonic_hacks/sigil/.worktrees/p3a
export SIGIL_BUILD=$SIGILR/target/release/sigil
export SIGIL_EMIT=$SIGILR/target/release/emit_sound_blob
cd $SIGILR && cargo build --release -p sigil-cli --bin sigil -p sigil-harness --bin emit_sound_blob
```

The sigil crate registry is global across worktrees; a second concurrent agent building sigil will
contend. If another session is active in sigil, **STOP and report BLOCKED**.

- [ ] **Step 10: Prove the baseline reproduces from the worktrees**

```bash
cd $SIGILR && crates/sigil-harness/golden/capture_goldens.sh 2>&1 | grep -E "^   full|^>> "
```

Expected: the same seven pairs as Step 4. If they differ, the worktree build is not equivalent to
master's — **STOP and report BLOCKED** (there is a recorded, unresolved worktree-build oddity in this
tree; do not paper over it).

---

## Task 1: Capability probe — de-risk the constructs the vocabulary depends on

The vocabulary needs payload-carrying `comptime enum`s, `match`, ragged nested arrays, empty array
literals, `++` accumulation across nested `for` loops, and `.len`. Every one of those is supported by
the sigil evaluator, but **payload enums have zero existing usage anywhere in aeon**. This codebase has
been bitten by vacuous probes before (spec §6.1). Ten minutes here saves the parcel.

**Files:**
- Create (temporarily): `engine/effects/raster_dsl.emp`

- [ ] **Step 1: Write the probe module**

```
// engine/effects/raster_dsl.emp — CAPABILITY PROBE (temporary content, replaced in Task 6).
module engine.effects.raster_dsl

comptime enum ProbeOp { A(int, int), B(int, int), C }

comptime fn probe_words(o: ProbeOp) {
    return match o {
        A(x, y) => [x, y],
        B(x, ys) => [x, ys.len] ++ ys,
        C        => [],
    }
}

comptime fn probe_size(o: ProbeOp) -> int {
    return match o {
        A(x, y)  => 2,
        B(x, ys) => 2 + ys.len,
        C        => 0,
    }
}

comptime fn probe_build(ops) {
    comptime var out = []
    for o in ops {
        out = out ++ probe_words(o)
    }
    return out
}

comptime fn probe_count(ops) -> int {
    comptime var n = 0
    for o in ops {
        n = n + probe_size(o)
    }
    return n
}

const PROBE_OPS = [ ProbeOp.A(1, 2), ProbeOp.B(3, [4, 5, 6]), ProbeOp.C ]
const PROBE_OUT = probe_build(PROBE_OPS)

// 1. accumulation across a nested `for` + `++` reaches the fn-level `comptime var`
ensure(PROBE_OUT.len == 7, "PROBE 1: expected 7 words, got {PROBE_OUT.len}")
// 2. the flattened value is right, element by element
ensure(PROBE_OUT[0] == 1 && PROBE_OUT[1] == 2 && PROBE_OUT[2] == 3 && PROBE_OUT[3] == 3,
       "PROBE 2: flatten order wrong")
ensure(PROBE_OUT[4] == 4 && PROBE_OUT[5] == 5 && PROBE_OUT[6] == 6, "PROBE 2b: tail wrong")
// 3. the INDEPENDENT count path agrees with the concatenation path
ensure(probe_count(PROBE_OPS) == PROBE_OUT.len,
       "PROBE 3: size path {probe_count(PROBE_OPS)} != build path {PROBE_OUT.len}")
// 4. a `Label` param defaulted to 0 compares against 0 as the "is it bound?" idiom (spec §5.2).
//    INTENT: `Value::Label` vs `Value::Int` is a VARIANT MISMATCH in values_equal's `_ => a == b`
//    arm, not a designed predicate. If sigil ever diagnoses cross-class comparison this ensure
//    inverts SILENTLY to always-pass, which is why the negative half exists below.
comptime fn probe_label_unbound(sym: Label = 0) -> int {
    if sym != 0 { return 1 }
    return 0
}
ensure(probe_label_unbound() == 0, "PROBE 4: an unbound Label default must compare EQUAL to 0")
```

- [ ] **Step 2: Register the probe so it is actually evaluated**

A pure-comptime module is only walked if something imports it. Add the import to
`games/sonic4/data/parallax/configs.emp`, immediately after the existing
`use engine.effects.palette.{cycle_channel, pal_cycle_channel, PalCycleScript1}` line (`:33`):

```
use engine.effects.raster_dsl.*
```

- [ ] **Step 3: Build and verify the probe passes**

```bash
cd $AEON && ./build.sh 2>&1 | tail -20
```

Expected: a successful build, and the printed `crc=`/`len=` **identical to Task 0 Step 4's `s4`
values** — the probe emits zero bytes. If any `ensure` fires, the vocabulary design in Task 6 must
change; **STOP and report which probe number failed** rather than working around it.

- [ ] **Step 4: Negative probe — prove the ensures can actually fail**

Temporarily change PROBE 1 to `PROBE_OUT.len == 8` and rebuild.

```bash
cd $AEON && ./build.sh 2>&1 | grep -i "PROBE 1"
```

Expected: `PROBE 1: expected 7 words, got 7`. **This step is not optional** — an `ensure` that cannot
fail is the exact failure mode §6.1 was written about. Revert to `== 7` afterwards and rebuild to
confirm green.

- [ ] **Step 5: Negative probe for the Label witness**

Temporarily add, after PROBE 4:

```
comptime fn probe_label_bound(sym: Label = 0) -> int {
    if sym != 0 { return 1 }
    return 0
}
ensure(probe_label_bound(sym: OJZ_TestPal) == 0, "PROBE 5 NEGATIVE: a BOUND Label must NOT equal 0")
```

Build. Expected: **PROBE 5 fires** (`a BOUND Label must NOT equal 0`), proving the comparison
distinguishes bound from unbound. Then delete PROBE 5's four lines and rebuild green.

Do **not** write `probe_label_bound(sym: 0)` — an explicitly-supplied `0` for a `Label` param is a hard
error (`expected a label (a \`Label\` argument), got int`); only the *default* path skips the class check.

- [ ] **Step 6: Commit the probe result as a note, then strip the probe**

Record the outcome in `docs/superpowers/notes/2026-08-13-parcel-a-capability-probe.md`: which of the
five probes passed, the exact negative-probe messages from Steps 4 and 5, and the unchanged `crc`/`len`.
This is the §5.2 `Label != 0` witness the spec still owed — it is now paid.

Leave `raster_dsl.emp` in place with only the probe module header for now (Task 6 fills it); delete the
`ProbeOp`/`probe_*` bodies once its note is written.

```bash
cd $AEON && git add docs/superpowers/notes/2026-08-13-parcel-a-capability-probe.md \
                    engine/effects/raster_dsl.emp \
                    games/sonic4/data/parallax/configs.emp
cd $AEON && git commit -m "probe(effects): confirm payload enums, ++ accumulation, and the Label != 0 witness

Pays the two toolchain debts spec 6.1/5.2 left owed. Five probes, two with
negative controls: an ensure that cannot fail is the failure mode this parcel
is guarding against."
cd $AEON && git show --stat HEAD
```

Verify the stat lists exactly those three paths and nothing under `data/editor/`.

---

## Task 2: The helper-closure collision tool

> **SHIPPED — `912c00d7` + `de116cdd`. The drafted code below is superseded; read the shipped
> `tools/emp_helper_closure.py` instead.** Four defects in the draft, two of which made the gate
> worthless:
> - **`module_path()`'s dots-to-slashes mapping is WRONG.** Module ids are not paths —
>   `engine.types` lives at `engine/system/types.emp`, `engine.constants` at
>   `engine/system/constants.emp`. Two of twelve helpers failed to resolve, so the drafted gate
>   returned rc=2 and never checked anything. The shipped tool builds a `module_index()` by reading
>   the `module` declaration out of all 143 `.emp` files. **Any later task needing a module-id ->
>   path mapping must use that, not string substitution.**
> - **`pub context` was missing from the item set.** `pub_comptime_name`
>   (`sigil-frontend-emp/src/resolve/mod.rs:23-50`) injects `Context(d) if d.public`; the tree has
>   `ints_off`/`vblank` (`engine/irq.emp`) and `z80_stopped` (`engine/z80_bus.emp`), so those two
>   helpers were reporting the EMPTY SET.
> - `vars` must match only the overlay form (`name.is_some()`), and `pub data X: <bare Named>` is
>   injected as a type stub by `pub_struct_data_name`. Correct, but inert on the current helper set.
> - `.emp` has non-nesting `/* */` block comments (`lexer.rs:117`), so line-comment stripping is
>   insufficient; item position is depth 0 or depth 1 inside a `section` body. **Not inert:**
>   `implement` blocks (`games/*/config/game.emp`) bind contract values with depth-1 `const` lines,
>   and `Item::Implement` is not `Item::Section` — sigil never recurses into it, so a depth-blind
>   scanner reads those two files exactly backwards.
>
> Reading: **394 names across 12 helpers, no collisions.** 22 tests, mutation-tested (the reviewer
> found the item-position gate initially had no failing test; it does now). Full suite 944 -> 966.

`publicize_helper_comptime` (`native.rs:1134-1155`) force-publicizes every **private** comptime item of
a helper module, and `normalize_helper_imports` (`:1077-1126`) injects one glob per helper **in list
order** so between two helpers the later wins silently. The moment `palette_dsl` joins the list,
`palette.emp`'s private `clamp07` becomes a globally-injected name. The one way that changes bytes is a
name currently unresolved (degrading to a label reference) that starts resolving to an injected const.

This tool must exist and run **before** the `COMPTIME_HELPERS` edit, so a green golden is not mistaken
for absence of collision (spec §4.4).

**Files:**
- Create: `tools/emp_helper_closure.py`
- Test: `tools/test_emp_helper_closure.py`

- [ ] **Step 1: Write the failing test**

```python
#!/usr/bin/env python3
"""Tests for emp_helper_closure — the COMPTIME_HELPERS name-collision gate."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emp_helper_closure import (
    comptime_items, helper_ids_from_native, find_collisions, main as closure_main,
)

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIGIL_NATIVE = os.path.join(
    os.path.dirname(AEON), "sigil", "crates", "sigil-harness", "src", "native.rs"
)

SAMPLE = """\
// a comment mentioning const NOT_AN_ITEM = 1
module engine.fake.dsl

use engine.structs.{Sec}

pub const ALPHA = 3
const BETA = $10
pub comptime fn gamma(x: int) -> int { return x }
comptime fn delta() -> int { return 1 }
pub struct Epsilon { e_a: u16 }
comptime enum Zeta { One, Two }
pub comptime enum Eta { A(int) }
bitfield Theta : u8 { b0: 1 }
newtype Iota = u16
pub vars Kappa { k: u16 }
pub proc NotAnItem () clobbers() { rts }
pub data NotThisEither: [u16; 1] = [0]
ensure(1 == 1, "not an item")
"""


class TestComptimeItems(unittest.TestCase):
    def test_extracts_every_comptime_kind_public_and_private(self):
        with tempfile.NamedTemporaryFile("w", suffix=".emp", delete=False) as f:
            f.write(SAMPLE)
            path = f.name
        try:
            names = comptime_items(path)
        finally:
            os.unlink(path)
        self.assertEqual(
            names,
            {"ALPHA", "BETA", "gamma", "delta", "Epsilon", "Zeta",
             "Eta", "Theta", "Iota", "Kappa"},
        )

    def test_excludes_procs_data_ensures_and_comments(self):
        with tempfile.NamedTemporaryFile("w", suffix=".emp", delete=False) as f:
            f.write(SAMPLE)
            path = f.name
        try:
            names = comptime_items(path)
        finally:
            os.unlink(path)
        for excluded in ("NotAnItem", "NotThisEither", "NOT_AN_ITEM"):
            self.assertNotIn(excluded, names)


class TestHelperList(unittest.TestCase):
    def test_helper_ids_parsed_from_native_rs(self):
        ids = helper_ids_from_native(SIGIL_NATIVE)
        self.assertIn("engine.vdp", ids)
        self.assertIn("engine.level.parallax_dsl", ids)
        self.assertGreaterEqual(len(ids), 12)


class TestCollisions(unittest.TestCase):
    def test_reports_a_duplicate_across_two_helpers(self):
        found = find_collisions({"a.one": {"X", "Y"}, "b.two": {"Y", "Z"}})
        self.assertEqual(found, [("Y", ["a.one", "b.two"])])

    def test_clean_set_reports_nothing(self):
        self.assertEqual(find_collisions({"a.one": {"X"}, "b.two": {"Y"}}), [])


class TestLiveTree(unittest.TestCase):
    def test_the_shipped_helper_set_is_collision_free(self):
        """The live gate. Fails the suite the moment a helper shadows another."""
        rc = closure_main([AEON, SIGIL_NATIVE])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it and verify it fails**

```bash
cd $AEON && python3 -m pytest tools/test_emp_helper_closure.py -q 2>&1 | tail -5
```

Expected: collection error, `ModuleNotFoundError: No module named 'emp_helper_closure'`.

- [ ] **Step 3: Write the tool**

```python
#!/usr/bin/env python3
"""
emp_helper_closure — the COMPTIME_HELPERS name-collision gate.

sigil force-publicizes every PRIVATE comptime item of a COMPTIME_HELPERS module
(native.rs publicize_helper_comptime) and then injects one `use <helper>.*` glob per
helper into EVERY module, in list order (normalize_helper_imports). Between two
helpers the later silently wins. A name that is currently unresolved in some module —
degrading to a label reference — would start resolving to an injected const, which is
the one way helper membership changes emitted bytes.

So the exported closures must be pairwise disjoint. This checks that.

Usage:
    python3 tools/emp_helper_closure.py [AEON_DIR] [NATIVE_RS]
"""

from __future__ import annotations

import os
import re
import sys
from typing import Dict, List, Set, Tuple

# One `const`/`comptime fn`/`struct`/... declaration, with the optional `pub` and the
# optional `comptime` qualifier. Anchored at line start so a mention inside a comment
# or a string never matches.
ITEM_RE = re.compile(
    r"^\s*(?:pub\s+)?(?:comptime\s+)?"
    r"(const|fn|struct|enum|bitfield|newtype|vars)\s+"
    r"([A-Za-z_][A-Za-z0-9_]*)",
)

# `comptime fn` is an item; a bare `fn` is not a thing in .emp, but `proc`/`data`
# certainly are and must never match — they are excluded by the alternation above.
COMMENT_RE = re.compile(r"^\s*//")

HELPERS_RE = re.compile(
    r"const\s+COMPTIME_HELPERS\s*:\s*&\[&str\]\s*=\s*&\[(.*?)\];", re.DOTALL
)


def comptime_items(path: str) -> Set[str]:
    """Every comptime item name a module would export after force-publicization."""
    names: Set[str] = set()
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            if COMMENT_RE.match(line):
                continue
            m = ITEM_RE.match(line)
            if m:
                names.add(m.group(2))
    return names


def helper_ids_from_native(native_rs: str) -> List[str]:
    """The COMPTIME_HELPERS list, read from sigil rather than duplicated here."""
    with open(native_rs, "r", encoding="utf-8") as fh:
        src = fh.read()
    m = HELPERS_RE.search(src)
    if not m:
        raise SystemExit(f"{native_rs}: could not find `const COMPTIME_HELPERS`")
    return re.findall(r'"([a-z0-9_.]+)"', m.group(1))


def module_path(aeon: str, module_id: str) -> str:
    """`engine.level.parallax_dsl` -> `<aeon>/engine/level/parallax_dsl.emp`."""
    return os.path.join(aeon, *module_id.split(".")) + ".emp"


def find_collisions(closures: Dict[str, Set[str]]) -> List[Tuple[str, List[str]]]:
    """Names exported by more than one helper, sorted for a stable report."""
    owners: Dict[str, List[str]] = {}
    for mod in sorted(closures):
        for name in closures[mod]:
            owners.setdefault(name, []).append(mod)
    return sorted((n, m) for n, m in owners.items() if len(m) > 1)


def main(argv: List[str]) -> int:
    aeon = argv[0] if argv else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    native_rs = (
        argv[1]
        if len(argv) > 1
        else os.path.join(
            os.path.dirname(aeon), "sigil", "crates", "sigil-harness", "src", "native.rs"
        )
    )
    helpers = helper_ids_from_native(native_rs)
    closures: Dict[str, Set[str]] = {}
    missing: List[str] = []
    for mod in helpers:
        path = module_path(aeon, mod)
        if not os.path.exists(path):
            missing.append(f"{mod} -> {path}")
            continue
        closures[mod] = comptime_items(path)
    if missing:
        print("COMPTIME_HELPERS names a module with no .emp file:")
        for row in missing:
            print(f"  {row}")
        return 2
    collisions = find_collisions(closures)
    if collisions:
        print(f"{len(collisions)} name collision(s) across {len(helpers)} helpers:")
        for name, mods in collisions:
            print(f"  {name}: {', '.join(mods)}")
        return 1
    total = sum(len(v) for v in closures.values())
    print(f"emp_helper_closure: OK — {total} names across {len(helpers)} helpers, no collisions")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run the tests and verify they pass**

```bash
cd $AEON && python3 -m pytest tools/test_emp_helper_closure.py -q 2>&1 | tail -5
```

Expected: `6 passed`. If `test_the_shipped_helper_set_is_collision_free` fails on the **current**
twelve helpers, that is a pre-existing defect — record it in `docs/BUGS.md` and report it; do not
"fix" it by loosening the tool.

- [ ] **Step 5: Run the tool by hand and read the number**

```bash
cd $AEON && python3 tools/emp_helper_closure.py
```

Expected: `emp_helper_closure: OK — <N> names across 12 helpers, no collisions`. Record `N`; Task 5
compares against it.

- [ ] **Step 6: Commit**

```bash
cd $AEON && git add tools/emp_helper_closure.py tools/test_emp_helper_closure.py
cd $AEON && git commit -m "test(effects): gate COMPTIME_HELPERS against name collisions

publicize_helper_comptime force-publicizes a helper's PRIVATE comptime items and
normalize_helper_imports lets the later helper win silently. The one way helper
membership changes bytes is a name that was degrading to a label reference
starting to resolve. Runs on the live tree from pytest, and reads the helper list
out of native.rs rather than duplicating it."
cd $AEON && git show --stat HEAD
```

---

## Task 3: The vocabulary reference doc

Spec §4.1: "The plan must open Parcel A with a vocabulary table." Tasks 6-8 are written against it, so
it lands before the code.

**Files:**
- Create: `docs/EFFECTS_AUTHORING.md`

- [ ] **Step 1: Write the doc**

Copy the whole "**The vocabulary table (spec §4.1)**" section of this plan — wire format, the
record/arm schedule with the `L` derivation, the descriptor table, the "what each guard actually
proves" table (including the `[u16; P.len]` prohibition and its reason), and the "new correctness the
constructors guarantee" list. Add at the top:

- a one-paragraph statement of what the DSL is for (an author adds a water section without typing a
  VDP register word, an arm word, or a CRAM command);
- the **scope exclusion** from spec §4.1: a program mixing sparse events with a dense run is **not
  authorable in Phase 3** — the wire format permits it (`raster.emp:495-508`), neither constructor can
  author it, and a section takes one tier or the other;
- the pointer that the dense tier keeps `raster_gradient_program` (`raster.emp:258-286`), because a
  `[u16; N]` array cannot hold a link-time symbol;
- the §4.4 discipline rule, stated as a rule for anyone adding a constructor: *a constructor's returned
  value may name only its own parameters, numeric literals, its own module's items, and
  `COMPTIME_HELPERS` items; anything else is inlined and pinned with a module-level `ensure`.*

- [ ] **Step 2: Commit**

```bash
cd $AEON && git add docs/EFFECTS_AUTHORING.md
cd $AEON && git commit -m "docs(effects): the Phase-3 raster/palette authoring vocabulary

The table Tasks 6-8 are written against: wire format, arm schedule, descriptor
set, and what each guard actually proves (the length annotation catches framing
drift, not word-value drift - the goldens are the real bar)."
```

---

## Task 4: `palette_dsl.emp` — move the palette constructors

A pure move plus one wart fix. Byte-neutral by construction: `variant()` and `cycle_channel()` already
carry their `ensure` validation and a comptime model of the runtime derive whose proofs verify known
colours through known variants (`palette.emp:145-172`).

**What moves:** `variant` (`palette.emp:123-137`), `clamp07` (`:147-151`), `variant_channel` (`:152-154`),
`variant_word` (`:156-162`), the three proof `ensure`s (`:165-172`), `cycle_channel` (`:196-204`).

**What stays in `palette.emp`:** `pal_variant` (`:115-121`), `pal_cycle_channel` (`:186-193`),
`PalCycleScript1`/`PalCycleScript2` (`:209-210`), `clamp_d1_07` and `step_d3_toward_d4` (the `Code`
splices — they operate on live registers and belong with the runtime), every `pub const`, every proc,
and the five starter variants at `:824-830` (**data — Parcel C moves those, not A**).

**Files:**
- Create: `engine/effects/palette_dsl.emp`
- Modify: `engine/effects/palette.emp` (delete the moved block, add the `use`)
- Modify: `games/sonic4/data/parallax/configs.emp:33` (import source for `cycle_channel`)

- [ ] **Step 1: Create the module**

```
// engine/effects/palette_dsl.emp — the Phase-3 palette authoring vocabulary.
//
// The constructors and validation half of engine.effects.palette: variant(),
// cycle_channel(), the cycle-script wrappers, and the comptime model of the runtime
// derive with its build-time proofs. Pure comptime — this module emits no ROM bytes;
// it is glob-imported into every module (the native comptime-helper set).
//
// The wire-format STRUCTS deliberately stay in engine.effects.palette: they are read
// by runtime code, so moving them here would invert the dependency (design spec 3.1).
// A call site therefore needs `pal_variant` / `pal_cycle_channel` / `PalCycleScriptN`
// in scope — a comptime fn's struct-literal field values resolve at the EMISSION
// site's scope, not this one.
module engine.effects.palette_dsl

// Bound-pinning only: these names are used by the module-level ensures below, never
// inside a constructor body (a body's free names resolve at the CALL site).
use engine.effects.palette.{PAL_MAX_VARIANTS, PAL_CYCLE_MAX_CHANNELS, pal_variant, pal_cycle_channel}

// ===========================================================================
// VARIANTS — authorable per-channel transforms
//
// A variant is a cheap transform of the live composed palette, so it never goes
// stale under cycling or cross-fade: per channel, clamp((c >> shift) + bias).
// Genesis colour word is 0000 BBB0 GGG0 RRR0 — 3 bits per channel — so shift is
// 0..3 and bias -7..+7; both validated at build time, not runtime.
// ===========================================================================

pub comptime fn variant(shift_r: int = 0, bias_r: int = 0,
                        shift_g: int = 0, bias_g: int = 0,
                        shift_b: int = 0, bias_b: int = 0,
                        lines: int = %1110) -> pal_variant {
    ensure(shift_r >= 0 && shift_r <= 3, "variant: shift_r {shift_r} outside 0..3 (3-bit channel)")
    ensure(shift_g >= 0 && shift_g <= 3, "variant: shift_g {shift_g} outside 0..3")
    ensure(shift_b >= 0 && shift_b <= 3, "variant: shift_b {shift_b} outside 0..3")
    ensure(bias_r >= -7 && bias_r <= 7,  "variant: bias_r {bias_r} outside -7..+7")
    ensure(bias_g >= -7 && bias_g <= 7,  "variant: bias_g {bias_g} outside -7..+7")
    ensure(bias_b >= -7 && bias_b <= 7,  "variant: bias_b {bias_b} outside -7..+7")
    // bit 0 (character line) must never be selected — the derive would read/write it.
    ensure((lines & %1) == 0, "variant: lines mask {lines} selects line 0 (the character's) — use bits 1-3")
    ensure((lines & %1110) != 0, "variant: lines mask {lines} selects no level line (bits 1-3)")
    return pal_variant{ v_shift_r: shift_r, v_bias_r: bias_r,
                        v_shift_g: shift_g, v_bias_g: bias_g,
                        v_shift_b: shift_b, v_bias_b: bias_b,
                        v_lines: lines, v_pad: 0 }
}

// ---- comptime model of the runtime derive, and the build-time proof of the
//      packing. `variant_channel` and `variant_word` are the intended semantics;
//      the asm in Palette_DeriveVariant must match them, and the ensures below
//      assert known colours through known variants so the shift/clamp/repack is
//      proven at build time. This model-plus-proof pattern is the standard the
//      raster DSL is held to as well (design spec 4.2). ----
comptime fn clamp07(x: int) -> int {
    if x < 0 { return 0 }
    if x > 7 { return 7 }
    return x
}
comptime fn variant_channel(chan3: int, shift: int, bias: int) -> int {
    return clamp07((chan3 >> shift) + bias)
}
// c is a full 12-bit colour word 0000 BBB0 GGG0 RRR0.
comptime fn variant_word(c: int, v: pal_variant) -> int {
    let r = variant_channel((c >> 1) & 7, v.v_shift_r, v.v_bias_r)
    let g = variant_channel((c >> 5) & 7, v.v_shift_g, v.v_bias_g)
    let b = variant_channel((c >> 9) & 7, v.v_shift_b, v.v_bias_b)
    return (b << 9) | (g << 5) | (r << 1)
}

// Build-time proof: mid-grey $0888 (R=G=B=4) through "halve R and G, keep B"
//   R: 4>>1=2  G: 4>>1=2  B: 4>>0=4  -> $0844
ensure(variant_word($0888, variant(shift_r: 1, shift_g: 1)) == $0844,
       "Palette_DeriveVariant packing model drifted — the halve-RG test vector no longer packs to $0844")
// Bias + clamp proof: $000E (R=7) through "R>>0 +3" clamps to 7 (10 -> 7): stays $000E
ensure(variant_word($000E, variant(bias_r: 3)) == $000E,
       "variant bias clamp model drifted — R=7 +3 must clamp to 7, not overflow into G")
// Negative-bias-to-zero proof: $000E (R=7) through "R>>2 -3" = clamp(1-3)=0 -> $0000
ensure(variant_word($000E, variant(shift_r: 2, bias_r: -3)) == $0000,
       "variant negative-bias model drifted — clamp floor must be 0")

// ===========================================================================
// CYCLING — sec_pal_cycle script authoring
// ===========================================================================

pub comptime fn cycle_channel(line: int, first: int, count: int, period: int, dir: int = 0) -> pal_cycle_channel {
    ensure(line >= 1 && line <= 3,        "cycle_channel: line {line} outside 1..3 (line 0 is the character's)")
    ensure(first >= 0 && first <= 15,     "cycle_channel: first {first} outside 0..15")
    ensure(count >= 2 && first + count <= 16, "cycle_channel: span first+count {first}+{count} exceeds line's 16 entries")
    ensure(period >= 1 && period <= 255,  "cycle_channel: period {period} outside 1..255")
    ensure(dir == 0 || dir == 1,          "cycle_channel: dir {dir} must be 0 (fwd) or 1 (rev)")
    return pal_cycle_channel{ pc_line: line, pc_first: first, pc_count: count,
                              pc_period: period, pc_dir: dir, pc_pad: 0 }
}

// ---- script wrappers: the channel count is DERIVED, not typed ----------------
// The wart these fix: the count used to be spelled three times for one number — in
// the type name (PalCycleScript1), in the struct's array length, and again by the
// author as `pcs_count: 1`. The wrapper derives the header word from the array, so
// only the type name and the constructor name still carry the number, and a mismatch
// between them is a build error instead of a runtime walk off the end of the script.
//
// The literal 4 is PAL_CYCLE_MAX_CHANNELS, INLINED on purpose: a body's free names
// resolve at the CALL site, and a caller naming neither constant would otherwise get
// `unknown name`. The module-level ensure below is the single source of truth.
pub comptime fn cycle_script1(chs: array) -> PalCycleScript1 {
    ensure(chs.len == 1, "cycle_script1: {chs.len} channels — use cycle_script{chs.len}")
    return PalCycleScript1{ pcs_count: 1, pcs_ch: chs }
}
pub comptime fn cycle_script2(chs: array) -> PalCycleScript2 {
    ensure(chs.len == 2, "cycle_script2: {chs.len} channels — use cycle_script{chs.len}")
    return PalCycleScript2{ pcs_count: 2, pcs_ch: chs }
}
ensure(PAL_CYCLE_MAX_CHANNELS == 4,
       "palette_dsl ships wrappers up to 2 channels against a PAL_CYCLE_MAX_CHANNELS of {PAL_CYCLE_MAX_CHANNELS} — add cycle_script4 if a script needs it")

// variant()'s `lines` default and pal_region's slot bound both assume 2 variant slots.
// PAL_MAX_VARIANTS cannot be raised past 2 without a fix first: palette.emp's
// `andi.w #(PAL_MAX_VARIANTS - 1), d0` is a power-of-two mask, so 3 would silently
// fold slot 2 onto slot 0.
ensure(PAL_MAX_VARIANTS == 2,
       "PAL_MAX_VARIANTS is {PAL_MAX_VARIANTS} — the power-of-two mask in Palette_SetVariant must be fixed first")
```

- [ ] **Step 2: Delete the moved block from `palette.emp` and add the import**

Delete `palette.emp:123-137` (`variant`), `:145-172` (the model + three proofs) and `:196-204`
(`cycle_channel`). Keep the section banner comments that describe the *structs* that remain. Then add,
after `use engine.structs.{Sec}` (`:12`):

```
// The constructors + validation live in the DSL; the wire-format structs below stay
// here because runtime code reads them. Ambient injection makes this `use` redundant
// at build time (normalize_helper_imports strips it), but it documents the seam —
// the same convention `use engine.structs.{Sec}` above follows.
use engine.effects.palette_dsl.{variant, cycle_channel}
```

`variant()` is still called by the five starter variants at `:824-830`; those call sites need
`pal_variant` in scope, which `palette.emp` defines. No other change.

- [ ] **Step 3: Re-point `configs.emp`'s cycle import**

`games/sonic4/data/parallax/configs.emp:33` currently reads:

```
use engine.effects.palette.{cycle_channel, pal_cycle_channel, PalCycleScript1}
```

Replace with:

```
use engine.effects.palette.{pal_cycle_channel, PalCycleScript1}
use engine.effects.palette_dsl.{cycle_channel, cycle_script1}
```

- [ ] **Step 4: Adopt `cycle_script1` at the one call site**

`configs.emp:352-355` currently reads:

```
pub data OJZ_ShimmerCycle: PalCycleScript1 = PalCycleScript1{
    pcs_count: 1,
    pcs_ch: [ cycle_channel(line: 2, first: 8, count: 4, period: 8) ],
}
```

Replace with:

```
pub data OJZ_ShimmerCycle: PalCycleScript1 = cycle_script1(
    [ cycle_channel(line: 2, first: 8, count: 4, period: 8) ])
```

- [ ] **Step 5: Build both shapes and confirm byte-identity**

```bash
cd $AEON && ./build.sh 2>&1 | tail -6 && DEBUG=1 ./build.sh 2>&1 | tail -6
```

Expected: both succeed, and the printed `crc=`/`len=` match Task 0 Step 4's `s4` and `s4_debug` values
**exactly**. A move of comptime-only items emits zero bytes; a mismatch here means something real moved
— **STOP and report BLOCKED** rather than rebaselining.

- [ ] **Step 6: Commit**

```bash
cd $AEON && git add engine/effects/palette_dsl.emp engine/effects/palette.emp \
                    games/sonic4/data/parallax/configs.emp
cd $AEON && git commit -m "refactor(effects): split the palette authoring vocabulary into palette_dsl

Constructors and validation move; the wire-format structs stay with the runtime
that reads them, so the dependency does not invert. cycle_script1/2 derive the
header word from the channel array - the count used to be spelled three times
for one number. Zero bytes moved: both shapes byte-identical."
cd $AEON && git show --stat HEAD
```

---

## Task 5: Join both DSLs to `COMPTIME_HELPERS` (the paired sigil change)

This is why Parcel A is a paired parcel (spec §2, §4.4). `raster_dsl.emp` exists from Task 1 with an
empty body; adding it now means Task 6 can author constructor bodies that name `raster_dsl`'s own items
freely.

**Files:**
- Modify: `$SIGILR/crates/sigil-harness/src/native.rs:1733-1746`

- [ ] **Step 1: Run the collision tool BEFORE the edit and record the number**

```bash
cd $AEON && python3 tools/emp_helper_closure.py
```

Expected: `OK — <N> names across 12 helpers`. This is the "before" reading.

- [ ] **Step 2: Add both modules to the helper list**

In `$SIGILR/crates/sigil-harness/src/native.rs`, extend `COMPTIME_HELPERS`:

```rust
        "engine.z80_bus",
        "engine.level.parallax_dsl",
        // Effects Phase 3 (Parcel A): the raster + palette authoring vocabularies.
        // Pure comptime, no `in <section>`, so neither takes a registry entry, a pins
        // region, a `map.toml` slot, nor frozen-table rows — see the doc comment above.
        // Order matters: `normalize_helper_imports` prepends one glob per helper in
        // LIST order and the later helper silently wins a duplicate name, which is why
        // `tools/emp_helper_closure.py` gates the set for disjointness.
        "engine.effects.palette_dsl",
        "engine.effects.raster_dsl",
    ];
```

- [ ] **Step 3: Rebuild both sigil binaries**

```bash
cd $SIGILR && cargo build --release -p sigil-cli --bin sigil \
                          -p sigil-harness --bin emit_sound_blob
```

- [ ] **Step 4: Re-run the collision tool — it now reads 14 helpers from `native.rs`**

```bash
cd $AEON && python3 tools/emp_helper_closure.py
```

Expected: `OK — <M> names across 14 helpers, no collisions`, with `M > N`.

If it reports a collision, **rename the loser in the DSL** with a module prefix (`pal_clamp07`,
`rdsl_*`) rather than removing the guard. `clamp07` is the likeliest candidate — it is a generic name
and Task 4 just made it globally injected. Do not proceed to Step 5 with a collision outstanding: a
green golden afterwards would not mean the collision was absent, only that it happened to be benign
**today**.

- [ ] **Step 5: Build both aeon shapes and confirm byte-identity**

```bash
cd $AEON && ./build.sh 2>&1 | tail -6 && DEBUG=1 ./build.sh 2>&1 | tail -6
```

Expected: `crc=`/`len=` unchanged from Task 0. `collect_pub_comptime` injects only comptime kinds —
zero bytes, zero link symbols — so helper membership is byte-neutral unless it resolves a name that was
degrading to a label reference. That is precisely what an unchanged CRC proves here.

- [ ] **Step 6: Commit the sigil side**

```bash
cd $SIGILR && git add crates/sigil-harness/src/native.rs
cd $SIGILR && git commit -m "feat(native): add the effects DSLs to COMPTIME_HELPERS

engine.effects.palette_dsl + engine.effects.raster_dsl are pure comptime (no
\`in <section>\`), so neither needs a registry entry, a pins region, a map.toml
slot, or frozen-table rows. Paired with aeon feat/effects-p3-parcel-a; the
aeon-side tools/emp_helper_closure.py gates the set for name disjointness."
cd $SIGILR && git show --stat HEAD
```

- [ ] **Step 7: Commit the aeon side (the `use` lines the globs now supersede)**

No aeon file changes in this task — the `use` lines stay as documentation, exactly as
`use engine.structs.{Sec}` does in `raster.emp:14` and `palette.emp:12`. `normalize_helper_imports`
drops them at build time; keeping them in source is this codebase's established convention. Nothing to
commit here; note it in the task log.

---

## Task 6: `raster_dsl.emp` — the real vocabulary

**Files:**
- Modify: `engine/effects/raster_dsl.emp` (replace the Task-1 probe body)

- [ ] **Step 1: Replace the module with the vocabulary**

```
// engine/effects/raster_dsl.emp — the Phase-3 sparse-tier raster authoring vocabulary.
//
// The general constructor covers the SPARSE tier only. A [u16; N] array cannot hold a
// link-time symbol, so a program carrying the gradient's stream pointer is not
// expressible as a word array at any spelling: the DENSE tier keeps
// raster_gradient_program in engine.effects.raster. A program mixing sparse events
// with a dense run is deliberately NOT authorable in Phase 3 (design spec 4.1) even
// though the wire format permits it — a section takes one tier or the other.
//
// This module owns the encoding arithmetic and its validation; engine.effects.raster
// owns only the decoding. Pure comptime — emits no ROM bytes; glob-imported into every
// module (the native comptime-helper set).
//
// THE LITERALS IN THE FUNCTION BODIES BELOW ARE DELIBERATE. A comptime fn's free names
// resolve at its CALL SITE, so a body spelling OP_CRAM would force every author's
// module to import engine.effects.raster's constants or get `unknown name` — and in
// struct-literal position a missing import degrades SILENTLY to a label reference. The
// module-level ensures immediately below keep the single source of truth without
// imposing that on callers. This is the pattern water_arm0 established
// (engine/effects/raster.emp:585-597).
//
// vdp_comm / VdpTarget / VdpOp ARE safe to name in a body: engine.vdp is itself a
// COMPTIME_HELPERS member, so it is glob-injected at every call site.
module engine.effects.raster_dsl

use engine.effects.raster.{OP_SET_REG, OP_CRAM, OP_PAL_REGION, OP_RUN_GRADIENT,
                          RASTER_OPS_END, RASTER_ARM_PARK, RASTER_CRAM_MAX,
                          RASTER_BUF_SIZE, RASTER_MIN_FIRE_LINE, RASTER_MAX_FIRE_LINE,
                          pal_stage_off}

// ---- the inlined-literal pins (see the module note above) -------------------
ensure(OP_SET_REG == 0 && OP_CRAM == 2 && OP_PAL_REGION == 4 && OP_RUN_GRADIENT == 6,
       "raster_dsl's inlined opcodes drifted from engine.effects.raster")
ensure(RASTER_OPS_END == $FFFF, "raster_dsl's inlined terminator drifted from RASTER_OPS_END")
ensure(RASTER_ARM_PARK == $8AFF, "raster_dsl's inlined park word drifted from RASTER_ARM_PARK")
ensure(RASTER_CRAM_MAX == 3, "raster_dsl's inlined per-fire colour ceiling drifted from RASTER_CRAM_MAX")
ensure(RASTER_BUF_SIZE == 128, "raster_dsl's inlined buffer bound drifted from RASTER_BUF_SIZE")
ensure(RASTER_MIN_FIRE_LINE == 3 && RASTER_MAX_FIRE_LINE == 223,
       "raster_dsl's inlined screen-line bounds drifted from RASTER_{MIN,MAX}_FIRE_LINE")
// pal_region inlines the staging arithmetic rather than calling pal_stage_off (a
// call-site name); this pins the formula against its authority.
ensure(pal_stage_off(1, 3, 5) == 1 * 128 + 3 * 32 + 5 * 2,
       "raster_dsl's inlined Pal_Variant_Stage arithmetic drifted from pal_stage_off")

// ===========================================================================
// DESCRIPTORS
//
// The enum is plumbing; the AUTHORING surface is the constructors below it, which
// are where every bound is checked. Payload TYPES are not checked by the evaluator
// (they are declared `int` here even where the real payload is an array) — the
// constructors' ensures are what actually enforce the shapes.
// ===========================================================================

pub comptime enum RasterOp {
    SetReg(int, int),                     // (mid-frame $8xxx word, frame-top reset word)
    Cram(int, int),                       // (CRAM byte address, colour-word ARRAY)
    PalRegion(int, int, int, int, int),   // (CRAM byte address, slot, pal line, entry, count)
}

pub comptime enum RasterFire {
    Fire(int, int),                       // (screen line the effect lands on, RasterOp ARRAY)
}

// ---- op constructors --------------------------------------------------------

// set_reg — a mid-frame VDP register write, paired with the frame-top word that
// restores the SAME register. Pairing them is what makes "a mode change cannot latch
// past the frame" structural instead of a comment: raster_program derives the program's
// init words from these resets, so an author cannot write the mid-frame half alone.
pub comptime fn set_reg(word: int, reset: int) -> RasterOp {
    ensure(word >= $8000 && word <= $97FF,
           "set_reg: {word} is not a VDP register write word ($8000..$97FF)")
    ensure(reset >= $8000 && reset <= $97FF,
           "set_reg: frame-top reset {reset} is not a VDP register write word ($8000..$97FF)")
    ensure((word >> 8) == (reset >> 8),
           "set_reg: mid-frame word {word} writes VDP reg {(word >> 8) - $80} but its frame-top reset {reset} writes reg {(reset >> 8) - $80} — they must be the same register")
    return RasterOp.SetReg(word, reset)
}

// sh_on — Shadow/Highlight ON below the fire line, H40 base restored at frame top.
// $8C89 is $8C81 | bit 3: the resolution bits are untouched, per the V28/V30 quirk
// ruling in the raster survey. $8C81 is boot's H40 base (games/sonic4/data/boot_data.emp:140).
pub comptime fn sh_on() -> RasterOp {
    return set_reg($8C89, $8C81)
}

// cram — an inline CRAM write: `colours` words starting at CRAM byte address `addr`.
pub comptime fn cram(addr: int, colours: array) -> RasterOp {
    ensure(addr >= 0 && addr <= 126, "cram: CRAM byte address {addr} outside 0..126")
    ensure((addr & 1) == 0, "cram: CRAM byte address {addr} is odd — colours are words")
    ensure((addr >> 5) != 0,
           "cram: address {addr} is on CRAM line 0, the character's line (CharacterDef.cd_palette) — a raster write there repaints the active character")
    ensure(colours.len >= 1 && colours.len <= 3,
           "cram: {colours.len} colours exceeds RASTER_CRAM_MAX (3) — that is the ~60-cycle per-fire budget, not a FIFO limit")
    ensure(((addr >> 1) & 15) + colours.len <= 16,
           "cram: {colours.len} colours from entry {(addr >> 1) & 15} runs past the end of CRAM line {addr >> 5}")
    return RasterOp.Cram(addr, colours)
}

// pal_region — a SCOPED colour swap streamed from a variant's Pal_Variant_Stage bytes.
// The destination CRAM address and the staging source must name the same line and
// entry; hand authoring had no such check.
pub comptime fn pal_region(addr: int, slot: int, pal_line: int, entry: int, count: int) -> RasterOp {
    ensure(addr >= 0 && addr <= 126, "pal_region: CRAM byte address {addr} outside 0..126")
    ensure((addr & 1) == 0, "pal_region: CRAM byte address {addr} is odd — colours are words")
    ensure(slot >= 0 && slot < 2, "pal_region: slot {slot} outside 0..PAL_MAX_VARIANTS(2)")
    ensure(pal_line >= 1 && pal_line <= 3,
           "pal_region: staging line {pal_line} outside 1..3 (line 0 is the character's)")
    ensure(entry >= 0 && entry <= 15, "pal_region: entry {entry} outside 0..15")
    ensure(count >= 1 && count <= 3,
           "pal_region: {count} colours exceeds RASTER_CRAM_MAX (3)")
    ensure(entry + count <= 16,
           "pal_region: {count} colours from entry {entry} runs past the end of line {pal_line}")
    ensure((addr >> 5) == pal_line,
           "pal_region: destination CRAM address {addr} is on line {addr >> 5} but the staging source is line {pal_line}")
    ensure(((addr >> 1) & 15) == entry,
           "pal_region: destination CRAM address {addr} is entry {(addr >> 1) & 15} but the staging source is entry {entry}")
    return RasterOp.PalRegion(addr, slot, pal_line, entry, count)
}

// ---- fire constructors ------------------------------------------------------

// fire — one scheduled event. `line` is the SCREEN line the effect lands on; the DSL
// derives the fire line (line - 1) and the arm schedule. The floor of 3 is the priming
// records': fires 0/1 prime on lines 0-1, so the earliest real fire is 2, landing on 3.
// Lines 0-2 are the init words' job.
pub comptime fn fire(line: int, ops: array) -> RasterFire {
    ensure(line >= 3 && line <= 223,
           "fire: screen line {line} outside 3..223 (lines 0-2 belong to the priming records and the init words)")
    ensure(ops.len >= 1, "fire: a fire with no ops — drop the fire rather than authoring an empty one")
    return RasterFire.Fire(line, ops)
}

// region_boundary — the composite the water cluster is: at `line`, optionally turn
// Shadow/Highlight on, then swap the region. SET_REG comes first BY CONSTRUCTION here,
// so the mixed-fire invariant is structural for this constructor and only checked for
// hand-assembled fires.
pub comptime fn region_boundary(line: int, addr: int, slot: int, pal_line: int,
                                entry: int, count: int, sh: int = 0) -> RasterFire {
    ensure(sh == 0 || sh == 1, "region_boundary: sh {sh} must be 0 or 1")
    if sh == 1 {
        return fire(line, [sh_on(), pal_region(addr, slot, pal_line, entry, count)])
    }
    return fire(line, [pal_region(addr, slot, pal_line, entry, count)])
}

// ===========================================================================
// ENCODING
// ===========================================================================

comptime fn fire_line_of(f: RasterFire) -> int {
    return match f { Fire(m, ops) => m }
}
comptime fn fire_ops(f: RasterFire) {
    return match f { Fire(m, ops) => ops }
}

// op_words — the emitted body of one op.
comptime fn op_words(o: RasterOp) {
    return match o {
        SetReg(w, reset) => [0, w],
        Cram(a, cols)    => [2,
                             vdp_comm(a, VdpTarget.Cram, VdpOp.Write) >> 16,
                             vdp_comm(a, VdpTarget.Cram, VdpOp.Write) & $FFFF,
                             cols.len - 1] ++ cols,
        PalRegion(a, slot, pl, e, n) => [4,
                             vdp_comm(a, VdpTarget.Cram, VdpOp.Write) >> 16,
                             vdp_comm(a, VdpTarget.Cram, VdpOp.Write) & $FFFF,
                             n - 1,
                             slot * 128 + pl * 32 + e * 2],
    }
}

// op_size — the SAME fact by an independent path. This is what makes
// `data X: [u16; raster_words(P)] = raster_program(P)` a real guard rather than the
// tautology `[u16; P.len] = P` would be: two expressions of the word count that must
// agree. It catches header/record FRAMING drift; a wrong word VALUE inside a
// correctly-sized body is caught by the pinned hand-word twins and by the goldens.
comptime fn op_size(o: RasterOp) -> int {
    return match o {
        SetReg(w, reset)             => 2,
        Cram(a, cols)                => 4 + cols.len,
        PalRegion(a, slot, pl, e, n) => 5,
    }
}

// op_mask — the pal_dirty_mask bit an op needs re-asserted at frame top. CRAM byte
// address >> 5 is the palette line (32 bytes = 16 words per line). THIS is what makes
// a mid-frame write transient; a mask naming any other line leaves the write latched
// forever, which is the observed P1 bug (the red covered the whole ground, not just
// below the split, when the mask said %0001 and the op wrote line 2).
comptime fn op_mask(o: RasterOp) -> int {
    return match o {
        SetReg(w, reset)             => 0,
        Cram(a, cols)                => 1 << (a >> 5),
        PalRegion(a, slot, pl, e, n) => 1 << (a >> 5),
    }
}

// op_init — the frame-top reset word an op requires, if any.
comptime fn op_init(o: RasterOp) {
    return match o {
        SetReg(w, reset)             => [reset],
        Cram(a, cols)                => [],
        PalRegion(a, slot, pl, e, n) => [],
    }
}

comptime fn op_is_set_reg(o: RasterOp) -> int {
    return match o {
        SetReg(w, reset)             => 1,
        Cram(a, cols)                => 0,
        PalRegion(a, slot, pl, e, n) => 0,
    }
}

// prog_mask — OR of every op's mask bit.
comptime fn prog_mask(fires: array) -> int {
    comptime var m = 0
    for f in fires {
        for o in fire_ops(f) {
            m = m | op_mask(o)
        }
    }
    return m
}

// prog_init — the distinct frame-top reset words, in first-appearance order.
comptime fn prog_init(fires: array) {
    comptime var out = []
    for f in fires {
        for o in fire_ops(f) {
            for w in op_init(o) {
                comptime var seen = 0
                for x in out {
                    if x == w { seen = 1 }
                }
                if seen == 0 { out = out ++ [w] }
            }
        }
    }
    return out
}

// fire_lines — the full fire-line list: the two priming fires on lines 0 and 1, then
// one per authored event at (screen line - 1). Ruling 1a: the event fire must be at
// M-1 so its writes land on M. This is the SPARSE rule; the dense tier's T-1 setup
// line is a different, measured fact and must not be applied here.
comptime fn fire_lines(fires: array) {
    comptime var out = [0, 1]
    comptime var prev = 1
    for f in fires {
        let fl = fire_line_of(f) - 1
        ensure(fl > prev,
               "raster program: fires must be in strictly ascending screen-line order, and two events cannot share a fire line (fire line {fl} follows {prev})")
        out = out ++ [fl]
        prev = fl
    }
    return out
}

// arm_at — the arm word for record i. Ruling 1b: the word WRITTEN at record i is
// consumed at the next reload and schedules gap(L[i+1] -> L[i+2]); past the end it
// parks the counter 255 lines away, i.e. never within active display.
comptime fn arm_at(L: array, i: int) -> int {
    if i + 2 >= L.len { return $8AFF }
    let gap = L[i + 2] - L[i + 1] - 1
    ensure(gap >= 0 && gap <= 255,
           "raster program: gap {L[i + 1]}->{L[i + 2]} does not fit one counter reload (0..255)")
    return $8A00 | gap
}

// check_mixed_fire — ruling 14. In a fire mixing OP_SET_REG with a CRAM-class op,
// OP_SET_REG must be FIRST. OP_SET_REG writes with no delay while every CRAM op burns
// EFX_BLANK_DELAY first, so a SET_REG placed AFTER a CRAM op executes strictly later in
// the line — a worse artifact than the measured one, and invisible to an author.
comptime fn check_mixed_fire(f: RasterFire) -> int {
    comptime var n_set = 0
    comptime var n_cram = 0
    comptime var first_set = -1
    comptime var i = 0
    for o in fire_ops(f) {
        if op_is_set_reg(o) == 1 {
            n_set = n_set + 1
            if first_set < 0 { first_set = i }
        }
        if op_is_set_reg(o) == 0 { n_cram = n_cram + 1 }
        i = i + 1
    }
    ensure(n_set == 0 || n_cram == 0 || first_set == 0,
           "raster fire at screen line {fire_line_of(f)}: OP_SET_REG must be the FIRST op in a mixed fire (it is at index {first_set}). A mixed fire already switches its mode register ~45% across the line (measured, engine/effects/raster.emp:164-167); placing SET_REG after a CRAM op pushes it strictly later still, because CRAM ops burn EFX_BLANK_DELAY and SET_REG does not. Schedule a pixel-clean mode change a line earlier instead.")
    return 0
}

// ---- the two public entry points --------------------------------------------

// raster_words — the word count, computed from op_size. Use it as the length
// annotation on the `pub data`:
//     pub data P: [u16; raster_words(PROG)] = raster_program(PROG)
// NOT `[u16; PROG.len] = PROG`, which is tautological. Note the guard only bites on a
// `data` declaration — `const` does not enforce its declared array length.
pub comptime fn raster_words(fires: array) -> int {
    comptime var n = 2 + 4 + 2            // mask + init_count, two priming records, terminator
    n = n + prog_init(fires).len
    for f in fires {
        n = n + 2                          // the record's arm word + op_count
        for o in fire_ops(f) {
            n = n + op_size(o)
        }
    }
    return n
}

// raster_program — the flat program. Header, two priming records, one record per
// authored fire in ascending screen-line order, terminator.
pub comptime fn raster_program(fires: array) {
    ensure(fires.len >= 1, "raster_program: a program with no fires — use Raster_Program_None")
    let L = fire_lines(fires)
    let init = prog_init(fires)
    comptime var out = [prog_mask(fires), init.len] ++ init
    out = out ++ [arm_at(L, 0), 0]        // fire 0 — priming, line 0
    out = out ++ [arm_at(L, 1), 0]        // fire 1 — priming, line 1
    comptime var i = 0
    for f in fires {
        check_mixed_fire(f)
        comptime var body = []
        for o in fire_ops(f) {
            body = body ++ op_words(o)
        }
        out = out ++ [arm_at(L, i + 2), fire_ops(f).len] ++ body
        i = i + 1
    }
    out = out ++ [$8AFF, $FFFF]           // terminator — reached only by a stray fire
    // Raster_VBlank and Raster_InstallWater both copy a FIXED RASTER_BUF_SIZE bytes
    // into Buf_A / Buf_B, so a program longer than the buffer would be truncated live.
    // (The converse over-read of a short template is pre-existing and harmless — the
    // walker never reaches past the terminator — and is booked in docs/BUGS.md.)
    ensure(out.len * 2 <= 128,
           "raster_program: {out.len} words = {out.len * 2} bytes exceeds RASTER_BUF_SIZE (128) — Raster_VBlank and Raster_InstallWater copy a fixed 128 bytes")
    ensure(out.len == raster_words(fires),
           "raster_program: emitted {out.len} words but raster_words counted {raster_words(fires)} — the two encoding paths disagree")
    return out
}
```

- [ ] **Step 2: Build and confirm nothing moved**

```bash
cd $AEON && ./build.sh 2>&1 | tail -6
```

Expected: success, `crc`/`len` unchanged from Task 0. Nothing calls the new constructors yet, so this
proves only that the module parses and its module-level pins hold — which is exactly what it needs to
prove at this point.

- [ ] **Step 3: Re-run the collision tool**

```bash
cd $AEON && python3 tools/emp_helper_closure.py
```

Expected: `OK ... across 14 helpers, no collisions`. `cram`, `fire`, `set_reg` and `variant` are all
generic-sounding names now injected globally — this is the step that proves none of them shadow an
existing helper item.

- [ ] **Step 4: Commit**

```bash
cd $AEON && git add engine/effects/raster_dsl.emp
cd $AEON && git commit -m "feat(effects): the sparse-tier raster authoring vocabulary

Descriptors + constructors that own the arm schedule, the CRAM command split,
count-1, and the derivation of pal_dirty_mask and the frame-top init words from
the ops themselves. Three things hand authoring could not check are now
structural: a mid-frame register write must carry its own frame-top reset, a
region's destination must name the same line/entry as its staging source, and
SET_REG must lead a mixed fire. Zero bytes."
cd $AEON && git show --stat HEAD
```

---

## Task 7: Re-express `OJZ_TestRaster` in place, pinned word-for-word

The P1 acceptance program: below screen line 120, Shadow/Highlight on and OJZ's dominant ground colour
repainted bright red. It is the only fixture exercising the plain `OP_CRAM` path with an inline colour
(spec §8.2), so it is the harder of the two to express and goes first.

**Files:**
- Modify: `games/sonic4/data/parallax/configs.emp:310-329`

**Target words** (from the shipped fixture — the DSL must reproduce these 18 exactly):

```
%0100, 1, $8C81, $8A75, 0, $8AFF, 0, $8AFF, 2, 0, $8C89, 2, $C04A, $0000, 0, $000E, $8AFF, $FFFF
```

- [ ] **Step 1: Add the mismatch helper to `raster_dsl.emp`**

The instrument spec §8.1 asks for. It reports *where* the divergence is, which a golden diff cannot.

```
// first_mismatch — -1 when the two word lists are equal, else the index of the first
// differing element. The development instrument for re-expressing a hand-authored
// program through the DSL (design spec 8.1); pair it with a separate length ensure,
// because a length difference is a different failure than a value difference.
pub comptime fn first_mismatch(a: array, b: array) -> int {
    for i in 0..a.len {
        if i < b.len {
            if a[i] != b[i] { return i }
        }
    }
    return -1
}
```

- [ ] **Step 2: Write the DSL program and its pin, keeping the hand words**

Replace `configs.emp:310-329` (the `pub data OJZ_TestRaster: [u16; 18] = [ ... ]` block, keeping the
explanatory comment above it) with:

```
// The fire schedule below is now DERIVED. Kept as prose because it is what the arm
// words mean, and the walk-through is the thing a reader needs:
//   fire 0 @ line 0    priming, arm = $8A00 | (120 - 3) = $8A75 (117)
//   fire 1 @ line 1    priming, arm = park (nothing scheduled after the event)
//   fire 2 @ line 119  the event; its writes land on line 120
// VBlank leaves reg $0A = 0 -> fire 0 at line 0, reload 0 -> fire 1 at line 1,
// reload 117 -> fire 2 at 1 + 117 + 1 = 119. Effect on 120.
//
// pal_dirty_mask is DERIVED from the CRAM address ($4A >> 5 = line 2), so the mask
// can no longer name the wrong line — the observed P1 bug, where a mask of %0001
// against an op writing line 2 left the red latched over the whole ground instead of
// only below the split.
const OJZ_TEST_PROG = [
    fire(120, [ sh_on(),                            // S/H ON below the line
                cram($4A, [$000E]) ]),              // bright red at line 2 entry 5
]

// THE PIN (design spec 8.1). The hand-authored words are the ones measured on
// hardware during P1; the DSL must reproduce them exactly. Retained deliberately
// rather than deleted: a `const` emits nothing, and it turns a Parcel-C/D regression
// from "golden ROM differs" into "the DSL diverges at word 11". It retires in Parcel
// D together with the fixture it pins (design spec 8.2).
const OJZ_TEST_HAND = [
    %0100,
    1, $8C81,
    $8A75, 0,
    $8AFF, 0,
    $8AFF, 2,
      OP_SET_REG, $8C89,
      OP_CRAM, $C04A, $0000,
                 0, $000E,
    $8AFF, RASTER_OPS_END,
]
ensure(raster_words(OJZ_TEST_PROG) == OJZ_TEST_HAND.len,
       "OJZ_TestRaster: DSL counts {raster_words(OJZ_TEST_PROG)} words, the hand program is {OJZ_TEST_HAND.len}")
ensure(first_mismatch(raster_program(OJZ_TEST_PROG), OJZ_TEST_HAND) == -1,
       "OJZ_TestRaster: DSL output diverges from the hand-authored words at index {first_mismatch(raster_program(OJZ_TEST_PROG), OJZ_TEST_HAND)}")

pub data OJZ_TestRaster: [u16; raster_words(OJZ_TEST_PROG)] = raster_program(OJZ_TEST_PROG)
```

Note `OJZ_TEST_HAND` keeps naming `OP_SET_REG` / `OP_CRAM` / `RASTER_OPS_END`; the import prune in
Task 9 must therefore happen **after** the pin is retired, or the pin must be rewritten in literals.
It is rewritten in literals in Task 9 Step 3.

- [ ] **Step 3: Build and read the ensure output**

```bash
cd $AEON && ./build.sh 2>&1 | tail -20
```

If either ensure fires, the message names the diverging index. Map it back with the wire format in
`docs/EFFECTS_AUTHORING.md`: indices 0-2 are the header, 3-6 the two priming records, 7-8 the event
record's arm and op count, 9+ the op bodies. **Do not adjust the hand words to match the DSL** — the
hand words are the hardware-measured truth; fix the DSL.

Expected on success: build completes and the printed `crc`/`len` are **identical to Task 0's `s4`
values**.

- [ ] **Step 4: Prove the pin can fail**

Temporarily change `cram($4A, [$000E])` to `cram($4A, [$000C])` and rebuild.

```bash
cd $AEON && ./build.sh 2>&1 | grep -i "diverges"
```

Expected: `OJZ_TestRaster: DSL output diverges from the hand-authored words at index 15`. Revert and
rebuild green. A pin that cannot fail is worth nothing.

- [ ] **Step 5: Prove the length annotation moves with the program**

Temporarily add a second colour: `cram($4A, [$000E, $000E])`. Rebuild.

Expected: the length ensure fires — `OJZ_TestRaster: DSL counts 19 words, the hand program is 18`.
This proves `raster_words` tracks the descriptors rather than being a frozen literal. Revert and
rebuild green.

- [ ] **Step 6: Commit**

```bash
cd $AEON && git add engine/effects/raster_dsl.emp games/sonic4/data/parallax/configs.emp
cd $AEON && git commit -m "refactor(effects): author OJZ_TestRaster through the raster DSL

Same 18 words, none of them typed: the arm schedule, the split CRAM command,
count-1 and pal_dirty_mask are all derived. The hand-authored words stay as a
zero-byte pin so a later divergence reports an index instead of a golden diff.
ROM byte-identical."
cd $AEON && git show --stat HEAD
```

---

## Task 8: Re-express `OJZ_WaterRaster` in place, pinned word-for-word

The P2 water template: at the water line, S/H on and line-2 entries 4-6 swapped to the deep-water
variant's derived bytes, streamed from `Pal_Variant_Stage` slot 0. Its arm0 is a **default** — the
runtime patches it — which makes the `WATER_TEMPLATE_ARM0_OFF` invariant this task's new guard.

**Files:**
- Modify: `games/sonic4/data/parallax/configs.emp:389-403`

**Target words:**

```
%0100, 1, $8C81, $8A75, 0, $8AFF, 0, $8AFF, 2, 0, $8C89, 4, $C048, $0000, 2, 72, $8AFF, $FFFF
```

(`72` is `pal_stage_off(0, 2, 4)` = `0*128 + 2*32 + 4*2`.)

- [ ] **Step 1: Replace the fixture**

Replace `configs.emp:389-403` (the `pub data OJZ_WaterRaster: [u16; 18] = [ ... ]` block, keeping the
long explanatory comment above it, which stays accurate) with:

```
// The default water line. Raster_InstallWater / Raster_PatchWaterLine overwrite the
// priming arm word at runtime from Raster_Water_Line, so the boundary MOVES live; this
// value is only what the template ships with.
const OJZ_WATER_LINE = 120

const OJZ_WATER_PROG = [
    region_boundary(line: OJZ_WATER_LINE,
                    addr: OJZ_WATER_CRAM_ADDR,   // $48 — CRAM line 2, entry 4
                    slot: 0, pal_line: 2, entry: 4, count: 3,
                    sh:   1),
]

// THE PATCH-OFFSET INVARIANT, previously carried only by prose. Raster_PatchWaterLine
// writes the priming arm word at a FIXED byte offset into Buf_B
// (WATER_TEMPLATE_ARM0_OFF = 6), which is word index 3 — and word 3 is arm0 only when
// init_count is exactly 1. Any second init word would silently shift arm0 to index 4,
// and the patch would then rewrite an init word every frame instead of the boundary.
ensure(raster_program(OJZ_WATER_PROG)[3] == $8A00 | (OJZ_WATER_LINE - 3),
       "OJZ_WaterRaster: word 3 is not the priming arm word — Raster_PatchWaterLine patches byte offset 6 (WATER_TEMPLATE_ARM0_OFF) unconditionally, which is word 3 only when init_count == 1")

// THE PIN (design spec 8.1) — the words measured on hardware during P2. Retires in
// Parcel D with the fixture.
const OJZ_WATER_HAND = [
    %0100,
    1, $8C81,
    $8A75, 0,
    $8AFF, 0,
    $8AFF, 2,
      OP_SET_REG, $8C89,
      OP_PAL_REGION, $C048, $0000,
                 2,
                 pal_stage_off(0, 2, 4),
    $8AFF, RASTER_OPS_END,
]
ensure(raster_words(OJZ_WATER_PROG) == OJZ_WATER_HAND.len,
       "OJZ_WaterRaster: DSL counts {raster_words(OJZ_WATER_PROG)} words, the hand program is {OJZ_WATER_HAND.len}")
ensure(first_mismatch(raster_program(OJZ_WATER_PROG), OJZ_WATER_HAND) == -1,
       "OJZ_WaterRaster: DSL output diverges from the hand-authored words at index {first_mismatch(raster_program(OJZ_WATER_PROG), OJZ_WATER_HAND)}")

pub data OJZ_WaterRaster: [u16; raster_words(OJZ_WATER_PROG)] = raster_program(OJZ_WATER_PROG)
```

- [ ] **Step 2: Build and confirm byte-identity**

```bash
cd $AEON && ./build.sh 2>&1 | tail -20 && DEBUG=1 ./build.sh 2>&1 | tail -6
```

Expected: both shapes build; `crc`/`len` identical to Task 0's `s4` and `s4_debug`.

- [ ] **Step 3: Prove the new patch-offset invariant can fail**

Temporarily replace the composite with a hand-built fire carrying a second, different register write:

```
const OJZ_WATER_PROG = [
    fire(OJZ_WATER_LINE, [ sh_on(),
                           set_reg($8F02, $8F02),
                           pal_region($48, 0, 2, 4, 3) ]),
]
```

Rebuild. Expected: **the patch-offset ensure fires** — two distinct init words push `init_count` to 2
and arm0 off word 3. This is a real class of bug the shipped code could not detect. Revert to the
`region_boundary` form and rebuild green.

- [ ] **Step 4: Prove the mixed-fire ordering ensure can fail**

Temporarily reorder a hand-built fire so `sh_on()` follows the region op:

```
const OJZ_WATER_PROG = [
    fire(OJZ_WATER_LINE, [ pal_region($48, 0, 2, 4, 3), sh_on() ]),
]
```

Rebuild. Expected: `OP_SET_REG must be the FIRST op in a mixed fire (it is at index 1)`, carrying the
45% figure. Revert and rebuild green. This is ruling 14's gate; it must be demonstrated, not assumed.

- [ ] **Step 5: Prove the region address/source cross-check can fail**

Temporarily change `region_boundary`'s `entry: 4` to `entry: 5` (leaving `addr: $48`). Rebuild.

Expected: `pal_region: destination CRAM address 72 is entry 4 but the staging source is entry 5`.
Revert and rebuild green.

- [ ] **Step 6: Commit**

```bash
cd $AEON && git add games/sonic4/data/parallax/configs.emp
cd $AEON && git commit -m "refactor(effects): author OJZ_WaterRaster through the raster DSL

Same 18 words. Adds the WATER_TEMPLATE_ARM0_OFF invariant as a build-time
assertion: Raster_PatchWaterLine patches byte offset 6 unconditionally, which is
the priming arm word only while init_count == 1 - previously carried by prose
alone. ROM byte-identical."
cd $AEON && git show --stat HEAD
```

---

## Task 9: Shed the superseded authoring helpers and prune the imports

`raster.emp` now has comptime helpers the DSL subsumes. Deleting them is this codebase's established
response to a superseded comptime path — `raster_fire_screen` was deleted for exactly this reason
(`raster.emp:150-156`).

**Disposition, verified by grep — do not deviate without re-checking:**

| Helper | Callers after Task 8 | Action |
|---|---|---|
| `raster_arm` (`:197-203`) | **`raster_gradient_program` at `:273`, `:275`** — the DENSE tier, which stays | **KEEP** |
| `raster_fire_line` (`:207-212`) | none (only its own body and a comment at `:263`) | **DELETE** — `raster_dsl.fire()` owns the 3..223 floor |
| `water_arm0` (`:592-595`) | none | **DELETE** with its `ensure` at `:596-597`; the `RASTER_MIN/MAX_FIRE_LINE` pin survives in `raster_dsl` |
| `pal_stage_off` (`:112-117`) | `raster_dsl`'s pin `ensure` | **KEEP** — it is the format's documented authority (the handler comment at `:476` cites it) and the pin is a live caller, not a dormant scaffold |
| `RASTER_MIN_FIRE_LINE` / `RASTER_MAX_FIRE_LINE` | `Raster_PatchWaterLine` at `:650-664`, `:652` | **KEEP** |

- [ ] **Step 1: Delete `raster_fire_line`**

Delete `raster.emp:205-212` (the fn and its comment). At `:263`, the comment "Floor is 3, matching
raster_fire_line" becomes stale — change it to "Floor is 3, matching `raster_dsl.fire`".

- [ ] **Step 2: Delete `water_arm0` and re-home its rationale**

Delete `raster.emp:586-597` (the call-site-resolution comment, the fn, and its bounds `ensure`). Keep
`:580-585` — the `RASTER_MIN_FIRE_LINE` / `RASTER_MAX_FIRE_LINE` consts and the formula comment, which
`Raster_PatchWaterLine` still needs. Amend the comment at `:581-583` to read:

```
// RASTER_MIN_FIRE_LINE is the `- 3` above, named ONCE: engine.effects.raster_dsl's
// arm_at reduces to $8A00 | (M - 3) for a single-event program and pins itself against
// this constant; Raster_PatchWaterLine below is the runtime twin. They were previously
// two hand-synced literals with only a comment holding them together.
```

- [ ] **Step 3: Rewrite the two pins in literals, then prune the imports**

The `OJZ_TEST_HAND` / `OJZ_WATER_HAND` pins currently name `OP_SET_REG`, `OP_CRAM`, `OP_PAL_REGION`,
`RASTER_OPS_END` and `pal_stage_off`. Replace those names with their literal values, so the pins do not
share symbols with the encoder they pin:

In `OJZ_TEST_HAND`: `OP_SET_REG` -> `0`, `OP_CRAM` -> `2`, `RASTER_OPS_END` -> `$FFFF`.
In `OJZ_WATER_HAND`: `OP_SET_REG` -> `0`, `OP_PAL_REGION` -> `4`, `RASTER_OPS_END` -> `$FFFF`,
`pal_stage_off(0, 2, 4)` -> `72`.

Add above each pin: `// Literals on purpose: a pin sharing symbols with the encoder it pins is weaker.
raster_dsl's module-level ensures hold these against engine.effects.raster.`

Then replace `configs.emp:26-27`:

```
// Effects P1 gate fixtures (below) need the raster program vocabulary + the CRAM
// command builder they are pinned against.
use engine.effects.raster.{OP_SET_REG, OP_CRAM, OP_PAL_REGION, RASTER_OPS_END, RASTER_ARM_PARK, raster_arm, pal_stage_off, water_arm0}
```

with:

```
// The sparse fixtures are authored through engine.effects.raster_dsl, which is a
// COMPTIME_HELPERS member and therefore ambient. What remains is the DENSE tier's
// import surface: raster_gradient_program's BODY names these, and a comptime fn's
// free names resolve at the EMISSION site's scope, so they must be visible HERE or
// they degrade to unresolved label refs.
use engine.effects.raster.{RASTER_ARM_PARK, RASTER_OPS_END, raster_arm}
```

Leave `:28-33` (the existing comment plus the `RasterGradientProgram, RASTER_CRAM_MAX,
raster_gradient_program, RASTER_ARM_EVERY_LINE, OP_RUN_GRADIENT` import) unchanged — that comment
already explains exactly this rule and is now the only place it is needed.

**`raster_arm`, `RASTER_ARM_PARK` and `RASTER_OPS_END` must stay in the list.**
`raster_gradient_program`'s returned struct literal names all three (`raster.emp:273-284`) and
`OJZ_TestGradient` is emitted from `configs.emp`. Dropping any of them degrades a struct field to a
label reference **silently** — the failure mode `configs.emp:28-33` was written about.

- [ ] **Step 4: Build both shapes**

```bash
cd $AEON && ./build.sh 2>&1 | tail -6 && DEBUG=1 ./build.sh 2>&1 | tail -6
```

Expected: `crc`/`len` identical to Task 0. If `OJZ_TestGradient`'s bytes moved, an import was pruned
too far — restore it.

- [ ] **Step 5: Confirm the deletions left no references**

```bash
cd $AEON && grep -rn --include='*.emp' -w -e raster_fire_line -e water_arm0 engine games
```

Expected: no output.

- [ ] **Step 6: Commit**

```bash
cd $AEON && git add engine/effects/raster.emp games/sonic4/data/parallax/configs.emp
cd $AEON && git commit -m "refactor(effects): delete the authoring helpers raster_dsl supersedes

raster_fire_line and water_arm0 both lose their last caller; raster_arm stays
because raster_gradient_program (the dense tier) still calls it, and the dense
tier's import surface stays with it - those names resolve at the emission site.
ROM byte-identical."
cd $AEON && git show --stat HEAD
```

---

## Task 10: The budget-model checker

Spec §4.3: a checker over the `code-derived` rows that resolves each named `.emp` symbol and fails on
disagreement. Not the originally-drafted generator, which was unsound — the measured rows are upper
bounds including profiler instrumentation and exception entry, so an `ensure` against them would fail
programs that demonstrably run today.

**It is not vacuous — it already has a catch:** `tools/effects_budget_model.toml:99` says
`raster_state_bytes = 286`; `RASTER_STATE_SIZE` is 288 (`raster.emp:184`). `PALETTE_STATE_SIZE` agrees
at 472, so it is a real one-row drift, not a systematic offset. That is spec §10 item 5.

**Files:**
- Create: `tools/effects_budget_check.py`
- Test: `tools/test_effects_budget_check.py`
- Modify: `tools/effects_budget_model.toml`

- [ ] **Step 1: Add the `[symbols]` table to the TOML**

Today the row-to-symbol linkage is comment-only prose, which no checker can consume. Append at the end
of `tools/effects_budget_model.toml`:

```toml
# ---------------------------------------------------------------------------
# [symbols] — the machine-readable half of the "code-derived" status key. Each entry
# maps a dotted row path above to the .emp constant that is its authority;
# tools/effects_budget_check.py resolves the constant and fails on disagreement.
#
# NOT resolvable, deliberately absent, and recorded here so their absence is not read
# as an oversight: save_set_registers (a `movem` operand, not a constant),
# program_overhead_fires (no symbol exists), full_line_fire_cost (ceil(16/3), computed
# prose), compose_static_frame (prose). The two NEEDS-MEASUREMENT rows are evidence
# gaps, not build gates.
[symbols]
"raster.sparse.cram_words_per_fire"         = "engine/effects/raster.emp:RASTER_CRAM_MAX"
"raster.op_pal_region.max_colours_per_fire" = "engine/effects/raster.emp:RASTER_CRAM_MAX"
"palette.max_active_variants"               = "engine/effects/palette.emp:PAL_MAX_VARIANTS"
"palette.cycle_max_channels"                = "engine/effects/palette.emp:PAL_CYCLE_MAX_CHANNELS"
"palette.fade_window_frames"                = "engine/effects/palette.emp:PAL_FADE_FRAMES"
"ram.palette_state_bytes"                   = "engine/effects/palette.emp:PALETTE_STATE_SIZE"
"ram.raster_state_bytes"                    = "engine/effects/raster.emp:RASTER_STATE_SIZE"
"ram.variant_stage_bytes"                   = "engine/effects/palette.emp:PAL_MAX_VARIANTS * 128"
```

Also correct the header (`:1-2`), which claims a generator enforces the model:

```toml
# Effects suite budget model (design suite §8) — the ONE machine-readable budget.
# The `code-derived` rows are gated by tools/effects_budget_check.py against the
# [symbols] table at the bottom of this file; the `fixed` rows are documentation with
# provenance; the NEEDS-MEASUREMENT rows are evidence gaps. There is deliberately no
# generator: the measured rows are upper bounds that include profiler instrumentation
# and exception entry (~2090 cyc/fire against a usable_cycles_after_entry of 60), so a
# generated `ensure` would fail programs that demonstrably run today (design spec §4.3).
```

- [ ] **Step 2: Write the failing test**

```python
#!/usr/bin/env python3
"""Tests for effects_budget_check — the budget model's code-derived rows."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from effects_budget_check import (
    emp_constants, eval_int_expr, check, main as budget_main,
)

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SAMPLE_EMP = """\
module engine.fake
// pub const DECOY = 999
pub const SIMPLE = 3
pub const HEXY = $10
pub const BINNY = %1110
pub const BUF = 128
pub const SUM = 4 + 4 + 2 + BUF + BUF
pub const SHIFTED = BUF << 1
"""


class TestEmpConstants(unittest.TestCase):
    def setUp(self):
        fh = tempfile.NamedTemporaryFile("w", suffix=".emp", delete=False)
        fh.write(SAMPLE_EMP)
        fh.close()
        self.path = fh.name

    def tearDown(self):
        os.unlink(self.path)

    def test_reads_decimal_hex_and_binary(self):
        c = emp_constants(self.path)
        self.assertEqual(eval_int_expr(c["SIMPLE"], c), 3)
        self.assertEqual(eval_int_expr(c["HEXY"], c), 16)
        self.assertEqual(eval_int_expr(c["BINNY"], c), 14)

    def test_resolves_expressions_referencing_other_constants(self):
        c = emp_constants(self.path)
        self.assertEqual(eval_int_expr(c["SUM"], c), 266)
        self.assertEqual(eval_int_expr(c["SHIFTED"], c), 256)

    def test_ignores_commented_out_constants(self):
        self.assertNotIn("DECOY", emp_constants(self.path))

    def test_rejects_a_non_arithmetic_expression(self):
        with self.assertRaises(ValueError):
            eval_int_expr("__import__('os').system('true')", {})


class TestCheck(unittest.TestCase):
    def test_reports_a_disagreeing_row(self):
        rows = check(
            {"ram": {"raster_state_bytes": 286}},
            {"ram.raster_state_bytes": "fake.emp:RASTER_STATE_SIZE"},
            resolver=lambda ref: 288,
        )
        self.assertEqual(rows, [("ram.raster_state_bytes", 286, 288)])

    def test_agreeing_rows_report_nothing(self):
        rows = check(
            {"ram": {"raster_state_bytes": 288}},
            {"ram.raster_state_bytes": "fake.emp:RASTER_STATE_SIZE"},
            resolver=lambda ref: 288,
        )
        self.assertEqual(rows, [])

    def test_a_symbol_naming_a_missing_row_is_an_error_not_a_pass(self):
        with self.assertRaises(KeyError):
            check({"ram": {}}, {"ram.nope": "fake.emp:X"}, resolver=lambda ref: 1)


class TestLiveTree(unittest.TestCase):
    def test_the_shipped_budget_model_agrees_with_the_shipped_code(self):
        """The live gate. Fails the suite the moment a constant and the TOML drift."""
        rc = budget_main([AEON])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run and verify it fails**

```bash
cd $AEON && python3 -m pytest tools/test_effects_budget_check.py -q 2>&1 | tail -5
```

Expected: `ModuleNotFoundError: No module named 'effects_budget_check'`.

- [ ] **Step 4: Write the checker**

```python
#!/usr/bin/env python3
"""
effects_budget_check — gate the effects budget model's code-derived rows.

tools/effects_budget_model.toml carries a [symbols] table mapping a dotted row path to
the .emp constant that is its authority. This resolves each constant (following
references to other constants in the same file) and fails on disagreement.

Deliberately NOT a generator. The measured rows are upper bounds including profiler
instrumentation and exception entry, so a generated `ensure` against them would fail
programs that demonstrably run today (design spec 4.3).

Usage:
    python3 tools/effects_budget_check.py [AEON_DIR]
"""

from __future__ import annotations

import ast
import os
import re
import sys
import tomllib
from typing import Any, Callable, Dict, List, Tuple

CONST_RE = re.compile(r"^\s*(?:pub\s+)?const\s+([A-Z][A-Z0-9_]*)\s*=\s*(.+?)\s*$")
COMMENT_RE = re.compile(r"^\s*//")
TRAILING_COMMENT_RE = re.compile(r"\s+//.*$")

# `$1F` -> 0x1F, `%1010` -> 0b1010, applied before the expression is parsed.
HEX_RE = re.compile(r"\$([0-9A-Fa-f]+)")
BIN_RE = re.compile(r"%([01]+)")

# The only AST node types the evaluator walks. Anything else — a call, an attribute,
# a subscript — is a hard error, so this never becomes an arbitrary-code path.
_ALLOWED = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Name, ast.Load,
    ast.Add, ast.Sub, ast.Mult, ast.LShift, ast.RShift, ast.BitOr, ast.BitAnd,
    ast.BitXor, ast.USub, ast.UAdd, ast.FloorDiv,
)


def emp_constants(path: str) -> Dict[str, str]:
    """Every `const NAME = <expr>` in a module, as unevaluated expression text."""
    out: Dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            if COMMENT_RE.match(line):
                continue
            m = CONST_RE.match(line)
            if m:
                out[m.group(1)] = TRAILING_COMMENT_RE.sub("", m.group(2)).strip()
    return out


def eval_int_expr(expr: str, consts: Dict[str, str], _seen: frozenset = frozenset()) -> int:
    """Evaluate an .emp integer expression, resolving names against `consts`."""
    src = BIN_RE.sub(lambda m: str(int(m.group(1), 2)), HEX_RE.sub(r"0x\1", expr))
    src = src.replace("/", "//")
    try:
        tree = ast.parse(src, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"cannot parse {expr!r}: {exc}") from exc

    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED):
            raise ValueError(f"{expr!r} contains an unsupported construct: {type(node).__name__}")

    def walk(node: ast.AST) -> int:
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant):
            if not isinstance(node.value, int):
                raise ValueError(f"{expr!r} is not an integer expression")
            return node.value
        if isinstance(node, ast.Name):
            if node.id in _seen:
                raise ValueError(f"{expr!r}: circular reference through {node.id}")
            if node.id not in consts:
                raise ValueError(f"{expr!r}: unknown constant {node.id}")
            return eval_int_expr(consts[node.id], consts, _seen | {node.id})
        if isinstance(node, ast.UnaryOp):
            v = walk(node.operand)
            return -v if isinstance(node.op, ast.USub) else v
        if isinstance(node, ast.BinOp):
            a, b = walk(node.left), walk(node.right)
            op = node.op
            if isinstance(op, ast.Add):
                return a + b
            if isinstance(op, ast.Sub):
                return a - b
            if isinstance(op, ast.Mult):
                return a * b
            if isinstance(op, ast.FloorDiv):
                return a // b
            if isinstance(op, ast.LShift):
                return a << b
            if isinstance(op, ast.RShift):
                return a >> b
            if isinstance(op, ast.BitOr):
                return a | b
            if isinstance(op, ast.BitAnd):
                return a & b
            if isinstance(op, ast.BitXor):
                return a ^ b
        raise ValueError(f"{expr!r}: unsupported node {type(node).__name__}")

    return walk(tree)


def make_resolver(aeon: str) -> Callable[[str], int]:
    """`path.emp:EXPR` -> the integer value, with the module's constants in scope."""
    cache: Dict[str, Dict[str, str]] = {}

    def resolve(ref: str) -> int:
        rel, _, expr = ref.partition(":")
        path = os.path.join(aeon, rel)
        if path not in cache:
            if not os.path.exists(path):
                raise ValueError(f"[symbols] names a missing file: {rel}")
            cache[path] = emp_constants(path)
        return eval_int_expr(expr, cache[path])

    return resolve


def dig(model: Dict[str, Any], dotted: str) -> Any:
    node: Any = model
    for part in dotted.split("."):
        node = node[part]
    return node


def check(model: Dict[str, Any], symbols: Dict[str, str],
          resolver: Callable[[str], int]) -> List[Tuple[str, Any, int]]:
    """Rows whose TOML value disagrees with its .emp authority."""
    bad: List[Tuple[str, Any, int]] = []
    for row in sorted(symbols):
        declared = dig(model, row)      # KeyError on a symbol naming a missing row
        actual = resolver(symbols[row])
        if declared != actual:
            bad.append((row, declared, actual))
    return bad


def main(argv: List[str]) -> int:
    aeon = argv[0] if argv else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    toml_path = os.path.join(aeon, "tools", "effects_budget_model.toml")
    with open(toml_path, "rb") as fh:
        model = tomllib.load(fh)
    symbols = model.get("symbols")
    if not symbols:
        print(f"{toml_path}: no [symbols] table — nothing is gated, which is not a pass")
        return 2
    bad = check(model, symbols, make_resolver(aeon))
    if bad:
        print(f"{len(bad)} budget row(s) disagree with the shipped code:")
        for row, declared, actual in bad:
            print(f"  {row}: model says {declared}, {symbols[row]} is {actual}")
        return 1
    print(f"effects_budget_check: OK — {len(symbols)} code-derived rows agree")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 5: Run it and watch it CATCH the known drift**

```bash
cd $AEON && python3 tools/effects_budget_check.py
```

Expected — the checker earning its keep on its first run:

```
1 budget row(s) disagree with the shipped code:
  ram.raster_state_bytes: model says 286, engine/effects/raster.emp:RASTER_STATE_SIZE is 288
```

If it reports **zero** rows on this first run, the checker is not resolving anything and is vacuous —
**STOP and debug it**, do not proceed.

- [ ] **Step 6: Fix the drift**

`tools/effects_budget_model.toml:99`: `raster_state_bytes = 286` -> `288`, and correct the trailing
comment to `# RASTER_STATE_SIZE (Program/Cursor/Pending/Line + Buf_A/Buf_B 128 each + Active_Buf +
dense + water)`. Re-run:

```bash
cd $AEON && python3 tools/effects_budget_check.py
```

Expected: `effects_budget_check: OK — 8 code-derived rows agree`.

- [ ] **Step 7: Run the tests**

```bash
cd $AEON && python3 -m pytest tools/test_effects_budget_check.py -q 2>&1 | tail -5
```

Expected: `8 passed`.

- [ ] **Step 8: Record the caught defect and book the other five**

Add the six spec §10 items to `docs/BUGS.md`, each tagged with its owning parcel, so none is lost:

- Item 5 (this parcel, **FIXED**): the TOML claimed `raster_state_bytes = 286` against a
  `RASTER_STATE_SIZE` of 288 — documentation drift, caught by the new checker on its first run, no
  runtime effect.
- Item 4 (this parcel, **partially closed**): `Raster_InstallWater` copies a fixed 128 bytes from
  34-36 byte templates. Parcel A adds the *upper* bound `ensure` so an author cannot exceed the buffer;
  the over-read of a short template stays open.
- Items 1, 2, 3, 6: **Parcel C's** — water surviving exactly one section crossing; the unreachable
  cross-fade layer; the count-0 cycle script leaving `PAL_ACT_CYCLE` set (which C **must** fix, because
  `Pal_Cycle_None` would be the first thing ever to exercise that path and would re-arm the
  15.1%-of-frame derive `ff0720ff` recovered); and the un-gated `act_sec_field_equs`.

- [ ] **Step 9: Commit**

```bash
cd $AEON && git add tools/effects_budget_check.py tools/test_effects_budget_check.py \
                    tools/effects_budget_model.toml docs/BUGS.md
cd $AEON && git commit -m "test(effects): gate the budget model's code-derived rows against the .emp

Adds a [symbols] table (the linkage was comment-only prose no checker could
consume) and a resolver that follows constant references. It caught a real drift
on its first run: the model claimed raster_state_bytes 286 against a
RASTER_STATE_SIZE of 288. A checker, not a generator - the measured rows are
upper bounds including profiler instrumentation, so a generated ensure would
fail programs that demonstrably run today."
cd $AEON && git show --stat HEAD
```

---

## Task 11: The gate — seven goldens green with no rebaseline

**Files:** none (measurement only).

- [ ] **Step 1: Rebuild both sigil binaries from the worktree**

```bash
cd $SIGILR && cargo build --release -p sigil-cli --bin sigil \
                          -p sigil-harness --bin emit_sound_blob
```

A stale binary produces a green run against the wrong compiler. Not optional.

- [ ] **Step 2: The helper-closure collision diff — BEFORE the golden run**

```bash
cd $AEON && python3 tools/emp_helper_closure.py
```

Expected: `OK — <M> names across 14 helpers, no collisions`. Spec §4.4 is explicit that this runs
first, so a green golden is not mistaken for absence of collision.

- [ ] **Step 3: Fresh-build all seven goldens**

```bash
cd $SIGILR && crates/sigil-harness/golden/capture_goldens.sh
```

**The gate:** every one of the seven `full`/`anchor` pairs must equal Task 0 Step 4's, which are the
chain tip `character-lens-sweep-postmerge` — in particular `s4 fedcf197/696836 anchor 202f705f/0xa11f0`.

**Any difference is a parcel failure, not a rebaseline trigger.** Do not run `refreeze --freeze`.
Parcel A moves zero bytes by design; a moved anchor means data relocated and the parcel's own
byte-compare has self-rebaselined into vacuity (spec §2.1). Bisect the task commits to find which one
moved bytes.

- [ ] **Step 4: The in-suite byte gates**

```bash
cd $SIGILR && SIGIL_STRICT_GATE=1 cargo test --release -p sigil-cli \
    --test native_full_rom --test native_offcanonical_full \
    --test native_offcanonical_rom --test native_rom > /tmp/t11-byte.out 2> /tmp/t11-byte.err
grep -E "^test result" /tmp/t11-byte.out
```

Expected: every line `0 failed`. `SIGIL_STRICT_GATE=1` is mandatory — without it these skip *green*.

- [ ] **Step 5: Chain check**

```bash
cd $SIGILR && cargo run -q --release -p sigil-harness --bin refreeze -- --check
```

Expected: `OK (tip \`character-lens-sweep-postmerge\`, chain len 111)` — **unchanged**, no new entry.
This is *not* the goldens (Step 3 is); it is here only to prove nothing was frozen.

- [ ] **Step 6: The full sigil suite (this parcel's port-flip ritual)**

```bash
cd $SIGILR && SIGIL_STRICT_GATE=1 cargo test --workspace --release --no-fail-fast \
    > /tmp/t11-full.out 2> /tmp/t11-full.err
grep -E "^test result" /tmp/t11-full.out | awk '{p+=$4; f+=$6; i+=$8} END {print "passed",p,"failed",f,"ignored",i}'
grep -E "^(failures:|test .* FAILED)" /tmp/t11-full.out | head -40
```

Expected: `passed 3672 failed 0 ignored 4`, matching Task 0 Step 6. **Read the aggregate totals and the
failing-target lines — never `tail` a test run.** A tail once hid 16 failures in this tree and a merge
went out claiming green.

- [ ] **Step 7: The aeon python suite**

```bash
cd $AEON && python3 -m pytest -q > /tmp/t11-py.out 2>&1; tail -3 /tmp/t11-py.out
```

Expected: `974 passed, 2 skipped` — Task 0's 944 plus the 30 new tests (22 closure, shipped in
`de116cdd`; 8 budget from Task 10). If the count is not exactly `944 + 22 + <Task 10's count>`, a test
file is not being collected. Task 2 landed 22 rather than the drafted 6 — see its SHIPPED note.

**Caveat to state in the evidence note rather than paper over:** nothing runs `pytest` automatically —
no CI, no hook, not `test.sh`. The two new checkers are gates only when someone runs the suite. That is
a pre-existing gap already booked in `docs/DEFERRED_WORK.md` §5; this parcel adds to the pile rather
than fixing it.

- [ ] **Step 8: Confirm the working tree holds only this parcel's files**

```bash
cd $AEON && git status --short && git log --oneline master..HEAD
cd $SIGILR && git status --short && git log --oneline master..HEAD
```

Expected: aeon shows **9** commits (Tasks 1, 2, 3, 4, 6, 7, 8, 9, 10 — Task 5's change is sigil-side
only) and no modifications outside the daemon's `data/editor/` and `data/sprites/` paths; sigil shows
1 commit.

---

## Task 12: Evidence, docs, and the paired merge

**Files:**
- Create: `docs/superpowers/notes/2026-08-13-effects-p3-parcel-a-evidence.md`
- Modify: `docs/DEFERRED_WORK.md`

- [ ] **Step 1: Write the evidence note**

It must carry, so a reader can falsify each claim:

1. **The seven golden pairs before and after**, side by side, plus the statement that no
   `refreeze --freeze` ran and the chain length is unchanged at 111.
2. **The five capability-probe results** from Task 1 including both negative-control messages — the
   §5.2 `Label != 0` witness the spec left owed, now paid, and the §6.1 `const`-vs-`data` guard check.
3. **The four negative controls on the shipped guards**: the word-value pin (Task 7 Step 4), the
   patch-offset invariant (Task 8 Step 3), the mixed-fire ordering ensure (Task 8 Step 4) and the
   region address/source cross-check (Task 8 Step 5), each with the exact message it produced. Without
   these the guards are decoration.
4. **The collision-tool readings** before (12 helpers) and after (14), and any rename it forced.
5. **The budget checker's first-run catch** (286 vs 288) and the post-fix OK line.
6. **The suite totals**: sigil `3672/0/4`, aeon pytest `958 passed, 2 skipped`.
7. **What this parcel did NOT prove**: the length annotation catches framing drift, not word-value
   drift; the two pinned fixtures are the only programs the DSL has ever produced, so its generality is
   unproven until Parcel D authors new content; and nothing runs the two new python gates
   automatically.
8. **The verified aeon+sigil SHA pair.**

- [ ] **Step 2: Update `docs/DEFERRED_WORK.md`**

Cite by heading, not by number — the file has two independently numbered lists and "entry 3" is
ambiguous. Add under the effects heading: `region_boundary`'s signature is Parcel-A-shaped (the
parameters `OJZ_WaterRaster` needs) and Parcel D re-shapes it once the pack's needs are known; and the
raster DSL covers the sparse tier only, with sparse-plus-dense mixing explicitly out of scope for
Phase 3.

Do **not** touch the water/underwater-hooks entry at `:229` or the dense-tier reserved-register entry
at `:273` — those belong to Parcel C and ruling 12 respectively.

`docs/ENGINE_ARCHITECTURE.md` §7 is **not** edited here: reconciling its P2 drift is an explicit
Parcel-C obligation (spec §11), and doing it in A would put an unattributable doc change inside a
byte-neutral parcel.

- [ ] **Step 3: Commit the docs**

```bash
cd $AEON && git add docs/superpowers/notes/2026-08-13-effects-p3-parcel-a-evidence.md \
                    docs/DEFERRED_WORK.md
cd $AEON && git commit -m "docs(effects): Parcel A evidence — seven goldens green, no rebaseline

Includes the four negative controls on the new guards and the two toolchain
witnesses spec 5.2/6.1 left owed. Records what the parcel did NOT prove: the
length annotation catches framing drift, not word-value drift, and the DSL's
generality is unproven until Parcel D authors new content."
```

- [ ] **Step 4: Merge the pair**

Merge aeon **and** sigil together. A sigil master coupled to an unmerged aeon branch has already made
aeon master unbuildable once in this tree.

```bash
cd /home/volence/sonic_hacks/aeon && git checkout master && \
  git merge --no-ff feat/effects-p3-parcel-a \
  -m "Merge effects-p3-parcel-a: the raster + palette authoring vocabulary

Comptime-only: both DSL modules, the COMPTIME_HELPERS pairing, the helper-closure
collision gate, the budget-model checker, and the two shipped sparse fixtures
re-expressed in place. All seven golden ROMs green with no rebaseline."

cd /home/volence/sonic_hacks/sigil && git checkout master && \
  git merge --no-ff feat/effects-p3-parcel-a \
  -m "Merge effects-p3-parcel-a: add the effects DSLs to COMPTIME_HELPERS"
```

- [ ] **Step 5: Post-merge verification from master, in both repos**

```bash
cd /home/volence/sonic_hacks/sigil && cargo build --release -p sigil-cli --bin sigil \
                                                  -p sigil-harness --bin emit_sound_blob
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
export AEON_DIR=/home/volence/sonic_hacks/aeon
cd /home/volence/sonic_hacks/sigil && crates/sigil-harness/golden/capture_goldens.sh
cd /home/volence/sonic_hacks/aeon && python3 -m pytest -q 2>&1 | tail -3
```

Expected: the same seven pairs, `958 passed, 2 skipped`. **Never leave master broken.**

- [ ] **Step 6: Record the verified pair and clean up**

Append the two merge SHAs to the evidence note as "verified pair", commit that one-line edit, then:

```bash
cd /home/volence/sonic_hacks/aeon  && git worktree remove .worktrees/p3a
cd /home/volence/sonic_hacks/sigil && git worktree remove .worktrees/p3a
```

Do not push — this tree's convention is merge-to-master locally.

---

## Self-review against the spec

| Spec requirement | Where it lands |
|---|---|
| §2.1 comptime-only, zero bytes moved | Standing constraint 1; every task's build step asserts unchanged `crc`/`len` |
| §4.1 vocabulary table first | Task 3 -> `docs/EFFECTS_AUTHORING.md`; the table is inline in this plan too |
| §4.1 must express `OJZ_TestRaster`'s plain `OP_CRAM` at a different CRAM address | `cram()`; Task 7 |
| §4.1 the region op's address/entry/count triple | `pal_region()`; Task 8 |
| §4.1 the mask and init words derive from the descriptors | `op_mask`/`prog_mask`, `op_init`/`prog_init`; Task 6 |
| §4.1 T-1 is a DENSE fact, not sparse | Standing constraint 7; comment on `fire_lines` |
| §4.1 sparse+dense mixing out of scope | Task 3 Step 1; Task 12 Step 2 |
| §4.2 palette constructors move; model-plus-proof retained | Task 4 |
| §4.2 the `PalCycleScriptN` wart | `cycle_script1`/`cycle_script2`; Task 4 Steps 1, 4 |
| §4.3 checker not generator; 7 rows / 6 constants + `variant_stage_bytes` | Task 10 (8 `[symbols]` rows) |
| §4.3 TOML gains an explicit symbol key per row | Task 10 Step 1 |
| §4.3 the `RASTER_STATE_SIZE` 286/288 catch | Task 10 Steps 5-6 |
| §4.4 structural half — `COMPTIME_HELPERS` | Task 5 |
| §4.4 discipline half — literals + co-located pins | Standing constraint 6; `raster_dsl`'s module note and its six pin `ensure`s |
| §4.4 helper-closure collision diff **before** the golden run | Task 2 (tool), Task 11 Step 2 (ordering) |
| §5.2 the `Label != 0` comptime witness | Task 1 Steps 1, 5, with a negative control |
| §5.3 rider — `RASTER_BUF_SIZE` bound `ensure` | `raster_program`'s final ensure |
| §5.4 / ruling 14 `SET_REG`-must-be-first, with the 45% figure | `check_mixed_fire`; Task 8 Step 4 |
| §6.1 length guards sit on `data`, never `const` | Standing constraint 5; the guard table in Task 3; Task 7 Step 5 |
| §8.1 gate: seven goldens, no rebaseline | Task 11 Step 3 |
| §8.1 per-fixture comptime word-compare as the working instrument | `first_mismatch`; Tasks 7-8 |
| §8.1 port-flip ritual | Task 11 Step 6, with the finding that `palette_port` does not exist as a test binary |
| §2 paired merge, both sigil binaries rebuilt | Standing constraints 3-4; Task 12 Step 4 |

**Known limits, stated rather than papered over:** `raster_words` and `raster_program` are two paths
over a shared descriptor set, so the length annotation catches framing drift but not a wrong word inside
a correctly-sized body — the hand-word pins and the goldens cover that. The DSL will have produced
exactly two programs when this parcel merges, both of which already existed; its generality is Parcel
D's evidence to produce, not A's.
