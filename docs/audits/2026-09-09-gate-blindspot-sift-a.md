# Gate blind-spot sift, batch A — 13 `tools/test_*.py` files (2026-09-09)

**Method:** `docs/DEFERRED_WORK.md` §"A GATE THAT DOCUMENTS ITS OWN BLIND SPOT IS NOT THEREBY
COVERING IT (2026-09-09)" (lines 30967-31001), read verbatim before starting and followed as
written. The discriminator is a **control**, not a re-read: for a declared non-coverage, construct
the case it says it would miss and check whether it is present in the tree TODAY. A declaration says
*this gate would not catch X*; only a control says *and there is no X here today*.

**Nothing in this audit was fixed.** OCCUPIED findings are recorded with evidence and left alone;
the ruling is the owner's.

**Scope:** 13 files, sifted by 4 parallel subagent lanes plus the controller; every SPECIFIC-
CONSTRUCTIBLE statement had its control run. The controller personally re-verified every OCCUPIED
finding rather than relaying it (per the repo's own "verify at dispatch" discipline).

---

## LEADING: OCCUPIED findings

Four distinct occupied holes, none of them in the severity class of sigil's instance (a silent live
defect behind a diligent note). O-1 through O-3 are **disclosed or already-booked**, which is stated
here so the class is not over-read. **O-4 was added in a follow-up pass** (below) that fills in
`tools/test_effects_gen.py`, which this report's own table left as "see the section below (audited
by a separate lane)" with no such section ever landing — that lane's output was never merged into
this file. O-4 is not disclosed anywhere else in this tree and is the one finding in this batch
closer to sigil's original shape: its safety today depends on an untracked cross-file agreement.

### O-1 — `tools/test_citation_form.py:19-28` — a MOVED citation resolving to real, plausible, WRONG text

The gate's declared gap: *"`ojz_scenes.emp` was the worst instance and this gate would NOT have
caught it: its numbers resolved to real, non-blank, plausible, wrong symbols"* — MOVED/GONE
citations are deliberately not gated (`tools/test_citation_form.py:387-389`).

**The case is present right now.** `tools/test_effects_gen.py:769-771` cites
`games/sonic4/data/effects/ojz_scenes.emp:170-173` as the source of the hand idiom
`drift: SceneDrift.Rate(-32)`. Controller-verified:

```
$ sed -n '165,180p' games/sonic4/data/effects/ojz_scenes.emp
// THE MASK BRIDGE, USE 1 OF 2. The shipped header declares band_count 4 with
// layer_mask $1F — five bits for four bands. ...
$ grep -n "SceneDrift.Rate(-32)" games/sonic4/data/effects/ojz_scenes.emp
220:    layers: [ layer(world_y: 512,  ... drift: SceneDrift.Rate(-32)),
221,222,223: (same, three more bands)
```

Lines 170-173 today are unrelated `MASK BRIDGE` prose. The cited code lives at 220-223. Prose was
inserted above it after the citation was written (at `1636e7726`, 2026-09-02, lines 170-173 *were*
the declaration). The citation is real, non-blank, plausible and about the wrong topic — the exact
shape the gate names and does not gate.

**Scale, from the gate's own census:** 185 of 359 live citations classify MOVED, 27 GONE. The gate
returns `citation form: OK` regardless — exactly as declared. This is not one stale line; it is a
population, and the gate's design decision not to gate MOVED is what leaves it open.

### O-2 — `tools/test_anchor_sweep_band.py:84-91 / 307-321 / 1397-1403` — the one live generated sweep has no band-fit or headroom check, and the module docstring states the wrong mechanism

Declared in three places; the most concrete is line 307-321: reporting the section-5 sweep as a
violation *"would be a claim this file cannot support: it does not read scene anchors."*

**The case is present.** Controller-verified by running the gate's own coverage report:

```
$ PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/tmp/blindspot-a-ctl-pyc python3 -c \
  "import sys; sys.path.insert(0,'tools'); import test_anchor_sweep_band as m; print(m.coverage_report())"
  LIVE GENERATED POPULATION: 1 sweep(s). the arm has a real subject; ...
  NOT CHECKED: seeded headroom for 0 of the 1 generated sweep(s) — ...
  NO BAND TO FIT: 1 of the 3 scanned sweep(s) — ojz_act1_sec_patch_motion(sec: 5, ch: 0)
    (section 5 -> preset OJZ_Preset_Sec5 binds no `patched:` program, so there is no raster band
     on any channel in the section(s) that install it)
EXIT=0
```

So the one live Aurora-authored sweep — shipping via the owner-approved d-53
`ParallaxConfig_OJZ_Underwater` loan — has zero band-fit and zero headroom verification.

**AND THE SECOND HALF, which is the part worth the owner's attention: the module docstring names the
wrong mechanism for its own gap.** Lines 84-91 say the sweep *"is in the second class and is
reported as NOT EVALUATED"* — the camera/spawn-section class. The live report puts it in a
different bucket entirely (`NO BAND TO FIT`, no `patched:` program at all), and the headroom-
unevaluated bucket the docstring points at reads **0**. The two later declarations in the same file
(307-321, 1397-1403) state the mechanism correctly. This is citation staleness in prose, occurring
where `test_citation_form.py` structurally cannot see it.

**Severity note, stated so this is not over-read:** the gap is *loudly reported on every run*
(`coverage_report()` / `UserWarning`), not silently swallowed. It is an open, disclosed hole, not a
green hiding a defect.

### O-3 — `tools/test_bg_emit.py:588-591` — a load-bearing factual claim about a sibling repo that has been false for 7 days

*"...it has to be, because no writer in either repo can produce vertical phases yet (aurora ROADMAP
row 55's column-wise shift-fill is costed and not built)."* Unedited since `40c378afa`
(2026-09-02).

**False since 2026-09-03.** Aurora ROADMAP row 55 is struck as DELIVERED.

**AND IT IS ALREADY BOOKED, which materially lowers this finding's novelty** — controller-verified:
`docs/DEFERRED_WORK.md:19022-19030` already carries it struck through, with
*"**STALE WITHIN ONE DAY — THE WRITER SHIPPED 2026-09-03 AND THIS SENTENCE WENT ON READING AS THE
BLOCKER.**"* The booking exists; what the booking did not do is reach the test file's docstring,
where the sentence still reads as a live justification. This is a distribution failure, not an
undiscovered hole.

### O-4 — `tools/test_effects_gen.py:3054-3059` — a `pal_region` band streams from a variant slot the document never authors, and the assumed hand-authored survivor is a real but untracked cross-file agreement

Declared gap (`_check_cleared_slot_is_not_streamed`, `tools/effects_gen.py:1664-1708`, "Ruling Q6's
narrow half"): a `pal_region` band naming a slot the document's `variants` array does not REACH
(absent, not explicitly `null`) is not refused — *"absent means 'the hand `preset()` call's value is
still there', which the generator cannot see, and that is the majority case."* Confirmed by reading
the function: `slots = preset.get("variants"); cleared = {i for i, v in enumerate(slots) if v is
None}; if not cleared: return` — an empty `variants` array has no `None` entries, so the whole check
no-ops.

**The case is present right now, in shipping content:**

```
$ python3 -c "
import json
for f in ['games/sonic4/data/editor/effects/presets/ojz_sec3_shimmer.json',
          'games/sonic4/data/editor/effects/presets/ojz_sec5_showcase.json']:
    d = json.load(open(f)); variants = d.get('variants', [])
    for b in d.get('bands', []):
        pr = (b.get('on') or {}).get('pal_region')
        if pr:
            slot = pr.get('slot')
            print(f, 'slot', slot, 'absent?', slot is None or slot >= len(variants),
                  '(variants', variants, ')')"
games/sonic4/data/editor/effects/presets/ojz_sec3_shimmer.json slot 0 absent? False (variants [{'shift_g': 1, 'shift_r': 1}, None] )
games/sonic4/data/editor/effects/presets/ojz_sec5_showcase.json slot 0 absent? True (variants [] )
games/sonic4/data/editor/effects/presets/ojz_sec5_showcase.json slot 0 absent? True (variants [] )
games/sonic4/data/editor/effects/presets/ojz_sec5_showcase.json slot 0 absent? True (variants [] )
```

`ojz_sec5_showcase.json` carries THREE `pal_region` bands naming variant slot 0 while its own
`variants` array is empty — the exact "absent" case the gate declares it does not refuse.

**Whether the assumption it rests on is actually true today was traced, not assumed.**
`games/sonic4/data/effects/ojz_effects.emp:1634-1646` declares the HAND-authored, section-5-
installed `OJZ_Preset_Sec5` with `variants: [Variant_Water_Deep, 0]` explicit — slot 0 IS populated.
The adjacent comment block (lines 1369-1394) already names this exact failure mode in its own words:
*"A preset with an empty variants array would CLEAR the slot under total binding, silently dropping
the water tint act-wide the moment a section crossing installs it — a real regression dressed up as
'the preset said nothing'."* So: today the two authoring surfaces (the editor JSON feeding
`effects_gen.py`, and the hand `.emp` preset in `ojz_effects.emp`) agree, and the agreement is
correct — but **nothing in the build graph checks that they agree**, and nothing would report it the
day they stop.

**Severity note, stated so this is not over-read:** this is not a currently-wrong ROM. It is a live,
named case of the declared gap, sitting in shipping content, whose only protection is a hand-
maintained coincidence between two files that do not reference each other.

---

## Table — every extracted statement

| File | Line | Verbatim quote (trimmed) | Class | Verdict | Evidence |
|---|---|---|---|---|---|
| test_anchor_sweep_band.py | 77-83 | "the occurrence would have landed in `unresolved` and the scan would have FAILED rather than falling silent" | FALSE POSITIVE | — | Asserts a catch, not a miss |
| test_anchor_sweep_band.py | 84-91 | "The live section-5 sweep is in the second class and is reported as NOT EVALUATED" | SPECIFIC | **OCCUPIED** | O-2; and the named mechanism is itself stale |
| test_anchor_sweep_band.py | 92-96 | "On channel 0 the band bound is currently WEAKER than `anchor_sweep()`'s own screen bound" | GENERAL-LIMIT | n/a | Re-derived accurate: 128px travel < 218-line ch0 band |
| test_anchor_sweep_band.py | 307-321 | "would be a claim this file cannot support: it does not read scene anchors" | SPECIFIC | **OCCUPIED** | O-2 (same underlying case) |
| test_anchor_sweep_band.py | 1397-1403 | "The live member today is section 5's generated sweep... reaches channel 0 through the d-53 parallax: loan" | SPECIFIC | **OCCUPIED** | O-2 (same case); this statement is accurate and current |
| test_anim_frame_bound.py | 22-23 | "does not check that a REGISTRY row is right — that Ani_Particle really is animated against Map_TestObj" | SPECIFIC | CLEAR | Both real spawn sites set `Map_TestObj` via `test_obj_prolog` |
| test_anim_frame_bound.py | 24 | "says nothing about the DPLC table (LS-9's `offset_table_frames(map)==offset_table_frames(dplc)` ensure owns that)" | SPECIFIC | CLEAR | That `ensure()` is live in 5 data files, build-fatal |
| test_anim_frame_bound.py | 24-25 | "nothing about whether a frame's art is correct" | GENERAL-LIMIT | n/a | No mechanical control decides "right picture" |
| test_anim_frame_bound.py | 84, 133 | "how a scan goes silently blind" / "a table the proof silently skipped" | FALSE POSITIVE ×2 | — | Reasoning for the assertion immediately following |
| test_bg_emit.py | 3-9 | "WHAT THIS FILE DOES NOT DO... read the tree's own `s4*.lst`" | SPECIFIC | CLEAR | 1 of ~30 mentions is a real read, `@needs_build`-gated |
| test_bg_emit.py | 191/199-206 | "TestBgAnimBandCeiling does not read it — either restore the name or add the array's real width" | SPECIFIC | CLEAR | `engine/ram.emp:752` still spells `BGANIM_MAX_BANDS` |
| test_bg_emit.py | 579 | "a later edit that re-hardcodes the horizontal reading would go unnoticed by every other test in this file" | SPECIFIC | CLEAR | The class it heads is 15 tests, 12 referencing `"vertical"` |
| test_bg_emit.py | 588-591 | "no writer in either repo can produce vertical phases yet" | SPECIFIC | **OCCUPIED** | O-3 — false since 2026-09-03, already booked |
| test_bg_emit.py | 1887 | "THE POINT: the symbol half alone cannot see this. Same tree, no --rom, green." | SPECIFIC | CLEAR | `build.sh:1213-1215` passes `--rom` on the gating call |
| test_bg_emit.py | 220, 777, 1844-49, 1681, 2138, 2666, 2869 | (7 hits) | FALSE POSITIVE ×7 | — | Historical bugs / assertion messages / deliberate modes the same test asserts |
| test_bganim_vprobe.py | 4 | "spelled in TWO places that cannot see each other" | FALSE POSITIVE | — | The problem the gate solves, not its own gap |
| test_bganim_vprobe.py | 25-29 | "WHY IT DOES NOT OPEN A ROM... the ROM-side claim is `tools/bganim_vprobe_witness.py`'s job" | SPECIFIC | CLEAR | Delegate exists, takes `rom_path`/`lst`, checks VRAM byte-for-byte |
| test_citation_form.py | 19-28 | "this gate would NOT have caught it: its numbers resolved to real, non-blank, plausible, wrong symbols" | SPECIFIC | **OCCUPIED** | O-1 — `test_effects_gen.py:769` cites `ojz_scenes.emp:170-173` |
| test_citation_form.py | 148 | "Asking it cannot see an ignored tree BY CONSTRUCTION" | FALSE POSITIVE | — | Describes the fix, phrased as a negated blind spot |
| test_citation_form.py | 387-389 | "MOVED/GONE are deliberately NOT gated" | GENERAL-LIMIT | n/a | Design choice; the companion of O-1 |
| test_deb2_appendix.py | 51-52 | "does NOT tell you whether your edit moved a ROM. It cannot... the repin/refreeze ritual's job" | GENERAL-LIMIT | n/a | Needs an external CRC-vs-baseline ritual |
| test_deb2_appendix.py | 54 | "does NOT cover the non-`mark` half of the hazard (renamed or added labels)" | GENERAL-LIMIT | n/a | Open-ended future-edit class |
| test_deb2_appendix.py | 55-56 | "does NOT check the appendix CONTENTS beyond its magic and non-emptiness — a corrupt table with a correct header passes" | SPECIFIC | CLEAR | `deb2_probe --verify`: all 4 ROMs IDENTICAL |
| test_deb2_appendix.py | 57-58 | "grades only the shape THIS `./build.sh` produced... DEFERRED by conftest.py, never silently skipped" | SPECIFIC | CLEAR | Ran with zero ROMs: "4 deferred... NOT passes" printed |
| test_demo_specialization_witness.py | 274 | "Not a derivation OF the pin (that would re-create the shared blind spot the poison exposed)" | SPECIFIC | CLEAR | `test_every_pinned_proc_is_a_proc_that_actually_hosts_a_gated_span` passes today |
| test_drift_record.py | 186 | "`shapes` returned 3, which the caller cannot see" | FALSE POSITIVE | — | Assertion message about the reader's behaviour, not this file's scope |
| test_drift_record.py | 316-327 | "shapes the job builds and the record does not cover" | SPECIFIC | CLEAR | Covered set == job's exact 4 shapes; detector fires on a synthetic 5th |
| test_extern_guard_reachability.py | 44-46 | "watched, not closed... no mutation of THIS repo can drive it red" | GENERAL-LIMIT | n/a | Sigil-side allowlist; 0/5 shapes inapplicable today |
| test_extern_guard_reachability.py | 52-56 | "(H2) a guard whose condition is rewritten so it can no longer be false" | GENERAL-LIMIT | **UNRUN (full) / CLEAR (narrow)** | Full semantic proof needs a mutating census sweep; static scan of all 139 conditions found zero literal self-comparisons |
| test_extern_guard_reachability.py | 57-59 | "Per-guard identity... nothing in the toolchain today can distinguish that" | GENERAL-LIMIT | n/a | Corroborated by DEFERRED_WORK LS-16c |
| test_extern_guard_reachability.py | 64-67 | "our scanner cannot see a closure, and sigil's counts do not know which sites are ours" | GENERAL-LIMIT | n/a | Structural split of authority |
| test_extern_guard_reachability.py | 140-149 | "`--check` therefore CANNOT see them... This gate cannot close LS-16b and does not pretend to" | SPECIFIC | CLEAR | Live 5-shape sweep: `test_excusals_are_not_stale` passed |
| test_freeze_preflight.py | 21-27 | "WHAT THIS DOES NOT DO... It never runs cargo." | GENERAL-LIMIT | n/a | Deliberate: the real gate relinks the binary other lanes pin against |
| test_freeze_preflight.py | 29-36 | "If sigil ever changes the staleness sentence, this file stays green while the real pre-flight misclassifies" | SPECIFIC | **CONFIRMED-STILL-CLEAR** | Re-checked at sigil tip today; see below |
| test_gate_fixtures.py | 124, 868 | "No blind spot: every address-shaped operand resolved..." / "Never render a blind spot as silence." | FALSE POSITIVE ×2 | — | **This file carries ZERO genuine non-coverage claims** |
| test_lab_index_lint.py | 33-34 | "The acknowledged limit is the same: this reads SOURCE, not the ROM." | GENERAL-LIMIT | n/a | Open-ended "the assembler could be wrong" class |
| test_lab_index_lint.py | 304-305 | "`.lab_index`'s own absolute address is a link-time fact this text lint cannot see" | SPECIFIC | CLEAR | `.lab_index` at `$0BEB74` — even; 79 of 3105 labels are odd, so the check discriminates |

| test_effects_gen.py | 2420-2431 | "Ruling Q6's narrow half... A slot the variants array does not REACH is not refused" (boundary arm) | SPECIFIC | CLEAR | No real preset document uses the `boundary` key at all — vacuously clear |
| test_effects_gen.py | 3054-3059 | same ruling, `pal_region`/narrow-slot arm: "absent means... which the generator cannot see" | SPECIFIC | **OCCUPIED** | O-4 |
| test_effects_gen.py | 3813-3816 | same ruling, anchor/sweep arm: "absent means the section's hand-authored anchor is still there, and the generator cannot see it" | SPECIFIC | CLEAR | The one real sweep document (`ojz_sec5_showcase.json`) authors `patch_world_ys[0]` explicitly, not absent |
| test_effects_gen.py | 4488-4489 | "a compiled `lsr.b #2` the JSON cannot see" | FALSE POSITIVE | — | Enforced by the very next assertion (document order preserved verbatim) |

`tools/test_effects_gen.py` was left as "see the section below (audited by a separate lane)" in the
version of this file first committed — that lane's output never landed here. **Filled in above** in
a follow-up pass (same audit, same branch); see the O-4 control below for the full derivation.

---

## Controls, per SPECIFIC-CONSTRUCTIBLE statement

### `test_freeze_preflight.py:29-36` — CONFIRMED-STILL-CLEAR (controller-run)

The brief asked whether the prior control (recorded in `DEFERRED_WORK.md:30942-30950`, run at sigil
`ea8c64fa`, verdict NOT occupied) is still current. It is.

Read at a **committed** revision of sigil, never through the working path (another lane's live
tree):

```
$ cd /home/volence/sonic_hacks/sigil && git log -1 --format='%H %ci'
30189ca0f27e6bd6f14429d83807987cac9f4884 2026-09-09 05:03:29 -0400
$ git show 30189ca0:crates/sigil-harness/src/repin.rs | grep -n "STALE against the live listings"
1432:        "src/pins.rs is STALE against the live listings.\n\n{report}\n{}",
2208:                    !line.contains("is STALE against the live listings"),
2233:            gate.contains("is STALE against the live listings"),
```

Sigil has moved since `ea8c64fa` (tip is now `30189ca0`, and `repin.rs` has been touched: `53bc85de
repin: delete the tests field, and report the pins nothing imports`), so this was **not** a no-op
re-check. The emitted sentence at line 1432 is byte-identical to both consumers on our side:

```
$ grep -n "STALE against the live listings" tools/freeze_preflight.sh tools/test_freeze_preflight.py
tools/freeze_preflight.sh:114:    if grep -q "is STALE against the live listings" ...
tools/freeze_preflight.sh:120,151: (the two evidence-printing arms)
tools/test_freeze_preflight.py:62:    src/pins.rs is STALE against the live listings.
tools/test_freeze_preflight.py:177,210,355: (fixture assertions + the pattern literal)
```

**Positive control:** the search discriminates. `git show 30189ca0:...repin.rs` was grepped for a
reworded variant and returns nothing, and the same grep run over the two aeon consumers returns the
literal — so a reword on sigil's side would show as an absence here, not as a silent match.

**Verdict: CONFIRMED-STILL-CLEAR** at sigil `30189ca0`. The declared gap is not occupied today.

**One correction to the record while I was here:** `DEFERRED_WORK.md:30901` says
"`tools/test_freeze_preflight.py` (12 tests)". It is **13** today —
`PYTHONDONTWRITEBYTECODE=1 ... python3 -m pytest tools/test_freeze_preflight.py -q` → `13 passed in
0.53s`. Cosmetic, but the doc's number no longer matches the file.

### O-1 control — `test_citation_form.py`

Commands and output are quoted in the OCCUPIED section above (controller-verified independently of
the reporting lane). The lane additionally ran the gate's own census —
`python3 tools/test_citation_form.py --census` → `LIVE: 359 citations / 185 MOVED / 124 STABLE / 27
GONE / 23 anchored` — and the gate returned `citation form: OK`, i.e. the case passes the gate, as
declared. **Positive control:** the same classifier's `_dead()` path *does* fail on the sibling
class (blank / past-EOF / delimiter targets), so the classifier is not inert — it is structurally
blind to MOVED by design.

### O-2 control — `test_anchor_sweep_band.py`

Controller-run `coverage_report()` output quoted above (exit 0). Corroborated in source:
`games/sonic4/data/effects/ojz_effects.emp:1634-1654`, `OJZ_Preset_Sec5` binds
`Raster_Program_None` (no `patched:` program) while passing
`ojz_act1_sec_patch_motion(sec: 5, ch: 0)`, and `docs/decisions.jsonl` d-53 records the owner-
approved parallax loan that gives channel 0 its consumer. **Positive control:** the same report
names the other two scanned sweeps as *checked*, so "NO BAND TO FIT" is a discriminating bucket, not
a blanket state.

### O-3 control — `test_bg_emit.py`

`git blame -L 588,591 tools/test_bg_emit.py` → `40c378afa (2026-09-02 22:16:33)`, unedited for 7
days. Aurora `docs/ROADMAP.md` row 55 read directly (not relayed) → `DELIVERED 2026-09-03`, branch
`feat/ew-band-axis-vertical`, `shiftedPhaseBanks`. **Positive control:** two independent sources
agree (aurora's own ROADMAP, and aeon's `DEFERRED_WORK.md:19022-19030` which strikes the identical
sentence). Controller-verified the DEFERRED_WORK booking directly.

### O-4 control — `test_effects_gen.py` (follow-up pass)

Full command, output and cross-file trace are in the O-4 section above. **Positive control:** the
same absent/cleared-slot detector correctly flags a constructed absent case
(`pwy=[2272]; pm=[{'sweep':{}}, {'sweep':{}}]` → index 1 flagged `absent? True`, index 0 `False`),
so the real-data scan finding zero occurrences on the `boundary` arm and one occurrence (3 bands) on
the `pal_region` arm is a discriminating result, not a search that could never match. The companion
`boundary`-arm statement (2420-2431) and anchor/sweep-arm statement (3813-3816) were run with the
same method and came back CLEAR — no real document uses `boundary` at all, and the one real sweep
document authors its anchor explicitly rather than leaving it absent.

### CLEAR controls (condensed — each was run with its command, output and a positive control)

| Statement | Control | Positive control |
|---|---|---|
| `test_effects_gen.py:2420-2431` | `grep -l '"boundary"' games/sonic4/data/editor/effects/presets/*.json` → no output | The same key IS matched inside `tools/effects_gen.py`'s own `BOUNDARY_KEYS`/`"boundary" in preset` checks, confirming the term is real and searchable |
| `test_effects_gen.py:3813-3816` | Only real sweep doc (`ojz_sec5_showcase.json`) has explicit `patch_world_ys[0] = 2272`, not absent | Same absent-detector flags a synthetic out-of-range sweep as absent (see O-4 control) |
| `test_bg_emit.py:3-9` | Every `s4*.lst` mention resolves to a `tempfile.mkdtemp` tree except one `@needs_build` reader (L2281) | The method surfaced that one genuine reader among ~29 hermetic uses |
| `test_bg_emit.py:191` | `engine/ram.emp:752` still spells `[u16; BGANIM_MAX_BANDS]` | Same substring check against a synthetic literal `[u16; 6]` fails as designed |
| `test_bg_emit.py:579` | The class it heads is 15 tests, 12 referencing `"vertical"` directly | DEFERRED_WORK independently records the same mutation class (up to 9 tests red on one mutation) |
| `test_bg_emit.py:1887` | `build.sh:1213-1215` passes `--rom` on the only gating call | The file's own `test_build_sh_post_sigil_gate_passes_the_rom...` asserts the same fact independently |
| `test_anim_frame_bound.py:22-23` | Both `TestParticle` spawners splice `test_obj_prolog` → `move.l #Map_TestObj, mappings(a0)` | All three `DECLARED_PAIRS` evidence regexes re-run by hand and still match |
| `test_anim_frame_bound.py:24` | `offset_table_frames(map)==offset_table_frames(dplc)` ensure live in 5 data files | `engine/objects/dplc.emp:257` defines the function; the sites instantiate its canonical form |
| `test_bganim_vprobe.py:25-29` | `tools/bganim_vprobe_witness.py` exists, takes `rom_path`/`lst`, checks 256 VRAM bytes byte-for-byte | `ls`-equivalent on a fabricated witness name returns "No such file" — the existence check discriminates |
| `test_deb2_appendix.py:55-56` | `deb2_probe.py --verify` on all 4 shapes → `IDENTICAL` ×4 | `--verify` reproduces the appendix through the real `convsym` pipeline; corruption would print `DIFFERENT` |
| `test_deb2_appendix.py:57-58` | Run with zero ROMs present → conftest prints "4 deferred... These are NOT passes" | Raw pytest says "4 skipped"; the conftest line is what makes it non-green |
| `test_demo_specialization_witness.py:274` | `test_every_pinned_proc_is_a_proc_that_actually_hosts_a_gated_span` PASSED | 17 passed, 1 correctly deferred (`needs_build`) |
| `test_drift_record.py:316-327` | covered == job_shapes == `['demo','demo_debug','s4','s4_debug']`; no NOTE printed | Same logic with a synthetic 5th shape printed the NOTE — the detector fires |
| `test_extern_guard_reachability.py:140-149` | Live 5-shape `sigil build --check` sweep; all 5 tests passed, both seam files + 3 poison files still correctly excused | On an incomplete environment the same check went **red** — proof it can fail |
| `test_lab_index_lint.py:304-305` | `.lab_index` at `$0BEB74` in `s4.debug.lst` (md5 `f71ff626…`, mtime 2026-09-09T09:13:40Z) — even | 79 of 3105 labels in the same listing sit at odd addresses; "even" is not a trivial universal |

**ROM/listing referents used:** `s4.debug.lst` md5 `f71ff626…` mtime 2026-09-09T09:13:40Z (lab_index
control); all four ROM shapes md5-verified against the dispatch values before the `deb2_probe
--verify` control (`s4.bin ed512d731ebd…` etc., all matched).

---

## Totals (auditable)

**Files examined: 13 of 13.** Every file appears in the table above, including the one that turned
out to carry no genuine non-coverage claim.

| | Count |
|---|---|
| Files examined | 13 |
| Files carrying ≥1 genuine non-coverage statement | 12 |
| Files carrying **zero** (`test_gate_fixtures.py`) | 1 |
| **Genuine statements extracted** | **33** (30 original + 3 effects_gen, filled in below) |
| — SPECIFIC-CONSTRUCTIBLE | 22 |
| — GENERAL-LIMIT | 11 |
| **Grep false positives** (matched the population regex but are not non-coverage claims) | **16** (15 original + 1 effects_gen) |
| Verdicts on the 22 SPECIFIC statements: OCCUPIED | 6 statements / **4 distinct findings** |
| — CLEAR | 16 |
| — UNRUN | 0 (one GENERAL-LIMIT, extern_guard H2, carries a full-form UNRUN with a narrow sub-case run CLEAR) |

Per-file statement counts: anchor_sweep_band 4 (+1 fp) · anim_frame_bound 3 (+2 fp) · bg_emit 5 (+7
fp) · bganim_vprobe 1 (+1 fp) · citation_form 2 (+1 fp) · deb2_appendix 4 · demo_specialization
_witness 1 · drift_record 1 (+1 fp) · extern_guard_reachability 5 · freeze_preflight 2 ·
gate_fixtures 0 (+2 fp) · lab_index_lint 2 · **effects_gen 3 (+1 fp) — filled in by the follow-up
pass below; the original commit deferred this file to "a separate lane" whose output never
landed.**

---

## Where this audit contradicts its own brief

Recorded because a brief's facts are the ones the executor cannot doubt from inside.

1. **The brief implies all 13 files carry such a note. `tools/test_gate_fixtures.py` carries
   none.** Both its regex hits are *positive* claims ("No blind spot: every address-shaped operand
   resolved to a name or to self"; "Never render a blind spot as silence"), i.e. the opposite of a
   declared gap. A population built by that grep contains files with zero occupancy risk.
2. **The population grep in `DEFERRED_WORK.md` undercounts.** It matches `does not (cover|catch|
   see)` but not `does NOT check`, `does NOT tell you`, `does NOT gate`. **4 of the 11 genuine
   statements in the deb2/demo/drift/extern group were found only by reading the docstrings
   directly.** The "38 of 100 files" figure in the booking is therefore a **lower bound** on the
   population, and the remaining unaudited files should not be enumerated by that regex alone.
   (This is the repo's own "enumerate by what TOUCHES the value, not by what names it".)
3. **`DEFERRED_WORK.md:30901` says `test_freeze_preflight.py` has 12 tests. It has 13.**
4. **The branch named in the brief did not exist.** `parcel/blindspot-sift-a` was created here from
   `26b1d106`; no such branch was present at dispatch.

## Adjacent findings — not declared gaps, flagged because they are loud

- **`test_extern_guard_reachability.py::test_excusals_are_not_stale` trusts data from a shape whose
  `--check` errored.** It computes `reachable_somewhere` from `_unreachable(checks[shape]["out"])`
  without consulting that shape's `rc`. When three shapes errored early (missing pre-generated debug
  fixtures) their stdout carried no `module.unreachable` warnings, `_unreachable()` returned an empty
  set, and the test failed reporting **all 5 excusals** as newly reachable — a loud failure with a
  wholly wrong stated cause. A reader carrying that reason forward would hunt a seam change that had
  not happened. Compare the freeze_preflight defect this same day: *a gate's verdict and its stated
  reason are separately checkable.*
- **`test_anchor_sweep_band.py:1232-1233`** — "Today this adds nothing over the hand-only test above,
  because the generated population is empty" is stale; the population is 1 today (confirmed by the
  live coverage report). Harmless to correctness, another instance of drifted self-description.

## What THIS audit does not cover

Running the discipline that manufactured the camouflage, so: stated, and controlled where a control
was available.

1. **It never built anything.** Per the brief, `./build.sh` was forbidden. All ROM/listing evidence
   comes from artifacts built 2026-09-09 09:07-09:29Z, md5-verified before use. **A control that
   required a fresh ROM would have been UNRUN, and none was silently downgraded.** *Control on
   myself:* the one place a build mattered (deb2 appendix contents) was reachable through
   `deb2_probe --verify` against the existing shapes, and its md5s matched the dispatch values —
   so this limit did not bite on any statement in this batch.
2. **It never ran the emulator.** Forbidden (deadlocks from background agents). `test_bganim_vprobe`
   delegates its ROM-side claim to `tools/bganim_vprobe_witness.py`, an emulator-driven manual gate.
   **Its existence and contract were verified; whether it currently PASSES was not and could not be
   checked here.** That is TAGGED for foreground follow-up, not a CLEAR.
3. **A GENERAL-LIMIT classification is a judgement, not a measurement.** 11 statements were
   classified as unresolvable-by-control and no control was run on them. If any of those is
   *actually* constructible, this audit reproduces exactly the failure it was sent to find, one
   level up. The extern_guard H2 statement is the honest edge case: classified GENERAL-LIMIT, but a
   narrow constructible sub-case was extracted and run anyway (CLEAR), which is the treatment the
   other 10 did not get.
4. **CLEAR means "not present today", not "cannot occur".** Every CLEAR here is a point measurement
   against this tree at `26b1d106` + the 2026-09-09 artifacts. Three of the findings in this very
   report are notes that were true when written and rotted; a CLEAR verdict has the same half-life.
5. **The four lanes were parallel and I re-verified only the OCCUPIED findings personally.** The 14
   CLEAR verdicts are relayed with their commands and positive controls quoted, but I did not re-run
   all of them. A CLEAR that was reported without actually running its control would look identical
   to one that was — which is precisely the mechanism this audit is about. The positive-control
   requirement is the only thing standing against that, and it is weaker than re-execution.
6. **One lane modified its environment to run a control** (`make -C tools/salvador`, then
   `tools/gen_compression_vectors.py`, to make `sigil build --check` runnable). No `./build.sh`.
   Everything written is gitignored; **`git status --porcelain` was verified empty by the controller
   afterwards** and is empty at the time of this commit.
7. **It audits 13 of the ~38+ files in the population.** No claim is made about the other 25, and
   per contradiction 2 above, the true population is larger than 38.
8. **The `test_effects_gen.py` section (O-4, and its table/control rows) was added in a separate,
   later pass on this same branch, by a session that could not tell whether the original "separate
   lane" had already run and simply failed to land, or had never run at all.** No `SIGIL_BUILD`/
   `SIGIL_EMIT`-dependent control was attempted for this file (none of its three statements needed
   one). This pass did not re-verify any of the other 30 statements above it, GENERAL-LIMIT
   classifications included — it trusts them at face value the same way item 5 above already flags
   as a real, unclosed limit of this report.

## Independent second-pass addendum (separate session, same branch, same dispatch)

A second session was independently dispatched to this same worktree/branch under the identical
brief and, unaware of the above until this point, produced its own full 13-file pass by hand,
converging on the same file path. Rather than overwrite the above (materially more thorough —
4 controller-verified OCCUPIED findings against this session's 1, with the O-2 finding
independently re-derived below before this session read the table above and found it already
there), this addendum records the two places this session's independent work adds something the
above does not carry, and leaves everything else untouched.

**1. Independent confirmation of O-2's mechanism, reached before reading the table above.**
Tracing `OJZ_Preset_Sec5` by hand (`games/sonic4/data/effects/ojz_effects.emp:1611-1654`) found
the SAME contradiction the table's row for lines 84-91/307-321/1397-1403 already documents: an
older in-file comment block (~1611-1628) says section 5's channel 0 "is derived every frame and
read by no one" (a "STRUCTURAL GAP AND NOT A CHOICE"), while the very next preset declaration
(1636-1644, same file, same day, tagged `d-53`) contradicts it directly — `parallax:
ParallaxConfig_OJZ_Underwater` was added specifically "to give channel 0 a CONSUMER" via
`SceneAnchor.At(0, 15, 0)`. Traced one level further than the table above does: `SceneAnchor.At`
reads `Effects_Screen_L[ch]`, which `engine/effects/raster.emp::Effects_LatchWorldLines` computes
for **every** patch channel **unconditionally, every frame** (gated only on `Effects_Motion_Any`,
which section 5 sets since it authors a real sweep) — completely independent of whether a
`patched:` raster program exists for that channel. So the "NO BAND TO FIT" bucket the coverage
report reports for this sweep is accurate for the RASTER band-fit path specifically, but does not
mean the value is inert: it is live input to the waterline row-remap perspective calculation on
whatever section installs `ParallaxConfig_OJZ_Underwater` while channel 0's sweep is active. This
matches O-2's conclusion (an unverified live value) rather than changing it — flagged here only
because the mechanism is worth having spelled out at the RAM-write level (`Effects_LatchWorldLines`
comment block, `engine/effects/raster.emp:2144-2290`) for whoever picks up the "NEEDS AN
INDEPENDENT DERIVATION" open half of O-2, since the current CLEAR/OCCUPIED split in that section
does not name `Effects_LatchWorldLines` as the load-bearing proof that the value is live rather
than merely computed-and-discarded.

**2. A gap in `test_bganim_vprobe.py:25-29`'s CLEAR verdict (row above) and in "what this audit
does not cover" item 2: neither checked whether `tools/bganim_vprobe_witness.py` is actually
invoked by anything automated, only that it exists with the right contract.** It is not:

```
$ grep -n "bganim_vprobe_witness" build.sh
(no output)
$ grep -rl "bganim_vprobe_witness" . --include="*.py" --include="*.sh" --include="*.yml" \
    --include="*.yaml" --include="*.timer" --include="*.service"
tools/test_bganim_vprobe.py
tools/bganim_vprobe_witness.py
```
It is referenced nowhere outside its own file and the file naming it in prose (plus narrative
prose in `docs/DEFERRED_WORK.md:25271,28699` describing one-off manual runs over the headless
Aether bus). Unlike `tools/effects_gates.py` → `demo_specialization_witness.py` (row 274 above,
confirmed by both sessions as a real `subprocess` call, itself scheduled via the enabled
`aeon-effects-gates.timer` — confirmed running, last fired ~90 min before this session's check),
`bganim_vprobe_witness.py` has **no caller anywhere in the tree** — build.sh, CI, or a timer. The
docstring's claim ("that runs after a build with the ROM named on its command line") reads as a
standing guarantee; it describes a tool that is real and correctly shaped but is invoked, today,
only when a person remembers to type the command by hand. This downgrades the existing CLEAR to,
at minimum, a CLEAR-with-caveat: the delegate's *existence* is confirmed, its *execution* is not
automated by anything, and nothing in this tree would notice if it were never run again.

Nothing above was fixed. Both notes are additions to the existing record, not corrections to a
wrong verdict on O-1 through O-4.
