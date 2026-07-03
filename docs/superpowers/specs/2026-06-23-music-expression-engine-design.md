# Music Expression Engine — Design Spec (E-now + Macro Automation Spine)

**Date:** 2026-06-23
**Status:** Design — pending user review → writing-plans
**Scope owner:** engine (mechanism/architecture); content (songs/samples) is downstream/user-driven.

---

## AMENDMENT (2026-07-01): shipped-state deltas

Everything in this spec except per-note portamento has SHIPPED (Phases 1/2/3 merged to master).
Small deltas between the design text and the shipped engine:

- **§3.3 macro grammar** shipped with its own control bytes, not the PSG-env `$80-$83` set:
  **`TAG_MAC_*` = `$E0` NEXT (yield one frame), `$E1` REG (+part+reg+val), `$E2` LOOP
  (+2-byte BIG-ENDIAN body-base, `Snd_SongBase`-rebased), `$E3` END** — see
  `tools/song_packer.py` (`TAG_MAC_*`) and `MacroTick`.
- **§9.1 SeqChannel sizing:** the music `SeqChannel` end-state is **58 bytes** (build-asserted
  in `sound_constants.asm`), not the 56 projected here.
- **§9.3 / the recovery doc's "code-banking technique" is UNSOUND for in-frame CODE:** Z80
  code fetched through the `$8000` window corrupts under 68k bus contention (DMA/BUSREQ; `di`
  doesn't help) → wild PC → self-reinit. **Only DATA may be banked**; all in-frame code must be
  resident (`engine/sound/sound_banked_z80.asm` was deleted when its last routine,
  `Fm_FnumApplyDelta`, moved resident). §9.3's data co-location itself stands.
- **Portamento (§4 / T1) costing is superseded** by the turnkey plan
  `docs/superpowers/plans/2026-06-28-portamento-resume.md` (~323 B resident code + bank the
  remaining DATA tables); execute that plan, not §9.3's original budget math.

---

## 1. Overview & intent

This is the **once-and-done music instrument** for Sonic 4. The music *core* (FM+PSG
sequencer, DAC drums, Phase 3a FM depth, SFX engine + game integration, Moving Trucks
verified faithful) is already complete and merged to master. This spec adds the
**expression layer** that turns a faithful playback engine into a best-in-class one, and —
critically — **finalizes the music data format**, because everything authored against it
(including via MegaDAW, which can only expose what the format supports) is re-authored if
the format changes later.

**Design principle (the reason this spec is maximal):** be maximal on the **data format and
per-channel state** now — those are the things a later change forces a re-author of. Let
the **rendering code** land in phases, but every phase plugs into the *end-state* format, so
later work *completes* the engine rather than rewriting it. ("Design for C, build for A.")

The architecture is built so that all expression features are facets of **one** mechanism (a
per-channel automation/macro stream), not a pile of one-off renderers — this is what makes
"design once" real.

---

## 2. Scope

### In scope (build this effort)
- **Macro/automation spine** — generalize the per-channel automation stream (slot[1]).
- **T1 — Pitch expression:** sub-semitone fine pitch, note-to-note **portamento**,
  **per-channel software vibrato** (rate/depth/phase/onset).
- **T2 — FM TL volume envelopes** (intra-note swells/tremolo on carriers).
- **Music PSG volume envelopes** (extend the shipped SFX PSG env onto music).
- **T3 — Hardware LFO control:** `$22` rate (sequencer-settable) + per-channel `$B4`
  AMS/FMS depth automation. Doc fix: `$08` = 3.82 Hz (not 3.98).
- **T4 — Master fade + global tempo** (fade-in/out/to-prev; speed-up/slow-down).
- **Raw-register escape opcode** (`MEV_REGWRITE`) — write any YM2612 register from the stream.
- **SSG-EG per-operator** ($90–$9E) — metallic/buzzy/AY timbres.
- **Task 0 — RAM/code recovery** (the enabler): bank hot tables to ROM window; extend the
  channel array; relocate the DEBUG trace ring.

### Already shipped (reused, not rebuilt)
Per-op TL bias (`sc_opbias`), pan (`sc_pan` → `$B4`), trill/arp pitch-envelopes
(`MEV_PITCHENV` / `sc_points`), voice-stepping reg-deltas (`MEV_REGDELTA`), the SFX
software-modulation core (`Mod_Advance`), the PSG volume-envelope renderer (`PsgEnvUpdate`).

### Out of scope / deferred (with reason)
- **CH3 special mode / CSM** — niche; complicates FM3 SFX voice arbitration; CSM contends
  with our ~59 Hz Timer-A. Reachable later via `MEV_REGWRITE` if a song needs it.
- **True division-based (linear-in-cents) portamento** — research consensus: trackers
  default to **linear-in-fnum**, which is what sounds right and is add-only (no per-frame
  multiply/divide). Division-based glide is a nicety not worth the cost. Skipped deliberately.
- **Echo-style live event injection** — mailbox is already reentrant/extensible; build only
  if a concrete boss/cutscene needs it.
- **Content** (songs, instrument banks, samples) — user-driven; this spec defines the format
  the content targets.

---

## 3. Architecture

### 3.1 Two fold-points, not four systems
Every researched driver converged on: *keep everything additive in its native domain — no
per-frame multiply/divide.* We already have the two seams this needs and extend them:

- **Carrier-TL write** (`Fm_SetVolume`, `sound_fm.asm:347` — already folds log-volume +
  `sc_opbias` + SFX ducking) → also folds **FM vol-env output** + **master-fade scalar**.
- **fnum fold** (`Mod_Advance` `sound_sequencer.asm:418` + `Fm_WriteFreq` `:740`) → reused
  for **portamento** + **fine detune** + **vibrato**, plus a **block-boundary correction**.

### 3.2 The dual-stream / macro spine
The format already carries a **per-channel second stream** — `sc_mod_ptr` (slot[1],
`sound_constants.asm:773`). The song loader already parses a big-endian `mod_ptr` offset per
channel header record and stores it (`z80_sound_driver.asm:971-982`); it is NULL today and
nothing reads it. `ModUpdate` is deliberately **stream-agnostic** (reads only `sc_*` state,
`sound_sequencer.asm:90-96`).

The spine is therefore:
- **slot[0]** `sc_stream_ptr` — the **note/command stream** (notes, durations, patch, the
  existing coordination opcodes). Unchanged.
- **slot[1]** `sc_mod_ptr` — the **automation stream**: a new per-frame reader (`MacroTick`)
  parses macro events and writes per-channel automation **state** (`sc_*`). It never writes
  the chip directly.
- **`ModUpdate`** — the renderer: turns automation **state** → chip writes, once/frame,
  write-on-change. Untouched in spirit; gains the music-side rendering (un-gated).

**Reader → state → renderer** separation means each new expression feature is a new macro
*target* + (optionally) a renderer fold — never a re-parse and never a format break.

### 3.3 Generalized macro format (one format, many targets)
The shipped PSG vol-env IS a macro in miniature: a **body** of value bytes + control codes
(`$80` loop-to-start, `$81` sustain/hold, `$83` rest/stop), a per-channel **cursor**
advanced one entry/frame, resolved via a tiny id→ptr map (`PsgVolEnv_Resolve`,
`sound_psg.asm:123`). We generalize this into the macro format used by all automation:

```
macro body := { value | control }*
  value    : signed/abs byte applied to the macro's TARGET
  control  : $80 LOOP <to>     ; loop point (loops until release if before release)
             $81 HOLD          ; sustain current value (no advance) until key-off
             $82 RELEASE       ; release point (key-off jumps here, then runs to END)
             $83 END           ; stop the macro (and, for vol, key-off semantics)
```

A macro is bound to a **target** (volume / pitch-offset / pan / arbitrary register) when
armed. Targets fold additively into the same two fold-points (§3.1). This is the
Furnace/MDSDRV/AMPS "macro track" model — the single most "feels alive" lever, and it
subsumes vibrato, vol-env, pitch-env, pan-LFO, etc. as *instances* of one mechanism.

> Dedicated note-stream opcodes (vibrato `MEV_MODSET`, `MEV_FMENV`, etc.) remain as
> ergonomic fast-paths for the common in-line cases; the slot[1] macro stream is the general
> automation path. Both write the same `sc_*` state, so they compose.

---

## 4. T1 — Pitch: fine pitch, portamento, per-channel software vibrato

**Representation (chosen, see scope-decision dialogue):** keep the existing **packed
16-bit `fnum`+`block` word** (`$A4` = `block<<3|fnumHi`, `$A0` = `fnumLo`) and the current
132-entry 2-page chromatic tables (`FmPitchTableZ`, `sound_tables_z80.asm:11`). Add:

1. **Fine detune** — `sc_detune` (signed byte), sign-extended and added to the looked-up
   fnum word at note-on (and folded by the renderer for held notes). Enables sub-semitone
   offset + detune-unison/chorus.
2. **Block-boundary correction** — after any per-frame fnum add (portamento or vibrato),
   if `fnum > FNUM_HI` → `fnum >>= 1; block += 1`; if `fnum < FNUM_LO` → `fnum <<= 1;
   block -= 1`. (Halving fnum + incrementing block is the *same pitch* — the chip shifts
   fnum by block — so glides cross octaves seamlessly.) Constants `FNUM_LO`/`FNUM_HI` =
   the chip's per-octave fnum span (~`$0280`..`$04FF`; top ≈ 2× bottom). This is the fix our
   current `Mod_Advance` lacks (it only survives small vibrato today). Refs: S.C.E.
   `zDoPitchSlide` 0x283/0x508 thresholds; modern jsgroth YM2612 phase model.
3. **Portamento** — reuse the already-reserved `sc_porta_accum` (+32, current sliding pitch)
   and `sc_porta_incr` (+34, signed slope/frame). Target = `FmPitchTableZ[sc_note]`
   (recomputed, no stored target). On a porta-armed note-on: keep `sc_porta_accum` (don't
   snap), set new `sc_note` as target, key-on at the current pitch, slide each frame toward
   target with block correction; when reached, zero `sc_porta_incr` and snap exact. On a
   non-porta note-on: snap `sc_porta_accum = table[note]` so the next glide starts correct.
   **Zero new bytes** (uses reserved fields). Linear-in-fnum slope (cheapest, tracker default).
4. **Per-channel software vibrato** — **un-gate `Mod_Advance`/`ModUpdate` for music** (remove
   the `Snd_ChanClass` SFX-only gates at `sound_sequencer.asm:153/194`, `sound_fm.asm:704`),
   and give the **music `SeqChannel` the modulation block** (the 13 bytes `sc_mod_ctrl`
   .. `sc_last_freq`, currently SfxChannel-only). Music gains full per-channel vibrato:
   independent rate (`sc_mod_speed`), depth (`sc_mod_delta`), reversal period
   (`sc_mod_steps`), **per-note onset delay/swell-in** (`sc_mod_wait`, re-armed each note via
   `Mod_ReArm`), and phase (per channel). Armed by `MEV_MODSET` (now music-legal) **or** a
   pitch-target macro.
5. **PSG** — same `Mod_Advance` core drives the 10-bit divisor (no block); `Psg_ApplyMod`
   re-latches the divisor. Music PSG gains vibrato/portamento via the same path.

**Music note-on must now latch `sc_base_freq`** (today SFX-only) so the renderer has the
unmodulated base to add the offset onto.

---

## 5. T2 — FM TL volume envelope + music PSG volume envelope

Both FM and PSG volume envelopes use the **unified `sc_env`/`sc_env_cur`/`sc_env_out`** slot
(§9.1 — a channel is FM *xor* PSG, so one 3-byte slot serves both; the renderer branches on
the channel's route).

**FM vol-env (new):** mirror the shipped PSG env exactly, but write FM **carrier** TLs.
- State: `sc_env` (id), `sc_env_cur` (cursor), `sc_env_out` (last delta, write-on-change).
- Format: the §3.3 macro body (loop/hold/release/end), resolved via an `FmVolEnv_Ids/Ptrs`
  map mirroring `PsgVolEnv_*`.
- Render: advance one entry/frame in `ModUpdate`; fold `sc_env_out` into the existing
  `Fm_SetVolume` carrier-TL computation (`effective_TL = base + log(vol) + sc_opbias +
  duck + env_out + master_fade`, saturating clamp 0..$7F). Carrier selection reuses
  `CarrierMaskTableZ` (already algorithm-aware — never touches modulator TLs).
- Arm: `MEV_FMENV` (note-stream) or a volume-target macro (slot[1]).

**Music PSG vol-env:** the renderer (`PsgEnvUpdate`) already exists; it's gated SFX-only
because the env fields are past the music struct today. With the music struct grown (Task 0,
unified `sc_env`), un-gate it for music. `MEV_PSGENV` becomes music-legal.

---

## 6. T3 — Hardware LFO control (complementary to software vibrato)

Software vibrato (T1) is the per-channel expressive path; the hardware LFO is the cheap
*uniform* path and a tremolo source. Both coexist (stackable — keep cached per-channel `$B4`).

- **`MEV_LFO`** (new opcode): set `$22` = `enable | rate` (3-bit, 8 speeds). **Must save and
  restore the DAC `$2A` address-park** around the `$22` write (the DAC streamer parks the
  bank-0 address on `$2A`; a stray `$22` write otherwise misroutes the next DAC byte). Set
  once per song/section is the norm; opcode allows rare mid-song change.
- **Per-channel `$B4` AMS/FMS depth:** automatable (cache the `$B4` byte; OR/AND in AMS
  (bits 4-5) / FMS (bits 0-2) without disturbing the L/R pan bits). Via a small opcode or a
  pan/$B4-target macro.
- **Doc fix:** `z80_sound_driver.asm` LFO comment "~3.98 Hz" → **3.82 Hz** (the real `$08`
  rate). Rate table (Hz): 3.82, 5.33, 5.77, 6.11, 6.60, 9.23, 46.11, 69.22.

---

## 7. T4 — Master fade + global tempo

**Master fade (global scalar, not per-channel ramp):** one `SND_MASTER_FADE` byte
(attenuation units; 0 = full, $7F = silent), folded into the **same** TL write (`Fm_SetVolume`)
and into `Psg_SetVolume` (`+ fade>>~3`, clamp $0F). Zero marginal per-channel cost. A small
fade state machine (`target`, `speed/delay` counters) ramps it each frame; while a fade is
active, force the per-frame volume re-assert (a global "fade dirty" flag drives `ModUpdate`
to re-write TLs). Fade-out → ramp to $7F then stop; fade-in → start $7F, ramp to 0;
fade-to-previous → ramp down, restore saved song state.

**Global tempo:** a global tempo scalar applied to the existing per-channel tempo accumulator
(`sc_tempo_accum -= 16`, reload `sc_tempo_base`, `sound_sequencer.asm:71-79`). Keep the fixed
~59 Hz frame tick (no YM Timer reprogram). Speed-up (speed-shoes/invincibility) = larger
scalar; slow-down (drowning/time-over) = smaller. SMPS overflow-accumulator idiom.

**Triggers:** mailbox commands (68k → driver) for game events (death/clear/level-start/
speed-shoes/drowning/1-up) **and** `MEV_FADE`/`MEV_TEMPO` note-stream opcodes for in-song use.

---

## 8. Add-ons: raw-register escape + SSG-EG

- **`MEV_REGWRITE`** (new): operands `part` (0/1) + `reg` + `value` → write any YM2612
  register from the stream (with the `$2A` restore discipline if part 0). The ultimate
  anti-pigeonhole primitive — any present/future chip feature reachable without a format change.
- **SSG-EG** ($90–$9E, per operator): buzzy/metallic/AY timbres; one reg write at note-on.
  Implement as either a **7th `RegDelta` group** (`RegDeltaGroupBase` currently $30–$80,
  6 groups, `sound_fm.asm:547`) + a per-op patch byte, **or** via `MEV_REGWRITE`. Prefer the
  RegDelta group (consistent with voice-stepping) + carry an SSG-EG byte per op in the patch.

---

## 9. Task 0 — RAM & code recovery (the enabler)

The new code + per-channel state exceed current budgets; recovery comes first.

### 9.1 Per-channel state growth (+17 B music `SeqChannel`, 39 → 56)
| Field(s) | Bytes | For |
|---|---|---|
| `sc_mod_ctrl`..`sc_last_freq` (mod block) | 13 | software vibrato + portamento base/shadow |
| `sc_env`,`sc_env_cur`,`sc_env_out` | 3 | vol-env — **FM and PSG share one slot** (a channel is FM *xor* PSG): FM carriers via `Fm_SetVolume`, PSG via `Psg_SetVolume` |
| `sc_detune` | 1 | fine pitch |
| `sc_porta_accum`,`sc_porta_incr` | 0 | already reserved (+32/+34) |
| **Total** | **+17** | music `SeqChannel` 39 → 56 B |

These are added to the **shared prefix** so SFX channels keep their existing fields and gain
FM vol-env "for free" via the shared `sc_env` slot (SFX already had `sc_psgenv` here — it
becomes the unified `sc_env`; SfxChannel grows correspondingly; verify it stays < `$1F00`).
Exact offset layout finalized in the plan.

### 9.2 Data-region rework (clean, contained) — ✅ DONE
The channel array (`$1808`) is capped at the trace ring (`$1A00`). Made the trace-ring base
**track the end of the seq-RAM block** (`SND_SEQ_TRACE = (Snd_SpindashRev + 1 + $FF) & $FF00`)
so a future per-channel struct growth slides the trace ring up into the currently-unused
`$1A20–$1AFF` gap automatically. **Critical:** the DEBUG trace writer builds the ring address
as `ld h,SND_SEQ_TRACE>>8 / ld l,wr`, so the ring MUST stay **page-aligned** — the formula
rounds up to the next `$100` boundary (with current sizes it lands back on `$1A00`, fully
behavior-preserving). Asserts added: ring page-aligned, and `ring + len ≤ SND_SONG_BUF`.

### 9.3 Code-space recovery (F5) — ✅ DONE via **CO-LOCATION** (not a swap)
**Measured (DEBUG): only 2 bytes free** to `$16F0` — F5 was mandatory. The original plan
(separate table bank + one bank-swap per `Sequencer_Frame`) **failed**: Moving Trucks is a
**STREAM-path song** (FM6=FM) — it reads its stream/patch/pitch *through the `$8000` window
every frame*, so the window can't also hold a separate table bank (proved: corrupted→silent).
**The window can't be COPY-assumed.**

**What shipped instead — co-location:** the engine lookup tables (`FmPitchTableZ`,
`PsgDivisorTableZ`, `LogVolumeLutZ`, `CarrierMaskTableZ`, `PsgVolEnv_*`, engine-default
`MovingTrucks_PitchTable`) are emitted at the **START of MT's own streamed bank** (window
`$8000`, under `cpu z80 / phase 08000h` so the labels equal their window pointers). During
MT's frame the window is already on MT's bank, so table reads + stream/patch/pitch reads all
hit the same bank — **no swap, zero runtime cost**. SFX is covered for free (its blobs share
MT's bank). **Result: headroom 2 → ~1016 B.** Verified: MT renders == pre-banking baseline
within capture variance (same-rom control r=0.992; MT-vs-baseline r=0.996).

> **Banking model (the general rule):** put the engine tables at bank-start in whatever bank
> the window holds during a frame. STREAM songs + their SFX → done (one shared bank). COPY /
> FM6=DAC-drum songs run with the DAC sample bank in the window — they need a label-free
> data-only copy of the tables emitted at the DAC bank start too. **Deferred** (no COPY songs
> exist — the Phase-3 scratch COPY test songs were dropped); a one-include hook for the first
> real DAC-drum song. See DEFERRED_WORK.

### 9.4 Daemon caution
`tools/ojz_strip_gen.py` and `data/editor/` are auto-commit-daemon-watched — not touched by
this work. Sound tooling (`gen_sound_tables.py`, the transcoder) is fair game.

---

## 10. MEV opcode allocation

Free slots today: `$F1–$FE` (13; `$F1` reserved-but-`Seq_BadOpcode`). New opcodes:
`MEV_PORTA`, `MEV_FMENV`, `MEV_LFO`, `MEV_REGWRITE`, `MEV_FADE`, `MEV_TEMPO`, `MEV_MACRO`
(arm a slot[1] macro on a target), `MEV_DETUNE` (or fold into note/porta), `MEV_LFODEPTH`
(`$B4` AMS/FMS) — ~9, fits in 13. `MEV_MODSET`/`MEV_PSGENV` are **un-gated** for music
(no new opcode). SSG-EG = RegDelta 7th group (no opcode). Every opcode handler obeys the
**hl-preservation rule** (push/pop hl around any call that clobbers the live stream ptr —
`sound_sequencer.asm:597` et al.). Final numeric assignment + the `sound_constants.asm`
collision asserts finalized in the plan.

---

## 11. Build-time validation (AS asserts)
- `SeqChannel_len` / `SfxChannel_len` equal their expected new sizes.
- `SND_SEQ_END` + scratch + trace-ring < `$1B00` (song buffer); SfxChannel array < `$1F00`.
- `Z80_SOUND_SIZE` ≤ `$16F0` (code ceiling) **after** F5 banking.
- New MEV opcodes in `$E0–$FF`, no collisions (mirror existing `MEV_*` asserts).
- Carrier-mask table covers all 8 algorithms; `FNUM_LO`/`FNUM_HI` sane.
- Banked-table bank alignment / size asserts.

---

## 12. Testing & verification

Per project rule: **verify rendered AUDIO, not the register/key-on stream** (a key-on stream
can be 100% correct yet inaudible). Build with `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`
(plain build excludes all sound).

- **Per feature, audible test:** a tiny test song/phrase exercising each (a portamento glide
  across an octave; a vibrato with delayed onset; an FM swell; a PSG tremolo; an LFO change;
  a master fade-out; a tempo speed-up; an SSG-EG timbre). Render via Exodus VGM →
  `vgm2wav`; compare energy + spectrum; confirm by ear where subjective.
- **Block-boundary correctness:** a slow glide spanning ≥1 octave must be *continuous*
  (no octave jump) — the specific failure mode this design fixes.
- **Regression:** Moving Trucks must still render byte/spectrum-faithful (the macro/recovery
  changes must not perturb existing playback); the golden self-test (DEBUG boot) stays green.
- **Budget:** confirm no new lag — `Sequencer_Frame` worst-frame cost << DAC ring lead;
  the once-per-frame bank swap measured.
- **Live hardware state** via Exodus MCP (`z80_registers`, `read_vram`, VGM capture).

---

## 13. Implementation phasing (each phase audible + verifiable)

0. **Recovery** — F5 table-banking + data-region rework + grown struct (build + golden test green).
1. **Macro spine** — slot[1] `MacroTick` reader + generalized macro format + `MEV_MACRO`;
   re-express the existing PSG vol-env through it as proof (no behavior change).
2. **T1** — fine pitch + portamento + per-channel software vibrato (un-gate, block-boundary).
3. **T2** — FM vol-env + music PSG vol-env.
4. **T3** — LFO `$22` + `$B4` automation + doc fix.
5. **T4** — master fade + global tempo (mailbox + opcodes).
6. **Add-ons** — `MEV_REGWRITE` + SSG-EG.

Each phase merges to master when verified (commit early/often; feature branch per phase).

---

## 14. Open questions (resolve during writing-plans)
- Exact final per-channel field offset layout (and whether music + SFX fully unify the prefix).
- Macro stream **clocking**: per-frame (60 Hz) vs per-event-tick — recommend per-frame for
  smooth automation, decoupled from note tempo (matches Furnace/MDSDRV macro semantics).
- Final `MEV_*` numeric assignments.
- Whether `$B4` AMS/FMS gets its own opcode or rides the macro/pan path.
- Confirm real code headroom by building before sizing F5.

---

## Format validity rules (normative) — added 2026-07-03

`tools/song_packer.py` is the enforcement reference for every rule below (2026-07-01 sound-specs review §5 item 9). The Z80 engine does **not** re-validate streams — the format is trust-the-packer: a violating blob **hangs or corrupts the driver, it does not error**. Any other producer (the future MegaDAW exporter) MUST enforce ALL of these rules itself. Markings: **TRUST-PACKER** = the engine has no runtime defense; **ENGINE-GUARDED** = the engine also defends at runtime (the rule is still normative — don't emit it). Line numbers cite the enforcing code as of this date.

### (a) Stream structure

1. Every channel command stream is non-empty (`song_packer.py:927-928`). **TRUST-PACKER** (fetch runs into adjacent blob bytes).
2. The LAST event of every stream is `Jump` ($EF) or `End` ($FF) (`song_packer.py:929-931`). **TRUST-PACKER**.
3. `Jump` requires a preceding `LoopPoint` ($EE) in the same stream (`song_packer.py:910-912`). **TRUST-PACKER**.
4. The loop body (`LoopPoint`..`Jump`) contains ≥1 **time-advancing** event (`song_packer.py:900-916`). The time-advancing set is exactly: `Rest` $80, `Note` $81–$DF, `NoteDur` $E3, `NoteRaw` $E7, `PitchEnv` $E8. All other events are zero-tick; a zero-tick-only loop spins the Z80 fetch loop forever. **TRUST-PACKER** (hard hang).
5. `channel_count` is 1..11 (`CHROUTE_COUNT`) (`song_packer.py:961-965`); channel routes are unique — no two streams on one chip channel (`song_packer.py:966-971`). **TRUST-PACKER**.
6. Header flags: `SH_F_STREAM` is always set (the packer force-sets it — every song streams from ROM; `song_packer.py:952-955`); `SH_F_FM6_ADAPTIVE` requires `SH_F_FM6_FM` (`song_packer.py:959-960`). **TRUST-PACKER**.

### (b) Durations & notes

1. `SetDur` operandless duration byte: $00–$7F ticks (range-dispatched opcode space) (`song_packer.py:156-158`).
2. `Note` pitch index 0..$5E ($81 + pitch ≤ $DF) (`song_packer.py:173-175`).
3. `NoteDur` ($E3): pitch 0..$5E, dur 0..255 (`song_packer.py:627-631`).
4. `NoteRaw` ($E7): FM-only; a4/a0 raw bytes; dur **1..255** (0 illegal) (`song_packer.py:647-653`).
5. `PitchEnv` ($E8): FM-only; 1..5 points, each an absolute fnum-table index 0..$83 (`song_packer.py:656, 674-683`).
6. `Vol` ($E0): 0..127 (`song_packer.py:185-187`).

### (c) Repeats ($E5/$E6)

1. **Single-level only — nesting is illegal.** The engine keeps ONE `sc_repeat_ptr`/`sc_repeat_count` per channel; a nested `RepeatStart` would overwrite the saved pointer and corrupt the loop (`song_packer.py:853-859`; `engine/sound/sound_sequencer.asm:1678-1687`). Sequential (non-overlapping) repeat blocks are legal — the count re-arms after each block (`sound_sequencer.asm:1696-1702`; `test_song_packer.py:817`). **TRUST-PACKER**.
2. Every `RepeatEnd` has a preceding open `RepeatStart` (`song_packer.py:862-864`); every `RepeatStart` is closed (`song_packer.py:924-926`). **TRUST-PACKER**.
3. The repeat body contains ≥1 time-advancing event (same set as (a)4) — else the Z80 replays it entirely within one frame (loop collapse) (`song_packer.py:866-872`). **TRUST-PACKER**.
4. `RepeatEnd` count is **1..255**; count = 1 plays the body once. **Operand 0 is illegal**: the engine decrements before testing, so 0 runs **255 passes** — there is no runtime clamp (`song_packer.py:781-784`; DEFERRED_WORK.md **D7, still open 2026-07-03**; `sound_sequencer.asm:1711-1737`). **TRUST-PACKER**.

### (d) Route legality

Routes: FM = 0..5 (FM1–FM6), PSG = 6..8, noise = 9, DAC = 10 (`song_packer.py:94-109`; mirror of `sound_constants.asm`).

1. **FM routes only**: `Patch` $E1 (`song_packer.py:215-217`), `NoteFill` $ED (`:204-205`), `NoteRaw` $E7 (`:648-649`), `PitchEnv` $E8 (`:675-676`), `OpBias` $E9 (`:598-600`, op 0..3, val signed −128..127), `RegDelta` $EA (`:748-750`; count 1..255, group_code 0..5, byte values, `:751-763`), `FmEnv` $F7 (`:275-277`), `Macro` $F9 (`:344-346`).
2. `RegWrite` $F8: FM routes, plus ONE narrow DAC-route door — part 1 reg $B6 (FM6/DAC pan) only (`song_packer.py:300-312`). On any route it refuses reg $2A/$2B (DAC data/enable) and the $24–$27 timer block (`:315-323`) — **ENGINE-GUARDED** (the handler skips those writes and re-parks $2A; `sound_constants.asm:467-479`), but normative for exporters regardless.
3. **PSG/noise routes only**: `PsgEnv` $EB (rejected on FM; `song_packer.py:255-257`). **Noise route (9) only**: `PsgNoise` $F2, ctrl $E0..$EF (`:465-469`). **DAC route only**: `Dac` $E2 (`:614-616`).
4. **Any route**: `SetDur`, `Rest`, `Note`, `Vol`, `NoteDur`, `Pan` $E4 (engine renders it FM-only; harmless store elsewhere — `sound_constants.asm:315-322`), `Detune` $F6 (signed −128..127; `song_packer.py:483-485`), `Porta` $F5 (0..255 = off..rate; `:499-501`), `Lfo` $F4 (0..$0F; `:515-518`), `Tempo` $F3, `ModSet` $EC (wait/speed/step unsigned bytes, change signed; `:561-566`), `SpinRev` $F0.
5. `Tempo` event operand is **0..$FE** — $FF is reserved as the `SND_TEMPO_RESTORE` mailbox sentinel and must never be authored (`song_packer.py:534-540`).
6. **Music-illegal**: `MEV_SPINREV_RESET` $F1 must NEVER appear in a music stream — the reset is dispatch-folded (`Sfx_BeginSound` zeroes the rev) and the engine maps a stream $F1 to `Seq_BadOpcode` (`song_packer.py:120, 918-922`; `sound_constants.asm:413`). **ENGINE-GUARDED** (bad-opcode trap, not corruption) — still forbidden.
7. **Music-legal expression set** (D8, CLOSED 2026-06-27): the opcodes beyond the base set that a music stream may carry are exactly `_MUSIC_LEGAL_EXPRESSION_OPCODES` = { `MEV_PSGENV` $EB, `MEV_FMENV` $F7, `MEV_REGWRITE` $F8, `MEV_MACRO` $F9, `MEV_DETUNE` $F6, `MEV_LFO` $F4, `MEV_TEMPO` $F3, `MEV_PORTA` $F5 } (`song_packer.py:121-123`). Note the packer's runtime gate is the ILLEGAL blacklist ({$F1}); the legal set documents intent — an exporter MUST emit no opcode outside this spec. $FA (`MEV_EXT`) is a reserved prefix: no handler exists; emitting it is illegal (`sound_constants.asm:509-515`).
8. **Engine-assumed (NOT packer-enforced)**: `Porta` must follow at least one normal note on the channel (the glide start is seeded by the previous pitch) (`song_packer.py:488-492` docstring only). **TRUST-PACKER** — exporters must order accordingly.

### (e) Macros (slot[1] stream, TAG_MAC_* namespace)

TAG_MAC_* bytes ($E0–$E3) are a PRIVATE namespace read only by MacroTick — not MEV_* opcodes (`sound_constants.asm:482-501`).

1. Body non-empty (`song_packer.py:427-428`); terminated by `MacEnd` or `MacLoop` as the body's **last** event; no mid-body `MacLoop`/`MacEnd` (unreachable tail / un-yielded spin) (`:429-440`). **TRUST-PACKER**.
2. A `MacLoop`-terminated body contains ≥1 `MacNext` **before** the `MacLoop` — MacroTick executes until a `TAG_MAC_NEXT` yield; a loop with no yield spins the Z80 forever (`song_packer.py:441-448`). **TRUST-PACKER** (hard hang).
3. `MacReg`: part 0/1; reg not $2A/$2B and not $24–$27 (`song_packer.py:382-390`; **ENGINE-GUARDED**, `sound_constants.asm:488`); val a byte AND not in $E0..$E3 (control-code-valued data is rejected to keep bodies inspectable, even though operand-position decoding makes it technically safe) (`:395-399`).
4. A slot[0] `Macro` ($F9) event is only legal on a channel that HAS a macro body — otherwise its operand packs as offset 0 and MacroTick executes the song header as tags (`song_packer.py:1013-1018`). **TRUST-PACKER**.
5. Depth: exactly ONE macro stream per channel (`sc_mod_ptr`); `MacLoop` targets only its own body start (back-patched BE offset) — there are no nested macro calls (`song_packer.py:404-409, 991-1009`).

### (f) Bounds

1. All header and operand pointers are 16-bit BE **blob-relative** offsets; the total blob layout must fit ≤ $FFFF or the pointers silently truncate (`song_packer.py:1020-1025`). **TRUST-PACKER**.
2. `pitchtable_offset` 0..$FFFF (`song_packer.py:972-974`); `tempo`, `tempo_mod`, `flags` header bytes 0..255 (`:941-951`). The header `tempo_mod` accepts the full 0..255 (any value is a valid TempoWait addend); the $FF exclusion applies only to the `MEV_TEMPO` event operand ((d)5).
3. Env ids (`PsgEnv`/`FmEnv`) are 1-based bytes, 0 = off (`song_packer.py:258-259, 278-279`). The packer does NOT cross-check ids against the engine's env-table sizes — an out-of-table id indexes garbage. **TRUST-PACKER** (exporters emit only ids defined in the engine tables).

### (g) Channel init-ordering (`_validate_channel`)

1. Route byte 0..10 (`song_packer.py:841-842`).
2. **FM channel**: BOTH `Patch` ($E1) AND `Vol` ($E0) must appear before the channel's FIRST time-advancing event — the chip is keyed at that point, and an uninitialized channel plays the YM2612 power-on garbage voice / undefined volume (`song_packer.py:877-894`). Order between Patch and Vol is free (`test_song_packer.py:441-450`). **`Rest` counts as time-advancing** for this check — keying runs via the tick driver either way (`test_song_packer.py:452-457`). **TRUST-PACKER**.
3. **PSG/noise channel**: `Vol` ($E0) before the first time-advancing event (no patch concept; $E1 is already route-illegal) (`song_packer.py:895-899`). **TRUST-PACKER**.
4. **DAC channel**: exempt — it only triggers samples ($E2) (`song_packer.py:877-884`; `test_song_packer.py:483-488`).
