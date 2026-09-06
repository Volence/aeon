# EFFECTS-W1 — the missing authoring keys, named

**The task was to name, for each authoring key the W1 tail still needs, its type, range,
default and the engine field it lands in, so the hub could draft the schema CRs.
THE MEASURED ANSWER IS THAT THERE ARE NONE.** All three keys the closing inventory books as
missing — item 4's two and item 9c's one — **exist at contract tip today**, and all three
readers land in this tree. The count in the inventory was 3; the corrected count is **0**.

The keys are named below anyway, in full, because a booking that says "missing" and a schema
that says "present" cannot be told apart from either side alone, and the next person to read
`2026-09-06-effects-w1-closing-inventory.md` will inherit the same 3. The tables are the
receipt: each row carries the engine field, the derivation of its range, and the revision the
schema half was read at.

**What IS genuinely wrong is one rung count and two sentences**, and they are in §4 and §5.
The one worth a CR is §4: `rowRemap.height_shift` is a **five-value schema window over a
one-value buildable window**, and the four values that pass the schema and fail the build are
refused only by a `_refuse` in `tools/effects_gen.py`.

---

## §0 — How the authority was read, and one path correction

Contract read at **empyrean `origin/main` = `b6913fae756ccf79736945a9f409d3d801c15521`**, after
`git -C ../empyrean fetch -q origin`, via `git -C ../empyrean show "<rev>:<path>"` — never
through the sibling working tree, which is a peer's live checkout.

**PATH CORRECTION, because the dispatch and at least one doc carry the wrong one.** The
schemas are at `contract/schema/…`, not `contract/…`:

| what | path at empyrean tip |
|---|---|
| preset schema | `contract/schema/aurora-effects-preset.schema.json` |
| scene schema | `contract/schema/aurora-effects-scene.schema.json` |

`git show origin/main:contract/aurora-effects-preset.schema.json` fails with "does not exist",
which reads as *the key is not there* to anyone who does not check the directory listing. It
is there.

Aeon side measured at `HEAD = c4c5c3d8`; `git rev-list --count HEAD..master` = 1 and
`git diff master..HEAD` over `tools/effects_gen.py`, `engine/level/scene_dsl.emp`,
`engine/effects/raster_dsl.emp`, `engine/effects/preset.emp` is **empty**, so every derivation
below holds at `master` (`3d414618`) unchanged.

---

## §1 — Item 4, the anchor mover: BOTH KEYS PRESENT, END TO END

**Schema half landed empyrean `d36d704` (2026-09-03). Reader half landed aeon. A document
authoring both keys SHIPS in this tree today.**

Positive-control measurement, `grep -c` over `tools/effects_gen.py` at `c4c5c3d8`:

| token | count now | count at `e190297c` (the booking's own measurement) |
|---|---|---|
| `patch_world_ys` | **29** | 0 |
| `patch_motion` | **35** | 0 |
| `anchor_sweep` | **10** | 0 |

The shipped document is `games/sonic4/data/editor/effects/presets/ojz_sec5_showcase.json`:

```json
"patch_motion":    [ { "sweep": { "amp_shift": 4, "period_shift": 1 } }, null, null, null ],
"patch_world_ys":  [ 2272, null, null, null ]
```

### 1.1 `patch_world_ys` — the anchor SEED, positionally per patch channel

| | |
|---|---|
| **engine field** | `EffectsPreset.ep_patch_world_ys[RASTER_MAX_PATCH]` at `+$1C` (`engine/effects/preset.emp:66`), copied verbatim into `Effects_World_Y[]` by `Effects_InstallPreset` on **every** install |
| **type** | `u16`, **whole pixels, absolute act/level space**. There is no `* 256` on this path and there must never be one — the runtime's screen line is `anchor - Camera_Y` (`engine/effects/raster_dsl.emp:2095-2103`) |
| **range** | `0 .. 65535`, **excluding `32767`** |
| **default** | `PATCH_ANCHOR_NONE` = `$7FFF` (`engine/effects/raster_dsl.emp:2145`), which is `preset()`'s own default array (`preset.emp:141-144`) — i.e. *channel unused* |
| **array length** | exactly `RASTER_MAX_PATCH` = 4 |

**Where the range is derived, not chosen.** The upper bound is the field's own width — it is a
`u16` and the install copies words. The excluded value is the sentinel: `$7FFF` = 32767 means
*unused*, so authoring 32767 as a world Y silently disables the channel. `0` is **not** the
"off" spelling — it is a real world Y above the screen top, and the most invasive state a
channel can have; `null` is the off spelling.

**The length guard is the interesting one and it is an `ensure`, not prose.**
`preset.emp:161` refuses a length other than 4 *as an equality*, because
`Effects_InstallPreset` seeds exactly 4 words: a short array makes the install read the bytes
that follow in ROM **as anchors**, and a long one silently drops the tail. Both directions are
wrong and only one of them would ever look like an error.

### 1.2 `patch_motion[i].sweep` — the packed motion word

| | |
|---|---|
| **engine field** | `EffectsPreset.ep_patch_motion[RASTER_MAX_PATCH]` at `+$26` (`preset.emp:86`); read by the `CAP_ANCHOR_MOTION`-gated latch loop in `Effects_LatchWorldLines` (`engine/effects/raster.emp:2205-2284`) |
| **type** | one packed `u16` per channel: `amp_shift` bits 15..12, `period_shift` bits 11..8, `phase` bits 7..0, built by `anchor_sweep()` (`raster_dsl.emp:2273`) |
| **default** | `ANCHOR_MOTION_NONE` = `0` (`raster_dsl.emp:2250`) — the whole word, not a byte |

Sub-field ranges, **re-derived here from the engine's own comptime functions rather than
copied from the schema**, so the two are an agreement and not a transcription:

| field | derivation | value |
|---|---|---|
| `amp_shift` min | `anchor_shift_min(ANCHOR_SINE_AMP=256, ANCHOR_SCREEN_LINES=224)`: smallest `s` with `(256>>s)*2 <= 224`. `s=1` gives 256 > 224; `s=2` gives 128 ≤ 224 | **2** |
| `amp_shift` max | `anchor_shift_max(256)`: largest `s` with `256>>s >= 1` | **8** |
| `period_shift` max | `anchor_period_shift_max(ANCHOR_SINE_ENTRIES=256, ANCHOR_TICK_BITS=16)`: largest `p` with `256<<p <= 65536` | **8** |
| `phase` max | `ANCHOR_SINE_ENTRIES - 1` | **255** |

Constants at `engine/effects/raster_dsl.emp:2173-2179`. **The schema at tip encodes exactly
`2..8` / `0..8` / `0..255`. It matches, independently derived.**

`phase` is the only optional sub-field, because it is the only one `anchor_sweep()` defaults
(to 0). `amp_shift` 0 is structurally illegal and the reason is the sentinel, not taste:
`anchor_sweep(0, 0, 0)` packs to `0`, which **is** `ANCHOR_MOTION_NONE`, so a legal shift-0
sweep would read as *no motion* silently. `raster_dsl.emp:2280` refuses the collision
explicitly even though the derived min of 2 already makes it unreachable — two facts that
could drift apart, guarded separately.

### 1.3 What a writer must guarantee that the consumer CANNOT check

Two obligations, in the `default_off`/`axis` shape of `tools/EFFECTS_CONSUMER_CONTRACT.md`
§1.2, both already in the schema's prose at tip and restated here because this is the aeon
half:

**(a) A sweep must fit its channel's `patchable(lo, hi)` band, and NO comptime scope can
check it.** `lo`/`hi` live in the raster program's `patchable(...)` call; the amplitude lives
in the preset; the two meet only through a runtime pointer. `raster_dsl.emp:2190-2195` states
this in the file that would otherwise be the natural place for the `ensure`. The consequence
is **asymmetric** and an author told "it vanishes" would be warned wrong at one edge: past
`hi` the record is **DROPPED** and the band is absent for that frame; below `lo` it is
**CLAMPED UP** and still emitted. `tools/test_anchor_sweep_band.py` is the only scope that can
see both numbers, and `games/sonic4/data/generated/effects_channel_bands.json` is the sidecar
that publishes `ch -> {lo, hi}` to the writer.

**(b) A motion is READ only in a game whose `SCANLINE_CAPS` raise `CAP_ANCHOR_MOTION`
(`$0100`; sonic4 yes, demo no).** The **seed** is installed unconditionally; the latch loop
that consumes the motion is gated. So in an ungated game an authored sweep is a **silent
no-op, not a refusal** — nothing anywhere says the sweep did not happen.

### 1.4 Verdict on item 4

**Zero keys absent.** The inventory's "needs two keys and a schema CR" was true when written
into the item-4 merge message (`094496ca`, 2026-09-03 02:51) and false by the end of that day.
It has been carried forward through the closing inventory unchecked.

---

## §2 — Item 9c, the row remap: THE SCENE KEY IS PRESENT

**Schema half landed empyrean `3992d16`, 2026-09-04 00:24:54 -0400. Reader half landed aeon
`d593070a`, 2026-09-04 00:34:52 -0400 — TEN MINUTES LATER.** `grep -c rowRemap
tools/effects_gen.py` = **6**; `render_row_remap` is `tools/effects_gen.py:2673` and
`render_layer` calls it at `:2762`.

### 2.1 `layer[].rowRemap` — `"none"` | `{plane_y, height_shift}`

| | |
|---|---|
| **engine field** | `SceneLayer.ly_remap: SceneRemap` (`engine/level/scene_dsl.emp:852`), lowering into `struct band_remap (size: 8)` (`engine/level/parallax.emp:418-423`): `brm_ladder: *u8`, `brm_plane_y: u16`, `brm_hshift: u8`, `brm_anchor_ch: u8` |
| **constructor** | `SceneRemap.Ladder(<ladder Label>, plane_y, height_shift)`; the ladder is **derived from `height_shift`**, never named by the author (one number, one source) |
| **default** | `SceneRemap.None` (`scene_dsl.emp:887`) → `brm_ladder = NULL`, which is the per-band gate at `parallax.emp:419`. **Absent and `"none"` lower to the same eight bytes** — the distinction is authoring, not ROM |

`plane_y`:

| | |
|---|---|
| **type** | `u16`, a **Plane-B line** — not a world Y, not a screen line. The runtime computes the background's image of the surface as `plane_y - Vscroll_BG` |
| **range** | `0 .. 511`, **derived from `PLANE_B_SPAN`** — the plane is 512 lines tall in this engine's 64×64 configuration |
| **enforced** | `scene_dsl.emp:1035` (`>= 0`) **and `scene_dsl.emp:1044` (`< 512`)**, plus the schema's `minimum/maximum` |

`height_shift`:

| | |
|---|---|
| **type** | a **SHIFT**, `H = 1 << height_shift`. The ladder is `(H+1)` rows of `H` bytes — **quadratic in H** |
| **range, as `layer()` accepts it** | `3 .. 7` (`scene_dsl.emp:1033`). Below 3 the remapped run is under 8 lines and nothing is visible; above 7 the table (16,512 B at H=128) is larger than the act's whole parallax data |
| **range, as anything can actually BUILD it** | **`{4}` and nothing else.** See §4 |
| **default** | none — required whenever `rowRemap` is an object |

**The unit hazard is the sharpest thing on this key** and it is a *silent* one: an editor that
displays "band height = 16 lines" and exports `16` asks for `H = 65536`. `scene_dsl.emp:1033`
catches 16 because it is outside 3..7 — **but every value 3..7 is legal**, so a conversion bug
*inside that window* lands as a band four times too tall rather than as a refusal. The editor
may DISPLAY `1 << height_shift`; it must EXPORT the shift.

### 2.2 What a writer must guarantee that the consumer CANNOT check

Four preconditions, all real `ensure`s for hand-authored scenes, none of them encodable in
JSON Schema (they are cross-key and cross-file):

1. **The scene must declare `anchor:`.** `scene_dsl.emp:1991`. The remap's perspective quantity
   is the separation between the background's image of the surface and the foreground's truth
   about it, and the foreground half is `Effects_Screen_L[ch]`.
2. **The remapped layer must have SOMETHING TO VARY, or the remap is the IDENTITY and the
   effect is ABSENT — not subtle, absent.** `scene_dsl.emp:1985`. One of: its own live `dsb`
   with a `deform_bg` table; the scene anchor's live `dsb` with a `deform_bg` table; or a
   `curve:` on that layer. **A live shift with NO table is flat-pathed at runtime and does not
   count.**
3. **At most ONE layer per scene may carry `rowRemap`.** `scene_dsl.emp:1998`. The engine keeps
   one per-frame mark and last-mark-wins is deliberate (it is how an anchored split of one
   remapped layer picks the half below the surface) — which makes it exactly the wrong answer
   for two authored layers, silently.
4. **The game must raise `CAP_ROW_REMAP`.**

### 2.3 Verdict on item 9c

**Zero keys absent, and 9c is not a contract item at all any more.** The 9c block in
`DEFERRED_WORK` written 2026-09-05 says *"what is left of 9c is the scene key itself + the hub
schema CR"* — both had landed the day before. What is actually left is in that same block, one
paragraph up, in the right words: the route was **proved end to end** with a probe and
**deliberately reverted** because `plane_y` had no visual basis. The remaining sentence is
**"Ask aurora to author"** — a content ask, not a schema one.

---

## §3 — The corrected count, and why the bookings drifted

| booking | says | measured |
|---|---|---|
| closing inventory, item 4 | "authoring half needs **two keys** and a schema CR" | both keys at empyrean tip since `d36d704` (2026-09-03); a document authoring them ships |
| closing inventory, item 9c | "9c needs a **scene key** + schema CR" | key at empyrean tip since `3992d16` (2026-09-04) |
| `DEFERRED_WORK:19212` (2026-09-05) | "the scene key + the hub schema CR remain" | landed the previous day |
| **total** | **3 keys** | **0** |

Both drifted the same way and it is the direction this tree has now named several times: a
booking is a pointer to where to look, never a statement of what is true. Neither of these
could be contradicted by anything local — a green build says nothing about a schema in another
repo, and the schema said nothing about the booking. **The only instrument that separates
"absent" from "present" here is `git -C ../empyrean show <rev>:<path>`, and it costs one
command.**

The item-4 booking has a second, sharper property worth keeping: **it was written by the party
that later closed it**, inside the merge message of the engine half, in the present tense
("AUTHORING HALF STILL BLOCKED, verified on origin/master rather than inherited"). It was
verified, it was true, and it aged out within hours. Verification does not make a status claim
durable; only the timestamp beside it tells a later reader how far to trust it.

---

## §4 — THE GAP THAT IS REAL: `height_shift` is a five-rung schema over a one-rung engine

**This is the entry the hub should turn into a CR.**

`contract/schema/aurora-effects-scene.schema.json` at tip encodes
`height_shift: {minimum: 3, maximum: 7}` — five legal values. **Four of them fail the build.**

```python
# tools/effects_gen.py:148-152
# THE ONLY LADDER THAT EXISTS, keyed by the shift it is the ladder for. The other four legal
# shifts (3, 5, 6, 7) are refused BY NAME below until EFFECTS-W1 item 9b's generator lands:
# `layer()` accepts them (scene_dsl.emp:1006 bounds 3..7), so without this the emission would
# fail on an undefined Label and name a missing symbol instead of the authoring mistake.
ROW_REMAP_LADDERS = {4: "RowRemapLadder_Waterline16"}
```

`engine/level/parallax_dsl.emp` carries exactly one ladder, `row_remap_ladder16()` at line
**396**, and its H is the module const `ROW_REMAP_H16 = 16` rather than a parameter — an `.emp`
`comptime fn` must return a concrete array type, so it **cannot** take H as an argument.

**The authority for "only 4 builds" lives in `tools/effects_gen.py` and nowhere a consumer can
execute.** This is the same class as `default_off` (`EFFECTS_CONSUMER_CONTRACT.md` §1.2): a
constraint that is real, enforced as a refusal, and living where no consumer can read it. The
schema does carry it **in prose** — the `height_shift` description says "TODAY ONLY 4 BUILDS"
— which is better than the `default_off` case was, but prose in a `description` is not what a
validator enforces, and the validator is what an editor's UI will be built against. **A slider
offering 3..7 is a correct reading of the schema's shape and a wrong reading of reality.**

**And the escape hatch the refusal names is stale.** Its message says *"The generated ladder
for the other shifts is EFFECTS-W1 item 9b."* **9b landed 2026-09-04** and delivered
`tools/row_remap_ladder_gen.py` — the model with H as an argument — plus its gate. That tool's
own docstring says **"WHAT THIS DOES NOT DO. It does not write into the tree."** `--emit emp`
prints `.emp` source to stdout; nothing regenerates `parallax_dsl.emp` from it, deliberately.
So the other four shifts are a **paste-in away, not automatic**, and the sentence pointing an
author at 9b now points at something that has already happened without changing the answer.

**Three ways to close it, all of them somebody else's call, with the consequence of each:**

| option | shape | consequence |
|---|---|---|
| (a) narrow the schema | `height_shift: {const: 4}` (or `enum: [4]`) | The writer-side refusal moves to where the writer meets it. Costs a second CR when a ladder is added. Truthful today. |
| (b) leave the window, add the ladders | paste `row_remap_ladder_gen.py --height N --emit emp` output for 3/5/6/7 into `parallax_dsl.emp`, extend `ROW_REMAP_LADDERS` | Schema becomes true without a CR. **Prices in ROM:** the ladder is `(H+1)×H` bytes — 272 B at H=16, but **4,160 B at H=64 and 16,512 B at H=128**. Four ladders nobody has authored against is data with no consumer. |
| (c) leave both, fix the message | narrow nothing; correct `effects_gen.py`'s refusal to say "paste an emitted ladder from `row_remap_ladder_gen.py`", not "wait for 9b" | Zero bytes, zero CR. Does not stop a UI built from the schema's numbers. |

**Recommendation, stated as a recommendation and not a ruling:** (a) plus (c). (b) spends ROM
on ladders for heights no authored scene has asked for, and the H the shipped waterline uses is
16 for a measured reason (`9d`: at H=16 the derived art need is 8 tiles; H=64 needs 32, and the
`bg_region` reserve after 9d is 80, not the 128 a stale figure still quotes).

**Whatever is chosen, `tools/effects_gen.py:2716`'s citation of `parallax_dsl.emp:220` is
wrong** — `row_remap_ladder16()` is at line **396** — and the empyrean schema's `height_shift`
description carries the same `parallax_dsl.emp:220`. One wrong line number, two repos, because
the second copied the first.

---

## §5 — Two sentences in the contract that are no longer true

Reported as **statements about a peer's tree, read at a revision** (`b6913fae`), not as
findings in it — the fix is empyrean's to make, and the mechanism half of each is verified
firsthand *here*.

**(1) `rowRemap.plane_y`'s description says "THIS SCHEMA IS THE ONLY ENFORCEMENT OF THE 511
CEILING: aeon's ensure at scene_dsl.emp:1008 tests >= 0 only". IT WAS TRUE FOR TEN MINUTES.**
Verified in this tree: `engine/level/scene_dsl.emp:1044` is
`ensure(remap_none == 1 || scene_remap_plane_y(rowRemap) < 512, …)`, with 512 inlined per the
file's pin block (`PLANE_B_SPAN`) exactly as the sibling `vsplit` guard spells it. It landed in
`d593070a` at 2026-09-04 00:34:52 -0400; the schema sentence was committed in `3992d16` at
2026-09-04 00:24:54 -0400. **Ten minutes.** The schema is now the *second* enforcement, which
is the desirable state — the sentence just over-claims its own load-bearing role, and a future
reader trimming the "redundant" aeon ensure on its authority would remove the only one that
fires at build time for a hand-authored scene.

**Aeon-side consequence, and it is ours to land: `DEFERRED_WORK`'s row
`ROWREMAP-PLANEY-CEILING` ("has no upper guard anywhere in the tree", booked 2026-09-04) is
CLOSED by `d593070a`, the same day, and has read open for two days.** Struck in this parcel.

**(2) The `parallax_dsl.emp:220` citation**, §4 above. `row_remap_ladder16()` is at 396.

---

## §6 — What is actually left on the W1 tail, in the right category

| item | inventory's category | measured category |
|---|---|---|
| 4 | contract (two keys + CR) | **nothing** — shipped end to end |
| 9c | contract (one key + CR) | **content** — an authored scene with a `plane_y` that has a visual basis. "Ask aurora to author." |
| — | not tracked | **contract** — `height_shift`'s rung count (§4), which nobody booked because it is not a missing key, it is a present key admitting values that cannot build |

**So the tail's remaining contract work is not the three keys anybody booked; it is one bound
on a key that already exists.** That inversion is the finding.

---

## §7 — Left open, named

- **Which of §4's three options to take** is a hub/owner call, not this lane's. Nothing here is
  blocked on it: `height_shift: 4` builds today.
- **The empyrean-side corrections in §5 are cross-repo claims.** They are stated with the
  revision read and the aeon-side mechanism verified firsthand; the schema edits belong to
  empyrean and this note does not make them.
- **`patch_world_ys`' `u16` upper bound and its refusal of 32767 are enforced NOWHERE in this
  tree** — the schema's closed writer-side check is the only refusal an author meets. That is
  the schema departing from its shape-only posture deliberately, recorded at tip, and it is
  correct; noted so the asymmetry with `plane_y` (now double-enforced) is not read as an
  oversight.
- **No ROM bytes.** This parcel is documentation only; nothing under `engine/` or `games/` is
  touched, so the four-shape crc evidence is not applicable and was not manufactured.
