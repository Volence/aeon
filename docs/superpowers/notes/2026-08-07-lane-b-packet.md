# Lane B packet — the guard sweep, ranked

Branch: aeon `lane-b` (1 commit), branched from master `5ecc51f`. **No sigil
change.** Not merged, not pushed.

## Verification of the brief's claims — one correction

Every census item was re-cited against the tree before acting.

* **`s4lz.emp:228` — CONFIRMED with a refinement.** The brief says "THE FILE HAS
  ZERO `ensure` STATEMENTS (I counted)". `grep -c ensure` returns **1**, and that
  one occurrence is **the word inside the lying comment itself**. So the claim
  holds and is if anything sharper than stated: the file's only mention of a
  guard is the sentence asserting one exists.
* **`VDP_Shadow_len` — CONFIRMED exactly**, including that `vdp_init.emp:18`'s
  `ensure` is a `<= 32` ceiling and `ram.emp:113` is derived.
* **`dplc.emp:65,69`, `plane_buffer.emp:76,94,231,244,383`, `section.emp:277`,
  `sprites.emp:151,236`, `constants.emp:440-441`, `act_descriptor.emp:74` —
  all CONFIRMED** at the cited lines.
* **`sound_debug.emp:58` — STALE PATH.** The file is at
  `engine/debug/sound_debug.emp`, not under `games/sonic4/debug/`. Its two
  `ensure`s are at `:56` and `:58`. Item still real; the citation had drifted.

## The ranking — "could this plausibly change", and why

| # | site | can the number change? | action |
|---|---|---|---|
| 1 | `VDP_Shadow_len` vs `sizeof(VdpShadow)` | **Yes in practice.** The struct mirrors VDP regs $00-$12, but the failure is a SILENT dropped register with no crash and no golden byte. | **equality `ensure` added** |
| 2 | `BLOCK_TILE_SIZE` / `BLOCK_TILE_SHIFT` | **Yes.** Block geometry is an engine design parameter, and the roadmap names a Tile/Block/Chunk/Section rework. ~10 consumers read the SHIFT. | **`ensure` added** |
| 3 | `act_descriptor.emp:74` `MAX_ACT_SECTIONS * 66` | **Yes** — `sizeof(Sec)` moves whenever a section field is added, and the guard would then bound the wrong product. | **derived**: `* sizeof(Sec)` |
| 4 | `s4lz.emp:228` `lsr.w #5` for TILE_SIZE | **No.** 32 bytes per 8×8 4bpp tile is fixed by the VDP. | **comment corrected, no guard** |
| 5 | `dplc.emp:65,69` `lsl #5` for TILE_SIZE | **No**, same reason. | **comments corrected, no guard** |
| 6 | `plane_buffer.emp:76,244` / `section.emp:277` `#160` / `#80` | **Yes** — `TILE_CACHE_STRIDE` is a cache-geometry tuning choice. | **NOT touched** — already owned by an OPEN mul2 ledger row (the deferred stride-naming parcel), which was reverted once for deleting the corpus's only stride tripwires. Front-running it would repeat that. |
| 7 | `plane_buffer.emp:94,231,383` `lsl.w #7` | **Yes in principle** (`PLANE_H_CELLS` is VDP-configurable 32/64/128), but changing plane width is a whole-engine change nobody makes accidentally. | **NOT touched**, ranked low |
| 8 | `sprites.emp:151,236` `lsl.w #6` for `SPRITES_PER_BAND * 2` | **Yes** — band capacity is a tuning number, and `sprites.emp` has ZERO `ensure`s. | **NOT touched** — the best of the remaining, and the recommended next guard |
| 9 | `sound_debug.emp:58` `<= 176` | **Yes** (`Sound_Dbg_Mirror`'s size), but it is debug-only and the guard already fires loudly on overflow. | **NOT touched**, ranked lowest |

## The finding that cost the most, and it is a general constraint

**A comptime `ensure` on an IMPORTED constant cannot be added to a module that a
port test compiles standalone — but an instruction operand naming the same
constant can.** Measured three times in this lane:

* `dplc.emp` + `ensure(TILE_SIZE == 32)` → 3 failures in
  `dplc_negative_probes.rs` and 4 more in `dplc_port.rs`, all
  `unknown name TILE_SIZE`.
* `s4lz.emp` + the same → 2 failures in `load_art_port.rs`.
* `vdp_init.emp` + `ensure(… == sizeof(VdpShadow))` → 5 failures in
  `tranche3_negative_probes.rs`, `unknown type: VdpShadow`.

The asymmetry is the point: `s4lz.emp` **already contains**
`adda.w #TILE_SIZE, a1` and compiles standalone fine, because an instruction
operand defers to link time while an `ensure` must fold at comptime. So "the
module already names this constant" does NOT imply "the module can assert about
it". Every ported module's standalone harness pins its comptime dependency set,
and adding a guard widens it.

Consequence for the ranking: sites 4 and 5 are guarded by a **comment** rather
than an `ensure` not because the guard is worthless but because it costs a
harness change to protect a number the Mega Drive fixes. That is the trade the
brief asked to be made explicitly.

**And it produced a better answer for site 1 than the brief proposed.** The brief
said "`constants.emp` cannot see `VdpShadow`, so the guard belongs in
`vdp_init.emp` or `structs.emp`". Both would have needed a new import and both
are standalone-compiled. **`engine/ram.emp` needs neither** — it already carries
`use engine.constants.*` and `use engine.structs.{DMAEntry, VdpShadow}`, it is
where the buffer is declared, and it already hosts a wall of exactly this kind of
cross-authority `ensure` (`:39`, `:40`, `:52`, `:53`). The guard joined that wall
with zero ripple.

## Gates — all own-run

* **Byte bar, seven targets: NEUTRAL.** Every full CRC, size, anchor CRC and
  anchor end identical to the chain-51 tip. Confirmed after the final edit, not
  only mid-lane.
* **`refreeze --check`: OK (tip `migmask`, chain len 51)**; nothing frozen.
* **Full strict**, foreground, streams separated: **3511 passed / 0 failed /
  4 ignored = 3515**, and the branch's `#[test]` total counted this session is
  **3515**. Closes exactly, and equals master — this lane adds no Rust test.
* **Negative probes, both polarities, for every added check:**
  `VDP_Shadow_len` 19→20, `BLOCK_TILE_SHIFT` 4→5 and `MAX_ACT_SECTIONS` 48→600
  each fail the build with their own message; reverting each restores the byte
  bar exactly (`s4.bin 84c33dfc`). The `TILE_SIZE` 32→64 probe fired two errors
  at once while those guards were still in place, which is how their cost was
  measured before they were withdrawn.

## Per-pass findings

**Step 3 (retrospect)** — the standalone-harness constraint above is a language
observation as much as a test one: `.emp` has one spelling for "this module
depends on that name" (`use`) but two very different requirements behind it
(link-time vs comptime), and only the harness discovers which. A module that
wants to assert about an imported constant has no way to say so.

**Step 5 (engine optimize)** — none; this lane is byte-neutral by construction.

**Neither bucket — the headline** — **the lying comment was not a documentation
bug, it was a load-bearing one.** `s4lz.emp:228` said the shift was "drift-locked
by the ensure" and the file's only occurrence of the word was in that sentence. A
reader auditing stride restatements greps for `ensure`, finds the comment, reads
"drift-locked", and moves on — the false claim actively consumes the attention
that would have found the gap. That is strictly worse than silence, and it is
worth a standing rule: **a comment may not name a guard; it may only state a
fact.** Every "guarded by X" comment in the corpus is a claim nothing checks.

---

## Panel round (2026-08-07)

The lens read the whole corpus for the defect class this lane is about and found
**four surviving false guard-claims the lane's own sweep missed**, one of them
materially worse than either it fixed. All are now closed.

**Rank-1, and the guard LANDED rather than being downgraded to a comment.**
`sound_constants.emp` claimed "the build asserts `Z80_SOUND_SIZE <=
SND_STATE_BASE`". No such assertion existed. Unlike `TILE_SIZE`, this number
genuinely drifts — the Z80 driver blob grows whenever an opcode is added — and
the failure is the code blob silently overwriting the playback state block: no
crash, no golden byte, audible only as corruption. The lane's own doctrine says
guard-if-the-harness-allows, comment-if-not, so the harness question was
MEASURED rather than assumed: the `ensure` went into `boot_data.emp` beside its
existing blob-parity guard (where `Z80_SOUND_SIZE` already folds), and **full
strict passed 3511/0/4 = 3515**. No standalone harness compiles that module
without `engine.sound_constants` in reach, so the guard stands.

Also closed: `sound_constants.emp`'s "Every seam is asserted below" (false for
the first seam it listed), and `hblank.emp` + `parallax.emp`'s "drift-locked
against structs.asm" claims about the VDP shadow-offset block — nothing relates
that block to `VdpShadow`'s field offsets, and `engine.vdp` says so itself. The
`parallax.emp` one is fixed in lane A, which already owns that file.

**The `BLOCK_TILE_SHIFT` guard covered 8 of its 10 consumers, not 10.**
`tile_cache.emp:534,537` divide a *block* count by *blocks-per-section*, which is
`BLOCKS_PER_SECTION_AXIS` — a separate constant that merely equals
`BLOCK_TILE_SIZE` today. The new guard would have passed while those two divided
by the wrong power of two. Closed properly rather than ledgered: a named
`BLOCKS_PER_SECTION_SHIFT` with its own equality `ensure`, and the two sites
respelled. Byte-identical (both shifts are 4).

**Three free derivations the lane skipped while writing three costed comments**
— `ART_STAGING_BUFFER_SIZE`, `BG_TILE_BASE_SLOT`-adjacent and
`load_art.emp`'s `ART_POOL_PAGE_BYTES` all multiplied by a literal 32 with
`TILE_SIZE` in scope and no import needed. Now derived.

**Corrections to this packet's own claims**, both found by the lens:

* The commit and this packet enumerated FIVE changed files; the diff touched
  SIX. `vdp_init.emp`'s `ensure` message text also changed
  (`engine/constants.asm` → `engine.constants`, correct — there is no `.asm`
  authority any more) and went undisclosed.
* The stated rationale for the `act_descriptor` change was wrong. "A field added
  to `Sec` lowers the ceiling instead of leaving this guard checking a number the
  engine no longer uses" cannot happen: the consumers still spell the stride as a
  literal under `section.emp`'s `ensure(sizeof(Sec) == 66)`, so a `Sec` change
  trips THAT first and this guard never observes it. The edit is still right — the
  ceiling now moves with the struct and the message reports both operands instead
  of a baked 496 — but it is the ceiling's own net, not the stride's. The comment
  now says so, and the accurate "guarded by `section.emp`" cross-reference the
  first draft DELETED is restored: in a lane about false guard claims, removing
  the true one while keeping three stale literals was backwards.

**Negative probes, both new guards, both fired:** `SND_STATE_BASE` lowered below
the blob size fails with "would overwrite the playback state block";
`BLOCKS_PER_SECTION_SHIFT` 4 → 5 fails with "divides by the wrong power of two".
Reverted by string-replace (never `git checkout` — that trap fired twice this
session), and the rebuild is byte-identical.

**Still ledgered, not fixed:** `engine/vdp.emp` hand-restates four `VdpShadow`
field offsets — the second authority for the struct whose LENGTH this lane
guarded. Closing it needs `vdp.emp` to import `VdpShadow`, which is exactly the
standalone-harness cost this lane measured elsewhere, so it is ranked next rather
than taken blind. Also ledgered: the act ceiling is an engine invariant living in
the tree's only game act file.
