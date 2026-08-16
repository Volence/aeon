# NEXT-SESSION WORK ORDER — 2026-08-16

Supersedes `2026-08-18-next-session-handoff.md`.

---

## State at handoff

| repo | branch | state |
|---|---|---|
| **aeon** | `master` | merged, green, all four shapes rebuilt |
| **sigil** | `master` | merged, green — repin + refreeze done (chain 128, tip `raster-cost-model`) |
| oracle | `main` | untouched this session |

The two repos were merged **as a pair**; a sigil tree at chain 128 does not build a pre-parcel aeon
tree to the frozen bytes and vice versa (`[[reference_sigil_byte_changing_parcel_ritual]]`).

```bash
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
```

### ROM CRCs

| shape | master (before) | branch (after) |
|---|---|---|
| `s4.bin` | `f0e45751` | **`d5daa3e5`** |
| `s4.debug.bin` | `3da516e4` | **`a4438c22`** |
| `demo.bin` | `dca06660` | **`c199280f`** |
| `demo.debug.bin` | `6c5e1875` | **`7aa1aae4`** |

`demo` moves because it links `Raster_Install` and therefore the whole raster module. Total ROM
length is UNCHANGED in every shape — the +4 bytes came out of inter-section padding.

### One environment trap worth keeping

**The `Bash` tool died mid-session and came back on its own.** Every call — including `/bin/echo` —
returned exit 1 with empty output for several minutes, workspace-wide (a subagent hit the same
wall). It recovered without intervention. When it did, `ps` showed **588 processes, 42 GB free**, so
it was NOT the resource exhaustion it looked like; but it also showed **9 orphaned `Xvfb`
processes** from the cost-model sweep's ~40 headless boots, and a long-lived `oracle_gui` that is
the user's own live instance and must not be reaped.

Practical rule: **check `pgrep -c -f Xvfb` between probe batches**, and if the shell goes silent,
retry for a few minutes before concluding anything — and never blanket-`pkill oracle_gui`, because
one of them is the user's.

A second-order trap this exposed: a command that appears to fail with no output **may have
completed its work**. The `refreeze --freeze` that returned exit 1 with no output had in fact
written every golden and the provenance entry. Check the tree before re-running a mutating tool.

---

## What shipped (all on `raster-cost-model`)

### 1. Two live raster bugs, both found while auditing Parcel R

- **`Raster_InstallPatched` ship-entry publish race.** `Effects_Offscreen_Entry` was published ~10
  instructions before `Raster_BuildShipEntry` filled the `Static_Pal_Ship` entry it names.
  `Enqueue_Dirty_Buffers` tests only that pointer and then queues `Static_Pal_Ship`, so a VBlank in
  the window shipped the PREVIOUS program's source/destination/length under this program's trailer.
  Now: clear for the whole install window, build, publish last. 0 is the consumer's inert value, so
  the worst case is one frame with no ship instead of one frame with the wrong one.
- **`Raster_Dense_Lines` never reset per frame.** A dense run whose line count reached past line 223
  never counted down to 0; left set, the next frame's first HInt took `.dense_body` and streamed
  from a stale cursor across the top of the screen. Now rewound beside `Raster_Cursor` in
  `Raster_VBlank`.

### 2. The measured per-fire cost model

`fire_cost_cycles` was `418 + 36 x stream_words` summed over stream ops only. It is now

```
FIRE_BASE + sum over ops of ( fetch + dispatch(depth) + class work + word slope x words + tail )
```

Every constant measured on oracle AND independently confirmed by hand-counting the emitted 68000
stream. Eight fixtures, four free parameters, **zero residual**. Dispatch depth derives from the
opcode order, so inserting an opcode re-prices everything behind it.

**Evidence: `docs/benchmarks/effects-p3/DENSITY-EVIDENCE.md`** — a file four places already cited
and which did not exist. **Rig: `tools/raster_cost_probe.py`.**

---

## THE FINDING THAT MATTERS MOST

**The parcel brief's central claim was FALSE, and the tree already contained the refutation.**

The brief said `check_density` charged roughly HALF what a fire costs. That came from differencing
oracle's `interrupts.hint`, which **in this ROM is HBlank plus VBlank, entire** — oracle classifies
an interrupt by comparing its handler entry address against `$78` and a fixed ROM window, and
`VBlank_Handler` at `$2310` matches neither. Proof from one live sample, to the cycle:
`interrupts.hint` 9,370 = `VBlank_Handler` 5,690 + HBlank trampoline 3,680, `vint` 0.

| fire | old model | brief's figure | actually |
|---|---:|---:|---:|
| `reg_sh_on` + 3-word `stream_pal_region` | 526 | ~1,002 | **660** |
| 1-word `stream_vsram` | 454 | ~665 | **458** |

**The old model was accurate to 1.5% on both shapes it was fitted to.** It was mis-STRUCTURED, not
under-charging — and one of the four structural faults was that the per-fire base was charged once
per STREAM OP rather than once per fire, so two errors in opposite directions cancelled on the one
shape anyone had checked.

Three things to carry forward from this:

- **`tools/effects_budget_model.toml` had recorded the classifier bug on 2026-08-14**, in detail,
  including the phrase "confirmed three times on live data, to the cycle". Two later sessions
  measured against the broken counter anyway. `[[feedback_read_your_own_notes]]` again.
- **A caveat that says "never compare two configs that differ in VBlank work" has already conceded
  the counter is not measuring what its name says.** That was the moment to read
  `OpGetProfilerFrames`; it took two minutes when finally done.
- **The old model could not have failed its own pins**: two anchors, two parameters. Fitting a model
  to exactly as many points as it has parameters proves nothing. The replacement is pinned to eight
  measurements with four parameters, so the pins can fail — and a one-cycle perturbation of
  `RASTER_STREAM_WORD_CYC` fails five of them by name.

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

Whole fires: one `reg_set` **396**; 1-word stream **458**; 3-word `stream_cram` **518**; 3-word
`stream_pal_region` **566**; the OJZ water fire (`reg_sh_on` + 3-word region) **660**.

**A `stream_vsram` word costs exactly what a colour word costs** — measured, not assumed. Same
instruction path: a VSRAM op emits `OP_CRAM` with a different command longword.

---

## The instrument, and how to use it again

```bash
python3 tools/raster_cost_probe.py                 # the whole F-series
python3 tools/raster_cost_probe.py --repeat 5      # the noise floor
python3 tools/raster_cost_probe.py --dump --only F3 # every profiler routine row
```

- **Read the per-routine row, never `interrupts.hint`.** The probe keys on the HBlank trampoline's
  entry address (`$FFB452`), which oracle prints as `$FFFFB452` — compare the low 24 bits, and note
  the row carries no symbol name, so matching on `HBlank_Vector_Slot` finds nothing.
- **Noise floor is ZERO.** Five independent boots per fixture, eight fixtures, spread 0 on all,
  `calls` identical too. The "+/- 35" figure was the spread of `interrupts.hint` on live content
  with the camera running. **Do not carry that number forward.**
- **Fixtures install by RAM poke** — the program image straight into `Raster_Buf_A` with
  `Raster_Patch_Tab` / `Effects_Offscreen_Entry` / `Raster_Active_Buf` / `Raster_Program` beside it.
  No ROM bytes, no `map.toml` entry, no frozen-table work, no rebuild per fixture.
- **`calls` is the install check** — it reports the fires the hardware actually took, so a
  mis-encoded fixture shows up as a wrong fire count before any cycle figure is read.
- **The profiler is driven by the GUI MAIN loop, not by `run_frames`.** `set_profiler` only flips a
  flag; the main loop is what calls `SetProfilingEnabled(true)` and drains the event ring. Sleep
  ~0.4 s after enabling AND after the run, or you get "no profiler frames recorded".
- **`headless_emulator` launches oracle with `env -C <oracle repo>`**, so a RELATIVE ROM path
  silently fails to load while every poke and read still answers `ok` against blank RAM. The only
  symptom is "no profiler frames recorded", which reads like a profiler problem and is not.

---

## Emulator evidence behind the freeze

The `--ab` string on chain entry 128, verbatim:

> `aeon@af32aea7 — ab_runner A/B master vs branch on all three committed effects scenes (mid_band /
> suppressed / above_screen), s4.debug.bin: ALL EQUAL on every gated capture including the whole-VDP
> state_hash, --selfcheck deterministic on all three. Replay fixtures NOT run: the net desyncs on
> MASTER at tick 735 (booked, docs/BUGS.md) and the arming recipe is a still-open queue item, so
> they cannot discriminate this change. ROM effect is +4 bytes in RASTER, everything after shifted
> 4; total ROM length unchanged.`

The three scenes returning EQUAL is the CORRECT result: both bugs are a race window and a dense
overrun, neither reachable in the scenes' normal path. What the A/B rules out is a regression in the
path that IS reachable, and the whole-VDP `state_hash` covers it.

**The replay net is not a usable gate right now and that is not this parcel's doing** — see the
2026-08-14 order's "the arming recipe is missing" section. Do not let a freeze be blocked on it
without saying so explicitly in the `--ab` string, which is what was done here.

---

## Also verified this session

- `effects_budget_check` went from **8 gated rows to 19** — the cost model's constants now have a
  machine-checked path from `effects_budget_model.toml` back to the shipped `.emp`. Poisoned in
  both directions (a wrong TOML row fails; a one-cycle `.emp` change fails five fixture pins).
- The density guard demonstrated **refusing and admitting** by building: two 3-colour fires one line
  apart REFUSED; two lines apart ADMITTED with the ROM byte-identical; four `reg_set`s then a fire
  one line later REFUSED at 678, where the old model scored it **0**.
- Every program shipped in the tree still builds. Nothing is near the boundary —
  `OJZ_TwoChannel`'s bands are 2 fire lines apart (976 cycles) against a heaviest fire of 660.
- `repin` moved 6 pins, all +4: `RASTER` len, then `PALETTE` / `PRESET` /
  `EFFECTS_INSTALL_PRESET` / `RASTER_GET_CHANNEL_BAND` / `PALETTE_COMPOSE` bases. After it,
  `raster_port`, `raster_negative_probes`, `parallax_port`, `game_loop_port`, `soundbankhead_port`
  all re-ran **green**.

### A pre-existing sigil failure, NOT from this parcel

`sigil-frontend-emp/tests/deep_nesting_aborts.rs::depth_diagnostic_does_not_flood` **overflows the
stack** (SIGABRT) in a debug build. The test file has no aeon input at all — pure synthetic source —
and the sigil tree was clean at `b30b136a` when it failed, so it is independent of everything here.
A parser depth guard that is supposed to emit a bounded diagnostic is recursing to death instead.
**This contradicts the 3717/0 baseline the previous order recorded**, so that baseline was either
taken with a different runner or has since regressed. Worth 20 minutes.

---

## The queue

### 1. Finish the freeze ritual (above). Then merge aeon + sigil as a pair.

### 2. Parcel R — mid-screen restore. Now unblocked on the cost side.

Its brief deferred it partly because a fourth stream op would enter a model that already
under-charged the third. That is no longer true: the model charges every op class its measured cost
including dispatch position, and **a new opcode automatically re-prices every op behind it** — so R
can be costed honestly by adding one `match` arm and one measured work constant.

**Read the adjudications before touching it**: `2026-08-18-parcel-r-sweep-adjudication.md`,
`-sweep-2-adjudication.md`, `-review-of-the-review.md`. Settled: the palette mechanism is sound
(snapshot `Palette_Buffer` per line at each `bclr` in `Enqueue_Dirty_Buffers`); `OP_RESTORE_REG` is
dead (three independent kills); scroll needs its own derivation. Recommended scope: **one band SPAN
per program, palette only, program-keyed ship refusal.**

Two process lessons that killed both R drafts and still apply: **an adjudication MINTS fixes, and
those fixes enter the next draft UNSWEPT** — treat a fix named in an adjudication as a claim to be
swept, not a ruling to build on. And **positive claims need MORE redundancy than kills**: a kill
needs one witness, soundness has to survive all of them.

### 3. EFX-7 — `Raster_VBlank`'s explicit-clear arm is unreachable

Independently re-derived twice now: `HBlank_Uninstall` has no live caller, so IE1 is never dropped.
Byte-changing, deliberately open. Note it interacts with the dense-counter fix above — with no
program armed the handler is still installed, so a stale cursor is still walkable.

### 4. Render anchoring in `oracle`, then the framediff instrument

Unchanged and still in that order; the second is worthless before the first. **A gate may select and
assert on REPORT fields; it may never read pixels.**

### 5. Also open

- The band-budget parcel (relax `check_intervals`) — worth ~3 rows, priced honestly.
- Parcel D — starter pack + content. The visible one.
- Sound packages **5** and **6**; the `STRESS_EVICT` famine root-cause.
- **EFX-2**; splitting the VSRAM op class off `RASTER_CRAM_MAX` (now known to only ever make fires
  cheaper, so nothing the model admits today becomes illegal under it); the spacing sweep 2/4/8.
- `tools/demo_drift_classifier.py` is still run by nothing.
- **sigil:** `lea -NAMED_CONST(aN), aN` is silently DROPPED by the contract-closure walk.
  Workaround: `suba.w #CONST, aN`.

---

## Traps banked this session

- **`.emp` expressions cannot span lines.** A multi-line `&&` inside an `ensure` condition, or a
  multi-line `+` in a `return`, is a parse error — the line break ends the expression. Breaking
  after the `,` between condition and message is fine, which is why the existing multi-line
  `ensure`s look like they contradict this.
- **A comptime fn's free names resolve at the CALL SITE**, so the cost model's constants had to be
  DEFINED in `raster_dsl` and pinned to the imported opcodes at module level, not spelled as
  arithmetic over the imports. This module's opening note already said so; it is worth re-reading
  before adding anything to it.
- **An unreferenced `const` is inert.** A poison probe needs an `ensure` that reads it, or the
  program is never evaluated and the probe silently proves nothing.
- **`git add` exact paths only.** `games/sonic4/data/editor/**` belongs to an auto-commit daemon.
- **Subagents must never touch `mcp__oracle__*`.** The `ab_runner` harness and
  `raster_cost_probe.py` are both safe — they isolate each instance under its own
  `XDG_RUNTIME_DIR`.
