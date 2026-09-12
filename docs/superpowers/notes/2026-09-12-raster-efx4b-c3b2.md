# Raster lens findings EFX-4b and C3b-2 — two branches, 2026-09-12

Worktree agent for the aeon overseer. Each finding is on its own branch. Line numbers below were
re-found by symbol.

**`tools/effects_gates.py` was NOT run on either branch.** It boots an emulator, and agents cannot.
Both branches touch `engine/effects/raster.emp`, so the effects-gate ritual applies: **the
controller runs it at landing.**

## Bases and the control

Both branches were cut from `origin/master` = `35f54923`. origin/master moved from `af5e097b` to
`35f54923` during the session: the worktrees share refs, and another session landed LS-10a. The
range `af5e097b..35f54923` is **docs only** (`docs/DEFERRED_WORK.md`, `docs/lane-log.jsonl`, one
notes file). The control built at `af5e097b` is therefore the byte control for both branches'
source. Branch 2's four CRCs matching it exactly is consistent with that.

Control, `tools/landing_build.sh` on `af5e097b`, run detached: `finished=0`, `REAL_EXIT=0`,
`emp_expect_fail` 54/54 in every shape.

| ROM | size | CRC32 |
|---|---|---|
| s4.bin | 821123 | 52828985 |
| s4.debug.bin | 847389 | ddf22eca |
| demo.bin | 97075 | c0898f05 |
| demo.debug.bin | 103359 | 80bbeb9b |

sigil `md5 49ecc532e0b133ab0eab9447e071805c`, unchanged before and after the session.

---

## Branch 1 — `parcel/efx4b-bounded-copy` — EFX-4b — CLOSED by padding

The branch name predates the choice: the fix is padding, not a bounded copy.

Commits on `35f54923`:
`38c63452` fix(raster): pad every static raster program to the install buffer ·
`5a1d80cb` docs(raster): static programs are emitted through static_program ·
`acaee6d1` docs(cite): name the symbol in two raster.emp citations the pad shifted ·
`24d3f826` fix(gate): plane_base_swap_gate asserts the PADDED OJZ_BaseSwap image ·
then the commit carrying this file (its SHA is the branch tip in the report).

### Enumeration — what stages a static program, by what touches the staging pointer

The staging pointer is `Raster_Pending`. Its writers, from a tree-wide grep of the symbol:

| writer | stores | source of the value |
|---|---|---|
| `Raster_Install` (raster.emp) | `a0` | its two callers, below |
| `Raster_VBlank` | clears it on consumption | — |
| `Raster_InstallPatched` | clears it (a staged static program loses) | — |
| emulator tools: `band_capture.py`, `band_witness.py`, `raster_off_gate.py`, `base_swap_witness.py`, `ramp_authored_witness.py`, `ramp_boundary_probe.py` | a ROM program symbol, or a RAM twin in scratch RAM | test instruments, outside the language |

`Raster_Install` has two callers: `Effects_InstallPreset` (`EffectsPreset.ep_raster`, or
`Raster_Program_None` when it is 0) and `Debug_BandDemoHotkey`'s `.raster_table` rows (or
`Raster_Program_None`). The programs those reach:

* **`ep_raster` values** (every `preset(raster:)` in the tree): `OJZ_TestRaster`, `OJZ_TestGradient`
  (struct), `Raster_Program_None`, `OJZ_DepthVSplit`, and through `ojz_act1_sec_raster`
  `EditorRaster_OJZ_Act1_ojz_sec5_showcase` and `_ojz_sec6_baseswap`.
* **`.raster_table` rows**: `OJZ_BandDemo` and `OJZ_BaseSwap` (both DEBUG-only),
  `EditorRaster_OJZ_Act1_aurora_ramp_witness` (struct), `_authored_probe`, `_ojz_sec3_shimmer`,
  `_ramp_probe` (struct).
* **Emitted, installed only by tools**: `OJZ_WaterRaster`, `OJZ_TestVsram`, `OJZ_TestRamp` (struct).

That is **14 static programs, all padded**: 10 `[u16]` arrays through `raster_program`, 4 dense-tier
structs (`RasterGradientProgram` ×1, `RasterRampProgram` ×3), plus one hand array. The hand array,
`Raster_Program_None`, **cannot reach `.copy_program`**: Raster_VBlank's semantic empty test (first
record's op_count == `RASTER_OPS_END`) diverts it to `HBlank_Uninstall` first. That confirms the
ledger's correction. Patched templates are outside this family: `patched_program()` already pads
them, and they are never copied (the builder re-records them).

### The candidates, each costed on this tree

* **A length word in the header.** It moves arm0 off word 1. "The header is ONE word" is what
  `patch_table`'s `rec_off` pre-resolution, the builder's constant 5-word prologue, every hand twin
  and every tool decoder rely on. Rejected.
* **A bounded copy.** The runtime cannot know the length. Records carry per-opcode payloads (OP_CRAM's
  is variable), so a record walk would be a second wire decoder in VBlank. A terminator scan is
  **unsound**: a legal raw ramp `start` with low word `$8AFF` followed by a small negative `step`
  (high word `$FFFF`) spells `[$8AFF][$FFFF]` mid-record. fp16() never produces that low word, but
  `raster_ramp_program` bounds a raw start's value, not its spelling. Rejected.
* **Walk the ROM program in place** (DEFERRED_WORK's booked angle). This is the cleanest runtime of
  all, but it makes `Raster_Active_Buf` a ROM pointer, and `tools/effects_scene_assert.py` refuses
  exactly that ("points at X, which is neither captured buffer") on the dense scene, whose program is
  the static `OJZ_TestGradient`. The ramp and base-swap witnesses also rely on the copy snapshotting
  their RAM twins. It is a mechanism change behind emulator-only gates. Rejected for this parcel, and
  answered in DEFERRED_WORK where it was booked.
* **Padding (chosen).** Data only: zero runtime bytes, zero cycles, and `raster.emp`'s procs emit
  identical code. The static and patched families now share one rule: an installable image is
  exactly the buffer, zero-filled past its terminator.

### What changed

* `engine/effects/raster_dsl.emp`: `static_words()` / `static_program(fires)` pad `raster_program`
  to `RASTER_BUF_WORDS`. The banner above them records the reasoning. `raster_program` stays the
  unpadded body the hand-twin pins, band-cap fixtures and `patched_program` read. Its existing
  `out.len * 2 <= 128` ensure keeps the pad non-negative.
* `engine/effects/raster.emp`: trailing `rgp_pad: [u16; 49]` / `rrp_pad: [u16; 47]`, zero-filled by
  both constructors, and `ensure(sizeof(..) == RASTER_BUF_SIZE)` for both structs. The pad lengths
  are literals, because of EMP_PITFALLS §8 and §2, and the ensure ties them to the constant. There is
  deliberately no `(size: N)` annotation: three tools find these structs by the regex
  `pub struct <Name> {`. Those tools read the program's fields by name and skip the array-typed pad,
  so the prefix they decode is unchanged. That is **why they stay valid**, and it is worth knowing
  they now see the first 30/34 bytes of a 128-byte struct.
* `games/sonic4/data/effects/ojz_effects.emp`: all six hand declarations. `tools/effects_gen.py`:
  both emission sites (bands, base_swap). `effects_scenes.emp` regenerated: four declarations, plus
  line-cite shifts in `effects_channel_bands.json`.
* `tools/test_static_program_padding.py` (new, in the build.sh pytest lane) refuses a `pub data` that
  calls `raster_program(` directly, since the old spelling still compiles. It fails on a corpus with
  zero `static_program` declarations.
* `tools/plane_base_swap_gate.py`: the landing build caught that this gate pinned `OJZ_BaseSwap`'s span
  to the 46-byte program, so s4.debug came back UNMEASURABLE. It now reads `RASTER_BUF_SIZE` from
  source, compares the program as the image's prefix, and FAILS on any nonzero pad byte (new pure
  helper `pad_nonzero`).
* Docs: EFFECTS_AUTHORING (examples, guard table, the EFX-4b bullet), EDITOR_RASTER_PRESETS, the
  consumer contract's lowering, ENGINE_ARCHITECTURE, DEFERRED_WORK. Two `raster.emp:N` citations the
  shift moved onto delimiters were rewritten as file + symbol. `test_citation_form` caught them; both
  were already stale before the shift.

### Red-first, every new check, mutation shown on disk before the red run

Each was restored with `git checkout HEAD -- <file>` from a committed baseline, with no other edits
in the file.

| check | mutation (`git diff`) | red result |
|---|---|---|
| `tools/test_static_program_padding.py` | `OJZ_TestRaster: [u16; static_words()] = static_program(..)` → `[u16; raster_words(OJZ_TEST_PROG)] = raster_program(OJZ_TEST_PROG)` | `1 failed, 1 passed`, names `ojz_effects.emp: pub data OJZ_TestRaster` |
| `ensure(sizeof(..) == RASTER_BUF_SIZE)` | `rrp_pad: [u16; 47]` → `46` **and** the ctor fill `0..47` → `0..46` (consistent, so only this ensure can fire) | build exit 1, `[Error] … RasterRampProgram 126 bytes, but … RASTER_BUF_SIZE (128)` |
| `pad_nonzero` (plane_base_swap_gate) | `return [i for i, b in enumerate(tail) if b != 0]` → `return []` | `1 failed, 19 passed`: `test_a_nonzero_pad_byte_is_reported` |

The gate itself on real artifacts: DEBUG `OJZ_BaseSwap` at 128 bytes before `OJZ_TestPal`, an 82-byte
pad, all zero, OK. Release emits 0 bytes, OK.

### Measured image shapes (`s4.bin`/`s4.lst` and `s4.debug.bin`/`s4.debug.lst` from the green landing run)

Every one of the 14 static programs spans **exactly 128 bytes**, and its last nonzero word is the
`$FFFF` terminator followed only by zero. `OJZ_BandDemo`/`OJZ_BaseSwap` emit 0 bytes in release, as
before (their labels alias the next symbol). `Raster_Program_None` stays 6 bytes (it is diverted).
The patched templates are unchanged (164 / 162).

Pad bytes, from each program's measured length: release 980 B over 12 programs, DEBUG 1080 B over 14.

### Byte picture — `tools/landing_build.sh` on `24d3f826`: `finished=0`, `REAL_EXIT=0`

`emp_expect_fail` 54/54 in all four shapes; needs_build lane 14 ran / 0 deferred / 0 failed; the tools
pytest lane was 2447 passed, 2 skipped in each shape.

| ROM | size | CRC32 | vs control |
|---|---|---|---|
| s4.bin | 821123 | 269b6b19 | size same, bytes moved (52828985) |
| s4.debug.bin | 847389 | 94fa9df8 | size same, bytes moved (ddf22eca) |
| demo.bin | 97075 | c0898f05 | identical |
| demo.debug.bin | 103359 | 80bbeb9b | identical |

ROM length did not move in any shape: the pad sits inside the images and the layout absorbed it. How
(which fill shrank) was **not measured** here. demo carries no static raster program, and the struct
change emits nothing, so demo is byte-identical.

**Byte-mover:** sigil-side goldens that pin `section:ojz_effects` / `ojz_effects_editor_act1`
(`crates/sigil-harness/repin.toml`, `pins.rs`) presumably need the repin/refreeze ritual. That is
the controller's and the sigil lane's step; I did not run sigil's tests (shared target dir).
`raster_port` should be unaffected, because `raster.emp`'s emitted code is unchanged and struct
declarations emit nothing, but that is `[UNVERIFIED]`.

New cross-module names: `static_program` and `static_words` (comptime helpers in the glob-injected
`raster_dsl`, referenced from `ojz_effects.emp` and the generated `effects_scenes.emp`). No new link
label. No sigil `*_port` test lowers `ojz_effects.emp` or `raster_dsl.emp`: grep of
`crates/sigil-cli/tests/*port*.rs`.

Ledger-ready note:
> EFX-4b CLOSED 2026-09-11 by padding: every installable static program image is exactly RASTER_BUF_SIZE,
> zero-filled past its terminator. The array family goes through static_program()/static_words(); the
> two dense-tier structs carry pad fields pinned by ensure(sizeof(..) == RASTER_BUF_SIZE). All 14 staged
> programs were measured at 128 bytes with a zero tail in both sonic4 shapes. The length word, the bounded
> copy (terminator scan unsound) and walk-in-place (effects_scene_assert refuses a ROM Active_Buf) were
> rejected, with reasons in static_program's banner. tools/test_static_program_padding.py refuses the old
> declaration spelling. Branch parcel/efx4b-bounded-copy.

TAGs: effects_gates NOT run (emulator); the controller runs it at landing. `[RUNTIME-UNVERIFIED]`: that
Raster_Buf_A now holds zeros past the terminator after an install (the ROM images are measured; the
copy's result in RAM is not). The dense scene captures 48 bytes of Buf_A, so bytes 30..47 of that
capture change from ROM junk to zeros. No effects_gates assertion reads them (the dense arm reads words
1/3/5/7/8/9/10), but the controller's run is what confirms it.

---

## Branch 2 — `parcel/c3b2-latch-disjoint` — C3b-2 — worst case REFUTED, residue NARROWED

Tip `eee80c90f2a9016f6c5d694c5408878875633a9a`, base `35f54923`. Commits: `c25b4499`
test(poison): GUARD 2 check_intervals gets its first negative fixture · `eee80c90` docs(raster): say
what the unbracketed Effects_Screen_L latch can and cannot do.

Files: `games/sonic4/test/poison/poison_patchable_overlap.emp` (new), `tools/emp_expect_fail.py` (one
CASES row), `engine/effects/raster.emp` (a comment block above `Effects_LatchWorldLines`).

### What `check_intervals` already covered, and why the seat missed it

`check_intervals` (raster_dsl GUARD 2, `7fbc0fe2`, 2026-08-15) refuses ANY program whose records'
reachable fire-line intervals are not strictly ascending and disjoint. A static record's interval is
its own fire line; a patchable record's is its band minus one. `raster_program()` calls it
unconditionally, and `patched_program()` calls `raster_program()` first, so no program the language
can emit escapes it. The seat's sentence ("`patchable()` ensures the line is inside its own band …
there is no ensure that consecutive records' bands are disjoint or ordered") is accurate about
`patchable()` and wrong about the program: the check lives one constructor up.

Why that closes the worst case (gap -1 = `$FF` = `RASTER_ARM_PARK`), each step read from the code:

1. Each `Effects_Screen_L` word is written by ONE `move.w`: the plain loop's `move.w d2,(a1)+`, the
   motion arm's `move.w d2,6(a0)`. A VBlank reader therefore sees a channel's old line or its new
   one, never half.
2. GUARD 11 in `raster_program` gives each channel at most one patchable record.
3. `Raster_BuildSchedule` clamps each record's line up to its own `band_lo_fl`, or DROPS the record
   past `band_hi_fl` (`.suppress`). It never emits a line outside the record's own band.
4. Bands are strictly ascending and disjoint, so the emitted lines ascend under ANY mix of
   per-channel cameras. That makes `gap = L[k] - L[k-1] - 1 >= 0`, and the byte is never `$FF`.
   `check_density` also measures between band edges, so a tear cannot overrun a line either.

**The worst case is unreachable for every program sigil will build, independent of content.**
Hand-spelled `[u16]` arrays bypass every DSL guard, this one included. No shipped installable program
is one (`Raster_Program_None` has no records).

**The residue that IS real (narrowed):** on a lag frame, the tear can put two channels' boundaries
one frame of camera motion apart, for one frame. It is cosmetic, and not unique to this window: a
VBlank landing anywhere between the latch and the end of `Parallax_Update` already pairs this frame's
raster with last frame's hscroll.

### The other call site's protection, and why it is not the better fix here

`Effects_InstallPreset` clears `Raster_Patch_Tab` and `Effects_Offscreen_Entry` before its call to
the latch. That clear is a ONE-WAY teardown of the outgoing program, which the incoming install
republishes. It exists for a different hazard: the outgoing table re-patched to the incoming anchors,
a one-frame boundary jump at every crossing.

Per frame it would have to be a save / clear / restore, and the restore races `Raster_VBlank`, whose
`.copy_program` and empty-program arms clear `Raster_Patch_Tab` themselves when a staged static
install lands. Restoring after that VBlank would resurrect a dead program's table over the new
program's buffer. Clearing the ship pointer would also drop a frame-top ship.

If the cosmetic residue ever matters, the cheap correct fix is a single `movem.l` publish of all four
words, since interrupts are taken only between instructions. An `ints_off` bracket would instead delay
VBlank entry by up to the motion arm's length.

### Proof — red-first, both on disk

* **Durable: `poison_patchable_overlap`**, two patchable records with bands 40..120 over 100..180.
  - Measured: 2 `[Error]`s. check_intervals reports "can collide with the previous record" (fire lines
    99..179 against 119); check_density reports -20 scanlines.
  - Wiring: row `GUARD 2 overlap` in `tools/emp_expect_fail.py` CASES, with that fragment and count 2.
    Green: `emp_expect_fail: OK — 55/55`.
  - Red-first mutation on disk: `-        ensure(lo_fl > prev_hi,` →
    `+        ensure(lo_fl > prev_hi || lo_fl == lo_fl,`. Result: `FAIL  GUARD 2 overlap … failed
    WITHOUT the expected fragment`, `emp_expect_fail: FAIL — 54/55`. Exactly the one row failed, and
    the error left standing was check_density's.
  - Restored with `git checkout HEAD -- engine/effects/raster_dsl.emp`.
  - This is check_intervals' first negative fixture: until now, relaxing it would have left every
    build green.
* **One-shot on shipped content:** `OJZ_TC_PROG` channel 1 `lo: 222` → `lo: 200`, overlapping channel
  0's `3..220`. It was refused by check_intervals ("fire lines 199..222 … previous record … 219"), by
  check_density, and by the `OJZ_TwoChannel` hand-twin pin. Restored from HEAD.

### Byte picture — zero bytes, as expected

`tools/landing_build.sh` on `eee80c90`: `finished=0`, `REAL_EXIT=0`, `emp_expect_fail` 55/55 in all
four shapes, needs_build lane 14 ran / 0 deferred / 0 failed, tools pytest 2442 passed / 2 skipped
per shape.

| ROM | size | CRC32 | vs control |
|---|---|---|---|
| s4.bin | 821123 | 52828985 | identical |
| s4.debug.bin | 847389 | ddf22eca | identical |
| demo.bin | 97075 | c0898f05 | identical |
| demo.debug.bin | 103359 | 80bbeb9b | identical |

New cross-module names: none. The poison is never imported, and no label was added.

Ledger-ready note:
> C3b-2 worst case REFUTED, residue NARROWED, 2026-09-11. The whole-frame dropout needs two records
> able to reach one fire line. check_intervals (GUARD 2, 7fbc0fe2) refuses that for every program
> raster_program/patched_program emit, and Raster_BuildSchedule's clamp-or-drop keeps each record in its
> own band. With one move.w per Screen_L store and GUARD 11's one record per channel, no camera tear
> gives a negative gap. "Nothing enforces that" was wrong, but the guard had no poison row; that is now
> closed by poison_patchable_overlap (red-first shown). The residue is a one-lag-frame cosmetic disagreement
> between two channels' boundaries. It stays unbracketed on purpose, with the reasons in the comment above
> Effects_LatchWorldLines. Branch parcel/c3b2-latch-disjoint @ eee80c90, zero bytes in all four shapes.

TAGs: effects_gates NOT run (emulator); the controller runs it at landing. `[RUNTIME-UNVERIFIED]`: the
cosmetic one-lag-frame residue. Nothing here observed a tear.

## Merge note

Both branches edit `engine/effects/raster.emp`, in different places: the comment above
`Effects_LatchWorldLines` on branch 2; the structs, constructors and the `.copy_program` comment on
branch 1. They should merge textually clean in either order. Whichever lands second moves
`raster.emp`'s line numbers again, so re-run `tools/test_citation_form.py` after the second merge.
