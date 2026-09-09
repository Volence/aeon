# Gate blind-spot sift B (2026-09-09)

Method: `docs/DEFERRED_WORK.md`, "A GATE THAT DOCUMENTS ITS OWN BLIND SPOT IS NOT THEREBY
COVERING IT" (line 30967). The doc's method and this dispatch's method agree; nothing here
contradicts it. Per-statement classification (SPECIFIC-CONSTRUCTIBLE / GENERAL-LIMIT), and
for every SPECIFIC-CONSTRUCTIBLE statement a CONTROL: construct the case the note says it
would miss and check whether it is present in the tree today. Verdicts: OCCUPIED / CLEAR /
UNRUN. A fourth column value, **FALSE POSITIVE**, is used where the grep matched text that
is not actually a claim about *this* gate's own coverage (most often: text explaining why a
*different, weaker* mechanism would miss something that *this* gate's own test then proves
it catches). That is a real finding about the population, not a dodge — the brief asked for
it by name.

No fix was applied anywhere. All 13 files' own test suites were run read-only, with
`PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/tmp/blindspot-b-pyc` and a cleared prefix
directory, to rule out the stale-`__pycache__` false-green trap. No emulator was touched. No
build was run; the four ROM shapes and two listings were read only, and every finding drawn
from one quotes its md5 prefix and mtime, checked against the briefed identity before use
(all six matched exactly — see the table in "Artifact identity" below).

## REVISION NOTE (2026-09-09, post-coordinator review)

Finding #10 (`test_palette_census_lint.py`) as originally filed did not survive
verification: it cited a nonexistent path (`engine/debug/release_fault.emp` — the real
file is `engine/system/release_fault.emp`) and claimed `engine/effects/raster.emp` writes
CRAM "without naming either symbol," which is false of the file as a whole (it names
`Palette_Ship_Snap` four times, in the code that already is the census's row 12). Both
defects trace to the same root cause: **my original population was built by grepping the
literal string `CRAM` and excluding lines containing the two symbol names — enumeration by
NAME, not by the write MECHANISM**, which the census's own declared gap is about. That is
the exact vacuity this audit exists to catch, one level up in my own instrument. Re-derived
below by mechanism (`vdp_comm`/`vdp_comm_reg` targeting `VdpTarget.Cram` — verified as the
tree's only two producers of a CRAM command word). The corrected section replaces the
original #10 entirely; four distinct write mechanisms survive as genuinely OCCUPIED, none
of them raster.emp-as-a-whole or the wrong release_fault.emp path. Finding #9
(`test_overseer_bound.py`) stands unedited, per instruction.

## Totals

- **Files examined: 13/13** (every file in the brief exists and was read; none was empty or missing).
- **Statements extracted: 26** (every grep hit from the booking's own pattern, plus a
  per-file supplementary grep for `does not / cannot / blind / silently / invisible /
  unseen` to catch phrasing the booking's pattern would miss — no statement was found by
  the supplementary grep that the primary pattern had not already surfaced, except where
  noted per-file below).
  - **FALSE POSITIVE: 14** — text that reads like a non-coverage claim but is not one about
    *this* gate's own residual coverage (usually: justifying why a companion check exists,
    with the companion check present and passing in the same file).
  - **GENERAL-LIMIT: 3** — a limit no static control can resolve (delegated to a different,
    already-existing enforcement layer, or an inherently non-source-level property).
  - **SPECIFIC-CONSTRUCTIBLE: 9** — a control was run on every one of these. None returned UNRUN.
    - **CLEAR: 5**
    - **CLEAR but the docstring itself is stale** (the gap was true when written, a
      separate fix closed it hours-to-days later, and the note was never updated): **2**
    - **OCCUPIED: 2 statements** — #9 (`test_overseer_bound.py`, one loud, self-reporting
      deviation) and #10 (`test_palette_census_lint.py`, corrected 2026-09-09 after
      coordinator review: 4 distinct write MECHANISMS survive a mechanism-based
      re-derivation, none of them the file-level `raster.emp` claim or the wrong
      `release_fault.emp` path my first pass filed). Detailed below; neither was fixed.
  - **UNRUN: 0.**

## Artifact identity (verified before use)

| file | md5 (mine) | briefed | match |
|---|---|---|---|
| s4.bin | ed512d731ebd... | ed512d731ebd | yes |
| s4.debug.bin | f2d6fc54ce8e... | f2d6fc54ce8e | yes |
| demo.bin | 08bc93848a6f... | 08bc93848a6f | yes |
| demo.debug.bin | 964caa3eb601... | 964caa3eb601 | yes |
| s4.lst | 266c11a24e2c... | 266c11a24e2c | yes |
| s4.debug.lst | f71ff6265f68... | f71ff6265f68 | yes |

All six matched exactly. `s4.lst` and `s4.debug.lst` were read for two controls below.

## The statement table

| # | file:line | quote (trimmed) | class | verdict | evidence (one line) |
|---|---|---|---|---|---|
| 1 | test_legacy_seam_keys.py:25 | "this is the axis a spelling gate cannot see" | FALSE POSITIVE | n/a | Describes a hypothetical simpler gate; row 7 of *this* file (`test_legacy_seam_values_are_accepted_shapes`) covers axis 2, and it passes. |
| 2 | test_legacy_seam_keys.py:67-69 | "A 65th means a new read MECHANISM appeared and rows 3-4 may be blind to it" | SPECIFIC-CONSTRUCTIBLE | CLEAR | Every non-accessor read in `ControlSocket.cpp` outside the recognised `(*req.p)["key"]` shape (`.value(...)` x2, one `req.p->contains`) lives in `HandleMessage`/`initialize`, which does not take `const JsonObj&` and is categorically outside `_functions()`'s domain; `test_parameter_read_population_is_closed` passes (total==64) against today's source. |
| 3 | test_map_dplc_binding.py:33-35 | "Every guard must say what it does NOT cover... a message that does not say so invites a green build" | FALSE POSITIVE | n/a | This is a requirement THIS file imposes on registry entries (enforced by `test_every_guard_states_what_it_does_not_cover`), not a residual gap of the file itself. |
| 4 | test_map_dplc_binding.py:37-39 | "It cannot tell you a REGISTRY ROW is right: that two blobs really are one asset's pair... nothing here reads [a load site]" | SPECIFIC-CONSTRUCTIBLE | CLEAR | Cross-checked all 6 registry pairs against real load sites (`sonic.emp`, `knuckles.emp`, `tails.emp`, `tails_appendage.emp`, `dust_spindash.emp`, `player_instashield.emp`) — every pair's `Map_X`/`DPLC_X` is genuinely used together at its load site. Proxy, not full proof (file admits this). |
| 5 | test_map_dplc_binding.py:39-40 | "whether today's counts agree is the `.emp` ensure's job... without pytest" | GENERAL-LIMIT | n/a | Delegates to a different, already-present enforcement layer (`ensure()` in the `.emp` itself), not a coverage hole. |
| 6 | test_map_dplc_binding.py:42-43 | "nothing at all about the unbounded frame byte, which no guard in the tree closes" | SPECIFIC-CONSTRUCTIBLE | **CLEAR, but STALE** | This file was committed 2026-09-07 02:26 (`4f998cc9`). LS-9a ("`AnimateSprite` bounds no frame byte") CLOSED the SAME DAY at 08:10-08:44 by `tools/anim_frame_bound.py`, wired into `build.sh --built-after` for both games (DEFERRED_WORK.md line 29760). The docstring here was never updated to say so. |
| 7 | test_ojz_block_gen_cache.py:176 | "The poison the file digest cannot see... Output verification is what catches it" | FALSE POSITIVE | n/a | Describes the file-digest mechanism's limit, which the SAME test (`test_verify_stream_rejects_a_forged_stream`) proves `_verify_stream` catches. Test passes. |
| 8 | test_overseer_bound.py:90 | "A gate that cannot see its subject has not passed, it has not run" | FALSE POSITIVE | n/a | General design remark about a missing-instrument failure mode; not a residual gap — `test_the_boot_read_exists_and_is_measurable` is exactly the guard against it. |
| 9 | test_overseer_bound.py:108-109 | "this gate cannot assert the ruled bound today without failing the build for every lane" | SPECIFIC-CONSTRUCTIBLE | **OCCUPIED (overt, ratified, not hidden)** | See dedicated section below. |
| 10 | test_palette_census_lint.py:24-25 | "WHAT IT CANNOT CATCH: a write that reaches CRAM without naming either symbol (a raw address literal, a pointer handed in from elsewhere, a direct VDP-port write)" | SPECIFIC-CONSTRUCTIBLE | **OCCUPIED (mechanism-verified, corrected 2026-09-09)** | See dedicated, corrected section below — original file-level raster.emp claim WITHDRAWN, release_fault.emp path corrected, population re-derived by write mechanism (`vdp_comm`/`vdp_comm_reg` targeting `Cram`), 4 distinct occupied mechanisms found. |
| 11 | test_raster_cycle_table_lint.py:13-18 | "sigil cannot see (3) at all... Both build GREEN" | FALSE POSITIVE | n/a | Describes sigil's limit; THIS python gate exists to close exactly that gap and is proven red in both pre- and post-relaxation forms (docstring's own red-first log). All 11 tests pass. |
| 12 | test_raster_wire_pin.py:16-18 | "The probe's existing empirical check... does NOT cover it" | FALSE POSITIVE | n/a | Describes `raster_cost_probe.py`'s own weaker `calls`-count check; THIS file's spin-solver pin (pin 1) closes it and passes. |
| 13 | test_raster_wire_pin.py:28 | "arity alone cannot see a transposition" | FALSE POSITIVE | n/a | Rationale for pin 4 (`test_spin_sits_between_command_and_count`), which exists in this file and passes. |
| 14 | test_raster_wire_pin.py:315 | "Arity cannot see a transposition -- swapping SPIN and count-1..." | FALSE POSITIVE | n/a | Same claim, restated inside the poison test itself that covers it (#13's test body). |
| 15 | test_raster_wire_pin.py:422 | "silently, and every dense `calls` check starts failing for a reason no one would look for here" | SPECIFIC-CONSTRUCTIBLE | CLEAR | `engine/effects/raster.emp:1627-1671`: `.dense_end:` still ends `clr.w Raster_Dense_Mode` / `// fall through` directly into `.park:`, with no intervening transfer, today. |
| 16 | test_reels_gate.py:178 | "A plausible-address mutation, which a byte-count check cannot see" | FALSE POSITIVE | n/a | Describes a weaker byte-count check's limit; the file's own PROVEN-RED log shows `reels_gate.py`'s address check catching exactly this mutation. |
| 17 | test_row_remap_ladder_gen.py:15-18 | "It does not pin the emitted image byte for byte" | GENERAL-LIMIT | n/a | Deliberate design choice, explicitly cross-referenced to the companion ROM-level gate `tools/row_remap_gate.py` ("neither subsumes the other"). |
| 18 | test_row_remap_ladder_gen.py:315 | "`entry[i] = i` — they cannot see this — but the pass would write the buffer back unchanged" | FALSE POSITIVE | n/a | Rationale for `test_p6_not_all_identity`, which is the very test in this file that checks it, and passes. |
| 19 | test_s4budget.py (docstring + line 374) | "`RAM: 0KB/64KB (0%)` was a dead parser wearing a measurement's clothes" | SPECIFIC-CONSTRUCTIBLE (KNOWN PRIOR, re-derived) | CLEAR, RE-DERIVED FIRSTHAND | Ran `tools/s4budget.py` against the real, artifact-matching `s4.lst`/`s4.bin` → `RAM: 47.8 KB/64.0 KB (74.6%)`. The prior "measures RAM=0" finding is STALE; this file was rewritten 2026-08-18 specifically to fix it, and the 0% figure it now quotes is a *historical description of the bug it fixed*, not today's behaviour. |
| 20 | test_s4budget.py:663 | "The ceiling arm cannot see that case" | FALSE POSITIVE | n/a | Rationale for the independent `check_budget_cursor` arm, which exists (`resolve_budgets`) and is tested by the same function (`test_the_arms_are_independent_of_the_ceiling_verdict`), which passes. |
| 21 | test_scene_band_shape_coverage.py:23-27 | "empyrean's writer schema still mirrors the OLD ceiling as `layers minItems 1 / maxItems 8`... invisible to it" | SPECIFIC-CONSTRUCTIBLE | **CLEAR, but STALE** | Read `/home/volence/sonic_hacks/empyrean/contract/schema/aurora-effects-scene.schema.json` directly: `layers.maxItems == 16` today, matching aeon's `MAX_PARALLAX_BANDS == 16`. `docs/DEFERRED_WORK.md` (~line 15308) records this closed 2026-08-27 (empyrean `277bc15`, aurora re-vendor `d54d386`) — same day as this test file's last commit (`c85fc877`, 2026-08-27 01:07), so the docstring predates the schema fix by hours and was never updated. |
| 22 | test_scene_band_shape_coverage.py:36 | "That is a gate that cannot see its subject" | FALSE POSITIVE | n/a | Describes why the rejected `.emp ensure` ALTERNATIVE would be vacuous; not a property of the actual Python gate. |
| 23 | test_scene_budget_ledger.py:17-18 | "What this cannot see — sigil ceasing to emit equates to the listing at all — remains `--check`'s job against a DEBUG listing" | SPECIFIC-CONSTRUCTIBLE | CLEAR (today), plus a secondary honest-gap finding | Ran `python3 tools/scene_budget_report.py --lst s4.debug.lst --check` against the real, artifact-matching DEBUG listing: exit 0, every ledger row present. Also confirmed (`grep scene_budget_report build.sh` = no hits) that `--check` is **not wired into any automated lane** — but this is not hidden: `docs/DEFERRED_WORK.md` line 13226 books it by name, dated 2026-08-22, with unlock options and an explicit "run it by hand after any sigil listing-format change" instruction. |
| 24 | test_scene_budget_ledger.py:77 | "SceneBudget_* rows spelled pub const (mints NO symbol — the formatter cannot see it)" | FALSE POSITIVE | n/a | Describes the anti-pattern `test_no_ledger_row_is_pub_const` itself checks for; zero such rows exist today and the test passes. |
| 25 | test_scene_span_labels.py:132 | "§8.2's path-level span gates cannot see any capability-gated block" | FALSE POSITIVE | n/a | Describes the PRE-Task-6 state (before any bracket existed) as a red-first anchor; `test_the_convention_is_in_force_at_all` confirms brackets exist today and passes. |
| 26 | test_scene_span_labels.py:8-21 | "the `.lst` half of the convention lives POST-BUILD, in tools/demo_specialization_witness.py and the span gates in tools/effects_gates.py" | GENERAL-LIMIT | n/a | Architectural split, explicitly named to the two files that own the other half; not a coverage hole in this file. |

## The two OCCUPIED findings, in full

### #9 — test_overseer_bound.py: the boot read is over its ruled bound today

The declared gap: "this gate cannot assert the ruled bound [100,000 B] today without
failing the build for every lane on a question only [the owner] can answer" (line 108-109).

**Control.** Measure `docs/OVERSEER.md` today:

```
$ wc -c docs/OVERSEER.md
114303 docs/OVERSEER.md
```

114,303 > 100,000 (`BOOT_READ_BOUND_BYTES`). **The declared case is present right now.**

**Why this is OCCUPIED but not the sigil archetype.** It is not hidden. Every run of
`test_overseer_md_does_not_grow_while_the_bound_question_is_open` prints, unconditionally,
pass or fail: `ruled bound 100,000 — residual N OVER, owner's card 7`. I ran it:

```
$ pytest tools/test_overseer_bound.py -q   # 6 passed
```

All 6 pass — because the file uses a RATCHET (`RATCHET_BYTES = 114_320`) instead of the
ruled bound, and 114,303 <= 114,320 by exactly 17 bytes of margin. The gap is loud, dated,
attributed to a named open question ("owner's card 7"), and self-documents the exact
mechanism and unlock path. This is the opposite of camouflage — but it is still true, today,
that the file the suite ruled must stay under 100,000 B is 14,303 B over, and the gate that
exists cannot say so as a failure. Left exactly as found, per the no-fix instruction. **17
bytes of ratchet margin remain before the NEXT commit to `docs/OVERSEER.md` goes red for
growth**, which is worth knowing before anyone adds to that file.

### #10 — CORRECTED 2026-09-09 (post-coordinator review). test_palette_census_lint.py

**The coordinator established two defects in my original write-up, verified here firsthand:**

1. **`engine/debug/release_fault.emp` does not exist.**
   ```
   $ git ls-files | grep -i release_fault
   engine/system/release_fault.emp
   ```
   The file lives at `engine/system/release_fault.emp`. My original citation was wrong;
   whatever I was looking at when I wrote it was not that path. Corrected below.

2. **`engine/effects/raster.emp` DOES name both symbols.**
   ```
   $ grep -n "Palette_Buffer\|Palette_Ship_Snap" engine/effects/raster.emp
   205: // Palette_Ship_Snap (this frame's base-DMA payload) back to CRAM.
   243: // cursor (Pal_Variant_Stage / Palette_Ship_Snap), so their write is the absolute-long form
   1466: // with TWO deliberate differences: the source is Palette_Ship_Snap (whose offset
   1467: // IS the CRAM byte address — BuildStaticDMA maps Palette_Buffer+$00/20/40/60 to
   1496: lea Palette_Ship_Snap, a2   // snapshot base (was VDP_CTRL)
   ```
   "raster.emp writes CRAM without naming either symbol" is false of the file as a whole:
   its restore path (`Raster_HInt`'s `.op_pal_restore`, census row 12) is built entirely
   around `Palette_Ship_Snap` and is exactly what the census already registers that file
   for. **The file-level claim is WITHDRAWN.** What survives is narrower: specific write
   sites *inside* raster.emp whose own data does not touch either symbol, found below by
   mechanism rather than by name.

**My own first check was the same defect the audit exists to find, one level up.** I had
grepped the string `CRAM` and filtered out lines containing the two symbol names — that
enumerates by NAME (does this line contain the word "CRAM" / "Palette_Buffer"), not by
MECHANISM (does this line cause a write to reach CRAM's address space). A comment, an
`ensure()`, or a docstring mentioning both words in the same paragraph defeats a
name-based filter in either direction. Redone below.

**THE MECHANISM, named explicitly.** A CRAM-targeted VDP command word can be produced in
exactly two places in this source tree: `vdp_comm(addr, VdpTarget.Cram, op)` (comptime,
folds to a literal longword) and `vdp_comm_reg(reg, VdpTarget.Cram, op)` (runtime, encodes
into a register). This is not an assumption — `target_bits(VdpTarget.Cram)` (the function
that turns the `Cram` enum case into its bit pattern) has exactly two non-ensure call sites
in the whole tree, both inside `engine/vdp.emp` itself:

```
$ grep -rn "target_bits(" --include="*.emp" engine games
engine/vdp.emp:134:comptime fn target_bits(t: VdpTarget) -> int {
engine/vdp.emp:151-153:  (three ensure()s pinning target_bits against engine.constants — not writes)
engine/vdp.emp:162:    let type = target_bits(target)      // inside vdp_comm
engine/vdp.emp:194:    let tr = target_bits(target) & op_bits(op)   // inside vdp_comm_reg
```

So the population is: every call to `vdp_comm(..., VdpTarget.Cram, ...)` or
`vdp_comm_reg(..., VdpTarget.Cram, ...)` anywhere in `engine/` or `games/`, MINUS the ones
inside an `ensure(...)` (a comptime proof about a value, not a write), PLUS every caller of
the raster DSL's shared encoder (`op_words` in `raster_dsl.emp`, which every `stream_cram`/
`stream_pal_region`/`pal_restore`/`raster_gradient_program`/`raster_ramp_program` call
funnels through) traced back to where its colour/address DATA actually comes from, because
`op_words` itself is the mechanism, not a site.

```
$ grep -rn "vdp_comm(.*Cram\|vdp_comm_reg(.*Cram\|VdpTarget\.Cram" --include="*.emp" engine games
```
(full output: 22 hits — 3 ensures in vdp.emp already excluded above, 2 more ensures in
raster.emp:554/805 that prove an already-built `cmd` IS a CRAM-write command rather than
performing a write, 6 inside raster_dsl.emp's `op_words` — the shared encoder, not a site
— and the following ACTUAL WRITE SITES:)

| site | reaches CRAM | names either symbol | verdict |
|---|---|---|---|
| `buffers.emp:115,122,129,136` (`BuildStaticDMA`, `SRC_PAL_LINE0..3`) | yes — DMA setup | **yes** — source is `extern("Palette_Buffer")` (line 18-21 of the file) | not occupied — census row 10 |
| `raster.emp` `.op_pal_restore` handler (~1466-1496) | yes — HInt-time CRAM stream | **yes** — `lea Palette_Ship_Snap, a2` at line 1496 | not occupied — census row 12 |
| `games/sonic4/data/effects/ojz_effects.emp`: `stream_cram(OJZ_TEST_CRAM_ADDR, [OJZ_BAND_SHADE])` and siblings (`OJZ_BAND_LIT`, `OJZ_BAND_SUN`, the water-gradient bands) | yes — dispatched every active frame by `Raster_HInt`'s OP_CRAM in the shipped OJZ act | **no** — `OJZ_BAND_SHADE`/`_LIT`/`_SUN` (ojz_effects.emp:357-359) are plain literal colour constants (`$0224` etc.), never derived from either symbol | **OCCUPIED** |
| `games/sonic4/data/effects/ojz_effects.emp:1012` `OJZ_TestGradient = raster_gradient_program(..., cmd: vdp_comm(OJZ_GRAD_CRAM_ADDR, Cram, Write), stream: OJZ_GradientStream, ...)` | yes — dense CRAM stream | **no** — `OJZ_GradientStream` (line 1002) is `comptime for i in 0..288 { grad_word(i) }`, a computed literal ramp, not either symbol | **OCCUPIED** |
| `engine/effects/raster_dsl.emp` `stream_pal_region(addr, slot, pal_line, entry, count)`, called live from `games/sonic4/data/generated/ojz/act1/effects_scenes.emp:248,253-255` (real authored bands, not a poison fixture) | yes — HInt-time CRAM stream | **no** — sources `Pal_Variant_Stage` (a distinct 256-byte RAM buffer, `engine/ram.emp:737`), which `SYMBOL_RE` in the lint does not match | **OCCUPIED** |
| `engine/effects/raster.emp:1882-1900` `Raster_BuildShipEntry` (`a1: u32`), called from `Raster_InstallPatched` — core engine, not gated behind DEBUG or under `test/poison/` | yes — builds a real DMA-queue entry, dest via `vdp_comm_reg(d2, VdpTarget.Cram, VdpOp.Dma)` | **no** — source is `Pal_Variant_Stage`, dest label `Static_Pal_Ship`; neither census symbol appears in the proc | **OCCUPIED** |
| `engine/system/boot_data.emp:111` `CRAM_WRITE_CMD = vdp_comm(0, Cram, Write)`, consumed in `engine/system/boot.emp:216-219` (`move.l d0,(a3)` x64, zero-fill) | yes — 128-byte CRAM clear, every boot | **no** | **OCCUPIED** (survives — matches the coordinator's own note) |
| `engine/system/release_fault.emp:73-74` — corrected path — `move.l #vdp_comm(0, Cram, Write), VDP_CTRL` then `move.w #$000E, VDP_DATA` inside `pub proc ReleaseFault () @noreturn` | yes — writes literal red ($000E) to CRAM[0] | **no** | **OCCUPIED** — fires only after a fault, `@noreturn`, the frame loop has already halted permanently |

**Four genuinely OCCUPIED write mechanisms survive the mechanism-based re-derivation**
(the OJZ literal-colour bands and gradient count as one class since both are
`stream_cram`-family literal data; `stream_pal_region`; `Raster_BuildShipEntry`; boot's
CRAM clear; the fault screen). All are real production code, not poison or test-only
fixtures — `effects_scenes.emp`'s `stream_pal_region` calls are live generated content in
the shipped OJZ act, confirmed by grep (defined AND called, not merely defined).

**What "OCCUPIED" means here, precisely, and what it does not.** Per the coordinator's
question: yes to "does the write reach CRAM" and no to "does it name either symbol" for
all listed survivors — so by the stated two-question test, the census's declared gap IS
occupied at these sites. What I have NOT done, and am not claiming: proven any of these
constitutes a live INVARIANT VIOLATION. The two OJZ raster-band mechanisms write colours
the base-DMA invariant was never about — `palette.emp` documents that `Raster_VBlank`
re-asserts the program's own dirty mask every frame specifically so a raster tint does not
need to route through `Palette_Buffer` to be safe — and boot/fault-time writes happen
outside the running frame loop the invariant describes. `Raster_BuildShipEntry` and
`stream_pal_region`'s `Pal_Variant_Stage` path is the one I would flag as most worth a
second look: it is a second, parallel DMA-to-CRAM path for the SAME palette lines (1-3)
the census tracks, active during normal gameplay, and neither
`test_palette_census_lint.py` nor its `.emp ensure` cross-references it. I have not traced
whether it can race the base-DMA snapshot; that would need either a control-flow proof
against `Palette_Ship_Snap`'s consumer or an emulator run, and the latter is barred here.
**Tagged for foreground follow-up on that one path specifically** — not the broad,
name-based "several things touch CRAM" claim I filed originally, which the coordinator was
right to send back.

## What this audit does not cover (my own blind spots, named)

- **I read most of each file but not literally every line of the two 1000-line files**
  (`test_legacy_seam_keys.py` at 1008 lines, `test_s4budget.py` at 674) beyond the targeted
  grep hits and their surrounding context. A non-coverage statement phrased with neither the
  booking's grep vocabulary nor my supplementary greps' vocabulary (`does not/cannot/blind/
  silently/invisible/unseen`) would not have surfaced. Running the control on myself: I
  re-grepped every file for `overlook|escape|slip|miss(es)?\b|goes? unchecked|not verif`
  after drafting this table. Actual output: mostly code (`re.escape`, `test_..._escapes_...`
  function names, `stats["memo_misses"]` dict keys). One new hit,
  `test_scene_span_labels.py:112` ("A partial list here would let the next promotion slip
  through unchecked"), is a rationale for why THIS test's own reserved-bit list must be
  exhaustive — it asserts the list already IS exhaustive ("All four are listed, not a
  sample"), so it is the same FALSE POSITIVE shape as the rest of this file's population,
  not a new residual gap. No additional genuine non-coverage claim was found.
- **The `.emp`-source `ensure()` half of several files' invariants (e.g. the frame-count
  binding in `test_map_dplc_binding.py`, item #5 above) was not independently re-run**; I
  trusted that these fire at sigil build time based on the docstrings and the DEFERRED_WORK
  cross-references, rather than building the tree myself (which is barred).
- **The palette-census control (#10) is evidence, not proof.** I did not trace
  `Raster_HInt`/`Palette_Ship_Snap` timing to confirm the reconciliation is actually
  sufficient in every case; I found only that the census's own docstring doesn't mention
  the other gates that plausibly cover it. That is a documentation-completeness finding,
  not a verified-safe or verified-broken finding, and I have labeled it that way rather than
  rounding it in either direction.
- **I did not run the wider `pytest tools/` sweep** (all ~100 files), only the 13 files' own
  suites plus the two artifact-reading commands (`s4budget.py`, `scene_budget_report.py
  --check`) named in this report. A regression in a file outside the 13 is out of scope by
  the brief and out of scope here.
- **Two "CLEAR, but STALE" findings (#6, #21) are docstring-staleness, not gate-behaviour
  findings** — the underlying defect classes are closed by OTHER tools (`anim_frame_bound.py`,
  the empyrean schema edit) that these two files' own text does not know about. I did not
  edit either docstring, per the no-fix instruction, but flag both as a cheap, low-risk
  documentation fix if you want it done.

## Totals, restated for the audit trail

- 13/13 files examined, all existed, none empty.
- 26 statements extracted.
- Classification: 14 FALSE POSITIVE, 3 GENERAL-LIMIT, 9 SPECIFIC-CONSTRUCTIBLE.
- Verdicts on the 9 SPECIFIC-CONSTRUCTIBLE: 5 CLEAR, 2 CLEAR-BUT-STALE-DOCSTRING, 2 OCCUPIED
  statements, 0 UNRUN. #10's OCCUPIED verdict was corrected 2026-09-09 after coordinator
  review (see the REVISION NOTE and the corrected #10 section): the original file-level
  `raster.emp` claim and the `engine/debug/release_fault.emp` path were both wrong — my
  first-pass population was name-based (grep `CRAM`, exclude the two symbol names), the
  same defect class this audit exists to find. Re-derived by write MECHANISM
  (`vdp_comm`/`vdp_comm_reg` targeting `VdpTarget.Cram`, the tree's only two producers of a
  CRAM command word, confirmed exhaustive by `target_bits`'s call-site closure): 4 distinct
  occupied write mechanisms survive, each cited by exact site and traced one hop back to its
  source data. Neither statement was fixed, per the audit's own rule.
- Every one of the 13 files' own pytest suites was run and is green today (pyc cache cleared,
  `PYTHONDONTWRITEBYTECODE=1`): test_legacy_seam_keys.py 8 passed, test_map_dplc_binding.py
  10 passed, test_ojz_block_gen_cache.py 25 passed, test_overseer_bound.py 6 passed,
  test_palette_census_lint.py 6 passed, test_raster_cycle_table_lint.py 11 passed,
  test_raster_wire_pin.py 45 passed, test_reels_gate.py 22 passed,
  test_row_remap_ladder_gen.py 41 passed, test_s4budget.py 52 passed,
  test_scene_band_shape_coverage.py 10 passed, test_scene_budget_ledger.py 7 passed,
  test_scene_span_labels.py 11 passed.
