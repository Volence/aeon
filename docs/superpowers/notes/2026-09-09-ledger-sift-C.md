# Lens ledger sift — parcel C

Slice: `C2b-4, C3a-3, C3b-2, CTRL-1, B1-6, C1a-3, C3a-4, C5-7, V-7, V-8, CTRL-6, CTRL-7, CTRL-8, CTRL-10, CTRL-9`
(15 ids, per the dispatch — `CTRL-9`/`CTRL-10` listed last in the source dispatch string but
worked in numeric order below).

Each id's finding was extracted as the LATEST occurrence in `docs/lens-findings.jsonl` (parsed
line-by-line, last write per id wins) before any verification began. All checks below ran against
this worktree's checkout of `master` (branch `parcel/ledger-sift-c`, cut from the tip that also
carries `49a8144c`).

---

## C2b-4

**Severity:** high · **state:** open · Seat C2b, batch LS-2.
**Finding (one line):** an edit that removes a register from a Z80 proc's `clobbers()` set builds
green in aeon while sigil's own cross-repo test (`z80_clobbers_incomplete`) fails it — and aeon's
docs mention that gate only inside `DEFERRED_WORK.md` table rows, never as a required pre-merge
ritual.

**VERDICT: STILL-TRUE**

Evidence:
- `/home/volence/sonic_hacks/sigil/crates/sigil-cli/tests/z80_clobbers_incomplete.rs:14-21`:
  ```
  //! REFERENCE-DEPENDENT: the five resident sound `.emp` modules live in the
  //! sibling `aeon` tree (`AEON_DIR`, or `EMPYREAN_SUITE_ROOT`).
  //! Absent, every test here SKIPS green — unless `SIGIL_STRICT_GATE=1` makes a
  //! missing reference a hard failure, so the pre-merge run cannot skip the
  //! diagnostic.
  //!
  //! ```text
  //! SIGIL_STRICT_GATE=1 AEON_DIR=/path/to/aeon cargo test -p sigil-cli --test z80_clobbers_incomplete
  //! ```
  ```
  — confirms exactly the "gate fails ... under an environment variable" mechanism the row
  describes, and confirms it SKIPS GREEN by default (i.e. it does not run unless invoked
  explicitly with both env vars).
- `docs/DEFERRED_WORK.md:29746` (LS-2, closed) directly states the underlying measurement holds:
  *"The sweep's 'three of four cells unguarded' holds ... STILL OPEN and ranked ABOVE this item:
  Z80 under-declaration has no gate at all (see LS-2a)."*
- `docs/DEFERRED_WORK.md:29749` (LS-2a, still open, no strikethrough): *"The Z80 half of the
  contract family has NO gate in either direction ... What is missing is the gate that would
  catch a real one."* — this is aeon's own build, confirming the in-repo half is still green on
  a broken Z80 contract.
- The cross-repo gate (`[call.clobbers-incomplete]`) is mentioned in aeon's docs only inside
  `docs/DEFERRED_WORK.md` (LS-2's closure note and LS-14a, both table rows) plus the sweep packet
  itself — `grep -c` across `docs/OVERSEER.md`, `docs/BUGS.md`, `CLAUDE.md` for the term returns
  zero. No landing-lane ritual (`docs/OVERSEER.md`'s "Landing lane" section) names running it.
  The paired-freeze/strict-suite ritual that WAS in `OVERSEER.md` was explicitly retired
  2026-09-02 (`docs/OVERSEER.md:146-148`, "owner CUT THE CEREMONY"), which is a separate general
  mechanism, not this specific Z80 gate.

**Detail check:** the row's detail is accurate; no correction needed.

---

## C3a-3

**Severity:** suspicion · **state:** open · Seat C3a, batch LS-S1.
**Finding:** the HBlank window calibration (`tools/hblank_window_sweep.py`) folds in
interrupt-entry latency, which depends on what the main loop is executing; its "spread 0"
evidence is what a pinned mainline phase looks like, not proof the window is jitter-free. The
dense tier has no spin and fires many times a frame, which the instrument doesn't exercise.

**VERDICT: STILL-TRUE (suspicion undischarged)**

Evidence:
- `docs/DEFERRED_WORK.md:30020-30023` carries the suspicion **verbatim**, under a heading
  `## Suspicions carried forward, NOT booked as defects`:
  > "LS-S1 — the HBlank window calibration folds in interrupt-entry latency, which depends on
  > what the MAIN LOOP is executing, and `hblank_window_sweep.py` varies the spin word while
  > holding that term fixed. Its 'spread 0' evidence is what a pinned phase looks like. The
  > dense tier has no spin at all and fires 96×/frame. The falsifier is written so that a
  > REFUTATION is the more useful result — see packet C3a-S1. Do not let a confirming run ride
  > on the mechanism story."
- `grep -n "LS-S1" docs/DEFERRED_WORK.md` returns exactly this one occurrence — no closure entry
  anywhere else in the queue.
- `tools/hblank_window_sweep.py` still exists (`git ls-files tools/hblank_window_sweep.py`) and
  is referenced in several *other*, unrelated DEFERRED_WORK entries (line 12332, "SHIPPED. The
  mode is in `tools/hblank_window_sweep.py`") that extended its feature set (a `--words` input,
  flip-x columns) but never address the mainline-phase confound this suspicion names.
- The user's memory note "HBlank window solved — spins DERIVED not fitted; row N+1 convention
  pinned" describes a *different*, earlier-resolved topic (which row's word gets sampled),
  documented in `docs/benchmarks/scanline-p2/HBLANK-WINDOW-SWEEP-RESULTS.md` and pre-sweep
  planning docs from 2026-08 — none of it contains the phrase "interrupt-entry latency" or
  addresses the dense-tier-has-no-spin point. It does not settle this suspicion; the two are
  easily confused by name only.

**Detail check:** accurate as written.

---

## C3b-2

**Severity:** medium · **state:** open · Seat C3b, `where: engine/effects/raster.emp:2201`
(V2 in the packet).
**Finding:** the per-frame `Effects_Screen_L` latch — documented as "one latch, three readers,
one camera" — is written one word at a time from `Effects_LatchWorldLines`, with no `ints_off`
bracket, on both its arms; a VBlank landing mid-write tears the four values across two cameras.
The consequence (a negative inter-record gap storing `$FF` = `RASTER_ARM_PARK`, killing every
remaining fire) is masked today only because shipped content's bands happen to be disjoint with
margin — nothing enforces that. The latch's *other* call site (`Effects_InstallPreset`) IS
protected.

**VERDICT: STILL-TRUE**

Evidence:
- `engine/ram.emp:626-635` (current line numbers; content matches the row's cited intent
  verbatim):
  ```
  // The LATCHED, UNCLAMPED screen line of each patch channel: world_y - Camera_Y, signed,
  // recomputed once per frame in the MAIN LOOP (Effects_LatchWorldLines) after Camera_Update
  // and before Parallax_Update.
  //
  // IT EXISTS TO BE THE ONLY DERIVATION OF L. Three places used to compute anchor - Camera_Y
  // independently ... independent derivations put the fire line and the boundary state on
  // DIFFERENT cameras and every transition pops. One latch, three readers, one camera.
  ```
- `engine/effects/raster.emp:2201` is `pub proc Effects_LatchWorldLines () clobbers(d0-d4/a0-a2)`
  — the exact proc, confirming the row's `where.line` still resolves to the right symbol.
- Neither the motion arm (loop ending `dbf d0, .mch` around line 2283, storing
  `move.w d2, 6(a0) // Effects_Screen_L[ch]` at `raster.emp:2281`) nor the `.plain` fallback
  (`.plain_ch: move.w (a0)+, d2 / sub.w d1, d2 / move.w d2, (a1)+ / dbf d0, .plain_ch`, ending
  `raster.emp:2292`) is wrapped in `ints_off` / `ints_off_until_rte` — grepping the whole file
  for `ints_off` shows it used elsewhere (e.g. `raster.emp:1152`) but not around either of these
  two store loops.
- `Effects_InstallPreset`'s call site (the contrast the row cites) IS protected: it clears
  `Raster_Patch_Tab` first (`raster.emp:1762`, `move.l a1, Raster_Patch_Tab // table first`),
  with an explicit comment block (`raster.emp:1751`) about VBlank landing mid-update — the
  asymmetry the row describes.

**Detail check:** accurate; line 2201 still names the correct proc despite drift risk elsewhere
in the file.

---

## CTRL-1

**Severity:** high · **state:** open · seat: controller, batch LS-2.
**Finding:** register contracts (`clobbers()`) are machine-checked in one of four cells only
(68000 under-declare); three of four cells are unguarded, and the Z80 side is unguarded in both
directions. The row's detail also claims "the conventions document states they are
compiler-verified."

**VERDICT: STILL-TRUE — but the row's own detail is stale on one clause**

Evidence for the technical claim (still true):
- `CODING_CONVENTIONS.md:494-503` now carries the exact 2×2 table:
  ```
  | | under-declare (body writes MORE than declared) | over-declare (declaration wider than the body) |
  |---|---|---|
  | **68000** | **BUILD-FATAL.** ... | **UNCHECKED.** ... |
  | **Z80** | **UNCHECKED.** ... | **UNCHECKED.** ... |
  ```
  i.e. 1 of 4 cells guarded, exactly what the row states.
- `docs/DEFERRED_WORK.md:29749` (LS-2a, still open, unstruck): *"The Z80 half of the contract
  family has NO gate in either direction..."*

Detail correction: the row's supporting sentence — *"The conventions document states they are
compiler-verified"* — is **no longer true of the tree** and was already fixed before the row's
own timestamp window closed. Commit `b83204df` ("fix(contracts): the two live over-declaring
clobber sets, and what the conventions actually enforce", 2026-09-07T01:04:53-04:00) rewrote
`CODING_CONVENTIONS.md:492` from *"These are compiler-verified (tranche-3 ruling, §10)"* to the
2×2 table quoted above. `git merge-base --is-ancestor b83204df master` succeeds (it is `master`'s
own history — this worktree's HEAD is built on it). The row (`at: 2026-09-08T23:50:23Z`) was
written a day after that doc fix landed, and its *underlying technical measurement* (3 of 4 cells
unguarded) is a live re-derivation, not a repetition of the old doc claim — but as literally
worded, "the conventions document states they are compiler-verified" is false today and has been
since 2026-09-07.

---

## B1-6

**Severity:** medium · **state:** open · Seat B1, batch Tier 2.
**Finding:** nothing outside the source catches a magic mask/number; `tools/s4lint.py` (now
retired) carried none, and the sigil lint registry carries none either.

**VERDICT: STILL-TRUE**

Evidence:
- `git ls-files tools/s4lint.py` returns nothing (file untracked/gone); `git log --oneline --all`
  shows `6ee64536 retire(tools): delete s4lint and its 412 tests — LS-14, hub-ruled retire` —
  confirms the row's own "now more so" correction (one of the two places the seat looked no
  longer exists).
- Searched sigil's lint-emitting sources (`/home/volence/sonic_hacks/sigil/crates/*/src/*.rs`)
  for any `magic`/mask/number lint id: no lint named for a magic mask or magic number exists in
  the registry (`layout.*`, `clobber.*`, `branch.*`, `proc.*`, `call.*` families found; none for
  magic constants).
- No new lint tool has been added under `tools/` since; `CODING_CONVENTIONS.md` has no
  "magic-mask" grep hit either.

**Detail check:** accurate; the row's own self-correction ("STILL TRUE and now more so") is
itself confirmed correct.

---

## C1a-3

**Severity:** low · **state:** open · Seat C1a, `where: engine/objects/dplc.emp`.
**Finding:** `perform_dplc`'s entry decode spends 36 cycles (`lsr.w #8` + `lsr.w #4`) where
`rol.w #4` + `andi.w #$F` (22 cycles) would do; the seat priced it as not worth a standalone
landing (+2 bytes, ~154 cyc/frame peak, 0.12%).

**VERDICT: STILL-TRUE**

Evidence — `engine/objects/dplc.emp:333-337`:
```
    .entry_loop:
        move.w  (a2)+, d0                        // DPLC entry word
        move.w  d0, d3
        lsr.w   #8, d3
        lsr.w   #4, d3                           // d3 = tile_count - 1
        addq.w  #1, d3                           // d3 = tile_count
```
Unchanged — still the `lsr.w #8` / `lsr.w #4` pair the row describes, not the cheaper
`rol.w #4` / `andi.w #$F` form.

**Detail check:** accurate.

---

## C3a-4

**Severity:** suspicion · **state:** open · Seat C3a, `where: engine/level/section.emp`
(packet's S2).
**Finding:** `Section_RedrawPlanes` masks interrupts for a ~3-frame synchronous VDP poke storm on
the cache-recovery path (mid-game, display on, IE1 possibly set). The frame-rewind interlock in
`Raster_HInt` (`raster.emp`, "a stale fire ALWAYS lands on priming record 0") guards the rewind
case by construction, but a cursor left mid-schedule by an interrupt *mask* has different
provenance and sits outside that argument, which is stated as exhaustive. Low severity,
self-healing in one frame.

**VERDICT: STILL-TRUE (suspicion undischarged)**

Evidence:
- `engine/level/section.emp:181-186` (header comment, unchanged from the row's description):
  ```
  // Section_RedrawPlanes — camera-aware atomic full-plane rewrite (§4.2).
  // Level-init draw + cache-recovery path only (via Section_Plane_Dirty);
  // continuous-scroll streams the plane incrementally, so this never fires
  // mid-traversal (~3 frames synchronous when it does run).
  ```
- `engine/level/section.emp:229-231`: `move.w sr, -(sp)` / `move.w #$2700, sr` — masks interrupt
  levels for the whole storm; restored only at the tail. Confirms the "masks interrupts for
  three or four frames" claim.
- `engine/effects/raster.emp:1423-1424`: *"And it is sufficient, because a stale fire ALWAYS
  lands on priming record 0 — that is where the rewind put the cursor, and the rewind is the
  thing being interlocked."* — the interlock's own stated coverage argument, confirmed present
  and still framed as exhaustive (no qualifier added for a mask-induced mid-schedule cursor).
- The sweep packet's own write-up, `docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md:1118-1126`
  (`### C3a-S2`), matches the ledger row closely, including the exact interlock quote.
- No closure entry exists anywhere in `docs/DEFERRED_WORK.md` for this suspicion (`grep -n
  "C3a-S2"` only hits the packet itself); no other doc references it as settled.

**Detail check:** the row cites `raster.emp:1459-1463` for the interlock comment; current line
numbers have drifted (the "stale fire ALWAYS lands on priming record 0" sentence is now at
`raster.emp:1423`), consistent with the well-known line-rot risk this workspace's own notes warn
about (LS-4's convention of citing by symbol, not line). Not a factual error, just drift — the
symbol and the argument are both still there.

---

## C5-7

**Severity:** low · **state:** open · Seat C5, `where: tools/fixtures/s4_listing_excerpt.lst`.
**Finding:** the committed fixture's RAM layout is stale; a corrected RAM model gives
`Game_RAM_End = $FFFFBE02` (matching a real `.lst`), but the fixture shows `Game_RAM_End =
$FFFFBC02` — a 512 B (0x200) disagreement — and a prior validation against this fixture passed
only by luck (the `@align(256)` on `Player_Pos_Ring` absorbs ±128 B of error).

**VERDICT: STILL-TRUE**

Evidence:
- `tools/fixtures/s4_listing_excerpt.lst` (current content, last touched
  `a4ebf2d1`, 2026-08-18 — well before the 2026-09-04 `LEVEL-EXTENT-SYMBOLS` RAM growth):
  ```
  (0) 2181/FFFFBC00 :        Player_Ring_Index:
  (0) 2182/FFFFBC02 :        Game_RAM_End:
  ```
- `docs/DEFERRED_WORK.md`'s own "Landing evidence (2026-09-04)" table (around line 23712)
  records the real, post-landing figure: *"`Game_RAM_End` is `$FFFFBE02` (release) /
  `$FFFFED28` (debug)."*
- `$FFFFBE02 - $FFFFBC02 = $200 = 512` decimal — confirms the exact 512 B gap the row states.
- `git log -1 -- tools/fixtures/s4_listing_excerpt.lst` shows the fixture has not been touched
  since `a4ebf2d1` (2026-08-18), i.e. it predates the RAM growth that makes it stale, and no
  later commit corrects it.
- No `s4.lst` exists in this tree to re-derive the current live figure directly (not built, per
  task rules); the DEFERRED_WORK landing-evidence table is the best available independent real
  measurement and it corroborates the row.

**Detail check:** accurate.

---

## V-7

**Severity:** medium · **state:** open · Seat V, `where: engine/compression/s4lz.emp`, batch
Tier 2, booked as LS-17.
**Finding:** guard density (`ensure`/`assert`) is heavy in authoring-time DSL/constant files and
near-zero in runtime execution paths; sharpest instance, `s4lz.emp`'s stream-version check and
dictionary bound were DEBUG-only, so a malformed S4LZ stream in `s4.bin` (release) had no net at
any layer.

**VERDICT: ALREADY-FIXED (the sharpest/headline claim) — with an open residual the row itself
would still find true today**

Evidence the headline claim is fixed:
- `engine/compression/s4lz.emp:78-101` now carries a header block titled *"RELEASE-SHAPE FAULT
  CHECKS (LS-17, owner ruling 2026-09-09 — `crash`)"*, stating three checks (stream version,
  dictionary bound, written-extent-vs-header) are *"present in the SHIPPED ROM, not just the
  DEBUG shape ... gated `DEBUG == 1 || CRASH_REPORT == 1`."*
- `build.sh:217-218` refuses `CRASH_REPORT=0` for both canonical shapes (`if
  [[ "${CRASH_REPORT:-1}" != "1" ]]; then ... ERROR`), so `CRASH_REPORT == 1` is true in every
  canonical build including plain release — these checks are live in `s4.bin` today.
- Code confirms real fault paths exist now, not just comments: `s4lz.emp:301-325` has a shared
  `.fault:` tail calling `raise_error "S4LZ stream fault %<.w d0>"`, reached from `.fault_version`
  / `.fault_dict` / `.fault_extent` labels — this is the "net" the row says is absent.
- Landing commit: `805da83c` "ls17(s4lz): three checks that fault into the crash screen the
  release ROM already ships", committed `2026-09-08T22:34:54-04:00` = `2026-09-09T02:34:54Z`,
  which is **after** the V-7 ledger row's own timestamp (`at: 2026-09-09T00:46:54Z`). Full parcel
  `parcel/ls17-compression-crash` (commits `805da83c` .. `e793893a`) is on `master`:
  `git merge-base --is-ancestor 805da83c master` → true; `git merge-base --is-ancestor e793893a
  master` → true.
- `docs/DEFERRED_WORK.md:29786` (LS-17): *"PARTIALLY CLOSED 2026-09-09, `parcel/ls17-compression-crash`
  — the owner answered `crash`."*

Residual, NOT covered by the fix (so a rerun of the row's own methodology today would still find
part of it true):
- `engine/compression/zx0_resume.emp` still has **0 ensure(), 0 assert.** — deliberately left
  unguarded. Commit `1ee17a78 ls17(zx0_resume): the resumable decoder gets NO check, and the
  reason is structural` and `docs/DEFERRED_WORK.md:29786`: *"STILL OPEN, and deliberately: (a)
  `zx0_resume.emp` got NO check ... `@resumable` makes every [raise_error frame op] build-fatal
  there."*
- The broader guard-density asymmetry claim across other runtime files (`sound_sequencer`,
  `tile_cache`, `plane_buffer`, `sound_psg`, `collision`, `vblank`, `boot`) was not re-measured
  in this sift (out of scope of the row's central, headline sentence) and DEFERRED_WORK does not
  claim it was addressed either.

**Detail check:** the row's re-verification note ("Re-verified 2026-09-09 on master: s4lz.emp
still greps 0 ensure() and 3 assert.") is now misleading as a bare grep count — 2 of those 3
`assert.` string matches in the current file are prose *describing* the old, now-superseded
behaviour ("this was `assert.b d0, eq, #1`"), not live code; the only live `assert.` left is the
DEBUG-only dict-length-even check at `s4lz.emp:118`. A grep-only re-check would over-count.

---

## V-8

**Severity:** low · **state:** open · Seat V, `where: build.sh`, batch Tier 2.
**Finding:** the "always build all four shapes" rule (EMP_PITFALLS §6 Trap C) has no automation;
`build.sh:869` (approx.) now runs a scratch `sigil build --game demo` assemble on every
non-`FAST` sonic4 build (LS-16a), but its own banner disclaims that this is a demo build or
exercises demo's verification lanes — so the rule is partially, not fully, automated.

**VERDICT: STILL-TRUE**

Evidence:
- `docs/EMP_PITFALLS.md:188`: `- **Trap C — sonic4 can build green over a broken tree:**` —
  confirms the rule exists in the pitfalls doc.
- `build.sh:868-877` (current lines):
  ```
  if [[ "${GAME}" == "sonic4" && "${FAST:-0}" != "1" ]]; then
      _xg_out="$(mktemp -d)"
      echo "Evaluating the other game's link-time guards (assemble only, scratch output)..."
      if ! "${SIGIL_BUILD}" build --aeon . --native --game demo \
              -o "${_xg_out}/demo.bin" --emit-lst "${_xg_out}/demo.lst" >"${_xg_out}/log" 2>&1; then
  ```
  and `build.sh:844-846`:
  ```
  # WHAT A GREEN HERE DOES NOT MEAN: this assembles the other game to decide its
  # link-time guards. It is not a demo build, it runs none of demo's verification
  # lanes, and it says nothing about demo's ROM.
  ```
  — matches the row's quote verbatim.
- `git ls-files tools/test_extern_guard_reachability.py` confirms the LS-16c guard-half tool
  exists.
- `git log -1 --format="%H %ad" -- build.sh` → `4c4accb4 2026-09-08 20:23:03 -0400` — last touch
  to `build.sh` predates the row's timestamp (`2026-09-09T00:46:54Z`); no commit since adds
  per-commit automation of the *whole* four-shape rule (only the guard-evaluation half, already
  closed as LS-16a/LS-16c, is automated).

**Detail check:** accurate.

---

## CTRL-6

**Severity:** medium · **state:** open · seat: controller, `where:
tools/test_effects_gates_segments.py`, batch Tier 1.
**Finding:** the test is vacuous when artifacts are missing, correct when fresh, falsely red when
stale — a three-state guard, not a pass/fail one. The ordering defect (a listing-reading gate
running before the listing exists) was closed by `parcel/ls1-gate-ordering` (LS-1); LS-1a, LS-1c,
LS-1d remain open riders.

**VERDICT: STILL-TRUE** (the row's own "PARTIAL CLOSURE, STATED RATHER THAN CLAIMED" framing
matches the tree exactly)

Evidence:
- `build.sh:614-632` — the pre-build pytest lane explicitly deselects `needs_build`:
  ```
  # `-m "not needs_build"`; the tests that read a build artifact out of the working
  ...
      deselecting -m needs_build; those run in the POST-SIGIL lane below
  ```
- `build.sh:896-954` — a separate POST-SIGIL lane runs exactly `-m needs_build`, after the sigil
  build has produced the listing — confirming the ordering fix (LS-1) is present and structural,
  not merely claimed.
- `docs/DEFERRED_WORK.md:29741` (LS-1a, unstruck/open): *"the post-sigil lane's freshness rule is
  `mtime >= ${SIGIL_T0}`, which is provenance, not content ... nothing in the tree checks that a
  `.lst` corresponds to the source that is on disk."*
- `docs/DEFERRED_WORK.md:29744` (LS-1c, unstruck/open): *"The nightly is the ONLY runner of
  `test_segmented_parent_checks_the_row_set_it_aggregated`, so it is graded once a day and never
  at merge time."*
- `docs/DEFERRED_WORK.md:29745` (LS-1d, unstruck/open): `preset_lab_witness` failure mode,
  independently replicated at a different SHA.
- All three riders (LS-1a/1c/1d) carry no strikethrough/closure marker anywhere in
  `DEFERRED_WORK.md` — confirmed by `grep -n "^| LS-1[acd]"`.

**Detail check:** accurate; this is one of the more self-aware rows in the slice.

---

## CTRL-7

**Severity:** tagged · **state:** open · seat: controller (raised by C1a).
**Finding (TAG, not a defect):** every cycle-count figure in the performance seats assumes sigil
emits the mnemonic the source spells; a bare `bcc` relaxed to `.w` costs 12 not-taken cycles
rather than 8. Not one of the eight controller-run measurements checked this — it needs a read of
`s4.lst`, which this task is barred from producing (no build).

**VERDICT: STILL-TRUE — tag remains undischarged**

Evidence that nothing has settled it since:
- `grep -n "924 cycles\|C1a-1\|CTRL-7"  docs/DEFERRED_WORK.md` → no hits at all; the tag is not
  referenced anywhere in the living queue.
- `grep -rln "bcc.*relaxed\|not-taken.*12"  docs/` → only the sweep packet
  (`docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md`) and the ledger itself carry this
  language; no closure doc exists.
- No `s4.lst` is present in the tree (not built, per task rules), and none of the commits landed
  since the row's timestamp touch cycle-cost documentation for C1a-1/C1a-3.

**Escape hatch:** this TAG can only be discharged by reading a built `s4.lst` at a named SHA,
which requires a build — explicitly out of scope for this read-only sift (rule 6). Reported as
STILL-TRUE/undischarged rather than attempted.

---

## CTRL-8

**Severity:** tagged · **state:** open · seat: controller (raised by C1b).
**Finding (TAG, not a defect):** `tst.w Sst.code_addr(a3)` at offset `$00` is 8 cycles if sigil
folds the zero displacement, 12 if it emits `0(a3)` — makes C1b-F1's 2,784 cyc/frame figure
either the optimistic or the pessimistic end. Settled only by reading the listing.

**VERDICT: STILL-TRUE — tag remains undischarged**

Evidence: same search as CTRL-7 — `grep -n "2,784 cycles\|3,072 cycles\|C1b-F1\|CTRL-8"
docs/DEFERRED_WORK.md` returns nothing; no other doc references this tag as settled.

**Escape hatch:** same as CTRL-7 — requires reading a built `s4.lst`, out of scope here.

---

## CTRL-10

**Severity:** low · **state:** open · seat: controller, `where:
docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md`, batch Tier 3.
**Finding:** the packet is missing Seat B2a's entire write-up (though the summary, a controller
run, and 4 ledger rows B2a-1..4 all cite it) and Seat B2b's items 6-7 (body jumps 5→8). Header
claims ~75 findings / 7 suspicions; body only writes up a fraction of the suspicions.

**VERDICT: STILL-TRUE**

Evidence:
- `grep -n "^## " docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md` lists 15 `##` headings
  (Step 0, A2, B1, Step-0 addendum, B2b, C1a, C2a, C2b, C1b, Controller result, C4a, C3a, V,
  C3b, C5) — **no `## Seat B2a` heading anywhere in the current file.**
- Packet summary (`docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md:1600-1601`): *"Seats run:
  14 — step 0 ×2, A2, B1, B2a+B2b (twinned), C1a+C1b (twinned), C2a+C2b (twinned), C3a+C3b
  (twinned), C4a, C5, V."* — B2a is counted here, but has no section.
- `docs/lens-findings.jsonl` carries `B2a-1` through `B2a-4` (confirmed by `grep -n
  '"id": "B2a-'`), all citing `sweep.packet: docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md`
  — a reader who follows that citation finds no B2a evidence.
- B2b section (`docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md:329-449`) headings:
  `B2b-1, B2b-2, B2b-3, B2b-4, B2b-5, B2b-8` — jumps straight from 5 to 8, confirming items 6-7
  are missing. Ledger's `B2b-6` ("Comments across the engine cite assembler files that no longer
  exist") matches the *content* of the packet's `B2b-8` — confirming the renumbering claim.
- C2b's own census line (`docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md:694-695`): *"3
  verified findings, 3 characterised suspicions"* — but the C2b section (lines 692-793) only has
  one suspicion subsection, `### C2b's suspicion S1`, confirmed by `grep -n "^###"` over that
  range (no S2/S3).
- `git log --oneline -- docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md` shows exactly 11
  commits touching the file — matching the row's own "for each of the 11 commits that touched
  it" claim — and none of them adds a B2a section or B2b items 6-7.

**Detail check:** accurate; every specific sub-claim independently verified against the file on
disk.

---

## CTRL-9

**Severity:** low (corrected from `tagged` by the controller, 2026-09-09) · **state:** open ·
seat: controller.
**Finding:** the sweep itself records seven surfaces it did not fully examine (C4b never
dispatched; A2 sampled ~35/217 universals; B1's magic-mask sweep engine-only, games/ sampled;
C1a skipped `engine/sound/` and the player physics tree entirely; C4a only checked
`tile_cache.emp`'s entry points; B2b ran no harness / no red-first; C5's ROM pass sampled 81/135
`embed()` paths) plus the charter's own declared out-of-scope list. Not a defect — a record of
what the sweep's silence does/doesn't mean.

**VERDICT: STILL-TRUE (record of coverage gaps, confirmed present in the packet)**

Evidence, spot-checked against the packet:
- `docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md:1600-1601`: *"C4b was not dispatched —
  recorded as a gap, not as coverage."*
- Line 51 area: A2's field-offset sweep description ("62 structs, 29 fully sized") is present;
  the row's "~35 of 217" universal-claims figure and "1,846 'always'/'never'/'cannot'" population
  are specific enough that they trace to A2's section (not independently re-counted here, but
  consistent with the section's own stated sampling methodology).
- Line 441: *"The seat's own honesty about its limits, recorded: it executed no harness and ran
  no red-first..."* — matches the B2b claim.
- Lines 521-522: *"It did not open `engine/sound/` at all (~6,500 lines, and the 68k side runs
  every frame), nor `player_common/air/sensors/climb/fly/instashield` (~5,300 lines of per-frame
  code)."* — matches the C1a claim verbatim.
- Line 1490 area: *"ROM sampled: 81 of 135..."* — matches the C5 claim.
- This row is itself the mechanism that carried these gaps into the ledger; since CTRL-10 (above)
  independently confirms the packet's structural gaps (missing B2a section, truncated B2b), the
  two rows corroborate each other rather than conflict.

**Detail check:** the severity-correction note within the row itself (tagged → low) is a
self-correction, already reflected in the extracted latest line; no further correction needed.

---

# Summary table

| id | verdict |
|---|---|
| C2b-4 | STILL-TRUE |
| C3a-3 | STILL-TRUE |
| C3b-2 | STILL-TRUE |
| CTRL-1 | STILL-TRUE |
| B1-6 | STILL-TRUE |
| C1a-3 | STILL-TRUE |
| C3a-4 | STILL-TRUE |
| C5-7 | STILL-TRUE |
| V-7 | ALREADY-FIXED |
| V-8 | STILL-TRUE |
| CTRL-6 | STILL-TRUE |
| CTRL-7 | STILL-TRUE |
| CTRL-8 | STILL-TRUE |
| CTRL-10 | STILL-TRUE |
| CTRL-9 | STILL-TRUE |

**Counts (derived by counting the sections above, not from memory):**
- STILL-TRUE: 14
- ALREADY-FIXED: 1
- MOOT: 0
- UNDETERMINED: 0

Total: 15, matching the assigned slice.
