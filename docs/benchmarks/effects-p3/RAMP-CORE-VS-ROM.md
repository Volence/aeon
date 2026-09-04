# The ramp landing moved because the EMULATOR changed, not because the engine did

**Measured 2026-09-03 · branch `measure/ramp-tier-legacy-core` · instrument
`tools/ramp_legacy_core_probe.py`**

**THIS OVERTURNS THE CONCLUSION PUBLISHED THE SAME DAY ON `33e50207`.** That parcel — the one
this measurement was dispatched by — concluded from a `top+1` / `top+2` difference between the
2026-08-14 captures and today's ROM that *the engine's dense VSRAM write landing moved,
fire+1 -> fire+2*, and bracketed it to a `perf(raster)` batch on 2026-08-19. It also, honestly,
recorded that the cycle story predicted the **wrong direction** and that the instrument remained
a live candidate, because the 2026-08-14 captures came off the legacy Exodus-derived C++ core
and the Rust core only became the ratified default on 2026-08-26.

The instrument is the cause. **The engine did not move.**

## The measurement

One ROM. One probe. Both cores.

    ROM     s4.debug.bin, 740204 bytes, md5 21c57d329caad5c20fe8b15455ae5374
            built at 33e50207 (the merge that published the conclusion under test),
            DEBUG=1 ./build.sh, in this worktree
    legacy  oracle-old, `pre-single-threaded-refactor-137-g1eb09a9`
            binary linux-port/build/oracle_gui, 88526584 bytes, mtime 2026-08-20 01:02:04
            serverName "oracle", serverVersion "2.1-linux", implementation "oracle-cpp"
    rust    oracle-next `40efbf8`
            binary target/release/oracle-aether, 2188440 bytes, mtime 2026-09-02 06:30:25
            serverName "oracle-next"

| capture API | core | **DENSE** landing (tops 40, 112, 190) | **SPARSE** landing (splits 112/140) |
|---|---|---|---|
| `screenshot` | **legacy** | **`top + 1`** — 41, 113, 191 · 0 gaps | **`split + 0`** — band 112..140, 29 rows |
| `screenshot` | **rust** | **`top + 2`** — 42, 114, 192 · 0 gaps | **`split + 1`** — band 113..140, 28 rows |
| `scanlines`  | **rust** | **`top + 2`** — 42, 114, 192 · 0 gaps | **`split + 1`** — band 113..140, 28 rows |

Today's ROM reads **`top + 1` on the legacy core** — exactly what the 2026-08-14 captures read.
It reads `top + 2` only on the Rust core. **The difference is in the CORE.**

## Three things this rules out, each with what would have falsified it

**The capture API is not the cause.** Row 3 exists for that alone. The legacy core has *no*
`emulator/scanlines` — its `Handlers()` table has no such entry — so its only reading is
`emulator/screenshot`, and a probe that used screenshot on one core and scanlines on the other
would leave "the two APIs number rows differently" as a live and *completely different* finding
("the ratified reading is off by one against its own core's framebuffer"). The Rust core
advertises `emulator/screenshot` too. Driven through it, **the Rust core still reads `top + 2`**,
identical to its scanlines reading, on both tiers. Had it read `top + 1` there, the verdict would
have been the API, not the core.

**"A uniform instrument shift is EXCLUDED" is refuted — by the measurement it was missing.**
`DEFERRED_WORK.md` excluded a uniform shift on the grounds that `vsplit_landing_gate` pins the
SPARSE tier green *on the Rust core*. That argument compares sparse-on-Rust against
dense-on-Rust; it never measured sparse on the legacy core, and so could not see a shift that
moves both tiers together. **Both tiers move by exactly one line between the cores** — dense
`+1 -> +2`, sparse `+0 -> +1`. The shift is uniform, and a uniform shift is what an instrument
does. Had the sparse tier read `+1` on *both* cores while the dense tier moved, the exclusion
would have held and the engine hypothesis would have survived.

**A cancelling conspiracy is not needed and has no room to hide.** In principle both could have
moved and cancelled (engine `+1`, core `-1`). But `ramp_boundary_probe.py` §6 already pinned the
dense *schedule* unchanged with **no renderer in the loop** — `N + top` is exactly 224 at all
seven tops in both eras — so the engine's fire line did not move; and the two-tier uniform shift
above accounts for the whole one-line difference. The engine explanation has nothing left to do.
This is also why the parcel's own wrong-direction cycle caution never needed resolving: the
arithmetic said the engine could not have produced this, and it was right.

## What makes the numbers admissible

**Controls first, and there are three.** Two arms per path, two separate boots each, before any
treatment:

* **untreated** control-vs-control — **224/224 rows identical** on both cores, VDP `state_hash`
  identical.
* **treated** control-vs-control — two arms with the *same* record — **224/224 identical** on
  both cores. The untreated control alone exercises neither the RAM poke nor the dense run, so
  it says nothing about a capture taken while `.dense_body` re-arms reg `$0A` on every scanline.
* **install visibility** — treated vs untreated differ on 189 rows (legacy) / 187 (rust). A
  control pair that is stable *because nothing is happening* would pass the first two and mean
  nothing.

**The scene is frozen in every arm on both cores** (`Debug_Scene_Freeze = 1`, `Camera_Y = 144`),
and that is a measured necessity, not hygiene — see below. Holding it on one side only would put
a second difference beside the core.

**Every arm is frame-locked.** `frame_token` (legacy) / `frame` (rust) must advance exactly as
many steps as the arm ran frames, or the arm is retried. All reported arms locked; `legacy_trtB`
needed two attempts once.

**No rewind occurred.** Each arm is a fresh instance and takes exactly one `emulator/reset`
before any frame is counted; after that anchor nothing calls reset, restore, a checkpoint or
`run_to`. Every trail printed is monotonically increasing, on both cores, in every arm. **No
`wait_for_break` anywhere** — every stop is a scheduled `run_frames`, so oracle's
`WAITFORBREAK-INSTANT-TIMEOUT` defect cannot reach this measurement.

**Machine load, the covariate.** `uptime` load average ran 4.5 to 16.9 across the session (peers
compiling). The legacy dropped-render defect showed up under it; the frame lock caught every
instance.

## Two instrument defects measured here, both of which produce CONFIDENT WRONG ANSWERS

Neither errors. Both hand back a clean picture.

**1. The legacy render thread falls behind the machine, and on a scrolling scene that is dozens
of rows.** oracle-old's own `ab_runner.py` demotes its screenshot to advisory for this reason and
estimates ~0.4% of pixels. Measured here it is far worse. Unfrozen, two identical boots:
`state_hash` **combined identical** (`0x3B24E54DAB1346B1` both) while `state_hash` **framebuffer
differed**, and **79-83 of 224 screenshot rows differed** — with the differing band *moving
between runs* (141..223 one pair, 0..78 another). The machine is perfectly deterministic; only
its render is not. Frozen, three identical boots gave three byte-identical screenshots.

Freezing removes the scroll, which removes the difference between adjacent frames, which is what
makes a one-frame-late capture harmless. The residual drops are caught by the frame lock. Before
the lock existed this defect produced a `top` 40 run appearing to differ **from row 5** and a
28-row authored band coming back **146 rows wide and non-contiguous** — both plausible-looking
numbers that would have been read as engine behaviour.

**2. `SP_DRIVE = 2` gives a SILENT NULL on the legacy core.** `vsplit_landing_gate`'s two
post-install frames are enough on the Rust core (identical answer at 2 and at 8). On the legacy
core two frames produce **zero differing rows** — the program readback passes, the frame lock
passes, nothing errors, and the probe reports "the fixtures did not differ." That reads exactly
like *"this core cannot render a mid-frame VSRAM split"*, which is false: at 8 frames the same
fixtures band normally. A clean, confident, wrong **negative about the very tier the published
finding says did not move.** `SP_DRIVE` is 8 here, matching `DENSE_AFTER`.

## What is NOT established

**The fourth cell of the 2x2 is unmeasured: the 2026-08-14 ROM on the Rust core.** It would
predict `top + 2`. Nothing here requires it — the same-ROM/two-core comparison is already a
controlled experiment and the era-matched cell (today's ROM, legacy core) reproduces the
2026-08-14 reading exactly — but anyone wanting the full square should build `c2a7e1a9` and run
`--core rust` against it.

**Neither core is asserted correct.** This says the two disagree by one line and that the
disagreement, not the engine, explains the archive. Which one matches silicon is a separate
question, and this project has no real hardware; `vsplit_landing_gate`'s own carried caveat
already records that emulators disagree about mid-frame VSRAM (GensKMod latches at HBlank start,
Exodus/BizHawk consult continuously).

**The legacy sparse band is 29 rows, not the authored 28.** Its edges are at `+0` (upper) and
`+1` (lower), so no single landing offset describes the legacy sparse result, and it is reported
as a band rather than smoothed into a number. This is a property of the legacy core worth its own
look; it does not affect the verdict, which rests on both tiers shifting one line in the same
direction between the cores.

## What needs to change, and what this does not touch

`engine/effects/raster.emp`'s comment block, `docs/DEFERRED_WORK.md`'s RAMP BOUNDARY entry,
`docs/benchmarks/effects-p3/RAMP-EVIDENCE.md` and the amended suite contract in
`empyrean`'s `aurora-effects-preset.schema.json` all currently attribute the shift to the engine
and to the 2026-08-19 `perf(raster)` batch. **That attribution is wrong and the 2026-08-19
bracket is a coincidence.** Correcting them is the owner's call, not this branch's — nothing here
is landed.

**The `top + 2` NUMBER is not disputed** for anyone measuring on the Rust core today: that is
what the ratified instrument reports, on both its APIs, at every top. What is disputed is the
CAUSE, and therefore every downstream sentence that says the engine changed on 2026-08-19.

## Reproducing

    export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
    export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
    DEBUG=1 ./build.sh

    python3 tools/ramp_legacy_core_probe.py --core legacy --tops 40,112,190
    python3 tools/ramp_legacy_core_probe.py --core rust   --tops 40,112,190
    python3 tools/ramp_legacy_core_probe.py --core rust --capture screenshot --tops 40,112,190

Exit 0 = measured; **exit 2 = could not measure**, which the probe returns rather than a verdict
whenever a control fails, an arm cannot be frame-locked, or a band comes back empty.
