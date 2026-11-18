# LOOPS-P from aeon's side, and whether the section-0 alignment pin survives regions

> **⚠ CORRECTED 2026-11-17 (pre-land review). Read this before the body.**
> 1. **The mark counts in "A real loop, in the shipped ROM" are wrong at `deb52a95`.** They were copied from stale comments, not derived. Decoding `section_0.collattr{,b}.bin` at that commit gives **16 marks** (8 `XOVER_TO_B` on plane A, 8 `XOVER_TO_A` on plane B): two four-cell bars at column 143, rows 52-55 and 68-71. They make **three** distinct marked words (`$8000`, `$949A`, `$4000`), so three `CrossoverTable` slots, not two. `DEFERRED_WORK.md` (LOOP SPRITE PRIORITY SWAP, item 4) reached the same figures independently.
> 2. **The prediction that the pin "breaks for certain" in §3.3's tools parcel was wrong.** That parcel landed (`e2af59ea`, zero bytes moved). `binding_region("sec0")` spells `EditorSceneBinding_OJZ_Act1_Sec0`, and sigil's row still matches. The trap is still live: unbinding region `sec0` would move the head label.
> 3. **The inverted order was not itself the defect.** Parcel 2's derive reads `Sst.layer`, Parcel 3's output, so Parcel 3 had to come first. What was missing was a record of the departure.
> 4. **Superseded:** Parcel 2 shipped 2026-09-10. LINES-EVERYWHERE (2026-09-26) retired the painted marks, `Player_LoopCrossover` and `loop_crossover_gate.py`, and PATH-SWAP-DELETE (`e1a050e5`) removed `path_swap.emp`. Rows L-1 to L-6 are closed or moot. L-7 (GATE-VACUITY closure) and the `test_effects_gen.py` section-0 blind spot are still open.

**Read at:** aeon `deb52a95` (`origin/master`), in a clean worktree on branch
`recon/loops-p-and-section0-order`. **Research only** — nothing built, no emulator touched,
no engine or tool file changed by this pass.

> **Tree note, because it changes what "master" means for anyone reading this.** The
> checkout's local `master` was at `60846831`, **7 commits BEHIND `origin/master`**, and
> `docs/DEFERRED_WORK.md` differs by +69 lines across that gap. Everything below is read at
> `deb52a95`, the tip the hub named. A claim checked against the local `master` alone would
> have been checked against a different document.

---

## Q1 — LOOPS-P is NOT done from aeon's side. Eight rows are owed.

**The headline, stated so it can be refuted:** the project's three named parcels are
**two-of-three built**. Parcel 1 (the tilt) and Parcel 3 (Route P, the painted crossover)
both shipped and are gated. **Parcel 2 — the sprite priority swap — is not built in either
of the two mechanisms that could carry it**, and the anchor document says in as many words
that Parcel 3 was supposed to sequence *after* it. That sequencing has been inverted in
practice and nothing records the inversion.

The hub's "then a real one" is **satisfied**: a real loop is drawn in OJZ act 1 section 0,
is in the shipped ROM, and a player has been driven round it. The hub's "build-time check"
is **satisfied in the half that was ever going to be built** and **deliberately declined in
the other half**, with the argument written down — see the receipts below. Neither of those
is what keeps the project open.

### Board rows still owed to LOOPS-P, aeon-side

| # | Row (board title) | Size | Evidence it is open |
|---|---|---|---|
| L-1 | **The sprite priority swap is unbuilt, and the crossover that was meant to follow it shipped first** | M | `games/sonic4/objects/path_swap.emp:39`; `player_common.emp:1132`; anchor §6 |
| L-2 | **`loop_crossover_gate.py`'s header still asserts "no loop geometry in OJZ act 1" — there is** | S | `tools/loop_crossover_gate.py:13-19` |
| L-3 | **[TAG-RUNTIME] "an air cell with a non-zero attr is invisible to every sensor" is still read, never executed** | S | anchor §11; DEFERRED_WORK "Air-cell crossover marks — HALF MEASURED" |
| L-4 | **[TAG-RUNTIME] `path_swap.emp`'s despawn/re-arm has never been tested on a real loop — and now there is one** | S | anchor §11 |
| L-5 | **The per-act "this act has crossovers" flag: its own revisit trigger has fired** | M | DEFERRED_WORK ~3437 |
| L-6 | **`docs/loop-arc-cells-section0.json` recommends a mark placement the shipped paint contradicts** | S | anchor §12; DEFERRED_WORK ~26105 |
| L-7 | **GATE-VACUITY is booked as future work that a later ruling declined to build; no closure row says so** | S | DEFERRED_WORK:16835 vs anchor §8.2 |
| L-8 | **The DPLC re-page debt Parcel 1 was told to ledger separately** | M | research §6; owner decision `d-47-revised` |

### The receipts for what IS done

Verified firsthand at `deb52a95` unless marked relayed.

**Parcel 1 — the tilt (Option A).** Shipped 2026-08-28 on `parcel/sprite-tilt`.
`Player_ApplyTilt` in `games/sonic4/player/player_common.emp`, called from `Player_Display`
between `AnimateSprite` and `Player_LoadArt`; **zero engine changes**. The research doc's own
header block records the measurement that superseded its estimate — *"110 bytes of routine
plus 2 at the call site; **+132 B** total ROM in both sonic4 shapes"* against a predicted
"~40-60". Graded by `tools/sprite_tilt_gate.py`, invoked from `build.sh:1298`.

**Parcel 3 bake half.** `parcel/loop-crossover`, aeon `8a4313b5` (2026-09-02).
`tools/collision_pipeline.py:294` — `bake_plane_cell` reads
`xover = (cell_word >> XOVER_SHIFT) & XOVER_MASK` and interns it; `emit_tables` emits
`crossover.bin`; `collision_data.emp:17` embeds it and `:129` publishes `CrossoverTable`.
Rule R1 is a **refusal**, not a report: `XOVER == 3` raises a `ValueError`.

**Parcel 3 read half.** `parcel/loop-crossover-read`, aeon `602170f7`.
`Player_LoopCrossover` at `games/sonic4/player/player_common.emp:1132`.

**The step-over defect, found by driving a real player and fixed.** Merge `4df9bebf`
(2026-09-05). Above ~8 px/frame the one-cell mark was invisible; the read now sweeps from the
previous cell to the resolved one. Graded at all three speeds against a control ROM built
from the pre-fix engine, with `$600` (6 px/frame) as the **negative control** — 6 px cannot
straddle an 8 px cell, so the fix must be a no-op there, and is.

**A real loop, in the shipped ROM.** Section 0, column 143, four painted marks (two cells,
each marked `XOVER_TO_B` on plane A and `XOVER_TO_A` on plane B). The `Player_LoopCrossover`
cost comment states it as a fact about the build: *"the shipped `CrossoverTable` now holds
TWO marked slots (the section-0 loop)"*. Driven at `PHYS_TOP_SPEED`: **15 distinct angles,
123 px climbed, both marks fired, both halves traversed on their own plane** (relayed — that
is a 2026-09-04 emulator measurement recorded in `DEFERRED_WORK.md`, not re-run here).

**The build-time check, and this is the part most likely to be misread.** There were two
candidate build-time checks and they had different fates.

* **The encoding rules R1-R6 — BUILT.** Pinned in `tools/test_collision_consistency.py`, each
  with the converse control the anchor's §8.1 demands, plus the ROM-executing
  `tools/loop_crossover_gate.py` and the player-driving `tools/loop_step_over_witness.py`.
* **The reachability assertion — DECLINED, with an argument.** The research doc proposed
  *"every cell where plane A and plane B differ is reachable from a transition"*.
  `docs/LOOP_CROSSOVER_ENCODING.md` §8.2 refuses it on two independent grounds, quoted:
  *"it would fail today on content that is perfectly fine"* (section 0 has 736 cells solid on
  A only and 44 on B only, divergent with no crossover, because plane B is partial authoring
  rather than a loop) and *"the bake cannot decide it"* — reachability needs a traversal
  model and *"a fitted number in a build gate is worse than no gate"*.

**So do not book "the build-time check" as owed.** What is owed is L-7: `GATE-VACUITY`
(DEFERRED_WORK:16835, booked 2026-08-28 on aurora's finding) still reads as live work
*"binding on whoever builds it"*, and the later §8.2 ruling that declines to build it has no
closure row pointing back. That is a documentation row, not an engineering one.

### The rows in detail

**L-1 — the priority swap, and the inverted sequencing.** This is the substantive one.

Research §6 named three parcels; §4.3 calls the missing one *"Gap 1"* and is emphatic that
without it *"a loop reads as a flat painted circle"*. Two mechanisms could carry it and
**neither does**:

* `games/sonic4/objects/path_swap.emp:39` — `const PATHSWAP_BIT_PRIO = 5 // subtype:
  reserved (priority swap)`. Not merely unused: `PathSwap_Init` carries a DEBUG guard that
  `raise_error "PathSwap: reserved subtype bit PATHSWAP_BIT_PRIO (5) set but unimplemented"`.
  The constant exists; the behaviour does not, and the code says so.
* `Player_LoopCrossover` — its own header states the write set: *"this routine writes only
  `Sst.layer` and the two `PlayerBlock` cell fields"*. I grepped `games/` and `engine/` for
  any site that derives an `art_tile` priority bit from `Sst.layer`: **none**.

The anchor's recommended resolution is on record and unexecuted —
`docs/LOOP_CROSSOVER_ENCODING.md` (~:620): *"ship the 2-bit layer field, derive priority from
the layer at the engine read site"*. The 2-bit field shipped. The derive did not.

**And the sequencing was inverted without a record.** `LOOP_CROSSOVER_ENCODING.md:384` says
*"This parcel sequences **after** the sprite priority swap (`loops-and-sprite-rotation.md`
§6, Parcel 2)."* Parcel 3 landed 2026-09-02; Parcel 2 has not landed at all. Nothing in
either document notes that the stated order was not followed. I flag this as the finding
rather than the byte count: **a loop that rides correctly and renders flat will read to the
owner as "the loop doesn't work", and the row that explains why is not on any board.**

**L-2 — the gate header, still stale at `deb52a95`.** Booked 2026-09-06. I re-read
`tools/loop_crossover_gate.py:13-19` in this tree and **both premises are still present and
still false**: *"every cell of every shipped act holds XOVER_NONE (anchor §2.1: all 18 plane
files, all 65,536 cells each)"* and *"there is no loop geometry anywhere in OJZ act 1 (anchor
§0)"*. The booking is careful about why this matters and I agree with its reasoning: the gate
itself is unaffected (it executes ROM bytes), but the sentence **argues against a
content-side gate**, so leaving it standing suppresses the check the content has now made
non-vacuous. The booking's own instruction is binding and worth repeating on the board row:
**re-derive the count at the moment of the fix; do not re-type today's figure**, because a
fresh literal goes stale on the identical clock.

**L-5 — the per-act flag's trigger has fired.** DEFERRED_WORK (~3437) books it *"DELIBERATELY
LEFT OPEN"* and sets its own revisit condition: *"Revisit when the first real loop lands,
which is also when the cost starts buying something."* **The first real loop has landed.**
The stated reason for not building it — *"adding one here would ship a second encoding ahead
of its first user"* — is spent. Cost figure to re-derive rather than copy: the booking says
~1.24% of an NTSC frame for two players on a frame where both changed cell, re-derived
2026-09-05 by `tools/loop_crossover_cost.py`; that tool re-sums from the emitted encodings,
so run it rather than quoting the number.

### What is NOT aeon's, and should not hold LOOPS-P open

Listing these explicitly because they are the loudest loop rows in the record and a reader
sweeping for "loop" will hit them first.

* **The left-arc foot repaint.** The owner reported *"with the loop, with collision on the
  one side, I can't get past it if coming from the left"*. Root cause measured: plane A rows
  68-71, cols 132-135 are all `sol=3` (side faces) because *"the left arc's cells are the
  PRE-EXISTING ones swapped B→A during the half swap"*. **Fix is aurora's paint.**
* **The rightward-exit third mark.** A completing rightward circuit crosses the centre mark a
  third time and exits on the wrong plane; the routine's own comment states that entry and
  exit *"need opposite answers from inputs that are identical, so no rule keyed on position,
  plane and direction alone can separate them"* and that the fix is *"a PAINT change and
  belongs to the collision lane, not here"*. **Correctly reported and stopped at.**
* **The run-up.** ~55 px of flat approach because a pre-existing foliage column walls it.
  **Owner's call, aurora's card.**
* **Owner decisions** research §7 items 1, 2, 5, 6, 7, and the §11 "keep or delete
  `path_swap.emp`" question.

⚠ **One instrument limit, stated rather than papered over.** I tried to read owner rulings
out of `docs/decisions.jsonl` and **could not** — the rows carry the question and the options
but no ruling field I could find, so my scan returned "no ruling" for every row including
ones I know were ruled (decision 4 was ruled *painted*, recorded in prose in
`LOOP_CROSSOVER_ENCODING.md` §11: *"The owner ruled painted"*). **Do not read my table above
as evidence that any owner decision is unruled.** Rulings in this repo live in prose.

### One unresolved observation, recorded as unresolved

The post-sweep `$900` run *"still ends with a 413 px drop after correctly riding the loop
(x 1589, y 970 at 200 frames). Pit, end of the streamed window, or a second defect —
unestablished, and recorded as unestablished."* The record later names the left-arc wall as a
**candidate** explanation and explicitly declines to assume it. I am not resolving it here
either; it needs a run, so it is **TAGGED** for the controller.

---

## Q2 — the alignment pin: what it actually is, and what step 4 does to it

### The booking, quoted from source

`docs/DEFERRED_WORK.md`, added by `533b76f3` (2026-09-09), heading **"SECTION 0 IS A SPECIAL
CASE THAT ORDINARY EDITS CANNOT SURVIVE — THREE MECHANISMS, ONE SHAPE"**. First correction to
what was relayed to me: **the booking has three mechanisms, not two.** Item 1 is the one aeon
owns and it reads, in full:

> 1. **An alignment row is pinned to section 0 being the FIRST binding.** Unbinding its scene
>    — an ordinary editor action, and one aurora correctly advised — makes the head label
>    `..._Sec4`, and `sigil_harness::section_align::DECLARED` names `..._Sec0`, so the link
>    refuses with `[layout.undeclared-alignment]`. **Our own comment at
>    `tools/effects_gen.py:4101` already documents this trap**, which means we knew and did
>    not guard it.

### The pin, named in source

**It is not in aeon.** It is a literal string in a table in the sigil repo. Read firsthand,
cross-repo, at `/home/volence/sonic_hacks/sigil/crates/sigil-harness/src/section_align.rs`:

* `:51` — the doc banner **"── THE KEY IS THE HEAD LABEL ──"**.
* `:61` — the field: *"The section's HEAD LABEL — its lowest-offset label, the spelling a
  `map.toml` …"*.
* `:228` — the row itself, and this is the pin:

  ```rust
  d("EditorSceneBinding_OJZ_Act1_Sec0", 2, WORD), // ojz_effects_editor_act1
  ```

The aeon side of the pair, all verified in this tree:

* `games/sonic4/data/generated/ojz/act1/effects_scenes.emp:166` — the first **byte-emitting**
  declaration in the module is `pub data EditorSceneBinding_OJZ_Act1_Sec0`. The four
  preceding `pub const Scene_Editor_*` and `EditorScenes_OJZ_Act1` emit no bytes.
* `:166-169` — the bound sections today are **0, 4, 7, 8**.
* `tools/effects_gen.py:4085-4092` — the emission order: an optional act-default binding, then
  `for i in sorted(bound)`. No `EditorSceneBinding_OJZ_Act1_Default` appears in the artifact,
  so no act-default binding is emitted; the head is therefore `binding_sec(min(bound))`.
* `tools/effects_gen.py:3637` — `binding_sec(i)` returns
  `f"EditorSceneBinding_{zone}_{act}_Sec{i}"`. **The section index is inside the symbol name.**

So the booking's mechanism reproduces exactly: unbind section 0, `min(bound)` becomes 4, the
head label becomes `EditorSceneBinding_OJZ_Act1_Sec4`, and sigil's literal does not match.

**And aeon's own placement row is deliberately NOT the pin.** `games/sonic4/map.toml:127`
uses `"section:ojz_effects_editor_act1"`, and the comment above it says why:

> The row is keyed by SECTION NAME … because this block's head label is CONTENT-DERIVED —
> whatever the generator emits first … **A label row here would rot with content; the name
> row does not.**

That is worth flagging to the hub on its own: **aeon already identified this exact rot and
immunised its own row against it. The surviving exposure is entirely the peer repo's
label-keyed table.**

### Does it depend on section 0, on whatever is first, or on neither?

**On none of the three as posed. It depends on a fourth thing: the SPELLING of the module's
lowest-offset label, matched as a literal string.** Both halves of that matter and the
booking's phrasing collapses them:

* **Ordering** decides *which* declaration is lowest — `sorted(bound)`, so the lowest bound
  section index.
* **Naming** decides *what that declaration is called* — and `binding_sec(i)` puts the
  section index in the name.

The pin breaks if **either** changes. Aurora's argument ("that is a statement about ORDER,
not scope, and nothing anyone has measured says regions delete a pin to a first entry") is
answering only the ordering half. It is correct about the ordering half and it does not reach
the naming half, which is the half that section identity lives in.

**A third property, and it is the one that makes the row worth keeping open regardless of
regions:** the pin is sensitive to **authoring**, not to code. No engineer has to change
anything for it to break. The owner unbinding a scene in Aurora — which is what happened —
moves a symbol name in a generated file and refuses the link in a different repo. That is not
an order property or a scope property; it is a **content-derived identifier crossing a repo
boundary as a literal**.

### So: does it survive REGIONS-V1-CORE step 4?

**Yes — step 4 as designed does not touch it. But the reprieve is narrower than it looks and
it does not extend to the parcel that follows.** The argument, so it can be checked:

**1. Step 4's own file list does not include the generator or its output.** From
`docs/superpowers/designs/2026-09-09-regions-v1-design.md` "Step 4 — delete the section
identity fields", the enumerated edits are `engine/structs.emp`, `engine/level/section.emp`,
`engine/level/tile_cache.emp`, `games/sonic4/data/levels/ojz/act1/act_descriptor.emp`,
`tools/boot_override_gate.py`, `tools/preset_lab_witness.py`, `tools/parallax_crossing_gate.py`,
and `docs/ENGINE_ARCHITECTURE.md`. **`tools/effects_gen.py` and
`data/generated/ojz/act1/effects_scenes.emp` are not among them.**

**2. What step 4 deletes is two `Sec` struct fields, not section identity in the generator.**
It deletes `Sec.sec_parallax_config` and `Sec.sec_effects` and re-pins
`sizeof(Sec) == 34` → `== 26`. The generator emits from the **editor's saved scene sidecars**,
not from `Sec`. Step 4 changes nothing about which sections have bound scenes, so `sorted(bound)`
is unchanged and `binding_sec(0)` is still emitted first.

**3. The one thing step 4 does remove is the binding symbols' only structural consumer — and
that cannot move a head label.** `act_descriptor.emp:229` is
`sec_parallax_config: ojz_act1_sec_scene(sec: sec)`, and it is the only caller of the
comptime chooser. Step 4 drops it. But `ojz_act1_sec_scene` is a `comptime fn` — it emits no
bytes and holds no address — while `EditorSceneBinding_OJZ_Act1_Sec0` is a `pub data` in the
module body. Losing a comptime caller does not unemit a `pub data`.

**4. The module stays reachable, so it cannot silently vanish.** I enumerated its importers:
`games/sonic4/data/effects/ojz_effects.emp` (three separate `use` lines — the raster/cycle/
variant/patch choosers, `EditorReelBindings_OJZ_Act1`, and `Scene_Editor_ojz_act1_depth`),
`games/sonic4/test/ojz_scroll_test.emp`, and `act_descriptor.emp`. Step 4 removes one `use` of
one symbol from the last of these. **This mattered enough to check**: an unreachable `.emp`
module is a known way for declarations to stop existing, which would have been a different
and much quieter failure than a refused link.

**5. Where it DOES break is §3.3, and that is a different parcel.** The design's "What the
tools side has to become" says: *"Mode by file presence … `regions.json` present → region
mode, and a sidecar carrying a non-null `sceneRef` is **refused, never merged**."* When that
lands, the per-section sidecars stop producing `binding_sec(i)` declarations, the generator
emits *a table* instead, and **the head label moves for certain**. §3.3 also says this is
explicitly out of scope: *"Not planned in detail here — it is a tools parcel with its own
lane and its own repo boundaries."*

**So the correct board answer is: the pin survives step 4 and is scheduled to break in the
tools parcel of §3.3.** Treating it as a step-4 risk mislocates it by one parcel; treating
aurora's "nothing says regions delete it" as a closure mislocates it by a whole mechanism.
The fix is one line in the peer repo either way, and it is cheap **whenever it is done on
purpose** — it is expensive only when an author trips it, because the error surfaces as a
link refusal in a repo the author never opened.

### The booking's own wording, judged

Asked to say plainly if it is inaccurate about its own mechanism: **it is accurate in every
checkable particular and misleading in its emphasis.**

* Accurate: the `..._Sec4` head label, the `DECLARED` naming `..._Sec0`, the
  `[layout.undeclared-alignment]` refusal, and the `effects_gen.py:4101` comment. I checked
  all four; `:4101` is the line *"is the key `sigil_harness::section_align::DECLARED` matches
  on"*, mid-sentence in the block at `:4093-4110`, so the citation is to the right block.
* Misleading: **"pinned to section 0 being the FIRST binding"** reads as a claim about
  ordering, which is what invited aurora's ordering-only rebuttal. The pin is to a
  **label string** that happens to encode both the ordering and the identity. Recommend the
  row be re-worded to *"a peer-repo alignment row matches a literal head-label string that
  encodes which section is bound lowest"*.
* One more thing the booking gets right and is worth not losing: *"which means we knew and
  did not guard it."* That is exactly right, and see the next section for how the guard that
  exists fails to be one.

### ⚠ A finding neither lane has booked: the guard that exists cannot see this case

`tools/test_effects_gen.py:1140`, class
`TestTheHeadLabelIsABindingAndNeverAPayloadName`, is the aeon-side guard on the head label.
Three tests. Its expectation is **derived, not copied** — `self.assertEqual(head,
names.binding_sec(0))` asks the same `ActNames` the generator uses, and its own docstring says
so, which is good practice and works: a rename of the binding scheme moves the test with it.

**But all three tests call `self.write_sidecar(0, {"sceneRef": "shimmer"})`.** The fixture
**always binds section 0**. So the suite is structurally incapable of producing the failure
the booking is about — section 0 becoming unbound. What it actually grades is the
deform-table ordering defect of 2026-09-05 (that a payload label cannot lead the section),
which it grades well and with a stated control.

The name is what does the damage: `test_with_a_table_attached_the_head_label_is_still_the_
section_0_binding` reads like coverage of the section-0 dependency, and a reader checking
"is this guarded?" finds a green test whose name contains the exact words. **It is green
because the bed is the runner** — the fixture supplies the very condition whose absence is
the defect. Recommend a fourth test that binds only sections 4, 7, 8 and asserts what the
head label becomes, which converts an unguarded trap into a measured one.

*(Incidental, low value, unverified by running: there is a `if __name__ == "__main__": unittest.main()` at `tools/test_effects_gen.py:1244-1245` with at least one further test class
defined **after** it, so direct execution of that file would not collect the later class.
Harmless under pytest collection, which is how `build.sh` runs these. Noted, not chased.)*

---

## What I could not settle, and why

1. **Anything needing a running ROM.** Per the invariant, no emulator was touched. **TAGGED
   for the controller:** L-3 (the `probe_core` air-cell claim, which the existing instrument
   is structurally unable to see — the crossover trace is byte-identical across solidity
   values, which is *why* it cannot); L-4 (`path_swap` despawn/re-arm on the section-0 loop);
   and the unresolved `$900` 413 px drop.
2. **Whether the pin's sigil-side fix is truly one line.** I read `section_align.rs` firsthand
   and the row is one line, but the `effects_gen.py` comment records that *"Sigil ruled the
   refusal loud and correct and REFUSED both alternatives — a DECLARED pattern rule, and
   re-keying the row off the head label (which desynchronises from `map.toml` order,
   `section_align.rs:61`)"*. The second refused alternative is **self-contradictory as
   written** — the row is *already* keyed off the head label — so I cannot tell which
   re-keying sigil declined. **This is a question for the sigil lane, not a grep.** It does
   not change any conclusion above; it changes the cost estimate of the eventual fix.
3. **Owner-ruling status for research §7 decisions 1, 2, 5, 6, 7.** My instrument
   (`docs/decisions.jsonl`) does not carry rulings, and rulings in this repo live in prose
   across `DEFERRED_WORK.md` and the anchor. I did not attempt a prose sweep for five separate
   rulings; the hub should ask the owner rather than trust an absence here.
4. **The aurora half of anything.** The left-arc repaint, the third-mark paint, the run-up
   foliage, and booking item (a) (the raster binding) are all named above as **not aeon's**
   and are relayed from this repo's record, not re-derived against aurora's tree.

---

*Read at aeon `deb52a95`; sigil read at `e3e344e7` (`master`, working tree carrying 15 modified files, so the
file as read is not necessarily the committed one) — a sigil claim above should be
re-confirmed by the sigil lane before it is quoted as current.*
