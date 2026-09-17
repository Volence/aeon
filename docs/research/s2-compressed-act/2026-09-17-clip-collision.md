# S2-COMPRESSED-ACT parcel 5 — clip → `collattr.bin`

Branch `parcel/s2-clip-collision`, base `caae1521`. Staged-plan row 5 of
`docs/research/2026-09-17-s2-compressed-act-design.md` §10. The design doc is patched in
place at §1.3 item 2, §2.2, §2.3, §3.5, §8, §10 row 5 and §13, where this parcel made a
sentence in it false.

No `.emp` touched, no ROM byte moved, the shipping act's collision tables, the S&K bank and
`games/sonic4/data/editor/ojz/act1` untouched, all three donor trees read-only, no emulator
used.

---

## 1. What row 5 owed, and what it delivered

**The row:** *"Run `bake_cell` over the clip's chunk words, emit both plane files."*
**The check:** *"The attr-set entry count for a given clip matches `s2_clip_budget.py`'s
prediction for that rectangle, and the bake refuses a clip that cuts a crossover pair."*

Both halves pass. The first passes exactly, with six numbers. The second required building
a refusal that did not exist — see §4.

### The transcode, which is the whole parcel in one function

`collision_pipeline.chunk_entry_to_plane_words` turns one **donor chunk-entry word** into
the two **aurora per-plane cell words**. The design's §1.3 called this the "collision
indirection collapse" and noted that `bake_cell` already does it; row 5's observation is
that `bake_cell` does it one step *too far* for a converted tree. `bake_cell` goes donor
word → interned attr byte in one hop, which is what the ROM wants. A converted editor tree
wants the intermediate, because that is the word an author edits.

```
donor chunk entry            aurora per-plane cell
9:0   block id               9:0   base-bank SHAPE index
10    X flip                 10    X flip
11    Y flip                 11    Y flip
13:12 path-A solidity        13:12 THIS plane's solidity
15:14 path-B solidity        15:14 XOVER (crossover mark)
```

Resolve the block id through the zone's collision index to a shape index, carry the flips,
split the two solidity nibbles into the two planes' own words, emit `XOVER_NONE`.

**It is EXACTLY equivalent to `bake_cell`, measured rather than argued.** Over every
distinct `(chunk word, index_a, index_b)` triple the six showcase zones reference — **5,129
triples, 10,258 cells** — the two paths produce identical attr bytes *and* byte-identical
attr sets in the same intern order. A triple and not a word, because the block-id → shape
indirection is per zone and two zones can give one word two meanings.

That equivalence is what licenses everything below: the design's predictor reaches
`bake_cell` from the donor side and never opens a clips.json, a converted tree or a plane
file; the bake reads plane words off disk through `bake_plane_cell`. Without the
equivalence they would be two tools agreeing about nothing.

### What ships

| file | what row 5 added |
|---|---|
| `tools/collision_pipeline.py` | `chunk_entry_to_plane_words`; `AttrSet(cap=None)` for counting callers; `bake_plane_cell` R3 (§6) |
| `tools/ojz_strip_gen.py` | `load_base_bank(bank_dir=None)` + `SK_BANK_DIR` |
| `tools/s2_zone_convert.py` | both plane files per section, crop-masked like the art; `zone.json` `collision` block; `verify_tree` check E |
| `tools/clip_manifest.py` | `section_plane_grid`, `collision_grids`, `collision_banks`; **R12**; W1 retired |
| `tools/clip_act_bake.py` | the collision pass: compose, C1/C2/C3, emit both act plane files, recount off disk, per-clip §8 readout |
| `tools/test_s2_clip_collision.py` | 33 rows, 13 mutations |
| `tools/land_gate.py` | the new gate registered as a reader of the design's tool |

---

## 2. THE CHECK, FIRST HALF — six numbers, six exact matches

| fixture | clip | emitted alone | `s2_clip_budget.py collision` | act emitted | act predicted |
|---|---|---|---|---|---|
| `s2_two_clip` | `ehz_s2` | **95** | `EHZ:2,1` → **95** | **207** | `EHZ:2,1 CPZ:2,1` → **207** |
| `s2_two_clip` | `cpz_s2` | **148** | `CPZ:2,1` → **148** | | |
| `s2_two_clip_pins` | `ehz_s1` | **62** | `EHZ:1,1` → **62** | **191** | `EHZ:1,1 CPZ:1,1` → **191** |
| `s2_two_clip_pins` | `cpz_s1` | **148** | `CPZ:1,1` → **148** | | |

Each act's number is counted twice — once over the composed grids, once decoded back off
the emitted plane files — and the bake refuses on a disagreement, so a difference would be
the emission and not the arithmetic. Both acts recount identically (207, 191).

The art half of both fixtures is unchanged from parcel 3: 1,182 and 900 (zone, tile) pairs
verified, worst window 12 and 10, 682 and 1,771 positions at the peak, 48,471 windows.

**And at whole-zone scope, all six showcase zones agree too:** the converter emits EHZ 105,
CPZ 160, HPZ 152, WFZ 108, OOZ 67, MTZ 62, and `s2_clip_budget.py collision <ZONE>` prints
the same six.

### One correction to §3.5's table, and one caveat on using that tool as a per-clip predictor

- **CPZ is 160, not 162.** §3.5's correction note moved the three *headline* figures from
  the horizontal (rotated) array to the vertical one but left the per-zone table alone.
  EHZ 105, OOZ 67, MTZ 62, WFZ 108 and HTZ 122 all reproduce; only CPZ moved.
- **`collision <ZONE>:<s0>,<n>` has no vertical extent.** It counts every chunk its COLUMN
  range references, over every row of the layout grid, where a clip is a rectangle. It
  agrees for the tracked fixtures because those clips are full-height. A clip shorter than
  its zone's grid is a different rectangle, and `clip_act_bake`'s number is the one about
  the bytes.

### The crop costs nothing, measured because it was the obvious worry

Collision is crop-masked to exactly the camera-box crop the art uses — anything else puts
invisible solid ground under a blank region. Two of the six zones have layout grids that
reach below their crop: EHZ's below-crop chunks are all chunk 0 (air), **OOZ's are real
chunks** (180-186 among them). The cropped and uncropped attr-set counts are identical for
both — **105/105 and 67/67** — because the below-crop chunks reuse shapes the crop already
needs. Nothing published moves.

---

## 3. Bank selection — parcel 4's first hand-off

`ojz_strip_gen.load_base_bank()` hard-coded the S&K bank. It now takes the directory:

- a converted S2 tree's `zone.json` **names** its bank (`games/sonic4/data/collision/base_s2`)
  and pins that bank's `heightmaps.bin` and `angles.bin` sha256;
- `clip_manifest.collision_banks(act)` resolves an act's bank from its clips' zones and
  **REFUSES an act whose clips disagree**. Nothing can produce one today — both S2 donors
  share one shape vocabulary byte for byte (parcel 4) — but an act has ONE attr set and one
  index inside it must mean one shape, so two banks would make the same index mean two. The
  refusal is where it can be read, not discovered in the output;
- `generate()` still calls it with **no argument** and still reads `base/`.

**It is load-bearing, not decorative.** Mutation M5 points the clip bake at the S&K bank
instead, and five rows go red including two of the four count rows. (Only two: `ehz_s2` and
`ehz_s1` happen to need 95 and 62 entries under *either* bank. That coincidence is exactly
why the gate also has a row that walks emitted cells back to their donor cells.)

---

## 4. THE CHECK, SECOND HALF — and the design's §2.3 was wrong

§2.3 said: *"A clip whose marquee cuts a loop in half will fail the bake, loudly"*, citing
`apply_editor_collision_overlay`'s R2.

**It will not, and it did not.** R2 refuses a **self-mark** — a plane-A cell carrying
`XOVER_TO_A`. Cutting a loop in half produces a perfectly well-formed mark whose partner is
simply **absent**, which R2 cannot see. Nothing else saw it either:
`collision_xover_census.py` reports pairing but is explicitly a census, not a gate.

Nor is the thing a rectangle cuts the per-cell pair. The repo's own pairing rule is "same
cell index, marked on both planes" (8 paired indices in the shipped act), and a rectangle
clips both planes identically — it can never split that. What a cut really removes is the
loop's **other crossing**: act 1's eight marked indices are two *bands* of one column,
§3.3's bottom-centre and top-centre.

**C1 is the refusal that makes the sentence true**, and it is conservative by necessity:

> A clip is refused when its source rectangle contains at least one crossover mark and its
> source zone contains at least one **outside** that rectangle.

The encoding records which **plane** a mark points at and never which **loop** it belongs
to, so nothing can tell a severed loop from two unrelated ones. That is stated in the
refusal message rather than hidden, and the false positive — a clip that leaves an
unrelated loop behind — has an in-file `severed_xover_reason` opt-out in R11's style, so
the argument sits where the next reader of the manifest will see it.

**C1 is structurally vacuous on today's data and the gate says so.** A converted Sonic 2
tree has no crossover marks and *cannot* have any: the donor chunk word's bits 15:14 are
path-B solidity, so there is no crossover field to convert. C1 guards the path that opens
the moment an author paints a mark onto a donor tree in aurora. Every C1 row therefore
paints its own subject, `test_a_converted_tree_has_no_marks_to_begin_with` is the control
that proves the painting is what makes the difference, and
`test_a_clip_that_keeps_every_mark_is_accepted` is the discriminating control — same marks,
same bake, one rectangle that takes all of them, and it must pass. Without that second row
C1 could be "refuse any clip of a tree that has marks anywhere"; mutation M7 (drop the
`outside` term) reds it and nothing else.

---

## 5. W1 RULED — and its premise was false

W1 warned that an `src_rect` off the 128-px chunk grid would bite collision, and left
promoting it to a refusal as row 5's call *with its evidence*. The evidence says the
warning was aimed at the wrong number.

**Collision is not authored per 128-px chunk in any sense a clip can cut.** A chunk is 8×8
independent **block placements** and each carries its own entry word — its own block id,
its own flips, its own two solidity nibbles. A cut between two blocks inside a chunk severs
nothing; a cut at a chunk boundary is not special.

**The quantum that binds is the BLOCK, 16 px, and it binds on the paste SHIFT, not on the
src origin.** Derived from the runtime rather than from either file format:

- a collision cell's height profile is `PROFILE_LEN` = 16 bytes covering a 16-px block, and
  `probe_core` selects the column with `andi.w #$F, d0` on the **world** x
  (`games/sonic4/player/player_sensors.emp`);
- the collision row is the world tile row halved (`engine/level/collision_lookup.emp`
  `lsr.w #1`), so y is the same story.

The geometry a cell describes is anchored to its own world position mod 16. Move it 8 px
and every probe reads the wrong half of a profile — **silently**, because the art is one
word per 8-px cell and moves correctly. The failure is ground 8 px out of place, which no
screenshot shows.

So **R12**: `dst origin − src origin` is a multiple of 16 in both axes. A refusal with no
opt-out, because unlike R11 there is no argument to be made. It is a rule about the
*shift*: a 16-px-aligned src pasted to a 16-px-aligned dst is correct, and so is an
8-px-aligned src pasted 2048 px away. W1 is retired with its tag kept reserved and its
false premise recorded in `clip_manifest`'s header, so a future W1 cannot inherit it.

`test_w1_warns_on_an_unchunked_src` became
`test_r12_refuses_a_paste_that_shifts_collision_off_the_16px_grid`: the same mutation that
row always made (src x + 8) now refuses, and the row also carries the retired premise as a
*passing* case — the same rect at a 16-px offset, genuinely not 128-px aligned, loading
clean.

---

## 6. The unruled `rotate_profile` — the decision, and why

Parcel 4 left `collision_pipeline.emit_tables` calling the **unruled** `rotate_profile`,
which raises on a row whose solid span touches neither edge (S2 shape `$18` and its flips
are the only such shapes in either bank), and said turning a refusal into a silent value on
the shipping path was not its call.

**Row 5's answer: leave it raising. Move the DETECTION, not the behaviour.**

The reasoning, in order of weight:

1. **Silencing it is a change to how every act in the repo is baked, made to serve one clip
   act that does not exist yet.** `$18` is referenced by no showcase zone (asserted by
   `test_the_showcase_zones_do_not_need_18`, which fails if a zone-list change ends that),
   so the cost of leaving it raising is zero today and the cost of silencing it is every
   future act.
2. **What was actually wrong was the DISTANCE, not the loudness.** The author marquees a
   rectangle in aurora and finds out at the ROM bake, in a traceback from a function four
   layers down that names a height profile and no clip. **C3** detects the same condition
   at the clip, by name, against the clip that caused it, before a byte is emitted.
3. **When row 6 or later genuinely needs `$18` in a shipping act, the argument for
   `rotate_profile_ruled` in `emit_tables` will be made against a real clip instead of a
   hypothetical one** — and `test_the_unruled_rotate_profile_is_still_the_one_emit_tables_calls`
   makes that argument happen in the open: it fails the moment someone routes the ruling
   in. Mutation M10 is exactly that change, and it reds that row alone.

---

## 7. FOUND: `bake_plane_cell` accepted a shape past the end of the bank

Found while painting a synthetic over-cap act for the C2 row. An aurora plane cell word
gives the shape **10 bits** (0..1023); a base bank holds `MAX_PROFILES` = **256**. So an
authored word can name a shape that is not there, and `bake_plane_cell` sliced past the end
of the bank and interned a **zero-length** height profile.

`emit_tables` then met it as a bare `IndexError: index out of range` raised from inside
`rotate_profile`, naming neither the cell nor the shape nor the bank. And for any profile
that did not raise there, `heightmaps[i*16:(i+1)*16] = b""` on a `bytearray` **deletes**
those bytes rather than filling them, silently shortening the table.

Now **R3**, a named refusal that says which shape, how many the bank holds, and that the
two banks disagree about what an index means — the most likely cause now that there are
two.

**Byte-neutral for the shipping act, measured rather than assumed:** every committed editor
plane file, every solid cell, highest shape index is **255**.
`test_no_committed_plane_file_names_a_shape_past_its_bank` keeps that measurement as a
control, so if it ever reaches 256 this says so before a build does.

---

## 8. The refusal namespace

Row 5's refusals are tagged **C1-C3** rather than continuing `clip_manifest`'s R/W
namespace, because they are **bake-time** facts: each needs the collision bytes and the
base bank, neither of which the manifest loader reads.

| tag | where | what |
|---|---|---|
| R12 | `clip_manifest` | the paste shift is a multiple of 16 px in both axes (W1's replacement) |
| C1 | `clip_act_bake` | the clip takes some of its zone's crossover marks and leaves others (opt-out: `severed_xover_reason`) |
| C2 | `clip_act_bake` | the act needs more than `AttrSet.CAP` = 255 attr-set entries — §3.5's cap, with the per-clip breakdown attached |
| C3 | `clip_act_bake` | the act interns a profile `emit_tables`' `rotate_profile` will refuse |
| R3 | `collision_pipeline` | a cell word names a shape past the end of its bank |

C2 is the one that matters for the showcase act. It reports **how far over** and **which
clip is the most expensive alone**, because the author's next move is to move a marquee,
and "you need 278, and `cpz_s2` alone is 148" is actionable where "it overflowed" is not.
That is what `AttrSet(cap=None)` exists for; every bake that writes ROM tables keeps the
cap.

---

## 9. Evidence

**Gate.** `tools/test_s2_clip_collision.py`, **33 rows**, in build.sh's pre-build tool lane
(`pytest tools -m "not needs_build"`, run once per landing by `tools/landing_build.sh`). No
row carries `needs_build`.

**Red-first, 13 mutations**, each applied on disk and shown before the red run, each
restored from a committed baseline by copy and verified with `cmp` plus a clean-tree check:

| # | mutation | rows red |
|---|---|---|
| M1 | `index_a`/`index_b` swapped in the transcode | 4 |
| M2 | flips dropped in the transcode | 4 |
| M3 | both `np.repeat`s on one axis (block → cell expansion transposed) | 9 |
| M4 | collision written without the crop mask | 2 |
| M5 | clip baked against the S&K bank | 5 |
| M6 | C1 disarmed | 1 |
| M7 | C1 without the `outside` term (over-refuses) | 1 — the discriminating control |
| M8 | `load_base_bank`'s default moved to `base_s2` | 1 — the ROM-safety row |
| M9 | R12 checks x only | 1 |
| M10 | `emit_tables` silenced with `rotate_profile_ruled` | 1 — the §6 decision |
| M11 | C3 disarmed | 1 |
| M12 | C2 disarmed | 1 |
| M13 | R3 disarmed | 1 |

Two of these are worth naming because of what they did **not** red. M1 (swap the two
planes) left every count row green — a plane swap produces the same attr *set* — and was
caught only by the row that walks emitted cells back to their donor cells. M4 (no crop
mask) left every count row green too, for the reason §2 measures, and was caught only by
the pad row. Neither row is redundant with the counts.

**And one thing the mutations corrected about this gate's own design, recorded because the
correction went against the obvious reading.** M1 first reddened the "donor's own geometry"
row on ONE of its two parametrisations. The instinct was that the sampled comparison should
become exhaustive — and an exhaustive comparison was added, and it does **not** see M1 at
all: M1 mutates the *scalar* transcode, while the exhaustive half compares the emitted files
against `rederive_zone_collision`, both on the *vectorised* path, so both sides move
together. It reds on a transposed rectangle (M3) and on the file round trip, which is what
it is for, and it was already sensitive to those on both parametrisations. What actually
missed M1 was the 120-cell **random** sample in the scalar half, and the miss was not bad
luck in general: whether a cell can show an A/B swap depends on the zone's two collision
indices disagreeing *there*. Replaced with a **strided** sweep (every 7th cell in both axes,
count derived from the rectangles), after which M1 reds both parametrisations. Both
comparisons are kept; neither subsumes the other.

**Two other gates caught this parcel and both were right.**
`test_clip_manifest.py::test_w1_warns_on_an_unchunked_src` failed the moment R12 landed —
that is the W1 ruling meeting its own pin, fixed by rewriting the row (§5).
`test_land_gate_classifier` refused the new gate: it imports the design's measurement tool
and so reads a CHECKED path, and the audit would not pass until it was registered as a
reader of `docs/research/s2-compressed-act/`. Fixed in the rule, not routed around.

**Lanes.** Pre-build tool lane with `__pycache__` cleared and **no converted donor trees
present**: **4 failed, 3019 passed, 2 skipped, 28 deselected, 55 errors, 143 subtests passed in
68.29 s**. The 4-failed/55-error artifact-freshness family was established by an **in-place
control taken before this parcel touched anything** (same worktree at base `caae1521`, same
conditions): **4 failed, 2986 passed, 2 skipped, 28 deselected, 55 errors, 143 subtests passed
in 70.49 s**. Delta **+33 passed** = exactly this parcel's rows, and the FAILED/ERROR node-id
sets (59 ids) are **byte-identical**.

**`tools/landing_build.sh`: exit 0, `finished=0`, stamp written** (key `c16fa2cf89c4d807`,
head `cca263d7d4a4`). Three shapes built:

| shape | bytes | md5 | vs master |
|---|---|---|---|
| `s4.bin` | 821,479 | `ae62156a66c9c3f13e93940e938c340e` | identical |
| `s4.debug.bin` | 848,075 | `b15ef259523f67ac963ef0cf4df003dc` | identical |
| `demo.debug.bin` | 104,707 | `f740c22498f6ad132ac9f8bd978c9350` | identical |

**No ROM byte moved.** In-build pre-build lane 3078 passed / 2 skipped / 0 failed / 0 errors
(= parcel 4's 3045 plus this parcel's 33). needs_build lane 27 ran / 0 deferred / 0 failed /
1 exempted (`test_deb2_appendix[demo.bin]`, the shape this caller does not build). Wall clock:
2026-09-17, dev box up 1 day 22 h, load average 1.3-2.5 across the runs.

**Reproduction** (needs the converted donor trees, which are gitignored):

```bash
python3 tools/s2_zone_convert.py convert --all-six
python3 tools/clip_act_bake.py bake games/sonic4/data/clips/s2_two_clip/clips.json
python3 tools/clip_act_bake.py bake games/sonic4/data/clips/s2_two_clip_pins/clips.json
S=docs/research/s2-compressed-act/s2_clip_budget.py
python3 $S collision EHZ:2,1 CPZ:2,1      # -> 207, the act the bake prints
python3 -m pytest tools/test_s2_clip_collision.py -q
```

---

## 10. What row 6 inherits

- **The tree contract is complete for art + collision.** A converted donor zone is now a
  tree aurora can open, marquee *and* re-bake, and `clip_act_bake` writes an act tree with
  `section_N.tiles.bin`, `section_N.local.bin`, `section_N.collattr.bin`,
  `section_N.collattrb.bin`, `sec{N}_local_map.bin`, `pool.bin` and `clipact.json`.
- **What row 6 still has to build is the BLOCK stream.** Nothing here exercises
  `ojz_block_gen` or S4LZ. `sec{N}_blocks.bin` is where the collision planes and the art
  meet in the format the ROM actually reads, and it is the missing piece between this
  parcel's output and a bootable act — along with the `project.json` entry and the
  `act_descriptor.emp` with matching `GRID_W`/`GRID_H` that parcel 3 named.
- **Once that exists, `fg_page_order.check` can be pointed at a second act**, which closes
  parcel 3's restatement of the row-3 check — or that restatement is permanently accepted.
- **The 255 cap now refuses rather than warns (C2), and the showcase act does not fit.**
  Six zones clipped to two sections each is 353 (with the real prototype HPZ); one section
  each is 199. Row 6 is a ONE-clip act so it is far inside the cap, but §9.3's ruling is
  still owed before the act grows past about three zones, and the owner still has to choose
  between clipping harder, merging near-identical shapes, widening the attr field to a
  word, or per-region banks.
- **C1 is a guard with no data behind it yet.** The first act that paints a loop onto a
  donor tree is the first test of it that is not synthetic.
- **The one-way crossover force is legal and C1 does not know it.** §3.3 says
  `{TO_B on A, NONE on B}` strictly dominates a toggle, so an author may deliberately mark
  one plane only. C1 counts marks and does not care, which is right; but a future
  pair-checking rule must not assume two-way.
