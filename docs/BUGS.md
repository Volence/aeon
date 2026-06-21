# Known Bugs

Open defects with reproduction notes and any captured live-emulator evidence. Newest first.
(Distinct from `DEFERRED_WORK.md`, which tracks deferred *features*, not defects.)

---

## BUG-001 — Section-streaming rendering corruption (background → garbage tiles + red field)

**Status:** OPEN. **Severity:** high (game becomes unplayable in that area). **Reproducibility:** INTERMITTENT
— happens "every now and then," often (but not always) right after a spindash. The user could NOT reliably
re-trigger it, so the live evidence below was captured from a single frozen occurrence (2026-06-21) and is the
primary record — a restart loses it.

**Screenshot:** `docs/research/bug_streaming_corruption_2026-06-21.png` — the whole background is a RED field
filled with a repeating grid of garbage tiles; the Sonic **sprite is intact**; the DEBUG HUD reads
`COL: need layout co…`.

### Symptom
The BACKGROUND planes render garbage tiles over a red backdrop. Sprites (player) are unaffected.

### NOT a crash, NOT sound
- 68k `PC = 0x1DD4` — the normal main-loop wait (`Process_DMA_Critical` region). CPU running fine; SR=$2600.
- The player sprite renders correctly → sprite VRAM + sprite palette are intact. This is a **plane / level-art /
  backdrop** corruption only.
- Unrelated to the sound work in this session.

### Live-emulator evidence (frozen frame, 2026-06-21)
- **Player** (object list): x=1301 (`$0515`), y=694 (`$02B6`). **Vel 0,0** (stopped). In section **(0,0)**.
- **Camera_X = `$04770000`, Camera_Y = `$02420000`** (16.16). Cam X=1143 — still inside section 0
  (`SECTION_SIZE = $0800` = 2048px), so `Sec (0,0)` is CORRECT; this is NOT a section-index mismatch.
- **`Section_Stream_State` ($FFA8EC): section 0 = `$02` (SS_RESIDENT), section 1 = `$02`, rest `$00` (IDLE).**
  → the engine believes section 0 (the player's section) is fully loaded.
- **`Slot_Section_Map` ($FFA8E0): slot0=(0,0) slot1=(1,0) slot2=(0,0) slot3=(0,0).**
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
- `Section_Plane_Dirty` ($FFA8EA) = `$00` (no full redraw pending). `Section_Teleport_Guard` ($FFA8E9) = `$00`.
- `Section_Top_Row_Written` = `$0002`, `Section_Bottom_Row_Written` = `$003B`. `Lag_Frame_Count` = `$28` (40).
- HUD overlay: `COL: need layout co…` — the engine itself flagged that the **collision layout for the player's
  position is not loaded.**

### Diagnosis
**Section-streaming state↔data DESYNC: section 0 is flagged `SS_RESIDENT`, but its art (VRAM tiles + RAM
nametable cache) and collision LAYOUT are not actually loaded.** The engine even self-detects the missing
collision (`COL: need layout`). So a streaming event marked the section resident WITHOUT (re)loading its
art/collision, and the fill/DMA then drew the empty/blank cache → garbage tiles over the red backdrop.

### Leading suspects (unconfirmed)
1. **Teleport/rebase "pure rebase, no redraw" path** treating the section as already-resident and SKIPPING the
   art/collision (re)load in an edge case where the data wasn't actually present. (See `engine/level/section.asm`
   teleport/rebase; memory `project_teleport_rebase` — "teleports are pure rebases, reinit/redraw removed".)
2. **`Decomp_Buffer` aliases `Tile_Cache_Nametable`** (ram.asm:28). A decompress during the streaming event
   would overwrite the nametable cache → blank/garbage cache → blank/garbage VRAM after the next fill/DMA.
3. **Race/timing edge case** — the intermittency + the spindash trigger (fast camera jump stressing the
   streamer) point to a timing window, not a deterministic path.

### Recommended next step (its own focused session)
Reproduce with a **watchpoint** to trap the corrupting moment:
- Watch `Section_Stream_State + 0` (section 0's state byte) for a write to `$02` (resident) and check, at that
  instant, whether the art-load / collision-load actually ran. OR
- Watch the `Tile_Cache_Nametable` region for the write that blanks it (catch the aliased decomp clobber). OR
- Watch CRAM line-0 index-0 for the `$000E` write (find whether it's the debug warning or corruption).
Then trace backward from the trigger (spindash launch → camera jump → which section routine fires).
This is an **engine/section-streaming** bug — separate from sound. Do NOT guess a fix; trace the corrupting write.
