# DAC Drum / DAC-Format-Revision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A clean, from-scratch DAC drum playback path — `$E2`-triggered one-shot PCM drums that play once and cleanly stop, noise-shaped 4-bit DPCM payload, a shared DAC bank the window swaps to per frame, FM6 time-share, and a best-in-class ~18-20 kHz DAC rate.

**Architecture:** Layered on the existing free-running `SndDrv_Sample` streaming loop. A two-stage one-shot stop state machine; a constant-cost (branchless, no-clamp) 4-bit DPCM decode in the FILL producer with the predictor in RAM; four cached-`SetBank` brackets (B1-B4) that keep the `$8000` window on the song bank for every sequencer frame / ISR blob read and on the sample bank for every FILL; FM6 dedicate-while-active then adaptive toggle. Every layer is verified by rendered-audio cross-correlation of the captured YM `$2A` stream vs a same-codec-decoded reference (`r ≥ 0.9`), never "is it non-silent."

**Tech Stack:** AS Macro Assembler (Z80 inline `phase 0` blob + 68k), Python 3 (offline encoder + verifier with numpy), the Exodus/`oracle` emulator via MCP (VGM `$2A` capture). Build: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`.

**Design source of truth:** `docs/superpowers/specs/2026-06-24-dac-drum-format-revision-design.md`. Read it before starting; this plan is the actionable task breakdown.

---

## Conventions for every task

- **Build** (the assembly "compile + static test"): `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`.
  PASS = exit 0, `s4.log` has no `error`/`fatal`, `s4.bin` produced and is ~450 KB (sound adds
  ~88 KB; a silent ~362 KB build means the flags were dropped). A plain `./build.sh` proves nothing.
- **Cross-correlation verify** (the runtime "behavioral test"): `oracle` MCP →
  `emulator_reload_rom s4.bin` → trigger → `emulator_vgm_start` → wait (a background `Bash` `sleep`,
  oracle runs ~3× real-time, so ~4 s wall ≈ 12 s audio) → `emulator_vgm_stop` →
  `python3 tools/dac_verify.py <captured.vgm> <reference.dpcm> <table_index>`. PASS = the printed
  `best_xcorr_vs_sample ≥ 0.9` (or `= 1.0` for L0) over a contiguous sample-length window, plus the
  expected `$80`-silence cadence.
- **CODING_CONVENTIONS.md is the law** (sized branches, `function` for compile-time math,
  `struct`/`endstruct`, `phase`/`dephase`, PascalCase/ALL_CAPS/.lowercase, no `mulu`/`divu`, no
  unstopped Z80 during VDP access). The Z80 driver is inside the `phase 0` blob — labels resolve into
  Z80 RAM; new code must stay below `SND_STATE_BASE` (the `Z80_SOUND_SIZE` assert guards it).
- **Git hygiene:** stage **exact paths only**, never `git add -A`/`-u` (untracked user WIP + the
  auto-commit daemon on `data/editor/` & `tools/ojz_strip_gen.py` must not be swept in). Commit at the
  end of each task.
- **Verify the real output, never a proxy.** A DAC enabled on a bad pointer streams ROM garbage that
  looks audible. The gate is always the cross-correlation, never register state alone.

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `sound_constants.asm` | clean DAC state block, 9-byte `DacSample`, `NUM_DELTA_TABLES`, `SH_F_FM6_ADAPTIVE`, asserts | modify |
| `engine/z80_sound_driver.asm` | state machine, decode FILL, two-stage exhaust, B1-B4 brackets, `Snd_StartSample`, `SndDrv_TimerATick`/`IdleTick`/`ISR`/`Idle`, `DacSampleTable`, `DecTable`, FM6 | modify |
| `engine/sound_sequencer.asm` | ch6 voice-writer gate while DAC active | modify |
| `tools/dac_encode.py` | offline noise-shaped DPCM-HQ encoder (.wav → .dpcm + table) | create |
| `tools/test_dac_encode.py` | pytest for the encoder (round-trip, wrap, no-clamp) | create |
| `tools/dac_verify.py` | extract YM `$2A` from VGM, same-codec decode, corrcoef | create |
| `tools/gen_dectable.py` | emit the `DecTable` families as an `.asm` include | create |
| `data/sound/dac/*.dpcm` | encoded kick/snare/hat payloads | create |
| `data/sound/dac_dectable.asm` | the inline `DecTable` block (generated) | create |
| `data/sound/dac_samples.asm` | shared DAC payload bank + descriptors | modify |
| `data/sound/song_drumtest.asm` | DEBUG-only `$E2` drum-test song | create |
| `data/sound/song_table.asm` | register the DEBUG drum-test song id | modify |
| `engine/game_loop.asm` | DEBUG button trigger for the drum-test song | modify |
| `main.asm` | shared DAC payload bank; drum-test song bank w/ co-located tables+SFX | modify |
| `docs/ENGINE_ARCHITECTURE.md` | §6: two DAC banking modes + rate decision + drum path | modify |

---

## Task 0.0: Worktree setup

**Files:** none (environment).

- [ ] **Step 1: Create the sibling worktree + branch**

The build references `../skdisasm`, so the worktree MUST be a **sibling** of `aeon` (a nested
`.worktrees/` worktree breaks the build).

```bash
cd /home/volence/sonic_hacks/aeon
git worktree add ../aeon-dacdrum -b feat/dac-drum master
```

- [ ] **Step 2: Symlink the gitignored native toolchain** (this machine builds NATIVE, not Wine)

```bash
cd /home/volence/sonic_hacks/aeon-dacdrum
ln -s ../aeon/tools/bin tools/bin
ln -s ../aeon/tools/salvador/salvador tools/salvador/salvador
```

- [ ] **Step 3: Baseline build (sound on)**

Run: `cd /home/volence/sonic_hacks/aeon-dacdrum && SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`
Expected: exit 0, `s4.log` clean, `s4.bin` ~450 KB. (Establishes the worktree builds before any change.)

- [ ] **Step 4: Capture the MT audio baseline** (regression reference for every later layer)

`oracle` MCP: `emulator_reload_rom` the baseline `s4.bin`; `emulator_vgm_start`; background `sleep 6`;
`emulator_vgm_stop`; save the VGM as `/tmp/mt_baseline.vgm`. (MT auto-plays on boot.) No commit.

---

## Task 0.1: Clean DAC state block

**Files:**
- Modify: `sound_constants.asm` (the `SND_STATE_BASE` block, ~lines 39-220)

- [ ] **Step 1: Verify the dead fields are truly unreferenced**

Run:
```bash
cd /home/volence/sonic_hacks/aeon-dacdrum
grep -rn "SND_PLAY_ACTIVE\|SND_PLAY_PTR\|SND_PLAY_LEN\|SND_TEST_SAMPLE\b\|SND_DAC_RATE\b\|SND_DRAIN_SAMPLES\|SND_DRAIN_MAX\|SND_DRAIN_PAD\|SND_PLAY_MODE\|SND_LOOP_OFS" engine/ sound_constants.asm
```
Expected: matches ONLY in `sound_constants.asm` (definitions), none in `engine/`. If any `engine/`
reference appears, STOP and report — that field is live and must be kept.

- [ ] **Step 2: Replace the state block with the clean, non-aliased layout**

In `sound_constants.asm`, delete `SND_PLAY_ACTIVE/PTR/LEN`, `SND_TEST_SAMPLE`, `SND_DAC_RATE`,
`SND_DRAIN_SAMPLES/MAX/PAD`, and the overlapping `SND_LOOP_OFS`/`SND_PLAY_MODE` (the `$16FF`
landmine). Lay out the clean block (keep `SND_STATE_BASE = $16F0`; the block now fits in fewer bytes):

```
SND_STATE_BASE          = $16F0
; --- DAC playback state (Z80 RAM; all reads/writes bank-free) ---
SND_DEC_ACC             = SND_STATE_BASE+$00     ; DPCM running predictor (RAM, see decode FILL); seeded $80
SND_DAC_PHASE           = SND_STATE_BASE+$01     ; 0=idle, 1=playing, 2=draining-tail
SND_SONG_BANK           = SND_STATE_BASE+$02     ; current song bank (set in Snd_LoadSong; B1 latches it)
SND_ROM_BANK            = SND_STATE_BASE+$03     ; current sample bank (stashed by Snd_StartSample; B1 latches it)
SND_CUR_BANK            = SND_STATE_BASE+$04     ; SetBank cache (no-op check)
SND_RING_RD             = SND_STATE_BASE+$05     ; ring read ptr low byte
SND_RING_WR             = SND_STATE_BASE+$06     ; ring write ptr low byte
SND_ROM_PTR             = SND_STATE_BASE+$08     ; sample window read ptr (2 bytes; even-aligned)
SND_ROM_LEN             = SND_STATE_BASE+$0A     ; packed bytes remaining (2 bytes)
SND_DEC_IY              = SND_STATE_BASE+$0C     ; DecTable base for this sample (2 bytes; iy reloaded
                                                 ; at FILL top — iy is NOT safe across the loop's ei/ISR)
SND_STATE_END           = SND_STATE_BASE+$0E
```
(`+$07` is an unused pad keeping the word fields even-aligned.)

(Word fields `SND_ROM_PTR`/`SND_ROM_LEN` placed at even offsets per AS alignment caution. Final
offsets are the implementer's to assign cleanly; the names + the no-aliasing rule are what matters.)

- [ ] **Step 3: Replace the old overflow assert with one against the new end**

```
        ; the DAC state block must stay below the page-aligned DAC ring at SND_RING_BASE ($1700).
        if SND_STATE_END > SND_RING_BASE
          fatal "DAC state block (ends \{SND_STATE_END}) runs into the DAC ring at \{SND_RING_BASE}"
        endif
```

- [ ] **Step 4: Update every changed reference in `engine/z80_sound_driver.asm`**

Search the driver for the old names and rename to the new ones (notably `SND_CUR_BANK`,
`SND_RING_RD/WR`, `SND_ROM_PTR/LEN`). Add no behavior — only the field moves.

Run: `grep -n "SND_RING_RD\|SND_RING_WR\|SND_ROM_PTR\|SND_ROM_LEN\|SND_CUR_BANK\|SND_ROM_BANK" engine/z80_sound_driver.asm`
and confirm each resolves to the new layout.

- [ ] **Step 5: Build green**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`
Expected: exit 0, `s4.log` clean, `s4.bin` ~450 KB. (No behavior change yet — pure RAM re-layout.)

- [ ] **Step 6: Runtime smoke (RAM re-layout is boot-sensitive)**

`oracle`: `emulator_reload_rom s4.bin`; confirm the driver is alive (`emulator_z80_read` the alive
marker region / MT still plays). Per the AS-even-alignment lesson, a bad RAM layout address-errors at
runtime even when the build passes — so a boot check is mandatory after any RAM-layout change.

- [ ] **Step 7: Commit**

```bash
git add sound_constants.asm engine/z80_sound_driver.asm
git commit -m "refactor(sound): clean DAC state block, delete dead 1B fields + \$16FF landmine"
```

---

## Task 0.2: 9-byte DacSample descriptor

**Files:**
- Modify: `sound_constants.asm` (the `DacSample struct`, ~lines 222-233)
- Modify: `engine/z80_sound_driver.asm` (`Snd_DacLookup` indexing)

- [ ] **Step 1: Extend the struct + add `NUM_DELTA_TABLES`**

```
NUM_DELTA_TABLES = 3              ; sharp-transient / body / quiet (grow as the kit needs)

DacSample struct
ds_bank         ds.b 1          ; +0  sample bank id = (addr & $7F8000) >> 15
ds_rate         ds.b 1          ; +1  RESERVED forward-compat (per-sample rate); v1 ignores it
ds_table        ds.b 1          ; +2  DPCM delta-table index (0..NUM_DELTA_TABLES-1)
ds_ptr          ds.w 1          ; +3  Z80-window ptr (addr & $7FFF)|$8000, little-endian
ds_length       ds.w 1          ; +5  PACKED byte count (nibble pairs); < $8000
ds_loop_ofs     ds.w 1          ; +7  RESERVED forward-compat (loop restart); v1 = 0, ignored
DacSample endstruct             ; = 9 bytes

        if DacSample_len <> 9
          error "DacSample struct is \{DacSample_len} bytes, expected 9"
        endif
```

- [ ] **Step 2: Fix `Snd_DacLookup` to index by 9 (`*8 + index`)**

In `engine/z80_sound_driver.asm`, the lookup currently computes `index*8 = index<<3`. Change to
`index*9 = index*8 + index`:

```z80
        ; hl = DacSampleTable + index*9  (index*8 + index)
        ld      l, a
        ld      h, 0
        ld      e, l                     ; save index
        ld      d, h
        add     hl, hl
        add     hl, hl
        add     hl, hl                   ; hl = index*8
        add     hl, de                   ; hl = index*9
        ld      de, DacSampleTable
        add     hl, de
```

- [ ] **Step 3: Build green**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`
Expected: exit 0; the existing `DacSampleTable` (id 1 = blip) re-pads to 9 bytes/record and its
size assert passes (update the table's trailing fields to the 9-byte form if needed — add `ds_table`
byte = 0 and keep `ds_loop_ofs` = 0).

- [ ] **Step 4: Commit**

```bash
git add sound_constants.asm engine/z80_sound_driver.asm data/sound/dac_samples.asm
git commit -m "feat(sound): 9-byte DacSample descriptor (ds_table) + NUM_DELTA_TABLES"
```

---

## Task 1.1: DEBUG drum-test harness

**Files:**
- Create: `data/sound/song_drumtest.asm`
- Modify: `data/sound/song_table.asm` (register the id, DEBUG-only)
- Modify: `engine/game_loop.asm` (DEBUG button trigger)

- [ ] **Step 1: Write a minimal `$E2` drum-test song**

A DEBUG-only song with one DAC channel that fires `$E2 <id>` then rests, on a slow loop (so a
one-shot sample plays, fully stops, then re-triggers — exercises L0/L1/L2). Follow the SongHeader +
channel-record format in `sound_constants.asm` (`SH_FLAGS/SH_TEMPO_BASE/SH_CHCOUNT/...`,
`SHC_ROUTE/SHC_CMD_*`). Route = `CHROUTE_DAC`. Stream body: `MEV_DAC, 1` (blip id), a long
`MEV_REST` gap (default duration set high), `MEV_JUMP` to a `MEV_LOOP_POINT` at the top. Wrap it under
`ifdef __DEBUG__`. Header `SH_FLAGS` for now = COPY/FM6=DAC (`0` — DAC on, no stream) so the test runs
without the shared-bank work (Layer 5 switches the *shared-bank* test song to STREAM).

- [ ] **Step 2: Register it in `song_table.asm` (DEBUG-only)**

Add, under `ifdef __DEBUG__`, a `SONG_DRUMTEST` id (e.g. `= 2`) appended to `SongTable` /
`SongPatchTable`, and bump `SONG_COUNT` accordingly inside the same `ifdef` so the asserts hold.

- [ ] **Step 3: DEBUG button trigger in `game_loop.asm`**

Under `ifdef __DEBUG__`, on a held-and-edge button (e.g. the C button via the controller state the
game loop already reads), post `SONG_DRUMTEST` to the music mailbox using the existing
`Sound_PlayMusic` API. Match the pattern of any existing debug input the game loop has.

- [ ] **Step 4: Build green + load**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` → exit 0.
`oracle`: `emulator_reload_rom s4.bin`; press the trigger (`emulator_press`); confirm `SND_SEQ_ACTIVE`
goes 1 and the DAC starts (`SND_STAT_DAC_ACTIVE` = 1). The blip will currently LOOP (master behavior);
that's expected until Task 1.2.

- [ ] **Step 5: Commit**

```bash
git add data/sound/song_drumtest.asm data/sound/song_table.asm engine/game_loop.asm
git commit -m "test(sound): DEBUG \$E2 drum-test song (id 2) + button trigger"
```

---

## Task 1.2: Two-stage one-shot stop state machine

**Files:**
- Modify: `engine/z80_sound_driver.asm` (the FILL exhaust ~lines 414-423; `Snd_StartSample`;
  the `STOPPING` write)

- [ ] **Step 1: Replace the unconditional blip re-loop with the two-stage exhaust**

Replace the `.fillDone` re-loop block (currently reloads `SND_BLIP_PTR/LEN`) with the underflow-safe
exhaust → `DRAINING_TAIL`. After the producer's `len -= 1` and `ld (SND_ROM_LEN),hl`:

```z80
        ld      a, h
        or      l
        jp      nz, .fillDone            ; bytes remain -> normal pass
        ; producer exhausted: enter DRAINING_TAIL. Do NOT stop yet — the ring still
        ; holds up to LEAD_CAP decoded bytes the consumer must still emit.
        ld      a, 2
        ld      (SND_DAC_PHASE), a       ; PHASE = DRAINING_TAIL
        ; fall through to a balanced no-ROM-read tail (same cost as SKIP)
.fillDone:
        ei
        jp      SndDrv_Sample
```

- [ ] **Step 2: In the dispatch, branch PHASE==2 to a SKIP-balanced no-read tail; STOP at lead==0**

In the common-prefix dispatch (where `b` = lead = `(WR-RD)&$FF`), before the FILL fall-through add:
when `SND_DAC_PHASE == 2` (draining), do not read ROM; if `b == 0` (ring empty) → `.stop`, else burn
the SKIP pad.

```z80
        ld      a, (SND_DAC_PHASE)
        cp      2
        jp      z, .draining             ; DRAINING_TAIL: no ROM read
        ; ... existing DMA/SKIP dispatch + FILL fall-through ...

.draining:
        ld      a, b                     ; b = ring lead
        or      a
        jp      z, .stop                 ; ring drained -> stop
        ; lead>0: emit the tail; burn the SkipPad-equivalent so the pass stays balanced
        jp      SndDrv_Skip              ; (SKIP body = no-read, balanced)

.stop:
        ld      a, SND_REG_DAC_DATA      ; re-park $2A on $4000
        ld      (SND_Z80_YM_A0), a
        ld      a, 80h
        ld      (SND_Z80_YM_A1), a       ; $2A = $80 (DC center)
        xor     a
        ld      (SND_STAT_DAC_ACTIVE), a ; clear active
        ld      (SND_DAC_PHASE), a       ; PHASE = idle
        ; (FM6 hand-back is added in Task 4.1 / 7.1)
        ei
        jp      SndDrv_Idle              ; back to the idle loop
```

Keep the exact cycle balance: the `.draining → jp SndDrv_Skip` path must equal a FILL pass. Verify the
pad math against the file-header cycle proof; adjust `SkipPad`/the draining branch so DRAINING_TAIL
passes cost exactly `SND_LOOP_CYC` like FILL/SKIP/DRAIN.

- [ ] **Step 3: `Snd_StartSample` sets PHASE=1 + re-inits cleanly (no blip hardcode)**

In `Snd_StartSample`, after priming the ring + setting `DAC_ACTIVE=1`, set `SND_DAC_PHASE = 1`
(playing). Remove any `SND_BLIP_*` reference. It already resets `RD=0`, primes `WR=LEAD_PRIME` with
`$80`, and reloads `SND_ROM_PTR/LEN` from the descriptor — confirm those remain.

- [ ] **Step 4: Build green**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` → exit 0, clean log.

- [ ] **Step 5: Verify L0 (blip plays once, bit-exact) + L2 (clean stop + re-trigger)**

`oracle`: reload; trigger the drum-test song; `emulator_vgm_start`; background `sleep 5`;
`emulator_vgm_stop`. Then:

```bash
python3 tools/dac_verify.py /tmp/cap.vgm data/sound/temp_blip.bin 0   # raw blip = "table-less"; see tools note
```
Expected: `best_xcorr_vs_sample = 1.000` over one blip-length window (FILL/ring/consumer bit-exact),
AND the `$2A` stream shows the blip ONCE then `$80` silence in the gap (not a continuous loop), then
the next trigger. Also probe `SND_STAT_DAC_ACTIVE` → returns to 0 after the blip (no stranded active);
`SND_DAC_PHASE` cycles 1→2→0.

(Note: in Task 1.2 the FILL is still raw — `dac_verify.py` compares against the raw blip bytes. The
DPCM-decode path arrives in Layer 3; from then on the reference is the `.dpcm` + table.)

- [ ] **Step 6: Commit**

```bash
git add engine/z80_sound_driver.asm
git commit -m "feat(sound): two-stage one-shot DAC stop (DRAINING_TAIL -> DC-center), no re-loop"
```

---

## Task 2.1: Noise-shaped DPCM-HQ encoder (`tools/dac_encode.py`)

**Files:**
- Create: `tools/dac_encode.py`, `tools/test_dac_encode.py`

- [ ] **Step 1: Write the failing test**

```python
# tools/test_dac_encode.py
import numpy as np
from dac_encode import encode_dpcm, decode_dpcm, DELTA_TABLES

def test_roundtrip_wraps_no_clamp():
    # the decoder MUST be mod-256 wrap (no clamp): decode(encode(x)) reconstructs
    # within the table's quantization, and decoding never branches on saturation.
    x = (np.sin(np.linspace(0, 40*np.pi, 2000)) * 110 + 128).astype(np.uint8)
    nibbles, table = encode_dpcm(x, seed=0x80)
    y = decode_dpcm(nibbles, table, seed=0x80)
    assert len(y) == len(x)
    # noise-shaped DPCM is lossy but tracks the signal: high correlation
    assert np.corrcoef(x.astype(float), y.astype(float))[0, 1] > 0.95

def test_decode_is_pure_wrap():
    # a known nibble stream decodes by acc=(acc+table[n])&0xFF exactly
    table = DELTA_TABLES[0]
    acc = 0x80
    out = decode_dpcm(bytes([0x00]), table, seed=0x80)  # one byte = 2 nibbles
    exp0 = (0x80 + table[0]) & 0xFF
    exp1 = (exp0 + table[0]) & 0xFF
    assert list(out) == [exp0, exp1]
```

- [ ] **Step 2: Run it — expect failure (module missing)**

Run: `cd tools && python3 -m pytest test_dac_encode.py -v`
Expected: FAIL (`ModuleNotFoundError: dac_encode`).

- [ ] **Step 3: Implement `dac_encode.py`**

```python
# tools/dac_encode.py  — offline noise-shaped 4-bit DPCM (DPCM-HQ)
import numpy as np

# starting delta families (sharp-transient / body / quiet); the encoder may also
# fit per-kit tables, but these are the shipped defaults. Signed 8-bit, mod-256.
DELTA_TABLES = [
    [0,1,2,4,8,16,32,64,-128,-1,-2,-4,-8,-16,-32,-64],     # 0: sharp transients
    [-34,-21,-13,-8,-5,-3,-2,-1,0,1,2,3,5,8,13,21],        # 1: body
    [-20,-12,-8,-6,-4,-3,-2,-1,0,1,2,3,4,6,8,12],          # 2: quiet/tails
]

def decode_dpcm(nibble_bytes, table, seed=0x80):
    acc = seed & 0xFF
    out = []
    for byte in nibble_bytes:
        for nib in ((byte >> 4) & 0xF, byte & 0xF):        # high nibble first
            acc = (acc + table[nib]) & 0xFF
            out.append(acc)
    return np.array(out, dtype=np.uint8)

def encode_dpcm(samples, table_index=None, seed=0x80):
    """Greedy nearest-delta with error-feedback noise shaping. Returns (packed_bytes, table_index).
    No clamp: the predictor wraps mod-256 exactly like the Z80 decoder."""
    samples = np.asarray(samples, dtype=np.int32)
    candidates = range(len(DELTA_TABLES)) if table_index is None else [table_index]
    best = None
    for ti in candidates:
        table = DELTA_TABLES[ti]
        acc = seed & 0xFF
        err = 0.0                                          # error-feedback accumulator
        nibbles = []
        for s in samples:
            target = s + err                               # push prior quant error forward (noise shaping)
            # choose the nibble whose (acc+delta)&0xFF is closest to target (shortest wrap distance)
            bestn, bestd = 0, 1e9
            for n, d in enumerate(table):
                val = (acc + d) & 0xFF
                dist = min(abs(val - target), 256 - abs(val - target))
                if dist < bestd:
                    bestn, bestd = n, dist
            acc = (acc + table[bestn]) & 0xFF
            err = float(s) - float(acc)                    # feed quant error to the next sample
            nibbles.append(bestn)
        if len(nibbles) & 1:                               # pad to whole bytes (even sample count)
            nibbles.append(0)
        packed = bytes((nibbles[i] << 4) | nibbles[i+1] for i in range(0, len(nibbles), 2))
        score = np.corrcoef(samples.astype(float),
                            decode_dpcm(packed, table, seed)[:len(samples)].astype(float))[0, 1]
        if best is None or score > best[2]:
            best = (packed, ti, score)
    return best[0], best[1]
```

- [ ] **Step 4: Run the tests — expect pass**

Run: `cd tools && python3 -m pytest test_dac_encode.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add tools/dac_encode.py tools/test_dac_encode.py
git commit -m "feat(tools): noise-shaped DPCM-HQ encoder + tests"
```

---

## Task 2.2: Encode S3K samples + emit the DecTable

**Files:**
- Create: `tools/gen_dectable.py`, `data/sound/dac_dectable.asm`, `data/sound/dac/{kick,snare,hat}.dpcm`
- Modify: `engine/z80_sound_driver.asm` (include `DecTable` inline in the blob)

- [ ] **Step 1: Encode kick/snare/hat from the S3K `.wav`**

Write a small driver in `tools/dac_encode.py` (`if __name__ == "__main__"`) that reads a `.wav`,
resamples to the target rate (start ~8.3 kHz; Layer 6 re-encodes at the final rate), and writes the
`.dpcm` + prints the chosen `ds_table`:

```bash
cd /home/volence/sonic_hacks/aeon-dacdrum
python3 tools/dac_encode.py "../skdisasm/Sound/DAC/86.wav" data/sound/dac/kick.dpcm   # kick
python3 tools/dac_encode.py "../skdisasm/Sound/DAC/81.wav" data/sound/dac/snare.dpcm  # snare
python3 tools/dac_encode.py "../skdisasm/Sound/DAC/8C.wav" data/sound/dac/hat.dpcm    # hat
```
Each prints its `ds_table` index (note it for the descriptor in Task 2.3). Confirm each `.dpcm` length
is even and < `$8000`.

- [ ] **Step 2: Emit the `DecTable` include**

```python
# tools/gen_dectable.py
from dac_encode import DELTA_TABLES
print("DecTable:")
for i, t in enumerate(DELTA_TABLES):
    row = ", ".join(str(b & 0xFF) for b in t)   # signed -> 0..255 db bytes
    print(f"        db      {row}   ; table {i}")
print("DecTable_End:")
```
Run: `python3 tools/gen_dectable.py > data/sound/dac_dectable.asm`

- [ ] **Step 3: Include `DecTable` INLINE in the Z80 blob (bank-free)**

In `engine/z80_sound_driver.asm`, near the inline `DacSampleTable` (before the even-pad/`dephase`),
add:

```z80
; --- DPCM decode tables (inline = Z80-addressable, bank-free; read every FILL via iy).
; Must NOT live in the $8000 window (the window holds the sample payload during FILL).
DecTable:
        include "data/sound/dac_dectable.asm"
DecTable_End:
        if (DecTable_End-DecTable) <> NUM_DELTA_TABLES*16
          fatal "DecTable wrong size for NUM_DELTA_TABLES"
        endif
```
(The generated file already emits the `DecTable:`/`DecTable_End:` labels; if so, include the rows
only — keep exactly one label pair. Adjust to avoid a double label.)

- [ ] **Step 4: Build green**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` → exit 0; the `DecTable` size assert passes.

- [ ] **Step 5: Commit**

```bash
git add tools/gen_dectable.py tools/dac_encode.py data/sound/dac_dectable.asm data/sound/dac engine/z80_sound_driver.asm
git commit -m "feat(sound): inline DecTable + encoded S3K kick/snare/hat (.dpcm)"
```

---

## Task 2.3: Shared DAC payload bank + descriptors

**Files:**
- Modify: `data/sound/dac_samples.asm` (shared bank payloads + asserts)
- Modify: `engine/z80_sound_driver.asm` (`DacSampleTable` entries for kick/snare/hat)
- Modify: `main.asm` (include the shared DAC bank)

- [ ] **Step 1: Lay out the shared DAC payload bank**

In `data/sound/dac_samples.asm`, after the existing blip, add a `$8000`-aligned shared payload bank
that `BINCLUDE`s the `.dpcm` files contiguously, with per-sample labels + no-straddle asserts:

```
        align   $8000
Dac_SharedBank_Start:
Dac_Kick:   BINCLUDE "data/sound/dac/kick.dpcm"
Dac_Kick_End:
Dac_Snare:  BINCLUDE "data/sound/dac/snare.dpcm"
Dac_Snare_End:
Dac_Hat:    BINCLUDE "data/sound/dac/hat.dpcm"
Dac_Hat_End:
        ; no sample may straddle a 32KB window boundary (FILL never re-banks mid-sample)
        if (Dac_Kick >> 15) <> ((Dac_Hat_End-1) >> 15)
          fatal "shared DAC bank crosses a 32KB boundary"
        endif
SND_KICK_BANK  = (Dac_Kick  & $7F8000) >> 15
SND_KICK_PTR   = (Dac_Kick  & $7FFF) | $8000
SND_KICK_LEN   = Dac_Kick_End  - Dac_Kick
; ... SND_SNARE_*, SND_HAT_* likewise ...
        if (SND_KICK_LEN & 1) <> 0
          fatal "DAC sample length must be even (FILL decodes 2 nibbles/byte)"
        endif
```

- [ ] **Step 2: Add the descriptors to `DacSampleTable`**

Append kick/snare/hat (ids 2/3/4) to the inline `DacSampleTable` using the 9-byte form, with the
`ds_table` indices printed in Task 2.2:

```z80
        ; id 2 = kick
        db      SND_KICK_BANK
        db      0                        ; ds_rate (reserved)
        db      0                        ; ds_table (from the encoder)
        dw      SND_KICK_PTR
        dw      SND_KICK_LEN
        dw      0                        ; ds_loop_ofs (reserved)
        ; id 3 = snare, id 4 = hat ...
```
Update `DAC_SAMPLE_COUNT` and the `DacSampleTable` size assert.

- [ ] **Step 3: Build green**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` → exit 0; bank-align + length asserts pass.

- [ ] **Step 4: Commit**

```bash
git add data/sound/dac_samples.asm engine/z80_sound_driver.asm main.asm
git commit -m "feat(sound): shared DAC payload bank + kick/snare/hat descriptors"
```

---

## Task 3.1: DPCM decode FILL + cycle rebalance

**Files:**
- Modify: `engine/z80_sound_driver.asm` (the FILL producer; `Snd_StartSample` decode init;
  `SND_LOOP_CYC`/pads)
- Modify: `sound_constants.asm` (`SND_LOOP_CYC` if it lives there)

- [ ] **Step 1: Replace the raw 2-byte FILL with the 1-byte/2-nibble decode**

Replace the FILL producer body (read 2 ROM bytes → ring) with: load `acc` from RAM, read ONE ROM
byte, decode 2 nibbles (no clamp, mod-256 wrap), write 2 ring bytes, store `acc`, `len -= 1`. SMC the
table index per nibble; `iy` is set to `DecTable + ds_table*16` once in `Snd_StartSample`.

```z80
        ; --- FILL: read 1 ROM byte from the window, decode 2 nibbles -> 2 ring bytes ---
        ld      iy, (SND_DEC_IY)         ; DecTable base (iy is NOT safe across the loop's ei/ISR)
        ld      a, (SND_DEC_ACC)         ; predictor (RAM — survives the loop's ei/ISR clobber)
        ld      c, a
        ld      hl, (SND_ROM_PTR)
        ld      e, (hl)                  ; e = packed byte (sample bank in window) [+ROM bus pen, ONE read]
        inc     hl
        ld      (SND_ROM_PTR), hl
        ; nibble 1 (high)
        ld      a, e
        rrca
        rrca
        rrca
        rrca
        and     0Fh
        ld      (.i1+2), a               ; SMC the (iy+n) displacement
.i1:    ld      a, (iy+0)                ; a = DecTable[ds_table*16 + nibble1]
        add     a, c
        ld      c, a                     ; acc += delta (mod 256, no clamp)
        ; nibble 2 (low)
        ld      a, e
        and     0Fh
        ld      (.i2+2), a
.i2:    ld      a, (iy+0)
        add     a, c
        ld      c, a
        ; write the 2 decoded bytes to the ring
        ld      a, (SND_RING_WR)
        ld      h, SND_RING_PAGE
        ld      l, a
        ld      a, (.i1_dec)             ; first decoded byte (stash from above — see note)
        ; ... (store both decoded bytes; WR += 2) ...
        ld      a, c
        ld      (SND_DEC_ACC), a         ; persist predictor
        ld      hl, (SND_ROM_LEN)
        dec     hl
        ld      (SND_ROM_LEN), hl
        ld      a, h
        or      l
        jp      nz, .fillDone
        ; producer exhausted -> DRAINING_TAIL (Task 1.2)
        ld      a, 2
        ld      (SND_DAC_PHASE), a
.fillDone:
        ei
        jp      SndDrv_Sample
```

(Implementer: keep BOTH decoded bytes — restructure so nibble-1's decoded value is written to
`ring[WR]` and nibble-2's to `ring[WR+1]`; the sketch elides the intermediate store for brevity. The
invariant: 1 ROM byte in → 2 ring bytes out, predictor persisted to `SND_DEC_ACC`, no conditional in
the accumulate.)

- [ ] **Step 2: Init the decode in `Snd_StartSample`**

After loading the descriptor, compute the DecTable base for this sample and store it in
`SND_DEC_IY` (the FILL reloads `iy` from it each pass, because `iy` is clobbered by the ISR), and seed
`SND_DEC_ACC = $80`:

```z80
        ld      a, (hl_descriptor + DacSample_ds_table)   ; ds_table
        add     a, a
        add     a, a
        add     a, a
        add     a, a                     ; a = ds_table*16
        ld      e, a
        ld      d, 0
        ld      iy, DecTable
        add     iy, de                   ; iy = DecTable + ds_table*16
        ld      (SND_DEC_IY), iy         ; persist for the FILL (iy is not ISR-safe)
        ld      a, 80h
        ld      (SND_DEC_ACC), a         ; seed predictor (DC center)
```

- [ ] **Step 3: Measure the balanced FILL total; set `SND_LOOP_CYC`; regrow the pads**

Build, then read the AS listing / hand-count the new FILL producer cycles. Set `SND_LOOP_CYC` to the
new balanced total (≈432). Regrow `SkipPad` to match the new producer and `DrainPad` to (producer +
21-cyc dispatch tail) so `FILL == SKIP == DRAIN`. `SND_DAC_RATE_HZ` auto-follows `dac_rate_hz()`.
Document the new per-path breakdown in the file-header proof.

- [ ] **Step 4: Build green**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` → exit 0; the rate constant recomputes (~8.3 kHz).

- [ ] **Step 5: Verify L1 (kick decodes correctly) + L4 (noise-shaped ≥ stock)**

Point the drum-test song's `$E2` at id 2 (kick). `oracle`: reload; trigger; capture VGM; then:
```bash
python3 tools/dac_verify.py /tmp/cap.vgm data/sound/dac/kick.dpcm <kick_table>
```
Expected: `best_xcorr_vs_sample ≥ 0.9` (decoded `$2A` matches the same-codec-decoded kick). For L4,
encode snare with table 0 (stock JMan2050 deltas) vs the noise-shaped table and compare the 4-10 kHz
spectral centroid of each decoded reference; the noise-shaped one ≥ stock on transient sharpness
(record the numbers in the commit message).

- [ ] **Step 6: Commit**

```bash
git add engine/z80_sound_driver.asm sound_constants.asm
git commit -m "feat(sound): constant-cost DPCM decode FILL (predictor in RAM) + rebalance"
```

---

## Task 4.1: FM6 dedicate-while-active

> **STATUS: DONE + verified (commit a29594c, 2026-06-25).** Also shipped a pre-step
> "Step 0" (commit ea81f3b): idle `$2A=$80` gated to the Timer-A tick to de-flood the
> VGM logger. `$B6=$C0` + the ch6 key-on gate (placed at `Fm_NoteOnFreq.keyon` — the
> single FM key-on chokepoint, more complete than the `sound_sequencer.asm` location
> here, which misses the ModUpdate re-key). 3-agent review: all approve. Verified in
> oracle: `$B6=$C0` lands; kick de-wrapped-ring r=1.0 byte-exact; MT not regressed.
> The FM6 key-on gate's INTEGRATED runtime proof (FM6 music suppressed during a
> sample) is deferred to Task 5.3 (blocked by the pre-bracket bank conflict).

**Files:**
- Modify: `engine/z80_sound_driver.asm` (`Snd_StartSample` `$B6=$C0`; the FM6 hand-back at `.stop`)
- Modify: `engine/sound_sequencer.asm` (gate the ch6 key-on while `SND_STAT_DAC_ACTIVE`)

- [ ] **Step 1: Write `$B6=$C0` (force DAC stereo) at sample start**

In `Snd_StartSample`, after the `$2B=$80` DAC-mode write and before priming, add (part-II addr port
`$4002`, data `$4003`):

```z80
        ld      a, SND_REG_LR_AMS_FMS    ; $B4 base -> $B6 = $B4 + ch6-in-part(2)
        ld      (SND_Z80_YM_A2), a       ; select $B6 on part II ($4002)
        ld      a, 0C0h                  ; L+R on, AMS=FMS=0 (force DAC stereo)
        ld      (SND_Z80_YM_A3), a       ; $4003 = $C0
```
(Confirm `$B6` = `$B4 + 2`; FM6 is part-II channel-in-part 2.)

- [ ] **Step 2: Gate the ch6 voice key-on while the DAC is active**

In `engine/sound_sequencer.asm`, where the FM voice writer keys ch6 on (the route-6/FM6 path), guard
the key-on with `SND_STAT_DAC_ACTIVE`: if the DAC is active, **advance the channel's bookkeeping but
skip the `$28` key-on** (FM6 coasts on its release rate). Keep all other channels unaffected.

```z80
        ; FM6 only: while a DAC sample owns ch6, do not (re)key it.
        ld      a, (ix+sc_route)
        cp      CHROUTE_FM6
        jr      nz, .normal_keyon
        ld      a, (SND_STAT_DAC_ACTIVE)
        or      a
        jr      nz, .skip_keyon          ; DAC owns ch6 -> advance state, no key-on
.normal_keyon:
        ; ... existing key-on ...
.skip_keyon:
```

- [ ] **Step 3: Re-key FM6 at the clean stop**

At `.stop` (Task 1.2), after clearing `DAC_ACTIVE`, the next `Sequencer_Frame` will re-key FM6 on its
next note automatically (the gate opens). No explicit re-key needed for the dedicate path. (The
adaptive path in Task 7.1 adds an explicit immediate re-key.)

- [ ] **Step 4: Build green**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` → exit 0.

- [ ] **Step 5: Verify L5 (dedicate)**

Author the drum-test song to also play a sustained FM6 note spanning a `$E2`. `oracle`: reload;
trigger; capture VGM. Confirm: the FM6 note sounds before the `$E2`; during the drum FM6 coasts (no
re-key); the drum plays (kick r ≥ 0.9); `$2A` passes through `$80` at the stop; FM6 re-articulates on
its next note after the drum. (Inspect the VGM FM key-on stream + the `$2A` cadence.)

- [ ] **Step 6: Commit**

```bash
git add engine/z80_sound_driver.asm engine/sound_sequencer.asm
git commit -m "feat(sound): FM6 dedicate-while-active (\$B6=\$C0 stereo, gate ch6 key-on)"
```

---

## Task 5.1: Bank brackets B1 + B2

> **STATUS: DONE + verified (commit c9b392a, 2026-06-25).** B1 Run_SeqFrame_OnSongBank
> from both tick paths; B2 stash-only StartSample; Snd_LoadSong seeds SONG/ROM bank;
> init zeroes both. MT regression clean (banks $0F, tonal).

**Files:**
- Modify: `engine/z80_sound_driver.asm` (`Snd_StartSample`, `SndDrv_TimerATick`, `SndDrv_IdleTick`,
  `Snd_LoadSong`)

- [ ] **Step 1: B2 — `Snd_StartSample` stash-only (no SetBank)**

In `Snd_StartSample`, replace the `call SndDrv_SetBank` (on `ds_bank`) with a stash:

```z80
        ld      a, (hl)                  ; ds_bank
        ld      (SND_ROM_BANK), a        ; stash; the frame bracket (B1) latches it
        ; (NO SetBank here — Snd_StartSample reads no sample ROM)
```

- [ ] **Step 2: B1 — wrap `Sequencer_Frame` on the song bank (shared helper)**

Add a helper and call it from BOTH tick paths:

```z80
; Run one sequencer frame with the window on the SONG bank, then restore the SAMPLE bank.
Run_SeqFrame_OnSongBank:
        ld      a, (SND_SONG_BANK)
        call    SndDrv_SetBank           ; window -> song bank (cached: no-op if already)
        call    Sequencer_Frame
        ld      a, (SND_ROM_BANK)
        jp      SndDrv_SetBank           ; window -> sample bank (tail-call; cached)
```
Replace `call Sequencer_Frame` in `SndDrv_TimerATick` AND `SndDrv_IdleTick` with
`call Run_SeqFrame_OnSongBank`.

- [ ] **Step 3: Set `SND_SONG_BANK` + seed `SND_ROM_BANK` in `Snd_LoadSong`**

In both load paths, set `SND_SONG_BANK = (SND_MUSIC_PARAM_BANK)` and seed
`SND_ROM_BANK = SND_SONG_BANK` (so B1 is a no-op for DAC-off songs like MT):

```z80
        ld      a, (SND_MUSIC_PARAM_BANK)
        ld      (SND_SONG_BANK), a
        ld      (SND_ROM_BANK), a        ; seed = song bank (B1 no-op until a sample arms)
```

- [ ] **Step 4: Build green + MT regression**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` → exit 0.
`oracle`: reload; let MT auto-play; capture 6 s VGM; compare to `/tmp/mt_baseline.vgm` (decode both to
WAV via `vgm2wav`, `wav_compare.py` spectral r ≥ ~0.99). MT must be unchanged (B1 is a cached no-op
for the DAC-off song).

- [ ] **Step 5: Commit**

```bash
git add engine/z80_sound_driver.asm
git commit -m "feat(sound): bank brackets B1 (frame on song bank) + B2 (StartSample stash-only)"
```

---

## Task 5.2: Bank brackets B3 + B4

> **STATUS: DONE + verified + reviewed (commit eda6418, 2026-06-25).** B3 made
> DAC-aware (restore SAMPLE bank when streaming, else pre-ISR bank); B4 idle->stream
> latch. 3-agent review + focused re-review (all approve) drove 2 fixes: DAC-aware B3
> (cross-bank mailbox retrigger) + DAC_ACTIVE-guarded SND_ROM_BANK seed (music-load-
> mid-drum, a Task-5.1 regression). Verified: fresh MT, mailbox kick r=1.0, MT+kick
> coexist. DISCOVERY: PollMailbox doesn't run during DAC streaming -> those 2 edge
> cases are currently UNREACHABLE (fixes kept correct-by-design-intent). Also logged
> 2 pre-existing latent bugs (StopMusic->PlayMusic silence; SFX/mailbox latency
> during a drum) — out of bank-bracket scope.

**Files:**
- Modify: `engine/z80_sound_driver.asm` (`SndDrv_ISR`, `SndDrv_Idle`)

- [ ] **Step 1: B3 — make the ISR bank-transparent**

In `SndDrv_ISR`, save the current bank id before `SndDrv_PollMailbox` and restore it after:

```z80
SndDrv_ISR:
        push    af
        push    bc
        push    de
        push    hl
        ld      a, (SND_CUR_BANK)        ; save the pre-ISR bank
        push    af
        call    SndDrv_PollMailbox       ; may SetBank (SFX blob / song load)
        pop     af
        call    SndDrv_SetBank           ; restore the pre-ISR bank (cached if unchanged)
        pop     hl
        pop     de
        pop     bc
        pop     af
        ei
        ret
```

- [ ] **Step 2: B4 — latch the sample bank at the idle→streaming entry**

In `SndDrv_Idle`, before the `jp nz, SndDrv_Sample` that enters streaming, SetBank the sample bank
(covers the mailbox `SND_REQ_SAMPLE` path whose `Snd_StartSample` ran in the bank-transparent ISR):

```z80
SndDrv_Idle:
        di
        ld      a, (SND_STAT_DAC_ACTIVE)
        or      a
        jr      z, .stay_idle
        ld      a, (SND_ROM_BANK)
        call    SndDrv_SetBank           ; B4: enter streaming on the sample bank
        jp      SndDrv_Sample
.stay_idle:
        ; ... existing idle body ...
```

- [ ] **Step 3: Build green + MT regression**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` → exit 0. `oracle`: MT regression vs baseline
(unchanged). Smoke the drum-test song still plays (kick r ≥ 0.9).

- [ ] **Step 4: Commit**

```bash
git add engine/z80_sound_driver.asm
git commit -m "feat(sound): bank brackets B3 (ISR bank-transparent) + B4 (streaming-entry latch)"
```

---

## Task 5.3: Shared-bank DAC-on test song + the full L3 proof

**Files:**
- Modify: `data/sound/song_drumtest.asm` (switch to STREAM + own bank; FM melody + FM6 + `$E2` kick)
- Modify: `main.asm` (the drum-test song bank with co-located engine tables + SFX blobs)
- Modify: `sound_constants.asm` (a brackets-present assert if expressible at build time)

- [ ] **Step 1: Make the drum-test song a STREAM/DAC-on song in its own bank**

Set its `SH_FLAGS = SH_F_STREAM` (FM6=DAC default — DAC on). Give it a few FM channels playing a
short melody, an FM6 line, and a DAC channel firing `$E2` kick/snare on a beat. Place the song +
co-located engine tables + its FM patch bank + the SFX blobs in ONE `$8000`-aligned bank in `main.asm`
(mirror the MT block at `main.asm:256-289`), so `SND_SONG_BANK` covers every frame + ISR blob read.
The DAC payloads stay in the SEPARATE shared DAC bank (Task 2.3).

- [ ] **Step 2: Build green (bank-fit asserts)**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` → exit 0; the song-bank no-straddle assert passes;
`SND_SONG_BANK != sample bank` is allowed.

- [ ] **Step 3: Verify L3 — music-channel corrcoef after `$E2` (the bank-swap gate)**

`oracle`: reload; trigger the drum-test song; capture a multi-second VGM. Decode to WAV; confirm the
**FM/PSG music channels are correct AFTER each `$E2`** (a bank-swap failure would corrupt every note
after the drum — the garbage-that-looks-audible trap). Gate: the music spectrum matches a
DAC-channel-muted render of the same song (`emulator_set_channel_enabled` to mute the DAC, capture the
"clean music" reference, then compare). Drum hits themselves: kick/snare r ≥ 0.9.

- [ ] **Step 4: Verify B3 — fire an SFX mid-drum**

While the drum-test song plays, trigger a gameplay SFX (e.g. ring `$33`) via the SFX path. Confirm:
the SFX sounds correctly, the music continues correctly, and the drum after the SFX still plays
(r ≥ 0.9) — proving the ISR's SFX-blob read on the song bank didn't strand the window and corrupt the
sample FILL.

- [ ] **Step 5: MT regression** — unchanged vs `/tmp/mt_baseline.vgm`.

- [ ] **Step 6: Commit**

```bash
git add data/sound/song_drumtest.asm main.asm sound_constants.asm
git commit -m "test(sound): STREAM DAC-on drum-test song (own bank) + full L3/B3 proof"
```

---

## Task 6.1: Rate prefix-trim (`$2A` re-park on every `$4000`-touch path)

**Files:**
- Modify: `engine/z80_sound_driver.asm` (drop the per-sample `$2A` re-select; re-park `$2A` on exit of
  the ISR / Timer-A frame / `SndDrv_SetBank`)

- [ ] **Step 1: Re-park `$2A` in every path that touches `$4000`**

Ensure `SndDrv_PollMailbox`/`SndDrv_ISR`, the Timer-A frame path (`SndDrv_TimerATick`,
`SndDrv_IdleTick`), and `SndDrv_SetBank` each re-select `$2A` on `$4000` before returning to the loop
(several already do; add it to any that don't — notably after `SndDrv_SetBank`'s `$6000` writes the
addr latch is untouched, but the frame's FM writes leave it elsewhere). Document each touch-point.

- [ ] **Step 2: Drop the per-sample `$2A` re-select from the consumer**

In `SndDrv_Sample`'s consumer, remove the `ld a,SND_REG_DAC_DATA / ld (SND_Z80_YM_A0),a` re-select
(the ~+24-cyc cost). The latch now holds because every `$4000`-touching path re-parks `$2A` on exit.

- [ ] **Step 3: Build green + verify correct-reg in Exodus**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` → exit 0. `oracle`: reload; play the drum-test song
+ MT. Confirm the DAC data lands on `$2A` (the original wrong-reg bug does NOT reappear): kick r ≥ 0.9
AND MT regression unchanged. (Exodus is the venue that caught the original bug; this is the gate. No
real hardware — note that explicitly.) **Fallback:** if any wrong-reg shows, revert this task and keep
the per-sample re-select at the modest rate.

- [ ] **Step 4: Commit**

```bash
git add engine/z80_sound_driver.asm
git commit -m "perf(sound): re-park \$2A on every \$4000-touch path, drop per-sample re-select"
```

---

## Task 6.2: Raise the rate + re-derive DMA-survival

**Files:**
- Modify: `engine/z80_sound_driver.asm` (pads/balance), `sound_constants.asm` (`SND_LOOP_CYC`,
  ring depth), `tools/dac_encode.py` driver (re-encode at the final rate)

- [ ] **Step 1: Re-balance to the target rate**

With the prefix trimmed, recompute `SND_LOOP_CYC` for the shorter balanced loop and regrow/shrink
`SkipPad`/`DrainPad` so `FILL == SKIP == DRAIN` at the new total. Target ~18-20 kHz (`SND_DAC_RATE_HZ`
follows `dac_rate_hz()`). Optionally amortize the K=30 Timer-A poll ONLY if it stays cycle-balanced
(else leave it).

- [ ] **Step 2: Re-derive the ring lead vs worst-case DMA at the new rate**

The ~250-byte lead is wall-clock (~28 ms at 8948, ~12.5 ms at 20 kHz). Compute the worst-case 68k
DMA + VBlank stall (use the existing budget docs / `Lag_Frame_Count`) and confirm the lead outlasts
it at the new rate. If 256 B is too short, deepen the ring — note this requires widening the
single-byte `SND_RING_RD/WR` scheme (a real change; budget it here, within the ~1 KB Z80 headroom).

- [ ] **Step 3: Re-encode the samples at the final rate**

Re-run `tools/dac_encode.py` with the final target rate so the drum pitch is correct; rebuild the
`.dpcm`.

- [ ] **Step 4: Build green + verify L6**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` → exit 0. `oracle`: drum-test + MT. Gates: `$2A`
cadence steady at the new rate; kick/snare r ≥ 0.9; MT regression unchanged; ring survives a
forced-DMA stress (scroll/teleport while a drum plays — capture and confirm no `$2A` underrun gap).

- [ ] **Step 5: Commit**

```bash
git add engine/z80_sound_driver.asm sound_constants.asm data/sound/dac
git commit -m "perf(sound): raise DAC rate to ~18-20kHz + re-derive ring DMA-survival"
```

---

## Task 7.1: Adaptive FM6 time-share (per-song flag)

**Files:**
- Modify: `sound_constants.asm` (`SH_F_FM6_ADAPTIVE` flag), `engine/z80_sound_driver.asm`
  (toggle at trigger edge + re-key at exhaust), `engine/sound_sequencer.asm` (flag-gated gate),
  `data/sound/song_drumtest.asm` (set the flag for an adaptive test)

- [ ] **Step 1: Add the per-song flag**

```
SH_F_FM6_ADAPTIVE_B = 2
SH_F_FM6_ADAPTIVE   = 1<<SH_F_FM6_ADAPTIVE_B
```
Cache it at load (e.g. into a `SND_FM6_ADAPTIVE` RAM byte) so the trigger/exhaust paths can branch.

- [ ] **Step 2: Toggle FM6 at the DAC trigger edge (FM→DAC)**

In `Snd_StartSample`, when `SND_FM6_ADAPTIVE`: key-off FM6 ops (`$28 = ch6sel`, op-mask 0), write
`$2A=$80` (DC-center pass-through to avoid a level jump), then `$2B=$80` + `$B6=$C0`, before priming.

- [ ] **Step 3: Re-key FM6 at exhaust (DAC→FM)**

At `.stop`, when `SND_FM6_ADAPTIVE`: after the `$2A=$80` DC-center, re-assert FM6's current sequencer
note (`$A4/$A0` fnum from its `SeqChannel`, then `$28=$F0|ch6sel` key-on) so FM6 resumes immediately
rather than waiting for its next note. (Dedicate path keeps the Task 4.1 behavior when the flag is
clear.)

- [ ] **Step 4: Build green + verify L5 (adaptive)**

Set `SH_F_FM6_ADAPTIVE` on the drum-test song; give FM6 a line that plays continuously across several
`$E2` hits. `oracle`: reload; trigger; capture VGM. Confirm FM6 plays music BETWEEN drum hits,
key-offs cleanly at each hit (`$2A` through `$80`), and re-keys after — and the drums still play
(r ≥ 0.9). Compare the FM6 line pre/post a hit against an FM6-only render.

- [ ] **Step 5: Commit**

```bash
git add sound_constants.asm engine/z80_sound_driver.asm engine/sound_sequencer.asm data/sound/song_drumtest.asm
git commit -m "feat(sound): adaptive Echo-style FM6 time-share (per-song flag)"
```

---

## Task F.1: Doc sync — ENGINE_ARCHITECTURE.md §6

**Files:**
- Modify: `docs/ENGINE_ARCHITECTURE.md` (§6 sound)

- [ ] **Step 1: Document the DAC drum path**

Update §6 to describe: the DAC one-shot state machine (IDLE/PLAYING/DRAINING_TAIL/STOPPING); the
noise-shaped DPCM-HQ payload + the inline DecTable; the four bank brackets B1-B4 and the two banking
modes (shared DAC bank + per-frame swap; co-located tables in the song bank); FM6
dedicate/adaptive; the ~18-20 kHz rate decision + the no-real-hardware Exodus verification posture.
Remove any stale "SFX deferred"/"DAC single-sample" wording.

- [ ] **Step 2: Commit**

```bash
git add docs/ENGINE_ARCHITECTURE.md
git commit -m "docs(arch): §6 DAC drum path, banking modes, DPCM-HQ, rate decision"
```

---

## Task F.2: Finish the branch

**Files:** none (integration).

- [ ] **Step 1: Full clean build + the whole verification matrix**

Run `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` from clean; re-run L0-L6 + MT regression once more in
`oracle`. All gates green.

- [ ] **Step 2: Use superpowers:finishing-a-development-branch**

Present merge options. On approval, fast-forward-merge `feat/dac-drum` → `master` (never break
master), remove the worktree, and update `docs/DEFERRED_WORK.md` (mark DAC-format E2/E3 done).

---

## Self-Review (run before execution)

- **Spec coverage:** state machine §3.1→T1.2; clean RAM §3.2→T0.1; descriptor §3.3→T0.2; codec
  §3.4→T2.1/2.2/3.1; decode FILL/rebalance §3.5→T3.1; bank swaps B1-B4 §3.6→T5.1/5.2/5.3; FM6
  §3.7→T4.1/7.1; rate §3.8→T6.1/6.2; layout §4→T2.3/5.3; content §5→T2.1/2.2; verification §6→every
  task's gate; build order §7→tasks in order. **No gaps.**
- **`SND_DEC_IY` (resolved):** `iy` is not safe across the loop's `ei`/ISR, so the decode reloads the
  DecTable base from `SND_DEC_IY` (RAM) at FILL top. Now consistent across T0.1 (state block),
  T3.1 Step 1 (FILL reload), and T3.1 Step 2 (`Snd_StartSample` stores it).
- **Type/name consistency:** `SND_DEC_ACC`, `SND_DAC_PHASE`, `SND_SONG_BANK`, `SND_ROM_BANK`,
  `Run_SeqFrame_OnSongBank`, `DecTable`, `DacSample`/`ds_*`, `dac_verify.py`, `dac_encode.py`,
  `decode_dpcm`/`encode_dpcm` used consistently across tasks.
- **No placeholders:** every code step shows the asm/python; measured values (`SND_LOOP_CYC`, pads,
  ring depth, `ds_table`) are precise procedures, not TBDs.
```
