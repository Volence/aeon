# NEXT-SESSION WORK ORDER — 2026-08-14

Written at the end of the blanket-register-restore session, mid-flow, for a clean restart.
**Two decisions were already taken by the user. Do them in this order.**

---

## State at handoff

**Both repos are on `master`, green, nothing in flight.**

- aeon `84616803` — Merge parcel/blanket-register-restore: the composability unlock
- sigil `2863d720` — Merge parcel/blanket-register-restore: harness lockstep
- refreeze **chain 115**; four build shapes green; sigil suite **3711 / 0**

Working tree has only the pre-existing editor-JSON churn (auto-commit daemon territory) —
`games/sonic4/data/editor/…` and `games/sonic4/data/sprites/object-bindings.json`. Not ours.

Build env (build.sh hard-errors without these):
```bash
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
```
Current ROM CRCs: s4.debug `c13412fc` · s4 `abb6777d` · demo.debug `7c39eda5` · demo `db3f9b0f`

---

## TASK 1 (do first) — close the four testing gaps on the just-merged parcel

**User ruling: "Close the top four now."** These are gaps in the parcel that already merged;
anything found lands as a follow-up commit on master. Budget ~20 min. Emulator work is the
CONTROLLING SESSION's — never a subagent (oracle MCP from a background agent deadlocks).

### 1a. Render the dense raster fixtures — HIGHEST RISK

`OJZ_TestGradient` and `OJZ_TestRamp` each shrank by 2 words when the init words were deleted.
They have **no hand-pin twin** (the three pins cover only the sparse tier), so they were verified
ONLY by reading emitted bytes. `OP_RUN_RAMP` itself shipped one day earlier (chain 113).

Nobody has looked at them since. Find which OJZ sections bind them (`games/sonic4/data/parallax/configs.emp`,
the `sec_raster_table` bindings) and render each. A/B against a master build from BEFORE
`84616803` if anything looks off.

Expected emitted shapes, already read out of the ROM last session:
```
OJZ_TestGradient  0004 8A5D 0000 8A00 0000 8A00 0001 0006 C048 0000 0060 0001 2CFA 8AFF FFFF
OJZ_TestRamp      0000 8A6D … 0008 4002 0010 0060 00000000 00008000 8AFF FFFF
```
(`$8A5D` = gap 1->95 for `top=96`; step `$00008000` = 0.5 px/line.)

**If they render correctly, add a dense-tier hand pin** so the next parcel is not in this position.

### 1b. Negative-probe the three `$0F` IPL asserts

They were added but **never watched to fire**. A guard never observed failing may be vacuous, and
this tree has a documented history of exactly that (`reference_verified_vacuous_gates`).

Sites: `engine/level/bg.emp`, `engine/level/section.emp`, `engine/level/plane_buffer.emp` —
each `if DEBUG == 1 { move.w sr,d0 · andi.w #$0700,d0 · assert.w d0, hs, #$0600 }`.

Probe: temporarily lower the mask at ONE main-loop excursion (e.g. change `section.emp`'s
`move.w #$2700, sr` to `#$2300`), build DEBUG, confirm the assert trips to the MD Debugger
screen naming the assert, then REVERT. Record the exact failure text.

### 1c. Exercise `Set_VDP_Reg` once

Zero callers — its indexed write and its `assert.w d0, ls, #$12` bound have never executed.
Call it once from a scratch site with a known register (e.g. reg `$07` backdrop colour) and
confirm the colour changes on the next frame; separately confirm an out-of-range index trips the
bound assert in DEBUG. Revert the scratch call.

### 1d. Boot `demo` and the release shape

Neither was ever run this parcel — only sonic4 DEBUG.
- `DEBUG=1 ./build.sh demo` then boot: expect a white 16x16 box on a dark-blue backdrop.
  (`demo_state.emp` lost an `ori.l` in this parcel.)
- Boot plain `s4.bin`: expect OJZ renders identically to the DEBUG shape (asserts self-gate to
  zero bytes, so plain differs only by their absence).

**Any byte-moving fix here needs the full ritual again** — repin, refreeze, both sigil binaries
rebuilt, suite to 3711/0, merged as a pair. Comment-only fixes do not.

---

## TASK 2 — Effects P3 **Parcel 0**: re-stamp the replay net

**User ruling: Parcel 0 next.** Spec: `docs/superpowers/specs/2026-08-13-effects-p3-design.md` §2.0.
Runbook: `docs/superpowers/plans/2026-08-13-replay-net-restamp.md`.
It is first because it is "what makes C's and D's regression evidence mean anything."

### The blocker to solve FIRST — the arming recipe is missing

Last session could not measure the net at all. Hand-arming playback is **not reproducible**:
three attempts on the SAME ROM (`c13412fc`) gave three different actual hashes.

| arming point | actual `d0` |
|---|---|
| ~20 s free-run, then pause | `0xBD37D0BF` |
| first `Input_Tick` after reset (bp `$2602`) | `0x10023248` |
| armed too early | **write wiped** — state init zeroes `Input_Source` AND `Replay_Ptr` |

So the fixture expects a **specific starting game state**, and no doc found says which. The
restamp runbook §3 documents the harvest loop but assumes playback is already running.
**Reconstructing that recipe is the first sub-task** — likely by finding how the fixture was
originally RECORDED (`Input_Source = INPUT_RECORD`, and whatever state entry that ran from).

### Hard-won mechanics (do not rediscover these)

- **Arm by writing:** `Input_Source = 1` (INPUT_PLAYBACK) and `Replay_Ptr = <fixture> + 20`.
  `HEADER_LEN` is **20** (`tools/replay_pack.py`).
- **Addresses are per-build — re-read them from the `.lst` every time.** Deleting `VDP_Dirty_Mask`
  shifted them: on `84616803` it is `Input_Source $FFFF8036` / `Replay_Ptr $FFFF803C` /
  `Replay_OJZ_Fixture $A1D80`; on the pre-merge master they were `$FFFF803A` / `$FFFF8040` /
  `$A1DA0`. Using the wrong pair silently does nothing.
- **oracle `write_memory` wants 24-bit, `0x`-prefixed**: `0xFF803C`, NOT `FFFF803C` and NOT bare
  `FF803C`. `breakpoint_add` likewise needs `0x26A2` — a bare `26A2` is parsed as decimal.
- **Read `d0` at a breakpoint, never off the crash screen.** Break at
  `$engine.replay$Input_Tick$desync` (`$26A2` on both recent builds) and call
  `emulator_registers`. The MD Debugger's 8x8 font misreads badly — an OCR of master's dump gave
  `DD37D08F` where the register actually held `0x0D37D0EB`.
- `Replay_Check_Log` is **record-mode only**; it is not populated during playback.
- `emulator_press` wedges intermittently (StopSystem race) and blocks ALL MCP until
  `pkill -9 -x oracle_gui`. Prefer `emulator_hold` + free-run + screenshot. Short presses wedge
  less than long ones.

### Known state of the net

Master desyncs at **tick 735** (`d1 = 0x2DF`), expected payload `d2 = 1D375066`. Booked in
`docs/BUGS.md` — owed since the character-lens-sweep merge (`b7b0f299`), which deliberately
changed Sonic's grounded behaviour. ~15+ checkpoints from ring ~733 to the 1721 stream end need
re-stamping. Note an EARLIER re-stamp (`32a79e1d`) already happened and was re-staled by that merge.

**Re-recording is NOT an option**: the stream uses `BUTTON_C` in four runs including the spindash
rev inside the desyncing region, and the oracle driver cannot press `c`.

**The gate is NOT "both fixtures green"** — that is true by construction for a re-recorded fixture
and tests nothing. The spec wants the divergence to disappear **for the attributed reason**.

**A pure re-stamp needs no sigil ritual** — only 4-byte hash payloads change, so fixture length
holds, `EndOfRom` does not move, aeon-only.

---

## After Task 2

Effects P3 **Parcel C** (EffectsPreset / `sec_effects` / all data relocation — the layout mover),
then **Parcel D** (starter pack, world-anchored gradient, section rebinding). D is the one the
blanket restore directly unblocks: `WATER_TEMPLATE_ARM0_OFF` no longer depends on `init_count`.

Also open, unrelated: sound packages 5 and 6, the `STRESS_EVICT` famine root-cause
(`project_open_work_inventory` memory), and the aborting-test-binary item below.

---

## Two things booked in `docs/BUGS.md` last session — read them before trusting any gate

1. **The replay net was never validly measured** for the blanket-restore parcel (Task 2 above).
2. **sigil's `deep_nesting_aborts` binary stack-overflows and aborts**, printing no `test result`
   line, so its tests count **0 passed / 0 failed**. Every recent total — including this parcel's
   `3711/0` — is a **LOWER BOUND, not a complete count**. Pre-existing, and it is itself the
   anti-abort regression test. User ruled: booked, not chased.

## Session lessons worth carrying

- **Verify a computed offset against emitted bytes, not the prose that derived it.**
  `WATER_TEMPLATE_ARM0_OFF` was 2; the plan said 4. At 4 the water patch would have decremented a
  record's `op_count` and `dbf` would have walked ~35k words of ROM as opcodes inside a raw
  interrupt handler. The hand pins caught it.
- **Build all four shapes.** `section.emp`'s bracket is `with z80_stopped if SOUND_DRIVER_ENABLED == 0`,
  so sonic4 (sound ON) builds green while `demo` fails with `[context.escape]`.
- **A/B against master before calling an anomaly a bug.** Two screens that looked like corruption
  (whole-screen red, whole-screen blue) were the per-section palette and water fixtures rendering
  correctly. Neither was readable from the branch capture alone.
