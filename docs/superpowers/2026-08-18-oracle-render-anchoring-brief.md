# BRIEF — oracle render anchoring, then the framediff instrument

**For:** an agent with no prior context on this work.
**Two parcels, strictly in order.** Parcel 2 is worthless before Parcel 1 lands, and building it
first produces a precise measuring instrument pointed at a moving target.

---

## The world you are working in

Three repos matter:

| repo | what it is | branch | push? |
|---|---|---|---|
| `/home/volence/sonic_hacks/aeon` | the Mega Drive game engine under development (68000 + Z80) | `master` | yes, pre-authorised |
| `/home/volence/sonic_hacks/oracle` | the C++ emulator used to verify it (an Exodus port) | **`main`** | **NO — no remote, not authorised. Commit locally only** |
| `/home/volence/sonic_hacks/sigil` | the from-scratch Rust assembler that builds aeon | `master` | yes |

**`oracle/linux-port/harness/ab_runner.py` is the gate harness, and it already exists.** Read it
first. It boots isolated headless emulator instances (`launcher.py` gives each its own
`XDG_RUNTIME_DIR`/`HOME`), replays a JSON scene of `poke` / `press` / `run_frames` steps, captures a
VDP `state_hash`, named `memory_hash` regions and `memory_read` byte regions, and prints a gated
OLD-vs-NEW table. Exit 0 = all gated captures equal, 1 = differ, 2 = `--selfcheck` failed (the SCENE
is nondeterministic — a scene bug, distinct from a ROM difference), 3 = usage.

A worked example of it in use, with committed scenes and a gate, is
`aeon/tools/scenes/` + `aeon/tools/effects_scene_assert.py`, and the evidence they produced is
`aeon/docs/benchmarks/effects-p3-removal/GATE-EVIDENCE.md`.

**Do not run emulator MCP tools (`mcp__oracle__*`) from a subagent** — they deadlock. The harness is
safe to run from anywhere because it isolates its instances.

---

## PARCEL 1 — anchor the rendered frame to the deterministic step count

### The defect

`ab_runner` captures a screenshot but marks it **ADVISORY** and excludes it from the verdict. Its own
docstring says why: the VDP renders on a dedicated worker thread (`S315_5313::RenderThread`) draining
an async operation queue, and the framebuffer the GUI copies is **not anchored to the deterministic
`ExecuteSystemStep` count**. Two identical runs can therefore capture a one-render-frame-off image
even when every state hash is byte-identical, so gating on pixels would false-positive on identity.

**Measured 2026-08-17, so you do not have to re-measure it.** Three identical runs of

```bash
cd oracle/linux-port/build && ./oracle_cli /home/volence/sonic_hacks/oracle/settings.xml \
  --rom /home/volence/sonic_hacks/aeon/s4.debug.bin --frames 30 --frames-dir DIR
```

agreed on 26 of 28 frames and differed on frames 2 and 5:

| frame | A vs B | A vs C | differing rows |
|---|---|---|---|
| 2 | 8.9% of pixels | 1.1% | 134-154 |
| 5 | 25.0% | 23.0% | 98-153 |
| all others | 0% | 0% | — |

The frame TOKENS advanced by exactly 1 in all three runs, so the frames were correctly ALIGNED and
the CONTENT differed. This is not a capture-indexing artifact — do not go looking for one.

### The code

- `oracle/linux-port/gui/ControlSocket.cpp:1415` — `OpScreenshot`. It does NOT capture; it fills a
  `pendingScreenshot` hand-off struct, sets `requested`, and polls `done` with a 5 s deadline.
- `oracle/linux-port/gui/main_gui.cpp:2171` — where the main loop services that request and saves
  from its `frame` copy. **This is where the anchoring must happen.**
- `oracle/Devices/315-5313/S315_5313.h:806-827` — the VDP's render-thread state:
  `_renderThreadMutex`, `_timesliceMutex`, `_renderThreadUpdate`, `_renderThreadLagging`,
  `_renderThreadLaggingStateChange`, `_pendingRenderOperationCount`.
- `oracle/linux-port/harness/ab_runner.py` — `_settle_frame_token()` is the existing BEST-EFFORT
  mitigation (poll `status.frame_token` until it stops advancing). It improves the saved image and
  is explicitly NOT an authority. Understand why it is insufficient before replacing it.

### The two candidate approaches

The docstring names both; pick with evidence, not taste, and record the reasoning.

1. **Wait for render-idle on the capture path** — the servicing site blocks until
   `_pendingRenderOperationCount == 0` (and/or the render thread has caught up to the `run_frames`
   frame token) before reading `frame`.
2. **Render synchronously from committed VDP state** — the capture path renders the frame itself
   from committed state rather than reading whatever the worker thread last produced.

(2) is more invasive but is the one that makes the capture a FUNCTION of committed state, which is
what "deterministic" actually means here. (1) may be sufficient and is much smaller. **Measure
before choosing**, and say what you measured.

### Definition of done — non-negotiable

1. **Ten identical `oracle_cli --frames-dir` runs are byte-identical on EVERY frame**, including
   frames 2 and 5. Ten, not three: the defect is a race, and three runs happened to agree on 26
   frames while disagreeing on two. Report the count of differing frames per pair.
2. **`ab_runner`'s screenshot is promoted from advisory to GATED** — `capture_items()` currently
   passes `advisory=True` for it. Flipping that flag is the deliverable; the docstring's "GATED vs
   ADVISORY" section and the closing "(screenshot is advisory...)" line must be rewritten to match.
3. **`ab_runner --selfcheck` passes with the screenshot gated**, on all three scenes in
   `aeon/tools/scenes/`. If it does not, the anchoring is not done — do not widen the control.
4. A before/after record of the frames-2-and-5 numbers above.

### Traps

- **Do not "fix" this by sampling later frames or settling harder.** That is what `_settle_frame_token`
  already does, and it is why the capture is advisory rather than trustworthy. The goal is that the
  captured frame is a function of committed state, not that the race is usually won.
- **Do not gate anything on pixels until (1) above passes.** The whole reason this brief exists in
  two parcels is that an instrument built on an unanchored source measures the race, not the change.
- The emulator is a large C++ codebase with threading throughout. If a change requires holding
  `_renderThreadMutex` on the main thread, think carefully about lock ordering — the header
  documents `_renderThreadMutex` as "Top level, `timesliceMutex` child", and inverting that is a
  deadlock.

---

## PARCEL 2 — `replay_framediff`, the canonical instrument

**Only start this once Parcel 1's definition of done is met.**

### The settled design (2026-08-15, by a Fable adviser briefed with a finished gate as the
requirements list — reuse it, do not redesign it)

**Whole frames are the dump primitive. Named row ranges are REFUSED.** The load-bearing half of a
previous parcel's result was "zero differing pixels at rows 120..223" — an assertion about rows a
fixture author would never have thought to declare, so a declare-what-matters format structurally
cannot express the gate.

The instrument, per checkpoint:
- differing rows grouped into **bands with explicit edges**
- per differing row: a **pixel count** and **`min_x` / `max_x`**
- the **identical ranges enumerated explicitly** (an assertion of absence must be visible)
- text output plus a **JSON sidecar**

**No committed golden images.** Pixels never enter the repo; dumps go to scratch and are disposable.
The committed artifact is the small framediff REPORT — it churns only when an effect's geometry
actually moves, which is exactly when review should look, whereas a PNG golden churns on any pixel
anywhere.

**The hard line that stops every parcel re-inventing its instrument:** a gate script may select and
assert on REPORT fields; **it may never read pixels**. If a gate needs a question the report cannot
answer, the REPORT FORMAT gets extended — once, reviewed, versioned with the harness — and every
later gate inherits it. Do not add assertion flags to the runner.

### Where it should live

`aeon/tools/effects_scene_assert.py` is the precedent: the harness measures, an aeon-side script
asserts. A framediff binary is emulator-agnostic (it diffs two directories of frames), so it
survives the eventual move to `oracle-next` untouched. Prefer that property.

### Definition of done

Re-derive an existing pixel result through the tool. The best available target is the water
boundary's rendered position: `aeon/docs/benchmarks/effects-p3-removal/GATE-EVIDENCE.md` records
that at latched line 60 the tint covers everything below row 60, and the three-state matrix gives
you scenes that place the boundary at known rows. If the tool cannot state "rows 0-59 identical,
rows 60-223 differ, band edge at 60" from two runs that differ only in one anchor poke, it is not
finished.

---

## Process expectations

- Commit every step; never leave either repo broken.
- `git add` exact paths only — never `-A`, never a glob. `aeon/games/sonic4/data/editor/**` belongs
  to an auto-commit daemon; never stage or touch it.
- Verify the branch at commit time (`git branch --show-current`) — parallel sessions share these
  trees, and `oracle` is `main` while the others are `master`.
- For a judgement call inside the approved scope, dispatch a Fable adviser
  (`Agent(model: "fable", ...)`) with the evidence and your leaning, and record the ruling.
- For anything that changes DIRECTION, freezes a format, or is hard to reverse: **STOP** and write
  the brief instead.
