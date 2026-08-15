# NEXT-SESSION WORK ORDER — 2026-08-18

Supersedes `2026-08-17-next-session-handoff.md`. Its queue item 1 (`replay_runner` framebuffer dump)
is **DONE in substance but NOT as written** — read "What actually shipped" before planning anything
against it, because the parcel it describes was largely already built and the half that wasn't turns
out to be blocked on an emulator change.

---

## State at handoff

- **aeon** `master` — green, pushed. Suite unchanged from the previous order (3717/0).
- **oracle** `main` — TWO COMMITS, **local only and unpushed**. This repo has no remote and is not
  push-authorised; review them before doing anything else with it.
- **sigil** `master` — untouched this session, still `b30b136a`.

```bash
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
```

---

## What actually shipped

The order scoped "teach `replay_runner` to dump framebuffers" in `oracle-next`. The owner retargeted
it to `oracle` (oracle-next is not ready; conversion comes later). The survey then found most of the
parcel already existed, and the remainder was the wrong half:

| the order wanted | reality |
|---|---|
| headless frame dump | `oracle_cli --frames-dir` already writes `frameNNNN.png` per frame |
| state control (`--poke`) | `ab_runner` scenes already do `poke`/`press`/`run_frames`, by addr or symbol |
| `--expect-identical` | already exists as `ab_runner --selfcheck` (exit 2 = the SCENE is nondeterministic — a distinction the order's design did not have) |
| paired report as the artifact | already exists: the table + per-side `hashes.json` |
| `replay_framediff` over pixels | **not built, and blocked — see below** |

So the parcel became: **make the existing gated captures show BYTES rather than hashes**, and adopt
them for the effects gates.

**Shipped:**
- `oracle/linux-port/harness/ab_runner.py` — a `memory_read` capture (gated like `memory_hash`),
  reporting actual bytes, with a per-byte diff (`+OFF old->new`) printed under a differing row.
  `memory_hash` answers "did this large region change"; `memory_read` answers "what exactly is in
  this small one", with a 1..256 byte ceiling keeping the two distinct.
- `oracle/linux-port/harness/memory_read_test.py` — including the non-vacuity half: poke a byte,
  re-capture, assert the diff is at exactly that offset.
- `aeon/tools/scenes/effects_raster_{mid_band,suppressed,above_screen}.json` + `README.md`.
- `aeon/tools/effects_scene_assert.py` — the gate. Reads a sidecar, asserts words. Never touches an
  emulator, never reads a pixel.
- Evidence: `aeon/docs/benchmarks/effects-p3-removal/GATE-EVIDENCE.md`, "Re-derived through
  `ab_runner`".

**Definition of done, met:** the previous parcel's three-state raster matrix now re-derives through
the tool. Nine expectations, every one computed from the arm formula BEFORE the run, all confirmed;
`--selfcheck` green on all three scenes; the gate demonstrated failing on a wrong expectation and
exiting 2 when asked to assert nothing.

---

## The blocker that matters most

**Pixels are not gateable on `oracle`, by construction.** The VDP renders on a worker thread
(`S315_5313::RenderThread`) draining an async queue, and the framebuffer the GUI copies is not
anchored to the deterministic `ExecuteSystemStep` count. `ab_runner` has known this since it was
written — its screenshot capture is ADVISORY and excluded from the verdict for exactly this reason.

Measured this session so nobody re-measures it: three identical `oracle_cli --frames-dir` runs of
`s4.debug.bin` agreed on 26 of 28 frames and differed on frames 2 and 5 by **8.9%** and **25.0%** of
pixels (rows 134-154 and 98-153). Frame tokens advanced by exactly 1 in all three runs, so the frames
were correctly ALIGNED and the CONTENT differed — this is not a capture-indexing artifact.

**The fix is emulator-side and already named** in `ab_runner`'s docstring: `OpScreenshot` waits for
`_pendingRenderOperationCount == 0` / the `run_frames` frame token, or renders synchronously from
committed VDP state. **That is the prerequisite for any framediff instrument.** Building the
instrument first would produce a careful measuring tool pointed at a nondeterministic source.

Deliberately NOT booked in `docs/BUGS.md`: it is an oracle limitation, not an aeon defect, and
burying it in aeon's bug list is how it gets lost. It lives here and in the gate evidence.

---

## The queue

### 1. Render anchoring in `oracle`, then the framediff instrument

Two parcels, in that order, and the second is worthless before the first. The first is C++ in the
emulator's screenshot path; the second is the report format the 2026-08-16 order already designed
(bands with explicit edges, per-row pixel counts and `min_x`/`max_x`, identical ranges enumerated,
text plus JSON sidecar) — that design is still good and should be reused verbatim.

Note the hard line from that order, which survived contact and is worth keeping: **a gate may select
and assert on REPORT fields; it may never read pixels.** If a gate needs a fact the report cannot
express, the report format grows once, reviewed, and every later gate inherits it.

### 2. The band-budget parcel — relax `check_intervals`

Unchanged from the previous order. Crux settled (one runtime compare, no per-record cost in the
table); what makes it real is the collision PRIORITY ruling and a `Raster_GetChannelBand` contract
change. **Worth ~3 rows** — priced honestly, do not oversell it.

### 3. Parcel R — mid-screen restore. Still STOPPED

Its brief deferred it until an owner of derived state existed. Three now do: `Effects_Screen_L`, the
per-frame schedule rebuild, and now a committed scene+gate pattern for asserting derived state
without an emulator ritual.

### 4. Parcel D — starter pack + content. The visible one.

### Also open

- Sound packages **5** and **6**; the `STRESS_EVICT` famine root-cause.
- **EFX-2**, **EFX-7** — both byte-changing, both deliberately open.
- Splitting the VSRAM op class off `RASTER_CRAM_MAX`; the spacing sweep 2/4/8.
- `tools/demo_drift_classifier.py` is still run by nothing.
- **sigil:** `lea -NAMED_CONST(aN), aN` is silently DROPPED by the contract-closure walk. `-128`
  resolves, `-RASTER_BUF_SIZE` does not. Gate blindness, not codegen. Workaround: `suba.w #CONST, aN`.
- **The 4-test suite delta** versus the 2026-08-16 baseline (3717 vs 3721) is still unattributed.

---

## Traps and findings from this session

- **`ab_runner`'s `load_scene` silently accepted unrecognised capture keys** — a typo'd key captured
  NOTHING and the run still reported green. Found because the plan predicted a `SceneError` that
  never came. Closed with an allow-list plus a test. Worth remembering as a shape: *the absence of an
  expected error is itself a finding.*
- **`oracle` uses `main`, not `master`.** aeon and sigil use `master`. A subagent correctly refused
  to proceed on the mismatch rather than guessing.
- **The harness isolates properly** — `launcher.py` boots each instance under its own
  `XDG_RUNTIME_DIR`/`HOME`, so harness runs cannot collide with a live `oracle_gui`. Subagents may
  run the harness; they still must never touch `mcp__oracle__*`.
- **A 700-frame `emulator_press` wedges the oracle MCP** (StopSystem race). Recovery needs `kill -9`;
  `pkill -x` was not enough. Keep presses <= 200 frames.
- **Oracle's `interrupts.hint` profiler counter INCLUDES VBlank.** Do not read it as HBlank cost.
- **Match build SHAPES before comparing warning counts** (plain 88/14/7, debug 85/13/5). Comparing
  across shapes produced a false regression alarm this session.
