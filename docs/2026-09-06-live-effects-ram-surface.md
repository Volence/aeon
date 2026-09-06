# LIVE-EFFECTS — the RAM surface an Oracle panel writes

For the oracle lane, so a panel is built against a stated contract rather than a struct
inferred from bytes. Everything below is **measured from this tree and from a running
window**, not derived from source alone; where something is not measured it says so.

Written 2026-09-06T15:52:24Z against aeon master `852f1a85`; addresses read from `s4.debug.lst`.

## ⚠ 0. CORRECTION (2026-09-06T17:04:41Z) — §1 BELOW WAS A *WHAT-IS-READ* SURVEY PRESENTED AS A *WHAT-TO-WRITE* CONTRACT

**Oracle found this by building against the engine instead of against this note, and they were
right to. Read §0 before §1; §1's addresses are correct and its ADVICE was incomplete in four
ways, one of which writes over code.**

Their sentence is the finding and it generalises past this file: **a what-to-write contract cannot
be derived from a what-is-read survey.** I traced where the engine READS each selector, confirmed
it re-reads every frame, and concluded a panel could just write it. Every one of those reads is
real. What I never traced is what the engine WRITES, and each channel has a companion cell that
makes a bare pointer poke either overwritten or inert.

**All four re-verified here in aeon's own source before this correction was written** — a peer's
claim about our tree is the class this lane verifies rather than accepts.

### (1) `Raster_Program` is an OUTPUT. Write `Raster_Pending`.
The install path writes `Raster_Pending` (`engine/effects/raster.emp:946`); the VBlank side reads
and clears it (`:974`, `:976`) and the engine itself writes `Raster_Program` (`:1024`, `:1831`).
**So a poke into `Raster_Program` is a write into the machinery's output**, and a stale
`Raster_Patch_Tab` re-records the outgoing program every VBlank. The panel's write cell is
`Raster_Pending`.

### (2) Parallax: a transition PROMOTES `Parallax_Target_Config` over a poked current.
While `Parallax_Transition_Frames != 0` the state machine is mid-lerp, and when the counter
reaches zero the active config reverts — so a bare write to `Parallax_Current_Config` during a
transition is discarded. **The panel writes the `.instant` arm's FOUR cells**
(`engine/level/parallax.emp:1284-1287`): `Parallax_Current_Config`, `Parallax_Target_Config = 0`,
`Parallax_Transition_Frames = 0`, `Parallax_Snap_Pending = 1`. **Without the last one the band
scrolls lerp toward the new targets instead of snapping**, which is the engine's own stated reason
for that arm writing four cells rather than one.

### (3) Bands: the pointer alone is INERT — `BgAnim_SetTable` also poisons `BgAnim_LastStep`.
`engine/level/bg_anim.emp:183-186` writes the pointer **and then** `moveq #-1` into two longwords
of `BgAnim_LastStep`. Those are the per-band "last step drawn" sentinels; without poisoning them
the walk believes it has already drawn this step and **the switch appears to happen and nothing
repaints.** A panel must write the pointer and both `BgAnim_LastStep` longwords.

### (4) ⚠ `Parallax_Active_Config` IS A PROC, NOT A CELL — writing it writes over CODE.
`pub proc Parallax_Active_Config` at `engine/level/parallax.emp:1358`. It reads like a state
variable and is executable memory. **§1's original text did not warn**, and a panel resolving it
by name from the listing and poking it would corrupt the ROM image in RAM-backed shapes and fault
in others.

### And one the panel must NOT write
**VDP register `$0B` (Mode Set 3) is `Parallax_Update`'s alone** — it asserts it every frame from
the active config, so a panel writing it is overwritten within a frame and, worse, disagrees with
the buffers the same pass builds.

### What I should have done
Traced each selector's WRITERS as well as its readers, and asked of each: *if I write this cell
myself, what else does the engine's own installer do that I am not doing?* **That question is
answerable from the same source I already had open.** I had even read `BgAnim_SetTable`'s header
that morning — *"Out: `BgAnim_Table_Ptr` = a0, every band's LastStep poisoned to the Init
sentinel"* — and did not carry it into the note. **Having the fact and not using it is worse than
not having it.**

## 1. The three selectors — write these, never `Debug_Lab_Index`

| what | symbol | address | width | shape |
|---|---|---|---|---|
| parallax scene | `Parallax_Current_Config` | `$FFFF88EC` | u32 | **both** (release + debug) |
| raster program | `Raster_Program` | `$FFFF8BD6` | u32 | **both** |
| band table | `BgAnim_Table_Ptr` | `$FFFFE91A` | u32 | **DEBUG ONLY** |

Each holds a **pointer**, and the engine **re-reads it every frame** — `Parallax_Update`
lists `Parallax_Current_Config` under its own *Reads*, and the raster build does
`move.l Raster_Program, d0` per frame. **So a write takes effect on the next frame with no
engine change.** Observed live across two lab rows: `Raster_Program` held `Raster_Buf_B`
(RAM) on the floor row and `EditorRaster_OJZ_Act1_aurora_ramp_witness` (ROM) on another.

**`Debug_Lab_Index` (`$FFFFEE0D`, u8) is the CHORD'S CURSOR ONLY.** Writing it moves the
on-screen label and changes nothing that runs. This cost this lane an hour today — the
label said one row while the machine ran another.

**`Raster_Program` = 0 means no program**, and the engine short-circuits on it
(`beq` after the read). `BgAnim_Table_Ptr` = 0 is **never valid**; `BgAnim_Init` seeds it.

**Shape warning: the band selector does not exist in a release build.** A panel that offers
band switching must gate on the shape, or it will write a RAM address that is something
else entirely. The other two are present in both.

## 2. The band table layout

```
BgAnim_Table:  u16  count            // number of records that FOLLOW
               band[count]           // 44 bytes each, contiguous
```

`count` is how many of the following records the walk reads, so a **table whose count is 0
turns the whole system off** — that is exactly how the shipped act boots silent.
`BGANIM_MAX_BANDS` = 4.

One record, `struct bganim_band`, **44 bytes**, pinned by an `ensure` in
`engine/level/bg_anim.emp`:

| off | field | type | meaning / range |
|---|---|---|---|
| 0 | `driver` | u16 | **0 = Camera_X, 1 = Camera_Y, 2 = Logic_Tick.** Only these three |
| 2 | `rate_shift` | u16 | `step = driver_value >> rate_shift`. Larger = slower |
| 4 | `step_mask` | u16 | pattern period along the axis **in px, minus 1** (so 63 = 64 px). Must be `2^n - 1` |
| 6 | `col_shift` | u16 | **log2 of the rotation UNIT in bytes.** Historical name: `rows*32` horizontal, `cols*32` vertical |
| 8 | `tile_count` | u16 | tiles in the band |
| 10 | `vram_dest` | u16 | **VRAM byte address** of the band's first slot |
| 12..44 | `banks` | u32 x 8 | pointers to the 8 pre-shifted art banks, 1 px apart |

**Worked example, the shipped act's band 0**, straight out of the generated module:
`[0, 4, 63, 7, 32, $8000]` = Camera_X driven, 1 px per 16 units, 64 px period, rotation
unit 128 B, 32 tiles, first slot at VRAM $8000.

**The fields a panel can usefully nudge are `driver` and `rate_shift`.** `step_mask` and
`col_shift` are geometry derived from the art's shape — changing either without changing
the art gives a cadence the art does not have, which is a picture rather than an effect.
`vram_dest` and `banks` are placement and would need the art moved.

## 3. Bands-off has NO canonical target — a real gap, named rather than papered over

> **⚠ CLOSED — this section is STALE as written (noted 2026-09-06 by the live-effects-hook
> lane, which read the symbol at master while looking for a placement precedent).**
> `BgAnim_Table_Empty` EXISTS: `engine/level/bg_anim.emp`, end of module, the second option
> below, landed. Its own banner carries two facts a panel needs and this section does not:
> the data is DEBUG-only, and **it appears in the RELEASE listing with an address anyway**
> while `BgAnim_Table_Ptr` does not — so a bands-off control must gate on BOTH symbols, not
> on the target alone. Read that banner, not this section, and treat the paragraph below as
> the record of the gap rather than as its current state.

There is **no `BgAnim_Table_Empty` symbol in this tree.** Bands-off means pointing
`BgAnim_Table_Ptr` at a `u16` containing 0. The shipped act's own `BgAnim_Table` happens to
be exactly that (it is `default_off`), so it works today **by coincidence of content, not by
contract** — an act with live bands has a non-zero count there.

**Two ways to close it, and the second is mine to do if oracle wants it:** the panel supplies
its own zero word in RAM and points at that; or aeon adds a 2-byte `BgAnim_Table_Empty`
constant so bands-off has a stable, act-independent target. **Say which and I will land the
second — it is two bytes.**

## 4. Nudging parameters: NOT YET, and this is the S hook

> **✅ LANDED 2026-09-06 (parcel `live-effects-hook`). §6 below is the contract; this section
> is the design note that produced it.** The scratch, the arm cell and
> `Parallax_InstallScratch` are on branch `parcel/live-effects-hook`.

`Parallax_Current_Config` points at **ROM**, so a scene's factors cannot be edited in place.
The hook is the live-palette shape: a **RAM scratch config**, plus an entry point that copies
the active ROM config into it and re-points the selector; the panel then edits the RAM copy
and the next frame picks it up.

**The pattern already exists on the raster channel** — `Raster_Buf_A` (`$FFFF8BE4`) and
`Raster_Buf_B` (`$FFFF8C64`), 128 B each (`RASTER_BUF_SIZE`), are RAM working copies and
`Raster_Program` legitimately points at them. So this is copying a shape, not inventing one.
**Until it lands, a nudge control has nothing to write and should not ship** — a slider that
silently does nothing is worse than an absent one.

## 5. The torn-frame caveat DISSOLVES under pause-write-resume — oracle's correction, accepted

I flagged that a mid-frame write races the once-per-frame read. **Oracle is right that a
paused write cannot land mid-frame**, so the pause-write-resume flow the owner already
accepted (*"a small pause to pause and unpause for the change is fine"*) removes it entirely.
**The caveat stands only for a write to a running machine**, which is the scripted-sweep case
and not the panel's.

## 6. THE SCRATCH CONFIG — the surface a nudge control writes (LANDED 2026-09-06)

Everything in this section is measured from `s4.debug.lst` and from the structs that decide
the layout, not read off the design. **DEBUG SHAPES ONLY** — see the shape note at the end.

### 6.1 The three symbols

| what | symbol | address (s4.debug) | width | shape |
|---|---|---|---|---|
| the RAM working copy | `Parallax_Scratch_Config` | `$FFFFEA26` | 542 B | **DEBUG ONLY** |
| one past its end | `Parallax_Scratch_Config_End` | `$FFFFEC44` | — | **DEBUG ONLY** |
| the request cell | `Parallax_Scratch_Arm` | `$FFFFEC44` | u8 | **DEBUG ONLY** |

**542 is derived, not chosen**, and the derivation is the reason a panel can trust it for any
scene rather than for the shipped ones:

```
  sizeof(parallax_config)                 = 30                 the header
+ sizeof(band_record) * MAX_PARALLAX_BANDS = (10+0+10+4+8) * 16 = 512   the widest band array
                                          ----
                                            542
```

`10+0+10+4+8` is the legacy `band_entry` plus this game's four capability tails
(ext/curve/drift/remap; ext is 0 today). Both halves are pinned in `engine/ram.emp` rather
than trusted — the header by an `extern("parallax_config_len")` ensure, the per-band sum by
being literally the expression `Parallax_Shadow_Bands` is reserved with, which
`engine/level/parallax.emp` already checks against `sizeof(band_record) * MAX_PARALLAX_BANDS`.
So a capability that widens a band cannot leave the scratch short silently.

**ONE buffer, not two, and the asymmetry with the raster channel is derived rather than
inherited.** `Raster_Buf_A`/`_B` are a pair because `Raster_BuildSchedule` **rebuilds** the
program every VBlank while `Raster_HInt` walks the live one — the engine is its own second
writer and needs a back buffer. Nothing rebuilds a parallax config: it is read-only input,
read once per frame by `Parallax_Update`. The only writer is the panel, under pause (§5). A
second buffer here would have no producer.

### 6.2 How to install it — poke a byte, run a frame

```
write $FFFFEC44 = 1        (Parallax_Scratch_Arm; any nonzero value)
run one frame
read  $FFFF88EC            (Parallax_Current_Config)
```

If `Parallax_Current_Config` now reads `$FFFFEA26`, the scratch is installed and holds a copy
of the config that was active. **That compare is the success test** — the arm cell is a
request byte, not a status byte; the engine clears it as it services it whether the install
took or was refused. (`Parallax_Current_Config` stores the full sign-extended long
`$FFFFEA26` where the listing resolves the symbol to the 24-bit bus address `$FFEA26`. Mask
before comparing; a raw compare is a false mismatch, and it was the first thing this lane's
own probe got wrong.)

**⚠ The source is NOT necessarily the config the pointer held when you armed.** The arm frame
runs the section boundary check too, and `Parallax_Active_Config` returns the *target* during
a transition — so the hook copies whatever was active when `Parallax_Update` reached the
poll. **Measured, this exact case:** the pointer read `$01428E` before arming and the scratch
came back byte-identical to the config at `$012F08`. That is the engine behaving normally.
A panel that wants to *know* what it is editing reads the scratch after the install rather
than assuming it holds the config it last displayed.

**`Parallax_Snap_Pending` reads 0 after the arm frame, and that is the PASS.** The install
sets it, and the same frame's `Parallax_Update` pass — the one that runs immediately after
the poll — consumes it. A 1 read back would mean the snap did *not* happen.

**Why a poke and not a call.** An Aether client drives a bus, not a call stack: it can write a
byte and run a frame and cannot force a `jsr`. `Parallax_Update` polls the arm at its head,
**ahead** of its own config select, so the install lands on **that** frame rather than the one
after — a panel that armed and stepped exactly one frame would otherwise read the ROM pointer
back and conclude the hook did nothing.

`Parallax_InstallScratch` is also callable directly if a client ever can: `In:` nothing,
`Out:` carry CLEAR = installed, carry SET = refused, `Clobbers:` d0-d2/a0-a1.

**It is REFUSED, with nothing written, when** no config is active (parallax off) or the active
config's `pcfg_band_count` exceeds `MAX_PARALLAX_BANDS` (16). A refusal never clamps — a
clamped copy is a scene with bands silently missing.

**Three consequences a panel has to handle:**

1. **Crossing a section boundary EVICTS the scratch.** `Parallax_CheckBoundary` installs the
   new section's own ROM preset, exactly as it always did. Re-arm after a crossing.
2. **Arming again does NOT reload the ROM values.** The second install copies the *scratch*
   (it is the active config by then) onto itself, so edits survive. To get the original scene
   back, write the ROM pointer through the four-cell path of §0(2), or cross a boundary.
3. **`pcfg_transition` in the scratch is forced to 1** by the install. That is deliberate:
   `Parallax_StartTransition` picks smooth-vs-instant from the new config's byte, and a scene
   authoring 0 (the shipped default) would be *staged as a lerp target* instead of installed —
   the panel would then be editing a config that is not driving anything. Do not write 0 back.

### 6.3 Header layout — `Parallax_Scratch_Config` + $00..$1D

Same shape as §2's band-record table. "editable" is about whether a write does something
**coherent**, not whether the engine survives it — every field here is read, none is executed.

| off | field | type | may a panel write it? | range / meaning |
|---|---|---|---|---|
| `$00` | `pcfg_band_count` | u8 | **down only** | how many band records are read. Writing a value **above** the count the install copied reads scratch bytes that were never written. `0` is legal and means "parallax inert" (`Parallax_Update` takes `.no_config`) |
| `$01` | `pcfg_v_factor_bg` | u8 | **yes, with a caveat** | shift in `Vscroll_BG = ((camY - v_center) >> v_factor) + v_offset`. `0..14`; **`15` = LOCK** (plane ignores the camera, pinned at `v_offset`). ⚠ caveat in 6.5 |
| `$02` | `pcfg_layer_mask` | u16 | **yes — the best knob here** | bit *i* = band *i* active. `$0000..$FFFF`. Clearing a bit drops that band and it inherits the band above. Free, instant, reversible |
| `$04` | `pcfg_v_center_y` | u16 | **yes, with a caveat** | the section's "natural" camera Y in the mapping above. ⚠ caveat in 6.5 |
| `$06` | `pcfg_v_offset` | u16 | **yes, with a caveat** | the u16 **image of a SIGNED word** — two's complement, the runtime adds it with `add.w`. ⚠ caveat in 6.5 |
| `$08` | `pcfg_transition` | u8 | **NO** | read at install time and nowhere else; the hook forces `1`. Writing it changes nothing until the next install and breaks that one if set to 0 |
| `$09` | `pcfg_deform_speed_fg` | u8 | **yes** | FG H-deform phase increment per frame. `0..255`; `1` is what a scene with no table emits |
| `$0A` | `pcfg_deform_speed_bg` | u8 | **yes** | same for Plane B |
| `$0B` | `pcfg_anchor_ch` | u8 | **yes, bounded** | patch channel carrying the world-anchored split, `0..RASTER_MAX_PATCH-1` (= `0..3`), or **`$FF` = `PARALLAX_ANCHOR_NONE`, no overlay**. Any other value indexes past the channel array |
| `$0C` | `pcfg_deform_table_fg` | u32 (ROM ptr) | **0 or a real table only** | `0` = no FG H-deform. A non-table address is read as 256 signed bytes — noise, not a fault, but not an effect either |
| `$10` | `pcfg_deform_table_bg` | u32 (ROM ptr) | **0 or a real table only** | as above, Plane B |
| `$14` | `pcfg_v_deform_table_bg` | u32 (ROM ptr) | **0 or a real table only** | `0` = whole-plane V-scroll; non-zero = per-column. **This one also drives VDP reg $0B bit 2**, and `Parallax_Update` re-asserts it every frame from this field, so toggling it is coherent — the register and the buffers move together |
| `$18` | `pcfg_v_deform_speed_bg` | u8 | **yes, two modes** | bit 7 clear: timer speed `0..$7F` (`0` = static column shape). bit 7 set (`PCFG_VDSP_SCREEN_ANCHOR`): screen-anchored, lean gain in bits 3-0 (`PCFG_VDSP_GAIN_MASK`) |
| `$19` | `pcfg_v_deform_shift_bg` | u8 | **yes, two fields** | bits 3-0 (`PCFG_VDS_SHIFT_MASK`) = amplitude shift on V-column samples, `0..15`, larger = smaller. bit 7 (`PCFG_VDS_DECLINE_BORROW`, `$80`) = this scene declines the column-19 borrow. Bits 6-4 are structurally free and read as nothing |
| `$1A` | `pcfg_anchor_dsa` | u8 | **yes** | Plane A deform shift below the anchored line. `0..14`; **`15` = no deform on that plane** |
| `$1B` | `pcfg_anchor_dsb` | u8 | **yes** | as above, Plane B |
| `$1C` | `pcfg_v_factor_fg` | u8 | **inert — writing it does NOTHING** | RESERVED. The v1 pipeline always sets `fg_vscroll = camY`; the field has **no runtime reader**. A slider on it would be the silent no-op §0 exists to prevent |
| `$1D` | `pcfg_bob` | u8 | **yes, packed** | **the WHOLE BYTE `0` = no bob** (the sentinel is the byte, not a nibble). Otherwise bits 7-4 = amplitude shift `a`, peak `SINE_AMPLITUDE >> a`, legal `1..8` (`BOB_SHIFT_MIN..BOB_SHIFT_MAX`); bits 3-0 = period shift `p`, one sway = `SINE_CYCLE_ENTRIES << p` ticks, legal `0..8` (`BOB_PERIOD_SHIFT_MAX`). `a = 0` is a 256-px sway and out of range |

### 6.4 Band layout — record *i* at `$1E + 32*i`, for *i* < `pcfg_band_count`

`sizeof(band_record)` is **32** for this game: the 10-byte legacy `band_entry` plus the curve
(10), drift (4) and remap (8) tails. Offsets are **within the record**.

| off | field | type | may a panel write it? | range / meaning |
|---|---|---|---|---|
| `+0` | `band_top_plane` | u16 | **yes, ordered** | first **PLANE LINE** of the band, `0..511`. ⚠ the records must stay in **strictly ascending** top order — the fill reads band *i+1*'s top as band *i*'s end |
| `+2` | `band_factor_a_s1` | u8 | **yes — the main knob** | Plane A scroll shift 1. `0..14`; **`15` = whole-factor zero, "locked"** |
| `+3` | `band_factor_a_s2` | u8 | **yes — the main knob** | Plane A shift 2. `0..14`; **`15` = single-term factor** (use s1 alone) |
| `+4` | `band_factor_b_s1` | u8 | **yes — the main knob** | Plane B shift 1, same sentinels |
| `+5` | `band_factor_b_s2` | u8 | **yes — the main knob** | Plane B shift 2, same sentinels |
| `+6` | `band_factor_ops` | u8 | **yes** | bit 0: Plane A `0 = ADD` / `1 = SUB` the second term. bit 1: Plane B, same. `0..3`; bits 2-7 unread |
| `+7` | `band_deform_shift_a` | u8 | **yes** | Plane A deform amplitude shift. `0..14`; **`15` = no FG deform** |
| `+8` | `band_deform_shift_b` | u8 | **yes** | Plane B, same |
| `+9` | `band_phase_offset` | u8 | **yes** | `0..255`, added to the deform sample index to desync this band |
| `+10` | `bc_to_s1` | u8 | **yes** | curve far-end factor shift 1. `0..14`; **`15` = ramp to locked** |
| `+11` | `bc_to_s2` | u8 | **yes** | curve far-end shift 2. `0..14`; **`15` = single-term** |
| `+12` | `bc_flags` | u8 | **bits 0-1 yes, bit 2 NO** | bit 0 `CURVE_FLAG_OP_BIT` (far-end second term ADD/SUB), bit 1 `CURVE_FLAG_ACTIVE_BIT` (**this is the on switch** — clear it and the band is a flat factor again). bit 2 `CURVE_FLAG_CONT_BIT` is written by the engine's own shadow pass; a value here is overwritten |
| `+13` | `bc_pad` | u8 | **NO** | alignment only, unread |
| `+14` | `bc_step` | i16 | **inert — DERIVED EVERY FRAME** | the ROM image is always 0; the curve hoist recomputes it into the shadow copy each frame. Writing it does nothing |
| `+16` | `bc_rem` | i16 | **inert — DERIVED EVERY FRAME** | as above |
| `+18` | `bc_span` | u16 | **inert — DERIVED EVERY FRAME** | as above |
| `+20` | `bd_rate_1616` | u32 | **yes** | band drift, px/frame in **16.16 signed** (`[pixels:i16][fraction:u16]`, pixels in the high word). `0` = no drift. This is a lovely knob — a band that creeps |
| `+24` | `brm_ladder` | u32 (ROM ptr) | **0 or a real ladder only** | row-remap index table, `(H+1) x H`. **`0` = this band does not remap** — the only safe write |
| `+28` | `brm_plane_y` | u16 | **yes if a ladder is attached** | BG plane line of the surface this layer's art paints |
| `+30` | `brm_hshift` | u8 | **NO** | `H = 1 << brm_hshift`, and `H` is the ladder table's own geometry. Changing it without changing the ladder walks off the table |
| `+31` | `brm_anchor_ch` | u8 | **yes, bounded** | patch channel carrying the FG's truth about the surface, `0..3` |

### 6.5 The one caveat that is not per-field — the vertical mapping does not re-derive

`band_top_plane` is a **PLANE LINE**, and the build computed it from an authored world Y
through the scene's own vertical mapping:

```
band_top_plane = ((world_y - pcfg_v_center_y) >> pcfg_v_factor_bg) + pcfg_v_offset
```

Nothing recomputes that at runtime. So writing `pcfg_v_factor_bg`, `pcfg_v_center_y` or
`pcfg_v_offset` changes where the **camera** puts the plane while every band top stays where
the build put it — the layers slide relative to the art they were registered against. That is
a real knob (it is exactly "how fast does the BG plane climb"), and it is also the one place
where a slider produces a picture whose parts disagree. **Label it, or move the band tops with
it.** `pcfg_v_factor_bg = 15` (lock) is the clean case: the plane ignores the camera, sits at
`v_offset`, and eighteen of the twenty shipped scenes already author it.

The parallel with §2's band-record advice holds, and the answer is **not** the same one:
there, `driver`/`rate_shift` were nudgeable and `step_mask`/`col_shift` were art geometry. Here
the division is **three-way**, which is why it could not be assumed:

* **free knobs** — the factor shifts, the layer mask, the deform speeds and shifts, the phase
  offsets, the drift rate, the bob. Nothing else in the record depends on them.
* **inert fields** — `pcfg_v_factor_fg`, `bc_step`/`bc_rem`/`bc_span`, `bc_pad`,
  `pcfg_transition` after install. A control on any of these is a slider that does nothing,
  which §0 exists to stop shipping.
* **coupled fields** — the three vertical-mapping bytes above (coupled to every band top),
  `band_top_plane` (coupled to its neighbours' order), `brm_hshift` (coupled to the ladder
  table), `pcfg_band_count` upward (coupled to what the install actually copied).

Pointer fields (`pcfg_deform_table_*`, `brm_ladder`) are a fourth class only in the sense that
their one safe written value is `0`.

### 6.6 Shape: DEBUG ONLY, and why

The scratch, the arm cell and `Parallax_InstallScratch`'s body are all inside `if DEBUG == 1`.
A plain `s4.bin` emits **zero bytes** for them and none of the three symbols has an address
there. The reasoning is written out at `Parallax_InstallScratch` in
`engine/level/parallax.emp`; the short form is that no release path can reach it — a shipped
game that wants a runtime-built config builds it in its own RAM and calls
`Parallax_StartTransition`, which is public and in **both** shapes — so a resident scratch
would be 542 bytes of work RAM nothing calls.

**⚠ The `BgAnim_Table_Empty` warning applies here too, and it is now MEASURED for this hook
rather than inherited.** Comparing the release ROM against master: **zero bytes differ
between the header and `EndOfRom` ($BDC92)** — the release image is byte-identical — and the
whole `+20 B` delta is the deb2 symbol appendix, carrying exactly **one** new name:

> **`Parallax_InstallScratch` APPEARS IN THE RELEASE LISTING, with an address, while
> `Parallax_Scratch_Config` and `Parallax_Scratch_Arm` do NOT.** The proc emits no bytes
> there, so its label collapses onto its neighbour's address — but the *name* still ships.

So a panel that decides "the hook is available" by resolving `Parallax_InstallScratch` will
offer nudge controls on a release build and then write into whatever occupies the scratch's
address. **Gate on the SHAPE.** If you must gate on symbols, gate on
`Parallax_Scratch_Config` — the RAM symbol, which is genuinely absent in release — and never
on the proc.

Per-shape cost, measured against a master control built from the same worktree
(`c631c6db`/`a2f204da`/`ff638f53`/`de5fef4b` reproduced exactly):

| shape | bytes | where |
|---|---|---|
| `s4.bin` | **+20** | deb2 appendix only; ROM image byte-identical; `EndOfRom` unmoved |
| `s4.debug.bin` | **+125** | deb2 appendix (7 new names); `EndOfRom` unmoved — the code landed in placer fill |
| `demo.bin` | **+20** | as `s4.bin` |
| `demo.debug.bin` | **+125** | as `s4.debug.bin` |

Debug-shape *code*: `Parallax_InstallScratch` 66 B (sonic4) / 64 B (demo), plus 14 B of arm
poll in `Parallax_Update` in both. RAM: 544 B (542 scratch + arm + pad), DEBUG shapes only.

### 6.7 It has been driven, not just built

`tools/parallax_scratch_probe.py` boots its own headless emulator and runs the whole path.
Its shape matters as much as its result: every run starts from `emulator/reset` and replays
the identical approach, two untouched runs are **required** to be byte-identical before any
poked run is allowed to mean anything, and only then is one byte changed. Measured on
`s4.debug.bin` `f4d9c299`:

* arm → install: `Current_Config` `$FFFFEA26`, `Target_Config` 0, `Transition_Frames` 0, arm
  cleared; the scratch's 158 bytes (4 bands) byte-identical to the ROM config at `$012F08`
  with `pcfg_transition` forced `0 -> 1`.
* determinism rung: two re-approached runs byte-identical over 6 frames — **and the buffer
  moves on its own on 1 of those 5 frame steps**, which is why the control had to be absent
  rather than sampled.
* the subject: band 0's `band_factor_b_s1` at `$FFEA48`, `1 -> 3`. On the very next frame
  **64 BG lines of `Hscroll_Buffer` differ and 0 FG lines do** — the plane the field governs
  and only that plane. Line 0's BG word `$FC1E -> $FF06`.
* `pcfg_layer_mask` `$001F -> $0000` moves the buffer on all six frames too, so the result is
  not one field's peculiarity.

**⚠ TWO THINGS THE PROBE COULD NOT ESTABLISH, stated because a green above would otherwise
be read as covering them.**

1. **The hook is LINKED INTO `demo.debug` AND UNREACHABLE THERE.** The symbols resolve
   (`Parallax_Scratch_Config` `$FFE6DC`, same 542-byte span) and the proc is emitted, but
   `Parallax_Update` **has no caller in `games/demo`** — grep-verified, its only callers are
   in `games/sonic4/test/ojz_scroll_test.emp` — so the arm poll never runs. Measured:
   `--expect-refusal` on `demo.debug.bin` found the arm still set after a frame, the
   selector still 0 and all 542 scratch bytes untouched. **Nothing ran.** That is a fact
   about reachability, not about the refusal, and the probe reports it as `UNREACHABLE, NOT
   PASS` (exit 2) rather than as either verdict.
2. **The refusal arm is therefore DEFENSIVE AND UNEXERCISED.** Neither shipped fixture can
   produce its trigger: sonic4 always has an active config, and demo never polls. `carry
   SET` on a null config is argued from the source, not measured. A panel should not build a
   flow that depends on distinguishing "refused" from "installed" — read
   `Parallax_Current_Config` back, which is measured and definitive.
