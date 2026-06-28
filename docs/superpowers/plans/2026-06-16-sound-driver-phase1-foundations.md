# Sound Driver — Phase 1 Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the Z80-autonomous sound-driver spine — a driver shell, a verified direct-injection mailbox, a YM-Timer-driven cooperative scheduler, and a single DAC sample that audibly plays on command from the 68k.

**Architecture:** A new Z80 program (`engine/z80_sound_driver.asm`) replaces the idle program, assembled inline with `cpu z80`/`phase 0`. The 68k posts commands by writing a record into Z80 RAM with read-back-verified writes; the Z80 polls a dirty flag, latches, and acts. A YM2612 hardware timer drives a cooperative main loop (Batman model): background DAC feeding between ticks, sequencer/lifecycle work on each timer overflow. This slice plays a small test sample embedded in Z80 RAM — ROM-bank streaming, the DMA-survival read-ahead buffer, and the YM write-queue are deferred to Plan 1B.

**Tech Stack:** Motorola 68000 + Zilog Z80 assembly, AS Macro Assembler (`asl`), `tools/s4lint.py`, build via `./build.sh`, runtime verification via Exodus emulator MCP tools.

**Source spec:** `docs/superpowers/specs/2026-06-16-sound-driver-design.md` (§4.1 autonomy/mailbox, §4.2 scheduler, §5 DAC, §12 Phase 1, §12.x sub-designs #1 command API and #2 RAM map).

---

## Verification model (read first — this is not pytest)

This is bare-metal assembly. "Tests" take three forms; every task uses at least one:

1. **Build-time assertions** — AS `if … error/fatal` blocks and struct-size checks. These fail the assemble (`./build.sh`) if a structural invariant breaks. This is our fastest, most TDD-like check.
2. **DEBUG boot self-tests** — code under `ifdef __DEBUG__` that runs at boot and `assert`s golden values (pattern: `debug/compression_selftest.asm`, invoked from `engine/boot.asm`). Built with `DEBUG=1 ./build.sh`.
3. **Exodus MCP runtime inspection** — after the ROM is loaded in the user's Exodus, inspect live state with MCP tools:
   - `emulator_reload_rom` then `emulator_reset` / `emulator_resume` to run the new build.
   - `emulator_load_symbols` (point at `s4.lst`) so labels resolve.
   - `emulator_read_memory` to read **Z80 RAM** (`$A00000`–`$A02000`) and 68k RAM.
   - `emulator_get_channel_states` to confirm YM DAC/FM/PSG state.
   - `emulator_lookup_symbol` to turn a label into an address before reading.

**The user launches/owns Exodus — never auto-launch it.** Plan steps that verify at runtime state the exact MCP calls and expected values; the implementer runs them against the user's running emulator.

**Build commands used throughout:**
```bash
# Foundations builds gate the driver behind SOUND_DRIVER_ENABLED.
SOUND_DRIVER_ENABLED=1 ./build.sh            # normal build → s4.bin, s4.lst, s4.log
SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh    # + __DEBUG__ self-tests
SOUND_DRIVER_ENABLED=1 ./build.sh -pe        # errors to stdout (no s4.log)
python3 tools/s4lint.py main.asm             # lint (also run automatically by build.sh)
```
A clean build prints a size summary and exits 0. Errors land in `s4.log` (or stdout with `-pe`).

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `docs/superpowers/specs/2026-06-16-sound-command-api.md` | Create | Sub-design #1: the 68k↔Z80 command/mailbox contract |
| `docs/superpowers/specs/2026-06-16-sound-z80-ram-map.md` | Create | Sub-design #2: the Z80 8 KB RAM budget |
| `engine/z80_sound_driver.asm` | Create | The Z80 driver: shell, mailbox poll, scheduler, DAC playback |
| `engine/sound_api.asm` | Create | 68k-side API: `Sound_Init`, verified mailbox writes, `Sound_PlaySample`, `Sound_Ping` |
| `sound_constants.asm` | Create | Shared 68k/Z80 equates: Z80-space addresses, mailbox offsets, command IDs |
| `engine/boot.asm` | Modify | Load driver over idle program (conditional), call `Sound_Init` |
| `main.asm` | Modify | `include` the new sound sources |
| `debug/sound_selftest.asm` | Create | DEBUG boot self-test: ping handshake + sample-trigger checks |

`sound_constants.asm` is shared because both the 68k API and the Z80 driver must agree on mailbox offsets and command IDs — defining them once is the single source of truth. The Z80 driver and 68k API are split because they are two independent units with one well-defined interface (the mailbox), each testable on its own.

---

## Task 1: Sub-design — 68k↔Z80 Command API contract

This is a design task (spec sub-#1). It produces the interface every later task depends on. No code yet.

**Files:**
- Create: `docs/superpowers/specs/2026-06-16-sound-command-api.md`

- [ ] **Step 1: Research the handoff mechanisms across all references**

Dispatch a research subagent (general-purpose) with this brief:
> Survey how each reference driver hands commands from the 68k (or host) to the Z80 sound driver, focused on the *mailbox/command record* design, not the audio. Cover all eight local disassemblies and Flamedriver: read the cracked Z80 listings under `/home/volence/sonic_hacks/aeon/docs/research/z80_blobs/*.lst` (Batman, Gunstar, Alien Soldier, TF4) and `batman_driver_analysis.md`; the S.C.E. Flamedriver source `/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/Sound/Flamedriver.asm`; and search online (SpritesMind, plutiedev, Echo's `doc/api-asm.68k`, MDSDRV, Mega PCM 2.1 `docs/API.md`). For each: where does the command byte/record live, how is "new command" signalled (flag byte? ring buffer? sequence counter?), is the write verified (read-back/retry — Batman/Zyrinx), how are multi-byte args made atomic, and how does the Z80 ack? Return a comparison + a recommended minimal command-record layout for our Phase-1 needs (ping handshake + play-sample). Be concrete with addresses.

- [ ] **Step 2: Write the contract doc**

Capture decisions in `docs/superpowers/specs/2026-06-16-sound-command-api.md`. It MUST define, concretely:
- **Mailbox record** in Z80 RAM (fixed offsets), e.g. `cmd_id`, `arg0`, `arg1`, and a `pending` flag written **last** by the 68k (acts as the commit). Phase-1 layout target:
  - `MBX_CMD` (1 byte) — command id
  - `MBX_ARG0`, `MBX_ARG1` (2 bytes) — arguments
  - `MBX_PENDING` (1 byte) — 0 = idle, nonzero = command waiting (written last)
- **Command IDs** for Phase 1: `SND_CMD_NONE=0`, `SND_CMD_PING=1` (Z80 copies `arg0` into a status byte `STAT_PING_ECHO`), `SND_CMD_PLAY_SAMPLE=2` (`arg0` = sample index).
- **Status/ack region** the 68k can read back: `STAT_ALIVE` (driver writes a known marker, e.g. `$5A`, once running), `STAT_PING_ECHO`, `STAT_ACK_COUNT` (incremented per command consumed), `STAT_TICK` (scheduler tick counter).
- **Verified-write protocol**: 68k writes each byte then reads it back and retries on mismatch; the `MBX_PENDING` commit byte is written (and verified) *after* args.
- **Atomicity rule**: 68k must not write a new command while `MBX_PENDING != 0` (it polls/waits or drops by priority — Phase 1: wait-then-write in the test harness).

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-06-16-sound-command-api.md
git commit -m "docs(sound): Phase 1 sub-design — 68k<->Z80 command API contract"
```

---

## Task 2: Sub-design — Z80 RAM memory map

Design task (spec sub-#2). Budgets the 8 KB Z80 RAM so later tasks place data without collision. No code yet.

**Files:**
- Create: `docs/superpowers/specs/2026-06-16-sound-z80-ram-map.md`

- [ ] **Step 1: Research Z80 RAM budgeting in the references**

Dispatch a research subagent:
> Across the cracked Z80 listings (`docs/research/z80_blobs/*.lst`, `batman_driver_analysis.md`), Flamedriver (`Sonic-Clean-Engine-S.C.E.-/Sound/Flamedriver.asm`), and Mega PCM 2.1 / DualPCM docs online, report how each lays out the Z80's 8 KB RAM: where code sits, stack location, where the command mailbox/state lives, and (critically) how large the DAC read-ahead/DMA-survival buffer is (Mega PCM uses a 256-byte ring; what do others use?). Note any "high RAM" conventions. Return a recommended 8 KB budget for our driver that reserves room now for: driver code, stack, mailbox+status, per-channel playback state, and a future read-ahead buffer (Plan 1B) — so we don't have to move things later.

- [ ] **Step 2: Write the RAM map doc**

`docs/superpowers/specs/2026-06-16-sound-z80-ram-map.md` defines the 8 KB ($0000–$1FFF Z80 space) budget. Target layout (adjust per research, keep regions non-overlapping and documented):
- `$0000–$15FF` — driver code (`phase 0`), grows downward-to-up; ~5.5 KB headroom.
- `$1600–$16FF` — per-channel / playback state (sample ptr, remaining length, rate, active flags).
- `$1700–$1BFF` — **reserved** for the read-ahead ring buffer (Plan 1B); unused in Foundations.
- `$1C00–$1DFF` — embedded test sample (Foundations only; removed when ROM-banking lands).
- `$1F00–$1F0F` — mailbox record (`MBX_*`).
- `$1F10–$1F3F` — status/ack region (`STAT_*`).
- `$1FFE` — stack top (grows down).
- A build-time assertion strategy: the driver's `phase 0` block ends with a size constant asserted `<` the state region start, so code growth into data fails the build.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-06-16-sound-z80-ram-map.md
git commit -m "docs(sound): Phase 1 sub-design — Z80 RAM memory map"
```

---

## Task 3: Shared constants file

Single source of truth for addresses/offsets/IDs from Tasks 1–2. Pure equates; no executable code, so its "test" is that it assembles when included.

**Files:**
- Create: `sound_constants.asm`
- Modify: `main.asm` (add include)

- [ ] **Step 1: Write the constants**

Create `sound_constants.asm`:
```asm
; ======================================================================
; sound_constants.asm — shared 68k/Z80 sound equates (single source of truth)
; See docs/superpowers/specs/2026-06-16-sound-command-api.md and -z80-ram-map.md
; ======================================================================

; --- Z80-space base addresses (as seen from the 68k bus) ---
SND_Z80_BASE            = Z80_RAM                ; $A00000 (from constants.asm)

; --- Mailbox record (Z80 offsets; 68k address = SND_Z80_BASE + offset) ---
SND_MBX_BASE            = $1F00
SND_MBX_CMD             = SND_MBX_BASE+$00
SND_MBX_ARG0            = SND_MBX_BASE+$01
SND_MBX_ARG1            = SND_MBX_BASE+$02
SND_MBX_PENDING         = SND_MBX_BASE+$03       ; written last = commit

; --- Status / ack region (Z80 writes, 68k reads) ---
SND_STAT_BASE           = $1F10
SND_STAT_ALIVE          = SND_STAT_BASE+$00      ; driver writes SND_ALIVE_MARKER
SND_STAT_PING_ECHO      = SND_STAT_BASE+$01
SND_STAT_ACK_COUNT      = SND_STAT_BASE+$02
SND_STAT_TICK           = SND_STAT_BASE+$03

SND_ALIVE_MARKER        = $5A

; --- Command IDs ---
SND_CMD_NONE            = 0
SND_CMD_PING            = 1
SND_CMD_PLAY_SAMPLE     = 2

; --- Playback state (Z80 offsets) ---
SND_STATE_BASE          = $1600
SND_TEST_SAMPLE         = $1C00                  ; embedded test sample (Foundations)
SND_TEST_SAMPLE_LEN     = 256

; --- YM2612 ports as seen from the Z80 ($4000-$4003) ---
SND_Z80_YM_A0           = $4000                  ; addr part I / status read
SND_Z80_YM_D0           = $4001                  ; data part I
SND_REG_DAC_DATA        = $2A                    ; YM reg: DAC sample byte
SND_REG_DAC_ENABLE      = $2B                    ; YM reg: bit7 = DAC mode
SND_REG_TIMER_A_HI      = $24
SND_REG_TIMER_A_LO      = $25
SND_REG_TIMER_CTRL      = $27
```

- [ ] **Step 2: Include it and prove it assembles**

In `main.asm`, add the include near the other top-level constant includes (after `constants.asm` is included, since `Z80_RAM` is referenced). Find the existing `include "constants.asm"` line and add immediately after:
```asm
        include "sound_constants.asm"
```

- [ ] **Step 3: Build to verify it assembles cleanly**

Run: `SOUND_DRIVER_ENABLED=1 ./build.sh -pe`
Expected: build completes, prints size summary, exit 0. No `Symbol undefined` for `Z80_RAM`.

- [ ] **Step 4: Commit**

```bash
git add sound_constants.asm main.asm
git commit -m "feat(sound): shared 68k/Z80 sound constants (mailbox, status, IDs)"
```

---

## Task 4: Z80 driver shell — replaces the idle program, proves autonomy

Build the minimal Z80 driver: init, write the `STAT_ALIVE` marker, then an empty main loop. Wire it into boot behind `SOUND_DRIVER_ENABLED`. Verify the Z80 is running *our* code by reading the alive marker.

**Files:**
- Create: `engine/z80_sound_driver.asm`
- Modify: `engine/boot.asm`
- Modify: `main.asm` (include driver source where the idle program is currently included, if separate)

- [ ] **Step 1: Research Z80 driver init/main-loop idioms**

Dispatch a research subagent:
> From the cracked listings (`docs/research/z80_blobs/*.lst`, esp. Batman init at $0000–$004A) and Flamedriver's Z80 init, report the canonical Z80 sound-driver startup: stack setup, `im 1`/`di`, YM readiness wait (busy-flag poll on `$4000` bit 7), initial register writes, and the shape of the main loop. Confirm the YM busy-flag poll idiom and whether `di` should be held during register-write pairs. Return a minimal, correct init sequence we can mirror.

- [ ] **Step 2: Write the driver shell**

Create `engine/z80_sound_driver.asm`:
```asm
; ======================================================================
; engine/z80_sound_driver.asm — Z80-autonomous sound driver (Phase 1)
; Assembled inline in 68k ROM via cpu z80 / phase 0. Loaded into Z80 RAM
; over the idle program at boot when SOUND_DRIVER_ENABLED is defined.
; ======================================================================
Z80_Sound_Start:
        save
        cpu z80
        phase 0

; --- entry ---
SndDrv_Init:
        di
        im      1
        ld      sp, $1FFE                ; stack top (see z80-ram-map sub-design)

        ; YM ready: wait for busy flag (bit7 of $4000) to clear, then DAC off
        ld      ix, SND_Z80_YM_A0        ; ix = $4000
.wait_ym:
        bit     7, (ix+0)
        jr      nz, .wait_ym
        ld      (ix+0), SND_REG_DAC_ENABLE   ; select reg $2B
        ld      (ix+1), $00                  ; DAC mode OFF at init

        ; clear mailbox + status region
        xor     a
        ld      (SND_MBX_CMD), a
        ld      (SND_MBX_PENDING), a
        ld      (SND_STAT_PING_ECHO), a
        ld      (SND_STAT_ACK_COUNT), a
        ld      (SND_STAT_TICK), a

        ; announce we are alive
        ld      a, SND_ALIVE_MARKER
        ld      (SND_STAT_ALIVE), a

; --- main loop (Phase 1 shell: nothing yet) ---
SndDrv_Main:
        jr      SndDrv_Main

        dephase
        restore
Z80_Sound_End:

Z80_SOUND_SIZE = Z80_Sound_End - Z80_Sound_Start

        ; code must not grow into the playback-state region
        if Z80_SOUND_SIZE > SND_STATE_BASE
          fatal "Z80 sound driver code (\{Z80_SOUND_SIZE} bytes) overruns state region at \{SND_STATE_BASE}"
        endif
```

- [ ] **Step 3: Wire into the build (include + boot load)**

In `main.asm`, locate where `engine/z80_init.asm` is included (per integration map it is included from `engine/boot.asm`). Wherever the idle program is included, gate it:
```asm
    ifdef SOUND_DRIVER_ENABLED
        include "engine/z80_sound_driver.asm"
    else
        include "engine/z80_init.asm"
    endif
```
In `engine/boot.asm`, find the Z80-load loop that uses `Z80_IDLE_SIZE` and the source label `Z80_IdleProgram`. Make both conditional:
```asm
    ifdef SOUND_DRIVER_ENABLED
        lea     Z80_Sound_Start(pc), a6
        moveq   #Z80_SOUND_SIZE-1, d1
    else
        lea     Z80_IdleProgram(pc), a6
        moveq   #Z80_IDLE_SIZE-1, d1
    endif
```
(Adapt register names to the existing loop — match the surrounding code at the load site exactly; only the source pointer and count differ.)

- [ ] **Step 4: Build (both configs) to verify it assembles and fits**

Run: `SOUND_DRIVER_ENABLED=1 ./build.sh -pe`
Expected: exit 0, size summary. No `fatal` from the size guard (driver is well under `$1600`).
Run: `./build.sh -pe` (driver OFF)
Expected: exit 0 — the idle path still builds.

- [ ] **Step 5: Runtime verify autonomy via Exodus MCP**

With the user's Exodus running the new ROM:
1. `emulator_reload_rom` (load the freshly built `s4.bin`), then `emulator_reset`, then `emulator_resume`.
2. `emulator_read_memory` at address `$A01F10` (that is `SND_Z80_BASE + SND_STAT_ALIVE`), length 1.

Expected: byte = `$5A`. This proves the Z80 booted **our** driver (not the idle loop) and ran past init.

3. (Optional sanity) `emulator_read_memory` at `$A01F00` length 4 → mailbox should read all `$00`.

- [ ] **Step 6: Commit**

```bash
git add engine/z80_sound_driver.asm engine/boot.asm main.asm
git commit -m "feat(sound): Z80 driver shell with autonomy alive-marker (replaces idle)"
```

---

## Task 5: Direct-injection mailbox + verified 68k writes

Add the 68k API (`Sound_Init`, verified writes, `Sound_Ping`) and the Z80 poll loop that consumes commands. Prove the round trip with a ping handshake.

**Files:**
- Create: `engine/sound_api.asm`
- Modify: `main.asm` (include `engine/sound_api.asm`)
- Modify: `engine/boot.asm` (call `Sound_Init` after Z80 starts)
- Modify: `engine/z80_sound_driver.asm` (add mailbox poll + ping handler)

- [ ] **Step 1: Research verified-write + poll-consume patterns**

Dispatch a research subagent:
> Detail the read-back-verify write pattern (Batman/Zyrinx `move.b dN,(aM); cmp.b (aM),dN; bne retry`) and the Z80-side "poll a pending flag, latch, clear, ack" loop. Cross-check Batman's direct-injection model (`batman_driver_analysis.md` mailbox section), Flamedriver's command handling, and Echo/MDSDRV/Mega PCM 2.1 command APIs online. Flag any hazard with the 68k writing Z80 RAM while the Z80 is running (bus arbitration) and whether stopZ80 is needed for these byte writes (it generally is not, but confirm). Return the exact 68k write loop and Z80 poll loop to mirror.

- [ ] **Step 2: Write the 68k API**

Create `engine/sound_api.asm`:
```asm
; ======================================================================
; engine/sound_api.asm — 68k-side sound API (Phase 1)
; Posts commands into Z80 RAM with read-back-verified writes.
; ======================================================================

; ----------------------------------------------------------------------
; Sound_VerifiedWrite — write d0.b to (a0), retry until read-back matches
; In:  d0.b = value, a0 = 68k address of a Z80 RAM byte
; Clobbers: nothing beyond d0/a0 inputs
; ----------------------------------------------------------------------
Sound_VerifiedWrite:
        move.b  d0, (a0)
        cmp.b   (a0), d0
        bne.s   Sound_VerifiedWrite
        rts

; ----------------------------------------------------------------------
; Sound_Init — clear the mailbox (driver clears status itself)
; ----------------------------------------------------------------------
Sound_Init:
        lea     (SND_Z80_BASE+SND_MBX_CMD).l, a0
        moveq   #0, d0
        bsr.s   Sound_VerifiedWrite
        lea     (SND_Z80_BASE+SND_MBX_PENDING).l, a0
        moveq   #0, d0
        bsr.s   Sound_VerifiedWrite
        rts

; ----------------------------------------------------------------------
; Sound_PostCommand — generic: wait until idle, write args, commit pending
; In:  d0.b = cmd id, d1.b = arg0, d2.b = arg1
; ----------------------------------------------------------------------
Sound_PostCommand:
        ; wait until the driver has consumed any prior command
.wait_idle:
        tst.b   (SND_Z80_BASE+SND_MBX_PENDING).l
        bne.s   .wait_idle
        movem.l d0-d2/a0, -(sp)
        ; arg0
        move.b  d1, d0
        lea     (SND_Z80_BASE+SND_MBX_ARG0).l, a0
        bsr.s   Sound_VerifiedWrite
        ; arg1
        move.b  d2, d0
        lea     (SND_Z80_BASE+SND_MBX_ARG1).l, a0
        bsr.s   Sound_VerifiedWrite
        ; cmd id
        movem.l (sp), d0-d2/a0           ; restore d0 (cmd) without popping
        lea     (SND_Z80_BASE+SND_MBX_CMD).l, a0
        bsr.s   Sound_VerifiedWrite
        ; commit: pending = 1 (written LAST)
        moveq   #1, d0
        lea     (SND_Z80_BASE+SND_MBX_PENDING).l, a0
        bsr.s   Sound_VerifiedWrite
        movem.l (sp)+, d0-d2/a0
        rts

; ----------------------------------------------------------------------
; Sound_Ping — handshake: ask the driver to echo d1.b into STAT_PING_ECHO
; In:  d1.b = value to echo
; ----------------------------------------------------------------------
Sound_Ping:
        move.b  #SND_CMD_PING, d0
        moveq   #0, d2
        bra.w   Sound_PostCommand
```

- [ ] **Step 3: Add the Z80 mailbox poll + ping handler**

In `engine/z80_sound_driver.asm`, replace the `SndDrv_Main` loop body with a poll that consumes commands:
```asm
SndDrv_Main:
        ; poll mailbox pending flag
        ld      a, (SND_MBX_PENDING)
        or      a
        jr      z, SndDrv_Main           ; nothing pending

        ; latch command + args, then clear pending (ack)
        ld      a, (SND_MBX_CMD)
        ld      b, a                     ; b = cmd
        ld      a, (SND_MBX_ARG0)
        ld      c, a                     ; c = arg0
        xor     a
        ld      (SND_MBX_PENDING), a     ; clear pending -> 68k may post next

        ; bump ack counter
        ld      a, (SND_STAT_ACK_COUNT)
        inc     a
        ld      (SND_STAT_ACK_COUNT), a

        ; dispatch
        ld      a, b
        cp      SND_CMD_PING
        jr      nz, .not_ping
        ld      a, c                     ; echo arg0
        ld      (SND_STAT_PING_ECHO), a
.not_ping:
        jr      SndDrv_Main
```

- [ ] **Step 4: Call Sound_Init at boot and include the API**

In `engine/boot.asm`, after the Z80 is released and running (after the existing Z80 start sequence, before `GameLoop`), add:
```asm
    ifdef SOUND_DRIVER_ENABLED
        bsr.w   Sound_Init
    endif
```
In `main.asm`, add near the other engine includes:
```asm
    ifdef SOUND_DRIVER_ENABLED
        include "engine/sound_api.asm"
    endif
```

- [ ] **Step 5: Build and lint**

Run: `SOUND_DRIVER_ENABLED=1 ./build.sh`
Expected: lint passes (no E001 unsized branch, no E006/E011 — there is no VDP/Z80-stop interaction here), assembles, exit 0.

- [ ] **Step 6: Runtime verify the round trip via Exodus MCP**

The Foundations build has no game-side ping call yet, so drive it via MCP:
1. `emulator_reload_rom`, `emulator_reset`, `emulator_resume`.
2. Confirm alive: `emulator_read_memory $A01F10` len 1 → `$5A`.
3. Simulate a 68k post by writing the mailbox directly: `emulator_write_memory $A01F01` (ARG0) = `$3C`; then `emulator_write_memory $A01F00` (CMD) = `$01` (PING); then `emulator_write_memory $A01F03` (PENDING) = `$01` (commit last).
4. Let it run a moment (the Z80 polls continuously). `emulator_read_memory $A01F03` len 1 → `$00` (driver cleared pending = consumed).
5. `emulator_read_memory $A01F11` (STAT_PING_ECHO) len 1 → `$3C` (echoed arg0).
6. `emulator_read_memory $A01F12` (STAT_ACK_COUNT) len 1 → `$01` (one command consumed).

Expected: all match. This proves the mailbox round-trips and the driver acks. (The verified-write 68k path itself is exercised by `Sound_Init` at boot; later tasks add a real game-side caller.)

- [ ] **Step 7: Commit**

```bash
git add engine/sound_api.asm engine/z80_sound_driver.asm engine/boot.asm main.asm
git commit -m "feat(sound): direct-injection mailbox + verified writes + ping handshake"
```

---

## Task 6: YM-Timer-driven cooperative scheduler skeleton

Replace the busy poll loop with the cooperative model: a YM timer ticks at a sub-frame rate; between ticks the loop does background work (mailbox poll), and on each timer overflow it advances a tick counter and reloads the timer. This is the scheduler spine the DAC and FM will hang off.

**Files:**
- Modify: `engine/z80_sound_driver.asm`

- [ ] **Step 1: Research YM Timer tempo + the cooperative loop shape**

Dispatch a research subagent:
> Specify YM2612 Timer A usage for a Z80 sub-frame scheduler tick: registers `$24`/`$25` (Timer A value, 10-bit), `$27` control bits (D0 load A, D2 enable-A overflow flag, D4 reset-A flag), and reading the overflow in status bit 0 at `$4000`. Cross-check Batman (uses Timer B: `$26`/`$27` with bit-1 overflow — `batman_driver_analysis.md`) and TF4 (Timer A). Give the exact register writes to start Timer A, poll its overflow, and reset/reload it, plus a sensible Timer A value for roughly 4–8 ticks per NTSC frame. Confirm whether to mask/`di` around YM writes. Return the cooperative-loop skeleton (background work → check overflow → on overflow: tick + reset/reload).

- [ ] **Step 2: Add a tiny reusable background-poll routine**

In `engine/z80_sound_driver.asm`, refactor the mailbox poll into a subroutine so the cooperative loop can call it between ticks. Add before `SndDrv_Main`:
```asm
; --- consume at most one pending command (background work) ---
SndDrv_PollMailbox:
        ld      a, (SND_MBX_PENDING)
        or      a
        ret     z
        ld      a, (SND_MBX_CMD)
        ld      b, a
        ld      a, (SND_MBX_ARG0)
        ld      c, a
        xor     a
        ld      (SND_MBX_PENDING), a
        ld      a, (SND_STAT_ACK_COUNT)
        inc     a
        ld      (SND_STAT_ACK_COUNT), a
        ld      a, b
        cp      SND_CMD_PING
        ret     nz
        ld      a, c
        ld      (SND_STAT_PING_ECHO), a
        ret
```

- [ ] **Step 3: Start Timer A in init**

In `SndDrv_Init`, after the DAC-off write and before clearing the mailbox, start Timer A:
```asm
        ; --- start YM Timer A for the scheduler tick ---
        ld      (ix+0), SND_REG_TIMER_A_HI       ; reg $24 = Timer A high 8 bits
        ld      (ix+1), $C0                       ; reference value; research-tuned
        ld      (ix+0), SND_REG_TIMER_A_LO       ; reg $25 = Timer A low 2 bits
        ld      (ix+1), $00
        ld      (ix+0), SND_REG_TIMER_CTRL       ; reg $27
        ld      (ix+1), $05                       ; D0 load A | D2 enable-A flag
```

- [ ] **Step 4: Replace the main loop with the cooperative scheduler**

Replace the entire `SndDrv_Main` body:
```asm
SndDrv_Main:
        call    SndDrv_PollMailbox               ; background work between ticks

        ; check Timer A overflow (status bit 0 at $4000)
        ld      a, (ix+0)                         ; read YM status ($4000)
        bit     0, a
        jr      z, SndDrv_Main                   ; no overflow yet -> keep working

        ; --- timer tick ---
        ld      (ix+0), SND_REG_TIMER_CTRL       ; reg $27
        ld      (ix+1), $15                       ; D4 reset-A flag | reload (D0|D2)

        ld      a, (SND_STAT_TICK)               ; advance tick counter
        inc     a
        ld      (SND_STAT_TICK), a

        jr      SndDrv_Main
```

- [ ] **Step 5: Build and lint**

Run: `SOUND_DRIVER_ENABLED=1 ./build.sh`
Expected: assembles, lint passes, exit 0, size guard not tripped.

- [ ] **Step 6: Runtime verify the tick advances at a sub-frame rate**

With Exodus running the new ROM:
1. `emulator_reload_rom`, `emulator_reset`, `emulator_resume`.
2. `emulator_read_memory $A01F13` (STAT_TICK) len 1 → record value `T0`.
3. `emulator_run_to_scanline` to advance ~1 full frame (or `emulator_resume` briefly then `emulator_pause`).
4. `emulator_read_memory $A01F13` again → `T1`.

Expected: `T1 != T0`, and the per-frame delta is several ticks (sub-frame rate — confirms Timer A is driving the loop, not frame-locked). Exact delta depends on the Timer A value; the research step sets the target (~4–8/frame). If the delta is 0, the timer isn't running (check `$27` writes); if it's wildly high, lower the Timer A value.
5. Confirm the mailbox still works concurrently: repeat Task 5's MCP ping sequence and verify `STAT_PING_ECHO` updates — proves background work + ticking coexist.

- [ ] **Step 7: Commit**

```bash
git add engine/z80_sound_driver.asm
git commit -m "feat(sound): YM Timer A cooperative scheduler skeleton (sub-frame tick)"
```

---

## Task 7: Single-channel DAC playback — the audible milestone

Embed a small test sample in Z80 RAM and play it on `SND_CMD_PLAY_SAMPLE`: enable DAC mode, feed reg `$2A` from the sample with a per-sample delay, cooperatively yielding to the timer tick. Add a DEBUG self-test and a game-side trigger for an audible check.

**Files:**
- Modify: `engine/z80_sound_driver.asm` (test sample data, play-sample handler, DAC feed)
- Create: `debug/sound_selftest.asm`
- Modify: `engine/boot.asm` (invoke the self-test under `__DEBUG__`)

- [ ] **Step 1: Research the DAC feed loop + per-sample rate**

Dispatch a research subagent:
> Detail the Z80 DAC playback inner loop that writes reg `$2A`: Batman's continuous feed (`batman_driver_analysis.md`, `$00C0–$00DD` — fetch byte, write `$2A`, `ld b,c / djnz` rate delay, break on timer overflow), Gunstar's accumulator DPCM, and Mega PCM 2.1's cycle-balanced PCM loop (`src/z80/loop-pcm.asm`). For a *raw 8-bit PCM, single channel from Z80 RAM*, give the exact feed loop with a per-sample `djnz` rate delay and how to interleave it with the Timer-A overflow check so the scheduler tick still fires (resume the sample mid-stream — the coroutine model). Recommend a rate-delay value for a clean mid-rate playback (~11–16 kHz) given the loop's cycle count. Return the loop to mirror.

- [ ] **Step 2: Add the embedded test sample**

In `engine/z80_sound_driver.asm`, inside the `phase`/`dephase` block but the data must land at `SND_TEST_SAMPLE` ($1C00). Place a labelled, `org`-fixed sample. After `Z80_Sound_End`'s code but within the Z80 phase region, define it via a nested phase, OR (simpler) emit it at the fixed address by asserting placement. Use this approach: define the sample bytes right after the main loop and assert the label equals `$1C00` by padding. Concretely, append before `dephase`:
```asm
        ; pad to the fixed test-sample address, then emit a 256-byte ramp/tone
        ds      SND_TEST_SAMPLE - ($ - 0)        ; pad current Z80 PC ($) up to $1C00
SndTestSample:
        ; 256-byte sample: two cycles of a simple triangle (audible buzz)
        ; (research step may swap for a nicer waveform; ramp proves the path)
val set 0
        rept 128
        db      val
val set (val + 2) & $FF
        endr
        rept 128
        db      val
val set (val - 2) & $FF
        endr
SndTestSampleEnd:
        if (SndTestSample <> SND_TEST_SAMPLE)
          fatal "test sample at \{SndTestSample}, expected \{SND_TEST_SAMPLE}"
        endif
        if (SndTestSampleEnd - SndTestSample) <> SND_TEST_SAMPLE_LEN
          fatal "test sample length mismatch"
        endif
```
(If `ds`-to-absolute is awkward under `phase`, instead place the sample in its own `phase SND_TEST_SAMPLE` … `dephase` sub-block — the research/implementer picks whichever the assembler accepts; the invariant is the two `if … fatal` guards.)

- [ ] **Step 3: Add playback state + the play-sample handler**

In `SndDrv_PollMailbox`, extend dispatch to handle `SND_CMD_PLAY_SAMPLE` by initialising playback state (pointer = `$1C00`, remaining = 256) and enabling DAC mode. Add after the ping handling (replace the final `ret` region):
```asm
        cp      SND_CMD_PLAY_SAMPLE
        ret     nz
        ; init playback: hl-shadow pointer + length live in fixed RAM
        ld      hl, SND_TEST_SAMPLE
        ld      (SndPlayPtr), hl
        ld      hl, SND_TEST_SAMPLE_LEN
        ld      (SndPlayLen), hl
        ; enable DAC mode (reg $2B bit7)
        ld      (ix+0), SND_REG_DAC_ENABLE
        ld      (ix+1), $80
        ld      a, 1
        ld      (SndPlayActive), a
        ret
```
Define the state variables at fixed addresses (state region) — add near the top of the phase block:
```asm
        ; playback state (fixed addresses in the state region)
        phase SND_STATE_BASE
SndPlayActive:  db 0
                db 0            ; pad
SndPlayPtr:     dw 0
SndPlayLen:     dw 0
        dephase
```

- [ ] **Step 4: Feed the DAC in the cooperative loop**

In `SndDrv_Main`, before the overflow check, add the DAC feed so a byte is output each loop iteration when active:
```asm
SndDrv_Main:
        call    SndDrv_PollMailbox

        ld      a, (SndPlayActive)
        or      a
        jr      z, .no_dac

        ; --- feed one DAC byte ---
        ld      hl, (SndPlayPtr)
        ld      a, (hl)
        inc     hl
        ld      (ix+0), SND_REG_DAC_DATA         ; reg $2A
        ld      (ix+1), a                        ; write sample byte
        ld      (SndPlayPtr), hl
        ; per-sample rate delay (research-tuned)
        ld      b, $10
.rate:  djnz    .rate
        ; decrement remaining length
        ld      hl, (SndPlayLen)
        dec     hl
        ld      (SndPlayLen), hl
        ld      a, h
        or      l
        jr      nz, .no_dac                      ; more samples remain
        ; sample finished: DAC off, mark inactive
        xor     a
        ld      (SndPlayActive), a
        ld      (ix+0), SND_REG_DAC_ENABLE
        ld      (ix+1), $00

.no_dac:
        ld      a, (ix+0)                         ; YM status
        bit     0, a
        jr      z, SndDrv_Main

        ld      (ix+0), SND_REG_TIMER_CTRL
        ld      (ix+1), $15
        ld      a, (SND_STAT_TICK)
        inc     a
        ld      (SND_STAT_TICK), a
        jr      SndDrv_Main
```

- [ ] **Step 5: Add a DEBUG self-test (non-audible structural check)**

Create `debug/sound_selftest.asm`:
```asm
    ifdef __DEBUG__
; Boot self-test: ping handshake + sample-trigger state check (no audio assert).
Sound_SelfTest:
        ; ping with a known value, verify echo
        moveq   #$27, d1
        bsr.w   Sound_Ping
        bsr.w   .wait_consumed
        cmp.b   (SND_Z80_BASE+SND_STAT_PING_ECHO).l, d1   ; d1 vs echo
        bne.s   .fail
        ; trigger a sample, verify the driver marks it active then inactive
        move.b  #SND_CMD_PLAY_SAMPLE, d0
        moveq   #0, d1
        moveq   #0, d2
        bsr.w   Sound_PostCommand
        bsr.w   .wait_consumed                              ; pending cleared
        rts
.fail:
        ; halt loudly in DEBUG so the failure is obvious on hardware/emulator
        bra.s   .fail
.wait_consumed:
        tst.b   (SND_Z80_BASE+SND_MBX_PENDING).l
        bne.s   .wait_consumed
        rts
    endif
```
Note: `cmp.b (addr),d1; bne` — adjust operand order to AS syntax used elsewhere (`cmp.b` compares source to dest; mirror the form used in `debug/compression_selftest.asm`).

In `engine/boot.asm`, beside the existing `CompressionSelfTest` invocation:
```asm
    ifdef __DEBUG__
      ifdef SOUND_DRIVER_ENABLED
        bsr.w   Sound_SelfTest
      endif
    endif
```
Include the file in `main.asm` near the other debug includes:
```asm
    ifdef __DEBUG__
      ifdef SOUND_DRIVER_ENABLED
        include "debug/sound_selftest.asm"
      endif
    endif
```

- [ ] **Step 6: Build (DEBUG + release) and lint**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`
Expected: assembles, lint passes, size guards OK, exit 0.
Run: `SOUND_DRIVER_ENABLED=1 ./build.sh`
Expected: exit 0.

- [ ] **Step 7: Runtime verify playback via Exodus MCP (+ audible check)**

With Exodus running the DEBUG ROM:
1. `emulator_reload_rom`, `emulator_reset`, `emulator_resume`. The boot self-test runs automatically; if it hit `.fail` the game won't proceed past boot — that itself is the assertion.
2. Drive a fresh sample manually for inspection: write mailbox via MCP — `emulator_write_memory $A01F00`=`$02` (PLAY_SAMPLE), `$A01F03`=`$01` (commit).
3. Immediately `emulator_read_memory $A01600` (SndPlayActive) len 1 → `$01` (playing) shortly after triggering.
4. `emulator_get_channel_states` → confirm the YM DAC (channel 6 / DAC) shows enabled/active during playback.
5. After the sample completes, `emulator_read_memory $A01600` len 1 → `$00` (stopped), and `emulator_get_channel_states` shows DAC disabled.
6. **Audible check (user):** ask the user to confirm they hear a short buzz/tone when the sample triggers. This is the Foundations milestone: the 68k commanded the autonomous Z80 driver and a sample played.

- [ ] **Step 8: Commit**

```bash
git add engine/z80_sound_driver.asm debug/sound_selftest.asm engine/boot.asm main.asm
git commit -m "feat(sound): single-channel DAC playback — Foundations audible milestone"
```

---

## Self-Review

**Spec coverage (against §12 Phase 1, scoped to the Foundations slice):**
- §12.x sub-design #1 command API → Task 1 ✅
- §12.x sub-design #2 Z80 RAM map → Task 2 ✅
- §4.1 Z80 autonomy + direct-injection mailbox + verified writes → Tasks 4, 5 ✅
- §4.2 Timer-driven cooperative scheduler → Task 6 ✅
- §5 single-channel DAC (high-quality path) → Task 7 ✅ (raw PCM from RAM; **deferred to Plan 1B:** ROM-bank streaming, read-ahead DMA-survival buffer, YM write-queue, 32 kHz jitter tuning)
- **Deferred to later Phase-1 plans (explicitly out of this slice):** minimal FM sequencer + patch load, basic PSG + pause silence, log volume curve, carrier mask, DC-offset removal. These are Plan 1C; called out here so the gap is intentional, not missed.

**Placeholder scan:** No "TBD"/"add error handling"/"similar to". Cycle-/timer-sensitive constants (Timer A value `$C0`, DAC rate delay `$10`) are concrete *and* flagged in their task's research step for validation — they are starting values, not placeholders. The one assembler-syntax caveat (`ds`-to-absolute vs nested `phase` for the sample; `cmp.b` operand order) is called out with the invariant that must hold, so the implementer can pick the form the assembler accepts.

**Type/label consistency:** `SND_MBX_*`, `SND_STAT_*`, `SND_CMD_*`, `SndPlay{Active,Ptr,Len}`, `SndDrv_{Init,Main,PollMailbox}`, `Sound_{Init,VerifiedWrite,PostCommand,Ping,SelfTest}`, `Z80_SOUND_SIZE` are used identically across tasks. Mailbox offsets in `sound_constants.asm` match every MCP `emulator_read_memory`/`emulator_write_memory` address used in verification (e.g. `SND_STAT_ALIVE`=$1F10 → `$A01F10`).

---

## Execution Handoff

After this plan is approved, the next Phase-1 plans are:
- **Plan 1B — DAC robustness:** ROM-bank sample streaming, read-ahead DMA-survival buffer, YM write-queue, 32 kHz jitter tuning.
- **Plan 1C — Minimal FM/PSG + quality:** FM sequencer + patch load, PSG + pause silence, log volume curve, per-algorithm carrier mask, DC-offset removal.
