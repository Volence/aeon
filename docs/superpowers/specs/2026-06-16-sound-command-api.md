# Sub-Design — 68k↔Z80 Sound Command API Contract (Phase 1)

**Date:** 2026-06-16
**Status:** Contract approved for Phase 1 — defines the interface every later sound task depends on
**Branch:** `design/sound-driver`
**Parent spec:** `docs/superpowers/specs/2026-06-16-sound-driver-design.md` (§4.1 Z80 autonomy & 68k handoff, §12.x #1 command-API sub-design)
**Consumed by:** Task 3 transcribes the constants below into `sound_constants.asm`. The offsets/IDs here are the agreed Phase-1 targets — validated against research, unchanged.

This is the **Phase 1 minimal** contract: a ping handshake and a play-sample command, plus
the status/ack region the 68k polls. It is deliberately a *strict subset* of the eventual full
command set (§12.x #1: `PlayMusic`, `PlaySFX`, `PlaySoundLocal`, continuous SFX, bank-swap,
fades). The record layout and verified-write protocol defined here are designed so that fuller
commands slot in later **without changing the handoff mechanism** — only adding command IDs and
(for variable-length payloads) a second staging record.

---

## 1. Research findings

Surveyed how each reference driver hands a command from the host (68k) to the Z80, focused on
the *mailbox / command-record* mechanism (not the audio). Sources read in full are cited inline.

### Reference comparison

| Driver | Where the command lives | "New command" signal | Verified write? | Multi-byte atomicity | Z80 ack |
|---|---|---|---|---|---|
| **Batman & Robin** (Jesper Kyd) | Direct-injection records in Z80 RAM: DAC staging block `$16EA–$16F3` + a request flag `$16F4`; 6× channel-start records at `$17EA` (6 bytes each) | **Flag byte written last** (`$16F4 = $80`) for DAC; for channel-start, record's **first byte nonzero** | No read-back *in the blob* (the 68k loader is not in the blob; verified writes are a Zyrinx-era 68k-side convention) | All arg bytes written **before** the flag/first-byte commit; Z80 latches the whole block in one pass | Z80 **clears** the flag / zeroes the record after latching (clear = consumed) |
| **Flamedriver / SMPS** (S.C.E.) | 3 contiguous input bytes `zMusicNumber`, `zSFXNumber0`, `zSFXNumber1` (forced even-aligned, read by 68k **as a longword**) | Nonzero byte present (`or e / or d` test "anything in the play queue?") | No read-back | The 3 bytes are written and the Z80 reads them together once per frame; even-alignment lets the 68k post them as one aligned write | Z80 **zeroes** each input byte after transferring it into its internal queue |
| **Echo** (sikthehedgehog) | Two 4-byte command slots at the **top of Z80 RAM** (`$A01FFC`/`$A01FFF` window); status byte at `$A01FF0` | **Command-ID byte written LAST** is the commit; 68k tests slot byte `== 0` (idle) before writing | No read-back; instead the 68k **requests the Z80 bus** (`Z80Request`) so the write can't race the driver | Args (e.g. the banked 3-byte address) written **first**, command-ID byte (the commit) written **last**; whole thing under Z80-bus-held | Z80 **zeroes** the slot's command byte when consumed; 68k busy-waits on `tst.b (slot)` and falls back to a 2nd slot |
| **Mega PCM 2.1** (vladikcomper) | Single `CommandInput` byte in Z80 RAM (`move.b X, MegaPCM_CommandInput_Addr`) + a status-output byte | The byte itself; **"last command wins"** — driver reads `CommandInput` once per frame, a few scanlines after VBlank | No read-back | Play-sample is a **single byte** (sample ID ≥ `$81`), so atomicity is trivial; priority resolves conflicts (higher-priority sample isn't overridden) | Status-output byte the 68k can poll; driver consumes once per frame |
| **Gunstar / Alien / TF4** (Treasure/Technosoft, SMPS-derived) | SMPS-style queue bytes in low Z80 RAM (`$1FF7`, `$1FFA`, `$1FFB`, `$1FFE` in Gunstar's blob) | Nonzero byte in a queue slot | No read-back | Single-byte sound IDs | Driver clears the slot after dequeuing |

### What the survey establishes

1. **The flag-byte-written-last commit is universal.** Every record-style driver (Batman, Echo)
   writes the payload first and the "go" byte last, so the Z80 can never latch a half-written
   record. Mega PCM / SMPS sidestep it by making the command a single byte (atomic by
   construction). This is the load-bearing rule.

2. **"Pending" is encoded in the commit byte itself.** Batman's `$16F4`, Echo's slot command-ID
   byte, and SMPS's `zMusicNumber` all double as both the command *and* the "there is a command"
   flag: **nonzero = pending, zero = idle**. The Z80 **zeroes it to ack** (= "consumed"). We
   adopt this but make `pending` a **dedicated byte** separate from `cmd_id` (see §5 rationale) —
   cleaner than overloading and lets `cmd_id` keep a real value while `pending` toggles.

3. **No reference reads back its writes** — but all of them either hold the Z80 bus during the
   write (Echo) or accept the small race because the Genesis Z80↔68k RAM path is normally
   reliable. Our parent spec (§4.1) deliberately goes further: **read-back-and-retry verified
   writes** (Batman/Zyrinx convention, also logged in `DEFERRED_WORK`) to harden against bus
   contention during 68k→VDP DMA. This is a *superset* of every reference and is cheap (~8
   cycles/byte). We keep it.

4. **Atomicity = don't write while pending.** Echo busy-waits on the slot byte; Mega PCM accepts
   "last write wins" within a frame. For our Phase-1 **test harness** we take the simplest
   correct rule: the 68k **must not** post a new command while `pending != 0`. (A later full API
   may add Echo-style multi-slot queuing; not needed for ping + play-sample.)

5. **A status/ack region the 68k polls is standard** (Echo's `$A01FF0` status word, Mega PCM's
   status-output byte, Batman's inferred `$1810+` heartbeat snapshot). We formalize a small
   fixed-offset status block with an alive marker, a ping echo, an ack counter, and a scheduler
   tick — enough to verify the driver is running and consuming commands in Phase 1.

**Sources:**
- `docs/research/z80_blobs/batman_driver_analysis.md` §7 (68k→Z80 mailbox: DAC staging `$16EA`
  + flag `$16F4`; channel-start records `$17EA`) and §0/§12.6 (direct-injection, zero-parse).
- S.C.E. Flamedriver source `Sound/Flamedriver.asm` lines 285–328 (`zMusicNumber`/`zSFXNumber0/1`
  even-aligned 68k input, longword note at line 369–371) and 905–950 / 1795–1841
  (`zFillSoundQueue`, queue cycling, clear-to-ack).
- Echo `doc/api-asm.68k` (`Echo_GetStatus` busy bit 15; `Echo_SendCommand*` write command byte
  last) and `src-68k/echo.68k` lines 42–113 (two-slot mailbox at `$A01FFC/$A01FFF`,
  `tst.b (slot)` idle check, `Z80Request`/`Z80Release` around the write, command-ID written last,
  banked-address arg bytes written before it).
- Mega PCM 2.1 `docs/API.md` (`MPCM_play` ≡ `move.b X, MegaPCM_CommandInput_Addr`; single command
  byte; "accepts commands once per frame… only the last stored command is processed"; priority).
- Gunstar/Alien/TF4 blobs (`docs/research/z80_blobs/gunstar_z80.lst` queue reads at `$1FFx`).

---

## 2. Mailbox record (Z80 RAM, fixed offsets)

A single fixed command record in Z80 RAM. Offsets are **relative to the mailbox base label**
(`MBX_BASE`, placed by the Z80 RAM memory-map sub-design — §12.x #2). All four bytes are
byte-sized and byte-addressable from both CPUs.

| Offset | Constant | Size | Written by | Meaning |
|---|---|---|---|---|
| `+$00` | `MBX_CMD`     | 1 | 68k | Command ID (see §3). Valid only while `MBX_PENDING != 0`. |
| `+$01` | `MBX_ARG0`    | 1 | 68k | First argument (command-specific). |
| `+$02` | `MBX_ARG1`    | 1 | 68k | Second argument (command-specific; unused in Phase 1, write 0). |
| `+$03` | `MBX_PENDING` | 1 | 68k → Z80 | **Commit / handshake byte.** `0` = idle (mailbox free); **nonzero = command waiting**. Written LAST by the 68k. The Z80 **clears it to 0** when it has consumed the command (this is the consume-ack). |

```
MBX_BASE + $00 : MBX_CMD       (1 byte)   ; command id
MBX_BASE + $01 : MBX_ARG0      (1 byte)   ; arg 0
MBX_BASE + $02 : MBX_ARG1      (1 byte)   ; arg 1
MBX_BASE + $03 : MBX_PENDING   (1 byte)   ; 0 = idle, nonzero = command waiting (commit byte)
                                          ; record is 4 bytes total
```

**Write ordering (the load-bearing invariant):** the 68k writes `MBX_CMD`, `MBX_ARG0`, `MBX_ARG1`
in any order, then writes `MBX_PENDING` **last**. The Z80 reads `MBX_PENDING` first; only if
nonzero does it read the args. This guarantees the Z80 never latches a partially written record —
the same flag-byte-last commit Batman (`$16F4`) and Echo (command-ID byte) rely on.

**Recommended Phase-1 commit value:** the 68k writes `MBX_PENDING = 1`. The Z80 treats any nonzero
value as pending. (A later full API may reuse `MBX_PENDING` as a monotonically incrementing
sequence counter so the 68k can detect "consumed" without a clear; for Phase 1 the
clear-to-zero ack is simpler and matches every reference.)

---

## 3. Command IDs (Phase 1)

| Constant | Value | `arg0` | `arg1` | Z80 behaviour |
|---|---|---|---|---|
| `SND_CMD_NONE`        | `0` | — | — | No command. Never written as a live command; this is the idle / "no-op" value. |
| `SND_CMD_PING`        | `1` | echo token | — | Driver copies `arg0` into the status byte `STAT_PING_ECHO`, then acks. Lets the 68k confirm a round-trip with a value it chose (proves the driver read *this* command, not a stale one). |
| `SND_CMD_PLAY_SAMPLE` | `2` | sample index | — | Driver begins playback of sample `arg0` from the sample table (single-channel DAC, Phase 1). Then acks. |

Command IDs are dense from 0 so the Z80 dispatch can be a jump table indexed by `MBX_CMD`
(`MBX_CMD < SND_CMD_COUNT` bounds-check, then `jp (table + cmd*2)`), matching the parent spec's
"byte-aligned dispatch, minimal branching" principle (§10). Future commands append (`SND_CMD_PLAY_MUSIC`,
`SND_CMD_STOP`, …) — **never renumber `0–2`**, since `sound_constants.asm` and any built ROMs
depend on them.

`SND_CMD_COUNT` = number of defined IDs (currently `3`) — exported for the dispatch bounds-check.

---

## 4. Status / ack region (Z80 RAM, 68k reads back)

A separate fixed-offset block the **Z80 writes and the 68k polls** (read-only from the 68k's
perspective). Base label `STAT_BASE` (placed by the §12.x #2 RAM map).

| Offset | Constant | Size | Written by | Meaning |
|---|---|---|---|---|
| `+$00` | `STAT_ALIVE`     | 1 | Z80 | Liveness marker. Driver writes **`$5A`** once, after init completes and its main loop is running. The 68k polls this after kicking the Z80 to confirm the driver booted. (`$5A` chosen as a non-trivial, non-zero, non-`$FF` bit pattern — distinguishable from cleared/uninitialised RAM.) |
| `+$01` | `STAT_PING_ECHO` | 1 | Z80 | Last `arg0` received via `SND_CMD_PING`. The 68k writes a token in `arg0`, then reads it back here to confirm a full round-trip. |
| `+$02` | `STAT_ACK_COUNT`  | 1 | Z80 | Incremented (mod 256) **once per command consumed**. The 68k snapshots it before posting and waits for it to change → command was processed. Robust even if the 68k misses the `MBX_PENDING` clear edge. |
| `+$03` | `STAT_TICK`       | 1 | Z80 | Scheduler tick counter (incremented every Timer tick, §4.2 of parent). Lets the 68k confirm the cooperative scheduler is actually running (value changing), independent of commands. |

```
STAT_BASE + $00 : STAT_ALIVE      (1 byte)   ; $5A once driver is running
STAT_BASE + $01 : STAT_PING_ECHO  (1 byte)   ; arg0 of last PING
STAT_BASE + $02 : STAT_ACK_COUNT  (1 byte)   ; ++ per command consumed (mod 256)
STAT_BASE + $03 : STAT_TICK       (1 byte)   ; scheduler tick counter
```

`STAT_ALIVE_MARKER = $5A` is exported as a named constant so the 68k boot check and the Z80
init use the same value (build-time agreement, not a magic number duplicated in two files).

---

## 5. Verified-write protocol (68k side)

Per the parent spec §4.1, every 68k write to the mailbox is **read-back-and-retried** to survive
bus contention (notably during 68k→VDP DMA). The protocol, in order:

1. **Hold the Z80 bus** for the duration of the record write (`stopZ80` / bus-request), so the
   driver cannot latch a half-written record and the read-back reads true RAM (mirrors Echo's
   `Z80Request`/`Z80Release`). Release after the commit byte is verified.
2. For each **argument** byte (`MBX_ARG0`, `MBX_ARG1`) and `MBX_CMD`:
   write it, read it back, retry on mismatch:
   ```
   .retry: move.b  d0, (a1)        ; write byte
           cmp.b   (a1), d0        ; read back, compare
           bne.s   .retry          ; mismatch -> rewrite (~8 cycles/byte)
   ```
3. **Only after all args + cmd verify**, write and verify `MBX_PENDING` (the commit) the same way.
   This is the last write — the record is now live for the Z80.

`MBX_PENDING` is committed **after** the args specifically so that the verified-write retries on
the args cannot leave a "pending" flag standing over an unverified argument.

(Holding the Z80 bus already prevents the driver from observing a torn write; the read-back is the
second line of defence against the write itself being dropped/corrupted on the bus. Both are kept
because the parent spec mandates verified writes and the cost is negligible — a few cycles per
byte, a handful of times per frame.)

---

## 6. Atomicity rule

**The 68k must not write a new command while `MBX_PENDING != 0`.**

Phase-1 test-harness policy: **wait-then-write.** Before posting, the 68k polls `MBX_PENDING`
until it reads `0` (Z80 has consumed the previous command and cleared it), then performs the
verified write of §5. Optionally it also snapshots `STAT_ACK_COUNT` and waits for it to change
to positively confirm consumption.

This is the minimal correct discipline (Echo busy-waits on its slot byte the same way). The full
API (§12.x #1) may later relax this with a multi-slot queue or "last-write-wins" semantics for
fire-and-forget SFX, but Phase 1 needs only one in-flight command at a time, so the single-record
wait-then-write rule is sufficient and trivially verifiable on hardware/Exodus.

---

## 7. Lifecycle (one command, end to end)

```
68k                                            Z80 driver (per scheduler pass)
---                                            ------------------------------
(at boot) kick Z80, poll STAT_ALIVE == $5A     init -> STAT_ALIVE = $5A; enter main loop
wait MBX_PENDING == 0                           each pass: if MBX_PENDING != 0:
[hold Z80 bus]                                      cmd = MBX_CMD; a0 = MBX_ARG0; a1 = MBX_ARG1
write+verify MBX_ARG0, MBX_ARG1, MBX_CMD           dispatch by cmd (jump table):
write+verify MBX_PENDING = 1   <-- commit             PING -> STAT_PING_ECHO = a0
[release Z80 bus]                                     PLAY_SAMPLE -> start DAC of sample a0
wait STAT_ACK_COUNT change (or MBX_PENDING == 0)   STAT_ACK_COUNT++
read STAT_PING_ECHO / observe sample playing       MBX_PENDING = 0   <-- consume-ack
```

---

## 8. Constants summary (for `sound_constants.asm`, Task 3)

```
; --- Mailbox record offsets (relative to MBX_BASE) ---
MBX_CMD          = $00      ; command id byte
MBX_ARG0         = $01      ; argument 0
MBX_ARG1         = $02      ; argument 1
MBX_PENDING      = $03      ; commit/handshake: 0 idle, nonzero pending (written last)
MBX_LEN          = $04      ; record size in bytes

; --- Command IDs ---
SND_CMD_NONE        = 0     ; idle / no-op
SND_CMD_PING        = 1     ; arg0 -> STAT_PING_ECHO
SND_CMD_PLAY_SAMPLE = 2     ; arg0 = sample index
SND_CMD_COUNT       = 3     ; dispatch bounds-check

; --- Status / ack region offsets (relative to STAT_BASE) ---
STAT_ALIVE        = $00     ; $5A when driver running
STAT_PING_ECHO    = $01     ; arg0 of last PING
STAT_ACK_COUNT    = $02     ; ++ per command consumed (mod 256)
STAT_TICK         = $03     ; scheduler tick counter
STAT_LEN          = $04     ; status block size in bytes

; --- Markers ---
STAT_ALIVE_MARKER = $5A     ; liveness sentinel (non-zero, non-$FF)
MBX_PENDING_SET   = 1       ; value the 68k writes to commit a command
```

`MBX_BASE` and `STAT_BASE` themselves are **not** fixed here — they are assigned by the Z80 RAM
memory-map sub-design (§12.x #2). Only the intra-block offsets and the IDs/markers are frozen by
this contract.

---

## 9. Deviations from the target layout

**None.** The target layout handed down in the task (MBX_CMD/ARG0/ARG1/PENDING at +$00..+$03 with
PENDING written last; IDs NONE=0/PING=1/PLAY_SAMPLE=2; status ALIVE=$5A/PING_ECHO/ACK_COUNT/TICK;
verified writes; wait-then-write atomicity) is **validated by the research and adopted unchanged.**
It is essentially Echo's proven flag-byte-last mailbox (`src-68k/echo.68k`) plus Batman/Zyrinx
verified writes plus a Mega-PCM-style status block — i.e. the union of the references' handoff
techniques, which is exactly what the parent spec aims for.

Two **clarifications** (not deviations) for the implementer:
- `STAT_ACK_COUNT` and `STAT_TICK` are defined mod-256 (single byte wrap is fine; the 68k watches
  for *change*, not absolute value).
- Holding the Z80 bus during the verified write is recommended (Echo precedent) in addition to the
  read-back; together they cover both torn-read and dropped-write failure modes.
