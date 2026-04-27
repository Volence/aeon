---
name: Ristar Engine Techniques (Research)
status: RESEARCH (no full disasm — reconstructed from prototype + community)
date: 2026-04-27 (updated 2026-04-27 — engine lineage corrected)
---

# Ristar (Sega, 1994) — Engine Techniques Research

Ristar is a 1994 platformer by an internal Sega team that overlapped with the
Sonic group (per the Wikipedia/Ristar article, EGM 1994 quoted Sega marketing
saying it was *not* the Sonic programming team, though many staff later went
to Nights / Sonic Team). We have the production ROM only — no public
disassembly of S.C.E. quality exists. Findings below are reconstructed from:

- Hidden Palace prototype catalog
  — https://hiddenpalace.org/Category:Ristar_prototypes
  Builds: Jul 1, Jul 18, Aug 12, Aug 26, Sep 9, Oct 19, Oct 24, Nov 1, Nov 2.
  Note: there is NO Aug 17 build, and none of the listed builds publish
  symbol/source files. Earlier note in this doc was wrong on both counts.
- TCRF Genesis page — https://tcrf.net/Ristar_(Genesis) (and Proto: pages,
  which our research host could not reach but are referenced by Hidden Palace).
- Existing partial disassemblies — three on GitHub:
  https://github.com/sonicretro/ristar (IDA 5.5 .idb, mostly SMPS + a few
  decompression/palette routines; readme by andlabs, 2010, explicitly
  "early disassembly").
  https://github.com/RocketRobz/ristar-disasm (mirror of the above).
  https://github.com/Not-So-Filter/ristar-disasm ("research disassembly",
  unreachable from our IP at the time of this research).
  None of these expose object code or RAM map.
- SonLVL issue #162 (Ristar level format research)
  — https://github.com/sonicretro/SonLVL/issues/162
- Luke Zapart "Feel" — Ristar level editor, 2006
  — https://lukezapart.com/old-projects
- StarDec (drx, ~2006) — http://drx.pl/stuff/StarDec.rar
- SpritesMind general Genesis dev forum (no Ristar-specific deep threads
  located).

**Treat almost everything below tagged INFERRED.** The community has cracked
the compression and level format, but nobody has published an object/RAM map.
When in doubt, run the ROM in Exodus + MCP and confirm directly.

We have produced our own v1 disassembly at
`/home/volence/sonic_hacks/The Adventures of Batman and Robin/ristar_disasm/`
— linear capstone disassembly with entropy-based data extraction, 460k
instructions, 97 data files, 45k auto-generated labels. See its
`ANALYSIS.md` for the disasm-grounded version of this note.

## Engine lineage — CORRECTION

**Prior note in this doc claimed "Sonic 3K-family DNA throughout." That is
wrong.** Multiple sources converge on Sonic 1, not Sonic 3K, as the engine
basis:

- Wikipedia (Ristar) cites the EGM 1994 source describing Ristar as built
  on top of Sonic 1's engine.
- SonLVL issue #162: "Ristar's level format is very similar to Sonic 1,
  although plenty of things are compressed into a unique 'Star' format.
  Bit flags in the chunk blocks are assigned differently, such as flipping."
- Sonic 1's object slot ("Sprite Status Table") is **$40 bytes** — Ristar
  inherits this size and the Sonic 1 field layout, NOT the Sonic 3K
  $4A-byte extended slot.

So the correct framing is: **Sonic 1 engine fork + selectively-borrowed
Sonic 3K-era refinements + Ristar-specific systems**. Compression is a
mix-and-match: Nemesis (same as Sonic) + drx-named "Star" (Ristar-specific,
used for level/bulk data where Sonic uses Kosinski/Enigma). SMPS sound
driver is in the same family as Sonic but with Ristar-specific PCM mixing
code (visible in the published `smps-z80-ristar-mixing.asm`).

Distinguishing additions over Sonic 1:

- Much heavier per-stage cinematic scripting (Sonic acts don't reprogram
  VDP registers per-act the way Ristar does). [INFERRED — observed via
  emulation, not confirmed from source]
- Per-object animation system carries inline event tags (SFX, hitbox swap,
  callback) — Sonic 1's animation tables are just frame+duration.
  [INFERRED — observed via gameplay timing, not confirmed from source]
- Grab arm — a generic chained-sprite rope primitive reused for boss
  appendages. [INFERRED — visible in sprite ripping resources but not
  confirmed in code]

## Five distinctive engineering decisions

### 1. Event-tagged animation frames

Each animation frame carries inline event bytes alongside the frame index and
duration:

- Play SFX X
- Switch hitbox to Y
- Spawn dust/effect Z
- Trigger script callback (jump to a per-object hook)

This is why Ristar's grab/release/swing/squash anims look authored rather
than mechanical: the animation system *is* the cinematic engine. No parallel
state machines polling for "frame 5 of throw anim" to trigger a SFX — the
SFX is glued to the frame.

**For our engine:** see `docs/research/animation-system.md`. Bake event tags
into the frame stream from day one — adding them later means a format break.

### 2. Chained-sprite "rope" primitive

The grab arm is *not* a stretched bitmap or a raster effect. It's:

- A "shoulder anchor" object at Ristar's body
- A "tip" object that travels outward
- N "segment" objects sized 8x8 or 16x16, evenly spaced between anchor and
  tip, count computed from current distance

All three rendered as ordinary hardware sprites. Each frame the parent
recomputes the segment count and writes positions into a fixed pool of
child slots.

Same primitive is reused for the Round 4 boss elastic neck, and likely
several other articulated bosses.

**For our engine:** This generalizes to neck/tongue/whip/grappling-hook /
elastic-rope mechanics. A `RopeChain` object class with `(anchor, tip,
segment_art_tile, max_segments)` would pay for itself the first time we
need any extending appendage. Pairs with our existing children-particles
framework (`docs/research/children-particles.md`).

### 3. Per-stage HInt handler dispatch

Ristar does not have a single shared raster routine. Each act (or sometimes
each "scene" within an act) registers its own HInt handler, and the VBlank
exit code points the IRQ vector at it on stage load.

Examples:

- Planet Freon intro: HInt does cell-scroll + per-line palette fade for
  the cloud descent.
- Round 1 boss "pull-in": HInt rewrites HSCROLL with a scaled-row offset
  table, sampling the same row repeatedly to fake zoom-toward-camera.
- Underwater acts: HInt walks an `HSCROLL_base[line] = base + sin(line+t)`
  table for water shimmer. Sin LUT is recomputed once per frame, not
  per-line.

**For our engine:** This matches our research direction in
`docs/research/per-section-background.md`. Make the section streamer
register a section-specific HInt routine pointer at section entry, rather
than one global "raster effects" handler that branches on stage ID. Cleaner
and pays no per-frame branch cost.

### 4. Cell-scroll (per-8-pixel HScroll) as the workhorse

Most Ristar parallax bands aren't full per-line — they're per-tile-row
HScroll table writes. ~28 entries instead of 224, ~12% the DMA cost,
~80% the visual quality. Per-line is reserved for the dramatic moments
(boss zoom, water shimmer).

**For our engine:** Already aligned with our §4.6 parallax plan
(`HSCROLL_MODE_CELL` is the default). Ristar is direct evidence that
"cell mode by default, per-line for hero shots" is the right tradeoff.

### 5. Raycast-against-objects for the grab

The grab is *not* a tile-collision query. It's a short directional sweep
(8 directions) over the active object slots, checking distance from
Ristar's shoulder against each candidate's hitbox. Cheap — ~30 cycles per
candidate object, and the active slot count is small.

**For our engine:** Worth a generic helper in
`docs/research/collision-system.md`: `RaycastObjects(origin, dir, range,
mask) -> first_hit`. Useful for grabs, throws, lock-on aiming, line-of-sight
enemy AI, harpoon weapons. Avoids overloading the tile collision system
for what is fundamentally an object-vs-object query.

## Sound driver — concrete details (CONFIRMED, mostly)

Source: `sonicretro/smps-rips` README; `sonicretro/ristar/smps-z80-ristar-mixing.asm`
(github.com/sonicretro/ristar).

- **Variant: SMPS 68k Type 2.** Sequencer runs on 68k, music data in 68k ROM.
  Same family as Sonic 2 — NOT Sonic 3K's Z80-resident driver. So the Sonic 1
  engine lineage extends to audio: Ristar adopted Sonic 2's SMPS evolution,
  not Sonic 3K's.
- **Z80 side is a custom dual-PCM mixer**, not the music driver. Two
  `sample_entry` slots (10 bytes each: `playing, id, bank, offset, length,
  length_high_byte, length_low_word`). 68k writes the slot, sets a single
  mailbox byte (`driver_input` at Z80 RAM `$F0B1`), Z80 picks it up.
- **Mixing is `add a, l` with no clipping** — sum two PCM streams per tick,
  write to YM2612 reg `$2A`. Three loop variants by active slot count
  (`PCMplayloop_2samples`, `sample0only`, `nosample0loop`). Self-modifying
  bank-switch (`zMakeBankSwitch0/1`) patches 8 instruction operands per
  channel for the Z80's 32 KB bank window.
- **No timer; pitch via inner-loop `pitchloop` 3-cycle delay.** Output rate
  is the natural inner-loop period.
- **5 built-in PCM samples in driver ROM** (`PCM0`–`PCM4`, sizes 96..2411
  bytes); 68k can also stream arbitrary PCM by writing offset/length/bank
  directly into the slot.
- **No exposed beat / channel-state poll surface in the published Z80 code.**
  Audio-driven cutscene sync would have to be added on the 68k side reading
  the SMPS sequencer's internal state. Notable for our backlog item #18
  (beat-driven visuals).

**For our engine:** Flamedriver supersedes all of this. But two ideas survive:
- The 10-byte slot + single mailbox interface is a clean shape, regardless
  of driver.
- **Dual-PCM via runtime `add` mixing is cheap enough to be the default.**
  Sega shipped this in 1994 with no clipping logic and no audible artifacts
  that anyone bothered to fix in 6+ months of dev. We can stop treating
  multi-channel DAC as an "advanced" feature.

## Star compression (CONFIRMED — drx's StarDec source)

Source: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/stardec.cpp`
(reverse-engineered decompressor by drx, ~2006).

Algorithmic shape — **a Kosinski cousin**, byte-oriented control stream:

| Token   | Bits read | Meaning                                                          |
| ------- | --------- | ---------------------------------------------------------------- |
| `1`     | 1 + 8     | Literal byte                                                     |
| `01`    | 2 + 16    | Long ref: 13-bit signed offset, 3-bit count (2..8) or extended count byte (1..256). Offset=0 word ⇒ end-of-stream |
| `00`    | 4 + 8     | Short ref: 8-bit signed offset (−256..−1), 2-bit count (2..5)    |

Compare to Kosinski:
- Kosinski uses a **16-bit LE descriptor word** (16 control bits before refill).
- Star uses a **single descriptor byte** (8 control bits before refill).
- Token semantics are otherwise nearly identical: same offset width, same
  short/long split, same end-of-stream sentinel pattern.

**Algorithmic novelty: zero.** Star is a Kosinski variant with a different
descriptor refill cadence and minor count encoding tweaks. Anything S4LZ
already does that's better than Kosinski (byte-aligned tokens, word copies,
nibble dispatch) is also better than Star.

**For our engine:** Nothing to adopt. Confirms the theme — Sega's 1994 internal
formats were all small variations on classic LZ77; the modern community
work (LZ4W, ZX0, S4LZ) materially outperforms them on 68000.

## What we should NOT borrow

- Compression (Nemesis + Star) — Star is just Kosinski with a different
  descriptor; S4LZ already beats both.
- SMPS 68k Type 2 — Flamedriver replaces it (but see "10-byte slot + mailbox"
  shape note above).
- Sonic-style 16x16 + sensor collision — already in our plan, but Ristar
  doesn't push it any further than Sonic 1 (and Sonic 1 has fewer sensors
  than Sonic 2/3K, so this is regression, not improvement).
- HUD-as-sprites pattern (INFERRED from TCRF prerelease notes) — we want to
  evaluate the Window plane separately.

## Open questions — what would need an Exodus session to confirm

The community-published material is now *exhausted* for object/collision/HUD
internals. No public disassembly covers the 68k code beyond a few
decompression and palette routines. To confirm any of the following, run the
production ROM in Exodus + MCP and trace:

- **Object slot stride and active count** — set memwatch on `$FFFFB000`–
  `$FFFFE000` at level init, find the memset / clear loop. Stride byte and
  RAM range gives slot size and slot count.
- **Sonic-1 vs Sonic-2 sensor count** — write-watchpoint on player x_pos
  during a slope walk, count distinct sensor reads against collision tiles.
- **Grab raycast loop** — breakpoint on a grab-button press, single-step the
  routine that fires after, see whether it iterates object slots (raycast),
  reads collision tiles (probe), or fattens the player hitbox (extension).
- **Animation event-tag byte layout** — find the animation update routine by
  watching the anim_frame field, decode the table format from the data it
  reads.
- **Rope chain update cadence** — set a write-watchpoint on the segment
  child slots' position fields during a grab; per-frame writes vs.
  state-transition-only writes will be obvious.
- **HUD plane** — toggle Plane A / Window in Exodus layer view to confirm
  whether HUD is sprite-only, Plane A overlay, or Window plane.
- **Round 6 mirror room** — break on entry, snapshot VDP regs $02/$04
  (plane base) before and during the effect.

Estimated cost: 1–2 hours of focused MCP-driven tracing. **Worth doing only
if we decide to actually adopt one of the above as part of the engine
plan** — until then, the research note's `INFERRED` tags stand.

## Worth borrowing — short list

| Item                              | Where it lands                          | Priority |
| --------------------------------- | --------------------------------------- | -------- |
| Event-tagged animation frames     | `animation-system.md`                   | High — format break if added late |
| Chained-sprite rope primitive     | `sprite-rendering-advanced.md`          | Medium — when we need extending appendage |
| Per-section HInt handler pointer  | `per-section-background.md`             | High — already aligned with plan |
| Raycast-against-objects helper    | `collision-system.md`                   | Medium — gameplay-feature dependent |
| Cell-scroll as default            | §4.6 parallax plan                      | DONE — already adopted |
