# Does appending Sonic's art disturb anything else? — a measurement

**Discharges the condition the hub attached to the `d-47-revised` ruling:**

> *before any art ships, MEASURE the risk this lane flagged as unmeasured — that
> appending art disturbs nothing else. **A measurement, not the argument.***

The condition exists because reasoning is what produced d-47's two wrong numbers.
So the deliverable is an instrument (`tools/dplc_straddle.py`, gated in
`build.sh`) and numbers. Nothing below is inferred from the card; every figure is
re-derived from source, the shipped blobs, and a fresh listing of both canonical
shapes.

**Verdict in one line:** the ruled `targeted` re-cut disturbs **nothing
measurable** — but *"appending art disturbs nothing"* is **false as a general
claim**, and the margin protecting this particular append is **5,188 bytes**, not
"nothing to worry about".

---

## 1. The falsifier, banked first

This section is written before the derivation on purpose. At a session boundary
the derivation is the perishable half; a falsifier survives without it and is
still a working instrument.

**Appending art DOES disturb something if any of these is true.**

| # | Falsifier | Verdict |
|---|---|---|
| **F1** | The set of DPLC entries whose DMA source **straddles a `$20000` boundary** changes. A straddling transfer is split by `QueueDMA` into **two** queue entries, so it costs an extra Important slot — the exact resource d-47 is budgeting. | **NOT FIRED** (at this append) |
| **F2** | Any ROM address downstream of the insertion point moves, and something hard-references it. | **NOT FIRED** |
| **F3** | Post-append room under the `dac_banks` anchor drops below `DATA_GROWTH_RESERVE`, or the bank placement rule re-fires and moves an anchor. | **NOT FIRED** (margin 2,076 B) |
| **F4** | `dplc_peak_tiles` changes, moving the character VRAM window. | **NOT FIRED** (29 → 29) |
| **F5** | The 12-bit `tile_start` field (max 4095) is approached or overrun. | **NOT FIRED** (3,158 of 4,096 tiles used) |
| **F6** | The peak **slot** cost after the re-cut exceeds `DMA_IMPORTANT_SLOTS - DPLC_ENTRY_RESERVE` = 10. | **NOT FIRED** (exactly 10) |

**F1 is the one that matters**, and it is the one nobody had an instrument for.
Restated so it cannot be argued away:

> A frame's cost against the 12-slot Important queue is
> `entries + straddles`, **not** `entries`. Whether an entry straddles is a
> function of **where the art landed in ROM**. `dplc_peak_entries` — the comptime
> function every `ensure` in this tree uses — parses the blob and never learns
> the base address, so **it is structurally incapable of seeing F1.**

---

## 2. Making the claim precise enough to be false

"Appending art disturbs nothing else" is not falsifiable until "disturbs" is
pinned to this tree. Here it means, exactly:

**The ruled `targeted` change is:** append 112 tiles (+3,584 B) to
`art/optimized/characters/sonic.bin`, and rewrite the six frames that exceed 10
entries so each loads one contiguous run. That collapses 72 entry words to 10,
shrinking `games/sonic4/data/dplc/optimized/sonic.bin` by 124 B. Net **+3,460 B**.

All three of those numbers were **re-derived here from the shipped blobs** and
reproduce the card exactly (§4.1) — which is worth stating, since the card's
other numbers did not.

The change has **two** placement effects, and the second is the one the card
missed:

1. `Art_Sonic` **grows** by 3,584 B at its tail.
2. `DPLC_Sonic` **shrinks** by 124 B, and it sits *immediately before* `Art_Sonic`
   in the same section (`games/sonic4/data/collision/collision_data.emp:82-84`).
   So **`Art_Sonic`'s base address moves by −124 B** — and every DPLC entry's DMA
   source moves with it.

An append is therefore not a pure tail operation. It is a **base shift plus a tail
extension**, and F1 is sensitive to the base shift.

---

## 3. The instrument

`tools/dplc_straddle.py`. Gated in `build.sh` (post-sigil, beside `bganim_room`
and `sprite_tilt_gate` — it must read the listing *this* invocation emitted).
Unit tests: `tools/test_dplc_straddle.py` (17, run by build.sh's pytest lane).

**Everything is derived, nothing transcribed:**

- `TILE_SIZE`, `DMA_IMPORTANT_SLOTS`, `DPLC_ENTRY_RESERVE` — parsed from their
  defining `.emp` lines at run time.
- The ratchet the gate compares against is **read out of**
  `collision_data.emp`'s `ensure(dplc_peak_entries(_dplc_sonic) <= N)`, not
  written down.
- The `$20000` boundary is **derived from the split code**, not typed:
  `dma_queue.emp` does `lsr.l #1, d1` (source → words) then a 16-bit
  `sub.w d3,d0 / sub.w d1,d0 / blo .split`, so the borrow fires every
  `(1<<16) words = (1<<17) bytes`. `boundary_from_source()` re-reads those three
  instructions and **raises** if any stops matching, rather than keeping a stale
  constant.
- Art/DPLC lengths come from the files the `.emp` `embed()` lines name; base
  addresses from a fresh `s4.lst` / `s4.debug.lst`.
- The DPLC parser is written fresh from the format spec in `dplc.emp`'s header —
  deliberately *not* shared with `tools/dplc_layout.py`, so a bug in one cannot
  silently agree with the other.

**Loud on unmeasurable.** Every input it cannot establish raises `Unmeasurable`
and exits 2. Nothing renders "couldn't measure" as 0 or as green.

**Proven red.** `--selftest` drives the gate through three states: green at the
real placement; **red** at a failing art-base shift it *searches for at run time*
(so the proof stays valid as the art changes, and fails loud if no failing shift
exists rather than passing vacuously); and `Unmeasurable` on a broken derivation.
The build wiring was separately proven red by poisoning the gate's subject —
`DEBUG=1 ./build.sh` exited 1 naming the gate — then restored.

---

## 4. The measurements

Both canonical shapes, built fresh (`s4.bin` `bd721e32…`, `s4.debug.bin`
`f07cf7fd…`).

### 4.1 The re-cut reproduces

| | card | measured here |
|---|---|---|
| frames over the 10-entry wall | 6 | **6** — `$0E`, `$BE`, `$BF`, `$C1`, `$C4`, `$C8` |
| tiles appended | 112 | **112** (3,584 B) |
| entries collapsed | 72 → 10 | **72 → 10** |
| DPLC delta | −124 B | **−124 B** |
| net ROM | +3,460 B | **+3,460 B** |

### 4.2 F1 — the straddle set (the headline)

**Today, before any change, three DPLC entries already straddle** and cost a slot
their entry count does not show. Nothing in the tree had measured this:

| character | debug shape | release shape | that frame's cost |
|---|---|---|---|
| sonic | frame `$6C` | frame `$71` | 1 entry → **2 slots** |
| tails | frame `$A5` | frame `$AA` | 1 entry → **2 slots** |
| knuckles | frame `$8C` | frame `$90` | 4 entries → **5 slots** |

They are harmless *today* only because they land on light frames. That is luck,
not design — and it is exactly the property an append moves.

**After the targeted re-cut**, at both shapes:

```
peak ENTRIES 13 -> 10
peak SLOTS   13 -> 10        (the wall is 12 - 2 = 10)
straddling frames before: $6C      after: $6C
DISTURBED: 0 frames gained a straddle, 0 lost one
frames whose SLOT cost went UP: 0
```

**F1 does not fire.** Measured, not argued.

### 4.3 But the general claim is FALSE — and here is the margin

Holding the re-cut DPLC fixed and sweeping `Art_Sonic`'s base one byte at a time
across ±8 KB (16,385 shifts) and then ±64 KB (131,073 shifts):

| peak SLOTS | shifts | meaning |
|---|---|---|
| 10 | 16,230 of 16,385 (±8 KB) | fine |
| **11** | **155 of 16,385** | a straddle lands on a 10-entry frame and **eats one of the two reserve slots** |

Across the full ±64 KB window (131,073 shifts) **2,773 shifts fail**, in **43
disjoint bands**: min width **31 B**, median **31 B**, max **415 B**. 31 B is one
tile minus one byte — the natural width of a straddle window; the wide bands are
several such windows fused. The worst band reaches peak slots **17**.

So: *appending art* is **not** intrinsically safe. **This particular append is
safe because of where it lands**, and the distance to the nearest failure is:

```
art base may move EARLIER by  5,188 B   before peak SLOTS hits 11  (frame $90)
art base may move LATER  by 36,092 B    before peak SLOTS hits 11
```

**5,188 B is the real safety margin on F1** — not "nothing".

### 4.4 The two approved parcels interact, and nobody was checking

Block-stream dedup was ruled a **separate** win. It removes ~20,986 B from a run
that sits **upstream** of `Art_Sonic`, so it shifts this same base by **−20,986 B**
— four times the 5,188 B margin above, in the dangerous direction.

| configuration | art-base shift | peak SLOTS |
|---|---|---|
| re-cut alone | −124 | **10** |
| **dedup alone (today's DPLC)** | −20,986 | **13** — the overrun simply persists |
| dedup + re-cut | −21,110 | **10** |

Both land safe. But the combined safe band is
**[−29,796, −15,300]** of art-base shift, i.e. the dedup's saving must fall
between **15,300 B and 29,796 B** for the combination to hold. The quoted 20,986 B
sits inside it with **5,686 B of slack above and 8,810 B below**.

That is comfortable — but it is a **coupling between two parcels that were ruled
independent**, and the dedup's 20,986 B is another lane's figure the hub already
flagged for re-derivation. **Whichever of the two lands second must re-run
`tools/dplc_straddle.py --recut Art_Sonic` on the merged tree.** The gate in
`build.sh` now catches it either way.

### 4.5 F2 — nothing downstream moves

`Art_Sonic` is the **last packed blob in the ROM**. Sweeping all 944 label rows of
`s4.debug.lst`, the only ROM labels at or after it are:

```
072DA0  Art_Sonic
090000  Dac_Temp_Blip        <- org anchor, map.toml [[anchor]] at = 0x90000
098000  Dac_SharedBank_Start …
```

Everything between is the 21,920 B growth hole. The islands are **anchored, not
packed**, so growth cannot slide them. Tails' and Knuckles' art, all mappings, all
block blobs and the BG-anim section are **upstream** and do not move at all. The
only thing that moves is `Art_Sonic`'s own base, by the −124 B of §2.

### 4.6 F3 — ROM room, and a THIRD wrong number in the card

d-47 (both revisions) says the targeted option *"costs 3,460 bytes of ROM, with
about 20 KB of room to spare, so no other budget moves"* and *"fits today with
room to spare"*.

**That is the raw room, not the spendable room** — the same misreading the revised
card explicitly corrected for option B and then left standing for option A.
`tools/bganim_room.py`'s `rom_room()` returns anchor minus packed-data end;
`DATA_GROWTH_RESERVE` (16,384 B) is a **separate floor the placement rule
enforces** and is never inside that figure.

| shape | room today | spendable | after +3,460 B | margin over reserve |
|---|---|---|---|---|
| `s4.debug.lst` (**binding**) | 21,920 B | **5,536 B** | 18,460 B | **2,076 B** |
| `s4.lst` | 24,160 B | 7,776 B | 20,700 B | 4,316 B |

The fix **fits** — F3 does not fire, and the rule re-derives `dac_banks` to
`0x90000` in both shapes, so **no anchor moves**. But it consumes **62.5 % of all
remaining spendable data room**, leaving 2,076 B, not ~20 KB. The BG-animation
ceiling is untouched (26,698 B still available against a ruled 12,288 B).

### 4.7 F4 / F5 — VRAM window and the tile-index field

- `dplc_peak_tiles`: **29 → 29**. The re-cut copies the same tiles, so the
  character VRAM window does not move. F4 does not fire.
- Highest tile index referenced: **3,045 → 3,157**. The `tile_start` field is 12
  bits (`andi.l #$0FFF, d0`, `dplc.emp:166`), max 4,095. Art goes 3,046 → 3,158
  tiles, leaving **938 tiles (30,016 B)** of headroom. F5 does not fire.
- The appended region lands at `0x8A9E4..0x8B7E4`, **83,996 B short of the next
  `$20000` boundary**, so no appended entry can straddle until the art grows by
  ~84 KB.

---

## 5. Verdict

**The condition is discharged. The claim holds for the ruled change, and the
argument it replaces was too weak in three specific ways.**

1. **`targeted` disturbs nothing measurable.** Six falsifiers, both canonical
   shapes, zero fired. Peak slot cost 13 → 10, exactly the wall.
2. **The general claim is false.** 43 failing bands within ±64 KB. The safety
   margin here is 5,188 B of base movement, and it is *asymmetric* — it is much
   tighter in the direction the other approved parcel pushes.
3. **Three straddling entries already ship**, unmeasured until now, and the
   arithmetic every `ensure` in this tree performs is structurally blind to them.
4. **The card's "~20 KB to spare" is wrong** for the same reason its option-B
   number was. The real margin is 2,076 B.

**What changed so this cannot come back:** `dplc_straddle --gate` runs in
`build.sh` on both sonic4 shapes and fails the build if any frame's measured slot
cost exceeds the committed entry ratchet. That is the first check in this tree
that measures **slots** rather than **entries**.

---

## 6. What remains UNMEASURED, and why

Stated plainly rather than reasoned around.

1. **⚠ RUNTIME — the OTHER Important producer.** `DPLC_ENTRY_RESERVE = 2` exists
   for `PageIn_EnqueueLanding`, whose landings can *also* straddle. This
   measurement covers **DPLC** entries only. How many *page-in landings* straddle
   in a given frame is a property of the act's art pool at run time and cannot be
   settled statically. **The instrument that would close it:** the split counter
   already specified on the d-47 instrument half (`DMA_Split_Reject_Count` split
   out of `DMA_Overflow_Count`, plus `DMA_Peak_Important`, which is declared at
   `engine/ram.emp:580` and **written nowhere**), sampled over a real act run.
   **Tagged for foreground follow-up — no emulator was used in this parcel.**

   > **ADDENDUM 2026-09-03** (`parcel/dma-straddle-counter`): that instrument is now
   > **built** — both cells above plus `Dbg_DMA_Straddle_All` / `_Frame` / `_Peak`,
   > which count the per-frame straddle DEMAND the reserve has to absorb. **The
   > sampling is still owed**; it needs the emulator and no agent parcel can take it.
   > Arming recipe and the meaning of each reading: `docs/DEFERRED_WORK.md`, "DMA
   > SPLIT-REJECT NEEDS TWO FREE IMPORTANT SLOTS". This paragraph's claim that the
   > page-in half "cannot be settled statically" is unchanged and is exactly right.

2. **The re-cut is modelled, not executed.** This parcel moves **zero ROM bytes**
   (proven: `s4.bin` and `s4.debug.bin` are byte-identical with and without the
   gate wired in — `bd721e32…` / `f07cf7fd…` both ways). The post-re-cut numbers
   come from applying the documented re-cut to the real blobs in memory. A
   *different* re-cut — different tile ordering, or option B's full re-page —
   produces a different straddle set and **must be re-measured**, not inherited.
   `--recut` is in the tool for exactly that.

3. **Only the four `CharacterDef` DPLC tables are covered** (Sonic, Tails, Tails'
   appendage, Knuckles). The Deferrable producers (insta-shield, spindash dust)
   charge a different queue and were out of scope.

4. **The dedup's 20,986 B is another lane's figure.** §4.4 brackets the safe band
   around it rather than trusting it, but the band itself assumes that lane's
   parse of the block format is right.

---

## 7. Reproducing

```bash
export SIGIL_BUILD=…/sigil/target/release/sigil
export SIGIL_EMIT=…/sigil/target/release/emit_sound_blob
DEBUG=1 ./build.sh                      # the gate runs inside this

python3 tools/dplc_straddle.py --lst s4.debug.lst --recut Art_Sonic
python3 tools/dplc_straddle.py --lst s4.debug.lst --sweep Art_Sonic --range -8192:8192
python3 tools/dplc_straddle.py --lst s4.debug.lst --selftest    # the red-first proof
cd tools && python3 -m pytest test_dplc_straddle.py -q
```
