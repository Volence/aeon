# Raster substrate lens sweep — adjudication packet

**Review SHA:** `48ca8b5d` (working tree == HEAD for all subject files)
**Panel:** ratified assembly roster, 15 seats — A · A2 · B1 · B2×2 · C1×2 · C2×2 · C3×2 · C4×2 · C5 · V
**Raw findings:** 117 (31 major, 51 minor, 35 note)
**Charter:** sweep the substrate scanline-services P1 will freeze as its identity baseline.
parallax walker/fill internals excluded (P3 rewrites them). bg_anim included.
**Runs:** `wf_4e6a088e-398` (C4-w1 only; session limit killed 14) + `wf_75467791-d1f` (14/14).
Raw seat JSON: `2026-08-18-raster-substrate-sweep-packet.jsonl` beside this file (16 seats,
`{seat, findings[], coverage_notes}` per line).

> **Provenance note (added on import to the repo 2026-08-18):** this packet was produced in a
> session that wrote it only to `/tmp`, so it was invisible to the parallel scanline-P1 session,
> whose plan recorded the sweep as "never launched" (no branch, no worktree, the string appearing
> nowhere in the repo). Imported verbatim apart from this note and the filename above. The lesson
> is the mundane one: a review packet that lives in a scratchpad does not exist as far as any other
> session is concerned.

Overseer own-verified every ruling below against the code. One major was REFUTED.

---

## TIER 1 — CONFIRMED substrate defects. Fix before the freeze.

### 1. EFX_BLANK_DELAY is calibrated only for SetReg-prefixed fires — a single-op CRAM fire writes into visible display
`engine/effects/raster.emp:232` · C3-timing-w2 · **the sweep's top finding**

The project's own R1 calibration note, in-code at `raster.emp:797-804`, records:
"the bare single-op cram ON fire spilled identically at x~170, confirming sweep 4's anchor
finding: the clean mixed-shape evidence never covered single-op fires; ... the clean mixed
shape carries ~152 cyc of pre-burst delay: SetReg 94 + spin 58."

EFX_BLANK_DELAY=4 was fitted to the 152-cycle two-op shape. A single-op CRAM/region fire
carries 58 cycles of pre-burst delay and lands at x~170 of 320 — mid-active-display. The DSL
freely admits that shape: `band(..., sh: 0)` returns a single-op ON fire
(`raster_dsl.emp:628`), as do `region_boundary(sh: 0)` and `fx_tint_band`. Within one band the
OFF edge is clean (EFX_RESTORE_DELAY=13 was calibrated for the single-op case) and the ON edge
is dirty — invisible to the author.

Compounding: the author-facing guard text at `raster_dsl.emp:340` states "only the FIRST op's
writes are measured to land in HBlank (row 119...)" — but the row-119 fixture
(`ojz_effects.emp:115`) has the stream op **second**. The guard asserts the opposite of the
measurement recorded 460 lines away.

Latent today (every shipped OJZ CRAM/region fire is the two-op sh:1 shape). Deficit is roughly
EFX_BLANK_DELAY 4 → ~21. **Verified:** all four citations verbatim.
**Fix:** split the constant by op position (`_FIRST` vs `_AFTER_REG`) and re-pin the F-series,
or refuse single-stream-op CRAM fires in `fire()` without an explicit measured opt-out. Correct
`raster_dsl.emp:340` either way.

### 2. Palette variant staleness is set on INSTALLED, not on CHANGED — the 15.1% gate is voided
`engine/effects/palette.emp:356` · C4-altitude-w1 · **costs cycles today**

`.cycling` sets `PAL_ACT_VARIANT_STALE` before `Palette_DoCycle` decides whether anything
rotated (rotation is timer-gated at `palette.emp:419`). Any section binding a cycle script *and*
a variant pays the full ~19,332-cycle re-derive every frame — the exact regression the stale bit
exists to remove; the code calls it "the 15.1%-of-frame gate". `OJZ_Preset_Sec3`
(`ojz_effects.emp:574`) is that combination, and its output section never even streams.
`.fade` has the same shape at smaller scale.
**Verified:** instructions, preset binding, and the fix's precondition (DoCycle already
accumulates a touched-line mask in d7).
**Fix:** move the stale-set into DoCycle's rotation branch, gated on `d7 != 0`. One instruction.

### 3. No interlock between a deferred IRQ4 and Raster_VBlank's frame rewind
`engine/effects/raster.emp:609` · C3-timing-w2 · source-confirmed, not emulator-confirmed

VBlank rewinds `Raster_Cursor` and clears `Raster_Dense_Lines` unconditionally; HInt has no
frame/line test. A dense run whose last line is 223 is authorable — both constructors
`ensure(top + lines <= 224)` (`raster.emp:348`, `:433`) — and the HInt counter decrements for
lines 0..224, so HINT is raised on the same line as VINT. IRQ6 masks level 4, so the pending
IRQ4 runs *after* the rewind: it consumes priming record 0, overwrites the flushed `$0A=0`, and
shifts the whole next frame by one record. With the shipped gradient (top=96) the 96-line run
renders at 189..223 instead of 96..191, and repeats every frame — a stuck state, not a blip.
**Verified:** both `ensure`s admit last-line 223; the rewind is unconditional; HInt has no
frame test. Interrupt-priority reasoning is from the project's own HInt survey, not measured.
**Fix (cheap, at the freeze boundary):** tighten to `top + lines <= 223`. Structural: a
one-byte frame-epoch flag so a pre-rewind fire retires as a park.

### 4. Off-screen ship's dropped-base guard hardcodes palette line 2
`engine/system/buffers.emp:402` · C4-altitude-w2

The guard tests `btst #2, Palette_Dirty` (line 2) but the ship's palette line is authored data
carried in the trailer. For any ship on CRAM line 1 or 3 the guard tests a bit nothing sets and
goes fully vacuous. Latent — shipped content only uses line 2. **Verified.**

---

## TIER 2 — CONFIRMED gate-soundness gaps. The freeze leans on these gates.

### 5. `effects_gates.py` is UNWIRED, and it is the sole invoker of the emulator-backed lane
`tools/effects_gates.py:11` · V-gate-vacuity

Nothing invokes it: no build, no test runner, no CI, no hook. The only mention in build.sh is
inside a comment. It is the sole invoker of `raster_off_gate`, `raster_source_gate`,
`snapshot_poison_gate`, `effects_scene_assert` (three scenes) and every cost fixture — all
reachable only when a human types one command. **Verified by exhaustive grep.**

*Nuance the seat did not state:* build.sh **does** wire the source-level lane —
`effects_budget_check.py` (line 191), the pytest tool suite, and the 11-poison expect-fail lane.
The gap is precisely the emulator-backed lane. Note build.sh's own comment records that the
budget check was itself run-by-nothing until 2026-08-16, and that a bug-ledger entry had
credited it with preventing a drift it could not have caught.

### 6. `RASTER_WORK_REGION_CYC` has no measurement path in any gate
`tools/effects_gates.py:214` · V-gate-vacuity

The cost gate hardcodes `--only F0,F1,F3,F5,F8`, omitting F4 — the sole `stream_pal_region`
fixture. So `RASTER_WORK_REGION_CYC = 122` (`raster_dsl.emp:1008`), the constant gating the
shipped OJZ water band, never reaches hardware. **Verified:** the literal is at line 214, and
the doc history shows the list grew `F0,F1,F3` → `+F5,F8` with F4 simply never added.

### 7. The budget model's per-fire rows contradict a live `ensure`, in the half nothing reads
`tools/effects_budget_model.toml:55` · C4-w2 + A2 + B2 (three seats, independently)

`sparse_fire_reg1_cycles = 396` vs the live `ensure` at `raster_dsl.emp:1124` pinning fixture F1
at **412** ("was 396 at RUNGS=4"). Water fire 660 vs 676. **Verified:** `effects_budget_check.py`
gates only the `[symbols]` table; grep shows `sparse_fire_*` is read by *nothing* — no .py, no
.emp, no .sh. The file even has a `_SUPERSEDED` convention it failed to apply here.

---

## REFUTED by overseer verification

### `RASTER_FIRE_BASE_CYC` omits the 44-cycle IRQ4 entry → check_density unsound
`engine/effects/raster_dsl.emp:991` · C1-perf-w2, filed **major** · **REFUTED**

The premise is that 302 is a post-entry figure. It is not: it derives from fixture F0's
**absolute measured** 572 cycles for two priming records (`docs/benchmarks/effects-p3/
DENSITY-EVIDENCE.md:73`, "no fires — priming records only | 2 | 572 | (286 per no-op record)").
An HInt invocation inherently includes its own exception entry, and the constant's own note
places the hand-count/measurement discrepancy "inside the exception-entry/`movem`/`rte`
timings this emulator models." The model is entry-inclusive; check_density is not unsound on
this ground. Recorded so the claim is not re-litigated.

---

## TIER 3 — CONFIRMED perf, ranked by leverage

| # | Site | Win | Note |
|---|------|-----|------|
| 8 | `raster.emp:714` | OP_SET_REG pays all 5 compare rungs — 80 of its 110 cyc | Two seats, two walks (C1-w1 + C4-w1). Leading `tst.w d1 / beq` decimates it |
| 9 | `raster.emp:736` | 30 cyc/streamed word (abs-long + dbf) vs 16 via `-4(a2)` | **Highest leverage:** this constant is what sets `RASTER_CRAM_MAX = 3` |
| 10 | `raster.emp:834` | dense kind re-tested per scanline: ~2,300 cyc/frame | Run-invariant; flags from the entry test carry it free |
| 11 | `raster.emp:656` | redundant SR push/pop, ~30 cyc/fire (~3,030/frame in §2) | `rte` already restores SR. **Needs a sigil-side context flavour → aeon/sigil pairing ritual + user sign-off** |
| 12 | `palette.emp` ×6 | `lsl.w #1` → `add.w dN,dN`: ~768 cyc per full derive | In the routine already flagged as the hot spot |
| 13 | `raster.emp:560,622` `palette.emp:386,666` | 4 missed mandatory tail calls, all per-frame | Clobber sets verified subset-clean |

Also: the effects corpus uses **zero** `assert.*` constructs though the engine ships that
zero-byte-in-release construct at 47 sites, leaving `Raster_BuildSchedule`'s record walk
unbounded where `bg_anim` asserts the identical shape (B1).

---

## TIER 4 — drift the freeze would enshrine as documentation

**A2 returned 10 major comment-truth defects.** The freeze makes these permanent, and A2's
historical value is precisely that false comments mislead the perf seats:
- `raster_dsl.emp:1630` trailer offset documented `8n`; runtime steps `10n` (five-word entries)
- `raster.emp:934` trailer described as holding a built 14-byte DMAEntry; it holds parameters
- `palette.emp:323` header describes a d7 dirty accumulator that does not exist
- `raster.emp:803` EFX_RESTORE_DELAY arithmetic uses pre-R1 SetReg cost (94, now 110)
- `raster.emp:82` movem round trip priced at 40; it is 84 (40 push + 44 pop)
- `ojz_effects.emp:568/586/617/680` four stale/contradictory fixture notes, incl. "neither
  channel ships" two lines above the pin showing one does, and a density margin 150 cyc too
  generous

**B2 (both walks) — hand-synced duplication with no gate:**
`BGANIM_MAX_BANDS` in four places (and unlike `RASTER_MAX_PATCH`, no span guard, so raising it
in the generator alone lets `BgAnim_Update` walk past the array) · `RASTER_SH_BASE` a hand copy
of boot's reg `$0C` byte held only by a comment claiming pin parity it does not have ·
`RASTER_BUF_SIZE/2` as a bare `64` in four encoder sites · `palette_dsl`'s variant mirror whose
only callers are its own self-tests, while `palette.emp:678` claims the asm is build-time
checked · `raster_cost_probe.py` re-implements the wire format unpinned — and it is the
instrument that calibrates the constants `band()` enforces.

**C5 footprint:** gradient wire format has no repeat primitive — 528 of 576 stream bytes are
literal duplication (CRAM is 3 bits/channel, so a monotonic gradient holds ≤8 distinct rows) ·
patched-template 128-byte pad's stated justification was deleted with the copy it protected;
82 of `OJZ_TwoChannel`'s 164 bytes are zero pad.

**New angle on booked EFX-4b** (C4-w2): static programs may need no RAM copy at all — walk the
ROM template directly, dissolving the over-read rather than patching it.

---

## Sequencing recommendation

1. **Before P1 executes:** Tier 1 (#1-4) and Tier 2 (#5-7). #1 and #3 are latent-but-authorable
   and become load-bearing once Aurora binds the substrate; #2 costs cycles today; #5-7 are the
   gates the migration's byte-identity claim rests on.
2. **Cheap, same parcel:** Tier 4's A2 comment corrections and the `ensure`/pin additions from
   B2 — zero-byte or near, and the freeze enshrines the docs.
3. **After the freeze, as byte-moving parcels:** Tier 3 perf. #11 needs a sigil change and is a
   novel mechanism — flag for owner sign-off rather than assuming.
4. **Do not re-litigate:** the REFUTED entry.
