# Next-session handoff — 2026-08-12 (Knuckles C4 + Effects P2)

Two lanes ran in parallel worktrees this session. **Neither is merged.** This doc is
the complete state so a fresh session can finish both without re-deriving anything.

---

## 0. The lanes and their worktrees

| Lane | aeon worktree / branch | sigil worktree / branch |
|---|---|---|
| Knuckles C4 | `.worktrees/knuckles-c4` / `feat/knuckles-c4` | `.worktrees/knuckles-c4` / `feat/knuckles-c4` |
| Effects P2 | `.worktrees/effects-p2` / `feat/effects-p2-palette` | `.worktrees/effects-p2` / `feat/effects-p2` |

**Each lane has its own sigil binary pair.** Build with that lane's binaries:

```
SIGIL_BUILD=<sigil-worktree>/target/release/sigil \
SIGIL_EMIT=<sigil-worktree>/target/release/emit_sound_blob \
DEBUG=1 ./build.sh
```

The sigil module registry (`crates/sigil-harness/src/native.rs`) is global per binary
pair, so never build one lane with the other's binaries. Merge aeon+sigil **as a pair**,
one lane at a time — master must never hold a registry naming modules master's aeon lacks.

---

## 1. Knuckles C4 — what shipped

Full moveset: glide, glide-fall, slide, wall-catch, climb, ledge clamber. Verified
end-to-end on oracle with natural input. **Nine real bugs found and fixed**, one
reported bug **withdrawn** (see §3).

Commits on `feat/knuckles-c4` (oldest first):
`06c4eab5` dust palette permute · `b630be35` overhang finding note · `3ab8ad6f`
climb-down floor-probe fix · `70f523a9` 1-3px recess divergence · `6a6abaeb` dust
priority band · `d551b5ea` slide ObjectMove · `8e001fcf` solid-objects-are-floors
principle docs · ~~`4ea60239` DEBUG test platform~~ (reverted `8dc43d9b`, see §2c).

### The nine bugs (each was invisible to build gates and unit tests)

1. **`Glide_Collide` floor PAIR mis-read the wall face** — after the wall push snapped
   the player flush, the outer floor sensor read the wall's TOP-solidity as ground, so
   `GLF_INAIR` cleared and the dispatch took `.hit_floor` before ever consulting
   `GLF_PUSH`. Wall-catch was unreachable. Fix: single centre floor probe (S3K `sub_11FD6`).
2. **Ledge clamber never terminated** — check-then-advance left a resting state
   (`knux_step=16`, timer 0) that depended on a later poll. Fix: advance-then-test,
   S3K's order (`:31540`), so the terminal value is never a resting state.
3. **Climb jump-off read `Ctrl_1_Held`** — glide *requires* the jump held, so every
   catch auto-ejected instantly. Fix: `Ctrl_1_Press` (S3K `:31414` is a fresh press).
4. **Climb floor probes used the STANDING radius (19) while the climb runs the 10px
   ability box** — sensor origin 9px below his feet, so at a step base it slid under the
   floor surface, reported no floor, and he descended through the world to the bottom
   skim. Fix: probe at the climb-box feet (`+9`), S3K `:31334`/`:31352`.
5. **Climb froze on a 1-3px wall recess** — sloped grass tops make the face recede
   gradually; S3K freezes here too (`tst.w d1; bne .notMoving`) but its walls are
   flat-topped. **USER-RULED DIVERGENCE**: 1-3 now keeps climbing (embedded still
   freezes); mirrored on descent, which was spuriously *detaching*.
6. **`PSTATE_SLIDE` never integrated position** — velocity decayed correctly with
   `x_pos` frozen; the dust piling in one spot is what exposed it. Root cause is a
   structural translation gap: S3K integrates position in the glide family's shared
   wrapper (`Knux_Glide_Freespace`) *before* dispatching to `Knuckles_Sliding`, so that
   routine contains no move at all; our table-dispatched states must each own one.
7. **Dust rendered BEHIND the player** — S3K draws it in front (dust `$80` vs player
   `$100`; in S3K lower = front, in ours higher band = front). Fix: band 5 =
   `PLAYER_PRIORITY_BAND + 1` with a comptime ensure.
8. **Dust rendered red as Knuckles** — the shared dust art draws on CRAM line 0, which
   is the per-character line. Fix: permuted Knuckles' own line 0 (art + palette together,
   lossless) so grays sit at the shared indices **4/6/7 = `$0ECC`/`$0EEE`/`$0CAA`**,
   byte-matching Sonic/Tails, S3K's own convention; build-time ensure across CharacterDefs.
9. **Ledge top-out hop** — the ability→standing box restore applied its feet-planted
   9px lift at the clamber finish, where S3K applies none. Exempted the ledge finish only.

Plus: Tails' appendage was rendering next to the debug-fly cursor (fixed), and slide
dust was never wired (now wired; S3K's cadence-4 covers both the landing burst and the
ongoing trail).

### Deliberate divergences from S3K (documented in-module + DEFERRED_WORK)

- **1-3px wall recess keeps climbing** (bug 5) — S3K stops; our terrain has sloped tops.
- **Solid object tops behave as floors for every player state** (user ruling). Verified
  working: glide + object top → SLIDE with x_vel preserved; slide off the edge →
  ledge-drop → GLIDEFALL.
- Everything else is S3K-faithful, including the standing-on-a-slope drift (§3).

---

## 2. Knuckles C4 — what is left

### 2a. Oracle sub-tests still owed (controller-only; emulator work never in subagents)

Verified this session: wall-catch, climb up, ledge detect, clamber → stand, climb-down
→ land (on the pre-dip-fix build), **jump-off** (state `$08` JUMP, x_vel away from the
wall, y_vel up — requires release-then-press), glide→terrain→SLIDE, slide moves + dust
trails, glide→**object**→SLIDE, slide off object edge → GLIDEFALL.

**Not yet verified:**
- Climb-down descent + base landing **on the current build** (the dip fix changed the
  descent's recess handling after the earlier verification).
- The three detach conditions: latch-X drift (write `x_pos` ≠ `knux_latch_x`),
  `ST_ON_OBJECT` (set the status bit while climbing), wall-loss on descent.

**Recipe** (the reliable one — natural input; direct state injection produces artifacts
because the enter hooks never run):
1. Debug ROM boots INTO debug-fly. `press ["a"] frames:4` twice cycles to Knuckles
   (`Character_ID` at `$FFDE3E` should read 2), then `press ["b"] frames:4` drops into
   physics. **Always confirm `debug_flag` (SST+`$3C` = `$FF8BE0`) reads 0 before any
   physics test** — debug-fly suspends state dispatch and an injected state silently
   does nothing.
2. Place standing on the base slab left of the user's test wall: `x_pos` `$FF8BA6` =
   410<<16, `y_pos` `$FF8BAA` = 573<<16 (feet on the y=592 slab).
3. Jump, release, press again mid-air to glide right into the wall face at **x=464**
   (its top is y=544, base slab y=592). Catch latches at x≈454.
4. Then hold DOWN for the descent, or poke the detach condition under test.

Key RAM (player SST base `$FF8BA4`): `x_pos` +$02 · `y_pos` +$06 · `x_vel` +$0A ·
`y_vel` +$0C · `width/height_pixels` +$16/+$17 · `status` +$1E · `ground_speed` +$30 ·
**`player_state` +$32** · `debug_flag` +$3C · `glide_angle` +$44 · `knux_step` +$45 ·
`knux_timer` +$46 · `knux_latch_x` +$48.
PSTATE: GROUND 0 · AIR 6 · JUMP 8 · **GLIDE $10 · GLIDEFALL $12 · SLIDE $14 · CLIMB $16
· LEDGE $18**.

### 2b. Task 12 — docs + merge ritual

An agent was mid-flight on this at session end: ENGINE_ARCHITECTURE player-system
rewrite (incl. fixing the stale "PlayerV 18 of 34 bytes" figure), DEFERRED_WORK
closures + new riders, design-week queue log, and the **byte-changing parcel ritual**
(re-pin `BLOB_LEN_*` + `Z80_SOUND_SIZE` mirrors + `seam1_native_link.rs` pin → rebuild
BOTH sigil binaries → rebuild aeon with the tripwire ARMED → `repin` → `refreeze
--freeze <parcel> --ab <evidence>` → strict suite → `refreeze --check` + `repin --check`).
**Check that agent's final report before redoing any of it.**

**STATUS AT SESSION END: the ritual is COMPLETE and the lane is merge-ready.**

- aeon `feat/knuckles-c4` → **`6251de8d`** · sigil `feat/knuckles-c4` → **`08037f07`**
- plain `s4.bin` crc **`3d2cf804`** (695154) — never moved all lane
- debug `s4.debug.bin` crc **`d8e0c6c2`** (709621) — byte-for-byte the pre-scaffold ROM
- Built with the BLOB_LEN tripwire **ARMED**; no `BLOB_LEN_*`/`Z80_SOUND_SIZE`/seam-1
  re-pin was needed (this parcel touches no sound code — that ritual step is a no-op here)
- `refreeze --check` OK (tip `knuckles-c4`, chain len 107 — entry AMENDED in place, not
  duplicated) · `repin --check` clean · **strict suite 3667 passed / 0 failed** ·
  aeon pytest 941 passed / 2 skipped
- Note: sigil `59ec3162`'s message says "RITUAL INCOMPLETE" — **superseded** by
  `08037f07` right after it. Carry the completed state into any merge summary.

### THE MERGE IS BLOCKED ON ONE THING — a content decision only the user can make

The main aeon tree (on `master`) has the user's **live uncommitted Aurora edits** in the
exact files this branch also changed, so a merge would collide with their working tree.
I did not touch them. Comparison at session end:

| File | Main tree (user's live) vs branch |
|---|---|
| `section_0.tiles.bin`, `chunks.json` | identical — no issue |
| `section_0.collattr.bin` / `.collattrb.bin` | **448 cells differ**, world x896-1280 y256-512: branch has `30FF`, user has `30FB` |

That difference is **mine, not theirs**: while debugging the climb I rewrote those wall
cells from shape **251** (`30FB`, carries angle `$E0`) to shape **255** (`30FF`, flat
full square) so the test wall had a flat top. The user's live tree still holds their
original shape-251 paint. **Ask the user which wins** before merging:

- *Keep their 251* — `git checkout feat/knuckles-c4 -- <the two collattr files>` is WRONG;
  instead let their working copy stand, commit it on master after the merge, and re-run
  `tools/regenerate-level.sh` (the baked tree in the branch assumes 255).
- *Keep the branch's 255* — they discard their working-tree copy of those two files.

Either way the level tree must be re-baked to match whichever paint wins, since
`games/sonic4/data/generated/` in the branch was baked against `30FF`.

**Merge commands once resolved** (pair, aeon first or sigil first but both before any
build elsewhere):
```
git -C /home/volence/sonic_hacks/aeon   merge --no-ff feat/knuckles-c4
git -C /home/volence/sonic_hacks/sigil  merge --no-ff feat/knuckles-c4
```

### Also owed before/at merge

**Replay-net re-stamp** — the RAM layout moved (PlayerV grew the climb scratch), so the
input-replay fixtures may hash-drift. Expected disposition is **layout-induced → re-stamp
against a patched ROM image** per `docs/superpowers/plans/2026-08-13-replay-net-restamp.md`,
NOT a regression — but confirm which it is before dispositioning. (This line used to cite a
"probe-ROM logger" in `docs/superpowers/notes/2026-08-09-replay-net-rerecord-ab.md`; that
runbook is not in that note, and the technique — sketched in
`notes/2026-08-05-sst-fold-ab.md:27-38` — was never committed as code.) The generalised
`PHook_EnsureStanding` was verified to reproduce ball→standing byte-for-byte for
Sonic/Tails, so a behavioural drift there would be surprising and worth stopping for.

### 2c. Removable scaffolds (delete before shipping)

- ~~`4ea60239` DEBUG-only test platform~~ — **REVERTED at the merge ritual
  (`8dc43d9b`). Nothing to delete; read this before building another one.**

  It was 8 × `ObjDef_Solid` at x960-1088, top y=208, 48px above the y=256 surface,
  DEBUG-gated so the release ROM stayed byte-identical — and that part held. The
  strict suite caught the real problem: **a DEBUG-only ENTITY is not expressible.**
  Gating it made `entity_data` 48 bytes longer in the debug shape, and the harness
  enforces `debug_len == plain_len` for **every** ported section
  (`sigil crates/sigil-cli/tests/ojz_run_a_port.rs`) — level DATA must be
  shape-identical, because the port tests compile ONE length for both shapes. The
  invariant won; the scaffold was removed. It had already done its job (the ruled
  glide→SLIDE-on-a-solid-top behaviour was verified on it, and BUG 10 withdrawn).

  **If you need an object-landing fixture, the recipe survives — respect the
  constraint:** put the records in `data/editor/ojz/act1/section_0.objects.json` so
  they land in **BOTH** shapes, run `tools/regenerate-level.sh`, and revert before
  merging. Geometry: 8 blocks 16px apart at x = 968,984,…,1080, y = 216 (top y=208),
  over the x896-1279 flat band whose surface is y=256, with the x768-895 pit as a
  clear approach. Approach recipe: place at x=800, y=195 gliding right at `$1000`
  with C held → contact ~frame 10 at x≈960, `.solid_top` snaps to y=199. **Why the
  shipped sec0 solid can't be used instead:** it is 16×16 with its top only 8px above
  the surface, and a 16px/frame glide crosses it in ONE frame. Full note block is
  preserved in `tools/ojz_entity_gen.py`.
- The user's authored test walls in OJZ section 0 (their content — ask before removing).

### 2d. Open items needing the USER's ruling

1. **Glide/slide/climb SFX** — three `TODO(user)` placeholders; none of S3K's sounds
   exist in our bank. Sourcing audio is theirs.
2. **Ability-agency parcel** (user-endorsed, design banked, not built): Tails flight
   cancel (down+jump proposed), Knuckles re-glide from GLIDEFALL on a fresh press
   (can't gain height and resets speed to `$400`, so it costs momentum for control),
   and a **ball-cancel variant behind a debug flag** to feel-test — the user agreed
   cancels land in vulnerable fall by default, with ball-cancel prototyped for judgement.
3. **Slope mirror-symmetry divergence** (optional): standing on a 22.5° slope drifts
   downhill. This is AUTHENTIC S3K — slope factor `sin>>3` = −13 vs friction +12 = net
   −1/frame — and an `asr` flooring asymmetry means only **4 angles** (`$90 $91 $EF $F0`)
   drift while their mirrors don't. Minimal fix if wanted: take `abs` *before* the shift
   (2×2 code change, S3K divergence, needs a replay re-record).
4. **MPA side/top classification** on fast-horizontal approaches to narrow platforms —
   documented, never hit in practice; would need a ruling only if it bites.

---

## 3. The withdrawn bug + measurement traps (read before debugging collision)

"Bug 10" (glide onto a solid object dead-stops) was **reported by me and withdrawn** —
the behavior was always correct. Three compounding measurement errors produced
convincing false evidence:

1. **`width_pixels`/`height_pixels` are FULL box dimensions, not half-extents.**
   `aabb_axis_test` sums both objects' dims and doubles the delta. Reading them as
   half-extents doubled the platform and moved its top 8px.
2. **Velocities are 8.8 fixed = px/frame**: `x_vel $1000` is **16 px/frame**, not 4. A
   16px-wide object is crossed in ONE frame — no stepping granularity can catch it.
3. **Objects CULL when the camera is far.** `emulator_object_list` showed the platform
   absent entirely while `Camera_X` sat 5000px away; the resulting no-contact runs were
   misread as "intermittent bug" evidence. **Always check `object_list` + `Camera_X`
   before concluding anything about object collision.**

Also: **Oracle watchpoints wedge the emulator** — they survive `breakpoint_clear`,
re-fire on every resume, and stop frame advance; recovery is a full relaunch. Grab
`call_stack` inside the single break. And the **press RPC wedges** under pause-heavy
load (several times this session): recover with `pkill -9 -x oracle_gui` + relaunch,
and re-`load_symbols` after every ROM rebuild (a stale table points breakpoints at the
wrong proc).

**Process lesson worth keeping:** when the user reports a location, ask for the debug
overlay (Cam/P1/Vel) *first*. Three separate wrong-location analyses were resolved in
one step by their `P1 01C6.EC00, 023D.1800` screenshot. And measure the **observable**,
not the intended variable — "slide friction verified" passed while `x_pos` never moved.

---

## 4. Effects P2 — state and what's left

Code-complete, most gates verified. Branch `feat/effects-p2-palette` (aeon) +
`feat/effects-p2` (sigil).

**Shipped:** the palette engine (single owner of `Palette_Buffer`, fixed compose order
base → cycling → cross-fade → operators → variants), palette **variants** (cheap
per-channel shift/bias transforms derived from the live palette), **scanline regions**
(`OP_PAL_REGION`), a movable **water line** (patch slot + arm-word recompute), 16-frame
**cross-fades**, **global operators** (fade black/white, flashes), per-section **colour
cycling**, and the **dense raster tier** (`OP_RUN_GRADIENT`, conservative register-saving
version).

**Verified on oracle:** P1 regression (split at rows 119/120), water cluster with live
line moves at 80/120/160 (rock-stable, no tearing), section palette snap + restore with
character line 0 protected, fade-to-black ramp, cross-fade lerp monotonic, `sec_pal_cycle`
rotation at the authored 8-frame period.

**Two bugs found and fixed during that verification:**
- **sigil mis-encoded `add.w dN, aM` as ADDX garbage** (no ADDA promotion) — now a loud
  build error naming the `adda` spelling, with probes across ISA + both frontends. The
  aeon-side sites were respelled `adda.w`.
- `Palette_RotateSpan` did word math on byte-loaded registers with stale upper bits.

**Still open:**
1. **Row-119 A/B** — both fixes are built behind `EFX_ROW119_FIX` (fire-one-line-early
   vs S3K's cycle-counted blanking delay). Measure both with GATE-EVIDENCE's
   exact-colour-per-row method, pick, and record the loser's numbers.
2. **Dense-gradient gate** — needs an authored ~96-line `OP_RUN_GRADIENT` program;
   verify a monotonic ramp and profile the per-line cost. Mind the pipelined arm at
   BOTH run transitions.
3. **Budget model** — `tools/effects_budget_model.toml` has `NEEDS-MEASUREMENT` rows
   waiting on that profiling.
4. **USER RULING:** may the dense tier reserve a global register? Big cycle win
   (corpus ~26 cyc/line vs our conservative cost) but changes engine-wide register
   conventions. Conservative version shipped pending the call.
5. **S/H is provable after all** — the agent flagged it as undemonstrable because OJZ
   art is high-priority, but the spawn-area art IS low-priority; re-check and close.
6. **Merge ritual**: repin/refreeze per §2b, plus a **frozen-table audit** (this lane
   regenerated placement tables mid-parcel), plus the replay-net re-stamp. The 59 red
   sigil golden targets are by-design byte comparisons against pre-P2 goldens.

**Then Phase 3:** `raster_dsl`/`palette_dsl` constructors, the self-contained shareable
preset format, the forkable starter pack, and the dead-data proof (does sigil prune
unreferenced preset data?). That is also when **water becomes world-anchored** — today's
line is a *screen* row; real water computes `world water Y − camera Y` each frame into
the proven patch slot — and when the garish test fixtures get pruned for real content.

---

## 5. Suggested order

1. Finish Knuckles: the remaining sub-tests (§2a), confirm the docs/ritual agent's work
   (§2b), replay re-stamp, then merge the **aeon+sigil pair**.
2. Effects P2: the two gates (§4.1-4.2), budget numbers, the reserved-register ruling,
   then its own repin/refreeze + frozen-table audit, then merge that pair.
3. Only then Phase 3 / the ability-agency parcel / the user's optional divergences.

Never leave master broken; both shapes green before any merge; `git add` exact paths
only and verify the branch at commit time (parallel worktrees share one tree).
