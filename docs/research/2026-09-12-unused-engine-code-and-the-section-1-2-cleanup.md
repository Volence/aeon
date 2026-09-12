# Does unused engine code end up in the cartridge? — and what the section 1/2 cleanup costs

Research parcel, 2026-09-12. Branch `research/dead-code-shipping`, based on aeon `origin/master` 3b6a7b4a.
No engine behaviour changed. The experiment described in §3 was reverted and the tree verified
byte-identical to baseline before this document was committed.

---

## 0. The answer, in one paragraph

**Yes, you can have engine code that ships zero bytes — and the unit is the FILE, not the routine.**
sigil builds only the modules your game actually reaches by `use`. A `.emp` file nothing imports is
never resolved, never lowered, and contributes nothing to the cartridge; it is not merely unreferenced,
it is not compiled at all. But there is no finer knife than that. The moment a file *is* reached,
**everything in it ships whether or not anything calls it** — there is no dead-symbol elimination
anywhere in the toolchain. So the rule is: *a whole unused file is free; an unused routine inside a
used file is not.* Your two test effects are in the second situation. `OJZ_TestRaster` (section 1's red
band) and `OJZ_TestGradient` + `OJZ_GradientStream` (section 2's ramp) all live in
`games/sonic4/data/effects/ojz_effects.emp`, the same file that holds all nine of the act's live
presets — so unbinding them from the playable map saves **exactly zero bytes** and leaves **832 bytes**
sitting in the ROM doing nothing. That is not a reason to refuse your ruling: the cheap version of what
you asked for is two words of edit, costs nothing, breaks nothing, and leaves both mechanisms fully
intact and injectable. Making those 832 bytes actually *go away* is a separate, larger job (§5), and it
is the only part that needs your decision.

---

## 1. Which half this document covers

Two halves, deliberately split:

- **The assembler/linker half — NOT this document.** Answered by the sigil lane at sigil `0f2c3a42`,
  `docs/superpowers/notes/2026-09-12-unused-engine-code-ships.md`. Their finding: inclusion is decided
  by the profile's `use` closure; `--extra-entry` exists to evaluate an out-of-closure module and
  *refuses by name* a module that would emit bytes.
- **The engine-structure half — THIS document.** Given that mechanism, where does *our* code actually
  sit, and what does the owner's ruling therefore cost?

**The seam** is exactly this: sigil decides *whether a module is built*; aeon decides *what is in which
module*. Sigil's answer is a capability statement ("a whole unused module is free"). Ours is a
placement statement ("these two effects are not in a module of their own"). Neither half answers the
owner's question alone.

I verified sigil's claims independently at rev `0f2c3a42` rather than inheriting them; §2 records
where their account needed correcting.

---

## 2. The mechanism, from source

Read at sigil rev **`0f2c3a42`** (master tip), via `git show`/`git grep` only — never by path, since
that is a peer's live working tree.

**Which of the three possibilities is true:** *unreferenced code ships, and exclusion requires the code
to live in a module outside the `use` closure.* Not automatic dead-code elimination; not a conditional
gate in `map.toml`.

- **Module closure is the only filter.** `crates/sigil-frontend-emp/src/resolve/mod.rs:679` runs a BFS
  over `use` edges (`reachable_modules`, `:1100`); lowering, region resolution, contract bind and
  section concat all iterate `reachable` only (`:862`, `:755`, `:823`, `:950`).
- **No dead-code elimination below that.** `sigil_link::link` (`crates/sigil-link/src/lib.rs:67`) walks
  `for sec in sections` unconditionally — no reachability filter, no reference counting. A search for
  GC/DCE machinery across `crates/` returns nothing relevant.
- **Closure roots are a hardcoded Rust list**, `native.rs::registry` (`crates/sigil-harness/src/native.rs:288`),
  plus four fixed seeds and any `--extra-entry`, assembled into a synthetic entry module
  (`synthetic_entry_src`, `:1645`). `map.toml` is **not** a reachability input — it contributes
  `[defines]` and placement.
- **Import is all-or-nothing.** `use foo.{OneName}` adds the same closure edge as `use foo`:
  `enqueue_uses` (`resolve/mod.rs:1149`) ignores the name list entirely. There is no partial-module
  import, no per-symbol linkage, no comdat.

### Three corrections to things that are written down and wrong

1. **`map.toml`'s `order` list DRIVES placement; it is not a subsequence guard.** This flipped in
   "Parcel K5" (`native.rs:2570`, sort at `:2773`; `validate_placement` at `:3493` now *confirms* the
   drive). **`games/demo/map.toml`'s own header comment — "Each demo target's derived order is a
   subsequence; a derivation change fails loud" — is stale**, and it is what led me down the wrong path
   early. Worth fixing in a future parcel; I did not touch it here.
   Consequence that matters: an `order` row spelled as a *head label* whose module fell out of the
   closure matches nothing and is **silently ignored** (`native.rs:3587-3598` only errors the other
   direction, for an undeclared byte-emitting section). Only `section:<name>` rows are checked for
   naming nothing.
2. **The `SIGIL_WARNINGS=full` `[module.unreachable]` warning does not enumerate dropped modules.**
   Its subject is *unevaluated `ensure` guards*: `resolve/mod.rs:681-712` skips any out-of-closure
   module with zero `ensure`s (`if n == 0 { continue }`), pinned by
   `tests/module_unreachable.rs:59` (`unreached_module_without_guards_is_silent`). So it is not an
   inventory of what the build dropped. It also fires on 94 aeon files today with nine legitimate
   allowlisted engine modules — **a firing is not by itself a defect.**
3. **The listing's "unused" marker is not evidence of anything.** `ListingSymbol::unused`
   (`sigil-link/src/listing.rs:20`) exists for AS format fidelity, and **sigil never sets it true** —
   every production construction site passes `unused: false`. Do not use it to reason about elimination.

Also flagged: sigil's own doc comments at `blank_import.rs:7` and `ast.rs:344` claim a selective
`use base.{X}` does *not* put the module in the closure. That is contradicted by their own
`enqueue_uses`. It does not change any conclusion here (it would only make closures wider), but anyone
reasoning from those sentences about selective imports being "cheaper" is reasoning from untested prose.

---

## 3. The demonstration

A source argument about a linker is a reachability claim, so I measured it rather than reading it.
Three arms, identical 256-byte payload (`pub data ... : [u16; 128]`, nothing referencing it), same tree,
`DEBUG=1` shape. The only variable is whether a `use` edge reaches the module.

Instrument validated first: `FAST=1 DEBUG=1 ./build.sh` produced a ROM **byte-identical** to the
canonical `DEBUG=1 ./build.sh` (846601 B, `cmp` clean), in 2.9 s wall (uptime load avg 4.56 — other
lanes active on this box).

**Baseline:** `s4.debug.bin` = **846601 bytes**, cksum `63600635`, canonical build `finished=0`.

| arm | where the payload lives | symbol in `.lst`? | `ObjDef_Static` | ROM file |
|---|---|---|---|---|
| baseline | — | — | `0x157E0` | 846601 |
| **A** | inside `ojz_effects.emp` (module IS in closure) | **placed at `0x157E0`** | `0x158E0` (**+256**) | 846621 (+20) |
| **B** | its own new module, nothing `use`s it | **absent entirely** | `0x157E0` (unmoved) | **846601, byte-identical** |

**Arm A's +20 file delta is a trap, and it is why file size is the wrong instrument.** The 256 bytes
*were* placed — `ObjDef_Static` and everything downstream moved by exactly `0x100`. The ROM *file* grew
only 20 bytes because the downstream shift was absorbed by existing slack and the residual 20 is the
deb2 symbol appendix for one new symbol. Had I trusted the file size I would have reported "dead code
is nearly free", which is false. **Measure placement (symbol gaps), not file length.**

**Arm B is the finding.** Same declaration, same payload, same file tree — the symbol does not appear in
the listing at all, nothing downstream moves, and the ROM is byte-for-byte the baseline. Unbuilt is the
default.

**Arm C — what injection costs.** Adding the single `use games.sonic4.deadcode_probe_b` line to a module
already in the closure immediately changed the build's behaviour, which is itself the confirmation that
the module had not been built before. It did not silently start shipping; it **refused**:

```
[layout.undeclared-alignment] 1 section(s):
  - section `deadcode_probe_b` (head label `DeadCodeProbe_OutOfClosure`) has NO declared
    alignment in `sigil_harness::section_align::DECLARED`.
```

That table is **in the sigil repo**, so injecting a brand-new byte-emitting module is a cross-repo edit.
I tried twice to make the injected module merge into an existing declared section instead (reusing
`in ojz_effects`, then renaming the file to change scan order); both still failed, because
`section_align::DECLARED` is keyed on the section's **head label** and the probe kept becoming the head.
**I could not demonstrate a zero-toolchain-edit injection path, so I am reporting it as unproven rather
than claiming it.** Arm A is the proven cheap path: adding data to an *existing* module built green
(`rc=0`) with no map or sigil edit at all.

Everything above was reverted; the tree was rebuilt and confirmed byte-identical to baseline.

**Landing evidence for this (docs-only) branch.** `./tools/landing_build.sh` — all four canonical shapes
plus the needs-build lane — `finished=0`, exit 0. Four shapes at **2569 passed, 0 failed** each
(125 subtests, 2 skipped, 14 deselected); needs-build lane **14 ran, 0 deferred, 0 failed**.
Wall clock 22:29:31Z→22:45:39Z, uptime load avg 5.95 (several other lanes active on this box).

---

## 4. The concrete case: section 1's red band and section 2's ramp

### What they actually are

**A framing correction first: neither effect is editor-authored.** Sections 1, 2 and 3 have no
`section_N.meta.json` and cannot be reached from the editor at all. The editor sidecars under
`games/sonic4/data/editor/effects/` are the wrong lever — they govern sections 0, 4, 5, 6, 7 and 8.
Both of these are hand-written `pub data` bound by hand-written `preset()` calls in one file.

| thing | symbol | declared at | bound at |
|---|---|---|---|
| section 1's red band | `OJZ_TestRaster` | `ojz_effects.emp:265` | `:1523` `OJZ_Preset_Sec1 ... raster:` |
| section 2's ramp | `OJZ_TestGradient` | `ojz_effects.emp:1011` | `:1553` `OJZ_Preset_Sec2 ... raster:` |
| the ramp's data | `OJZ_GradientStream` | `ojz_effects.emp:1002` | via `OJZ_TestGradient`'s `stream:` |

The chain is `act_descriptor.emp:260,274` → `OJZ_Preset_Sec1/Sec2` → the two programs. Both sections'
own comments in `act_descriptor.emp` call them acceptance gates ("Effects P1 gate", "Effects P2 Task 5
gate") — they are test fixtures sited in the playable map, exactly as you diagnosed.

⚠ **One name to confirm with you.** There is also an `OJZ_TestRamp` (`ojz_effects.emp:1205`) and two
editor documents called `ramp_probe` and `aurora_ramp_witness`. **None of those three reaches any
section.** If "section 2's ramp" means the thing actually rendering on section 2, it is
`OJZ_TestGradient`, and that is what this document prices.

### Sizes, derived from `s4.debug.lst` (gaps between consecutive symbols)

| symbol | span | bytes |
|---|---|---|
| `OJZ_TestRaster` | `0x14DC8`→`0x14E48` | 128 |
| `OJZ_GradientStream` | `0x15030`→`0x15270` | 576 |
| `OJZ_TestGradient` | `0x15270`→`0x152F0` | 128 |
| **total program data** | | **832** |
| `OJZ_Preset_Sec1` | `0x154CE`→`0x154FC` | 46 |
| `OJZ_Preset_Sec2` | `0x154FC`→`0x1552A` | 46 |

None of the three data symbols is `DEBUG`-gated. **Re-derived independently from `s4.lst` (release
shape):** `OJZ_TestRaster` `0x14528`→`0x145A8` = 128; `OJZ_GradientStream` `0x14690`→`0x148D0` = 576;
`OJZ_TestGradient` `0x148D0`→`0x14950` = 128 — **the same 832**, and `OJZ_Preset_Sec1`/`Sec2` are 46 each
(`0x14B2E`/`0x14B5C`/`0x14B8A`). Release pays exactly what debug pays.

**And the release listing independently proves Option 2 works.** In `s4.lst`, `OJZ_BandDemo`,
`OJZ_BaseSwap` and `OJZ_TestPal` all sit at the *same* address `0x145A8` — i.e. the two
`if DEBUG == 1 { .. } else { [] }` programs occupy **zero bytes** in release, while still existing as
named, injectable programs in the debug shape. That is not a claim about a mechanism; it is the
mechanism already working in the shipped ROM.

### What the cleanup costs or saves

**Unbinding alone saves zero bytes.** Change `raster: OJZ_TestRaster` → `raster: Raster_Program_None` at
`:1523` and the same at `:1553`. `EffectsPreset` is a fixed 46-byte record (derived above: 0x2E), so the
preset rows do not shrink, and the 832 bytes of program data stay exactly where they are — because they
are `pub data` in a module the game unavoidably uses for its other seven presets.

This is not a hypothetical. **The file already contains four unbound-but-shipping programs**
(`OJZ_WaterRaster`, `OJZ_TestVsram`, `OJZ_TestRamp`, `OJZ_TestPal`) and its own ledger at
`ojz_effects.emp:2440-2475` says so outright — `OJZ_TestPal` is annotated *"Unbound, but NOT free."*

**What stays behind: all of the raster machinery, and that is correct rather than a cost.** The
hypothesis that unbinding these two might strand `engine/effects/` does not hold. `Raster_VBlank` is
called unconditionally from `engine/system/vblank.emp`, `Palette_Compose` from
`engine/system/game_loop.emp` every frame, and `games/demo/map.toml` links the same procs with zero
Sonic content. Six other act-1 sections still bind raster or patched programs (0, 4, 5, 6, 7 plus the
debug lab). `CAP_DENSE_TIER` brackets only `OP_RUN_RAMP`'s ENTER body and `Game.SCANLINE_CAPS` is a
hand-written constant, not derived from bindings — so unbinding section 2 removes **zero engine
instructions**.

**What the cleanup does break — none of it bytes, all of it test scaffolding.** These two effects are
the *subjects* of live gates:

- `tools/effects_gates.py:861-920` — the `scene:dense` gate requires `OJZ_GradientStream` in the `.lst`
  and asserts the 96-line run is live. **It goes red.** This is the gate the effects ritual mandates.
- `tools/raster_cost_probe.py` and `tools/effects_budget_model.toml:937-940,1075` — the shipped dense
  cost rows (31665 cycles/frame) are *measured on* `OJZ_TestGradient`.
- `tools/raster_frame_epoch_probe.py:102,192` — needs the `OJZ_GradientStream` symbol.
- `games/sonic4/test/ojz_scroll_test.emp:2329-2330` — lab glyph rows `SPLT`/`DENS` go stale.

If the programs merely become unbound (the cheap path), the *symbols survive* and only the gates that
assert the effect is **live on screen** need re-pointing — a much smaller blast radius than deletion.

---

## 5. The priced estimate

Your instruction was "take them out of the map but keep them in the engine to inject anywhere we may
want". There are three ways to do that, and they differ by an order of magnitude.

### Option 1 — Unbind in place. **Recommended. ~30 minutes, 0 bytes saved, 0 risk.**

Two argument edits (`ojz_effects.emp:1523`, `:1553`) to `Raster_Program_None`, plus re-pointing or
retiring the `scene:dense` gate and the two cost probes. The playable map is clean, both mechanisms stay
100% intact under their existing names, and re-injecting anywhere later is one word in a `preset()`
call — no new files, no toolchain edits, nothing to design. The 832 bytes stay in the ROM.
*This is exactly what you asked for, and it is essentially free.*

### Option 2 — Debug-gate the emission. **~1-2 days, saves 832 bytes in release.**

`ojz_effects.emp` already does this twice, for precisely this purpose:
```
pub data OJZ_BandDemo: [u16; OJZ_BAND_DEMO_EMIT_WORDS] = if DEBUG == 1 { static_program(...) } else { [] }
```
`OJZ_BandDemo` and `OJZ_BaseSwap` emit nothing in release and are driven by the debug effects-lab
hotkey. Wrapping the three data symbols the same way gets the release ROM its 832 bytes back while
keeping both effects present and injectable **in the debug shape**, which is where an effects lab lives
anyway. Cost is one byte-changing parcel: release and debug shapes now differ across this
neighbourhood, the four gates above need re-pointing at the debug shape, and it is a
repin/refreeze ritual (below). **Caveat: this makes them injectable in DEBUG only.** If "anywhere we may
want" includes shipping one in a release build later, this is the wrong option.

### Option 3 — Split into their own module, so they are free in every shape. **~3-5 days, cross-repo. Not recommended now.**

This is the only option that makes them genuinely present-but-free everywhere, and it is the expensive
one. Arm B proves the mechanism works; the cost is entirely in where these particular symbols sit:

- **`OJZ_TestRaster` is the head label of the entire `ojz_effects` section.** Moving it renames the
  section head, which forces edits to `games/sonic4/map.toml:132`, and in the **sigil** repo to
  `crates/sigil-harness/src/section_align.rs:233` (`d("OJZ_TestRaster", 2, WORD)`),
  `crates/sigil-harness/src/pins.rs:207`, `repin.toml`, `golden/provenance.toml`, and
  `crates/sigil-cli/tests/act_descriptor_port.rs`. All five of our symbols
  (`OJZ_TestRaster`, `OJZ_TestGradient`, `OJZ_GradientStream`, `OJZ_Preset_Sec1`, `OJZ_Preset_Sec2`)
  are named somewhere in that cross-repo pin infrastructure. **This is a paired aeon+sigil parcel, not
  a file move.**
- **Four gates in this file derive sizes from the GAP between symbols**, so reordering breaks them even
  though no value changes — `ojz_effects.emp:2465-2472` lists them
  (`plane_base_swap_gate.py:118`, `band_drift_golden.py:72-78`, `reels_gate.py:150-160`,
  `waterline_tint_coverage.py:84`). The file's own warning: **"UNBOUND DOES NOT MEAN DELETABLE
  ANYWHERE IN THIS FILE."**
- **Re-injection is not free either, and I could not prove it cheap.** Arm C shows a new byte-emitting
  module needs a `section_align::DECLARED` row in the sigil repo. So "inject anywhere we may want" would
  mean a cross-repo edit each time, unless someone first designs a parked-section mechanism that
  reserves placement for a module that is currently out of closure. **That design does not exist today**
  and is the real hidden cost in this option.

### What I am unsure about

- **Option 3's day range is the softest number here.** It is a byte-moving cross-repo parcel with a
  repin/refreeze ritual and four gap-derived gates, and this tree's history shows those routinely
  surface a surprise. 3-5 days is my honest estimate; I would not defend the lower bound.
- **Whether a zero-toolchain-edit injection path exists.** Two attempts failed (§3, Arm C). It may well
  be possible and I simply did not find the right spelling; a sigil-side answer would settle it in
  minutes. **Tagged for follow-up.**
- ~~Release-shape sizes were asserted rather than derived.~~ **Closed** — re-derived from `s4.lst`
  in §4; the release total is the same 832.
- **Nothing here was confirmed in motion.** No emulator was run (this parcel's standing constraint).
  Claims about what renders on sections 1 and 2 come from source and from the existing gates, not from
  a screen. **Tagged for foreground follow-up if a visual confirmation is wanted.**

---

## 6. Things I was asked to check that turned out to be wrong

- **"Placement is declared rather than derived from reachability, so unreferenced code ships anyway."**
  Half wrong. Reachability *is* the filter, at module granularity (§2, §3 Arm B). The hypothesis is
  correct only *within* a reached module, which happens to be the situation these two effects are in —
  so the conclusion about *this case* was right for the wrong reason.
- **`PER-GAME-BAND-DEFINES` as evidence that unused features are not free.** Over-read, and the revised
  reading is the correct one. `docs/lane-log.jsonl:254` (2026-09-10) describes it as a **record-width /
  sizing-constant** problem: "the row-remap feature widens a record for BOTH games", with per-game
  `-D` defines as the fix ("shipped in sigil 2026-08-22 with zero adoption"). That is a compile-time
  constant inside a record the game *does* use — module-granular elimination cannot help it, and it
  says nothing about dead code. The nearby precedent at `lane-log.jsonl:144` is the useful one: a
  feature left always-on charged the demo game 104 bytes, and putting it behind a switch cost both
  games nothing — which is Option 2's shape.
- **"Read the editor sidecars to find how the preset is bound."** Wrong tree for these two. Sections 1,
  2 and 3 have no editor presence at all (§4).
- **`games/demo/map.toml`'s "derived order is a subsequence" comment** is stale since Parcel K5 (§2).
- **The `SIGIL_WARNINGS=full` unreachable-module warning** is not an inventory of dropped modules; it
  counts unevaluated `ensure` guards and is silent on any guard-free dropped module (§2).

---

## 7. Recommendation

Take **Option 1** now — it is what you asked for, it costs half a day, it breaks nothing structural,
and it leaves both effects sitting under their existing names ready to bind to any section with a
one-word edit. Then decide Option 2 separately and on its own merits, as a "do we want 832 bytes back
in release" question rather than as part of a map cleanup. **Option 3 should not be started without a
parked-section design** covering how an out-of-closure module gets injected without a sigil edit;
without that, it buys 832 bytes and makes future injection harder than it is today.
