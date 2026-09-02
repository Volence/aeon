# EFFECTS-W1 item 5 — the engine-side key shapes for `variants` / `cycles` (DEMAND ARTIFACT)

*Status: **DEMAND ARTIFACT, documents only**, 2026-08-30. Nothing here is implemented; the
parcel that produced it moved no ROM byte and ran no build. This is the source the hub asked
for ("the hub cannot transcribe a source that does not exist"): a transcription of the ENGINE
fields an authored preset document would have to carry so that empyrean can draft the
`aurora-effects-preset` contract change and aurora can author against it.*

*Every claim is transcribed from source in this tree at aeon `82fb65a8` (the worktree base
for this parcel) with `file:line`. Cross-repo reads are at empyrean `origin/main` =
`5a894756`, read-only via `git show`. Where a comment in the tree disagrees with the code it
sits beside, the code is transcribed and the disagreement is named. Anything not found is
marked **NOT FOUND** rather than guessed. Byte images below are DERIVED from the struct
layouts, not read out of a listing — no build was run in this parcel.*

*Scope of this document, stated beside the claims: it describes what the engine CAN bind
today and what a document would have to say to bind it. It does not decide the JSON
spelling (that is the hub's contract change) and it does not decide which section gets
what (that is content). Section 4 lists what it deliberately leaves to the owner or hub.*

---

## 0. Where item 5 sits, and why the keys are still refused

- DoD row: `docs/DEFERRED_WORK.md:16195` — *"5 | `variants` / `cycles` lowering | M | yes,
  paired | Needs the item-13 contract CR before aurora can author against it."*
- The item-1 contract change deliberately did **not** carry these keys. Option C ("grow
  the preset document to total") was refused at empyrean `da91abce` because *"it makes
  item 1 depend on item 5 and inverts the ratified DoD order"* — `docs/DEFERRED_WORK.md:
  16635-16637`, and again at `tools/effects_gen.py:1108-1112`. The same refusal is carried
  by the hub at `AURORA_EFFECTS_SCHEMA.md` §3.1 (empyrean `5a894756`, lines 333-337) and
  §7 (lines 660-667): *"a preset document cannot express a total binding until `variants`,
  `cycles` and a palette reference exist"*.
- Today the generator refuses both keys **by name**, not as unknown keys:
  `tools/effects_gen.py:275-286` (`PRESET_REFUSED_KEYS`), asserted by
  `tools/test_effects_gen.py:1406-1416`
  (`test_the_reserved_wave2_keys_are_refused_BY_NAME_not_as_unknown`). The consumer
  contract row is `tools/EFFECTS_CONSUMER_CONTRACT.md:411`.
- The hub's schema has `bands` only: `contract/schema/aurora-effects-preset.schema.json`
  at empyrean `5a894756` — top-level `properties` are exactly `schema`, `id`, `name`,
  `bands`; `required` is `["schema","id","bands"]`; `unevaluatedProperties: false` closes
  the key set; its own `description` says *"Reserved and refused by name (still wave-2
  open): fires, variants, cycles."* **So the proposal in §2 is an ADDITION of two optional
  top-level keys to a closed object, and nothing in the existing four keys changes.**

---

## 1. What the engine can do TODAY at runtime

### 1.1 The preset record — two variant slots and one cycle script per preset

`engine/effects/preset.emp:56-67`, `struct EffectsPreset (size: 38)`:

| offset | field | type | meaning (transcribed) |
|---|---|---|---|
| `$10` | `ep_cycle` | `*u8` | `// 0 illegal, use Pal_Cycle_None` (`:63`) |
| `$14` | `ep_variants` | `[*u8; 2]` | `// PAL_MAX_VARIANTS; unused slots 0 = clear` (`:64`) |

- **Exactly two variant slots.** `PAL_MAX_VARIANTS = 2` at `engine/effects/palette.emp:76`
  (*"raise only on measured evidence"*). It is LOCKED at 2 by three things: the
  power-of-two mask `andi.w #(PAL_MAX_VARIANTS - 1), d0` in `Palette_SetVariant`
  (`palette.emp:304`, *"3 would silently fold slot 2 onto slot 0"* per `preset.emp:112-115`),
  the module ensure at `preset.emp:116-117`, and the twin ensure at
  `palette_dsl.emp:130-131`. The raster side pins the same bound independently:
  `raster.emp:156` (`pal_stage_off`) and `raster_dsl.emp:270` (`stream_pal_region`).
- **Exactly one cycle script per preset**, with up to `PAL_CYCLE_MAX_CHANNELS = 4`
  channels (`palette.emp:77`; the per-channel timer array is `Pal_Cycle_Timers: [u8; 4]`,
  `engine/ram.emp:548`).
- The constructor: `preset(pal: Label, parallax: Label = 0, raster: Label = 0, patched:
  Label = 0, cycle: Label = 0, variants: [Label; 2] = [0, 0], patch_world_ys: array = ...,
  transition: int = 0)` at `preset.emp:121-126`. `cycle:` is a single Label; `variants:` is
  a two-element array of Labels; both default to 0.
- **A source disagreement, recorded:** `preset.emp:63` says `ep_cycle` 0 is *"illegal"*,
  while `preset.emp:238-240` says `Palette_LoadCycle`'s *"own a0=0 path already turns
  cycling off cleanly, so no redirect is needed there"*, and the code at
  `Effects_InstallPreset` (`preset.emp:314-316`) passes the field straight through with no
  0-check. `Palette_LoadCycle` (`palette.emp:324-342`) does handle a0 = 0 (`:327-328`).
  So at runtime 0 is *handled*, and the total-binding sentinel `Pal_Cycle_None`
  (`palette.emp:815-834`, a non-NULL script with ZERO channels) exists for the
  *"NULL means keep"* reason the comment at `:817-821` gives. **The generator should emit
  `Pal_Cycle_None`, never 0, for "no cycling"** — that is the convention every shipped
  preset follows (`games/sonic4/data/effects/ojz_effects.emp:1030-1036, 1049, 1080`).

### 1.2 How the preset reaches the palette engine (the install path)

`Effects_InstallPreset` (`preset.emp:250-357`), on every section crossing:

- `ep_cycle -> Palette_LoadCycle` (`:314-316`), a straight write.
- `ep_variants[0]` / `[1]` -> `Palette_SetVariant(slot i, ptr)` (`:318-334`), **guarded**:
  each slot is compared against the live `Pal_Variant_Ptr[i]` and the call is SKIPPED when
  unchanged. The guard is *"required, not an optimisation"* (`:242-248`): `Palette_SetVariant`
  sets `PAL_ACT_VARIANT_STALE` on every call (`palette.emp:314-316`), which forces the full
  variant re-derive.
- The offsets used are `EP_VARIANT_0 = offsetof(EffectsPreset, ep_variants)` and
  `EP_VARIANT_1 = EP_VARIANT_0 + 4` (`preset.emp:149-150`).

The legacy per-channel installers are gone: `preset.emp:198-200` says total binding
*"Replaces the three legacy per-channel installers (Palette_LoadSection /
Palette_InstallCycleSection / Raster_InstallSection)"*, and `Palette_InstallCycleSection`
has **zero non-comment hits** in `engine/` and `games/` (grep, this parcel). The legacy
`Sec.sec_pal_cycle` field (`engine/structs.emp:121`, `$24`) is still FILLED by
`ojz_sec(cycle: ...)` (`games/sonic4/data/levels/ojz/act1/act_descriptor.emp:202, 216`) and
section 3 still passes `cycle: OJZ_ShimmerCycle` there (`:277`) — but the live route to the
palette engine is `Sec.sec_effects -> EffectsPreset.ep_cycle`. **A generator targets
`preset()`'s `cycle:` argument, not `ojz_sec()`'s.** (Whether any engine code still reads
`sec_pal_cycle` at all: no non-comment reader found in `engine/` by grep in this parcel —
an implementing parcel should re-verify before deleting the field.)

### 1.3 What a VARIANT physically is

**Wire format** — `engine/effects/palette.emp:130-136`, `pub struct pal_variant` (no
`(size:)` annotation in source; 8 bytes by field sum):

| offset | field | width | legal range (enforced at) | meaning |
|---|---|---|---|---|
| +0 | `v_shift_r` | `u8` | 0..3 (`palette_dsl.emp:36`) | right-shift of the 3-bit R channel |
| +1 | `v_bias_r` | `i8` | -7..+7 (`:39`) | signed bias added after the shift |
| +2 | `v_shift_g` | `u8` | 0..3 (`:37`) | |
| +3 | `v_bias_g` | `i8` | -7..+7 (`:40`) | |
| +4 | `v_shift_b` | `u8` | 0..3 (`:38`) | |
| +5 | `v_bias_b` | `i8` | -7..+7 (`:41`) | |
| +6 | `v_lines` | `u8` | bitmask, bits 1-3; bit 0 MUST be clear (`:43`); at least one of bits 1-3 set (`:44`) | which CRAM lines the derive covers; *"bit 0 ignored — character's"* (`palette.emp:134`) |
| +7 | `v_pad` | `u8` | 0 | |

**Semantics** — per colour channel, `clamp((c >> shift) + bias, 0, 7)` on the Genesis
`0000 BBB0 GGG0 RRR0` word (`palette.emp:122-128`; the comptime model is
`palette_dsl.emp:61-75` with three build-time vectors at `:77-86`; the asm is
`Palette_DeriveVariant`, `palette.emp:744-806`). Only lines named in `v_lines` are written;
uncovered lines are left as-is (`:730`).

**Constructor** — `variant(shift_r: int = 0, bias_r: int = 0, shift_g: int = 0, bias_g:
int = 0, shift_b: int = 0, bias_b: int = 0, lines: int = %1110) -> pal_variant`
(`palette_dsl.emp:32-49`). Every range above is an `ensure` in that body, so a generator
that forwards values verbatim gets the engine's own error sentence (the same SHAPE-vs-VALUE
posture `effects_gen.py:30-40` states for bands).

**Runtime life of a bound variant:**
- Bound by `Palette_SetVariant(d0 = slot 0..1, a0 = pal_variant* or 0 = clear)`
  (`palette.emp:298-319`) into `Pal_Variant_Ptr: [u32; 2]` (`ram.emp:546`).
- Derived once per frame by `Palette_Compose -> Palette_DoVariants -> Palette_DeriveVariant`
  (`palette.emp:411-421, 705-721`) into `Pal_Variant_Stage: [u8; 128 * 2]` (`ram.emp:545`),
  a full 128-byte 4-line image per slot — **but only when `PAL_ACT_VARIANT_STALE` is set**
  (`:418-421`), i.e. when a compose layer actually moved lines 1-3 or a rebind happened.
- Consumed mid-frame by a `pal_region` band: `OP_PAL_REGION` (`raster.emp:147`) streams
  `count` words from `Pal_Variant_Stage + (slot*128 + line*32 + entry*2)` to CRAM inside
  the HBlank handler (`raster.emp:1018-1040`; the offset is `pal_stage_off`,
  `raster.emp:156-162`). This is how a `bands[i].on.pal_region.slot` in today's preset
  document meets a variant: the band names the SLOT, the preset's `ep_variants[slot]` names
  the DESCRIPTOR, and *"the runtime binding of the variant to pal_line is NOT checkable at
  build time"* (schema `$defs.pal_region.count` description; `EFFECTS_CONSUMER_CONTRACT.md`
  §2.4). **Putting `variants` in the same document as `bands` is what would make that
  binding checkable** — see §4, Q6.

**Costs, quoted from source:**
- The full variant re-derive: **19,332 cycles/frame = 15.1% of every frame**, measured on
  OJZ_ScrollTest 2026-08-13 (`palette.emp:107-111`; repeated at `preset.emp:244`). The stale
  bit (`:102-119`) and the install-path compare-and-skip (`preset.emp:242-248`) exist to
  avoid paying it on frames where nothing moved; a preset that carries the SAME variant
  pointer as the previous section pays nothing at the crossing.
- RAM: `Pal_Variant_Stage` 256 B + `Pal_Variant_Ptr` 8 B, inside the 472-byte
  `Palette_State` block (`palette.emp:90-92`; `ram.emp:540-548`). **Fixed — authoring more
  variant DOCUMENTS costs no RAM**; only the two live slots exist.
- ROM: 8 bytes per emitted `pal_variant` (`ojz_effects.emp:894`: *"Murky, Poison, CaveDark
  and Dusk cost 32 emitted bytes between them"*).
- The HBlank handler budget the region stream lives inside is *"~60-cycle"*
  (`palette.emp:703`, `raster.emp:1023`); the deep-class burst ceiling is 3 colours per
  fire (`raster_dsl.emp:275-276`).

**Shipped instances** — `games/sonic4/data/effects/ojz_effects.emp:904-908`:
`Variant_Water_Deep = variant(shift_r: 1, shift_g: 1)`, plus four unreferenced seeds
(`Variant_Water_Murky`, `Variant_Poison`, `Variant_CaveDark`, `Variant_Dusk`). **Every OJZ
preset carries `variants: [Variant_Water_Deep, 0]`** and `:974-985` says why this is NOT
incidental: under total binding *"a preset with an empty variants array would CLEAR the slot
... silently dropping the water tint act-wide"*. (`:893-894` still says the variant's only
consumer is `ojz_scroll_test.emp:277`; that hand bind was deleted in C2 Task 13 per
`games/sonic4/test/ojz_scroll_test.emp:592-594`, and the consumers today are the presets at
`:1030-1080`. Stale comment, noted.)

**Derived byte image of `Variant_Water_Deep`** (from the layout above; not read from a
listing): `01 00 01 00 00 00 0E 00`.

### 1.4 What a CYCLE SCRIPT physically is

**Wire format** — `palette.emp:146-149` (header comment) and `:150-157` (struct), walked by
`Palette_DoCycle` at `:439-478`:

```
dc.w channel_count                 // u16, big-endian; 0 = cycling OFF (Pal_Cycle_None)
per channel, 6 bytes (pal_cycle_channel):
```

| offset | field | width | legal range (enforced at) | meaning |
|---|---|---|---|---|
| +0 | `pc_line` | `u8` | 1..3 (`palette_dsl.emp:93`) | CRAM line; *"never 0 — the character's"* (`palette.emp:151`) |
| +1 | `pc_first` | `u8` | 0..15 (`:94`) | first entry index in the line |
| +2 | `pc_count` | `u8` | >= 2 and `first + count <= 16` (`:95`) | entries in the rotation; runtime treats `< 2` as a no-op (`palette.emp:488-489`) |
| +3 | `pc_period` | `u8` | 1..255 (`:96`) | **frames BETWEEN rotations; the cadence is `period + 1` frames** — see below |
| +4 | `pc_dir` | `u8` | 0 or 1 (`:97`) | 0 = forward, 1 = reverse (`palette.emp:155`) |
| +5 | `pc_pad` | `u8` | 0 | |

**The cadence is `period + 1`, transcribed from the timer logic, not from the comment.**
`Palette_DoCycle` (`palette.emp:454-461`): when a channel's timer is 0 it reloads
`period` and rotates; otherwise it decrements. So after a rotation there are `period`
non-rotating frames, and the next rotation is on frame `period + 1`. `Palette_LoadCycle`
seeds every timer to 0 (`:335-339`, *"0 = rotate on the first compose"*), so the FIRST
rotation happens on the first compose after the install. `ojz_effects.emp:493-501` records
the same `+1` (*"`period: 8` yields 9 frames, not 8"*) and books the fix as a byte-moving
runtime change deliberately NOT made — it names the proc `Palette_RunCycles`, which does
not exist; the proc is `Palette_DoCycle`. (Note the field's own comment at `palette.emp:154`
— *"frames between rotations"* — is literally true and reads as the cadence, which it is not.)

**What a rotation is** — `Palette_RotateSpan` (`:480-521`): rotate `count` consecutive
words of `Palette_Buffer` at `line*32 + first*2` one step, forward (`:503-510`) or reverse
(`:511-518`), in place. It composes BEFORE cross-fade *"so a cycling band survives a
transition"* (`:428-430`), publishes only the lines it touched into `Palette_Dirty`
(`:472-475`), and sets `PAL_ACT_VARIANT_STALE` only when something actually rotated
(`:475`, the CHANGED-not-INSTALLED rule at `:190-200`) — so a cycle and a variant in the
same preset re-derive the variant only on rotation frames.

**Constructors** — `cycle_channel(line: int, first: int, count: int, period: int, dir: int
= 0) -> pal_cycle_channel` (`palette_dsl.emp:92-100`) and the script wrappers
`cycle_script1(chs: array) -> PalCycleScript1` / `cycle_script2(chs: array) ->
PalCycleScript2` (`:112-123`; struct shapes at `palette.emp:162-163`). The header word is
DERIVED from the array length by the wrapper (`:102-107`). **Only 1- and 2-channel wrappers
exist**; `:124-125` pins `PAL_CYCLE_MAX_CHANNELS == 4` with the message *"add cycle_script4
if a script needs it"*.

**A runtime bound with NO runtime guard, recorded so it is not read as covered:**
`Palette_LoadCycle` (`:329-339`) zeroes `channel_count` timer bytes starting at
`Pal_Cycle_Timers` with no upper bound; `Pal_Cycle_Timers` is `[u8; 4]` (`ram.emp:548`)
and is followed by `Pal_Fade_Frames`, `Pal_Op`, ... (`:549-556`). A script with more than 4
channels would overwrite those cells. Today the only guard is the comptime wrappers
(`chs.len == 1` / `== 2`). **A generator must cap `cycles` at `PAL_CYCLE_MAX_CHANNELS`
(4) and, for 3-4 channels, needs `PalCycleScript3/4` + `cycle_script3/4` added on the
engine side first** (§4, Q3).

**Costs:** ROM `2 + 6 * N` bytes per script (`Pal_Cycle_None` is 2 bytes, `palette.emp:834`;
`OJZ_ShimmerCycle` is 8). RAM: `Pal_Cycle_Script` 4 B + `Pal_Cycle_Timers` 4 B, fixed
(`ram.emp:547-548`). **Per-frame CPU cost of `Palette_DoCycle`/`Palette_RotateSpan`: NOT
FOUND** — `ojz_effects.emp:498-499`: *"there is no cycling row in the budget model and no
GATE-EVIDENCE cycling capture"*; `tools/effects_budget_model.toml` carries
`max_active_variants` and `variant_stage_bytes` (`:1091, :1155`) but no cycling row (grep,
this parcel).

**Shipped instance** — `ojz_effects.emp:502-503`:
`OJZ_ShimmerCycle: PalCycleScript1 = cycle_script1([ cycle_channel(line: 2, first: 8, count: 4, period: 8) ])`,
bound by `OJZ_Preset_Sec3` (`:1035`). The sentinel `Pal_Cycle_None: [u16; 1] = [ 0 ]`
(`palette.emp:834`) is bound by every other preset.

**Derived byte images** (from the layout above; not read from a listing):
`OJZ_ShimmerCycle` = `00 01 | 02 08 04 08 00 00`; `Pal_Cycle_None` = `00 00`.

### 1.5 The scope rule both channels inherit

A variant and a cycle are **EffectsPreset channels, bound per SECTION** — the same §16.1
ruling that put `bands` in a preset document and not a scene
(`docs/superpowers/specs/2026-08-28-raster-band-ownership-design.md` §16.1, quoted at
`effects_gen.py:218-225` and `EFFECTS_CONSUMER_CONTRACT.md:346-351`: *"The palette, the
palette cycle, the variants and the raster program are channels of an `EffectsPreset`"*).
So `variants` and `cycles` belong in `presets/<id>.json` beside `bands`, and a section
reaches them through its sidecar the way it reaches `bands` today.

The per-section friction is already paid once: `Sec.sec_effects` is a POINTER to a shared
record, so a section that binds anything of its own needs its own 38-byte preset
(`ojz_effects.emp:1055-1060, 1074-1077`; section 5's split at `:1078-1080`).

---

## 2. Proposed JSON key shapes — `cycles` and `variants`

Both keys are **optional, top-level, and additive** to the closed object the hub's schema
already defines. Neither changes `bands`. Each field below maps 1:1 to an engine field
named in §1; ranges are the engine constructors' and are **not to be restated** in the
schema or the generator (the standing rule, `effects_gen.py:30-40`, `AURORA_EFFECTS_SCHEMA.md`
§7.1). The JSON types here are SHAPE (integer vs string vs array), which is the generator's
layer.

### 2.1 `cycles` — the section's one cycle script

```
"cycles": [ <channel>, ... ]        // 1..4 channels; the array IS the script
<channel> = {
  "line":   integer,   // -> cycle_channel(line:)   -> pc_line    (1..3)
  "first":  integer,   // -> cycle_channel(first:)  -> pc_first   (0..15)
  "count":  integer,   // -> cycle_channel(count:)  -> pc_count   (>= 2, first+count <= 16)
  "period": integer,   // -> cycle_channel(period:) -> pc_period  (1..255; cadence = period+1 frames)
  "dir":    integer    // -> cycle_channel(dir:)    -> pc_dir     (0 fwd / 1 rev); OPTIONAL, default 0
}
```

- **One script per document**, because `ep_cycle` is one pointer (`preset.emp:63`). The
  key is an ARRAY OF CHANNELS rather than an array of scripts so the shape cannot express
  the thing the engine cannot bind.
- `dir` is the only field with an engine default (`palette_dsl.emp:92`, `dir: int = 0`); all
  others are required in the constructor and should be required in the document
  (`bands` sets the precedent: *"all four, none with a default"*, `effects_gen.py:293-299`).
- **Absent `cycles`** = the section keeps its hand-authored cycle channel (`hand:`), exactly
  as absent `rasterRef` keeps the hand raster channel (`effects_gen.py:1203-1211`). This is
  the no-cost majority case.
- **Empty `cycles: []`**: two readings are possible (lower to `Pal_Cycle_None` = "cycling
  OFF here", or refuse like empty `bands` at `effects_gen.py:497-503`). Not decided here —
  §4, Q2.
- **Not expressible:** more than 4 channels (`PAL_CYCLE_MAX_CHANNELS`); 3-4 channels until
  `cycle_script3/4` exist (§1.4); more than one script; a period of 0 (the constructor
  refuses it; the runtime would rotate every frame); line 0 (the character's line,
  `palette_dsl.emp:93`); a cadence of exactly `period` frames (the runtime is `period + 1`
  and the fix is booked, not made — `ojz_effects.emp:499-501`); any per-frame CPU budget
  check (no cycling row exists to check against, §1.4).

### 2.2 `variants` — the two staging slots

```
"variants": [ <variant> | null, <variant> | null ]   // index = slot; length 1..2
<variant> = {
  "shift_r": integer,  // -> variant(shift_r:) -> v_shift_r  (0..3)      OPTIONAL, default 0
  "bias_r":  integer,  // -> variant(bias_r:)  -> v_bias_r   (-7..+7)    OPTIONAL, default 0
  "shift_g": integer,  // -> v_shift_g                                    OPTIONAL, default 0
  "bias_g":  integer,  // -> v_bias_g                                     OPTIONAL, default 0
  "shift_b": integer,  // -> v_shift_b                                    OPTIONAL, default 0
  "bias_b":  integer,  // -> v_bias_b                                     OPTIONAL, default 0
  "lines":   integer   // -> variant(lines:)   -> v_lines    (bitmask; bits 1-3; bit 0 clear; non-zero)  OPTIONAL, default 14 (%1110)
}
```

- **Array index = `ep_variants[i]` = `Palette_SetVariant` slot = the `slot` a `pal_region`
  band names.** That identity is the whole reason to spell it as a positional array: a
  document whose `bands[i].on.pal_region.slot` is 1 and whose `variants[1]` is `null` is a
  band streaming from an idle slot, and with both keys in one document that becomes
  checkable (§4, Q6).
- `null` in a position lowers to `0` = *"unused slots 0 = clear"* (`preset.emp:64`). A
  length-1 array leaves slot 1 at the `hand:` value (see §3.3) — or at 0; §4, Q5.
- Every field is optional with the constructor's own default (`palette_dsl.emp:32-35`), so
  `Variant_Water_Deep` is `{"shift_r": 1, "shift_g": 1}` verbatim.
- `lines` is proposed as the INTEGER BITMASK because that is the 1:1 field; an
  author-facing `[1, 2, 3]` spelling would be a shape translation of the kind the generator
  already does for `sh` and `transition` (`effects_gen.py:41-46`) and is the hub's call —
  §4, Q4.
- **Absent `variants`** = the section keeps its hand-authored variant pair (`hand:`). **This
  is load-bearing, not a convenience:** every shipped preset carries
  `[Variant_Water_Deep, 0]` and an all-clear pair would drop the act-wide water tint at
  the first crossing (`ojz_effects.emp:974-985`). A document must be able to say nothing
  about variants without clearing them.
- **Not expressible:** a third slot (the `andi.w #1` mask, `palette.emp:304`; the
  `[*u8; 2]` field; three ensures); a shift outside 0..3 or a bias outside -7..+7 (3-bit
  channels); any coverage of CRAM line 0 (`palette_dsl.emp:43`; the derive never writes it,
  `palette_variant_gate.py` fixture 4); a variant that is NOT a per-channel
  shift-and-bias (there is no lookup-table or per-entry form — `pal_variant` is the only
  descriptor); per-entry masks (coverage is whole lines, `v_lines`); a transform of line
  0/the character.

### 2.3 One worked example document

`games/sonic4/data/editor/effects/presets/ojz_sec3_shimmer.json` — the hand-written section
3 (`OJZ_Preset_Sec3`, `ojz_effects.emp:1035`) re-expressed as a document, plus one band so
the file is a valid `bands`-carrying document under today's schema:

```json
{
  "schema": 1,
  "id": "ojz_sec3_shimmer",
  "name": "OJZ act 1 section 3 - shimmer band over deep water",
  "bands": [
    { "top": 120, "bot": 148, "sh": false,
      "on": { "pal_region": { "addr": 72, "slot": 0, "pal_line": 2, "entry": 4, "count": 3 } } }
  ],
  "cycles": [
    { "line": 2, "first": 8, "count": 4, "period": 9, "dir": 0 }
  ],
  "variants": [
    { "shift_r": 1, "shift_g": 1 },
    null
  ]
}
```

Bound from the sidecar exactly as `rasterRef` is today
(`games/sonic4/data/editor/ojz/act1/section_5.meta.json` is the live example:
`{"bgLayoutRef": null, "paletteRef": null, "rasterRef": "ojz_sec5_showcase", "sceneRef": null}`).
Whether ONE ref key now carries all three channels of the document or each channel gets its
own key is §4, Q1.

**`"period": 9` is not a typo, and the unit is the reason** *(AMENDED 2026-09-02 — it read
`8` when this page was written, which was wrong)*. **The document's `period` is in DOCUMENT
FRAMES** — the author's meaning, "a rotation every N frames" — and under the hub's Q7 ruling
the generator absorbs the engine's off-by-one by emitting `period - 1`. Shipped
`OJZ_ShimmerCycle` carries the engine byte `08` (§1.4's derived image
`00 01 | 02 08 04 08 00 00`) and therefore runs on a **9**-frame cadence, so a document that
is byte-for-byte identical to it must say `9`. Written as `8` this document would emit `07`
and run the shimmer at 8 frames — one frame faster than the shipped screen, visibly.

*Ruling: empyrean `docs/AURORA_EFFECTS_SCHEMA.md` §7.2, ruling Q7, read at empyrean
`origin/main` = `38f6df4130bcc00f5c859d78e0e30ff7c5fdb349`.*

*Note: `9` is the FAITHFUL value — it preserves the shipped shimmer exactly. Whether the
owner would rather have `8` (a shimmer one frame faster than today's) is a LOOK call, parked
as decision card **`d-51-shimmer-cadence-look`** in `docs/decisions.jsonl`. That card is
about whether to depart from faithfulness; it is not a reason to write `8` here.*

What that document lowers to is §3. Its `cycles` entry is byte-for-byte `OJZ_ShimmerCycle`
and its `variants[0]` is byte-for-byte `Variant_Water_Deep`, which is what §3.4 proves.

---

## 3. What the generator must emit

Following the shape the `bands` arm already emits (`effects_gen.py:1000-1022`
`render_preset`; the generated output at
`games/sonic4/data/generated/ojz/act1/effects_scenes.emp:136-145`) and the chooser it
already emits (`effects_gen.py:1487-1501`; output at `effects_scenes.emp:210-215`).

### 3.1 Imports the generated module must gain

The wire-format struct names must be in scope at the EMISSION site — *"a comptime fn's
struct-literal field values resolve at the EMISSION site's scope"* (`palette_dsl.emp:8-12`)
— which is why `ojz_effects.emp:48-52` imports both halves:

```
use engine.effects.palette.{pal_cycle_channel, PalCycleScript1, PalCycleScript2, pal_variant}
use engine.effects.palette_dsl.{cycle_channel, cycle_script1, cycle_script2, variant}
```

Emitted only when a document carries the key (the `bands` rule: *"APPENDS NOTHING AT ALL
when there are none"*, `effects_gen.py:1445-1449`, so the no-content bake stays
byte-identical and CRC-checkable).

### 3.2 Data blocks, one per document per key

```
// ---- AURORA-AUTHORED PALETTE CYCLE, through the REAL constructors ----
pub data EditorCycle_OJZ_Act1_ojz_sec3_shimmer: PalCycleScript1 = cycle_script1(
    [ cycle_channel(line: 2, first: 8, count: 4, period: 8, dir: 0) ])

// ---- AURORA-AUTHORED PALETTE VARIANTS ----
pub data EditorVariant_OJZ_Act1_ojz_sec3_shimmer_0: pal_variant = variant(shift_r: 1, bias_r: 0, shift_g: 1, bias_g: 0, shift_b: 0, bias_b: 0, lines: 14)
```

- **`period: 8` in that emitted call is the ENGINE BYTE, and it is correct as written — it
  is not the `9` §2.3's document says.** The two numbers differ by one on purpose: the
  document is in DOCUMENT FRAMES and the generator emits `period - 1` (hub §7.2, ruling Q7),
  so §2.3's `"period": 9` lowers to exactly the `period: 8` above, which is exactly what
  `OJZ_ShimmerCycle` carries by hand (`ojz_effects.emp:502-503`). Reading them as a
  contradiction is the mistake this note exists to prevent.
- Names follow `ActNames.raster()`'s act-qualified rule and its stated reason
  (`effects_gen.py:1274-1287`): `EditorCycle_<CAP>_<id>` and `EditorVariant_<CAP>_<id>_<slot>`.
  A `null` slot emits nothing.
- The wrapper is chosen by channel count (`cycle_script1` for 1, `cycle_script2` for 2);
  3-4 needs the engine additions in §1.4.
- Every constructor `ensure` fires on the authored numbers because a `pub data` in a lowered
  module is elaborated unconditionally (`effects_gen.py:240-246`; the module is reached
  through `act_descriptor.emp`'s import, witnessed by `tools/effects_seam_gate.py:1-30`).
- Placement: the same content-derived `"section:ojz_effects_editor_act1"` row
  (`games/sonic4/map.toml:127`), so no map.toml edit (`effects_scenes.emp:20-25`).

### 3.3 Choosers, and the `preset()` call site

Two more always-emitted zero-byte `pub comptime fn`s beside `ojz_act1_sec_raster`
(`effects_scenes.emp:210-215`), same `hand:` contract (`RASTER_BINDING_BANNER`,
`effects_gen.py:1618-1637`):

```
pub comptime fn ojz_act1_sec_cycle(sec: int, hand: Label = 0) -> Label {
    ensure(sec >= 0 && sec < 9, "...")
    comptime var out = hand
    if sec == 3 { out = EditorCycle_OJZ_Act1_ojz_sec3_shimmer }
    return out
}
pub comptime fn ojz_act1_sec_variant(sec: int, slot: int, hand: Label = 0) -> Label {
    ensure(sec >= 0 && sec < 9, "...")
    ensure(slot >= 0 && slot < 2, "...")
    comptime var out = hand
    if sec == 3 && slot == 0 { out = EditorVariant_OJZ_Act1_ojz_sec3_shimmer_0 }
    return out
}
```

and in `games/sonic4/data/effects/ojz_effects.emp`, the section's own preset:

```
pub data OJZ_Preset_Sec3: EffectsPreset = preset(pal: OJZ_Palette,
    raster:   ojz_act1_sec_raster(sec: 3, hand: Raster_Program_None),
    cycle:    ojz_act1_sec_cycle(sec: 3, hand: Pal_Cycle_None),
    variants: [ ojz_act1_sec_variant(sec: 3, slot: 0, hand: Variant_Water_Deep),
                ojz_act1_sec_variant(sec: 3, slot: 1, hand: 0) ])
```

- **Per-slot Label-returning choosers are proposed because that is the ONE chooser shape
  proven to compose into `preset()` and reach the ROM** — item 1 step 2 read the emitted
  `ep_raster` longwords back out of `s4.debug.bin` for both arms
  (`docs/DEFERRED_WORK.md:16650-16656`). A single chooser returning `[Label; 2]` into the
  `variants:` array argument is **NOT VERIFIED** in this parcel (no build was run); if sigil
  accepts it, it is the tidier form, and that is a one-line question for the implementing
  parcel, not for the hub.
- `hand:` for `cycle:` is `Pal_Cycle_None`, never 0 (§1.1's convention); `hand:` for
  variants is whatever the section carries today, which for every OJZ section is
  `[Variant_Water_Deep, 0]`.
- Witness equates, mirroring `EditorRaster_OJZ_Act1_Bindings` (`effects_scenes.emp:161-163`,
  consumed by `tools/effects_seam_gate.py`): `EditorCycle_OJZ_Act1_Bindings` and
  `EditorVariant_OJZ_Act1_Bindings`.

### 3.4 Byte-compatibility with the hand-written data, and how it is proven (red-first)

The generated `EditorCycle_..._ojz_sec3_shimmer` must be the same 8 bytes as
`OJZ_ShimmerCycle` (`ojz_effects.emp:502-503`), and `EditorVariant_..._0` the same 8 bytes
as `Variant_Water_Deep` (`:904`). Two layers, both red-first:

1. **Text golden, no build (tools/test_effects_gen.py).** Render the worked document and
   assert the emitted `cycle_channel(...)` / `variant(...)` argument lists equal the hand
   call text at `ojz_effects.emp:503` and `:904` after defaults are made explicit. **Red
   first, and the mutation is on the DOCUMENT side:** change the fixture document's
   `"period"` from `9` to `8` (§2.3), which lowers to `cycle_channel(..., period: 7, ...)`
   against the hand call's `period: 8`, and watch it fail by name before the real document
   passes. *(AMENDED 2026-09-02: this used to read "mutate `period` to 7 in the fixture",
   which was ambiguous about which side 7 lives on. 7 is an EMITTED byte, never a document
   value; the document value that produces it is 8.)* The existing refusal test `test_the_reserved_wave2_keys_are_refused_BY_NAME_not_as_unknown`
   (`:1406-1416`) must be INVERTED for `variants`/`cycles` in the same parcel (it goes red
   the moment the keys are accepted, as its author intended for `bands`'
   `test_the_real_repo_ships_no_preset_documents`, `EFFECTS_CONSUMER_CONTRACT.md:336-341`).
2. **Byte golden, on the built ROM.** Read the span at `EditorCycle_OJZ_Act1_ojz_sec3_shimmer`
   and at `OJZ_ShimmerCycle` out of `s4.debug.bin` at the listing's own addresses — the
   exact method step 2 used for `ep_raster` (`docs/DEFERRED_WORK.md:16650-16656`) — and
   assert the two 8-byte spans are equal; likewise the two `pal_variant` spans. **Red
   first: the same document-side mutation (`"period"` 9 → 8), rebuilt, differs at index 5
   of the 8-byte image** — `00 01 | 02 08 04 08 00 00` becomes `00 01 | 02 08 04 07 00 00`.
   This can live as a row in
   `tools/effects_seam_gate.py` (it already parses `s4.lst` for this module's symbols) or in
   `tools/effects_gates.py`; **no gate is added by THIS parcel** — it is the implementing
   parcel's, and the effects gate ritual (`CLAUDE.md`, "Effects gate ritual") applies to it.

   > **DO NOT write this byte-golden as a comptime `first_mismatch` ensure against the hand
   > `pub data` twin.** *(AMENDED 2026-09-02. This page used to offer
   > `first_mismatch(a, b) == -1` — `raster_dsl.emp:3402`, the idiom at
   > `ojz_effects.emp:213-216, 1273-1276` — as "the in-`.emp` alternative for arrays", with
   > the struct case marked NOT VERIFIED. It has since been verified, and the verdict
   > refutes the recommendation. The recommendation is withdrawn.)*
   >
   > The probe (`docs/superpowers/probes/2026-09-02-item5-comptime-probe.md`, verdict Q2-e,
   > evidence RED-4) measured the hand twin in exactly this position: *"**NO.** Bare in an
   > ensure: `unknown name`. Inside an array literal it resolves as a LABEL and
   > label-vs-struct `!=` is always true, so
   > `first_mismatch([Variant_Water_Deep], [variant(...)])` reports index 0 for the EQUAL
   > twin too (always-red, useless). Field access on the data symbol: `unknown name`."*
   >
   > **Why this matters more than a stale sentence normally would.** The construction is
   > **always-red** — it fires on correct code — and the single most natural edit anyone
   > makes to take an always-red guard green is to flip the expectation from `== -1` to
   > `== 0`. The probe measured that step too: *"with the EQUAL twin and `== -1` it fires
   > 'index 0'; with the EQUAL twin and `== 0` it passes."* So one keystroke converts an
   > always-red guard into a **permanently vacuous** one, and it looks like debugging the
   > whole way. This page's own withdrawn sentence sat next to that trap as an invitation,
   > which is the reason it is deleted rather than merely qualified.
   >
   > **Corroboration, stated as the sigil lane's measurement with their stated limit**
   > (2026-09-02): `first_mismatch` appears nowhere in sigil's corpus — no `.emp` fixture,
   > no Rust test, zero hits across master — so withdrawing this recommendation breaks no
   > fixture on their side. Their limit, in their words: the grep rules out **the specific
   > construction**, not the general shape of a cross-type comparison fixture.
   >
   > **What to do instead:** layers 1 and 2 above, both Python, neither of which needs
   > comptime equality at all. If a future parcel insists on an in-`.emp` guard, the only
   > shape the probe proved is a module-level `const X = variant(...)` feeding BOTH the
   > `pub data` and the ensure (probe verdict Q2-f) — and the probe's "Left open" item 1
   > records that whether such a `const` is visible ACROSS modules (generated
   > `effects_scenes.emp` ↔ hand `ojz_effects.emp`), which is the case item 5 actually
   > needs, **was not probed**.

The reference spans are the derived images in §1.3/§1.4 (`00 01 02 08 04 08 00 00` and
`01 00 01 00 00 00 0E 00`); the gate should read them from the listing, not from this page.

### 3.5 What else moves with the keys (the item's real size)

- `PRESET_KEYS` gains the two names and `PRESET_REFUSED_KEYS` loses them
  (`effects_gen.py:266, 275-286`); `load_preset` gains shape checks of the `bands` kind
  (`:451-518`: types, required keys, array-ness, positional length) and NO value checks.
- `tools/EFFECTS_CONSUMER_CONTRACT.md` §2.4 gains rows for every field above (the file's own
  rule: a new reader is a contract change that amends it *"and the empyrean schema pair in
  the same series"*, `effects_gen.py:5-8`), and `docs/EDITOR_RASTER_PRESETS.md` §B's key
  list is machine-compared against the generator's constants
  (`tools/test_effects_gen.py::TestEditorRasterPresetsDoc`, per that page's header).
- The hub's schema gains the two optional properties (§2) and drops them from its
  reserved-and-refused description; `AURORA_EFFECTS_SCHEMA.md` §7 keeps `fires` and
  `effectsRef` reserved.
- Every byte this emits pairs with sigil (DoD row: *"yes, paired"*).
- The section-3 hand data (`OJZ_ShimmerCycle`, the `cycle:` on `ojz_sec(sec: 3)`) becomes a
  second source for one screen the day a document binds it; retiring it is the same shape
  as `authored_probe`'s retirement in item 1.

---

## 4. Open questions for the owner or hub (listed, not answered)

- **Q1 — one ref or three.** Does the existing `rasterRef` grow to bind ALL channels the
  named document carries (then its name is wrong the moment a document has no `bands`), do
  `cycleRef` / `variantsRef` siblings appear (mirroring `rasterRef`'s own shape, §3.1 of the
  hub doc), or is this the day `effectsRef` is spent — which the hub reserved for the TOTAL
  binding and which still needs a palette reference `ep_pal` cannot default
  (`preset.emp:57`, `:119-120`)? The hub refused option C for item 1; item 5 is where that
  question comes back.
- **Q2 — empty `cycles: []`.** "Cycling OFF here" (lower to `Pal_Cycle_None`) or refuse (the
  empty-`bands` precedent: *"if the intent is 'no raster here', delete the file"*)? Unlike
  bands, OFF is a value the engine can bind, so the precedent does not settle it.
- **Q3 — 3- and 4-channel scripts.** Add `PalCycleScript3/4` + `cycle_script3/4` on the
  engine side before or with the lowering, or cap the document at 2 and say so in the
  schema? `PAL_CYCLE_MAX_CHANNELS` is 4 and `Pal_Cycle_Timers` is sized for it; the
  wrappers stop at 2 (`palette_dsl.emp:112-125`).
- **Q4 — `lines` spelling.** Integer bitmask (1:1 with `v_lines`) or an array of line
  numbers translated by the generator? Authoring ergonomics are aurora's; the 1:1 form is
  what this page proposes.
- **Q5 — a short `variants` array.** Does a length-1 array leave slot 1 at `hand:` (keeps
  today's water tint) or at 0 (clears it)? The engine's own words are *"unused slots 0 =
  clear"* (`preset.emp:64`) but that describes the RECORD, not the document's silence.
- **Q6 — the slot-binding assertion.** With `bands[i].on.pal_region.slot` and
  `variants[slot]` in one document, should the generator (or an engine ensure) refuse a
  band that streams from a slot the document leaves `null`/absent? Today that binding is
  the schema's own listed *"NOT checkable at build time"* limit; it becomes checkable, but
  only if the answer to Q5/absent-`variants` is "the document is the whole truth", which it
  is not while `hand:` fallbacks exist.
- **Q7 — the `period + 1` cadence.** Ship the key with the engine's true cadence
  (`period + 1`) documented in the schema row, or first land the booked runtime change that
  makes `period: N` mean N frames (`ojz_effects.emp:499-501`)? A schema that documents
  `period + 1` and an engine later fixed to `period` breaks every authored cycle by one
  frame silently.
- **Q8 — retire the hand twins.** When a document reproduces `OJZ_ShimmerCycle` /
  `Variant_Water_Deep`, do the hand instances (and the four unreferenced seed variants,
  `ojz_effects.emp:892-897`) go the way of `authored_probe`, and does the legacy
  `Sec.sec_pal_cycle` field (`structs.emp:121`) go with them?
- **Q9 — a cycling cost row.** Item 5 lowers a per-frame effect the budget model has no row
  for (§1.4). Is a `[palette.cycle_cost]` row (a cross-repo pin, like the bob's) part of the
  item or a rider?
- **Q10 — naming hazard, for the hub's prose.** `cycles` (this key) and the DEBUG hotkey's
  *raster cycle table* (`RASTER_CYCLE_COUNT`, `tools/test_raster_cycle_table_lint.py:6-16`)
  are unrelated; the contract should say which "cycle" it means once, so a reader of the
  lint does not conflate them.

---

## 5. NOT FOUND — what this page looked for and could not find

- **Per-frame CPU cost of `Palette_DoCycle` / `Palette_RotateSpan`** — no measurement, no
  budget-model row (`ojz_effects.emp:498-499`; `tools/effects_budget_model.toml` grep).
- **`Palette_RunCycles`** — named at `ojz_effects.emp:494`; no such proc exists. The proc
  is `Palette_DoCycle` (`palette.emp:439`).
- **`cycle_script3` / `cycle_script4` / `PalCycleScript3` / `PalCycleScript4`** — do not
  exist (`palette_dsl.emp:112-125`, `palette.emp:162-163`).
- **A `(size: N)` annotation on `pal_variant` / `pal_cycle_channel` / `PalCycleScriptN`**
  — none in source (`palette.emp:130-163`); sizes above are field sums.
- **A runtime bound on `channel_count`** in `Palette_LoadCycle` / `Palette_DoCycle` — none
  (`palette.emp:329-339, 442-444`).
- **The consumer `ojz_scroll_test.emp:277` claimed at `ojz_effects.emp:893-894`** — the
  bind was deleted (`ojz_scroll_test.emp:592-594`); consumers are the presets.
- **Any engine reader of `Sec.sec_pal_cycle`** — no non-comment hit in `engine/` (grep, this
  parcel); re-verify before deleting the field.
- **Whether a comptime fn may return `[Label; 2]` into `preset(variants:)`**, and whether
  two struct values can be compared by `first_mismatch` — unverified, no build here.
  - *Verified 2026-09-02* (`docs/superpowers/probes/2026-09-02-item5-comptime-probe.md`,
    built, red-first, ROM read-back): **both YES.** A `-> [Label; 2]` (or `-> array`) chooser
    reaches `ep_variants` in slot order, byte-identical to the hand pair; `first_mismatch`,
    direct `==`/`!=`, and field-wise all compare `pal_variant` / `pal_cycle_channel` values
    and all fire on a one-field mutation; the prefix case still returns -1. Two caveats the
    implementing parcel needs: a `[Label; 2]` fn annotation is NOT length-checked (the
    emitted record is, blamed on the `pub data` line), and the hand `pub data` twin cannot
    be named in the ensure (`unknown name` bare; a LABEL inside an array literal, which makes
    `first_mismatch([Variant_Water_Deep], ...)` always-red) — the value must come through a
    comptime-visible `const`.
- **A cycling capture in GATE-EVIDENCE** — none (`ojz_effects.emp:498-499`).
