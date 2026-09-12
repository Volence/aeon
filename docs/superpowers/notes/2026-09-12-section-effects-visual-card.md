# Section/effects cleanup, the visual half: status of every screen-changing question, and a draft card

Read-only research. No code changed, nothing built, no emulator used. The controller reviews the
draft card below and appends it to `docs/decisions.jsonl`; this note does not touch the ledger or
`docs/lane-status.json`.

**Tree read:** branch `notes/section-effects-visual-card`, cut from `origin/master` at
**`57528c22`** (verified: `git rev-parse origin/master` = `57528c22270e...`). Every `path:line`
below is at that tip unless another revision is named.

**Sources, at the revisions read:**

- Pricing: `docs/2026-09-10-section-effects-inventory.md` at `21d99cf7` (branch
  `recon/section-effects-inventory`, read with `git show`), section D4 and the table "What is
  yours to settle, priced".
- Card format: empyrean `contract/DECISIONS.md` at `origin/main` `61d378b`.
- Ledger: `docs/decisions.jsonl` at `57528c22`, 149 lines, all 149 parse.
- The owner's working copy (main checkout `/home/volence/sonic_hacks/aeon`), read only. **Method,
  because the brief's recipe was refused:** this worktree's harness refuses `git -C` into the
  main checkout. I read `/home/volence/sonic_hacks/aeon/.git/HEAD` (`ref: refs/heads/master`),
  resolved `master` from this worktree (shared refs: `a38ce7c9`, 7 behind `origin/master`),
  wrote `git show master:<path>` to the scratchpad, and ran plain `diff` against the main
  checkout's files. Nothing in the main checkout was modified, staged or checked out.

**Why the card exists:** the 2026-09-12 handoff lists the owner's open cards as VRAM-FOR-OBJECTS,
CTRL-3, EFX-2 and CHAR-10 and says "Nothing else is owed by him from this lane"
(`docs/superpowers/2026-09-12-aeon-overseer-handoff.md:73-74`). Its next-work order is "the lens
residue, then the section/effects cleanup, then regions per the owner's 09-11 order" (`:76`). No
ledger id mentions this cleanup: searched `SECTION-EFFECTS`, `section-effects`, `scheme b`, 0 hits.

---

## 1. Every screen-changing question, and where it stands

The first six rows are the inventory's priced table (its rows in its order). Scheme B is row 4. The
last two rows were not in the inventory; I found them while verifying.

| # | Question | Status | Evidence |
|---|---|---|---|
| 1 | Section 0's waterline back on ("the pending edit") | **SETTLED**, and **CHANGED** (the pending edit is gone) | `WATERLINE-OFF-READING` (`docs/decisions.jsonl:142`) carries `answered: {by: "hub", chose: "gone", at: 2026-09-09T23:43:39Z}`, delegated by the owner ("Feel free to: fix the cards, answer any you can"). The committed state is channel 0 off: `games/sonic4/data/effects/ojz_effects.emp:1516-1522` (`PATCH_ANCHOR_NONE` / `ANCHOR_MOTION_NONE` in slot 0), with the revert recipe at `:1440-1449`. **The re-enable edit the inventory quarantined no longer exists:** the main checkout's `ojz_effects.emp` is identical to its HEAD `a38ce7c9` (`diff` exit 0), and `git diff master origin/master` on that file touches only the static-program padding (EFX-4b), never `OJZ_Preset_Sec0`. Not in the card: one word on that card overturns it. |
| 2 | Does section 5 keep the Underwater loan? | **OPEN** (the trial is settled; keeping it is not). **CHANGED** price | d-53 (`docs/decisions.jsonl:105`) answered `reuse_underwater`, owner "Sure let's do it to see it?"; that card's own costs said "you should see it before it stays". The binding is still live: `ojz_effects.emp:1677-1686`, `games/sonic4/data/levels/ojz/act1/act_descriptor.emp:310-317`. **I found no record that he has watched it.** Searched `docs/**/*.md` for `remap visible on 5`, `observable on section 5`, `absent on section 0`, `p >= 8 at rest`: only hit `docs/DEFERRED_WORK.md:32832`, which is the unmet TAG itself. Searched `docs/lane-log.jsonl` (281 lines) for row-remap lines mentioning section 5 or the screen: 0 hits. **The price moved:** the inventory says reverting "strands `CAP_ROW_REMAP` (`scene_registry.emp:488`)". At this tip the guard is `games/sonic4/data/effects/scene_registry.emp:504-505` and it tests `SceneRegistry_CapsFolded = fold_caps(SCENES)` (`:510`), the registry list, which holds `Scene_OJZ_Underwater` at `:346` whether or not any section installs it. A revert takes the effect out of normal play and strands nothing: the scene stays in the registry and in the debug lab's scene table (`games/sonic4/test/ojz_scroll_test.emp:2371`, lab row 1 at `:2296`). |
| 3 | Should the row-remap waterline be on section 0 or 5? | **CHANGED**: effectively decided by row 1 | On section 0 it would need two things. First, channel 0's line back on: section 0's band split reads the same latched line as the tint, and it went off-screen when the waterline went off (`ojz_effects.emp:1451-1457`). That reverses row 1's answer. Second, a way past section 0's rung-1 editor scene, which overrides the preset's Underwater binding (`engine/effects/preset.emp:228-237`; `games/sonic4/data/generated/ojz/act1/effects_scenes.emp:344` and `:166`). The crossing gate needs that override to stay distinct (`tools/parallax_crossing_gate.py:49-59`, `:671-673`). The row remap's own tuning comment admits it was measured on section 0, where it never installed (`games/sonic4/data/effects/ojz_scenes.emp:252-270`). Folded into the card's `detail` as "not offered, because it reopens a settled answer". |
| 4 | Do sections 1-3 keep visible gate fixtures? (**Scheme B**) | **OPEN**. **CHANGED** scope: section 3 is content, so the question is sections 1 and 2 | **Section 1:** `OJZ_Preset_Sec1` binds `raster: OJZ_TestRaster` (`ojz_effects.emp:1523`). At screen line 120 it turns Shadow/Highlight on and writes CRAM line 2 entry 5 to `$000E`, bright red (`:194-215`). The descriptor calls it "Effects P1 gate" (`act_descriptor.emp:258-260`). **Section 2:** `OJZ_Preset_Sec2` binds `raster: OJZ_TestGradient` (`ojz_effects.emp:1553`), a 96-line dense ramp on lines 96..191 (`:941-1014`). Its three entries differ by one 3-bit step, "a subtle effect" (`:1538-1541`), yet it is the budget model's "real worst case on shipped content": 31,665 cyc/frame, 24.7% (`tools/effects_budget_model.toml:935-941`; 25.7% pre-rider at `engine/effects/raster_dsl.emp:2803-2804`). Descriptor: "Effects P1 gate" / "Effects P2 Task 5 gate" (`act_descriptor.emp:266-274`). **Section 3 is out of scope by evidence:** `d-51-shimmer-cadence-look` (`docs/decisions.jsonl:106`, hub `keep_look`, 2026-09-02) treats `OJZ_ShimmerCycle` as "content that already ships". Its editor twin `ojz_sec3_shimmer.json` is golden-checked (`tools/editor_palette_golden.py:76-81`) but not bound: there is no `section_3.meta.json` (`find` returns 0, 4, 5, 6, 7, 8), and `ojz_act1_sec_cycle` has no arms (`effects_scenes.emp:471-475`). The inventory's premise that sections 1, 2 **and 3** exist to host fixtures missed d-51, which predates it. |
| 5 | Rename `OJZ_Preset_Depth` -> `OJZ_Preset_Sec4` | **CHANGED**: the inventory's "safe" is wrong. Not visual; not the owner's | A rename is coupled to sigil, with three sites per member (`repin.toml` by name, generated `pins.rs` identifiers where it is a compile error, and the string literals in `act_descriptor_port.rs`). The prefix sweep would also move `Depth` into the swept set and orphan its pin. Sources: `docs/DEFERRED_WORK.md:32683-32691` and `:32803-32818`, `ojz_effects.emp:2506-2517`, `docs/superpowers/designs/2026-09-09-regions-v1-design.md:543-561`. It is a coordinated lane task (sigil has offered the edits), so it stays off the card. |
| 6 | Correct the stale prose | **SETTLED**: landed as Scheme A | `docs/DEFERRED_WORK.md:32720-32759` ("SECTION/EFFECTS RECORD FIX"). One remnant is left deliberately: lab row 35's glyph still reads `BARE` (`ojz_scroll_test.emp:2331`; `DEFERRED_WORK.md:32794-32802`). That is a debug-readout vocabulary choice, emitted bytes, and the lane's to make. |
| 7 | *(not in the inventory)* The owner's uncommitted working-copy edit | **OPEN, but his authoring, not a question** | His current uncommitted edit is **not** the waterline one. It moves layers 4 and 5 of section 0's background scene `ojz_act1_start` from world Y 112/160 to 303/318 (main checkout `games/sonic4/data/editor/effects/ojz_act1_start.json:37,44` against its HEAD; regenerated `effects_scenes.emp:117-118`). No inventory row depends on it, and the card touches nothing in section 0. It is presumably the edit behind the id-less `blockedOnOwner` entry "your uncommitted edit to one generated effects file collides with a landed change" (main-checkout `docs/lane-status.json`, read only). |
| 8 | *(not in the inventory)* Section 2 was the act's only second palette | **OPEN, and already on the owner's desk through EFX-2** | `DEFERRED_WORK.md:22866-22884` books the owner call (accept one palette, or give section 7 or 8 a real second one). EFX-2's `show` option (`docs/decisions.jsonl:147`, open) gives one section its own colours. Under contract rule 10 (one question, one card) it stays on EFX-2 and is not folded in here. |

**Ledger search, stated with its terms.** Two passes over all 149 lines of `docs/decisions.jsonl`
at `57528c22`:

- A `grep -i` for `waterline|sec5|section 5|section-5|underwater|row.remap|rowremap|fixture|sections 1|OJZ_Test|TestRaster|TestGradient|Shimmer|d-53|Preset_Depth|scheme b|section-effects|SECTION-EFFECTS`.
- A parsed-JSON term scan for `section 1`, `section 2`, `section 3`, `sections 1`, `fixture`, `ramp`, `split`, `shimmer`, `row remap`, `row-remap`, `waterline`, `underwater`, `section 5`, `section 0`, `depth`, `rename`, `loan`, `ojz`.

Relevant hits:

- `d-53-moving-band-needs-a-home` (lines 102, 105 answered): row 2.
- `WATERLINE-OFF-READING` (142, answered): rows 1 and 3.
- `d-51-shimmer-cadence-look` (100, 106 answered): row 4's section 3.
- `EFX-2` (147, open): row 8.
- `d-15` / `d-15-answered` (15, 28): section 4 became the showcase because sections 0-3 held fixtures; context only.

I opened `d-26`, a `ramp` hit, and it is about divide instructions, so it is irrelevant. The other
term hits (`split`, `depth`, `ojz`, `fixture` on d-6..d-49, LS-*, SP6-*, VRAM-FOR-OBJECTS,
CHAR-10) match on unrelated words, judged from the ids and question heads the scan printed.

**Nothing in the ledger asks whether sections 1-3 keep their test effects, where the row remap
should live, or about the `Depth` rename. Those searches came back empty.**

---

## 2. The draft card

**One card, three packages.** The two open questions (rows 2 and 4) are independent, but they are
the same kind of question: what the playable act shows. Both are cheap, and one answer settles
the whole visual half, so the cleanup can run in one parcel. I left out the fourth combination
(keep the test effects, give section 5 back its background) because nothing in the tree suggests
he wants it. `detail` says any mix is possible, so a freehand answer lands cleanly under rule 8b.

**The inventory's sequencing view ("Regions: NEUTRAL now, HELPS later") does not change the
recommendation.** The regions design transcribes each section's bindings one to one (regions
design `:530-532`, §4 step 1), and a region names a preset, not its program. So unbinding two
rasters costs the same before or after the migration. Doing it first follows the owner's own order
(handoff `:76`), and the migration's baseline then starts from the cleaned act instead of needing
a second content change afterwards. That makes the timing a mild reason to do it now, not a reason
to pick another option.

```json
{
  "id": "SECTION-EFFECTS-VISUAL",
  "at": "FILL-AT-APPEND",
  "question": "Two of the first level's playable sections still show test effects we built only so our checks could prove the engine works. In section 1 the most common ground colour turns bright red below a fixed line and the console's shadow mode switches on there, and section 2 carries a faint colour ramp that is hard to see but is the most expensive effect in the game, about a quarter of every frame. Separately, section 5 is still wearing the underwater background you let us borrow on 3 September so you could see the moving waterline, and nobody has recorded whether you want it kept. All of this changes what you see while playing, so it is your call.",
  "options": [
    {
      "key": "keep_all",
      "name": "Leave all of it as it is",
      "what": "Sections 1 and 2 keep their test effects, section 3 keeps its water shimmer, and section 5 keeps the borrowed underwater background with the moving waterline.",
      "costs": "No work now. Anyone playing still meets the red ground band in section 1 and pays for the ramp in section 2. The level layout change planned next copies them across unchanged, so removing them later is the same size of job, done in the new layout instead."
    },
    {
      "key": "tests_out",
      "name": "Take the test effects out of sections 1 and 2, keep everything else (RECOMMENDED)",
      "what": "Sections 1 and 2 look like the level's plain sections. The two test effects stay in the cartridge for our checks, so you no longer meet them while playing. Section 3's water shimmer and section 5's borrowed underwater look stay exactly as they are.",
      "costs": "About a day of our work, an estimate. The check that walks into section 2 to find the ramp needs another way to switch it on, the frame time budget has to be measured again because section 2's ramp is its heaviest case, and the debug readout names for both sections change. Section 2 gets about a quarter of each frame back. If you miss either effect, putting it back is one line."
    },
    {
      "key": "tests_out_and_5_back",
      "name": "Do that, and also give section 5 back its own background",
      "what": "Everything in the option above, and section 5 keeps its coloured bands but returns to the level's normal background, as it was before 3 September. The moving waterline and the perspective ripple under it then appear nowhere in normal play, though they stay in the cartridge.",
      "costs": "The same day of work plus a one line change. The moving band setting you can change in the editor goes back to having nothing on screen to move in play, which is the problem you answered on 3 September, until some section gets a background made for it."
    }
  ],
  "recommend": {
    "key": "tests_out",
    "because": "Section 1's effect was built to be as loud as possible so a machine could spot it in a screenshot, and section 2's ramp is nearly invisible yet costs a quarter of every frame, so neither is level design. When effects have got in the way of playing before, the animated background tiles and section 0's dark waterline last week, you asked for them to go. Section 5 is a different case: you borrowed that look in order to judge it, it is the only place the moving waterline shows in play, and undoing it later is one line, so it should stay until you have watched it. Doing this now, before the level layout change, means the new layout starts with only real level content in it."
  },
  "detail": "Drafted 2026-09-12 on branch notes/section-effects-visual-card from origin/master 57528c22; the evidence table is docs/superpowers/notes/2026-09-12-section-effects-visual-card.md. Pricing source: docs/2026-09-10-section-effects-inventory.md at 21d99cf7, D4 Scheme B plus its priced table. SECTION 1: OJZ_Preset_Sec1 binds raster: OJZ_TestRaster (ojz_effects.emp:1523), which at screen line 120 sets S/H on and writes CRAM line 2 entry 5 to $000E (:194-215); the descriptor calls it the Effects P1 gate (act_descriptor.emp:258-260). SECTION 2: OJZ_Preset_Sec2 binds raster: OJZ_TestGradient (ojz_effects.emp:1553), a 96-line dense ramp on lines 96..191 (:941-1014) whose three entries differ by one 3-bit step (:1538-1541); tools/effects_budget_model.toml:935-941 records it as the real worst case on shipped content, 31665 cyc/frame, 24.7 percent. SECTION 3 IS OUT OF SCOPE: d-51-shimmer-cadence-look (hub keep_look, 2026-09-02) treats OJZ_ShimmerCycle as shipped content; its editor twin ojz_sec3_shimmer.json is golden-checked (editor_palette_golden.py:76-81) but unbound (no section_3.meta.json; ojz_act1_sec_cycle has no arms, effects_scenes.emp:471-475). SECTION 5: the d-53 loan, parallax: ParallaxConfig_OJZ_Underwater (ojz_effects.emp:1677-1686), answered reuse_underwater 2026-09-03 ('Sure let's do it to see it?'); no record of a viewing since was found. A revert strands nothing: the CAP_ROW_REMAP guard (scene_registry.emp:504-505) folds over the registry list SCENES (:510), which holds Scene_OJZ_Underwater at :346 regardless of any binding, so the inventory's 'strands CAP_ROW_REMAP' price does not hold at this tip. WORK FOR tests_out (estimated, not measured; byte-moving; the effects-gate ritual applies): unbind the two rasters but keep the preset NAMES, because renaming OJZ_Preset_* is sigil-coupled (DEFERRED_WORK, THE SECTION SYMBOL FAMILIES ARE CROSS-SEAM COUPLED); keep OJZ_TestRaster and OJZ_TestGradient emitted (map.toml:128 names OJZ_TestRaster as a placement head, reels_gate.py:159); re-home tools/scenes/effects_raster_dense.json (Camera_X 4960 at :10, README.md:85-94) and the dense scene in effects_gates.py (:861-917), which asserts the dense cursor end state and so would go RED rather than silent if the ramp were simply unbound (derived from :896-917 and README.md:96-101, not run); re-measure the budget rows; relabel lab rows 29 and 30 (ojz_scroll_test.emp:2324-2325, emitted bytes, held by test_lab_index_lint.py). A grep of tools/ for OJZ_TestRaster and OJZ_Preset_Sec1 found no gate that reaches section 1's program. Whether the debug lab can install the dense program directly is UNVERIFIED (.raster_table is lint-held to preset documents, ojz_scroll_test.emp:1876-1878). NOT OFFERED HERE: section 0's waterline (WATERLINE-OFF-READING, answered gone); moving the row remap to section 0, which needs channel 0's line back on and so reverses that answer (ojz_effects.emp:1451-1457); a second palette (EFX-2 carries it); the OJZ_Preset_Depth rename (not visual, sigil-coordinated). The two halves are independent and any mix can be done. NOBODY HAS LOOKED AT THESE SECTIONS ON SCREEN FOR THIS CARD: every description is derived from source.",
  "supersedes": null,
  "refs": { "queue": ["SECTION-EFFECTS-VISUAL"], "project": null }
}
```

**Why `tests_out` and not `keep_all`, argued from the tree and not from taste:**

- Section 1's program was chosen to be "objectively measurable from a screenshot"
  (`ojz_effects.emp:194-198`). That is the right property for a machine instrument and the wrong
  one for a level someone plays.
- The owner has twice asked for an effect gone because it got in the way. One was the animated BG
  tiles, "they're so distracting" (`ojz_scroll_test.emp:2436-2437`). The other was section 0's
  waterline, "dark and distracting" (`ojz_effects.emp:1440`).
- **The counter-evidence, stated so it is weighed and not buried:** on 2026-09-03 he asked for
  section 2's blue test palette to go *so the ramp could be seen* (`ojz_effects.emp:1524-1525`).
  So he has used section 2 as an effects showroom, and the card's recommendation takes that away
  from normal play. I still recommend it because the ramp is nearly invisible against the real
  palette anyway (`:1538-1541`), and a showroom does not need to sit in the playable act. But
  whether a debug-menu route to view it exists is unverified (see §3), so the card promises only
  that the checks keep it.

**Why keep section 5 in the recommendation.** The d-53 loan was taken "to see it". It is the only
place in normal play where the row remap and the moving split can appear (rows 2 and 3). Its
revert is one line with nothing stranded (row 2). Retiring it before he has looked would decide
for him the one thing that card deferred to his eye.

---

## 3. What I could not settle

1. **Nothing here was looked at on screen.** These are TAGGED for the controller's foreground
   session:
   - that section 1 shows the red band and shadow mode below line 120 at this tip;
   - that section 2's ramp is as faint as the source says;
   - that the row remap is visible on section 5 and absent on section 0 (the inventory's own
     unmet tag, `DEFERRED_WORK.md:32830-32834`);
   - what section 5 looks like with the loan reverted (its editor colour bands, top 32/34/36,
     should remain).
2. **The route by which the checks switch the test effects on after `tests_out`.**
   - The dense scene reaches section 2 by a camera poke, and the boundary crossing installs the
     preset (`tools/scenes/README.md:85-94`).
   - The debug lab installs raster programs from `.raster_table`, but that table is lint-held to
     the preset documents on disk in both directions (`ojz_scroll_test.emp:1876-1878`).
   - I did not establish whether a hand dense program can be installed by the lab or by a scene
     poke. So "about a day" is an estimate, not a measurement.
3. **`OJZ_TestRaster`'s pin "retires in Parcel D together with the fixture it pins (design spec
   8.2)"** (`ojz_effects.emp:217-222`). This is a retirement plan already on record. A grep of the
   two Parcel D spec files (`docs/superpowers/specs/2026-08-16-parcel-r1-palette-bands-v5.md`,
   `2026-08-17-effects-tail-design-v3.md`) for `8.2` found no matching section heading, and I did
   not determine Parcel D's status. If that retirement is scheduled, `tests_out` may be half of it
   already.
4. **Sigil-side consequences of unbinding** (not renaming) the two rasters. `act_descriptor_port.rs`
   pins preset addresses, and unbinding changes a pointer inside a fixed-size record, not its
   address. I did not enter the sigil repo, per the brief, so this is unverified.
5. **Section 0's own test machinery** is outside Scheme B and pinned by identity: channel 1's
   two-line split at the screen bottom, "a gate fixture parked in the bottom two screen lines"
   (`ojz_effects.emp:1464-1466`), plus four refuse-fixtures and the crossing gate. It is not in the
   card; moving it is a larger job, and it is barely visible.

## 4. Contradictions with the brief, and with the inventory

**With the brief:**

- "Scheme C is blocked on a schema CR (item 9c)" is half-stale.
  - The row-remap scene key and its schema CR landed on 2026-09-04 (empyrean `3992d16`, aeon
    reader `d593070a`), and 9c's remainder is content (`DEFERRED_WORK.md:19629-19635`).
  - Scheme C's live blocker is the preset-document rule set that bars sections 0 and 7 from
    binding a document (`DEFERRED_WORK.md:801-808`; `ojz_effects.emp:1649-1669`). Lifting it is
    d-53's `open_the_door` contract change, not item 9c.
- The brief's `git -C /home/volence/sonic_hacks/aeon diff` recipe is refused by this worktree's
  isolation. The equivalent read is described at the top of this note.

**With the inventory, at this tip:**

- **The rename row is wrong** (row 5).
- **"Reverting the loan strands `CAP_ROW_REMAP`" does not hold** (row 2). The guard folds over the
  registry, and it has moved from `:488` to `:504-505`.
- **Scheme B's cost "effects_raster_dense.json ... (silent)"** is right for *moving* the ramp to
  another section, but for *unbinding* it the dense gate goes red: it asserts the run's end state
  (`tools/effects_gates.py:896-917`). This is derived, not run.
- **"Sections 1, 2 and 3 exist today to host" fixtures:** section 3 has been treated as shipped
  content since d-51 (row 4).
- **The pending section-0 waterline edit it quarantined no longer exists in the owner's working
  copy.** A different uncommitted edit (section 0's background layers) is there now (row 7).

**Incidental:** the handoff says only four cards are owed (`:73-74`), while the main checkout's
`docs/lane-status.json` also lists `SP6-MODULATION-DIVERGENCE` and one id-less entry. Noted, not
pursued.
