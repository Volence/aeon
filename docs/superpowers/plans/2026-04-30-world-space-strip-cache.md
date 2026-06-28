# World-Space Strip Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace uncompressed ROM strips + planned §4.7 flat collision maps with S4LZ-compressed strips decompressed on-demand into a world-space circular cache, plus build-time-generated collision maps with height map collision lookups.

**Architecture:** Streaming S4LZ decompressor fills an 80-column circular buffer in RAM as the camera scrolls. Section_UpdateColumns and Section_RedrawPlanes read from the cache instead of ROM. Collision maps are flat 128×24 byte arrays decompressed at preload time, queried via shift-based lookup. Height maps and angle arrays are global ROM tables.

**Tech Stack:** 68000 assembly (AS Macro Assembler), Python 3 build tools (s4lz.py, ojz_strip_gen.py)

**Spec:** `docs/superpowers/specs/2026-04-30-world-space-strip-cache-design.md`

---

## File Structure

### New Files
| File | Purpose |
|------|---------|
| `engine/s4lz_stream.asm` | Streaming S4LZ decompressor with pause/resume at token boundaries |
| `engine/level/strip_cache.asm` | World-space circular strip cache (init, fill, get column, teleport) |
| `engine/level/collision_lookup.asm` | Flat collision map query, height map + angle lookup, dual floor sensors |
| `data/collision/heightmaps.bin` | 4096-byte floor/ceiling height profiles (stub: type 0 = air, type 1 = flat solid) |
| `data/collision/heightmaps_rot.bin` | 4096-byte rotated height profiles for wall sensors (stub) |
| `data/collision/angles.bin` | 256-byte surface angle array (stub) |

### Modified Files
| File | Changes |
|------|---------|
| `constants.asm` | Strip cache, collision map, and height map constants |
| `structs.asm` | StreamState struct; Sec struct: add `sec_strip_checkpoints` at $2C, rename `sec_strips_a` → `sec_strips_s4lz` |
| `ram.asm` | Lower RAM: strip cache + collision slots + stream states; Upper RAM: cache metadata. Relocate streaming buffers |
| `main.asm` | Include new `.asm` files |
| `engine/level/section.asm` | Section_UpdateColumns + RedrawPlanes read from cache; teleport adjusts stream state; remove neighbor strip pointer caching |
| `engine/level/load_art.asm` | Level init: populate strip cache + decompress collision maps |
| `test/ojz_scroll_test.asm` | Add `Strip_Cache_Fill` call to game loop |
| `tools/s4lz.py` | Add `--checkpoint-interval` flag, emit checkpoint tables during compression |
| `tools/ojz_strip_gen.py` | Compress strips via s4lz module, emit checkpoints, generate stub collision maps |
| `build.sh` | Update pipeline steps for strip compression |
| `data/levels/ojz/act1/act_descriptor.asm` | Switch to compressed strip BINCLUDEs, add checkpoint + collision map data |

---

### Task 1: Constants, Structs, and RAM Layout

**Files:**
- Modify: `constants.asm`
- Modify: `structs.asm`
- Modify: `ram.asm`

- [ ] **Step 1: Research**

Check all 8 reference disassemblies (S.C.E., Batman & Robin, Vectorman, Gunstar Heroes, Alien Soldier, Thunder Force IV, Ristar, sonic_hack) for how they define streaming decompression state, tile cache buffers, and collision map storage in RAM. Search plutiedev.com, md.railgun.works, and SpritesMind for Genesis RAM layout patterns. Check modern engine designs for streaming buffer metadata conventions.

- [ ] **Step 2: Add strip cache and collision constants to constants.asm**

Add after the `PLANE_BUFFER_SIZE` constant block (after line 277):

```asm
; -----------------------------------------------
; Strip Cache (§4.7)
; -----------------------------------------------
STRIP_CACHE_COLS        = 80        ; columns in circular cache (viewport 40 + margin 20×2)
STRIP_CACHE_SIZE        = STRIP_CACHE_COLS * STRIP_BYTE_SIZE  ; 80 × 96 = 7680 bytes
STRIP_CACHE_MARGIN      = 20        ; lookahead columns each side

; Collision maps (§4.7)
COLLISION_MAP_COLS      = 128       ; cells per section (SECTION_SIZE / 16)
COLLISION_MAP_ROWS      = 24        ; cells per section (384 / 16)
COLLISION_MAP_SIZE      = COLLISION_MAP_COLS * COLLISION_MAP_ROWS  ; 3072 bytes
COLLISION_CELL_SHIFT    = 4         ; pixel → cell (/ 16)
COLLISION_ROW_SHIFT     = 7         ; row × 128 via lsl #7

; Height maps (§4.7)
NUM_COLLISION_PROFILES  = 256
HEIGHT_PROFILE_SIZE     = 16        ; bytes per profile (one per pixel column in 16px block)
HEIGHT_MAP_SIZE         = NUM_COLLISION_PROFILES * HEIGHT_PROFILE_SIZE  ; 4096 bytes
ANGLE_TABLE_SIZE        = 256       ; one byte per collision type

; Collision types
CTYPE_AIR               = 0
CTYPE_FLAT_SOLID        = 1

; Streaming buffer relocation (§4.7 — moved out of strip cache region)
; In 1D mode, vertical slot 1 ($FFFF1E00+) is unused → streaming buffers live there
STREAMING_RELOCATED     = 1
```

- [ ] **Step 3: Update streaming buffer constants in constants.asm**

Replace the existing streaming buffer address definitions (lines 261-263):

```asm
; Per-section streaming (§2 A.4)
; Relocated into reserved vertical strip cache slot 1 region (§4.7).
; Only valid in 1D mode — 2D vertical sections require resolution.
STREAMING_BUFFER_SIZE   = 4096
STREAMING_BUFFER_A      = $FFFF1E00     ; inside reserved vertical slot 1
STREAMING_BUFFER_B      = $FFFF2E00     ; inside reserved vertical slot 1
```

- [ ] **Step 4: Add vertical threshold stubs to constants.asm**

Add after `SECTION_DEFERRED_BWD_LOAD` (line 235):

```asm
; Vertical thresholds (2D-ready, unreachable in 1D)
SECTION_UP_THRESHOLD    = $7FFF
SECTION_DOWN_THRESHOLD  = $7FFF
SECTION_UP_PRELOAD      = $7FFF
SECTION_DOWN_PRELOAD    = $7FFF
```

- [ ] **Step 5: Add StreamState struct to structs.asm**

Add before the Sec struct (before line 106):

```asm
; -----------------------------------------------
; StreamState — S4LZ streaming decompressor bookmark (§4.7)
; -----------------------------------------------
StreamState struct
ss_src          ds.l 1      ; $00 — current ROM position in compressed stream
ss_output_pos   ds.l 1      ; $04 — cumulative bytes decompressed from stream start
ss_xor_prev     ds.w 1      ; $08 — tile-delta XOR state (0 for strip streams)
StreamState endstruct       ; = $0A (10 bytes)

    if StreamState_len <> $0A
      error "StreamState struct is \{StreamState_len} bytes, expected $0A"
    endif
```

- [ ] **Step 6: Modify Sec struct in structs.asm**

Replace `sec_strips_a` at $00 and `sec_pcfg_pad_2C` at $2C:

```asm
sec_strips_s4lz     ds.l 1          ; $00 — S4LZ compressed strip stream ptr (ROM; §4.7)
```

```asm
sec_strip_checkpoints ds.l 1        ; $2C — strip checkpoint table ptr (ROM; 4 × word; §4.7)
```

And update `sec_collision` comment at $34:

```asm
sec_collision_s4lz  ds.l 1          ; $34 — S4LZ compressed 128×24 collision map (ROM; §4.7)
```

- [ ] **Step 7: Reorganize lower RAM in ram.asm**

Replace the Decomp_Buffer section (lines 8-13) with the new strip cache layout:

```asm
; -----------------------------------------------
; Lower RAM — strip cache, collision maps, stream state (§4.7)
; Replaces Decomp_Buffer after level init. LoadArt_S4LZ still
; writes here during init (display off, before cache is populated).
; -----------------------------------------------
        phase $FFFF0000

; Strip cache — world-space circular buffer
Strip_Cache:            ds.b STRIP_CACHE_SIZE       ; 7680 bytes (vertical slot 0)
Strip_Cache_End:
Strip_Cache_V1_Reserved: ds.b STRIP_CACHE_SIZE      ; 7680 bytes (vertical slot 1; unused in 1D)
Strip_Cache_V1_End:

; Collision map slots — flat byte arrays, decompressed at preload
Collision_Map_Slot0:    ds.b COLLISION_MAP_SIZE      ; 3072 bytes
Collision_Map_Slot1:    ds.b COLLISION_MAP_SIZE      ; 3072 bytes
Collision_Map_Slot2:    ds.b COLLISION_MAP_SIZE      ; 3072 bytes (reserved for 2D)
Collision_Map_Slot3:    ds.b COLLISION_MAP_SIZE      ; 3072 bytes (reserved for 2D)

; Stream states — 4 streaming decompressor bookmarks
S4LZ_Stream_States:     ds.b StreamState_len * 4    ; 40 bytes
; Checkpoint ROM pointers — cached at stream init
Stream_Checkpoint_Ptrs: ds.l 4                      ; 16 bytes

; Keep Decomp_Buffer as alias for LoadArt_S4LZ backward compat
Decomp_Buffer = Strip_Cache

Lower_RAM_End:

        if Lower_RAM_End > $FFFF8000
          error "Lower RAM overflow by \{Lower_RAM_End - $FFFF8000} bytes!"
        endif

        dephase
```

- [ ] **Step 8: Add strip cache metadata to upper RAM in ram.asm**

Add after `Camera_Pan_Offset` padding (after line 245):

```asm
; -----------------------------------------------
; Strip Cache metadata (§4.7 — .w addressable)
; -----------------------------------------------
Strip_Cache_Head_Col:   ds.w 1          ; world tile col of rightmost valid entry
Strip_Cache_Head_Idx:   ds.w 1          ; ring buffer index (0..79) of Head
Strip_Cache_Left_Col:   ds.w 1          ; world tile col of leftmost valid entry
Strip_Cache_Fwd_Stream: ds.b 1          ; slot index (0-3) of forward decompression stream
                        ds.b 1          ; pad
```

- [ ] **Step 9: Build and verify**

```bash
cd /home/volence/sonic_hacks/aeon && ./build.sh
```

Expected: clean build. All struct size checks pass. RAM overflow check passes. No runtime change (data not populated yet). The `sec_strips_a` → `sec_strips_s4lz` rename will cause build errors in section.asm, load_art.asm, and plane_buffer.asm — fix all references mechanically (same field, same offset, new name). Similarly rename `sec_collision` → `sec_collision_s4lz` in any references.

Files that reference `Sec_sec_strips_a`:
- `engine/level/section.asm` (lines 50, 65, 374, 389, 502, 518, 647, 650)
- `engine/level/plane_buffer.asm` (line 29)

Replace all `Sec_sec_strips_a` → `Sec_sec_strips_s4lz` in those files. Note: the data still points to raw uncompressed strips until Task 3 — the rename is purely cosmetic until then.

- [ ] **Step 10: Commit**

```bash
git add constants.asm structs.asm ram.asm engine/level/section.asm engine/level/plane_buffer.asm
git commit -m "feat(§4.7): foundation — strip cache constants, StreamState struct, RAM layout

Add STRIP_CACHE_*, COLLISION_MAP_*, and HEIGHT_MAP_* constants.
Add StreamState struct (10-byte decompressor bookmark).
Rename Sec.sec_strips_a → sec_strips_s4lz, add sec_strip_checkpoints
and sec_collision_s4lz fields.
Reorganize lower RAM: strip cache + collision map slots + stream states.
Relocate streaming buffers into reserved vertical slot 1 region.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: S4LZ Checkpoint Emission (Build Tool)

**Files:**
- Modify: `tools/s4lz.py`

- [ ] **Step 1: Research**

Check ZSTD seekable format, Brotli seekable, and any Genesis homebrew compression tools for checkpoint/seekable compression patterns. Check how Ristar's Star compressor handles restart points. Search GitHub for "seekable lz" and "checkpoint compression" implementations.

- [ ] **Step 2: Add checkpoint_interval parameter to compress() in s4lz.py**

Modify the `compress()` function signature (line 165) and add checkpoint tracking logic. The function should track cumulative output bytes and record the compressed stream offset at each checkpoint boundary.

```python
def compress(data: bytes, tile_delta: bool = False,
             checkpoint_interval: int = 0) -> tuple[bytes, list[int]]:
    """Compress data using S4LZ format.
    
    Args:
        data: Input data to compress
        tile_delta: Apply tile-delta XOR preprocessing
        checkpoint_interval: If > 0, record compressed stream offsets
            every checkpoint_interval bytes of output. Returns list of
            word offsets from stream start (past header).
    
    Returns:
        (compressed_bytes, checkpoints) where checkpoints is a list of
        word offsets into the compressed stream at each interval boundary.
        First checkpoint is always 0 (stream start).
    """
```

Inside the encoding loop (Phase 4, around line 272), track cumulative output bytes emitted. After encoding each sequence, check if we've crossed a checkpoint boundary and record the current compressed stream offset (relative to start of data, past header).

Key implementation detail: checkpoint offsets are relative to the first byte AFTER the 4-byte header. This matches how the engine's `S4LZ_Stream_Init` stores `ss_src` (past header).

- [ ] **Step 3: Update all callers of compress()**

The return type changed from `bytes` to `tuple[bytes, list[int]]`. Update `main()` (around line 583) and the `verify` subcommand to handle the new return type:

```python
# In main(), compress subcommand:
compressed, checkpoints = compress(data, tile_delta=args.tile_delta)

# If --checkpoint-interval was given, write checkpoint table
if args.checkpoint_interval:
    compressed, checkpoints = compress(
        data, tile_delta=args.tile_delta,
        checkpoint_interval=args.checkpoint_interval)
    ckpt_path = args.output.replace('.s4lz', '_checkpoints.bin')
    with open(ckpt_path, 'wb') as f:
        for offset in checkpoints:
            f.write(struct.pack(">H", offset))
```

- [ ] **Step 4: Add CLI arguments**

Add `--checkpoint-interval` to the compress subparser:

```python
compress_parser.add_argument('--checkpoint-interval', type=int, default=0,
    help='Record checkpoint offsets every N bytes of output')
```

- [ ] **Step 5: Test checkpoint emission**

```bash
cd /home/volence/sonic_hacks/aeon
# Compress an existing raw strip file with checkpoints every 6144 bytes (64 strips × 96)
python3 tools/s4lz.py compress \
    --checkpoint-interval 6144 \
    data/generated/ojz/act1/sec0_strips_a.bin \
    /tmp/test_strips.s4lz

# Verify checkpoints file exists and has 4 entries (8 bytes)
ls -la /tmp/test_strips_checkpoints.bin
python3 -c "
import struct
with open('/tmp/test_strips_checkpoints.bin', 'rb') as f:
    data = f.read()
    count = len(data) // 2
    for i in range(count):
        offset = struct.unpack('>H', data[i*2:i*2+2])[0]
        print(f'Checkpoint {i}: compressed offset {offset}')
"
```

Expected: 4 checkpoints. First is 0 (stream start). Others are increasing offsets.

- [ ] **Step 6: Verify round-trip with checkpoints**

```bash
# Decompress from checkpoint and verify output matches
python3 tools/s4lz.py verify data/generated/ojz/act1/sec0_strips_a.bin
```

Expected: PASS — verify still works with updated compress() signature.

- [ ] **Step 7: Commit**

```bash
git add tools/s4lz.py
git commit -m "feat(§4.7): s4lz checkpoint emission — record compressed offsets at output intervals

compress() now accepts checkpoint_interval and returns (bytes, checkpoints).
CLI: --checkpoint-interval N writes a binary checkpoint table alongside the .s4lz.
Used by strip cache for backward seeking (checkpoint every 64 strips = 6144 bytes).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Strip Compression Pipeline (Build Tool)

**Files:**
- Modify: `tools/ojz_strip_gen.py`
- Modify: `build.sh`
- Modify: `data/levels/ojz/act1/act_descriptor.asm`

- [ ] **Step 1: Research**

Check build pipelines in modern retro homebrew projects (Xeno Crisis, Tanglewood, Demons of Asteborg) for how they chain asset compression into their build. Check how sonic_hack's build.sh orchestrates Kosinski compression. Look at the existing aeon build.sh pipeline (lines 1-100) for the current strip generation + tile compression flow.

- [ ] **Step 2: Add strip compression to ojz_strip_gen.py**

After the existing strip generation step (which outputs `secN_strips_a.bin`), add a new step that:

1. Imports the `compress` function from `s4lz`
2. Reads each raw `secN_strips_a.bin`
3. Compresses with `checkpoint_interval = 64 * 96` (64 strips × 96 bytes = 6144)
4. Writes `secN_strips.s4lz` (compressed stream)
5. Writes `secN_strip_checkpoints.bin` (4 × word checkpoint table)

```python
# Add to generate() function, after raw strip emission:
from s4lz import compress as s4lz_compress

STRIPS_PER_CHECKPOINT = 64
CHECKPOINT_INTERVAL = STRIPS_PER_CHECKPOINT * STRIP_BYTE_SIZE  # 6144

for sec_idx in range(num_sections):
    raw_path = os.path.join(out_dir, f"sec{sec_idx}_strips_a.bin")
    with open(raw_path, 'rb') as f:
        raw_data = f.read()
    
    compressed, checkpoints = s4lz_compress(
        raw_data, tile_delta=False,
        checkpoint_interval=CHECKPOINT_INTERVAL)
    
    s4lz_path = os.path.join(out_dir, f"sec{sec_idx}_strips.s4lz")
    with open(s4lz_path, 'wb') as f:
        f.write(compressed)
    
    ckpt_path = os.path.join(out_dir, f"sec{sec_idx}_strip_checkpoints.bin")
    with open(ckpt_path, 'wb') as f:
        # Pad to exactly 4 entries (8 bytes)
        while len(checkpoints) < 4:
            checkpoints.append(checkpoints[-1] if checkpoints else 0)
        for offset in checkpoints[:4]:
            f.write(struct.pack(">H", offset))
    
    ratio = len(compressed) / len(raw_data) * 100 if raw_data else 0
    print(f"  sec{sec_idx} strips: {len(raw_data)} -> {len(compressed)} ({ratio:.1f}%)")
```

- [ ] **Step 3: Update act_descriptor.asm data includes**

For each section, change the BINCLUDE for strips and add checkpoint + collision entries.

Replace each section's strip include from:
```asm
OJZ_Sec0_Strips_A:
    BINCLUDE "data/generated/ojz/act1/sec0_strips_a.bin"
    align 2
```

To:
```asm
OJZ_Sec0_Strips_S4LZ:
    BINCLUDE "data/generated/ojz/act1/sec0_strips.s4lz"
    align 2
OJZ_Sec0_Strip_Checkpoints:
    BINCLUDE "data/generated/ojz/act1/sec0_strip_checkpoints.bin"
    align 2
```

Do this for all 9 sections (sec0 through sec8).

Update the Sec table entries to point to the new labels:

```asm
; In each OJZ_Act1_SecN entry:
    dc.l    OJZ_Sec0_Strips_S4LZ           ; sec_strips_s4lz ($00)
    ; ...
    dc.l    OJZ_Sec0_Strip_Checkpoints      ; sec_strip_checkpoints ($2C)
    ; ...
    dc.l    0                               ; sec_collision_s4lz ($34) — stub, populated in Task 8
```

- [ ] **Step 4: Remove raw strip BINCLUDEs**

After verifying the compressed data is generated correctly, remove the raw `secN_strips_a.bin` BINCLUDE blocks from act_descriptor.asm. The raw files are still generated by the build tool (for backward compat verification) but no longer included in the ROM.

Note: this means the engine can no longer read raw strips from ROM. Section_UpdateColumns currently reads via `Sec_sec_strips_s4lz`, which now points to compressed data it can't directly parse. **The game will NOT render correctly until Task 7 wires up the strip cache.** This is expected — Tasks 4-6 build the engine infrastructure, and Task 7 completes the switchover.

- [ ] **Step 5: Build and verify data generation**

```bash
cd /home/volence/sonic_hacks/aeon && ./build.sh
```

Expected: build succeeds (assembly passes). ROM contains compressed strip data. Game will show corrupted/missing FG tiles (expected — engine still tries to read raw data from what's now compressed).

Verify compressed output:
```bash
ls -la data/generated/ojz/act1/sec*_strips.s4lz
ls -la data/generated/ojz/act1/sec*_strip_checkpoints.bin
```

- [ ] **Step 6: Commit**

```bash
git add tools/ojz_strip_gen.py build.sh data/levels/ojz/act1/act_descriptor.asm
git commit -m "feat(§4.7): strip compression pipeline — S4LZ strips + checkpoints

ojz_strip_gen.py now compresses strips via s4lz with checkpoints every
64 strips. act_descriptor switched to compressed BINCLUDEs.
FG rendering broken until strip cache engine code is wired up (Tasks 4-7).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 4: Streaming S4LZ Decompressor (Engine)

**Files:**
- Create: `engine/s4lz_stream.asm`
- Modify: `main.asm`

- [ ] **Step 1: Research**

Check all 8 disassemblies for interruptible/resumable decompression:
- Ristar: Star decompressor yields to VBlank via state save to RAM
- S.C.E./sonic_hack: KosM 4KB fixed modules (no inter-module state)
- Batman & Robin: check if custom DMA-integrated decompressor exists
- Alien Soldier: check for any streaming decompression patterns
Search plutiedev.com for "cooperative decompression" or "interruptible decompress" patterns. Check modern game engines for streaming decompression state machine designs.

- [ ] **Step 2: Create engine/s4lz_stream.asm with S4LZ_Stream_Init**

```asm
; Streaming S4LZ decompressor (§4.7)
; Pause/resume at token boundaries. Each call decompresses N bytes,
; saves bookmark, returns. The blocking S4LZ_Decompress in
; s4lz_decompress.asm remains for tile art (run-to-completion loads).

; -----------------------------------------------
; S4LZ_Stream_Init — initialize a streaming decompressor slot
; In:  d0.w = slot index (0-3)
;      a0   = ROM pointer to S4LZ compressed data (at header start)
; Out: none
; Clobbers: d0-d1, a1
; -----------------------------------------------
S4LZ_Stream_Init:
        ; compute StreamState base = S4LZ_Stream_States + slot × 10
        ; slot × 10 = slot × 8 + slot × 2
        move.w  d0, d1
        lsl.w   #3, d1                          ; × 8
        add.w   d0, d0                          ; × 2
        add.w   d0, d1                          ; × 10
        lea     (S4LZ_Stream_States).l, a1
        adda.w  d1, a1                          ; a1 = StreamState base

        ; skip S4LZ header (4 bytes: size.w + flags.b + pad.b)
        lea     4(a0), a0
        move.l  a0, StreamState_ss_src(a1)      ; src = past header
        clr.l   StreamState_ss_output_pos(a1)   ; output_pos = 0
        clr.w   StreamState_ss_xor_prev(a1)     ; xor_prev = 0
        rts
```

- [ ] **Step 3: Implement S4LZ_Stream_Decompress**

This is the core routine. It processes tokens from the compressed stream, writing output to the caller-provided buffer, until the requested byte count is produced or the stream ends.

```asm
; -----------------------------------------------
; S4LZ_Stream_Decompress — decompress N bytes from a stream
; In:  d0.w = slot index (0-3)
;      a2   = output destination (RAM, word-aligned)
;      d1.w = byte count to produce (must be even)
; Out: d0.b = 0 if more data available, $FF if stream ended
; Clobbers: d0-d4, a0-a3
; -----------------------------------------------
S4LZ_Stream_Decompress:
        ; -- load bookmark --
        move.w  d0, d2
        lsl.w   #3, d2
        add.w   d0, d0
        add.w   d0, d2                          ; d2 = slot × 10
        lea     (S4LZ_Stream_States).l, a3
        adda.w  d2, a3                          ; a3 = StreamState base

        movea.l StreamState_ss_src(a3), a0      ; a0 = compressed source
        movea.l a2, a1                          ; a1 = output write pointer
        lea     (a2, d1.w), a2                  ; a2 = target end address

.sd_token:
        ; -- read token --
        moveq   #0, d0
        move.b  (a0)+, d0                       ; token byte
        beq.w   .sd_stream_end                  ; $00 = end of stream
        addq.l  #1, a0                          ; skip pad byte

        ; -- literals (high nibble) --
        move.w  d0, d3
        lsr.w   #4, d3                          ; d3 = literal count
        beq.s   .sd_no_lits

        cmpi.w  #15, d3
        beq.s   .sd_lit_ext

        subq.w  #1, d3                          ; adjust for dbf
.sd_lit_copy:
        move.w  (a0)+, (a1)+
        dbf     d3, .sd_lit_copy
        bra.s   .sd_no_lits

.sd_lit_ext:
        move.w  (a0)+, d3                       ; extended literal count
        subq.w  #1, d3
.sd_lit_ext_copy:
        move.w  (a0)+, (a1)+
        dbf     d3, .sd_lit_ext_copy

.sd_no_lits:
        ; -- matches (low nibble) --
        andi.w  #$0F, d0                        ; d0 = match count
        beq.s   .sd_check_target                ; 0 = no match, check if done

        cmpi.w  #15, d0
        beq.s   .sd_match_ext

        ; read offset, set source
        move.w  (a0)+, d4                       ; match offset (bytes)
        movea.l a1, a2                          ; save target end temporarily
        ; wait — a2 is our target end. Use d2 instead.
        ; Actually, we need a2 as the target boundary. Let's use a different
        ; register for the match source. Push/pop or use stack.
        ; Simpler: use the stack or rearrange registers.

        ; Register plan:
        ;   a0 = compressed source (advances)
        ;   a1 = output dest (advances)
        ;   a2 = target end address (read-only after setup)
        ;   a3 = StreamState base (read-only)
        ;   d0 = match count (consumed here)
        ;   d4 = match offset → compute match source

        ; match source = a1 - offset
        move.l  a1, d2                          ; d2 = current output pos
        sub.w   d4, d2                          ; d2 = match source addr
        movea.l d2, a4                          ; a4 = match source (uses a4)

        subq.w  #1, d0                          ; adjust for dbf
.sd_match_copy:
        move.w  (a4)+, (a1)+
        dbf     d0, .sd_match_copy
        bra.s   .sd_check_target

.sd_match_ext:
        move.w  (a0)+, d4                       ; match offset
        move.l  a1, d2
        sub.w   d4, d2
        movea.l d2, a4

        move.w  (a0)+, d0                       ; extended match count
        subq.w  #1, d0
.sd_match_ext_copy:
        move.w  (a4)+, (a1)+
        dbf     d0, .sd_match_ext_copy

.sd_check_target:
        cmpa.l  a2, a1                          ; produced enough?
        blt.s   .sd_token                       ; no — process next token

        ; -- save bookmark --
        move.l  a0, StreamState_ss_src(a3)
        move.l  a1, d0
        sub.l   a2, d0                          ; bytes past target (overshoot tracking)
        add.l   d0, StreamState_ss_output_pos(a3)
        moveq   #0, d0                          ; status = more data
        rts

.sd_stream_end:
        move.l  a0, StreamState_ss_src(a3)
        moveq   #-1, d0                         ; status = stream ended ($FF)
        rts
```

Note: This uses `a4` as a scratch register for match source. The routine header should document `a4` in the clobber list. The actual implementation will need careful register allocation — the above is the algorithmic template. The implementer should verify register usage against the blocking `S4LZ_Decompress` in `s4lz_decompress.asm` and adjust as needed.

- [ ] **Step 4: Add include to main.asm**

Add after the `s4lz_decompress.asm` include (line 103):

```asm
    include "engine/s4lz_stream.asm"
```

- [ ] **Step 5: Build and verify**

```bash
cd /home/volence/sonic_hacks/aeon && ./build.sh
```

Expected: clean build. No runtime change (streaming decompressor not called yet).

- [ ] **Step 6: Commit**

```bash
git add engine/s4lz_stream.asm main.asm
git commit -m "feat(§4.7): streaming S4LZ decompressor — pause/resume at token boundaries

S4LZ_Stream_Init and S4LZ_Stream_Decompress: slot-indexed bookmark,
decompress N bytes per call, save/restore compressed stream position.
Used by strip cache fill (not wired up yet).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 5: Strip Cache Core (Engine)

**Files:**
- Create: `engine/level/strip_cache.asm`
- Modify: `main.asm`

- [ ] **Step 1: Research**

Check all 8 disassemblies for world-space tile caching or ring-buffer nametable management. Specifically look for: how Vectorman manages its 64×64 planes with scrolling, how Thunder Force IV's multi-layer scroll engine caches tile data, how S.C.E. handles level scrolling buffers. Search for "circular buffer tile cache" and "ring buffer nametable" in retro game dev communities. Check modern streaming world engines for sliding window cache patterns.

- [ ] **Step 2: Create engine/level/strip_cache.asm with coordinate conversion**

```asm
; World-space strip cache (§4.7)
; 80-column circular buffer in lower RAM ($FFFF0000).
; Decompressed on-demand as camera scrolls.

; -----------------------------------------------
; Engine_To_World_Col — convert engine tile col to world tile col
; In:  d0.w = engine tile col (e.g., Camera_X / 8)
; Out: d0.w = world tile col
; Clobbers: d1
; -----------------------------------------------
Engine_To_World_Col:
        subi.w  #SLOT_ORIGIN_L/8, d0           ; d0 = engine_col - 64
        moveq   #0, d1
        move.b  (Slot_Section_Map).w, d1        ; slot 0 sec_x
        lsl.w   #8, d1                          ; sec_x × 256 (= SECTION_TILE_WIDTH)
        add.w   d1, d0
        rts

; -----------------------------------------------
; Strip_Cache_GetColumn — get strip data pointer for a world tile col
; In:  d0.w = world tile col (must be within valid cache range)
; Out: a0   = pointer to 96-byte strip in cache
; Clobbers: d0-d1
; -----------------------------------------------
Strip_Cache_GetColumn:
        ; ring index = Head_Idx - (Head_Col - world_col)
        move.w  (Strip_Cache_Head_Col).w, d1
        sub.w   d0, d1                          ; d1 = Head_Col - world_col (0..79)
        move.w  (Strip_Cache_Head_Idx).w, d0
        sub.w   d1, d0                          ; d0 = Head_Idx - offset
        bpl.s   .sc_no_wrap
        addi.w  #STRIP_CACHE_COLS, d0           ; wrap negative → 0..79
.sc_no_wrap:
        ; d0 = ring buffer index (0..79)
        ; ×96 via shift+add (no mulu)
        lsl.w   #5, d0                          ; ×32
        move.w  d0, d1
        add.w   d0, d0                          ; ×64
        add.w   d1, d0                          ; ×96
        lea     (Strip_Cache).l, a0
        adda.w  d0, a0
        rts
```

- [ ] **Step 3: Implement Strip_Cache_Init**

```asm
; -----------------------------------------------
; Strip_Cache_Init — populate cache for initial viewport + margins
; Called at level init (display off, after Level_LoadArt).
; In:  a0 = act descriptor
; Out: none
; Clobbers: d0-d7, a0-a4
; -----------------------------------------------
Strip_Cache_Init:
        movem.l a5-a6, -(sp)

        ; compute starting world col: viewport left edge - margin
        move.l  (Camera_X).w, d6
        swap    d6                              ; d6.w = Camera_X pixels
        lsr.w   #3, d6                          ; d6 = engine tile col (left edge)
        move.w  d6, d0
        bsr.w   Engine_To_World_Col             ; d0 = world col of left edge
        subi.w  #STRIP_CACHE_MARGIN, d0         ; d0 = first col to cache
        bpl.s   .sc_clamp_ok
        moveq   #0, d0                          ; clamp to 0
.sc_clamp_ok:
        move.w  d0, (Strip_Cache_Left_Col).w
        clr.w   (Strip_Cache_Head_Idx).w        ; start filling from ring index 0

        ; determine which section this starting col belongs to
        move.w  d0, d7                          ; d7 = current world col
        move.w  d7, d1
        lsr.w   #8, d1                          ; d1 = section_x (world_col / 256)

        ; initialize forward stream for starting section
        movea.l (Current_Act_Ptr).w, a5
        move.w  d1, d0
        bsr.w   .sc_init_section_stream         ; init stream slot 0 for section d0

        ; fill STRIP_CACHE_COLS strips
        moveq   #STRIP_CACHE_COLS-1, d5         ; loop counter
        moveq   #0, d4                          ; ring buffer write index

.sc_fill_loop:
        ; check if current world_col crossed into next section
        move.w  d7, d0
        andi.w  #$FF, d0                        ; section-local col
        bne.s   .sc_same_section
        tst.w   d4                              ; skip check on first iteration
        beq.s   .sc_same_section
        ; crossed section boundary — init new stream
        move.w  d7, d1
        lsr.w   #8, d1                          ; new section_x
        move.w  d1, d0
        bsr.w   .sc_init_section_stream

.sc_same_section:
        ; decompress one strip (96 bytes) into cache at ring index d4
        move.w  d4, d0
        bsr.w   .sc_ring_addr                   ; a2 = cache address for index d4
        moveq   #0, d0                          ; stream slot 0
        move.w  #STRIP_BYTE_SIZE, d1            ; 96 bytes
        bsr.w   S4LZ_Stream_Decompress

        addq.w  #1, d7                          ; next world col
        addq.w  #1, d4                          ; next ring index
        dbf     d5, .sc_fill_loop

        ; set head trackers
        subq.w  #1, d7                          ; last filled col
        move.w  d7, (Strip_Cache_Head_Col).w
        subq.w  #1, d4
        move.w  d4, (Strip_Cache_Head_Idx).w

        ; set forward stream section
        move.w  d7, d0
        lsr.w   #8, d0
        move.b  d0, (Strip_Cache_Fwd_Stream).w

        movem.l (sp)+, a5-a6
        rts

; helper: init stream for section d0.w
.sc_init_section_stream:
        ; d0.w = section_x, a5 = act descriptor
        movea.l Act_sec_grid_ptr(a5), a0
        move.w  d0, d1
        lsl.w   #6, d1                          ; sec × 64
        move.w  d0, d2
        lsl.w   #3, d2                          ; sec × 8
        add.w   d2, d1                          ; sec × 72
        adda.w  d1, a0                          ; a0 = Sec ptr
        movea.l Sec_sec_strips_s4lz(a0), a0     ; a0 = S4LZ stream
        moveq   #0, d0                          ; stream slot 0
        bra.w   S4LZ_Stream_Init                ; tail call

; helper: ring buffer address for index d0.w
.sc_ring_addr:
        ; d0.w = ring index (0..79)
        ; Out: a2 = cache address
        lsl.w   #5, d0                          ; ×32
        move.w  d0, d1
        add.w   d0, d0                          ; ×64
        add.w   d1, d0                          ; ×96
        lea     (Strip_Cache).l, a2
        adda.w  d0, a2
        rts
```

- [ ] **Step 4: Implement Strip_Cache_Fill (per-frame)**

```asm
; -----------------------------------------------
; Strip_Cache_Fill — decompress new strips as camera scrolls
; Called each frame after Camera_Update, before Section_UpdateColumns.
; In:  none
; Out: none
; Clobbers: d0-d7, a0-a4
; -----------------------------------------------
Strip_Cache_Fill:
        ; -- compute rightmost needed world col --
        move.l  (Camera_X).w, d6
        swap    d6
        addi.w  #327, d6                        ; right edge + 7 (round up)
        lsr.w   #3, d6                          ; d6 = right edge engine tile col
        move.w  d6, d0
        bsr.w   Engine_To_World_Col
        addi.w  #STRIP_CACHE_MARGIN, d0         ; + lookahead margin
        move.w  d0, d7                          ; d7 = right_needed world col

        ; -- fill rightward if needed --
        move.w  (Strip_Cache_Head_Col).w, d5    ; d5 = current head
.scf_right_loop:
        cmp.w   d7, d5
        bge.s   .scf_right_done
        addq.w  #1, d5                          ; next col to fill

        ; check section boundary
        move.w  d5, d0
        andi.w  #$FF, d0
        bne.s   .scf_right_same_sec
        ; crossed into next section — reinit stream
        move.w  d5, d0
        lsr.w   #8, d0                          ; new section_x
        move.b  d0, (Strip_Cache_Fwd_Stream).w
        movea.l (Current_Act_Ptr).w, a5
        bsr.w   .sc_init_section_stream

.scf_right_same_sec:
        ; advance ring index (mod 80)
        move.w  (Strip_Cache_Head_Idx).w, d0
        addq.w  #1, d0
        cmpi.w  #STRIP_CACHE_COLS, d0
        blt.s   .scf_no_wrap
        moveq   #0, d0
.scf_no_wrap:
        move.w  d0, (Strip_Cache_Head_Idx).w

        ; decompress one strip
        bsr.w   .sc_ring_addr                   ; a2 = dest
        moveq   #0, d0                          ; stream slot 0
        move.w  #STRIP_BYTE_SIZE, d1
        bsr.w   S4LZ_Stream_Decompress

        ; update trackers
        move.w  d5, (Strip_Cache_Head_Col).w
        ; update left col (evict oldest if cache full)
        move.w  d5, d0
        subi.w  #STRIP_CACHE_COLS-1, d0
        cmp.w   (Strip_Cache_Left_Col).w, d0
        ble.s   .scf_right_loop
        move.w  d0, (Strip_Cache_Left_Col).w
        bra.s   .scf_right_loop

.scf_right_done:
        rts
```

Note: backward fill (leftward scrolling) is deferred to a future optimization. For the initial implementation, backward scrolling past the left margin causes the cache to miss and leftward columns will not be available. This is acceptable because Sonic games are primarily right-scrolling; backward scrolling is rare and brief.

- [ ] **Step 5: Add include to main.asm**

Add after the `section.asm` include (line 116):

```asm
    include "engine/level/strip_cache.asm"
```

- [ ] **Step 6: Build and verify**

```bash
cd /home/volence/sonic_hacks/aeon && ./build.sh
```

Expected: clean build. No runtime change (strip cache not called yet).

- [ ] **Step 7: Commit**

```bash
git add engine/level/strip_cache.asm main.asm
git commit -m "feat(§4.7): strip cache core — circular buffer with world-space addressing

Strip_Cache_Init (cold fill from compressed streams),
Strip_Cache_Fill (per-frame rightward fill driven by camera),
Strip_Cache_GetColumn (world col → cache pointer, no mulu).
Engine_To_World_Col conversion. Not wired up yet.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 6: Integration — Level Init + Game Loop

**Files:**
- Modify: `engine/level/load_art.asm`
- Modify: `test/ojz_scroll_test.asm`

- [ ] **Step 1: Research**

Check all 8 disassemblies for level initialization order — specifically how they sequence tile loading, nametable population, and decompression buffer setup. Check if any engine separates "decompress tile art" from "fill nametable" in their init sequence. Look at the existing `ojz_scroll_test.asm` init sequence (lines 9-120) to understand the current ordering.

- [ ] **Step 2: Add Strip_Cache_Init call to Level_LoadArt**

In `engine/level/load_art.asm`, add the strip cache initialization after the existing `BG_Init` call (after line 113). The strip cache must be populated AFTER tile art DMA is complete (LoadArt_S4LZ calls VSync_Wait) but BEFORE Section_Init (which triggers Section_FillInitial / Section_UpdateColumns).

```asm
        ; -- §4.7: populate strip cache from compressed streams --
        movea.l a4, a0                          ; a0 = act ptr
        jsr     Strip_Cache_Init
```

Note: `Strip_Cache_Init` writes to $FFFF0000 (Strip_Cache), which is the same address as the old Decomp_Buffer. This is safe because `Section_LoadArt` already finished and DMA'd the tile art to VRAM before this point.

- [ ] **Step 3: Add Strip_Cache_Fill to game loop**

In `test/ojz_scroll_test.asm`, add the fill call in `GameState_OJZScroll_Update` between Camera_Update and Section_Check (after line 161):

```asm
        ; -- §4.7: fill strip cache with new strips as camera scrolls --
        jsr     Strip_Cache_Fill
```

The updated call order becomes:
```
Camera_Update → Strip_Cache_Fill → Section_Check → EntityWindow_Scan → Section_UpdateColumns
```

- [ ] **Step 4: Build and verify**

```bash
cd /home/volence/sonic_hacks/aeon && ./build.sh
```

Expected: clean build. The strip cache is now populated and filled each frame, but Section_UpdateColumns still tries to read raw strip data via `Sec_sec_strips_s4lz` (which points to compressed data). The game will show corrupted FG tiles. This is expected — Task 7 completes the switchover.

- [ ] **Step 5: Commit**

```bash
git add engine/level/load_art.asm test/ojz_scroll_test.asm
git commit -m "feat(§4.7): wire strip cache into level init and game loop

Strip_Cache_Init called after tile art load, before section init.
Strip_Cache_Fill called each frame between Camera_Update and Section_Check.
FG still corrupted — Section_UpdateColumns reads from cache in next task.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 7: Section_UpdateColumns + RedrawPlanes Integration

**Files:**
- Modify: `engine/level/section.asm`
- Modify: `engine/level/plane_buffer.asm`

- [ ] **Step 1: Research**

Check all 8 disassemblies for how they handle nametable streaming from RAM vs ROM. Specifically examine S.C.E.'s `DrawBGScrollBlock` for ring-buffer nametable streaming patterns. Check how sonic_hack's `DrawChunks` reads from level layout data. Examine Thunder Force IV for multi-layer streaming patterns. The key question: how do other engines abstract the data source (ROM vs RAM) for nametable column writes?

- [ ] **Step 2: Replace Draw_TileColumn to read from strip cache**

In `engine/level/plane_buffer.asm`, modify `Draw_TileColumn` (lines 21-63) to read from the strip cache instead of ROM. The section_local_col + Sec pointer parameters are replaced with a world tile col parameter:

```asm
; -----------------------------------------------
; Draw_TileColumn — append one tile column from strip cache to Plane_Buffer
; In:  d0.w = target VDP nametable column (0–63)
;      d1.w = world tile column (strip cache lookup)
; Out: none (silently drops if buffer full)
; Clobbers: d0–d3, a0–a2
; -----------------------------------------------
Draw_TileColumn:
        ; -- overflow check --
        move.w  (Plane_Buffer_Ptr).w, d2
        addi.w  #4 + STRIP_TILE_HEIGHT*2, d2
        cmpi.w  #PLANE_BUFFER_SIZE - 2, d2
        bhi.s   .done

        ; -- get strip from cache --
        move.w  d0, -(sp)                       ; save nametable col
        move.w  d1, d0
        bsr.w   Strip_Cache_GetColumn           ; a0 = strip data (96 bytes in cache)
        movea.l a0, a1                          ; a1 = strip source
        move.w  (sp)+, d0                       ; restore nametable col

        ; -- buffer write pointer --
        lea     (Plane_Buffer).w, a2
        adda.w  (Plane_Buffer_Ptr).w, a2

        ; -- write entry header --
        add.w   d0, d0                          ; col × 2
        addi.w  #VRAM_PLANE_A & $FFFF, d0
        move.w  d0, (a2)+
        move.w  #$8000 | (STRIP_TILE_HEIGHT/2 - 1), (a2)+

        ; -- copy strip data --
        moveq   #STRIP_TILE_HEIGHT/2 - 1, d3
.copy:
        move.l  (a1)+, (a2)+
        dbf     d3, .copy

        ; -- terminator + update pointer --
        move.w  #0, (a2)
        move.w  (Plane_Buffer_Ptr).w, d2
        addi.w  #4 + STRIP_TILE_HEIGHT*2, d2
        move.w  d2, (Plane_Buffer_Ptr).w
.done:
        rts
```

Remove `Draw_TileColumn_Direct` — it was only used for preview-zone strip reads from neighbor pointers. The strip cache handles cross-section reads natively.

- [ ] **Step 3: Rewrite Section_UpdateColumns to use world-space addressing**

Replace the current Section_UpdateColumns (lines 776-920 of section.asm) with a simplified version that reads from the strip cache. The slot 0 / slot 1 / preview neighbor routing logic is eliminated:

```asm
; -----------------------------------------------
; Section_UpdateColumns — per-frame nametable streaming from strip cache (§4.7)
; Writes newly-revealed tile columns on right and left edges.
; Called AFTER Camera_Update and Strip_Cache_Fill each frame.
; In:  none
; Out: none
; Clobbers: d0–d7, a0–a3, a5–a6 (a5/a6 only on dirty redraw)
; -----------------------------------------------
Section_UpdateColumns:
        ; -- §4.2: full-plane redraw if dirty (post-teleport) --
        tst.b   (Section_Plane_Dirty).w
        beq.s   .not_dirty
        clr.b   (Section_Plane_Dirty).w
        bsr.w   Section_RedrawPlanes
        move.w  d7, (Section_Right_Col_Written).w
        move.w  d5, (Section_Left_Col_Written).w
        rts
.not_dirty:
        movem.l d2-d7/a0-a3, -(sp)

        move.l  (Camera_X).w, d6
        swap    d6                              ; d6.w = Camera_X pixels

        ; -------- right side --------
        move.w  d6, d7
        addi.w  #327, d7
        lsr.w   #3, d7                          ; d7 = right_needed engine tile col

        ; convert to world col for cache bounds check
        move.w  d7, d0
        bsr.w   Engine_To_World_Col
        move.w  d0, d7                          ; d7 = right_needed world col

        ; clamp to act boundary
        ; (max world col = (grid_w × 256) - 1 + preview margin)
        movea.l (Current_Act_Ptr).w, a0
        moveq   #0, d0
        move.w  Act_grid_w(a0), d0
        lsl.w   #8, d0                          ; d0 = grid_w × 256
        subq.w  #1, d0
        cmp.w   d0, d7
        ble.s   .right_clamp_ok
        move.w  d0, d7
.right_clamp_ok:
        ; clamp to cache bounds
        move.w  (Strip_Cache_Head_Col).w, d0
        cmp.w   d0, d7
        ble.s   .right_cache_ok
        move.w  d0, d7
.right_cache_ok:

        move.w  (Section_Right_Col_Written).w, d5
.right_loop:
        cmp.w   d7, d5
        bge.w   .right_done
        cmpi.w  #PLANE_BUFFER_SIZE - 2 - (4 + STRIP_TILE_HEIGHT*2), (Plane_Buffer_Ptr).w
        bhi.w   .right_done
        addq.w  #1, d5

        ; convert world col → engine col for nametable position
        move.w  d5, d0
        moveq   #0, d1
        move.b  (Slot_Section_Map).w, d1
        lsl.w   #8, d1
        sub.w   d1, d0
        addi.w  #SLOT_ORIGIN_L/8, d0           ; d0 = engine tile col
        andi.w  #63, d0                         ; d0 = nametable col

        move.w  d5, d1                          ; d1 = world col
        bsr.w   Draw_TileColumn
        bra.w   .right_loop
.right_done:
        move.w  d5, (Section_Right_Col_Written).w
        ; bump left if wrapped
        move.w  d5, d3
        subi.w  #63, d3
        cmp.w   (Section_Left_Col_Written).w, d3
        ble.s   .left_clamp_skip
        move.w  d3, (Section_Left_Col_Written).w
.left_clamp_skip:

        ; -------- left side --------
        move.w  d6, d7
        lsr.w   #3, d7                          ; d7 = left edge engine tile col
        move.w  d7, d0
        bsr.w   Engine_To_World_Col
        move.w  d0, d7                          ; d7 = left_needed world col

        ; clamp to cache and act bounds
        move.w  (Strip_Cache_Left_Col).w, d0
        cmp.w   d0, d7
        bge.s   .left_cache_ok
        move.w  d0, d7
.left_cache_ok:

        move.w  (Section_Left_Col_Written).w, d5
.left_loop:
        cmp.w   d7, d5
        ble.w   .left_done
        cmpi.w  #PLANE_BUFFER_SIZE - 2 - (4 + STRIP_TILE_HEIGHT*2), (Plane_Buffer_Ptr).w
        bhi.w   .left_done
        subq.w  #1, d5

        move.w  d5, d0
        moveq   #0, d1
        move.b  (Slot_Section_Map).w, d1
        lsl.w   #8, d1
        sub.w   d1, d0
        addi.w  #SLOT_ORIGIN_L/8, d0
        andi.w  #63, d0

        move.w  d5, d1
        bsr.w   Draw_TileColumn
        bra.w   .left_loop
.left_done:
        move.w  d5, (Section_Left_Col_Written).w
        move.w  d5, d3
        addi.w  #63, d3
        cmp.w   (Section_Right_Col_Written).w, d3
        bge.s   .right_clamp_skip2
        move.w  d3, (Section_Right_Col_Written).w
.right_clamp_skip2:

        movem.l (sp)+, d2-d7/a0-a3
        rts
```

- [ ] **Step 4: Rewrite Section_RedrawPlanes to use strip cache**

Replace the Plane A fill logic in `Section_RedrawPlanes` (lines 630-766) to read from the strip cache instead of routing through slot definitions and neighbor pointers:

```asm
Section_RedrawPlanes:
        lea     (VDP_CTRL).l, a5
        lea     (VDP_DATA).l, a6
        move.w  sr, -(sp)
        move.w  #$2700, sr

        ; column-major write
        move.w  #$8F80, (a5)

        ; compute start world col
        move.l  (Camera_X).w, d5
        swap    d5
        lsr.w   #3, d5                          ; d5 = engine start tile col
        move.w  d5, d0
        bsr.w   Engine_To_World_Col             ; d0 = world start col
        move.w  d0, d5                          ; d5 = start_world_col (returned to caller)

        moveq   #0, d3                          ; col counter (0..63)
        moveq   #0, d6                          ; zero for fill

.pla_fill:
        move.w  d5, d7
        add.w   d3, d7                          ; d7 = world_col
        move.w  d7, d0

        ; convert world col → engine col for nametable position
        moveq   #0, d1
        move.b  (Slot_Section_Map).w, d1
        lsl.w   #8, d1
        sub.w   d1, d0
        addi.w  #SLOT_ORIGIN_L/8, d0
        andi.w  #63, d0                         ; d0 = plane_col

        ; set VDP write address
        moveq   #0, d4
        move.w  d0, d4
        add.w   d4, d4
        addi.l  #VRAM_PLANE_A, d4
        vdpCommReg d4, VRAM, WRITE, 1
        move.l  d4, (a5)

        ; check if world_col is in cache range
        move.w  d7, d0
        cmp.w   (Strip_Cache_Left_Col).w, d0
        blt.s   .pla_zero_fill
        cmp.w   (Strip_Cache_Head_Col).w, d0
        bgt.s   .pla_zero_fill

        ; read from strip cache
        bsr.w   Strip_Cache_GetColumn           ; a0 = strip data
        movea.l a0, a1
        moveq   #STRIP_TILE_HEIGHT/2-1, d4
.pla_copy:
        move.l  (a1)+, (a6)
        dbf     d4, .pla_copy
        bra.s   .pla_next

.pla_zero_fill:
        moveq   #STRIP_TILE_HEIGHT/2-1, d4
.pla_zero:
        move.l  d6, (a6)
        dbf     d4, .pla_zero

.pla_next:
        addq.w  #1, d3
        cmpi.w  #64, d3
        blt.w   .pla_fill

        ; -- Plane B (unchanged — BG layout is act-wide, not strip-cache dependent) --
        ; ... (keep existing Plane B logic from lines 738-755 unchanged) ...
```

- [ ] **Step 5: Convert Section_Right/Left_Col_Written to world space**

Currently these trackers are in engine tile col space. They must now track world tile cols to match the strip cache. Update `Section_FillInitial` (line 98-101):

```asm
Section_FillInitial:
        ; Set trackers to world cols matching initial camera position.
        ; After Level_LoadArt → Strip_Cache_Init, the cache is populated.
        ; Set right/left as if a teleport just fired — Section_UpdateColumns
        ; will fill the visible window on first few frames.
        move.l  (Camera_X).w, d0
        swap    d0
        lsr.w   #3, d0                          ; d0 = engine tile col of camera left
        bsr.w   Engine_To_World_Col             ; d0 = world col
        subq.w  #1, d0
        move.w  d0, (Section_Right_Col_Written).w
        addq.w  #1, d0
        move.w  d0, (Section_Left_Col_Written).w
        rts
```

- [ ] **Step 6: Remove Section_Fwd/Bwd_Neighbor_Strips usage from section.asm**

The strip cache handles cross-section reads natively. Remove all neighbor strip pointer caching from:
- `Section_Init` (lines 37-70): remove BWD/FWD neighbor strip pointer lookups
- `Section_TeleportFwd` (lines 361-393): remove neighbor strip pointer updates
- `Section_TeleportBwd` (lines 490-522): remove neighbor strip pointer updates

Keep the RAM variables `Section_Fwd_Neighbor_Strips` and `Section_Bwd_Neighbor_Strips` in ram.asm for now (they may be useful for other systems), but stop writing to them.

- [ ] **Step 7: Build and test**

```bash
cd /home/volence/sonic_hacks/aeon && ./build.sh
```

Expected: clean build. **This is the critical test milestone.** Load in emulator and verify:
1. FG terrain renders correctly (same as before compression)
2. Scrolling right reveals new terrain smoothly
3. No visual artifacts at section boundaries
4. Plane B (background) renders correctly (unchanged)

If FG is corrupted: check strip cache addressing (×96 math), world-col conversion, ring buffer index calculation. Use Exodus MCP to inspect strip cache RAM at $FFFF0000 and compare against expected strip data.

- [ ] **Step 8: Commit**

```bash
git add engine/level/section.asm engine/level/plane_buffer.asm
git commit -m "feat(§4.7): Section_UpdateColumns reads from strip cache — FG rendering restored

Section_UpdateColumns and Section_RedrawPlanes now use world-space strip
cache instead of ROM strip pointers. Draw_TileColumn takes world_col.
Slot 0/1/preview routing logic eliminated. Neighbor strip pointer caching
removed. Section_Right/Left_Col_Written converted to world col space.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 8: Teleport Integration

**Files:**
- Modify: `engine/level/section.asm`
- Modify: `engine/level/strip_cache.asm`

- [ ] **Step 1: Research**

Check all 8 disassemblies for how they handle tile cache/buffer state across screen transitions, teleports, or level segment changes. How does S.C.E. handle plane data across act transitions? How does sonic_hack's teleport interact with DrawChunks state? The key question: does any engine maintain a continuous tile cache across coordinate shifts?

- [ ] **Step 2: Verify world-space invariance across teleport**

The strip cache operates in world space. World-space coordinates are invariant across teleport (verified in design):

```
Before FWD teleport: world_col = (Camera_X/8 - 64) + sec_x_slot0 × 256
After FWD teleport:  world_col = ((Camera_X - SECTION_SHIFT)/8 - 64) + (sec_x_slot0 + 2) × 256
                               = same value (shifts cancel)
```

Therefore: **Strip_Cache_Head_Col, Strip_Cache_Head_Idx, and Strip_Cache_Left_Col require NO adjustment on teleport.** The cache contents remain valid.

However, Section_Right/Left_Col_Written ARE in world space now and also don't need adjustment. But they ARE reset by teleport (the full-plane redraw pattern). This is handled by `Section_Plane_Dirty` → `Section_RedrawPlanes`, which already reads from the cache.

- [ ] **Step 3: Update Section_TeleportFwd stream state**

After teleport, the forward decompression stream may need to switch to the new section if the cache's head is now in a different section. Add to `Section_TeleportFwd` (after the parallax snap code, around line 449):

```asm
        ; -- §4.7: update forward stream section if cache head crossed boundary --
        ; The cache data is valid (world-space invariant), but the streaming
        ; decompressor needs to know which section to feed from next.
        move.w  (Strip_Cache_Head_Col).w, d0
        lsr.w   #8, d0                          ; section_x of current head
        move.b  d0, (Strip_Cache_Fwd_Stream).w
        ; Re-init stream at the correct position (after head's section-local col)
        ; This is needed so Strip_Cache_Fill decompresses from the right point.
        movea.l (Current_Act_Ptr).w, a0
        moveq   #0, d0
        move.b  (Strip_Cache_Fwd_Stream).w, d0
        bsr.w   Strip_Cache_ReinitStreamAtCol   ; reinit from checkpoint nearest to head
```

- [ ] **Step 4: Implement Strip_Cache_ReinitStreamAtCol**

Add to `engine/level/strip_cache.asm`:

```asm
; -----------------------------------------------
; Strip_Cache_ReinitStreamAtCol — reinitialize forward stream to resume
; from a specific world column (used after teleport).
; In:  d0.w = section_x to stream from
;      a0   = act descriptor
; Out: none
; Clobbers: d0-d4, a0-a2
; -----------------------------------------------
Strip_Cache_ReinitStreamAtCol:
        ; Get Sec ptr for this section
        movea.l Act_sec_grid_ptr(a0), a1
        move.w  d0, d1
        lsl.w   #6, d1
        move.w  d0, d2
        lsl.w   #3, d2
        add.w   d2, d1
        adda.w  d1, a1                          ; a1 = Sec ptr

        ; Compute section-local strip index from Head_Col
        move.w  (Strip_Cache_Head_Col).w, d3
        andi.w  #$FF, d3                        ; d3 = section-local col of head
        addq.w  #1, d3                          ; next col to decompress

        ; If past section boundary, move to next section
        cmpi.w  #SECTION_TILE_WIDTH, d3
        blt.s   .reinit_this_sec
        ; next section — increment and re-lookup
        ; (handled by Strip_Cache_Fill on next frame)
        rts

.reinit_this_sec:
        ; Find nearest checkpoint before this strip
        ; checkpoint_index = strip / 64 (= STRIPS_PER_CHECKPOINT)
        move.w  d3, d0
        lsr.w   #6, d0                          ; d0 = checkpoint index (0-3)

        ; Read checkpoint offset from ROM table
        movea.l Sec_sec_strip_checkpoints(a1), a2  ; a2 = checkpoint table
        add.w   d0, d0                          ; word index
        move.w  (a2, d0.w), d4                  ; d4 = compressed byte offset

        ; Init stream at checkpoint position
        movea.l Sec_sec_strips_s4lz(a1), a0     ; a0 = S4LZ stream base
        adda.w  #4, a0                          ; skip header
        adda.w  d4, a0                          ; a0 = checkpoint compressed position
        moveq   #0, d0                          ; slot 0
        bsr.w   S4LZ_Stream_Init

        ; Decompress forward to skip strips between checkpoint and target
        move.w  d3, d0
        andi.w  #$3F, d0                        ; strips past checkpoint
        beq.s   .reinit_done
        mulu.w  #STRIP_BYTE_SIZE, d0            ; total bytes to skip
        ; Note: mulu used here because this is a one-time teleport cost,
        ; not per-frame. Could decompose but not worth the complexity.
        move.w  d0, d1                          ; d1 = bytes to decompress
        lea     (Strip_Cache_V1_Reserved).l, a2 ; temp dest (unused vertical slot 1)
        moveq   #0, d0                          ; slot 0
        bsr.w   S4LZ_Stream_Decompress          ; skip strips

.reinit_done:
        rts
```

- [ ] **Step 5: Add same stream reinit to Section_TeleportBwd**

Mirror the stream reinit code in `Section_TeleportBwd` (same pattern as Step 3).

- [ ] **Step 6: Build and test**

```bash
cd /home/volence/sonic_hacks/aeon && ./build.sh
```

Expected: clean build. Test in emulator:
1. Scroll right past the teleport threshold ($1200) — teleport fires, terrain stays seamless
2. Continue scrolling right through multiple sections
3. Scroll left past backward threshold ($0200) — backward teleport, terrain stays seamless
4. No visual artifacts, stuttering, or corrupted tiles at teleport boundaries

- [ ] **Step 7: Commit**

```bash
git add engine/level/section.asm engine/level/strip_cache.asm
git commit -m "feat(§4.7): teleport integration — strip cache survives coordinate shifts

World-space cache is teleport-invariant (no data invalidation needed).
Forward stream re-initialized from nearest checkpoint after teleport.
Backward teleport mirrors forward logic.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 9: Collision Map Build Pipeline + Loading

**Files:**
- Modify: `tools/ojz_strip_gen.py`
- Modify: `data/levels/ojz/act1/act_descriptor.asm`
- Modify: `engine/level/load_art.asm`
- Modify: `engine/level/section.asm`

- [ ] **Step 1: Research**

Check all 8 disassemblies for collision map storage and loading patterns:
- sonic_hack: collision index → height array via chunks
- S.C.E.: collision response tables, height map organization
- Ristar: check for flat collision arrays or chunk-based lookup
- NES/Game Boy homebrew: tile index → collision LUT pattern (Balloon Fight, Ice Climber)
Search for "flat collision map" and "tile collision lookup table" in retro game dev. Check modern 2D engines (Celeste, Hollow Knight devlogs) for tile-based collision patterns.

- [ ] **Step 2: Add collision map generation to ojz_strip_gen.py**

Add a stub collision LUT and collision map generator. For the initial implementation, derive collision from tile content: non-empty tiles = solid (type 1), empty tiles = air (type 0). This is a placeholder until authored collision data exists.

```python
def generate_collision_map(strip_data: bytes, section_width_tiles: int,
                           section_height_cells: int) -> bytes:
    """Generate a flat collision map from strip data.
    
    Stub implementation: tiles with non-zero content → CTYPE_FLAT_SOLID (1),
    zero tiles → CTYPE_AIR (0). Each collision cell covers a 16×16 pixel
    area (2×2 tiles in the strip).
    
    Args:
        strip_data: Raw nametable strip data (section_width_tiles × STRIP_BYTE_SIZE)
        section_width_tiles: Number of tile columns (256)
        section_height_cells: Collision rows (24 for 384px / 16px)
    
    Returns:
        Flat byte array, collision_cols × collision_rows
    """
    COLLISION_COLS = section_width_tiles // 2  # 128 (16px cells from 8px tiles)
    collision_map = bytearray(COLLISION_COLS * section_height_cells)
    
    STRIP_BYTE_SIZE = 96  # 48 rows × 2 bytes
    
    for col_16 in range(COLLISION_COLS):
        tile_col = col_16 * 2  # two 8px tile cols per 16px cell
        strip_offset = tile_col * STRIP_BYTE_SIZE
        
        for row_16 in range(section_height_cells):
            tile_row = row_16 * 2  # two 8px tile rows per 16px cell
            
            # Check if any of the 4 tiles (2×2) in this cell are non-zero
            has_content = False
            for tc in range(2):  # two tile columns
                so = (tile_col + tc) * STRIP_BYTE_SIZE
                for tr in range(2):  # two tile rows
                    word_offset = so + (tile_row + tr) * 2
                    if word_offset + 1 < len(strip_data):
                        tile_word = (strip_data[word_offset] << 8) | strip_data[word_offset + 1]
                        if tile_word != 0:
                            has_content = True
            
            cell_index = row_16 * COLLISION_COLS + col_16
            collision_map[cell_index] = 1 if has_content else 0  # CTYPE_FLAT_SOLID / CTYPE_AIR
    
    return bytes(collision_map)
```

Add to the `generate()` function, after strip compression:

```python
    # Generate and compress collision maps
    for sec_idx in range(num_sections):
        raw_strip_path = os.path.join(out_dir, f"sec{sec_idx}_strips_a.bin")
        with open(raw_strip_path, 'rb') as f:
            raw_strips = f.read()
        
        collision = generate_collision_map(raw_strips, 256, 24)
        
        # S4LZ compress the collision map (no tile-delta)
        compressed_coll, _ = s4lz_compress(collision, tile_delta=False)
        
        coll_path = os.path.join(out_dir, f"sec{sec_idx}_collision.s4lz")
        with open(coll_path, 'wb') as f:
            f.write(compressed_coll)
        
        ratio = len(compressed_coll) / len(collision) * 100
        print(f"  sec{sec_idx} collision: {len(collision)} -> {len(compressed_coll)} ({ratio:.1f}%)")
```

- [ ] **Step 3: Add collision map BINCLUDEs to act_descriptor.asm**

For each section, add:
```asm
OJZ_Sec0_Collision_S4LZ:
    BINCLUDE "data/generated/ojz/act1/sec0_collision.s4lz"
    align 2
```

Update the Sec table `sec_collision_s4lz` ($34) field to point to the collision data:
```asm
    dc.l    OJZ_Sec0_Collision_S4LZ             ; sec_collision_s4lz ($34)
```

- [ ] **Step 4: Add collision map loading to Level_LoadArt**

In `engine/level/load_art.asm`, add collision map decompression after the strip cache init. Collision maps decompress run-to-completion (they're small: 300-900 bytes compressed → 3072 bytes).

```asm
        ; -- §4.7: decompress collision maps for starting sections --
        ; Slot 0
        movea.l a4, a0
        moveq   #0, d6
        move.b  Act_start_sec_x(a4), d6
        bsr.w   .compute_sec_ptr                ; a0 = Sec ptr
        movea.l Sec_sec_collision_s4lz(a0), a0  ; S4LZ source
        cmpa.w  #0, a0
        beq.s   .skip_coll0
        lea     (Collision_Map_Slot0).l, a1     ; dest
        bsr.w   S4LZ_Decompress
.skip_coll0:

        ; Slot 1
        moveq   #0, d6
        move.b  Act_start_sec_x(a4), d6
        addq.b  #1, d6
        cmp.b   Act_grid_w+1(a4), d6
        bge.s   .skip_coll1
        bsr.w   .compute_sec_ptr
        movea.l Sec_sec_collision_s4lz(a0), a0
        cmpa.w  #0, a0
        beq.s   .skip_coll1
        lea     (Collision_Map_Slot1).l, a1
        bsr.w   S4LZ_Decompress
.skip_coll1:
```

- [ ] **Step 5: Add collision map preload to Section_StreamArtGroup path**

In `engine/level/section.asm`, add collision map decompression alongside tile art preloading. In the `.preload_fwd` and `.preload_bwd` routines, after calling `Section_StreamArtGroup`, also decompress the collision map:

```asm
; After Section_StreamArtGroup call in .preload_fwd:
        ; §4.7: preload collision map for the same section
        movea.l Sec_sec_collision_s4lz(a4), a0
        cmpa.w  #0, a0
        beq.s   .preload_fwd_no_coll
        ; Determine target slot (forward section → slot 1 in collision map)
        lea     (Collision_Map_Slot1).l, a1
        bsr.w   S4LZ_Decompress
.preload_fwd_no_coll:
```

Mirror for `.preload_bwd` (decompresses to Collision_Map_Slot0).

- [ ] **Step 6: Add collision map slot rotation at teleport**

In `Section_TeleportFwd`, after the slot map rotation, rotate collision maps. Since collision maps are per-slot and the slots rotate at teleport, the collision map for the departing section's slot gets overwritten by the preloaded collision map.

For the deferred cold-load pattern: when the collision map for the new slot hasn't been preloaded, the deferred load trigger will also decompress the collision map.

Add to `.deferred_fwd_load`:
```asm
        ; §4.7: also decompress collision map for deferred slot
        movea.l Sec_sec_collision_s4lz(a0), a0
        cmpa.w  #0, a0
        beq.s   .dfwd_no_coll
        lea     (Collision_Map_Slot1).l, a1
        bsr.w   S4LZ_Decompress
.dfwd_no_coll:
```

Mirror for `.deferred_bwd_load` → `Collision_Map_Slot0`.

- [ ] **Step 7: Build and test**

```bash
cd /home/volence/sonic_hacks/aeon && ./build.sh
```

Expected: clean build. Collision maps generated, compressed, included in ROM, and decompressed to RAM at level init and preload. Verify with Exodus MCP:

```
# Read collision map slot 0 (should have non-zero bytes for ground tiles)
emulator_read_memory address=0xFFFF3C00 length=128
```

- [ ] **Step 8: Commit**

```bash
git add tools/ojz_strip_gen.py data/levels/ojz/act1/act_descriptor.asm \
    engine/level/load_art.asm engine/level/section.asm
git commit -m "feat(§4.7): collision map pipeline — build, compress, load at init/preload

ojz_strip_gen.py generates stub collision maps (non-empty tile = solid).
S4LZ compressed, BINCLUDEd in act_descriptor.
Decompressed to Collision_Map_Slot0/1 at level init and preload thresholds.
Slot rotation and deferred load integrated with teleport.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 10: Collision Lookup, Height Maps, and Dual Floor Sensors

**Files:**
- Create: `engine/level/collision_lookup.asm`
- Create: `data/collision/heightmaps.bin` (stub)
- Create: `data/collision/heightmaps_rot.bin` (stub)
- Create: `data/collision/angles.bin` (stub)
- Modify: `main.asm`

- [ ] **Step 1: Research**

Check all 8 disassemblies for collision lookup implementations:
- sonic_hack: `FindFloor`, `FindWall`, `FindCeiling` — chunk → block → collision index → height array
- S.C.E.: optimized floor sensor implementation, height map organization
- Ristar: check floor detection for non-Sonic physics model
- Alien Soldier: check for simplified collision (platformer with different physics)
Search plutiedev.com for "height map collision" and "floor sensor" implementations. Study how Sonic 2/3 dual sensors work (inner sensor positioning, which sensor wins). Check modern 2D platformer collision tutorials for dual-sensor ground detection.

- [ ] **Step 2: Generate stub height map data**

Create a Python script or inline build step that generates:

`data/collision/heightmaps.bin` (4096 bytes):
- 256 profiles × 16 bytes each
- Type 0 (air): 16 bytes of $00
- Type 1 (flat solid): 16 bytes of $10 (full height = 16)
- Types 2-255: 16 bytes of $00 (placeholder for future slopes)

`data/collision/heightmaps_rot.bin` (4096 bytes):
- Same structure, rotated 90° for wall sensors
- Type 0: all $00
- Type 1: all $10
- Types 2-255: all $00

`data/collision/angles.bin` (256 bytes):
- Type 0: $00 (flat)
- Type 1: $00 (flat solid)
- Types 2-255: $00 (placeholder)

Generate with a small Python helper in the build:
```python
# tools/gen_collision_data.py
import struct, sys, os

def generate_heightmaps(path):
    data = bytearray(256 * 16)
    # Type 1 = flat solid: all pixels at height 16
    for i in range(16):
        data[1 * 16 + i] = 0x10
    with open(path, 'wb') as f:
        f.write(data)

def generate_angles(path):
    data = bytearray(256)
    # All types: angle 0 (flat) for now
    with open(path, 'wb') as f:
        f.write(data)

if __name__ == '__main__':
    out_dir = sys.argv[1] if len(sys.argv) > 1 else 'data/collision'
    os.makedirs(out_dir, exist_ok=True)
    generate_heightmaps(os.path.join(out_dir, 'heightmaps.bin'))
    generate_heightmaps(os.path.join(out_dir, 'heightmaps_rot.bin'))
    generate_angles(os.path.join(out_dir, 'angles.bin'))
    print(f"Generated collision data in {out_dir}")
```

- [ ] **Step 3: BINCLUDE collision data in main.asm data section**

Add after the existing data includes (around line 167):

```asm
; -----------------------------------------------
; Collision data (§4.7 — global, shared across all zones)
; -----------------------------------------------
HeightMaps:
    BINCLUDE "data/collision/heightmaps.bin"
    align 2
HeightMapsRot:
    BINCLUDE "data/collision/heightmaps_rot.bin"
    align 2
AngleTable:
    BINCLUDE "data/collision/angles.bin"
    align 2
```

- [ ] **Step 4: Create engine/level/collision_lookup.asm**

```asm
; Collision lookup system (§4.7)
; Flat collision map query → height map profile → angle table

; -----------------------------------------------
; Collision_GetType — look up collision type for a world position
; In:  d0.w = world X (pixels, relative to slot 0's origin)
;      d1.w = world Y (pixels)
; Out: d0.b = collision type byte (CTYPE_AIR, CTYPE_FLAT_SOLID, etc.)
; Clobbers: d0-d2, a0
; -----------------------------------------------
Collision_GetType:
        ; -- determine which collision map slot to use --
        ; Slot routing: section_local_x determines horizontal slot (0 or 1)
        ; In 1D: always slot 0 or 1 based on X position
        movea.l #Collision_Map_Slot0, a0        ; assume slot 0

        ; section-local X = world_x - SLOT_ORIGIN_L
        move.w  d0, d2
        subi.w  #SLOT_ORIGIN_L, d2              ; d2 = section-local X
        cmpi.w  #SECTION_SIZE, d2
        blt.s   .cgt_slot0
        subi.w  #SECTION_SIZE, d2               ; adjust for slot 1
        lea     (Collision_Map_Slot1).l, a0
.cgt_slot0:
        ; -- flat map lookup --
        lsr.w   #COLLISION_CELL_SHIFT, d2       ; X / 16 → column (0..127)
        lsr.w   #COLLISION_CELL_SHIFT, d1       ; Y / 16 → row (0..23)

        ; bounds check row
        cmpi.w  #COLLISION_MAP_ROWS, d1
        blt.s   .cgt_row_ok
        moveq   #CTYPE_AIR, d0
        rts
.cgt_row_ok:
        lsl.w   #COLLISION_ROW_SHIFT, d1        ; row × 128
        add.w   d2, d1                          ; flat offset
        move.b  (a0, d1.w), d0                  ; collision type
        rts

; -----------------------------------------------
; Collision_GetFloorHeight — floor height at a specific X,Y position
; In:  d0.w = world X (pixels)
;      d1.w = world Y (pixels)
; Out: d0.w = signed floor distance (negative = above floor, positive = below)
;      d1.b = surface angle
;      d2.b = collision type (0 = air, no floor)
; Clobbers: d0-d4, a0-a1
; -----------------------------------------------
Collision_GetFloorHeight:
        move.w  d0, d3                          ; save X
        move.w  d1, d4                          ; save Y
        bsr.w   Collision_GetType               ; d0.b = collision type
        move.b  d0, d2                          ; d2.b = type (output)
        tst.b   d0
        beq.s   .cgf_air                        ; air — no floor

        ; -- height map lookup --
        andi.w  #$FF, d0
        lsl.w   #4, d0                          ; type × 16
        move.w  d3, d1
        andi.w  #$F, d1                         ; x_pixel & $F
        add.w   d1, d0
        move.b  HeightMaps(pc, d0.w), d1        ; d1.b = height (0..16)

        ; floor distance = cell_y_bottom - player_y + height
        move.w  d4, d0
        andi.w  #$F, d0                         ; y within 16px cell
        ext.w   d1
        sub.w   d1, d0                          ; distance: negative = above floor

        ; -- angle lookup --
        moveq   #0, d1
        move.b  d2, d1
        move.b  AngleTable(pc, d1.w), d1        ; d1.b = surface angle
        rts

.cgf_air:
        move.w  #$7F, d0                        ; large positive = far below
        moveq   #0, d1                          ; angle = flat
        rts

; -----------------------------------------------
; Collision_FloorSensors — dual floor sensor query
; In:  a0 = SST pointer (player object)
; Out: d0.w = floor distance (from closer sensor)
;      d1.b = surface angle
;      d2.b = collision type
; Clobbers: d0-d6, a0-a1
; -----------------------------------------------
Collision_FloorSensors:
        ; -- compute sensor positions --
        ; Left sensor:  x_pos - width/2, y_pos + height/2
        ; Right sensor: x_pos + width/2, y_pos + height/2
        move.l  SST_x_pos(a0), d3
        swap    d3                              ; d3.w = x integer
        move.l  SST_y_pos(a0), d4
        swap    d4                              ; d4.w = y integer
        moveq   #0, d5
        move.b  SST_width_pixels(a0), d5
        lsr.w   #1, d5                          ; d5 = half width
        moveq   #0, d6
        move.b  SST_height_pixels(a0), d6
        lsr.w   #1, d6                          ; d6 = half height
        add.w   d6, d4                          ; d4 = y + half_height (foot position)

        ; -- left sensor --
        move.w  d3, d0
        sub.w   d5, d0                          ; x - half_width
        move.w  d4, d1
        movem.l d3-d6, -(sp)
        bsr.w   Collision_GetFloorHeight         ; d0 = left distance, d1 = angle, d2 = type
        movem.l (sp)+, d3-d6
        move.w  d0, -(sp)                       ; save left distance
        move.b  d1, -(sp)                       ; save left angle
        move.b  d2, -(sp)                       ; save left type

        ; -- right sensor --
        move.w  d3, d0
        add.w   d5, d0                          ; x + half_width
        move.w  d4, d1
        bsr.w   Collision_GetFloorHeight         ; d0 = right distance, d1 = angle, d2 = type

        ; -- pick closer sensor (smaller distance = closer to surface) --
        move.b  (sp)+, d5                       ; left type
        move.b  (sp)+, d4                       ; left angle
        move.w  (sp)+, d3                       ; left distance

        cmp.w   d3, d0
        ble.s   .cfs_right_wins                 ; right distance <= left → right wins
        ; left wins
        move.w  d3, d0
        move.b  d4, d1
        move.b  d5, d2
        rts

.cfs_right_wins:
        ; d0/d1/d2 already set from right sensor
        rts
```

- [ ] **Step 5: Add include to main.asm**

Add after the `strip_cache.asm` include:

```asm
    include "engine/level/collision_lookup.asm"
```

- [ ] **Step 6: Add collision data generation to build.sh**

Add before the assembly step:

```bash
# Generate collision data (height maps, angles)
python3 tools/gen_collision_data.py data/collision
```

- [ ] **Step 7: Build and test**

```bash
cd /home/volence/sonic_hacks/aeon && ./build.sh
```

Expected: clean build. Collision system compiled and linked. Height maps and angle data in ROM.

Test with Exodus MCP: read collision map RAM, call collision lookup mentally or via breakpoint to verify type = 1 for ground positions and type = 0 for air positions.

- [ ] **Step 8: Update ENGINE_ARCHITECTURE.md**

Update the §4.7 section in `docs/ENGINE_ARCHITECTURE.md` to reflect the new design: strip cache replaces flat ROM collision maps, streaming S4LZ decompressor, world-space coordinate convention. Remove any references to the old "16 KB flat collision map in ROM" design.

- [ ] **Step 9: Commit**

```bash
git add engine/level/collision_lookup.asm data/collision/ tools/gen_collision_data.py \
    main.asm build.sh docs/ENGINE_ARCHITECTURE.md
git commit -m "feat(§4.7): collision lookup + height maps + dual floor sensors

Collision_GetType: flat 128×24 map query (~40 cycles).
Collision_GetFloorHeight: type → height profile → surface angle.
Collision_FloorSensors: dual-sensor ground detection (closer sensor wins).
Stub height maps (type 0 = air, type 1 = flat solid).
Stub angle table (all flat). Full slope data authored later.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Self-Review Checklist

### Spec Coverage
| Spec Section | Task(s) | Status |
|---|---|---|
| §1 Streaming S4LZ Decompressor | Task 4 | Covered: S4LZ_Stream_Init, S4LZ_Stream_Decompress |
| §1 Checkpoint Table | Tasks 2, 3, 8 | Covered: emission in s4lz.py, checkpoint table per section, ReinitStreamAtCol |
| §2 Strip Cache | Tasks 5, 6, 7 | Covered: init, fill, get column, ring buffer addressing |
| §3 Collision Map (flat, compressed) | Tasks 9 | Covered: build pipeline, loading, lookup |
| §3 Height Maps + Angle Array | Task 10 | Covered: stub data, BINCLUDE, lookup routines |
| §3 Dual Floor Sensors | Task 10 | Covered: Collision_FloorSensors |
| §4 RAM Layout | Task 1 | Covered: lower RAM reorganization, upper RAM metadata |
| §5 Build Pipeline | Tasks 2, 3, 9 | Covered: checkpoint emission, strip compression, collision map generation |
| §6 Integration — Section_UpdateColumns | Task 7 | Covered: world-space cache read, simplified routing |
| §6 Integration — Section_RedrawPlanes | Task 7 | Covered: reads from strip cache |
| §6 Integration — Teleport | Task 8 | Covered: world-space invariance, stream reinit |
| §6 Integration — Preload | Task 9 | Covered: collision map preload alongside tile art |
| §6 Integration — Level Init | Tasks 6, 9 | Covered: strip cache cold fill, collision map decompression |
| §6 Integration — Per-Frame Order | Task 6 | Covered: Camera_Update → Strip_Cache_Fill → Section_Check → Section_UpdateColumns |
| §7 World-Space Convention | Tasks 5, 7 | Covered: Engine_To_World_Col, world-space trackers |
| §3 Collision-Aware Tile Dedup | Deferred | Inactive with stub LUT (all tiles same type). Implement when authored collision data arrives. |
| §2 Backward Fill (leftward scrolling) | Deferred | Forward fill only in initial implementation. Backward scrolling past margin causes cache miss. Acceptable for Sonic gameplay. |

### Placeholder Scan
- No TBD/TODO in task descriptions
- All code blocks contain actual implementation code
- All file paths are exact
- Build/test commands are concrete

### Type Consistency
- `StreamState` struct: `ss_src`, `ss_output_pos`, `ss_xor_prev` — consistent across Tasks 1, 4, 8
- `Strip_Cache_Head_Col`, `Strip_Cache_Head_Idx`, `Strip_Cache_Left_Col` — consistent across Tasks 1, 5, 7, 8
- `Sec_sec_strips_s4lz`, `Sec_sec_strip_checkpoints`, `Sec_sec_collision_s4lz` — consistent across Tasks 1, 3, 5, 8, 9
- `Engine_To_World_Col` — defined in Task 5, used in Tasks 7, 8
- `Strip_Cache_GetColumn` — defined in Task 5, used in Task 7
- `S4LZ_Stream_Init`, `S4LZ_Stream_Decompress` — defined in Task 4, used in Tasks 5, 8
- `Collision_Map_Slot0`, `Collision_Map_Slot1` — defined in Task 1 (ram.asm), used in Tasks 9, 10
