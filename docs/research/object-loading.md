# Object Loading Research (Load_Object — §3.7)

## Reference Analysis

### Sonic-lineage (S.C.E., sonic_hack)
- **6 bytes per layout entry**: X word, Y word (+ flip bits in high 3), object ID byte, subtype byte
- **Camera-relative dual-pointer scan**: front/back pointers walk X-sorted list, quantized to $80-pixel chunks
- **Global respawn table**: 256-1024 bytes, 1 byte per entry, bit 7 = "loaded" flag
- **Global object ID namespace**: 1-byte ID indexes into Obj_Index table of code pointers (word offsets)
- **No data blocks**: objects manually set all fields in their init routines (Option C)
- S.C.E. adds Y-axis scanning pass and word-sized respawn indices
- S.C.E. has `Seek_Object_Manager` for teleportation/camera jumps

### Action games (Batman & Robin, Gunstar Heroes, Alien Soldier, Thunder Force IV)
- **No level layout parsing** — all objects spawned via code/scripts at runtime
- Batman: bytecode interpreter drives spawning, linked-list O(1) alloc
- Gunstar/Alien Soldier: single/dual link fields ($58/$5C) for multi-part boss coordination
- Thunder Force IV: type-segregated 32-byte pools, zero-branch hot loops per type
- None relevant to level object loading, but boss/dynamic spawning patterns inform child creation

### Vectorman
- **12-byte dispatch entries**: type/flags, parameter, update pointer, render pointer
- Split update/render allows skipping render for invisible objects
- Hardcoded data addresses per type — speed over flexibility

## Design Decisions

### Data block format (Option A — self-contained)
Each object type has a ROM data block containing code pointer + format byte + field data.
Type table entries are pointers to data blocks. One lookup gives everything.

### Format byte
Bits flag which optional fields are present in the data block:
- bit 0: velocity (x_vel, y_vel)
- bit 1: collision (width, height, type)
- bit 2: animation (anim_table)
- bit 3: subtype (flag only — copy from caller)
- bit 4: render_flags
- bit 5: priority
- bit 7: art requirements (DEFERRED — needs AllocVRAM)

### Always-present fields
- code_addr (word) — behavior routine
- mappings (long) — sprite mappings pointer (dc.l 0 for invisible objects like pathswitchers)
- art_tile (word) — TEMPORARY fallback until AllocVRAM exists

### Deferred
- AllocVRAM integration (bit 7) — stub with hardcoded art_tile for now
- Section lifecycle integration (§4.9)
- Respawn tracking (§4.9 rolling state)
- 4-byte compact layout parsing (needs section-local coordinates)
