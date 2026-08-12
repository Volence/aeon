# Dust Effect — design spec

**Date:** 2026-08-11
**Status:** Approved by user (design dialogue 2026-08-11)
**Lineage:** rides the character-dispatch line (`feat/character-dispatch`) — the
design consumes `CharacterDef.cd_stand_wh`, which exists only there.
**Extends:** the Effect pool (`AllocEffect`, `Effect_Slots`, `NUM_EFFECTS = 16`),
the animation event vocabulary (`AF_DELETE`, `AF_END`), `Perform_DPLC_Deferrable`,
and the player state dispatcher (`Player_SetState`, `PState_EnterHooks`).
**Reference:** S3K `Obj_DashDust` (skdisasm `sonic3k.asm:33958`), S2 `Obj08`
(`s2disasm/s2.asm:42225`), S.C.E. `Objects/Players/Spin Dust/Spin Dust.asm`.

---

## 1. Goal & user-ratified scope

Give the player visible dust: the puff cycling behind a spindash charge, and the
puffs kicked up by a skid. Knuckles' glide-slide reuses the skid puff when Task
10 lands, which is why the slide is designed in now rather than bolted on later.

**In scope**

| Role | Consumer today |
|---|---|
| Spindash charge dust | `PState_Spindash` (live) |
| Skid puff | the skid arm-edge in `Player_Animate` (live) |
| Knuckles glide-slide puff | Task 10 (`PSTATE_SLIDE`), same object, different Y offset |

**Out of scope, by user ruling (2026-08-11):** water splash and water-run
dust. Aeon has no water system — `ST_UNDERWATER` is a declared status bit with
zero implementation, no water level, no water tables, nothing that sets it. The
splash role would ship with no caller, which the standing no-dormant-scaffolds
rule forbids. Water splash becomes a separate design task, revisited when the
water system itself is designed.

**Also deliberately dropped from the reference behaviour:**

- **S3K's `air_left >= 12` drowning guards.** Every dust path in S2/S3K is gated
  on them, and the S3K source states the reason outright (`sonic3k.asm:30764`):
  the drowning countdown numbers DMA into the dust's own 16-tile VRAM window.
  We do not share that window with anything, so the guard has no meaning here.
  Do not port it back in "for fidelity" — it would be a check that can never
  fire, guarding a collision that cannot happen.
- **Reverse gravity** (`Reverse_gravity_flag`) — no such mode exists here.
- **S3K's invisible routine-6 emitter object.** See §2.1.
- **The second (Knuckles) art variant** — ships with his palette swap, §5.4.

---

## 2. Architecture

Two objects, both allocated from the **Effect** pool, spawned by the player.

The pool choice is settled by precedent, not preference:
`tails_appendage.emp:16-30` records the reasoning. The **Dynamic** pool is
camera-culled (`core.emp` `.run_culled`, `CULL_DISTANCE_X/Y`), so a slot that
leaves the camera box is not dispatched at all — a follower there would silently
stop following, which debug-fly reaches trivially. The **System** pool is a fixed
always-dispatched sweep but has no allocator and no slot registry. **Effect** is
a fixed always-dispatched sweep *with* `AllocEffect`, and is the pool
`Perform_DPLC`'s budget assumptions were written against for non-player art.

### 2.1 What we do NOT reproduce from the reference

S2, S3K and S.C.E. all implement dust as **one** object with a two-level
dispatch: `routine` selects init / main / delete / **emitter mode**, and inside
main, `anim` selects splash vs charge vs puff. The emitter (routine 6) is an
*invisible* object that spawns a fresh puff child every 4 frames.

That emitter exists for one reason: **to keep the puff art loaded.** It sets
`mapping_frame = $15`, a frame whose sprite mapping is empty (draws nothing) but
whose DPLC entry is a single 16-tile load. So the invisible object's only job is
to be a DPLC pump, and the four puff frames carry *empty* DPLC lists
(`$FFFF` terminator in S.C.E./S2; a zero entry count in S3K) so that puffs at
different animation frames can coexist in one resident block.

We make the puff art **permanently resident** instead, which deletes the entire
mechanism: no emitter object, no dispatch cost, no `$15` sentinel frame, no
empty-DPLC convention. This is also the independently-converged best practice
across the modern corpus (§7).

The reference's other reason for a pinned singleton — that a player can toggle
dust with a single byte write because there are no state hooks — does not apply:
we have `PState_EnterHooks` / `PState_ExitHooks`.

### 2.2 The two components

Both live in `games/sonic4/objects/`.

| | `Dust_Spindash` | `Dust_Puff` |
|---|---|---|
| Role | charge dust, attached | skid / slide puff, detached |
| Created by | `PHook_SpindashEnter` | `Dust_Tick`, on a 4-frame cadence |
| Retired by | self, on `player_state != PSTATE_SPINDASH` | self, `AF_DELETE` at 16 frames |
| Position | re-read from the player every frame | written once at spawn; static in world space |
| Velocity | none | none |
| Art | DPLC, peak 12 tiles, `Perform_DPLC_Deferrable` | fully resident — **zero DMA, ever** |
| Script | `[1, F0..F6, AF_END]` — 7 frames, 14-frame loop | `[3, F0..F3, AF_DELETE]` — 4 frames, 16-frame life |
| Sprite | 4x3 tiles peak, single piece | 2x2 tiles, single piece |
| Player link | player SST pointer in its own `sst_custom` | none |
| Priority band | 2 | 2 |
| Concurrency | 1 | ~4 |

Duration semantics: `AnimateSprite` reloads `anim_timer` with the duration byte
and ticks `subq.b #1 / bpl`, so byte N holds a frame for **N+1** display frames
(`animate.emp:91`). Duration 1 = 2 frames, duration 3 = 4 frames. This matches
S3K and SPG ("the subimage lasts for 1 frame more than the duration is actually
set to"), so the scripts above are the reference timings exactly: 7 x 2 = 14 and
4 x 4 = 16.

### 2.3 Why the follower self-retires instead of being torn down by a hook

`Player_SetState` (`player_common.emp:819`) calls the outgoing state's exit hook
unconditionally before writing the new state, so `PHook_SpindashExit` is a
genuine universal teardown point and was the obvious place to delete the
follower. It is the wrong place anyway:

- It requires caching the follower's slot pointer somewhere, and that pointer can
  be invalidated behind the hook's back. `DeleteChildren` runs on a character
  switch (the appendage reconcile), and `DeleteObject`'s C1b cascade runs when
  the player dies. A stale cached pointer plus a delete is the classic
  double-delete that corrupts the free stack.
- Any teardown path that does *not* route through `Player_SetState` leaks.

So the follower polls instead: one compare of `PlayerV.player_state` against
`PSTATE_SPINDASH` per frame, self-deleting on mismatch. No stored pointer, no
double-delete surface, and it self-heals — if the player slot is zeroed under it,
`player_state` reads 0 (`PSTATE_GROUND`), the compare fails, and the follower
retires on its next dispatch.

**This is not the S2 floating-dust bug.** s2disasm documents a stock bug where a
player grabbed mid-charge leaves dust hanging in the air; that dust polled
`spin_dash_flag`, which a grab leaves set. We poll the **state byte**, which is
written by the single dispatcher on every transition and has no stale path.

### 2.4 Why the follower does not use `parent_ptr`

It needs the player's SST to copy position and read state, and `parent_ptr` is
the obvious field. `children.emp:630-635` records why every effect leaves it
zero: a non-zero `parent_ptr` makes `Draw_Sprite` dereference the parent every
frame to test `RF_MULTISPRITE`, and an effect spawned by a multisprite parent was then
skipped as batch-rendered while being absent from the sibling chain — i.e. never
drawn at all.

The follower therefore keeps the player pointer in its own `sst_custom` word.
That also keeps it 2P-ready without reading the `Player_1` label, and keeps it
out of the sibling chain entirely (no chain contract to satisfy, no cascade
interaction).

---

## 3. Control flow

### 3.1 Charge dust

`PHook_SpindashEnter` allocates one `Dust_Spindash` and writes the player
pointer into its `sst_custom`. The hook's clobber contract widens from
`clobbers(d1/a1)` to cover `AllocEffect` (`d0`, `a1`) and the piece-count
refresh.

Allocation failure means no dust for that charge. That is the correct outcome
(§6) and needs no branch beyond the standard silent skip.

Per frame the follower copies the player's `x_pos`/`y_pos`, mirrors the facing
bit from the player's `status`, applies the per-character Y offset (§3.3), runs
`AnimateSprite`, `Perform_DPLC_Deferrable`, and `Draw_Sprite`.

Two things S3K does here that we deliberately skip: it re-derives the VDP
priority bit from the player's `art_tile` on the animation-restart frame, and it
forces low priority otherwise. Our priority is a fixed band (§4), so neither
applies.

### 3.2 Skid and slide puffs

A single `Dust_Tick` call in the player's per-frame path, **after**
`Player_Animate`. It reads the authoritative `PlayerV.skid_latch` that the
animation classifier already maintains (`player_common.emp:699-733`), and — once
Task 10 lands — the Knuckles slide state.

This is one owner and one trigger condition. The alternative, re-deriving "is
skidding" inside the ground state, would duplicate a four-term condition
(grounded, opposing input held, `|gsp| >= PHYS_SKID_MIN`, latch state) that
already has exactly one home, and would drift from it.

Placing the call after `Player_Animate` is load-bearing: the classifier is what
sets and clears `skid_latch`, so reading it earlier in the frame reads last
frame's value.

Cadence: a 4-frame countdown, matching S2/S3K/S.C.E. exactly (all three use a
plain `subq.b` countdown reloaded with 3; no masks, no randomisation — the
reference dust uses no RNG at all, which is convenient because Aeon has no
engine RNG). The counter is zeroed when not emitting, so the first puff of every
skid lands on the frame the skid arms, as in the reference.

**The counter lives in the PlayerBlock, not `PlayerV`.** `Replay_Hash` covers
`PlayerV` bytes `$30..$4B` plus the `$4C` tail word (`replay.emp:8-46`), so a new
field written during gameplay there would change the recorded hashes and
invalidate every replay fixture. The PlayerBlock is a4-relative per-slot working
state and is not hashed — the same reasoning as `PBLK_JUMPBUF`, and the standing
C1 ruling that character state stays out of the hashed SST window.

### 3.3 The per-character Y offset

S3K drops the puff at the player's Y **+16** for a skid and **+6** for Knuckles'
glide-slide, then subtracts 4 more for a "short character", keyed off a
repurposed SST byte (`$38`) set at init for the P2 slot.

We derive it from `CharacterDef.cd_stand_wh`'s height half instead, via the
existing blessed accessor. That follows the precedent already set for the curl
geometry, whose header states the reason: S3K computes the same per-character
delta (`y_radius - default_y_radius`), which is why it is data here rather than
an engine constant. A magic short-character flag would be a second, divergent
encoding of a fact the record already carries.

---

## 4. VRAM

`POOL_TILE_CEILING` 960 -> 896, i.e. `PAGE_FRAMES` 15 -> 14. Dust takes 28 of
the 64 tiles this frees at the top of the FG art pool; the character DPLC window
at 960 is unchanged.

| Symbol | Tile | Tiles | Contents |
|---|---|---|---|
| (FG art pool) | 0-895 | 896 | 14 pages of 64 |
| `VRAM_DUST_PUFF` | 896 | 16 | 4 puff frames, resident for the whole act |
| `VRAM_DUST_SPINDASH` | 912 | 12 | charge-dust DPLC target |
| (spare) | 924-959 | 36 | unallocated, available for future sprite art |
| (`VRAM_TEST_SONIC`) | 960 | — | wall: the character DPLC window |

Comptime `ensure`s: `PAGE_FRAMES * ART_POOL_PAGE_TILES == POOL_TILE_CEILING`
(already present, and 14 x 64 = 896 satisfies it); `dplc_peak_tiles(dust DPLC)
<= 12`; the puff block is 16; the two blocks do not overlap; the pair ends at or
below `VRAM_TEST_SONIC`. Derive the walls from the symbols, never restate the
numbers, so relocating either re-checks the allocation (the
`VRAM_TAILS_APPENDAGE` precedent).

`tools/ojz_strip_gen.py`'s `POOL_TILE_CEILING = 960` must move to 896 in the
same change; it carries a "keep in sync" comment and is the generator side of
the same fact.

**Cost, stated honestly:** the FG residency cache loses one frame, engine-wide
and permanently. The OJZ act needs **10 pages (612 tiles)** against the
remaining 14, so it stays fully resident and nothing changes today
(`PageIn_Fully_Resident` still latches, since pool pages <= `PAGE_FRAMES_CLAMP`).
The cost only bites an act wanting more than 896 tiles of resident FG art, and
§9.7's design is that such an act streams gracefully rather than failing.

### 4.0 Why NOT the BG region (a corrected recommendation)

The design dialogue first chose the BG region (`BG_TILE_CAPACITY` 448 -> 420,
dust at 1444-1471 ending at the SAT) on the assumption that the BG budget had
headroom because the editor's *source* tilesets measure 468-510 tiles. **That was
wrong and the assumption was never measured.** The generated blob
`games/sonic4/data/generated/ojz/act1/bg_tiles.bin` is **14336 bytes = exactly
448 tiles** — the cap is spent to the byte. Lowering it to 420 would trip
`inject_editor_bg.py`'s assert on the next regeneration and, at runtime, make
`BG_Init`'s length clamp silently truncate the copy, dropping the last 28 tiles
of background art.

The BG option therefore costs an **art regeneration** (re-export the background
28 tiles smaller, i.e. visibly less detail), where the FG option costs **two
numbers and no regenerated data**. Recorded here so nobody "restores" the BG
plan later: the FG pool is over-provisioned by 5 pages, BG has zero slack.

### 4.1 Why 28 tiles, and why they are separate

The puff block **must** be resident and **must** be contiguous. Puffs spawn every
4 frames and each animation frame lasts 4, so live puffs are always on
*different* frames simultaneously; every frame therefore has to be in VRAM at
once. And the four frames are addressed as tile offsets 0/4/8/`$C` from one
`art_tile` base, so they must be contiguous. 16 tiles is a floor, not a target.

The charge dust cannot be made resident: 7 frames at up to 12 tiles is 84 tiles.
It gets a DPLC window.

**S3K shares one 16-tile window between the two and has a real artifact as a
result** — we do not copy it. Charge frames are 8 or 12 tiles, so the DPLC writes
window tiles 0-11; live puffs address 0-15; so a puff lingering into a charge
renders fragments of charge art. It is reachable and ordinary: puffs stop
spawning below `|gsp| = $400` (`PHYS_SKID_MIN`) and the spindash trigger needs
`|gsp| < $100`, about 6 frames apart at the classic `$80`/frame skid
deceleration, against a 16-frame puff life. "Skid to a stop, immediately charge"
leaves roughly 10 frames of overlap. Because the charge animation cycles every 2
frames, the lingering puff would *shimmer* rather than show one wrong frame.

The two alternatives were considered and rejected in the design dialogue:

- **Share 16 tiles and flush live puffs on charge.** Visually the worst of the
  three: 3-4 puffs mid-fade all vanish in a single frame, right where the eye
  already is, reading as a bug rather than as style. It also reintroduces a
  512-byte puff-art reload on the next skid plus a resident-or-not flag.
- **Share 16 tiles and accept the artifact.** Cheapest and most faithful; the
  shimmer is small, brief, behind the player, and only affects three of the four
  puff frames (tiles 12-15 are never overwritten, so the last frame survives
  intact). Rejected because 12 tiles is 2.7% of a BG budget that dedups before it
  hits the cap, and the artifact is the kind of thing that gets filed as a bug
  later and paid for anyway.

The FG pool carve is quantised: `POOL_TILE_CEILING` is pinned by
`ensure(PAGE_FRAMES * ART_POOL_PAGE_TILES == POOL_TILE_CEILING)` with 64-tile
pages, so the 28-tile ask costs a whole page and leaves 36 tiles spare. That is
not the objection it first appears to be (§4.0) — the pool has 5 pages of slack.

The only other free gaps in the sprite-addressable range are 4 tiles at
1020-1023 and 3 after the Tails appendage. Neither fits either half. (Note the
"ring placeholder" is 16 tiles at 1000-1015, not 4 — the 960-1023 band is
otherwise fully allocated.)

---

## 5. Art & data

### 5.1 Source and size

Donor: `skdisasm/General/Sprites/Dash Dust/Dash Dust.bin` (5952 B = 186 tiles,
uncompressed). We ship two of its four frame groups:

| Group | Mapping frames | Tiles | Per-frame |
|---|---|---|---|
| Charge dust | `$0A`-`$10` (7) | 72, contiguous `$062`-`$0A9` | 8, 8, 8, 12, 12, 12, 12 |
| Puff block | (the `$15` load) | 16, `$0AA`-`$0B9` | 4 drawn per frame |

Total shipped: **88 tiles = 2816 B** per palette variant. Charge DPLC peak is 12.

Frames `$16`-`$1D` are the splash/drown set and index a *different* art base
(`ArtUnc_SplashDrown`); they are out of scope and not imported.

### 5.2 Mappings and scripts

Charge frames are single-piece (4x2 and 4x3) at offsets (-32,+4) and (-32,-4).
Puff frames are 2x2 at (-8,-8) with tile offsets 0/4/8/`$C`. Converted to Aeon's
VDP-order mapping format; S3K's 6-byte piece layout is already handled by the
`gen_characters.py` / `convert_s2_mappings.py` path (`S3K_MAP_PIECE = 6`).

The puff needs **no DPLC table at all** — it never streams. This is cleaner than
S3K's empty-entry convention, and our decoder would have handled either
(`dplc.emp:91-93` treats a zero entry count as zero DMA).

### 5.3 THE PALETTE — measured, and it is not optional

The dust draws on **CRAM line 0**, the character palette. Measured over the 88
shipped tiles: the art uses only **4 palette indices — 0, 1, 12, 13** (4286
transparent px, 1244 at index 1, 81 at 12, 21 at 13).

Under Aeon's `art/palettes/SonicAndTails.bin`, **all 1346 non-transparent pixels
are wrong**: index 1 is `$0EEE` white in S3K and `$0222` near-black here; 12 is
`$0ECC` pale lavender vs `$000E` bright red; 13 is `$0CAA` vs `$0008` dark red. A
raw drop-in renders the charge dust near-black with red highlights.

A colour-lossless permutation exists and is **`1->6, 12->4, 13->7`** — a strict
subset of the remap table already pinned for Tails, so `PALETTE_REMAP_EXPECTED`
needs no change. Apply it at build time, exactly as `derive_palette_remap` /
`remap_art_indices` do for Tails.

### 5.4 Two variants are provably required (and only one ships now)

Under `characters_staging/palettes/knuckles_main.bin` the **raw** S3K art is
already correct: that file is byte-identical to S3K's Knuckles palette, and it
differs from S3K line 0 only at indices 2, 3, 4 — none of which the dust uses.

**No single art variant can serve both palettes.** The three colours the dust
needs sit at disjoint indices in the two lines (`$0EEE` at ST[6] / KN[1];
`$0ECC` at ST[4] / KN[12]; `$0CAA` at ST[7] / KN[13]), and the two lines agree
only at indices 0, 10, 11 — none of them a colour the dust uses. So there is no
index assignment satisfying both.

Sonic and Tails share Aeon's line 0, so **one permuted variant ships with this
work**. Knuckles' raw variant is part of the Knuckles work, because his
per-character palette swap is what creates the need. Cost when it lands: a second
2816 B blob, selected per character at the same chokepoint that swaps his palette
(`Player_RefreshPhysics`, the verified single point through which both
`Player_Init` and `Debug_CharacterHotkey` route) — which must also re-DMA the
resident puff block, since it is palette-specific.

### 5.5 Importer

A new deterministic importer mirroring `gen_characters.py`: no timestamps, no
RNG, byte-identical on re-run, parsing the donor DPLC/mapping `.asm` rather than
trusting hardcoded offsets. It must **assert independently** that no emitted DPLC
entry exceeds 16 tiles rather than trusting its own generation.

### 5.6 Resident art load

The 16-tile puff block is DMA'd once at level init, alongside the existing
sprite-art load. Today that load lives in the OJZ scroll-test state's init (`TestArt` via
`QueueDMA_Critical`), which despite the name is the live gameplay state — the new
load is its peer and belongs beside it. Recorded here so the placement is a
known interim rather than a surprise when that state is replaced.

---

## 6. Failure modes & degradation

**Pool exhaustion: silent skip.** `AllocEffect` returns Z-clear and the spawn is
abandoned. This is already the house policy at every creator
(`children.emp:604`, `tails_appendage.emp:170`) and is the unanimous choice
across every codebase surveyed — seven Genesis disassemblies, SGDK, and Quake
1/2/3 all drop the *new* spawn; Nystrom names it the right answer for particles
specifically ("If all particles are in use, the screen is probably full of
flashing graphics"). No eviction, no growth, no assert.

Worst-case Effect-pool occupancy is **6 of 16**: ~4 puffs (16-frame life at a
4-frame cadence) + 1 follower + the Tails appendage. No reserve floor is
warranted at that headroom; if explosions and ring scatter later share the pool,
TF4's `>N free` reserve-floor idiom is the cheap escalation.

**Sprite budget: dust truncates first, by construction.** `Render_Sprites` walks
bands 7 (front) down to 0 and stops emitting at `MAX_VDP_SPRITES`
(`sprites.emp:225`), so low bands are dropped first. Band 2 therefore gives both
correct layering (behind the player at 4 and the appendage at 3) and free
graceful degradation. This is a deliberate **deviation** from the reference:
S2/S3K/S.C.E. all put dust at priority 1-of-8-*front* and Ristar puts effects
mid-stack, which protects cosmetics at the expense of gameplay sprites.

**DMA: the charge dust yields.** `Perform_DPLC_Deferrable` is documented for
exactly this ("non-player objects, budget-gated, can slip one frame"), and
`perform_dplc` leaves `prev_frame` stale on a dropped enqueue so the next frame
retries rather than showing stale tiles. The puff never queues a transfer at all.

**Replay determinism: unaffected.** `Replay_Hash` covers Player_1 only, and only
address-free fields. Dust writes no player field and its cadence counter is
outside the hashed window (§3.2), so the recorded fixtures stay valid and the
regression gate needs no re-record. This is a hard constraint on the
implementation, not an observation: **dust must never write a Player_1 field.**

---

## 7. Reference & corpus provenance

S3K/S2/S.C.E. specifics are cited inline above. Two findings from the wider
survey shaped the design rather than merely confirming it:

**Effect art resident, never streamed** was arrived at independently by four
shipped codebases: Sik's advice ("if it's 'small and common', you'll want to keep
it in VRAM instead of allocating it every time"), Tänzer's measured result after
making explosions permanent ("makes slow-down much more rare now", following a
`VRAM_alloc(256) failed ... largest free block = 249` with 515 tiles free),
Dragon's Castle's build-time `rs` VRAM chain, Cave Story MD's fixed
`TILE_SMOKEINDEX`/`TILE_GIBINDEX` ranges, and Honey Guardian's "manually preload
the frames". SGDK documents that add/release churn fragments sprite VRAM and
needs a defrag pass. The one effect anywhere that does stream (Cave Story MD's
damage numbers) is rate-limited to one spawn per frame. The corroborating
hardware fact is that small transfers waste the DMA budget on setup cost, so
per-puff streaming is the expensive way to do it.

**Skip-spawn, not evict-oldest.** Across the whole corpus the only eviction found
is Alien Soldier's narrow "expendable bit" path, and no source supports evicting
a gameplay entity for a cosmetic.

The reference numbers this design matches exactly: 4-frame cadence, 16-frame puff
life, ~4 puffs alive per skidding player, 14-frame looping charge cycle, static
world-space puffs with no velocity, one hardware sprite / 4 tiles per puff.

---

## 8. Verification

1. **Build both canonical shapes** (`./build.sh`, `DEBUG=1 ./build.sh`) plus
   `DEBUG=1 ./build.sh demo` — the demo game must be unaffected, proving the work
   stayed game-side.
2. **The replay regression gate must pass unchanged, with no fixture
   re-record.** That is the specific proof that dust is hash-neutral. A failure
   here means something wrote a player field.
3. **Emulator, by eye and by state:** charge dust appears on the charge frame and
   is gone the frame the state leaves SPINDASH; puffs appear every 4 frames while
   skidding, each living 16 frames, static in world space as the camera scrolls.
   Capture **during** motion, not at rest — at-rest screenshots hide scroll
   artifacts.
4. **The overlap case explicitly:** skid to a stop, immediately charge. Puffs
   must finish their own fade while charge dust runs, with no shimmer and no pop.
   This is the case the 28-tile split exists to make correct, so it is the case
   that proves it.
5. **VRAM inspection** at `VRAM_DUST_PUFF` / `VRAM_DUST_SPINDASH`: the puff block
   intact across a charge, the charge window changing per animation frame.
6. **Comptime walls** are gates, not checks to run: the `ensure`s in §4 fail the
   build rather than the emulator.
7. **Byte-changing parcel ritual** applies in full: `SIGIL_BLOB_LEN_DRIFT=warn`,
   both sigil release binaries rebuilt, repin then refreeze, three gates. Each new
   `.emp` module needs a `map.toml` `order` entry **plus** a sigil `ModuleSpec`
   with a **real pin**, landed in the same change as the file.

---

## 9. Risks

| Risk | Mitigation |
|---|---|
| Palette re-index applied wrongly -> dust renders black/red | §5.3 gives the exact measured mapping; verify by eye on first boot, it is not subtle |
| A future act wants >896 resident FG tiles | §9.7 streams rather than fails; the current act needs 612 of 896 |
| `ojz_strip_gen.py` left at 960 while the engine says 896 | both are changed in one parcel; the generator's own manifest output is the cross-check |
| Puff Y offset derivation wrong per character | compare Sonic and Tails directly; the offset is the only per-character term |
| Follower survives a teardown path | §2.3's state poll is total by construction; verify with a character switch mid-charge |
| Skid arm-edge fires more than once per skid | `skid_latch` is a latch; the cadence counter is the rate limiter |

---

## 10. Riders (ledgered, NOT folded into this work)

- **TF4 misattribution.** `docs/ENGINE_ARCHITECTURE.md` (4 sites: lines ~1118,
  1165, 1955, and §3.5) and `docs/research/children-particles.md:166` credit
  Thunder Force IV with "round-robin sprite flicker" via a counter at `$F29A`.
  That address is a global Y-drift accumulator added to every projectile's Y
  accumulator (`thunderforce4_disasm/code/disasm.asm:7206`, `:7231`); TF4 has no
  such mechanism, and the same doc's claimed TF4 RAM pools are palette/tilemap
  staging buffers. Our own per-frame intra-band link-order cycling
  (`sprites.emp:242-255`) is real and good — only the provenance is wrong.
- **`particle_anims.emp:17`** comment says "duration 4 frames/frame"; with the
  N+1 semantics of `animate.emp:91` a duration byte of 4 holds for 5 frames.
- **Water splash / water-run dust** — a design task gated on a water system
  existing at all (§1).
- **Knuckles dust art variant** — §5.4, belongs to the Knuckles palette work.
