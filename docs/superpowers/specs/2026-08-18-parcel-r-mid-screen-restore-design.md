# DESIGN DRAFT — Parcel R: mid-screen restore

**Date:** 2026-08-18
**Status:** DRAFT, pre-lens-sweep. Owner signed off on approach **(A)** (a restore that streams from
the live base) on the strength of `2026-08-18-parcel-r-recommendation.md`; this draft settles the
form, not the direction.
**Scope:** make a raster effect expressible as a BAND — on at line M, off at line N — instead of
on-at-M-and-runs-to-the-bottom.

---

## 1. The gap

A raster effect can be turned ON at any line. There is **no mechanism to turn one OFF at a lower
line**, so a tint confined to lines 100-140 is inexpressible: everything a program does persists to
frame bottom and is undone only at frame top, by two separate frame-top mechanisms —
`Flush_VDP_Shadow` re-blitting all 19 shadowed registers, and `Palette_Dirty` causing
`Enqueue_Dirty_Buffers` to re-ship the program's CRAM lines from `Palette_Buffer`.

Neither has a mid-frame form, and that was deliberate: the blanket frame-top restore is what lets two
independently-authored effects touch the same register and simply compose, and it replaced an older
per-program `init[]` header that made composition a negotiation between preset authors.

## 2. What the corpus does, and why it is silent here

Verified this session against the disassemblies:

- **No Sonic-family reference restores mid-screen.** S3K's `HInt3` parks the counter (`$8AFF`,
  `sonic3k.asm:1015`) as its FIRST act and never re-arms — one fire per frame, effect runs to the
  bottom. S2, S.C.E. and Ristar's water are the same shape. The reason is content, not technique:
  water reaches the bottom of the screen by nature, so the case never arose.
- **The multi-event shape is Treasure's, and is already ruled shipped practice.** Gunstar runs a
  mid-frame state machine re-arming reg `$0A` inside the handler (`$8A80` at ROM `$001744`,
  `$8A1F`/`$8A8F` at `$00182C`/`$00183E`); Alien Soldier parks after its single event
  (survey ruling 4a, `docs/research/2026-08-12-raster-hint-survey.md`).

So a band is two ordinary fires, and Aeon's sparse tier already schedules N fires per frame. **The
novel part is not the second fire. It is what the second fire writes.**

## 3. The finding that collapsed the decision

R was stopped on: *"it needs a staging buffer holding the pre-effect values, maintained by somebody."*

**`Palette_Buffer` already is that buffer** (`engine/ram.emp:225`, 128 bytes = 4 lines x 32). The
composition pipeline `base -> cycling -> cross-fade -> global operators -> variants`
(`engine/effects/palette.emp:31`) writes the LIVE COMPOSED BASE there, with the variant going to the
separate `Pal_Variant_Stage` that `OP_PAL_REGION` streams from (`palette.emp:67-68`, `:104`).

Three consequences:
1. **No new RAM.** The pre-effect image is exactly what is in there.
2. **No new owner.** `Palette_Compose` is already "one owner, one deterministic order, once per
   frame", and it is kept truthful across cycling, cross-fade and variants **because the frame-top
   restore already depends on it** — `Enqueue_Dirty_Buffers` re-ships from it every frame.
3. **No new mid-frame writer.** `Palette_Compose` runs from GameLoop, not VBlank
   (`engine/system/game_loop.emp:49`); `Enqueue_Dirty_Buffers` reads it in VBlank. During active
   display the handler only READS it — the identical relationship `OP_PAL_REGION` already has with
   `Pal_Variant_Stage`, so the P-b-in-spirit concern about a new mid-frame writer does not arise.

## 4. The design

### 4.1 A SOURCE field on the existing op, not a new opcode

`OP_PAL_REGION` and a restore differ in exactly one way: the RAM base they stream from. Everything
else — the command longword, the `EFX_BLANK_DELAY` spin, the count, the `RASTER_CRAM_MAX` ceiling,
the handler's register juggling — is identical.

**Proposed: the op's existing offset word gains a source selector in its high bits**, so the wire
body is unchanged in LENGTH and the handler gains one test rather than one opcode:

```
OP_PAL_REGION
  dc.l <CRAM write command>
  dc.w count-1
  dc.w src_off        bit 15: 0 = Pal_Variant_Stage (today), 1 = Palette_Buffer
                      bits 0-14: the byte offset, exactly as today
```

`Pal_Variant_Stage` is `PAL_MAX_VARIANTS * 128` = 256 bytes and `Palette_Buffer` is 128, so a real
offset never exceeds 255 and bit 15 is free by a wide margin. `pal_stage_off()` already `ensure`s
slot/line/entry bounds; a sibling `pal_base_off(line, entry)` = `line * 32 + entry * 2` does the same
for the base, and both assert the result cannot collide with the selector bit.

**Why not a separate `OP_PAL_RESTORE` opcode:** the handler's dispatch is a compare chain, and its
own comment records that `OP_SET_REG` — the chain's fall-through — is the most expensive op to
DISPATCH. Adding a fifth opcode lengthens that chain for every op in every fire, to express a
difference of one `lea`. A source bit costs one `btst`/`bne` inside the region path only.

**This is the draft's most attackable choice** and the lens sweep should go at it: it trades wire
clarity (an opcode you can read in a hex dump) for dispatch cost, and it puts a flag in a field that
is currently a pure offset.

### 4.2 Authoring

```emp
// pal_band — an effect confined to lines [top, bottom). Two fires: the region at `top`,
// the restore at `bottom`.
pub comptime fn pal_band(top: int, bottom: int, addr: int, slot: int,
                         pal_line: int, entry: int, count: int) -> array
```

It returns a FIRE LIST (two fires), so it composes with `compose()` like every other preset, and both
fires go through `fire()` and inherit every per-fire ceiling. The restore fire's `count` and `entry`
are the region's — restoring exactly what was written, which is a property the constructor can
guarantee rather than an author obligation.

### 4.3 What bounds a band's height

Nothing new: `check_density`. A restore fire is an ordinary fire — a 3-word CRAM fire is measured at
**526 cycles against a 488-cycle line** — so a band shorter than the density guard allows is REFUSED
at build time, with the guard's existing message. That is correct behaviour and must be documented at
the constructor, so an author meets it as a rule rather than as a surprise.

### 4.4 The register case — IN, and for the same reason

"Shadow/Highlight off at line 140" has the identical shape: `VDP_Shadow_Table` is to registers what
`Palette_Buffer` is to palette — the frame-top restore's own source, one owner, read-only during
active display. A restore of a register is `OP_SET_REG` with a value read from the shadow rather than
baked, so it needs the same one-bit treatment: a `set_reg` variant whose word is fetched from
`VDP_Shadow_Table + <reg offset>` instead of carried inline.

Taking it now is cheap and keeps the two halves symmetric. Taking it later means a second parcel that
re-opens the same op formats. **Flagged for the sweep**: it is the one place this draft grows beyond
the minimum, and the argument for it is symmetry rather than a content demand.

## 5. Correctness arguments

1. **A restore restores to what the rest of the screen shows.** Above the band, CRAM holds the base
   shipped at frame top from `Palette_Buffer`. The restore streams from that same buffer, so the
   pixels below the band are byte-identical to the pixels above it, by construction — including
   mid-fade and mid-cycle, because `Palette_Buffer` holds the live composed base at both moments.
2. **Composition survives.** Two bands over the same palette line compose exactly as two regions do:
   the last write on a line wins, and every mid-frame write is still transient because the frame-top
   re-ship is unchanged. R adds no state that a second effect must know about.
3. **No new ordering hazard.** The handler gains a read of a buffer written once per frame from the
   main loop, which is what it already does for `Pal_Variant_Stage`.
4. **The band is closed on every path.** If the restore fire is suppressed (its record dropped by
   `Raster_BuildSchedule` because a patchable band moved past its reach) the effect would run to the
   frame bottom — the pre-R behaviour, not a corruption. Worth stating because it is the interaction
   between R and the local-removal parcel, and it means a patchable BAND needs both fires to share a
   fate. **Open: should `patchable` refuse to mark one fire of a band?**

## 6. Gates

R is the first parcel that starts with its gate already built. `aeon/tools/scenes/` +
`aeon/tools/effects_scene_assert.py` assert a raster program's shape from a deterministic harness
capture, so:

- **Comptime:** a hand twin for a two-fire band program; `first_mismatch` over the whole image; the
  source-bit assertion (a base-sourced op's offset word has bit 15 set, a staging-sourced one does
  not) — checked against the emitted image, not just the constructor.
- **Runtime, through the scene harness:** a band scene whose live buffer carries TWO records with the
  expected arm words, the second carrying the restore's source bit. Plus a poison control.
- **The composite:** the gate must assert the restore fire's OP WORDS, not merely that a second
  record exists. A record on the right line writing the wrong source is the failure this parcel can
  actually produce.

## 7. Open questions for the sweep

1. Source bit on the offset word, or a separate opcode? (§4.1 — the most attackable choice.)
2. Register restore in scope, or booked? (§4.4.)
3. Should `patchable` refuse to mark one fire of a two-fire band? (§5.4.)
4. Is `pal_band`'s guarantee that the restore matches the region's entry/count worth the constructor
   coupling, or should they be independent arguments?
