# Regions part 2, step 1 — `Region` 16 to 22 bytes, and nothing reads the new half

Parcel `parcel/regions-p2-step1`, based on aeon master `70c302ed`.
Spec: empyrean `origin/main:docs/superpowers/specs/2026-09-14-regions-part-2-design.md` §4.1,
step table row 1. No emulator was used; nothing in this step has a runtime observable.

## What landed

Two fields APPENDED to `Region` (`engine/structs.emp`), so no existing offset moves and
`Parallax_CheckBoundary`'s two span-major `move.l` cache fills are untouched:

```
rg_bg_layout: *u8 = 0    $10   nametable blob; 0 = Act.act_bg_layout
rg_bg_span:   u16 = 0    $14   BG map height in px, the scroll modulus; 0 = PLANE_B_SPAN
```

`ojz_region()` (`games/sonic4/data/levels/ojz/act1/act_descriptor.emp`) gains
`bg_layout: Label = 0, bg_span: int = 0` and three build-time `ensure`s. Act 1's ten region
rows are unchanged — both fields default — and **nothing in the engine reads either field.**
No streamer, no clamp, no wipe. The picture cannot have moved, and the `.bin` bears that out
(see "What the bytes did" below: every changed byte is the table's own growth plus two
`mul_const` sites).

`tools/region_table.py`, the one out-of-assembler `Region` reader, reads both new fields.

## THE FINDING: §4.1's three ensures, read literally, cannot all hold

§4.1 says the span must be "a multiple of 8, at least `SCREEN_HEIGHT`, and, when
`rg_bg_layout` is 0, equal to 0". As three unconditional conjuncts **that is unsatisfiable
for a defaulted row** — 0 is not >= 224 — and the SAME step-1 row requires act 1's ten
defaulted rows to compile unchanged. The two sentences of the spec contradict each other.

Resolved the only way that keeps both the sentinel and act 1: **rule 2 is written against a
span that is PRESENT.**

```
ensure(bg_span % 8 == 0, ...)                      // 0 already satisfies this — no exemption needed
ensure(bg_span == 0 || bg_span >= SCREEN_HEIGHT, ...)
ensure(bg_layout != 0 || bg_span == 0, ...)
```

The reasoning is written at the constructor, not only here, because the next author to read
§4.1 will meet the same contradiction.

The third rule's converse is deliberately NOT enforced: `bg_layout != 0` with `bg_span == 0`
is legal and means "my own picture, the plane's own height", which is what the field's
documented `0 = PLANE_B_SPAN` sentinel says.

## The four proofs the spec's step-1 row asks for

Each mutation was applied to the real file, read back off disk, built, and then restored with
`git checkout HEAD -- <path>` from the COMMITTED baseline. Logs under the session scratchpad;
the mutation text and the compiler's own words are quoted here because a restored tree and an
unapplied mutation print the same `ok`.

### 1. `(size: 21)` goes red

Mutation (read back from `engine/structs.emp:121`): `pub struct Region (size: 21) {`

```
EXIT=1
error: native build (sonic4 debug): build_program: 2 error(s);
  ./engine/structs.emp:121:26: [Error] struct Region: declared size 21 but fields total 22
```

### 2, 3, 4. Each new `ensure` inverted from the real call site

The call site is act 1's region row 0 (`act_descriptor.emp:649`), a row that ships. Each
mutation was chosen to violate exactly ONE rule, and each build named exactly that rule and no
other — which is what makes them three proofs rather than one.

| # | mutation appended to row 0's argument list | the build's own message |
|---|---|---|
| 2 | `bg_layout: OJZ_Act1_BG_Layout, bg_span: 516` | `act_descriptor.emp:499:5: [Error] ojz_region(x0: 0, y0: 0): bg_span 516 is not a multiple of 8 px. ...` |
| 3 | `bg_layout: OJZ_Act1_BG_Layout, bg_span: 216` | `act_descriptor.emp:504:5: [Error] ojz_region(x0: 0, y0: 0): bg_span 216 is shorter than the 224 px screen, so the scroll clamp \`0 .. bg_span - 224\` is empty ...` |
| 4 | `bg_span: 512` (no layout) | `act_descriptor.emp:511:5: [Error] ojz_region(x0: 0, y0: 0): bg_span 512 is written on a row whose bg_layout is 0. ...` |

516 is >= 224 and its layout is real, so only rule 1 can fire. 216 is a multiple of 8 and its
layout is real, so only rule 2 can. 512 satisfies rules 1 and 2, so only rule 3 can.

### A positive control the spec did not ask for, and it earns its place

Three reds prove the guards refuse. They do NOT prove the fields work: a `Region` whose new
half were dropped on the floor would pass all three the same way, because every act-1 row
takes the default and a guard that only ever sees 0 is a guard with no subject.

So: row 0 given `bg_layout: OJZ_Act1_BG_Layout, bg_span: 512` — legal under all three rules —
built GREEN, and the row was read back out of `s4.debug.bin` at `OJZ_Act1_Regions`:

```
row 0 bytes: 000007ff 000007ff 000154e0 0001486e 00024f5c 0200
             x0/x1    y0/y1    effects   parallax  bg_layout bg_span
rg_bg_layout ($10) = 0x24f5c   == OJZ_Act1_BG_Layout, from the listing
rg_bg_span   ($14) = 512
row 1 (untouched)  = 0x0 / 0   == the defaults, emitted as the sentinel
```

The fields emit, at the declared offsets, and the defaults emit 0. Restored afterwards.

## The pytest half — and it did not pass first time

The spec names `tools/parallax_crossing_gate.py`'s `struct_offsets()` as the reader to keep
green. **That is the wrong reader for this change.** `parallax_crossing_gate.py`'s
`struct_offsets()` is called for `Act`, `EffectsPreset` and `parallax_config` only; `Region`
goes through `tools/region_table.py`'s `struct_layout()`, a separate implementation, and no
pytest imports the crossing gate at all (it runs under `tools/effects_gates.py`, an emulator
lane). The test that actually holds the `Region` layout is `tools/test_region_table.py`, and
it **FAILED** on the record change:

```
AssertionError: struct Region's field order is ['rg_x0', ..., 'rg_bg_layout', 'rg_bg_span'];
the readers expect ['rg_x0', 'rg_x1', 'rg_y0', 'rg_y1', 'rg_effects', 'rg_parallax']
```

`REGION_FIELDS` is an exact-equality contract, not the subset check it reads as. Correct
behaviour: `region_table.py` is the one out-of-assembler `Region` reader and a row handed back
with the background half missing is a half-read record. Both names added; `read_regions()`
now returns `bg_layout` / `bg_span`, with the sentinel meaning written at the read.

A second gate also failed, and **its citation was already wrong before this parcel**:
`test_citation_form.py` reported `docs/ART_PIPELINE_CONTRACT.md:965 cites
engine/structs.emp:145 -- bare delimiter`. At `70c302ed` line 145 was a Page-frame comment,
not the `struct Sec` the prose names (`struct Sec` was at :194 then, :219 now). The gate's
predicate is "the cited line is not blank or a bare delimiter", so a citation that has drifted
onto any LIVE line is invisible to it; this parcel's comment block pushed it two lines further
onto `}`, and only then did it go red. Fixed by citing the symbol, and the gate's reach is
booked in `docs/DEFERRED_WORK.md` as `CITATION-LIVE-LINE`.

### A new test, proven red by inversion

`test_the_background_fields_are_appended_last_and_the_rectangle_is_still_two_move_l` holds
step 1's actual claim instead of its byte count, with both halves derived from the mechanism
rather than copied off the declaration: the four rectangle words must be the first four
fields, contiguous and long-aligned, because the crossing fills its cache with two `move.l`
over exactly those words; and the background pair must be LAST.

Inverted by moving the two fields BEFORE `rg_effects` with their offset comments renumbered so
the record still totals 22 and the offset-comment check still passes — i.e. the exact mutation
the test exists to catch and the only one the older checks would have let through:

```
AssertionError: struct Region's last two fields are ['rg_effects', 'rg_parallax']; the
background pair was APPENDED (regions part 2 step 1) so that no older offset moved.
```

Restored; 7 passed.

## What the bytes did, and a cost worth knowing before step 8

Measured by building the parcel's tree and the `70c302ed` baseline with the same toolchain and
diffing the listings' FULL symbol maps (identical symbol sets in both shapes: 3157 DEBUG, 2549
release), not by reading a size line and attributing the difference.

| shape | ROM total | what actually moved |
|---|---|---|
| `s4.bin` (release) | 820515 -> 820515, **+0 B** | `OJZ_Act1_Regions` +60 B (10 rows x 6), everything to `$A8000` shifts +60 and comes back to +0 there. **No code moved at all.** |
| `s4.debug.bin` | 846874 -> 846894, **+20 B** | table +66 B (11 rows — the shape carries the E2 snap row), same absorption; then `Debug_LabCycleHotkey` +10 B and `Debug_PresetReadout_Show` +10 B |

**The table's bytes cost nothing in either shape** — they land in padding that already existed
ahead of a fixed bank base. The whole of the DEBUG ROM's growth is the two `mul_const.w dN,
#sizeof(Region)` sites, where a power-of-two stride stopped being one and the macro re-elected
from a single shift to a shift-add chain. Neither site emits in release (their inner labels are
absent from `s4.lst` — the bodies are DEBUG-only), which is why release moved zero bytes.

**Carry this into the later steps:** changing this record's SIZE is a code cost at every stride
site, not only a data cost, and the table's own arithmetic cannot see it.

*Correction made before this note shipped, recorded because the wrong version was already
written down:* the first draft said release "does not carry the two DEBUG resolves" on the
strength of the path `games/sonic4/test/`. `Debug_LabCycleHotkey:` **is** in the release
listing, so that reasoning was wrong even though its conclusion survived — the bodies are
DEBUG-gated, not the file. The release figure above is measured, not inferred from the DEBUG
one.

The stale comment at the first of those sites ("sizeof(Region) is 16, so mul_const elects a
shift ... 160 bytes") was repaired in the same commit; both halves of it were false the moment
the record grew.

## Build shapes — all four green

`tools/landing_build.sh` at HEAD `f5e55cb0`, assembler sigil `700177b1`
(`md5(SIGIL_BUILD)=324d85d6ad5267a99bd57f118871ed1f`), `finished=0`, STAMP WRITTEN:

| shape | exit | size | md5 |
|---|---|---|---|
| `s4.bin` | 0 | 820515 | `b9f9698cca305eca8c8a25b9da05657d` |
| `s4.debug.bin` | 0 | 846894 | `01295a2407078afd9b8a45645e443010` |
| `demo.debug.bin` | 0 | 103642 | `10e87f9c44406e6b996c88d9b1f3e0a9` |
| `demo.bin` (the shape `landing_build.sh` does not build; `./build.sh demo`) | 0 | 97209 | `bffe70c4eefbc116be8835784df92dd1` |

Lanes, aggregate totals: pre-build `pytest tools -m "not needs_build"` **2689 passed, 2
skipped, 14 deselected, 140 subtests passed**; `emp_expect_fail` 5 passed / 9 skipped;
`needs_build` lane **13 ran, 0 deferred, 0 failed, 1 EXEMPTED** (`test_deb2_appendix[demo.bin]`
— a shape this caller does not build, graded by the `./build.sh demo` above, which ran it: "1
passed, 13 skipped").

**The first `landing_build.sh` run of this parcel exited 2 and is NOT evidence, and the reason
is worth repeating to whoever runs it next.** All three shapes built green in that run, but I
committed the docs WHILE it was running, so HEAD moved under it and the gate refused to stamp:
`NO STAMP: HEAD MOVED during the run (959e8be0 -> f5e55cb0). The run graded a tree that is no
longer HEAD; nothing it printed is evidence for either commit.` That is the gate doing exactly
its job — three green shapes and a printed md5 block look identical either way. Commit before
you start it, not during.

## Open / not done here

* **PAIRED HALF NOT DONE, and it is not mine to do.** This parcel changes ROM bytes in every
  shape, so sigil's goldens no longer match. Per the byte-changing ritual that is a
  `repin` + `refreeze --freeze <parcel> --ab` on the sigil side, landing in lockstep with this
  branch. Nothing here touches sigil and sigil's suite was not run.
* **Not cross-seam by NAME.** `rg_bg_layout` / `rg_bg_span` appear in `.emp` modules only:
  neither residual `game_root.asm`, nor `engine/debug/debugger.asm`, nor either `map.toml`
  names any `Region` field. (`map.toml`'s "Region geometry" is sigil's ROM-region concept, a
  different word.) So the new names cross no seam; the byte change above is the pairing
  obligation, not a name.
* **Steps 2 onward unstarted.** Nothing reads the fields; that is the step boundary, not an
  omission.
