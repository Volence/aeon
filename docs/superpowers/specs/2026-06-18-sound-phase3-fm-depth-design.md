# Sound Phase 3 — FM Depth (Moving-Trucks-driven), design-for-C / build-for-A

**Date:** 2026-06-18
**Status:** Design approved (brainstorming, 2026-06-18)
**Branch:** `feat/sound-phase3-fm-depth`
**Builds on:** Phase 1 (1A/1B/1C) + the 1D FM infra merged to master (adaptive FM6 slot,
DAC-off ROM streaming, `MEV_REPEAT`/`MEV_NOTE_RAW`, per-song `SongPatchTable` + stream loader).
**Drives / acceptance test:** a faithful native-sequencer port of **"Moving Trucks"** (The
Adventures of Batman & Robin; Zyrinx "Advanced Z80 Player", Jesper Kyd).

---

## 1. Goal & guiding principle

Give our sound driver the **FM-depth** capabilities that make a Zyrinx-class FM soundtrack
sound alive, and prove them by playing Moving Trucks **as a real port** — our sequencer
playing the song from its musical data, NOT a captured-register replay. This is part of the
master spec's **Phase 3** (FM depth); we scope to the subset Moving Trucks exercises and use
the song as the forcing function / acceptance test.

**North star (non-negotiable):** best-in-class. Every choice leads with the best-of-class
option, and **no format/architecture decision may pigeonhole us out of the full best-of-class
end state.** Concretely we adopt **"design for C, build for A"**:
- **C** = the master spec's full dual-per-channel-data-streams model (a tempo-gated note stream
  *and* an independent-timing modulation stream). This is the best-in-industry end state.
- **A** = Zyrinx's single-stream-sets-state model (one command stream configures per-channel
  modulation state rendered per frame). This is what Moving Trucks uses and can validate.
- We **lay out the format + the modulation layer for C**, but **implement A** first, fully
  validated by Moving Trucks. Reaching C is then purely additive (a second stream reader writing
  the same state) — **no format migration, no layer rewrite.**

**Out of scope (defer to a later Phase 3b, when a song needs them):** SSG-EG, hardware LFO,
Ch3 special/CSM, detune-unison, full PSG envelopes, the independent second modulation stream
itself. Moving Trucks uses none of these.

## 2. Reverse-engineering basis (done)

The Zyrinx driver is fully reverse-engineered and a reference player validated against the
oracle. Authoritative artifacts:
- `…/disasm/sound/zyrinx_driver.asm` — full labeled disassembly (6180 bytes, machine-verified).
- `…/disasm/sound/ZYRINX_FORMAT.md` (v2) — corrected format spec (132-entry pitch table, command
  set, timing model, 6-per-channel-block song layout, channel allocation).
- `docs/research/z80_blobs/batman_driver_analysis.md` — the original (pre-existing) RE; reconcile.
- `tools/zyrinx_player.py` — validated reference simulator: renders Moving Trucks from
  `bank1_song03.bin`; matches the oracle note-for-note on 5/6 channels, audio spectrum r=0.93.
- Oracle: `/tmp/moving_trucks_ref.vgm` (the real full song, 158.6 s, GD3-confirmed, 100% of its
  pitch writes map to the driver's fnum table). **Verification oracle only — never a source.**

Key facts the design rests on: 6 driver channels map **1:1 to FM1–6** (not via CH-select);
the drums are **pure FM** (DAC never enabled); pitch motion is **re-articulated, never bent on a
held key**; the per-frame patch/TL re-assert (~290 writes/s/channel) is the signature timbre.

## 3. Architecture — per-frame engine + separable modulation layer

The driver runs one **frame** per Timer-A overflow at **~59.4 Hz** (region-independent; the
Timer-A reload is computed at build time from the target rate via a `function`, not a magic
literal). Per frame, per active channel, in order:

1. **`ModUpdate` (the modulation layer).** Reads the channel's *modulation state* and writes the
   YM2612: frequency (`$A4/$A0`), key-on/off (`$28`), patch reload (on voice change), pan
   (`$B4`). This unit is **stream-agnostic** — it only reads state. Voice-stepping, trills/arps,
   and portamento all happen here, per frame.
2. **Command-stream advance.** A per-channel **tempo accumulator** gates musical timing:
   `tempo_accum -= 16` each frame; on borrow, `tempo_accum += tempo_base` and the channel
   consumes its next command(s) up to the next WAIT. Commands **set modulation state**; they do
   not write the YM directly.

`tempo_base` is the song/channel "format code" (Moving Trucks = `$38`); a per-pattern tempo byte
replaces it (absolute) when non-zero. WAIT byte `W` ($80–$FF) waits `$FF − W` event-ticks.

The DAC (1B) continues to run in the same Z80 loop; the per-frame FM work shares the budget with
it (see §8 risk + the cycle-budget spike).

## 4. C-ready data model (the no-pigeonhole guarantee)

Each channel carries a **stream table**, not a single pointer:
- `slot[0]` = **command stream** (always present).
- `slot[1]` = **modulation stream** (field reserved in the layout **now**; **null for A /
  Moving Trucks**).

Both slots write the **same shared modulation-state struct**, which `ModUpdate` renders. The
`SongHeader`/per-channel descriptor commits this `{stream[0], stream[1]}` layout from day one, so
the format is C-ready. Path to C: populate `slot[1]` + add a second reader — **no format change,
no `ModUpdate` change.**

## 5. Per-frame features (the Phase-3a feature set)

1. **Pitch — per-song fnum table.** A note operand is an absolute index `0..$83` into a
   **per-song** pitch table; Moving Trucks embeds the exact Zyrinx 132-entry table (bit-identical
   pitches incl. sub-bass). The 1C test song keeps its own table. Per-pattern signed transpose is
   added then clamped (Zyrinx clamp behavior). A per-song pitch-table pointer lives in the header.
2. **Multi-point pitch envelopes (trills/arps).** A note carries 1–5 pitch *points* →
   `points[5]`, `count`, `cursor` in channel state. `ModUpdate` advances the cursor each frame
   (wrap at `count`) and re-articulates. `count=1` = a plain note; `count≥2` = the Zyrinx trill/arp.
3. **Voice-stepping.** The command stream changes the *current voice index* in state; `ModUpdate`
   reloads the patch when it changed since last frame and re-asserts carrier TL each frame → the
   continuous timbre sweep. **Re-key happens on a note / pitch-change, not on a voice change.**
4. **Pan.** Commands set pan state (off/L/R/C); `ModUpdate` writes `$B4` L/R (and AMS/FMS) bits.
5. **Per-operator TL bias.** Per-op TL offsets in state, added to the patch's operator TLs at
   patch load — the per-note brightness accent.
6. **Portamento (lowest priority).** A command sets target + duration; `ModUpdate` runs a Q5
   fixed-point accumulator each frame. Moving Trucks barely uses it (one `$0A`, audibly
   negligible per the RE); build it for completeness, but it may defer without hurting MT fidelity.

## 6. Channel state + opcodes (extends the v0 format)

The `SeqChannel` struct grows a **modulation-state block**: `points[5]` + `count` + `cursor`;
`voice` + `last_voice`; portamento `accum`/`target`/`incr`; `pan`; `op_bias[4]`; `tempo_base` +
`tempo_accum`; per-song pitch-table pointer. Defined via `struct`/`endstruct`, laid out with
`phase`/`dephase` per the coding conventions.

Opcodes extend the existing `MEV_*` set (no rip-and-replace):
- **Reuse:** `MEV_PATCH` ($E1) = voice change *without* re-key; `MEV_PAN` ($E4, reserved) = pan;
  `MEV_REPEAT`/`MEV_REPEAT_END` ($E5/$E6) + `MEV_LOOP`/`MEV_JUMP` ($EE/$EF) = the pattern/repeat/
  loopback structure (already shipped); `MEV_NOTE_RAW` ($E7) stays as the raw-register escape hatch.
- **Add (free opcode space $E8–$ED / $F0–$FE):** `MEV_PITCHENV` (multi-point note: count + 1–5
  point indices), `MEV_OPBIAS` (per-op TL offsets), `MEV_PORTA` (glide target + duration), and a
  per-channel tempo set (or carry `tempo_base` in the header + per-pattern override).
- Single-pitch songs (the 1C test song) keep using `$81–$DF` / `NOTE_DUR`; `MEV_PITCHENV` is the
  Zyrinx-style note. Exact byte encodings are finalized in the implementation plan; the packer
  (`tools/song_packer.py`) gains matching event classes with build-time validation.

## 7. The port path (source = song data, not a recording)

Extend the **validated reference player** (`tools/zyrinx_player.py`) to *emit our native format*:
transcode `bank1_song03.bin` (the real Moving Trucks song data) into our v0+Phase-3 opcode
streams, preserving structure — patterns→sequences→repeats via `MEV_REPEAT`/`LOOP`, the pitch
envelopes, voice-stepping, pan, transpose, per-channel tempo. Emit the per-song 132-entry pitch
table and the FmPatch bank (reuse `zyrinx_port.py`'s Zyrinx-voice→FmPatch translation). Our
sequencer then plays it. The oracle VGM is consulted only to verify.

## 8. Verification, regression, and the one risk

**Per feature**, verify by building the ROM (our engine playing the native MT song), capturing
our YM stream in Exodus, rendering to audio (`vgm2wav`), and diffing vs `/tmp/moving_trucks_ref.vgm`:
- **rendered-audio** energy (fraction-sounding, mean/peak) + **average log-spectrum correlation**
  (the real metric — never a register/key-on proxy), plus per-channel note-sequence match.
- Use the **Exodus Z80 MCP tools** (`emulator_z80_registers/read`, post GUI+MCP restart) to read
  our sequencer's live per-channel state directly when chasing residuals.

**Regression:** the 1C test song and the 1B DAC must keep working unchanged (the per-frame model
is a superset; plain channels just hold; the test song's tempo is re-expressed for the frame model).

**The one real risk — cycle budget.** The per-frame FM work (6 voices × patch reloads + the TL
re-assert) must coexist with the DAC on one Z80. Zyrinx proves it's feasible on the same hardware,
but our budget must be confirmed. **First implementation step is a cycle-budget spike** (measure a
worst-case frame: 6 channels voice-stepping + DAC); if over budget, the fallback is the documented
options (split FM work across the even/odd frame halves like Zyrinx, or throttle re-assert rate).

**The one open RE residual — the exact re-key rule.** The reference player overproduced key-ons on
the two dense voice-stepping channels (ch1/ch4); the precise condition under which the driver
re-articulates (each cursor step? only on pitch change? a same-pitch throttle?) was not resolvable
from static analysis. Resolve it during implementation by tracing the live behavior against the
oracle with the Z80 MCP tools — calibrate, don't guess.

## 9. Decomposition (for the implementation plan)

1. **Cycle-budget spike** (de-risk before building).
2. **Per-frame engine core**: Timer-A → 59.4 Hz frame, per-channel tempo accumulator, the
   `ModUpdate` skeleton + the C-ready stream table; regression: test song + DAC still play.
3. **Pitch**: per-song fnum table + transpose/clamp; single-note path.
4. **Multi-point pitch envelopes** (trills/arps).
5. **Voice-stepping** + the re-key rule (calibrated vs oracle).
6. **Pan** + **per-op TL bias**.
7. **Portamento** (optional/last).
8. **The port**: extend `zyrinx_player.py` to emit the native MT song + pitch table + patch bank;
   wire `SONG_MOVINGTRUCKS` back in (streaming, FM6=FM).
9. **Final verification** vs the oracle (audio + spectrum) and the regression suite.

Each step builds, is verified in Exodus, and is committed. Merge to master when the port plays
faithfully and the regressions hold.
