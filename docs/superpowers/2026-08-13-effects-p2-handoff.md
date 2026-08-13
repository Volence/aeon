# Next-session handoff — 2026-08-13 (Effects P2)

Supersedes the Effects P2 half of `2026-08-12-next-session-handoff.md` (§4). The
Knuckles half of that doc is **done — merged as `50d54612`**.

**Master is untouched and green.** All work below is on the branch pair.

| | aeon | sigil |
|---|---|---|
| worktree | `.worktrees/effects-p2` | `.worktrees/effects-p2` |
| branch | `feat/effects-p2-palette` | `feat/effects-p2` |
| tip | `6daf6c6d` | `c4938391` |

Build with THIS lane's binaries (the sigil module registry is global per binary pair):

```
SIGIL_BUILD=/home/volence/sonic_hacks/sigil/.worktrees/effects-p2/target/release/sigil \
SIGIL_EMIT=/home/volence/sonic_hacks/sigil/.worktrees/effects-p2/target/release/emit_sound_blob \
DEBUG=1 ./build.sh
```

Shapes: debug `fa5c04e5` / 711162 · plain `2add4b51` / 696698 · 31.8 KB free before
stack · aeon pytest **941 passed, 2 skipped**.

---

## 1. What this session closed

- **Rebased the pair onto post-Knuckles master.** aeon rebased clean. The sigil side
  was rebuilt as `master + the ISA fix cherry-picked`; the two old repin commits were
  DROPPED deliberately — they pinned a pre-rebase layout and the ritual regenerates
  them anyway.
- **Task 5 (dense tier) — GATED AND PASSING.** Authored the fixture that never
  existed (`OJZ_TestGradient`, 96-line run on OJZ section 2) plus its authoring
  surface, and fixed a real off-by-one it exposed: the ENTER schedule puts the setup
  fire at `T-1`, not the `T-2` the sparse rule predicts, because entering a run costs
  its own pipelined arm. All 7 ramp boundaries land exactly.
- **Task 4 (row-119) — DECIDED.** Blanking delay adopted and made unconditional; the
  fire-early option DELETED (it was dead code — its helper was imported but never
  called, and removing it changed zero bytes).
- **S/H PROVEN — closes handoff §4.5.** 1.95x brightness step DOWN across the
  boundary. The claim that OJZ art is all high-priority is wrong for section 1.
- **Task 9 budget model populated** from oracle profiling.
- Sigil now reports every build error, not just the first.

Evidence: `docs/benchmarks/effects-p2/GATE-EVIDENCE.md` (+ 4 captures).

## 2. THE ONE DECISION WAITING ON THE USER

**May the dense tier reserve a global register?** (old §4.4)

Measured answer: **it is a headroom improvement, not a correctness or lag fix.** A
96-line dense run costs 41579 cyc/frame (32.5%) vs 8358 (6.5%) sparse — marginal
~342 cyc/line, an upper bound including profiler instrumentation and exception
entry. But it produces **zero lag frames**: `VSync_Wait` measured 62.8% idle WITH the
run active vs 62.4% without. The corpus form (~26 cyc/line, survey Ruling 4c) buys
back headroom, at the cost of changing engine-wide register conventions.

Caveat that could flip this: `OJZ_ScrollTest` is a near-empty game state. A populated
level has far less idle to absorb the run. **Re-measure in real content before
concluding it is free.** The conservative handler ships unchanged either way.

## 3. Highest-value bug found, NOT fixed

**`Palette_DeriveVariant` costs 15.1% of every frame** (19332 cyc) — bigger than the
entire sparse raster tier, and *identical in section 1 and section 2*. This
contradicts the budget model's own `compose_static_frame = "one compare"`: a frame
with nothing changing was supposed to be nearly free. Either the early-out never
fires or a variant is held active in sections that do not use one.

Left for a session that can read the palette-engine design properly — it is a
palette defect, not part of the Task-4/5 raster parcel. **This is the top
optimisation target in the effects suite.**

## 4. What remains before merge

### 4a. The repin/refreeze ritual — THE blocking item

Running the sigil suite with `AEON_DIR` pointed at the P2 worktree gives
**3533 passed / 139 failed**, including `pins_rs_is_current`. These are the expected
byte comparisons against pre-P2 goldens; the ritual is what clears them.

> **TRAP, verified this session:** a plain `cargo test` in sigil defaults
> `AEON_DIR` to `/home/volence/sonic_hacks/aeon` — the MAIN tree, on master. It
> reports a clean **3672 passed / 0 failed** that says nothing about the branch. You
> MUST pass `AEON_DIR=<the effects-p2 worktree>` or you are gating master against
> itself. Same family as the "refreeze --check is NOT the goldens" trap.

Ritual (per `memory/reference_sigil_byte_changing_parcel_ritual`): `SIGIL_BLOB_LEN_DRIFT=warn`
→ rebuild BOTH sigil binaries → rebuild aeon with the tripwire ARMED → `repin` →
`refreeze --freeze <parcel> --ab <evidence>` → strict suite → `refreeze --check` +
`repin --check`. This parcel touches no sound code, so the `BLOB_LEN_*` /
`Z80_SOUND_SIZE` / seam-1 re-pin steps should be no-ops (as they were for Knuckles) —
confirm rather than assume.

Also owed at merge: the **frozen-table audit** (this lane regenerated placement
tables mid-parcel) and the **replay-net re-stamp** — the RAM layout moved
(`Palette_State`), so expect layout-induced hash drift; disposition it via the
probe-ROM logger per `docs/superpowers/notes/2026-08-09-replay-net-rerecord-ab.md`,
and STOP if it looks behavioural rather than layout-induced.

### 4b. Smaller residuals, all written up in GATE-EVIDENCE.md

- A dense run leaves its last stream value latched below the run; real content must
  author a restoring op. (Also means the run's END line is not directly observable.)
- A fire mixing `OP_SET_REG` with a CRAM op still switches its mode register mid-line
  (~45% across). Extending the delay there costs ~40 cyc of a ~60-cyc budget — needs
  a cycle measurement first.
- Dense tier not yet captured under MOTION (the discriminator used is
  art-independent, so a static frame is sound for the claim made, but a moving
  capture is still owed).
- Two budget rows honestly unmeasured: `OP_PAL_REGION` handler delta, fade step —
  neither scenario was armed.
- Test fixtures are garish placeholders; Phase 3 prunes them for real content.

## 5. Reproduction notes that cost real time — read before touching oracle

1. **`emulator_read_cram` is FRAME-LATCHED.** It cannot see a mid-frame CRAM write and
   returns the base palette at every scanline. Per-scanline CRAM sampling is NOT a
   valid instrument for raster work. Measure the framebuffer.
2. **Player SST base is `$FF8D86`**, not the `$FF8BA4` in the 2026-08-12 handoff —
   `Palette_State` moved the RAM. Take it from `emulator_player_state`, never a doc.
3. **`Sec` fields are "0 = keep current", which masks install failures.** A
   physics-mode teleport drops the player into a pit; he lands in grid row 2, whose
   `sec_raster_table` is 0, so the PREVIOUS section's program stays installed and it
   reads exactly like a failed install. Confirm `debug_flag` (SST `+$3C`) is `$FF`
   before teleporting, and check `Camera_Y` as well as X.
4. **The camera is soft-clamped** and converges to a teleport over several hundred
   frames. For an A/B, wait until `Camera_X`/`Camera_Y` STOP CHANGING — comparing two
   captures at different camera positions makes the pixel counts meaningless.
5. **A `comptime fn`'s struct-literal field values resolve at the EMISSION site's
   scope**, so a constructor's own module-local constants must be imported into the
   consumer module. An unresolved bareword degrades SILENTLY to a label ref.

## 6. Suggested order

1. The repin/refreeze ritual + frozen-table audit + replay re-stamp, then merge the
   **aeon+sigil pair** (§4a). This is the only thing between P2 and master.
2. The `Palette_DeriveVariant` 15%-of-frame defect (§3).
3. The reserved-register ruling once §2's caveat is re-measured in real content.
4. Then Phase 3: `raster_dsl`/`palette_dsl` constructors, the shareable preset format,
   the forkable starter pack, the dead-data proof, world-anchored water, and pruning
   the test fixtures for real content.
