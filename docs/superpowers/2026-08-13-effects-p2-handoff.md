# Next-session handoff — 2026-08-13 (Effects P2)

> **STATUS UPDATE (later the same day): §4a IS CLOSED. The merge gate is green.**
> All 14 failures are fixed; the strict suite is 3672/0 and aeon pytest 941/2-skipped.
>
> - **The `ojz_act_pool` shape-invariance blocker was a STALE FIXTURE, not a shape leak.**
>   Adjudicated with byte evidence in
>   `notes/2026-08-13-ojz-act-pool-shape-invariance-ruling.md`. Nothing was re-baselined;
>   the gate now measures the section's own bytes plus a map-fill tail check, and was
>   negative-probed. **Note the numbers in §4a below are wrong** — the real delta is
>   2 bytes (`0x2F16`/`0x2F18`), and the "15166" belonged to a DIFFERENT failure
>   (`generated_pins_match_the_hand_typed_baseline`), which §4a had conflated into the
>   same row.
> - **The replay-net item is NOT this lane's.** Both master and effects-p2 desync
>   byte-identically (tick 1282, actual `BBB93779`, expected `1F420103`), so P2
>   contributes zero delta to the net. The break is inherited from the Knuckles C4 merge,
>   whose own re-stamp was never done. Evidence + the corrected premise (the hash is
>   layout-proof BY CONTRACT, so "RAM moved therefore expect drift" is not a safe default)
>   in `notes/2026-08-13-replay-net-attribution.md`.
> - Two incidental catches: the tranche5 negative probes (a) and (b) had gone **vacuous**
>   (they assert only that resolve/link failed, which the unresolved `Palette_Compose`
>   satisfied for the wrong reason), and `sound_api_port`'s synthetic consumer LMA is now
>   **derived** instead of hand-typed after going stale for the third time.
>
> Still open below and unchanged: §2 (the reserved-register ruling) and §3 (the
> `Palette_DeriveVariant` defect — now root-caused on hardware, see the session summary).

Supersedes the Effects P2 half of `2026-08-12-next-session-handoff.md` (§4). The
Knuckles half of that doc is **done — merged as `50d54612`**.

**Master is untouched and green.** All work below is on the branch pair.

| | aeon | sigil |
|---|---|---|
| worktree | `.worktrees/effects-p2` | `.worktrees/effects-p2` |
| branch | `feat/effects-p2-palette` | `feat/effects-p2` |
| tip | `58c1b857` | `a5b2a5b2` |

Build with THIS lane's binaries (the sigil module registry is global per binary pair):

```
SIGIL_BUILD=/home/volence/sonic_hacks/sigil/.worktrees/effects-p2/target/release/sigil \
SIGIL_EMIT=/home/volence/sonic_hacks/sigil/.worktrees/effects-p2/target/release/emit_sound_blob \
DEBUG=1 ./build.sh
```

Shapes: debug `f9b3d140` / 711252 · plain `2e932149` / 696788 · 31.8 KB free before
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
- **World-anchored water + an off-screen wrap bug fixed.** The boundary was a screen
  row; it is now anchored to a world Y. The runtime patch path had no off-screen guard
  (the comptime one does), so a negative screen line wrapped into an arbitrary on-screen
  row — unreachable while the line was a build-time constant, reachable on every
  vertical scroll once world-anchored. All four branches verified on hardware.

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

### 4a. Merge gate — repin/refreeze DONE, PORT-FLIP remains

**repin + refreeze are DONE** (sigil `a5b2a5b2`, provenance chain entry 108). Golden
CRCs agree with the aeon build exactly (s4 `2e932149`, s4_debug `f9b3d140`).

Gate went **139 failed -> 14 failed** (3658 passed). The remaining 14 are the
PORT-FLIP set — port tests compile one module in isolation, so a NEW cross-seam
reference breaks them until the test's symbol table is taught about it. Enumerated:

| failure | cause | fix |
|---|---|---|
| `parallax_{,debug_}region_matches_reference` | parallax now calls `Palette_InstallCycleSection` (Task 8 cycling hook) | add a pin + an entry in `parallax_port.rs`'s symbol table (pattern: the existing `Palette_LoadSection` / `Raster_InstallSection` rows) |
| `game_loop_{,debug_}region_matches_reference` | game_loop now calls `Palette_Compose` | same pattern, `game_loop_port.rs` |
| `act_descriptor_{,debug_}region_matches_reference` | unresolved `OJZ_TestGradient` + `OJZ_ShimmerCycle` data symbols | teach the port test's scope about the two new fixtures |
| `sound_api_debug_region_matches_reference` | `sound_api [0x9D30,0xA182)` now overlaps the test's hard-pinned `sec40960 [0xA000,0xA006)` | move the test's synthetic pin |
| `ojz_run_a_{,debug_}regions_match_reference` | **`ojz_act_pool len must be shape-invariant`, 12056 vs 15166** | **INVESTIGATE FIRST — do not re-baseline** |
| `two_module_*` (3), `drain_define_is_load_bearing`, `generated_pins_match_the_hand_typed_baseline` | layout-dependent harness baselines | re-derive after the above |

> **The `ojz_run_a` one is the reason this was not finished.** `debug_len == plain_len`
> for a ported level section is the SAME invariant that killed the Knuckles DEBUG test
> platform (see the 2026-08-12 handoff §2c) — level DATA must be shape-identical
> because the port tests compile ONE length for both shapes. A 3110-byte difference is
> either a genuine shape-dependent leak into level data or a stale port fixture.
> Establish which BEFORE touching it; re-baselining a real shape leak would bury
> exactly the class of bug that invariant exists to catch.

> **TRAP, verified this session:** a plain `cargo test` in sigil defaults
> `AEON_DIR` to `/home/volence/sonic_hacks/aeon` — the MAIN tree, on master. It
> reports a clean **3672 passed / 0 failed** that says nothing about the branch. You
> MUST pass `AEON_DIR=<the effects-p2 worktree>` or you are gating master against
> itself. Same family as the "refreeze --check is NOT the goldens" trap.

Commands that worked, for the record:

```
# repin
SIGIL_EMIT=<sigil-wt>/target/release/emit_sound_blob SIGIL_BLOB_LEN_DRIFT=warn \
  cargo run --release -q -p sigil-harness --bin repin -- --aeon <aeon-wt>

# refreeze
SIGIL_EMIT=... SIGIL_BUILD=... AEON_DIR=<aeon-wt> SIGIL_BLOB_LEN_DRIFT=warn \
  cargo run --release -q -p sigil-harness --bin refreeze -- \
    --freeze effects-p2 --ab docs/benchmarks/effects-p2/GATE-EVIDENCE.md --note "..."
```

The `BLOB_LEN_*` / `Z80_SOUND_SIZE` / seam-1 re-pin steps were no-ops as expected (this
parcel touches no sound code) — confirmed, not assumed: `refreeze` reported
`pins.rs unchanged` on its internal repin pass.

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
- The **gradient is not world-anchorable** yet — its arm words are comptime ROM
  constants. Making it movable means installing it into `Raster_Buf_B` the way water
  is, then reusing `Raster_PatchWaterLine`'s (now correct) off-screen handling. Left
  unbuilt rather than built speculatively.
- A fully-submerged view keeps a 3-line un-effected sliver at the top (screen lines
  0-2 are the priming records'); a seamless full-screen state must come from the
  program's frame-top init words — a content decision.
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
5. **A `comptime fn`'s free names resolve at its CALL site, not where it is defined.**
   Broader than the struct-literal case: any module-local constant a comptime fn
   spells must be visible in the CALLING module. In a scalar field this is a loud
   `unknown name`; in a struct-literal field it degrades SILENTLY to a label ref.
   Either import into the consumer, or inline the literal and pin it with a
   module-scope `ensure` (what `water_arm0` does).

## 6. Suggested order

1. The repin/refreeze ritual + frozen-table audit + replay re-stamp, then merge the
   **aeon+sigil pair** (§4a). This is the only thing between P2 and master.
2. The `Palette_DeriveVariant` 15%-of-frame defect (§3).
3. The reserved-register ruling once §2's caveat is re-measured in real content.
4. Then Phase 3: `raster_dsl`/`palette_dsl` constructors, the shareable preset format,
   the forkable starter pack, the dead-data proof, world-anchored water, and pruning
   the test fixtures for real content.
