# HANDOFF — character dispatch (Tails + Knuckles), 2026-08-10

Cold-start brief. Read this plus the plan
`docs/superpowers/plans/2026-08-08-character-dispatch-v2.md` and the spec
`docs/superpowers/specs/2026-07-02-character-dispatch-design.md` (APPROVED).

---

## 1. Exact repo state

| repo | branch | HEAD | clean? |
|---|---|---|---|
| aeon | `feat/character-dispatch` | `828da0d5` | yes |
| sigil | `master` | `ae32bf0f` | yes |

**Nothing is pushed.** aeon has NOT merged to master — C1 is mid-flight.

Build (both required env vars, build.sh hard-errors without them):
```bash
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
cd /home/volence/sonic_hacks/aeon
./build.sh            # plain  crc=11504636 len=414153
DEBUG=1 ./build.sh    # debug  crc=1a623f64 len=428171
DEBUG=1 ./build.sh demo   # demo crc=b5a586d1 len=97528
```
**Rebuild BOTH sigil release binaries (`cargo build --release` in sigil) after any
sigil edit, before building aeon** — historically the most-missed step.

---

## 2. What is DONE

**C1 Task 1** — branch, all plan anchors re-pinned post-P2 (engine RAM all moved:
`Engine_RAM_End` 617→736, `Player_1` 305→346, camera 228/292→246/316). The plan's
"exactly 4 hardwired Sonic sites" and "PlayerV 18 used / 30 usable / 12 free"
claims were both VERIFIED correct.

**C1 Task 2** (`b6034471`) — `CharacterDef` (sizeof 32), `CharacterDefs` roster,
shared `Player_InitAssets` / `Player_LoadArt`, all four dispatch sites converted.

**Module split** (`c3c12257`) — roster + shared loaders moved out of
`player_common` into `games/sonic4/player/characters.emp`.

**sigil, 3 parcels, all merged to sigil master:**
- `9f6b6209` — sound-bank ids + bank top now DERIVED from the map anchor instead
  of a hardcoded `0x0B`/`0x60000`. Gate was **ROM byte-identical**.
- `9cbc5fd0` — `games.sonic4.characters` ModuleSpec + repin/refreeze (chain 88).
- `ae32bf0f` — the `test_p1_player_port` group fixed for the new module layout.

Gates currently green: all three ROM shapes build; `refreeze --check` OK (tip
`characters-modulespec`, chain 88); the replay fixture passes on the shipped
debug ROM.

---

## 3. ⚠ THE RULING THAT GOVERNS ALL REMAINING WORK

**Character state lives in GAME RAM, never in the SST.**

The plan says to add `PlayerV.chardef: u32`. **Do not.** `engine/system/replay.emp`
hashes the whole SST custom window `$30..$4D`; its contract is that every field in
a hashed span is ADDRESS-FREE, and a DEBUG mismatch is a hard
`raise_exception "REPLAY DESYNC"`, not a warning. A ROM pointer there poisons
every recorded fixture.

Shipped instead: `Character_ID: u16` + `Player_Chardef: u32` in
`games/sonic4/config/ram.emp`. **`PlayerV` is untouched at 18 bytes.**
**Task 3 must follow the same rule** — its per-slot work goes in game-RAM arrays,
NOT new SST fields.

---

## 4. NEXT WORK, in order

### 4a. C1 Task 3 — per-slot globals, ability hook, `Camera_Target`, P2 audit
Plan Task 3, unmodified except the game-RAM rule above. `characters.emp` now
exists, so new code goes in properly-named modules.

### 4b. C1 Task 4 — the formal gate, then merge aeon to master
Gate recipe (VERIFIED, use verbatim — full detail in
`docs/superpowers/notes/2026-08-10-characters-modulespec-ab.md`):
1. `breakpoint_add GameState_OJZScroll_Init` (`$5E03C`) **BEFORE** `reset`
   (`run_to` after reset misses it — the scene inits during the deferred reset).
2. `reset`, `wait_for_break`.
3. `write_memory 0xFF803A value=1 width=1`  (`Input_Source = INPUT_PLAYBACK`)
   `write_memory 0xFF8040 value=386478 width=4` (`Replay_Ptr = $5E5AE`).
4. `breakpoint_clear all`, `resume`, ~30 s (fixture is 1721 ticks).
5. PASS = `Replay_Done` (`$FF803C`) == `$FF`, no fault screen.

**Mask .lst addresses to the 24-bit bus** — the listing prints `$FFFF803A`;
oracle `write_memory` REJECTS that. Use `$FF803A`.

### 4c. BLOCKED ON A USER RULING — the VRAM shortfall (gates C2/C3/C4)
Measured peak tiles/frame: **Sonic 29, Knuckles 29, Tails body 24, appendage 9.**
Need three simultaneous windows = **62 tiles**. Have **32** (tile 960 → hard stop
at `VRAM_TEST_OBJ` 992). Nothing below 960 exists (`POOL_TILE_CEILING = 960`,
tiled exactly by 15 × 64-tile page frames).

Reference research, MEASURED on the emulator (not inferred):

| | leader | follower | tail | total |
|---|---|---|---|---|
| S3K / S2 | 32 | **16** | 12-16 | 60-64 |
| **Sonic Classic Heroes** | 32 | 32 | 32 | **96** |

- **S3K ships a latent bug — do NOT copy its numbers.** `Tails_Load_PLC` loads
  the FULL `PLC_Tails` into a 16-tile window; Tails' worst frame is 24 tiles and
  **walk peaks at 22**, so the follower overruns into the tail's region on the
  commonest animation in the game. Near-certainly the origin of the classic
  Tails-tail corruption.
- **Classic Heroes measured windows: 1760-1791, 1920-1951, 1952-1983.** Stock S2
  boxes all character art into `$F000-$F7FF` = tiles 1920-1983 (64 tiles); CH
  split that 32/32 and **carved the third 32-tile window out of level-art space**
  at `$DC00`. So CH made the SAME trade Aeon faces.

**Recommendation on file:** drop ONE page frame → frees tiles 896-959 → 96 tiles,
matching CH exactly. **Cost: residency cache 15 → 14 frames, and it already
famines under sustained right-scroll.** Unmeasured alternative worth costing
first: the staged raw multi-entry DPLCs (`characters_staging/*/dplc/<name>.bin`)
don't duplicate tiles the way the contiguous-art path does.

**DOC DRIFT to fix with whatever lands:** `games/sonic4/config/constants.emp:125`
and `:136` say the character window is "up to 25 tiles" ending at 985. **Sonic
actually reaches 989.** Not a live bug, but every downstream VRAM judgement used
a number 4 tiles optimistic — including the staging README, which is why it
wrongly reports Knuckles as EXCEEDING the window when he merely matches Sonic.

### 4d. Assets — already staged and re-verified 2026-08-10
`games/sonic4/data/characters_staging/` — S3K Tails/Knuckles, 547 frames.
`gen_characters.py` regenerates all 20 files **byte-identically**, and an
independent parse (not the generator's own assert) found **zero** DPLC entries
over 16 tiles. Trustworthy. Task 5 consumes these.

### 4e. Second user ruling pending — `@object_bank` module placement
Ledgered in `docs/DEFERRED_WORK.md` as a SIGIL ASK, NOT STARTED, needs a spec.
Of ~60 `map.toml` `order` rows only ~8 are real memory-map anchors; the rest is
ceremony. Proposal: `module games.sonic4.tails in tails @ object_bank` — files
declare a placement REQUIREMENT, never a POSITION. Would make adding a character
zero-toolchain-edit. Novel cross-repo bet; wants explicit sign-off.

---

## 5. OPEN DEFECT — 8 failing sigil tests

`cargo test` in sigil is **3659 passed, 8 FAILED** across `native_full_rom`,
`seam2_dac_head_colink`, `seam2_layout_derivation`, `seam2_sfx_head_colink`,
`soundbankhead_port`. All pin literal sound-bank addresses in Rust.

**Not yet proven inherited vs introduced — do not assume either.** Known:
`seam2_layout_derivation` was independently flagged stale BEFORE this work (pins
`mt_bank_lma 0x58607` vs live `0x58628`). This group is also exactly the "Phase E
literal-address assertions" the ROM-relayout scoping earmarked. **Next step:
bisect against sigil `e6e99cdf` (pre-parcel-1) to settle it.**

**Always aggregate test results, never tail the log:**
```bash
cargo test -q --release --workspace --no-fail-fast 2>&1 | awk '
/^test result/ { for(i=1;i<=NF;i++){ if($i=="passed;") p+=$(i-1); if($i=="failed;") f+=$(i-1) } }
/^error: test failed, to rerun pass/ { print "FAILING: " $0 }
END { printf "\nTOTAL: %d passed, %d FAILED\n", p, f }'
```
A `tail -45` on a `--no-fail-fast` run hid 16 failures earlier today and a merge
went out claiming green.

---

## 6. TRAPS — all measured today, all cost real time

1. **Screenshots are NOT valid A/B evidence in this engine.** Same ROM, same
   deterministic instruction anchor, identical `Logic_Tick`/camera/SST: screens
   differed by **85,352 bytes** across two oracle launches. The §9.7 art-streaming
   page decoder runs on IDLE TIME, so VRAM residency is host-timing dependent
   while game logic is fully deterministic. A/B on deterministic STATE only —
   SST spans, `Camera_*`, `Logic_Tick`, the replay checkpoint net.
   `AB_PROTOCOL.md`'s "visible plane cmps pixel-identical" clause is NOT
   satisfiable here.
2. **A passing control proves nothing unless it varies the nuisance variable.**
   Two separate "IDENTICAL" screenshot readings were collisions (same-session
   runs landing on the same decode/animation state). Re-run controls in a FRESH
   PROCESS.
3. **Whole-WRAM hashes are invalid when code moves sections** — WRAM stores
   `code_addr` for every object, so it necessarily changes.
4. **Watchpoint before `reset` wedges oracle** (`PC=SP=0xFFFFFFFF`, frozen frame
   token; `breakpoint_clear` + `reset` do NOT recover — watchpoints survive
   `breakpoint_clear`). It fires inside the boot RAM clear. Add watchpoints AFTER
   the boot clear and after the poke. Recovery is kill + relaunch.
5. **The frozen tables are PRODUCTION PLACEMENT INPUTS, not gate data.**
   `native.rs:497-503` builds shipped sonic4 from
   `SizeSource::Frozen(load_frozen_table(...))`; `map.toml` anchors only VALIDATE.
   Editing one without the other trips `[map.undeclared-island]` or
   `[map.anchor-absent]`. Move both in ONE commit.
6. **`derive_frozen_table` refuses to drop a vanished boundary label** — renaming
   a section head means hand-renaming its row in all five sonic4-rooted frozen
   tables before `refreeze --freeze` will run.
7. **`DUMMY_REGION` → `pins::CHARACTERS` in the ModuleSpec is NOT safe** despite
   looking byte-neutral. The ROM is unchanged but it shifts the PinnedBaked path
   and breaks tests. Tried and reverted; leave it as `DUMMY_REGION`.
8. **New `.emp` modules CANNOT be pre-registered.** Registering
   `games.sonic4.tails` before the file exists hard-fails the ROM build
   (`no module found under the scan root`). C2/C4 must add the `ModuleSpec` in
   the SAME change that creates the `.emp` file.

---

## 7. Subagent dispatch rule (learned the hard way today)

**Never give a subagent an absolute prohibition.** A brief saying "NEVER edit the
sigil repo" caused an agent to silently DEGRADE the design (jamming the roster
into `player_common`) rather than stop — and report `DONE_WITH_CONCERNS`, which
gets skimmed. Always phrase boundaries as "don't do X without coordination" and
pair them with: *"If X is required to do this cleanly, STOP and report BLOCKED.
Do NOT restructure the work to avoid X. Putting code somewhere it doesn't belong
to satisfy a constraint is a BLOCKED result, not DONE_WITH_CONCERNS."*

Also standing: **subagents must never touch the emulator** (oracle MCP from a
subagent deadlocks the arbiter — the controller does all emulator work), and
`git add` exact paths only, never `-A`.
