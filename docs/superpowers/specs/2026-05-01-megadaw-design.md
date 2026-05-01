# MegaDAW — Mega Drive Digital Audio Workstation

**Date:** 2026-05-01
**Status:** Design approved
**Location:** `/home/volence/sonic_hacks/megadaw/`

## Overview

MegaDAW is a standalone DAW for composing Sega Genesis / Mega Drive music with cycle-accurate hardware emulation. Ableton-style workflow (arrangement view, piano rolls, plugin-style instrument editors) with a built-in YM2612 and SN76489 emulator so that what you hear in the DAW is exactly what plays in-game. No guesswork, no "export and hope" — the DAW IS the hardware.

Target audience: the Genesis dev and music community. No existing tool provides a proper DAW workflow for Genesis hardware — trackers like Furnace and Deflemask exist but use a tracker paradigm, not a modern DAW paradigm.

## Tech Stack

- **Framework:** Tauri (Rust backend + web frontend)
- **Frontend:** TypeScript + React
- **Audio core:** Rust, dedicated real-time thread via `cpal`
- **YM2612 emulation:** Nuked OPN2 (cycle-accurate, die-declapped)
- **SN76489 emulation:** Most accurate available Rust-compatible SN76489 emulator. Evaluate at implementation time: Nuked-SMS-PSG (same die-declap methodology as Nuked OPN2), BlipBuf-based emulators, or a direct port. Priority is accuracy over performance.
- **IPC model:** Frontend communicates with Rust backend via Tauri commands. Backend routes to audio engine via lock-free ring buffer. Audio thread never allocates, locks, or blocks.

## System Architecture

### Three Layers

**1. Frontend (TypeScript + React)**
The DAW UI. Arrangement view, piano rolls, instrument editors, mixer, transport controls. Communicates with the backend exclusively through Tauri IPC commands. No audio logic.

**2. Backend (Rust, Tauri host)**
Project state management (songs, tracks, instruments, samples). File I/O (save/load projects, import/export). Sequencer (reads arrangement data, dispatches note-on/off/parameter changes to the audio engine on a per-tick schedule). Driver profile management.

**3. Audio Engine (Rust, dedicated real-time thread)**
Nuked OPN2 + SN76489 emulation. Receives commands from the sequencer via a lock-free ring buffer. Renders audio samples and pushes them to OS audio output via `cpal`. Real-time safe — no allocation, no locks, no blocking.

### Data Flow — Playback

```
User hits Play
  → Frontend sends "play" via Tauri IPC
  → Backend sequencer reads arrangement data, advances tick-by-tick
  → Sequencer pushes note/param commands to lock-free ring buffer
  → Audio thread reads commands, writes YM2612/SN76489 registers
  → Emulators render samples → cpal → speakers
```

### Data Flow — Instrument Editing

```
User drags a knob in FM editor
  → Frontend sends "set_param(channel, operator, param, value)" via IPC
  → Backend forwards to audio engine ring buffer
  → Audio thread applies register write to Nuked OPN2
  → Change is audible immediately
```

## Driver Profile System

Each target engine/sound driver registers as a **driver backend** implementing a common trait. The driver profile declares:

- Available channel layout (how many FM, DAC, PSG channels)
- Supported features (SSG-EG, FM3 special mode, multi-DAC, pseudo-stereo, DPCM, etc.)
- Import formats it can read
- Export formats it can write
- Driver-specific metadata fields (e.g. section music ID, sound bank pointer)

The frontend queries the active driver profile to determine which UI controls to show/hide. The backend validates projects against the profile before export.

### Target Engine Selection

Project settings include a target engine selector. Changing the target engine reconfigures the DAW:

| Feature | Flamedriver (S4) | Generic SMPS | XGM2 (future) |
|---|---|---|---|
| FM channels | 5 (+ FM3 special = 6) | 5 | 4 |
| DAC channels | 2-3 (multi-mix) | 1 | 4 |
| PSG envelopes | S3K-style | S3K-style | XGM-style |
| Stereo panning | L/R per channel | L/R per channel | L/R per channel |
| Pseudo-stereo DAC | Yes | No | No |
| Frequency panning hints | Yes | No | No |
| SSG-EG envelopes | Yes | No | Depends |
| Continuous SFX flag | Yes | No | No |
| DPCM compression | Yes | No | Yes |
| Section music metadata | Yes | No | No |

Day one ships the **Flamedriver (Sonic 4)** backend. Architecture supports adding others without touching the core.

## Frontend — UI Layout

### Main Window

**Top bar:** Transport controls (play, stop, loop toggle), tempo/BPM, time signature, song position, project name, target engine selector.

**Center — Arrangement View:** Horizontal timeline with one row per channel. Fixed channel order based on active driver profile (FM1-5, DAC 1-N, PSG 1-3, Noise). Colored note regions. Zoom/scroll. Double-click a region to open in piano roll.

**Bottom panel — Editor area (swappable context):**
- **Piano roll** — opens on region double-click
- **Instrument editor** — opens on track instrument slot click
- **Mixer** — channel strips with volume, L/R panning, solo/mute

**Left sidebar:** Track list with instrument names, solo/mute buttons, color coding. Project file browser (instruments, samples).

### Arrangement View

- One row per hardware channel, labeled (FM1, FM2, ..., DAC1, PSG1, ..., Noise)
- Create regions by drawing or double-clicking on a track
- Regions can be moved, copied, duplicated, resized, split
- Color-coded by channel type (customizable)
- Loop markers on the timeline ruler
- Tempo track — special lane for mid-song tempo changes (BPM automation)

### Piano Roll

- Vertical piano keyboard on the left, time grid horizontally
- Draw notes with mouse, drag to resize/repitch
- Velocity lane at the bottom — per-note velocity bars
- For FM/PSG tracks: note range clamped to what the hardware can produce (impossible notes cannot be placed)
- For DAC tracks: vertical axis becomes a sample slot list (kick, snare, hat, etc.) — drum grid mode like Ableton
- Quantize snap: 1/1, 1/2, 1/4, 1/8, 1/16, triplets, off
- Per-channel effects lanes: volume changes, panning changes, modulation (vibrato depth/speed) — mapped directly to driver commands on export

### Hardware-Honest Mixing

The mixer and all controls reflect only what the Genesis hardware can do:
- Per-channel volume (FM total level, PSG volume)
- Stereo panning (hard left, hard right, or both — three states, not a knob)
- Software modulation envelopes (vibrato/tremolo via driver)
- Tempo changes

No reverb, EQ, compression, delay, or any effect that doesn't exist on hardware. What you hear is what you get.

## Instrument Editors

Three plugin-style panels. Each opens in the bottom editor area when you click a track's instrument slot. They feel like self-contained instrument plugins within the DAW.

### FM Synth Editor (YM2612)

- **Algorithm selector** — visual diagram showing the 8 operator routing configurations with connections drawn
- **4 operator panels**, each with:
  - Attack rate, decay rate, sustain rate, release rate (knobs)
  - Total level, rate scaling, multiply, detune (knobs)
  - Amplitude modulation toggle
  - SSG-EG mode selector with waveform preview (when driver supports it)
- **Envelope visualization** — drawn ADSR curve per operator, updates live on knob drag
- **Feedback level** knob
- **LFO sensitivity** per operator (AMS/FMS)
- **FM3 special mode toggle** (when driver supports it) — unlocks per-operator frequency fields
- **Preset browser** — factory + user presets, organized by category (bass, lead, pad, percussion, etc.)
- **Import button** — TFI, DMP, VGI, OPN, Y12, Furnace .fui formats
- **Audition keyboard** — click notes to preview the patch through Nuked OPN2

### PSG Envelope Editor (SN76489)

- **Volume envelope** — drawable curve (sequence of volume values per tick)
- **Noise mode** — periodic vs white noise toggle, tone period selector
- **Audition trigger** — click to preview

### DAC Sample Editor

- **Waveform display** of loaded sample
- **Trim controls** — start/end points, loop point marker
- **Target sample rate selector** (8kHz, 11kHz, 16kHz, 23kHz, 32kHz) — re-renders preview through DAC emulation on change
- **DPCM compression toggle** (when driver supports it) — A/B the compressed vs raw version
- **Pitch control** for pitch-shifted playback
- **Import** — WAV/AIFF with auto-conversion, or pre-converted Genesis-format samples
- **Visual comparison** — original waveform overlaid with what-the-Genesis-will-play waveform

## Import / Export System

Pluggable architecture — each driver backend registers importers and exporters. The core DAW never knows about format specifics.

### Day-One Importers (Flamedriver/SMPS Backend)

- **SMPS2ASM text files** — parse macro format, map channels/notes/instruments/volumes/modulation to internal model
- **SMPS binary** — parse raw binary format
- **FM instrument formats** — TFI, DMP, VGI, OPN, Y12, Furnace .fui → FM presets
- **WAV/AIFF samples** — auto-convert to target DAC format with real-time preview
- **Pre-converted Genesis samples** — raw PCM, DPCM passthrough

### Day-One Exporters

- **SMPS2ASM text** — human-readable, debuggable, plugs into build pipelines
- **SMPS binary** — ready for direct ROM inclusion

### SMPS Instrument Handling

FM instruments in SMPS are embedded in the song data as a "voice table" — 25 bytes per patch containing raw YM2612 register values (algorithm, feedback, per-operator detune/multiply/TL/RS/AR/DR/SR/RR/SL/SSG-EG). Import extracts these automatically. Export writes them back.

PSG envelopes are also embedded in song data as volume envelope sequences.

DAC samples are separate files referenced by a sample table (sample ID → address + length + rate).

### Test Corpus

S.C.E. Flamedriver branch S3K tracks for round-trip validation: import → play in MegaDAW → export → confirm match.

### Future Formats (architecture supports, not built day one)

- XGM/XGM2, VGM, TFM Music Maker, MDSDRV, Echo
- MIDI import (when MIDI input support lands)

## Standard DAW Features

All of these are essential for v1:

- **Undo/redo** (Ctrl+Z / Ctrl+Shift+Z) — full action history
- **Copy/paste** — notes, regions, across tracks or within
- **Quantize** — snap notes to grid (1/4, 1/8, 1/16, triplets, etc.)
- **Loop playback** — set loop region on timeline, playback repeats
- **Solo/mute** per track — isolate channels
- **Tempo/time signature** — set BPM, time sig, tempo changes mid-song
- All other standard DAW workflow features users expect

## MIDI Support

Architecture designed to support MIDI input from day one. Actual MIDI implementation deferred to a future version. When shipped: plug in a MIDI keyboard, select a track, play notes live into the piano roll with real-time Nuked OPN2 preview.

## Project File Structure

One song per project. Project is a self-contained folder:

```
my-song/
├── project.json            ← song metadata, tempo, time sig, target engine,
│                             arrangement (tracks, regions, notes)
├── instruments/
│   ├── fm/
│   │   ├── bass-01.json        ← FM patch (YM2612 params + metadata)
│   │   └── lead-bright.json
│   ├── psg/
│   │   └── pluck-01.json       ← PSG volume envelope + settings
│   └── dac/
│       ├── kick.json           ← sample metadata (rate, loop, DPCM toggle)
│       ├── kick.wav            ← original source sample
│       └── kick.pcm            ← converted Genesis-format (generated)
├── exports/                    ← generated output
│   ├── smps2asm/
│   │   └── my-song.asm
│   └── binary/
│       └── my-song.bin
└── .megadaw                    ← version marker
```

### Global Library

```
~/.megadaw/
├── library/
│   ├── fm/                 ← shared FM presets across all projects
│   ├── psg/
│   └── dac/
├── drivers/                ← installed driver backends
└── config.json             ← app preferences, audio settings, recent projects
```

Using a global library instrument in a project copies it into the project folder. Projects are always self-contained and shareable.

### File Formats

JSON for all human-readable data (project, instruments, config). Binary only for audio samples and generated exports. Everything is inspectable, diffable, and version-controllable.
