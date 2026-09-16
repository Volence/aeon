# Regions seam, part two: the emitter, and the flip that is an L

Parcel `parcel/regions-emit`, aeon, 2026-09-16. The successor to
`parcel/regions-loader-golden` (`docs/superpowers/notes/2026-09-16-regions-loader-golden.md`),
step 2 of the **AURORA REGIONS EDITOR** spec
(`empyrean docs/superpowers/specs/2026-09-14-aurora-regions-editor-design.md`).

No emulator, no running app, no `mcp__oracle__*`. Everything below reads source, fixtures and
Python; the build lanes are the ordinary four shapes.

**SCOPE NARROWED MID-PARCEL BY THE CONTROLLER, and it is recorded here rather than absorbed
silently:** the B′ chooser re-key is OUT, and `games/sonic4/data/effects/ojz_effects.emp` is not to
be touched, because a second agent is landing the night-palette fix in that file
(`OJZ_Palette_Night`, :1966) and two agents in one file is a merge nobody wants to referee. The
emitter needs to *read* that file — `effects_library_records()` already parses its
`pub data <Name>: EffectsPreset` lines to validate a region's `preset` — and reads nothing else
from it, so the narrowing is not a blocker. B′ is booked below.

---

## 1. PHASE 0 — the third blocker stands, and the brief UNDERSTATES it

The brief asked me to test its own reading rather than confirm it. The reading is right about the
mechanism and **wrong about the severity, in the direction that matters**: the reels refusal is not
the thing blocking the flip, it is the last thing *refusing* a flip that would otherwise succeed
and silently throw away every Aurora binding in the act.

### 1.1 The refusal reproduces exactly

Sandbox (`RegionSandbox`, the loader-golden parcel's pattern): act 1 in region mode, the golden
document written, every `section_*.meta.json` removed — which is the state `Migrate sections`
leaves. `effects_gen.generate()` raises `SceneShapeError`:

```
/tmp/…/games/sonic4/data/editor/effects/ojz_act1_depth.json: scene 'ojz_act1_depth' carries a
`reels` key but no section binds it with a `sceneRef` sidecar, so it is never
Effects_ResolveParallax's rung 1 and the binding table would have no config pointer to key on.
Reels bind to a SECTION's lowered record, not to a scene in the library — assign the scene to a
section, or drop the key.
```

Confirmed. `render_module`'s `bound` map is built from `load_section_scene_refs`, so in region mode
it is empty, `rung1` is empty, and the rung-1 rule refuses.

### 1.2 THE MEASUREMENT THAT CHANGES THE ANSWER: remove the blocker, and the bake goes green EMPTY

I removed the only named blocker — dropped the `reels` key from `ojz_act1_depth.json` in the
sandbox, nothing else — and re-ran `generate()`. **It succeeded.** Census of the module it produced
against the shipped one:

| emitted population | legacy (shipped) | region mode, reels key removed |
|---|---|---|
| `EditorSceneBinding_*` records | **4** (Sec0, Sec4, Sec7, Sec8) | **0** |
| chooser arms (`if sec == N`) | **14** | **0** |
| `EditorRaster_*` programs | 6 | 6 |
| `EditorCycle_*` / `EditorVariant_*` | 1 / 1 | 1 / 1 |
| reels payload + binding table | 2 | 1 (the table, empty) |
| module size | 541 lines / 33 691 B | 384 lines / 25 712 B |

Unified diff: 11 hunks, **169 lines removed**, 12 added.

**Read what the two middle rows say together.** The raster/cycle/variant *programs* are still
emitted, because they are emitted per authored DOCUMENT and the documents are still there. What
vanished is every *binding*. All six choosers degrade to `comptime var out = hand; return out`, so
`ojz_act1_sec_raster(sec: 5)` returns 0 and `OJZ_Preset_Sec5`'s raster channel becomes null — the
band showcase disappears from the ROM while six raster programs sit in it unreferenced. Same for
the four scene bindings, the shimmer cycle and its variant.

**So the narrow fix the brief floated — "let a region's `sceneRef` establish the rung-1 binding the
way a sidecar's does" — is the one change that must NOT be made alone.** Today the reels rule is a
load-bearing tripwire: it is the only refusal standing between a migrated act 1 and a green build
of a silently de-bound ROM. Relaxing it in isolation converts a loud refusal into a quiet content
loss, which is the exact failure mode this seam's whole design is organised against.

### 1.3 The real price: the binding half of `render_module` is keyed on SECTION INDEX, end to end

Not one rule. Every binding mechanism in the generated module is section-keyed:

* `ActNames.binding_sec(i)` mints `EditorSceneBinding_OJZ_Act1_Sec<i>`.
* Six `pub comptime fn <act>_sec_*(sec: int, …)` choosers, whose arms are `if sec == N`, with an
  `ensure(sec >= 0 && sec < 9)` derived from the act's section count.
* `EditorReelBindings_OJZ_Act1` keys on `extern("EditorSceneBinding_OJZ_Act1_Sec4")` — pointer
  identity of a section-keyed symbol.
* `render_module`'s `bound` / `raster_bound` / `cycle_bound` / `variant_bound` / `patch_bound` /
  `patched_bound` / `reels_bound` are all `{section index: …}`.

Reference count for `ojz_act1_sec_*` and `EditorSceneBinding_OJZ_Act1_Sec*` outside the generated
module itself: **87 sites across 14 files**, including `games/sonic4/data/effects/ojz_effects.emp`
(26), `act_descriptor.emp` (17), and seven gate/witness tools
(`effects_seam_gate`, `parallax_crossing_gate`, `depth_onset_probe`, `sec5_band_witness`,
`row_remap_witness`, `lens_residue_raster_witness`, `boot_override_gate`) plus
`games/sonic4/test/ojz_scroll_test.emp`'s `.lab_index`. There is a reader on aurora's side of the
seam too — `src/core/formats/effects/section-wiring.ts`, named in empyrean `a718ea7c`'s
`docs/AURORA_REGIONS_SCHEMA.md`, whose own amendment describes it keying on `sec_N`. That is a
citation of a ruling, not a claim about their working tree, and it is the hub's to confirm.

**A correct flip therefore needs all three of:** (1) the scene-binding half re-keyed from section
to region row, (2) the reels table re-keyed with it — same `bound` map, so it is one piece, not two
— and (3) **B′**, the five preset-channel choosers, whose 19 call sites are in the file this parcel
is forbidden to touch and whose ruling is `3fc9ffa5`. Without (3), a flip that passes (1) and (2)
still drops the raster/cycle/variant/patch bindings exactly as measured in §1.2.

**VERDICT: L, decisively not S. Stop condition taken — act 1 is NOT flipped**, the price is booked
in `docs/DEFERRED_WORK.md` under `REGIONS-EMIT-BINDINGS`, and emission is proven against a sandbox
act. Booked, not attempted.

### 1.4 What I think the brief got wrong, stated plainly

Three things, in descending order of consequence:

1. **Severity, per §1.2.** "This blocks flipping act 1 into region mode" is true and reads as an
   obstacle. It is better described as a *guard*: the blocker is the only thing currently making the
   flip fail loudly instead of quietly. A brief that sends someone to remove it gets the worst
   available outcome.
2. **"one rule in one generator plus its tests, no `.emp` engine change" would be S.** The rule is
   one `if`; the *keying it depends on* is the whole binding half of a 5 391-line generator plus
   87 downstream sites plus a cross-repo reader. Sizing the rule instead of the keying is how this
   reads as S from outside.
3. **The parcel's headline — "`generate()` emits the table from the document" — cannot be true of
   THIS tree in this parcel**, because no act in this tree is in region mode and flipping one is the
   L above. What lands is the emitter itself, wired into `generate()` behind the mode switch, inert
   on every act here, and proven end to end in a sandbox. That is the same posture
   `check_mode_conflict` shipped in deliberately one parcel ago, and it is stated rather than
   glossed.

Nothing here is a criticism of the brief's method — it explicitly asked to be tested and said it
would rather be corrected than agreed with, and the correction only exists because it named its
own reading as a reading.
