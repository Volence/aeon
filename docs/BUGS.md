# Known Bugs

Open defects with reproduction notes and any captured live-emulator evidence. Newest first.
(Distinct from `DEFERRED_WORK.md`, which tracks deferred *features*, not defects.)

---

## ⚠ EFX-10 — OPEN 2026-08-17, re-scoped 2026-08-17. Lane runs via the carrier backend (interim); the sigil-side fix is still open.

**Booked during Parcel R1 Task 8**, whose five band guards it was built to gate. The lane's
direct invocation is `sigil emp <poison> --root <aeon>`. That path
(`run_emp_program`, `sigil-cli/src/main.rs`) does **not** apply the two manifest rewrites
`sigil build` applies (`sigil-harness/src/native.rs`, `build_emp`):

```
publicize_helper_comptime(&mut manifest, COMPTIME_HELPERS)
normalize_helper_imports(&mut manifest, COMPTIME_HELPERS, &[])
```

Measured 2026-08-17, three failures deep, each blocking the next:

1. A poison naming `raster_program` gets `unknown function raster_program`. The helper globs are
   what put it in scope in an ordinary module.
2. Adding `use engine.effects.raster_dsl.*` fixes the NAME and not the guard: `raster_program`'s
   body resolves free names at the **call site**, and raster_dsl's own helpers (`fire_ops`,
   `arm_at`, `check_intervals`, `op_stream_words`, …) are private. A glob imports only `pub`
   items; `publicize_helper_comptime` is what makes them importable in the real build. Result:
   20+ `unknown function` errors *inside raster_dsl*.
3. The `use` also drags `engine.effects.raster` into the closure, which resolves
   `RASTER_MAX_PATCH` / `vdp_comm_reg` only through those globs, and its RAM labels only because
   `engine.ram` is reachable via the real build's synthetic entry. Seeding `engine.ram` from the
   poison then demands the build's `-D` interface values (`DEBUG`, `MAX_RING_BUFFER`,
   `COLLECTED_WINDOW_SLOTS`), which the lane does not pass.

**Task 7's "verified by experiment" claim is true only of a self-contained poison** — one whose
`ensure` names nothing outside itself. That is the shape it was verified with (CASES shipped
empty), and it is the shape no real guard poison can take.

**Current state (2026-08-17): the lane runs via the carrier backend** (temporary,
aeon-side, Fable-ruled 2026-08-17). `tools/emp_expect_fail.py` no longer invokes `sigil
emp --root` at all — it rewrites `games/sonic4/test/poison_carrier.emp` (a real module
already in the build's `use` closure, via one edge from
`games/sonic4/data/effects/ojz_effects.emp`) to each poison's body in turn and runs the
real `sigil build --native` invocation, which does apply `publicize_helper_comptime` /
`normalize_helper_imports`. All seven Task 8 poisons are gated this way (moved from
`BLOCKED_CASES` into `CASES` verbatim), plus a permanent sentinel case that fails the
lane loudly if the carrier ever falls out of the build's `use` closure. The five R1 band
guards are now protected by a gate, not only by review and this entry.

**The carrier is a workaround, not the fix — it is explicitly named for removal.** The
proper fix remains sigil-side: `--extra-entry <module>` on `sigil build`, appending the
poison to `synthetic_entry_src`'s `use` list so it elaborates inside the REAL profile
without any file's body being rewritten out from under it. (The alternative floated
earlier — giving `sigil emp --root` the same helper treatment plus a way to seed extra
reachability and the `-D` values — is the larger change; `--extra-entry` reuses the
existing real-build path instead.) The removal condition is named in the carrier's own
header comment (clean-not-bolted-on): the carrier file, its `use` edge, and the
rewrite-per-case mechanism in `emp_expect_fail.py` all retire together the day
`--extra-entry` lands.

---

## ✅ EFX-8 — CLOSED 2026-08-15 (Effects P3 Parcel P-b). A patched program renders again.

**Booked 2026-08-15**, found while re-deriving the tree for Effects Parcel P, and confirmed
independently by a review lens. This is the **EFX-1 successor**: EFX-1 recorded water surviving
exactly one crossing; total binding made it survive **zero**.

The patched path (`Raster_Buf_B`) has had no runtime observability since Parcel C2 merged:

1. `games/sonic4/test/ojz_scroll_test.emp:286-288` installs `OJZ_WaterRaster` in Init, so
   `Raster_Active_Buf` = `Raster_Buf_B`.
2. `Parallax_Init` seeds `Parallax_Prev_Sec_X/Y` to `$FF` (`engine/level/parallax.emp:126-128`), so
   `Parallax_CheckBoundary` — called at `ojz_scroll_test.emp:378`, **before** the patch call at
   `:384` — reports a crossing on Update frame 1.
3. `Effects_InstallPreset` reads `OJZ_Preset_Sec0`, whose `ep_patched` is 0
   (`games/sonic4/data/effects/ojz_effects.emp:540`), and stages the static `OJZ_TestRamp`
   (`engine/effects/preset.emp:212-224`).
4. `Raster_VBlank .copy_program` re-points `Raster_Active_Buf` at `Raster_Buf_A`
   (`engine/effects/raster.emp:491-494`).
5. From that frame on, `Raster_PatchWaterWorldY`'s liveness test (`raster.emp:892-894`) takes
   `.not_patched` **forever**.

**Why C2's gate did not catch it.** The declared deltas covered water becoming per-section; nothing
was measuring `Buf_B`, and the scroll test's own comment (`ojz_scroll_test.emp:282-283`) records
that no preset sets `ep_patched` — it anticipated a later section swapping to the Buf_A path, not
section 0's own preset doing it one frame after Init.

**Consequence for gates, not just for pixels.** Any raster gate phrased around "the water boundary"
measured nothing while this was open, and a broken patched-path implementation would have measured
identically to a correct one.

**CLOSED by P-b Task 7**, exactly as this entry anticipated: `OJZ_Preset_Sec0` now binds
`patched: OJZ_TwoChannel`, and by `preset()`'s exclusivity ensure section 0 surrenders its static
`OJZ_TestRamp` — a declared delta, not a regression. Observed rendering on oracle
(`s4.debug.bin` crc `2318eef6`) **after the first section crossing**, which is the exact frame at
which this defect used to kill it:

- `Raster_Patch_Tab` = `$000130FC` (non-zero), `Raster_Active_Buf` = `$FFFF8A22` (= `Raster_Buf_B`)
- `Raster_Buf_B[0..7]` = `0004 8A4D 0000 8A59` — the **predicted** arm words, not merely non-zero
- three absolute framebuffer row bands, both clamp directions, in
  `docs/benchmarks/effects-p3-p-b/GATE-EVIDENCE.md`

Two of the five reproduction steps above no longer exist at all: step 1's hand install and step 5's
`Raster_PatchWaterWorldY` were deleted in P-b Task 6. Step 4 survives and is now a **feature with a
live witness** — walking out of section 0 into section 1's static-raster preset leaves
`Raster_Patch_Tab = 0` and `Active_Buf = Buf_A`, which is `.copy_program`'s teardown working.

---

## ✅ EFX-9 — CLOSED 2026-08-15. `tools/effects_budget_check.py` was correct and was RUN BY NOTHING.

**Booked 2026-08-15** during Effects P3 Parcel P-b Task 9, and it is the reason EFX-5's
"gate-checked, which is precisely why it never drifted" claim above is **false**.

`tools/effects_budget_model.toml` read `raster_state_bytes = 288`. The shipped
`RASTER_STATE_SIZE` was **298** before this parcel touched it — a 10-byte drift, exactly the
size of the OP_RUN_RAMP cells (`Dense_Kind` 2 + `Ramp_Acc` 4 + `Ramp_Step` 4) added by an
earlier parcel that never updated the model. EFX-5 recorded this row as protected by the
`[symbols]` gate. It is not protected, because **nothing runs the gate**:

- `build.sh` does not invoke `effects_budget_check.py`. Neither does any tool script or CI.
- The only references to it in the tree are its own unit-test file and two comments in the
  model that describe the gate as though it ran.

The checker itself is **fine**, and that is the point — this is not a broken tool, it is a
correct tool nobody calls. Proved by inversion 2026-08-15: setting the row to 305 against a
real 306 prints `ram.raster_state_bytes: model says 305, engine/effects/raster.emp:RASTER_STATE_SIZE is 306`
and exits **1**; the correct value exits **0**. It would have caught the 10-byte drift on the
day it happened.

It was ALSO crashing rather than reporting, from the moment P-b put a helper constant into
`RASTER_STATE_SIZE`: its resolver read only the named module, so `RASTER_MAX_PATCH` (a
`*_dsl.emp` COMPTIME_HELPERS member, glob-injected into code modules by sigil) raised
`unknown constant` as an unhandled traceback. Fixed in P-b — the resolver now folds in sibling
`*_dsl.emp` constants, mirroring how sigil actually resolves those names. A gate that dies with
a traceback instead of a verdict is worse than one that is merely unrun, because a caller
wiring it in would have inherited a red build with no finding in it.

**CLOSED by wiring it into `build.sh`**, beside `s4lint` and under the same `NO_LINT` guard, so
the source gates share one escape hatch. P-b corrected the value (288 → 306) and repaired the
crash; the wiring followed immediately after as the remainder of Parcel B.

Proved build-fatal AND escapable, rather than assumed:

| model | code | result |
|---|---|---|
| 306 | 306 | `effects_budget_check: OK — 8 code-derived rows agree`, build completes, crc `4c4cac75` |
| 305 | 306 | `1 budget row(s) disagree with the shipped code`, build **exits 1** before assembling |
| 305 + `sonic4 --no-lint` | 306 | builds anyway, crc `4c4cac75` |

**The hatch invocation is not the obvious one.** `GAME` is positional (`$1`), so
`./build.sh --no-lint` parses the flag AS THE GAME NAME and dies with
`unknown --game '--no-lint'`. It must be `./build.sh sonic4 --no-lint`. Pre-existing
arg-parsing behaviour, recorded here because it is the first thing anyone reaching for the
hatch will hit.

---

## Effects suite defect ledger (EFX-1 … EFX-6) — booked 2026-08-14, Parcel C2

Surfaced by the Effects P3 design audits. Recorded here with their real status after
Parcel C2, because several were half-fixed or already fixed and the spec did not know.

### ✅ EFX-1 — FIXED. Water survived exactly one section crossing.
`Raster_InstallSection` read a NULL `sec_raster_table` as "keep current", so water
installed in the spawn area persisted into sections that never asked for it, rendering
at a stale screen line indefinitely. **Fixed by total binding** — `Effects_InstallPreset`
writes every channel, so a section without a patched template gets `Raster_Program_None`
and the water stops. This is delta D2 in `docs/benchmarks/effects-p3-c2/DECLARED-DELTAS.md`.
**⚠ EFX-8 above recorded the overshoot: the same fix drove the patched channel past "off" into
UNREACHABLE, so for a time no patched program rendered at all. Both are now closed — the fix was
real, the overshoot was the successor defect, and P-b's Task 7 restored the channel by giving a
section preset a `patched:` binding rather than by weakening total binding.**

### ⚠ EFX-2 — OPEN (deliberately). The cross-fade layer is unreachable.
`Palette_ArmFade` and `Palette_LoadCycle`'s fade sibling `Palette_DoFade` have no
callers; `Pal_Target` and `PAL_FADE_FRAMES` are dead in the shipped ROM. `EffectsPreset`
reserves `ep_transition` to claim it, and **no Parcel-C2 fixture uses it on purpose** —
wiring a cross-fade would have added a behavioural delta to a conversion parcel whose
gate is "behaviour-identical against a declared list". Left for a content parcel.
(Note `Palette_LoadCycle` itself is NO LONGER dead — `Effects_InstallPreset` calls it.)

### ✅ EFX-3 — FIXED. A count-0 cycle script left cycling ACTIVE.
Both `Palette_InstallCycleSection` and `Palette_LoadCycle` armed `PAL_ACT_CYCLE` BEFORE
reading the channel count, so a non-NULL script with zero channels exited with cycling
on. `Palette_Compose`'s `.cycling` arm then set `PAL_ACT_VARIANT_STALE` every frame,
re-arming the ~19,332-cycle (15.1%-of-frame) variant re-derive that `ff0720ff` had
recovered. Latent because the count-0 path was documented but never exercised — and
`Pal_Cycle_None` is exactly what exercises it, which is why the fix was sequenced first.
Verified on oracle in BOTH directions: pre-fix instruction order leaves `Pal_Active` bit
1 SET (`$12`), fixed order leaves it CLEAR (`$10`).

### ✅ EFX-4 — CLOSED 2026-08-15 (Effects P3 Parcel P-b), and it has a SUCCESSOR below.
It read: `Raster_InstallWater` copies a fixed `RASTER_BUF_SIZE` (128 bytes) from templates that
are 34-36 bytes, so ~94 bytes of adjacent ROM land in `Buf_B` past the terminator.

**Closed because its subject no longer exists and its scope no longer applies.** `Raster_InstallWater`
was deleted in P-b Task 6, and the copy that replaced it (`Raster_CopyPatchedTemplate`) reads only
**patched** templates — which `patched_program` pads to exactly 64 words before appending the patch
table at +128. The fixed 128-byte read is therefore fully defined for every template it can now
receive: the copy stops exactly at the table boundary, and the padding is what makes that true. Its
overflow half stays guarded by `raster_dsl.emp`'s `RASTER_BUF_SIZE` ensure.

**Its citations were stale in both directions**, which is why this is a close rather than a
carry-forward: the named subject was gone, and the site the over-read now actually lives at was
never named. See the successor.

**UPDATE 2026-08-16 (HInt schedule local-removal parcel): `Raster_CopyPatchedTemplate` — the proc
this closure's own rationale rested on — is now ALSO deleted.** There is no fixed 128-byte
template-body read anywhere any more. `Raster_BuildSchedule` (the replacement for both the
old `Raster_PatchAll` patcher and the deleted copy) reads the template's two priming records
verbatim (a fixed 5-word prologue: 1 header word + 2 [arm/op_count] words each) and then, per
authored record, copies exactly `rec_len` bytes starting at `rec_off` — both values read from the
patch table, which `check_rec_layout` (GUARD 10, `raster_dsl.emp`) proves at build time match the
emitted image. A short template is therefore not over-read by ANY fixed-size copy: the builder's
per-record copy length is the record's own authored length, not a buffer constant. This closure's
conclusion (no over-read on the patched path) still holds; only the mechanism that makes it true
changed. The static-program path this entry never covered is unaffected — see EFX-4b, still open.

### ⚠ EFX-4b — OPEN (successor to EFX-4). `Raster_VBlank .copy_program` over-reads SHORT STATIC programs.
**Booked 2026-08-15**, splitting off the half of EFX-4 that survived the deletion of its subject.

`Raster_VBlank`'s `.copy_program` path copies a fixed `RASTER_BUF_SIZE` (128 bytes) into
`Raster_Buf_A` from any staged **static ROM program**, and static programs are NOT padded —
`Raster_Program_None` is three words. So ~122 bytes of adjacent ROM land in `Buf_A` past the
terminator on every static install.

**Harmless today, for the same reason the original was**: the record walk stops at
`RASTER_OPS_END` and never reaches the junk. Booked rather than hot-fixed.

**It is strictly narrower than EFX-4 was**, and that is the point of splitting it: the patched
path is now provably fine (padding), so this is about the static path alone, and the fix — a
length word, or a bounded copy, or padding static programs the way patched ones already are — is
a different change against a different routine than anything EFX-4 ever proposed.

### ⚠ EFX-5 — was recorded FIXED, and the reasoning was WRONG. See EFX-9 above.
It read: "`tools/effects_budget_model.toml` reads `raster_state_bytes = 288`, and is
gate-checked via `[symbols]` → `RASTER_STATE_SIZE` — which is precisely why it never drifted,
while two ungated values beside it did." **The value HAD drifted** (288 against a real 298) and
the gate that was credited with preventing it is run by nothing. The row is corrected to 306 in
P-b; the wiring is EFX-9. The spec's other two complaints
(`full_line_fire_cost`, `sparse_tier_cycles_per_frame`) were likewise already renamed /
superseded. One prose residual was corrected; see the note there about why the `8358`
figure in the dense-tier comment is a legitimate DIFFERENTIAL and must not be swapped
for the newer numbers.

### ✅ EFX-6 — FIXED. The `Sec` equ blob could go stale silently.
`sigil/crates/sigil-harness/src/test_support.rs` supplies `Sec_*` equs to standalone port
oracles, and nothing cross-checked them against `harvest_engine_struct_offsets`, so a
renamed field left it supplying a DEAD equ. A test now asserts the two name sets agree.

---

## ⚠ OPEN — `.lst` symbol addresses are 4 bytes stale for `boot_head` in the DEMO shapes (2026-08-14)

**A sigil listing/image skew, sound-off shapes only.** `demo.lst` reports
`BootData : 392`, `BootData_VDPRegs : 3AC`, `Z80_Sound_Start : 3C8`, but the emitted image
places them at `$38E` / `$3A8` / `$3C4` — a consistent **-4** on `boot_head` symbols in both
demo shapes. `BootData_PostBlob` (`$3F8`) matches exactly, and the s4 shapes are not skewed;
pc-relative references in the image resolve to the IMAGE addresses, so the ROM is correct and
only the listing lies.

**Why it matters:** anything consuming `.lst`/deb2 addresses for that section reads 4 bytes
off — the MD Debugger's symbol view, and any evidence-gathering that resolves a demo boot
symbol before poking it. The boot-cursor investigation below hit exactly this class of trap
from the other direction.

**Suspected mechanism:** the same `packed_align_of` provisional-pin machinery that owns
inter-section alignment, reporting a padded base the packer did not actually emit. Wants a
sigil ledger row. Found by static whole-ROM disassembly diff during the
`boot-cursor-section-seam` hunt; not chased, because the ROM bytes are right.

---

## ✅ FIXED — the RELEASE shape of both games rendered NOTHING (2026-08-14, aeon `f2adf85c` / sigil `7e1b70dd`, chain 116)

Kept as a booked entry because it was **pre-existing and long-lived**, and because of what it
says about the verification posture: every gate was green the whole time.

`boot.emp` copied the Z80 blob with `move.b (a5)+,(a0)+` and then kept walking the SAME `a5`
into `boot_tail`'s data. The blob ends a *section*, and the chainer aligns `boot_tail`'s base
per `sigil native.rs::packed_align_of`, so a pad opens whose width is a function of blob
length: **4 bytes in DEBUG, 6 in release**. Both shapes read the pad as their PSG-silence
bytes. Debug's skew was survivable (the words still paired up). Release's put `$0000` in the
auto-increment slot; the VDP takes `$0000` as a command's FIRST word, stranding the
control-port flip-flop — after which **no VDP write in the entire ROM ever landed again**:
blank backdrop, VRAM all zeros, CRAM at power-on `$0EEE`, in BOTH games, while game logic ran
on normally. Fixed by naming the label (`lea BootData_PostBlob(pc), a5`).

**Three lessons worth more than the fix:**

1. **Every shape must actually be BOOTED.** This survived because verification runs on DEBUG.
   The pre-merge commit `b2bb1c5a` is equally blank; so, almost certainly, is a long run of
   ancestors. `refreeze --check`, the 3711-test suite and the byte goldens were all green
   throughout — none of them looks at a screen.
2. **The guard existed and checked the wrong property.** `boot_data.emp`'s
   `ensure((Z80_SOUND_SIZE & 1) == 0)` called itself "THE NET the review asked for and never
   got". The thing that shears the walk is the alignment PAD, and a pad is even — so the
   parity check passed happily in both shapes. Another entry for the
   gate-measures-something-adjacent-to-its-subject file.
3. **A cross-section `(a5)+` walk is not a layout-independent construct.** `packed_align_of`'s
   own doc comment records that a repin can change a section's alignment quantum with no
   source change at all (it happened to the SFX section in `2c49f538`), so no `ensure` could
   have pinned this durably — only naming the label removes the hazard.

Evidence: `docs/benchmarks/boot-cursor-seam/AB-EVIDENCE.md`.

---

## ⚠ OPEN — the replay net was NOT verified for the blanket-register-restore parcel (2026-08-14)

The parcel merged with every other gate green (four build shapes, sigil `3711/0`, refreeze
chain 115, a three-checkpoint emulator A/B against master) but **the replay net was not
validly measured**, and that is recorded here rather than left implied by silence.

**Why it could not be measured.** Arming playback by hand — write `Input_Source = 1` and
`Replay_Ptr = <fixture> + 20` (`HEADER_LEN`), then run — is **not reproducible**. Three
attempts on the SAME branch ROM (`crc=c13412fc`) gave three different actual hashes at the
desync trap:

| arming point | actual `d0` |
|---|---|
| after ~20 s free-run, then pause | `0xBD37D0BF` |
| at the first `Input_Tick` after reset (breakpoint `$2602`) | `0x10023248` |
| armed too early | write wiped — state init zeroes `Input_Source` AND `Replay_Ptr` |

So the fixture expects a **specific starting game state**, and the arming recipe for it is not
written down anywhere found. `docs/superpowers/notes/2026-08-13-replay-net-restamp-ab.md` §3
documents the harvest loop but assumes playback is already running.

**What IS known.** Under comparable arming, branch and master both trap at **exactly tick 735**
(`d1 = 0x2DF`) with the **same expected payload** (`d2 = 1D375066`) — i.e. the pre-existing
lens-sweep debt below, not a new divergence. Read `d0` at breakpoint
`$engine.replay$Input_Tick$desync` (`$26A2`, both builds) rather than off the crash screen: the
MD Debugger's 8x8 font is not reliably readable at that density (an OCR of master's dump gave
`DD37D08F` where the register actually held `0x0D37D0EB`).

**Grounds for merging anyway:** the parcel changes VDP register writes only — the blanket
flush, DEBUG-shape asserts, and one deleted dead `move.w #$8F02, VDP_CTRL`. Nothing touches
player RAM, and `engine/system/replay.emp:7-16` states the hash is address-free by
construction, so the RAM-layout shift from deleting `VDP_Dirty_Mask` cannot move it.

**To close:** find or reconstruct the arming protocol, then re-measure. This is entangled with
the tick-735 re-stamp below — both want the same missing recipe.

### ✅ CLOSED 2026-08-14 — measured with the headless runner; the net was GREEN all along

The missing recipe was never found because it was not needed: the **headless replay runner**
(`oracle-next/target/release/replay_runner`, wired as `test.sh` section 8 by `b64b896e`, which
landed a few hours AFTER this entry was written) arms deterministically and grades the run
itself. Measured on it:

| ROM | `ojz_fixture` | `ojz_slide_fixture` |
|---|---|---|
| master post-boot-fix `3cffc29b` | **PASS** — 1721 ticks, `Replay_Done=$FF` | **PASS** — 2350 ticks |
| pre-boot-fix `c13412fc` (this entry's ROM) | **PASS** | **PASS** |

Both fixtures run to their declared end, `Input_Source` self-clears on the completion path,
and the runner's **negative control** trips correctly (planting `$DEADBEEF` over the first
checkpoint raises `REPLAY DESYNC` at Logic_Tick 2) — so the compare is live and the passes are
not vacuous.

**The tick-735 desync never existed.** It was an artifact of hand-arming, exactly as this entry
suspected when it recorded three different hashes from three arming attempts on one ROM. The
re-stamp this entry pointed at was ALREADY DONE and merged: `32a79e1d` (2026-08-13, "re-stamp
ojz_fixture checkpoints stale since the Knuckles C4 merge") is on master and is the most recent
change to `games/sonic4/test/replay_fixture.emp`. The Effects P3 roadmap's "Parcel 0 — shipped"
row was right; the 2026-08-14 work order that reopened it was working from the bad measurement.

**Lesson:** a manual measurement that yields a different answer every time is not weak evidence,
it is ABSENT evidence, and it must not be written up as a finding. This entry booked
"master desyncs at tick 735" as fact off three mutually-contradictory readings.

---

## ⚠ OPEN — a sigil test binary ABORTS and its tests vanish from the suite totals

`sigil-frontend-emp --test deep_nesting_aborts` dies partway through with
`fatal runtime error: stack overflow, aborting` (SIGABRT). It therefore never prints a
`test result` line, and the standard aggregate command sums it as **0 passed, 0 failed** — it
is invisible in both directions.

**Pre-existing**, confirmed by stashing the parcel's changes and re-running; unrelated to the
blanket restore. But it means every recent `TOTAL passed: N failed: 0` — including this
parcel's `3711/0` — was computed with an unknown number of tests silently uncounted.

The irony is the point: this is the regression test for *"sigil must always fail with a
message, never a bare process abort"* (lens sweep seat SAFE, finding S19), and it is itself
aborting.

**To close:** fix the overflow so the binary reports, then re-baseline the expected total. Until
then, treat any suite total as a lower bound rather than a complete count.

---

## effects suite — 2026-08-13 Phase 3 design audit · EFX-5 FIXED · EFX-4 partially closed · EFX-1/2/3/6 OPEN (Parcel C)

Source: `docs/superpowers/specs/2026-08-13-effects-p3-design.md` §10. Booked here by Effects
P3 **Parcel A** (Task 10) so that none is lost in the gap between parcels — only EFX-5 is
Parcel A's to fix; the rest are recorded, not repaired.

**Every claim below was re-verified against the code at booking time**, and the citations are
the CURRENT line numbers. Two of the spec's own citations did not survive verification and are
corrected in place: EFX-3's `palette.emp:374-395` predates Parcel A's Task 9 deletions (the
proc is now `:324-345`), and EFX-2's "zero callers" is true of `Palette_ArmFade` but not of
`Palette_DoFade`, which is called and merely unreachable.

### EFX-1 — water survives exactly one section crossing — OPEN (Parcel C)

`Raster_InstallWater` (`engine/effects/raster.emp:585`) is called once, at level init
(`games/sonic4/test/ojz_scroll_test.emp:283`), and points `Raster_Program` / `Raster_Active_Buf`
at **Buf_B**. `Raster_InstallSection` (`raster.emp:533-543`) reads `Sec.sec_raster_table` and
takes `beq .keep` on 0 — the descriptor 0-convention, "keep current".

In `OJZ_Act1_Sections` only section 1 (`raster: OJZ_TestRaster`,
`games/sonic4/data/levels/ojz/act1/act_descriptor.emp:176`) and section 2
(`raster: OJZ_TestGradient`, `:189`) carry a table; every other section takes `ojz_sec`'s
`raster: Label = 0` default (`:137`). **Repro:** spawn in section 0 (water live in Buf_B),
scroll right into section 1 — `Raster_Pending` takes `OJZ_TestRaster`, VBlank stages it into
Buf_A and makes Buf_A active, and the water install is gone. Scroll back into section 0: its
table is 0, so `.keep` fires and **nothing ever restores the water** for the rest of the level.

*Fix:* Parcel C's total-binding preset install (a section states its whole effects state rather
than patching a neighbour's).

### EFX-2 — the cross-fade layer is unreachable — OPEN (Parcel C)

`Palette_ArmFade` (`engine/effects/palette.emp:250`) is the **only writer** of
`Pal_Fade_Request` (`:219` is a `tst.b`, `:231` a `clr.b`) and has **zero callers** across
`engine/` and `games/`. So `Palette_LoadSection`'s `.load_target` branch (`:229-238`) can never
be taken, which means `Pal_Target` is never written and `Pal_Fade_Frames` is never set from
`PAL_FADE_FRAMES` (`:237` is its only non-zero writer).

`Palette_Compose`'s `.fade` therefore always falls through on `tst.b Pal_Fade_Frames`
(`:388-390`), and **`Palette_DoFade` (`:513`) never executes** — note it IS called, at `:392`,
so "zero callers" is the wrong description of it; it is called under a condition that cannot
hold. `Pal_Target` (96 bytes of RAM) and `PAL_FADE_FRAMES` are dead in the shipped ROM by the
same chain.

`Palette_LoadCycle` (`:293`) likewise has zero callers — `Palette_InstallCycleSection`
deliberately duplicates its body inline to keep `a0 = Sec*` (`:321-322`).

*Fix:* Parcel C's `ep_transition` exists to claim this layer.

### EFX-3 — a count-0 cycle script leaves cycling ACTIVE — OPEN, and Parcel C would ACTIVATE it

In `Palette_InstallCycleSection` (`palette.emp:324-345`) the `ori.b #PAL_ACT_CYCLE, Pal_Active`
at `:333` happens **before** `channel_count` is even read (`:335`) and before the
`subq.w #1,d0` / `bmi .keep` count test (`:336-337`). A non-NULL script with `channel_count == 0`
therefore returns with `PAL_ACT_CYCLE` **set**. `Palette_LoadCycle` (`:293-311`) has the
identical shape (`ori` at `:298`, count at `:301`, `bmi .done` at `:303`).

`Palette_Compose`'s `.cycling` (`:381-385`) then takes its branch every frame and
unconditionally does `ori.b #PAL_ACT_VARIANT_STALE, Pal_Active` before calling
`Palette_DoCycle` — which itself early-outs on count 0, so the cycling work is free. **The cost
is downstream:** at `.variants` (`:404-414`) the re-set STALE bit defeats the gate that took
`Palette_DoVariants` from 19332 cyc/frame (15.1%) to 0 (`fix/palette-variant-derive`), re-arming
that derive every frame. *Precision:* this only costs the derive when a variant slot is bound —
with `PAL_ACT_VARIANT` clear, `.variants` early-outs on `btst #4` and the stale bit is merely set
and never consumed.

**Latent today** because nothing exercises the empty-script path: the convention is documented
(`:318-319`) but the only `sec_pal_cycle` in the tree is `OJZ_ShimmerCycle`
(`act_descriptor.emp:198`), and no `Pal_Cycle_None` exists yet. **Parcel C must move the flag set
after the count test** — `Pal_Cycle_None` would be the first thing ever to run this path.

### EFX-4 — `Raster_InstallWater` over-reads a short template — **now CLOSED, see the live entry near the top of this file (2026-08-15); its surviving half is EFX-4b**

*Historical record from the 2026-08-13 audit, kept for provenance. `Raster_InstallWater` no longer exists.*

`Raster_InstallWater` (`raster.emp:585-593`) copies a fixed
`move.w #(RASTER_BUF_SIZE / 2) - 1, d1` / `dbf` loop = 64 words = **128 bytes**, unconditionally,
from a template that is **18 words / 36 bytes** (`OJZ_WATER_HAND`,
`games/sonic4/data/parallax/configs.emp:473-484`, pinned equal to the DSL's output). ~92 bytes of
adjacent ROM land in `Raster_Buf_B` past the terminator.

**Harmless today** — the record walk stops at `RASTER_OPS_END` and never reaches the junk — which
is why this is booked rather than hot-fixed.

**Parcel A closed the UPPER bound only:** `engine/effects/raster_dsl.emp:382-383` now `ensure`s
an authored program cannot *exceed* `RASTER_BUF_SIZE`, so no author can overflow Buf_B. The
over-read of a SHORT template stays open (it wants a length word or a bounded copy).

*Follow-up for whoever next touches that file:* the comment at `raster_dsl.emp:380-381` still
says this defect is "NOT yet in docs/BUGS.md — Task 10 books it". Task 10 has now booked it, but
Task 10 is forbidden to edit `.emp`, so the note is stale by one line and wants deleting.

### EFX-5 — the budget model claimed a `raster_state_bytes` the code disagreed with — **FIXED (Parcel A, Task 10)**

`tools/effects_budget_model.toml` said `raster_state_bytes = 286`. `RASTER_STATE_SIZE`
(`raster.emp:184`) is `4+4+4+2+128+128+4+2+4+4+2+2` = **288**. `PALETTE_STATE_SIZE` agreed at 472,
so this was a real one-row drift and not a systematic offset.

Documentation drift with **no runtime effect** — nothing read the TOML at build time, which is
precisely how it survived. Caught by the new `tools/effects_budget_check.py` on its first run and
fixed in the same commit. The checker is now the standing gate: it resolves each `[symbols]` row
against its `.emp` authority, and `tools/test_effects_budget_check.py::TestLiveTree` fails the
python suite the moment a constant and the TOML drift again.

### EFX-6 — `act_sec_field_equs()` is un-gated against the struct harvest — OPEN (Parcel C), and ALREADY STALE

`act_sec_field_equs()` (sigil `crates/sigil-harness/src/test_support.rs:111`) supplies
`Act_*` / `Sec_*` equs to standalone port oracles. Its own doc names `engine/structs.emp` as the
source of truth and says "the values track the struct declarations" — but **nothing cross-checks
the two**, so a field rename silently leaves a dead equ.

**This is not hypothetical; it is already stale, measured at booking.** The blob stops at
`Act_edge_mode $20` and declares `("Act_len", "$22")` (`:127`), while `engine/structs.emp:28-51`
continues through `pad_21 $21`, `act_sec_local_maps $22` and `act_art_budget $26` — so the real
`Act_len` is `$28`, which sigil's `crates/sigil-cli/tests/structs_module.rs:58` asserts of the
actual harvest. The blob is two fields and 6 bytes behind. (`pad_21` is anonymous and correctly
omitted; the other two are not.)

**Consequence today is exactly the predicted one and no worse:** the stale entries are dead equs
that no port reads, so all seven goldens stay byte-identical and nothing fails — which is the
whole argument for adding the gate. Spec §5.1's rider names the same hazard on
`("Sec_sec_collision_s4lz", "$34")` (`:142`), the very field Parcel C renames to `sec_effects`;
that rename must land with the cross-check, or it lands silently.

---

## ⚠ OPEN — the OJZ replay fixture needs a RE-STAMP (character lens sweep, merged 2026-08-13)

**`ojz_fixture` desyncs at tick 735** on merged master. This is an EXPECTED, CORRECT
desync, not a regression: the lens-sweep parcel deliberately changes Sonic's grounded
behaviour (the skid-latch one-writer clear, `ST_PUSHING` now cleared in
`PHook_GroundEnter`, the quadrant clear in `Air_LandOnObject`), and the fixture's
checkpoints were re-stamped by the Effects-P3 lane (`32a79e1d`) against the PREVIOUS
behaviour. The recording captured the old behaviour; the golden needs updating.

**Measured** on merged master (`s4.debug.bin` crc `3dc20e2c`): `Input_Source = 1`,
`Replay_Ptr = $A1DB4`, run → `REPLAY DESYNC` fault screen, `d1 = 0x2DF` (tick 735),
`d0 = DD37D093` (actual), `d2 = 1D375066` (expected payload). `Logic_Tick` freezes at 735.

**Why this is more work than the last re-stamp.** Parcel 0's stale set was 7 checkpoints,
all at/above ring 1280 (everything after the spindash). Ours desyncs at ~ring 733, well
before it, because the changed behaviour is ordinary grounded play rather than the
spindash — so roughly 15+ checkpoints from ring ~733 to the 1721 stream end need
re-stamping.

**The recipe** is `docs/superpowers/notes/2026-08-13-replay-net-restamp-ab.md` §3, unchanged:
run → trap → read `d0`/`d1` off the MD Debugger screen (registers are CLOBBERED at a
fault, so screenshot the dump rather than calling `emulator_registers`) → patch that
4-byte payload in `games/sonic4/data/replays/ojz_fixture.bin` → rebuild → repeat until
`Replay_Done = $FF` and `Input_Source` self-clears. Verify the slide fixture
(`Replay_Ptr = $A1EC4`) too — it was green before and may or may not have moved.

**What is NOT affected:** the automated gates are all green — sigil workspace suite
3672 passed / 0 failed (goldens re-frozen against the merged ROM, provenance 111), three
aeon shapes build, and `tools/test_replay_fixture.py` (the STRUCTURAL gate) passes. The
replay net is a MANUAL gate, not wired into any runner, which is exactly why this note
exists: nothing will fail loudly to remind you.

**Precedent:** master carried a stale fixture from the Knuckles C4 merge (2026-08-12)
until Parcel 0 fixed it a day later, so a pending re-stamp after a behaviour change is
known maintenance rather than a broken build.

---

## character subsystem — 2026-08-13 lens sweep · CHAR-1/2/3/7/8 FIXED · CHAR-4/5/6 + the coverage hole OPEN

Full evidence, reproduction chains and fixes: `docs/superpowers/notes/2026-08-13-character-lens-sweep.md`.
Every one was confirmed by ≥2 independent panel seats and re-verified by the overseer against the
code (and, where cited, against skdisasm). Review SHA `53efbf69`.

**Why all of these shipped, and why none of them will be caught by the replay net:**
`Debug_CharacterHotkey` (`games/sonic4/test/ojz_scroll_test.emp:514`) is the ONLY writer of
`Character_ID`, and it stands down under `Input_Source != 0` — so under playback a replayed `A`
cannot cycle the character and under record a cycle cannot be captured. **Every fixture, present
and future, runs as Sonic by construction**, leaving `PSTATE_FLY/GLIDE/GLIDEFALL/SLIDE/CLIMB/LEDGE`,
both ability hooks and the per-character asset paths at zero automated coverage. The planned
fixture re-record will go green and change none of that. Fixing it needs a design decision (how
does a fixture select a character?), so it is a *task*, not a patch.

### CHAR-1 — ~~skid dust trails the whole jump arc~~ **FIXED**
*Fix:* skid_latch cleared unconditionally at the top of `Player_Animate`, re-armed only by `.skid_show` (one writer); the once-per-skid SFX edge re-keyed onto the previous frame's `anim`. Oracle before/after: 3 mid-air DustPuffs -> 0; natural repro clean on the final combined ROM; grounded skid dust unaffected (2 puffs at feet).
`PlayerV.skid_latch`'s only clear (`player_common.emp:896`) sits below both the `ST_ROLLING`
(`:836`) and `ST_IN_AIR` (`:855`) early-returns, and `Dust_Tick` (`dust_spindash.emp:85-90`) reads
it guarded by nothing but a `PSTATE_SLIDE` check. **Repro (3 inputs):** run to
`|gsp| >= PHYS_SKID_MIN`, hold Left (dust correct), then press jump while still holding Left.
Puffs trail the whole arc at 1 per 4 frames until landing *and* releasing. Same leak into roll,
spindash and (Knuckles) glide. Tails skid→jump→flight emits ~120 puffs, permanently occupying ~4
of 16 `NUM_EFFECTS` slots and silently dropping other effects.
**Fix:** clear the latch at the top of `Player_Animate` and let `.skid_show` re-`st` it.

### CHAR-2 — ~~left-wall glide catches always fail~~ **FIXED — VERIFIED END-TO-END (owner playtest, 2026-08-13)**
**TWO bugs on one code path; the first masked the second.**

*Bug A (facing):* the wall side came from `tst.w x_vel`, but `GLF_PUSH_BIT` is set
exactly by the wall-probe hit whose handler does `clr.w x_vel`, so x_vel is always 0
at the catch and the left branch was never taken. Now keyed on `PlayerV.glide_angle`
(S3K's `double_jump_property + $40`), scratch in d7 because `Climb_WallDist` returns
in d0.

*Bug B (off-by-one) — the reason it STILL failed after A:* `Air_WallProbeLeft` snaps
so `x - PUSH_RADIUS` (x-10) is flush, but `Climb_WallDist` probed `x - CLIMB_RADIUS - 1`
(x-11) — one pixel inside the wall. Both corner probes returned **-1**, and the
both-flush test needs **0**, so no left wall could ever be caught. The right side used
x+10 on both sides of that equation, which is why right walls worked and the feature
looked functional. The `-1` was imported from S3K's `GetDistanceFromWall`
(`sonic3k.asm:31527`), where it compensates for S3K's asymmetric wall queries; ours are
stamped from one symmetric core and never needed it.

**Measured at the catch, gliding left into a real wall:**
`before -1/-1 -> GLIDEFALL` · `after 0/0 -> Climb_Catch -> player_state $16 (PSTATE_CLIMB)`.
Right-wall catch re-verified unaffected (glide_angle $00, flush, climbs, tops out).
Owner then climbed the left wall up and down: **works**.

**Process note:** Bug A was reported fixed on mechanism evidence after I failed to stage
a left-wall catch in OJZ act1 sec0. The owner drove to a real left wall and it still
flopped off. The partial verification was honestly labelled, and that label is what made
the second bug findable instead of shipping as "done".

`Knuckles_Gliding_WallCatch` (`player_climb.emp:492`) picks the wall side with `tst.w x_vel`, but
both `Air_WallProbeLeft/Right` do `clr.w x_vel(a0)` on the very hit that sets `GLF_PUSH_BIT`, so
`x_vel` is always 0 there and `bmi` never taken. Knuckles always faces right; `Climb_WallDist`
then probes rightward into open air and drops to `GLIDEFALL`. **Right walls work by accident**,
which is why nine rounds of playtest passed.
**Fix (S3K-faithful):** discriminate on `PlayerV.glide_angle` — `sonic3k.asm:30776` uses
`double_jump_property + $40 / bpl`, never velocity. Second site, same root:
`player_glide.emp:158-163` `.hit_floor`.

### CHAR-3 — ~~`Slide_Terrain` rotated probe vs fixed +Y snap~~ **FIXED**
*Fix:* `clr.b PlayerBlock.quadrant(a4)` at the top of `PState_Slide` — the `Air_Collide` idiom, and truthful: the slide's terrain model is fixed-down exactly like S3K's.
`player_glide.emp:478-485` calls the rotated `Player_SensorFloor` and `add.l d0, y_pos` regardless,
while writing `angle` from the floor every frame — which `Player_Main:583-587` turns into next
frame's quadrant. `PSTATE_SLIDE` never routes through `Air_Collide`, so nothing zeroes it here, and
every other `Player_SensorFloor` consumer either uses `Player_SnapToSurface` or forces quadrant 0.
Reaches wrong-axis snap / spurious ledge-drop once a slide follows terrain past ±45°. S3K's slide
uses a fixed downward probe (`sub_11FD6` → `Sonic_CheckFloor`).
**Fix:** `clr.b PBLK_QUADRANT(a4)` at the top of `PState_Slide` (one instruction).

### CHAR-4 — the glide family has no ceiling probe at all
`Glide_Collide` and `Slide_Terrain` probe left wall, right wall, floor — nothing upward. S3K's
`Knux_DoLevelCollision_CheckRet` (`sonic3k.asm:32629`) probes the ceiling in three of its four
motion classes, and a glide is in a horizontal class essentially always. Gliding into a rising
overhang, the head enters solid terrain with nothing to eject it, and the parachute (`y_vel >= 0`)
means it cannot self-correct. Compounds with CHAR-6.

### CHAR-5 — the single-centre glide floor probe rests on a false S3K claim — **RECORD CORRECTED, behaviour unchanged**
*The false citation is fixed in place* (`sub_11FD6` runs `FindFloor` twice; the real cause is `PUSH_RADIUS` == Knuckles' ability `x_radius`), with the ~10px GLIDEFALL landing cost recorded. The probe itself is unchanged: restoring the A/B pair risks re-opening the wall-catch bug it was introduced for, and the test section has no climbable wall at glide height to verify against.
`player_glide.emp:315-325` justifies dropping the A/B pair with "S3K's glide floor check
(sub_11FD6) is likewise a single CENTRE sensor". `sub_11FD6` trampolines into `Sonic_CheckFloor`,
which runs `FindFloor` **twice** (`x ± x_radius`) and keeps the nearer. Consequence: `GlideFall`
lands ~10px later than an ordinary fall beside a platform lip. The real cause of the bug it was
introduced for is that `PUSH_RADIUS` (10) equals Knuckles' ability `x_radius`, so a post-snap outer
sensor lands exactly on the snap pixel.

### CHAR-6 — `PHook_AirEnter` lifts 9px on MID-AIR ability-box exits; S3K lifts 0
All three mid-air 21→39 restores (glide release, slide ledge-drop, wall-catch fail) run
`PHook_EnsureStanding`'s `(39-21)>>1 = 9` teleport with no head-clearance check. All three S3K
sites leave `y_pos` alone; S3K lifts only on the two GROUNDED landings — where ours is correct and
should stay.

### CHAR-7 — ~~minor state leaks~~ **FIXED**
*Fix:* `Air_LandOnObject` now clears the derived quadrant alongside `angle`; `ST_PUSHING` cleared once in `PHook_GroundEnter`, which all four Knuckles landing paths reach.
`Air_LandOnObject` (`player_air.emp:420-423`) doesn't clear the cached quadrant before
`Air_LandState`'s ceiling probe, so a solid-object landing while carrying a steep angle decides
stand-vs-roll from a horizontal clearance reading. And `ST_PUSHING` survives the whole
jump→glide→climb chain (none of the four Knuckles landing paths clears it), showing one frame of
`ANIM_PUSH` on touchdown — fixable once in `PHook_GroundEnter`.

### CHAR-8 — ~~vacuous guards~~ **FIXED**
*Fixed:* the climb guard re-bound to `KNUX_ABILITY_RADIUS` (exported) with its three derived offsets guarded too; the three `PhysTable_*` guards and the clamber terminal bound through shared constants (`PHYS_ROW_WORDS`, `CLIMB_CLAMBER_BYTES`). All proven to fail on the drift they exist to catch. No tautological assert was left behind where the binding became structural.
*Also fixed since:* all 16 unguarded `PBLK_*` offsets now bind to `PlayerBlock` (inserting one field at its head fires 18 guards; 5 would have fired before), and the palette guards are pinned to the authored gray literals `$0ECC`/`$0EEE`/`$0CAA` per palette instead of merely agreeing with each other (a lockstep recolour now fires both).
`ensure(CLIMB_RADIUS == PLAYER_X_RADIUS + 1)` (`player_climb.emp:121`) binds the climb probes to
**Sonic's standing radius**, not `KNUX_ABILITY_RADIUS`; it holds only by the 9+1==10 coincidence, so
retuning the ability radius silently desyncs all six probe offsets with a green build. Found by
five separate seats. Also: 21 hand-rolled `PBLK_*` offsets across 8 files with only 5 `offsetof`
guards; the `PhysTable_*` guards name a table their condition never references
(`sizeof(PhysTable_X)` is the fix); and the palette guard tests agreement rather than the grayness
it exists to secure.

---

## 🚨 TRIAGE TRAP — A RED SCREEN NO LONGER MEANS BUG-001 — 2026-08-05

**Read this before diagnosing any red-screen report.** `engine/system/release_fault.emp:73`
writes `move.w #$000E, VDP_DATA` into CRAM[0] and forces the display OFF (`$8134`) before
halting in `.halt: bra .halt`. `$000E` is **the exact value BUG-001's frozen 2026-06-21
capture recorded** as its "pure RED backdrop" evidence — and BUG-001's own recommended-next-step
block said "Watch CRAM line-0 index-0 for the `$000E` write" as its third triage target. That
recipe is now struck out at the source (see BUG-001 below), but anyone working from the
screenshot or from memory will still reach for it.

At HEAD, a red screen means **a fatal fault halt in the lean release shape** — a bus/address
error or an unhandled exception — **not** streaming corruption. The two are trivially told
apart: the fault halt has the display OFF (whole raster is backdrop, no planes, no sprites,
frozen), while the BUG-001 symptom kept rendering garbage plane tiles and an INTACT Sonic
sprite over the red field.

Scope note: `ReleaseFault` is the **lean-profile** path (introduced by `parcel/item29-mddbg-strip`,
provenance chain 39). The default release shape and every DEBUG build show the MD Debugger
crash screen instead, so the red halt is specifically a lean-build signature.

---

## BY DESIGN (recorded) — release builds drop an SFX SILENTLY on ring overflow — 2026-08-05

**Not a regression, but it is the one remaining SFX-loss path, and `BUGS.md` still named the
retired 1-byte mailbox as the loss mechanism.** `sound_api.emp:305-313`: `Sound_PlaySFX`
computes `nextWr` and, if `nextWr == Rd` (ring full — more than 7 DISTINCT pending ids
enqueued in one frame before `Sound_DrainSfxRing` runs), branches to `.ps_drop` and **loses
the newest id**. The `raise_error "Sound_PlaySFX: SFX ring full (>7 in one frame)"` that
catches it sits inside `if DEBUG == 1`, placed BEFORE the shared drop branch so the plain
shape stays byte-identical — which means **release loses the SFX with no signal at all**.

Deliberate and documented at the site (a >7-distinct-ids frame is treated as a content bug,
not a runtime condition). Recorded here so that a future "an SFX didn't play" report is
triaged against THIS path, not against the mailbox collision that was fixed in 2026-06.

---

## BY DESIGN (recorded) — same-id, same-frame SFX requests COLLAPSE — 2026-08-05

`sound_api.emp:295-297`: before enqueueing, `Sound_PlaySFX` compares the incoming id against
the **most recent pending entry** (`(Wr-1)&MASK`) and skips on a match ("same id already
pending -> skip (no double-fire)"). Intentional per the in-code comment, and the right default
for the spam case. But it means a **legitimate rapid double-fire of one id inside a single
frame is merged into one**.

Recorded because it presents **identically to BUG-002's "no follow-up noises" symptom class** —
a user reporting "the second one didn't play" could be hitting this dedup, the release-side
ring-full drop above, or a genuine defect, and the three are indistinguishable by ear.

---

## FIXED — odd Z80 blob → boot ADDRESS ERROR — 2026-08-03

**Caused and fixed by the same parcel** (`parcel/wave4-z80-sound-reclaim`), and the most
instructive defect of the batch: it was a KNOWN hazard that had been marked closed by a
mechanism that never shipped.

**Mechanism:** `boot.emp`'s copy loop walks `a5` through the Z80 blob and then continues
with the SAME register into `boot_tail` — four PSG-silence bytes and its word-wide VDP
command reads. Nothing re-aligned `a5` at the hand-off, so the blob's length silently
became an alignment precondition for every following `move.w (a5)+`.

**Reachability:** every blob size shipped before this parcel happened to be even (6172
plain / 6298 debug), so the precondition held by accident. The reclaim moved the blob to
5941 / 6067 — both ODD — and the 68k landed in `ErrorHandlerBlob` with `ADDRESS ERROR` at
`$001889` (debug) / `$001B91` (config_a), i.e. the first misaligned word read. Symptom at
the A/B bench: NEW produced 26,721 bytes of VGM against OLD's 157,311. Bisected to the
reclaim half by building at the end of the bug batch (`2adf697`), which boots clean.

**Why it was live at all:** the 2026-07-16 review listed this exact hazard in its Tier-4
boot/hardware-risk list — "No build-time evenness assert on either Z80 blob (odd blob =
boot address error)" — and tagged it **[closed by D8 linker asserts — do not hand-fix]**.
That diagnostics-tier mechanism was never built, so the item sat un-fixed under a
closed-looking marker, and the first parcel to change the blob length by an odd number hit
it. See the corresponding correction in the review's STATUS section.

**Fix (`5526113`):** `align 2` inside the `Z80_Sound_Start`/`Z80_Sound_End` brackets plus
`ensure((Z80_SOUND_SIZE & 1) == 0)` — the padding makes it right and the ensure makes it
stay right, independent of any future diagnostics tier.

> **⚠️ THE `align 2` IS LOAD-BEARING RIGHT NOW — DO NOT "SIMPLIFY" IT AWAY.** The blobs at
> HEAD are STILL ODD: `engine/sound/generated/z80_sound_blob.bin` = **5933 bytes**,
> `z80_sound_blob_debug.bin` = **6059 bytes**. The padding byte is what keeps `a5` aligned
> into `boot_tail`; remove it and the boot ADDRESS ERROR returns immediately, in both
> shapes. This is not a historical precaution against a hypothetical future odd blob — the
> blob is odd today and every day since `5526113`.

**Two false leads recorded so they are not re-walked:** `pins.rs` was stale (regenerated
with `repin`) but is a gate/record, NOT a placement input — ROM CRCs were byte-identical
before and after the repin. And `Z80_SOUND_SIZE` is link-derived with no hardcoded mirror
in Aeon, so a stale size constant was not the cause either.

**Consequence for the record:** every ROM built during the reclaim tasks was unrunnable for
this reason. Those tasks' blob-size measurements remain valid (the blob is emitted
independently of the ROM link), but no functional claim about them could have been made
before `5526113`. Evidence: `docs/superpowers/notes/2026-08-03-wave4-sound-ab.md` Result 3.

---

## FIXED — Z80 sound defect cluster (7 defects) — 2026-08-03

Review item 23's sound bug-fix batch plus three extras approved at plan time, all landed on
`parcel/wave4-z80-sound-reclaim` ahead of the size campaign (refactoring around known-broken
code means touching the same routines twice). Net cost +28 Z80 bytes, repaid many times over
by the reclaim in the same parcel. A/B evidence:
`docs/superpowers/notes/2026-08-03-wave4-sound-ab.md`.

### driver B1 — SFX state is power-on GARBAGE from boot until the first song — **FIXED (`9ef153e`)**
**Mechanism:** `SfxChannels`, both duck bytes and `SeqChannels` are never initialised at
driver start — they hold whatever the Z80 RAM powered up with until the first
`Snd_LoadSong` wipes them. `Sequencer_Frame` FALLS THROUGH to `.run_sfx` even with
`SND_SEQ_ACTIVE = 0`, so `Sfx_Frame` walks all 7 channel records every frame from the very
first tick. **Reachability:** the whole boot window before the first song load — with
garbage `sx_*` fields, wild chip writes and bank-latch writes are reachable, not
theoretical. **Fix:** `call Sfx_StopAll` at init, net **±0 bytes** (it replaces the
3-byte `ld (SND_SFX_QUEUE_CNT), a` and returns `a = 0`, so the following stores are
unchanged).
**Placement constraint — this is the part that matters:** `Sfx_StopAll` clobbers `de`, and
`de` holds `$4001` (the YM part-I DATA port) as a **driver-lifetime invariant**. At the
review's suggested site — below the `ld de, SND_Z80_YM_A1` — the call would have left
`de = 68`, redirecting every steady-state `ld (de),a` DAC write to Z80 RAM `$0044`. The
call therefore sits ABOVE the `ld de`, with the ordering constraint commented at the site.
**ORACLE-INVISIBLE by construction:** emulators zero RAM at power-on, so the pre-fix
behaviour cannot be exhibited in oracle. Verified statically.

### SFX B1 — Sfx_DuckRamp resurrects a STOPPED song's PSG channel — **FIXED (`53660ad`)**
**Mechanism:** `Sfx_DuckRamp` re-asserts volume across the music channels with no
`SND_SEQ_ACTIVE` gate (unlike `Sfx_Restore`, which has one). **Reachability:** `StopMusic`
leaves a PSG channel with `SCF_KEYED` still set and its tone latch stale, so the next
ducking SFX un-silences that channel at the stale latched pitch — an audible tone that
**DRONES until the next song load**, with nothing in the stopped-sequencer path to kill it.
**Fix:** +5 B `SND_SEQ_ACTIVE` gate after the level store.

### SFX B2 — queue arbitration compared RAW priority — **FIXED (`e94fc47`)**
**Mechanism:** the SFX queue arbitrates on the raw priority byte, but bit 7 is the
non-latching flag under the 7-bit priority model (SFX Stage B), not magnitude. A bit-7 SFX
would therefore carry **+128 phantom queue weight** and win arbitration it should lose.
**Reachability:** LATENT — the build-fatal ensure added in the Stage B/C parcel keeps every
authored priority below `$80`, so no shipped SFX can express it today. Fixed anyway because
the flag is a supported authoring feature. **Fix:** +2 B mask.

### PSG #1 — Psg_ApplyMod let an EXACT-ZERO divisor reach the chip — **FIXED (`d5f8d6d`)**
**Mechanism:** the floor guard tested only for a NEGATIVE sum, so a modulation accumulator
landing on exactly zero passed straight through to the PSG divisor latch — a
chip-ambiguous value, and a direct contradiction of the routine's own comment
(`Psg_EmitNoiseClock` does the same clamp correctly). **Reachability:** live from MUSIC,
not just SFX — `Mod_Update` reaches it, and `PsgDivisorTableZ` ships its **top 13 entries as
`$0001`**, so an accumulator of −1 lands on exact zero from ordinary high notes. **Fix:**
+4 B, clamping the exact-zero case as well as the negative one.

### sequencer B1 — PSG down-glide 16-bit underflow evaded the overshoot snap — **FIXED (`bb66ff8`)**
**Mechanism:** a portamento down-glide subtracts the rate from a 16-bit divisor; on
underflow the value wraps to `$FFxx`, which the overshoot test then reads as "still ABOVE
the target". The glide therefore keeps running through wrapped space at garbage pitch for
up to ~65536/rate frames instead of snapping. The borrow was already sitting in CF and was
simply never tested. **Reachability:** same `$0001` top-of-table divisors as PSG #1 — any
fast down-glide from a high note. **Fix:** +2 B (`jr c` off the `sbc` into the existing
snap).

### FM bug 11 — Fm_PatchLoad clobbers sc_pan on a mid-song patch change — **FIXED (`dda5e74`)**
**Mechanism:** `Fm_PatchLoad` writes register `$B4` straight from the patch, overwriting
the channel's authored pan. Pan is **write-on-change** against a shadow, and
`Seq_HookSetPatch` never re-asserts it, so the shadow still reads "already correct" and
the channel stays MISPANNED indefinitely — for the rest of the song. **Reachability:** any
song with a `MEV_PATCH` after a `MEV_PAN` on the same channel. **Fix:** +4 B — zero the
`sc_last_pan` shadow so the next pan write re-fires, the same resync `Sfx_Restore` already
performs after its own patch re-upload.
**Recorded because it is a trap:** the review's suggested fix — "source `$B4` from
`sc_pan`" — would have been a **REGRESSION**. `sc_pan` is the raw `$B4` byte and `0` means
"never panned, keep the patch default", so that fix would write `$00` (both outputs off)
and SILENCE every unpanned channel.

### PSG M5 — Psg_NoteOn's detune fold had no floor — **GUARDED (`9463906`)**
**Mechanism:** `Psg_NoteOn` folds detune into the divisor with no range guard, so a
negative detune applied to a divisor-1 note wraps to `$FFxx`. **Reachability:** NOT
reachable with any authored content today — recorded as a **guard, not a repair**. **Fix:**
+11 B, clamping BOTH the negative and the exact-zero case rather than the cheaper
negative-only test: negative-only is precisely the defect fixed in PSG #1 one commit
earlier, and re-shipping that shape to save 6 B is a bad trade inside a parcel handing back
~230.

---

## FIXED — G10 — move_lock permafreeze on solid-object landing — 2026-08-03

A slip-locked player (move_lock set by the S3K slip nudge) who landed on a solid
object kept frozen input forever: Player_SlopeRepel (the normal decrementer) is
bypassed by Ground_PostMove's on-object exit, and nothing else ticked the lock.
Fixed on parcel/bug005-sprites-player (`a8e2b5b` + comment follow-ups): the
on-object exit now ticks the lock (memory-direct form — the register form trips
a sigil relaxation oscillation at the player_ground/player_air section boundary).
Grounded-frame-only semantics preserved (airborne stays frozen by design).

**CONFIRMED IN-EMULATOR 2026-08-03** (previously review-proven only). Repro
recipe, invariant-safe — do NOT poke `Camera_X/Y` to get there, that trips
entity_window's single-axis slide assert: boot DEBUG, stay in debug-fly (the OJZ
scroll test boots into it — 16px box, `height_pixels` $10), fly to the Sec1
`TestSolid` at world (2304, 176) so the entity window spawns it legitimately
(`emulator_object_list` confirms), fly ~80px above it, press B once to toggle
back to Sonic (`height_pixels` $27), let him land. With `status` = $20
(ST_ON_OBJECT) held throughout, poking `PlayerV.move_lock` = 30 then advancing
frames gives 30 -> 20 (10 frames) -> 0 (25 more), i.e. exactly 1/frame, floored
at 0. Pre-fix this path never ticked, so the value would have stayed at 30
indefinitely.

---

## BUG-005 — one-frame stray Sonic sprite piece ("second face") — OPEN-INSTRUMENTED, minor

**Status:** OPEN-INSTRUMENTED. **Severity:** low (single-frame visual flicker, no state corruption).
**Reported:** 2026-08-02 by the user from a live spindash-stress session (OJZ, DEBUG
build, chain-30): one captured frame shows a duplicate chunk of Sonic's head floating
beside him. Frozen-state diagnosis was lost to an emulator control-socket hang before
the sprite table could be dumped (the artifact frame could not be re-frozen).

**Ruled out (2026-08-02 forensics):**
- The `mapping_dsl` sprSize w/h swap — real, but Sonic's mappings come from the
  hardware-correct S2 conversion path, and the swap is FIXED anyway (byte-identical,
  see the mapping_dsl commit).
- The torn-table DMA race — structurally prevented: `Sprite_Table_Dirty` is set only
  AFTER the terminator fix-up in `Render_Sprites.done`, and the 68k-source DMA halts
  the CPU, so a mid-build table can never ship. *(Amended 2026-08-05: that claim had
  one hole — a DROP-RETAINED dirty flag (Critical queue full) is set-but-stale, and
  IRQ6 landing mid-emit on a lag frame could ship the previous length against a
  mid-emit buffer. Closed by the `Sprite_Emit_Active` bracket, `parcel/defect-batch-8`
  — the "can never ship" claim is now unconditional again.)*
- Steady-state chain corruption — tick-stepped VDP sprite-table sampling through a
  replayed jump transition (ticks 1002-1015) shows coherent link chains, correct
  terminators, and `Sprites_Rendered` matching the chain every sampled tick. Stale
  entries beyond the terminator exist by design and are unreferenced.

**Leading suspects:** the `.done` terminator fix-up (`move.b #0, -5(a4)`) landing on
the wrong entry for one frame if `d5`/`a4` skew (e.g. a `DrawRings` path that moves
one without the other), or a multisprite sibling-walk piece-count edge on a specific
pose transition. Both would extend the chain into stale entries for exactly one frame
— matching the observed single-frame ghost. Concrete probe target: the band-cap path
(`sprites.emp` `.band_limit_pop`, ~line 463) reaches `.done` SKIPPING the `DrawRings`
call the normal band-exit runs — the one named site where the `a4`/`d5` provenance at
`.done` differs from the common path (`DrawRings` is contracted `out(d5: u16, a4)`, so a
skew there requires an internal bug — but this is where to look first).

**Live net (2026-08-02, DEBUG builds only):** the chain-walk assert is now in place
at `Render_Sprites.done` (`engine/objects/sprites.emp`), immediately after the
terminator fix-up. It walks the finished SAT link chain from entry 0 (bounded at
`MAX_VDP_SPRITES` iterations so a cyclic chain cannot hang) and
`assert.w d1, eq, d5` traps if the link-path length ≠ the emitted count — in-frame,
with the builder's registers live (d5 = count, a4 = write ptr), before
`Sprites_Rendered` is stored. Both exit paths (`.band_limit_pop` included) converge
on `.done`, so the cap path is covered; the `.empty_table` path needs no walk
(count 0, entry 0 is the hidden terminator). Plain ROMs are byte-identical — the
net compiles only under `DEBUG == 1`.

**~~Next step (its own session)~~ — EXECUTED 2026-08-05** (the overnight
verification round, `docs/superpowers/notes/2026-08-05-verification-round.md`):
(1) the `.band_limit_pop` suspect was probed DIRECTLY — a file-level probe ROM
forced the cap to 12 so the path fired every frame for 25 s under the
object-test soak; the chain-walk net stayed silent and every frame rendered
exactly cap-many coherent sprites. **The named a4/d5-skew class does not
reproduce at this path — suspect downgraded.** (2) The replay screenshot burst
through pose transitions with ring emission ran clean (7 sampled frames, no
ghost, net silent, Replay_Done=$FF). Status stays OPEN-INSTRUMENTED at LOW —
the original artifact remains unreproduced and the standing DEBUG net is the
trap; there is no active suspect left. Scope note (unchanged): the assert
proves link==count CONSISTENCY — it catches the named skew class, not a bug that
advances both in lockstep to an over-count (a different class than this ghost).

---

## ✅ RECLASSIFIED — BUG-001 — section-streaming corruption — UNREPRODUCIBLE ON CURRENT ENGINE (2026-08-02)

**Disposition:** the June-2026 corruption (red field + garbage BG tiles, often
post-spindash) is reclassified NOT-REPRODUCIBLE-BY-DESIGN on the current engine. All
three recorded suspects are structurally retired by architecture that shipped AFTER
the report: (1) the decompress-clobbers-cache alias — mid-game block decompression
now targets the separate `Block_Stage_Buffers`; the `Art_Staging_Buffer` alias of
`Tile_Cache_Nametable` is init-only (display-off, pre-cache-live, `engine/ram.emp`);
(2) the teleport/rebase skip-reload edge — per-frame teleports were deleted by
continuous scroll (2026-06-22/23); (3) the spindash camera-jump race — camera jumps
are contract-locked (`CAMERA_JUMP_LOCK`). Empirical: the 2026-08-02 replay-harness
sessions ran the streaming path under sustained scroll + repeated spindash bursts
(multiple full fixture replays + two live stress rounds) with zero corruption, clean
render, zero lag frames. The original evidence block below is HISTORICAL (its RAM
cell names predate the engine/game split — see the dated annotation). If the symptom
ever reappears, the replay harness is the capture tool: record at the deterministic
anchor and the corrupting timeline becomes replayable.

> **⚠️ Single-entry note (2026-08-05):** BUG-001 previously appeared TWICE in this file —
> this banner, and a second `## BUG-001` heading further down whose status line still read
> `**Status:** OPEN. **Severity:** high`. That contradiction is resolved: **this banner is
> the status**, and the 2026-06-21 write-up is folded in below it as history.

> **⚠️ The EMPIRICAL half of this reclassification predates the BG column-major rewrite
> (2026-08-05).** The 2026-08-02 replay-harness soak ran against the ROW-major BG layout;
> `7b6f55b` (`parcel/item28-bg-transpose`) then rewrote **the exact plane-write path this
> bug described** — BG layout to column-major, `Draw_BG_TileColumn` to sequential `move.l`,
> per-column autoinc-`$80` blits. The **structural** half is unaffected (all three suspects
> are retired by architecture the transpose did not touch), and the transpose itself was
> verified framebuffer-byte-identical over 900 frames including max diagonal scroll. But the
> soak evidence is **as-of the old path**: if this ever needs re-affirming empirically, the
> stress rounds must be re-run on the current layout, not cited from 2026-08-02.

### Historical record — the original 2026-06-21 write-up (STATUS SUPERSEDED BY THE BANNER ABOVE)

Kept verbatim except where annotated, because the frozen-frame capture is unrepeatable (a
restart lost it) and because knowing *what was believed and why* is the point of keeping it.
**Its "Status: OPEN / Severity: high" line is void** — see the disposition above.

**Was:** BUG-001 — Section-streaming rendering corruption (background → garbage tiles + red field)

**Original status line (VOID):** ~~**Status:** OPEN. **Severity:** high (game becomes unplayable in that area).~~
**Reproducibility:** INTERMITTENT
— happens "every now and then," often (but not always) right after a spindash. The user could NOT reliably
re-trigger it, so the live evidence below was captured from a single frozen occurrence (2026-06-21) and is the
primary record — a restart loses it.

**Screenshot:** `docs/research/bug_streaming_corruption_2026-06-21.png` — the whole background is a RED field
filled with a repeating grid of garbage tiles; the Sonic **sprite is intact**; the DEBUG HUD reads
`COL: need layout co…`.

> **Doc note (2026-08-05) — the `COL: need layout co…` HUD indicator NO LONGER EXISTS.** That
> string appears nowhere in `engine/`, `games/` or `tools/` at HEAD. It was a capture-era debug
> overlay and is gone; do not go looking for it, and do not treat its absence in a future
> report as evidence of anything. Read it here purely as 2026-06-21 evidence that the engine
> of that era self-detected a missing collision layout.

#### Symptom
The BACKGROUND planes render garbage tiles over a red backdrop. Sprites (player) are unaffected.

> **⚠️ 2026-08-05: "red backdrop" is no longer diagnostic of this bug at all.** See the
> **TRIAGE TRAP** entry at the top of this file — `ReleaseFault` deliberately paints CRAM[0]
> `$000E` (the very value captured below) and halts with the display off.

#### NOT a crash, NOT sound
- 68k `PC = 0x1DD4` — the normal main-loop wait (`Process_DMA_Critical` region). CPU running fine; SR=$2600.
- The player sprite renders correctly → sprite VRAM + sprite palette are intact. This is a **plane / level-art /
  backdrop** corruption only.
- Unrelated to the sound work in this session.

#### Live-emulator evidence (frozen frame, 2026-06-21)
- **Player** (object list): x=1301 (`$0515`), y=694 (`$02B6`). **Vel 0,0** (stopped). In section **(0,0)**.
- **Camera_X = `$04770000`, Camera_Y = `$02420000`** (16.16). Cam X=1143 — still inside section 0
  (`SECTION_SIZE = $0800` = 2048px), so `Sec (0,0)` is CORRECT; this is NOT a section-index mismatch.
- **`Section_Stream_State` ($FFA8EC): section 0 = `$02` (SS_RESIDENT), section 1 = `$02`, rest `$00` (IDLE).**
  → the engine believes section 0 (the player's section) is fully loaded.
- **`Slot_Section_Map` ($FFA8E0): slot0=(0,0) slot1=(1,0) slot2=(0,0) slot3=(0,0).**

> **Doc note (2026-08-02):** the cell names `Section_Stream_State` ($FFA8EC) and `Slot_Section_Map`
> ($FFA8E0) cited in the two bullets above no longer exist in `engine/ram.emp` — the A.4 art-stream
> state machine was never landed under those labels (this is confirmed in-code by the comment in
> `engine/system/replay.emp`). The evidence is left verbatim as the original 2026-06-21 frozen-frame
> record; the equivalent current section-streaming state lives in the `Section_*` cells
> (`Section_Plane_Dirty`, `Section_Top_Row_Written` / `Section_Bottom_Row_Written`,
> `Section_Left_Col_Written` / `Section_Right_Col_Written`, `Section_Fwd_Neighbor_Data` /
> `Section_Bwd_Neighbor_Data`). Read the two addresses above as "whatever streaming-progress cell
> occupied that offset at capture time," not as live symbol names. The same reading applies to the
> rest of this frozen record: capture-era paths (`ram.asm:28` — today `engine/ram.emp`) and the
> in-record suspect annotations are historical. In particular the `Decomp_Buffer`-aliases-cache
> "Strong suspect" bullets are SUPERSEDED by the reclassification banner above — the alias is
> `Art_Staging_Buffer: alias(Tile_Cache_Nametable)` today, init-only/display-off, structurally
> retired as a suspect.
>
> **Extended 2026-08-05:** the same reading now also applies to `Section_Teleport_Guard`
> ($FFA8E9) in the bullet list below — that symbol is **gone from the tree** along with the rest
> of the leapfrog subsystem (deleted by continuous scroll, 2026-06-22/23). The 2026-08-02 note
> above did not reach that far down the list.

- **`Tile_Cache_Nametable` (RAM $FF0000): BLANK — uniform tile-0 entries (`1000 0000` repeating).** The RAM-side
  section nametable cache holds no real art. (NOTE: `Decomp_Buffer` *aliases* `Tile_Cache_Nametable`,
  ram.asm:28 — a decompress firing during a streaming event would clobber this cache. Strong suspect.)
- **VRAM level-art region ($0000+): sparse / incomplete** — mostly zeros with a few stray bytes per tile;
  the section art is not actually resident in VRAM.
- **VRAM plane nametable (~$C000): GARBAGE** — random tile indices (`43BE 43F7 B8A7 33BF…`) mixed with
  repeating blank-tile entries (`00000001`, `00000004`). (Note: VRAM garbage ≠ the RAM cache's uniform blank,
  so the VRAM may be STALE pre-corruption content the DMA never overwrote — worth confirming the plane base.)
- **CRAM palette line 0 index 0 = `$000E` (pure RED, R7G0B0); lines 1-3 index 0 = `$0000` (black).** The
  backdrop entry alone is red → the red field. (Determine: is this a DELIBERATE debug "missing-layout" warning
  the engine paints, or palette corruption? Lines 1-3 being correct suggests a targeted write, i.e. likely a
  debug indicator paired with the `COL: need layout` HUD.)
- **No fill stuck:** `Cache_Fill_Resume_Col` = `$FFFF`, `Cache_Fill_RowResume_Row` = `$FFFF` (both "none
  pending"). So it is NOT a half-finished/interrupted tile-cache fill.
- `Section_Plane_Dirty` ($FFA8EA) = `$00` (no full redraw pending). `Section_Teleport_Guard` ($FFA8E9) = `$00`
  (**symbol no longer exists — see the extended doc note above**).
- `Section_Top_Row_Written` = `$0002`, `Section_Bottom_Row_Written` = `$003B`. `Lag_Frame_Count` = `$28` (40).
- HUD overlay: `COL: need layout co…` — the engine itself flagged that the **collision layout for the player's
  position is not loaded.** (**Indicator removed — see the doc note under Screenshot.**)

#### Diagnosis (as reasoned in 2026-06-21 — superseded, retained for the reasoning)
**Section-streaming state↔data DESYNC: section 0 is flagged `SS_RESIDENT`, but its art (VRAM tiles + RAM
nametable cache) and collision LAYOUT are not actually loaded.** The engine even self-detects the missing
collision (`COL: need layout`). So a streaming event marked the section resident WITHOUT (re)loading its
art/collision, and the fill/DMA then drew the empty/blank cache → garbage tiles over the red backdrop.

#### Leading suspects (unconfirmed at the time — ALL THREE STRUCTURALLY RETIRED, see the banner)
1. **Teleport/rebase "pure rebase, no redraw" path** treating the section as already-resident and SKIPPING the
   art/collision (re)load in an edge case where the data wasn't actually present. (See `engine/level/section.emp`
   teleport/rebase; memory `project_teleport_rebase` — "teleports are pure rebases, reinit/redraw removed".)
2. **`Decomp_Buffer` aliases `Tile_Cache_Nametable`** (ram.asm:28). A decompress during the streaming event
   would overwrite the nametable cache → blank/garbage cache → blank/garbage VRAM after the next fill/DMA.
3. **Race/timing edge case** — the intermittency + the spindash trigger (fast camera jump stressing the
   streamer) point to a timing window, not a deterministic path.

#### ~~Recommended next step (its own focused session)~~ — **NEUTRALISED 2026-08-05: DO NOT FOLLOW THIS RECIPE**

> **All three watchpoint targets are dead or actively misleading at HEAD.** This block is kept
> only so nobody re-derives it from the evidence above and walks the same dead ends:
>
> 1. ~~Watch `Section_Stream_State + 0` for a write to `$02`~~ — **the symbol does not exist**
>    anywhere in the tree. Neither does `Section_Teleport_Guard`. Both belonged to the leapfrog
>    subsystem, deleted by continuous scroll (2026-06-22/23). There is nothing to set a
>    watchpoint on.
> 2. Watch the `Tile_Cache_Nametable` region for a blanking write — **the suspect it was aimed
>    at is retired**: the alias is `Art_Staging_Buffer: alias(Tile_Cache_Nametable)`, init-only
>    and display-off. A watchpoint here now traps normal init traffic.
> 3. ~~Watch CRAM line-0 index-0 for the `$000E` write~~ — **ACTIVELY MISLEADING.** At HEAD the
>    engine itself writes `$000E` to CRAM[0] deliberately, from `release_fault.emp:73`, as the
>    fatal-fault backdrop. This watchpoint will fire on the fault halt and tell you nothing about
>    streaming. See the TRIAGE TRAP entry at the top of this file.
>
> **If the symptom ever reappears, the capture tool is the replay harness** (banner above):
> record at the deterministic anchor and the corrupting timeline becomes replayable — a strictly
> better instrument than any of the three watchpoints, and the reason this recipe was not
> rewritten rather than retired.

**Original text (historical):** Reproduce with a **watchpoint** to trap the corrupting moment:
Watch `Section_Stream_State + 0` (section 0's state byte) for a write to `$02` (resident) and check, at that
instant, whether the art-load / collision-load actually ran. OR watch the `Tile_Cache_Nametable` region for the
write that blanks it (catch the aliased decomp clobber). OR watch CRAM line-0 index-0 for the `$000E` write
(find whether it's the debug warning or corruption). Then trace backward from the trigger (spindash launch →
camera jump → which section routine fires). This is an **engine/section-streaming** bug — separate from sound.
Do NOT guess a fix; trace the corrupting write.

---

## ✅ RESOLVED — BUG-004 — window-despawned parent leaks its children (gap-ledger row 1599) — FIXED 2026-08-02

**Was:** `EntityWindow_DespawnObjects` deleted only the parent; children are untagged by
construction (`AllocDynamic` tags `SLOT_TAG_UNTAGGED`, only the window spawn path re-tags),
so they could never despawn themselves — a window-despawned parent leaked its children's
dynamic slots for the level, each orphan dereferencing a freed `parent_ptr` every frame.
**Fix (ruled (a), Volence):** the despawn path cascades `jbsr DeleteChildren` before
`DeleteObject` (merge `8678ddb`, chain-23 `despawn-cascade`). **Oracle A/B:** pre-fix
3 orphans orbit the zeroed corpse at origin forever (end-state live=33, 3 slots never
returned); post-fix parent+3 children freed the same frame, end-state 30-clean, free stack
fully recovered. Full procedure + screenshots:
`docs/superpowers/2026-08-02-engine-debts-opener-evidence.md`.

---

## BUG-002 — SFX gameplay-integration cluster (spurious triggers, wrong duration, rev churn)

**Status:** PARTLY FIXED (see each item). **Severity:** medium (audible wrongness, no crash).
**Reported:** 2026-06-21 by the user from live play: "when you walk and roll the SFX lasts too long and
gets weird at the end; spindash press-once-and-release-quick does no follow-up noises; rev a lot → weird
sounds; sometimes random things trigger sounds when they shouldn't — e.g. Sonic in the air triggers the
jump noise without jumping; a few others I can't reliably trigger."

### ~~Common systemic thread — the 1-byte SFX mailbox (deferred A2)~~ — **SUPERSEDED, FIXED 2026-06-22**

> **⚠️ THIS THREAD IS DEAD. Do not attribute new SFX-loss reports to it.** The 1-byte mailbox
> was replaced by an **8-deep ring buffer** in `98798d1` (2026-06-22): `engine/ram.emp:460-462`
> declares `Sfx_Ring_Buf: [u8; 8]` + `Sfx_Ring_Wr` / `Sfx_Ring_Rd`, with
> `SFX_RING_DEPTH = 8` at `engine/sound/sound_constants.emp:452`. `Sound_PlaySFX` now only
> ENQUEUES (`sound_api.emp:283-329`); the **sole** writer of `SND_REQ_SFX` is
> `Sound_DrainSfxRing` (:357/:361, inside one `z80_stopped` hold), which posts at most one id
> per frame and only when the Z80 has cleared the previous — called once per frame from
> `game_loop.emp:32`. `DEFERRED_WORK.md:1396` records the A2 runtime verification as
> **DISCHARGED**.
>
> **Date caution:** every sub-item filed under this thread below is dated 2026-06-21 and
> therefore **predates the fix by one day**. Their root-cause analyses stand on their own
> evidence; only the "…and the mailbox collision dropped one" *contributing* clause is now
> void. Today's SFX-loss paths are the two BY-DESIGN entries at the top of this file
> (release-side ring-full drop, and same-id same-frame dedup).

**Original text (historical):** The 68k posts SFX to a SINGLE byte (`SND_REQ_SFX` $1F03). **Two SFX in one frame → the second clobbers the
first → one is dropped.** This is the deferred A2 item (DEFERRED_WORK.md). Several symptoms below are this
collision surfacing in real play. A small ring-buffer mailbox (A2) is the systemic fix; the per-bug fixes
below remove specific collisions at the source.

### Item 4 + Item 2 — spurious roll-jump SFX after a spindash launch — **FIXED 2026-06-21**
> **Symbol note (2026-08-10):** the narrative below names `Player_JumpBuffer`, a global that no
> longer exists. The per-slot split (C1) folded it into the player working block, where it is now
> `PBLK_JUMPBUF(a4)`; the `.asm` files it cites are the `.emp` twins today
> (`games/sonic4/player/player_spindash.emp`, `player_ground.emp`). The fix itself still stands at
> `player_spindash.emp` `.launch`. History left as written.

**Root cause (data-flow traced, not guessed):** charge-mashing JUMP latches `Player_JumpBuffer`; `.rev`
consumes it each rev, BUT the release frame runs `.release` (never `.rev`), so a jump press landing in the
buffer window at the moment of release is never consumed. `.release` → `jmp PState_Roll`, and `PState_Roll`
(player_ground.asm:327) fires `Player_Jump` on any set buffer → (4) the jump SFX `$62` plays "in the air"
right after the launch + the player roll-jumps without an intentional press; AND (2) that same frame the dash
`$B6` and the spurious jump `$62` both hit the 1-byte mailbox → one drops → "no follow-up noise" on a quick
spindash. **Fix:** `clr.b (Player_JumpBuffer).w` at the spindash launch (player_spindash.asm `.launch`,
before `jmp PState_Roll`) — drops the stale charge press; a FRESH press after launch still roll-jumps.
~~**Verify when emulator reloaded:**~~ **STALE TO-DO (noted 2026-08-05)** — this line was never struck
after the fact. Later follow-ups in this same cluster (Items 1+3 follow-up, follow-up #2, follow-up #3,
BUG-003) are all marked **hardware-verified** on ROMs built after this fix, and the spindash-release path
was exercised throughout those captures. Repro if you want it: spindash + mash jump + release → no
airborne jump chirp; the dash plays.

### Item 1 — roll SFX "lasts too long and gets weird at the end" — **FIXED 2026-06-21**
**Ruled out** re-trigger-per-frame (roll/skid each fire ONCE). A 73-agent + adversarial-verify root-cause
pass found the real cause is in the **transcoded blob**: the roll `$3C` tail is a 42-pass `smpsLoop` whose
body has a per-pass `smpsFMAlterVol $01` (cumulative attenuation → fade to silence). Our engine has no
relative-AlterVol opcode, so the transcoder COLLAPSED the fade to ONE constant `MEV_VOL` inside a
`RepeatStart/RepeatEnd` body, which the engine replays identically every pass → the tail held flat at near-
full volume then HARD-CUT (= "lasts too long / weird at the end"). A secondary divergence: `smpsNoAttack`
was a transcoder no-op, so each pass re-keys the FM envelope (a stutter). NB the user's "walk" was the roll
FM tail — skid `$36` is byte-faithful PSG (no AlterVol; verified).
**Fix (transcoder-only — the Z80 driver has just 4 bytes free, so no new opcode):** `tools/sfx_transcode.py`
now UNROLLS an AlterVol-bearing `smpsLoop` into per-pass `Vol`+note events, walking the TL attenuation up by
the S&K per-pass delta and inverting `LogVolumeLutZ` to the `sc_volume` index that renders it — a dB-faithful
`+1 TL/pass` decay-to-quiet (regression test asserts each pass == +1 attenuation). Roll Vol now fades
`99→…→20`. **Deferred:** honoring `smpsNoAttack` (suppress the per-pass re-key) needs a Z80 no-key-on note
path — no room until bytes are reclaimed; the restored fade makes the re-key quiet, so re-evaluate by ear.

### Item 3 — "rev spindash a lot → weird sounds" — **FIXED 2026-06-21**
**Primary cause (confirmed):** the spindash `$AB` loop body is the SMPS bare-duration "replay previous note"
idiom (`dc.b smpsNoAttack, $02`); the transcoder dropped the standalone duration byte, so the `$AB`
`RepeatStart/RepeatEnd` body had **zero time-advancing events** → the Z80 ran all 24 reps in one frame and
fell to END → the rev played only its ~24-frame attack then stopped dead, and every rev tap re-fired that
truncated, tail-less attack (= "weird"). The same AlterVol-collapse (Item 1) flattened what little tail
existed. **Fix (transcoder-only):** (a) `_process_dcb` now implements the bare-duration replay (re-articulate
the previous pitch), restoring the loop body's timing; (b) the AlterVol unroll restores the per-pass fade.
`$AB` tail now has 24 note re-articulations fading `95→…→16`. The monotonic mod-sweep and `$10` transpose
clamp were verified **faithful — left unchanged**. A defensive packer backstop now rejects any
`REPEAT_START..REPEAT_END` body with no time-advancing event (the collapse class) for all SFX and music.

### Items 1 + 3 follow-up — re-key buzz + swept-pitch linger — **FIXED 2026-06-21 (hardware-verified)**
User retest after the fade fix: roll had "a higher pitch noise after", spindash-hold made "a jingle after a
second", and the spindash-release linger sounded "too high". VGM capture of OUR ROM proved the cause: the
unrolled tails RE-KEYED the FM envelope every pass (43× roll on `$28`/chsel `$04`, 26× spindash chsel `$05`,
at 30 Hz) = the jingle; and with the re-key gone the tail would have held at the modSet *swept* pitch
(spindash fnum `1912`) = the "too high" linger. Fix (the deferred `smpsNoAttack`, now done — see
DEFERRED_WORK B4): bit 7 of a NoteDur pitch = no-attack; `Seq_Op_NoteDur` skips the note-on hook for a held
note (4 Z80 bytes, the exact free budget); the transcoder holds all tail passes EXCEPT the first-after-modSet
(which re-keys to reset the swept pitch to base). **Re-captured & verified:** KEY-ON 43→2 / 26→2, tail holds
at base fnum (`1364` / `1288`, not swept), TL fade intact (`5→48` / `0→54`).

### Items 1 + 3 follow-up #3 — transition re-key click ("second faint spin") — **FIXED 2026-06-22**
The held-tail fix left ONE re-key at the main→tail seam (43→**2**): the main note sweeps up via its modSet,
then the first tail note re-keyed to reset the swept pitch to base — a faint "second attack" the user heard
as "a second more faint spin noise" on the momentum roll. **Fix:** `Seq_Op_ModSet` now, for an SFX FM channel
(route `< CHROUTE_PSG1`), re-writes the unmodulated `sc_base_freq` via **`Fm_WriteFreq`** — which changes a
HELD note's `$A4/$A0` with NO `$28` key-on (the vibrato path) — so when the sweep modSet turns off the tail
snaps to base with no re-key; the transcoder then holds ALL tail passes (dropped `_emit_notedur`'s
first-after-modSet exception). The +18 Z80 bytes were reclaimed by folding 6 more inline channel-class tests
into `Snd_ChanClass` (`Z80_SOUND_SIZE` back to `$16EE`, 2 free — *at this fix. The follow-on
"$1618 / 216 B free" figure this parenthetical used to carry is STALE (noted 2026-08-05): the
resident ceiling is `SND_STATE_BASE = $18F0` (`engine/sound/sound_constants.emp:88`), and after
the wave-4 reclaim the blobs are 5933 / 6059 bytes, i.e. roughly **450 B free plain / 324 B free
debug**. Treat every size figure in this cluster as as-of-its-own-date; measure the blob, don't
quote the doc.*). **Verified on hardware:** roll & spindash
KEY-ON **2→1**, fades still `5→53`/`0→54`, tails held at base — and a regression sweep confirmed skid/ring/
jump/dash all still sound (no fallout from the PSG-path conversions). The roll/spindash tails are now a single
clean attack fading smoothly to silence — fully S&K-faithful (one key-on, like S&K).

### Items 1 + 3 follow-up #2 — "distorted jingle for a bit" — **FIXED 2026-06-21 (RENDERED-audio verified)**
After the held-tail fix the user still heard "a distorted jungle [jingle] after them for a bit." The `$28`
re-key count was a PROXY; rendering the capture to WAV (vgm2wav) showed the truth: the roll RMS only faded
`1.00→0.68` then **plateaued**, and the spindash barely faded — yet one carrier's TL walked a full 32 dB.
Root cause: for alg-4 voices there are TWO carriers (S2+S4); only ONE faded. `Fm_SetVolume` reads the
algorithm/carrier-mask + base TLs via `Fm_PatchPtr`, which resolves `sc_patch` into the MUSIC patch table
`SND_SEQ_PATCHTAB` — but SFX channels load their voice from `sx_patch_base` and never set `sc_patch`, so
EVERY SFX volume write used a stale/empty patch's algorithm → wrong carrier mask → faded the wrong/one
carrier. Latent until now because one-shot SFX have constant volume; the fade fix exposed it. **Fix:**
`Fm_PatchPtr` returns `sx_patch_base` for SFX channels (`engine/sound_fm.asm`); `Sfx_Restore` passes the
MUSIC channel so its path is unaffected. The Z80 was at its $16F0 ceiling, so the bytes were reclaimed by
merging the two SFX gates in `Fm_NoteOnFreq` + factoring the 12-site `push ix/pop hl/ld a,h/cp` channel-class
test into `Snd_ChanClass` (5 sites converted; `Z80_SOUND_SIZE` now `$16EE`, 2 free — *at this fix; the
"$1618 / 216 B free" follow-on figure is STALE, see the correction in follow-up #3 above: ceiling is
`SND_STATE_BASE = $18F0`, post-wave-4 blobs are 5933 / 6059, ≈450 B free plain / 324 B debug*). **Rendered-audio
verified:** both carriers (`$48`+`$4C` roll, `$49`+`$4D` spindash) now fade `5→53` / `0→54`, and the audio
RMS decays to `0.02` (fades to silence) — no plateau, no distortion. The roll/spindash tails are now a clean
held note fading smoothly to silence (S&K-faithful). LESSON: the `$28` count was a proxy; only the rendered
WAV envelope revealed the un-faded carrier.

### BUG-003 — dash `$B6` "duh" = PSG noise rendered as a TONE — **FIXED 2026-06-21**
After the FM tails were clean the user heard a "duh..." after the spindash (the *release* fires the dash
`$B6`). The dash's PSG3 channel uses `smpsPSGform $E7` (noise mode) — its release is meant to be **white
noise**. But the transcoder routed it as `CHROUTE_PSG3`/`SFXEL_PSG` (a TONE voice) and dropped the
`smpsPSGform` opcode ("handled via sx_kind" — but sx_kind was *tone*), so the engine played an audible
descending TONE on PSG ch2 = the "duh." (Pre-existing; unrelated to the FM work — exposed once the FM was
clean.) **Fix (transcoder):** pre-scan a PSG channel for `smpsPSGform`; if present, reroute it to
`CHROUTE_PSGN`/`SFXEL_NOISE` and emit a fixed white-noise mode note (`$E6`, clk/2048), dropping the
tone-only modulation. **Verified on hardware:** the dash now writes the noise control `$E6` + ch3 noise
volume fading `5→15`, ZERO ch2 tone writes; rendered audio spectral-flatness `0.667` = broadband noise (was
tonal), fading to silence. **Refinement deferred (DEFERRED_WORK B5):** S&K's `$E7` is white noise *tracking
PSG3's swept tone frequency* (a descending-pitch "pshhew"); reproducing that needs the engine to drive PSG3's
frequency as the noise clock (or a tone-clock + noise channel split). The fixed-rate noise is the right
*character*; the pitch sweep is the remaining nuance.

### "A few others" (user can't reliably trigger)
~~Most likely further instances of the 1-byte-mailbox collision (A2) — any frame that fires two SFX (e.g.
ring + skid, jump + ring). Tracked under A2 in DEFERRED_WORK.md; the ring-buffer mailbox resolves the class.~~

**SUPERSEDED 2026-08-05.** That attribution is void: the ring-buffer mailbox SHIPPED (`98798d1`,
2026-06-22, 8 deep) and A2's runtime verification is DISCHARGED (`DEFERRED_WORK.md:1396`) — a frame
firing two SFX (ring + skid, jump + ring) is exactly what the ring handles, and those pairings were
exercised throughout the phase's captures. If "a few others" ever becomes reproducible, triage it
against the paths that are actually live today: the **release-side ring-full drop** (>7 distinct ids
in one frame, silent outside DEBUG) and the **same-id same-frame dedup** — both recorded as BY-DESIGN
entries at the top of this file.

### EFX-7 — `Raster_Clear` is a no-op and `HBlank_Uninstall` is unreachable — **CLOSED 2026-08-16**

**Closed by** making the teardown arm REACHABLE, not by deleting it. `Raster_VBlank` now tests the
staged program's SHAPE — a program whose first record is already the terminator has no records —
and takes the uninstall arm for it. That is exactly `Raster_Program_None`, which every "raster OFF"
preset already installs, so **no authoring surface changed and no sentinel value exists to get
wrong**. `HBlank_Uninstall` has a live caller again and IE1 is dropped.

**Two things in the booking below were already stale when it was closed**, and both are worth
noting because they changed what the right fix was:
- **`Raster_Clear` no longer exists.** It was deleted at some point after the booking, so the
  "sentinel the clear" fix the booking proposes had nothing left to sentinel.
- **`Raster_Install` has a caller** (`preset.emp`, via `Effects_InstallPreset`), which never passes
  0 — it redirects a null `ep_raster` to `Raster_Program_None`. So the "both procs have zero
  callers, it is latent" severity was only half true: the *clear* path was unreachable, but the
  install path is live and every OFF section was paying for it.

**What it was costing**, measured before/after on the same scene (oracle, 2026-08-16): an armed
`Raster_Program_None` took **512 cycles per frame across TWO HInt entries**. Two, not one, because
`.park` does not advance the cursor — the line-0 fire reads the terminator and parks, the counter
still holds VBlank's 0 so line 1 re-reads the same record, and only then does the `$8AFF` reload
push the next fire past the frame. After the fix the handler is not entered at all.

**Gate:** `tools/raster_off_gate.py` — 12 assertions across armed / off / re-armed / off again,
with `HBLANK_SLOT_RTE` and `HBLANK_IE1_BIT` read out of `hblank.emp` rather than hard-coded. It
fails exactly the six OFF assertions when pointed at a pre-fix ROM.

**A note on why an image gate could never have caught this:** nothing on screen changes when the
handler is armed-but-parked. The defect is pure cost and pure dead code, and it survived from P1
with a booking against it the whole time.

*The original booking follows, unedited.*

---

### EFX-7 (original booking) — `Raster_Clear` is a no-op and `HBlank_Uninstall` is unreachable

**Surfaced during:** the 2026-08-14 five-lens vocabulary review (runtime-surface lens), confirmed by
the controller.

**What:** `Raster_Clear` stores 0 into `Raster_Pending`. `Raster_VBlank` opens with

```
move.l  Raster_Pending, d0
beq.s   .no_install          // 0 is filtered HERE
clr.l   Raster_Pending
move.l  d0, Raster_Program
bne.s   .copy_program        // d0 provably non-zero -> ALWAYS taken
jbsr    HBlank_Uninstall     // dead code
```

so a pending value of 0 is read as "nothing pending" and skipped. The documented
"0 = clear/uninstall" convention on `Raster_Install` is therefore **unreachable**, HInt is never
disarmed through this path, and `HBlank_Uninstall`'s only reference in the tree is that dead branch.

**Severity:** latent. `Raster_Clear` and `Raster_Install` both have zero callers — sections go through
`Raster_InstallSection`, which stores `Raster_Pending` directly. Nothing in the shipped ROM depends on
the broken path.

**Why it still matters:** `docs/EFFECTS_AUTHORING.md` documented `Raster_Clear` as install route 2's
teardown, i.e. the authoring reference pointed at a no-op. That text now carries the warning; the code
is still wrong.

**Fix:** sentinel the clear (e.g. `Raster_Pending = -1` meaning "explicit clear") or branch on
`Raster_Program` rather than on `d0`. **This changes emitted bytes**, so it needs the byte-changing
parcel ritual — rebuild both sigil binaries, repin, and `refreeze --freeze <name> --ab <evidence>` with
real emulator A/B evidence. Not appropriate for a documentation-and-guards parcel; deliberately
deferred rather than smuggled in.
