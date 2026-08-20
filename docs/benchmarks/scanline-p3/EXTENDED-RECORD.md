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
