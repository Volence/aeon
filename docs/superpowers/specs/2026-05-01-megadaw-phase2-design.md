# MegaDAW Phase 2: Project Model + Backend

**Parent spec:** [2026-05-01-megadaw-design.md](2026-05-01-megadaw-design.md)

**Goal:** Internal data model, project persistence, driver profile system, instrument management (FM/PSG/DAC), and DAC sample conversion pipeline. Deliverable: "create a project, add instruments, preview them through the emulator, save, reload, instruments still there."

**Phase 1 baseline:** Tauri v2 + React app at `/home/volence/sonic_hacks/megadaw/` with working YM2612 (Nuked OPN2) + SN76489 (pure Rust) audio engine on a real-time cpal thread. IPC commands for test tones + panic. 10 tests passing.

---

## 1. Data Model

All structs derive `Serialize`, `Deserialize`, `Clone`. UUIDs via the `uuid` crate (v4).

### 1.1 Song (top-level)

```rust
struct Song {
    metadata: SongMetadata,
    tracks: Vec<Track>,
    instruments: InstrumentBank,
}

struct SongMetadata {
    name: String,
    tempo: f64,              // BPM
    time_signature: (u8, u8), // (numerator, denominator)
    ticks_per_beat: u32,     // 480 (standard MIDI resolution)
    driver_id: String,       // "flamedriver"
}
```

### 1.2 Track / Region / Note

```rust
struct Track {
    id: Uuid,
    name: String,
    channel: ChannelAssignment,
    instrument_id: Option<Uuid>,
    regions: Vec<Region>,
    muted: bool,
    solo: bool,
    volume: u8,   // 0-127
    pan: Pan,      // Left, Right, Center
}

enum ChannelAssignment {
    Fm(u8),       // 0-5 (channel 5 = DAC-capable on hardware)
    Psg(u8),      // 0-2
    PsgNoise,
    Dac(u8),      // 0-2 (multi-DAC when driver supports)
}

enum Pan {
    Left,
    Right,
    Center,
}

struct Region {
    id: Uuid,
    start_tick: u64,
    duration_ticks: u64,
    notes: Vec<Note>,
}

struct Note {
    tick: u64,            // relative to region start
    pitch: u8,            // MIDI note number 0-127
    velocity: u8,         // 0-127
    duration_ticks: u64,
}
```

Tracks, regions, and notes are fully defined now but will be empty arrays in Phase 2 projects. Phase 3 (sequencer) populates them.

### 1.3 Instrument Bank

```rust
struct InstrumentBank {
    fm: Vec<FmInstrument>,
    psg: Vec<PsgInstrument>,
    dac: Vec<DacInstrument>,
}
```

### 1.4 FM Instrument

Maps 1:1 to the YM2612 register set. Field ranges match hardware bit widths.

```rust
struct FmInstrument {
    id: Uuid,
    name: String,
    algorithm: u8,     // 0-7
    feedback: u8,      // 0-7
    operators: [FmOperator; 4],
    metadata: InstrumentMetadata,
}

struct FmOperator {
    detune: u8,         // 0-7
    multiple: u8,       // 0-15
    rate_scale: u8,     // 0-3
    attack_rate: u8,    // 0-31
    amp_mod: bool,
    d1r: u8,            // 0-31 (first decay rate)
    d2r: u8,            // 0-31 (second decay rate)
    sustain_level: u8,  // 0-15
    release_rate: u8,   // 0-15
    total_level: u8,    // 0-127
}
```

### 1.5 PSG Instrument

```rust
struct PsgInstrument {
    id: Uuid,
    name: String,
    volume_sequence: Vec<u8>,    // 0-15 per tick
    loop_point: Option<usize>,   // index to loop back to, None = one-shot
    noise_mode: Option<NoiseMode>,
    metadata: InstrumentMetadata,
}

enum NoiseMode {
    Periodic(u16),  // with tone period
    White(u16),
}
```

### 1.6 DAC Instrument

```rust
struct DacInstrument {
    id: Uuid,
    name: String,
    target_sample_rate: u32,  // 8000, 11025, 16000, 22050, 32000
    loop_start: Option<u32>,  // sample index
    loop_length: Option<u32>,
    original_file: String,    // relative path to source (.wav or .pcm)
    pcm_file: String,         // relative path to converted Genesis .pcm
    source_is_raw: bool,      // true if imported as pre-converted PCM
    metadata: InstrumentMetadata,
}
```

### 1.7 Shared Metadata

```rust
struct InstrumentMetadata {
    category: String,
    author: String,
    tags: Vec<String>,
}
```

---

## 2. Driver Profile System

### 2.1 Trait

```rust
trait DriverProfile: Send + Sync {
    fn name(&self) -> &str;
    fn id(&self) -> &str;
    fn channel_layout(&self) -> ChannelLayout;
    fn supports_feature(&self, feature: DriverFeature) -> bool;

    fn validate_fm(&self, inst: &FmInstrument) -> Result<(), Vec<String>>;
    fn validate_psg(&self, inst: &PsgInstrument) -> Result<(), Vec<String>>;
    fn validate_dac(&self, inst: &DacInstrument) -> Result<(), Vec<String>>;

    fn fm_to_bytes(&self, inst: &FmInstrument) -> Vec<u8>;
    fn fm_from_bytes(&self, bytes: &[u8]) -> Result<FmInstrument, String>;

    fn import_formats(&self) -> Vec<&str>;
    fn export_formats(&self) -> Vec<&str>;
}
```

### 2.2 Supporting Types

```rust
struct ChannelLayout {
    fm_channels: Vec<FmChannelInfo>,
    psg_channels: Vec<PsgChannelInfo>,
    dac_channels: Vec<DacChannelInfo>,
}

struct FmChannelInfo {
    index: u8,
    name: String,
    supports_special_mode: bool, // FM3 only
}

struct PsgChannelInfo {
    index: u8,
    name: String,
    is_noise: bool,
}

struct DacChannelInfo {
    index: u8,
    name: String,
}

enum DriverFeature {
    SsgEg,
    Fm3SpecialMode,
    MultiDac,
    Dpcm,
    PseudoStereo,
}
```

### 2.3 Driver Registry

```rust
struct DriverRegistry {
    drivers: HashMap<String, Box<dyn DriverProfile>>,
}
```

Phase 2 ships with one entry: `"flamedriver"`.

### 2.4 Flamedriver Implementation

**Channel layout:**
- FM1-FM5 (indices 0-4), FM6/DAC (index 5)
- FM3 special mode supported (index 2)
- PSG1-PSG3 (indices 0-2) + PSG Noise
- DAC × 1 (single DAC, no multi-DAC yet)

**Features supported:** `Fm3SpecialMode`. Not supported: `SsgEg`, `MultiDac`, `Dpcm`, `PseudoStereo`.

**fm_to_bytes — 25-byte voice table packing:**

The Flamedriver/SMPS voice format (S3K-derived) packs operators in register-write order: 4→3→2→1. Algorithm/feedback is the **last** byte (matching S3K smpsVcAlgorithm macro output order).

```
Bytes 0-3:   DT/MUL for ops 4,3,2,1 — each: (detune << 4) | multiple
Bytes 4-7:   RS/AR for ops 4,3,2,1 — each: (rate_scale << 6) | attack_rate
Bytes 8-11:  AM/D1R for ops 4,3,2,1 — each: (amp_mod << 7) | d1r
Bytes 12-15: D2R for ops 4,3,2,1
Bytes 16-19: SL/RR for ops 4,3,2,1 — each: (sustain_level << 4) | release_rate
Bytes 20-23: TL for ops 4,3,2,1 — each: total_level | (carrier_flag << 7)
Byte  24:    (feedback << 3) | algorithm
```

**TL carrier flag (bit 7):** Set on operators that are carriers for the given algorithm. This tells the driver which TL values to adjust for channel volume scaling. Carrier assignments per algorithm:

| Algorithm | Carriers (bit 7 set) |
|-----------|---------------------|
| 0         | Op 4                |
| 1         | Op 4                |
| 2         | Op 4                |
| 3         | Op 4                |
| 4         | Op 2, 4             |
| 5         | Op 2, 3, 4          |
| 6         | Op 2, 3, 4          |
| 7         | Op 1, 2, 3, 4       |

**fm_from_bytes:** Unpacks the same 25-byte format, enabling import from existing S3K/Flamedriver songs.

**Validation rules:**
- All FM operator fields within hardware bit widths
- Warn (not error) if all carrier TLs are 0x7F (instrument is silent)
- PSG volume sequence length > 0
- DAC target sample rate in allowed set {8000, 11025, 16000, 22050, 32000}

---

## 3. Project Persistence

### 3.1 Folder Structure

```
my-song/
├── .megadaw                  # { "version": "0.1.0" }
├── project.json              # metadata + tracks/regions/notes
├── instruments/
│   ├── fm/
│   │   └── {uuid}.json
│   ├── psg/
│   │   └── {uuid}.json
│   └── dac/
│       ├── {uuid}.json       # metadata
│       ├── {uuid}.wav        # original source (WAV imports)
│       ├── {uuid}.raw        # original source (raw PCM imports)
│       └── {uuid}.pcm        # converted Genesis 8-bit unsigned
└── exports/                  # generated, not saved in project.json
```

### 3.2 project.json Schema

```json
{
  "metadata": {
    "name": "My Song",
    "tempo": 120.0,
    "timeSignature": [4, 4],
    "ticksPerBeat": 480,
    "driverId": "flamedriver"
  },
  "tracks": [
    {
      "id": "uuid",
      "name": "FM Lead",
      "channel": { "Fm": 0 },
      "instrumentId": "uuid-or-null",
      "regions": [],
      "muted": false,
      "solo": false,
      "volume": 100,
      "pan": "Center"
    }
  ]
}
```

Instruments are NOT embedded in project.json — they're referenced by UUID and stored as separate files in `instruments/`.

### 3.3 Instrument File Example (FM)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "DEZ Bass",
  "algorithm": 0,
  "feedback": 2,
  "operators": [
    {
      "detune": 4, "multiple": 1, "rateScale": 0,
      "attackRate": 31, "ampMod": false,
      "d1r": 4, "d2r": 0, "sustainLevel": 1,
      "releaseRate": 8, "totalLevel": 5
    },
    {
      "detune": 6, "multiple": 4, "rateScale": 1,
      "attackRate": 31, "ampMod": false,
      "d1r": 8, "d2r": 15, "sustainLevel": 5,
      "releaseRate": 8, "totalLevel": 28
    },
    {
      "detune": 5, "multiple": 0, "rateScale": 0,
      "attackRate": 31, "ampMod": false,
      "d1r": 8, "d2r": 0, "sustainLevel": 3,
      "releaseRate": 8, "totalLevel": 37
    },
    {
      "detune": 4, "multiple": 5, "rateScale": 0,
      "attackRate": 31, "ampMod": false,
      "d1r": 4, "d2r": 0, "sustainLevel": 1,
      "releaseRate": 8, "totalLevel": 32
    }
  ],
  "metadata": {
    "category": "bass",
    "author": "",
    "tags": []
  }
}
```

### 3.4 ProjectManager

```rust
struct ProjectManager {
    project_path: Option<PathBuf>,
    song: Option<Song>,
    dirty_instruments: HashSet<Uuid>,
    driver_registry: DriverRegistry,
}
```

**Operations:**
- `create(path, name, driver_id, tempo, time_sig)` — create directories, write .megadaw + empty project.json
- `open(path)` — validate .megadaw exists, load project.json, scan instruments/ and load all JSONs, load DAC .pcm files into memory for preview
- `save()` — write project.json, write only dirty instrument files, clear dirty set
- `close()` — drop song, clear state

Instruments are loaded into memory on project open. DAC PCM data is loaded as `Vec<u8>` for preview playback.

---

## 4. DAC Conversion Pipeline

### 4.1 Import Paths

**WAV import (`import_dac_wav`):**
1. Read WAV with `hound` crate
2. If stereo, mix to mono (average L+R)
3. Convert samples to f32 normalized (-1.0 to 1.0)
4. Resample from source rate to target rate via linear interpolation
5. Quantize to 8-bit unsigned (0-255, center at 128)
6. Write .pcm file
7. Copy original .wav into project
8. Create DacInstrument metadata JSON

**Raw PCM import (`import_dac_raw`):**
1. Copy .raw file into project
2. Copy same bytes as .pcm (already Genesis format)
3. User specifies sample rate (default 16000)
4. Create DacInstrument metadata JSON with `source_is_raw: true`

### 4.2 Re-conversion

When user changes target sample rate on a WAV-sourced sample:
1. Re-read original .wav from project
2. Re-run resample + quantize at new rate
3. Overwrite .pcm file

Raw PCM imports cannot be re-converted (no higher-quality source to resample from). Changing rate on a raw import only changes the playback speed metadata.

### 4.3 Preview

New `AudioCommand` variant:

```rust
AudioCommand::DacPlayback {
    samples: Arc<Vec<u8>>,   // 8-bit unsigned PCM
    sample_rate: u32,
}
```

The audio engine renders DAC samples at the specified rate by stepping through the buffer at `sample_rate / output_rate` increments per output frame. DAC output replaces FM channel 6 (matching real hardware behavior). Mixed alongside FM+PSG using the same scaling as Phase 1.

### 4.4 Dependencies

- `hound` crate for WAV reading (pure Rust, no system deps)
- `uuid` crate with `v4` feature for instrument IDs

---

## 5. Tauri IPC Commands

All commands return `Result<T, String>`. State managed via `Mutex<ProjectManager>` in Tauri app state (alongside existing `Mutex<AudioThread>`).

### 5.1 Project Management

| Command | Parameters | Returns |
|---------|-----------|---------|
| `create_project` | path, name, driver_id, tempo, time_sig | `()` |
| `open_project` | path | Song JSON |
| `save_project` | — | `()` |
| `close_project` | — | `()` |
| `get_project_info` | — | Option<SongMetadata> |

### 5.2 FM Instruments

| Command | Parameters | Returns |
|---------|-----------|---------|
| `add_fm_instrument` | FmInstrument JSON (no id) | Uuid |
| `update_fm_instrument` | id, FmInstrument JSON | `()` |
| `delete_fm_instrument` | id | `()` |
| `list_fm_instruments` | — | Vec<FmInstrument> |
| `preview_fm_instrument` | id, midi_note | `()` |

### 5.3 PSG Instruments

| Command | Parameters | Returns |
|---------|-----------|---------|
| `add_psg_instrument` | PsgInstrument JSON (no id) | Uuid |
| `update_psg_instrument` | id, PsgInstrument JSON | `()` |
| `delete_psg_instrument` | id | `()` |
| `list_psg_instruments` | — | Vec<PsgInstrument> |
| `preview_psg_instrument` | id, midi_note | `()` |

### 5.4 DAC Instruments

| Command | Parameters | Returns |
|---------|-----------|---------|
| `import_dac_wav` | wav_path, target_rate | Uuid |
| `import_dac_raw` | pcm_path, sample_rate | Uuid |
| `update_dac_instrument` | id, metadata JSON | `()` |
| `reconvert_dac` | id, new_rate | `()` |
| `delete_dac_instrument` | id | `()` |
| `list_dac_instruments` | — | Vec<DacInstrument> |
| `preview_dac` | id | `()` |

### 5.5 Driver Info

| Command | Parameters | Returns |
|---------|-----------|---------|
| `list_drivers` | — | Vec<{id, name}> |
| `get_driver_info` | driver_id | ChannelLayout + features |

### 5.6 Audio (extending Phase 1)

| Command | Parameters | Returns |
|---------|-----------|---------|
| `stop_all_sound` | — | `()` |

Phase 1 test tone commands (`play_fm_test_tone`, `play_psg_test_tone`) remain but are superseded by the instrument preview commands.

### 5.7 MIDI Note to Hardware Frequency

Preview commands accept a MIDI note number (0-127) and must convert to hardware frequency encoding:

**FM (YM2612):** MIDI note → block (octave) + F-number. Formula: `F-num = (freq * 2^20) / (master_clock / 144)` where `master_clock = 7,670,453 / 2`. Block = octave (0-7). A lookup table of F-numbers for one octave (12 notes) is the cleanest approach — shift block for other octaves.

**PSG (SN76489):** MIDI note → 10-bit tone period. Formula: `period = master_clock / (32 * freq)` where `master_clock = 3,579,545`. Again, a lookup table for all 128 MIDI notes avoids runtime float math.

Both tables are computed once at startup or as const arrays.

---

## 6. New Crate Dependencies

| Crate | Purpose | Features |
|-------|---------|----------|
| `uuid` | Instrument/track/region IDs | `v4`, `serde` |
| `hound` | WAV file reading | — |
| `serde` | Serialization | `derive` (already present) |
| `serde_json` | JSON read/write | — (already present) |

---

## 7. Module Organization

New files in `src-tauri/src/`:

```
src-tauri/src/
├── model/
│   ├── mod.rs              # re-exports
│   ├── song.rs             # Song, SongMetadata, Track, Region, Note, Pan, ChannelAssignment
│   ├── instrument.rs       # InstrumentBank, FmInstrument, FmOperator, PsgInstrument, DacInstrument, NoiseMode, InstrumentMetadata
│   └── driver.rs           # DriverProfile trait, ChannelLayout, DriverFeature, DriverRegistry
├── driver/
│   ├── mod.rs
│   └── flamedriver.rs      # Flamedriver DriverProfile implementation
├── project/
│   ├── mod.rs
│   └── manager.rs          # ProjectManager (create/open/save/close)
├── dac/
│   ├── mod.rs
│   └── pipeline.rs         # WAV import, raw import, resample, quantize
├── audio/                  # existing Phase 1
│   ├── command.rs          # + DacPlayback variant
│   ├── engine.rs           # + DAC rendering
│   └── thread.rs
├── ipc/
│   └── commands.rs         # Phase 1 commands + all Phase 2 commands
└── lib.rs                  # register new commands + ProjectState
```

---

## 8. What's NOT in Phase 2

- Arrangement view UI (Phase 3)
- Piano roll UI (Phase 3)
- Sequencer playback engine (Phase 3)
- FM/PSG/DAC instrument editor UI panels (Phase 3+)
- SMPS full-song import/export (Phase 4+)
- Global preset library (~/.megadaw/library/)
- TFI/DMP/VGI/OPN/Y12 format importers
- DPCM compression
- AIFF import
- MIDI input
