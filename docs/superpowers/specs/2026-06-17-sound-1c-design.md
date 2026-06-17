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
"tick."** Note durations are counted in ticks. Tempo = the Timer-A period (the song header
selects it; bigger period = slower song). Because Timer-A is sub-frame and NTSC/PAL-independent,
tempo is frame-rate-independent (master spec §8). 1B does **not** use Timer-A (its DAC loop is
free-running), so Timer-A is free for tempo here.

```
SongHeader:
  db   tempo                ; Timer-A period selector (tempo); bigger = slower
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
