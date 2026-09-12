# Entity-window C4a parcel — four stacked branches (2026-09-11/12)

A RECORD. Coordinates below are frozen at the SHAs they name.

**Base:** `origin/master` at `6763a40223d7a4a0ec812ec0324dc3fabe2b3f5c` when the stack was cut. Branch
0 was cut from it and each later branch from the previous tip, so they stack and must land in
order. **Assembler:** `sigil af35fa561663`, binary md5 `49ecc532e0b133ab0eab9447e071805c` before the
first build and after every one (nobody relinked it mid-run). **No emulator was run.** Every cycle
figure is DERIVED from sigil's own 68000 table (`crates/sigil-isa/src/m68k_cycles.rs`, the UM Table 8
rows) against capstone decodes of the built bytes, not measured.

**Byte pictures** are per shape against the branch's PARENT, from the ROMs `tools/landing_build.sh`
wrote (each run builds all four to temp names and renames them into place, so presence proves
freshness). The four ROMs were copied aside after every run and compared by a script (size, CRC32,
count of differing bytes). The control is a full landing run at the base itself (`finished=0`).

| shape | base `6763a402` size | CRC32 |
|---|---|---|
| `s4.bin` | 821123 | `52828985` |
| `s4.debug.bin` | 847389 | `ddf22eca` |
| `demo.bin` | 97075 | `c0898f05` |
| `demo.debug.bin` | 103359 | `80bbeb9b` |

**Why the ROM sizes barely move.** The ROM is placed by frozen tables, not by accumulation: a code
region that grows or shrinks moves every address inside that region, and the slack before the next
fixed region absorbs the difference. `EndOfRom` stayed `$BDDA0` (s4) through all four branches. The
only whole-ROM size change in this parcel (branch 3) is past `EndOfRom`, in the deb2 symbol appendix.

---

## Branch 0 — `parcel/ew-ensure-msg-0912` — tip `a6d99aa4024412179093afc044f2a9a8f3bd6a9a`

**Closes:** `docs/DEFERRED_WORK.md` "Side findings of the 2026-09-11 lens-tools parcel" item (a),
struck in the same commit. Not a ledger row.

**What changed:** the `COLLECTED_MASK_BYTES * 8 == MAX_LIST_ENTRIES` ensure message in
`engine/objects/entity_window.emp` said `tools/ojz_entity_gen.py`'s `MAX_LIST_ENTRIES` is compared by
no build step. `tools/test_ojz_entity_list_cap.py` compares it (since `2637d402`). The message now
names the test and its lane, and keeps the consequence for the builds that skip that lane.

**Verified:** the test has no `needs_build` marker (its own header), so it runs in build.sh's pre-build
`pytest -m "not needs_build"` call, which sits inside build.sh's `if NO_LINT == 0` block; `FAST=1`
sets `NO_LINT=1`. The one test that pins this message's text, `tools/ls8_pin_redproof.py`'s P1 GUARDS
fragment, pins its opening words, which did not change. Nothing else in tools/ or sigil quotes the
edited clause.

**Byte picture vs base:** all four shapes **IDENTICAL** (same sizes, same CRC32s as the table above).

**Landing:** `tools/landing_build.sh` exit 0, `finished=0`, `REAL_EXIT=0`. Pre-build pytest per shape
2436 passed / 2 skipped / 14 deselected (0 failed), four times; POST-SIGIL lane 14 ran / 0 deferred / 0
failed. Cross-module names: none. TAGs: none.

---

## Branch 1 — `parcel/c4a3-despawn-rollptr` — tip `ccc9a2beb553b8e9e7fb39b87ab84274e1f16809`

**Closes:** ledger **C4a-3**.

**What changed:** `EntityWindow_DespawnRings` rebuilt `&Ring_Buffer[index]` every iteration (a hand
×6 chain, a `lea`, an indexed read). It now walks `a2` down the buffer one `RING_BUFFER_ENTRY_SIZE`
per iteration, which is `RingCollision`'s walk. The setup multiply is `mul_const.w d0,
#RING_BUFFER_ENTRY_SIZE, d1` (CODING_CONVENTIONS 2.1), not a copy of RingCollision's hand chain.

**The safety argument was re-derived for this loop, not copied.** Both loops read in full. DespawnRings
walks `d5` from `Ring_Count-1` down to 0 with `dbf` and removes with `RingBuffer_Remove(d5)`, which
decrements `Ring_Count` and copies the entry at the new count (the old last index, never below `d5`)
into slot `d5`, or does nothing when `d5` was the last. So a removal rewrites only the slot under the
cursor, from an index already visited; entries below the cursor never move. The removed slot's new
occupant is not re-tested, exactly as in the index form. `a2` survives the remove path by the callees'
declared contracts (`EntityWindow_EntryForSection` d1/a0, `EntityLoaded_Clear` d0/d2/a0,
`RingBuffer_Remove` d1-d2/a0-a1); the declaration widens `a0-a1` to `a0-a2`, and the one caller
(`EntityWindow_Scan`'s tail) declares `a0-a4` and tail-jumps into `DespawnObjects`, which loads its own
`a2`. The loop-invariant Y band in the same loop (DEFERRED_WORK "Entity despawner micro-opts") is a
separate finding and was deliberately not taken.

**Encoding checked:** `move.w (a2),d1` = `3212`, `subq.w #6,a2` = `5d4a`, `adda.w d0,a2` = `d4c0`; sigil
elected `move.w d0,d1 / add.w d0,d0 / add.w d1,d0 / add.w d0,d0` for the ×6. `MAX_RING_BUFFER` = 128
read off the built `cmpi.b #$80, d4` in `RingBuffer_Add` (it is a define, not a const in any aeon file).
DespawnRings 140 → 144 bytes.

**Byte picture vs branch 0:** sizes unchanged in all four; content differs everywhere past the proc.

| shape | size | CRC32 | bytes differing from parent |
|---|---|---|---|
| `s4.bin` | 821123 | `2ba60500` | 17208 |
| `s4.debug.bin` | 847389 | `7b0c690e` | 25988 |
| `demo.bin` | 97075 | `f7db0d87` | 13237 |
| `demo.debug.bin` | 103359 | `9d412cfd` | 21321 |

**Cycles, derived:**

| | old | new |
|---|---|---|
| every iteration | `move.w d5,d0` 4 + `add.w` ×3 12 + `lea (xxx).w,a0` 8 + `move.w (a0,d0.w),d1` 14 = **38** | `move.w (a2),d1` 8 + `subq.w #6,a2` 8 = **16** |
| `check_active` read | `move.b 4(a0,d0.w)` 14 | `move.b 4(a2)` 12 |
| `check_y` read | `move.w 2(a0,d0.w)` 14 | `move.w 2(a2)` 12 |
| remove path, two reads | 14 + 14 | 12 + 12 |
| setup, once per call (non-empty buffer) | 0 | `move.w` 4 + `mul_const` 16 + `lea` 8 + `adda.w` 8 = **+36** |

So −24 per kept in-window ring, −26 per ring kept only by its active section, −28..−30 per removed
ring; net per frame ≈ 36 − 24N for N buffered rings. Break-even at N = 2 (N = 1 costs +12); about
−3.0 K cycles per frame at a full 128-entry buffer (~2.4 % of an NTSC frame). The seat's "~30/ring,
~600/frame shipped" is its own number; the shipped buffered count was not re-derived.

**Landing:** exit 0, `finished=0`, `REAL_EXIT=0`. Pre-build pytest 2436 passed / 2 skipped ×4, 0
failed; POST-SIGIL 14 ran / 0 deferred / 0 failed. Cross-module names: none. **TAG:** profile
`EntityWindow_DespawnRings` on OJZ act 1 before/after.

---

## Branch 2 — `parcel/c4a4-flatid-reuse` — tip `928cc052e1ef23aa1a38e9b16e26d496ecc0ac2b`

**Closes:** ledger **C4a-4**, both halves.

**Which fix, and why:** the preferred one (reuse the product) where there is a product to reuse, and
the written bound argument at the loop that is left. `Section_GetSecPtrXY` now returns the flat id it
computes (in `d0`), so `EntityWindow_BuildEntries` drops its `jbsr Section_FlatIDXY` on the next line.
Three callers need the id and no Sec pointer, so they keep `Section_FlatIDXY`, and its loop now carries
the bound argument (structural bound, what breaks it, the alternative named and not taken, executions
per frame). Converting that loop to `mul_bounded` was costed and not taken: on the shipped 3x3 grid the
mulu form costs 90 against the loop's 54 / 78 / 100 on rows 0 / 1 / 2, on a per-frame caller; the
loop's ceiling at `grid_h` = 16 is 386. The argument says to revisit when an act raises `grid_h`.

**Every caller, by call site (`jbsr`, engine/ + games/), before either contract changed:**
- `Section_GetSecPtrXY`: `Section_RedrawPlanes`, `Parallax_CheckBoundary`, `GameState_OJZScroll_Init`,
  `EntityWindow_BuildEntries`. All four branch on Z only; none reads `d0` as a value except BuildEntries,
  which now takes the id. `d4` (the new stride-multiply scratch) is dead across the call at all four and
  already declared by each.
- `Section_FlatIDXY`: `EntityWindow_Init`, `EntityWindow_Slide`, `GameState_OJZScroll_Update` (per frame),
  and BuildEntries (removed). The bound argument's premise, that every remaining caller derives `sec_y`
  from a clamped camera centre, was checked: `Camera_Init` clamps the seed and runs before
  `Section_Init` (`ojz_scroll_test.emp:677` before `:826`), `Camera_Update` clamps every frame, and the
  DEBUG warp path's `Section_Init` (`Debug_Warp_Consume`) follows `center_camera_on`, which clamps both
  ends. The act descriptor's `(GRID_H << SECTION_SIZE_SHIFT) <= $8000` ensure caps `grid_h` at 16.

**New contract:** `out(d0: SectionId, a0, zero: none) clobbers(d1-d2, d4)`. Found = Z clear (from the
`tst.l (a0)` that already guarded the Sec) with `d0` = the flat id; not found = Z set, `a0` = 0, `d0` = 0.
**The stride product builds in d1 with d4 as scratch, NOT d2**, although `d2` is declared clobbered:
`Parallax_CheckBoundary` stores `d2`/`d3` into `Parallax_Prev_Sec_X/Y` right after the call, relying on
the body rather than the declaration (see side finding 2). That warning is now in GetSecPtrXY's header.

**Encoding checked:** GetSecPtrXY 54 → 54 bytes (`moveq #1,d0` out, `move.w d0,d1` in; `move.w d1,d4 /
lsl.w #4,d1 / add.w d4,d1 / add.w d1,d1` for ×34; `d2` untouched). BuildEntries 146 → 142. FlatIDXY
unchanged (26 bytes; the argument is a comment).

**Byte picture vs branch 1:**

| shape | size | CRC32 | bytes differing from parent |
|---|---|---|---|
| `s4.bin` | 821123 | `675ed1aa` | 18102 |
| `s4.debug.bin` | 847389 | `9fb31f19` | 27017 |
| `demo.bin` | 97075 | `4c007cb6` | 14129 |
| `demo.debug.bin` | 103359 | `a524f1c8` | 22347 |

**Cycles, derived:** GetSecPtrXY's found path is unchanged (−4 +4), so every caller but BuildEntries
is unchanged. BuildEntries saves, per valid entry, the `bsr.w` (18) plus FlatIDXY's body: 54 at
`sec_y` = 0, 56 + 22·`sec_y` after (`moveq` 4, `moveq` 4, `move.b` 4, `subq` 4, `bmi` 8/10, per row
`add.w $4(a2),d0` 12 + `dbf` 10, `dbf` exit 14, `moveq` 4, `move.b` 4, `add.w` 4, `rts` 16). That is
−72 / −96 / −118 on rows 0 / 1 / 2, −404 at the `grid_h` ceiling; up to four valid entries per
BuildEntries run (init, and once per slide), so ~−336..−428 per slide on the shipped grid. A cold-path
saving whose point is that the per-slide cost no longer grows with `grid_h`.

**Landing:** exit 0, `finished=0`, `REAL_EXIT=0`. Pre-build pytest 2436 passed / 2 skipped ×4, 0 failed;
POST-SIGIL 14 ran / 0 deferred / 0 failed. Cross-module names: none new (GetSecPtrXY's contract widened
by `d4` and typed its `d0` out). **TAG:** a slide on OJZ act 1 before/after, confirming every tracked
entry's `ess_section_id` is unchanged (it now comes from GetSecPtrXY's `d0`).

---

## Branch 3 — `parcel/c4a2-findslot-hoist` — code commit `cd5a38c887dcff8db6323c25f1fd1b59d623a83f`, tip = the commit that adds this note

**Closes:** ledger **C4a-2**.

**What changed:** the spawn gates ran `Collected_FindSlot`'s 9-slot tag scan for every candidate that
reached the collected (rings) / killed (objects) gate, through `Collected_CheckRing` /
`Killed_CheckObject`, although `a1` (so the section and its slot) is fixed for a whole walk. Now each
walk caches the slot in `a4`, lazily: the five walkers (`ScanRingsRight`, `PopulateSectionRings`,
`RescanRings`, `ScanObjectsRight`, `RescanObjects`) zero `a4`; `TrySpawnRing` / `TrySpawnObject` look the
slot up at the first candidate that reaches the gate, cache it, and every later candidate is one `btst`
against it. A section with no slot leaves `a4` = 0 and pays the scan each time, as before (unreachable
in sonic4, whose 9 slots cover the 3x3 keep-neighbourhood holding the tracked 2x2; demo spawns nothing).
`Collected_CheckRing` and `Killed_CheckObject` are deleted, with a three-line pointer where they were.

**Lazy, not the eager hoist the seat described, and why.** An eager hoist (one scan per walk, always)
charges a walk in which no candidate reaches the gate a full scan, ~94 + 34k cycles, where today it pays
nothing. That walk is common: a right-edge walk over rings a slide populate already loaded, a rescan that
brings nothing new into the band. The lazy cache costs such a walk 8 cycles (`suba.l a4,a4`) and is never
worse than today by more than that.

**The contract is `inout(a4: u32)`, and the first attempt was wrong.** Declared as `(a4: u32) ...
out(a4)`, both FAST shapes failed sigil's contract closure: `[proc.out-unverified]` "EntityWindow_TrySpawnRing
:: out(a4) (got 1, want 0)", and the same for TrySpawnObject. `out()` needs a production on every return
path with no param seed, and a lazily filled cache passes through unchanged on most paths. That is
sigil's `inout` facet exactly (`contract_baseline.rs`: "PASS-THROUGH (no write) is contract-valid"; its
`INOUT_UNVERIFIED_BASELINE` is empty), the shape `DrawRings` and `PageCache_PatchRun_Seq` already use. With
`inout` both shapes build green and the warning census is identical to the base in both (release 165,
debug 152, same breakdowns). No sigil baseline change was needed.

**The seat's two claims, verified from the code:**
- *"Nothing moves a slot during a walk"* — **holds.** `Ring_Collected_Window` is referenced only by
  `engine/ram.emp`'s declaration and this module. Its writers: `Collected_Init`, `Collected_ClaimSlot`
  (+ `Collected_UnparkSlot`, `clear_slot_bitmasks`), `Collected_UpdateCenter` (+ `clear_slot_bitmasks`),
  and the bit setters `Collected_MarkRing` (from `RingCollision`) and `Killed_MarkObject`. The first
  group runs only from `EntityWindow_Init`, `EntityWindow_BuildEntries` and `EntityWindow_Slide`, each
  finishing before any walk it starts; nothing a walk calls (`EntityLoaded_*`, `Collected_FindSlot`,
  `RingBuffer_Add`, `Load_Object`, `AllocDynamic`) reaches them; the bit setters change bits, not which
  slot holds a section. `Load_Object` does not run object code (read in full).
- *"The walkers have a free address register"* — **half right.** `a2` is free in the ring walkers but
  not in the object path (`TrySpawnObject` loads the type table into `a2`; `Load_Object` clobbers
  `a2`/`a3`). `a4` is free in all five and survives every callee by their closure-checked contracts.
  The five walkers and `RescanY` widened (`a0-a3` → `a0-a4`); `Scan`, `Init`, `Slide` already declared
  `a0-a4`.

**Encoding checked (both FAST shapes, capstone):** `move.l a4,d0` = `200c`, `movea.l a0,a4` = `2848`,
`btst d4,$2(a4,d1.w)` = `09341002` (`$12` for the killed half).

**Byte accounting, s4 release, entity_window code region (per-symbol diff of the two listings):**

| symbol | before | after | Δ |
|---|---|---|---|
| `Collected_CheckRing` | 26 | — | −26 |
| `Killed_CheckObject` | 26 | — | −26 |
| `Collected_ClaimSlot` | 76 | 74 | −2 (no source change: its `jbsr Collected_FindSlot` relaxed `bsr.w` → `bsr.b`, the deleted 52 bytes having sat between them; 18 cycles either way) |
| `EntityWindow_TrySpawnRing` | 116 | 128 | +12 |
| `EntityWindow_TrySpawnObject` | 180 | 192 | +12 |
| five walkers | | | +2 each (+10) |
| **total** | | | **−20** |

`EndOfRom` unchanged (`$BDDA0`). The whole-ROM growth is all past it, in the deb2 symbol appendix, and
goes with the listing's name set changing (−4 names: the two procs and their `$uncollected` / `$alive`
locals; +2: the two `$have_slot` locals). The appendix mechanism was not dissected.

**Byte picture vs branch 2** (landing run at the code commit `cd5a38c8`):

| shape | size | Δ size | CRC32 | bytes differing from parent | `EndOfRom` |
|---|---|---|---|---|---|
| `s4.bin` | 821155 | +32 | `c489a42a` | 51339 | `$BDDA0`, unchanged |
| `s4.debug.bin` | 847423 | +34 | `d398e2e6` | 74485 | `$C1602`, unchanged |
| `demo.bin` | 97109 | +34 | `b5df5871` | 33763 | `$1121A`, unchanged |
| `demo.debug.bin` | 103393 | +34 | `2cf9d0e9` | 48075 | `$1121A`, unchanged |

`EndOfRom` did not move in any shape, so every size delta is in the deb2 symbol appendix past it.

**Landing at `cd5a38c8`:** exit 0, `finished=0`, `REAL_EXIT=0`. Pre-build pytest 2436 passed / 2 skipped
×4, 0 failed; POST-SIGIL 14 ran / 0 deferred / 0 failed.

**Cycles, derived**, per candidate reaching the collected/killed gate, section in window slot k (0..8):

| path | old | new |
|---|---|---|
| slot already cached | — | `move.l a4,d0` 4 + `bne` 10 + `move.w` 4 + `lsr.w #3` 12 + `btst Dn,d8(An,Xn)` 14 = **44** |
| first lookup of the walk / every candidate before | caller setup 38 (`move.b` 12, `moveq` 4, `move.w` 4, `bsr.w` 18) + CheckRing 108 (`movem.l` 16, `bsr` 18, `movem.l` 20, `beq` 8, `move.w` 4, `lsr.w` 12, `btst` 14, `rts` 16) + FindSlot 50 + 34k = **196 + 34k** | 4 + 8 + `move.b` 12 + `bsr` 18 + FindSlot 50 + 34k + `beq` 8 + `movea.l` 4 + 4 + 12 + 14 = **134 + 34k** |
| section has no slot (every time) | 472 | 394 |

(FindSlot per the base bytes: `lea` 8 + `moveq` 4, 34 per slot missed, hit 18 + `moveq` 4 + `rts` 16. The
closing `bne`, 8 or 10, is common to both and left out.) So −152 − 34k per cached candidate, −62 for
each walk's first, −78 with no slot; +8 per walker call. Worked example: a slide populating a section
with 12 in-band new rings in slot 4 (OJZ act 1's maximum is 12 rings per section): the ring walk goes
from ~4080 to ~858 cycles on that frame. The floor: a coarse-row crossing where every candidate is
loaded pays +8 × up to 8 walker calls = +64.

This derivation sits a constant 18 cycles under LS-6's quoted 222..494 for the whole old gate; the
34-per-slot slope agrees. Not reconciled.

**Also in the branch:** the `MAX_LIST_ENTRIES` ensure message named the deleted procs as mask-addressing
sites; it now names the two gates (its opening words, the P1 fragment, unchanged). ARCH §4.9 (per-frame
scan, 4.9.5's pseudo-API) and DEFERRED_WORK "RescanY burst is unbudgeted" updated: the burst's SHAPE is
untouched and still unbudgeted.

**Cross-repo, required before or with landing:** sigil `crates/sigil-cli/tests/preserves_corpus.rs:138-139`
name `Collected_CheckRing` and `Killed_CheckObject` as residue witnesses, and its `residue_status` does
`panic!("proc {proc} not found")`, so `residue_procs_verify_as_predicted` FAILS against any aeon tree
carrying this branch until those two rows go (the non-vacuity count derives from `cases.len()`). It is
not a build dependency: aeon's own build is green. Cross-module names: none new.

**TAG:** on OJZ act 1, a slide into a ring-bearing section and a coarse-row crossing, before/after: the
same rings spawn, collected rings stay collected, and the cycle counts of `PopulateSectionRings` / `RescanY`.

---

## For every byte-moving branch (1, 2, 3)

Sigil's `entity_window_port` byte-gates the whole `entity_window` region, `section_port` and
`parallax_port` pin `Section_GetSecPtrXY`, and `repin.toml` lists the section symbols: the routine
repin + refreeze ritual applies to each. No branch adds a name referenced across modules.

## Things the brief said that the tree disagrees with

1. **C4a-4's cost formula is the wrong loop.** The row prices FlatIDXY's loop at "24 + 14·sec_y". That
   is `mul_bounded`'s word-form loop (a register add). FlatIDXY's loop adds from memory
   (`add.w Act.grid_w(a2), d0`, 12 cycles, not 4); the proc costs 54 at row 0 and 56 + 22·row after.
2. **C4a-2's "free address register" is half right**, and its eager hoist would lose on common walks
   (above). The lazy form is what shipped.
3. **C4a-2's object path uses `Killed_CheckObject`**, confirming C4a-1's landing note that the finding's
   single-symbol naming was loose.
4. **C4a-3's "~30 cycles per ring"** derives to 24..30 here, depending on the path.

## Side findings, booked here, not fixed

1. **`tools/landing_build.sh` exits 1 with no `finished=` stamp when `SIGIL_BUILD` is unset** —
   DEFERRED_WORK's lens-tools side finding (b), reproduced in this parcel: the first branch-0 run was
   launched from a shell that had not exported the two variables, died at the `:?` expansion on line 59,
   and trailed `REAL_EXIT=1` with no stamp.
2. **`Parallax_CheckBoundary` relies on `Section_GetSecPtrXY` preserving `d2`, which the declaration says
   it clobbers.** It stores `d2`/`d3` right after the call. The contract closure does not flag a read of
   a declared-clobbered register, so any future body change that uses `d2` would silently corrupt the
   parallax crossing detector. Branch 2 keeps the body off `d2` and says so in the header.
3. **Same class in the ring walkers:** `EntityWindow_TrySpawnRing` declares `a0` clobbered and its header
   says "no caller relies on it", but all three ring walkers advance `a0` after the call
   (`addq.w #RING_LIST_ENTRY_SIZE, a0`) and rely on it surviving (it does: the body restores it).
4. **`Killed_MarkObject` has no caller in `engine/` or `games/`.** The killed mask is never set, so the
   killed gate always answers "alive" today.
5. **A third copy of the flat-id product** sits in `engine/level/tile_cache.emp` (`mul_bounded.w d3, d1,
   #MAX_ACT_SECTIONS`), outside this parcel.
6. **Wall clock is not quoted:** the builds ran at load average 9 to 15 on 16 cores.

## Master moved during the run

`origin/master` went from `6763a402` to `ee52a9ea` (18 commits, fetched into the shared repository by
another session) while this stack was being built. Those commits touch neither
`engine/objects/entity_window.emp` nor `engine/level/section.emp`; they do touch `docs/DEFERRED_WORK.md`
and `docs/ENGINE_ARCHITECTURE.md`, and add notes. `git merge-tree --write-tree --name-only origin/master
parcel/c4a2-findslot-hoist`, run at the code commit `cd5a38c8`, reported a clean tree (`e0922f1f`) and no
conflicts; this note is a new file and cannot conflict. That is a TEXTUAL result. The byte pictures above
are against each branch's parent on the old base, and master carries its own byte-moving commit (the red
spring's coil palette index), so the merged ROMs match neither: landing evidence has to be taken on the
merged tree.

## Proposed ledger lines (the controller appends at landing; `fixedAt` = the merge SHA)

```json
{"id": "C4a-3", "at": "<stamp at append>", "sweep": {"date": "2026-09-06", "packet": "docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md", "sha": "9cfebb72", "pin": "61f22403"}, "seat": "C4a", "severity": "low", "title": "The despawner rebuilds an address its sibling walks with a pointer, and the sibling states the cure", "state": "fixed", "fixedAt": "<merge>", "where": {"path": "engine/objects/entity_window.emp"}, "detail": "FIXED by parcel/c4a3-despawn-rollptr (commit ccc9a2be), evidence docs/superpowers/notes/2026-09-12-entity-window-c4a-parcel.md. EntityWindow_DespawnRings walks a2 down Ring_Buffer one RING_BUFFER_ENTRY_SIZE per iteration instead of rebuilding &Ring_Buffer[index]. RingCollision's swap-with-last safety argument was re-derived against this loop rather than copied (RingBuffer_Remove rewrites only the slot under the cursor, from an already-visited higher index). Setup via mul_const. DERIVED, not measured: -22 cycles every iteration plus 2-8 on the reads, +36 once per call, ~-3.0K cycles/frame at a full 128-entry buffer. DespawnRings 140 -> 144 bytes; ROM sizes unchanged (frozen placement). The Y-band invariant in the same loop (DEFERRED_WORK 'Entity despawner micro-opts') is a separate finding and still open."}
{"id": "C4a-4", "at": "<stamp at append>", "sweep": {"date": "2026-09-06", "packet": "docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md", "sha": "9cfebb72", "pin": "61f22403"}, "seat": "C4a", "severity": "low", "title": "A value is computed, discarded, and immediately recomputed by a loop whose cost grows with the world size", "state": "fixed", "fixedAt": "<merge>", "where": {"path": "engine/level/section.emp"}, "detail": "FIXED by parcel/c4a4-flatid-reuse (commit 928cc052), evidence docs/superpowers/notes/2026-09-12-entity-window-c4a-parcel.md. Section_GetSecPtrXY returns the flat id it computes in d0 (found = Z clear; the 1/0 flag is gone) and EntityWindow_BuildEntries dropped its Section_FlatIDXY recompute. Every caller of both routines was enumerated by call site. FlatIDXY keeps three callers that need no Sec pointer; its loop now carries the written bound argument (sec_y <= grid_h - 1 <= 15 through the camera clamp; mul_bounded costed and not taken on the shipped grid, revisit when grid_h rises). GetSecPtrXY's stride scratch is d4, NOT d2: Parallax_CheckBoundary relies on d2 surviving against the declaration. DERIVED: -72..-118 cycles per valid entry per BuildEntries run on the shipped grid; GetSecPtrXY unchanged. BuildEntries -4 bytes. The row's '24 + 14*sec_y' was mul_bounded's loop, not FlatIDXY's (56 + 22*sec_y)."}
{"id": "C4a-2", "at": "<stamp at append>", "sweep": {"date": "2026-09-06", "packet": "docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md", "sha": "9cfebb72", "pin": "61f22403"}, "seat": "C4a", "severity": "medium", "title": "A per-entry answer is recomputed for every candidate inside the walk", "state": "fixed", "fixedAt": "<merge>", "where": {"path": "engine/objects/entity_window.emp"}, "detail": "FIXED by parcel/c4a2-findslot-hoist (commit cd5a38c8), evidence docs/superpowers/notes/2026-09-12-entity-window-c4a-parcel.md. The collected/killed slot is looked up at most once per WALK, lazily, and cached in a4, declared inout (out(a4) failed sigil's [proc.out-unverified]: a lazily filled cache passes through unchanged on most paths, which is inout's pass-through); every later candidate is one btst. Collected_CheckRing and Killed_CheckObject deleted. The seat's claims were checked: nothing a walk reaches moves a slot (writers enumerated) holds; 'the walkers have a free address register' is half right (a2 is not free in the object path; a4 used). Lazy chosen over the seat's eager hoist, which charges a full scan to walks where no candidate reaches the gate. DERIVED: -152-34k cycles per cached candidate, -62 for a walk's first, +8 per walker call. entity_window code -20 bytes; ROM sizes +32 (s4) / +34 (other three), all in the deb2 appendix past an unchanged EndOfRom. REQUIRES a sigil edit: crates/sigil-cli/tests/preserves_corpus.rs:138-139 name the two deleted procs and panic when a named proc is missing."}
```
