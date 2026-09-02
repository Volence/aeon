# Chain 198: where the +4 in `DEBUG_ASSEMBLED_LEN` is

Read-only forensic investigation, 2026-09-02. Subject: sigil
`crates/sigil-harness/tests/repin_pins.rs:1151` asserts `pins::DEBUG_ASSEMBLED_LEN == 0xA7F34`;
the generated `crates/sigil-harness/src/pins.rs:44` now reads `0xA7F38`. The ledger term for
chain 198 (`item5-cycles-variants`) needs a cause that was measured, not one that fits.

Candidate story under test: *the +4 is a 4-byte `dc.l` table row that chain 198 added in the
DEBUG shape only.*

---

## 1. Verdict

**CONFIRMED, and identified to a single named span.**

The +4 is the third `dc.l` row of `Debug_BandDemoHotkey`'s `.raster_table` in
`games/sonic4/test/ojz_scroll_test.emp`. The table goes 2 rows (8 B) to 3 rows (12 B). The
whole proc, table included, is inside `if DEBUG == 1`, so the release shape emits none of it
and `ASSEMBLED_LEN` holds at `0xA5C82`.

The identification is a *unique* per-region attribution, not a consistency argument: the +4 is
the only length change anywhere past the absorbing bank anchor, in either shape.

---

## 2. Evidence, per region

### 2.1 Provenance and artifacts re-derived, not inherited

Both reference trees carry all four ROMs and their `.lst` files, and every one matches the
frozen provenance row byte-for-byte:

| artifact | chain 197 (`.aeon-ref-197`, aeon `8dd28114`) | chain 198 (`.aeon-ref-198`, aeon `73b07a4f`) |
|---|---|---|
| `s4.bin` | 719347 / crc32 `f403f461` | 719440 / crc32 `df76de71` |
| `s4.debug.bin` | 736354 / crc32 `50545389` | 736454 / crc32 `0d6d1175` |
| `demo.bin` | 96458 | **byte-identical** (md5 `66cf5b15…`) |
| `demo.debug.bin` | 101323 | **byte-identical** (md5 `e80ec439…`) |

`EndOfRom` read out of the listings: plain `0xA5C82` in BOTH chains; debug `0xA7F34` ->
`0xA7F38`. `EndOfRom` is exactly `DEBUG_ASSEMBLED_LEN`, so the pin drift is the debug ROM's
own last emitted address moving, +4.

### 2.2 The exhaustive delta walk

Method: parse every `(N) i/ADDR : Name:` line out of each listing, intersect on name, sort by
the chain-197 address, and print every point at which `addr198 - addr197` *changes*. This
enumerates every span whose length moved; nothing can hide between two printed transitions.
Parsed 2314/2317 symbols (plain) and 2747/2750 (debug); 0 symbols disappeared, 3 appeared in
each shape.

**PLAIN — 4 transitions, total holds:**

```
0x000000 -> 0x000000  d=+0x0   Vectors
0x01324c -> 0x01327a  d=+0x2e  EditorRaster_OJZ_Act1_ojz_sec5_showcase
0x01327a -> 0x0132b8  d=+0x3e  OJZ_TestRaster
0x090000 -> 0x090000  d=+0x0   Dac_Temp_Blip
```

**DEBUG — 6 transitions, total +4:**

```
0x000000 -> 0x000000  d=+0x0   Vectors
0x013a96 -> 0x013ac4  d=+0x2e  EditorRaster_OJZ_Act1_ojz_sec5_showcase
0x013ac4 -> 0x013b02  d=+0x3e  OJZ_TestRaster
0x090000 -> 0x090000  d=+0x0   Dac_Temp_Blip
0x0a688e -> 0x0a6892  d=+0x4   OJZ_SectionMarkerColors      <-- the whole pin drift
0xffff0000 -> 0xffff0000 d=+0x0 Tile_Cache_Nametable         (RAM; not ROM)
```

Both shapes carry an identical `+0x3E` of new content upstream and both return to `d=0` at
`Dac_Temp_Blip` (`0x90000`) — the fixed sound-bank org anchor absorbs all 62 bytes in *both*
shapes. Past that anchor, plain has **zero** further transitions; debug has exactly **one**.

### 2.3 The span that grew

The last delta-0 symbol before the step is
`$games.sonic4.ojz_scroll_test$Debug_BandDemoHotkey$raster_table`, and the step is at the next
symbol. So the grown span is `[.raster_table, OJZ_SectionMarkerColors)`:

| | 197 | 198 |
|---|---|---|
| `…Debug_BandDemoHotkey$raster_table` | `0xA6886` | `0xA6886` |
| `OJZ_SectionMarkerColors` | `0xA688E` | `0xA6892` |
| **span length** | **8 B** | **12 B** |

The proc *body* — `Debug_BandDemoHotkey` `0xA67C8` to `.raster_table` `0xA6886` = `0xBE` — is
unchanged in both chains, as are all four of its interior labels (`$no_wrap`, `$not_on`,
`$done`, and the two `$diag27$…` sites). `RASTER_CYCLE_COUNT` moved 2 -> 3, but it lowers to a
comptime immediate and costs nothing.

### 2.4 The bytes themselves, read out of the ROMs

Not "a 4-byte growth" — three well-formed longwords, each equal to a listing address:

```
197 s4.debug.bin @0xA6886, 16 B:  00013ae6 00013a48 | 000e00e0 0e0000ee
198 s4.debug.bin @0xA6886, 20 B:  00013b24 00013a48 00013a96 | 000e00e0 0e0000ee
```

Resolving each longword against the listings:

| row | 197 value | 198 value | symbol | note |
|---|---|---|---|---|
| 0 | `0x013AE6` | `0x013B24` | `OJZ_BandDemo` | hand-authored `.emp`; sits after the insertion, so it takes the full `+0x3E` |
| 1 | `0x013A48` | `0x013A48` | `EditorRaster_OJZ_Act1_authored_probe` | ahead of the insertion, unmoved |
| 2 | — | `0x013A96` | `EditorRaster_OJZ_Act1_ojz_sec3_shimmer` | **NEW** — the added row |

Row 2's value is exactly the listing address of the symbol chain 198 minted. The trailing
`000e00e0 0e0000ee` is `OJZ_SectionMarkerColors`' first payload, visibly displaced by 4.

### 2.5 The source, for corroboration only

`git diff 445a5856~1 73b07a4f -- games/sonic4/test/ojz_scroll_test.emp`:

```
     const RASTER_CYCLE_COUNT = 2      ->  3
     .raster_table:
         dc.l    OJZ_BandDemo
         dc.l    EditorRaster_OJZ_Act1_authored_probe
+        dc.l    EditorRaster_OJZ_Act1_ojz_sec3_shimmer
```

The diff is listed last on purpose: the measurement above stands without it.

### 2.6 Where the other 62 bytes are (and why they are not in the +4)

Measured spans in the chain-198 debug listing:

| symbol | 197 | 198 | span |
|---|---|---|---|
| `EditorRaster_OJZ_Act1_ojz_sec3_shimmer` | — | `0x13A96` | 46 B (to `…sec5_showcase` `0x13AC4`) |
| `EditorCycle_OJZ_Act1_ojz_sec3_shimmer` | — | `0x13AF2` | 8 B (to the variant) |
| `EditorVariant_OJZ_Act1_ojz_sec3_shimmer_0` | — | `0x13AFA` | 8 B (to `OJZ_TestRaster` `0x13B02`) |

46 + 8 + 8 = 62 = `0x3E`, which is exactly the cumulative delta reached at `OJZ_TestRaster`,
in both shapes. `…sec5_showcase`'s own span holds at `0x2E` across the chain. All 62 bytes are
org-anchor absorbed at `0x90000` and reach neither total.

---

## 3. The falsifier

**If the story were false, I would have expected at least one of:**

1. The debug delta walk stepping at a symbol *other than* `OJZ_SectionMarkerColors` — i.e. the
   4 bytes living in some other proc, an alignment pad, or a re-encoded branch.
2. Offsetting transitions past the anchor (say `+8` at one span and `-4` at another) summing to
   +4, in which case no single region is the cause and "the dc.l row" would be a fiction.
3. The grown span's last 4 bytes being **zeros or a non-address** — the signature of alignment
   padding rather than a pointer row.
4. A matching `+4` in the **plain** total, which would make the row shape-invariant rather than
   DEBUG-only, and would break the "DEBUG shape only" half of the claim.
5. The 62 content bytes only *partly* absorbed — e.g. 58 absorbed and 4 leaking — which would
   produce the same `+4` from a completely different mechanism and is the most seductive
   alternative, because it also reconciles the arithmetic.

**What I actually looked for and saw:**

1 and 2 — the transition walk is exhaustive over all 2747 common debug symbols by construction,
and prints five transitions, of which exactly one lies past `0x90000`. There are no offsetting
pairs anywhere. Attribution is unique.

3 — read the ROM bytes directly (§2.4). The four added bytes are `00 01 3A 96`, which equals the
listing address of the newly minted `EditorRaster_OJZ_Act1_ojz_sec3_shimmer`. A pad would have
been zeros; a coincidence would not have landed on a symbol that did not exist one chain ago.

4 — `ASSEMBLED_LEN` holds at `0xA5C82`, and the release listing shows `Debug_BandDemoHotkey`
parked at `0xA45DC` as a **zero-byte label**, sharing that address with `Debug_CharacterHotkey`,
`Debug_SceneCycleHotkey` and `Debug_Warp_Consume` — the label-parking idiom the ledger already
documents. None of its interior labels, `.raster_table` included, exist in `s4.lst` at all.
*Instrument check, per the standing trap:* `grep raster_table s4.lst` is **not** empty — it
returns one line, the unrelated struct-field equate `Sec_sec_raster_table = $00000018`. So the
absence of the table label is a positive read of a non-empty result, not an unverified zero.

5 — refuted by the plain shape acting as the control. Both shapes carry the identical `+0x3E`
and both return to `d=0` at `Dac_Temp_Blip`. If absorption were partial, plain would have
leaked the same residue and `ASSEMBLED_LEN` would have moved. It did not.

**Negative control, on two axes:** `demo.bin` and `demo.debug.bin` are byte-identical across
197 -> 198. Demo links neither `ojz_scroll_test` nor the editor presets, so nothing should move
— and nothing did, across the compiler change as well as the parcel. That also settles the
chain's *other* commit: `73b07a4f`'s edit to `engine/level/parallax_dsl.emp` (engine code, in
every profile's use closure) touches only comments and `ensure` message strings, and
`demo.debug.bin` holding byte-identical is what proves it emitted nothing.

---

## 4. Draft ledger term

For `assert_eq!(pins::DEBUG_ASSEMBLED_LEN, …)`:

> `+4 item5-cycles-variants` (DEBUG-only, and the whole delta: `Debug_BandDemoHotkey`'s
> `.raster_table` takes a third `dc.l` row for `EditorRaster_OJZ_Act1_ojz_sec3_shimmer` —
> measured per region rather than argued, the span `.raster_table`..`OJZ_SectionMarkerColors`
> goes `0xA6886`..`0xA688E` -> `0xA6886`..`0xA6892`, 8 B -> 12 B, and the added longword reads
> `00013A96` in the ROM, exactly the new symbol's address. It is the ONLY span that moves past
> the `0x90000` bank anchor in either shape. Plain HOLDS at `0xA5C82` because the proc is inside
> `if DEBUG == 1` and parks as a zero-byte label on `0xA45DC` beside three other gated hotkeys.
> The parcel's 62 B of real content — the 46 B preset record, 8 B cycle, 8 B variant — is
> emitted in BOTH shapes and org-anchor absorbed, which is why neither total carries it.)

For `assert_eq!(pins::ASSEMBLED_LEN, …)`:

> `HOLDS item5-cycles-variants` (the 62 B of new content — `EditorRaster_…_ojz_sec3_shimmer`
> 46 B, `EditorCycle_…` 8 B, `EditorVariant_…_0` 8 B, measured as listing spans — is emitted in
> the release shape and absorbed at the `0x90000` sound-bank anchor: the delta profile reaches
> `+0x3E` at `OJZ_TestRaster` and returns to 0 at `Dac_Temp_Blip`. The discriminator that this
> is ABSORBED and not DEBUG-fenced: the release FILE grew +93 (719347 -> 719440) for deb2
> records the release shape really minted, three new symbols' worth.)

---

## 5. Contradiction found in the frozen record

**The chain-198 provenance prose decomposes the file deltas wrongly, and its own `anchor_end`
fields refute it.** It reads:

> "Release +93 = 62 bytes of new content … + 31 bytes of deb2 appendix; debug +100 = 62 + 4
> (the dc.l table row) + 34 appendix."

Both sums are arithmetically valid (62+31=93, 62+4+34=100) and both are wrong about the
mechanism: they let the 62 content bytes reach the file end. They cannot. The deb2 appendix
starts at exactly `EndOfRom` with no padding (magic `de b2 04 02` read at `0xA5C82` /
`0xA7F34` / `0xA7F38` in all four ROMs), so `file_delta = assembled_delta + appendix_delta`
identically. Measured:

| shape | appendix 197 | appendix 198 | appendix delta | assembled delta | file delta |
|---|---|---|---|---|---|
| release | 40305 | 40398 | **+93** | **0** | +93 |
| debug | 48430 | 48526 | **+96** | **+4** | +100 |

So the true decomposition is *release +93 = 0 assembled + 93 appendix* and *debug +100 =
4 assembled + 96 appendix*. The prose's own row records `s4 anchor_end = 0xa5c82` unchanged —
if 62 content bytes had reached the tail, that field would have moved by 62 too.

The provenance correctly flagged its appendix figures as "DERIVED arithmetic … labelled as
derived because the prefix-packed appendix could not be confirmed a second way". The
derivation, not the measurement, is what was wrong: it subtracted the content bytes from the
file delta before attributing the remainder, and those bytes never left the absorbed region.
This does not disturb the +4 verdict, which is measured directly and never depended on the
appendix arithmetic. Recording it here because a future term that reuses "62 + 4 + 34" would
inherit the error.

Second, smaller note: the brief framed the +4 as something "chain 198 added in the DEBUG shape
only". Precise as far as it goes, but worth stating the scope — the *parcel* is not DEBUG-only.
It adds 62 bytes that ship in `s4.bin`; only the table row that makes the new preset reachable
from the hotkey cycle is DEBUG-gated.

---

## Method notes / reproduction

Listings parsed with the regex `^\(\d+\)\s+\d+/([0-9A-Fa-f]+)\s*:\s*(.*?):\s*$` over
`.aeon-ref-197/*.lst` and `.aeon-ref-198/*.lst`; ROM bytes read with plain `seek`/`read` at the
listing addresses. No emulator was used and none is needed — every claim here is a static
property of the four frozen artifacts. Nothing was rebuilt; no cargo command was run.
