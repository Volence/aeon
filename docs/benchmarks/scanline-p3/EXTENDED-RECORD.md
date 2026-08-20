# The extended record — the typed conditional-data spike, and what it bought

**Parcel:** Scanline P3, Phase 1, Task 8 (`docs/superpowers/plans/2026-08-20-scanline-p3-walker-mechanisms.md`)
**Branch:** `p3/t8-extended-record`
**Design:** §3.1 — "Record shapes are capability-dependent. No-new-capability scenes lower to
the EXISTING 28-byte header + 10-byte entries byte-identically. Extended records exist only
in games whose mask includes MULTI_DEFORM_TABLE."

---

## 1. THE SPIKE — run FIRST, before anything was authored on it

Design §3.1 offers two forms and prices them: the typed one, or "the proven untyped
`if CAP {..} else {Data.empty}` form", which "forfeits size-annotation pins". Task 8 Step 1's
rule is that the typed form is proven to round-trip **before** the addressing rewrite depends
on it, and that a failed spike STOPS the leg for a ruling rather than inventing a second
emission path.

**VERDICT: the typed form is PROVEN. The untyped fallback was not taken and no
size-annotation pin was forfeited.**

### 1.1 What "typed conditional data" can and cannot be in this language

The first thing the spike settled is that the obvious spelling does not exist.
`crates/sigil-frontend-emp/src/parser.rs:544-600` enumerates every item opener — `use`,
`const`, `equ`, `enum`, `bitfield`, `struct`, `offsets`, `table`, `dispatch`, `vars`,
`region`, `data`, `extern`, `proc`, `type`, `interface`, `implement`, `context`, `script`,
`newtype`, `align` — and **`if` is not among them.** So

```emp
if CAP != 0 { pub struct band_entry { ...ext... } } else { pub struct band_entry { ...legacy... } }
if CAP != 0 { pub data X: ExtCfg = ... }          else { pub data X: LegacyCfg = ... }
```

are both ungrammatical, and a `data X: T` binding carries exactly one type annotation, so the
two-types-one-binding route is closed too. The untyped conditional in this tree
(`games/sonic4/data/sound/mt_bank.emp:154`, `data Song_DrumTest = if DEBUG == 1 { Blob } else
{ Data.empty }`) is untyped precisely because it is an *expression*-level conditional with no
`: T`, which is why it forfeits the pins.

**The form that works is to parameterise the TYPE, not to choose between two types.** A
record whose trailing field is an array of an extension struct, with the array's LENGTH a
capability-derived comptime constant (1 or 0), is one type whose shape and `sizeof` are
capability-selected — and a zero-length array field emits zero bytes.

### 1.2 The spike, as run

Appended to `games/sonic4/data/effects/scene_registry.emp` (a PLACED, byte-emitting module —
emission is half the claim, and an unplaced module emits nothing), built with
`FAST=1 DEBUG=1 ./build.sh`, read back out of `s4.debug.bin` at the address `s4.debug.lst`
gives for the symbol. Removed again before Step 2; it is reproduced here in full because a
spike whose source is gone is a claim, not evidence.

```emp
const SPIKE_EXT_N = 0                      // flipped to 1 for the second arm

struct spike_ext (size: 4) { sx_tbl_a: u16, sx_tbl_b: u16 }
struct spike_entry (size: 4 + 4*SPIKE_EXT_N) {
    se_top: u16,
    se_a:   u8,
    se_b:   u8,
    se_ext: [spike_ext; SPIKE_EXT_N],
}
struct SpikeCfg2 { hdr: u16, bands: [spike_entry; 2] }

comptime fn spike_band(t: int) -> spike_entry {
    return spike_entry{ se_top: t, se_a: $A1, se_b: $B2,
                        se_ext: if SPIKE_EXT_N == 1 { [ spike_ext{ sx_tbl_a: $1234, sx_tbl_b: $5678 } ] } else { [] } }
}

ensure(sizeof(spike_entry) == 4 + 4*SPIKE_EXT_N, "...")
ensure(offsetof(spike_entry, se_ext) == 4, "...")
ensure(sizeof(SpikeCfg2) == 2 + 2*sizeof(spike_entry), "...")

pub data Spike_Record: SpikeCfg2 = SpikeCfg2{ hdr: $ABCD, bands: [ spike_band($0104), spike_band($0209) ] }
```

### 1.3 Both arms round-tripped, byte for byte

Read out of the built ROM at `Spike_Record` = `$12C96`:

| arm | bytes at `Spike_Record` | reading |
|---|---|---|
| `SPIKE_EXT_N = 0` | `AB CD  01 04 A1 B2  02 09 A1 B2` | header + **two 4-byte** entries, extension absent |
| `SPIKE_EXT_N = 1` | `AB CD  01 04 A1 B2 12 34 56 78  02 09 A1 B2 12 34 56 78` | header + **two 8-byte** entries, extension INTERLEAVED at the right stride |

Four separate facts land in those two rows, and each was a real question before it was run:

1. **A zero-length array field is legal and emits nothing** — no padding, no placeholder byte.
2. **`struct (size: <comptime expr>)` accepts a capability-derived size** (4 and 8 from one
   declaration).
3. **A single-level `if` in struct-literal field position picks an array literal correctly in
   BOTH arms**, including the empty `[]`. This is the EMP_PITFALLS §1 neighbourhood (a nested
   if-expression yields unit *silently*), which is exactly why the proof is bytes rather than
   a green build: a unit-folded arm would have shown up as wrong bytes here.
4. **The stride is the record's, automatically** — the second entry starts at +4 / +8 with no
   arithmetic authored anywhere.

### 1.4 The pins are LIVE — proven red, both of them

The whole reason to prefer the typed form is the pins it keeps. Neither is taken on trust:

**Size-annotation pin.** `struct spike_entry (size: 4 + 4*SPIKE_EXT_N + 1)` (one byte wrong,
extension arm):

```
error: native build (sonic4 debug): build_program: 4 error(s);
  [Error] struct spike_entry: declared size 9 but fields total 8
```

**Array-length pin on the typed `data` binding.** `bands: [spike_entry; 3]` against a
two-element literal:

```
  [Error] array length mismatch: expected 3 element(s), got 2
  [Error] SPIKE: sizeof(SpikeCfg2) = 26
```

That second one is the pin `scene_registry.emp`'s own banner calls "the ONLY enforcement that
a lowering produced the right number of bands" — it survives the capability parameterisation
intact, which is the property the untyped fallback would have thrown away.

---

## 2. Correction C5, checked against the tree rather than the design

The plan's C5 says the design's claimed pin `ensure(sizeof(band_entry)==10)` does not exist.
Confirmed, and here is what does exist, after T7's reshape:

| the design claims | the tree actually has | what Task 8 did with it |
|---|---|---|
| `ensure(sizeof(band_entry)==10)` in parallax.emp | an **evenness-only** ensure inside the copy generator | rewritten against `sizeof(band_entry)`, never against 10, so it carries to the extended size — evenness of prefix + extension, not of prefix alone. **Proven red:** inverting it fails the build THREE times, once per call site |
| — | `engine/ram.emp:38` `BAND_ENTRY_LEN = 10`, pinned by `ensure(extern("band_entry_len") == BAND_ENTRY_LEN)` | **untouched.** `band_entry` keeps its ten fields for ever (§3 explains why it must), so the harvested length and its mirror do not move |
| the record change moves RAM (axis 6) | `Parallax_Shadow_Bands` = `BAND_ENTRY_LEN * MAX_PARALLAX_BANDS` = 80 B | **does not move.** The extension is empty in both shipped games, so `sizeof(band_record)` is 10 and the reservation is the same 80 B. The DEBUG shape's RAM row is unchanged at **6.5 KB free** (release 16.7 KB), read off the build, not assumed |

Two guards were added so that a future widening cannot be silent, since ram.emp cannot see
the capability itself (§3): the reservation is pinned to `sizeof(band_record) *
MAX_PARALLAX_BANDS` through the resolved RAM span, and `PARALLAX_STATE_LONGS` now carries a
DERIVED extension term instead of a hand-added one, so widening `BAND_ENTRY_LEN` is the ONE
edit a capability flip needs. Both fire together, both name the constant:

```
error: declared-chain drift guard FIRED: 2 error(s); first
  "Parallax_Shadow_Bands reserves fewer bytes than the shadow view needs:
   sizeof(band_record) x MAX_PARALLAX_BANDS = 160 — widen BAND_ENTRY_LEN in engine/ram.emp
   by sizeof(band_ext)"
```

---

## 3. WHAT DID NOT LAND, AND WHY — the capability cannot reach the layout

**This is a partial landing and the boundary is exactly here.** The record shape, the
lowering, the strides, the witness and the copies all shipped. The one thing that did not is
the record shape SELECTING ITSELF from the game's declared mask. The natural spelling

```emp
pub const BAND_EXT_N = if (Game.SCANLINE_CAPS & CAP_MULTI_DEFORM_TABLE) != 0 { 1 } else { 0 }
```

was written, built, and rejected by the compiler. **Three contexts have no contract binding
at all**, each measured on 2026-08-20:

| context | diagnostic |
|---|---|
| the layout of an emitted `data` binding's record type | `unknown name Game.SCANLINE_CAPS` — **twenty of them, one per shipped config record** |
| `harvest_engine_struct_offsets` (the ambient `STRUCT_OFFSET_TWINS` layout: one file + `types.emp`, no profile, no defines, no contract) | `harvest_engine_struct_offsets: layout band_entry: unknown name Game.SCANLINE_CAPS` — dies before a byte is emitted |
| `harvest_engine_ram_addresses` (the focused `use engine.ram`-only build) | `ram harvest build_program: unknown name Game.SCANLINE_CAPS` — so ram.emp cannot size a reservation by capability either |

And inside a `comptime fn` body it is worse than absent: it degrades to a LABEL
(`` `&` not defined for label and int ``), the EMP_PITFALLS §2 call-site rule biting a
contract member. Design §3.1 independently forbids a scene constructor from reading the
capability set, so that route was closed anyway.

**A build DEFINE is visible in all three.** This is the measurement that turns the blocker
into a one-line ask rather than a research project: with `BAND_EXT_N` driven off `DEBUG`,
the whole mechanism — record type, registry arrays, `scene_band()`, witness — built and
`s4.debug.bin` came out **byte-identical** at `d7b36f90`. Nothing about the mechanism is
wrong; its input is out of reach.

**The ask, booked in `docs/DEFERRED_WORK.md`:** expose each game's declared `SCANLINE_CAPS`
as an `emp_defines` row (`crates/sigil-harness/src/native.rs`, beside `MAX_RING_BUFFER`),
cross-pinned to `Game.SCANLINE_CAPS`.

**What shipped instead, and its exact ceiling.** `BAND_EXT_N` is a literal `0` in
parallax.emp, pinned two-directionally against `Game.SCANLINE_CAPS` in scene_registry.emp,
where both names are visible. Both directions are proven red:

```
[Error] this game declares CAP_MULTI_DEFORM_TABLE in Game.SCANLINE_CAPS (63) but
        engine/level/parallax.emp's BAND_EXT_N is 0 — the lowered band record would carry
        no per-layer deform extension while the scenes demand one. …
[Error] engine/level/parallax.emp's BAND_EXT_N is 1 but this game does NOT declare
        CAP_MULTI_DEFORM_TABLE (Game.SCANLINE_CAPS = 31) — every band would carry
        sizeof(band_ext) bytes of ROM and shadow RAM that nothing reads …
```

So a capability flip is a loud, single-constant edit rather than a silent wrong lowering.
**The ceiling: one engine constant cannot be 0 for one game and 1 for another, so this tree
cannot carry two games that disagree about the bit.** That is precisely what the define
buys, and it is why the item is booked rather than closed.

### 3.1 Why the record is TWO structs

`band_entry` is one of sigil's `STRUCT_OFFSET_TWINS`
(`crates/sigil-harness/src/native.rs:1348-1357`), harvested ambiently to produce
`band_entry_len` for `engine/ram.emp`'s mirror pin. That layout sees one file plus
`types.emp` — no profile, no defines, no contract — so a harvested struct's size expression
may not name anything else. Putting the extension on `band_entry` therefore fails the whole
build before emission. The legacy twin stays contract-free and never gains a field;
`band_record` (`br_base: band_entry` at offset 0, `br_ext: [band_ext; BAND_EXT_N]`) is the
capability-shaped composite, deliberately absent from that list. Every field reference in
the walker is still spelled `band_entry.<field>(aN)` because the prefix is at 0.

### 3.2 A trap this cost real time — importing a struct re-elaborates its declaration

A module that imports `band_record` must also import `band_entry`, `band_ext` and
`BAND_EXT_N`, even though it never spells them: the declaration is re-elaborated in the
importing module's own name environment. A partial import fails **pointing at the
declaration**, in parallax.emp, naming types parallax.emp plainly declares — forty
diagnostics blaming a correct file. Written up as EMP_PITFALLS §8; the three importers are
named at the declaration itself so the next reader is not sent hunting.

---

## 4. Byte accounting — all four shapes, before and after

Four full canonical builds each side (not `FAST=1`), so the pytest / `emp_expect_fail` /
budget lanes are included in the green.

| shape | before | after | length |
|---|---|---|---|
| `s4.bin` | `445092a7` | `445092a7` | 699108 |
| `s4.debug.bin` | `d7b36f90` | `d7b36f90` | 715010 |
| `demo.bin` | `9320c210` | `9320c210` | 96336 |
| `demo.debug.bin` | `2ef6bf83` | `2ef6bf83` | 101044 |

**All four unchanged** — no repin, no refreeze, nothing to re-derive. The deb2 trap (a
zero-byte label moves `demo.bin` while `s4.bin` sits still) is why all four are taken rather
than sonic4 alone.

RAM rows, read off the builds: sonic4 DEBUG **6.5 KB free** before the stack (the shape the
plan says to gate on, not release's 16.7 KB) — unchanged, as is `Parallax_Shadow_Bands` at
80 B, so **axis 6 does not move**.

**The §8.1 capability-off witness is REACHED.** `SIGIL_WARNINGS=full DEBUG=1 ./build.sh`
lists 35 `[module.unreachable]` modules; `games.sonic4.scene_equiv_proof` is not among them,
nor is `scene_registry`, `ojz_scroll_test` or `engine.parallax`. (A count, not a gate — the
load-bearing part is the absence of those four names.) The witness also gained the size pin
its field-wise proofs structurally cannot make: all 67 comparisons run through `.br_base`
and would keep passing if every record grew a tail.

---

## 5. The copies — three sites, one size, both directions

Before Task 8, a whole entry moved in three places and only ONE was derived from the struct:
Step 4a called the generator, while `.anchor_shift_band` and the split-entry write were
hand-unrolled three-move runs carrying the 10-byte shape as instructions. A field added to
the record would have lengthened one run and silently TRUNCATED two.

`copy_band_entry()` is now `copy_band_entry_fwd(src, dst)` + `copy_band_entry_back(cur)`
over one shared `copy_run_longs()`. Both directions are generated because they are not
interchangeable: forward is two post-incrementing cursors; backward is one pre-decrementing
cursor writing each piece a whole entry forward, which the shift-down walk requires. A
backward run is the forward run reversed, so a shared width source is what stops them
drifting apart.

**Evidence:**

- **byte-identical** at all three sites — the CRC table in §4 covers this change too;
- **live at all three sites**: inverting the generator's evenness ensure fails the build
  **three times**, one diagnostic per call site;
- **the direction is load-bearing**: emitting the backward run's trailing word after the
  longs instead of before moves `s4.debug.bin` to `760cccfa`. Restored.

---

## 6. What Task 9 inherits

- `band_ext` is authored and shaped: two table pointers, two speed bytes — exactly what
  `own(table, shift_a/b, phase, speed)` adds over `shared`, since `shift_a/b` and `phase`
  already live in the legacy prefix as `band_deform_shift_a/b` and `band_phase_offset`.
- The extension arm of `scene_band()` is DEAD in both shipped games and is labelled as such
  in the source; its only evidence is §1's spike. **Its reachability belongs on Task 15's
  poison list** — dead code is not coverage.
- **No capability-gated CODE block exists for `CAP_MULTI_DEFORM_TABLE`**, so no
  `.cap_multi_deform_table_<site>_begin/_end` bracket was authored: the shape is data-side
  and the walker's displacements are comptime constants, not branches. Task 9's per-band
  table load inside `.cap_deform_sample_*` is the first site that needs the bracket. The
  span tooling does not require a promoted bit to have a site
  (`tools/test_scene_span_labels.py`, 11 passed), so nothing is left vacuous by the absence.
- Turning the mirror back into a derivation is the DEFERRED_WORK item above; until it lands,
  Task 9 raising the bit means editing `BAND_EXT_N` **and** `BAND_ENTRY_LEN` — and the build
  will say so, in both places, in that order.
