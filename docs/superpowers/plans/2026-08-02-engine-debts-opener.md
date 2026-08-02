# Engine-Debts Era Opener — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **STATUS 2026-08-02:** Parcel 1 EXECUTED + MERGED (aeon `8678ddb` / sigil `7e6ca108`,
> chain-23 `despawn-cascade`, strict 2990/0/4 own-run, oracle A/B in the evidence note).
> Parcel 2 CLOSED (already-shipped spec-§9 latch, 7k-frame churn soak PASS, ledger
> amended). Parcel 3 (PAL deletion) OPEN — next.

**Goal:** Close the two ruled Tier-1 engine debts — the children-never-freed dynamic-slot
leak (fix (a): despawn cascade) and the NTSC-only PAL-timestep deletion — plus formally
close the already-shipped mid-walk-compact (occupancy A2) ledger row.

**Architecture:** Two byte-changing parcels on the post-flip sigil toolchain (each gates
through the x6 build + strict suite + repin + sanctioned provenance refreeze), one
docs-only closure. Overseer/porter split: an Opus porter implements each parcel in an
isolated worktree from this plan; the overseer countersigns every gate with own runs and
does ALL oracle/emulator verification foreground (no emulator in subagents).

**Tech Stack:** sigil (sole toolchain; `SIGIL_BUILD`/`SIGIL_EMIT` env required by
`build.sh`), `.emp` sources, oracle MCP for live A/B, sigil strict suite
(`cargo test` in `/home/volence/sonic_hacks/sigil`), `crates/sigil-harness` refreeze +
`capture_goldens.sh`, `tests/repin_pins.rs` baselines.

**Rulings on file (Volence, 2026-08-02):** leak fix = (a) despawn cascades;
A2 = alloc-fail/latch family — SATISFIED by the shipped spec-§9 latch (see Parcel 2);
PAL = (B) NTSC-only, delete the dead timestep machinery.

---

## Ground truth (verified 2026-08-02, master `e03aad8`)

- `engine/objects/entity_window.emp:1455` `EntityWindow_DespawnObjects` — `.despawn`
  (line ~1504) calls `DeleteObject` only; untagged slots (all children, by
  construction — `AllocDynamic` tags `SLOT_TAG_UNTAGGED`, only the window spawn path
  re-tags) skip the walk at line ~1477. → children of a despawned parent leak
  permanently and keep dereferencing a freed `parent_ptr`. Gap-ledger row 1599 (sigil
  `docs/superpowers/notes/campaign-gap-ledger.md:1599`), status OPEN (Volence) — now ruled (a).
- `engine/objects/children.emp:527` `pub proc DeleteChildren (a0: *Sst)
  clobbers(d0-d2/a1) preserves(a0)` — walks the sibling chain, `jbsr DeleteObject`
  each child, clears the parent's `sibling_ptr`. Safe mid-walk: `DeleteObject` zeroes
  each child's live-list entry and the despawn walker null-guards zeroed entries
  (entity_window.emp:1471-1472). `pub proc`s resolve at whole-ROM link — **no `use`
  needed** (precedent: `test_parent.emp:187` calls `DeleteChildren` bare).
- `engine/objects/core.emp:115` `AllocDynamic` — the mid-walk-compact hazard is
  ALREADY FIXED: full-count spawns latch to `Dynamic_Live_Pending` (spec §9), drained
  by `DrainDynamicPending` (core.emp:365) at the RunObjects frame-end reconcile after
  `CompactDynamicLive` (which now runs ONLY at frame end, walk-flag-asserted,
  core.emp:315-322). Alloc-fail only when the latch is also full (`.latch_full`).
- `engine/system/boot.emp:208-225` — region detection writes `Timing_Step` (2 sites)
  and clears `Frame_Accumulator`; **zero readers** of either (grep-verified again:
  only ram.emp declaration + boot writes + constants). `DMA_Budget_Default` writes on
  the same branch ARE live (drain reads them) — keep.
- `engine/ram.emp:117-118` — `Timing_Step: u16`, `Frame_Accumulator: u16` (4 bytes,
  even-parity-neutral to delete). `engine/system/constants.emp:292-293` —
  `NTSC_TIMING_STEP` / `PAL_TIMING_STEP`.

## Gate procedure (per byte-changing parcel — overseer countersigns every step)

1. Aeon builds all four shapes: `SIGIL_BUILD=... SIGIL_EMIT=... ./build.sh` (sonic4
   plain), `DEBUG=1`, `./build.sh demo`, `DEBUG=1 ./build.sh demo`. Config-A/B via
   `sigil build --config-*` (see `capture_goldens.sh` header). Build must be from the
   parcel branch, artifacts freshness-checked (the stale-ROM trap).
2. Sigil strict suite own-run: expect repin baseline failures for shifted addresses →
   porter updates `tests/repin_pins.rs` baselines from the fresh `.lst` (repin is a
   deliberate hand-edit, literal pins are the independent drift detector). Suite must
   return to N/0/4 with N ≥ baseline 2990.
3. Overseer foreground oracle A/B (behavioral evidence, per parcel below).
4. Sanctioned refreeze: `cargo run --bin refreeze` (harness) after the x6 capture —
   chain 22 → 23 (parcel 1) → 24 (parcel 3), each entry named, with the A/B evidence
   recorded in the commit/note.
5. Merge to master only after overseer countersign; sequential merges, origin
   precondition; commit exact paths only (never `git add -A`).

---

## Parcel 1 — Despawn cascade (leak fix (a))

**Branch:** `fix-despawn-cascade` (porter works in an isolated worktree)

**Files:**
- Modify: `engine/objects/entity_window.emp:1442-1527` (`EntityWindow_DespawnObjects`)
- Modify (docs): `docs/BUGS.md` (new resolved entry), sigil
  `docs/superpowers/notes/campaign-gap-ledger.md:1599` (row close — overseer-side)

### Task 1.1: The cascade edit

- [ ] **Step 1: Edit `.despawn` to cascade before the delete.** In
  `engine/objects/entity_window.emp`, change:

```
    .clr_obj_skip:
        movea.l 12(sp), a0              // SST ptr (a0 slot of the movem frame)
        jbsr    DeleteObject
        movem.l (sp)+, d5-d7/a0/a2
```

to:

```
    .clr_obj_skip:
        movea.l 12(sp), a0              // SST ptr (a0 slot of the movem frame)
        jbsr    DeleteChildren          // cascade FIRST: free the sibling chain before
                                        // the parent (leak fix (a), gap-ledger row 1599).
                                        // Children are untagged -> this walker skipped
                                        // them; their live-list entries zero out and the
                                        // null-guard at .loop skips them. preserves(a0),
                                        // clobbers(d0-d2/a1) — all dead here.
        jbsr    DeleteObject
        movem.l (sp)+, d5-d7/a0/a2
```

- [ ] **Step 2: Update the proc header comment.** After the sentence ending
  "…duplicate when its section re-enters (its loaded bit died with the entry)." add:

```
// A despawned parent CASCADES: DeleteChildren runs before DeleteObject, so a
// window-managed parent's linked children die with it (they are untagged and
// could never despawn themselves — the row-1599 leak, fixed 2026-08-02).
```

  Also amend the walk-rail comment at :1463-1465 — replace "DespawnObjects only
  deletes (no alloc → no mid-walk compaction today)" with "DespawnObjects only
  deletes (DeleteChildren + DeleteObject — no alloc → no mid-walk compaction today)".

- [ ] **Step 3: Verify the clobbers contract still holds.** The proc declares
  `clobbers(d0-d7, a0-a3)`; `DeleteChildren` needs `d0-d2/a1` ⊆ that. No declaration
  change. Run a plain build to let the checked-clobbers lint prove it:
  `SIGIL_BUILD=<sigil>/target/release/sigil SIGIL_EMIT=<sigil>/target/release/emit_sound_blob ./build.sh`
  Expected: build succeeds, `s4.bin` produced.

- [ ] **Step 4: Build all four shapes** (gate procedure step 1). Expected: all succeed;
  ROMs differ from chain-22 goldens ONLY in the entity_window region + shifted
  downstream addresses (porter records sizes/CRCs for the overseer).

- [ ] **Step 5: Commit** (exact paths):

```bash
git add engine/objects/entity_window.emp
git commit -m "Parcel: despawn cascade — EntityWindow_DespawnObjects frees the sibling chain before the parent (leak fix (a), gap-ledger row 1599)"
```

### Task 1.2: Sigil-side repin (porter, sigil worktree)

- [ ] **Step 1: Run the strict suite**, collect repin failures:
  `cd /home/volence/sonic_hacks/sigil && cargo test` — expected: repin/pin tests
  referencing entity_window-downstream addresses fail with old-vs-new values.
- [ ] **Step 2: Update `tests/repin_pins.rs` (and `pins.rs` if a literal pin moved)**
  from the fresh aeon `.lst` values. Every changed number must be traceable to the
  parcel's shift; anything unexplained is a STOP.
- [ ] **Step 3: Re-run strict to green** (≥ 2990 pass / 0 fail / 4 ignored).
- [ ] **Step 4: Commit** on a sigil branch `fix-despawn-cascade` with the aeon pairing
  named in the message.

### Task 1.3: Overseer gates (FOREGROUND — no subagent)

- [ ] **Step 1: Own-run rebuild + strict suite countersign.**
- [ ] **Step 2: Oracle live A/B (the leak reproduced, then killed).** DEBUG ROM,
  ObjectTest (or any scene with a `TestParent` + children). Procedure: locate the
  parent slot (object list), poke `Sst.slot_tag` to a tracked value (0) and
  `Sst.entity_section_id` to an untracked id ($FE) so the next
  `EntityWindow_DespawnObjects` pass despawns it. PRE-FIX ROM: parent slot freed,
  children remain live (leak observed — `Dynamic_Live_Count` drops by 1 only).
  POST-FIX ROM: parent AND all chained children freed same frame
  (`Dynamic_Live_Count` drops by 1+N, children `code_addr`==0, free-stack SP grew by
  (1+N)*2). No walk-rail assert fires.
- [ ] **Step 3: x6 golden capture + refreeze** (chain 22 → 23, entry
  `despawn-cascade`), evidence recorded.
- [ ] **Step 4: Docs close-out:** BUGS.md entry (resolved), ledger row 1599 → CLOSED
  (sigil side), memory update. Merge both halves; push.

---

## Parcel 2 — Occupancy A2: verify-and-close (NO CODE)

The ruled fix family (alloc-fail / latch) is ALREADY SHIPPED as the spec-§9 latch:
`AllocDynamic` latches full-count spawns to `Dynamic_Live_Pending` (alloc-fail only at
latch-full), `CompactDynamicLive` runs only at the frame-end reconcile under a
walk-flag assert rail, `DrainDynamicPending` appends in alloc order with the §6-2/§6-3
post-state invariants. The live list is never mutated mid-frame by the alloc path.

- [ ] **Step 1 (overseer, FOREGROUND): DEBUG soak.** Run the ObjectTest scene ≥5 min
  under DEBUG; confirm the `Dynamic_Live_Walking` rail and the drain invariants never
  fire (they assert every frame in DEBUG).
- [ ] **Step 2: Close the ledger row** (sigil `campaign-gap-ledger.md:1060` A2 thread):
  record "ruled alloc-fail/latch 2026-08-02; verified shipped as spec-§9 latch; churn
  branch `churn-first-objecttest-a2` (aeon 835967d) is .asm-era and stays unmerged as
  historical evidence." Note in DEFERRED_WORK.md if an entry references A2 as open.
- [ ] **Step 3: Memory update** (overseer).

---

## Parcel 3 — NTSC-only: delete the dead PAL timestep (ruling B)

**Branch:** `pal-ntsc-only` (porter, isolated worktree)

**Files:**
- Modify: `engine/system/boot.emp:208-225`
- Modify: `engine/ram.emp:117-118` (delete two fields)
- Modify: `engine/system/constants.emp:292-293` (delete two consts)
- Modify (docs): `docs/DEFERRED_WORK.md` (PAL entry → RESOLVED (B); item 6 note),
  `docs/ENGINE_ARCHITECTURE.md` §0.8 (region detection: timestep half removed)

### Task 3.1: The deletion

- [ ] **Step 1: Sweep for readers first** (must be empty before deleting):

```bash
grep -rn "Timing_Step\|Frame_Accumulator\|TIMING_STEP" engine/ games/ tools/ --include="*.emp" --include="*.py" --include="*.asm"
```

  Expected: ONLY boot.emp writes, ram.emp declarations, constants.emp definitions.
  Any other hit is a STOP (surface to overseer).

- [ ] **Step 2: boot.emp** — replace lines 208-225 (region detection block) with:

```
        // Region detection (§0.8) — NTSC-only product ruling (2026-08-02, B):
        // the region-adaptive DMA budget IS consumed (the drain reads it); the
        // PAL fixed-timestep machinery (Timing_Step/Frame_Accumulator) had zero
        // readers and was deleted rather than left as dead scaffolding.
        move.b  HW_VERSION, d0
        move.b  d0, Hardware_Region
        andi.b  #$C0, d0                    // keep bits 7:6 (domestic/export, NTSC/PAL)
        move.b  d0, Region_Flags
        btst    #6, d0                      // bit 6 = PAL
        bne     .pal
        // Explicit `.w` dest kept: a link-imm source and a relaxable dest can't
        // share an instruction (core.emp kept-width class, gap-ledger row 1046).
        move.w  #DMA_BUDGET_NTSC, (DMA_Budget_Default).w
        jbra    .region_done
    .pal:
        move.w  #DMA_BUDGET_PAL, (DMA_Budget_Default).w
    .region_done:
```

- [ ] **Step 3: ram.emp** — delete the two fields:

```
    Timing_Step:            u16,
    Frame_Accumulator:      u16,
```

  (4 bytes removed, even alignment preserved — `Hardware_Region`/`Region_Flags` u8
  pair above stays even-paired with `Ctrl_1_Held`/`Ctrl_1_Press` following.)
  Check the surrounding comment block for references to the deleted fields and prune.

- [ ] **Step 4: constants.emp** — delete:

```
pub const NTSC_TIMING_STEP = $0100      // 1.0
pub const PAL_TIMING_STEP  = $0133      // 1.2 (6/5 ratio)
```

- [ ] **Step 5: Build all four shapes** (gate step 1). Expected: succeeds; every RAM
  symbol after `Frame_Accumulator` shifts −4 (large but uniform byte diff).
- [ ] **Step 6: Commit** (exact paths: the three engine files).

### Task 3.2: Sigil-side repin (porter) — same procedure as Task 1.2

- [ ] RAM-address pins (`CACHE_LEFT_COL` class) and any baselines carrying upper-RAM
  addresses all shift −4; update from the fresh `.lst`; strict back to green; commit.

### Task 3.3: Overseer gates (FOREGROUND)

- [ ] **Step 1: Own-run rebuild + strict countersign.**
- [ ] **Step 2: Oracle A/B (behavior-inert proof).** Boot DEBUG ROM: verify
  `DMA_Budget_Default` still seeded ($1C20 NTSC at the new address), controllers/
  streaming/sound sanity pass (60 s play), runtime-boot after RAM changes (the
  ram-alignment lesson). Frame-identical expectations: gameplay A/B unchanged vs
  pre-parcel ROM over a scripted input run.
- [ ] **Step 3: x6 capture + refreeze** (chain → 24, entry `pal-ntsc-only`).
- [ ] **Step 4: Docs:** DEFERRED_WORK PAL entry → RESOLVED (B) dated; item 6 marked
  decided (frame-based PAL slow accepted, NTSC-only); ENGINE_ARCHITECTURE §0.8
  updated (this also closes one row of the 2026-07-16 arch-drift list). Merge + push.

---

## Order & handoff

Parcel 1 → Parcel 2 (docs-only, can interleave) → Parcel 3. Sequential merges.
Porters: Opus agents, one per parcel, isolated worktrees, this plan is their spec —
they implement and report; they do NOT run the oracle, do NOT merge, do NOT refreeze.
Overseer: countersigns builds/strict own-run, runs all oracle gates foreground,
performs refreezes and merges, updates ledger/memory.
