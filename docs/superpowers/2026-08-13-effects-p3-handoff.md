# Next-session handoff — Effects Phase 3 (2026-08-13)

**Master is green and clean at `a4cd089c`.** Nothing is uncommitted except the auto-commit
daemon's files under `games/sonic4/data/editor/` (another session's work — never `git add -A`).

Start by reading, in this order:

1. `docs/superpowers/specs/2026-08-13-effects-p3-design.md` — **the spec. Three audit rounds
   deep; treat §1's ruling list as settled.**
2. This file, for what is done and what is next.
3. `docs/superpowers/plans/2026-08-13-replay-net-restamp.md` — only if the replay net needs
   re-stamping again (see "Standing hazard" below).

---

## Done this session

| Parcel | State |
|---|---|
| **0** — replay net | ✅ **COMPLETE.** Net green, both fixtures verified |
| **A** — `raster_dsl` + `palette_dsl` + budget checker | Spec'd; gating probe ANSWERED; **plan not yet written** |
| **C** — preset binding | Spec'd |
| **D** — starter pack + content | Spec'd |

**Parcel 0 commits:** `de2d5f6f` (plan) → `3649d237` (doc fixes) → `32a79e1d` (the re-stamp)
→ `bb678954` (structural test + DEFERRED_WORK) → `a4cd089c` (evidence).
Evidence: `docs/superpowers/notes/2026-08-13-replay-net-restamp-ab.md` + four captures in
`docs/benchmarks/replay-restamp/`.

**Suite:** `python3 -m pytest -q` → **944 passed, 2 skipped**. The 2 skips are
`test_s4lint.py` looking for a deleted `main.asm` — **not** the replay net.

---

## The §6.1 probe is ANSWERED — do not re-run it

Ruling 7 (computed-length arrays) is confirmed **on the real build path with a negative
probe**, recorded in spec §6.1:

- `pub data X: [u16; probe_words(2)] = [1,2,3,4]` builds
- the same type with 3 elements fails: `array length mismatch: expected 4 element(s), got 3`
- probe reverted → `crc=d792e8d6 len=711252`, byte-identical

**The trap that came with it, which binds Parcel A:** `const` does **NOT** enforce its
declared array length — only `data` does. A length guard written on a `const` is vacuous.
This also makes `engine/sound/sound_sfx.emp:1611`'s "THE LENGTH GUARD IS THE TYPE
ANNOTATION" comment misattributed (the guard there holds because of the `pub data` line
beneath it). **Every Phase-3 length guard must sit on the `data` declaration.**

Method note: there is no standalone `sigil emp` entry point — the `sigil` binary takes an
`.asm`, and `emp_census`/`emp_contracts` only inspect procs. A layout-exercising probe has to
go through a registered module and `./build.sh`.

---

## Next: write the Parcel A plan

Parcel A = `raster_dsl.emp` + `palette_dsl.emp` + the budget checker. **Comptime-only, zero
bytes moved** (spec §2.1) — all data relocation was deliberately pushed to Parcel C, because
if A moves data its byte-compare self-rebaselines into vacuity and its "no repin" claim dies.

**Gate:** all seven golden ROMs green with **no rebaseline**
(`sigil/crates/sigil-harness/golden/*.bin`).

Things the plan must carry (all established, don't re-derive):

- **A vocabulary table first** (spec §4.1). The byte-compare is only winnable if the
  constructors can express every word already in the tree — including `OJZ_TestRaster`'s
  plain `OP_CRAM` with an inline colour at a different CRAM address, the region op's
  address/entry/count triple, and the `pal_dirty_mask`/init words.
- **`SET_REG`-must-be-first `ensure`** for mixed fires (ruling 14), not the acknowledgment
  boolean that was superseded.
- **A is a PAIRED aeon+sigil parcel** — because the two DSL modules go on `COMPTIME_HELPERS`
  (`sigil/crates/sigil-harness/src/native.rs:1733-1746`). Merge the pair together.
- **The helper-closure collision diff** (spec §4.4) before the golden run, since
  `publicize_helper_comptime` force-publicizes a helper's private comptime items.
- **The `Label != 0` comptime witness** still owed (spec §5.2) — the exclusivity `ensure`
  relies on a variant mismatch in `values_equal` with no precedent in the tree.
- **T-1 is a DENSE-tier fact**, not sparse (spec §4.1). Applying it to sparse arithmetic
  fails the byte-compare in the most confusing direction.

---

## Standing hazard: character work in flight

A concurrent session is running lens fixes on character code
(worktrees `.worktrees/lens-char`, `.worktrees/lens-fixes` on `review/character-lens-sweep`).

1. **The replay hash covers `Player_1` SST fields.** If those fixes change player
   *behaviour* — spindash, roll, `EnsureStanding`, i.e. the same surface Knuckles C4 touched
   — the fixture re-stamped this session goes red again and needs another pass. The loop is
   documented end-to-end in the Parcel 0 plan; a repeat is ~20 minutes, not an exploration.
   Layout-only changes are safe: the hash is address-free by contract
   (`engine/system/replay.emp:7-16`, `:49-64`), so a layout break desyncs at checkpoint
   **0**, never mid-run.
2. **Wait for those to merge before starting Parcel A.** A's gate is "goldens green with no
   rebaseline"; character changes landing mid-parcel make a golden diff unattributable.

---

## Two open items that are NOT Phase 3's, recorded so they are not lost

- **The replay net has no automated runner** — not pytest, not cargo, not `test.sh`, no CI.
  That is how master stayed red from the C4 merge until this session with nothing reporting
  it. `tools/test_replay_fixture.py` now gates fixture *structure* only. Recorded in
  `docs/DEFERRED_WORK.md` §5 with two candidate fixes.
- **Three pre-existing defects** found by the audits, in spec §10 and owed to `docs/BUGS.md`:
  water surviving exactly one section crossing; the entire cross-fade layer being unreachable
  (`Palette_ArmFade`/`Palette_LoadCycle` have zero callers); and a count-0 cycle script
  leaving `PAL_ACT_CYCLE` set — which **Parcel C must fix**, because `Pal_Cycle_None` would
  be the first thing ever to exercise that path and it would re-arm the 15.1%-of-frame
  variant derive that `ff0720ff` just recovered.
