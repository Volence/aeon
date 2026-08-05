# Known Bugs

Open defects with reproduction notes and any captured live-emulator evidence. Newest first.
(Distinct from `DEFERRED_WORK.md`, which tracks deferred *features*, not defects.)

---

## 🚨 TRIAGE TRAP — A RED SCREEN NO LONGER MEANS BUG-001 — 2026-08-05

**Read this before diagnosing any red-screen report.** `engine/system/release_fault.emp:73`
writes `move.w #$000E, VDP_DATA` into CRAM[0] and forces the display OFF (`$8134`) before
halting in `.halt: bra .halt`. `$000E` is **the exact value BUG-001's frozen 2026-06-21
capture recorded** as its "pure RED backdrop" evidence — and BUG-001's own recommended-next-step
block said "Watch CRAM line-0 index-0 for the `$000E` write" as its third triage target. That
recipe is now struck out at the source (see BUG-001 below), but anyone working from the
screenshot or from memory will still reach for it.

At HEAD, a red screen means **a fatal fault halt in the lean release shape** — a bus/address
error or an unhandled exception — **not** streaming corruption. The two are trivially told
apart: the fault halt has the display OFF (whole raster is backdrop, no planes, no sprites,
frozen), while the BUG-001 symptom kept rendering garbage plane tiles and an INTACT Sonic
sprite over the red field.

Scope note: `ReleaseFault` is the **lean-profile** path (introduced by `parcel/item29-mddbg-strip`,
provenance chain 39). The default release shape and every DEBUG build show the MD Debugger
crash screen instead, so the red halt is specifically a lean-build signature.

---

## BY DESIGN (recorded) — release builds drop an SFX SILENTLY on ring overflow — 2026-08-05

**Not a regression, but it is the one remaining SFX-loss path, and `BUGS.md` still named the
retired 1-byte mailbox as the loss mechanism.** `sound_api.emp:305-313`: `Sound_PlaySFX`
computes `nextWr` and, if `nextWr == Rd` (ring full — more than 7 DISTINCT pending ids
enqueued in one frame before `Sound_DrainSfxRing` runs), branches to `.ps_drop` and **loses
the newest id**. The `raise_error "Sound_PlaySFX: SFX ring full (>7 in one frame)"` that
catches it sits inside `if DEBUG == 1`, placed BEFORE the shared drop branch so the plain
shape stays byte-identical — which means **release loses the SFX with no signal at all**.

Deliberate and documented at the site (a >7-distinct-ids frame is treated as a content bug,
not a runtime condition). Recorded here so that a future "an SFX didn't play" report is
triaged against THIS path, not against the mailbox collision that was fixed in 2026-06.

---

## BY DESIGN (recorded) — same-id, same-frame SFX requests COLLAPSE — 2026-08-05

`sound_api.emp:295-297`: before enqueueing, `Sound_PlaySFX` compares the incoming id against
the **most recent pending entry** (`(Wr-1)&MASK`) and skips on a match ("same id already
pending -> skip (no double-fire)"). Intentional per the in-code comment, and the right default
for the spam case. But it means a **legitimate rapid double-fire of one id inside a single
frame is merged into one**.

Recorded because it presents **identically to BUG-002's "no follow-up noises" symptom class** —
a user reporting "the second one didn't play" could be hitting this dedup, the release-side
ring-full drop above, or a genuine defect, and the three are indistinguishable by ear.

---

## FIXED — odd Z80 blob → boot ADDRESS ERROR — 2026-08-03

**Caused and fixed by the same parcel** (`parcel/wave4-z80-sound-reclaim`), and the most
instructive defect of the batch: it was a KNOWN hazard that had been marked closed by a
mechanism that never shipped.

**Mechanism:** `boot.emp`'s copy loop walks `a5` through the Z80 blob and then continues
with the SAME register into `boot_tail` — four PSG-silence bytes and its word-wide VDP
command reads. Nothing re-aligned `a5` at the hand-off, so the blob's length silently
became an alignment precondition for every following `move.w (a5)+`.

**Reachability:** every blob size shipped before this parcel happened to be even (6172
plain / 6298 debug), so the precondition held by accident. The reclaim moved the blob to
5941 / 6067 — both ODD — and the 68k landed in `ErrorHandlerBlob` with `ADDRESS ERROR` at
`$001889` (debug) / `$001B91` (config_a), i.e. the first misaligned word read. Symptom at
the A/B bench: NEW produced 26,721 bytes of VGM against OLD's 157,311. Bisected to the
reclaim half by building at the end of the bug batch (`2adf697`), which boots clean.

**Why it was live at all:** the 2026-07-16 review listed this exact hazard in its Tier-4
boot/hardware-risk list — "No build-time evenness assert on either Z80 blob (odd blob =
boot address error)" — and tagged it **[closed by D8 linker asserts — do not hand-fix]**.
That diagnostics-tier mechanism was never built, so the item sat un-fixed under a
closed-looking marker, and the first parcel to change the blob length by an odd number hit
it. See the corresponding correction in the review's STATUS section.

**Fix (`5526113`):** `align 2` inside the `Z80_Sound_Start`/`Z80_Sound_End` brackets plus
`ensure((Z80_SOUND_SIZE & 1) == 0)` — the padding makes it right and the ensure makes it
stay right, independent of any future diagnostics tier.

> **⚠️ THE `align 2` IS LOAD-BEARING RIGHT NOW — DO NOT "SIMPLIFY" IT AWAY.** The blobs at
> HEAD are STILL ODD: `engine/sound/generated/z80_sound_blob.bin` = **5933 bytes**,
> `z80_sound_blob_debug.bin` = **6059 bytes**. The padding byte is what keeps `a5` aligned
> into `boot_tail`; remove it and the boot ADDRESS ERROR returns immediately, in both
> shapes. This is not a historical precaution against a hypothetical future odd blob — the
> blob is odd today and every day since `5526113`.

**Two false leads recorded so they are not re-walked:** `pins.rs` was stale (regenerated
with `repin`) but is a gate/record, NOT a placement input — ROM CRCs were byte-identical
before and after the repin. And `Z80_SOUND_SIZE` is link-derived with no hardcoded mirror
in Aeon, so a stale size constant was not the cause either.

**Consequence for the record:** every ROM built during the reclaim tasks was unrunnable for
this reason. Those tasks' blob-size measurements remain valid (the blob is emitted
independently of the ROM link), but no functional claim about them could have been made
before `5526113`. Evidence: `docs/superpowers/notes/2026-08-03-wave4-sound-ab.md` Result 3.

---

## FIXED — Z80 sound defect cluster (7 defects) — 2026-08-03

Review item 23's sound bug-fix batch plus three extras approved at plan time, all landed on
`parcel/wave4-z80-sound-reclaim` ahead of the size campaign (refactoring around known-broken
code means touching the same routines twice). Net cost +28 Z80 bytes, repaid many times over
by the reclaim in the same parcel. A/B evidence:
`docs/superpowers/notes/2026-08-03-wave4-sound-ab.md`.

### driver B1 — SFX state is power-on GARBAGE from boot until the first song — **FIXED (`9ef153e`)**
**Mechanism:** `SfxChannels`, both duck bytes and `SeqChannels` are never initialised at
driver start — they hold whatever the Z80 RAM powered up with until the first
`Snd_LoadSong` wipes them. `Sequencer_Frame` FALLS THROUGH to `.run_sfx` even with
`SND_SEQ_ACTIVE = 0`, so `Sfx_Frame` walks all 7 channel records every frame from the very
first tick. **Reachability:** the whole boot window before the first song load — with
garbage `sx_*` fields, wild chip writes and bank-latch writes are reachable, not
theoretical. **Fix:** `call Sfx_StopAll` at init, net **±0 bytes** (it replaces the
3-byte `ld (SND_SFX_QUEUE_CNT), a` and returns `a = 0`, so the following stores are
unchanged).
**Placement constraint — this is the part that matters:** `Sfx_StopAll` clobbers `de`, and
`de` holds `$4001` (the YM part-I DATA port) as a **driver-lifetime invariant**. At the
review's suggested site — below the `ld de, SND_Z80_YM_A1` — the call would have left
`de = 68`, redirecting every steady-state `ld (de),a` DAC write to Z80 RAM `$0044`. The
call therefore sits ABOVE the `ld de`, with the ordering constraint commented at the site.
**ORACLE-INVISIBLE by construction:** emulators zero RAM at power-on, so the pre-fix
behaviour cannot be exhibited in oracle. Verified statically.

### SFX B1 — Sfx_DuckRamp resurrects a STOPPED song's PSG channel — **FIXED (`53660ad`)**
**Mechanism:** `Sfx_DuckRamp` re-asserts volume across the music channels with no
`SND_SEQ_ACTIVE` gate (unlike `Sfx_Restore`, which has one). **Reachability:** `StopMusic`
leaves a PSG channel with `SCF_KEYED` still set and its tone latch stale, so the next
ducking SFX un-silences that channel at the stale latched pitch — an audible tone that
**DRONES until the next song load**, with nothing in the stopped-sequencer path to kill it.
**Fix:** +5 B `SND_SEQ_ACTIVE` gate after the level store.

### SFX B2 — queue arbitration compared RAW priority — **FIXED (`e94fc47`)**
**Mechanism:** the SFX queue arbitrates on the raw priority byte, but bit 7 is the
non-latching flag under the 7-bit priority model (SFX Stage B), not magnitude. A bit-7 SFX
would therefore carry **+128 phantom queue weight** and win arbitration it should lose.
**Reachability:** LATENT — the build-fatal ensure added in the Stage B/C parcel keeps every
authored priority below `$80`, so no shipped SFX can express it today. Fixed anyway because
the flag is a supported authoring feature. **Fix:** +2 B mask.

### PSG #1 — Psg_ApplyMod let an EXACT-ZERO divisor reach the chip — **FIXED (`d5f8d6d`)**
**Mechanism:** the floor guard tested only for a NEGATIVE sum, so a modulation accumulator
landing on exactly zero passed straight through to the PSG divisor latch — a
chip-ambiguous value, and a direct contradiction of the routine's own comment
(`Psg_EmitNoiseClock` does the same clamp correctly). **Reachability:** live from MUSIC,
not just SFX — `Mod_Update` reaches it, and `PsgDivisorTableZ` ships its **top 13 entries as
`$0001`**, so an accumulator of −1 lands on exact zero from ordinary high notes. **Fix:**
+4 B, clamping the exact-zero case as well as the negative one.

### sequencer B1 — PSG down-glide 16-bit underflow evaded the overshoot snap — **FIXED (`bb66ff8`)**
**Mechanism:** a portamento down-glide subtracts the rate from a 16-bit divisor; on
underflow the value wraps to `$FFxx`, which the overshoot test then reads as "still ABOVE
the target". The glide therefore keeps running through wrapped space at garbage pitch for
up to ~65536/rate frames instead of snapping. The borrow was already sitting in CF and was
simply never tested. **Reachability:** same `$0001` top-of-table divisors as PSG #1 — any
fast down-glide from a high note. **Fix:** +2 B (`jr c` off the `sbc` into the existing
snap).

### FM bug 11 — Fm_PatchLoad clobbers sc_pan on a mid-song patch change — **FIXED (`dda5e74`)**
**Mechanism:** `Fm_PatchLoad` writes register `$B4` straight from the patch, overwriting
the channel's authored pan. Pan is **write-on-change** against a shadow, and
`Seq_HookSetPatch` never re-asserts it, so the shadow still reads "already correct" and
the channel stays MISPANNED indefinitely — for the rest of the song. **Reachability:** any
song with a `MEV_PATCH` after a `MEV_PAN` on the same channel. **Fix:** +4 B — zero the
`sc_last_pan` shadow so the next pan write re-fires, the same resync `Sfx_Restore` already
performs after its own patch re-upload.
**Recorded because it is a trap:** the review's suggested fix — "source `$B4` from
`sc_pan`" — would have been a **REGRESSION**. `sc_pan` is the raw `$B4` byte and `0` means
"never panned, keep the patch default", so that fix would write `$00` (both outputs off)
and SILENCE every unpanned channel.

### PSG M5 — Psg_NoteOn's detune fold had no floor — **GUARDED (`9463906`)**
**Mechanism:** `Psg_NoteOn` folds detune into the divisor with no range guard, so a
negative detune applied to a divisor-1 note wraps to `$FFxx`. **Reachability:** NOT
reachable with any authored content today — recorded as a **guard, not a repair**. **Fix:**
+11 B, clamping BOTH the negative and the exact-zero case rather than the cheaper
negative-only test: negative-only is precisely the defect fixed in PSG #1 one commit
earlier, and re-shipping that shape to save 6 B is a bad trade inside a parcel handing back
~230.

---

## FIXED — G10 — move_lock permafreeze on solid-object landing — 2026-08-03

A slip-locked player (move_lock set by the S3K slip nudge) who landed on a solid
object kept frozen input forever: Player_SlopeRepel (the normal decrementer) is
bypassed by Ground_PostMove's on-object exit, and nothing else ticked the lock.
Fixed on parcel/bug005-sprites-player (`a8e2b5b` + comment follow-ups): the
on-object exit now ticks the lock (memory-direct form — the register form trips
a sigil relaxation oscillation at the player_ground/player_air section boundary).
Grounded-frame-only semantics preserved (airborne stays frozen by design).

**CONFIRMED IN-EMULATOR 2026-08-03** (previously review-proven only). Repro
recipe, invariant-safe — do NOT poke `Camera_X/Y` to get there, that trips
entity_window's single-axis slide assert: boot DEBUG, stay in debug-fly (the OJZ
scroll test boots into it — 16px box, `height_pixels` $10), fly to the Sec1
`TestSolid` at world (2304, 176) so the entity window spawns it legitimately
(`emulator_object_list` confirms), fly ~80px above it, press B once to toggle
back to Sonic (`height_pixels` $27), let him land. With `status` = $20
(ST_ON_OBJECT) held throughout, poking `PlayerV.move_lock` = 30 then advancing
frames gives 30 -> 20 (10 frames) -> 0 (25 more), i.e. exactly 1/frame, floored
at 0. Pre-fix this path never ticked, so the value would have stayed at 30
indefinitely.

---

## BUG-005 — one-frame stray Sonic sprite piece ("second face") — OPEN-INSTRUMENTED, minor

**Status:** OPEN-INSTRUMENTED. **Severity:** low (single-frame visual flicker, no state corruption).
**Reported:** 2026-08-02 by the user from a live spindash-stress session (OJZ, DEBUG
build, chain-30): one captured frame shows a duplicate chunk of Sonic's head floating
beside him. Frozen-state diagnosis was lost to an emulator control-socket hang before
the sprite table could be dumped (the artifact frame could not be re-frozen).

**Ruled out (2026-08-02 forensics):**
- The `mapping_dsl` sprSize w/h swap — real, but Sonic's mappings come from the
  hardware-correct S2 conversion path, and the swap is FIXED anyway (byte-identical,
  see the mapping_dsl commit).
- The torn-table DMA race — structurally prevented: `Sprite_Table_Dirty` is set only
  AFTER the terminator fix-up in `Render_Sprites.done`, and the 68k-source DMA halts
  the CPU, so a mid-build table can never ship. *(Amended 2026-08-05: that claim had
  one hole — a DROP-RETAINED dirty flag (Critical queue full) is set-but-stale, and
  IRQ6 landing mid-emit on a lag frame could ship the previous length against a
  mid-emit buffer. Closed by the `Sprite_Emit_Active` bracket, `parcel/defect-batch-8`
  — the "can never ship" claim is now unconditional again.)*
- Steady-state chain corruption — tick-stepped VDP sprite-table sampling through a
  replayed jump transition (ticks 1002-1015) shows coherent link chains, correct
  terminators, and `Sprites_Rendered` matching the chain every sampled tick. Stale
  entries beyond the terminator exist by design and are unreferenced.

**Leading suspects:** the `.done` terminator fix-up (`move.b #0, -5(a4)`) landing on
the wrong entry for one frame if `d5`/`a4` skew (e.g. a `DrawRings` path that moves
one without the other), or a multisprite sibling-walk piece-count edge on a specific
pose transition. Both would extend the chain into stale entries for exactly one frame
— matching the observed single-frame ghost. Concrete probe target: the band-cap path
(`sprites.emp` `.band_limit_pop`, ~line 463) reaches `.done` SKIPPING the `DrawRings`
call the normal band-exit runs — the one named site where the `a4`/`d5` provenance at
`.done` differs from the common path (`DrawRings` is contracted `out(d5, a4)`, so a
skew there requires an internal bug — but this is where to look first).

**Live net (2026-08-02, DEBUG builds only):** the chain-walk assert is now in place
at `Render_Sprites.done` (`engine/objects/sprites.emp`), immediately after the
terminator fix-up. It walks the finished SAT link chain from entry 0 (bounded at
`MAX_VDP_SPRITES` iterations so a cyclic chain cannot hang) and
`assert.w d1, eq, d5` traps if the link-path length ≠ the emitted count — in-frame,
with the builder's registers live (d5 = count, a4 = write ptr), before
`Sprites_Rendered` is stored. Both exit paths (`.band_limit_pop` included) converge
on `.done`, so the cap path is covered; the `.empty_table` path needs no walk
(count 0, entry 0 is the hidden terminator). Plain ROMs are byte-identical — the
net compiles only under `DEBUG == 1`.

**~~Next step (its own session)~~ — EXECUTED 2026-08-05** (the overnight
verification round, `docs/superpowers/notes/2026-08-05-verification-round.md`):
(1) the `.band_limit_pop` suspect was probed DIRECTLY — a file-level probe ROM
forced the cap to 12 so the path fired every frame for 25 s under the
object-test soak; the chain-walk net stayed silent and every frame rendered
exactly cap-many coherent sprites. **The named a4/d5-skew class does not
reproduce at this path — suspect downgraded.** (2) The replay screenshot burst
through pose transitions with ring emission ran clean (7 sampled frames, no
ghost, net silent, Replay_Done=$FF). Status stays OPEN-INSTRUMENTED at LOW —
the original artifact remains unreproduced and the standing DEBUG net is the
trap; there is no active suspect left. Scope note (unchanged): the assert
proves link==count CONSISTENCY — it catches the named skew class, not a bug that
advances both in lockstep to an over-count (a different class than this ghost).

---

## ✅ RECLASSIFIED — BUG-001 — section-streaming corruption — UNREPRODUCIBLE ON CURRENT ENGINE (2026-08-02)

**Disposition:** the June-2026 corruption (red field + garbage BG tiles, often
post-spindash) is reclassified NOT-REPRODUCIBLE-BY-DESIGN on the current engine. All
three recorded suspects are structurally retired by architecture that shipped AFTER
the report: (1) the decompress-clobbers-cache alias — mid-game block decompression
now targets the separate `Block_Stage_Buffers`; the `Art_Staging_Buffer` alias of
`Tile_Cache_Nametable` is init-only (display-off, pre-cache-live, `engine/ram.emp`);
(2) the teleport/rebase skip-reload edge — per-frame teleports were deleted by
continuous scroll (2026-06-22/23); (3) the spindash camera-jump race — camera jumps
are contract-locked (`CAMERA_JUMP_LOCK`). Empirical: the 2026-08-02 replay-harness
sessions ran the streaming path under sustained scroll + repeated spindash bursts
(multiple full fixture replays + two live stress rounds) with zero corruption, clean
render, zero lag frames. The original evidence block below is HISTORICAL (its RAM
cell names predate the engine/game split — see the dated annotation). If the symptom
ever reappears, the replay harness is the capture tool: record at the deterministic
anchor and the corrupting timeline becomes replayable.

> **⚠️ Single-entry note (2026-08-05):** BUG-001 previously appeared TWICE in this file —
> this banner, and a second `## BUG-001` heading further down whose status line still read
> `**Status:** OPEN. **Severity:** high`. That contradiction is resolved: **this banner is
> the status**, and the 2026-06-21 write-up is folded in below it as history.

> **⚠️ The EMPIRICAL half of this reclassification predates the BG column-major rewrite
> (2026-08-05).** The 2026-08-02 replay-harness soak ran against the ROW-major BG layout;
> `7b6f55b` (`parcel/item28-bg-transpose`) then rewrote **the exact plane-write path this
> bug described** — BG layout to column-major, `Draw_BG_TileColumn` to sequential `move.l`,
> per-column autoinc-`$80` blits. The **structural** half is unaffected (all three suspects
> are retired by architecture the transpose did not touch), and the transpose itself was
> verified framebuffer-byte-identical over 900 frames including max diagonal scroll. But the
> soak evidence is **as-of the old path**: if this ever needs re-affirming empirically, the
> stress rounds must be re-run on the current layout, not cited from 2026-08-02.

### Historical record — the original 2026-06-21 write-up (STATUS SUPERSEDED BY THE BANNER ABOVE)

Kept verbatim except where annotated, because the frozen-frame capture is unrepeatable (a
restart lost it) and because knowing *what was believed and why* is the point of keeping it.
**Its "Status: OPEN / Severity: high" line is void** — see the disposition above.

**Was:** BUG-001 — Section-streaming rendering corruption (background → garbage tiles + red field)

**Original status line (VOID):** ~~**Status:** OPEN. **Severity:** high (game becomes unplayable in that area).~~
**Reproducibility:** INTERMITTENT
— happens "every now and then," often (but not always) right after a spindash. The user could NOT reliably
re-trigger it, so the live evidence below was captured from a single frozen occurrence (2026-06-21) and is the
primary record — a restart loses it.

**Screenshot:** `docs/research/bug_streaming_corruption_2026-06-21.png` — the whole background is a RED field
filled with a repeating grid of garbage tiles; the Sonic **sprite is intact**; the DEBUG HUD reads
`COL: need layout co…`.

> **Doc note (2026-08-05) — the `COL: need layout co…` HUD indicator NO LONGER EXISTS.** That
> string appears nowhere in `engine/`, `games/` or `tools/` at HEAD. It was a capture-era debug
> overlay and is gone; do not go looking for it, and do not treat its absence in a future
> report as evidence of anything. Read it here purely as 2026-06-21 evidence that the engine
> of that era self-detected a missing collision layout.

#### Symptom
The BACKGROUND planes render garbage tiles over a red backdrop. Sprites (player) are unaffected.

> **⚠️ 2026-08-05: "red backdrop" is no longer diagnostic of this bug at all.** See the
> **TRIAGE TRAP** entry at the top of this file — `ReleaseFault` deliberately paints CRAM[0]
> `$000E` (the very value captured below) and halts with the display off.

#### NOT a crash, NOT sound
- 68k `PC = 0x1DD4` — the normal main-loop wait (`Process_DMA_Critical` region). CPU running fine; SR=$2600.
- The player sprite renders correctly → sprite VRAM + sprite palette are intact. This is a **plane / level-art /
  backdrop** corruption only.
- Unrelated to the sound work in this session.

#### Live-emulator evidence (frozen frame, 2026-06-21)
- **Player** (object list): x=1301 (`$0515`), y=694 (`$02B6`). **Vel 0,0** (stopped). In section **(0,0)**.
- **Camera_X = `$04770000`, Camera_Y = `$02420000`** (16.16). Cam X=1143 — still inside section 0
  (`SECTION_SIZE = $0800` = 2048px), so `Sec (0,0)` is CORRECT; this is NOT a section-index mismatch.
- **`Section_Stream_State` ($FFA8EC): section 0 = `$02` (SS_RESIDENT), section 1 = `$02`, rest `$00` (IDLE).**
  → the engine believes section 0 (the player's section) is fully loaded.
- **`Slot_Section_Map` ($FFA8E0): slot0=(0,0) slot1=(1,0) slot2=(0,0) slot3=(0,0).**

> **Doc note (2026-08-02):** the cell names `Section_Stream_State` ($FFA8EC) and `Slot_Section_Map`
> ($FFA8E0) cited in the two bullets above no longer exist in `engine/ram.emp` — the A.4 art-stream
> state machine was never landed under those labels (this is confirmed in-code by the comment in
> `engine/system/replay.emp`). The evidence is left verbatim as the original 2026-06-21 frozen-frame
> record; the equivalent current section-streaming state lives in the `Section_*` cells
> (`Section_Plane_Dirty`, `Section_Top_Row_Written` / `Section_Bottom_Row_Written`,
> `Section_Left_Col_Written` / `Section_Right_Col_Written`, `Section_Fwd_Neighbor_Data` /
> `Section_Bwd_Neighbor_Data`). Read the two addresses above as "whatever streaming-progress cell
> occupied that offset at capture time," not as live symbol names. The same reading applies to the
> rest of this frozen record: capture-era paths (`ram.asm:28` — today `engine/ram.emp`) and the
> in-record suspect annotations are historical. In particular the `Decomp_Buffer`-aliases-cache
> "Strong suspect" bullets are SUPERSEDED by the reclassification banner above — the alias is
> `Art_Staging_Buffer: alias(Tile_Cache_Nametable)` today, init-only/display-off, structurally
> retired as a suspect.
>
> **Extended 2026-08-05:** the same reading now also applies to `Section_Teleport_Guard`
> ($FFA8E9) in the bullet list below — that symbol is **gone from the tree** along with the rest
> of the leapfrog subsystem (deleted by continuous scroll, 2026-06-22/23). The 2026-08-02 note
> above did not reach that far down the list.

- **`Tile_Cache_Nametable` (RAM $FF0000): BLANK — uniform tile-0 entries (`1000 0000` repeating).** The RAM-side
  section nametable cache holds no real art. (NOTE: `Decomp_Buffer` *aliases* `Tile_Cache_Nametable`,
  ram.asm:28 — a decompress firing during a streaming event would clobber this cache. Strong suspect.)
- **VRAM level-art region ($0000+): sparse / incomplete** — mostly zeros with a few stray bytes per tile;
  the section art is not actually resident in VRAM.
- **VRAM plane nametable (~$C000): GARBAGE** — random tile indices (`43BE 43F7 B8A7 33BF…`) mixed with
  repeating blank-tile entries (`00000001`, `00000004`). (Note: VRAM garbage ≠ the RAM cache's uniform blank,
  so the VRAM may be STALE pre-corruption content the DMA never overwrote — worth confirming the plane base.)
- **CRAM palette line 0 index 0 = `$000E` (pure RED, R7G0B0); lines 1-3 index 0 = `$0000` (black).** The
  backdrop entry alone is red → the red field. (Determine: is this a DELIBERATE debug "missing-layout" warning
  the engine paints, or palette corruption? Lines 1-3 being correct suggests a targeted write, i.e. likely a
  debug indicator paired with the `COL: need layout` HUD.)
- **No fill stuck:** `Cache_Fill_Resume_Col` = `$FFFF`, `Cache_Fill_RowResume_Row` = `$FFFF` (both "none
  pending"). So it is NOT a half-finished/interrupted tile-cache fill.
- `Section_Plane_Dirty` ($FFA8EA) = `$00` (no full redraw pending). `Section_Teleport_Guard` ($FFA8E9) = `$00`
  (**symbol no longer exists — see the extended doc note above**).
- `Section_Top_Row_Written` = `$0002`, `Section_Bottom_Row_Written` = `$003B`. `Lag_Frame_Count` = `$28` (40).
- HUD overlay: `COL: need layout co…` — the engine itself flagged that the **collision layout for the player's
  position is not loaded.** (**Indicator removed — see the doc note under Screenshot.**)

#### Diagnosis (as reasoned in 2026-06-21 — superseded, retained for the reasoning)
**Section-streaming state↔data DESYNC: section 0 is flagged `SS_RESIDENT`, but its art (VRAM tiles + RAM
nametable cache) and collision LAYOUT are not actually loaded.** The engine even self-detects the missing
collision (`COL: need layout`). So a streaming event marked the section resident WITHOUT (re)loading its
art/collision, and the fill/DMA then drew the empty/blank cache → garbage tiles over the red backdrop.

#### Leading suspects (unconfirmed at the time — ALL THREE STRUCTURALLY RETIRED, see the banner)
1. **Teleport/rebase "pure rebase, no redraw" path** treating the section as already-resident and SKIPPING the
   art/collision (re)load in an edge case where the data wasn't actually present. (See `engine/level/section.emp`
   teleport/rebase; memory `project_teleport_rebase` — "teleports are pure rebases, reinit/redraw removed".)
2. **`Decomp_Buffer` aliases `Tile_Cache_Nametable`** (ram.asm:28). A decompress during the streaming event
   would overwrite the nametable cache → blank/garbage cache → blank/garbage VRAM after the next fill/DMA.
3. **Race/timing edge case** — the intermittency + the spindash trigger (fast camera jump stressing the
   streamer) point to a timing window, not a deterministic path.

#### ~~Recommended next step (its own focused session)~~ — **NEUTRALISED 2026-08-05: DO NOT FOLLOW THIS RECIPE**

> **All three watchpoint targets are dead or actively misleading at HEAD.** This block is kept
> only so nobody re-derives it from the evidence above and walks the same dead ends:
>
> 1. ~~Watch `Section_Stream_State + 0` for a write to `$02`~~ — **the symbol does not exist**
>    anywhere in the tree. Neither does `Section_Teleport_Guard`. Both belonged to the leapfrog
>    subsystem, deleted by continuous scroll (2026-06-22/23). There is nothing to set a
>    watchpoint on.
> 2. Watch the `Tile_Cache_Nametable` region for a blanking write — **the suspect it was aimed
>    at is retired**: the alias is `Art_Staging_Buffer: alias(Tile_Cache_Nametable)`, init-only
>    and display-off. A watchpoint here now traps normal init traffic.
> 3. ~~Watch CRAM line-0 index-0 for the `$000E` write~~ — **ACTIVELY MISLEADING.** At HEAD the
>    engine itself writes `$000E` to CRAM[0] deliberately, from `release_fault.emp:73`, as the
>    fatal-fault backdrop. This watchpoint will fire on the fault halt and tell you nothing about
>    streaming. See the TRIAGE TRAP entry at the top of this file.
>
> **If the symptom ever reappears, the capture tool is the replay harness** (banner above):
> record at the deterministic anchor and the corrupting timeline becomes replayable — a strictly
> better instrument than any of the three watchpoints, and the reason this recipe was not
> rewritten rather than retired.

**Original text (historical):** Reproduce with a **watchpoint** to trap the corrupting moment:
Watch `Section_Stream_State + 0` (section 0's state byte) for a write to `$02` (resident) and check, at that
instant, whether the art-load / collision-load actually ran. OR watch the `Tile_Cache_Nametable` region for the
write that blanks it (catch the aliased decomp clobber). OR watch CRAM line-0 index-0 for the `$000E` write
(find whether it's the debug warning or corruption). Then trace backward from the trigger (spindash launch →
camera jump → which section routine fires). This is an **engine/section-streaming** bug — separate from sound.
Do NOT guess a fix; trace the corrupting write.

---

## ✅ RESOLVED — BUG-004 — window-despawned parent leaks its children (gap-ledger row 1599) — FIXED 2026-08-02

**Was:** `EntityWindow_DespawnObjects` deleted only the parent; children are untagged by
construction (`AllocDynamic` tags `SLOT_TAG_UNTAGGED`, only the window spawn path re-tags),
so they could never despawn themselves — a window-despawned parent leaked its children's
dynamic slots for the level, each orphan dereferencing a freed `parent_ptr` every frame.
**Fix (ruled (a), Volence):** the despawn path cascades `jbsr DeleteChildren` before
`DeleteObject` (merge `8678ddb`, chain-23 `despawn-cascade`). **Oracle A/B:** pre-fix
3 orphans orbit the zeroed corpse at origin forever (end-state live=33, 3 slots never
returned); post-fix parent+3 children freed the same frame, end-state 30-clean, free stack
fully recovered. Full procedure + screenshots:
`docs/superpowers/2026-08-02-engine-debts-opener-evidence.md`.

---

## BUG-002 — SFX gameplay-integration cluster (spurious triggers, wrong duration, rev churn)

**Status:** PARTLY FIXED (see each item). **Severity:** medium (audible wrongness, no crash).
**Reported:** 2026-06-21 by the user from live play: "when you walk and roll the SFX lasts too long and
gets weird at the end; spindash press-once-and-release-quick does no follow-up noises; rev a lot → weird
sounds; sometimes random things trigger sounds when they shouldn't — e.g. Sonic in the air triggers the
jump noise without jumping; a few others I can't reliably trigger."

### ~~Common systemic thread — the 1-byte SFX mailbox (deferred A2)~~ — **SUPERSEDED, FIXED 2026-06-22**

> **⚠️ THIS THREAD IS DEAD. Do not attribute new SFX-loss reports to it.** The 1-byte mailbox
> was replaced by an **8-deep ring buffer** in `98798d1` (2026-06-22): `engine/ram.emp:460-462`
> declares `Sfx_Ring_Buf: [u8; 8]` + `Sfx_Ring_Wr` / `Sfx_Ring_Rd`, with
> `SFX_RING_DEPTH = 8` at `engine/sound/sound_constants.emp:452`. `Sound_PlaySFX` now only
> ENQUEUES (`sound_api.emp:283-329`); the **sole** writer of `SND_REQ_SFX` is
> `Sound_DrainSfxRing` (:357/:361, inside one `z80_stopped` hold), which posts at most one id
> per frame and only when the Z80 has cleared the previous — called once per frame from
> `game_loop.emp:32`. `DEFERRED_WORK.md:1396` records the A2 runtime verification as
> **DISCHARGED**.
>
> **Date caution:** every sub-item filed under this thread below is dated 2026-06-21 and
> therefore **predates the fix by one day**. Their root-cause analyses stand on their own
> evidence; only the "…and the mailbox collision dropped one" *contributing* clause is now
> void. Today's SFX-loss paths are the two BY-DESIGN entries at the top of this file
> (release-side ring-full drop, and same-id same-frame dedup).

**Original text (historical):** The 68k posts SFX to a SINGLE byte (`SND_REQ_SFX` $1F03). **Two SFX in one frame → the second clobbers the
first → one is dropped.** This is the deferred A2 item (DEFERRED_WORK.md). Several symptoms below are this
collision surfacing in real play. A small ring-buffer mailbox (A2) is the systemic fix; the per-bug fixes
below remove specific collisions at the source.

### Item 4 + Item 2 — spurious roll-jump SFX after a spindash launch — **FIXED 2026-06-21**
**Root cause (data-flow traced, not guessed):** charge-mashing JUMP latches `Player_JumpBuffer`; `.rev`
consumes it each rev, BUT the release frame runs `.release` (never `.rev`), so a jump press landing in the
buffer window at the moment of release is never consumed. `.release` → `jmp PState_Roll`, and `PState_Roll`
(player_ground.asm:327) fires `Player_Jump` on any set buffer → (4) the jump SFX `$62` plays "in the air"
right after the launch + the player roll-jumps without an intentional press; AND (2) that same frame the dash
`$B6` and the spurious jump `$62` both hit the 1-byte mailbox → one drops → "no follow-up noise" on a quick
spindash. **Fix:** `clr.b (Player_JumpBuffer).w` at the spindash launch (player_spindash.asm `.launch`,
before `jmp PState_Roll`) — drops the stale charge press; a FRESH press after launch still roll-jumps.
~~**Verify when emulator reloaded:**~~ **STALE TO-DO (noted 2026-08-05)** — this line was never struck
after the fact. Later follow-ups in this same cluster (Items 1+3 follow-up, follow-up #2, follow-up #3,
BUG-003) are all marked **hardware-verified** on ROMs built after this fix, and the spindash-release path
was exercised throughout those captures. Repro if you want it: spindash + mash jump + release → no
airborne jump chirp; the dash plays.

### Item 1 — roll SFX "lasts too long and gets weird at the end" — **FIXED 2026-06-21**
**Ruled out** re-trigger-per-frame (roll/skid each fire ONCE). A 73-agent + adversarial-verify root-cause
pass found the real cause is in the **transcoded blob**: the roll `$3C` tail is a 42-pass `smpsLoop` whose
body has a per-pass `smpsFMAlterVol $01` (cumulative attenuation → fade to silence). Our engine has no
relative-AlterVol opcode, so the transcoder COLLAPSED the fade to ONE constant `MEV_VOL` inside a
`RepeatStart/RepeatEnd` body, which the engine replays identically every pass → the tail held flat at near-
full volume then HARD-CUT (= "lasts too long / weird at the end"). A secondary divergence: `smpsNoAttack`
was a transcoder no-op, so each pass re-keys the FM envelope (a stutter). NB the user's "walk" was the roll
FM tail — skid `$36` is byte-faithful PSG (no AlterVol; verified).
**Fix (transcoder-only — the Z80 driver has just 4 bytes free, so no new opcode):** `tools/sfx_transcode.py`
now UNROLLS an AlterVol-bearing `smpsLoop` into per-pass `Vol`+note events, walking the TL attenuation up by
the S&K per-pass delta and inverting `LogVolumeLutZ` to the `sc_volume` index that renders it — a dB-faithful
`+1 TL/pass` decay-to-quiet (regression test asserts each pass == +1 attenuation). Roll Vol now fades
`99→…→20`. **Deferred:** honoring `smpsNoAttack` (suppress the per-pass re-key) needs a Z80 no-key-on note
path — no room until bytes are reclaimed; the restored fade makes the re-key quiet, so re-evaluate by ear.

### Item 3 — "rev spindash a lot → weird sounds" — **FIXED 2026-06-21**
**Primary cause (confirmed):** the spindash `$AB` loop body is the SMPS bare-duration "replay previous note"
idiom (`dc.b smpsNoAttack, $02`); the transcoder dropped the standalone duration byte, so the `$AB`
`RepeatStart/RepeatEnd` body had **zero time-advancing events** → the Z80 ran all 24 reps in one frame and
fell to END → the rev played only its ~24-frame attack then stopped dead, and every rev tap re-fired that
truncated, tail-less attack (= "weird"). The same AlterVol-collapse (Item 1) flattened what little tail
existed. **Fix (transcoder-only):** (a) `_process_dcb` now implements the bare-duration replay (re-articulate
the previous pitch), restoring the loop body's timing; (b) the AlterVol unroll restores the per-pass fade.
`$AB` tail now has 24 note re-articulations fading `95→…→16`. The monotonic mod-sweep and `$10` transpose
clamp were verified **faithful — left unchanged**. A defensive packer backstop now rejects any
`REPEAT_START..REPEAT_END` body with no time-advancing event (the collapse class) for all SFX and music.

### Items 1 + 3 follow-up — re-key buzz + swept-pitch linger — **FIXED 2026-06-21 (hardware-verified)**
User retest after the fade fix: roll had "a higher pitch noise after", spindash-hold made "a jingle after a
second", and the spindash-release linger sounded "too high". VGM capture of OUR ROM proved the cause: the
unrolled tails RE-KEYED the FM envelope every pass (43× roll on `$28`/chsel `$04`, 26× spindash chsel `$05`,
at 30 Hz) = the jingle; and with the re-key gone the tail would have held at the modSet *swept* pitch
(spindash fnum `1912`) = the "too high" linger. Fix (the deferred `smpsNoAttack`, now done — see
DEFERRED_WORK B4): bit 7 of a NoteDur pitch = no-attack; `Seq_Op_NoteDur` skips the note-on hook for a held
note (4 Z80 bytes, the exact free budget); the transcoder holds all tail passes EXCEPT the first-after-modSet
(which re-keys to reset the swept pitch to base). **Re-captured & verified:** KEY-ON 43→2 / 26→2, tail holds
at base fnum (`1364` / `1288`, not swept), TL fade intact (`5→48` / `0→54`).

### Items 1 + 3 follow-up #3 — transition re-key click ("second faint spin") — **FIXED 2026-06-22**
The held-tail fix left ONE re-key at the main→tail seam (43→**2**): the main note sweeps up via its modSet,
then the first tail note re-keyed to reset the swept pitch to base — a faint "second attack" the user heard
as "a second more faint spin noise" on the momentum roll. **Fix:** `Seq_Op_ModSet` now, for an SFX FM channel
(route `< CHROUTE_PSG1`), re-writes the unmodulated `sc_base_freq` via **`Fm_WriteFreq`** — which changes a
HELD note's `$A4/$A0` with NO `$28` key-on (the vibrato path) — so when the sweep modSet turns off the tail
snaps to base with no re-key; the transcoder then holds ALL tail passes (dropped `_emit_notedur`'s
first-after-modSet exception). The +18 Z80 bytes were reclaimed by folding 6 more inline channel-class tests
into `Snd_ChanClass` (`Z80_SOUND_SIZE` back to `$16EE`, 2 free — *at this fix. The follow-on
"$1618 / 216 B free" figure this parenthetical used to carry is STALE (noted 2026-08-05): the
resident ceiling is `SND_STATE_BASE = $18F0` (`engine/sound/sound_constants.emp:88`), and after
the wave-4 reclaim the blobs are 5933 / 6059 bytes, i.e. roughly **450 B free plain / 324 B free
debug**. Treat every size figure in this cluster as as-of-its-own-date; measure the blob, don't
quote the doc.*). **Verified on hardware:** roll & spindash
KEY-ON **2→1**, fades still `5→53`/`0→54`, tails held at base — and a regression sweep confirmed skid/ring/
jump/dash all still sound (no fallout from the PSG-path conversions). The roll/spindash tails are now a single
clean attack fading smoothly to silence — fully S&K-faithful (one key-on, like S&K).

### Items 1 + 3 follow-up #2 — "distorted jingle for a bit" — **FIXED 2026-06-21 (RENDERED-audio verified)**
After the held-tail fix the user still heard "a distorted jungle [jingle] after them for a bit." The `$28`
re-key count was a PROXY; rendering the capture to WAV (vgm2wav) showed the truth: the roll RMS only faded
`1.00→0.68` then **plateaued**, and the spindash barely faded — yet one carrier's TL walked a full 32 dB.
Root cause: for alg-4 voices there are TWO carriers (S2+S4); only ONE faded. `Fm_SetVolume` reads the
algorithm/carrier-mask + base TLs via `Fm_PatchPtr`, which resolves `sc_patch` into the MUSIC patch table
`SND_SEQ_PATCHTAB` — but SFX channels load their voice from `sx_patch_base` and never set `sc_patch`, so
EVERY SFX volume write used a stale/empty patch's algorithm → wrong carrier mask → faded the wrong/one
carrier. Latent until now because one-shot SFX have constant volume; the fade fix exposed it. **Fix:**
`Fm_PatchPtr` returns `sx_patch_base` for SFX channels (`engine/sound_fm.asm`); `Sfx_Restore` passes the
MUSIC channel so its path is unaffected. The Z80 was at its $16F0 ceiling, so the bytes were reclaimed by
merging the two SFX gates in `Fm_NoteOnFreq` + factoring the 12-site `push ix/pop hl/ld a,h/cp` channel-class
test into `Snd_ChanClass` (5 sites converted; `Z80_SOUND_SIZE` now `$16EE`, 2 free — *at this fix; the
"$1618 / 216 B free" follow-on figure is STALE, see the correction in follow-up #3 above: ceiling is
`SND_STATE_BASE = $18F0`, post-wave-4 blobs are 5933 / 6059, ≈450 B free plain / 324 B debug*). **Rendered-audio
verified:** both carriers (`$48`+`$4C` roll, `$49`+`$4D` spindash) now fade `5→53` / `0→54`, and the audio
RMS decays to `0.02` (fades to silence) — no plateau, no distortion. The roll/spindash tails are now a clean
held note fading smoothly to silence (S&K-faithful). LESSON: the `$28` count was a proxy; only the rendered
WAV envelope revealed the un-faded carrier.

### BUG-003 — dash `$B6` "duh" = PSG noise rendered as a TONE — **FIXED 2026-06-21**
After the FM tails were clean the user heard a "duh..." after the spindash (the *release* fires the dash
`$B6`). The dash's PSG3 channel uses `smpsPSGform $E7` (noise mode) — its release is meant to be **white
noise**. But the transcoder routed it as `CHROUTE_PSG3`/`SFXEL_PSG` (a TONE voice) and dropped the
`smpsPSGform` opcode ("handled via sx_kind" — but sx_kind was *tone*), so the engine played an audible
descending TONE on PSG ch2 = the "duh." (Pre-existing; unrelated to the FM work — exposed once the FM was
clean.) **Fix (transcoder):** pre-scan a PSG channel for `smpsPSGform`; if present, reroute it to
`CHROUTE_PSGN`/`SFXEL_NOISE` and emit a fixed white-noise mode note (`$E6`, clk/2048), dropping the
tone-only modulation. **Verified on hardware:** the dash now writes the noise control `$E6` + ch3 noise
volume fading `5→15`, ZERO ch2 tone writes; rendered audio spectral-flatness `0.667` = broadband noise (was
tonal), fading to silence. **Refinement deferred (DEFERRED_WORK B5):** S&K's `$E7` is white noise *tracking
PSG3's swept tone frequency* (a descending-pitch "pshhew"); reproducing that needs the engine to drive PSG3's
frequency as the noise clock (or a tone-clock + noise channel split). The fixed-rate noise is the right
*character*; the pitch sweep is the remaining nuance.

### "A few others" (user can't reliably trigger)
~~Most likely further instances of the 1-byte-mailbox collision (A2) — any frame that fires two SFX (e.g.
ring + skid, jump + ring). Tracked under A2 in DEFERRED_WORK.md; the ring-buffer mailbox resolves the class.~~

**SUPERSEDED 2026-08-05.** That attribution is void: the ring-buffer mailbox SHIPPED (`98798d1`,
2026-06-22, 8 deep) and A2's runtime verification is DISCHARGED (`DEFERRED_WORK.md:1396`) — a frame
firing two SFX (ring + skid, jump + ring) is exactly what the ring handles, and those pairings were
exercised throughout the phase's captures. If "a few others" ever becomes reproducible, triage it
against the paths that are actually live today: the **release-side ring-full drop** (>7 distinct ids
in one frame, silent outside DEBUG) and the **same-id same-frame dedup** — both recorded as BY-DESIGN
entries at the top of this file.
