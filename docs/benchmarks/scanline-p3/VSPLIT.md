# Vscroll-split lowering — per-layer vertical depth, and the two-writer ruling

**Parcel:** Scanline P3, Phase 1, Task 11 (`docs/superpowers/plans/2026-08-20-scanline-p3-walker-mechanisms.md`)
**Branch:** `p3/t11-vscroll-split`
**Design:** §2 — per-layer vertical depth is mid-frame whole-plane VSRAM changes at layer
boundaries, "lowered to the existing vscroll-split raster op (`fx_vscroll_split` family). Each
boundary with a distinct v-factor is one raster fire, priced in axis 4."

**What landed:** the LOWERING — a per-layer attachment, its guards, the act-to-screen line
derivation, the fold into fires, the two-writer ruling as both a refusal and a measured
precedence, and the instrument that holds the precedence.
**What did not land, deliberately: adoption.** No shipped scene authors a split. Visible
vertical depth on the OJZ scenes is the owner's content pass; this parcel's surface is the
mechanism. That is why all four canonical images are byte-identical (§6).

---

## 1. The authored model

```
layer(world_y: 112, fa: FACTOR_1, fb: FACTOR_1_4, vsplit: SceneVSplit.At($0043))
```

reads as: from this layer's top down, Plane B's whole-plane vertical scroll is `$0043`.

`SceneVSplit` is the fourth attachment enum in `engine/level/scene_dsl.emp`, and the only one
in the model that lowers to a **raster program** rather than to a band record. It reaches no
`band_entry` field at all, which is why it cannot move a config byte.

**The lowering is a call, not a copy.** `scene_vsplit_fires(s)` walks the scene's real layers
and, for each one carrying a split, calls `fx_vscroll_split(line, offset)` — the preset that
has existed since Parcel C1 and was until now reachable only by hand from a game's effects
module. The op, the command longword, the solved blanking spin, the landing check, the density
guard and the axis-4b HInt total all belong to `raster_dsl` and are reached by calling it.
There is no second encoder.

The result composes: `compose([scene_vsplit_fires(s), ...])` merges fires that land on the same
line, and `patchable(scene_vsplit_fires(s), ch:, lo:, hi:)` is how a split would follow a world
anchor instead of a static top. Neither is the fold's business.

## 2. Three spaces, and where the fire line comes from

A layer top is authored in ACT pixels. `scene_plane_line()` (Task 7) maps that to a PLANE line.
Step 4a maps a plane line to a SCREEN line every frame as `plane_line - (Vscroll_BG mod 512)`.
A baked raster fire needs the third space at **comptime**, and the only scenes where that is
possible are exactly the ones the two-writer ruling leaves legal:

```
screen = scene_plane_line(s, wy) - v_offset          (v_factor == 15, the lock sentinel)
```

because on a locked plane `Vscroll_BG` is pinned at `v_offset` (`parallax.emp`'s `.v_locked`
arm: "locked: BG = vOffset (static, ignores camera + lerp)"), a scene constant. For the
eighteen shipped locked scenes — `v_offset 0`, identity plane mapping — that is simply the
authored top, which is why their tops (0/32/80/112/160) have always read as screen lines.

`scene_vsplit_line()` repeats the lock test rather than trusting `scene()`'s: `Scene { .. }`
type-checks and skips every constructor guard, and this is where such a value stops. The
SCREEN-LINE RANGE is deliberately not re-checked — `fire()` owns 3..223 and every fire this
lowering builds goes through it, so a second range guard could never fire on its own.

## 3. The two-writer ruling

Plane B's vertical scroll word (VSRAM entry 1) has had two writers all along:
`Parallax_Step5_Vscroll` computes it in VBlank and `Vscroll_Write` ships it at frame top, while
a vscroll-split fire writes it mid-frame from the HBlank handler. Before this task the
collision was unauthorable — the split was reachable only from a game's effects module, which
knows nothing about the scene. **Lowering makes it authorable, so the ruling ships with the
lowering.** It has two halves.

### 3a. REFUSED — two ensures in `scene()`, both red-first

| Case | Why it cannot be resolved | Verbatim first line of the diagnostic |
|---|---|---|
| `v_factor != 15` (camera-tracked plane) | the VBlank value is a function of `Camera_Y`; the split carries ONE baked scroll value at ONE baked fire line, and that line is a screen line only while `Vscroll_BG` is constant | `scene(): a layer authors vsplit: At(..) while this scene's Plane-B vertical scroll TRACKS THE CAMERA (v_factor 3; 15 is the lock sentinel).` |
| `v_deform: Columns(..)` (per-column mode) | with VDP reg `$0B` bit 2 set, entry 1 is **plane B of column 0**, not the plane; `Vscroll_Write` ships the whole 80-byte column buffer by DMA, so a whole-plane mid-frame write moves one 16-px column of forty | `scene(): a layer authors vsplit: At(..) while this scene attaches a per-column V-deform table (SceneVDeform.Columns).` |

Both live in `scene()` rather than in the fold, deliberately: a scene that authors a split and
never calls `scene_vsplit_fires()` would otherwise carry an unadjudicated collision. Every
scene is constructed; not every scene is lowered.

### 3b. PRECEDENCE — for what remains legal, and it is measured

> The VBlank writer governs screen lines 0..N. The mid-frame write governs N+1..223, where N is
> the FIRE line and the authored screen line is N+1. And it does not accumulate: `Vscroll_Write`
> re-asserts the base every VBlank, so the split is a per-frame transient delta over a value
> the other writer owns outright.

That is renderable truth rather than a convention: the two writes happen at different times in
the same frame and the beam has already passed rows 0..N when the second lands, so each row is
drawn under exactly one of them. §4 is the measurement.

## 4. The instrument — `tools/vsplit_landing_gate.py`

**A differential between two split lines, never a picture compared with a description.** Two
programs identical but for the line they fire on (112 and 140) must render:

| rows | expected | what it proves |
|---|---|---|
| 3 .. 111 | IDENTICAL | a mid-frame write has no reach upward — the VBlank writer owns the top |
| 112 .. 139 | DIFFERENT | the mid-frame write governs the band between the two splits |
| 140 .. 223 | IDENTICAL | both fixtures now hold the SAME absolute scroll: the disagreement closes |

The third band is what makes it non-vacuous. A probe reading a constant, a stale capture or a
post-hoc end-of-frame render satisfies none of the three.

**What it installs is what the lowering emits.** Fixture A's words come from
`raster_cost_probe.program_words` (the wire transcription pinned to `raster_dsl.emp` by
`tools/test_raster_wire_pin.py`) and are then checked against the ROM image of `OJZ_TestVsram`,
15 words at `$012FA0`. The comptime end of the same chain is `OJZ_VSRAM_VIA_SCENE` (§5). So
what runs on the emulator is, byte for byte, what `layer(vsplit:)` lowers to.

### Measured, 2026-08-20, oracle-aether (`emulator/scanlines`, `source == "raster"`)

```
  setup  fixture A == OJZ_TestVsram @ $012FA0 (15 words)
  PASS  band width == authored split spacing: 28 rows differ; splits are 28 rows apart
  PASS  the disagreement is ONE contiguous band at the landing row: 113..140
  PASS  landing row is the authored line +/- the instrument's row resolution: bias 1
  PASS  VBlank writer governs the rows above the split: 0 of rows 3..111 differ
  PASS  the split does not accumulate frame to frame: the same 28 rows one frame on
  note  82 rows of the SAME fixture moved between the two frames — background animation
```

**The landing bias is 1 on this server and 0 on oracle, and that is the instrument, not the
engine.** `fire()` schedules an event authored at screen line M on fire line M-1 so its writes
land on M (the N+1 model). oracle-aether renders a row atomically at its start — the documented
limit is that a landing resolves to ±1 scanline and the early edge is not observable — so a
write issued in line M-1's blanking is timestamped after row M has been emitted and first shows
on M+1. On oracle (Exodus-derived, VSRAM consulted continuously) the same program measured the
first differing pixel row at exactly 112 (`docs/benchmarks/effects-p3/GATE-EVIDENCE.md`). The
two readings differ by precisely the instrument's own resolution.

So check 3 is a **band, not an equality**: bias ∈ {0,1}. The fact being defended is that the
split lands on the authored line to within one row, and a fire scheduled at M instead of M-1
reads as bias 2 and fails — which is what the off-by-one poison demonstrates.

**Transience is a differential too**, because the frozen scene is not static (BgAnim and
palette cycling keep ticking: 82 rows of one fixture move between two frames). Accumulation
would move fixture A's rows *away from* fixture B's; animation moves both identically. So the
assertion is that the band is the SAME band one frame later, not that a fixture is unchanged.

### Poisons (red-first, both exit 1)

| `--poison` | what it installs | measured |
|---|---|---|
| `line` | fixture A at 140, where B already is | band collapses to 0 rows; checks 1-3 fail |
| `offbyone` | fixture A one line lower (113) | band narrows to 27 rows starting at 114, bias 2; checks 1-3 fail |

The coarse one proves the band comes from the split at all; the off-by-one is the one that
matters, because the claim under test is a one-row fact and a gate has to be shown resolving
one row.

**A third poison was tried and discarded** — writing `$0040`, the documented pixel-invisible
shift (OJZ's trunk band repeats every 64 px). It is invisible only relative to a base that is
itself a multiple of 64, and at this gate's pinned camera the VBlank base is 466, so `$0040`
bands perfectly well and the poison passed every check, correctly. The reasoning is recorded in
the tool so nobody reinstates it without re-deriving the base.

The gate rides `tools/effects_gates.py` (registry row `vsplit_landing`, its own segment, the
`GATE_EMU_BUDGET` wedge timeout). It boots oracle-aether rather than oracle_gui, like
`warp_mailbox`, and manages its own four short server runs.

## 5. The acceptance proof — byte identity against the hand-authored twin

`Scene_VSplitWitness` (`games/sonic4/data/effects/ojz_scenes.emp`) re-expresses the shipped
`OJZ_TestVsram` program — one fire, screen line 112, Plane-B scroll `$0043` — through the new
attachment. `OJZ_VSRAM_VIA_SCENE` (`games/sonic4/data/effects/ojz_effects.emp`) then compares
the lowered words against `OJZ_VSRAM_HAND`, the hand-derived wire twin that shares no symbol
with the encoder, plus a length check (first_mismatch returns -1 on a prefix) and the
pal_dirty_mask check.

Both are `const`s: the proof costs zero ROM bytes in all four shapes.

**Red-first, both axes of the lowering:**

| perturbation | diverges at |
|---|---|
| witness offset `$0043` → `$0044` | index 12 — the scroll value word |
| witness top 112 → 120 | index 1 — the first arm word |

And three more guards, each proven by making it fail:

| guard | poked | diagnostic |
|---|---|---|
| `layer()` split range | `At(512)` | `vsplit: At(512) is outside the Plane-B span (0 .. 511)` |
| ascending split lines | tops 112 then 100, both split | `layer 1's vertical split lands on screen line 100, which is not below the previous split's` |
| the empty fold | witness with no `vsplit:` | `this scene has no layer carrying vsplit: At(..) ... would return an EMPTY fire list` |

The camera-tracked poison also fires `scene_vsplit_line()`'s own back-door guard, so both
layers of that ruling are live.

## 6. Byte accounting

Four canonical shapes, before and after, built with the full verification lanes:

| shape | before | after |
|---|---|---|
| `s4.bin` | `060401e4` | `060401e4` |
| `s4.debug.bin` | `0dbaa80f` | `0dbaa80f` |
| `demo.bin` | `c708b114` | `c708b114` |
| `demo.debug.bin` | `dec88cc1` | `dec88cc1` |

Byte-identical, deb2 appendix included: everything this task adds is comptime (attachment,
guards, fold, two zero-byte proofs) or lives in a Python tool. Lanes: `s4lint` clean, pytest
tools 1180 passed / 3 skipped, `effects_budget_check` 31 code-derived rows, `emp_expect_fail`
25/25. `SIGIL_WARNINGS=full`: 39 unreachable modules, the same explained set — none of
`scene_dsl`, `ojz_scenes`, `ojz_effects` is among them, and the red-first runs prove the
guards elaborate directly.

## 7. Axis 4a/4b — the ledger already owns this, and one finding

**No parallel cost estimate was built**, per the plan's Step 4. The ledger's fire costs ARE
`fire_cost_cycles` summed over the lowered program, inside `raster_program()`'s
`check_hint_total`, and the lowered fires reach it as ordinary fires.

**Measured that they do.** With the axis-4b reservation temporarily shrunk so the ensure fires
(and restored afterwards), the same two-fire pad reports:

```
without the lowered fire:   this program's 2 fires cost  640 model cycles
with it:                    this program's 3 fires cost 1264 model cycles
```

The count goes 2 → 3 and the total by exactly **624** cycles — which is also the whole modelled
cost the tree reports for `OJZ_TestVsram` itself, the program this lowering reproduces. A
lowered split fire is counted, at the price the DSL's own model gives it.

**FINDING, not a Task 11 defect: the axis-4b ensure cannot fire on any program
`raster_program()` accepts.** Two tighter guards dominate it:

* `check_density` requires `cost_i <= gap_i * 488`, and the cheapest fire class is ~320 cycles
  at one line of gap, so the most an all-sparse program can spend across screen lines 3..223 is
  about `320 x 221 = 70,720` cycles against the budget of `84,595`;
* `RASTER_BUF_SIZE` (128 bytes = 64 words) refuses any program past roughly twenty fires long
  before that — measured: a 205-fire pad failed with
  `raster_program: 827 words = 1654 bytes exceeds RASTER_BUF_SIZE (128)` while
  `check_hint_total` passed.

So axis 4b is a guard with no reachable subject in the sparse tier today. It is not vacuous in
the dangerous sense — it is a correct model of a real cost — but a reader should not count it
as protection. Booked here rather than fixed: changing it is a budget-model decision, not this
parcel's.

## 8. What this task deliberately did NOT do

* **No adoption.** No shipped scene authors a split; `Scene_VSplitWitness` is not in the
  registry and must not acquire a section binding.
* **No capability bit.** A `CAP_*` bit exists to elide ENGINE code for a game that does not use
  a mechanism. This lowering elides nothing — it emits a fire into a program the handler
  already interprets op by op — so a bit would be a span gate with no span.
* **No `scene_forces_per_line()` arm.** The five arms are about the HSCROLL pipeline; a vertical
  split touches neither the HScroll buffer nor the band tops, so an arm would be a false claim
  about the fill.
* **No second runtime mechanism.** Nothing was added to `engine/`'s runtime at all: the entire
  parcel is a comptime lowering plus a gate.
