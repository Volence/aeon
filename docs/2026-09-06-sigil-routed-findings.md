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

Booked, not started. `B7` (`tools/bganim_room.py`'s unasserted terminus, sigil's separate item
from the third file) is dispatched and is a sibling of the dedup-margin item above. The five here
are bug tier under the 2026-08-30 ordering, so they sit ahead of feature items, and each one is
**re-derived against the current tree before it is priced** — sigil's measurements are a week
old by the standards of a tree this active, and they said so themselves.
