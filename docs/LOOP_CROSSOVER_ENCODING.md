# Loop crossover encoding — the cross-repo anchor

**Status:** design anchor, **BUILT as of 2026-09-02** (`parcel/loop-crossover` aeon
`8a4313b5` for the bake, `parcel/loop-crossover-read` aeon `602170f7` for the engine). This
document exists so Aurora's paint tool and Aeon's engine parcel can be built against the
same contract without either waiting for the other.

**BOTH HALVES ARE BUILT.** §5 rows 1-12: a painted crossover travels from the editor file
through `bake_plane_cell`, into the attr-set's dedup key, out as `crossover.bin`, and into
the ROM as `CrossoverTable`. §5 **row 13**: `Player_LoopCrossover` reads that table once per
player per frame and writes `Sst.layer`. Rules R1-R6 are all built.

**ALL FOUR CLAIMS ARE NOW TRUE — AMENDED 2026-09-04.** This paragraph used to say the
opposite, and the sentence it turned on ("all 256 slots of the shipped `CrossoverTable` hold
`XOVER_NONE`") has expired: the table now holds **two** marked slots, section 0 carries loop
geometry with four painted marks (see §11 and §12), and a player has been driven through one.
**Four claims, and say which one you mean: the bytes reach the FILE · they reach the ROM ·
the engine READS them · a player MOVES.** The first three are proved by EXECUTING the built
ROM's own bytes (`tools/loop_crossover_gate.py` varies one byte of `CrossoverTable` in the
ROM image with every other input held fixed and requires `Sst.layer` to follow it, which
separates "readable" from "consumed"); the fourth by `tools/loop_step_over_witness.py`, which
drives a real player over the painted mark on a real ROM.

**Driving him is also what found the step-over defect** — the read site sampled once per
frame against a one-cell mark, so above ~8 px/frame the mark was invisible and the player ran
straight through the loop and fell through a floor a screen later. Fixed 2026-09-04; **§12**
is the whole account.

**Read the §5 and §7 tables' status columns for what exists** — every row carries its own
verdict and the commit that earned it. Do not read any prose in this document, including
this paragraph, as a substitute; §8.2 records at length what it cost the last time a design
split was read as a status report, and a paragraph is exactly what goes stale first.

Earlier, ahead of the rest: the named `XOVER_*` constants and §6 change (6)'s preservation
rule, landed on `fix/repaint-preserve-crossover` because the violator it names is a
committed tool that writes the owner's live tree and would have silently eaten the first
painted crossover. See §3.4 and §7 R4.

**Measured against:** aeon `fde35b2f` (`data(ojz): repaint the collision cells that made
Knuckles fall through the floor`), worktree clean for
`games/sonic4/data/editor/**` and `games/sonic4/data/collision/**`. Every number in this
document was taken at that commit. See §10 for what that invalidates in older documents.

**Supersedes:** `docs/decisions.jsonl` `d-39` (withdrawn by `d-39-corrected`). This document
is the corrected answer `d-39-corrected` promised. Nothing in `d-39`'s three options
survives unmodified.

**Provenance limit, LIFTED 2026-09-04.** This used to read *"no loop geometry exists anywhere
in OJZ act 1 ... this encoding has therefore not been validated against real geometry and
cannot be until a throwaway test loop is painted."* Section 0 now has a loop and four painted
marks (§12 gives their world coordinates), and the encoding has been driven end to end on a
real ROM. Claims below that were derived from source and from non-loop content are still
labelled as such — read each section's own status line, not this one.

---

## 1. The answer in one line

**One new field is needed, and only one.** The existing two-plane solidity already expresses
*"solid on both planes"* — the authoring convenience — with no encoding change at all; it
does **not** and cannot express *"standing here moves you to the other path"*, because
solidity is a property of the surface and layer is a property of the player.

---

## 2. The live hypothesis, split

`d-39-corrected` raised the possibility that the cell word may already express the state
`d-39` was about to add. It splits into two claims. One is true and shrinks the work; the
other is false and is the whole reason this field exists.

### 2.1 TRUE — "solid on both planes" needs no field, and is already in use

Aurora writes **two independent files per section**: `section_N.collattr.bin` (plane A) and
`section_N.collattrb.bin` (plane B), each 256×256 cells of one 16-bit big-endian word
(`tools/ojz_strip_gen.py`, `apply_editor_collision_overlay`). A cell that is solid on both
planes is simply a cell whose solidity field is non-zero in *both* files. The bake already
handles it: `apply_editor_collision_overlay` reads `wa` and `wb` independently and interns
each through `bake_plane_cell`.

This is not theoretical. Measured at `fde35b2f`, OJZ act 1 section 0:

| quantity | cells |
|---|---|
| solid on plane A | 1792 |
| solid on plane B | 1100 |
| **solid on BOTH planes** | **1056** |
| solid on A only | 736 |
| solid on B only | 44 |
| bits 15:14 non-zero, either plane | **0** |

(Sections 1–8 are entirely unauthored on both planes; bits 15:14 are zero in all 18 files.)

So the third state Sonic Worlds Next names (`docs/research/loops-and-sprite-rotation.md`
§10.4) and that `loops-and-sprite-rotation.md` §5.2 wanted Route P to add **is already the
representation**, and the owner is already authoring 1056 cells of it. What is missing is
*ergonomic*: an author must paint it into two files. That is an Aurora brush affordance
(one stroke, two words) and it needs **zero** bits, zero bake change, and zero engine
change. Aurora can ship that half immediately, independently of everything else here.

### 2.2 FALSE — the layer transition needs a field, and here is the demonstration

The burden is to show what reads a cell and writes `Sst.layer`. The answer is: **exactly one
thing does, and it is the object.**

Enumerating every access to the field (`Sst.layer`, `engine/objects/sst.emp`, declared
`layer: u8 @ $2D` — "collision layer select (0 = path A, 1 = path B)"):

| site | direction |
|---|---|
| `games/sonic4/objects/path_swap.emp` `PathSwap_Main` (`move.b d0, Sst.layer(a1)`) | **WRITE** — the only one |
| `games/sonic4/player/player_common.emp` `clr.b layer(a0)` (player init) | write (clear) |
| `player_sensors.emp` × 3, `player_climb.emp` × 4, `player_glide.emp` × 1 (`move.b layer(a0), d3`) | read → probe |

Every read feeds `d3` into `Collision_GetType` (`engine/level/collision_lookup.emp`), whose
only use of `d3` is `tst.b d3 / beq / addi.w #TILE_CACHE_COLL_SIZE, d1` — a *plane select on
the fetch*. It returns a byte. It writes nothing.

And what that byte can mean is closed: it is an index into an interned set whose key is
exactly `(heights, angle, solidity)` — `AttrSet.intern` in `tools/collision_pipeline.py`.
Two cells that differ only in some other property intern to the *same index*, so no
downstream table can distinguish them. The four tables the index addresses are
`HeightMaps`, `HeightMapsRot`, `AngleTable`, `SolidityTable`
*(the key is a 4-tuple since `8a4313b5` — `(heights, angle, solidity, xover)` — and there is
a fifth table, `CrossoverTable`. **That change does not weaken the argument in this section,
it is the argument's conclusion carried out:** the reason a field was needed is exactly that
no existing member of the key could carry the transition, and widening the key is how the new
one reaches a table at all. Nothing here about SOLIDITY has changed.)*
(`games/sonic4/data/collision/collision_data.emp`), consumed by `probe_core`
(`player_sensors.emp`), which uses `SolidityTable[attr] & d6` purely as a *class gate*
(pass → surface, fail → `.cl_air`).

**Therefore:** no assignment of solidity bits — on either plane, in any combination,
including "solid on both" — can change `Sst.layer`. Solidity decides whether a surface
stops you. It has no channel to the player's path membership. If the hypothesis were read as
covering the crossover, Route P's purpose evaporates and the object survives, which is the
opposite of the owner's steer.

**One field. The transition. That is the entire anchor.**

---

## 3. THE ANCHOR — the four facts Aurora needs

### 3.1 Which bits of which word — and which baker

This is the fact `d-39` got wrong, so it is stated with the baker named, per Aurora's own
correct objection that *"bits 15:14" without naming the baker is not an anchor*.

`tools/collision_pipeline.py` contains **two bakers over two different 16-bit word
encodings.** They are disjoint word spaces that happen to share a file:

| | `bake_cell` — the **donor chunk-entry word** | `bake_plane_cell` — **Aurora's per-plane cell word** |
|---|---|---|
| written by | sonic_hack chunk map (`load_chunk_map`) | Aurora, `section_N.collattr.bin` / `.collattrb.bin` |
| read by | `ojz_strip_gen.build_section_collision` | `ojz_strip_gen.apply_editor_collision_overlay` |
| bits 9:0 | block id | shape index into the S&K base bank |
| bit 10 / 11 | X-flip / Y-flip | X-flip / Y-flip |
| bits 13:12 | **path A** solidity (`PATH_A_SOL_SHIFT`) | **this plane's** solidity (`PLANE_SOL_SHIFT` since `8a4313b5`; it used to reuse `PATH_A_SOL_SHIFT`) |
| bits 15:14 | **path B solidity — LIVE (`PATH_B_SOL_SHIFT = 14`)** | **`XOVER` — LIVE since `8a4313b5` (`XOVER_SHIFT = 14`); it was dropped by the bake before that** |
| returns | *two* attr bytes (A, B) from one word | *one* attr byte |

> **THE FIELD LIVES IN `bake_plane_cell`'S WORD ONLY.**
> Bits 15:14 of the **donor** chunk-entry word are path-B solidity and must never be touched.
> Writing a transition value there would silently make ordinary ground solid on a path the
> author never painted. That is the `d-39` failure, preserved here so it cannot recur.

**The field, named `XOVER`:**

- **Word:** Aurora's per-plane collision cell word — the one `bake_plane_cell` consumes.
- **Bits:** **15:14**, 2 bits, `XOVER_SHIFT = 14`, `XOVER_MASK = 3`.
- **Files:** `games/sonic4/data/editor/ojz/act<N>/section_<S>.collattr.bin` (plane A) and
  `section_<S>.collattrb.bin` (plane B), same 16-bit big-endian cell word, same bit
  positions in both.

~~A naming hazard worth fixing in the same parcel: `bake_plane_cell` currently reads
*this plane's* solidity through the constant named `PATH_A_SOL_SHIFT`.~~ **FIXED `8a4313b5`:**
`PLANE_SOL_SHIFT = 12` exists for the per-plane word and `bake_plane_cell`,
`repaint_ojz_collision.py` and the tests all spell it. The two encodings no longer share a
constant name. See §6, change (0).

### 3.2 What each value means, including zero and the reserved one

| value | name | meaning |
|---|---|---|
| `0` | `XOVER_NONE` | **No crossover.** The player's `Sst.layer` is not touched by this cell. |
| `1` | `XOVER_TO_A` | Set the resolving object's `Sst.layer` to **0 (path A)**. |
| `2` | `XOVER_TO_B` | Set the resolving object's `Sst.layer` to **1 (path B)**. |
| `3` | **RESERVED** | **Illegal. The bake hard-errors.** Never emitted, never accepted. |

**Zero is "no crossover", and this is load-bearing rather than incidental.** All 18 shipped
plane files hold zero in these bits for all 65 536 cells each (measured, §2.1), so an
unpainted cell, an erased cell, and a cell from before this field existed all mean the same
thing and all mean *nothing happens*.

**Value 3 is reserved because of Aurora's sentinel trap, which is real here.** Top-of-range
is a sentinel across aeon encodings, so a producer that clamps a value into range lands on
3. If 3 were "toggle" — the semantically obvious fourth value — a clamping bug would author
*the most destructive value in the set*, one that fires on every crossing regardless of
which path you are on. Making 3 a hard bake error converts that class of bug from a silent
gameplay defect into a build failure. The cost of reserving it is that the field has no room
to grow; §9 explains why that cost is smaller than it looks and where growth would come from
instead.

**Toggle is not omitted for safety, it is omitted because it is redundant.** See §3.3.

### 3.3 Which plane's word carries it — **both, independently**

**Rule: the mark is read from the plane the player is currently on.**

A plane-A word's `XOVER` fires only for an object whose `Sst.layer == 0`; a plane-B word's
only for `Sst.layer == 1`. This falls directly out of the runtime read: the engine calls
`Collision_GetType(x, y, layer)` and only ever sees the current plane's byte. It cannot see
the other plane's without a second lookup, and paying for one would be a design choice with
no benefit.

This is what makes a **two-way loop** work with absolute values and no direction field, and
it answers the objection in `loops-and-sprite-rotation.md` §4.5.1 (*"no purely positional
bake can be correct for a two-way loop"*). §4.5.1 is right that the decision depends on
history — and the player's **current layer is that history**, already stored, already
per-object.

Worked, with the classic split (each plane holds one half of the circle; the ground under
the loop is solid on **both** — which is exactly why §2.1's "solid on both" matters):

- plane **L** = ground + LEFT half of the loop. plane **R** = ground + RIGHT half.
- Two marked columns: the loop's bottom-centre cell and its top-centre cell. At each, the
  plane-L word carries `XOVER_TO_B` and the plane-R word carries `XOVER_TO_A`.

| traversal | at bottom-centre | at top-centre | result |
|---|---|---|---|
| rightward | on L (ground) → R | on R → L | ascends the right half, descends the left half ✓ |
| leftward | on R (ground) → L | on L → R | ascends the left half, descends the right half ✓ |

Same cells, same values, opposite outcomes, decided entirely by which plane the player was
already on. A **toggle** value would produce the identical behaviour here, which is why it is
redundant: a per-plane pair `{TO_B on A, TO_A on B}` *is* a toggle, and the pair
`{TO_B on A, NONE on B}` is an absolute one-way force that a toggle cannot express — enter
from plane A and you are sent to B; arrive already on B and nothing happens. The per-plane
pair strictly dominates.

> **⚠ CORRECTED 2026-08-29, hours after this section was written.** This paragraph first
> spelled the one-way force as `{TO_B, TO_B}`, which is **a hard build error under the very
> next paragraph**: the second element is plane B carrying `XOVER_TO_B`, a self-mark, which
> R2 refuses. An author following the doc literally would have reddened their build, and the
> illustrative example would have been the thing that did it. Found by the editor lane
> reading the two paragraphs against each other while building their brush — which is the
> only way it could have been found, since **nothing executes a document**. The *conclusion*
> (per-plane pairs strictly dominate a toggle) was never in doubt and is unchanged; only the
> example was wrong. Recorded rather than silently edited, because a spec that contradicts
> itself four lines apart is worth knowing about even after it stops doing so.

> **⚠ AMENDED 2026-09-05 — the worked table above is the ENCODING, and the encoding alone
> is not sufficient.** Nothing in this section changes: the bits, the values, the per-plane
> rule and rule R2 are all exactly as written. What changed is the READ SITE. The table's
> two rows quietly assume that a player arriving at the bottom centre on plane L is
> travelling rightward and one arriving on plane R is travelling leftward — and R2 makes
> that assumption unfalsifiable from the paint, because a plane-A cell can only ever carry
> `XOVER_TO_B`. `docs/witness/loop-plane-b-exit-2026-09-05.json` measured what actually
> happens: a LEFTWARD player on plane A read `XOVER_TO_B` at the bottom centre, was moved
> onto the plane whose left half is not solid, and fell through the floor. Every traversal
> tested toggled the layer exactly once, in both directions.
>
> `Player_LoopCrossover` is therefore **direction-keyed** as of the owner's ruling that day:
> a mark fires only when the player's screen-space `Sst.x_vel` is heading for the arc that
> mark leads onto — `XOVER_TO_B` rightward, `XOVER_TO_A` leftward, neither at zero. The
> table's LEFTWARD row is then correct end to end. **Its RIGHTWARD row is still not**, and
> that is a paint problem, not a runtime one: a centre mark is crossed TWICE by a completing
> circuit, and the rightward entry and exit are the same cell, the same plane and the same
> direction, so no stateless rule can give them opposite answers. Sonic 2 resolves it with a
> return-to-default swapper past the exit foot. Booked in `docs/DEFERRED_WORK.md`.
>
> The commentary block on `Player_LoopCrossover` (5b) carries the rule, the argument for
> `x_vel` over `PlayerV.ground_speed`, and the cell-by-cell circuit analysis.

**Self-marks are illegal.** A plane-A cell carrying `XOVER_TO_A` (or plane-B carrying
`XOVER_TO_B`) is provably a no-op: to read it you must already be on that plane. It is
always an authoring mistake, it is decidable at bake time, and the bake refuses it (§7 rule
R2). Aurora's brush should therefore write the mark on **one plane per stroke**, not
symmetrically into both.

### 3.4 What a cell with no crossover holds

`XOVER_NONE` = `0`. Bits 15:14 clear. That is the current content of every cell in every
shipped act (§2.1) and the value Aurora must write for "erase crossover".

**Preservation rule, and it had a violator on our side of the wall — now FIXED.** Any
producer that *rewrites* a per-plane cell word must preserve bits 15:14 rather than rebuild
the word. `tools/repaint_ojz_collision.py::repaint_word` used to do:

```python
sol = (word >> cp.PATH_A_SOL_SHIFT) & 3
return (sol << cp.PATH_A_SOL_SHIFT) | SAFE_FULL_SHAPE
```

— it reconstructed the word from solidity and shape alone and **discarded bits 15:14
unconditionally**. This is the same class of defect Aurora already measured on their side
(`CollisionPalette.tsx` / `MapViewport.tsx` writing words wholesale), and it was in a
committed tool that was run against section 0 as recently as `fde35b2f`. It was harmless
only because the field is empty everywhere.

> **DONE**, ahead of the rest of this parcel, on branch `fix/repaint-preserve-crossover`:
> `repaint_word` now carries `(word >> cp.XOVER_SHIFT) & cp.XOVER_MASK` through, and
> `tools/collision_pipeline.py` gained the named `XOVER_*` constants (§6 change (0), the
> `XOVER_SHIFT` half) so no rewriter has to spell the field as a literal. Pinned by three
> tests, all non-vacuous by a deliberately authored mark (§8.1) — see §7 R4.
>
> It **preserves rather than refuses.** A refusal was considered and rejected: §4 Q4 rules
> geometry and path membership independent axes with all four combinations legal, §6 change
> (1) deliberately keeps a crossover alive on a cell with *no* geometry at all, and a
> whole-tree refusal would block the repaint of a loop's bottom-centre column — flat ground,
> exactly what rule A polices — over a field the repaint does not model. Repainting to shape
> 255 only makes a marked cell more solid, so it can make the mark fire more reliably and
> cannot lose it. A marked target is reported as a **NOTICE** in the tool's output instead.

---

## 4. Aurora's six questions, answered directly

1. **Which of the two bakers.** `bake_plane_cell`. Aurora's data feeds it, via
   `apply_editor_collision_overlay`. `bake_cell`'s word is the sonic_hack donor encoding and
   is off-limits — see the table in §3.1, which names the baker for every bit range in this
   document.
2. **Which plane carries the transition mark.** **Both**, independently, with the semantics
   "read from the plane you are on" (§3.3). Not a mark on one plane describing the other.
3. **Value semantics including zero.** §3.2. `0` = none (and every existing cell holds it),
   `1` = go to A, `2` = go to B, `3` = **reserved, bake hard-errors** — specifically because
   of the clamping trap you named.
4. **Can "layer transition" and "solid on both planes" coexist in one cell — one field or
   two?** **They are different axes and they coexist with no interaction.** Solidity is bits
   13:12 of *each plane's own word*; "solid on both" means both words have non-zero solidity.
   `XOVER` is bits 15:14 of each plane's own word. A cell can be solid on both planes *and*
   carry a transition on one or both planes; all four combinations are legal and meaningful.
   **One field**, because the hypothesis' true half needs none. This is the question that
   decided the shape: solid-on-both is *necessary* for a loop (the shared ground) and not
   remotely *sufficient*.
5. **The location of the assertion enforcing each rule.** §7 names a file and symbol for
   every rule, and says plainly which ones do not exist yet.
6. **Does the bake assert reachability?** **No, and this parcel should not add it.** §8
   gives the reason, and splits the checking between your editor and our build with the
   loop-shaped check on your side.

---

## 5. The path from painted cell to ROM

Every hop, with the tool named and whether it changes. `d-39`'s failure was a field free at
both ends with no path between them, so the point of this table is that every row is
accounted for.

| # | step | tool / symbol | status |
|---|---|---|---|
| 1 | author paints a crossover | Aurora brush | **DOES NOT EXIST** (their `lp2-loop-paint`) |
| 2 | serialise bits 15:14 into the cell word | Aurora `collision-cell-word.ts` | **DOES NOT EXIST** |
| 3 | write `section_N.collattr.bin` / `.collattrb.bin` | Aurora | exists — file format unchanged, 2 bytes/cell, big-endian |
| 4 | read both plane files, hand each word to the baker | `tools/ojz_strip_gen.py` `apply_editor_collision_overlay` | exists — **no change needed** |
| 5 | extract `XOVER`, pass it into the intern key | `tools/collision_pipeline.py` `bake_plane_cell` | **DONE** `8a4313b5` — and it does NOT gate the mark behind solidity (§6 change 1) |
| 6 | widen the dedup key to 4-tuple, store the value | `tools/collision_pipeline.py` `AttrSet.intern` / `AttrSet.entries` | **DONE** `8a4313b5` — `xover` is a REQUIRED argument, so a new call site cannot drop it the way `bake_plane_cell` did |
| 7 | emit a 5th 256-byte table | `tools/collision_pipeline.py` `emit_tables` / `emit_stub_tables` | **DONE** `8a4313b5` — `crossover.bin`; `tools/import_sk_collision.py` writes the zero form too, so a fresh tree has all five |
| 8 | write the table to the data dir | `tools/gen_collision_data.py` | **DONE** `8a4313b5` — no edit was needed: it writes whatever `emit_tables` returns, as does `ojz_strip_gen.generate`'s re-emit |
| 9 | attr bytes → per-column collision strips | `tools/ojz_strip_gen.py` `build_section_collision` / `write_strips_to_file` | exists — **no change**; the attr byte is still one byte |
| 10 | strips → 16×16 blocks with embedded dual-plane collision, S4LZ | `tools/ojz_block_gen.py` (`STRIP_COLL_OFFSET_A/B`, 128 B per plane per column) | exists — **no change**, no ROM format change |
| 11 | table blob into the ROM | `games/sonic4/data/collision/collision_data.emp` — `pub data CrossoverTable` | **DONE** `8a4313b5` — with an `ensure` tying its length to `SolidityTable`'s, the pairing the shared attr index depends on |
| 12 | placement | `games/sonic4/map.toml` (`collision_data` section, boundary key `HeightMaps`) | **NO EDIT NEEDED** — `order` lists section HEAD-labels only, and `CrossoverTable` is inside `HeightMaps`' section. Still **byte-moving**: measured `Map_Sonic`/`DPLC_Sonic`/`Art_Sonic` +256 B, the Z80 banks unmoved (their alignment padding absorbed it), `s4.bin` +16 B — the appended deb2 entry for the new symbol. **The sigil pin/refreeze ritual still applies.** |
| 13 | once-per-frame read + write to `Sst.layer` | engine — `Player_LoopCrossover`, `games/sonic4/player/player_common.emp`, called from `Player_Main`'s shared preamble | **DONE** `602170f7` — 64 bytes, one `Collision_GetType` on the cell the frame resolved onto, on the plane the object is on, indexing `CrossoverTable`; edge-triggered on a `PlayerBlock.xover_cell` compare. Cost, summed from the emitted encodings: 106 cycles same-cell, 518/524 on a cell change, 532/538 when it fires — 0.17% / 0.81% of an NTSC frame for two players. §6 changes (2)-(5) all landed here |

**The load-bearing property of this route: no per-cell ROM growth.** The crossover rides in
the *identity* of the interned attr byte, not alongside it, so steps 9 and 10 are untouched
and the ROM collision format does not change. The entire ROM cost is one 256-byte table.

---

## 6. What the engine parcel owes — the contract

**Changes (0), (1), (6) landed with the bake (`8a4313b5` / `fix/repaint-preserve-crossover`);
(2)-(5) landed with the read site (`602170f7`); (7) is unchanged and (8) is the standing
ritual.** Each is marked at its own heading. Written as requirements, and left in that voice
so the CONTRACT is still readable next to what satisfies it.

One requirement here was NOT satisfied as written, and it is flagged where it appears: (3)
names two places that are not the same place ("the shared per-frame player tail" and
"alongside the quadrant derive"). It landed at the quadrant derive.

This parcel sequences **after** the sprite priority swap
(`loops-and-sprite-rotation.md` §6, Parcel 2).

**(0) Constant hygiene, `tools/collision_pipeline.py`.** Add `PLANE_SOL_SHIFT = 12` and
`XOVER_SHIFT = 14` documented as *the per-plane word only*, and re-comment
`PATH_B_SOL_SHIFT = 14` as *the donor chunk-entry word only*. `bake_plane_cell` stops
borrowing `PATH_A_SOL_SHIFT`. Two constants may share a value; they must not share a name.

**(1) `bake_plane_cell` must not gate the crossover behind solidity.** Today it returns byte
0 early when `solidity == SOL_NONE or shape == 0`. A crossover on an air cell must survive
that gate, interning an entry of `(all-zero heights, angle 0, SOL_NONE, xover)` — a non-zero
attr index that is nonetheless air.

*This is verified safe for every existing sensor.* `probe_core`'s `.cell`
(`games/sonic4/player/player_sensors.emp`) reads the attr, and on a non-zero attr goes
straight to `SolidityTable[attr] & d6`; with `SOL_NONE` that is zero, so it takes `.cl_air`,
which zeroes `d0/d1/d2`. The attr never escapes. The only cost is one extra `SolidityTable`
read on such a cell. The `.full_back` back-probe likewise sees `d2 = 0` and behaves exactly
as it does over ordinary air.

Why it matters: without it, a painted crossover can only ever fire for a player standing on
solid ground, and `loops-and-sprite-rotation.md` §4.5.3 is explicit that the layer update
must work in every state *because you can enter a loop's far side airborne*.

**(2) The read site. DONE `602170f7`.** One lookup per frame, of the cell the object actually
resolved onto — **not** on the probe path. Sensors issue many speculative probes per frame
(both sensors of a pair, the ±16 extensions, ceiling checks) and a transition must never fire
from one. `Player_LoopCrossover` issues exactly one `Collision_GetType` per player per frame,
against `x_pos`/`y_pos`, and only on a frame where the cell changed.

**(3) Where it goes. DONE `602170f7`, at ONE of the two places this line names.** The
requirement says "the shared per-frame player tail in `Player_Main`, alongside the quadrant
derive" — and those are different sites: the quadrant derive is in the preamble, above the
state dispatch, not in the tail. It landed at the **quadrant derive**, which is the more
specific of the two and the established idiom for shared per-frame state taken from the
position the last frame resolved to. *The two placements are behaviourally identical*: a
pre-dispatch read on frame N+1 sees exactly the position a post-dispatch read on frame N
would have seen, so the layer reaches the sensors on the same tick either way. **Not** the
`Ground_PostMove` fall-through, which carries an explicit `SEAM GUARD` comment in
`player_ground.emp` forbidding state-specific insertions between the floor snap and
`Player_SlopeRepel`.

**(4) Edge-trigger. DONE `602170f7`, and as a LONG rather than a word.** Fire only when the
resolved cell *changes*. Standing still on a marked cell must not re-fire. `PlayerBlock.xover_cell`
is a `u32` holding the packed world cell `(x & $FFF8) << 16 | (y & $FFF0)` — the quantisation
`Collision_GetType` itself performs, derived from the block collision format
(`COLL_CELL_W`/`COLL_CELL_H`, `engine/system/constants.emp`) rather than chosen. A word would
not fit two 16-bit axes, and packing them lossily would alias two cells onto one id.

**The requirement's own wording contains the trap, so it is worth stating what "changes"
must mean.** The id is derived from **position only** — never from the layer, the mark, or
anything the fire writes. A trigger keyed on the VALUE ("fire when the mark becomes
non-zero") also survives standing still, so standing still does not discriminate between the
right rule and the wrong one. The case that does is §3.3's ORDINARY two-way pair: plane A
carries `XOVER_TO_B` at the same cell where plane B carries `XOVER_TO_A`, so a trigger that
re-armed when the layer changed would read the other plane's word there on the next frame and
flip back, every frame, forever. `tools/loop_crossover_gate.py` runs that exact cell for five
frames without moving and requires no second write.

**(5) The write. DONE `602170f7`.** `subq.b #XOVER_LAYER_BIAS, d0` then `move.b d0, Sst.layer(a0)`
— `XOVER_TO_A`(1) → layer 0, `XOVER_TO_B`(2) → layer 1. The engine must **not** re-derive this
mapping independently; it is the encoding, and it carries the R6 `ensure` pair tying the two
(§7 R6). The bias is a named constant precisely so the guard binds the emitted immediate.

**(6) `tools/repaint_ojz_collision.py::repaint_word` must preserve bits 15:14** (§3.4).
**DONE** — landed ahead of the rest of this parcel; see the callout in §3.4. Change (0)'s
`XOVER_SHIFT` / `XOVER_MASK` landed with it (the `PLANE_SOL_SHIFT` rename did not — it
touches `bake_plane_cell` and belongs with the baker work).

**(7) `path_swap.emp` survives.** Painted cells cannot be conditional, spawned, moved, or
carried by a boss. Route P takes the common case; the object remains the escape hatch. This
is `loops-and-sprite-rotation.md` §6's "where I push back on the owner" and it is unchanged
by anything in this document. **Flagged for the owner** (§11) because his steer was "get
away from the object" and that could be read as "delete it".

**(8) Byte-moving ritual.** Change (11)/(12) adds 256 bytes to the `collision_data` section.
Repin and refreeze per the standard ritual; `pins.rs` is a gate.

---

## 7. Where each rule is enforced — file and symbol, or "does not exist"

Aurora's Q-34: *an anchor whose rules live only in a paragraph is the thing this repo keeps
paying for.* Every rule in this document, with its enforcement site:

| rule | statement | enforced at | exists? |
|---|---|---|---|
| **R1** | `XOVER == 3` is illegal | `tools/collision_pipeline.py` `bake_plane_cell` — raise, do not clamp, do not warn | **DONE** `8a4313b5` — it raises. Pinned by `test_r1_the_reserved_crossover_value_raises_and_the_legal_one_does_not` with the 0b10 converse |
| **R2** | plane-A word must not carry `XOVER_TO_A`; plane-B must not carry `XOVER_TO_B` | `tools/ojz_strip_gen.py` `apply_editor_collision_overlay` (the only site that knows *which* plane a word came from — `bake_plane_cell` does not) | **DONE** `8a4313b5` — it raises, and the MIRRORED plane B (no `.collattrb.bin`) is subject to it too, with the message saying so. Pinned by `test_r2_a_self_mark_is_refused_on_the_plane_that_cannot_read_it`, all three asymmetric cases |
| **R3** | bit 14 means path-B solidity in the donor word and `XOVER` in the per-plane word, and no caller crosses them | `tools/test_collision_consistency.py::test_r3_the_two_bakers_read_bits_15_14_differently` | **DONE** `8a4313b5` — and change (0)'s `PLANE_SOL_SHIFT` landed with it, so `bake_plane_cell` no longer borrows the donor word's `PATH_A_SOL_SHIFT` |
| **R4** | every rewriter of a per-plane cell word preserves bits 15:14 | `tools/test_collision_consistency.py::test_repaint_word_preserves_the_loop_crossover_mark` (the function) and `::test_repaint_write_path_preserves_the_crossover_on_a_synthetic_plane` (the tool's real write path, incl. `Section.set_word`'s two tile rows) and `::test_run_reports_a_marked_target_as_a_notice_and_still_succeeds` (the NOTICE, and that a mark does NOT change the exit code) | **DONE** — both tests green, both red before the fix; the only rewriter on our side is now compliant |
| **R5** | the emitted `crossover.bin` matches the painted cells | `tools/test_collision_consistency.py::test_r5_an_authored_crossover_reaches_the_emitted_table` — the real `apply_editor_collision_overlay` + `emit_tables` path over a synthetic two-cell fixture, with §8.1's converse control | **DONE** `8a4313b5`, **but NOT where this row said.** It is a FIXTURE test, not a rule inside `collision_consistency.py`. Reason: bits 15:14 are zero in all 18 shipped files, so a rule over the baked artifact would examine a population of ZERO marked cells — and that gate REFUSES an empty population by design (`check()`'s vacuity guards). A rule that can never fire is the thing this document spends §8.1 warning about. Revisit when real content carries a mark |
| **R6** | the engine's layer mapping matches the encoding | `.emp` `ensure` block at the read site, `games/sonic4/player/player_common.emp` (reachable on every sonic4 shape's link, so it evaluates — `docs/EMP_PITFALLS.md` §3) | **DONE** `602170f7` — `XOVER_TO_A - XOVER_LAYER_BIAS == LAYER_PATH_A` and the `TO_B`/`PATH_B` twin, where `XOVER_LAYER_BIAS` is the immediate the emitted `subq.b` actually carries, so the guard binds the instruction and not a restatement of it. Plus `XOVER_NONE == 0` (the `beq` after the table fetch IS that test), `XOVER_TO_B == XOVER_TO_A + 1` (one subtraction can only map an adjacent pair) and `TILE_CACHE_COLL_PLANES == 2`. **An `ensure` cannot see a mis-typed IMMEDIATE**, which is why `tools/loop_crossover_gate.py` exists beside it: changing `#XOVER_LAYER_BIAS` to `#2` in the source builds green through every guard here and produces 9 findings there |
| — | loop-shaped reachability | **Aurora**, at paint time (§8) | **NEW, and not ours** |

**Why `tools/collision_consistency.py` and `tools/test_collision_consistency.py`.** They are
the existing home for build-time collision assertions, they already check the *baked
artifact* rather than authoring intent, they already carry the baseline mechanism
(`tools/collision_baseline.json`), and they are already build-fatal: `build.sh` runs
`python3 -m pytest "${TOOLS}"` and exits 1 on failure. Do not build a new harness.

---

## 8. Non-vacuity, and where the error surfaces

### 8.1 The vacuity warning, and how each rule escapes it

`d-39`'s warning survives its withdrawal and binds everything above: **every cell in every
shipped act holds zero in bits 15:14** (measured, §2.1 — all 18 files, all 65 536 cells
each). A gate written over real content therefore *cannot fail*, and a correct
implementation and a broken one emit the identical artifact.

So no rule here is proven by real content. Each is proven by a **synthetic fixture that
authors a non-zero value deliberately, plus a converse control**:

- **R1** — positive: a fixture word with bits 15:14 = `0b11` must raise. Converse: the same
  word with `0b10` must bake successfully. Without the converse, a `bake_plane_cell` that
  raised on *everything* would pass.
- **R2** — positive: a plane-A grid carrying `XOVER_TO_A` must be refused. Converse: the same
  grid carrying `XOVER_TO_B` must be accepted, and the same value in the plane-B grid must be
  refused. Three cases, because the rule is asymmetric and a symmetric bug passes two of them.
- **R3** — positive: one 16-bit value fed to both bakers, asserting `bake_cell` reads bits
  15:14 as path-B solidity (a *second* non-zero attr byte out) while `bake_plane_cell` reads
  them as `XOVER`. Converse: a value with 15:14 clear must produce path-B air from `bake_cell`.
- **R4** — positive: `repaint_word` over a word with `XOVER_TO_B` set must return a word with
  it still set. Converse: it must still clear the flip bits, so the test cannot pass by
  turning `repaint_word` into the identity function.
- **R5** — positive: a synthetic two-plane grid with a known crossover must produce a
  `crossover.bin` with that value at the expected attr index. **Converse control: the same
  grid with the field zeroed must produce a *different* artifact** — this is the one that
  proves the field is load-bearing end to end, and it is the exact check whose absence made
  `d-39`'s proposal unfalsifiable.
- **R6** — the `.emp` `ensure` is a comptime fact and fails the build directly; its trap is
  reachability, not vacuity (`docs/EMP_PITFALLS.md` §3).

The pattern is already in the tree: `tools/test_collision_consistency.py` pairs
`test_rule_a_fires_on_a_flat_run_claiming_45_degrees` with
`test_rule_a_permits_flat_and_odd_angles`. Follow it.

### 8.2 Reachability — the Route P build-time check. **No, and here is why.**

`loops-and-sprite-rotation.md` §5.2 proposed *"every cell where plane A and plane B differ is
reachable from a transition"* as a bake assertion. **This parcel should not implement it,
for two independent reasons.**

**First, it would fail today on content that is perfectly fine.** Measured at `fde35b2f`,
section 0 has 736 cells solid on A only and 44 solid on B only — divergent regions with no
crossover anywhere, because plane B is partial authoring, not a loop. The check would be
non-vacuous in the worst way: it would red the build on shipped, correct, loop-free content.
Baselining that away would suppress exactly the signal it exists to raise.

**Second, the bake cannot decide it.** Reachability needs a traversal model — which surfaces
connect, at what speed, in which direction. The bake sees interned bytes. Anything it could
compute would be a proxy with a fitted radius, and a fitted number in a build gate is worse
than no gate.

**So the split is:**

- **Our build checks the encoding** — R1 through R6. Bytes, decidable, cheap, non-vacuous by
  fixture.

  **⚠ THAT SENTENCE IS THE DESIGN, NOT THE STATE OF THE TREE — corrected 2026-08-29 after it
  was read as a statement of fact.** It describes which side of the wall each check BELONGS on.
  At that correction, **exactly one of the six was built: R4.** R1, R2, R3, R5 and R6 were
  **specified and not implemented**, exactly as the §7 table had always marked them (`NEW`
  against `DONE`) — the table was right and this prose was ahead of it.
  **AS OF 2026-09-02 ALL SIX ARE BUILT: R1-R5 at `8a4313b5`, R6 at `602170f7`.** R5 landed as
  a fixture test rather than as a rule inside `collision_consistency.py` — see its §7 row for
  why a rule there would examine a population of zero. R6's own §7 row records the thing an
  `ensure` structurally cannot check (the emitted immediate) and names what checks it instead.
  **The split this paragraph describes now holds in both directions: our build checks the
  encoding, and it does so without ever pretending to check the loop.**
  **Read the §7 table's status column for what exists; read this split for where it goes.**

  **How it went wrong, because the mechanism matters more than the correction.** The present
  tense is doing all the damage: *"our build checks"* is indistinguishable from a claim about
  today, and it sat two hundred lines from the table that contradicted it. The aurora lane
  **built an audit tier against this sentence** and asked the question that surfaced it; nothing
  in the document would have corrected them, because the two statements never appear together.
  A design split and a status report look identical in prose and are separated only by tense.
  **Write a division of responsibility in the future tense, or put the status beside it.**

  ~~**And note what R1's absence costs specifically**, since it is the one with a live consequence:
  R1 (`XOVER == 3` hard-errors) is exercised by nothing, because `bake_plane_cell` does not read
  bits 15:14 at all (`tools/collision_pipeline.py:229`; its docstring enumerates `9:0`, `10`,
  `11`, `13:12`). So the illegal value is not merely unchecked — it is undetectable on the bake
  path, and an act painted full of `XOVER == 3` produces a byte-identical ROM and a green build.~~
  **FIXED 2026-09-02 (`8a4313b5`): `bake_plane_cell` reads the field and R1 raises on 3.** Kept
  struck through rather than deleted, because the paragraph is the clearest statement anywhere of
  what "the field is dropped" actually bought — and the line number in it had already rotted
  before the fix, which is its own lesson about citing one.
  Booked in `docs/DEFERRED_WORK.md` under the authored-crossover-never-reaches-the-ROM entry.
- **Aurora checks the loop** — at paint time, where the *intent* is present. You know a
  stroke was a loop; the bake only knows it produced divergent cells. Refusing to author a
  loop that lacks its crossover is a better error than a build failure an hour later, and it
  is the only place the information exists.

If Aurora wants a build-side backstop later, the honest form is a rule scoped to *regions the
author declared as crossovers*, which requires a declaration this encoding does not carry.
That is a follow-up with a real design question in it, not a line item.

---

## 9. The cost nobody priced: how many distinct crossing kinds

`d-39` could not bound this and said so. It is now partly bounded and partly not, and the
unbounded part is not the part `d-39` thought.

**Bounded — the layer half: exactly 2.** `XOVER_TO_A` and `XOVER_TO_B`. The bound is
architectural, not measured: there are two collision planes and the field targets one of
them. Sonic Mania still defines `CPATH_COUNT = 2` with the same bit positions
(`loops-and-sprite-rotation.md` §10.1), so this is the answer rather than a legacy
compromise. Four of S3K's seven `Obj_PathSwap` subtype bits dissolve entirely under painting
rather than multiplying: band half-extent (bits 0-1) and orientation (bit 2) become the
*shape of the painted region*; direction sense (bits 3-4) becomes the per-plane pair (§3.3);
grounded-only (bit 7) becomes a property of the read site.

**Attr-set growth, bounded.** Widening the intern key splits an entry only where a marked
cell's geometry is also used unmarked. Worst case `2 × (distinct geometries at marked cells)`
plus at most 2 air-with-crossover entries. Current occupancy measured at `fde35b2f` from
`games/sonic4/data/collision/*.bin`: **20 of 256 slots used, 236 free** (highest index 20;
solidity histogram over the used range: `SOL_ALL` 13, `SOL_TOP` 7). A loop's two marked
columns will not come close.

**UNBOUNDED — sprite priority, and it is the real multiplier.** S3K's swapper carries *two
further independent bits* (5 and 6) that set the player's VDP high-priority bit per crossing
direction, and `loops-and-sprite-rotation.md` §4.3 Gap 1 is emphatic that without it *"a loop
reads as a flat painted circle"*. If priority must be painted independently of layer, the
field is not 2 bits and the value table is not 3 entries.

**I will not pick a number that fits one test loop.** What would bound it:

1. Paint **one loop** and record whether "drawn in front / behind" was ever needed
   *differently* from "on plane A / plane B". If priority is always a function of the layer
   you switch to, it needs no bits at all — the engine derives it at the same site, and the
   field stays at 2 bits.
2. Paint **one non-loop crossover** — a bridge over a road, or a branch you can take either
   way — because that is where the two genuinely decouple, and it is the case
   `loops-and-sprite-rotation.md` §5.2 names as the reason Route G cannot generalise.

Until both exist, the honest position is: **ship the 2-bit layer field, derive priority from
the layer at the engine read site, and treat the first case that needs them decoupled as the
trigger to revisit.** Value 3 being reserved means that revisit is a deliberate ruling and
not a silent widening — which is the point of reserving it.

Growth room, if it is ever needed, is **not** bits 15:14. It is bits 9:8 of the same word:
the shape index is 10 bits but the imported S&K base bank is 256 shapes
(`games/sonic4/data/collision/base/heightmaps.bin` is 4096 B = 256 × 16), so bits 9:8 have
never taken a non-zero value. That is a second unassigned pair in the same word, and it is
recorded here so a future session finds it in a document rather than re-deriving it — which
is how this lane got bits 15:14 wrong the first time.

---

## 10. Corrections to prior documents

**`docs/research/loops-and-sprite-rotation.md` §4.2's table is stale and must not be quoted.**
It was measured before the owner's painting and before `fde35b2f`'s 574-cell repaint. Its
central claim — *"of the 644 differing cells, 644 are solid on A and air on B, and zero are
solid on B and air on A"* — **no longer holds.** At `fde35b2f`: 736 solid on A only and
**44 solid on B only**. Plane B is no longer a strict subset of plane A. The §4.2 conclusion
that "there is no place where plane B provides a surface plane A does not" is **false as of
`fde35b2f`**; there are 44 such cells. The doc's own `[TAG-RUNTIME]` note said the table was
perishable, and it was right.

`d-39-corrected` repeats the "644 … and ZERO the other way" figure as a supporting argument.
The argument it supports (that emptiness makes a gate over the field vacuous) is **still
correct** — bits 15:14 really are zero in all 18 files — but the specific figure it leans on
is not current.

**`loops-and-sprite-rotation.md` §4.5.2's bit table is correct as scoped and was misread.**
It says "Aurora's per-plane cell word … 15:14 nothing, free", which is true of
`bake_plane_cell`'s word. `d-39` generalised it to "the collision cell word", which is false.
The doc is not at fault; the generalisation was. §3.1 above exists to make that
generalisation impossible to repeat.

**`loops-and-sprite-rotation.md` §5.2 Route P should be amended** to drop *"the same spare
bits can carry a 'solid on both planes' state"*. They cannot and need not: §2.1 shows the
representation already expresses it and that 1056 cells of it are already authored. Route P's
scope halves.

**`docs/DEFERRED_WORK.md`** carries no entry for this work; one should be added when the
parcel is scheduled.

---

## 11. Open, and for the owner

**BLOCKED / not answerable here — runtime confirmation.** Nothing in this document has been
run. Three items are tagged for the controller, none of which gate Aurora:

- **[TAG-RUNTIME]** the "air cell with a non-zero attr is invisible to every sensor" claim
  (§6 change 1) is derived from reading `probe_core`, not from executing it. It should be
  confirmed on a real build before the engine parcel relies on it.
- **[TAG-RUNTIME]** `path_swap.emp` despawns when the camera leaves and re-arms on respawn.
  Core Framework documents that configuration as a source of players stuck in loops
  (`loops-and-sprite-rotation.md` §10.4). Painted crossovers do not have this failure mode at
  all, which is a further argument for Route P — but the object survives (§6 change 7) and
  the behaviour still wants a deliberate test on a real loop.
- **[TAG-RUNTIME] — CLOSED 2026-09-04, and it found a defect on the way.** The named check
  was: paint a crossover pair, build, and watch the byte at `Player_1 + $2D` (`Sst.layer`) in
  the emulator; it must change on the frame the player ENTERS the marked cell and must NOT
  change again while he stays in it. The paint now exists (two cells at section-0 column 143,
  world x 1144..1151, rows y 432..447 and y 544..559, each marked `XOVER_TO_B` on plane A and
  `XOVER_TO_A` on plane B — §3.3's pair, twice), and `tools/loop_step_over_witness.py` drives
  a real player over the lower one on a real ROM. Both halves hold: the layer goes 0 -> 1 on
  the frame he reaches column 143 and stays 1 for the rest of the run.

  **What it also found: the mark was invisible above ~8 px/frame.** See §12.

**For the owner — one item, and it is not a blocker.** `loops-and-sprite-rotation.md` §6
recommends keeping `path_swap.emp` alongside Route P as the escape hatch for the dynamic
cases (conditional, spawned, moved by a boss). That is a reading of "get away from the
object" as *"stop needing the object for the common case"* rather than *"delete it"*. This
document assumes the former (§6 change 7). If the owner meant the latter, the dynamic cases
have no mechanism and that should be a deliberate choice rather than an inference from a
design document. **No numbers turn on it and Aurora's brush is unaffected either way**, so it
does not need answering before the editor lane proceeds.

**Not re-opened:** whether the crossover is painted or placed as an object. The owner ruled
painted. Everything above assumes it.

---

## 12. The step-over — the read site sampled, and a mark is one cell (fixed 2026-09-04)

Everything §6 change (4) says about the edge trigger is about a trigger that fires TOO
OFTEN. It says nothing about one that never fires at all, and that is what the shipped read
site did above about 8 px/frame.

The arithmetic is not subtle. A mark is ONE cell; `COLL_CELL_W` is 8 px; `PHYS_GSP_CAP` is
`$1000` = 16 px/frame; and `ObjectMove` (`engine/objects/core.emp`) is a single unconditional
add, so horizontal movement is not substepped anywhere. `Player_LoopCrossover` read the
position the frame RESOLVED to, once. A frame can therefore begin on one side of a marked
cell and end on the other without ever occupying it.

The vertical axis had already been protected the other way round: `PHYS_FALL_CAP` is `$F00`
= 15 px, deliberately ONE PIXEL under `COLL_CELL_H`, with an `ensure` in
`engine/system/constants.emp` that says in as many words what a whole-cell fall step would
do. X cannot be capped like that without making the game slower, so the read now SWEEPS: it
walks from the cell it last ran in to the cell it resolved to and probes each. The reach it
walks is derived from the physics caps and guarded in both directions by `ensure`s at the
read site (`games/sonic4/player/player_common.emp`).

### What it looked like on a real ROM

`tools/loop_step_over_witness.py` drives a player right from the section-0 ramp foot at an
injected ground speed and samples `Sst.layer` EVERY FRAME (at 9 px/frame a player crosses an
8 px cell in under one frame, so any coarser interval cannot resolve a flip even in
principle). The only variable swept is the sub-cell PHASE the run starts on — which is
exactly what decides whether a 16 px stride lands on the marked column or straddles it.
Two ROMs, differing only by this fix:

| ground speed | px/frame | start phase | pre-fix | post-fix |
|---|---|---|---|---|
| `$600` (`PHYS_TOP_SPEED`) | 6 | any of 8 | 1 flip, rides the loop | 1 flip, rides the loop |
| `$900` | 9 | +1 | **0 flips**, never enters the loop, runs on to x 2700 and falls 1923 px | 2 flips, climbs 143 px |
| `$1000` (`PHYS_GSP_CAP`) | 16 | +7 | **0 flips**, never enters the loop, falls 768 px | 1 flip, climbs 72 px |

The `$600` row is the negative control and it is the point: at 6 px/frame no phase of the
eight changes the outcome, because 6 px cannot straddle an 8 px cell. The defect is
speed-dependent, which is what makes it nasty — the player falls through a floor a long way
from the loop he apparently completed, so a bug report names the floor.

### What grades it now

- `tools/loop_crossover_gate.py`, families `sweep_step_over` (which cells the frame ASKED
  about, read out of `Collision_GetType`'s own arguments) and `sweep_step_over_marks` (the
  parity of the layer byte after crossing k marked cells, with no per-cell address
  arithmetic). Both derive their sweep from the build's own `PHYS_GSP_CAP` / `PHYS_FALL_CAP`
  and both go LOUD rather than quiet if those caps ever stop being able to skip a cell.
- The property graded is: every column index and every row index between the previous cell
  and the resolved cell must be among the cells asked about, plus the resolved cell itself.
  That is "a mark painted as a barrier across the path always fires". It is NOT a supercover
  claim — an isolated cell the true segment only clips the corner of can still be missed, and
  the gate's own docstring says so.

### One thing this turned up that is not an engine matter

`docs/loop-arc-cells-section0.json` recommends marks at the loop's entry/exit height on each
arc (cc 148 and cc 137 at row 70), explicitly "not at the crown, where a mis-fire strands the
player mid-arc". The shipped paint is not that: it is a single midline column (cc 143) marked
on BOTH planes at BOTH the crown and the floor. That is a content question for whoever owns
the paint, not a bug in the encoding — recorded here because the engine now honours whatever
is painted and the difference will start to matter.
