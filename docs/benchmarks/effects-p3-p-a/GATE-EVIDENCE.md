# Effects P3 Parcel P-a — gate evidence

**Date:** 2026-08-15 · **Branch:** `parcel/effects-p3-p-a` · **Base:** aeon `970c4b01` / sigil `ccfc6226` (chain 118)

P-a is the **encoder half** of the patch generalisation: a raster fire can be declared patchable
and the DSL emits a self-describing patch table, so a runtime patcher never needs a hardcoded
offset. **No runtime code exists in this parcel.** Nothing installs `OJZ_TwoChannel`, nothing walks
the table. That is the point of the split — Parcel P-b's whole risk is trusting these table
offsets, so they are proved byte-exactly at build time first.

Spec: `docs/superpowers/specs/2026-08-15-effects-p3-parcel-p-design.md`
Plan: `docs/superpowers/plans/2026-08-15-effects-p3-parcel-p-a.md`

---

## 1. What this parcel does NOT prove

Stated first, deliberately. A gate document that implies more coverage than it has is the failure
this ledger exists to prevent.

- **No runtime walks the patch table.** Its correctness *in use* — that a patcher reading `arm_off`
  and storing a gap byte actually moves a boundary — is Parcel P-b's gate, not this one.
- **Nothing renders.** No pixel was measured in this parcel; there is no framebuffer evidence and
  none is claimed.
- **`check_arm_layout`'s coverage narrows with fire count.** It validates records
  `0..fires.len-1`, so a single-fire program cross-checks only record 0. The two-channel fixture
  checks two. Coverage is not uniform in the number of records.
- **The density model still does not count `OP_SET_REG`**, so it under-states cost and refuses only
  on evidence. Unchanged by this parcel, restated because guard 8 now cites it.

---

## 2. ROM CRCs

| shape | before (master `970c4b01`) | after P-a |
|---|---|---|
| `s4.bin` release | `0fcdcbaa` (697033) | `416be247` (697047) |
| `s4.debug.bin` | `50f6ae69` (711656) | `9ef00c29` (711670) |
| `demo.bin` | `6af0112d` | unchanged |
| `demo.debug.bin` | `fdc82cc0` | unchanged |

Both sonic4 CRCs moved **only at Task 7**, when the `OJZ_TwoChannel` fixture added ROM data. Tasks
1-6 and the two follow-up fixes were all verified byte-neutral against `0fcdcbaa` / `50f6ae69` —
which is itself the evidence that the encoder rewrites did not disturb the static path.

### 2.1 The byte delta did not match prediction, and the prediction was the wrong model

The fixture emits 73 words = **146 bytes**. The ROM grew by **14**.

This was not accepted on trust — a missing-data explanation would have made the whole gate vacuous.
The full 73-word image was computed independently in Python, outside the toolchain, and located in
the ROM at **`0x1281a`**: all 146 bytes present and byte-identical. The two ROMs differ in 16803
regions from `0x5642` onward (pointer fixups), i.e. **the placer repacked** and absorbed the
addition into inter-section fill.

**The freeze then confirmed it independently and more precisely.** `repin` reported every affected
data pin moving by a uniform **+0x90 (144 bytes)** — `OJZ_SEC2..8_*`, `SOLIDITY_TABLE`,
`ANGLE_TABLE`, `HEIGHT_MAPS`, `HEIGHT_MAPS_ROT`, in both plain and debug. So the fixture displaced
downstream content by its own size (146 bytes, aligned to 144 at the placement granularity) while
the ROM's total LENGTH grew only 14, because trailing inter-section fill absorbed the rest. Two
independent measurements — a byte search outside the toolchain and the pin deltas inside it — agree
that the data is present, correctly sized, and correctly placed.

Recorded because "N bytes of data ⇒ ROM grows by N ± alignment" is a model that will mislead the
next parcel that tries to predict a delta. It is the same class as the known *region pins include
placer fill* behaviour: the ROM length measures the placer, not the payload.

---

## 3. The guards, and the inversion that proves each is live

A guard that cannot be made to fail is not a guard. Every guard below was inverted — predicate made
false or fed bad input — confirmed to FAIL with its own message, then restored to green. This
codebase has a documented ledger of vacuous guards, and an `ensure` comparing an imported data
symbol to an integer passes silently, so nothing here is taken on faith.

| # | Guard | Inversion used | Result |
|---|---|---|---|
| — | sigil's `match` exhaustiveness | deleted the `Patch` arm from `fire_ops` | FAIL `[match.non-exhaustive] missing Patch` |
| 1 | band within 3..223 | `lo: 2` | FAIL `band 2..120 outside screen lines 3..223` |
| 1b | band not inverted | `lo: 150, hi: 40` | FAIL `band 150..40 is inverted` |
| 3 | channel in range | `ch: 9` | FAIL `channel 9 outside the legal range` |
| 3b | exactly one fire marked | two fires in the list | FAIL `got 2 fires — mark exactly one` |
| 4 | authored line inside its band | line 100, band 130..180 | FAIL `the authored line 100 is outside its own band 130..180` |
| 4b | not already patchable | double `patchable(patchable(...))` | FAIL `this fire is already patchable` |
| 7 | `RASTER_MAX_PATCH` power of two | set it to 3 | FAIL `must be a power of two` |
| 2 | disjoint ascending fire-line intervals | static fire line 99 vs band reaching fire line 99 | FAIL `fire lines 99..179 can collide with … fire line 99` |
| 8 | worst-case density | bands `40..120` and `121..200` | FAIL `models at 526 cycles but only 1 scanline(s) = 488` |
| 9 | same-line merge agreement | two patchables on line 100, `ch: 0` vs `ch: 1` | FAIL `disagree about channel or band` |
| 6a | table offset points at an arm word | `arm_word_index(k=0)` → word 2 (an `op_count`) | FAIL `is not a VDP reg $0A write` |
| 6b | …and at the RIGHT record's arm | `arm_word_index(k=0)` → word 3 (another record's arm) | FAIL `points at an arm word, but not that record's` |

### 3.1 Guards 2, 8 and 9 also DISCRIMINATE

A guard that refuses everything is as useless as one that refuses nothing. Each was shown to accept
the adjacent legal case:

- guard 2 — moving the band's `lo` from screen 100 to 101 (fire line 99 → 100) **builds**;
- guard 8 — widening the second band from `lo: 121` to `lo: 130` (1 scanline → 10) **builds**;
- guard 9 — changing the second fire's `ch: 1` to `ch: 0` so the two agree **builds**, which is the
  legal "layer two effects onto one moving line" case.

Also confirmed: `compose` merging a patchable fire with a static one on the same line yields **one**
record that is still patchable.

### 3.2 Guard 6's two halves are independent, which is the point

Half A pointed the table at word 2, an `op_count` holding 0: **both** ensures failed (0 is neither an
arm word nor the right value). Half B pointed it at word 3, priming record 1's **real arm word**:
the `$8A00` class test **passed** and exactly **one** error was reported — the value test alone.

That asymmetry is the evidence. The two ensures fail on disjoint inputs, so the value test is doing
independent work rather than shadowing the class test. Had half B passed, the table's offsets would
have been protected only against landing on a non-arm word, and a same-class misdirection — the
failure that silently corrupts the interrupt schedule — would have reached P-b unchecked.

---

## 4. The fixture twins

`OJZ_TwoChannel` (`games/sonic4/data/effects/ojz_effects.emp`) is pinned by three hand-authored
twins: the program body, the patch table, and the whole padded image. Each was proved able to fail.

| Corruption | Caught by | Index reported |
|---|---|---|
| `39` → `40` in the table twin | whole-image twin **only** | **67** — exactly `band_lo` (64=count, 65=arm_off, 66=line_src, 67=band_lo) |
| `$8A3B` → `$8A3C` in the body twin | body twin **and** whole-image twin | **3** |
| last table entry deleted (short by 4 words) | **the length ensure only** | — no mismatch reported at all |

### 4.1 `first_mismatch` is blind to length in BOTH directions

The third row is the important one. The function's own comment claimed it was blind only to
`a`-is-a-prefix-of-`b`. Measured here: deleting the last table entry produced **no mismatch report
whatsoever** — `for i in 0..a.len` never visits past the end of `a`, and the `i < b.len` test skips
everything past the end of `b`, so a shorter `b` is equally invisible.

It answers "do the words they share agree", never "are these the same array". The separate `.len`
ensure beside every twin is load-bearing, not belt-and-braces. The comment has been corrected in
place with this measurement.

### 4.2 The hand words were independently corroborated

The VSRAM command longword `$4002 $0010` and the channel-0 op words were verified against the
existing `OJZ_VSRAM_HAND` and `OJZ_WATER_HAND` fixtures in the same file, which write the same VSRAM
address and the same palette region respectively. The `%0100` mask was derived by hand:
`1 << ($48 >> 5)` = `1 << 2`, with the vsram op contributing 0. No hand word required correction.

---

## 5. Two latent defects found by the fixture, both predating this parcel

**`fx_tint_band` had never been called anywhere in the tree, and shipped broken.** Its body called
`pal_stage_off`, and a comptime fn's free names resolve at the **call site** — so every author using
the preset would have hit four copies of `unknown function pal_stage_off` for a helper they never
named. `OJZ_TwoChannel` is its first call site since it shipped in Parcel C1; the water fixture
reaches the same shape through `region_boundary` with a literal address and never exercised it.

Fixed at the source rather than at the call site: `fx_tint_band` now inlines the staging arithmetic,
held to `pal_stage_off`'s authority by the module-level pin that already existed for `pal_region` —
the convention the module header states. No author-side import is required. **Byte-identical.**

**`first_mismatch`'s documented blindness was understated** — see §4.1.

Neither was introduced by P-a. Both were latent for two parcels because nothing exercised the path,
which is the general lesson: an unexercised authoring surface is unverified regardless of how
carefully it was reviewed.

---

## 6. Structural checks

- **Helper-closure collision gate** (`tools/emp_helper_closure.py`): `OK — 446 names across 14
  helpers, no collisions`. Required because `raster_dsl` is a COMPTIME_HELPERS member, so every new
  public name (`RASTER_MAX_PATCH`, `patchable`, `patched_program`, `patched_words`) is glob-injected
  into every module in the tree.
- **Module reachability**: the `SIGIL_WARNINGS=full` unreachable lists were captured before (from a
  temporary worktree at `master`) and after, for both targets, and diffed: **identical**, 14 modules
  for sonic4 and 40 for demo. Not merely equal counts — the lists themselves match, so no module
  changed reachability and no existing guard silently went dead. (Those counts are by design: each
  such module evaluates in the target that uses it.)

---

## 7. Ritual — performed, with results

| step | result |
|---|---|
| four shapes built | PASS; both demo CRCs unchanged (`6af0112d` / `fdc82cc0`), confirming P-a touched no demo-reachable module |
| four shapes **booted** on oracle | PASS — all four; captures in the session scratchpad |
| `refreeze --freeze parcel-p-a --ab docs/benchmarks/effects-p3-p-a/GATE-EVIDENCE.md` | appended, chain **118 → 119** |
| both sigil binaries rebuilt against the new `pins.rs` | done (`sigil-cli` + `sigil-harness`) |
| CRCs re-verified **after** the freeze | `416be247` / `9ef00c29` / `6af0112d` / `fdc82cc0` — **stable**, the ROM did not move again |
| sigil suite | **3716 passed / 0 failed** across 327 binaries, exit 0 |
| `refreeze --check` | `OK (tip parcel-p-a, chain len 119)` |
| `repin --check` | `pins.rs unchanged` |

**Boot evidence, stated for what it is.** Release renders the OJZ scene with the player and correct
palette; debug renders planes and rings; both demo shapes render the documented white box on the
dark-blue backdrop. That is a *liveness* check — it proves no shape red-screens or blacks out, which
is the failure the release-shape blackout precedent exists to catch. It is **not** evidence about
patchable fires, and none is claimed: nothing installs `OJZ_TwoChannel`.

**Order correction.** The plan ran the suite *before* the freeze. That is wrong for a byte-moving
parcel — golden ROM images are regenerated by the freeze, so the golden comparisons would read red
until it ran. The freeze goes first, then the strict suite, then the two `--check` passes.

**Suite totals are a lower bound**: `deep_nesting_aborts` still aborts without printing a
`test result` line (booked, user-ruled not to chase), so the 3716 figure under-counts rather than
over-counts.

**The ROM did not move after the freeze**, so the goldens captured during it match the tree and no
second freeze pass was needed. This is checked rather than assumed because fixing a region changes
`pins.rs`, and those pins feed placement — a gate document citing a CRC it did not test after the
final freeze would be worse than one citing none.
