# Sound Plan 1C Design — Minimal FM + PSG Music Sequencer

**Date:** 2026-06-17
**Status:** Design approved (2026-06-17), ready for plan
**Branch:** `feat/sound-1c` (to be created)
**Extends:** master sound spec `2026-06-16-sound-driver-design.md` (§6 FM/PSG, §8 tempo, §10
data format, §12 phasing). Builds on **1B** (DMA-survival DAC, merged to master) and **1A
Foundations** (Z80 shell, mailbox, Timer-A scheduler primitives).

## 1. Goal

**Hear a short multi-channel song play and loop cleanly** — a few FM melodic voices + PSG
tone/noise + DAC drums (reusing the 1B DAC) — driven by a hand-authored test song in a compact
event-list format. This validates the *entire* music pipeline (format → sequencer → FM/PSG
hardware → coexistence with the continuous DAC) on the smallest footprint, so depth can be
layered on safely afterward.

## 2. Scope

**In 1C:**
- A draft runtime **event-list music format (v0)** — compact, Z80-fast, versioned/extensible.
- A **minimal FM sequencer** (note on/off, duration, patch select, channel volume) for FM1–FM5.
- **Basic PSG** (3 tone + 1 noise) driven by the same sequencer, with pause silencing.
- A **minimal FM patch/instrument format** + ROM patch table.
- The two **cheapest quality wins** from the master spec: log-volume LUT + per-algorithm
  carrier mask (so volume is perceptual and preserves timbre).
- `PlayMusic(song_id)` / `StopMusic` on the existing 1A mailbox.
- A **hand-authored test song** + a tiny Python authoring helper.
- **Coexistence with the 1B DAC** (FM6 stays the DAC channel; drums play through it).

**Explicitly deferred (own later plans):**
- FM *depth* — dual data streams, true portamento, SSG-EG, LFO, Ch3 special, detune-unison
  (master spec **Phase 3**).
- N-channel DAC mixer, BRR, stereo PCM (**Phase 2**).
- Adaptive FM6/DAC slot (**Phase 4**) — 1C keeps FM6 permanently the DAC (the simple model).
- Section-aware banking, fades, ambient, distance attenuation (**Phase 5**).
- MegaDAW export retarget (**Phase 6**) — 1C hand-authors the test song; MegaDAW integration and
  real song-sourcing are downstream/user-driven (engine defines the format contract first).

## 3. Architecture

Five units with clear interfaces:

1. **Event-list format (layout/contract)** — the on-ROM song bytes. §4.
2. **Sequencer core (Z80)** — per-channel stream interpreters; advances on each tempo sub-tick;
   emits note/patch/volume → hardware writes. §5.
3. **FM voice writer (Z80)** — note→F-number, key-on/off, patch load, log-volume×carrier-mask. §6.
4. **PSG voice writer (Z80)** — note→PSG frequency, volume, noise. §7.
5. **Scheduler integration** — how the sequencer sub-tick interleaves with the free-running 1B
   DAC loop without starving it. §8 (the one genuinely tricky part).

Plus the **patch table** (ROM, §6) and the **command API** (§9).

## 4. Runtime event-list format (draft v0)

Per-channel byte streams, **SMPS-family layout** (proven, entropy-efficient, single-byte
dispatch). A song in ROM:

**Tempo model (unambiguous):** YM Timer-A is programmed so **one overflow = one sequencer
"tick."** Note durations are counted in ticks. The song header tempo byte maps to the Timer-A
reload N = tempo<<2; period = 18.773µs·(1024−N), so a BIGGER tempo byte → bigger N → SHORTER
period → FASTER song. Because Timer-A is sub-frame and NTSC/PAL-independent,
tempo is frame-rate-independent (master spec §8). 1B does **not** use Timer-A (its DAC loop is
free-running), so Timer-A is free for tempo here.

```
SongHeader:
  db   tempo                ; Timer-A reload selector (N = tempo<<2); bigger = faster
  db   channel_count
  ; per channel: routing byte + stream pointer (2 bytes, Z80 window-relative)
  rept channel_count
    db   channel_route       ; FM1..FM5 / PSG1..3 / PSGN / DAC  (enum)
    dw   stream_ptr
  endm
  dw   patch_table_ptr       ; FM patch table for this song
```

**Channel stream opcodes** (one byte + operands; ranges chosen for cheap range-dispatch):
| Byte | Meaning |
|---|---|
| `$00–$7F` | **Set default duration** = value (in tempo ticks) for following notes |
| `$80` | **Rest** for the current default duration (key-off, advance time) |
| `$81–$DF` | **Note** — pitch index `byte-$81` into the F-number table; key-on at current duration |
| `$E0 vv` | Set channel **volume** `vv` (linear 0–127; log-curve applied at write) |
| `$E1 pp` | Set FM **patch** index `pp` (FM channels only) |
| `$E2 ss` | **DAC trigger** sample id `ss` (DAC channel only → posts to the 1B DAC path) |
| `$E3 nn dd` | **Note with explicit duration** — pitch `nn`, duration `dd` (overrides default) |
| `$EE` | **Loop point** marker (jump target for `$EF`) |
| `$EF` | **Jump to loop point** (song/section loop) |
| `$FF` | **End of stream** (channel idle) |

v0 stays at this set. Future opcodes (portamento, pan, modulation, patch-tweak) slot into the
`$E4–$ED`/`$F0–$FE` space without breaking v0 — the dispatch is a jump table, so unknown
opcodes are a build-time validation error, never silent.

**Pitch / F-number table:** a build-generated table mapping semitone index → YM2612 F-number +
block (and → PSG 10-bit divisor for PSG channels). Equal-tempered, generated at build by a
`function`/Python helper so it's compile-time-correct, not hand-typed.

## 5. Sequencer core

**Per-channel state** (Z80 RAM struct, ~8 bytes each): `stream_ptr` (2), `duration_counter` (1),
`default_duration` (1), `cur_patch` (1), `cur_volume` (1), `cur_note` (1), `flags` (1, e.g.
active/keyed). Channel-count × struct sized into the §11 RAM budget.

**Per tick** (`Sequencer_Tick`, fired once per Timer-A overflow): for each active channel —
1. `duration_counter--`; if still > 0, continue (held note evolves, no work).
2. On expiry: read the next opcode(s) from `stream_ptr`, dispatch via jump table, execute
   (set duration / key-off+rest / key-on note / set vol / set patch / DAC trigger / loop / end),
   advance `stream_ptr`, reload `duration_counter`.

This is the classic SMPS tick loop, kept deliberately small. Note-on for FM = §6; PSG = §7.

## 6. FM voice writer + patch format

**Patch (instrument) format** — a ~25–29 byte ROM record holding the YM2612 per-channel FM
registers: algorithm+feedback (`$B0`), L/R+AMS/FMS (`$B4`), and the four operators' `DT/MUL`
(`$30`), `TL` (`$40`), `RS/AR` (`$50`), `AM/D1R` (`$60`), `D2R` (`$70`), `D1L/RR` (`$80`).
`Patch_Load(channel, patch_ptr)` writes them via the YM write-discipline (busy-poll before each
register-pair write — the FM hazard the master spec §5 flags; the DAC `$2A` path does not need
it, FM does).

**Note-on:** look up pitch → F-number+block, write `$A4+ch`/`$A0+ch`, then key-on (`$28`,
operator mask = all on). **Note-off / rest:** key-off (`$28`, mask = 0).

**Volume** = `log_lut[linear_vol]` applied **only to carrier operators' TL** (per the
**per-algorithm carrier mask**, an 8-byte table: algo→carrier-op bitmask). This preserves the
patch timbre (modulators untouched) — the master spec's "single easiest quality win." Both the
256-byte log LUT and the carrier-mask table are build-generated.

## 7. PSG voice writer

SN76489, written from the Z80 at `$7F11` (the Z80's PSG port). Note-on: pitch → 10-bit divisor,
latch+data (`$8x`/data for tone ch; `$Ex`/`$Fx` for noise). Volume: `$9x|attenuation` (the PSG
attenuation is already log-ish; map linear→attenuation via a small table). **Pause silencing:**
on `StopMusic`, write `$9F,$BF,$DF,$FF` so PSG tones don't sustain.

## 8. Scheduler integration (the tricky part)

The 1B DAC loop is **free-running** (its trip-time is the DAC sample clock, ~9.5 kHz). The
sequencer must run at the **tempo tick** rate (a few hundred Hz). Approach (the master spec's
cooperative model):

- Program **YM Timer-A** so one overflow = one tick (the tempo; NTSC/PAL-independent — §8).
- The DAC loop **polls the Timer-A overflow flag once per pass** (cheap: `ld a,($4000); bit`),
  in addition to outputting its ring byte. On overflow it re-arms the timer and calls
  `Sequencer_Tick`, then resumes outputting.
- `Sequencer_Tick` is **bounded and, if needed, split across ticks** (service half the FM
  channels per tick — master spec §4.2) so no single tick starves the DAC for long.
- The DAC sample that absorbs a tick is momentarily longer (a periodic micro-perturbation at the
  tick rate). This is exactly how Batman/SMPS interleave DAC + FM on one Z80; it's bounded
  and inaudible in practice. **Risk to validate first** (§10): VGM-confirm the DAC `$2A` cadence
  stays acceptable while the sequencer runs.

FM6 stays the DAC (1B). Sequencer FM writes target FM1–FM5; the DAC channel's stream only ever
emits `$E2` DAC triggers (routed to the 1B sample path), never FM note-ons.

### 8.1 Song-data banking decision (RESOLVED, Task 6)

**Decision — copy-to-RAM.** At `PlayMusic` time, inside the VBlank-ISR mailbox handler
(`Snd_LoadSong`, where the free-running DAC loop is paused), the loader saves the DAC bank, banks
in the song, copies the header + channel streams (a fixed `SND_SONG_BUF_SIZE` = 512 B) into a Z80
RAM buffer (`SND_SONG_BUF` at `$1B00`), then restores the DAC bank. The sequencer afterward reads
streams from RAM — **zero banking during playback** — so the free-running 1B DAC keeps its `$6000`
bank latch uninterrupted. DAC drum samples (`$E2`) re-bank to their own sample bank independently;
that is fine, because the song streams are already in RAM and never need the bank.

**Why (reference validation).** A full reference sweep found:
- **Live-read-in-ISR** (S2 / S3K / Flamedriver / sonic_hack) — read the stream straight from ROM
  in the music ISR. This is exactly what we **reject**: a live ROM read mid-playback would have to
  bank-switch the `$6000` latch out from under the free-running DAC, glitching it.
- **Re-bank-per-access live** (Echo / XGM2) — same banking-during-playback hazard.
- **Music on the 68k** (Ristar) — not applicable; our music is Z80-resident.
- **Dedicated sound-bank region** (Batman / Zyrinx) — a single fixed all-sound bank; less flexible
  (the MD has only one Z80 bank latch at `$6000`, so true dual-banking is impossible).
- **Copy-to-RAM / buffering** — directly precedented by TmEE's shipping driver (per-pattern ~2 KB
  buffering) and MegaPCM 2 (buffering for clean DAC). This is the model best matched to our
  constraint: a glitch-free, free-running DAC that owns the bank latch.

**Documented fallback.** If song streams ever exceed the Z80 RAM budget (the 512 B buffer), switch
to **TmEE-style per-pattern chunked buffering**: refill a smaller buffer periodically, each refill
performed in a DAC-paused window (same ISR-mailbox safety property), trading a little extra refill
bookkeeping for a smaller RAM footprint. The safety invariant (no banking while the DAC runs) is
unchanged.

**Build safety.** The fixed 512 B copy `ldir`s from the song's `$8000`-window pointer; a build
assert in `data/sound/song_table.asm` forbids placing a song so its window region crosses the
`$8000`-window top into Z80 RAM (else the source pointer would wrap past `$FFFF`). The copy may
read slightly past the song into adjacent ROM — harmless, since streams self-terminate.

## 9. 68k↔Z80 command API

Extends the 1A per-type mailbox slots:
- `SND_REQ_MUSIC` (already reserved at `$1F02`): the 68k posts a **song id**; the Z80 mailbox
  poll loads the song header, points each channel's `stream_ptr`, loads initial patches, starts
  the sequencer. `0` = stop (silence FM key-offs + PSG pause-silence).
- 68k helper `Sound_PlayMusic(d0=song_id)` / `Sound_StopMusic` (bus-held post, per 1A).
- Song id → `SongHeader` ptr via a ROM **song table** (bank-aware, reusing 1B's `SetBank`).

## 10. Verification

- Build → **Exodus (MCP)** → hear the test song loop. (Per user 2026-06-17 we test in Exodus;
  ignore the known DAC-contention "blips" — the driver is clean, verified on BlastEm in 1B.)
- **VGM-capture** while music plays: confirm FM register writes (`$A0–$B6`, `$28`) and PSG and
  DAC `$2A` all appear with sane structure; confirm the DAC cadence stays acceptable through the
  sub-tick service (the §8 risk).
- **DEBUG self-test:** sequencer advances all channels to end/loop without desync; patch loads
  hit the right registers (spot-check via Exodus YM state / VGM).
- Tempo correctness: a known-BPM test song's loop length matches expectation (Timer-A math).

## 11. Z80 RAM budget (addition to the 1A/1B map)

Add to the Z80 RAM map: per-channel sequencer structs (channel_count × ~8 B), the song's loaded
header/pointers, and small scratch. Must fit alongside the 1B 256-byte ring + state in the 8 KB
budget; the §12.2 RAM-map sub-design is updated as part of the plan's first task.

**RESOLVED (Task 2).** The sequencer region lives at **`$1800`**, in the FREE block ABOVE the
1B DAC ring (`$1700–$17FF`) — NOT below it. (The plan's illustrative guard
`if SND_SEQ_END > SND_RING_BASE` was wrong; the sequencer is above the ring.) Layout:

| Z80 range | Region | Constant | Notes |
|---|---|---|---|
| `$1800–$1807` | Sequencer header | `SND_SEQ_BASE` | `+0` tempo, `+1` chcount, `+2/3` patch-table ptr, `+4` active, `+5` bad-opcode marker (DEBUG), `+6` trace write index, `+7` unused |
| `$1808–$1875` | Per-channel `SeqChannel` array | `SND_SEQ_CHANNELS` | `CHROUTE_COUNT`(10) × `SeqChannel_len`(11) = 110 B → ends `$1876` |
| `$1A00–$1A1F` | Trace ring (DEBUG) | `SND_SEQ_TRACE` | 32 bytes, page-aligned; each = `(sc_route<<4) | event_code` |

`SeqChannel` is **11 bytes** (NOT padded to 16): `(ix+d)` indexed access is displacement-cost-
independent and the tick loop advances by `add ix,SeqChannel_len` (size added, never multiplied
by an index), so power-of-two padding buys nothing. `SND_SEQ_END` is guarded `< SND_REQ_BASE`
(`$1F00`, the mailbox base) and `<= SND_SEQ_TRACE` (`$1A00`) at build time. The trace ring's end
is also guarded `< SND_REQ_BASE`. `$1876–$19FF` and `$1A20–$1EFF` remain free for later tasks.

**Event-code values** (low nibble of each trace byte): `SEQEV_NOTEON=1, SEQEV_NOTEOFF=2,
SEQEV_VOL=3, SEQEV_PATCH=4, SEQEV_DAC=5, SEQEV_LOOP=6, SEQEV_JUMP=7, SEQEV_END=8`. The high nibble
is the channel's `CHROUTE_*` route, so the controller can decode which channel fired which event.

**DEBUG mirror (Task 2):** `Sound_Dbg_Mirror` widened 64→128 B. Upper half:
`[64..71]` sequencer header, `[72..82]` channel 0 (FM1), `[83..93]` channel 1 (PSG1),
`[94..125]` trace ring. (`SND_SEQ_ACTIVE` → mirror `[68]`, `SND_SEQ_TRACE_WR` → `[70]`, each
channel `sc_flags` at its base `+7`, `sc_stream_ptr` at `+0/+1`.)

## 12. Decomposition (task order for the plan)

1. **Format + tables (build-time):** event-list opcode constants, F-number/PSG-divisor table
   generator, log-volume LUT, carrier-mask table, a hand-authored test song + Python packer.
2. **Sequencer core (RAM-only dry run):** per-channel structs, the tick loop, jump-table
   dispatch — first driven by a stubbed "write" that just logs, to verify stream walking.
3. **FM voice writer + patch load:** wire note-on/off + patch + log-volume×carrier-mask to real
   YM registers; one FM channel audible.
4. **PSG voice writer:** PSG channels audible; pause silencing.
5. **Scheduler integration:** Timer-A sub-tick poll in the DAC loop + `Sequencer_Tick`; verify
   DAC cadence via VGM (the §8 risk) — the integration milestone.
6. **Command API + DAC drums:** `PlayMusic`/`StopMusic`; route `$E2` to the 1B DAC; the full
   test song (FM + PSG + drums) plays and loops.

Each task: research the relevant references first (SMPS/Echo/Flamedriver/Batman sequencer +
format + the specific YM/PSG write discipline) per the project's per-task research rule, then
build + Exodus-verify + commit.

## 13. Open items / risks

- **Sub-tick service vs DAC cadence** (§8) — the integration risk; validate at task 5 with VGM
  before building the full song on top.
- **YM busy-poll cost** inside the bounded tick — confirm the FM register-pair writes + busy-poll
  fit the per-tick budget without overrunning the next DAC sample badly.
- **F-number table accuracy** — verify pitch against a reference (a known note's measured
  frequency) so the whole tuning isn't off.
- v0 format is deliberately minimal; we accept it will gain opcodes in Phase 3 (designed for it).
