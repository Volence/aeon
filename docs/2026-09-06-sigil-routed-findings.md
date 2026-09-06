# The sigil lane's findings routed to aeon — the aeon-side booking

**Why this file exists, and it is the finding underneath the findings.** These five items were
committed in sigil on 2026-09-05 and reached this lane as a queue row reading `S1S3S9 — "Sigil's
routed findings"` and nothing else. On 2026-09-06 a rebooted aeon session searched its own tree
for what that row meant and found **no booking, no doc, no lane-log entry, no ledger line** —
only the title. The findings were never lost; **the routing was.** A row naming another repo's
work, with no artifact on this side, is unreadable by every successor session, and it took a
peer's correction to recover it rather than anything in this tree.

So the rule this file enacts: **a finding routed to this lane gets an artifact in THIS repo at
the moment it is accepted, naming the peer revision it came from.** A queue row is a pointer, and
a pointer with nothing at the far end is indistinguishable from a row somebody invented.

---

## Anchors — all verified reachable here before this file was written

Verified 2026-09-06 with `git merge-base --is-ancestor <rev> origin/master` run in
`/home/volence/sonic_hacks/sigil` after a fetch; all four returned ancestor. SHAs supplied by the
sigil lane, emitted by their `git log -1`, and **re-verified here rather than transcribed on
trust**. Sigil `origin/master` was `4dc3c863` at verification time.

| file | sigil revision |
|---|---|
| `docs/superpowers/notes/2026-09-05-consuming-end-name-as-position.md` | `79767f26780ebb76b4d0414b5b7f8b58301d129a` |
| `docs/superpowers/notes/2026-09-05-p6-resweep-current-layout.md` | `ebd227296ab3b8765bf05a9765986afc029a5fc2` |
| `docs/superpowers/notes/2026-09-05-decouple-aeon-side-inventory.md` | `b0cf2eeb0474534410340b3faaa42d595dd82112` |

**Cite by HEADING, never by line number** — the sigil lane states the first file is still being
edited, and a coordinate into a live document is the rot this suite has already paid for twice.
The row name `S1S3S9` is section numbering inside the first file, which is why it reads as opaque
from this side; that opacity is the reason the row was unreadable, not an accident of spelling.

**Two things the sigil lane explicitly does NOT assert, carried here because dropping a peer's
own caveat is how a hedged claim hardens into a certified one.** (1) Whether any of this is still
true of the aeon tree *today*: every measurement is dated 2026-09-05 and the subjects are our
files, so **re-derive before pricing the work**. (2) They have not checked whether S1's and S9's
sites have moved since; the headings will hold, the internals may not.

---

## The three from the first file (the `S1S3S9` row)

### S1 — `tools/s4lint.py`: a byte offset inside the live object record inferred from a symbol's spelling

Heading: ``S1 — `s4lint.py` · `SST_FIELDS` / `SST_LEN` → `_resolve_sst_offset` → `check_e009` ``

A 26-row `Dict[str, int]` plus `SST_LEN = 0x50` is the tool's entire model of the object record,
and nothing measures it. Sigil verified it **already wrong** against `engine/objects/sst.emp`,
whose own header declares that file the sole author of the layout: six fields disagree, four
table entries name fields absent from the struct, and seven struct fields are absent from the
table. Only `SST_LEN` still agrees.

The failure is three classes at once: **silent** for stale-forward fields, **silent** for
unrecognised ones (`_resolve_sst_offset` returns `None`, so `check_e009` simply does nothing and
a rename switches the check off with no message), and **loud but misattributed** for
`SST_sst_custom`, where the error blames the assembly line's arithmetic for the table's
staleness.

**Priced by its blast radius, which sigil measured rather than assumed: E009 fires on nothing
today.** `build.sh` lints `games/${GAME}/game_root.asm`; the tree has three tracked `.asm` files
and a `SST_` grep across them is a genuine no-match. This is a loaded gun, not a firing one — and
the tool emits no signal that its coverage has collapsed to zero, which is the part worth fixing.

**Structurally fixable: YES** — the linter already tokenises `struct`/`ds.b`/`endstruct` and
walks the include graph, and the `.emp` side is the sole author. **Hazard that comes with the
fix, and it is why the staleness survived:** `tools/test_s4lint.py::test_sst_custom_base_no_error`
documents the stale constant as correct in its own docstring, so correcting the table turns a
green test red. **A green gate is currently locking in a false positive.** Anyone taking this
must expect the red and rule on it, not tune around it.

### S3 — four copies of "where does this routine end", and a fifth that already learned the lesson

Heading: ``S3 — four independent `routine_extent` implementations, one of which learned the lesson``

`instashield_gate`, `sprite_tilt_gate`, `loop_crossover_gate` and `waterline_art_gate` each infer
a routine's ROM extent as "up to the next symbol above it", and **none of the four filters phased
symbols**. `scene_spans.lst_proc_sizes` does, via `vma_phased_symbol_names()`.

**The fifth is the control and is what makes the other four legible** — this is not four sites to
fix by taste, it is one already-correct implementation and three that predate it. Propagate the
correction; do not re-derive a fifth opinion.

### S9 — `tools/effects_gen.py` decides POINTER IDENTITY by string-comparing symbol names

Heading: ``S9 — `effects_gen.py` · POINTER IDENTITY decided by string-comparing symbol NAMES``

`render_module`'s reels arm asks an **address** question — does any hand preset's `parallax:`
point at the same ROM object as this section's lowered record — and answers it by **name equality
on whatever identifier the argument happens to spell**. Any second name for one address (an
`equ`, a re-export through `scene_registry.emp`) reports no hit, the `reels` key is accepted, and
two sections resolve to one `Parallax_Current_Config` pointer.

Sigil calls it the purest instance of the whole pass's parameter, and the symptom is stated in
our own file: **nothing errors, nothing is missing, the wrong strips simply scroll.**

---

## The two from the second file

Both under heading ``6. Left open, and routed elsewhere``, items 2 and 3, marked "Aeon lane"
there. (Item 4 of that section is a correction sigil owes its own inventory, and is theirs.)

### The decaying dedup margin — a quantity nothing computes

`packed_data_end`'s distance to the next forbidden band is computable by `dplc_straddle` today
and **nothing computes it**. Measured decay: 5,686 B to 2,584 B of slack in seven days, about
440 B/day.

**This is the one with a clock on it.** A margin nobody measures is not a margin, and a decay
rate is the only form in which this can be a decision rather than a surprise. Note the shape it
shares with B7 (`bganim_room.py`'s unasserted terminus): both are quantities the tree depends on
that no gate observes, and both fail by staying quiet.

### Knuckles' ceiling equals the bar, with nothing stating it

`2 × 5 = 10` sits exactly at the limit and **nothing in the tree says so**, so the first change
that needs an eleventh finds out by breaking. A bar met exactly is indistinguishable from a bar
met with room, right up until it is not.

---

## Status on this side

> **WORKED 2026-09-06 on `parcel/s1s3s9`.** Every row below was **re-derived against this tree
> before it was priced**, as the caveat above demanded, and two of the five did not come back
> the way they went out. Verdicts:
>
> | row | verdict | where |
> |---|---|---|
> | **S9** — pointer identity by name | **REPRODUCES, and worse than booked. FIXED.** | `tools/effects_gen.py` |
> | **dedup margin** | **REPRODUCES. Now computed on every build.** | `tools/dplc_straddle.py` |
> | **Knuckles' `2 × 5 = 10`** | **DOES NOT REPRODUCE — the ceiling is 6, headroom 4.** | same commit |
> | **S3** — four `routine_extent` copies | **REPRODUCES as a class, LATENT as an instance. FIXED.** | the four gates |
> | **S1** — `s4lint.py`'s object model | **REPRODUCES exactly. DECLINED as out of scope — needs an owner ruling.** | below |
>
> **S9 — reproduces, and the booking understated it.** The dangerous second spelling for one
> address is not an exotic `equ`: it is **this generator's own published accessor**.
> `<stem>_sec_scene(sec: N)` is emitted as a `pub comptime fn -> Label` returning
> `EditorSceneBinding_<CAP>_SecN`, and the sibling raster chooser is already written in exactly
> that form in the shipped effects library — `raster: ojz_act1_sec_raster(sec: 5, hand:
> Raster_Program_None)`. An author writing the parallax channel the way the file next to it
> writes the raster channel defeated the refusal silently. The argument is now captured whole
> and classified; what cannot be decided is refused by name rather than guessed. The reels arm
> is live today (one scene authors `reels`) and both shipped `parallax:` arguments classify as
> plain symbols, so the new refusal trips no correct run; the bake is byte-identical.
>
> **The dedup margin — reproduces, and the clock is independently confirmed.** Sigil measured
> the growth-direction margin at 32,990 B on 2026-09-05; this tree measures **32,467 B** a day
> later, 523 B of decay against their stated ~440 B/day. Two things their note did not carry:
> the **shrink** direction is the tighter one (**8,815 B**), and the tightest margin is already
> **under the tree's own `DATA_GROWTH_RESERVE` (49,152 B)** — the straddle wall arrives before
> the growth the bank-placement rule holds room for. Emitted as a warning, not a failure, since
> that state is true of the shipped tree today.
>
> **Knuckles' ceiling — does not reproduce.** `2 × peak entries` is a valid upper *bound* on the
> ceiling, not the ceiling. The ceiling is `entries + how many of that frame's entries can
> straddle SIMULTANEOUSLY`, and every Knuckles frame names disjoint tile runs, so at most one
> entry can contain a boundary. **Measured ceiling 6, headroom 4** — not 10, not equal to the
> bar. Control, because a refutation of a peer's number needs one: the same function
> independently reproduces sigil's separately measured "Sonic's `$1E` splits 7 ways", and a
> brute-force sweep of a whole `0x20000` period at byte granularity matched the analytic ceiling
> for **all four subjects exactly**. What survives of the row is the half that mattered — the
> constraint was unstated, and it is now printed on every build with a `CEILING EQUALS THE BAR`
> tag that fires only at zero headroom. The correct constraint is not "≤ 5 entries per frame";
> it is `entries + simultaneous overlap ≤ 10`, so sigil's conclusion pointed at the wrong
> variable.
>
> **S3 — reproduces as a class, latent as an instance, and both halves are measured.** All six
> routines the four gates bound compute the same extent with and without the filter today, so
> nothing is mis-measured. That is the tree being *arranged* so the assumption holds, which is a
> different thing from it being checked — and the failure is not uniformly loud: an executing
> arm reports a false red, but a scanning arm just finds fewer instructions
> (`waterline_art_gate.proc_span`'s own docstring records arm 3 reporting "zero instances of
> instructions that are plainly there"). The correction is **propagated by importing the one
> derivation**, not restated four times. Planting a real phased name one byte inside each
> routine truncated all six to 1 B before and none after.
>
> **S1 — DECLINED, and this is the row that wants a ruling rather than a fix.** It reproduces
> exactly, with one number sharper than the booking's: the table says `SST_sst_custom = $32`;
> `engine/objects/sst.emp` says **`sst_custom: [u8; 32] @ $30`**. The blast radius re-measures
> as sigil found it — `build.sh` lints `games/${GAME}/game_root.asm`, the tree has three tracked
> `.asm` files, and `SST_` appears **0 times** in all three, so E009 fires on nothing. Under the
> 2026-09-06 hub ruling (tooling work only where it blocks a deliverable or ships wrong output)
> this ships nothing wrong and blocks nothing. It is declined here, not dropped: see
> `docs/DEFERRED_WORK.md`, "S1 — s4lint's object-record model", for the ruling it needs and the
> green test that is locking in the false positive.

`B7` (`tools/bganim_room.py`'s unasserted terminus, sigil's separate item from the third file)
is dispatched and is a sibling of the dedup-margin item above. The five here were bug tier under
the 2026-08-30 ordering, so they sat ahead of feature items.

---

# Addendum, same day: the sending-side enumeration

After the booking above, the sigil lane applied the rule's **sending-side twin to their own
board** rather than closing the single instance, and found **four rows naming this lane** where
two had reached us. That is the enumeration bar working in the direction it usually does not:
the sender asking who is at the far end of their own rows, instead of the receiver discovering a
gap. Two more arrive below, and one row arrives as an explicit **do not book**.

Anchors as before: sigil `b0cf2eeb0474534410340b3faaa42d595dd82112`,
`docs/superpowers/notes/2026-09-05-decouple-aeon-side-inventory.md`, re-verified here as an
ancestor of sigil `origin/master`, **and every row below read firsthand out of that blob** rather
than from the sigil lane's summary of it.

## D2 — a label row rots when CONTENT decides the label

Row **D2** (cited by row id; the file's rows are stable, its line numbers are not). The
`ojz_effects_editor_act1` block's `order` row in `games/sonic4/map.toml` must be keyed by
**section name**, not by head label, because the head label is **content-derived** — whatever the
generator happens to emit first.

**Nothing is broken today**: sigil's SECTION-ROW spelling resolves the name to the head label at
placement. It is named because it is a live example of the general rule, and sigil puts it in
**the same defect class as B7** — a row that is right until content moves under it, with nothing
announcing the moment it stops being right.

Verdicts, both carried rather than merged, because they are two lanes' readings and not one
conclusion: **sigil's** is that the fix belongs at our generator; **aurora's** is that the only
stated ordering requirement is determinism AMONG tables, so nothing requires tables before
bindings and it is probably a one-line move. **Unproven until a build refuses or does not** —
which is the whole test, and it is cheap.

## The F class — terminus proxies, and what it says about our enforcement surface

> **STATUS 2026-09-06, after `parcel/bganim-room-terminus` (B7) and `parcel/f-class-terminus`:**
> F1 · F2 · F4 · F5 · F6 · F7 **CLOSED**. **F3 PARTLY** — two unchecked arms asserted, the
> load-bearing half (object-bank section MEMBERSHIP is declared nowhere, so a bank section
> ordered after the cursor understates `used` invisibly) needs a map-schema change and is
> **owner/sigil-lane work**. A **SIXTH instance** was found from our side and is open:
> `tools/art_rom_report.py` gates the art-pool ROM budget on `getsize` of the embedded page
> blobs, with no listing and no ROM — its assumption holds today (all 10 pages measured) but
> nothing checks it. Full evidence, the controls, and the two F3 fixes considered and rejected
> are in `docs/DEFERRED_WORK.md` under "THE REST OF THE F CLASS".


The same note carries a class F this booking did not originally reach: *a named label standing in
for "the end of a region"*, seven rows, **all of them ours**. Read the class before working any
single row, because the shape repeats: each computes a high-water mark from one hardcoded label,
each feeds a gate that passes, and violating the proxy makes the number **wrong but plausible**
while the gate goes green.

- **F1** — `Art_Sonic` stands for the end of the packed run. This is **B7**, dispatched
  2026-09-06 on `parcel/bganim-room-terminus`.
- **F2** — `Art_Sonic`'s extent equals its embed's length exactly: one embed, no pad, nothing
  trailing inside the section. **The other half of B7's own expression** (`end = LMA + blob_len`),
  understating `packed_end` and so overstating room, failing in the identical direction. **Routed
  into the B7 parcel mid-flight** rather than left as a sibling row, because fixing one half of a
  two-part assumption in the same three lines is how the second half becomes invisible.
  `map.toml` concedes the fragility in its own words — *"a section with several embeds has no
  such instrument"* — which is why the character-data sections were ordered before
  `collision_data`. **That means the tree is currently ARRANGED so the assumption holds, which is
  a different thing from it being checked.**
- **F3** — `DeformTable_Zero` stands for the object bank's high-water mark, consumed by
  `tools/s4budget.py`. An explicit proxy: the map comment names its ancestry, having replaced the
  AS-era `if * > $20000` guard and the retired `__BUDGET_DATA` sentinel. **A real terminus was
  traded for a proxy label.** The `$20000` ceiling is declared; the measurement of what sits under
  it is not.
- **F4** — `EndOfRom` equals the ROM file size, in `s4budget.py`'s `format_rom_report()`.
  **ASSUMPTION and structurally un-failable**: the disagreement prints as a `NOTE:` line and is
  **never appended to `breaches`**, so it cannot fail a build. Padding, a stale file and a real
  placement error all read identically. Sigil verified this firsthand and recommends it
  independently; **booked as real.**
- **F5** — the three sound-bank art regions' extents equal their embed lengths
  (`tools/dplc_straddle.py`). Feeds the straddle calculation, so a pad silently shifts which
  frames are judged to cross a boundary.
- **F6** — `SOUND_BANK_OFFSET = 2 * BANK_ALIGN` encodes `sound_bank == dac_banks + 0x10000` and
  is **never compared against the declared `sound_bank` anchor**; sigil verified the constant
  appears at its definition and twice inside one failure-message f-string, nowhere else. The two
  anchors can drift apart with nothing on our side noticing. Offered to the B7 agent as optional,
  with permission to decline it rather than stretch that parcel.
- **F7** — growth in `ojz_bg_anim` shifts the whole run `Map_TestObj .. Art_Sonic` downstream
  into the room under `dac_banks`: the ordering premise that makes the ceiling arithmetic mean
  anything.

**The sentence in that note worth more than any single row:** only **three** hard placement
checks live on aeon's build side (B6, B8, C1); all three are post-sigil listing readers, all
three are `sonic4`-only, all three are skipped under `FAST=1` — and **two of the three rest on F1
and F2, which nothing checks.** That is the argument for B7 being bug tier, and it is a much
stronger argument than B7's own row makes on its own.

## NOT BOOKED — `S4BUDGET-STALE-ASSUMPTION`, and why the refusal is the useful part

Sigil's own board carries a row reading *"their budget tool reports a value UNMEASURED while the
data it needs sits in the listing it just read."* **They searched their tree and could not match
that sentence to any artifact**, and told us so instead of restating it. Their instrument was
working — `s4budget` appears in 14 files there — so it is a genuine non-match, not an empty grep.

What their tree *does* hold about `s4budget` is two rows that are **not** that claim: **F4**
(above), and **E2**, whose finding runs in the **opposite** direction — that `UNMEASURED` is
never rendered as a number, with a docstring recording a prior defect where a dead parser
reported RAM `0KB/64KB` for a long time.

So one of two things is true and neither lane knows which: the artifact is somewhere their search
missed, or **the row's wording drifted from its source and is now a reconstruction.** Sigil is not
asserting the finding is false, only that they cannot show what it rests on.

**Their framing of the risk is the sharpest thing in this whole exchange and is why this section
exists rather than a silent omission:** *a row that has drifted from its source reads exactly
like a row with a source.* Had we asked for that one, they would have restated it in good faith
and we would have booked a finding **no measurement stands behind** — arriving with a peer's
confidence attached, which is what makes it expensive. This is the morning's own defect
(`S1S3S9`) run one step further: there, a row pointed at an artifact we could not see; here, a
row may point at no artifact at all, and the two are indistinguishable from the receiving end.

**Do not book it, and do not work it from the sentence.** If it is real it will re-derive from
our own tree, and that is the only form in which it should enter this file.
