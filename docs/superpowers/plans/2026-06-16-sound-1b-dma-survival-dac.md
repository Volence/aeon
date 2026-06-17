# Sound Driver — Plan 1B: DMA-Survival Single-Channel DAC

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the single-channel DAC stream real samples from ROM banks and never gap, scratch, or corrupt under Sonic's heavy DMA — by always playing from a Z80-RAM ring buffer that the Z80 fills during active display and drains (no ROM reads) during the DMA window.

**Architecture:** A 256-byte page-aligned ring buffer at Z80 `$1700`. The DAC output loop is cycle-balanced (jitter-free pitch) and always drains the ring. A producer fills the ring from banked ROM at 2:1 during active display; on the Z80's hardware VBlank interrupt it switches to DRAIN mode (no ROM) and resumes filling when the 68k clears a `DMA_ACTIVE` flag. `VInt_Level` swaps its `stopZ80`-around-DMA for setting/clearing that flag. Cached `SetBank` + build-time bank-aligned samples keep banking off the audio-critical path.

**Tech Stack:** Motorola 68000 + Zilog Z80 (AS Macro Assembler `asl`), `tools/s4lint.py`, `./build.sh`, Exodus emulator MCP for hardware verification.

**Source spec:** `docs/superpowers/specs/2026-06-16-sound-1b-design.md`.

---

## Verification model (same as Foundations)

Bare-metal: "tests" are (1) build-time `if … error/fatal` asserts, (2) DEBUG boot self-tests, (3) Exodus MCP runtime inspection. **The controller drives the Exodus MCP verification** (implementers do code+build+lint+commit headless). Key facts from Foundations (honor them):

- **Z80 = Intel hex** (`80h`, `1FFEh`) under `cpu z80`; 68k uses `$`.
- **Keep the even-pad block** last before `dephase` in `engine/z80_sound_driver.asm`.
- **No fall-through into `ret`-terminated routines** — helpers live after the main loop.
- **MCP can't read Z80 RAM** — observe driver state via `Sound_Dbg_Mirror` at 68k `$FFB202` (DEBUG mirror copies Z80 `$1F00..$1F2F` → mirror[0..47], and `$1600..$160F` → mirror[48..63]). MCP read addresses need the `0x` prefix.
- **68k↔Z80 RAM needs the bus held** (`stopZ80`) — but the *new* DMA_ACTIVE flag is written by the 68k while the Z80 runs; see Task 5 for why that one specific write is safe.
- Build: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` (+ `SOUND_DRIVER_ENABLED=1 ./build.sh` and `./build.sh` for ON/OFF). Run all three before each commit.

**Mirror note for 1B:** the playback-state region (`$1600`) gains fields (Task 1). The DEBUG mirror already snapshots `$1600..$160F` (16 bytes) — keep new observable state within that window, or widen the mirror copy.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `sound_constants.asm` | Modify | Ring/fill/drain/bank constants, `DMA_ACTIVE` flag, sample-descriptor struct offsets |
| `engine/z80_sound_driver.asm` | Modify | Ring drain (cycle-balanced), ROM fill + `SndDrv_SetBank`, fill/drain mode switch, VBlank ISR, sample-table lookup |
| `engine/vblank.asm` | Modify | `VInt_Level` / `VInt_Lag`: `stopZ80`-around-DMA → `DMA_ACTIVE` set/clear |
| `data/sound/dac_samples.asm` | Create | ROM sample blob(s) + the 8-byte descriptor table; migrated from `sonic_hack/sound/DAC/` |
| `tools/s4lint.py` | Modify | Refine the VDP-without-stopZ80 rule for the new sound-DMA model |
| `main.asm` | Modify | `include` the sample data |

---

## Task 1: 1B state layout + sample descriptor

Pure equates/struct — establishes the contract the rest of 1B uses. "Test" = it assembles.

**Files:** Modify `sound_constants.asm`, `main.asm`

- [ ] **Step 1: Research the layouts**

Dispatch a research subagent: confirm the Mega PCM ring-buffer state (read ptr / fill ptr / high-byte-full-check) from `github.com/vladikcomper/MegaPCM` 2.x `src/z80/*.asm`, and the Flamedriver 5-byte DAC descriptor (`Sonic-Clean-Engine-S.C.E.-/Sound/Flamedriver.asm` ~4814) + bank table. Confirm our 8-byte descriptor (bank/rate/ptr/length/loop) is sufficient and the field order is sane for Z80 indexed loads. 2-3 line note.

- [ ] **Step 2: Add constants**

Append to `sound_constants.asm`:
```asm
; --- 1B: ring buffer (page-aligned, 256 bytes) ---
SND_RING_BASE           = $1700                  ; Z80 addr; high byte $17 is the page
SND_RING_PAGE           = $17                     ; high byte for `inc l` wrap + full-check
SND_RING_LEN            = $100

; --- 1B: 68k->Z80 control (68k writes, Z80 reads) ---
SND_CTRL_DMA_ACTIVE     = SND_REQ_BASE+$04        ; $1F04: 1 = 68k DMA in progress (no ROM reads)

; --- 1B: playback/stream state (Z80 RAM, state region) ---
SND_RING_RD             = SND_STATE_BASE+$06      ; ring read (drain) ptr low byte
SND_RING_WR             = SND_STATE_BASE+$07      ; ring fill ptr low byte
SND_ROM_PTR             = SND_STATE_BASE+$08      ; current ROM window ptr (2 bytes)
SND_ROM_LEN             = SND_STATE_BASE+$0A      ; bytes remaining in sample (2 bytes)
SND_ROM_BANK            = SND_STATE_BASE+$0C      ; sample's bank id
SND_CUR_BANK            = SND_STATE_BASE+$0D      ; cached current bank (SetBank no-op check)
SND_LOOP_OFS            = SND_STATE_BASE+$0E      ; loop restart offset within sample (0 = one-shot)
SND_PLAY_MODE           = SND_STATE_BASE+$0F      ; 0 = FILL+PLAY, 1 = DRAIN (no ROM reads)
; (state region $1600..$160F is 16 bytes — fits exactly; mirror already covers it)

; --- 1B: 8-byte ROM-resident sample descriptor ---
DacSample struct
ds_bank         ds.b 1          ; +0  bank id = (addr & $7F8000) >> 15
ds_rate         ds.b 1          ; +1  per-sample rate delay (pitch); 0 = max
ds_ptr          ds.w 1          ; +2  Z80-window ptr: (addr & $7FFF) + $8000, little-endian
ds_length       ds.w 1          ; +4  byte count
ds_loop_ofs     ds.w 1          ; +6  loop restart offset (0 = one-shot)
DacSample ends

; --- Z80 bank register (as seen from the Z80) ---
SND_Z80_BANKREG         = $6000
```
NOTE: confirm `struct … ends` is the codebase's idiom (see `structs.asm`); if it uses `endstruct`, match it. Add a size assert mirroring the others:
```asm
    if DacSample_len <> 8
      error "DacSample struct is \{DacSample_len} bytes, expected 8"
    endif
```

- [ ] **Step 3: Build to verify it assembles**

Run: `SOUND_DRIVER_ENABLED=1 ./build.sh -pe`
Expected: exit 0, size summary, no undefined symbols, no struct-size error.

- [ ] **Step 4: Commit**

```bash
git add sound_constants.asm
git commit -m "feat(sound 1b): ring/stream state constants + DacSample descriptor"
```

---

## Task 2: Ring-buffer drain with cycle-balanced output (RAM-filled)

Restructure the DAC to **always drain the ring**, with a cycle-balanced output loop. The ring is pre-filled from the existing RAM sawtooth (ROM streaming comes in Task 4), so this isolates the ring + clean-pitch output. This is the trickiest task — budget hardware tuning time.

**Files:** Modify `engine/z80_sound_driver.asm`

- [ ] **Step 1: Research the cycle-balanced loop**

Dispatch a research subagent: pull Mega PCM's `src/z80/loop-pcm.asm` cycle-balanced structure (every branch path padded to equal cost; `di`/`ei` bounded; the `inc l` advance; high-byte full-check) and Batman's `$00C0` feed. Produce the exact balanced drain-loop skeleton and a starting per-sample cycle target for ~16 kHz at 3.58 MHz Z80. Note: this WILL need on-hardware tuning — report the structure + the formula (samples/sec = Z80_clock / cycles_per_sample).

- [ ] **Step 2: Add ring init + pre-fill in SndDrv_Init**

Replace the Foundations "generate sawtooth at `$1C00`" so it instead **generates directly into the ring** for this interim step, and set ring pointers. In `SndDrv_Init`, replace the sample-gen block with:
```asm
        ; --- fill the ring with a sawtooth (interim: RAM source until Task 4) ---
        ld      hl, SND_RING_BASE
        ld      b, 0                     ; 256 bytes
        xor     a
.gen_ring:
        ld      (hl), a
        inc     hl
        add     a, 8
        djnz    .gen_ring
        ; ring read ptr = page base; mark playing
        xor     a
        ld      (SND_RING_RD), a         ; low byte 0 -> $1700
        ld      (SND_STAT_DAC_ACTIVE), a
```
(The DAC drains the ring continuously; for this task the ring is static, so it loops the 256-byte sawtooth — same audible result as Foundations but via the ring.)

- [ ] **Step 3: Replace SndDrv_FeedDAC with the cycle-balanced ring drain**

Reference implementation (tune cycle padding on hardware in Step 6). The drain reads one ring byte via `inc l` page wrap and writes `$2A`, with a balanced rate delay:
```asm
; --- drain one ring byte to the DAC (cycle-balanced); ring read ptr in RAM ---
; Called once per SndDrv_Main iteration when SND_STAT_DAC_ACTIVE != 0.
SndDrv_DrainDAC:
        ld      a, (SND_STAT_DAC_ACTIVE)
        or      a
        ret     z
        ld      a, (SND_RING_RD)         ; ring read low byte
        ld      l, a
        ld      h, SND_RING_PAGE         ; hl = $17xx
        ld      a, (hl)                  ; sample byte
        ld      (ix+0), SND_REG_DAC_DATA ; reg $2A
        ld      (ix+1), a                ; -> DAC
        inc     l                        ; advance (wraps within page)
        ld      a, l
        ld      (SND_RING_RD), a
        ld      b, SND_DAC_RATE          ; balanced rate delay (tune)
.rate:  djnz    .rate
        ret
```
Update `SndDrv_Main` to `call SndDrv_DrainDAC` in place of `call SndDrv_FeedDAC`, and delete the old `SndDrv_FeedDAC` + the `$1C00` sample machinery (now unused). Keep the even-pad block last.

- [ ] **Step 4: Build (all three configs) + lint**

`SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`, `SOUND_DRIVER_ENABLED=1 ./build.sh -pe`, `./build.sh -pe` → all exit 0, lint clean, size guard OK.

- [ ] **Step 5: Runtime verify (controller, Exodus)**

Reload DEBUG ROM; the boot harness already posts a play request. Confirm via mirror: `SND_STAT_DAC_ACTIVE` ($FFB216) = 1, and the ring read ptr (`SND_RING_RD` → mirror offset 48+6 = `$FFB23A`) is advancing across frames. Ask the user to confirm a **clean, steady tone** (cycle-balanced = no warble vs Foundations).

- [ ] **Step 6: Tune the rate delay on hardware**

If the user reports warble or wrong pitch, adjust `SND_DAC_RATE` and any path-padding so every drain iteration costs identical cycles. Re-verify. (This is expected iteration — the cycle balance is the whole point.)

- [ ] **Step 7: Commit**

```bash
git add engine/z80_sound_driver.asm
git commit -m "feat(sound 1b): cycle-balanced ring-buffer drain (RAM-filled)"
```

---

## Task 3: Continuous producer/consumer fill (still RAM source)

Add the **fill-ahead producer** so the ring is continuously refilled as it drains — still copying from a RAM source (the migrated ROM path is Task 4). This proves the producer/consumer ring (fill ptr chasing read ptr, high-byte-full check) before ROM/banking complexity.

**Files:** Modify `engine/z80_sound_driver.asm`

- [ ] **Step 1: Research the fill cadence + full-check**

Research subagent: the exact Mega PCM 2:1 fill-ahead and the "high-byte gap = ring fullness" check (read-ptr high byte vs fill-ptr high byte; the ≤2/≤3 guard band). Give the fill routine that adds 0–2 bytes/iteration to keep the ring full without lapping the read ptr.

- [ ] **Step 2: Add a RAM source + fill routine**

For this task the "source" is a 1 KB RAM sample (generate it at `$1800` growth-reserve in init). Add a fill routine that copies source→ring while the ring has space, tracking `SND_RING_WR` and looping the source:
```asm
; --- top up the ring from the (RAM, interim) source; keep ~full, never lap read ptr ---
SndDrv_FillRing:
        ld      a, (SND_STAT_DAC_ACTIVE)
        or      a
        ret     z
        ld      a, (SND_RING_WR)         ; fill ptr low
        ld      e, a
        ld      a, (SND_RING_RD)         ; read ptr low
        ; fullness = (rd - wr) within the 256 page; stop if too close (guard band)
        sub     e
        cp      4                        ; guard band (tune per research)
        ret     c                        ; ring full enough -> done this pass
        ; copy 1 byte source -> ring
        ld      hl, (SND_ROM_PTR)        ; interim: points into the RAM source
        ld      a, (hl)
        inc     hl
        ld      (SND_ROM_PTR), hl
        ld      l, e
        ld      h, SND_RING_PAGE
        ld      (hl), a
        inc     e
        ld      a, e
        ld      (SND_RING_WR), a
        ; source loop bookkeeping (length/loop) ... (research: keep it simple for RAM source)
        ret
```
(Refine pointer/length/loop handling per the research; the above is the skeleton — the ROM version in Task 4 replaces the source read with a banked ROM read.) Call `SndDrv_FillRing` in `SndDrv_Main` after the drain. Initialise `SND_RING_WR`, `SND_ROM_PTR`/`SND_ROM_LEN` to the RAM source in init.

- [ ] **Step 3: Build (3 configs) + lint** — all exit 0.

- [ ] **Step 4: Runtime verify (controller)**

Mirror: `SND_RING_WR` (`$FFB23B`) and `SND_RING_RD` (`$FFB23A`) both advance and stay within the guard band of each other (ring stays ~full). User confirms continuous tone (now sourced via the producer, not a static ring).

- [ ] **Step 5: Commit**

```bash
git add engine/z80_sound_driver.asm
git commit -m "feat(sound 1b): producer/consumer ring fill (RAM source, 2:1 ahead)"
```

---

## Task 4: ROM streaming + cached banking + real sample

Replace the RAM source with **banked ROM**, add `SndDrv_SetBank`, the sample-descriptor table, and a **real migrated DAC sample**.

**Files:** Modify `engine/z80_sound_driver.asm`; Create `data/sound/dac_samples.asm`; Modify `main.asm`

- [ ] **Step 1: Research banking + build-time alignment**

Research subagent: Mega PCM `src/z80/set-bank.asm` (9-write `$6000` latch, cached no-op), Flamedriver `bankswitch` macro + `finishBank` boundary `fatal`, and `zmake68kBank`/`zmake68kPtr` (how a 68k ROM address becomes a bank id + a `$8000`-window Z80 pointer). Confirm how to migrate a `sonic_hack/sound/DAC/*.bin` raw 8-bit sample and compute its descriptor. Note whether AS can compute `(addr&$7F8000)>>15` and `(addr&$7FFF)+$8000` for the descriptor at build time.

- [ ] **Step 2: Create the sample data + descriptor table**

Create `data/sound/dac_samples.asm`: `incbin` one migrated raw 8-bit sample from `sonic_hack/sound/DAC/`, **aligned so it doesn't cross a 32 KB bank boundary** (pad with `cnop`/`align` to bank-start if needed), and a `DacSample` table entry computed from its address:
```asm
Dac_Sample_Drum:
        incbin  "data/sound/dac_drum.bin"      ; raw 8-bit unsigned PCM
Dac_Sample_Drum_End:

; build-time guard: sample must not cross a $8000 bank boundary
    if (Dac_Sample_Drum >> 15) <> ((Dac_Sample_Drum_End-1) >> 15)
      fatal "Dac_Sample_Drum crosses a 32KB bank boundary — pad it to a bank start"
    endif

; descriptor table (id 1 = drum), fields computed from the ROM address
DacSampleTable:
        ; id 1
        dc.b    (Dac_Sample_Drum & $7F8000) >> 15          ; ds_bank
        dc.b    0                                          ; ds_rate (0 = max; tune)
        dc.w    (Dac_Sample_Drum & $7FFF) | $8000          ; ds_ptr (Z80 window)
        dc.w    Dac_Sample_Drum_End - Dac_Sample_Drum      ; ds_length
        dc.w    0                                          ; ds_loop_ofs (one-shot)
```
Include it from `main.asm` (in a ROM data area, not the Z80 phase block). Copy a suitable drum `.bin` into `data/sound/dac_drum.bin`.

- [ ] **Step 3: Add SndDrv_SetBank (cached) to the driver**

```asm
; --- select ROM bank A into the Z80 $8000 window; no-op if already current ---
; In: a = bank id. Clobbers: a, hl. ~27 cyc no-op / ~162 cyc switch.
SndDrv_SetBank:
        ld      hl, SND_CUR_BANK
        cp      (hl)
        ret     z                        ; already current
        ld      (hl), a                  ; cache it
        ld      hl, SND_Z80_BANKREG      ; $6000
        ; write 9 bits LSB-first
        rept 8
        ld      (hl), a
        rrca
        endr
        ld      (hl), a                  ; 9th
        ret
```

- [ ] **Step 4: Point the fill path at banked ROM + descriptor lookup**

On a play request (in the mailbox poll), look up the descriptor by id, `SndDrv_SetBank ds_bank`, set `SND_ROM_PTR=ds_ptr`, `SND_ROM_LEN=ds_length`, `SND_LOOP_OFS=ds_loop_ofs`, reset ring ptrs, `SND_STAT_DAC_ACTIVE=1`. Change `SndDrv_FillRing`'s source read from the RAM source to the ROM window (`ld a,(SND_ROM_PTR)`-based read), decrement `SND_ROM_LEN`, and on exhaustion either loop (`ds_loop_ofs`) or stop. **The 68k posts a sample id (1) — already wired via `SND_REQ_SAMPLE`.** (Full code per research; the descriptor address is the table base + (id-1)*8.)

- [ ] **Step 5: Build (3 configs) + lint** — all exit 0; the bank-boundary `fatal` does not trip.

- [ ] **Step 6: Runtime verify (controller + user)**

Reload DEBUG; the boot harness posts sample id 1. Verify the mirror shows `SND_STAT_DAC_ACTIVE`=1, `SND_CUR_BANK` set, ring ptrs advancing. **User confirms the real drum sample plays** (recognisable, not a sawtooth). `emulator_get_channel_states` shows DAC active.

- [ ] **Step 7: Commit**

```bash
git add engine/z80_sound_driver.asm data/sound/dac_samples.asm data/sound/dac_drum.bin main.asm
git commit -m "feat(sound 1b): ROM-streamed real sample + cached banking"
```

---

## Task 5: DMA_ACTIVE signalling + Z80 VBlank ISR (the DMA-survival mechanism)

Add the fill↔drain switch: the Z80 VBlank ISR enters DRAIN; the 68k `DMA_ACTIVE` flag (set/cleared in `VInt_Level`) gates the return to FILL. This is where the DAC becomes DMA-proof.

**Files:** Modify `engine/z80_sound_driver.asm`, `engine/vblank.asm`

- [ ] **Step 1: Research the Z80 VBlank IRQ + safe flag write**

Research subagent: confirm (plutiedev / SpritesMind / md.railgun.works) that the Genesis asserts the Z80 /INT during VBlank with no 68k action; the `im 1` / `ei` setup and the RST $38 vector. Confirm the one subtlety: the 68k writing a single byte (`DMA_ACTIVE`) to Z80 RAM **while the Z80 runs** — is it safe? (It is a *write*; recall writes-while-running are normally ignored — so confirm whether the 68k must briefly hold the bus for this one byte, or whether the flag must instead live where the Z80 can't miss it. Resolve this explicitly — it is the correctness crux.) Return the exact ISR + the safe 68k flag-write pattern.

> **Controller note:** Foundations established 68k writes to Z80 RAM are *ignored* unless the bus is held. So `DMA_ACTIVE` must be written with the bus held too — but we're replacing `stopZ80`/`startZ80`. Likely resolution: the 68k writes `DMA_ACTIVE=1` with a brief `stopZ80`/`startZ80` *around just that byte* (microscopic vs the whole DMA), or the flag is set by the Z80 itself in its VBlank ISR and cleared by the 68k via a held-bus byte after DMA. The research step must nail this; do not implement until it's resolved.

- [ ] **Step 2: Add the Z80 VBlank ISR (enter DRAIN)**

Re-enable interrupts in `SndDrv_Init` (`im 1` then `ei` after setup) and add the ISR at RST $38 (`$0038`). The ISR sets a `SND_PLAY_MODE` flag to DRAIN (or self-modifies the fill call to a no-op):
```asm
; placed at Z80 $0038 (RST 38 / IM1 vector). Keep it tiny.
        phase $38
SndDrv_VInt:
        push    af
        ld      a, 1
        ld      (SND_PLAY_MODE), a       ; 1 = DRAIN (no ROM reads)
        pop     af
        ei
        ret
        dephase
```
(Placing code at `$38` inside the `phase 0` blob needs care — the blob loads at $0000 so $38 is within it; ensure `SndDrv_Init` entry and the $38 vector don't collide. Research/confirm the layout; an alternative is a `jp` at $38 to the handler.)

- [ ] **Step 3: Gate the fill path on mode + DMA_ACTIVE**

`SndDrv_FillRing` returns early when `SND_PLAY_MODE` = DRAIN. The main loop clears DRAIN (back to FILL) when it observes `SND_CTRL_DMA_ACTIVE` = 0:
```asm
        ld      a, (SND_CTRL_DMA_ACTIVE)
        or      a
        jr      nz, .stay_drain          ; 68k still DMAing -> keep draining
        xor     a
        ld      (SND_PLAY_MODE), a       ; FILL+PLAY resumes
.stay_drain:
```
The **drain path always runs** regardless of mode (the DAC never stops); only the **fill (ROM read)** is gated.

- [ ] **Step 4: Change VInt_Level / VInt_Lag (the engine edit)**

In `engine/vblank.asm`, replace the `stopZ80` / `startZ80` that wrap the DMA pipeline with the `DMA_ACTIVE` flag set/clear (using the safe write pattern from Step 1's research). Conceptually:
```asm
        ; was: stopZ80
        bsr.w   Sound_DmaBegin           ; sets SND_CTRL_DMA_ACTIVE=1 (bus-held byte write)
        ... existing DMA pipeline (Flush_VDP_Shadow, Process_DMA_*) ...
        ; was: startZ80
        bsr.w   Sound_DmaEnd             ; sets SND_CTRL_DMA_ACTIVE=0
```
Add `Sound_DmaBegin`/`Sound_DmaEnd` (68k, in `engine/sound_api.asm`) per Step 1's resolved safe-write pattern. Apply to `VInt_Lag` too. **Gate behind `SOUND_DRIVER_ENABLED`** so the OFF build keeps the original `stopZ80`/`startZ80`.

- [ ] **Step 5: Refine s4lint**

Update `tools/s4lint.py` so the VDP-without-stopZ80 rule understands the new model (the sound-DMA path uses `DMA_ACTIVE` instead of `stopZ80`). Document the new invariant in a comment. Don't weaken the rule for non-sound VDP writes.

- [ ] **Step 6: Build (3 configs) + lint** — all exit 0; lint clean (including the refined rule).

- [ ] **Step 7: Runtime verify (controller)**

Reload DEBUG. Under normal operation the sample must still play (mirror: DAC active, ring advancing). Observe `SND_PLAY_MODE` toggling: at VBlank it should be DRAIN, returning to FILL after DMA (sample it across `emulator_run_to_scanline` at a VBlank line vs an active line). User confirms the tone is still clean (no regression).

- [ ] **Step 8: Commit**

```bash
git add engine/z80_sound_driver.asm engine/vblank.asm engine/sound_api.asm tools/s4lint.py
git commit -m "feat(sound 1b): DMA_ACTIVE flag + Z80 VBlank ISR fill/drain switch"
```

---

## Task 6: Heavy-DMA hardware verification + buffer-size spike

Prove the headline claim — no gap/scratch/corruption under worst-case Sonic DMA — and size the buffer.

**Files:** (verification; possibly `sound_constants.asm` if the buffer is resized)

- [ ] **Step 1: Force a heavy-DMA frame**

Use the OJZ scroll/section-load path (the engine already streams section art via DMA). Drive the emulator to a frame doing a section-load (teleport / heavy tile-cache fill) while the drum sample loops. (If the DEBUG harness can trigger a section load, use it; else `emulator_run_to` a known heavy-DMA point.)

- [ ] **Step 2: Verify no audio dropout (user + state)**

User listens during the heavy-DMA frame(s): the sample must **not** gap or scratch. State check: the ring read ptr keeps advancing every frame (never stalls), and `SND_PLAY_MODE` enters DRAIN during the DMA and recovers.

- [ ] **Step 3: Verify no art corruption**

After the heavy-DMA frame, inspect VRAM (`emulator_read_vram`) / screenshot — the streamed tiles must be correct (the Z80 didn't glitch the DMA). Visual check by the user.

- [ ] **Step 4: Buffer-size spike**

Measure the worst single-frame DMA byte count (Exodus profiler / `Lag_Frame_Count` / count `Process_DMA_*` work). Confirm the 256-byte ring's drain window ≥ that DMA's Z80-halt-equivalent duration at the chosen DAC rate. If marginal, widen the ring into the `$1800` growth reserve and update `SND_RING_LEN`/page logic. Document the measured margin.

- [ ] **Step 5: Commit (if any tuning)**

```bash
git add -A
git commit -m "verify(sound 1b): heavy-DMA hardware validation + buffer sizing"
```

---

## Self-Review

**Spec coverage (vs `2026-06-16-sound-1b-design.md`):**
- §4.1 ring + fill/drain → Tasks 2, 3 ✅
- §4.2 flag+IRQ DMA signalling → Task 5 ✅
- §4.3 VInt_Level change + lint → Task 5 (steps 4, 5) ✅
- §4.4 cached banking + build-time alignment → Task 4 ✅
- §4.5 sample format + 68k API + real sample → Tasks 1, 4 ✅
- §4.6 cycle-balanced playback → Task 2 ✅
- §5 scope: write-queue deferred (not in plan ✅), raw PCM first (no BRR task ✅)
- §6 success criteria → Task 6 ✅
- §7 spikes → Task 2 step 6 (cycle), Task 5 step 1 (IRQ/flag-write), Task 6 step 4 (buffer size) ✅

**Placeholder scan:** The two genuinely hardware-dependent items (cycle-balanced rate tuning, the safe `DMA_ACTIVE` 68k-write pattern) are structured as **research-step-then-implement with explicit acceptance**, not "TODO" — the Step-1 research must resolve the flag-write crux *before* Task 5 implementation. Fill/source pointer-bookkeeping in Tasks 3/4 says "per research" with the skeleton shown — acceptable for the novel cycle-critical parts, but the implementer must produce complete code, not leave it.

**Type/label consistency:** `SND_RING_*`, `SND_CTRL_DMA_ACTIVE`, `SND_ROM_*`, `SND_CUR_BANK`, `SND_LOOP_OFS`, `SND_PLAY_MODE`, `SndDrv_{DrainDAC,FillRing,SetBank,VInt}`, `Sound_Dma{Begin,End}`, `DacSample`/`DacSampleTable` used consistently across tasks. `SND_PLAY_MODE` is referenced in Task 5 — **add it to the Task 1 constants** (state region, e.g. `SND_STATE_BASE+$0F`) so it's defined before use.

---

## Execution Handoff

After approval, two execution options:
1. **Subagent-Driven (recommended)** — fresh subagent per task + controller-driven Exodus verification between tasks.
2. **Inline Execution** — controller executes with checkpoints.
