# MegaDAW Phase 2: Project Model + Backend — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add internal data model, project persistence, driver profiles, instrument management, and DAC conversion so users can create projects, add instruments, preview through the emulator, save, and reload.

**Architecture:** Rust backend modules (model, driver, project, dac) behind Tauri IPC commands. All state lives in `ProjectManager` + `AudioThread`, bridged to React frontend via `invoke()`. No frontend UI changes beyond IPC wiring — Phase 3 adds the actual DAW interface.

**Tech Stack:** Rust, Tauri v2, serde/serde_json, uuid v1, hound (WAV), cpal, rtrb, Nuked OPN2 (FFI), pure Rust SN76489

---

## File Structure

```
src-tauri/src/
├── model/
│   ├── mod.rs              # re-exports all model types
│   ├── song.rs             # Song, SongMetadata, ProjectFile, Track, Region, Note, Pan, ChannelAssignment
│   ├── instrument.rs       # InstrumentBank, FmInstrument, FmOperator, PsgInstrument, DacInstrument, NoiseMode, InstrumentMetadata
│   └── driver.rs           # DriverProfile trait, ChannelLayout, DriverFeature, DriverRegistry
├── driver/
│   ├── mod.rs              # re-exports FlamedriverProfile
│   └── flamedriver.rs      # Flamedriver DriverProfile impl (25-byte voice packing, validation)
├── project/
│   ├── mod.rs              # re-exports ProjectManager
│   └── manager.rs          # ProjectManager (create/open/save/close, instrument CRUD, DAC PCM cache)
├── dac/
│   ├── mod.rs              # re-exports pipeline functions
│   └── pipeline.rs         # resample(), quantize_u8(), import_wav(), import_raw()
├── audio/
│   ├── mod.rs              # add frequency module export
│   ├── command.rs          # add DacPlayback, PsgEnvelopePreview, StopPreview variants
│   ├── engine.rs           # add DAC rendering + PSG envelope stepping
│   ├── thread.rs           # unchanged
│   └── frequency.rs        # NEW: midi_to_fm_freq(), midi_to_psg_period()
├── ipc/
│   ├── mod.rs              # export all new commands
│   └── commands.rs         # Phase 1 commands + 18 new Phase 2 commands
└── lib.rs                  # register new modules, state, and commands
```

---

### Task 1: Data Model Structs

**Files:**
- Modify: `src-tauri/Cargo.toml:21-27` (add uuid, hound)
- Create: `src-tauri/src/model/mod.rs`
- Create: `src-tauri/src/model/song.rs`
- Create: `src-tauri/src/model/instrument.rs`
- Modify: `src-tauri/src/lib.rs:1` (add `mod model;`)

- [ ] **Step 1: Add uuid and hound dependencies to Cargo.toml**

Add after the `rtrb` line in `[dependencies]`:

```toml
uuid = { version = "1", features = ["v4", "serde"] }
hound = "3.5"
```

- [ ] **Step 2: Create model/mod.rs**

Create `src-tauri/src/model/mod.rs`:

```rust
pub mod song;
pub mod instrument;
pub mod driver;

pub use song::*;
pub use instrument::*;
pub use driver::*;
```

- [ ] **Step 3: Create model/song.rs with all song types**

Create `src-tauri/src/model/song.rs`:

```rust
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use super::instrument::InstrumentBank;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SongMetadata {
    pub name: String,
    pub tempo: f64,
    pub time_signature: (u8, u8),
    pub ticks_per_beat: u32,
    pub driver_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Track {
    pub id: Uuid,
    pub name: String,
    pub channel: ChannelAssignment,
    pub instrument_id: Option<Uuid>,
    pub regions: Vec<Region>,
    pub muted: bool,
    pub solo: bool,
    pub volume: u8,
    pub pan: Pan,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ChannelAssignment {
    Fm(u8),
    Psg(u8),
    PsgNoise,
    Dac(u8),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Pan {
    Left,
    Right,
    Center,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Region {
    pub id: Uuid,
    pub start_tick: u64,
    pub duration_ticks: u64,
    pub notes: Vec<Note>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Note {
    pub tick: u64,
    pub pitch: u8,
    pub velocity: u8,
    pub duration_ticks: u64,
}

/// On-disk format for project.json (no instruments — they're separate files).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectFile {
    pub metadata: SongMetadata,
    pub tracks: Vec<Track>,
}

/// Full in-memory song representation including instruments.
#[derive(Debug, Clone, Serialize)]
pub struct Song {
    pub metadata: SongMetadata,
    pub tracks: Vec<Track>,
    pub instruments: InstrumentBank,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_song_metadata_json_round_trip() {
        let meta = SongMetadata {
            name: "Test Song".into(),
            tempo: 140.0,
            time_signature: (4, 4),
            ticks_per_beat: 480,
            driver_id: "flamedriver".into(),
        };
        let json = serde_json::to_string(&meta).unwrap();
        assert!(json.contains("\"ticksPerBeat\":480"));
        assert!(json.contains("\"driverId\":\"flamedriver\""));
        let parsed: SongMetadata = serde_json::from_str(&json).unwrap();
        assert_eq!(parsed.tempo, 140.0);
        assert_eq!(parsed.ticks_per_beat, 480);
    }

    #[test]
    fn test_project_file_json_round_trip() {
        let pf = ProjectFile {
            metadata: SongMetadata {
                name: "Test".into(),
                tempo: 120.0,
                time_signature: (3, 4),
                ticks_per_beat: 480,
                driver_id: "flamedriver".into(),
            },
            tracks: vec![Track {
                id: Uuid::new_v4(),
                name: "FM1".into(),
                channel: ChannelAssignment::Fm(0),
                instrument_id: None,
                regions: vec![],
                muted: false,
                solo: false,
                volume: 100,
                pan: Pan::Center,
            }],
        };
        let json = serde_json::to_string_pretty(&pf).unwrap();
        let parsed: ProjectFile = serde_json::from_str(&json).unwrap();
        assert_eq!(parsed.tracks.len(), 1);
        assert_eq!(parsed.tracks[0].name, "FM1");
        assert!(matches!(parsed.tracks[0].channel, ChannelAssignment::Fm(0)));
    }

    #[test]
    fn test_channel_assignment_serialization() {
        let fm = ChannelAssignment::Fm(3);
        let json = serde_json::to_string(&fm).unwrap();
        assert_eq!(json, r#"{"Fm":3}"#);

        let noise = ChannelAssignment::PsgNoise;
        let json = serde_json::to_string(&noise).unwrap();
        assert_eq!(json, r#""PsgNoise""#);
    }
}
```

- [ ] **Step 4: Create model/instrument.rs with all instrument types**

Create `src-tauri/src/model/instrument.rs`:

```rust
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct InstrumentBank {
    pub fm: Vec<FmInstrument>,
    pub psg: Vec<PsgInstrument>,
    pub dac: Vec<DacInstrument>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FmInstrument {
    pub id: Uuid,
    pub name: String,
    pub algorithm: u8,
    pub feedback: u8,
    pub operators: [FmOperator; 4],
    pub metadata: InstrumentMetadata,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FmOperator {
    pub detune: u8,
    pub multiple: u8,
    pub rate_scale: u8,
    pub attack_rate: u8,
    pub amp_mod: bool,
    pub d1r: u8,
    pub d2r: u8,
    pub sustain_level: u8,
    pub release_rate: u8,
    pub total_level: u8,
}

impl Default for FmOperator {
    fn default() -> Self {
        Self {
            detune: 0, multiple: 0, rate_scale: 0, attack_rate: 0,
            amp_mod: false, d1r: 0, d2r: 0, sustain_level: 0,
            release_rate: 0, total_level: 127,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PsgInstrument {
    pub id: Uuid,
    pub name: String,
    pub volume_sequence: Vec<u8>,
    pub loop_point: Option<usize>,
    pub noise_mode: Option<NoiseMode>,
    pub metadata: InstrumentMetadata,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum NoiseMode {
    Periodic(u16),
    White(u16),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DacInstrument {
    pub id: Uuid,
    pub name: String,
    pub target_sample_rate: u32,
    pub loop_start: Option<u32>,
    pub loop_length: Option<u32>,
    pub original_file: String,
    pub pcm_file: String,
    pub source_is_raw: bool,
    pub metadata: InstrumentMetadata,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct InstrumentMetadata {
    pub category: String,
    pub author: String,
    pub tags: Vec<String>,
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_fm_operator() -> FmOperator {
        FmOperator {
            detune: 4, multiple: 1, rate_scale: 0, attack_rate: 31,
            amp_mod: false, d1r: 4, d2r: 0, sustain_level: 1,
            release_rate: 8, total_level: 5,
        }
    }

    #[test]
    fn test_fm_instrument_json_round_trip() {
        let inst = FmInstrument {
            id: Uuid::new_v4(),
            name: "DEZ Bass".into(),
            algorithm: 0,
            feedback: 2,
            operators: [test_fm_operator(), test_fm_operator(), test_fm_operator(), test_fm_operator()],
            metadata: InstrumentMetadata::default(),
        };
        let json = serde_json::to_string_pretty(&inst).unwrap();
        assert!(json.contains("\"attackRate\":31"));
        assert!(json.contains("\"ampMod\":false"));
        let parsed: FmInstrument = serde_json::from_str(&json).unwrap();
        assert_eq!(parsed.algorithm, 0);
        assert_eq!(parsed.operators[0].detune, 4);
    }

    #[test]
    fn test_psg_instrument_json_round_trip() {
        let inst = PsgInstrument {
            id: Uuid::new_v4(),
            name: "Pluck".into(),
            volume_sequence: vec![15, 14, 12, 10, 8, 6, 4, 2, 0],
            loop_point: Some(5),
            noise_mode: None,
            metadata: InstrumentMetadata::default(),
        };
        let json = serde_json::to_string(&inst).unwrap();
        let parsed: PsgInstrument = serde_json::from_str(&json).unwrap();
        assert_eq!(parsed.volume_sequence.len(), 9);
        assert_eq!(parsed.loop_point, Some(5));
    }

    #[test]
    fn test_dac_instrument_json_round_trip() {
        let inst = DacInstrument {
            id: Uuid::new_v4(),
            name: "Kick".into(),
            target_sample_rate: 16000,
            loop_start: None,
            loop_length: None,
            original_file: "kick.wav".into(),
            pcm_file: "kick.pcm".into(),
            source_is_raw: false,
            metadata: InstrumentMetadata::default(),
        };
        let json = serde_json::to_string(&inst).unwrap();
        assert!(json.contains("\"targetSampleRate\":16000"));
        assert!(json.contains("\"sourceIsRaw\":false"));
        let parsed: DacInstrument = serde_json::from_str(&json).unwrap();
        assert_eq!(parsed.target_sample_rate, 16000);
    }

    #[test]
    fn test_instrument_bank_default_is_empty() {
        let bank = InstrumentBank::default();
        assert!(bank.fm.is_empty());
        assert!(bank.psg.is_empty());
        assert!(bank.dac.is_empty());
    }
}
```

- [ ] **Step 5: Add `mod model;` to lib.rs**

Add `mod model;` at line 1 of `src-tauri/src/lib.rs` (before `mod audio;`).

- [ ] **Step 6: Run tests to verify everything compiles and passes**

Run: `cd /home/volence/sonic_hacks/megadaw/src-tauri && cargo test -- --lib model`
Expected: all tests PASS

- [ ] **Step 7: Commit**

```bash
git add src-tauri/Cargo.toml src-tauri/src/model/ src-tauri/src/lib.rs
git commit -m "feat(model): data model structs — Song, Track, FM/PSG/DAC instruments"
```

---

### Task 2: Driver Profile Trait + Flamedriver Backend

**Files:**
- Create: `src-tauri/src/model/driver.rs`
- Create: `src-tauri/src/driver/mod.rs`
- Create: `src-tauri/src/driver/flamedriver.rs`
- Modify: `src-tauri/src/lib.rs` (add `mod driver;`)

- [ ] **Step 1: Create model/driver.rs with trait and types**

Create `src-tauri/src/model/driver.rs`:

```rust
use std::collections::HashMap;
use serde::Serialize;
use super::instrument::{DacInstrument, FmInstrument, PsgInstrument};

pub trait DriverProfile: Send + Sync {
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

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ChannelLayout {
    pub fm_channels: Vec<FmChannelInfo>,
    pub psg_channels: Vec<PsgChannelInfo>,
    pub dac_channels: Vec<DacChannelInfo>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FmChannelInfo {
    pub index: u8,
    pub name: String,
    pub supports_special_mode: bool,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PsgChannelInfo {
    pub index: u8,
    pub name: String,
    pub is_noise: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct DacChannelInfo {
    pub index: u8,
    pub name: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum DriverFeature {
    SsgEg,
    Fm3SpecialMode,
    MultiDac,
    Dpcm,
    PseudoStereo,
}

pub struct DriverRegistry {
    drivers: HashMap<String, Box<dyn DriverProfile>>,
}

impl DriverRegistry {
    pub fn new() -> Self {
        Self {
            drivers: HashMap::new(),
        }
    }

    pub fn register(&mut self, driver: Box<dyn DriverProfile>) {
        self.drivers.insert(driver.id().to_string(), driver);
    }

    pub fn get(&self, id: &str) -> Option<&dyn DriverProfile> {
        self.drivers.get(id).map(|d| d.as_ref())
    }

    pub fn list(&self) -> Vec<(&str, &str)> {
        self.drivers.values().map(|d| (d.id(), d.name())).collect()
    }
}
```

- [ ] **Step 2: Write Flamedriver tests first (TDD)**

Create `src-tauri/src/driver/flamedriver.rs` with tests only:

```rust
use crate::model::driver::*;
use crate::model::instrument::*;
use uuid::Uuid;

pub struct FlamedriverProfile;

// Placeholder impl to make tests compile — will be filled in Step 3
impl DriverProfile for FlamedriverProfile {
    fn name(&self) -> &str { todo!() }
    fn id(&self) -> &str { todo!() }
    fn channel_layout(&self) -> ChannelLayout { todo!() }
    fn supports_feature(&self, _: DriverFeature) -> bool { todo!() }
    fn validate_fm(&self, _: &FmInstrument) -> Result<(), Vec<String>> { todo!() }
    fn validate_psg(&self, _: &PsgInstrument) -> Result<(), Vec<String>> { todo!() }
    fn validate_dac(&self, _: &DacInstrument) -> Result<(), Vec<String>> { todo!() }
    fn fm_to_bytes(&self, _: &FmInstrument) -> Vec<u8> { todo!() }
    fn fm_from_bytes(&self, _: &[u8]) -> Result<FmInstrument, String> { todo!() }
    fn import_formats(&self) -> Vec<&str> { todo!() }
    fn export_formats(&self) -> Vec<&str> { todo!() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_test_instrument() -> FmInstrument {
        FmInstrument {
            id: Uuid::nil(),
            name: "Test".into(),
            algorithm: 4,
            feedback: 5,
            operators: [
                FmOperator { detune: 1, multiple: 2, rate_scale: 0, attack_rate: 31, amp_mod: false, d1r: 5, d2r: 3, sustain_level: 2, release_rate: 8, total_level: 10 },
                FmOperator { detune: 3, multiple: 4, rate_scale: 1, attack_rate: 28, amp_mod: true, d1r: 7, d2r: 5, sustain_level: 4, release_rate: 10, total_level: 20 },
                FmOperator { detune: 5, multiple: 6, rate_scale: 2, attack_rate: 25, amp_mod: false, d1r: 9, d2r: 7, sustain_level: 6, release_rate: 12, total_level: 30 },
                FmOperator { detune: 7, multiple: 8, rate_scale: 3, attack_rate: 22, amp_mod: true, d1r: 11, d2r: 9, sustain_level: 8, release_rate: 14, total_level: 40 },
            ],
            metadata: InstrumentMetadata::default(),
        }
    }

    #[test]
    fn test_fm_to_bytes_length() {
        let driver = FlamedriverProfile;
        let inst = make_test_instrument();
        let bytes = driver.fm_to_bytes(&inst);
        assert_eq!(bytes.len(), 25);
    }

    #[test]
    fn test_fm_to_bytes_algo_feedback_is_last() {
        let driver = FlamedriverProfile;
        let inst = make_test_instrument();
        let bytes = driver.fm_to_bytes(&inst);
        // Byte 24 = (feedback << 3) | algorithm = (5 << 3) | 4 = 0x2C
        assert_eq!(bytes[24], (5 << 3) | 4);
    }

    #[test]
    fn test_fm_to_bytes_operator_order_is_4321() {
        let driver = FlamedriverProfile;
        let inst = make_test_instrument();
        let bytes = driver.fm_to_bytes(&inst);
        // Bytes 0-3: DT/MUL for ops 4,3,2,1
        // Op4 (idx 3): detune=7, mul=8 → (7<<4)|8 = 0x78
        assert_eq!(bytes[0], (7 << 4) | 8);
        // Op3 (idx 2): detune=5, mul=6 → (5<<4)|6 = 0x56
        assert_eq!(bytes[1], (5 << 4) | 6);
        // Op2 (idx 1): detune=3, mul=4 → (3<<4)|4 = 0x34
        assert_eq!(bytes[2], (3 << 4) | 4);
        // Op1 (idx 0): detune=1, mul=2 → (1<<4)|2 = 0x12
        assert_eq!(bytes[3], (1 << 4) | 2);
    }

    #[test]
    fn test_fm_to_bytes_carrier_flags_algo4() {
        let driver = FlamedriverProfile;
        let inst = make_test_instrument(); // algorithm 4: carriers = op2, op4
        let bytes = driver.fm_to_bytes(&inst);
        // TL bytes 20-23: ops 4,3,2,1
        // Op4 (carrier): TL=40 | 0x80 = 0xA8
        assert_eq!(bytes[20], 40 | 0x80);
        // Op3 (modulator): TL=30, no flag
        assert_eq!(bytes[21], 30);
        // Op2 (carrier): TL=20 | 0x80 = 0x94
        assert_eq!(bytes[22], 20 | 0x80);
        // Op1 (modulator): TL=10, no flag
        assert_eq!(bytes[23], 10);
    }

    #[test]
    fn test_fm_round_trip() {
        let driver = FlamedriverProfile;
        let original = make_test_instrument();
        let bytes = driver.fm_to_bytes(&original);
        let parsed = driver.fm_from_bytes(&bytes).unwrap();
        assert_eq!(parsed.algorithm, original.algorithm);
        assert_eq!(parsed.feedback, original.feedback);
        for i in 0..4 {
            assert_eq!(parsed.operators[i].detune, original.operators[i].detune);
            assert_eq!(parsed.operators[i].multiple, original.operators[i].multiple);
            assert_eq!(parsed.operators[i].rate_scale, original.operators[i].rate_scale);
            assert_eq!(parsed.operators[i].attack_rate, original.operators[i].attack_rate);
            assert_eq!(parsed.operators[i].amp_mod, original.operators[i].amp_mod);
            assert_eq!(parsed.operators[i].d1r, original.operators[i].d1r);
            assert_eq!(parsed.operators[i].d2r, original.operators[i].d2r);
            assert_eq!(parsed.operators[i].sustain_level, original.operators[i].sustain_level);
            assert_eq!(parsed.operators[i].release_rate, original.operators[i].release_rate);
            assert_eq!(parsed.operators[i].total_level, original.operators[i].total_level);
        }
    }

    #[test]
    fn test_fm_from_bytes_rejects_wrong_length() {
        let driver = FlamedriverProfile;
        assert!(driver.fm_from_bytes(&[0u8; 24]).is_err());
        assert!(driver.fm_from_bytes(&[0u8; 26]).is_err());
    }

    #[test]
    fn test_validate_fm_accepts_valid() {
        let driver = FlamedriverProfile;
        let inst = make_test_instrument();
        assert!(driver.validate_fm(&inst).is_ok());
    }

    #[test]
    fn test_validate_fm_catches_bad_algorithm() {
        let driver = FlamedriverProfile;
        let mut inst = make_test_instrument();
        inst.algorithm = 8;
        let err = driver.validate_fm(&inst).unwrap_err();
        assert!(err.iter().any(|e| e.contains("algorithm")));
    }

    #[test]
    fn test_validate_psg_catches_empty_envelope() {
        let driver = FlamedriverProfile;
        let inst = PsgInstrument {
            id: Uuid::nil(),
            name: "Bad".into(),
            volume_sequence: vec![],
            loop_point: None,
            noise_mode: None,
            metadata: InstrumentMetadata::default(),
        };
        let err = driver.validate_psg(&inst).unwrap_err();
        assert!(err.iter().any(|e| e.contains("empty")));
    }

    #[test]
    fn test_validate_dac_catches_bad_rate() {
        let driver = FlamedriverProfile;
        let inst = DacInstrument {
            id: Uuid::nil(),
            name: "Bad".into(),
            target_sample_rate: 12345,
            loop_start: None,
            loop_length: None,
            original_file: String::new(),
            pcm_file: String::new(),
            source_is_raw: false,
            metadata: InstrumentMetadata::default(),
        };
        let err = driver.validate_dac(&inst).unwrap_err();
        assert!(err.iter().any(|e| e.contains("target_sample_rate")));
    }

    #[test]
    fn test_channel_layout() {
        let driver = FlamedriverProfile;
        let layout = driver.channel_layout();
        assert_eq!(layout.fm_channels.len(), 6);
        assert_eq!(layout.psg_channels.len(), 4);
        assert_eq!(layout.dac_channels.len(), 1);
        assert!(layout.fm_channels[2].supports_special_mode); // FM3
        assert!(!layout.fm_channels[0].supports_special_mode);
        assert!(layout.psg_channels[3].is_noise);
    }

    #[test]
    fn test_supports_feature() {
        let driver = FlamedriverProfile;
        assert!(driver.supports_feature(DriverFeature::Fm3SpecialMode));
        assert!(!driver.supports_feature(DriverFeature::SsgEg));
        assert!(!driver.supports_feature(DriverFeature::Dpcm));
    }
}
```

- [ ] **Step 3: Create driver/mod.rs and add `mod driver;` to lib.rs**

Create `src-tauri/src/driver/mod.rs`:

```rust
pub mod flamedriver;

pub use flamedriver::FlamedriverProfile;
```

Add `mod driver;` to `src-tauri/src/lib.rs` (after `mod model;`).

- [ ] **Step 4: Run tests to verify they fail (todo!() panics)**

Run: `cd /home/volence/sonic_hacks/megadaw/src-tauri && cargo test -- --lib driver::flamedriver`
Expected: FAIL (todo!() panics)

- [ ] **Step 5: Implement FlamedriverProfile**

Replace the placeholder `impl DriverProfile for FlamedriverProfile` in `src-tauri/src/driver/flamedriver.rs`:

```rust
use crate::model::driver::*;
use crate::model::instrument::*;
use uuid::Uuid;

pub struct FlamedriverProfile;

/// Bit i = 1 means operator (i+1) is a carrier for that algorithm.
const CARRIER_MASKS: [u8; 8] = [
    0b1000, // algo 0: op4
    0b1000, // algo 1: op4
    0b1000, // algo 2: op4
    0b1000, // algo 3: op4
    0b1010, // algo 4: op2, op4
    0b1110, // algo 5: op2, op3, op4
    0b1110, // algo 6: op2, op3, op4
    0b1111, // algo 7: all
];

const OP_ORDER: [usize; 4] = [3, 2, 1, 0]; // ops 4,3,2,1

impl DriverProfile for FlamedriverProfile {
    fn name(&self) -> &str {
        "Flamedriver (S3K)"
    }

    fn id(&self) -> &str {
        "flamedriver"
    }

    fn channel_layout(&self) -> ChannelLayout {
        ChannelLayout {
            fm_channels: vec![
                FmChannelInfo { index: 0, name: "FM1".into(), supports_special_mode: false },
                FmChannelInfo { index: 1, name: "FM2".into(), supports_special_mode: false },
                FmChannelInfo { index: 2, name: "FM3".into(), supports_special_mode: true },
                FmChannelInfo { index: 3, name: "FM4".into(), supports_special_mode: false },
                FmChannelInfo { index: 4, name: "FM5".into(), supports_special_mode: false },
                FmChannelInfo { index: 5, name: "FM6/DAC".into(), supports_special_mode: false },
            ],
            psg_channels: vec![
                PsgChannelInfo { index: 0, name: "PSG1".into(), is_noise: false },
                PsgChannelInfo { index: 1, name: "PSG2".into(), is_noise: false },
                PsgChannelInfo { index: 2, name: "PSG3".into(), is_noise: false },
                PsgChannelInfo { index: 3, name: "PSG Noise".into(), is_noise: true },
            ],
            dac_channels: vec![
                DacChannelInfo { index: 0, name: "DAC".into() },
            ],
        }
    }

    fn supports_feature(&self, feature: DriverFeature) -> bool {
        matches!(feature, DriverFeature::Fm3SpecialMode)
    }

    fn validate_fm(&self, inst: &FmInstrument) -> Result<(), Vec<String>> {
        let mut errors = Vec::new();
        if inst.algorithm > 7 {
            errors.push(format!("algorithm {} > 7", inst.algorithm));
        }
        if inst.feedback > 7 {
            errors.push(format!("feedback {} > 7", inst.feedback));
        }
        for (i, op) in inst.operators.iter().enumerate() {
            let n = i + 1;
            if op.detune > 7 { errors.push(format!("op{n} detune {} > 7", op.detune)); }
            if op.multiple > 15 { errors.push(format!("op{n} multiple {} > 15", op.multiple)); }
            if op.rate_scale > 3 { errors.push(format!("op{n} rate_scale {} > 3", op.rate_scale)); }
            if op.attack_rate > 31 { errors.push(format!("op{n} attack_rate {} > 31", op.attack_rate)); }
            if op.d1r > 31 { errors.push(format!("op{n} d1r {} > 31", op.d1r)); }
            if op.d2r > 31 { errors.push(format!("op{n} d2r {} > 31", op.d2r)); }
            if op.sustain_level > 15 { errors.push(format!("op{n} sustain_level {} > 15", op.sustain_level)); }
            if op.release_rate > 15 { errors.push(format!("op{n} release_rate {} > 15", op.release_rate)); }
            if op.total_level > 127 { errors.push(format!("op{n} total_level {} > 127", op.total_level)); }
        }
        if errors.is_empty() { Ok(()) } else { Err(errors) }
    }

    fn validate_psg(&self, inst: &PsgInstrument) -> Result<(), Vec<String>> {
        let mut errors = Vec::new();
        if inst.volume_sequence.is_empty() {
            errors.push("volume_sequence is empty".into());
        }
        for (i, &v) in inst.volume_sequence.iter().enumerate() {
            if v > 15 {
                errors.push(format!("volume_sequence[{i}] = {v} > 15"));
            }
        }
        if let Some(lp) = inst.loop_point {
            if lp >= inst.volume_sequence.len() {
                errors.push(format!(
                    "loop_point {lp} >= sequence length {}",
                    inst.volume_sequence.len()
                ));
            }
        }
        if errors.is_empty() { Ok(()) } else { Err(errors) }
    }

    fn validate_dac(&self, inst: &DacInstrument) -> Result<(), Vec<String>> {
        let valid_rates = [8000, 11025, 16000, 22050, 32000];
        if valid_rates.contains(&inst.target_sample_rate) {
            Ok(())
        } else {
            Err(vec![format!(
                "target_sample_rate {} not in {:?}",
                inst.target_sample_rate, valid_rates
            )])
        }
    }

    fn fm_to_bytes(&self, inst: &FmInstrument) -> Vec<u8> {
        let mut bytes = Vec::with_capacity(25);
        let carrier_mask = CARRIER_MASKS[inst.algorithm as usize];

        for &idx in &OP_ORDER {
            let op = &inst.operators[idx];
            bytes.push((op.detune << 4) | op.multiple);
        }
        for &idx in &OP_ORDER {
            let op = &inst.operators[idx];
            bytes.push((op.rate_scale << 6) | op.attack_rate);
        }
        for &idx in &OP_ORDER {
            let op = &inst.operators[idx];
            bytes.push(((op.amp_mod as u8) << 7) | op.d1r);
        }
        for &idx in &OP_ORDER {
            bytes.push(inst.operators[idx].d2r);
        }
        for &idx in &OP_ORDER {
            let op = &inst.operators[idx];
            bytes.push((op.sustain_level << 4) | op.release_rate);
        }
        for &idx in &OP_ORDER {
            let op = &inst.operators[idx];
            let is_carrier = (carrier_mask >> idx) & 1 == 1;
            bytes.push(op.total_level | if is_carrier { 0x80 } else { 0 });
        }
        bytes.push((inst.feedback << 3) | inst.algorithm);

        bytes
    }

    fn fm_from_bytes(&self, bytes: &[u8]) -> Result<FmInstrument, String> {
        if bytes.len() != 25 {
            return Err(format!("expected 25 bytes, got {}", bytes.len()));
        }

        let fb_alg = bytes[24];
        let algorithm = fb_alg & 0x07;
        let feedback = (fb_alg >> 3) & 0x07;

        let mut operators = [
            FmOperator::default(),
            FmOperator::default(),
            FmOperator::default(),
            FmOperator::default(),
        ];

        for (pos, &idx) in OP_ORDER.iter().enumerate() {
            operators[idx].detune = bytes[pos] >> 4;
            operators[idx].multiple = bytes[pos] & 0x0F;
            operators[idx].rate_scale = bytes[4 + pos] >> 6;
            operators[idx].attack_rate = bytes[4 + pos] & 0x1F;
            operators[idx].amp_mod = bytes[8 + pos] & 0x80 != 0;
            operators[idx].d1r = bytes[8 + pos] & 0x1F;
            operators[idx].d2r = bytes[12 + pos] & 0x1F;
            operators[idx].sustain_level = bytes[16 + pos] >> 4;
            operators[idx].release_rate = bytes[16 + pos] & 0x0F;
            operators[idx].total_level = bytes[20 + pos] & 0x7F;
        }

        Ok(FmInstrument {
            id: Uuid::new_v4(),
            name: String::new(),
            algorithm,
            feedback,
            operators,
            metadata: InstrumentMetadata::default(),
        })
    }

    fn import_formats(&self) -> Vec<&str> {
        vec!["smps2asm"]
    }

    fn export_formats(&self) -> Vec<&str> {
        vec!["smps2asm", "binary"]
    }
}
```

- [ ] **Step 6: Run tests**

Run: `cd /home/volence/sonic_hacks/megadaw/src-tauri && cargo test -- --lib driver::flamedriver`
Expected: all tests PASS

- [ ] **Step 7: Commit**

```bash
git add src-tauri/src/model/driver.rs src-tauri/src/driver/ src-tauri/src/lib.rs
git commit -m "feat(driver): DriverProfile trait + Flamedriver 25-byte voice packing"
```

---

### Task 3: Project Persistence

**Files:**
- Create: `src-tauri/src/project/mod.rs`
- Create: `src-tauri/src/project/manager.rs`
- Modify: `src-tauri/src/lib.rs` (add `mod project;`)

- [ ] **Step 1: Create project/mod.rs**

Create `src-tauri/src/project/mod.rs`:

```rust
pub mod manager;

pub use manager::ProjectManager;
```

- [ ] **Step 2: Add `mod project;` to lib.rs**

Add `mod project;` to `src-tauri/src/lib.rs` (after `mod driver;`).

- [ ] **Step 3: Create project/manager.rs with ProjectManager and tests**

Create `src-tauri/src/project/manager.rs`:

```rust
use std::collections::{HashMap, HashSet};
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use uuid::Uuid;

use crate::model::driver::DriverRegistry;
use crate::model::instrument::*;
use crate::model::song::*;

pub struct ProjectManager {
    project_path: Option<PathBuf>,
    metadata: Option<SongMetadata>,
    tracks: Vec<Track>,
    instruments: InstrumentBank,
    dirty_instruments: HashSet<Uuid>,
    dac_pcm_cache: HashMap<Uuid, Arc<Vec<u8>>>,
    driver_registry: DriverRegistry,
}

impl ProjectManager {
    pub fn new(driver_registry: DriverRegistry) -> Self {
        Self {
            project_path: None,
            metadata: None,
            tracks: Vec::new(),
            instruments: InstrumentBank::default(),
            dirty_instruments: HashSet::new(),
            dac_pcm_cache: HashMap::new(),
            driver_registry,
        }
    }

    pub fn create(
        &mut self,
        path: &Path,
        name: &str,
        driver_id: &str,
        tempo: f64,
        time_sig: (u8, u8),
    ) -> Result<(), String> {
        if self.driver_registry.get(driver_id).is_none() {
            return Err(format!("unknown driver: {driver_id}"));
        }

        fs::create_dir_all(path).map_err(|e| e.to_string())?;
        fs::create_dir_all(path.join("instruments/fm")).map_err(|e| e.to_string())?;
        fs::create_dir_all(path.join("instruments/psg")).map_err(|e| e.to_string())?;
        fs::create_dir_all(path.join("instruments/dac")).map_err(|e| e.to_string())?;
        fs::create_dir_all(path.join("exports")).map_err(|e| e.to_string())?;

        let version = serde_json::json!({ "version": "0.1.0" });
        fs::write(
            path.join(".megadaw"),
            serde_json::to_string_pretty(&version).unwrap(),
        )
        .map_err(|e| e.to_string())?;

        let metadata = SongMetadata {
            name: name.to_string(),
            tempo,
            time_signature: time_sig,
            ticks_per_beat: 480,
            driver_id: driver_id.to_string(),
        };

        let project_file = ProjectFile {
            metadata: metadata.clone(),
            tracks: Vec::new(),
        };
        let json = serde_json::to_string_pretty(&project_file).map_err(|e| e.to_string())?;
        fs::write(path.join("project.json"), json).map_err(|e| e.to_string())?;

        self.project_path = Some(path.to_path_buf());
        self.metadata = Some(metadata);
        self.tracks = Vec::new();
        self.instruments = InstrumentBank::default();
        self.dirty_instruments.clear();
        self.dac_pcm_cache.clear();

        Ok(())
    }

    pub fn open(&mut self, path: &Path) -> Result<Song, String> {
        if !path.join(".megadaw").exists() {
            return Err("not a MegaDAW project (no .megadaw file)".into());
        }

        let json = fs::read_to_string(path.join("project.json")).map_err(|e| e.to_string())?;
        let project_file: ProjectFile =
            serde_json::from_str(&json).map_err(|e| e.to_string())?;

        let mut instruments = InstrumentBank::default();

        let fm_dir = path.join("instruments/fm");
        if fm_dir.exists() {
            for entry in fs::read_dir(&fm_dir).map_err(|e| e.to_string())? {
                let entry = entry.map_err(|e| e.to_string())?;
                if entry.path().extension().map_or(false, |ext| ext == "json") {
                    let data = fs::read_to_string(entry.path()).map_err(|e| e.to_string())?;
                    let inst: FmInstrument =
                        serde_json::from_str(&data).map_err(|e| e.to_string())?;
                    instruments.fm.push(inst);
                }
            }
        }

        let psg_dir = path.join("instruments/psg");
        if psg_dir.exists() {
            for entry in fs::read_dir(&psg_dir).map_err(|e| e.to_string())? {
                let entry = entry.map_err(|e| e.to_string())?;
                if entry.path().extension().map_or(false, |ext| ext == "json") {
                    let data = fs::read_to_string(entry.path()).map_err(|e| e.to_string())?;
                    let inst: PsgInstrument =
                        serde_json::from_str(&data).map_err(|e| e.to_string())?;
                    instruments.psg.push(inst);
                }
            }
        }

        let dac_dir = path.join("instruments/dac");
        if dac_dir.exists() {
            for entry in fs::read_dir(&dac_dir).map_err(|e| e.to_string())? {
                let entry = entry.map_err(|e| e.to_string())?;
                if entry.path().extension().map_or(false, |ext| ext == "json") {
                    let data = fs::read_to_string(entry.path()).map_err(|e| e.to_string())?;
                    let inst: DacInstrument =
                        serde_json::from_str(&data).map_err(|e| e.to_string())?;
                    let pcm_path = path.join("instruments/dac").join(&inst.pcm_file);
                    if pcm_path.exists() {
                        let pcm_data = fs::read(&pcm_path).map_err(|e| e.to_string())?;
                        self.dac_pcm_cache.insert(inst.id, Arc::new(pcm_data));
                    }
                    instruments.dac.push(inst);
                }
            }
        }

        self.project_path = Some(path.to_path_buf());
        self.metadata = Some(project_file.metadata.clone());
        self.tracks = project_file.tracks.clone();
        self.instruments = instruments.clone();
        self.dirty_instruments.clear();

        Ok(Song {
            metadata: project_file.metadata,
            tracks: project_file.tracks,
            instruments,
        })
    }

    pub fn save(&mut self) -> Result<(), String> {
        let path = self.project_path.as_ref().ok_or("no project open")?;
        let metadata = self.metadata.as_ref().ok_or("no project open")?.clone();

        let project_file = ProjectFile {
            metadata,
            tracks: self.tracks.clone(),
        };
        let json = serde_json::to_string_pretty(&project_file).map_err(|e| e.to_string())?;
        fs::write(path.join("project.json"), json).map_err(|e| e.to_string())?;

        for inst in &self.instruments.fm {
            if self.dirty_instruments.contains(&inst.id) {
                let json = serde_json::to_string_pretty(inst).map_err(|e| e.to_string())?;
                fs::write(path.join(format!("instruments/fm/{}.json", inst.id)), json)
                    .map_err(|e| e.to_string())?;
            }
        }
        for inst in &self.instruments.psg {
            if self.dirty_instruments.contains(&inst.id) {
                let json = serde_json::to_string_pretty(inst).map_err(|e| e.to_string())?;
                fs::write(path.join(format!("instruments/psg/{}.json", inst.id)), json)
                    .map_err(|e| e.to_string())?;
            }
        }
        for inst in &self.instruments.dac {
            if self.dirty_instruments.contains(&inst.id) {
                let json = serde_json::to_string_pretty(inst).map_err(|e| e.to_string())?;
                fs::write(path.join(format!("instruments/dac/{}.json", inst.id)), json)
                    .map_err(|e| e.to_string())?;
                if let Some(pcm) = self.dac_pcm_cache.get(&inst.id) {
                    fs::write(path.join("instruments/dac").join(&inst.pcm_file), pcm.as_ref())
                        .map_err(|e| e.to_string())?;
                }
            }
        }

        self.dirty_instruments.clear();
        Ok(())
    }

    pub fn close(&mut self) {
        self.project_path = None;
        self.metadata = None;
        self.tracks.clear();
        self.instruments = InstrumentBank::default();
        self.dirty_instruments.clear();
        self.dac_pcm_cache.clear();
    }

    pub fn is_open(&self) -> bool {
        self.project_path.is_some()
    }

    pub fn metadata(&self) -> Option<&SongMetadata> {
        self.metadata.as_ref()
    }

    pub fn project_path(&self) -> Option<&Path> {
        self.project_path.as_deref()
    }

    pub fn driver_registry(&self) -> &DriverRegistry {
        &self.driver_registry
    }

    pub fn song(&self) -> Option<Song> {
        self.metadata.as_ref().map(|meta| Song {
            metadata: meta.clone(),
            tracks: self.tracks.clone(),
            instruments: self.instruments.clone(),
        })
    }

    // --- FM CRUD ---

    pub fn add_fm_instrument(&mut self, mut inst: FmInstrument) -> Uuid {
        let id = Uuid::new_v4();
        inst.id = id;
        self.instruments.fm.push(inst);
        self.dirty_instruments.insert(id);
        id
    }

    pub fn update_fm_instrument(&mut self, id: Uuid, mut inst: FmInstrument) -> Result<(), String> {
        let existing = self.instruments.fm.iter_mut().find(|i| i.id == id)
            .ok_or("FM instrument not found")?;
        inst.id = id;
        *existing = inst;
        self.dirty_instruments.insert(id);
        Ok(())
    }

    pub fn delete_fm_instrument(&mut self, id: Uuid) -> Result<(), String> {
        let pos = self.instruments.fm.iter().position(|i| i.id == id)
            .ok_or("FM instrument not found")?;
        self.instruments.fm.remove(pos);
        self.dirty_instruments.remove(&id);
        if let Some(path) = &self.project_path {
            let file = path.join(format!("instruments/fm/{id}.json"));
            if file.exists() { let _ = fs::remove_file(file); }
        }
        Ok(())
    }

    pub fn list_fm_instruments(&self) -> &[FmInstrument] {
        &self.instruments.fm
    }

    pub fn get_fm_instrument(&self, id: &Uuid) -> Option<&FmInstrument> {
        self.instruments.fm.iter().find(|i| &i.id == id)
    }

    // --- PSG CRUD ---

    pub fn add_psg_instrument(&mut self, mut inst: PsgInstrument) -> Uuid {
        let id = Uuid::new_v4();
        inst.id = id;
        self.instruments.psg.push(inst);
        self.dirty_instruments.insert(id);
        id
    }

    pub fn update_psg_instrument(&mut self, id: Uuid, mut inst: PsgInstrument) -> Result<(), String> {
        let existing = self.instruments.psg.iter_mut().find(|i| i.id == id)
            .ok_or("PSG instrument not found")?;
        inst.id = id;
        *existing = inst;
        self.dirty_instruments.insert(id);
        Ok(())
    }

    pub fn delete_psg_instrument(&mut self, id: Uuid) -> Result<(), String> {
        let pos = self.instruments.psg.iter().position(|i| i.id == id)
            .ok_or("PSG instrument not found")?;
        self.instruments.psg.remove(pos);
        self.dirty_instruments.remove(&id);
        if let Some(path) = &self.project_path {
            let file = path.join(format!("instruments/psg/{id}.json"));
            if file.exists() { let _ = fs::remove_file(file); }
        }
        Ok(())
    }

    pub fn list_psg_instruments(&self) -> &[PsgInstrument] {
        &self.instruments.psg
    }

    pub fn get_psg_instrument(&self, id: &Uuid) -> Option<&PsgInstrument> {
        self.instruments.psg.iter().find(|i| &i.id == id)
    }

    // --- DAC CRUD ---

    pub fn add_dac_instrument(&mut self, inst: DacInstrument, pcm_data: Vec<u8>) -> Uuid {
        let id = inst.id;
        self.dac_pcm_cache.insert(id, Arc::new(pcm_data));
        self.instruments.dac.push(inst);
        self.dirty_instruments.insert(id);
        id
    }

    pub fn update_dac_instrument(&mut self, id: Uuid, mut inst: DacInstrument) -> Result<(), String> {
        let existing = self.instruments.dac.iter_mut().find(|i| i.id == id)
            .ok_or("DAC instrument not found")?;
        inst.id = id;
        *existing = inst;
        self.dirty_instruments.insert(id);
        Ok(())
    }

    pub fn delete_dac_instrument(&mut self, id: Uuid) -> Result<(), String> {
        let pos = self.instruments.dac.iter().position(|i| i.id == id)
            .ok_or("DAC instrument not found")?;
        let inst = self.instruments.dac.remove(pos);
        self.dirty_instruments.remove(&id);
        self.dac_pcm_cache.remove(&id);
        if let Some(path) = &self.project_path {
            for name in [
                format!("instruments/dac/{id}.json"),
                format!("instruments/dac/{}", inst.pcm_file),
                format!("instruments/dac/{}", inst.original_file),
            ] {
                let p = path.join(&name);
                if p.exists() { let _ = fs::remove_file(p); }
            }
        }
        Ok(())
    }

    pub fn list_dac_instruments(&self) -> &[DacInstrument] {
        &self.instruments.dac
    }

    pub fn get_dac_instrument(&self, id: &Uuid) -> Option<&DacInstrument> {
        self.instruments.dac.iter().find(|i| &i.id == id)
    }

    pub fn get_dac_pcm(&self, id: &Uuid) -> Option<Arc<Vec<u8>>> {
        self.dac_pcm_cache.get(id).cloned()
    }

    pub fn update_dac_pcm(&mut self, id: Uuid, pcm_data: Vec<u8>) {
        self.dac_pcm_cache.insert(id, Arc::new(pcm_data));
        self.dirty_instruments.insert(id);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::driver::FlamedriverProfile;
    use std::env;

    fn test_registry() -> DriverRegistry {
        let mut reg = DriverRegistry::new();
        reg.register(Box::new(FlamedriverProfile));
        reg
    }

    fn temp_project_path(name: &str) -> PathBuf {
        env::temp_dir().join(format!("megadaw_test_{name}_{}", Uuid::new_v4()))
    }

    fn cleanup(path: &Path) {
        let _ = fs::remove_dir_all(path);
    }

    #[test]
    fn test_create_project_makes_folder_structure() {
        let path = temp_project_path("create");
        let mut mgr = ProjectManager::new(test_registry());

        mgr.create(&path, "Test Song", "flamedriver", 120.0, (4, 4)).unwrap();

        assert!(path.join(".megadaw").exists());
        assert!(path.join("project.json").exists());
        assert!(path.join("instruments/fm").is_dir());
        assert!(path.join("instruments/psg").is_dir());
        assert!(path.join("instruments/dac").is_dir());
        assert!(path.join("exports").is_dir());
        assert!(mgr.is_open());

        cleanup(&path);
    }

    #[test]
    fn test_create_rejects_unknown_driver() {
        let path = temp_project_path("bad_driver");
        let mut mgr = ProjectManager::new(test_registry());
        let result = mgr.create(&path, "X", "nonexistent", 120.0, (4, 4));
        assert!(result.is_err());
        cleanup(&path);
    }

    #[test]
    fn test_open_rejects_non_project() {
        let path = temp_project_path("not_project");
        fs::create_dir_all(&path).unwrap();
        let mut mgr = ProjectManager::new(test_registry());
        let result = mgr.open(&path);
        assert!(result.is_err());
        cleanup(&path);
    }

    #[test]
    fn test_create_save_open_round_trip() {
        let path = temp_project_path("round_trip");
        let mut mgr = ProjectManager::new(test_registry());

        mgr.create(&path, "Round Trip", "flamedriver", 150.0, (3, 4)).unwrap();

        let fm_inst = FmInstrument {
            id: Uuid::nil(),
            name: "Bass".into(),
            algorithm: 2,
            feedback: 3,
            operators: [FmOperator::default(); 4],
            metadata: InstrumentMetadata::default(),
        };
        let fm_id = mgr.add_fm_instrument(fm_inst);

        let psg_inst = PsgInstrument {
            id: Uuid::nil(),
            name: "Pluck".into(),
            volume_sequence: vec![15, 12, 8, 4, 0],
            loop_point: None,
            noise_mode: None,
            metadata: InstrumentMetadata::default(),
        };
        let psg_id = mgr.add_psg_instrument(psg_inst);

        mgr.save().unwrap();
        mgr.close();
        assert!(!mgr.is_open());

        let song = mgr.open(&path).unwrap();
        assert_eq!(song.metadata.name, "Round Trip");
        assert_eq!(song.metadata.tempo, 150.0);
        assert_eq!(song.instruments.fm.len(), 1);
        assert_eq!(song.instruments.fm[0].id, fm_id);
        assert_eq!(song.instruments.fm[0].name, "Bass");
        assert_eq!(song.instruments.psg.len(), 1);
        assert_eq!(song.instruments.psg[0].id, psg_id);

        cleanup(&path);
    }

    #[test]
    fn test_delete_fm_removes_file() {
        let path = temp_project_path("delete_fm");
        let mut mgr = ProjectManager::new(test_registry());
        mgr.create(&path, "Del Test", "flamedriver", 120.0, (4, 4)).unwrap();

        let inst = FmInstrument {
            id: Uuid::nil(),
            name: "ToDelete".into(),
            algorithm: 0,
            feedback: 0,
            operators: [FmOperator::default(); 4],
            metadata: InstrumentMetadata::default(),
        };
        let id = mgr.add_fm_instrument(inst);
        mgr.save().unwrap();
        assert!(path.join(format!("instruments/fm/{id}.json")).exists());

        mgr.delete_fm_instrument(id).unwrap();
        assert!(!path.join(format!("instruments/fm/{id}.json")).exists());
        assert!(mgr.list_fm_instruments().is_empty());

        cleanup(&path);
    }

    #[test]
    fn test_close_clears_state() {
        let path = temp_project_path("close");
        let mut mgr = ProjectManager::new(test_registry());
        mgr.create(&path, "Test", "flamedriver", 120.0, (4, 4)).unwrap();
        mgr.close();
        assert!(!mgr.is_open());
        assert!(mgr.metadata().is_none());
        assert!(mgr.list_fm_instruments().is_empty());
        cleanup(&path);
    }
}
```

- [ ] **Step 4: Run tests**

Run: `cd /home/volence/sonic_hacks/megadaw/src-tauri && cargo test -- --lib project::manager`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add src-tauri/src/project/ src-tauri/src/lib.rs
git commit -m "feat(project): ProjectManager — create/open/save/close with instrument CRUD"
```

---

### Task 4: DAC Conversion Pipeline

**Files:**
- Create: `src-tauri/src/dac/mod.rs`
- Create: `src-tauri/src/dac/pipeline.rs`
- Modify: `src-tauri/src/lib.rs` (add `mod dac;`)

- [ ] **Step 1: Create dac/mod.rs**

Create `src-tauri/src/dac/mod.rs`:

```rust
pub mod pipeline;

pub use pipeline::{import_raw, import_wav, quantize_u8, resample};
```

- [ ] **Step 2: Add `mod dac;` to lib.rs**

Add `mod dac;` to `src-tauri/src/lib.rs` (after `mod project;`).

- [ ] **Step 3: Create dac/pipeline.rs with conversion functions and tests**

Create `src-tauri/src/dac/pipeline.rs`:

```rust
use std::path::Path;

pub fn resample(samples: &[f32], from_rate: u32, to_rate: u32) -> Vec<f32> {
    if from_rate == to_rate || samples.is_empty() {
        return samples.to_vec();
    }
    let ratio = from_rate as f64 / to_rate as f64;
    let output_len = (samples.len() as f64 / ratio) as usize;
    let mut output = Vec::with_capacity(output_len);

    for i in 0..output_len {
        let src_pos = i as f64 * ratio;
        let idx = src_pos as usize;
        let frac = (src_pos - idx as f64) as f32;
        let s0 = samples[idx.min(samples.len() - 1)];
        let s1 = samples[(idx + 1).min(samples.len() - 1)];
        output.push(s0 + (s1 - s0) * frac);
    }

    output
}

pub fn quantize_u8(samples: &[f32]) -> Vec<u8> {
    samples
        .iter()
        .map(|&s| {
            let clamped = s.clamp(-1.0, 1.0);
            ((clamped * 127.0) + 128.0) as u8
        })
        .collect()
}

pub fn import_wav(wav_path: &Path, target_rate: u32) -> Result<Vec<u8>, String> {
    let reader =
        hound::WavReader::open(wav_path).map_err(|e| format!("failed to open WAV: {e}"))?;
    let spec = reader.spec();

    let float_samples: Vec<f32> = match spec.sample_format {
        hound::SampleFormat::Int => {
            let max_val = (1i64 << (spec.bits_per_sample - 1)) as f32;
            reader
                .into_samples::<i32>()
                .map(|s| s.map(|v| v as f32 / max_val))
                .collect::<Result<Vec<_>, _>>()
                .map_err(|e| e.to_string())?
        }
        hound::SampleFormat::Float => reader
            .into_samples::<f32>()
            .collect::<Result<Vec<_>, _>>()
            .map_err(|e| e.to_string())?,
    };

    let mono = if spec.channels > 1 {
        float_samples
            .chunks(spec.channels as usize)
            .map(|chunk| chunk.iter().sum::<f32>() / chunk.len() as f32)
            .collect()
    } else {
        float_samples
    };

    let resampled = resample(&mono, spec.sample_rate, target_rate);
    Ok(quantize_u8(&resampled))
}

pub fn import_raw(raw_path: &Path) -> Result<Vec<u8>, String> {
    std::fs::read(raw_path).map_err(|e| format!("failed to read raw PCM: {e}"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_resample_same_rate_is_identity() {
        let samples = vec![0.0, 0.5, 1.0, -1.0];
        let out = resample(&samples, 44100, 44100);
        assert_eq!(out, samples);
    }

    #[test]
    fn test_resample_halves_length() {
        let samples: Vec<f32> = (0..1000).map(|i| (i as f32) / 1000.0).collect();
        let out = resample(&samples, 44100, 22050);
        let expected_len = (1000.0 * 22050.0 / 44100.0) as usize;
        assert!((out.len() as i32 - expected_len as i32).abs() <= 1);
    }

    #[test]
    fn test_resample_doubles_length() {
        let samples: Vec<f32> = (0..100).map(|i| (i as f32) / 100.0).collect();
        let out = resample(&samples, 22050, 44100);
        let expected_len = (100.0 * 44100.0 / 22050.0) as usize;
        assert!((out.len() as i32 - expected_len as i32).abs() <= 1);
    }

    #[test]
    fn test_quantize_center_is_128() {
        let out = quantize_u8(&[0.0]);
        assert_eq!(out[0], 128);
    }

    #[test]
    fn test_quantize_max_is_255() {
        let out = quantize_u8(&[1.0]);
        assert_eq!(out[0], 255);
    }

    #[test]
    fn test_quantize_min_is_1() {
        let out = quantize_u8(&[-1.0]);
        assert_eq!(out[0], 1);
    }

    #[test]
    fn test_quantize_clamps_overflow() {
        let out = quantize_u8(&[2.0, -2.0]);
        assert_eq!(out[0], 255);
        assert_eq!(out[1], 1);
    }

    #[test]
    fn test_import_wav_file() {
        let dir = std::env::temp_dir().join(format!("megadaw_wav_test_{}", uuid::Uuid::new_v4()));
        std::fs::create_dir_all(&dir).unwrap();
        let wav_path = dir.join("test.wav");

        let spec = hound::WavSpec {
            channels: 1,
            sample_rate: 44100,
            bits_per_sample: 16,
            sample_format: hound::SampleFormat::Int,
        };
        let mut writer = hound::WavWriter::create(&wav_path, spec).unwrap();
        for i in 0..4410 {
            let t = i as f32 / 44100.0;
            let sample = (t * 440.0 * 2.0 * std::f32::consts::PI).sin();
            writer.write_sample((sample * 32767.0) as i16).unwrap();
        }
        writer.finalize().unwrap();

        let pcm = import_wav(&wav_path, 16000).unwrap();
        let expected_len = (4410.0 * 16000.0 / 44100.0) as usize;
        assert!((pcm.len() as i32 - expected_len as i32).abs() <= 2);
        assert!(pcm.iter().any(|&s| s != 128), "should contain non-silent data");

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_import_wav_stereo_to_mono() {
        let dir = std::env::temp_dir().join(format!("megadaw_stereo_test_{}", uuid::Uuid::new_v4()));
        std::fs::create_dir_all(&dir).unwrap();
        let wav_path = dir.join("stereo.wav");

        let spec = hound::WavSpec {
            channels: 2,
            sample_rate: 44100,
            bits_per_sample: 16,
            sample_format: hound::SampleFormat::Int,
        };
        let mut writer = hound::WavWriter::create(&wav_path, spec).unwrap();
        for _ in 0..1000 {
            writer.write_sample(16383i16).unwrap(); // left
            writer.write_sample(-16383i16).unwrap(); // right
        }
        writer.finalize().unwrap();

        let pcm = import_wav(&wav_path, 44100).unwrap();
        assert_eq!(pcm.len(), 1000);
        // L+R averaged: (0.5 + -0.5) / 2 = 0.0 → 128
        for &s in &pcm {
            assert!((s as i16 - 128).abs() <= 1);
        }

        let _ = std::fs::remove_dir_all(&dir);
    }
}
```

- [ ] **Step 4: Run tests**

Run: `cd /home/volence/sonic_hacks/megadaw/src-tauri && cargo test -- --lib dac::pipeline`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add src-tauri/src/dac/ src-tauri/src/lib.rs
git commit -m "feat(dac): WAV import + raw PCM import + resample + quantize pipeline"
```

---

### Task 5: Audio Engine Extensions (DAC Playback, PSG Envelope Preview, Frequency Tables)

**Files:**
- Modify: `src-tauri/src/audio/command.rs` (add DacPlayback, PsgEnvelopePreview, StopPreview)
- Modify: `src-tauri/src/audio/engine.rs` (DAC rendering + PSG envelope stepping)
- Create: `src-tauri/src/audio/frequency.rs` (MIDI-to-hardware frequency conversion)
- Modify: `src-tauri/src/audio/mod.rs` (export frequency module)

- [ ] **Step 1: Add new AudioCommand variants**

In `src-tauri/src/audio/command.rs`, add `use std::sync::Arc;` at the top and three new variants to the enum:

```rust
use std::sync::Arc;

#[derive(Debug, Clone)]
pub enum AudioCommand {
    Ym2612Write { port: u32, data: u8 },
    Sn76489Write { data: u8 },
    FmKeyOn { channel: u8, operators: u8 },
    FmKeyOff { channel: u8 },
    Panic,
    DacPlayback { samples: Arc<Vec<u8>>, sample_rate: u32 },
    PsgEnvelopePreview { channel: u8, period: u16, envelope: Arc<Vec<u8>>, loop_point: Option<usize> },
    StopPreview,
}
```

- [ ] **Step 2: Create audio/frequency.rs with MIDI-to-hardware conversion**

Create `src-tauri/src/audio/frequency.rs`:

```rust
/// F-number table for one octave (C through B) computed at block 4.
/// Formula: f_num = freq * 144 * 2^(21-block) / master_clock
/// master_clock = 7,670,453 Hz, block = 4
const FM_FNUM_TABLE: [u16; 12] = [
    644,  // C
    682,  // C#
    723,  // D
    766,  // D#
    811,  // E
    859,  // F
    910,  // F#
    965,  // G
    1022, // G#
    1083, // A
    1147, // A#
    1215, // B
];

/// Convert MIDI note number to YM2612 (block, f_number).
/// Block = octave selector (0-7). F-number = pitch within octave (11-bit).
/// MIDI 60 = C4 → block 4. Usable range: ~MIDI 12-95.
pub fn midi_to_fm_freq(midi_note: u8) -> (u8, u16) {
    let semitone = (midi_note % 12) as usize;
    let octave = midi_note / 12;
    let block = octave.saturating_sub(1).min(7);
    (block, FM_FNUM_TABLE[semitone])
}

/// Convert MIDI note number to SN76489 10-bit tone period.
/// Formula: period = 3,579,545 / (32 * freq)
/// Returns 0 for notes too high to represent (period would be 0).
pub fn midi_to_psg_period(midi_note: u8) -> u16 {
    let freq = 440.0 * 2.0_f64.powf((midi_note as f64 - 69.0) / 12.0);
    let period = (3_579_545.0 / (32.0 * freq)) as u16;
    period.min(1023)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_midi_60_is_block_4() {
        let (block, _) = midi_to_fm_freq(60);
        assert_eq!(block, 4);
    }

    #[test]
    fn test_midi_48_is_block_3() {
        let (block, _) = midi_to_fm_freq(48);
        assert_eq!(block, 3);
    }

    #[test]
    fn test_midi_72_is_block_5() {
        let (block, _) = midi_to_fm_freq(72);
        assert_eq!(block, 5);
    }

    #[test]
    fn test_fm_a4_fnum_is_1083() {
        let (_, fnum) = midi_to_fm_freq(69); // A4
        assert_eq!(fnum, 1083);
    }

    #[test]
    fn test_psg_a4_period_near_254() {
        let period = midi_to_psg_period(69); // A4
        // 3579545 / (32 * 440) ≈ 254
        assert!((period as i32 - 254).abs() <= 1);
    }

    #[test]
    fn test_psg_high_note_clamps_to_1023() {
        let period = midi_to_psg_period(12); // C1, very low = high period
        assert!(period <= 1023);
    }

    #[test]
    fn test_psg_period_decreases_with_pitch() {
        let p_low = midi_to_psg_period(48);
        let p_high = midi_to_psg_period(72);
        assert!(p_low > p_high);
    }
}
```

- [ ] **Step 3: Add frequency module to audio/mod.rs**

Modify `src-tauri/src/audio/mod.rs`:

```rust
pub mod command;
pub mod engine;
pub mod frequency;
pub mod thread;

pub use command::AudioCommand;
pub use engine::AudioEngine;
pub use thread::AudioThread;
```

- [ ] **Step 4: Add DAC + PSG envelope state to AudioEngine and extend render()**

Modify `src-tauri/src/audio/engine.rs`. Add fields to `AudioEngine`:

```rust
use std::sync::Arc;
```

Add to the `AudioEngine` struct after `psg_clock_accumulator`:

```rust
    dac_samples: Option<Arc<Vec<u8>>>,
    dac_position: f64,
    dac_step: f64,
    psg_preview_envelope: Option<Arc<Vec<u8>>>,
    psg_preview_loop: Option<usize>,
    psg_preview_channel: u8,
    psg_preview_index: usize,
    psg_preview_tick_acc: f64,
    psg_preview_samples_per_tick: f64,
```

Initialize all to zero/None/0.0 in `new()`:

```rust
    dac_samples: None,
    dac_position: 0.0,
    dac_step: 0.0,
    psg_preview_envelope: None,
    psg_preview_loop: None,
    psg_preview_channel: 0,
    psg_preview_index: 0,
    psg_preview_tick_acc: 0.0,
    psg_preview_samples_per_tick: sample_rate_f / 60.0,
```

Add new match arms in `process_command`:

```rust
            AudioCommand::DacPlayback { samples, sample_rate } => {
                self.dac_samples = Some(samples);
                self.dac_position = 0.0;
                self.dac_step = sample_rate as f64 / self.sample_rate;
            }
            AudioCommand::PsgEnvelopePreview { channel, period, envelope, loop_point } => {
                // Set tone period
                let low_nibble = (period & 0x0F) as u8;
                let high_bits = ((period >> 4) & 0x3F) as u8;
                self.sn76489.write(0x80 | (channel << 5) | low_nibble);
                self.sn76489.write(high_bits);
                // Set initial volume to max (attenuation 0)
                self.sn76489.write(0x90 | (channel << 5));
                // Store envelope state
                self.psg_preview_envelope = Some(envelope);
                self.psg_preview_loop = loop_point;
                self.psg_preview_channel = channel;
                self.psg_preview_index = 0;
                self.psg_preview_tick_acc = 0.0;
            }
            AudioCommand::StopPreview => {
                self.dac_samples = None;
                self.dac_position = 0.0;
                if let Some(_) = self.psg_preview_envelope.take() {
                    // Silence the PSG channel
                    self.sn76489.write(0x90 | (self.psg_preview_channel << 5) | 0x0F);
                }
            }
```

Also reset preview state in the `Panic` arm:

```rust
            AudioCommand::Panic => {
                self.ym2612.reset();
                self.sn76489.reset();
                self.ym_clock_accumulator = 0.0;
                self.psg_clock_accumulator = 0.0;
                self.dac_samples = None;
                self.dac_position = 0.0;
                self.psg_preview_envelope = None;
            }
```

In `render()`, after the existing PSG mixing line (`let psg_sample = ...`), add DAC rendering and PSG envelope stepping. Replace the final mixing section:

```rust
            // --- DAC ---
            let dac_sample = if let Some(ref samples) = self.dac_samples {
                let idx = self.dac_position as usize;
                if idx < samples.len() {
                    let raw = samples[idx] as i32 - 128;
                    self.dac_position += self.dac_step;
                    raw * fm_scale
                } else {
                    self.dac_samples = None;
                    0
                }
            } else {
                0
            };

            // --- PSG envelope stepping ---
            if let Some(ref envelope) = self.psg_preview_envelope.clone() {
                self.psg_preview_tick_acc += 1.0;
                if self.psg_preview_tick_acc >= self.psg_preview_samples_per_tick {
                    self.psg_preview_tick_acc -= self.psg_preview_samples_per_tick;
                    if self.psg_preview_index < envelope.len() {
                        let vol = envelope[self.psg_preview_index];
                        let attenuation = 15u8.saturating_sub(vol);
                        self.sn76489.write(0x90 | (self.psg_preview_channel << 5) | attenuation);
                        self.psg_preview_index += 1;
                        if self.psg_preview_index >= envelope.len() {
                            if let Some(lp) = self.psg_preview_loop {
                                self.psg_preview_index = lp;
                            } else {
                                self.sn76489.write(0x90 | (self.psg_preview_channel << 5) | 0x0F);
                                self.psg_preview_envelope = None;
                            }
                        }
                    }
                }
            }

            // --- Mix and normalize ---
            let scaled_l = ym_l * fm_scale + psg_sample + dac_sample;
            let scaled_r = ym_r * fm_scale + psg_sample + dac_sample;

            buffer[frame * 2]     = (scaled_l as f32 / 32768.0).clamp(-1.0, 1.0);
            buffer[frame * 2 + 1] = (scaled_r as f32 / 32768.0).clamp(-1.0, 1.0);
```

- [ ] **Step 5: Add test for DAC playback in engine.rs**

Add to the `tests` module in `engine.rs`:

```rust
    #[test]
    fn test_dac_playback_produces_audio() {
        use std::sync::Arc;
        let mut engine = AudioEngine::new(44100);
        // 1000 samples of a square wave centered at 128
        let samples: Vec<u8> = (0..1000).map(|i| if i % 2 == 0 { 200 } else { 56 }).collect();
        engine.process_command(AudioCommand::DacPlayback {
            samples: Arc::new(samples),
            sample_rate: 16000,
        });
        let mut buf = [0.0f32; 4096];
        engine.render(&mut buf);
        let has_signal = buf.iter().any(|s| s.abs() > 0.01);
        assert!(has_signal, "DAC playback should produce audible output");
    }

    #[test]
    fn test_dac_stops_after_samples_exhausted() {
        use std::sync::Arc;
        let mut engine = AudioEngine::new(44100);
        let samples = vec![200u8; 10]; // very short
        engine.process_command(AudioCommand::DacPlayback {
            samples: Arc::new(samples),
            sample_rate: 44100,
        });
        let mut buf = [0.0f32; 4096];
        engine.render(&mut buf);
        // After 10 samples, DAC should be silent
        let tail = &buf[100..];
        let tail_signal = tail.iter().any(|s| s.abs() > 0.01);
        assert!(!tail_signal, "DAC should stop after samples exhausted");
    }
```

- [ ] **Step 6: Run all audio tests**

Run: `cd /home/volence/sonic_hacks/megadaw/src-tauri && cargo test -- --lib audio`
Expected: all tests PASS (existing + new)

- [ ] **Step 7: Commit**

```bash
git add src-tauri/src/audio/
git commit -m "feat(audio): DAC playback, PSG envelope preview, MIDI frequency tables"
```

---

### Task 6: Tauri IPC Commands — Project Management + Driver Info

**Files:**
- Modify: `src-tauri/src/ipc/commands.rs` (add ProjectState, project + driver commands)
- Modify: `src-tauri/src/ipc/mod.rs` (export new commands)
- Modify: `src-tauri/src/lib.rs` (register ProjectState + new commands)

- [ ] **Step 1: Add ProjectState and project management commands to commands.rs**

Add new imports at the top of `src-tauri/src/ipc/commands.rs`:

```rust
use std::path::PathBuf;
use std::sync::Mutex;
use tauri::State;

use crate::audio::{AudioCommand, AudioThread};
use crate::model::driver::{ChannelLayout, DriverFeature};
use crate::model::song::{Song, SongMetadata};
use crate::project::ProjectManager;
```

Add the new state struct alongside `AudioState`:

```rust
pub struct ProjectState {
    pub manager: Mutex<ProjectManager>,
}
```

Add project management commands after the existing `stop_all_sound`:

```rust
#[tauri::command]
pub fn create_project(
    state: State<'_, ProjectState>,
    path: String,
    name: String,
    driver_id: String,
    tempo: f64,
    time_sig_num: u8,
    time_sig_den: u8,
) -> Result<(), String> {
    let mut mgr = state.manager.lock().map_err(|e| format!("mutex poisoned: {e}"))?;
    mgr.create(&PathBuf::from(path), &name, &driver_id, tempo, (time_sig_num, time_sig_den))
}

#[tauri::command]
pub fn open_project(state: State<'_, ProjectState>, path: String) -> Result<Song, String> {
    let mut mgr = state.manager.lock().map_err(|e| format!("mutex poisoned: {e}"))?;
    mgr.open(&PathBuf::from(path))
}

#[tauri::command]
pub fn save_project(state: State<'_, ProjectState>) -> Result<(), String> {
    let mut mgr = state.manager.lock().map_err(|e| format!("mutex poisoned: {e}"))?;
    mgr.save()
}

#[tauri::command]
pub fn close_project(state: State<'_, ProjectState>) -> Result<(), String> {
    let mut mgr = state.manager.lock().map_err(|e| format!("mutex poisoned: {e}"))?;
    mgr.close();
    Ok(())
}

#[tauri::command]
pub fn get_project_info(state: State<'_, ProjectState>) -> Result<Option<SongMetadata>, String> {
    let mgr = state.manager.lock().map_err(|e| format!("mutex poisoned: {e}"))?;
    Ok(mgr.metadata().cloned())
}

// --- Driver Info ---

#[derive(serde::Serialize)]
pub struct DriverInfo {
    pub id: String,
    pub name: String,
}

#[tauri::command]
pub fn list_drivers(state: State<'_, ProjectState>) -> Result<Vec<DriverInfo>, String> {
    let mgr = state.manager.lock().map_err(|e| format!("mutex poisoned: {e}"))?;
    Ok(mgr
        .driver_registry()
        .list()
        .into_iter()
        .map(|(id, name)| DriverInfo {
            id: id.to_string(),
            name: name.to_string(),
        })
        .collect())
}

#[derive(serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DriverDetail {
    pub id: String,
    pub name: String,
    pub layout: ChannelLayout,
    pub features: Vec<DriverFeature>,
}

#[tauri::command]
pub fn get_driver_info(state: State<'_, ProjectState>, driver_id: String) -> Result<DriverDetail, String> {
    let mgr = state.manager.lock().map_err(|e| format!("mutex poisoned: {e}"))?;
    let driver = mgr
        .driver_registry()
        .get(&driver_id)
        .ok_or_else(|| format!("unknown driver: {driver_id}"))?;

    let all_features = [
        DriverFeature::SsgEg,
        DriverFeature::Fm3SpecialMode,
        DriverFeature::MultiDac,
        DriverFeature::Dpcm,
        DriverFeature::PseudoStereo,
    ];
    let features: Vec<DriverFeature> = all_features
        .into_iter()
        .filter(|&f| driver.supports_feature(f))
        .collect();

    Ok(DriverDetail {
        id: driver.id().to_string(),
        name: driver.name().to_string(),
        layout: driver.channel_layout(),
        features,
    })
}
```

- [ ] **Step 2: Update ipc/mod.rs to export new commands**

Replace `src-tauri/src/ipc/mod.rs`:

```rust
pub mod commands;

pub use commands::{
    AudioState, ProjectState,
    play_fm_test_tone, play_psg_test_tone, stop_all_sound,
    create_project, open_project, save_project, close_project, get_project_info,
    list_drivers, get_driver_info,
};
```

- [ ] **Step 3: Wire ProjectState into lib.rs**

Replace `src-tauri/src/lib.rs`:

```rust
mod audio;
mod dac;
mod driver;
mod ipc;
mod model;
mod project;
mod sn76489;
mod ym2612;

use std::sync::Mutex;

use audio::AudioThread;
use driver::FlamedriverProfile;
use ipc::{
    AudioState, ProjectState,
    close_project, create_project, get_driver_info, get_project_info,
    list_drivers, open_project, play_fm_test_tone, play_psg_test_tone,
    save_project, stop_all_sound,
};
use model::driver::DriverRegistry;
use project::ProjectManager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let audio_thread = AudioThread::new().expect("failed to initialize audio thread");

    let mut registry = DriverRegistry::new();
    registry.register(Box::new(FlamedriverProfile));
    let project_manager = ProjectManager::new(registry);

    tauri::Builder::default()
        .manage(AudioState {
            thread: Mutex::new(audio_thread),
        })
        .manage(ProjectState {
            manager: Mutex::new(project_manager),
        })
        .invoke_handler(tauri::generate_handler![
            play_fm_test_tone,
            play_psg_test_tone,
            stop_all_sound,
            create_project,
            open_project,
            save_project,
            close_project,
            get_project_info,
            list_drivers,
            get_driver_info,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

- [ ] **Step 4: Verify it compiles**

Run: `cd /home/volence/sonic_hacks/megadaw/src-tauri && cargo build`
Expected: compiles with no errors

- [ ] **Step 5: Run all tests**

Run: `cd /home/volence/sonic_hacks/megadaw/src-tauri && cargo test`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add src-tauri/src/ipc/ src-tauri/src/lib.rs
git commit -m "feat(ipc): project management + driver info Tauri commands"
```

---

### Task 7: Tauri IPC Commands — Instrument CRUD + Preview

**Files:**
- Modify: `src-tauri/src/ipc/commands.rs` (add FM/PSG/DAC CRUD + preview commands)
- Modify: `src-tauri/src/ipc/mod.rs` (export new commands)
- Modify: `src-tauri/src/lib.rs` (register new commands in handler)

- [ ] **Step 1: Add FM instrument CRUD + preview commands to commands.rs**

Add these imports to the top of `commands.rs` (alongside existing imports):

```rust
use std::sync::Arc;
use uuid::Uuid;
use crate::audio::frequency::{midi_to_fm_freq, midi_to_psg_period};
use crate::model::instrument::*;
use crate::dac;
```

Add FM instrument commands:

```rust
#[tauri::command]
pub fn add_fm_instrument(
    state: State<'_, ProjectState>,
    instrument: FmInstrument,
) -> Result<String, String> {
    let mut mgr = state.manager.lock().map_err(|e| format!("mutex poisoned: {e}"))?;
    let id = mgr.add_fm_instrument(instrument);
    Ok(id.to_string())
}

#[tauri::command]
pub fn update_fm_instrument(
    state: State<'_, ProjectState>,
    id: String,
    instrument: FmInstrument,
) -> Result<(), String> {
    let uuid = Uuid::parse_str(&id).map_err(|e| format!("invalid UUID: {e}"))?;
    let mut mgr = state.manager.lock().map_err(|e| format!("mutex poisoned: {e}"))?;
    mgr.update_fm_instrument(uuid, instrument)
}

#[tauri::command]
pub fn delete_fm_instrument(state: State<'_, ProjectState>, id: String) -> Result<(), String> {
    let uuid = Uuid::parse_str(&id).map_err(|e| format!("invalid UUID: {e}"))?;
    let mut mgr = state.manager.lock().map_err(|e| format!("mutex poisoned: {e}"))?;
    mgr.delete_fm_instrument(uuid)
}

#[tauri::command]
pub fn list_fm_instruments(state: State<'_, ProjectState>) -> Result<Vec<FmInstrument>, String> {
    let mgr = state.manager.lock().map_err(|e| format!("mutex poisoned: {e}"))?;
    Ok(mgr.list_fm_instruments().to_vec())
}

/// YM2612 operator-to-register-slot offset mapping.
/// Op1→slot 0 (+0), Op2→slot 2 (+8), Op3→slot 1 (+4), Op4→slot 3 (+12)
const OP_REG_OFFSETS: [u8; 4] = [0x00, 0x08, 0x04, 0x0C];

fn ym_write_port(thread: &mut AudioThread, port: u8, addr: u8, data: u8) {
    thread.send(AudioCommand::Ym2612Write { port: port as u32, data: addr });
    thread.send(AudioCommand::Ym2612Write { port: (port + 1) as u32, data });
}

#[tauri::command]
pub fn preview_fm_instrument(
    audio_state: State<'_, AudioState>,
    project_state: State<'_, ProjectState>,
    id: String,
    midi_note: u8,
) -> Result<(), String> {
    let uuid = Uuid::parse_str(&id).map_err(|e| format!("invalid UUID: {e}"))?;
    let mgr = project_state.manager.lock().map_err(|e| format!("mutex poisoned: {e}"))?;
    let inst = mgr
        .get_fm_instrument(&uuid)
        .ok_or("FM instrument not found")?
        .clone();
    drop(mgr);

    let mut thread = audio_state.thread.lock().map_err(|e| format!("mutex poisoned: {e}"))?;

    // Use channel 0 (Part I, offset 0)
    let ch: u8 = 0;
    let port: u8 = 0;

    // Key off first
    thread.send(AudioCommand::FmKeyOff { channel: ch });

    // Algorithm + Feedback
    ym_write_port(&mut thread, port, 0xB0 + ch, (inst.feedback << 3) | inst.algorithm);
    // Stereo L+R
    ym_write_port(&mut thread, port, 0xB4 + ch, 0xC0);

    // Program all 4 operators
    for (i, op) in inst.operators.iter().enumerate() {
        let slot = OP_REG_OFFSETS[i] + ch;
        ym_write_port(&mut thread, port, 0x30 + slot, (op.detune << 4) | op.multiple);
        ym_write_port(&mut thread, port, 0x40 + slot, op.total_level);
        ym_write_port(&mut thread, port, 0x50 + slot, (op.rate_scale << 6) | op.attack_rate);
        ym_write_port(&mut thread, port, 0x60 + slot, ((op.amp_mod as u8) << 7) | op.d1r);
        ym_write_port(&mut thread, port, 0x70 + slot, op.d2r);
        ym_write_port(&mut thread, port, 0x80 + slot, (op.sustain_level << 4) | op.release_rate);
    }

    // Set frequency from MIDI note
    let (block, fnum) = midi_to_fm_freq(midi_note);
    let freq_msb = (block << 3) | ((fnum >> 8) as u8 & 0x07);
    let freq_lsb = (fnum & 0xFF) as u8;
    ym_write_port(&mut thread, port, 0xA4 + ch, freq_msb);
    ym_write_port(&mut thread, port, 0xA0 + ch, freq_lsb);

    // Key on all operators
    thread.send(AudioCommand::FmKeyOn { channel: ch, operators: 0xF0 });

    Ok(())
}
```

- [ ] **Step 2: Add PSG instrument CRUD + preview commands**

```rust
#[tauri::command]
pub fn add_psg_instrument(
    state: State<'_, ProjectState>,
    instrument: PsgInstrument,
) -> Result<String, String> {
    let mut mgr = state.manager.lock().map_err(|e| format!("mutex poisoned: {e}"))?;
    let id = mgr.add_psg_instrument(instrument);
    Ok(id.to_string())
}

#[tauri::command]
pub fn update_psg_instrument(
    state: State<'_, ProjectState>,
    id: String,
    instrument: PsgInstrument,
) -> Result<(), String> {
    let uuid = Uuid::parse_str(&id).map_err(|e| format!("invalid UUID: {e}"))?;
    let mut mgr = state.manager.lock().map_err(|e| format!("mutex poisoned: {e}"))?;
    mgr.update_psg_instrument(uuid, instrument)
}

#[tauri::command]
pub fn delete_psg_instrument(state: State<'_, ProjectState>, id: String) -> Result<(), String> {
    let uuid = Uuid::parse_str(&id).map_err(|e| format!("invalid UUID: {e}"))?;
    let mut mgr = state.manager.lock().map_err(|e| format!("mutex poisoned: {e}"))?;
    mgr.delete_psg_instrument(uuid)
}

#[tauri::command]
pub fn list_psg_instruments(state: State<'_, ProjectState>) -> Result<Vec<PsgInstrument>, String> {
    let mgr = state.manager.lock().map_err(|e| format!("mutex poisoned: {e}"))?;
    Ok(mgr.list_psg_instruments().to_vec())
}

#[tauri::command]
pub fn preview_psg_instrument(
    audio_state: State<'_, AudioState>,
    project_state: State<'_, ProjectState>,
    id: String,
    midi_note: u8,
) -> Result<(), String> {
    let uuid = Uuid::parse_str(&id).map_err(|e| format!("invalid UUID: {e}"))?;
    let mgr = project_state.manager.lock().map_err(|e| format!("mutex poisoned: {e}"))?;
    let inst = mgr
        .get_psg_instrument(&uuid)
        .ok_or("PSG instrument not found")?
        .clone();
    drop(mgr);

    let mut thread = audio_state.thread.lock().map_err(|e| format!("mutex poisoned: {e}"))?;

    let period = midi_to_psg_period(midi_note);
    let channel: u8 = 0;

    thread.send(AudioCommand::PsgEnvelopePreview {
        channel,
        period,
        envelope: Arc::new(inst.volume_sequence),
        loop_point: inst.loop_point,
    });

    Ok(())
}
```

- [ ] **Step 3: Add DAC instrument commands**

```rust
#[tauri::command]
pub fn import_dac_wav(
    state: State<'_, ProjectState>,
    wav_path: String,
    target_rate: u32,
) -> Result<String, String> {
    let mut mgr = state.manager.lock().map_err(|e| format!("mutex poisoned: {e}"))?;
    let project_path = mgr.project_path().ok_or("no project open")?.to_path_buf();

    let pcm_data = dac::import_wav(std::path::Path::new(&wav_path), target_rate)?;

    let id = Uuid::new_v4();
    let original_filename = std::path::Path::new(&wav_path)
        .file_name()
        .map(|f| f.to_string_lossy().to_string())
        .unwrap_or_else(|| format!("{id}.wav"));

    // Copy original WAV into project
    let dest_wav = format!("{id}.wav");
    std::fs::copy(&wav_path, project_path.join("instruments/dac").join(&dest_wav))
        .map_err(|e| format!("failed to copy WAV: {e}"))?;

    // Write PCM file
    let pcm_filename = format!("{id}.pcm");
    std::fs::write(
        project_path.join("instruments/dac").join(&pcm_filename),
        &pcm_data,
    )
    .map_err(|e| format!("failed to write PCM: {e}"))?;

    let inst = DacInstrument {
        id,
        name: original_filename,
        target_sample_rate: target_rate,
        loop_start: None,
        loop_length: None,
        original_file: dest_wav,
        pcm_file: pcm_filename,
        source_is_raw: false,
        metadata: InstrumentMetadata::default(),
    };

    mgr.add_dac_instrument(inst, pcm_data);
    Ok(id.to_string())
}

#[tauri::command]
pub fn import_dac_raw(
    state: State<'_, ProjectState>,
    pcm_path: String,
    sample_rate: u32,
) -> Result<String, String> {
    let mut mgr = state.manager.lock().map_err(|e| format!("mutex poisoned: {e}"))?;
    let project_path = mgr.project_path().ok_or("no project open")?.to_path_buf();

    let pcm_data = dac::import_raw(std::path::Path::new(&pcm_path))?;

    let id = Uuid::new_v4();
    let original_filename = std::path::Path::new(&pcm_path)
        .file_name()
        .map(|f| f.to_string_lossy().to_string())
        .unwrap_or_else(|| format!("{id}.raw"));

    // Copy raw file into project
    let dest_raw = format!("{id}.raw");
    std::fs::copy(&pcm_path, project_path.join("instruments/dac").join(&dest_raw))
        .map_err(|e| format!("failed to copy raw PCM: {e}"))?;

    // PCM is the same as raw (already Genesis format)
    let pcm_filename = format!("{id}.pcm");
    std::fs::write(
        project_path.join("instruments/dac").join(&pcm_filename),
        &pcm_data,
    )
    .map_err(|e| format!("failed to write PCM: {e}"))?;

    let inst = DacInstrument {
        id,
        name: original_filename,
        target_sample_rate: sample_rate,
        loop_start: None,
        loop_length: None,
        original_file: dest_raw,
        pcm_file: pcm_filename,
        source_is_raw: true,
        metadata: InstrumentMetadata::default(),
    };

    mgr.add_dac_instrument(inst, pcm_data);
    Ok(id.to_string())
}

#[tauri::command]
pub fn update_dac_instrument(
    state: State<'_, ProjectState>,
    id: String,
    instrument: DacInstrument,
) -> Result<(), String> {
    let uuid = Uuid::parse_str(&id).map_err(|e| format!("invalid UUID: {e}"))?;
    let mut mgr = state.manager.lock().map_err(|e| format!("mutex poisoned: {e}"))?;
    mgr.update_dac_instrument(uuid, instrument)
}

#[tauri::command]
pub fn reconvert_dac(state: State<'_, ProjectState>, id: String, new_rate: u32) -> Result<(), String> {
    let uuid = Uuid::parse_str(&id).map_err(|e| format!("invalid UUID: {e}"))?;
    let mut mgr = state.manager.lock().map_err(|e| format!("mutex poisoned: {e}"))?;
    let project_path = mgr.project_path().ok_or("no project open")?.to_path_buf();

    let inst = mgr
        .get_dac_instrument(&uuid)
        .ok_or("DAC instrument not found")?
        .clone();

    if inst.source_is_raw {
        return Err("cannot reconvert raw PCM import (no higher-quality source)".into());
    }

    let wav_path = project_path.join("instruments/dac").join(&inst.original_file);
    let pcm_data = dac::import_wav(&wav_path, new_rate)?;

    // Overwrite PCM file
    std::fs::write(
        project_path.join("instruments/dac").join(&inst.pcm_file),
        &pcm_data,
    )
    .map_err(|e| format!("failed to write PCM: {e}"))?;

    // Update metadata
    let mut updated = inst;
    updated.target_sample_rate = new_rate;
    mgr.update_dac_instrument(uuid, updated)?;
    mgr.update_dac_pcm(uuid, pcm_data);

    Ok(())
}

#[tauri::command]
pub fn delete_dac_instrument(state: State<'_, ProjectState>, id: String) -> Result<(), String> {
    let uuid = Uuid::parse_str(&id).map_err(|e| format!("invalid UUID: {e}"))?;
    let mut mgr = state.manager.lock().map_err(|e| format!("mutex poisoned: {e}"))?;
    mgr.delete_dac_instrument(uuid)
}

#[tauri::command]
pub fn list_dac_instruments(state: State<'_, ProjectState>) -> Result<Vec<DacInstrument>, String> {
    let mgr = state.manager.lock().map_err(|e| format!("mutex poisoned: {e}"))?;
    Ok(mgr.list_dac_instruments().to_vec())
}

#[tauri::command]
pub fn preview_dac(
    audio_state: State<'_, AudioState>,
    project_state: State<'_, ProjectState>,
    id: String,
) -> Result<(), String> {
    let uuid = Uuid::parse_str(&id).map_err(|e| format!("invalid UUID: {e}"))?;
    let mgr = project_state.manager.lock().map_err(|e| format!("mutex poisoned: {e}"))?;
    let inst = mgr
        .get_dac_instrument(&uuid)
        .ok_or("DAC instrument not found")?;
    let pcm = mgr
        .get_dac_pcm(&uuid)
        .ok_or("DAC PCM data not loaded")?;
    let sample_rate = inst.target_sample_rate;
    drop(mgr);

    let mut thread = audio_state.thread.lock().map_err(|e| format!("mutex poisoned: {e}"))?;
    thread.send(AudioCommand::DacPlayback {
        samples: pcm,
        sample_rate,
    });

    Ok(())
}
```

- [ ] **Step 4: Update ipc/mod.rs with all exports**

Replace `src-tauri/src/ipc/mod.rs`:

```rust
pub mod commands;

pub use commands::{
    AudioState, ProjectState,
    // Phase 1
    play_fm_test_tone, play_psg_test_tone, stop_all_sound,
    // Project management
    create_project, open_project, save_project, close_project, get_project_info,
    // Driver info
    list_drivers, get_driver_info,
    // FM instruments
    add_fm_instrument, update_fm_instrument, delete_fm_instrument,
    list_fm_instruments, preview_fm_instrument,
    // PSG instruments
    add_psg_instrument, update_psg_instrument, delete_psg_instrument,
    list_psg_instruments, preview_psg_instrument,
    // DAC instruments
    import_dac_wav, import_dac_raw, update_dac_instrument, reconvert_dac,
    delete_dac_instrument, list_dac_instruments, preview_dac,
};
```

- [ ] **Step 5: Register all commands in lib.rs invoke_handler**

Update the `invoke_handler` in `src-tauri/src/lib.rs` to include all new commands. Replace the existing `invoke_handler` block and update the imports:

```rust
use ipc::{
    AudioState, ProjectState,
    // Phase 1
    play_fm_test_tone, play_psg_test_tone, stop_all_sound,
    // Project management
    create_project, open_project, save_project, close_project, get_project_info,
    // Driver info
    list_drivers, get_driver_info,
    // FM instruments
    add_fm_instrument, update_fm_instrument, delete_fm_instrument,
    list_fm_instruments, preview_fm_instrument,
    // PSG instruments
    add_psg_instrument, update_psg_instrument, delete_psg_instrument,
    list_psg_instruments, preview_psg_instrument,
    // DAC instruments
    import_dac_wav, import_dac_raw, update_dac_instrument, reconvert_dac,
    delete_dac_instrument, list_dac_instruments, preview_dac,
};
```

And the handler:

```rust
        .invoke_handler(tauri::generate_handler![
            play_fm_test_tone,
            play_psg_test_tone,
            stop_all_sound,
            create_project,
            open_project,
            save_project,
            close_project,
            get_project_info,
            list_drivers,
            get_driver_info,
            add_fm_instrument,
            update_fm_instrument,
            delete_fm_instrument,
            list_fm_instruments,
            preview_fm_instrument,
            add_psg_instrument,
            update_psg_instrument,
            delete_psg_instrument,
            list_psg_instruments,
            preview_psg_instrument,
            import_dac_wav,
            import_dac_raw,
            update_dac_instrument,
            reconvert_dac,
            delete_dac_instrument,
            list_dac_instruments,
            preview_dac,
        ])
```

- [ ] **Step 6: Build and run all tests**

Run: `cd /home/volence/sonic_hacks/megadaw/src-tauri && cargo build && cargo test`
Expected: compiles and all tests PASS

- [ ] **Step 7: Commit**

```bash
git add src-tauri/src/ipc/ src-tauri/src/lib.rs
git commit -m "feat(ipc): FM/PSG/DAC instrument CRUD + preview + complete Phase 2 command surface"
```

- [ ] **Step 8: Manual smoke test**

Run: `cd /home/volence/sonic_hacks/megadaw && WEBKIT_DISABLE_COMPOSITING_MODE=1 npm run tauri dev`

Verify the app launches. Phase 1 test buttons should still work. The new IPC commands are registered but have no frontend UI yet — they'll be callable from the browser dev console:

```javascript
// In browser console:
await window.__TAURI__.core.invoke('list_drivers')
await window.__TAURI__.core.invoke('get_driver_info', { driverId: 'flamedriver' })
```

- [ ] **Step 9: Final commit with any fixes**

```bash
git add -A
git commit -m "fix: any compile/runtime fixes from smoke test"
```

(Skip if no fixes needed.)
