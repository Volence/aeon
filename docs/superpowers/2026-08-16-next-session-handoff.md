# NEXT-SESSION WORK ORDER — 2026-08-16

Supersedes `2026-08-18-next-session-handoff.md`.

---

## State at handoff

| repo | branch | state |
|---|---|---|
| **aeon** | `master` | merged + pushed, all four shapes rebuilt |
| **sigil** | `master` | merged + pushed — repin + refreeze twice (chain **129**, tip `efx7-explicit-clear`) |
| oracle | `main` | untouched this session |

The two repos move **as a pair**; a sigil tree at chain 129 does not build a pre-parcel aeon tree to
the frozen bytes, or vice versa (`[[reference_sigil_byte_changing_parcel_ritual]]`).

```bash
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
```

### ROM CRCs

| shape | was (2026-08-18) | now |
|---|---|---|
| `s4.bin` | `f0e45751` | **`9c8ab255`** |
| `s4.debug.bin` | `3da516e4` | **`208043fa`** |
| `demo.bin` | `dca06660` | **`20452947`** |
| `demo.debug.bin` | `6c5e1875` | **`d5f9eb63`** |

Total ROM length is UNCHANGED in every shape across both parcels — the +4 and +0x10 came out of
inter-section padding. `demo` moves because it links `Raster_Install` and therefore the whole raster
module; a parcel touching `engine/effects` that did *not* move demo would be the surprising one.

### Run the gates

```bash
python3 tools/effects_gates.py      # 8 emulator-backed effects gates, one command
```

---

## What shipped

### 1. Two live raster bugs (chain 128)

- **`Raster_InstallPatched` ship-entry publish race.** `Effects_Offscreen_Entry` was published ~10
  instructions before `Raster_BuildShipEntry` filled the `Static_Pal_Ship` entry it names, so a
  VBlank in the window shipped the PREVIOUS program's source/destination/length. Now cleared for the
  whole install window, built, published last — 0 is the consumer's inert value, so the worst case
  is one frame with no ship instead of one with the wrong one.
- **`Raster_Dense_Lines` never reset per frame.** A run reaching past line 223 never counted down;
  left set, the next frame's first HInt took `.dense_body` and streamed a stale cursor across the top
  of the screen. Now rewound beside `Raster_Cursor`.

### 2. The measured per-fire cost model (chain 128)

`fire_cost_cycles` was `418 + 36 x stream_words` over stream ops only. Now

```
FIRE_BASE + sum over ops of ( fetch + dispatch(depth) + class work + word slope x words + tail )
```

Eight fixtures, four free parameters, **zero residual**; every op term confirmed a second way by
hand-counting the emitted 68000. Dispatch depth derives from the opcode order, so inserting an
opcode re-prices everything behind it. Evidence:
`docs/benchmarks/effects-p3/DENSITY-EVIDENCE.md`. Rig: `tools/raster_cost_probe.py`.

### 3. EFX-7 closed (chain 129) — an empty program now UNINSTALLS the handler

Closed by making the teardown arm **reachable**, not by deleting it. The test is SEMANTIC rather
than a sentinel: a program whose first record is already the terminator has no records, which is
exactly `Raster_Program_None` — what every "raster OFF" preset already installs. No authoring
surface changed and there is no magic pending value to get wrong.

Measured before/after on one scene: armed, `Raster_Program_None` cost **512 cycles per frame across
two HInt entries** to accomplish nothing. Two, not one, because `.park` does not advance the cursor.
After: the profiler has no row for the handler and reg `$00` IE1 reads clear.

**Two things in the booking were stale and changed what the right fix was**: `Raster_Clear` no
longer existed (so "sentinel the clear" had nothing to sentinel), and `Raster_Install` *does* have a
caller (`Effects_InstallPreset`) — so "both procs have zero callers, it is latent" was half wrong.
The clear path was unreachable, but the install path is live and every OFF section was paying.

### 4. A live sigil parser abort

`binary_continue`'s loop had no `depth_exceeded` check, though `postfix_expr`'s loop has carried one
all along. After the latch, `unary_expr` returns poison **without consuming** the token, so the loop
read each remaining `-` as a binary minus and built a left-nested `Expr::Binary` chain one node per
token. Recursively **dropping** a 60,000-node chain overflowed the stack: SIGABRT, uncatchable, no
diagnostic — the exact failure `deep_nesting_aborts.rs` exists to forbid.

It looked flaky because **the parse always succeeded and the abort came out of the destructor**, so
whether it fired depended on remaining stack. Isolated it reproduced 3 of 3; inside a loaded
`--workspace` run it sometimes survived. Byte-neutral: all four CRCs identical across the rebuild.

### 5. `tools/effects_gates.py` — one runner for eight gates

Because this tree keeps shipping gates that nothing runs. Every expectation is DERIVED: arm words
from each scene's own pokes plus the bands read out of `ojz_effects.emp`, cost figures computed from
the constants `raster_dsl.emp` ships. The derivation independently reproduces all six arm words in
the scenes README — which matters, because that README says in as many words to re-derive rather
than trust its table.

---

## THE FINDING THAT MATTERS MOST

**The cost-model brief's central claim was FALSE, and the tree already contained the refutation.**

It said `check_density` charged roughly HALF what a fire costs. That came from differencing oracle's
`interrupts.hint`, which **in this ROM is HBlank plus VBlank, entire** — oracle classifies an
interrupt by comparing its handler entry address against `$78` and a fixed ROM window, and
`VBlank_Handler` at `$2310` matches neither. Proof from one live sample, to the cycle:
`interrupts.hint` 9,370 = `VBlank_Handler` 5,690 + HBlank trampoline 3,680, `vint` 0.

| fire | old model | brief's figure | actually |
|---|---:|---:|---:|
| `reg_sh_on` + 3-word `stream_pal_region` | 526 | ~1,002 | **660** |
| 1-word `stream_vsram` | 454 | ~665 | **458** |

**The old model was accurate to 1.5% on both shapes it was fitted to.** It was mis-STRUCTURED, and
one of the four faults was that the per-fire base was charged once per STREAM OP rather than once
per fire — so two errors in opposite directions cancelled on the one shape anyone checked.

Three things to carry forward:

- **`tools/effects_budget_model.toml` had recorded the classifier bug on 2026-08-14**, including the
  phrase "confirmed three times on live data, to the cycle". Two later sessions measured against the
  broken counter anyway. `[[feedback_read_your_own_notes]]`.
- **A caveat saying "never compare two configs that differ in VBlank work" has already conceded the
  counter is not measuring what its name says.** That was the moment to read `OpGetProfilerFrames`;
  it took two minutes when finally done.
- **A model fitted to exactly as many points as it has parameters cannot fail its own pins.** The
  old one had two anchors and two parameters. The replacement is pinned to eight measurements with
  four parameters, and a one-cycle perturbation of `RASTER_STREAM_WORD_CYC` fails five by name.

---

## The measured numbers, for anyone costing a raster effect

| what | cycles |
|---|---:|
| per-fire constant (prologue, arm write, decode, epilogue, `rte`) | **302** |
| a `reg_set` op | 94 |
| a `stream_cram` / `stream_vsram` op, 1 word | 156 |
| a `stream_cram` op, 3 words | 216 |
| a `stream_pal_region` op, 3 words | 264 |
| one dispatch rung (failed compare) | 16 |
| one streamed word | 30 |
| NTSC scanline | 488 |

Whole fires: one `reg_set` **396** · 1-word stream **458** · 3-word `stream_cram` **518** · 3-word
`stream_pal_region` **566** · the OJZ water fire **660**.

**Out-of-sample, exact, on content it was never fitted to**: the live OJZ patched program reads
1690 cyc / 4 calls against a modelled 572 + 660 + 458 = 1690; `OJZ_TestVsram` reads 1030 against
572 + 458. `fire_cost_cycles` models FIRES — `.park` is not one, which is why an armed
`Raster_Program_None` was 512 for two entries rather than 2 x 286.

**A `stream_vsram` word costs exactly what a colour word costs** — measured, not assumed. Same
instruction path: a VSRAM op emits `OP_CRAM` with a different command longword.

---

## The instrument

```bash
python3 tools/raster_cost_probe.py                  # the whole F-series
python3 tools/raster_cost_probe.py --repeat 5       # the noise floor
python3 tools/raster_cost_probe.py --dump --only F3 # every profiler routine row
```

- **Read the per-routine row, never `interrupts.hint`.** Key on the HBlank trampoline's entry
  address (`$FFB452`), which oracle prints as `$FFFFB452` — compare the low 24 bits. The row carries
  no symbol name, so matching `HBlank_Vector_Slot` finds nothing.
- **Noise floor is ZERO** — 5 boots x 8 fixtures, spread 0, `calls` identical too. The "+/- 35"
  figure was `interrupts.hint` on live content with the camera running; **do not carry it forward.**
- **Fixtures install by RAM poke** straight into `Raster_Buf_A` with `Raster_Patch_Tab` /
  `Effects_Offscreen_Entry` / `Raster_Active_Buf` / `Raster_Program` beside it. No ROM bytes, no
  `map.toml`, no frozen-table work, no rebuild per fixture.
- **`calls` is the install check** — it reports the fires the hardware actually took.
- **The profiler is driven by the GUI MAIN loop, not `run_frames`.** `set_profiler` only flips a
  flag. Sleep ~0.4 s after enabling AND after the run, or you get "no profiler frames recorded".
- **`headless_emulator` launches oracle with `env -C <oracle repo>`** — a RELATIVE ROM path silently
  fails to load while every poke and read still answers `ok` against blank RAM. Same symptom.

---

## Traps banked this session

- **Suite totals are a LOWER BOUND.** A crashed test binary emits no `test result:` line, so the
  aggregate read "3717 passed, 0 failed" with a target dead of SIGABRT. Grep `targets failed` and
  `overflowed its stack` as well as summing the totals.
- **A command that appears to fail with no output may have completed its work.** The
  `refreeze --freeze` that returned exit 1 with empty output had already written every golden and
  the provenance entry. Check the tree before re-running a mutating tool.
- **The `Bash` tool died mid-session and came back on its own** — every call, `/bin/echo` included,
  returned exit 1 with empty output for several minutes, workspace-wide (a subagent hit the same
  wall). When it recovered, `ps` showed 588 processes and 42 GB free, so it was NOT the resource
  exhaustion it looked like; but it also showed **9 orphaned `Xvfb`** from the sweep's ~40 headless
  boots, and a long-lived `oracle_gui` that is the user's own instance and must not be reaped. Check
  `pgrep -c -f Xvfb` between probe batches; retry a few minutes before concluding anything.
- **`.emp` expressions cannot span lines.** A multi-line `&&` inside an `ensure` condition, or a
  multi-line `+` in a `return`, is a parse error. Breaking after the `,` between condition and
  message is fine, which is why existing multi-line `ensure`s look like they contradict this.
- **A comptime fn's free names resolve at the CALL SITE**, so the cost model's constants had to be
  DEFINED in `raster_dsl` and pinned to the imported opcodes at module level.
- **An unreferenced `const` is inert.** A poison probe needs an `ensure` that reads it, or it
  silently proves nothing.
- **`git add` exact paths only.** `games/sonic4/data/editor/**` belongs to an auto-commit daemon.
- **Subagents must never touch `mcp__oracle__*`.** `ab_runner`, `raster_cost_probe.py`,
  `raster_off_gate.py` and `effects_gates.py` are all safe — each instance gets its own
  `XDG_RUNTIME_DIR`.

---

## The queue

### 1. Parcel R — mid-screen restore. Unblocked on the cost side.

Its brief deferred it partly because a fourth stream op would enter a model that already
under-charged the third. No longer true: the model charges every op class its measured cost
including dispatch position, and **a new opcode automatically re-prices every op behind it** — so R
costs honestly by adding one `match` arm and one measured work constant, and
`tools/raster_cost_probe.py` measures that constant the same way the other three were measured.

**Read the adjudications first**: `2026-08-18-parcel-r-sweep-adjudication.md`,
`-sweep-2-adjudication.md`, `-review-of-the-review.md`. Settled: the palette mechanism is sound
(snapshot `Palette_Buffer` per line at each `bclr` in `Enqueue_Dirty_Buffers`); `OP_RESTORE_REG` is
dead (three independent kills); scroll needs its own derivation. Recommended scope: **one band SPAN
per program, palette only, program-keyed ship refusal.**

Two process lessons that killed both drafts: **an adjudication MINTS fixes, and those fixes enter
the next draft UNSWEPT** — treat a fix named in an adjudication as a claim to be swept, not a ruling
to build on. And **positive claims need MORE redundancy than kills**: a kill needs one witness,
soundness has to survive all of them.

### 2. Split the VSRAM op class off `RASTER_CRAM_MAX`

Now better founded than it was. Measured: a VSRAM word costs exactly what a colour word does today,
because a `stream_vsram` op IS an `OP_CRAM` with a different command longword — so the split is not
about the word cost. It is about whether a VSRAM write needs `EFX_BLANK_DELAY` (54 cycles) and the
3-word ceiling at all. Ristar writes **42 VSRAM words in one fire**.

**And the new model makes the trade-off visible for the first time**: a separate `OP_VSRAM` opcode
adds a dispatch RUNG, which costs 16 cycles to every op behind it in the chain. Put it last, before
the fall-through, and only `OP_SET_REG` pays. Weigh 54 saved per VSRAM op against 16 added per
`reg_set`, with the ceiling lifted on top — that is now an arithmetic question rather than a guess.
The prior claim that only CRAM writes glitch mid-line is a POSITIVE claim with one witness; sweep it
before building on it.

### 3. Render anchoring in `oracle`, then the framediff instrument

Unchanged, still in that order, second worthless before the first. **A gate may select and assert on
REPORT fields; it may never read pixels.**

### 4. Also open

- The band-budget parcel (relax `check_intervals`) — worth ~3 rows, priced honestly.
- Parcel D — starter pack + content. The visible one.
- Sound packages **5** and **6**; the `STRESS_EVICT` famine root-cause.
- **EFX-2**; the spacing sweep 2/4/8.
- `tools/demo_drift_classifier.py` is still run by nothing. So is `tools/effects_scene_assert.py`
  outside `effects_gates.py` — folding the remaining strays into that runner is cheap and is the
  shape that stops them rotting.
- **sigil:** `lea -NAMED_CONST(aN), aN` is silently DROPPED by the contract-closure walk.
  Workaround: `suba.w #CONST, aN`.
- The replay net still desyncs on master at tick 735 (booked, `docs/BUGS.md`) and the arming recipe
  is still missing. It could not discriminate either parcel this session, and both `--ab` strings
  say so explicitly rather than quietly omitting it.
