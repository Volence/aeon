# The reels' per-scene key shape — EFFECTS-W1 DoD item 10, authoring half, DEBUG TIER

*Status: **ANSWER ARTIFACT, documents only.** This parcel moves no ROM byte, changes no
`.emp` and no generator source, and runs no build. It exists so the hub can file a schema CR
and the aurora lane can build a panel against it without opening this repo.*

*Authored against `e2c66e6ff0bdc7740ef2b76e52da88edcc6ee9b5` (this worktree's HEAD, from
`git rev-parse HEAD` in the same pass that produced this text). Every `file:line` below was
opened in that tree here, and every one is anchored to a SYMBOL name so a later move
degrades the line number without invalidating the claim. Where a coordinate handed to this
lane turned out slightly wrong, §9 says so rather than repeating it.*

**Relationship to the existing item-10a artifact.**
`docs/superpowers/specs/2026-09-03-item10a-reels-key-shape.md` is the SURVEY: it establishes,
correctly and in detail, that no reels key exists and that `v_deform` is the wrong surface to
hang one on. It closes with five things "NOT ESTABLISHED", and the three load-bearing ones
are exactly what a CR cannot be written without: the JSON spelling, the source shape a key
lowers into, and whether the geometry may vary per scene. **This document decides those
three, at DEBUG tier.** It does not restate the survey; it re-derives only what it uses.

---

## The short version, before the evidence, because the first answer is the surprising one

1. **A DEBUG-tier key can AUTHOR the reels and can BIND them to a scene — both, today, with
   zero release bytes.** The binding does not need a descriptor field, a `Scene` struct
   change, a shape-divergent shipped record, or an engine hook. It needs one association
   table the generator already has both halves of. §4.
2. **The brief's premise that "there is no existing consumer a reels document key lowers
   into" is half wrong, and the half that is wrong is the half that makes this affordable.**
   `OJZ_Reels_Fill` already reads its rates from a ROM byte table through a generic walk. The
   consumer for the RATES exists. What does not exist is the **selection** — the table label
   is fixed at assembly time. §3.
3. **The geometry must be fixed, not authored, and the argument is not "it is hard" — it is
   that a per-scene band count is not expressible in the mechanism at all** without moving a
   hardcoded shift that an `ensure` names by file. §5. **Recommendation: v1 fixes the
   geometry at 5 x 4 and varies only the rates.**

The one thing a DEBUG-tier key does **not** buy: reels in the shipped ROM. That is a look
call, it is the owner's, it is priced in §8, and nothing in this note designs it.

---

## 1. The mechanism, re-derived

### 1.1 What it is

`OJZ_Reels_Fill` (`games/sonic4/data/effects/ojz_effects.emp:1793`, `pub proc
OJZ_Reels_Fill () clobbers(d0-d5/a0-a2)`) runs once per frame and does two things:

- **Advance** (`.advance`, `:1798`-`:1806`): walks `REEL_BAND_COUNT` byte accumulators in
  `OJZ_Reel_Phase` and adds each band's own signed constant from `OJZ_Reel_Speed`. `add.b`,
  so each phase wraps mod 256 — the header's own image is a slot-machine reel (`:1795`-`:1797`).
- **Fill** (`.col`, `:1809`-`:1825`): rebuilds all `VSCROLL_COL_PAIRS` entries of
  `Parallax_Vscroll_Column_Buf`. The **FG word is copied unchanged** from what
  `Parallax_Update` already wrote (`move.w d1, (a0)+`, `:1813`); the **BG word** becomes
  `Parallax_Current_Vscroll_BG + phase[column >> 2]` (`:1817`-`:1822`).

**No new VRAM, no new VSRAM write path, no new VDP register** — confirmed against the source
rather than taken from the brief: the proc writes only `Parallax_Vscroll_Column_Buf`
(`engine/ram.emp:400`, `[u8; 80]`), which `Vscroll_Write` already DMAs every frame. The
foreground is untouched by construction, not by convention.

### 1.2 Where the numbers live

| thing | symbol | site |
|---|---|---|
| the authored rates | `OJZ_REEL_SPEEDS: [i8; REEL_BAND_COUNT] = [3, -5, 2, -4, 6]` | `games/sonic4/data/effects/ojz_effects.emp:1756` |
| the emitted table | `OJZ_Reel_Speed` | `:1767`, length `REEL_SPEED_EMIT_LEN` (`:1766`) = `REEL_BAND_COUNT` in DEBUG, `0` otherwise |
| the runtime accumulators | `OJZ_Reel_Phase: [u8; REEL_BAND_COUNT]` | `games/sonic4/config/ram.emp:402` |
| the on/off flag | `OJZ_Reel_Active: u8` | `games/sonic4/config/ram.emp:401` |
| band count / band width | `REEL_BAND_COUNT = 5`, `REEL_COLS_PER_BAND = 4` | `games/sonic4/config/constants.emp:66-67` |

`REEL_BAND_COUNT` and `REEL_COLS_PER_BAND` live in the game's sole constants module rather
than beside the demo for a stated reason (`constants.emp:58-65`): `config/ram.emp` needs
`REEL_BAND_COUNT` for `OJZ_Reel_Phase`'s array length, and `ram.emp` cannot import the
effects module without a cycle. **The identity between them is therefore checked somewhere
else** — in `ojz_effects.emp`, "the one place all three names are already in scope"
(`ojz_effects.emp:1727`-`:1731`). This matters for the key: a schema arm that thinks it can
vary band count is asking to edit a constant three modules depend on, not a field.

### 1.3 The call site

`games/sonic4/test/ojz_scroll_test.emp:1368`-`:1373`, inside `GameState_OJZScroll_Update`:

```
        if DEBUG == 1 {
                tst.b   OJZ_Reel_Active         // (OJZ_Reel_Active).w
                beq     .skip_reels_fill
                jbsr    OJZ_Reels_Fill
        .skip_reels_fill:
        }
```

immediately after `jbsr Parallax_Update` (`:1357`) and before `jbsr BgAnim_Update` (`:1377`).

---

## 2. (a) Release-dormant BY CONSTRUCTION, gated in both directions — and exactly what a DEBUG-tier key commits to

Three independent gates, each verified:

1. **The data.** `OJZ_Reel_Speed`'s declared length is `REEL_SPEED_EMIT_LEN`, which is
   `if DEBUG == 1 { REEL_BAND_COUNT } else { 0 }` (`ojz_effects.emp:1766-1767`). Zero bytes
   in release.
2. **The code.** `OJZ_Reels_Fill`'s entire body, `rts` included, sits inside `if DEBUG == 1 {}`
   (`:1794`, closed `:1826`). Zero bytes in release.
3. **The switch.** `OJZ_Reel_Active` is inside `config/ram.emp`'s `if DEBUG == 1
   @shape_divergent {}` RAM-tail group (opened `:187`), and its **only writer in the tree is
   `tools/reels_witness.py`** — re-derived by grepping every `.emp`, `.py` and `.asm` outside
   `docs/`: the eight hits in `reels_witness.py` (the write is `:98`), two in `reels_gate.py`
   prose, and the rest are comments. **Nothing in the release shape can set it.** So even if
   1 and 2 were removed, the mechanism could not run.

`tools/reels_gate.py` asserts 1 and 2 from the built listing, in both directions
(`--shape release`: both symbols occupy zero bytes, `:254`-`:269`; `--shape debug`: the table
gap equals `band_count + (band_count % 2)` and the proc gap is positive, `:272`-`:293`).

**What a DEBUG-tier key therefore commits anyone to, stated precisely:**

- It commits the **schema** to a name and a payload shape. That is a real, permanent
  commitment: once `reels` is in the writer schema, retracting it breaks round-tripping.
- It commits **DEBUG-shape ROM bytes** — one 5-byte table per authoring scene, plus a small
  association table (§4). At three editor scenes today that is under 40 bytes, all of it
  behind `if DEBUG == 1`.
- It commits **nothing about the release ROM.** `reels_gate.py --shape release` stays green
  by the same construction it is green by now, and stays green *because the generated
  content is inside the same gate*, not because anyone remembered to check.
- It commits **nothing about how the effect looks.** Nobody has to like reels for this key to
  be correct; a DEBUG-tier key is a lab instrument.

**The prohibition that follows, and the CR must carry it as a prohibition rather than a
caveat:** *the generated reels content MUST be emitted inside `if DEBUG == 1`, and the
association table MUST NOT become a field of `Scene`, `parallax_config`, or `Sec`.* Any of
those three puts reels bytes in the release ROM, turns a DEBUG demo into shipped surface
area, and converts an owner-free parcel into a look call. The failure is silent at authoring
time and shows up as a `reels_gate.py --shape release` FAIL much later.

---

## 3. (b) A per-band rate is REAL CODE — where the analogy to `drift` and `bob` holds, and where it breaks

The header of `OJZ_Reels_Fill` says this by name (`ojz_effects.emp:1696`-`:1698`): the source
"is real code by construction (a per-band rate cannot be a spatial table sample, the family
the DSL already speaks)". Worked out against the two near neighbours.

### 3.1 How `drift` binds — the closest neighbour, four hops

| hop | what | site |
|---|---|---|
| 1 | document key `layer.drift = {"rate": N}` | `LAYER_KEYS`, `tools/effects_gen.py:120` |
| 2 | generator renders `SceneDrift.Rate(N)`, **no unit conversion** | `render_drift`, `tools/effects_gen.py:1848`-`:1882` |
| 3 | `layer(drift: ...)` stores it in `ly_drift` | `engine/level/scene_dsl.emp:819`, `:859` |
| 4 | lowers to a 16.16 long in the `band_drift` tail of `band_record` | `engine/level/parallax.emp:342` (`struct band_drift (size: 4)`), `:464` (`br_drift`) |
| 5 | a shipped loop consumes it, gated by `CAP_BAND_DRIFT`, accumulating into `Parallax_Drift_Acc` | `engine/level/parallax.emp:643` (`band_drift_rate`), `engine/ram.emp:431` |

That is the pattern the brief describes: **an authored value becomes a packed field in a
per-band record that a loop already walks.** `bob_shift`/`bob_period` is the same shape one
level up — two scene scalars (`SCENE_KEYS`, `tools/effects_gen.py:87`) packed by
`scene_bob_packed()` into a `pcfg` byte that `Parallax_Step5_Vscroll` unpacks
(`engine/level/scene_dsl.emp:63`-`:67` pin the ladders).

### 3.2 Where the analogy breaks — and it is not where the survey doc put it

**Break 1 — there is no per-band record for reels to occupy, and the word "band" is a false
friend.** `band_record`/`band_drift` partition the screen into up to `MAX_PARALLAX_BANDS`
(16) horizontal **row** bands, one per scene layer. A reel band is one of 5 vertical
**column** strips. These are unrelated partitions of the screen that share a noun. There is
no field to add, because there is no record whose cardinality is 5-columns-wide. (The
generator's own `render_drift` docstring makes the same warning in the other direction:
"`BAND_KEYS` in this file is the RASTER preset's scanline region, an unrelated use of the
word", `tools/effects_gen.py:1871`-`:1873`. That is now the third meaning of "band" on this
seam and the CR should not add a fourth.)

**Break 2 — the consumer is not shipped.** `drift`'s consumer runs in the release ROM of any
game declaring `CAP_BAND_DRIFT`. `OJZ_Reels_Fill` emits zero bytes in release (§2) and is
called from exactly one game state, inside `if DEBUG == 1`. A reels key therefore cannot
follow `drift`'s "author a value, a shipped loop picks it up" story, and must not be
described to aurora as though it could.

**Break 3 — there is no capability bit.** `drift` has `CAP_BAND_DRIFT`
(`engine/level/parallax.emp:72`, `:279`, `:364`); item 6's dense tier has `CAP_DENSE_TIER`.
Grepping the whole reels block (`ojz_effects.emp:1674`-`:1826`) for `CAP_` returns nothing.
Reels are gated by build shape and a RAM flag, not by a declared game capability. **A schema
`reels` key must therefore NOT be described as capability-gated**, and a generator arm must
not emit a capability check that does not exist.

### 3.3 Where it does NOT break — the finding that makes this affordable

`OJZ_Reels_Fill`'s advance loop is:

```
        lea     OJZ_Reel_Phase, a1              // (OJZ_Reel_Phase).w — REEL_BAND_COUNT bytes
        lea     OJZ_Reel_Speed(pc), a2          // ROM: REEL_BAND_COUNT signed byte speeds
        moveq   #REEL_BAND_COUNT-1, d5
    .advance:
        move.b  (a1), d0
        add.b   (a2)+, d0
        move.b  d0, (a1)+
        dbf     d5, .advance
```
(`ojz_effects.emp:1798`-`:1806`)

Everything after the two `lea`s is **already** a generic "read `REEL_BAND_COUNT` signed bytes
from ROM and accumulate" walk. It does not know or care which table it is reading. **The
consumer for the rates exists and is one register away from being parameterizable.** The
missing half is not a loop, not a record, not a decoder — it is that `a2` is loaded from a
fixed label instead of from a value that can vary per scene.

That is the whole delta, and it is why the source shape below is small.

### 3.4 THE SOURCE SHAPE — what the generator emits, what the engine reads

Three pieces. Two are generated; one is a two-line change to hand-authored DEBUG code.

**(i) One rate table per authoring scene — generated, DEBUG-gated.**

```
// in the generated module, inside `if DEBUG == 1 { ... }`
pub data EditorReels_OJZ_Act1_ojz_sec0_reels: [i8; REEL_BAND_COUNT] = [3, -5, 2, -4, 6]
```

Name derived exactly as `EditorCycle_*` / `EditorVariant_*` / `EditorRaster_*` already are
(`games/sonic4/data/generated/ojz/act1/effects_scenes.emp:224`, `:228`), so the naming rule
needs no invention.

**(ii) An association table keyed by the LOWERED CONFIG LABEL — generated, DEBUG-gated.**

The key insight for binding. `Parallax_Current_Config: u32` (`engine/ram.emp:390`, "ptr to
active parallax_config") holds, every frame, a pointer to the config the active scene lowered
to. The generator **already emits that exact label**: `pub data
EditorSceneBinding_OJZ_Act1_Sec0: SceneCfg5 = lower5(EditorScenes_OJZ_Act1[2])`
(`effects_scenes.emp:144`), and it is what reaches `Sec.sec_parallax_config`
(`engine/structs.emp:137`), which `engine/effects/preset.emp:229`-`:231` resolves and installs.

So the association is a flat list of (config label, rates label) longs:

```
pub data OJZ_Reel_Bindings: ... = [
    EditorSceneBinding_OJZ_Act1_Sec0, EditorReels_OJZ_Act1_ojz_sec0_reels,
    ...
    0, 0,                                    // terminator
]
```

**(iii) The consumer change — two lines in `OJZ_Reels_Fill`.** Before the advance loop, walk
`OJZ_Reel_Bindings` comparing each first long against `Parallax_Current_Config`; on a hit,
`movea.l` the second into `a2` instead of `lea OJZ_Reel_Speed(pc), a2`; on a miss, fall back
to `OJZ_Reel_Speed` (so the built-in demo and `tools/reels_witness.py` keep working
unchanged). Cost: a linear scan of N longs, N = 3 today, entirely inside `if DEBUG == 1`.

**Why this shape and not the alternatives:**

- **Not a `Scene`/`scene()` argument.** `Scene` lowers into `parallax_config` records that
  ship in the release ROM. A `reels:` argument there is release bytes — §2's prohibition.
- **Not a `Sec` descriptor field.** `sec_parallax_config` is a shipped field of a shipped
  struct (`engine/structs.emp:137`); a sibling `sec_reel_rates` widens every section record in
  every act in the release ROM to carry a DEBUG-only pointer. Same prohibition.
- **Not indexed by section number.** That would need a live "active section index" cell.
  **NOT FOUND**: grepping `engine/ram.emp` and the game RAM for `Current_Section` /
  `Section_Index` / `Active_Section` returns nothing, and the shipped resolve works off a
  `Sec` record pointer rather than an index (`preset.emp:229`). Keying on
  `Parallax_Current_Config` sidesteps the question entirely rather than inventing a cell.
- **Not `OJZ_Reel_Active` widened into a selector** (0 = off, N = the Nth authored set). This
  was considered and rejected: it needs no new tables at all, but it is not *binding* — the
  scene document would author numbers that a human then selects by poking a different number,
  which is a lab knob wearing an authoring key's name. It is worth naming in the CR only as
  the fallback if (ii) is judged too much for a first slice.

**The generated chooser is NOT part of this.** The `pub comptime fn ojz_act1_sec_reels(sec,
hand)` shape — a fourth always-emitted chooser next to `ojz_act1_sec_scene` /
`ojz_act1_sec_raster` (`effects_scenes.emp:271`, `:295`) — is the natural fourth member of
that family and emits zero bytes either way. It is the right shape **if and when** reels bind
per SECTION. At DEBUG tier, binding per CONFIG (ii) is strictly smaller and needs no
descriptor edit, so the chooser is not proposed here. Named so the CR does not think it was
overlooked.

---

## 4. THE KEY SHAPE — the verbatim block

Scene-level, sibling to `v_deform`. Not a layer key, not a preset key: §3.2 break 1 rules out
the layer level (a reel band is not a layer), and reels touch no `EffectsPreset` field at all.

```json
"reels": { "rates": [3, -5, 2, -4, 6] }
```

| property | rule |
|---|---|
| **spelling** | `reels`, lowercase, plural. A scene-level key in `SCENE_KEYS` (`tools/effects_gen.py:70`-`:90`). |
| **payload** | an object with exactly one member, `rates`. Closed (`unevaluatedProperties: false`). |
| **`rates` type** | array of integers |
| **`rates` length** | **exactly 5** (`minItems: 5, maxItems: 5`) — see §5 |
| **element range** | `-128 .. 127` |
| **element uniqueness** | `uniqueItems: true` |
| **zero** | **ALLOWED**, and deliberately unlike `drift.rate`'s `"not": {"const": 0}` — see below |
| **order** | left-to-right screen position. Index *i* owns column-pairs 4*i*..4*i*+3, i.e. screen X 64*i*..64*i*+63. |
| **absence** | no reels for this scene. Matches `v_deform`'s absent-key precedent exactly (`scene()`'s `v_deform: SceneVDeform = SceneVDeform.None`, `engine/level/scene_dsl.emp:1665`). |

### 4.1 Units — and the one conversion that must NOT happen

**`rates[i]` is SIGNED WHOLE PIXELS PER FRAME.** A rate of 3 moves that strip's background 3
pixels per frame. There is no fixed point anywhere on this path: `add.b (a2)+, d0` adds the
authored byte straight into the phase, and `ext.w d3` / `add.w Parallax_Current_Vscroll_BG, d3`
(`ojz_effects.emp:1819`-`:1821`) put the phase into the VSRAM word as whole pixels.

**PROHIBITION, not a caveat.** `drift.rate` is 1/256 px per frame, and Aurora multiplies by
256 **in the UI on export** (`tools/effects_gen.py:1856`-`:1860`). *That conversion must not
be applied to `reels.rates`.* A `reels` panel built by copying the drift panel's export path
would emit 768 for an intended 3. Do not assume the `i8` catches it: whether sigil refuses an
out-of-range literal in a `[i8; N]` initializer is **NOT ESTABLISHED** (the item-10a survey
left it open and this pass did not build anything to settle it), and the engine has no
magnitude `ensure` today (§6). **The `-128..127` schema bound is the only reliable place this
mistake is caught, which is why it is a schema bound and not just prose.**

### 4.2 The ladder — what the numbers mean visually

A strip's phase wraps every `256 / |rate|` frames. At 60 Hz:

| rate | cycle | reads as |
|---|---|---|
| 1 | 256 frames, 4.3 s | a slow crawl |
| 3 | 85 frames, 1.4 s | the shipped demo's slowest band |
| 6 | 43 frames, 0.7 s | the shipped demo's fastest band |
| 16 | 16 frames, 0.27 s | fast, still legible |
| 64+ | under 4 frames | a strobe, not a reel |

**The useful authoring range is roughly ±16**, and that is UI guidance for the panel's slider
default range — **not a refusal.** The schema bound stays the full `i8`, because the
mechanism genuinely works at any of these values and the engine refuses none of them; a
narrower schema bound would be the generator inventing a rule the engine does not have, which
is the exact posture `tools/effects_gen.py:30`-`:36` forbids.

**Zero is allowed, and the asymmetry with `drift` is deliberate.** `drift.rate: 0` is
meaningless — it spells "no drift", which absence already spells, so the schema excludes it.
`rates[i] = 0` is a *stationary strip among moving ones*, which is a real authored choice and
visually the most reel-like thing in the vocabulary. `uniqueItems` already caps it at one.

---

## 5. (c) The geometry is pinned — **RECOMMENDATION: fix it, vary only the rates**

### 5.1 What a per-scene band count would actually move

Two `ensure`s, both ungated (they run in every shape, every build — the `UNGATED` note at
`ojz_effects.emp:1741`-`:1744` states this as the intent):

- `ensure(REEL_BAND_COUNT * REEL_COLS_PER_BAND == VSCROLL_COL_PAIRS, ...)`
  (`ojz_effects.emp:1732`). The message names the failure: bands that do not cover every
  column-pair leave some columns holding whatever `Parallax_Update` last wrote.
- `ensure(REEL_COLS_PER_BAND == 4, ...)` (`ojz_effects.emp:1738`). The message names the
  file that must change with it: *"OJZ_Reels_Fill's column->band map is a hardcoded `lsr.b #2`
  (divide by 4) ... so the shift amount in games/sonic4/data/effects/ojz_effects.emp must move
  with it."*

`VSCROLL_COL_PAIRS` is itself pinned to H40 (`engine/level/parallax.emp:860`, `SCREEN_WIDTH / 16`,
with its own H40 `ensure` at `:862`), so `REEL_BAND_COUNT * REEL_COLS_PER_BAND == 20` is the whole
solution space: {1x20, 2x10, 4x5, 5x4, 10x2, 20x1}. Of those, **only the ones whose
`REEL_COLS_PER_BAND` is a power of two are expressible at all**, because the column→band map
is a shift.

### 5.2 The recommendation, and the argument

**Fix the geometry. `rates` is length 5, and band count is not an authored key.** Three
reasons, in decreasing order of force:

1. **It is not a value, it is a code shape.** `REEL_COLS_PER_BAND` is not read at runtime by
   anything — it is *compiled into* `lsr.b #2`. A per-scene band count is therefore a per-scene
   instruction, which means either self-modifying code, a `lsr.b d2` variable shift (a real
   change to a per-column inner loop), or one proc per geometry. None of those is "add a
   field".
2. **The array length would stop meaning anything.** `[i8; REEL_BAND_COUNT]` is a length
   contract that sigil now enforces at the signature since 2026-09-02 (`docs/EMP_PITFALLS.md`
   §13). A variable-length `rates` array gives that up and moves the length check into the
   generator, which is where §6 shows it does the least good.
3. **`REEL_BAND_COUNT` is not private to the effect.** It sizes `OJZ_Reel_Phase`
   (`config/ram.emp:402`), which is why it lives in `config/constants.emp` and not beside the
   demo (`constants.emp:58`-`:65`). Per-scene band counts mean per-scene RAM sizing, or a RAM
   array sized to the maximum and partly unused — a RAM cost paid in the DEBUG shape for an
   authoring convenience.

**What is given up, honestly:** 64-pixel strips only. An author who wants three wide reels or
ten narrow ones cannot have them. That is a real expressive loss and the CR should say so
rather than presenting 5 as natural. **It is also recoverable later without a schema break**:
adding an optional `"cols_per_band"` member to the `reels` object is additive, and a future
engine that carries a variable shift can accept it. Fixing the geometry in v1 costs a future
option nothing; *starting* with a variable geometry costs an inner loop now.

**BLOCKED-adjacent note, recorded rather than papered over:** I could not construct an
argument that a fixed geometry is *worse* on any axis except expressiveness, so this
recommendation is not a reluctant compromise. If the hub has a scene in hand that needs a
different strip width, that is new information and the recommendation should be revisited on
it — the shift-versus-field analysis above is the thing to re-derive, not the conclusion.

---

## 6. Refusals, and where each is enforced

The house rule this table obeys: **the generator validates SHAPE, sigil validates VALUE, and
neither duplicates the other** (`tools/effects_gen.py:30`-`:36`; a TYPE is shape, a RANGE is
value, `:37`-`:45`).

| # | refuses | enforced at | exists today? |
|---|---|---|---|
| 1 | unknown scene key (e.g. `reel`, `reels_rates`) | `_check_keys` against `SCENE_KEYS`, `tools/effects_gen.py:70`-`:90` | **yes**, once `reels` is added to the set |
| 2 | `rates` not an array / elements not integers | generator, `_render_int`'s type arm (`tools/effects_gen.py:1575`+) | **yes**, pattern exists |
| 3 | `rates.length != 5` | schema `minItems`/`maxItems`, **and** the `[i8; REEL_BAND_COUNT]` length contract at the generated `pub data` | partly — the `.emp` half is `EMP_PITFALLS` §13 behaviour |
| 4 | an element outside `-128..127` | **SCHEMA ONLY.** The engine has no magnitude `ensure` — see below | **NO** |
| 5 | two bands sharing a rate | `ensure(distinct5(...) == 1, ...)`, `ojz_effects.emp:1759`-`:1760` — but see the travel note | **yes, for the hand table only** |
| 6 | band geometry not covering the buffer | `ensure(REEL_BAND_COUNT * REEL_COLS_PER_BAND == VSCROLL_COL_PAIRS, ...)`, `ojz_effects.emp:1732` | **yes** |
| 7 | `REEL_COLS_PER_BAND != 4` while the shift says 4 | `ensure(REEL_COLS_PER_BAND == 4, ...)`, `ojz_effects.emp:1738` | **yes** |
| 8 | reels bytes present in the release shape | `tools/reels_gate.py --shape release`, `:254`-`:269` | **yes** |

### 6.1 Row 4 is a gap the CR must close, not a bound to restate

**There is no `ensure` anywhere that bounds a single rate's magnitude.** The only per-array
checks are length (`:1757`) and pairwise distinctness (`:1759`). This is the one place the
usual advice — "put the bound in the engine, cite it from the schema" — cannot be followed,
because there is nothing to cite. The CR must either (a) accept the schema as sole
enforcement and say so in the schema's own `description`, or (b) ask for a new
`ensure(-128 <= r && r <= 127)` beside the generated table as part of the implementing
parcel. **(b) is preferable** and costs one line, because §4.1's ×256 mistake is otherwise
caught by exactly one artifact in the whole chain.

### 6.2 Row 5 does not travel, and this is the important one

`distinct5` is **literally five-ary** (`comptime fn distinct5(a, b, c, d, e)`,
`ojz_effects.emp:1753`-`:1755`) and its single call is hand-written beside the hand-written
array (`:1759`). **A generated rate table would inherit neither the length `ensure` nor the
distinctness `ensure` unless the generator emits them beside every table it writes.** Nothing
in the tree forces that.

The CR's implementing parcel must therefore emit, per generated table, both guards — or
better, route every generated table through **one new `comptime fn` that carries them**, so
the check lives with the mechanism instead of beside each copy. That function does not exist
today; naming it is the difference between a key that is checked and a key that is checked
once, in the one place nobody generates.

### 6.3 A refusal the CR will not expect: `reels_gate.py` is adjacency-coupled

`tools/reels_gate.py` measures both spans by the **gap between adjacent symbols**:
`OJZ_Reel_Speed` → `OJZ_Reels_Fill` is "the table" (`:249`-`:250`), and `OJZ_Reels_Fill` →
`ObjDef_Static` (`NEXT_SYM`, `:102`) is "the proc" (`:251`-`:252`).

**Any new byte-emitting symbol landing between those pairs makes the gate raise
`Unmeasurable`** — not FAIL, `Unmeasurable`, with a message that explicitly warns "do NOT
read this as a byte mismatch" (`:280`-`:287`). Since the natural place to put generated reel
tables is the same module, right next to the hand table, **the implementing parcel will trip
this on its first build unless the generated content is emitted into the generated module
(`games/<game>/data/generated/.../effects_scenes.emp`) rather than into `ojz_effects.emp`.**
That is another independent reason for the source shape in §3.4, and it is worth a sentence
in the CR so an implementer does not spend an hour on a gate that is telling the truth.

---

## 7. What the schema CANNOT express — so the generator must

Five things. Each is a real obligation on the implementing parcel, not a disclaimer.

1. **That index order is screen order.** JSON arrays are ordered, so the schema can require
   five elements, but nothing in the schema says index 2 is the middle 64 pixels. The mapping
   lives in a shift (`lsr.b #2, d2`, `ojz_effects.emp:1817`). An editor that sorts, reverses,
   or round-trips `rates` through a dict keyed by band name silently relocates every strip.
   **The generator must emit in document order, verbatim, and the schema `description` must
   state the mapping.**
2. **That `REEL_BAND_COUNT` is 5.** The schema's `minItems: 5` is a hardcoded copy of an
   `.emp` constant in another repo. If `REEL_BAND_COUNT` ever moves, the schema is silently
   wrong in the permissive direction for a build that will then fail confusingly. **The
   generator must re-derive `REEL_BAND_COUNT` from `games/sonic4/config/constants.emp` and
   refuse a `rates` array whose length disagrees** — this is a SHAPE check (a length), so it
   is on the right side of the shape/value line, and `reels_gate.py:122` (`emp_const`) already
   has the parser for it.
3. **That the effect is DEBUG-only.** No JSON keyword expresses "this authored content
   reaches only one build shape". An author will save a scene with `reels` and see nothing in
   a release build. **The schema `description` must say it and the panel must show it**, or
   this becomes a support question.
4. **That the FG is untouched.** `reels` moves the background of a strip and nothing else
   (`move.w d1, (a0)+`, FG preserved, `ojz_effects.emp:1813`). An author expecting a whole
   vertical slice of the screen to move will not get it.
5. **That the excursion is 0..255 px below the camera's BG base, always positive.** The phase
   is an unsigned byte added to `Parallax_Current_Vscroll_BG` (`:1818`-`:1821`), so a negative
   *rate* means the strip travels the other way, not that it sits above the base. Nothing in
   the payload hints at this.

---

## 8. Open questions for the owner, priced

**Q1 — Promote reels into the release ROM? (THE look call. Not designed here, per scope.)**
Everything in §2 is deliberate: three gates, one of which is a witness tool that cannot exist
in a shipped ROM. Promotion means a real on-switch (a scene field or capability bit), release
emission for the table and the proc, and inverting `reels_gate.py`'s release arm — which
currently *asserts the absence*, so the gate is not adjusted but rewritten. **Price: M,** and
the majority of it is not code. It is the taste question of whether independently scrolling
64-pixel background strips belong in a Sonic zone at all, which nobody in this lane can
answer. **Recommendation: leave DEBUG-only until an actual scene wants it**, and note that
nothing in this key shape makes promotion harder later.

**Q2 — Does the hub want the association table (§3.4 ii) or the selector fallback (§3.4's
rejected alternative)?** The association table is real per-scene binding and costs one
generated table plus ~20 instructions in a DEBUG-only proc. The selector costs nothing new at
all but is not binding. **Price: S either way.** This lane recommends the association table;
the selector is named so a smaller first slice is available if the CR wants one.

**Q3 — Emit the range `ensure` (§6.1) in the same parcel, or book it separately?** One line.
**Price: XS.** Recommend same parcel; it is the only thing standing between a ×256 export bug
and a wrong-looking ROM.

**Q4 — Should the distinctness guard become a shared `comptime fn` (§6.2)?** Today's
`distinct5` is five-ary and hand-called. Generalizing it to a `comptime for` all-pairs check
that every generated and hand table routes through is the difference between a guard that
travels and a guard that was copied once. **Price: S.** No existing all-pairs idiom was found
in this tree to imitate, so this is new code rather than a pattern lift.

**Q5 — Does a second act's editor content need a second association table, or one global
one?** Not investigated; the generated module is per-act
(`games/sonic4/data/generated/ojz/act1/`) and only ojz/act1 has editor content today.
**Price: unknown, flagged rather than guessed.**

---

## 9. Corrections, and what this pass could not verify

**Corrections to coordinates this lane was handed** (each was given as "where to look", and
each was re-derived; these are the ones that came back different):

- The call site is at `ojz_scroll_test.emp:1369` for the `tst.b` and `:1371` for the `jbsr`,
  which matches. The `jbsr Parallax_Update` it follows is at `:1357`, not adjacent.
- **`reels_gate.py --shape debug` does not assert the table is "exactly `REEL_BAND_COUNT`
  bytes".** It asserts the *gap* to the next symbol equals `band_count + (band_count % 2)` —
  6, not 5 — because an `align 2` sits between the odd-length table and the proc
  (`ojz_effects.emp:1768`-`:1774`, `reels_gate.py:272`-`:287`). And a mismatch there is
  `Unmeasurable`, not FAIL. The distinction matters because §6.3's adjacency coupling is
  invisible if you believe the gate measures a declared length.
- `OJZ_Reel_Active` is at `config/ram.emp:401` and `OJZ_Reel_Phase` at `:402` — both as given.
  `REEL_BAND_COUNT`/`REEL_COLS_PER_BAND` at `constants.emp:66`-`:67` — as given.
- The "only writer is `tools/reels_witness.py`" claim: **re-derived and confirmed** by
  grepping every `.emp`/`.py`/`.asm` outside `docs/`. The write is `reels_witness.py:98`.

**Not verified in this pass, and marked rather than assumed:**

- **No build was run** (docs-only parcel, per the brief). Every byte-level claim about the
  release shape is read from source gates and their stated assertions, not from a listing.
- **No emulator, at all.** Nothing here claims reels have been seen on screen. The item-10a
  record's runtime pass is cited by the existing survey doc, not re-run here. **TAGGED for
  the controller's foreground pass** if runtime confirmation of §3.4's association walk is
  ever wanted — but note there is nothing to run yet, since this parcel implements nothing.
- **Whether sigil refuses an out-of-`i8` literal** in a `[i8; N]` initializer. Still open
  (the survey doc left it open too). §4.1's prohibition is written to be correct either way.
- **Whether a second act would need a second table (Q5).** Not traced.
- **The `Parallax_Current_Config` claim is structural, not measured.** `engine/ram.emp:390`
  declares it as "ptr to active parallax_config" and `engine/effects/preset.emp:229`-`:231`
  resolves `Sec.sec_parallax_config` into the install path; I did not trace the store into
  that cell instruction by instruction. If the CR's implementing parcel finds that
  `Parallax_Current_Config` holds something other than the label the generator emitted, §3.4
  (ii)'s key changes and the fallback is the per-section chooser named at the end of §3.4.
  **This is the single claim in this note most worth checking first.**

---

## 10. Booking

Appended at the end of `docs/DEFERRED_WORK.md` (tail, to keep a concurrent lane's conflict
trivial). Nothing else in that file was touched.
