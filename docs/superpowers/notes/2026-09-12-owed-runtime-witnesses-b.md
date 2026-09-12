# Owed runtime witnesses, batch b: C3b-2 in section 7, C4a-3 and C4a-2 before/after (2026-09-12)

Worktree helper for the aeon controller, branch `witness/owed-runtime-0912b`, cut from origin/master
`f512e228` (HEAD was already its tip; no reset needed). Headless only: every emulator was an
`oracle-aether` spawned and reaped by `tools/aether_instance.py` (handshake `implementation:
"oracle-rs"`). No emulator MCP tool was called. No `.emp` was changed.

| check | verdict | measured | control |
|---|---|---|---|
| C3b-2, section 7 | **NOT OBSERVED** | 0 tear hits in 3000 `VInt_Lag` stops; 95% bound **0.00100** per lag frame | structural facts all held at every stop (below); latch entered 24.4..31.6 lines into its tick, 0/240 ticks with a lag VBlank before it |
| C4a-3 before/after | **prediction HELD, exactly** | keep-all N=128: 18260 -> 15224 (**-3036**); remove-all N=128: 68948 -> 65400 (**-3548**) | all 11 rows (N = 0,1,2,3,64,128) equal `36 - 24N` / `36 - 28N` / 0; N = 0 is the no-change control |
| C4a-2 before/after | **MEASURED, parcel bound HELD** | 30 same-input call pairs; PopulateSectionRings -2070 / -984 where the old gate ran, +8 where it did not; RescanY -1630 .. +32 | 4 calls per ROM discarded (an HBlank inside the window), the same 4 on both ROMs |

## ROMs and trees

All built here with `DEBUG=1 ./build.sh` (each `finished=0`), assembler `SIGIL_BUILD` md5
`2e7c25920b95cec2c462ea51b4f078b5` before the first build, after every build, and after the pytest run.

| role | tree | s4.debug.bin crc32 | size |
|---|---|---|---|
| today (after) | this worktree, `f512e228` | `9ce1c2ff` | 847533 |
| C4a-3 before | `f64f26b3` (detached worktree) | `b726a287` | 847499 |
| C4a-3 before, booking's literal parent | `7a938fbe` = `f64f26b3^1` | `b726a287` (byte-identical, `cmp`) | 847499 |
| C4a-2 before | `104134ca` = `62fb300f^1` | `2b61c537` | 847499 |

Today's ROM is byte-identical to the ROM the earlier witnesses used (`.aeon-ls8-land`, `9ce1c2ff`):
master moved only in docs and tools since `9fe9ee91`.

Builds ran 18:04:20Z .. 18:12:27Z (`date -u`), four in parallel; `uptime` load 18.61 at the start and
12.78 at the end.

### Correction to the booking: `f64f26b3` is not the C4a-3 merge

`git show f64f26b3`: parents `7a938fbe` (first) and `a6d99aa4` (second), subject "merge(ew ensure
message)". Its second parent is **branch 0 of the C4a parcel, the ensure-message fix**, not C4a-3.
The C4a-3 merge is **`21a2887a`**, parents `f64f26b3` and `ccc9a2be` (the C4a-3 commit). The ledger's
own `fixedAt` for C4a-3 already says `21a2887a`.

So the right "before" tree for C4a-3 is `21a2887a^1` = `f64f26b3`. The booking's literal `f64f26b3^1`
= `7a938fbe` also predates C4a-3, and `git diff 7a938fbe f64f26b3 -- engine/` is one ensure message.
Both were built. Their ROMs are **byte-identical** (`b726a287`), and the listings differ only in
`entity_window.emp`'s DIGEST-READ row and the aggregate. The number does not depend on which parent
the booking meant, but the citation "parent of merge f64f26b3" names the wrong merge.

## How the old ROMs were measured honestly

The tools prove every source file they read against the listing's `DIGEST-READ` crc and size, and
refuse on any mismatch. For an old ROM the source reads were pointed at **that ROM's own tree**
(`--src-root` / `--before-src-root`), and each proof ran against that tree's listing. Every run prints
its "sources checked" block. For example, the C4a-3 before run read `engine/objects/entity_window.emp`
crc `16574a0a` and `engine/system/constants.emp` crc `ac1b3bb8` = its listing's DIGEST-READ. Today's
tree reads `c1dd6aac` / `6d486bd3`, so today's tree against the old ROM would, correctly, have
refused. `section_0.rings.json` has no digest row (sigil reads the baked `.bin`); it was compared
byte for byte with the ROM tree's copy. Each run also checks that the listing's `DIGEST-ROM` names the
ROM, and that the crc is the one passed with `--expect-crc`. Nothing was weakened.

Recorded runs came from **immutable detached worktrees at the tool commits** (`184bbbd5` for the
raster tool, `f1fdd51f` for the object tool), so nothing could change under a running tool.

## Instrument facts measured this session (the Rust core, `oracle-aether`)

- An armed execution breakpoint **halts `run_frames`**: `frames` returns 0, with pc at the
  breakpoint. A breakpoint at the pc the machine is already on is skipped on resume.
- `run_to {maxFrames: 1}` from mid-frame stops at the **next frame boundary** (frame 400 -> 401 in
  817502 mclk), not a full frame later.
- A single step that takes an interrupt **reports the autovector target as its pc**. From
  `VSync_Wait`'s spin the step sequence went `$2530, $2534, $FFB6A0` (the HBlank RAM trampoline),
  then `$87F2`. The C4a-2 tool re-runs this calibration at the start of every run, and refuses if
  the first pc out of the spin is not a vector target. It was `$FFB6A0` after 7407 steps (today)
  and 7405 steps (before). The vector targets are `$002334` (level 6), `$FFB6A0` (4), `$0C0676`
  (1-3, 5, 7).
- The warp mailbox **keeps debug fly on** (`debug_flag` 255 after the warp), and installs the
  destination section's preset through the crossing path.

---

## C3b-2 in section 7

**Why section 7.** Section 0 cannot show the residue: channel 0 is anchor-NONE and always
suppressed, and it binds no motion, so the `.plain` loop runs. The tool derives section 7 entirely
from source:
- `act_descriptor.emp`: GRID_W 3, section 7 is grid (1,2), world x 2048..4095, y 4096..6143, and it
  binds `OJZ_Preset_Sec7`.
- `ojz_effects.emp`: `patched: OJZ_WorldWater`, `patch_world_ys` anchored on channels **[2, 3]**,
  and `anchor_sweep(amp_shift: 5)` on channel **2**. SINE_AMPLITUDE 256 >> 5 = +/-8 px.
- The expected patch table is `OJZ_WorldWater` + RASTER_BUF_SIZE = `$015762`.

**The tear window, re-derived.** `RASTER_MAX_PATCH` = 4 (`raster_dsl.emp`), and the latch counts d0
down from 3, so channel c runs with d0 = 3 - c: channel 2 with **d0 = 1**, channel 3 with
**d0 = 0**. The loop bounds were decoded with capstone from the ROM:
- `.mch`: head `$008AD4`, store `move.w d2,$6(a0)` at `$008B20`, dbra `$008B24`.
- `.plain`: head `$008B2E`, store `$008B32`, dbra `$008B34`.

A tear is a `VInt_Lag` whose stacked PC (SP+66) is either:
- the loop's dbra with the saved d0 (SP+4) = 1, so channel 2's store has retired; or
- head..store with d0 = 0, so channel 3's store has not.

**The band where both records show.** The ROM's band table (fire-line space) gives channel 2 (2, 159)
and channel 3 (161, 222). The runtime anchor bank gives `Effects_World_Y` [NONE, NONE, 4320, 4410].
Each record is live and unclamped at every sweep phase for:
- channel 2: Camera_Y 4168..4309;
- channel 3: Camera_Y 4187..4248;
- both: **4187..4248**.

The flight was warped to (3072, 4352) through the warp mailbox. It then bounced diagonally, steered
every frame, with Camera_Y in 4195..4240 and Camera_X in 1952..3840 (the camera centre stays inside
section 7).

**Command** (run from `.aeon-owedwit-run-184bbbd5`, the tool at `184bbbd5`):
```
python3 -X pycache_prefix=<fresh dir> tools/lens_residue_raster_witness.py c3b2s7 --lag-budget 3000 \
    --rom <this worktree>/s4.debug.bin --lst <this worktree>/s4.debug.lst --expect-crc 9ce1c2ff
```
Run 1: 18:26:20Z .. 18:27:54Z (93.6 s wall), load 5.92 -> 14.63. Run 2: 18:27:54Z .. 18:29:14Z
(78.9 s), load 14.63 -> 7.41. Both `finished=0`. The two outputs are **identical** apart from the
clock lines (`diff`).

**Measured, every stop:**
- 3000 `VInt_Lag` stops over 23301 frames. `Lag_Frame_Count` was in step at every stop (0 out of
  step), and rose by 2999 by the last stop, whose own increment lands after it.
- `Raster_Patch_Tab` = `$015762` at **3000 / 3000** stops, with 0 stops or timing samples outside
  `OJZ_WorldWater`'s install.
- `Effects_Motion_Any` = `$5000` at every stop, so the **.mch loop runs**.
- Channel 2 / channel 3 record state: **live / live at 3000 / 3000**. Camera_Y at the stops was
  4192..4240.
- Stops inside `Effects_LatchWorldLines` at all: **0**.
- Where the lag VBlanks landed (nearest preceding non-phased symbol): PageCache_PatchRun_Seq 427,
  Canopy_Probe 344, Render_Sprites 343, PageCache_Audit 331, Parallax_Fill_PerLine 266,
  Tile_Cache_Fill 249, TileCache_FillRow 171, DrawRings 171.
- **Latch timing in section 7** (240 ticks of the same flight): entered **24.4 .. 31.6 scanlines
  (median 31.4)** after the VBlank that started its tick. **0 of 240** ticks had a lag VBlank between
  the tick start and the latch. Section 0 had measured 25.6 .. 56.2.

**Tear hits: 0.** Verdict **NOT OBSERVED**. The 95% upper bound on the per-lag-frame tear probability
is **0.00100** (1 - 0.05^(1/3000); rule of three 3/n = 0.00100). This is a **bound, not a clean
result**.

**What held in section 7, and what that says.** All three structural preconditions that section 0
lacked held at every stop: two live, unclamped, moving records on adjacent channels, and the `.mch`
loop. So section 7 is a scene where a tear, if caught, would show. What still keeps the count at
zero is timing, and it is the same fact in both sections. The latch runs in the first ~32 lines of
its tick, and the lag VBlanks land in the streaming work later in the tick. A lag VBlank can
interrupt the latch only if the pre-latch part of a tick overruns a whole frame, about 230 more lines
than it takes here. That never happened in 240 sampled ticks. This bounds the rate in the one scene
that could show the residue; it does not show the window closed.

---

## C4a-3: EntityWindow_DespawnRings before/after

**The prediction, stated before measuring, and what would refute it.** It is the parcel note's
(`2026-09-12-entity-window-c4a-parcel.md`, branch 1): "-24 per kept in-window ring, -26 per ring
kept only by its active section, -28..-30 per removed ring; net per frame ~ 36 - 24N for N buffered
rings". The +36 is the once-per-call setup, which only a non-empty buffer pays. Graded here as
**after - before**:
- keep-all (all N in window): **36 - 24N**, so +12 at N=1, -12 at N=2, -36 at N=3, -1500 at 64,
  -3036 at 128.
- remove-all (X right of the window, section untracked, the -28 path): **36 - 28N**, so +8, -20,
  -48, -1756, -3548.
- empty buffer: **0** (both forms skip the setup).

**Refutation:** both ROMs are deterministic, and every window is graded interrupt-free and equal to
its run_to re-run, so there is no noise for "about" to absorb. The prediction is refuted by **any row
whose measured delta differs from the formula by even one cycle**. The loose reading, "about -3.0 K
at 128", would be refuted by a wrong sign or a miss of more than 10%.

**The before form, decoded from `b726a287`** (capstone): the index loop.
- Its loop head rebuilds the entry address: `move.w d5,d0 / add.w d0,d0 / add.w d5,d0 /
  add.w d0,d0 / lea $af30.w,a0 / move.w (a0,d0.w),d1`.
- Hand model, MC68000 tables:
  - prologue **64**: the rolling prologue without move.w 4 + x6 16 + lea 8 + adda 8;
  - keep iteration **142**: address build 38, then the rolling keep path with
    `move.w 2(a0,d0.w)` 14 in place of `2(a2)` 12, and no subq;
  - remove iteration **538**: address build 38 + X tests 24, section compares 96, remove setup 50
    (two `(a0,d0.w)` reads at 14), then the unchanged callee costs, and dbf 10;
  - empty buffer 42, tail +4 +16.
- `EntryForSection` and `RingBuffer_Remove` are byte-identical in the two ROMs (disassembled).

**Command** (run from `.aeon-owedwit-run-f1fdd51f`):
```
python3 -X pycache_prefix=<fresh dir> tools/lens_residue_object_witness.py c4a3ab \
    --rom <this worktree>/s4.debug.bin --src-root <run worktree> --expect-crc 9ce1c2ff \
    --before-rom .aeon-owedwit-f64f26b3/s4.debug.bin --before-src-root .aeon-owedwit-f64f26b3 \
    --before-expect-crc b726a287 --c4a3-n 0,1,2,3,64,128
```
Run 1: 18:35:09Z .. 18:35:15Z. Run 2: 18:35:29Z .. 18:35:33Z. Load 2.68 .. 3.12. Both
`finished=0`; outputs **identical** apart from clock, pid and wall-time lines.

Seed: the same as the full-buffer witness. Stop at the proc's entry at boot + 400 and write
Ring_Count = N and N six-byte entries. Keep-all puts them at (Camera_X+160, Camera_Y+112); remove-all
puts them at Camera_X+832 with an untracked section. Every instruction is single-stepped to the one
after the rts, and the same window is re-run from the entry checkpoint with one run_to.

| N | variant | before cycles | after cycles | delta | predicted | held |
|---|---|---|---|---|---|---|
| 0 | keep | 42 | 42 | +0 | +0 | yes |
| 1 | keep | 226 | 238 | +12 | +12 | yes |
| 1 | remove | 622 | 630 | +8 | +8 | yes |
| 2 | keep | 368 | 356 | -12 | -12 | yes |
| 2 | remove | 1160 | 1140 | -20 | -20 | yes |
| 3 | keep | 510 | 474 | -36 | -36 | yes |
| 3 | remove | 1698 | 1650 | -48 | -48 | yes |
| 64 | keep | 9172 | 7672 | -1500 | -1500 | yes |
| 64 | remove | 34516 | 32760 | -1756 | -1756 | yes |
| 128 | keep | **18260** (127820 mclk) | **15224** (106568 mclk) | **-3036** | -3036 | yes |
| 128 | remove | **68948** (482636 mclk) | **65400** (457800 mclk) | **-3548** | -3548 | yes |

Every window: 0 interrupts, stepped mclk = run_to mclk, divisible by 7. Every row equals its form's
hand model. The trace matched the seed's path in every row: loop passes = N, EntryForSection and
RingBuffer_Remove 0 (keep) or N (remove), EntityLoaded_Clear 0, Ring_Count after N or 0. Today's
N = 128 figures reproduce the earlier witness exactly (15224 / 65400).

**Verdict: the prediction HELD at every measured N**, including the break-even: N=1 costs +12 and
N=2 saves 12. The saving at a full 128-entry buffer is **3036 cycles keep-all and 3548 remove-all**,
about 2.4% / 2.8% of an NTSC frame (896040 mclk / 7 = 128,006 cycles). That is what the parcel's "about -3.0 K" meant;
remove-all is not a case the "36 - 24N" formula spells, and its -28 slope is the note's own
per-removed-ring figure.

---

## C4a-2: PopulateSectionRings / RescanY before/after

**Method.** This is the c4a3 single-step method applied to calls made by a scripted route.
- Execution breakpoints at the two procs' entries halt the route at each call.
- The call is single-stepped from its first instruction to its stacked return address, and the mclk
  delta / 7 is its cycle count.
- The same window is re-run from a checkpoint at the entry with one run_to. It must give the same
  delta, and it did for all 34 calls on both ROMs.
- A step landing on an autovector target means an interrupt was taken inside the window. That window
  is **discarded, never billed to the proc**.
- The route itself is unchanged; the pad state is re-applied after each checkpoint restore.

**Route.** The c4a2 witness route, SUBJECT (ring 0 collected) and CONTROL (not):
1. Collect, then back to fly.
2. RIGHT until section 0 is evicted into the park (Camera_X 4616).
3. LEFT home.

A **vertical leg** was added, because the route alone crosses one coarse row. It starts from the
act's left clamp, goes DOWN until section 0's rings have left the despawn band by a coarse row
(derived y >= 669 = 157 + ENTITY_DESPAWN_BUFFER_Y 384 + 128), then UP home. This is the parcel TAG's
"coarse-row crossing": on the way up RescanY re-offers those rings, so the collected gate is reached.
- Why the left clamp: the route's LEFT leg is polled every 4 frames, and its overshoot depends on how
  many ticks each ROM fits in a poll. It measured Camera_X 8 on today's ROM against 24 on the before
  ROM, and a different camera makes a different call.
- Section-0 indices were checked at the end of every leg: [1..6] subject, [0..6] control, empty at
  the far point.

**Command:**
```
python3 -X pycache_prefix=<fresh dir> tools/lens_residue_object_witness.py c4a2ab \
    --rom <this worktree>/s4.debug.bin --src-root <run worktree> --expect-crc 9ce1c2ff \
    --before-rom .aeon-owedwit-104134ca/s4.debug.bin --before-src-root .aeon-owedwit-104134ca \
    --before-expect-crc 2b61c537
```
Run 1: 18:35:15Z .. 18:35:29Z. Run 2: 18:35:33Z .. 18:35:47Z. Load 2.68 .. 3.12. Both
`finished=0`; outputs **identical** apart from clock, pid and wall-time lines.

**Pairing.** Calls are paired by (tag, leg, proc, ordinal) and compared only when their inputs are
identical: camera, Ring_Count on entry and exit, and the section (PopulateSectionRings) or tracked ids
(RescanY). All 34 calls pair on the frame too (e.g. 571/571, 709/709, 1113/1113).

**The parcel's derived bound, checked per pair.**
- The lazy cache costs a walk at most +8 (`suba.l a4,a4`), so after - before <= 8 x walker calls.
- A walk in which the old ROM reached the collected/killed gate (`Collected_CheckRing` /
  `Killed_CheckObject` entered) must come out cheaper.

| tag | leg | call | before | after | delta | old gate reaches | bound |
|---|---|---|---|---|---|---|---|
| SUBJECT | route | Populate sec 2 (frame 571, cam 2568,16), 12 -> 20 rings | 16632 | 14562 | **-2070** | 8 | held |
| SUBJECT | route | Populate sec 5, 20 -> 20 | 1432 | 1440 | +8 | 0 | held |
| SUBJECT | route | Populate sec 4 (frame 709) | 2832 | 2840 | +8 | 0 | held |
| SUBJECT | route | Populate sec 3 (frame 841) | 144 | 152 | +8 | 0 | held |
| SUBJECT | route | RescanY (frame 403, cam 64,112) | 6888 | 6842 | -46 | 1 | held |
| SUBJECT | vertical | RescanY x9 comparable (rows 256 .. 126) | 10506 .. 21480 | 10476 .. 19850 | -1630 .. +32 | 0 .. 11 | held |
| CONTROL | route | Populate sec 2 (frame 571, cam 2568,56), 13 -> 21 | 16936 | 14866 | **-2070** | 8 | held |
| CONTROL | route | Populate sec 1 (frame 710, cam 4600,56), 8 -> 14 | 11274 | 10290 | **-984** | 6 | held |
| CONTROL | route | Populate sec 5 / sec 4 / sec 3 | 1432 / 2832 / 144 | 1440 / 2840 / 152 | +8 each | 0 | held |
| CONTROL | route | RescanY (frame 403) | 6632 | 6648 | +16 | 0 | held |
| CONTROL | vertical | RescanY x10 | 6274 .. 22510 | 6306 .. 20880 | -1630 .. +32 | 0 .. 11 | held |

The vertical RescanY pairs, in order. Subject rows: first one discarded, then
-30, -26, +32, +32, +32, +32, -298, -1630, -30. Control rows: -470, +32, -26, +32, +32, +32, +32,
-298, -1630, +32.
- The -1630 call is the one that brings section 0's rings back into band.
  - Subject: 2 -> 12 rings, ring 0 kept out by its collected bit.
  - Control: 2 -> 13.
  - 11 old gate reaches.
- The -470 control call reached the old killed gate 4 times (`Killed_CheckObject` 4).
- The zero-gate RescanY calls cost +32: 4 walks x 8. That is within the bound of 8 walker calls x 8.

**Discarded, on BOTH ROMs, the same 4 calls:**
- SUBJECT route Populate sec 1 (frame 709, 2 HBlanks);
- SUBJECT route Populate sec 0 (frame 841, 1 HBlank): the collected-half repopulate;
- CONTROL route Populate sec 0 (frame 843, 1 HBlank);
- SUBJECT vertical RescanY #1 (frame 1040, 2 HBlanks).

All four are level-4 (raster HInt) interrupts, deterministic in time. So no retry can clean them
without changing the scene, and the scene was not changed. **The populate of section 0 on the way
home, the one call that meets the collected ring directly, therefore has no clean before/after
figure.** The collected bit's effect on a gated walk IS measured, in the vertical leg's -1630 call,
where ring 0 is gated out on the subject side.

**Verdict: MEASURED; the parcel's derived bound held on all 30 same-input pairs.** Every walk in which
the old ROM reached the gate came out cheaper after, from -26 (one gate reach) to -2070 (eight). Every
walk that never reached it paid +8 per walker that passed its early exits.

---

## Tool changes (on this branch)

- `tools/lens_residue_raster_witness.py` (`184bbbd5`): `c3b2s7`.
  - `classify()` takes the low channel of the pair (default 0, so the section-0 path is unchanged).
  - `band_table` / `record_state` moved to module level, with the same logic.
- `tools/lens_residue_object_witness.py` (`f1fdd51f`):
  - `--src-root` with DIGEST-READ proof of every `.emp` read; `--expect-crc` replaces the
    hard-coded ROM gate (the default is unchanged).
  - `c4a3` sweeps `--c4a3-n` against a per-form model decoded from the ROM.
  - `c4a2t` (timed route + vertical leg + calibration).
  - `c4a3ab` / `c4a2ab` (before/after with the prediction and the bound).
- Neither tool is wired into build.sh or a pytest lane.

**`python3 -m pytest tools -q` on this branch:**
- With the build environment exported (`SIGIL_BUILD`, `SIGIL_EMIT`, `AEON_SKDISASM_DIR`):
  **2559 passed, 10 skipped, 0 failed, 0 errors** (18:35:14Z .. 18:36:26Z, load 2.68 .. 4.96).
- The first attempt, in a shell without `SIGIL_BUILD`, gave 4 failed / 55 errors. Every one was the
  provenance fixtures refusing to run without an assembler ("SIGIL_BUILD is unset ... measured
  NOTHING"), in `test_artifact_provenance`, `test_provenance_consumers`,
  `test_extern_guard_reachability`, `test_bg_emit` and `test_needs_build_lane`. None of them names
  either tool. It is recorded so the environment is not forgotten again.
- `test_no_baked_home_paths.py` and `test_routine_extent_phased.py` pass. Both tools take the ROM,
  listing and trees as arguments. Every routine extent comes from `scene_spans.lst_proc_sizes`:
  `Effects_LatchWorldLines`, `EntityWindow_DespawnRings`, `VSync_Wait`.

## Bookings

- `docs/DEFERRED_WORK.md`, the C4a runtime-TAG status line: updated in place (C4a-3 and C4a-2
  before/after measured, with the `f64f26b3` correction).
- **C3b-2 has no DEFERRED_WORK row.** The 2026-09-12 booking commit `3ee5cc3e` says so ("no
  DEFERRED_WORK row exists for them: C2a-6, C3b-2, B2a-2"). Its result is booked in
  `docs/lens-findings.jsonl` only, and no row was invented.
- `docs/lens-findings.jsonl`: one new latest-line row each for C3b-2, C4a-3 and C4a-2.

## Hygiene

- Every emulator was spawned and reaped by `aether_instance` inside the tools. Each run printed
  "reaped: gone" for its own pid. The probe did the same (pid 2144625, gone).
- At the end, `pgrep -f oracle-aether` showed only MCP-shim instances on `aeon/s4.debug.bin`
  (`/tmp/oracle-mcp-*` sockets). None was mine, and none was touched.
- Worktrees created: `.aeon-owedwit-7a938fbe`, `.aeon-owedwit-f64f26b3`, `.aeon-owedwit-104134ca`
  (the before builds), and `.aeon-owedwit-run-184bbbd5`, `.aeon-owedwit-run-f1fdd51f` (the immutable
  tool runners). They are removed after this note is committed, once no process of mine has a cwd or
  argument in them.
