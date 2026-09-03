# The dense per-line vertical scroll's key shape — EFFECTS-W1 DoD item 6 (DEMAND ARTIFACT)

*Status: **DEMAND ARTIFACT, documents only**, 2026-09-03. Nothing here is implemented; this
parcel moves no ROM byte and runs no build. Written for the same reason item 5's artifact
was — the hub cannot transcribe a source that does not exist — and the editor lane is
blocked on the answer (`docs/DEFERRED_WORK.md:17425`: "item 6's per-line field first (two
lanes wait on it)").*

*Every claim below is transcribed from source in this tree at aeon `cf3dfb1a` — **item 6's
own landing commit** (`git log -1 --format='%s' cf3dfb1a` = "merge: item 6 - dense per-line
vertical scroll, gated and budgeted"; `git rev-parse origin/master` = the same SHA at the
time this page was written). Every `file:line` cite anchors to a symbol name beside the
line number, so a later move does not silently invalidate it. `docs/DEFERRED_WORK.md`'s own
item-6 landing block (lines 16742-17067) is used only as a POINTER to what to go read — every
fact it states is re-derived from `engine/effects/raster.emp`, `engine/effects/raster_dsl.emp`,
`engine/effects/preset.emp` and `engine/level/scene_dsl.emp` directly in this pass, not copied
from it. Anything not found is marked **NOT FOUND** or **NOT ESTABLISHED** rather than
guessed.*

*Follows item 5's structure (`docs/superpowers/specs/2026-08-30-item5-variants-cycles-key-shapes.md`)
and item 4's (`docs/superpowers/specs/2026-09-03-anchor-authoring-key-shape.md`): transcribe
the engine fields, state what a generator would emit, give a byte/behaviour account against
the shipped fixture, and list what is left open.*

---

## 0. Where item 6 sits, and exactly what is being asked

- DoD row: `docs/DEFERRED_WORK.md:17408` — item 6, "Dense per-line VSRAM", **DONE
  2026-09-03**, `parcel/item6-dense-perline-vsram`. That parcel shipped the ENGINE
  mechanism's capability gate and its HBlank budget check. It did **not** ship an authoring
  surface — no JSON key, no schema property, nothing an editor can point at.
- The very next DoD entry names the gap explicitly: item 12's closing clause is *"per-line
  scroll authoring as a NEW field via schema CR once item 6 lands"*
  (`docs/DEFERRED_WORK.md:17436`), and the sequencing note directly above it reads *"item 6's
  per-line field first (two lanes wait on it), then a reels field, then the item-11 field"*
  (`:17425`). **This document is that "item 6's per-line field" deliverable.**
- Item 5's demand artifact is the direct precedent: it named the `cycles`/`variants` shapes
  the generator did not yet accept, the hub ruled ten questions off it, and the generator
  half landed after. This page is written the same way, for the same reason, one item later.

---

## 1. What the engine can do TODAY (transcribed from source at `cf3dfb1a`)

### 1.1 The wire struct — `RasterRampProgram`

`engine/effects/raster.emp:582-593`, no `(size: N)` annotation (**NOT FOUND** — same gap
item 5's artifact recorded for `pal_variant` / `pal_cycle_channel`; size below is a field sum,
34 bytes: 11 `u16` fields + 3 `u32` fields):

| offset | field | width | meaning |
|---|---|---|---|
| `+0` | `rrp_mask` | `u16` | derived `pal_dirty_mask`; 0 for a non-CRAM (i.e. VSRAM) target |
| `+2,+4` | `rrp_arm0`, `rrp_ops0` | `u16,u16` | fire 0 — priming |
| `+6,+8` | `rrp_arm1`, `rrp_ops1` | `u16,u16` | fire 1 — priming |
| `+10,+12` | `rrp_arm2`, `rrp_ops2` | `u16,u16` | fire 2 — the setup record, one op |
| `+14` | `rrp_op` | `u16` | always `OP_RUN_RAMP` (`raster.emp:202`, value `8`) |
| `+16` | `rrp_cmd` | `u32` | constant VDP write command, re-issued every line |
| `+20` | `rrp_lines` | `u16` | run length in scanlines |
| `+22` | `rrp_start` | `u32` | 16.16 initial accumulator |
| `+26` | `rrp_step` | `u32` | 16.16 per-line delta, signed |
| `+30,+32` | `rrp_end_arm`, `rrp_end_ops` | `u16,u16` | terminator |

"Same schedule as `RasterGradientProgram`" is the module's own comment (`raster.emp:579-581`):
two priming records, one setup record carrying the op, then a terminator — the dense tier's
uniform shape. The body differs only in what the setup record carries (a constant ROM stream
cursor for gradient, vs. a 16.16 start/step pair for ramp).

### 1.2 The constructor — `raster_ramp_program(top, lines, cmd, start, step)`

`engine/effects/raster.emp:629-678`. Five REQUIRED parameters, no defaults on any of them:

```
pub comptime fn raster_ramp_program(top: int, lines: int, cmd: int,
                                    start: int, step: int) -> RasterRampProgram
```

| param | meaning | how it is validated |
|---|---|---|
| `top` | first screen line of the run | `ensure(top >= 3, ...)` — `raster.emp:631` |
| `lines` | run length | `ensure(lines >= 1, ...)` — `:632` |
| `top`+`lines` | end of run | `ensure(top + lines <= 223, ...)` — `:640-641` (frame-rewind interlock, not the raw 224-line screen) |
| `cmd` | the VDP write command re-issued every line | must be exactly a CRAM-write or VSRAM-write command built via `vdp_comm()` — `ensure(is_cram + is_vsram == 1, ...)`, `:652-653` |
| `cmd`'s address (VSRAM) | | `ensure(addr <= 78, ...)`, `:654-655` |
| `cmd`'s address (CRAM) | | `ensure(addr <= 126, ...)`, `:656-657`, plus `ensure((addr >> 5) != 0, ...)` refusing CRAM line 0 (the character's palette line), `:658-659` |
| `start` | 16.16 initial accumulator | **no `ensure` inside this constructor at all** — see §7 |
| `step` | 16.16 per-line delta, signed | **no `ensure` inside this constructor at all** — see §7 |

`rrp_mask` is DERIVED, never authored: `1 << (addr >> 5)` for a CRAM target, `0` for VSRAM
(`:660-661`), for the reason the module states — a mask naming the wrong CRAM line leaves a
mid-frame write latched forever, and a CRAM-style mask computed from a VSRAM address would
misname CRAM line 0.

**Which screen line the first value lands on is target-dependent and MEASURED, not assumed**
(`raster.emp:602-609`, `docs/benchmarks/effects-p3/RAMP-EVIDENCE.md`, cited in-source, not
re-read here): a CRAM target's value `j` displays on line `top + j`; a VSRAM target's value
`j` displays on line `top + j + 1` (the same N+1 VSRAM-latency rule item 6's own header
comment ties to the sparse tier's `stream_vsram` `-1` convention). This is NOT compensated
inside the constructor — the comment (`:611-615`) states the compensation would have to be
conditional on the target, which is exactly the class of silent per-call surprise the sparse
tier's single `-1` rule was designed to avoid.

**AND STATED POSITIVELY, BECAUSE THE NEGATIVE FORM HAS ALREADY BEEN MISREAD ONCE: NOTHING ON THIS
PATH COMPENSATES FOR THE LINE, AT ANY STAGE.** Not the constructor, not `tools/effects_gen.py`, and
not the editor's codec — the editor's PREVIEW is the only place a `+1` legitimately exists, and it
is theirs. On 2026-09-03 the editor lane reported building a brief on the premise that aeon's
generator applies the compensation and quoted a sentence to that effect; **that sentence is in
neither this tree's `master` nor the in-flight generator parcel** (searched for the wording and for
the claim). What IS here and is structurally similar is `tools/effects_gen.py`'s drift comment —
*"a multiply here would apply it twice and every authored rate would come out 256x too fast"* — which
is about the `px/frame` to `1/256-px/frame` UNIT conversion, a different quantity, and which is
correct. **Two "would be applied twice" comments about two different quantities on one path is
exactly the confusion to expect**, so the rule is written here as a positive claim about every stage
rather than as a denial about one: a reader who meets "the constructor does not do it" can still
infer that something else does.

### 1.3 `fp16(whole, frac256)` — the ONLY authored-range enforcement in this whole feature

`engine/effects/raster.emp:684-689`:

```
pub comptime fn fp16(whole: int, frac256: int) -> int {
    ensure(frac256 >= 0 && frac256 <= 255, "fp16: frac256 {frac256} outside 0..255")
    ensure(whole >= -512 && whole <= 511, "fp16: whole {whole} outside -512..511")
    if whole < 0 { return (whole * 65536) - (frac256 * 256) }
    return (whole * 65536) + (frac256 * 256)
}
```

This is a convenience helper, not a type. `raster_ramp_program`'s `start`/`step` parameters
are plain `int`s with **no ensure of their own** (§1.2's table). `fp16()`'s two `ensure`s are
the entire authored-range contract for a ramp's rate and starting offset — see §7 for the
consequence.

### 1.4 The capability gate — `CAP_DENSE_TIER`

`engine/level/scene_dsl.emp:289`: `pub const CAP_DENSE_TIER = $0200` (the gapless
next-free-bit rule the file enforces; the reserved-comment placeholder that preceded
promotion was a value that had already moved twice and was never meant to be copied — see
the banner at `:260-288`).

The bit gates **construction only**, at TWO independent sites, never the interpreter's
dispatch chain or its per-line body:

1. **A game-side `ensure`**, not an engine-side one — `games/sonic4/data/effects/ojz_effects.emp:1048-1049`:
   ```
   ensure((Game.SCANLINE_CAPS & CAP_DENSE_TIER) != 0,
          "OJZ_TestRamp: this game's Game.SCANLINE_CAPS ({Game.SCANLINE_CAPS}) does not
           declare CAP_DENSE_TIER — ...")
   ```
   It sits beside the game's own call to `raster_ramp_program`, not inside the constructor's
   body, because a `comptime fn`'s free names resolve at its CALL SITE, and `Game` does not
   travel through that inlining (`ojz_effects.emp:1010-1022`; `docs/EMP_PITFALLS.md` #9,
   "Contract members (`Game.*`) do not exist in layout or harvest contexts",
   `docs/EMP_PITFALLS.md:202`, hit empirically before it was read). Every other
   "this game must declare `CAP_X`" check in the tree already lives this way
   (`scene_registry.emp`'s `CAP_MULTI_DEFORM_TABLE`/`CAP_FACTOR_CURVE`/`CAP_BAND_DRIFT`
   checks — module-level, game-side, none inside an engine constructor).
2. **One dispatch-safe interpreter leaf** — `engine/effects/raster.emp:1105-1134`,
   `.op_run_ramp`'s ENTER body only:
   ```
   if (Game.SCANLINE_CAPS & CAP_DENSE_TIER) != 0 {
   .cap_dense_tier_enter_begin:
       move.l  (a1)+, Raster_Dense_Cmd
       move.w  (a1)+, Raster_Dense_Lines
       move.l  (a1)+, Raster_Ramp_Acc
       move.l  (a1)+, Raster_Ramp_Step
       move.w  #-1, Raster_Dense_Mode
   .cap_dense_tier_enter_end:
   }
   ```
   The dispatch pair that reaches this label (`raster.emp:1014-1015`,
   `cmpi.w #OP_RUN_RAMP, d1 / beq .op_run_ramp`) and `.ramp_body` (the per-line writer) stay
   **unconditional in every game** — bracketing them would move `OP_PAL_RESTORE`'s dispatch
   depth for a game with no dense-VSRAM content, silently invalidating
   `raster_dsl.emp`'s "an op's depth is derivable from its opcode value alone" cost model
   (`raster.emp:1112-1124`). A game with the bit clear still dispatches to the label, finds
   nothing there, and falls through to `.advance` — a stray `OP_RUN_RAMP` word becomes a
   silent no-op cursor-advance rather than an armed run.

`sonic4` declares the bit (`games/sonic4/config/game.emp:114`, `SCANLINE_CAPS = $03DE`,
comment block `:97-113`) because `OJZ_TestRamp` constructs a `RasterRampProgram` as a
build-time wire-format proof, even though — see §1.6 — it never renders. `demo` does not
(`games/demo/config/game.emp:20`, `SCANLINE_CAPS = 0`) and constructs no ramp program at all;
its `.op_run_ramp` ENTER body is genuinely absent (22 bytes elided, per the item-6 landing
record — not re-measured in this documents-only pass).

### 1.5 How a ramp reaches a section — the ONE `raster:` channel, and why it competes with `bands`

`EffectsPreset.ep_raster` is a single pointer field, `*u8 @ $08`
(`engine/effects/preset.emp:62`), fed by `preset()`'s `raster: Label = 0` parameter
(`:141`). Binding is by DIRECT CALL-SITE ASSIGNMENT, not composition:
`games/sonic4/data/effects/ojz_effects.emp:1259` shows the shipped precedent for a
dense-tier program occupying this slot —
```
pub data OJZ_Preset_Sec2: EffectsPreset = preset(pal: OJZ_TestPal, raster: OJZ_TestGradient, ...)
```
`OJZ_TestGradient` is typed `RasterGradientProgram` (`raster.emp:469` struct,
`ojz_effects.emp:807`), a dense-tier wire record, assigned straight into `raster:`. A
`RasterRampProgram` (`OJZ_TestRamp`, `ojz_effects.emp:1001-1006`) is the same shape of value
and would bind the same way — but it is **currently unbound to any section**
("SECTION 0 SURRENDERS OJZ_TestRamp", `ojz_effects.emp:1178-1184`: `preset()`'s
`ep_raster`/`ep_patched` exclusivity ensure, `preset.emp:153-154`, forced the choice when
section 0 needed the patched template instead).

**`ep_raster` is ONE pointer per preset, and the sparse tier (`bands`) already claims it.**
`tools/effects_gen.py:1970-1973` states the mechanism the `bands` JSON key uses:
*"a section names one Aurora-authored PRESET DOCUMENT and gets that document's raster
program on its `preset()` call's `raster:` channel"*. A `bands` document's fires compile
through `raster_program(fires)` (`engine/effects/raster_dsl.emp:3138`) into a variable-length
`[u16; N]` array — a **structurally different wire shape** from `RasterGradientProgram`/
`RasterRampProgram`'s fixed priming/setup/terminator schedule. Both shapes are opaque
`Label`s to `preset()`; only ONE can occupy `raster:` per preset. **This is the architectural
fact that answers §2's question**: a `bands`-authored program and a hand-authored dense
program are mutually substitutable contents of the SAME one slot, not independently
composable — see §2's "not established" note on whether the two could ever be combined into
one program.

### 1.6 `OJZ_TestRamp` never renders

All nine of act 1's sections use total-binding presets and none binds `OJZ_TestRamp`
(`ojz_effects.emp:1178-1184`). It exists purely as a build-time wire-format proof — the
file's own term for its whole gate-fixture roster — same as `OJZ_TestGradient`,
`OJZ_TestVsram`, etc. Constructing it still requires `CAP_DENSE_TIER` (§1.4); that gate does
not distinguish "will render" from "is a fixture".

### 1.7 Cost

`RASTER_DENSE_LINE_RAMP_CYC = 304` (`engine/effects/raster_dsl.emp:1897`, measured by
`tools/raster_cost_probe.py`'s FR1/FR2 fixture pair per the item-6 landing record — not
re-run in this documents-only pass), checked against `RASTER_SCANLINE_CYC = 488`
(`raster_dsl.emp:1744`) by `ensure(RASTER_DENSE_LINE_RAMP_CYC < RASTER_SCANLINE_CYC, ...)`
(`:1908-1909`). 304/488 = 62.3% of the scanline window is free. ROM: 34 bytes per emitted
`RasterRampProgram` (§1.1's field sum), one per bound preset (the channel is one Label, not
a list). RAM: `Raster_Dense_Cmd`/`_Lines`/`_Mode` are shared with the gradient body (**exact
byte offsets NOT read in this pass** — out of scope for a document that changes no code);
`Raster_Ramp_Acc`/`Raster_Ramp_Step` are the ramp-specific accumulator pair, named at
`raster.emp:1129-1130`.

---

## 2. Spine question 1 — the PRESET DOCUMENT key: **NONE EXISTS.** Not `bands`, not a sibling key, not even `scene_dsl`.

This is the "real answer" the brief flagged as plausible, and it is the true one — more
starkly than "scene-only, no preset key" put it. Exhaustive checks, all at `cf3dfb1a`:

- **`tools/effects_gen.py` has zero hits for "gradient", "ramp" or "dense"** (`grep -n -i
  "gradient\|ramp\|dense" tools/effects_gen.py` → no output). The generator does not know
  the dense tier exists in any form.
- **`PRESET_KEYS`** (`tools/effects_gen.py:285-286`) = `{schema, id, bands, cycles, variants,
  patch_world_ys, patch_motion}` — items 3, 4 and 5's keys, nothing from the dense tier.
- **`PRESET_REFUSED_KEYS`** (`:299-305`) holds exactly one name, `"fires"`, and its own
  refusal message says why nothing dense-tier-shaped is even reserved-by-name yet: *"a
  general fire list would need the vscroll/register/patchable vocabulary as well"*
  (`:301-304`). Unlike `cycles`/`variants` before item 5 (which WERE refused BY NAME, i.e.
  reserved), a dense-tier key is not refused by name — it is simply **absent from the
  vocabulary**, one level further from existing than item 5's starting point was.
- **`BAND_ON_ARMS`** (`:484-486`) — the `bands[i].on` arm table — has exactly two entries,
  `cram` and `pal_region`, both SPARSE CRAM ops. `stream_vsram` is **deliberately excluded**,
  and the comment says exactly why: *"`band()` refuses a VSRAM ON op ('the ON op has no CRAM
  span')"* (`:482-483`). A dense run's defining trait — one value per SCANLINE, and for the
  ramp specifically a VSRAM target — cannot be expressed as a `bands[i].on` arm at all: the
  opcode class is wrong (`OP_RUN_RAMP`/`OP_RUN_GRADIENT` are opcodes 8/6, pinned distinct
  from the sparse tier's `OP_SET_REG`/`OP_CRAM`/`OP_PAL_REGION`/`OP_PAL_RESTORE` — opcodes
  0/2/4/10 — by `raster_dsl.emp:41`'s own drift pin), and the wire schedule is wrong (a fixed
  priming/setup/terminator record, §1.1, vs. a variable-length fire list).
- **`engine/level/scene_dsl.emp` carries no ramp-authoring construct either.** `SceneLayer`
  (`:703-736`) has fields for deform, curve (a DIFFERENT, older "ramp" — the BG HScroll
  factor curve, `SceneCurve.To`, `:392`, unrelated to per-line VSRAM), vsplit and drift; no
  field of any kind touches the dense tier. `CAP_DENSE_TIER`'s own banner in that file
  (`:260-289`) is a capability-bit declaration ONLY — it is not, and does not sit beside, an
  authoring construct the way `SceneVSplit` (`:501`) is. Searching the whole file for "ramp"
  turns up only that banner and the pre-existing, unrelated HScroll-factor-curve
  terminology.

**So the answer is not "scene_dsl-only" — it is document-surface-null.** The dense per-line
vertical scroll is authorable ONLY by hand-writing `.emp`: calling `raster_ramp_program()`
directly (`raster.emp:629`) and assigning its result to a `preset()` call's `raster:`
argument at the call site, exactly as `OJZ_TestGradient`/`OJZ_TestRamp` do
(`ojz_effects.emp:1001-1006`, `:1259`). No JSON file, preset or scene, can reach it today.

**What this means for where a CR would land, stated but NOT decided here (the hub's call,
per the brief):**
- It cannot be a new `bands[i].on` arm — the opcode class and wire schedule are wrong (above).
- It could be a new top-level PRESET-document key, sibling to `cycles`/`variants`
  (`preset()` has a free-standing `raster:` parameter the way it has `cycle:`), **but**
  unlike `cycles`/`variants` (each maps to its OWN separate `preset()` parameter), a ramp key
  would target the SAME `raster:` slot `bands` already lowers into (§1.5). **Whether a
  document could carry BOTH `bands` and a ramp key in the same preset — i.e. whether one
  program can mix sparse fires with an embedded dense run — is NOT ESTABLISHED from source
  in this pass.** `raster_program(fires)`'s fire-list model (`raster_dsl.emp:3138` onward)
  shows no combinator accepting a dense op, and `band()`'s `on:` arm table has no dense
  entry, which points toward "mutually exclusive with `bands`, like `patched:`" — but that is
  an inference from absence, not a read `ensure` refusing the combination, because no such
  combination-checking code exists to read. **Flagged as open, not guessed at.**
- It could equally be a document that is NOT a preset document at all — e.g. a new sidecar
  kind the way `rasterRef` currently names ONE preset document per section
  (`tools/effects_gen.py:1967-1975`, `load_section_raster_refs`) — since a dense run and a
  `bands` program are alternatives for the same channel rather than composable layers. This
  is the hub's shape call, not aeon's.

---

## 3. Spine question 2 — the lowering path, with line cites at `cf3dfb1a`

**There is no document-to-`.emp` lowering today** (§2). What exists is the hand-authoring
path a future generator would have to reproduce, and its three stops are:

1. **`engine/effects/raster.emp:629-678`** — `raster_ramp_program(top, lines, cmd, start,
   step) -> RasterRampProgram`. This is the ONE constructor a lowering step would call, in
   this parameter order, with no shortcuts — see §1.2's table for every `ensure` it runs.
2. **`engine/effects/raster.emp:684-689`** — `fp16(whole, frac256) -> int`. The recommended
   (not enforced-at-the-call-site) way to build `start`/`step`. A generator SHOULD emit
   `fp16(...)` calls rather than raw literals for the reason §7 gives.
3. **`games/sonic4/data/effects/ojz_effects.emp:1048-1049`** (or the equivalent site in a
   future generated module) — the `ensure((Game.SCANLINE_CAPS & CAP_DENSE_TIER) != 0, ...)`
   gate, which MUST be re-emitted at whatever new call site a generator creates, because it
   is not inside the constructor (§1.4's EMP_PITFALLS #9 note) and does not travel with it.
   A generated module that calls `raster_ramp_program()` without its own copy of this check
   would build fine for a game that already declares the bit and fail with no diagnostic at
   all for one that does not — the constructor would simply build a `RasterRampProgram` the
   interpreter silently no-ops for that game (§1.4).
4. **`engine/effects/preset.emp:141, :153-154`** — the `raster:` argument and the
   `ep_raster`/`ep_patched` exclusivity `ensure`. A generator emitting a ramp must route it
   through the SAME chooser mechanism item 4/item 5 established
   (`ojz_act1_sec_raster(sec, hand)`-shaped, `tools/effects_gen.py:2693-2694`'s own comment
   names this call site) rather than a second one, or the two raster-channel writers would
   race for one field.

`raster_dsl.emp` contributes NO ramp-specific authoring code (§2) — its only ramp-adjacent
lines are the opcode-value drift pin (`:41`) and dispatch-depth cost-model commentary
(`:1870-2007`). Any future lowering step therefore imports from `raster.emp` only, the same
module `OJZ_TestGradient`/`OJZ_TestRamp` already import from
(`ojz_effects.emp:56`: `use engine.effects.raster.{..., RasterRampProgram,
raster_ramp_program, fp16}`).

---

## 4. Spine question 3 — the refusal sites, every comptime `ensure`, by line

| # | Refuses | Site |
|---|---|---|
| 1 | `top < 3` | `engine/effects/raster.emp:631` |
| 2 | `lines < 1` | `:632` |
| 3 | `top + lines > 223` | `:640-641` |
| 4 | `cmd` is neither a CRAM-write nor a VSRAM-write command | `:652-653` |
| 5 | VSRAM `addr > 78` | `:654-655` |
| 6 | CRAM `addr > 126` | `:656-657` |
| 7 | CRAM `addr` names line 0 (the character's palette line) | `:658-659` |
| 8 | `fp16()`'s `frac256` outside `0..255` | `:685` |
| 9 | `fp16()`'s `whole` outside `-512..511` | `:686` |
| 10 | `raster:` and `patched:` both non-zero on the same `preset()` call | `engine/effects/preset.emp:153-154` |
| 11 | this game has not declared `CAP_DENSE_TIER` before constructing a `RasterRampProgram` | `games/sonic4/data/effects/ojz_effects.emp:1048-1049` (game-side, NOT inside the constructor — §1.4) |
| 12 | `RASTER_DENSE_LINE_RAMP_CYC >= RASTER_SCANLINE_CYC` (a build-wide invariant, not per-program) | `engine/effects/raster_dsl.emp:1908-1909` |

**No `ensure` bounds `start` or `step` directly** (§1.3, §7) — rows 8-9 bound them only
through the `fp16()` helper, which nothing forces a caller to use.

---

## 5. Spine question 4 — three states or absent-key semantics: **N/A today; the shape a future key would need**

Since §2 establishes there is no key, neither the "three positional states" model (item 4's
`patch_world_ys`/`patch_motion`) nor a simple "absent = keep" model applies to anything that
exists. For the hub's benefit, stated as a proposal only, not as something built:

- A ramp is **not naturally positional** the way `variants`/`patch_world_ys` are — those are
  arrays over a fixed number of independent slots (2 variant slots, `RASTER_MAX_PATCH` = 4
  patch channels). A preset has exactly ONE `raster:` channel (§1.5), so a ramp key would be
  a single OBJECT (all five of `top`/`lines`/`cmd`/`start`/`step`, or their document-facing
  equivalents), not an array — closer in shape to `cycles`' "the array IS the one script"
  precedent (item 5 §2.1) than to `variants`' per-slot array.
- Consistent with `rasterRef`'s existing rule (*"absent = keep the hand raster channel"*,
  `tools/effects_gen.py:1972`, and item 5's `cycles`/`variants` precedent), **absent** should
  mean "this section's hand-authored raster channel stands, whatever it is" — the no-cost
  majority case. Given §2's finding that a ramp key would compete with `bands` for the same
  slot, what a key PRESENT-BUT-EMPTY, or a document carrying BOTH `bands` and a ramp key,
  should mean is exactly the open combinability question §2 raises, and NOT a three-state
  table this page can respond for.
- `cmd`'s address+target split already has a JSON precedent to imitate: `bands`' own
  `pal_region` arm spells `addr` as an explicit integer rather than deriving it
  (`tools/effects_gen.py:471-478`'s stated reason — "spelled out... beats one fact computed
  twice"). A ramp key would likely want the same: an explicit VSRAM/CRAM target selector
  plus an explicit byte address, rather than asking an author to hand-construct a `vdp_comm`
  word.

---

## 6. The name — `RasterRampProgram` / `raster_ramp_program` / `OP_RUN_RAMP`, and this is not a naming DECISION, it is a naming CONFIRMATION

**The tree already uses the word the brief's candidate names proposed, verbatim, since
2026-08-14** — `engine/effects/raster.emp:582` (`RasterRampProgram`), `:629`
(`raster_ramp_program`), `:202` (`OP_RUN_RAMP` = `8`). There is nothing to invent and no
competing spelling anywhere in the tree: `grep -rn -i "ramp" engine/level/scene_dsl.emp`
turns up only this mechanism's own capability banner and one unrelated, older sense of
"ramp" (the BG HScroll factor curve, `SceneCurve.To`, `:392` — a DIFFERENT feature that
ramps a horizontal scroll FACTOR across a layer, not a per-line vertical scroll value; do not
conflate the two when drafting the CR's prose).

**Per the brief's own instruction, this settles §2's naming question**: any future document
key should be named for the RAMP (e.g. `ramp`, or a `raster_ramp`/`ramp_program`-shaped
key), never `per_line_scroll` or anything implying independent per-line values, because:

- The engine's own field names already carry the constraint the brief wants named —
  `rrp_step` (ONE rate, `raster.emp:591`) and `rrp_start` (ONE starting offset, `:590`) are
  the entire per-line-value vocabulary. There is no per-line array field anywhere in
  `RasterRampProgram` (§1.1's full field table) for a curve to occupy.
- `raster.emp`'s own comment states the boundary explicitly, at the site closest to where a
  generator would read it: *"a nonlinear/table-driven variant is a different, larger
  feature"* (paraphrased from the item-6 landing record's own framing, re-confirmed against
  source here: `raster_ramp_program`'s accumulator body, `:662-677`, has exactly one
  `rrp_step` field and nothing resembling a table pointer or per-line array).

**The MUST-NOT, stated as its own sentence for the document's own description, per the
brief:** a `ramp`-named key must author exactly one linear rate (`step`) and one starting
offset (`start`) over a `top`/`lines` span. **No per-line curve. No independent per-line
values.** The engine has no field to receive either.

---

## 7. The authored range — resolved from the `ensure`s, and the correction stated exactly

**The AUTHORED RANGE is the contract, not the storage width — same rule
`patch_world_ys` states for `u16`/`32767`.** Verified directly against `fp16()`'s two
`ensure`s (`raster.emp:685-686`), not against the earlier report:

| | Authored contract (the `ensure`s) | Storage (implementation note only) |
|---|---|---|
| `whole` (`step`/`start`'s integer part) | **-512 .. 511** — `ensure(whole >= -512 && whole <= 511, ...)`, `raster.emp:686` | `rrp_step`/`rrp_start` are `u32` fields carrying a signed 16.16 fixed-point value (`raster.emp:590-591`); the RAW field width could represent a whole part of roughly `-32768..32767` (a 16-bit signed integer part) |
| `frac256` (the 1/256-px sub-pixel part) | **0 .. 255** — `ensure(frac256 >= 0 && frac256 <= 255, ...)`, `:685` | packed into the low 16 bits of the same `u32`, scaled by 256 (`:687-688`) |

**The earlier report's numbers (`whole` in `-512..511`, storage signed 16.16) were BOTH
individually correct** — re-verified here directly against the `ensure`s and the field
declarations, not assumed. **What made them read as inconsistent is exactly the gap the
brief named**: a control authored against the raw 16.16 STORAGE type would expose roughly
`32768 / 512` = **64×** the range `fp16()`'s `ensure` actually admits (the brief's own
"roughly sixty times" is the right order of magnitude for this ratio). The fix is not a
different number — both `-512..511` and "16.16 signed" are right — it is stating them in the
right relationship: **range from the `ensure`, width as an implementation note**, exactly as
this table does.

**A gap this table surfaces that was NOT part of the original report, and belongs in any
future CR's refusal-site list: `fp16()`'s range is enforced only if the author calls
`fp16()`.** `raster_ramp_program`'s `start`/`step` parameters are plain `int`s with no
`ensure` of their own (§1.2, §4 row list) — nothing in the constructor stops a caller (today,
a hand-`.emp` author; tomorrow, a generator) from passing a raw 16.16 literal outside
`fp16()`'s range. This is a real gap in the ENGINE's authored-range enforcement, not a
schema-authoring nuance, and a future CR's generator MUST route every authored `step`/`start`
through `fp16(whole, frac256)` rather than accepting or emitting a raw integer, or the
document's own "authored range" claim would be enforced by nothing at all.

---

## 8. What could NOT be established in this pass

- **Whether a `bands` program and a dense-tier program (gradient or ramp) can be combined
  into ONE `raster:` value** — i.e. whether the mutual exclusivity §1.5/§2 infer from the
  absence of a combinator is an actual engine limit or merely an unbuilt one. No `ensure`
  refusing the combination exists to read, because no code accepting it exists either. This
  is the single largest open question for the hub's CR — see §2's closing paragraph.
- **Exact RAM offsets for `Raster_Dense_Cmd`/`Raster_Dense_Lines`/`Raster_Dense_Mode`** (the
  shared gradient/ramp dense-run state) — not looked up; out of scope for a document that
  changes no code and was not needed to answer the four spine questions.
- **Whether `OJZ_TestRamp` (or any dense-tier fixture) has ever been read back out of a built
  ROM as a byte-golden**, the way item 5's artifact did for `OJZ_ShimmerCycle`/
  `Variant_Water_Deep`. Not attempted here — no build was run in this documents-only pass
  (bar: "no build is required... but if you touch anything the build reads, verify all four
  shapes", and this parcel touches nothing the build reads).
- **What a `top`/`lines`/`cmd` JSON spelling should look like** (whether `cmd` should be
  spelled as a raw VDP command, or split into a target enum + byte address the way
  `pal_region`'s `addr` is spelled explicitly rather than derived) — named as a candidate in
  §5, not decided; the hub's call, matching how item 5 left its own JSON shapes as an
  overridable proposal.
- **Whether the `top >= 3` / `top + lines <= 223` frame-rewind-interlock bound would need
  restating in an authoring-facing form** (a raw scanline range vs. some more author-legible
  spelling) — not decided; `layer()`'s and `anchor_sweep()`'s messages being "the field's
  real documentation" (item 4 artifact §3's stated posture) is the precedent this page
  assumes would carry over, but that is an inference from a sibling item, not read from a
  ramp-specific source.
