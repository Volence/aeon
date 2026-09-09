# Ledger Sift A — 2026-09-09

Verifies whether 15 `open` findings from `docs/lens-findings.jsonl` (latest line per id,
parsed from the 129-line/92-id ledger) still hold against master as checked out in this
worktree. Slice: `S0-2, A2-1, A2-2, A2-5, B1-4, B1-5, B2a-2, B2a-3, B2a-4, B2b-4, B2b-5,
C1a-1, C1a-2, C1b-2, C1b-3`.

All 15 latest rows were extracted from `docs/lens-findings.jsonl` by parsing every line and
keeping the last occurrence per id; none of the 15 ids repeat in the file (each occurs on
exactly one line: S0-2@2, A2-1@3, A2-2@4, A2-5@7, B1-4@13, B1-5@14, B2a-2@17, B2a-3@18,
B2a-4@19, B2b-4@23, B2b-5@24, C1a-1@26, C1a-2@27, C1b-2@29, C1b-3@30), so "latest" and
"only" coincide here.

---

## S0-2 (low) — a correction sits far below a wrong claim a reader lands on first, in `docs/DEFERRED_WORK.md`

**VERDICT: STILL-TRUE**

The row claims: at (then) line 11926, a section heads "NOTHING in them is fixed"; 137 lines
later a "fully worked" claim contradicts it, and the row itself flags that the seat's line
numbers had already drifted from content growth ("coordinate-rot").

Today (doc has grown to 31246 lines):
- `docs/DEFERRED_WORK.md:12005`: `**Landing them made them discoverable; NOTHING in them is fixed.**`
- `docs/DEFERRED_WORK.md:12142`: `**THE TOOLS PACKET IS NOW FULLY WORKED — D1 through D10 all closed 2026-08-18.**`

12142 − 12005 = **137 lines**, exactly the distance the row recorded at the sweep commit
(`9cfebb72`, where the same two strings sat at lines 11953 and 12090 — also 137 apart). The
absolute line numbers moved (doc growth); the defect — a reader hits the wrong blanket claim
first and the correction is 137 lines downstream — is unchanged.

No detail-correctness issue: the row's own text already flags the line-drift risk.

---

## A2-1 (medium) — `RunObjects`/`RunObjects_Frozen` document d7 as preserved but clobber it immediately

**VERDICT: STILL-TRUE**

`engine/objects/core.emp:476`: `// Object routines MUST preserve a0 and d7.` (a callee
contract for object routines, printed on the caller's own header) followed by
`engine/objects/core.emp:481`: `pub proc RunObjects () clobbers(d0-d7/a0-a6) {` — the
machine-checked clobber list explicitly includes `d7`. Body:
```
engine/objects/core.emp:486:        lea     Player_1, a0
engine/objects/core.emp:487:        move.w  #NUM_PLAYERS-1, d7
```
d7 is written a few instructions into the proc, before any object dispatch.

Same pattern in `RunObjects_Frozen`:
```
engine/objects/core.emp:650:// Clobbers: d0-d6, a0-a6
engine/objects/core.emp:652:pub proc RunObjects_Frozen () clobbers(d0-d7/a0-a6) {
engine/objects/core.emp:654:        lea     Player_1, a0
engine/objects/core.emp:655:        move.w  #NUM_PLAYERS-1, d7
```
The header prose ("Clobbers: d0-d6, a0-a6") omits d7 even though the compiler-checked
signature declares it and the body writes it right away — exactly "document a register as
preserved that they overwrite immediately." The `clobbers()` attribute itself is correct
(includes d7); the English "Clobbers:" line is what's wrong.

---

## A2-2 (low) — a cache routine's header omits a register its body uses as a live pointer

**VERDICT: STILL-TRUE**

`engine/level/tile_cache.emp:539`: `// Clobbers: d0-d3, d5, a0, a2-a3` (omits a4).
`engine/level/tile_cache.emp:545`: `pub proc TileCache_CopyBlockColumn (...) clobbers(d0-d3/d5/a0/a2-a4) preserves(a1) {`
— the real signature includes a4.
`engine/level/tile_cache.emp:576`: `movea.l a1, a4  // staged base -> a4 (collision copy source)`
— a4 is loaded and held live as a pointer for the rest of the routine (the collision-copy
source cursor), confirming it's a genuine live register the header should list.

`where.line=539` matches the ledger row exactly.

---

## A2-5 (low) — an init routine's one-line header is contradicted by its own body comment eight lines below

**VERDICT: STILL-TRUE**

`engine/level/bg_anim.emp:131-132`:
```
// BgAnim_Init — force a bank DMA on each band's first Update.
// In: none. Clobbers: d0
```
`engine/level/bg_anim.emp:134`: `pub proc BgAnim_Init () clobbers(d0/a0) {` — includes a0.
`engine/level/bg_anim.emp:142`: `// shape's clobber set carries a0 — both callers in this tree already declare` — the
body's own comment explicitly states the clobber set carries a0 "in BOTH shapes", directly
contradicting the one-line header's "Clobbers: d0".

`where.line=132` matches the header line exactly.

---

## B1-4 (low) — three explicit branch sizes in a VBlank routine have no argument, where the same file argues its others

**VERDICT: STILL-TRUE**

`Raster_VBlank` (`engine/effects/raster.emp:973-1107`) contains three explicit-sized
branches with no adjacent sizing rationale:
- `engine/effects/raster.emp:975`: `beq.s   .no_install` — no comment at all on that line.
- `engine/effects/raster.emp:1006`: `bne.s   .copy_program` — preceding comment
  (`// word 2 = first record's op_count`) explains the compare, not the sizing.
- `engine/effects/raster.emp:1051`: `beq.s   .done  // no program armed: one tst per frame`
  — a semantic label, not a sizing argument.

`CODING_CONVENTIONS.md:126` restricts explicit `.s`/`.w` to `@as_compat` ports and
self-modified/patched fields, neither of which is invoked anywhere in `raster.emp` (grepped
for `as_compat`/`self-modif`/`load-bearing`/`encoding width` — none found). By contrast, the
file's other sized branches sit inside dense, deliberate cycle-accounting paragraphs: e.g.
`engine/effects/raster.emp:1252` (`beq.s .op_cram`) sits under the "WHAT IT COSTS AND WHAT
IT BUYS" dispatch-cost paragraph (`:1220-1249`), and `:1594`/`:1605`/`:1626`
(`Raster_HInt`'s dense/ramp bodies) sit inside per-line cycle-budget prose that explicitly
reasons about taken/not-taken costs. The three VBlank ones do not have that company.

`where.line=975` matches exactly.

---

## B1-5 (medium) — the four-point hardware-multiply/divide argument is unmet at every hand-written site; the jump routine's pair meets none of the applicable three

**VERDICT: STILL-TRUE**

Full census (`grep` for `mulu.`/`muls.`/`divu.`/`divs.` outside `mul_const`/`mul_bounded`)
finds exactly **9 instruction sites**, matching "9 sites found by two independent
instruments":
- `engine/system/math.emp:117,124` (`GetArcTan`, `divu.w` x2)
- `engine/level/parallax.emp:1942` (`Parallax_Update`, `divs.w`)
- `engine/level/parallax.emp:2194` (`Parallax_Step4_Fill`, `divs.w`)
- `games/sonic4/player/player_ground.emp:853,856` (`Ground_Move_Cap`, `muls.w` x2)
- `games/sonic4/player/player_ground.emp:1041,1044` (`Player_Jump`, `muls.w` x2)
- `games/sonic4/player/player_glide.emp:226` (`Glide_Move`, `muls.w`)

For multiplies only 3 of the convention's 4 points apply (point 1, divisor-non-zero, is
divide-only per `CODING_CONVENTIONS.md:297`). **`Player_Jump` — "the jump routine" —**
(`games/sonic4/player/player_ground.emp:1041,1044`) has this and only this as its argument:
```
games/sonic4/player/player_ground.emp:1039-1040:
        // variable×variable product — one-shot event, classic Sonic_Jump
        // does exactly this
```
- Point 2 (overflow bound): not stated.
- Point 3 (alternative named and rejected): not stated (contrast with `Ground_Move_Cap`'s
  sibling comment at `player_ground.emp:850-852`, which explicitly says "no table/shift
  form exists").
- Point 4 (cost/frequency): stated only as "one-shot event" — and
  `CODING_CONVENTIONS.md:303` explicitly lists `"it's only called once"` under **"What does
  not count."** So Player_Jump's stated reason is precisely the one the convention's own
  disposal list rejects — meeting none of the three applicable points.

"Two are complete": `GetArcTan` (`engine/system/math.emp:80-95`) argues all three
applicable points explicitly (structural non-zero divisor, overflow bound via the
`cmp/bcc`-routed smaller-magnitude dividend, and an explicit table-lookup alternative
rejected on exactness). `Parallax_Step4_Fill` (`engine/level/parallax.emp:2180-2192`)
likewise states the structural divisor bound, the overflow bound, an explicit rejected
alternative ("Widening the dividend — the 8.8 step this design rejected"), and states
frequency at `engine/level/parallax.emp:2093` ("ONCE PER FRAME PER CURVE LAYER"). By
contrast `Parallax_Update`'s `divs.w` (`parallax.emp:1942`) states points 1 and 2
(`parallax.emp:1931-1936`) but **no alternative-rejection language appears anywhere near
it** (checked via `grep -n "alternative\|rejected\|costed"` across the whole file — the
only nearby hits at `:2192` belong to `Parallax_Step4_Fill`'s block, not this one) — so it
is not complete either, leaving exactly 2 of the 6 distinct argued sites (by proc) complete,
consistent with "Two are complete."

---

## B2a-2 (medium) — a parent-chain safety assert exists in two of the four chain-manipulating routines

**VERDICT: STILL-TRUE**

Four routines manipulate the sibling/parent chain in `engine/objects/children.emp`:
`CreateChild_Normal` (148), `CreateChild_Complex` (269), `CreateChild_FlipAware` (341),
`CreateChild_Linked` (446). The chain-contract assert appears only in two:
- `engine/objects/children.emp:151`: `assert.w d0, eq, #0  // chain contract: a parent may not itself...`
- `engine/objects/children.emp:449`: `assert.w d4, eq, #0  // chain contract: a parent may not itself be...`

`CreateChild_Complex` and `CreateChild_FlipAware` have none, and both carry:
```
engine/objects/children.emp:268 / :340:
@scaffolding("engine API awaiting its consumer — zero call sites today; kept deliberately. ...")
```
confirmed zero call sites via `grep -rn "CreateChild_Complex"` / `"CreateChild_FlipAware"`
across the tree (only self-references inside `children.emp`'s own comments and headers).
`where.line=269` matches `CreateChild_Complex`'s proc line exactly.

---

## B2a-3 (medium) — the "independent oracle" proof transcribes the packing it's supposed to check, for most fields

**VERDICT: STILL-TRUE**

`games/sonic4/test/scene_equiv_proof.emp:170`:
`pub comptime fn cfg_band(cell: int, fa: int, fb: int, dsa: int, dsb: int, phase: int = 0) -> band_entry {`
— exact `where.line` match.

Field-by-field comparison against `engine/level/scene_dsl.emp:3461-3516`'s `scene_band()`
(the lowering path this file claims to check independently), for all 9 `band_entry` fields:

| field | `cfg_band` (oracle) | `scene_band` (lowering) | identical? |
|---|---|---|---|
| `band_top_plane` | `cell * 8` | `scene_plane_line(s, wy)` | **no** — deliberately different (the file says so at `:161-169`) |
| `band_factor_a_s1` | `fa & 15` | `fa & 15` | **yes, character-identical** |
| `band_factor_a_s2` | `(fa >> 4) & 15` | `(fa >> 4) & 15` | **yes** |
| `band_factor_b_s1` | `fb & 15` | `fb & 15` | **yes** |
| `band_factor_b_s2` | `(fb >> 4) & 15` | `(fb >> 4) & 15` | **yes** |
| `band_factor_ops` | same 2-statement-if accumulator, same bit literals | same | **yes** |
| `band_deform_shift_a` | `dsa` (raw passthrough) | `l.ly_dsa` (raw passthrough) | trivial, no packing to compare |
| `band_deform_shift_b` | `dsb` | `l.ly_dsb` | trivial |
| `band_phase_offset` | `phase` | `l.ly_phase` | trivial |

Five fields with an actual bit-packing derivation (`a_s1`, `a_s2`, `b_s1`, `b_s2`,
`factor_ops`) are character-identical formulas on both sides, so a wrong packing rule for
any of them would make BOTH sides wrong the same way — the comparison structurally cannot
catch it. The file's own header (`:155-169`) explicitly acknowledges doing this
deliberately for the ops/factor fields ("an INDEPENDENT spelling of the packing — bits 0/1
written as literals here, not imported from parallax") while making the opposite,
independent choice for `band_top_plane` — the one field where it states and meets the
correct standard: "This oracle deliberately does NOT learn that mapping... does its own
trivial conversion, `cell * 8`." Matches "five of nine" and "meets it for one field"
exactly.

No detail is wrong; the row is precise.

---

## B2a-4 (low) — three comptime solvers duplicated across two modules with nothing keeping them in step

**VERDICT: STILL-TRUE, with a caveat on "verbatim"**

A tree-wide `comptime fn` name census finds exactly two literally duplicated names, both
shared by exactly `games/sonic4/objects/ring_sparkle.emp` and
`games/sonic4/player/player_instashield.emp`:
- `count_bad_nibbles` — `ring_sparkle.emp:91` vs `player_instashield.emp:334`
- `script_display_frames` — `ring_sparkle.emp:123` vs `player_instashield.emp:377`

A third solver of the same *shape* (flat-accumulator index-validity check) exists under
different names: `ring_index_ok` (`ring_sparkle.emp:81`) vs `insta_index_ok`
(`player_instashield.emp:325`) — same control-flow idiom, different literal palette
sets, called by each module's own `count_bad_nibbles`.

Caveat: the bodies are **not byte-identical**. `count_bad_nibbles` differs in signature
(`blob: [u8; 128]` fixed array vs `blob: Data, len: int`), loop bound (`0..128` vs `0..len`)
and callee name. `script_display_frames` differs further: `ring_sparkle.emp`'s version has
no "stop" flag (`if script[i] < AF_SET_FIELD { frames = frames + 1 }`), while
`player_instashield.emp`'s tracks a `stop` flag once a control byte is hit. So "verbatim"
overstates literal identity for 2 of the 3; what's genuinely duplicated is the algorithmic
shape/idiom and (for 2 of 3) the exact name, with no shared source and no cross-check
keeping them in step — which is the substance of the risk the row describes ("nothing
keeping them in step"), even if "verbatim" is a slight overstatement.

---

## B2b-4 (high) — the sound driver's timing floor is mirrored as a literal in two modules with no pin either side

**VERDICT: STILL-TRUE (detail's guard count is off by one)**

`engine/sound/sound_fm.emp:135`: `pub const YM_ADDR_TO_DATA_MIN_T = 8     // after an address-port write`
— exact `where.line` match. Comment at `:131-132` states: "z80_sound_driver.emp and
sound_sequencer.emp carry the same declaration with a pointer back here" — confirmed:
- `engine/sound/z80_sound_driver.emp:113`: `const YM_ADDR_TO_DATA_MIN_T = 8`
- `engine/sound/sound_sequencer.emp:82`: `const YM_ADDR_TO_DATA_MIN_T = 8`

Three independent literal `= 8` declarations, no `ensure()` anywhere ties them together
(searched `ensure(YM_ADDR_TO_DATA_MIN_T` — zero hits). A guard drifting LOW in any one file
would silently pass its own `ensure(cycles(...) >= YM_ADDR_TO_DATA_MIN_T, ...)` gates.

**Detail correction:** the row says "Twelve build-fatal cycle guards consume it." Counting
`ensure(cycles(...) >= YM_ADDR_TO_DATA_MIN_T` occurrences today: `sound_fm.emp` has 2
(`:204,206`), `z80_sound_driver.emp` has 8 (`:595,597,998,1153,1155,1387,1389,1391`),
`sound_sequencer.emp` has 3 (`:2075,2077,2079`) — **13 total, not 12**. Checked the count
was already 13 at the sweep commit (`9cfebb72`) too, so this isn't post-sweep drift — the
row's own count was off by one when written. The core finding (mirrored, unpinned literal)
is unaffected.

---

## B2b-5 (high) — the collected/killed bitmask width has no guard binding it to the entry count, unlike an identical twin

**VERDICT: STILL-TRUE**

`engine/system/constants.emp:1119`: `pub const KILLED_BITMASK_OFFSET   = 18     // object killed bitmask starts after ring bitmask`
— exact `where.line` match. `engine/system/constants.emp:1133`:
`pub const COLLECTED_MASK_BYTES    = KILLED_BITMASK_OFFSET - COLLECTED_BITMASK_OFFSET  // 16`
and `:1134`: `pub const MAX_LIST_ENTRIES        = 128`. No `ensure` anywhere binds
`COLLECTED_MASK_BYTES*8 == MAX_LIST_ENTRIES` (grepped for the pair together, empty).

The "identical twin one block away" is `ENTITY_LOADED_OBJ_OFFSET`
(`engine/system/constants.emp:1125`, same 32-byte-slot, 16B-rings+16B-objects geometry),
which **is** guarded: `engine/objects/entity_window.emp:95`:
`ensure(ENTITY_LOADED_OBJ_OFFSET*8 == MAX_LIST_ENTRIES, "Loaded-mask half-slot does not cover MAX_LIST_ENTRIES bits")`.

The debug asserts that DO exist on the collected/killed path
(`engine/objects/entity_window.emp:187,212,234,263,545,561,579`, all
`assert.w dN, lo, #MAX_LIST_ENTRIES`) bound the query index against the entry-count
constant `MAX_LIST_ENTRIES`, not against the derived byte width `COLLECTED_MASK_BYTES`, so
they cannot see a `KILLED_BITMASK_OFFSET`/`COLLECTED_BITMASK_OFFSET` edit that narrows the
mask below what `MAX_LIST_ENTRIES` bits need — confirming "the debug assert on the same
lines cannot see it because it bounds the index against the number that got out of step."
Because collected and killed masks sit adjacent in the same slot, a narrowed collected mask
would spill into the killed mask on write — "silently mark an object dead for the whole
act" is a direct, structurally-supported consequence.

---

## C1a-1 (medium) — sprite registration reloads a pointer it already holds and shifts one bit further than needed

**VERDICT: STILL-TRUE**

`engine/objects/sprites.emp:156`: `.band_has_room:` — exact `where.line` match, inside
`Draw_Sprite`. Trace of register `a1` on the path that reaches this label:
```
engine/objects/sprites.emp:139:        lea     Sprite_Band_Counts, a1   // (band-overflow check)
...                                    // fast path to .band_has_room with a1
                                        // still = Sprite_Band_Counts
engine/objects/sprites.emp:166:        lea     Sprite_Bands, a1          // clobbers it — needed for the store
engine/objects/sprites.emp:167:        move.w  a0, (a1,d2.w)
engine/objects/sprites.emp:170:        lea     Sprite_Band_Counts, a1    // reloads the SAME value a1 held at :139/:141
engine/objects/sprites.emp:171:        addq.b  #1, (a1,d0.w)
```
`a1` holds `Sprite_Band_Counts` on entry to `.band_has_room` (from line 139, unclobbered on
the fast `blo .band_has_room` path), gets overwritten to `Sprite_Bands` for the store, then
is reloaded back to `Sprite_Band_Counts` at line 170 — a value it already had two
instructions earlier. Reordering (increment the count first, while `a1` still holds
`Sprite_Band_Counts`, then load `Sprite_Bands` into a different/the same register for the
store) would drop the second `lea`.

Shift: `engine/objects/sprites.emp:160`: `lsl.w #6, d2  // d2 = band * 64 (SPRITES_PER_BAND=32, *2 bytes)`.
`SPRITES_PER_BAND` is still 32 (`engine/system/constants.emp:492`), so the *byte* offset
math is correct; the "one bit further than needed" is that the code shifts `d2` by 6 to get
`band*64` and separately doubles `d1` (`add.w d3,d3`) for `count*2`, then adds — an
equivalent computation could combine `band` and `count` into a single *entry* index first
(`lsl.w #5,d2` = `band*32`, `add.w d1,d2` = `+count`) and double the combined result **once**
(`add.w d2,d2`) for the byte offset, using a 5-bit shift on `d2` rather than 6. Same
instruction count, one bit less on the shift that's spelled out in the comment as the
per-band stride.

---

## C1a-2 (low) — a parallax loop's stated reason for not being optimised doesn't hold, but the loop never runs on shipped content

**VERDICT: STILL-TRUE**

Stated blocker: `engine/level/parallax.emp:3444-3445`:
```
// `.lp_both` above is deliberately NOT converted: two sampled channels need two walk
// pointers and there is no second free address register.
```
Refuted by the tree's own later correction, `docs/DEFERRED_WORK.md:12713-12715`:
```
The per-line forcer is 1792 B, not the spec's 896, and `.lp_both` has
**14 registers live, not "all 16"** (`a0` is spilled at proc entry and dormant), which is the
stated justification for the curve∧deform prohibition.
```
and the file's own banner at `engine/level/parallax.emp:3046`: `the design doc's claim that
"`.lp_both` uses all 16 registers" — false, it uses 14 — got there because a roster comment
in this file went stale and was read as a measurement.` `a0` being "spilled... and dormant"
directly contradicts "no second free address register" — `a0` is demonstrably usable as a
second walk pointer, exactly as it's used as the walk pointer in the adjacent single-channel
loops (`.band_fg_only`/`.lp_bg`, per the register note at `parallax.emp:3436-3439`).

Frequency: `docs/DEFERRED_WORK.md:5977-5978` records that when the single-channel loops were
converted, `.lp_both` was deliberately left alone "which also leaves the walker model's
`line_both` term as an unchanged control" — treated purely as a synthetic benchmark control,
not something exercised by the shipped, currently-playable content; every `line_both`
mention found (`docs/benchmarks/scanline-p2/WALKER-MODEL.md`,
`docs/benchmarks/streaming/CHOKE-DIAGNOSIS.md:1082`, etc.) is a coefficient-fitting/control
fixture, not a live-content measurement. `Scene_WindyHaze`
(`games/sonic4/data/effects/ojz_scenes.emp:939-957`) is the one shipped config whose bands
combine `dsa=3` (FG active) with `dsb` in `{0,1,2,3}` (BG also active) on the same band —
which WOULD trigger `.lp_both` — but nothing in the researched registry/section wiring shows
it bound to a currently-playable section today, consistent with "one section binding away"
from paying the cost.

---

## C1b-2 (low) — one of three sibling loops does its setup before the emptiness test rather than after

**VERDICT: UNDETERMINED**

The row carries no `detail` field to disambiguate which trio of loops is meant, and
`where.line=521` in `engine/objects/core.emp` has drifted: at the sweep commit (`9cfebb72`)
line 521 was `.always_next:` (inside the shared `.run_always` dispatch body used by the
Player/System/Effect call sites, none of which has a *runtime* emptiness test — their
counts, `NUM_PLAYERS-1`/`NUM_SYSTEM-1`/`NUM_EFFECTS-1`, are comptime-nonzero constants);
today the same line is just `}` (the closing brace of the `if DEBUG == 1` block around the
System-slot call), which isn't a loop at all.

I identified every loop in the file that *does* have a genuine runtime emptiness test
(`beq` on a live count before entering the body): `.run_culled`
(`engine/objects/core.emp:573-577`), `.frozen_dyn_loop`
(`engine/objects/core.emp:663-667`), `.dyn_zero_scan`
(`engine/objects/core.emp:307-311`), and `.dyn_pend_scan`
(`engine/objects/core.emp:325-329`, DeleteObject's live/pending list zeroing scans). All
four, not just one of three, place their setup (`lea`/`move.w Count,dN`) **before** the
`beq` emptiness test:
```
engine/objects/core.emp:573-577 (.run_culled):
        if DEBUG == 1 { st Dynamic_Live_Walking }
        lea     Dynamic_Live, a2
        move.w  Dynamic_Live_Count, d7
        beq     .culled_done
```
I could not find a candidate trio where exactly one loop's setup precedes its test while two
siblings' setups follow — which is what the row's title requires as a contrast. What would
settle this: the original sweep seat's full note (this row has no `detail`) naming the exact
three loops and which one is "the odd one out," or confirmation that the row's locus has
simply rotted past recoverability (in which case it should be retired as unverifiable rather
than carried forward as `open`).

---

## C1b-3 (low) — a collision lookup re-derives per query a value its producers write twice a frame

**VERDICT: STILL-TRUE**

`engine/level/collision_lookup.emp:54-55`:
```
        move.w  Cache_Origin_Row, d2
        lsr.w   #1, d2                        // origin even → exact collision origin
```
inside `Collision_GetType` — called once per sensor probe (multiple per player per frame,
per `games/sonic4/player/player_sensors.emp`'s callers), recomputing `Cache_Origin_Row >> 1`
on every single call.

`Cache_Origin_Row`'s only non-init writers are exactly two procs in
`engine/level/tile_cache.emp`, each capable of firing at most once per frame as the tile
cache scrolls:
- `engine/level/tile_cache.emp:2209`: `move.w  d0, Cache_Origin_Row` (`TileCache_VSlide`,
  forward slide)
- `engine/level/tile_cache.emp:2231`: `move.w  d1, Cache_Origin_Row` (the mirrored
  retreat function)

("twice a frame" = these two producer call sites, not two writes to the same site.)
Neither producer writes a precomputed halved/"collision origin" value alongside
`Cache_Origin_Row`; no such RAM cell exists (searched for a sibling `Cache_*Coll*Origin*`
constant/variable — none found). So every one of potentially many per-frame sensor queries
repeats a `lsr.w #1` that the two producers could instead do once, at write time.

---

## Summary

| id | severity | verdict |
|---|---|---|
| S0-2 | low | STILL-TRUE |
| A2-1 | medium | STILL-TRUE |
| A2-2 | low | STILL-TRUE |
| A2-5 | low | STILL-TRUE |
| B1-4 | low | STILL-TRUE |
| B1-5 | medium | STILL-TRUE |
| B2a-2 | medium | STILL-TRUE |
| B2a-3 | medium | STILL-TRUE |
| B2a-4 | low | STILL-TRUE (verbatim-ness caveated) |
| B2b-4 | high | STILL-TRUE (detail count off by one: 13 not 12) |
| B2b-5 | high | STILL-TRUE |
| C1a-1 | medium | STILL-TRUE |
| C1a-2 | low | STILL-TRUE |
| C1b-2 | low | UNDETERMINED |
| C1b-3 | low | STILL-TRUE |

Counted directly from the 15 sections above (not from memory): **STILL-TRUE = 14,
ALREADY-FIXED = 0, MOOT = 0, UNDETERMINED = 1.**

Two rows had a factually wrong `detail` even though the underlying finding survives:
**B2b-4** (says "Twelve" guards, actually 13, both today and at the sweep commit — not
post-sweep drift, the count was wrong when written) and **B2a-4** ("duplicated verbatim" —
2 of the 3 duplicated bodies differ in signature/loop-bound/stop-logic; only the naming and
algorithmic shape are truly shared).
