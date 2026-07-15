# TheBlad768 + Spinball survey — deform engine, S3K Epilogue, SpinTool — 2026-07-14

Quick survey of external sources, filtered for what Aeon doesn't already have.
Three ideas worth keeping; everything else was confirmation of techniques already banked
in ENGINE_ARCHITECTURE.md §7 or stock-S3K machinery we deliberately replaced.

Sources:
- S.C.E. commit `c8ad081` (Draw Level.asm rework) — github.com/TheBlad768/Sonic-Clean-Engine-S.C.E.-
- S.C.E. tutorial `eng/how_to/new_deform_engine.md` (wraps MarkeyJester's SSRG deform post)
- Sonic 3 & Knuckles: Epilogue public source — github.com/TheBlad768/Sonic-3-Knuckles-Epilogue-Public-Source
  (archived read-only 2026-06-14; full-repo sweep by subagent, 2026-07-14)
- SpinTool (Sonic Spinball reverse-engineering/modding tool) — github.com/AlpasNet/SpinTool
  (fork = current lineage; merged upstream into Eggplant891/SonicSpintool via PR #5, 2026-07-05;
  full-source sweep by subagent, 2026-07-14)

---

## KEEP #1 — Computed-jump-table HScroll fill (S.C.E. "updated DeformScroll")

**What:** MarkeyJester's `DeformScroll` fills the HScroll buffer with a per-scanline
`move.l d1,(a2)+ / dbf` loop. S.C.E.'s updated (unreleased) version replaces the inner
loop with a computed jump into an unrolled run of `move.l` writes — Duff's-device style:
`jmp table(pc,d0.w)` where d0 derives from the span's scanline count, landing mid-run so
exactly N writes execute with zero loop overhead.

**Why it matters to us:** Our per-line HScroll pipeline is mandatory (per-cell tears at
band boundaries — closed in DEFERRED_WORK, root-caused on hardware 2026-06-23), so
`Parallax_Update` eats a 224-line fill every frame. Profiler under sustained MAX diagonal:
`Parallax_Update` ~7.4% of frame. The `dbf` costs ~10 cycles/line ≈ ~2,200 cycles/frame of
pure loop overhead across the constant-speed spans of each band. An unrolled
computed-entry fill converts that to near zero for band interiors.

**Caveats:**
- Our fill isn't a pure constant-`move.l` loop everywhere — the deform-table path adds a
  per-line table sample. The unroll applies cleanly to the zero-deform / constant-span
  case (OJZ default ships `DeformTable_Zero`); the deform-active path needs either a
  second unrolled body (sample+write pairs) or to keep the loop.
- Unroll body size: 224 × `move.l d1,(a2)+` = 448 bytes per body — cheap in ROM.
- Entry-offset math must account for the 2-byte instruction size (`d0 = (224-N)*2`).

**Where it lands:** `Parallax_Update` fill phase, engine/level/parallax.asm. Perf item —
see DEFERRED_WORK "From §4" entry. Measure before/after with the lag counter, not the
profiler (per streaming-feasibility lesson).

---

## KEEP #2 — Multi-phase boss choreography via chained routine pointers (Epilogue)

**What:** Epilogue's bosses (`Objects/Boss/Boss.asm`, `Objects/Boss Ball/Boss.asm`) run
multi-stage fights inside a single object:

- HP in `collision_property`; crossing a threshold (8→4 HP) swaps the active
  **attack-pattern table** — first half of the fight draws from one set of 4 patterns,
  second half from a different 4.
- Each attack pattern is a coroutine-style subroutine; the *next* routine's address is
  stored in a free object-RAM field ($34) and chained at runtime — mid-attack transitions
  are a pointer swap, no routine-counter ladder, no separate object IDs per phase.
- Patterns are position-gated state machines: wait until the boss reaches a
  camera-relative offset, then spawn child attack objects (8+ projectile types with
  per-type position/velocity tables).
- Damage feedback: palette hit-flash tables keyed off remaining HP — descending reds
  ($E,$866,$644,$422,0) alternating ascending whites ($888..$EEE), 6 cycles per hit,
  written to palette line 4 each frame.
- Defeat sequence: invulnerability lock → child cleanup → fall + screen shake →
  explosions → cutscene handoff.

**Why it matters to us:** This is Gunstar/Alien Soldier choreography adapted to a
Sonic-style object system, and it maps directly onto objects-v2: chained next-routine
pointer in a free SST field, HP-threshold pattern-table swap, children system for attack
spawns, palette-line-2 flash via the per-line dirty DMA. Cite this when the boss-system
design phase opens — it's the cleanest worked example of "one object, N phases" we've
seen in a shipped hack.

**Verdict on novelty:** the chaining + phase-table swap is their own engineering, not
lifted community code.

---

## KEEP #3 — Script-VM cutscene/animation architecture (Sonic Spinball, 1993)

**What:** Spinball (written largely in C — near-unique for a Genesis game) drives its
animation and cutscenes through small bytecode interpreters rather than hardcoded object
code:

- **Animation command stream** (`animation_sequence.cpp` in SpinTool documents the
  format): frame-display commands with timing, relative jumps / goto-previous-frame for
  loops, ADD_X/Y + SET_X/Y offset commands (sprites reposition mid-animation without new
  mapping frames), and CREATE_ANIM_OBJ_INSTANCE / composite-object spawn commands.
  Extended opcodes via an escape pattern (`(code & 0x1F) == 0x1F` → read second byte).
  End marker $8000, frame-skip marker $3FFF.
- **Cutscene script VM** (`tails_plane_decoder.cpp` — the Tails-plane sequence): ~18
  opcodes including direct object-slot placement, object-table application, subroutine
  call (depth-limited to 32), repeat-block (loop N times), and frame capture. Object
  positions in Sint16 fixed-point (1/16 px).

**Why it matters to us:** When a cutscene/scripted-sequence system opens (title
sequences, act intros/outros, boss defeat handoffs), "tiny script VM with subroutines +
repeat + object-spawn opcodes" is a better shape than S3K-style hardcoded cutscene
objects: sequences become data, tooling can emit them, and the interpreter is small.
This is the 1993 existence proof that it fits comfortably on the 68000. Pairs naturally
with the Epilogue chained-routine boss pattern (KEEP #2) — both replace routine-counter
ladders with data-driven control flow.

**Bonus historical note:** Spinball's bonus-stage sprite mapping is a 6-byte header
(**piece count** + X/Y origin) followed by **8-byte pieces in {Y, size, tile, X} VDP
order** — a 1993 precedent for our §7.8 count-header + VDP-order format, predating the
2024 Plutié reorder post by three decades.

---

## Confirmations / rejections (no action)

- **S.C.E. `VInt_DrawLevel` rework (c8ad081):** dedicated a5=control-port register and
  dbf count-minus-one convention — both idioms our plane_buffer.asm already uses.
  Their new `VInt_VRAMRead` (VRAM→RAM readback) is a capability we deliberately don't
  need: our 2D tile cache in RAM is authoritative, we never read the nametable back.
  Their secondary plane buffer ≈ our BG append routines into one buffer. Their drain has
  no mid-fill race guard (we fixed that class of bug in b96c861).
- **MarkeyJester deform list** (`{speed-ptr, scanline-count}` pairs, $0000 terminator,
  Y-compensated band boundaries): structural ancestor of our parallax_config/band
  system. Ours generalizes it — plane-space band tops with wrap rotation (Step 4a),
  per-section configs with lerp/snap transitions, additive deform tables, per-band
  Plane A factors. His "make the BG horizontally repetitive to skip column redraw"
  constraint is one we rejected: BG column streaming measured ~2% of frame.
  Cute idiom noted: `movea.w` sign-extended word pointers for RAM addresses.
- **Epilogue MSU-MD Mode 1 CD audio** (`Sound/MSU/MSU.asm`, `MCDSend` macro,
  `$A12010+` command ports, FM/PSG fallback): most novel thing in that repo, but low
  relevance — custom Z80 driver is a core Aeon feature, no real hardware to attach a
  Sega CD to, oracle doesn't model one. Filed as "fun someday" only.
- **Epilogue Sonium HInt VSRAM wave** (per-scanline VSRAM bump, multiply-shift-subtract
  interpolation): already covered more generally by §7 raster command table + Batman
  mid-frame VSRAM manipulation.
- **Epilogue SRAM system** (rotate-left word checksum, 'BOSS' magic, corruption-recovery
  screen): standard practice; our SRAM design (substrate-gaps item 2) already scopes
  slot format + checksums + wear pattern. One borrowable detail: a user-facing
  corruption screen with reinit, rather than silent reset.
- **Epilogue Time Attack / progressive text reveal:** UI polish, not engine tech.
- **Spinball LZW compression ("Compressed2"):** the game ships real LZW — variable
  9–11-bit codes, 2048-entry dictionary, reset token $100 / end token $101, $FFFF block
  markers. Genuinely novel for a Genesis cart (LZW's dictionary RAM cost is why everyone
  else used LZSS-family), but no action: LZW loses to ZX0 on both ratio and RAM.
  IMPORTANT caveat when reading SpinTool: the multi-strategy dictionary-reset optimizer
  (`compressed2_optimizer.cpp`) is the modern TOOL's recompressor for PNG reimport, NOT
  1993 game tech — don't cite it as Spinball engineering. Same for the tool's "virtual
  VRAM" written-byte tracking (import safety, tool-side).
- **Spinball per-sector collision-object culling + level-instanced flippers:**
  broad-phase object ID lists per map sector; flipper data/animations/collision defined
  per table. Sound 1993 engineering; our camera-driven entity window + data-driven
  archetypes already cover it.
- **Spinball ball/playfield collision — NOT decoded:** the pinball-novel part is
  opaque. `collision_tile.cpp` is a stub; `SplineCullingTable` and
  `flipper_collision_unknown` are named-but-undecoded pointers. The spline table hints
  playfield collision is curve-based, not tile-heightmap — if ever worth chasing, it
  needs a ROM + disassembly session on the collision code, not more tool-reading.
- **Spinball tile layout** (4x4 tile brushes → brush instances, 11-bit tile / 10-bit
  brush indices): conventional Genesis tilemap hierarchy, nothing to take.
