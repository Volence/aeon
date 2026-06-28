# Aeon engine/game restructure — Implementation Plan

> **STATUS (2026-06-28):** Tasks 0–2 DONE + merged (the directory wall, ROM byte-identical) plus the
> Task 7 generator/doc/tool cleanup. Tasks 3–6 (boot manifest, def split, RAM split, `games/demo/`)
> are DEFERRED — they hit ROM-layout/sound-bank coupling that needs its own design pass. See the
> spec's "Implementation status" section: `docs/superpowers/specs/2026-06-28-aeon-engine-game-restructure-design.md`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the repo into a hard engine/game wall — reusable `engine/` (zero Sonic-isms) plus `games/sonic4/` and a `games/demo/` starter — with no change to engine behavior.

**Architecture:** Move engine code into subsystem folders; move all player/object/content/entry code into `games/sonic4/`; extract boot boilerplate into the engine and parameterize the boot entry; split the shared def + RAM files along the wall; add a minimal `games/demo/`. Every stage ends with a green build, and RAM/boot stages are Oracle-verified.

**Tech Stack:** AS Macro Assembler (`asw`) 68000 + Z80; `build.sh`; Python build generators; Oracle (Exodus MCP) for runtime verification.

**Spec:** `docs/superpowers/specs/2026-06-28-aeon-engine-game-restructure-design.md`

---

## Conventions for every task

- **Build command (the "test"):** `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` — must end with `Build complete: s4.bin`. A plain `./build.sh` excludes sound and proves nothing about the sound code.
- **Includes are repo-root-relative** (`-i .`), so every moved file's `include "old/path"` must become `include "new/path"` across **all** `.asm`/`.inc`. Each task gives the exact `sed` for its moves.
- **Use `git mv`** (preserves history); never broad `git add` — stage exact paths.
- **Do not touch** the user's WIP files or `tools/ojz_strip_gen.py` (daemon-watched) except in Task 7 where noted.
- Work on branch `feat/engine-game-restructure` off `master`.

### Task 0: Branch + baseline

**Files:** none (git only)

- [ ] **Step 1: Create the feature branch**

```bash
cd /home/volence/sonic_hacks/aeon
git checkout -b feat/engine-game-restructure
```

- [ ] **Step 2: Capture a baseline ROM hash to prove behavior is unchanged**

```bash
SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh && sha256sum s4.bin | tee /tmp/aeon_baseline_sha.txt
```
Expected: `Build complete: s4.bin`. Record the hash — Tasks 1–2 are pure file moves and **should not change the ROM bytes**; compare after each. (Tasks 3–7 legitimately change bytes.)

---

### Task 1: Group engine files into subsystem folders

Move loose `engine/*.asm` and `debug/*` into `engine/{system,compression,sound,debug}/`. `engine/level/`, `engine/objects/`, `engine/player/` (player moves in Task 2), `engine/parallax_macros.inc`, and the root def files stay put this task.

**Files:**
- Create dirs: `engine/system/`, `engine/compression/`, `engine/sound/`, `engine/debug/`
- Move (system): `engine/{boot,vdp_init,z80_init,dma_queue,buffers,vblank,hblank,controllers,game_loop,math}.asm` → `engine/system/`
- Move (compression): `engine/{s4lz_decompress,zx0_decompress}.asm` → `engine/compression/`
- Move (sound): `engine/{z80_sound_driver,sound_fm,sound_psg,sound_sequencer,sound_sfx,sound_api,sound_banked_z80,sound_tables_z80,sfx_blob_win_tab}.asm` → `engine/sound/`
- Move (debug): `debug/{debugger,error_handler,compression_selftest,sound_debug}.asm` → `engine/debug/`
- Modify: every `.asm`/`.inc` that `include`s a moved path (rewrite via sed)

- [ ] **Step 1: Make the directories and move the files**

```bash
cd /home/volence/sonic_hacks/aeon
mkdir -p engine/system engine/compression engine/sound engine/debug
for f in boot vdp_init z80_init dma_queue buffers vblank hblank controllers game_loop math; do git mv engine/$f.asm engine/system/$f.asm; done
for f in s4lz_decompress zx0_decompress; do git mv engine/$f.asm engine/compression/$f.asm; done
for f in z80_sound_driver sound_fm sound_psg sound_sequencer sound_sfx sound_api sound_banked_z80 sound_tables_z80 sfx_blob_win_tab; do git mv engine/$f.asm engine/sound/$f.asm; done
for f in debugger error_handler compression_selftest sound_debug; do git mv debug/$f.asm engine/debug/$f.asm; done
```

- [ ] **Step 2: Rewrite include paths for every moved file**

```bash
cd /home/volence/sonic_hacks/aeon
S='engine/system'; for f in boot vdp_init z80_init dma_queue buffers vblank hblank controllers game_loop math; do
  grep -rlF "\"engine/$f.asm\"" --include='*.asm' --include='*.inc' . | xargs -r sed -i "s#\"engine/$f.asm\"#\"$S/$f.asm\"#g"; done
C='engine/compression'; for f in s4lz_decompress zx0_decompress; do
  grep -rlF "\"engine/$f.asm\"" --include='*.asm' --include='*.inc' . | xargs -r sed -i "s#\"engine/$f.asm\"#\"$C/$f.asm\"#g"; done
SD='engine/sound'; for f in z80_sound_driver sound_fm sound_psg sound_sequencer sound_sfx sound_api sound_banked_z80 sound_tables_z80 sfx_blob_win_tab; do
  grep -rlF "\"engine/$f.asm\"" --include='*.asm' --include='*.inc' . | xargs -r sed -i "s#\"engine/$f.asm\"#\"$SD/$f.asm\"#g"; done
DB='engine/debug'; for f in debugger error_handler compression_selftest sound_debug; do
  grep -rlF "\"debug/$f.asm\"" --include='*.asm' --include='*.inc' . | xargs -r sed -i "s#\"debug/$f.asm\"#\"$DB/$f.asm\"#g"; done
```

- [ ] **Step 3: Build and verify byte-identical ROM**

Run:
```bash
SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh && sha256sum -c <(sed 's# .*#  s4.bin#' /tmp/aeon_baseline_sha.txt)
```
Expected: `Build complete: s4.bin` and `s4.bin: OK` (bytes unchanged — a pure move).
If any `include not found` error: a path missed Step 2 — `grep -rn 'include "engine/<name>.asm"'` and fix, rebuild.

- [ ] **Step 4: Commit**

```bash
git add -A engine/ debug/ && git commit -m "refactor(engine): group loose files into system/compression/sound/debug"
```

---

### Task 2: Move player, game objects, content, and entry into `games/sonic4/`

**Files:**
- Create dirs: `games/sonic4/`
- Move (player): `engine/player/` → `games/sonic4/player/`
- Move (objects): `objects/` → `games/sonic4/objects/`
- Move (data): `data/` → `games/sonic4/data/`
- Move (entry): `main.asm` → `games/sonic4/main.asm`
- Modify: include paths for moved trees; `build.sh` (`MAIN_ASM` + a `GAME` parameter)

- [ ] **Step 1: Move the trees**

```bash
cd /home/volence/sonic_hacks/aeon
mkdir -p games/sonic4
git mv engine/player games/sonic4/player
git mv objects games/sonic4/objects
git mv data games/sonic4/data
git mv main.asm games/sonic4/main.asm
```

- [ ] **Step 2: Rewrite include paths for the moved trees**

```bash
cd /home/volence/sonic_hacks/aeon
grep -rlF '"engine/player/' --include='*.asm' --include='*.inc' . | xargs -r sed -i 's#"engine/player/#"games/sonic4/player/#g'
grep -rlF '"objects/'       --include='*.asm' --include='*.inc' . | xargs -r sed -i 's#"objects/#"games/sonic4/objects/#g'
grep -rlF '"data/'          --include='*.asm' --include='*.inc' . | xargs -r sed -i 's#"data/#"games/sonic4/data/#g'
```
Note: `binclude` directives for binary assets under `data/` are covered by the `"data/` rule (it matches both `include` and `binclude`).

- [ ] **Step 3: Parameterize `build.sh` for the game**

In `build.sh`, change line 5 from:
```bash
MAIN_ASM="main.asm"
```
to:
```bash
GAME="${1:-sonic4}"
MAIN_ASM="games/${GAME}/main.asm"
```

- [ ] **Step 4: Build and verify byte-identical ROM**

Run:
```bash
SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh && sha256sum -c <(sed 's# .*#  s4.bin#' /tmp/aeon_baseline_sha.txt)
```
Expected: `Build complete: s4.bin` and `s4.bin: OK` (still a pure move).
If `include not found`: `grep -rn 'include "data/\|include "objects/\|include "engine/player/'` and fix any missed path.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor(game): move player/objects/data/main into games/sonic4/"
```

---

### Task 3: Extract boot boilerplate to engine + parameterize the boot entry + create `engine.inc`

Split `games/sonic4/main.asm` into: engine-owned boilerplate (vectors, ROM header, reset/init) in `engine/system/`, the engine include list in `engine/engine.inc`, and a slim game manifest. Replace the hardcoded `GameState_OJZScroll_Init` boot jump with a game-supplied entry constant.

**Files:**
- Create: `engine/system/vectors.asm` (68000 vector table + ROM header macro/data, extracted from `main.asm` lines ~1–95)
- Create: `engine/engine.inc` (engine defs + engine code include order)
- Modify: `engine/system/boot.asm:224` (parameterized entry)
- Modify: `games/sonic4/main.asm` (slim manifest)
- Create: `games/sonic4/config/` (holds `GAME_ENTRY_STATE` for now)

- [ ] **Step 1: Read current `games/sonic4/main.asm` and identify the three regions**

Run: `sed -n '1,200p' games/sonic4/main.asm`
Identify: (a) vector table + ROM header + reset/init (top, before the first engine `include`), (b) the include list (engine + game), (c) any inline glue. Region (a) → `engine/system/vectors.asm`; region (b) splits into `engine/engine.inc` (engine includes) and the game manifest (game includes).

- [ ] **Step 2: Create `engine/system/vectors.asm`**

Move the 68000 exception-vector table, ROM header bytes, and reset/init entry (region a) verbatim into `engine/system/vectors.asm`. Keep all labels/values identical (byte-preserving). Leave the actual `include`s in main.asm for now.

- [ ] **Step 3: Create `engine/engine.inc` with the engine include order**

`engine/engine.inc` contains, in this order: engine defs (`engine/constants.asm`, `engine/sound_constants.asm`, `engine/structs.asm`, `engine/macros.asm`, `engine/parallax_macros.inc`, `engine/ram.asm` — these files still live at repo root until Tasks 4–5; reference their **current** paths here and update in those tasks), then `include "engine/system/vectors.asm"`, then every engine code include currently in `main.asm` (system/, compression/, objects/, level/, sound/, debug/) preserving current order and the `SOUND_DRIVER_ENABLED`/`__DEBUG__` conditionals.

> NOTE: at this point the engine def files (`constants.asm` etc.) are still at repo root. In `engine.inc` reference them at their current paths (`"constants.asm"` …); Task 4/5 move them and update `engine.inc` accordingly.

- [ ] **Step 4: Add the game entry constant**

Create `games/sonic4/config/entry.asm` containing:
```
; Game entry state — handed to the engine boot.
GAME_ENTRY_STATE equ GameState_OJZScroll_Init
```

- [ ] **Step 5: Parameterize the boot jump**

In `engine/system/boot.asm` line 224 change:
```
        move.l  #GameState_OJZScroll_Init, (Game_State).w
```
to:
```
        move.l  #GAME_ENTRY_STATE, (Game_State).w
```

- [ ] **Step 6: Slim `games/sonic4/main.asm` to a manifest**

Replace `main.asm` contents with: a short header comment, the game defs/config include (`include "games/sonic4/config/entry.asm"` and later the game constants/ram from Tasks 4–5), `include "engine/engine.inc"`, then the **game** code includes (`games/sonic4/player/*`, `games/sonic4/objects/*`) and the game **data** includes, preserving their current order from the old main.asm. Ensure `GAME_ENTRY_STATE` is defined before `engine.inc` (so boot.asm sees it).

- [ ] **Step 7: Build**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`
Expected: `Build complete: s4.bin`. (Bytes may differ now — include reordering can shift layout; that's fine. Do NOT compare to baseline from here on.)
If `symbol GAME_ENTRY_STATE undefined`: ensure `config/entry.asm` is included before `engine.inc` in the manifest.

- [ ] **Step 8: Oracle boot verification**

Reload the ROM in Oracle and confirm it boots to the OJZ scroll exactly as before (boot path changed):
```
emulator_reload_rom ; emulator_run_frames 120 ; emulator_screenshot
```
Expected: same first-playable frame as pre-restructure (OJZ scene renders).

- [ ] **Step 9: Commit**

```bash
git add -A && git commit -m "refactor(boot): engine owns vectors/init via engine.inc; parameterized boot entry"
```

---

### Task 4: Split shared def files along the wall

Move engine def files under `engine/`; bisect `constants.asm` and `sound_constants.asm` so the game slice (object IDs, ring/monitor/spindash, OJZ, song/SFX IDs) lives in `games/sonic4/config/`.

**Files:**
- Move: `structs.asm`, `macros.asm` → `engine/`
- Move + bisect: `constants.asm` → `engine/constants.asm` (engine) + `games/sonic4/config/constants.asm` (game)
- Move + bisect: `sound_constants.asm` → `engine/sound_constants.asm` (engine) + `games/sonic4/config/sound_ids.asm` (game)
- Modify: `engine/engine.inc` and `games/sonic4/main.asm` include paths

- [ ] **Step 1: Move the all-engine def files**

```bash
cd /home/volence/sonic_hacks/aeon
git mv structs.asm engine/structs.asm
git mv macros.asm  engine/macros.asm
```

- [ ] **Step 2: Bisect `constants.asm`**

Read `constants.asm`. Move game-specific definitions (game object IDs, ring/monitor/spindash constants, OJZ-specific constants) into a new `games/sonic4/config/constants.asm`; keep engine constants (VRAM layout, hardware registers, object-system offsets, render flags) in a moved `engine/constants.asm`:
```bash
git mv constants.asm engine/constants.asm   # then cut the game slice out into the file below
```
Create `games/sonic4/config/constants.asm` with the cut game definitions. Preserve every name/value exactly (no renames).

- [ ] **Step 3: Bisect `sound_constants.asm`**

Same pattern: engine driver constants (MEV opcodes, channel/FM/PSG register defs) stay in `engine/sound_constants.asm`; the game's song/SFX **ID** table moves to `games/sonic4/config/sound_ids.asm`:
```bash
git mv sound_constants.asm engine/sound_constants.asm   # then cut song/SFX IDs into the file below
```

- [ ] **Step 4: Update include paths**

In `engine/engine.inc`, update the def includes to the new engine paths:
```
include "engine/constants.asm"
include "engine/sound_constants.asm"
include "engine/structs.asm"
include "engine/macros.asm"
```
In `games/sonic4/main.asm`, add the game-config includes **before** `engine.inc` (engine code references engine defs; game defs that engine doesn't need can come after — but IDs used by game code must precede that code):
```
include "games/sonic4/config/constants.asm"
include "games/sonic4/config/sound_ids.asm"
```

- [ ] **Step 5: Build**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`
Expected: `Build complete: s4.bin`.
If `symbol <NAME> undefined`: a constant landed on the wrong side of the bisect — move that single def to the side that defines/uses it, rebuild. If `symbol redefined`: it was copied to both files — delete the duplicate.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "refactor(defs): split constants/sound_constants/structs/macros along engine|game wall"
```

---

### Task 5: Split RAM ownership

`ram.asm` becomes an engine block exporting `Engine_RAM_End`, plus a game block that continues the phase.

**Files:**
- Move + split: `ram.asm` → `engine/ram.asm` (engine block) + `games/sonic4/config/ram.asm` (game block)
- Modify: `engine/engine.inc` (include `engine/ram.asm`), `games/sonic4/main.asm` (include game ram after engine.inc)

- [ ] **Step 1: Inspect the current RAM map**

Run: `sed -n '1,478p' ram.asm` — identify the boundary between engine RAM (camera, plane buffer, object pool, DMA queue, sound state, tile cache, buffers) and game/player RAM (player state, game vars, OJZ state). Note the `phase`/`dephase` structure and even-alignment padding.

- [ ] **Step 2: Create `engine/ram.asm`**

```bash
git mv ram.asm engine/ram.asm
```
Edit `engine/ram.asm` to contain only the engine RAM block; at its end (still inside the same `phase` region, before `dephase`) export the cursor:
```
Engine_RAM_End equ *
```
Ensure the engine block ends on an even address (pad with one `ds.b` → even if needed, per the even-alignment rule).

- [ ] **Step 3: Create `games/sonic4/config/ram.asm`**

The game block continues the phase from `Engine_RAM_End`:
```
        phase Engine_RAM_End
; ... game/player RAM fields cut from the old ram.asm ...
        dephase
```
Move the game/player RAM fields here verbatim (same field names/sizes/order).

- [ ] **Step 4: Wire includes**

In `engine/engine.inc` ensure `include "engine/ram.asm"` is in the def section (after constants/structs, where `ram.asm` was). In `games/sonic4/main.asm` add `include "games/sonic4/config/ram.asm"` **after** `include "engine/engine.inc"` (so `Engine_RAM_End` is defined first).

- [ ] **Step 5: Build + assert check**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`
Expected: `Build complete: s4.bin`, no `phase`/overflow assertion errors, RAM summary line prints (e.g. `RAM: …KB/64KB`).

- [ ] **Step 6: Oracle runtime verification (RAM layout changed — build-green is not sufficient)**

```
emulator_reload_rom ; emulator_run_frames 300 ; emulator_screenshot
```
Then press A and run the player/sound for a few seconds:
```
emulator_press A ; emulator_run_frames 200 ; emulator_screenshot
```
Expected: OJZ scene renders, player responds, music/SFX play — identical behavior to pre-split. If anything is corrupt (garbage tiles, wrong scroll, silence), a RAM field overlapped — recheck the engine/game boundary and even-alignment, rebuild, re-verify.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "refactor(ram): engine block exports Engine_RAM_End; game RAM continues the phase"
```

---

### Task 6: Add `games/demo/` — minimal starter that boots a test object

Prove the engine boots, spawns, and renders with zero Sonic content.

**Files:**
- Create: `games/demo/main.asm` (manifest), `games/demo/config/entry.asm`, `games/demo/config/ram.asm`, `games/demo/objects/demo_object.asm`, a minimal placeholder sprite asset (uncompressed) under `games/demo/data/`

- [ ] **Step 1: Author the demo entry GameState + test object**

Create `games/demo/objects/demo_object.asm` defining a single object that uses the engine object system (`engine/objects/core.asm` spawn + `sprites.asm` render) to draw one placeholder sprite at a fixed position. Create `games/demo/config/entry.asm`:
```
; Demo entry — boot to a backdrop + one test object.
GAME_ENTRY_STATE equ GameState_DemoBoot
```
Define `GameState_DemoBoot` (in `demo_object.asm` or a small `games/demo/boot.asm`) to: set a backdrop color, init the object pool, spawn one `demo_object`. `; TODO: your game starts here` comment beside the spawn.

- [ ] **Step 2: Author `games/demo/config/ram.asm`**

```
        phase Engine_RAM_End
; demo has no extra game RAM yet
        dephase
```

- [ ] **Step 3: Author `games/demo/main.asm` (the ~30-line manifest)**

```
; Aeon demo game — minimal starter. Copy this folder to start a new game.
        include "games/demo/config/entry.asm"
        include "engine/engine.inc"
        include "games/demo/config/ram.asm"
        include "games/demo/objects/demo_object.asm"
```
Match whatever def-ordering Tasks 4–5 established (entry/config before `engine.inc`; ram after). Provide a minimal placeholder sprite/mapping the demo object references (uncompressed, shipped under `games/demo/data/`).

- [ ] **Step 4: Build the demo**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh demo`
Expected: `Build complete: demo.bin`.
If `symbol GameState_OJZScroll_Init undefined` leaks in: an engine file still references a Sonic symbol → that reference belongs in the game, move it (this is the wall doing its job).

- [ ] **Step 5: Oracle smoke test**

Load `demo.bin` in Oracle:
```
emulator_reload_rom ; emulator_run_frames 120 ; emulator_screenshot
```
Expected: backdrop color + one placeholder sprite visible. This proves engine agnosticism.

- [ ] **Step 6: Commit**

```bash
git add -A games/demo && git commit -m "feat(demo): minimal games/demo starter — boots + spawns one test object"
```

---

### Task 7: Cleanup — generators, docs, ctags, vestigial dirs

**Files:**
- Modify: `tools/*.py` generator output/input paths (`data/…` → `games/sonic4/data/…`)
- Modify: `tools/ojz_strip_gen.py` (daemon-watched — see step), `CLAUDE.md`, `.ctags.d/as68k.ctags`
- Remove/fold: `source/` (vestigial)

- [ ] **Step 1: Update generator paths**

```bash
cd /home/volence/sonic_hacks/aeon
grep -rln "data/generated\|data/editor\|'data/\|\"data/" tools/ --include='*.py' | grep -v ojz_strip_gen.py | xargs -r sed -i 's#data/generated#games/sonic4/data/generated#g; s#data/editor#games/sonic4/data/editor#g'
```
Review each changed file with `git diff tools/` to confirm only path strings changed.

- [ ] **Step 2: Run the generator test suite**

Run: `python3 -m pytest tools/ -q`
Expected: pass (or same pass set as before the restructure). Fix any path that points at the old tree.

- [ ] **Step 3: Update `tools/ojz_strip_gen.py` (daemon-watched — coordinate)**

Confirm the autocommit daemon is not running (`pgrep -af inotify`), then update its two `data/` path references and the 2 stale `s4_engine` comments to the new tree. Commit immediately so the daemon (if it wakes) sees a consistent state.

- [ ] **Step 4: Fold or remove `source/`**

`source/` held only `source/data/ojz_strips/` (intermediate collision strips). If regenerated by a generator, delete it; otherwise move under the game tree:
```bash
git rm -r source/   # if regenerated  — OR —  git mv source/data/ojz_strips games/sonic4/data/ojz_strips
```
Confirm via `grep -rn 'source/' build.sh tools/ engine/ games/` that nothing references it; fix any reference.

- [ ] **Step 5: Update docs + ctags**

Update `CLAUDE.md` (paths/structure section) and `.ctags.d/as68k.ctags` comment to the new layout. Update `docs/ENGINE_ARCHITECTURE.md` directory references.

- [ ] **Step 6: Final full build + Oracle regression**

```bash
SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh && SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh demo
```
Expected: both `s4.bin` and `demo.bin` build. In Oracle, verify `s4.bin` boots/renders/plays sound and `demo.bin` shows its test object.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "refactor(tools+docs): repoint generators/docs/ctags to new tree; drop vestigial source/"
```

---

### Task 8: Merge

- [ ] **Step 1: Confirm clean tree + both ROMs build green** (Task 7 step 6 passed).
- [ ] **Step 2: Merge to master**

```bash
git checkout master && git merge --ff-only feat/engine-game-restructure
```
If not fast-forwardable, rebase the branch on master first.

- [ ] **Step 3: Push**

```bash
git push origin master
```

- [ ] **Step 4: Post-merge coordination note (user-side):** the autocommit daemon's watch path must move to `games/sonic4/data/editor/ojz`; Oracle is unaffected (ROM still `s4.bin` at repo root).

---

## Notes / risks
- Tasks 1–2 must be byte-identical to baseline; if not, an include resolved to a different file — investigate before proceeding.
- Tasks 3–7 change bytes legitimately; rely on Oracle for behavior parity, not the hash.
- The user's uncommitted WIP (daemon-watched `data/editor/ojz`, `data/sprites/`, research docs, `forest_bg_gen.py`) moves under `games/sonic4/data/` with the `git mv data` in Task 2; it stays uncommitted (a tree move carries working-tree changes). Do not stage it.
- Even-alignment in RAM (Task 5) is load-bearing: an odd `ds.b` run address-errors the next word field at runtime even though the build passes.
