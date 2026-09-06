# Aeon `tools/` Lens Sweep (Roster B) — 2026-09-06

**Review pin: aeon `a02be34e`**, worktree `/home/volence/sonic_hacks/.aeon-tools-pin`, clean before and
after every seat. Read-only; all mutation done in `cp -a` copies under each seat's scratchpad.

**Corpus: `tools/` — 282 files, 127,658 lines**, of which **147 non-test tools** and **84 `test_*.py`**.
This tree was chartered **UNEXAMINED, NOT CLEARED** by the engine panel (packet `9cfebb72`); this is its
first review.

**Seats: T1 (generator correctness), T2 (gate honesty), T3 (build orchestration and cross-tool
consistency).** T1's parent seat was killed by the account session limit after fanning out; the
collision/art half completed and is reported here. **The OJZ-baker half of T1 was NOT covered and is a
named gap, not coverage.**

**Written under a pause for the owner's PC restart — seat prose preserved over polish.**

---

## T3 — build orchestration and cross-tool consistency

Denominator: **`build.sh` walked line by line, 1202 of 1202**, every tool invocation extracted
mechanically and classified by guard. Read in full: `level_staleness.py` (414), `regenerate-level.sh`
(245), `ojz_block_gen.py:1-560`. Ran: the block-generator cache 4×, `level_staleness.py`, three pytest
invocations, two `build.sh` runs under stub sigil binaries.

### T3-1 — a second live instance of the pre-sigil listing inversion, and this one SKIPS rather than fails

`tools/test_demo_specialization_witness.py:225-253` (`TestAgainstARealListing`) is collected by the
pytest lane at `build.sh:612`, **179 lines before** the sigil build at `:791`, and reads `s4.debug.lst`
out of the repo root. Measured both directions on a scratch copy:

| tree state | result |
|---|---|
| pin as committed (no `s4.debug.lst`) | `17 passed, 1 skipped` — the row vanishes silently |
| a 3-line fabricated `s4.debug.lst` planted | `1 failed, 17 passed` — on the row under test |

**Could the sample have failed?** Yes: the seat's first fabricated file passed green, and the verdict
tracked the file it planted. Six other post-sigil gates carry `--built-after ${SIGIL_T0}`; this class
carries neither that nor a lane. Live today in three ordinary flows, including any fresh clone.

### T3-2 — neither `STRESS_*` fixture shape can complete a build

Both keep `GAME=sonic4` and `FAST=0`, so the whole sonic4 post-sigil battery runs against
`s4.stress*` artifacts. Two independent collisions, both measured by calling the tools directly:

- `bganim_room.py` keys its ceiling on the listing **basename** and raises `Unmeasurable` for
  `s4.stress.lst` / `s4.stressart.lst` (`BGANIM_SECTION_CEILINGS` names only `s4.lst`, `s4.debug.lst`).
  Fail-closed and correct, but `build.sh:1024` cannot pass.
- `STRESS_EVICT` does not set `DEBUG=1` while passing `--stress-evict` to sigil, which builds debug —
  so `BASE_SWAP_SHAPE`/`REELS_SHAPE` resolve to `release` and grade a DEBUG ROM. `plane_base_swap_gate`
  asserts opposite things per shape and refuses a third value.

**Nothing in the tree exercises the STRESS path**, which is why it broke silently when those gates
landed (both dated 2026-09-06 in the pin). **⚠ The chain "therefore the build fails" remains a READ of
`build.sh`: the controller's two attempts to run `STRESS_EVICT=1 ./build.sh` did not complete (2-minute
tool cap, then the pause). Component facts measured; the conclusion is not.**

### T3-3 — both FAST banners enumerate 8 of the 19 lanes they skip and read as exhaustive

Named: `verify_level_bin`, `art_rom_report`, `s4budget`, `bganim_room`, `sprite_tilt_gate`,
`instashield_gate`, `loop_crossover_gate`, `effects_seam_gate`, `ctags`.
**Named in neither banner:** `effects_gen.py check`, `collision_consistency.py`, `row_remap_gate.py`,
`waterline_art_gate.py`, `editor_palette_golden.py`, `band_drift_golden.py`, `plane_base_swap_gate.py`,
`reels_gate.py`, `plane_role_swap_gate.py`, `dplc_straddle.py`, `dma_defer_headroom.py`.

Two matter most: **`collision_consistency.py`** catches the glide-momentum trap and the false-ledge
teeter, and **`effects_gen.py check`** is the only thing that catches a hand edit inside the committed
generated binding module. **Each of the eleven was added below the banner without extending it; the
next added gate makes it twelve.**

### T3-4 — `regenerate-level.sh` is hard-wired to sonic4 while `build.sh` invokes it for any game (latent)

`build.sh:482` and `:509` name it for `$GAME`; the script hardcodes `games/sonic4/...` and ends with
`--stamp sonic4`. Unreachable today (demo has no `data/editor`). The first `games/<newgame>/data/editor/`
makes `FAST=1 ./build.sh newgame` print "re-baking" having re-baked and re-stamped **sonic4**, then build
the new game from its stale tree, with the staleness gate red forever after.

### T3-5 — minor

`ctags -R .` runs bare under `set -e` after every gate has passed, so a ctags nonzero exits a successful
build with status 1 and no message. `-pe` is documented as accepted and is not: `./build.sh -pe` builds a
game named `-pe`. `STRESS_ART`'s restore trap omits two files the re-bake writes (currently inert,
deterministic). A tier-1 cache rejection has no distinguishing name in the log.

### T3 — checked and found SOUND

**The `tools/.cache` purity claim, tested rather than read.** Four runs, output hashed over all nine
`sec*_blocks.bin` plus the dict: `--no-cache` cold, cold cache, warm cache, and **a forged tier-1 entry
with a re-computed valid sha256 wrapper and one byte flipped inside the blob** — all four produce a
**byte-identical** output, and the poisoned section was rejected and recomputed. That fourth run is what
answers "could this have failed?": had decode-and-compare been absent, it would have read `9/9 served
whole` and the hash would have moved.

**Key completeness re-derived:** tier 1 hashes section index + raw data + both tool sources; `s4lz.py`
imports only stdlib (verified), so no third local module's edit can escape either key.

**`set -o pipefail` is on and `build.sh` is bash, not zsh** — the `PIPESTATUS` hazard in the brief does
not reach it, and the only pipes are three version parses and one `wc -l` inside an echo.

**The staleness gate's two arms are honest**, exclusions are not holes today (no generator reads them,
no such directory exists), the editor tree and stamp are both committed so the fresh-clone case is
genuinely quiet, and an unreadable file records a distinguishable value rather than comparing equal.

**Duplicated constants: 125 co-named across `tools/` and the engine, ZERO mismatching.** Includes
`SEC_SIZE = 34` in both `boot_override_gate.py` and `preset_lab_witness.py`.

---

## T2 — do the gates check what they claim

Denominator: **25 gate tools enumerated mechanically, 17 individually assessed, 12 actually executed**,
plus the whole 84-file / 2445-function pytest corpus **executed twice** (plain and line-traced),
**11 red-first mutation trials applied to disk, 9 valid, 2 invalidated by the seat's own targeting error
and diagnosed rather than reported.** Harness state: `2594 passed, 8 skipped, 112 subtests, rc=0`,
byte-identical totals traced and untraced.

### The headline is a NEGATIVE result, and it is a measurement

**The empty-population shape does not occur in the pytest corpus: 0 of 2445 test functions.** The seat
traced every line of every test file and asked, of each `for` loop containing assertions, whether the
header executed while the body never did. 73 functions were structurally at risk; every one of those
loops iterated at least once.

**The control that makes the zero worth anything:** it planted a `test_control.py` with a deliberately
empty population and re-ran the identical instrument. It flagged the vacuous case, flagged the partial
case, and correctly left the live loop alone. **The instrument can see the thing; the corpus does not
contain it.**

**An earlier version of this census reported 261 no-assertion functions. That number was the seat's own
blind spot** — its detector did not know `assertGreater`/`assertRaises`, so it was measuring `unittest`
style, not vacuity. It hand-read samples, found the error, rebuilt, and says explicitly: **do not carry
the 261 forward; it never described the tree.**

### T2-1 — `s4lint.py` is vacuous as a gate, with numbers

**584 of 1023 statements (57%) never execute** on the real build-time subject, line-traced and invoked
exactly as `build.sh` does. **44 of 64 functions are >50% dead** (`_analyze_dbf_loop_invariants` 97%,
`_invariant_read_key` 95%, `_parse_clobbers_header` 94%). **38 diagnostic codes are defined and none can
fire.** Vacuous as a gate; the 412 unit tests over synthetic inputs are **narrow but live** — the code is
tested, the subject is empty, and the aggregate merges those two different claims.

### T2-2 — a test whose name promises completeness and whose assertion checks two substrings

`test_build_fast_lanes.py::test_the_FAST_banners_do_not_claim_the_whole_gate_ran`. Docstring: *"Both
banners must name what was NOT measured."* Assertion: two `assertIn` calls about **one** gate's halves.
Measured against the real banner, **eleven genuinely-skipped gates are unnamed** (the same eleven T3-3
found independently). **Narrow, misfiled as complete: it cannot fail for the omission its own name
describes.** Its scoping comment is careful and correct about the haystack; the gap is the predicate.

### T2-3 — `effects_budget_check.py` axis-5 has a genuinely dormant arm

Run: `SpriteMask adopters: 0`. Three pricing comparisons sit under `if adopters > 0:` and have never
executed. **Narrow, not vacuous, and the author saw it coming** — the seat confirmed two neighbouring
arms by mutation (renaming a geometry constant → red; bumping a model value 7→8 → red), and line 227
states the intent: *"never a silent 0-adopter green."*

### T2-4 — `effects_seam_gate --source-only` does not see a malformed keyword on a non-chooser preset

Rewriting `raster:` → `rasterX:` at a real binding site left the gate green. **Suspected, backstop
unverified** — it should be rejected by sigil at compile time and `SIGIL_BUILD` was unset in that shell.
The gate **is** live on its own subject: renaming the declaration went red with a diagnostic naming both
the unbound preset and the orphaned rows.

### T2-5 — a print-only function inside the pass count

`test_dplc_tile_start.py::test_headroom_report` has no assertion and cannot fail; its own docstring says
so. Of 18 no-assertion functions, the seat hand-read 7: **1 is this, 6 are the legitimate
"must not raise" idiom, each paired with a negative twin.** Eleven unread.

### T2 — population by shape

| shape | count in slice |
|---|---|
| empty population | **0 / 2445 tests**, 1 gate arm |
| skipped rather than run | **8 skips / 2445 (0.33%)**, all with explicit reasons |
| a test nothing runs | 4 self-tests, 0 callers — **all four executed by the seat** |
| pins the wrong half of a pair | **0** |
| hand-copied literal | **0** — `emp_expect_fail` computes fragments from source |
| detector downstream of a filter | **0** |
| assertions copied not derived | **1** (T2-2) |
| loud-on-unmeasurable INVERTED | **0 — the opposite, 6 times** |

**On shape 3, a hypothesis the seat expected to confirm and did not:** nothing invokes `--selftest`
anywhere, so it ran all four rather than assume rot. `replay_pack` PASS, `prose_bound_sweep` PASS
("VERDICT: INSTRUMENT WORKS"), `dplc_straddle` rc=2 UNMEASURABLE, `dma_defer_headroom` rc=3
UNMEASURABLE. **Unrun, but not rotted, and loud about why they cannot run.**

**On shape 8, the repeated result is the inverse of the failure mode:** six gates refuse loudly rather
than reporting a green zero, and **21 of 84 test files hard-ERROR at collection** outside a suite
checkout rather than silently skipping.

### T2 — gates assessed and found sound

`row_remap_gate.py` (775 lines, **zero unit tests**) **mutation-tests itself** against the shipped ROM
record, including a control against its own fix going vacuous. `emp_expect_fail.py` defeats shapes 5/6/7
by construction — fragments **computed** from source constants, exact diagnostic counts, and a sentinel
case 0 as the anti-vacuity control. The fixture net was run **both directions**: a one-bit instruction
flip → 7 failed; a pure `+0x200` relocation → **stays green**, which is the designed invariance.
`level_staleness.py`: touching a PNG → STALE; **changing content while restoring the original mtime →
still rc=2**, the exact trap its docstring describes, closed.

---

## T1 — generator correctness (collision + art/palette half)

**⚠ The OJZ-baker half of this seat was never covered: its parent was killed by the account session
limit. UNEXAMINED, NOT CLEARED.**

### T1-1 — the imported S&K wall table uses the OPPOSITE sign convention to the engine, 232 of 256 shapes

The seat re-derived our convention against `probe_core` rather than trusting prose, then measured the
donor bank:

```
donor matches rotate_profile as-written: 24/256   (exactly the shapes whose rows are only 0 and 16,
donor matches SIGN-SWAPPED convention: 232/256     i.e. the values that carry no sign)
matches NEITHER:                         0/256
```

`import_sk_collision.build()` writes that donor bank verbatim to **both** `base/heightmaps_rot.bin` and
the live `heightmaps_rot.bin` the ROM embeds. **Every partial-width wall row would have its solid side
mirrored** — a wall solid on the left of a cell would push from the right.

**It cannot ship today:** `verify_level_bin.verify_collision_is_interned()` runs on every canonical build
and fails if a live table is byte-identical to `base/`. **But that tripwire's docstring explains the
danger purely as interning, and does not know a correctly-indexed raw bank would ALSO be wall-inverted**
— while `import_sk_collision.py`'s docstring calls `base/` "Authoritative". `collision_pipeline.py`'s 74
asserts never state the sign convention at all.

### T1-2 — `dedup_art.py` manufactures blank tiles for out-of-range DPLC references, and its own proof is blind

`dedup()` pads a short tile read with zeros; `loaded_bytes()` applies the **same** padding — so the
"EQUIVALENCE PROOF" compares padding to padding. Fixture: a 2-tile sheet with a DPLC requesting tiles 1,
2, 3. Exit 0, `EQUIVALENCE: OK`, and both non-existent tiles dedupe onto **one fabricated blank**, so the
frame loads `1, 2, 2`. The engine DMAs the blank into the character window and the frame renders with
transparent holes. Latent (shipped sheet is in range, and a byte-comparison test is build-fatal), and the
guard against exactly this — `verify_sprites.py` — lives in `test.sh`, which **no automated path runs**.

### T1-3 / T1-4 / T1-5

An out-of-bank shape index dies with a bare `IndexError` three frames from the cause, and the one
defensive guard present is what converts an error at the point of the mistake into a silent 0 that
survives to the crash site. `gen_collision_data.main()` **catches the exact `ValueError` its own loader
raises as a refusal** and emits plausible stub tables instead, exiting 0 — capped only by the fact that
**nothing invokes that file**, while its docstring claims `build.sh` does. And `collision_data.emp:114`
says *"NOTHING IN THE ENGINE READS THIS TABLE YET"* — both halves false: `Player_LoopCrossover` reads it,
and the committed table carries both mark values. The correction had already landed in
`collision_pipeline.py`'s header and not in the `.emp`.

### T1 — checked and found CORRECT, re-derived

**The Y-flip is exact over its whole domain**: for every in-contract byte the seat computed the 16-row
coverage vector, reversed it by hand, and compared — **0 errors in 33/33**. The single non-involution is
`0xF0 → 0x10 → 0x10`, both spellings of "full block", i.e. a canonicalization. **The angle flips are
exact**: both involutions over all 256 values, both parity-preserving (and that parity flag is
load-bearing), composing to exactly 180°. **`rotate_profile` never raises on the S&K bank in any of 1024
orientations**; on the sonic_hack bank 4 of 1024 raise, all shape 24, which is the refusal working and a
live tripwire rather than dead code. **`collision_pipeline.py test` was RUN: exit 0, 11 functions, 74
asserts, 344,064 placements.** Determinism is sound in both dedupe paths (stable sort over a fixed
candidate order; no dict/set iteration feeds baked bytes). **`png_to_bg_override.snap9` has no rounding
hazard** — a tie needs `v = 255(2k+1)/14` and `gcd(255,14)=1`, so no integer in 0..255 lands on a .5
boundary and banker's rounding is unreachable.

**Loose end closed by the controller after the seat reported:** `games/sonic4/vram.toml`'s `plane_b` /
`window_plane` overlap is **declared** — `overlay_with = ["plane_b"]` at `vram.toml:491` — so
`gen_vram_map.verify()` is satisfied. Not a defect.

---

# WHAT THIS PANEL DID NOT COVER

- **The OJZ bakers** — T1's parent seat died before reaching them. The single largest gap.
- **14 post-sigil listing gates could not be EXECUTED** by T2 (no `.lst`/`.bin` in the pin,
  `SIGIL_BUILD`/`SIGIL_EMIT` unset in subagent shells, read-only). Assessed by source read only.
- **`STRESS_EVICT=1 ./build.sh` never completed** — T3-2's conclusion is a read, not a measurement.
- **11 of 18 no-assertion test functions** unread; `band_drift_golden` read only in outline.
- **`effects_gates.py`**, the emulator-backed lane, out of scope by construction.
