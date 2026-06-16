# Sub-Design — Z80 RAM Memory Map (Phase 1)

**Date:** 2026-06-16
**Status:** Layout approved for Phase 1 — fixes the absolute addresses every later sound task builds on
**Branch:** `design/sound-driver`
**Parent spec:** `docs/superpowers/specs/2026-06-16-sound-driver-design.md` (§3 "Z80 RAM is 8 KB", §5 read-ahead buffer, §12.x #2 Z80-RAM-map sub-design)
**Sibling spec:** `docs/superpowers/specs/2026-06-16-sound-command-api.md` — defines the mailbox/status *offsets* (`MBX_CMD`..`MBX_PENDING`, `STAT_ALIVE`..`STAT_TICK`) and deliberately left the *absolute bases* (`MBX_BASE`, `STAT_BASE`) to **this** doc. This doc fixes those bases.
**Consumed by:** Task 3 transcribes the addresses/constants below into `sound_constants.asm`. They are exact and self-consistent with the sibling command-API contract.

The Z80 sees 8 KB of RAM as **Z80-space `$0000–$1FFF`** (mapped at 68k bus address `$A00000–$A01FFF`). This doc budgets all 8 KB so later Phase-1/1B tasks place code and data without collision, and reserves room *now* for the Plan 1B read-ahead buffer so nothing has to move later.

---

## 1. Research findings

Surveyed how each reference driver lays out its 8 KB Z80 RAM — specifically: where code sits,
where the stack lives, where the command mailbox / state lives, and how large the DAC
read-ahead / DMA-survival buffer is. Sources read in full are cited inline.

### Reference comparison — 8 KB Z80 RAM layout

| Driver | Code region | Stack top (SP init) | Mailbox / state location | DAC read-ahead / DMA buffer |
|---|---|---|---|---|
| **Batman & Robin** (Jesper Kyd) | `$0000–$1824` (code **and** all data/tables interleaved in one blob: F-num tables `$0F00–$13FF`, vol table `$1400`, 6× channel structs `$1480–$16D3`) | **`$1FFE`** (`ld sp,$1FFE` at init) | DAC live vars `$00EB–$00F5`; DAC request staging `$16E0–$16F4` + flag `$16F4`; 6× channel-start records `$17EA–$1822`; inferred 68k heartbeat readback at `$1810+` | **None.** Cooperative Timer-B coroutine feeds DAC byte-by-byte straight from ROM and is *immune to DMA* because it never waits on the 68k bus — but it has **no buffer**, so it cannot mix and cannot pre-fetch. |
| **Flamedriver / SMPS** (S.C.E.) | `$0000–$1C19` (driver code; `Size_of_Snd_driver_guess = $1200` headroom budget) | **`$2000`** (top of RAM; `ld sp, z80_stack`, with `z80_stack_top: ds.b $60` → **96-byte** stack) | RAM vars `phase`'d at `zDataStart = $1C1A`: queue bytes `zMusicNumber`/`zSFXNumber0/1`, then 10× music `zTrack` + 7× SFX `zTrack` + 10× save `zTrack` (track structs overlap save area). | **None** (classic single-channel DAC reads ROM directly; scratches under DMA — the problem this engine fixes). |
| **Gunstar Heroes** (Treasure) | low RAM | **`$1FF4`** (`ld sp,$1FF4`) | SMPS-style queue bytes near top of RAM (`$1FF7`, `$1FFA/B`, `$1FFE`) | None |
| **Alien Soldier** (Treasure) | low RAM | **`$1FE6`** init (then re-pointed per phase) | queue bytes high in RAM | None |
| **Thunder Force IV** (Technosoft) | low RAM | **`$2000`** (top) | queue bytes high in RAM | None |
| **Mega PCM 2.1** (vladikcomper) | code low | top of RAM | single `CommandInput` byte + status-output byte | **256-byte ring buffer, aligned to a 256-byte page** — the load-bearing read-ahead. Page alignment lets the Z80 advance the pointer by **incrementing only the low byte** (free wrap, no compare). Filled in batches (**32 or 30 bytes** per batch depending on mix mode); drained during DMA; a **minimum-fill threshold** (MDSDRV: ~40 bytes) guards against underrun. This is what makes Mega PCM "DMA-proof." |
| **MDSDRV** (superctr) | code low | top of RAM | command bytes | **Ring buffer up to 256 bytes** (configurable 40–220 used in practice; 100 bytes recommended for 2-ch mix), page-organised, 32/30-byte batch fills, 40-byte underrun threshold; 68k acks DMA via a flag each VBlank. |
| **DualPCM** (Sonic 1, Natsumi/AuroraField) | code low | top | queue bytes | **Double-buffer (ping-pong)**: two sample buffers; Z80 plays one while the other is refilled — the classic alternative to a ring. |

### What the survey establishes

1. **Code at the bottom, stack at the very top, growing down — universal.** Every driver
   `org`s code at `$0000` and sets `SP` at or just below `$2000`. Batman `$1FFE`, Gunstar
   `$1FF4`, Flamedriver/TF4 `$2000`. We adopt **`$1FFE`** (Batman's value; one word below the
   top so the first `push` lands at `$1FFC`). The sibling/task already specified `$1FFE`.

2. **Mailbox/state lives high, just under the stack — common.** Gunstar (`$1FF7+`), Batman's
   staging/channel records (`$16E0+`/`$17EA+`), Flamedriver's queue at the top of its var
   block. Putting the 68k-visible mailbox/status near the top keeps it clear of growing code
   and gives both blocks fixed, easily-memorised 68k addresses. We place mailbox + status at
   **`$1F00`** (high RAM), matching the sibling command-API target.

3. **The read-ahead buffer is the one thing the legends lack and Mega PCM nails.** None of
   the four commercial blobs nor stock Flamedriver buffers the DAC — they read ROM directly
   and either dodge DMA via a coroutine (Batman) or simply scratch (SMPS). Mega PCM 2 /
   MDSDRV / DualPCM are the modern answer, and the **256-byte page-aligned ring** is the
   canonical form: page alignment makes pointer advance a single `inc l`, batches of ~32
   bytes amortise the fill, and a small minimum-fill threshold prevents underrun during the
   worst-case 68k→VDP DMA freeze. Our parent spec §5 mandates exactly this. We therefore
   **reserve a 256-byte-aligned, 256-byte-capacity window now** (Plan 1B), even though
   Foundations doesn't fill it — so 1B never has to move code or restructure RAM.

4. **8 KB is genuinely tight, so reserve before you need it.** Flamedriver guesses `$1200`
   for code and *still* guards the fit with a build-time `fatal`; its data block runs right
   up to `$2000`. We pre-carve the read-ahead window, the per-channel state, and the test
   sample now, leaving driver code a generous but **bounded** `$0000–$15FF` (5.5 KB) — and
   assert that bound at build time (§5).

5. **"High RAM" convention.** The region `$1F00–$1FFF` (the top page) is, by community
   convention and by every reference above, where small 68k-visible records and the stack
   live. We honour it: status/mailbox at `$1F00–$1F3F`, stack descending from `$1FFE`. The
   ~`$1F40–$1FFB` gap between the status block and the stack is intentional slack (stack
   growth headroom + future small flags) and is documented as RESERVED.

**Sources:**
- `docs/research/z80_blobs/batman_driver_analysis.md` §1 (memory map: code/tables `$0000–$1824`,
  channel structs `$1480`, DAC staging `$16E0–$16F4`, mailbox `$17EA`), §2 (`ld sp,$1FFE`),
  §3 (DAC live vars `$00EB–$00F5`), §10 ("immune to 68k DMA stalls… never waits on the 68k").
- `docs/research/z80_blobs/{gunstar,alien,tf4}_z80.lst` — `ld sp,$1FF4` / `$1FE6` / `$2000`
  and queue bytes near the top of RAM.
- S.C.E. Flamedriver `Sound/Flamedriver.asm`: `Size_of_Snd_driver_guess = $1200` (line 26);
  `zDataStart = $1C1A` + `phase` (line 277–278); `z80_stack_top: ds.b $60` 96-byte stack
  (line 279); `ld sp, z80_stack` "end of z80 RAM" (line 811); build-time fit guards
  `if * > $2000 / fatal` (line 4759-ish) and `if $ > z80_stack_top / fatal` (line 4758).
- Mega PCM 2.1 (vladikcomper) README/Troubleshooting + MDSDRV `doc/dma.md` (superctr):
  PCM ring buffer **max 256 bytes**, **aligned to a 256-byte page** (advance = low-byte
  increment), **32/30-byte batch** fills, **~40-byte minimum-fill threshold**, DMA-protection
  via a 68k VBlank ack flag. https://github.com/vladikcomper/MegaPCM ,
  https://github.com/superctr/MDSDRV/blob/master/doc/dma.md
- DualPCM / Sonic-driver survey (Clownacy, "The Sound Drivers of Sonic the Hedgehog";
  s1disasm DualPCM PR #33) — double-buffer (ping-pong) DAC model, 8 KB RAM constraint,
  samples stored in ROM banks not in the driver.

---

## 2. The 8 KB budget (Z80-space `$0000–$1FFF`)

All regions are **non-overlapping**. Addresses are Z80-space; add `$A00000` for the 68k bus
address (e.g. mailbox `MBX_BASE` = Z80 `$1F00` = 68k `$A01F00`).

| Z80 range | 68k range | Size | Region | Constant | Phase | Notes |
|---|---|---|---|---|---|---|
| `$0000–$15FF` | `$A00000–$A015FF` | 5632 B (5.5 KB) | **Driver code + code-local tables** | `Z80_CODE_BASE = $0000` | 1 | `phase 0`. Holds the scheduler, DAC feed, mailbox poll, FM/PSG sequencer, YM write-queue, and build-time tables (log-vol LUT, carrier mask, F-num tables). End-of-code asserted `< Z80_STATE_BASE` (§5). |
| `$1600–$16FF` | `$A01600–$A016FF` | 256 B | **Per-channel / playback state** | `Z80_STATE_BASE = $1600` | 1 | Sample ptr, remaining length, rate/pitch, loop ptr/len, active flags, per-channel scheduler scratch, ack/tick mirrors. Sized generously for the Phase-2/3 channel structs (Batman's 6× struct = 618 B lives in *code* space; our live playback state here is far smaller — 256 B is ample for Phase 1's single DAC channel + headroom). |
| `$1700–$17FF` | `$A01700–$A017FF` | 256 B | **RESERVED — read-ahead ring buffer (Plan 1B)** | `Z80_PCM_BUF_BASE = $1700` `Z80_PCM_BUF_LEN = $0100` | 1B | **256-byte ring, 256-byte-page-aligned** (Mega-PCM/MDSDRV model): `$1700–$17FF` so pointer advance is a single low-byte `inc`. **Unused in Foundations** (the Phase-1 DAC reads ROM directly via Batman's coroutine); reserved now so 1B drops in without moving anything. |
| `$1800–$1BFF` | `$A01800–$A01BFF` | 1024 B | **RESERVED — read-ahead growth / future buffers** | `Z80_BUF_RESERVE_BASE = $1800` | 1B+ | Slack for a *larger* ring (mixing N voices may want >256 B total across channels), a second ping-pong half (DualPCM model), or echo/delay line (parent §"Stretch"). Keeps the 1B/Phase-2 buffer decision open without re-budgeting. |
| `$1C00–$1DFF` | `$A01C00–$A01DFF` | 512 B | **Embedded test sample (Foundations only)** | `Z80_TEST_SAMPLE_BASE = $1C00` `Z80_TEST_SAMPLE_LEN = $0200` | 1 | A short DAC sample baked into Z80 RAM so Phase 1 can play a sound **without ROM banking** (banking lands in Plan 1B/Phase 2). **Removed** when ROM-banking lands; the region then reverts to buffer growth (`$1800–$1DFF` becomes one contiguous reserve). |
| `$1E00–$1EFF` | `$A01E00–$A01EFF` | 256 B | **RESERVED — spare** | `Z80_SPARE_BASE = $1E00` | — | Unallocated headroom between the test sample and the high-RAM record page. Absorbs growth of either neighbour without disturbing the fixed high-RAM addresses below. |
| `$1F00–$1F0F` | `$A01F00–$A01F0F` | 16 B | **Mailbox record (68k→Z80)** | `MBX_BASE = $1F00` | 1 | Command record from the sibling contract: `MBX_CMD`+$00, `MBX_ARG0`+$01, `MBX_ARG1`+$02, `MBX_PENDING`+$03 (record is 4 B; rest of the 16 B is reserved for the full-API record growth — extra args / second staging record per command-API §1). |
| `$1F10–$1F3F` | `$A01F10–$A01F3F` | 48 B | **Status / ack region (Z80→68k)** | `STAT_BASE = $1F10` | 1 | Status block from the sibling contract: `STAT_ALIVE`+$00, `STAT_PING_ECHO`+$01, `STAT_ACK_COUNT`+$02, `STAT_TICK`+$03 (block is 4 B; remainder reserved for full-API status growth — per-channel playing flags, fade state, etc.). |
| `$1F40–$1FFB` | `$A01F40–$A01FFB` | 188 B | **RESERVED — stack growth headroom / misc flags** | `Z80_HIRAM_RESERVE_BASE = $1F40` | — | Intentional slack between the status block and the stack. Stack descends into the top of this; also holds any tiny future high-RAM flags. |
| `$1FFC–$1FFF` | `$A01FFC–$A01FFF` | 4 B | **Stack (top word)** | `Z80_STACK_TOP = $1FFE` | 1 | `ld sp, $1FFE` at init (Batman's value). Stack **grows downward** from here into the `$1F40–$1FFB` reserve. First `push` writes `$1FFC/$1FFD`. |

### Compact map (for quick reference)

```
$0000 ┌──────────────────────────────────────┐
      │ DRIVER CODE  (phase 0)               │  5632 B  Phase 1
      │   scheduler / DAC feed / mailbox     │
      │   poll / FM-PSG seq / YM queue /     │
      │   LUTs (log vol, carrier mask, fnum) │
$15FF ├──────────────────────────────────────┤  <-- Z80_CODE_END asserted < $1600
$1600 │ PER-CHANNEL / PLAYBACK STATE         │   256 B  Phase 1
$1700 ├──────────────────────────────────────┤
      │ READ-AHEAD RING  (256B, page-aligned)│   256 B  RESERVED (Plan 1B)
$1800 ├──────────────────────────────────────┤
      │ BUFFER GROWTH RESERVE                 │  1024 B  RESERVED (1B+)
$1C00 ├──────────────────────────────────────┤
      │ EMBEDDED TEST SAMPLE                  │   512 B  Phase 1 only
$1E00 ├──────────────────────────────────────┤
      │ SPARE                                 │   256 B  RESERVED
$1F00 ├──────────────────────────────────────┤
      │ MAILBOX  MBX_BASE   ($1F00-$1F0F)    │    16 B  Phase 1 (4B used)
$1F10 │ STATUS   STAT_BASE  ($1F10-$1F3F)    │    48 B  Phase 1 (4B used)
$1F40 ├──────────────────────────────────────┤
      │ STACK GROWTH RESERVE / hi-ram flags   │   188 B
$1FFC │ STACK (grows down from $1FFE)        │     4 B  Z80_STACK_TOP=$1FFE
$1FFF └──────────────────────────────────────┘
```

---

## 3. Why these bases (rationale, tied to the sibling contract)

- **`MBX_BASE = $1F00`, `STAT_BASE = $1F10`** — fixes the two addresses the sibling command-API
  doc left open. Both sit in "high RAM" (every reference convention), are 16-byte-aligned for
  easy 68k address arithmetic, and give the mailbox record room (`$1F00–$1F0F`) to grow into the
  full-API layout (extra args / a second staging record, command-API §1) **without** colliding
  with the status block. The status block (`$1F10–$1F3F`, 48 B) likewise has slack for full-API
  per-channel status. The intra-block offsets (`MBX_CMD`=+$00 … `STAT_TICK`=+$03) come **verbatim**
  from the sibling contract — this doc only sets the bases.

- **Read-ahead at `$1700`, page-aligned, 256 B** — matches the Mega-PCM/MDSDRV canonical ring
  exactly so the Plan 1B implementation can use the single-`inc-l` pointer-advance trick. Placing
  it on a `$xx00` boundary is *required* for that trick, which is the whole reason to fix the
  address now rather than let it fall wherever code ends.

- **Code bound at `$15FF` (5.5 KB)** — Batman's entire code+tables blob is `$1824` (~6 KB) and
  Flamedriver budgets `$1200` for code alone. 5.5 KB is comfortably larger than either for the
  Phase-1 feature set (no full FM depth yet) while still leaving the bottom 2.5 KB for state +
  buffers + records. The bound is enforced, not hoped for (§5).

- **Embedded test sample at `$1C00`** — Foundations has no ROM banking, so the only place to put
  playable sample bytes is Z80 RAM. 512 B at `$1C00` is enough for a short drum hit / tone at a
  few kHz. It is explicitly temporary: when banking arrives the sample comes from ROM and this
  window merges into the buffer-growth reserve.

---

## 4. Constants summary (for `sound_constants.asm`, Task 3)

```
; --- Z80 RAM regions (Z80-space addresses; 68k = +$A00000) ---
Z80_CODE_BASE          = $0000   ; driver code (phase 0)
Z80_CODE_LIMIT         = $1600   ; code MUST end strictly below this (= Z80_STATE_BASE)

Z80_STATE_BASE         = $1600   ; per-channel / playback state
Z80_STATE_LEN          = $0100   ;   256 bytes

Z80_PCM_BUF_BASE       = $1700   ; read-ahead ring (RESERVED, Plan 1B) — page-aligned
Z80_PCM_BUF_LEN        = $0100   ;   256 bytes (one 256-byte page: advance via inc low byte)

Z80_BUF_RESERVE_BASE   = $1800   ; buffer growth / future buffers (RESERVED)
Z80_BUF_RESERVE_LEN    = $0400   ;   1024 bytes

Z80_TEST_SAMPLE_BASE   = $1C00   ; embedded test sample (Foundations only; removed w/ banking)
Z80_TEST_SAMPLE_LEN    = $0200   ;   512 bytes

Z80_SPARE_BASE         = $1E00   ; spare (RESERVED)
Z80_SPARE_LEN          = $0100   ;   256 bytes

; --- High-RAM records (bases for the sibling command-API offsets) ---
MBX_BASE               = $1F00   ; mailbox record base (MBX_CMD..MBX_PENDING at +$00..+$03)
STAT_BASE              = $1F10   ; status/ack region base (STAT_ALIVE..STAT_TICK at +$00..+$03)

Z80_HIRAM_RESERVE_BASE = $1F40   ; stack growth headroom / misc hi-ram flags (RESERVED)

; --- Stack ---
Z80_STACK_TOP          = $1FFE   ; ld sp, Z80_STACK_TOP  (grows downward)

; --- 68k-bus convenience (absolute Genesis addresses) ---
Z80_RAM_68K_BASE       = $A00000
MBX_BASE_68K           = Z80_RAM_68K_BASE+MBX_BASE   ; $A01F00
STAT_BASE_68K          = Z80_RAM_68K_BASE+STAT_BASE  ; $A01F10
```

(The intra-record offsets `MBX_CMD/ARG0/ARG1/PENDING` and `STAT_ALIVE/PING_ECHO/ACK_COUNT/TICK`,
plus `STAT_ALIVE_MARKER`/`MBX_PENDING_SET`/command IDs, come from the sibling command-API spec
§8 — not redefined here. This doc adds only the **bases** and the **region budget**.)

---

## 5. Build-time size-assertion strategy

The load-bearing invariant: **driver code must not grow into the state region.** The driver's
`phase 0` block ends with a size constant, asserted strictly below `Z80_STATE_BASE`. If code
ever crosses `$1600`, the build fails — mirroring Flamedriver's `if $ > z80_stack_top / fatal`
guard, but catching collision with *data* (the more likely failure for a growing driver) rather
than with the stack.

At the **end of the driver's code/table block** (after the last byte the assembler emits inside
`phase 0`):

```
; ---- end of driver code (still inside `phase Z80_CODE_BASE`) ----
Z80_CODE_END:                       ; first free byte after code+tables
    if Z80_CODE_END > Z80_CODE_LIMIT
        fatal "Z80 driver code overflows into state region by \{Z80_CODE_END-Z80_CODE_LIMIT}h bytes (limit Z80_CODE_LIMIT=\{Z80_CODE_LIMIT}h)"
    elseif MOMPASS=1
        message "Z80 driver code: \{Z80_CODE_END}h used, \{Z80_CODE_LIMIT-Z80_CODE_END}h free before state region"
    endif
    dephase                          ; leave phase 0
```

- `Z80_CODE_LIMIT` (`= $1600`) is defined **equal to** `Z80_STATE_BASE` so the two can never
  silently diverge — if the state base moves, the code limit moves with it.
- The check uses `>` (not `>=`): code may fill up to and including `$15FF`; `$1600` is the first
  byte that belongs to state.
- `MOMPASS=1` prints the headroom on the first AS pass so the build log always reports remaining
  free code space (Flamedriver does the same for its pre-stack free space).
- A **complementary** top-of-RAM guard belongs with the RAM-variable declarations (the state /
  reserve / record regions): `if <end-of-declarations> > Z80_STACK_TOP : fatal` — the same
  pattern Flamedriver uses (`if $ > z80_stack_top`). Since every region above is fixed-address
  and additive, this reduces to asserting `Z80_HIRAM_RESERVE_BASE < Z80_STACK_TOP` and
  `MBX_BASE/STAT_BASE` non-overlap, which hold by construction; the live guard is the code-growth
  one above.

---

## 6. Deviations from the target layout (with rationale)

The task's target layout is **adopted essentially unchanged**; all deviations are additive
(filling gaps the target left implicit) — no region in the target was moved or resized in a way
that breaks it.

| Target (task) | This doc | Reason |
|---|---|---|
| `$0000–$15FF` driver code | `$0000–$15FF` (`Z80_CODE_LIMIT=$1600`) | **Same.** |
| `$1600–$16FF` per-channel state | `$1600–$16FF` (`Z80_STATE_BASE`) | **Same.** |
| `$1700–$1BFF` RESERVED read-ahead ring | Split: `$1700–$17FF` = the **256-byte page-aligned ring** (`Z80_PCM_BUF_BASE`); `$1800–$1BFF` = buffer-**growth** reserve | **Refinement, not a move.** Research (Mega-PCM/MDSDRV) shows the canonical ring is exactly **256 bytes, page-aligned** so the pointer advances with a single `inc l`. The target's `$1700–$1BFF` (1.25 KB) is *larger* than one ring needs; I pin the actual ring to the page-aligned `$1700` page and keep the rest (`$1800–$1BFF`) as explicit growth reserve for N-voice mixing / a second ping-pong half / echo line. The whole `$1700–$1BFF` span stays reserved for buffering, as the target intended. |
| `$1C00–$1DFF` embedded test sample | `$1C00–$1DFF` (`Z80_TEST_SAMPLE_BASE`, 512 B) | **Same** address; I note its lifecycle (merges into buffer reserve when banking lands). |
| `$1F00–$1F0F` mailbox | `$1F00–$1F0F` (`MBX_BASE=$1F00`) | **Same.** Fixes the base the sibling contract left open. |
| `$1F10–$1F3F` status/ack | `$1F10–$1F3F` (`STAT_BASE=$1F10`) | **Same.** Fixes the base the sibling contract left open. |
| `$1FFE` stack top | `Z80_STACK_TOP=$1FFE` | **Same** (Batman's value). |
| (gap `$1E00–$1EFF` not named) | `Z80_SPARE_BASE` RESERVED | New: the target's regions leave `$1E00–$1EFF` and `$1F40–$1FFB` implicit. I name both as RESERVED slack so the build is fully accounted for and growth has somewhere to go without touching fixed addresses. |
| (assert "code end < state start") | `Z80_CODE_END > Z80_CODE_LIMIT` → `fatal`, with `Z80_CODE_LIMIT ≡ Z80_STATE_BASE` | Implements the target's build-time assertion strategy; ties the limit to the state base so they can't drift. |

**No conflicts** with the sibling command-API contract: this doc only assigns `MBX_BASE`/`STAT_BASE`
(which that contract explicitly deferred here) and leaves every offset/ID/marker it froze untouched.
