# MegaDAW Phase 1: Audio Engine + Scaffold

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a Tauri application that plays accurate Sega Genesis FM tones through Nuked OPN2 and SN76489 emulation, proving the core audio pipeline works end-to-end.

**Architecture:** Tauri v2 app with a Rust audio core running on a dedicated real-time thread. The frontend is a minimal React test panel. The Rust backend owns two chip emulators (Nuked OPN2 for YM2612, pure Rust SN76489), a lock-free ring buffer for commands, and a cpal audio output stream. IPC between frontend and backend uses Tauri commands.

**Tech Stack:** Tauri v2, React 18, TypeScript, Vite, Rust (cpal, rtrb, cc), Nuked OPN2 (vendored C)

**Spec:** `docs/superpowers/specs/2026-05-01-megadaw-design.md`

**Phase overview:** This is Phase 1 of 8. See the spec for the full roadmap. This phase produces: "click a button, hear a Genesis FM tone."

---

## File Structure

```
/home/volence/sonic_hacks/megadaw/
├── src-tauri/
│   ├── Cargo.toml
│   ├── build.rs                        ← Compiles Nuked OPN2 C source via cc crate
│   ├── tauri.conf.json
│   ├── capabilities/
│   │   └── default.json                ← Tauri v2 capability permissions
│   ├── vendor/
│   │   └── nuked-opn2/
│   │       ├── ym3438.c                ← Nuked OPN2 source (vendored from GitHub)
│   │       └── ym3438.h
│   └── src/
│       ├── lib.rs                      ← Tauri entry point, command registration
│       ├── audio/
│       │   ├── mod.rs                  ← Re-exports AudioEngine, AudioThread, AudioCommand
│       │   ├── engine.rs               ← AudioEngine: owns emulators, renders samples
│       │   ├── thread.rs               ← AudioThread: cpal stream, real-time callback
│       │   └── command.rs              ← AudioCommand enum (NoteOn, NoteOff, SetRegister, etc.)
│       ├── ym2612/
│       │   ├── mod.rs                  ← Re-exports Ym2612
│       │   ├── bindings.rs             ← Raw unsafe FFI to Nuked OPN2 C library
│       │   └── chip.rs                 ← Safe Ym2612 wrapper struct
│       ├── sn76489/
│       │   ├── mod.rs                  ← Re-exports Sn76489
│       │   └── chip.rs                 ← Pure Rust SN76489 emulator
│       └── ipc/
│           ├── mod.rs                  ← Re-exports Tauri commands
│           └── commands.rs             ← #[tauri::command] handlers
├── src/
│   ├── main.tsx                        ← React DOM entry
│   ├── App.tsx                         ← Root component, renders TestPanel
│   ├── App.css                         ← Minimal styling
│   └── components/
│       └── TestPanel.tsx               ← Buttons to test FM/PSG/DAC playback
├── index.html
├── package.json
├── tsconfig.json
└── vite.config.ts
```

---

## Task 1: Create Tauri Project Scaffold

**Files:**
- Create: all files under `/home/volence/sonic_hacks/megadaw/`

- [ ] **Step 1: Initialize the Tauri project**

Run from `/home/volence/sonic_hacks/`:

```bash
npm create tauri-app@latest megadaw -- --template react-ts
```

Select defaults when prompted. This creates the full scaffold with Tauri v2, React, TypeScript, and Vite.

- [ ] **Step 2: Verify the scaffold builds**

```bash
cd /home/volence/sonic_hacks/megadaw
npm install
cargo build --manifest-path src-tauri/Cargo.toml
```

Expected: both npm install and cargo build succeed with no errors.

- [ ] **Step 3: Add Rust dependencies to Cargo.toml**

Edit `src-tauri/Cargo.toml` — add these to `[dependencies]`:

```toml
cpal = "0.15"
rtrb = "0.3"
```

Add a `[build-dependencies]` section:

```toml
[build-dependencies]
cc = "1"
```

- [ ] **Step 4: Create the Rust module structure**

Create the directory structure for our audio code:

```bash
mkdir -p src-tauri/src/audio
mkdir -p src-tauri/src/ym2612
mkdir -p src-tauri/src/sn76489
mkdir -p src-tauri/src/ipc
mkdir -p src-tauri/vendor/nuked-opn2
```

Create stub module files so the project compiles:

`src-tauri/src/audio/mod.rs`:
```rust
pub mod command;
pub mod engine;
pub mod thread;
```

`src-tauri/src/audio/command.rs`:
```rust
// AudioCommand will be defined in Task 5
```

`src-tauri/src/audio/engine.rs`:
```rust
// AudioEngine will be defined in Task 6
```

`src-tauri/src/audio/thread.rs`:
```rust
// AudioThread will be defined in Task 7
```

`src-tauri/src/ym2612/mod.rs`:
```rust
pub mod bindings;
pub mod chip;
```

`src-tauri/src/ym2612/bindings.rs`:
```rust
// FFI bindings will be defined in Task 2
```

`src-tauri/src/ym2612/chip.rs`:
```rust
// Ym2612 wrapper will be defined in Task 3
```

`src-tauri/src/sn76489/mod.rs`:
```rust
pub mod chip;
```

`src-tauri/src/sn76489/chip.rs`:
```rust
// Sn76489 emulator will be defined in Task 4
```

`src-tauri/src/ipc/mod.rs`:
```rust
pub mod commands;
```

`src-tauri/src/ipc/commands.rs`:
```rust
// Tauri IPC commands will be defined in Task 8
```

Update `src-tauri/src/lib.rs` to declare all modules:

```rust
mod audio;
mod ym2612;
mod sn76489;
mod ipc;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

- [ ] **Step 5: Verify everything compiles**

```bash
cd /home/volence/sonic_hacks/megadaw
cargo build --manifest-path src-tauri/Cargo.toml
```

Expected: compiles with no errors (warnings about unused modules are fine).

- [ ] **Step 6: Commit**

```bash
cd /home/volence/sonic_hacks/megadaw
git init
git add -A
git commit -m "feat: scaffold Tauri v2 project with module structure"
```

---

## Task 2: Vendor Nuked OPN2 + FFI Bindings

**Files:**
- Create: `src-tauri/vendor/nuked-opn2/ym3438.c`
- Create: `src-tauri/vendor/nuked-opn2/ym3438.h`
- Create: `src-tauri/build.rs`
- Modify: `src-tauri/src/ym2612/bindings.rs`

- [ ] **Step 1: Download Nuked OPN2 source**

```bash
cd /home/volence/sonic_hacks/megadaw/src-tauri/vendor/nuked-opn2
curl -L -O https://raw.githubusercontent.com/nukeykt/Nuked-OPN2/master/ym3438.h
curl -L -O https://raw.githubusercontent.com/nukeykt/Nuked-OPN2/master/ym3438.c
```

Verify both files downloaded (ym3438.h should define `ym3438_t` struct, ym3438.c should contain `OPN2_Clock`).

- [ ] **Step 2: Create build.rs to compile the C source**

`src-tauri/build.rs`:

```rust
fn main() {
    tauri_build::build();

    cc::Build::new()
        .file("vendor/nuked-opn2/ym3438.c")
        .include("vendor/nuked-opn2")
        .opt_level(2)
        .compile("nuked_opn2");
}
```

- [ ] **Step 3: Write FFI bindings**

Read `ym3438.h` to identify the exact struct layout and function signatures, then write the bindings.

`src-tauri/src/ym2612/bindings.rs`:

```rust
#![allow(non_camel_case_types, non_snake_case, dead_code)]

use std::os::raw::{c_int, c_uint};

pub const OPN2_TYPE_YM2612: u32 = 0;
pub const OPN2_TYPE_YM3438: u32 = 1;

// The ym3438_t struct is large and opaque to us.
// We allocate it as a blob of the right size and alignment.
// Check ym3438.h for the actual size — it's typically around 2800-3200 bytes.
// We use a conservatively large buffer and verify size at build time.
#[repr(C)]
pub struct ym3438_t {
    _data: [u8; 4096],
}

extern "C" {
    pub fn OPN2_Reset(chip: *mut ym3438_t);
    pub fn OPN2_SetChipType(chip: *mut ym3438_t, chip_type: c_uint);
    pub fn OPN2_Clock(chip: *mut ym3438_t, buffer: *mut i16);
    pub fn OPN2_Write(chip: *mut ym3438_t, port: c_uint, data: u8);
    pub fn OPN2_Read(chip: *mut ym3438_t, port: c_uint) -> u8;
    pub fn OPN2_SetTestPin(chip: *mut ym3438_t, value: c_uint);
    pub fn OPN2_ReadTestPin(chip: *mut ym3438_t) -> c_uint;
    pub fn OPN2_ReadIRQPin(chip: *mut ym3438_t) -> c_uint;
}
```

**Important:** After downloading `ym3438.h`, check the actual size of `ym3438_t`. If it differs from the 4096-byte buffer above, adjust `_data` to be at least as large. Add a compile-time assertion in Task 3 to verify.

- [ ] **Step 4: Verify compilation**

```bash
cd /home/volence/sonic_hacks/megadaw
cargo build --manifest-path src-tauri/Cargo.toml
```

Expected: compiles successfully. The `cc` crate compiles `ym3438.c` and links it. No undefined symbol errors.

- [ ] **Step 5: Commit**

```bash
cd /home/volence/sonic_hacks/megadaw
git add src-tauri/vendor/ src-tauri/build.rs src-tauri/src/ym2612/bindings.rs
git commit -m "feat: vendor Nuked OPN2 and create FFI bindings"
```

---

## Task 3: Safe YM2612 Wrapper

**Files:**
- Modify: `src-tauri/src/ym2612/chip.rs`
- Modify: `src-tauri/src/ym2612/mod.rs`

- [ ] **Step 1: Write failing test — instantiation and reset**

`src-tauri/src/ym2612/chip.rs`:

```rust
pub struct Ym2612 {
    // will be implemented
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_new_and_reset() {
        let mut chip = Ym2612::new();
        chip.reset();
        // After reset, reading status register should return 0 (no flags set)
        let status = chip.read_status();
        assert_eq!(status, 0);
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/volence/sonic_hacks/megadaw/src-tauri
cargo test ym2612::chip::tests::test_new_and_reset -- --nocapture
```

Expected: FAIL — `Ym2612::new()` not implemented.

- [ ] **Step 3: Implement Ym2612 struct**

`src-tauri/src/ym2612/chip.rs`:

```rust
use super::bindings::*;
use std::mem::MaybeUninit;

pub struct Ym2612 {
    chip: Box<ym3438_t>,
}

impl Ym2612 {
    pub fn new() -> Self {
        let mut chip = unsafe {
            let mut chip = Box::new(MaybeUninit::<ym3438_t>::zeroed().assume_init());
            OPN2_SetChipType(&mut *chip, OPN2_TYPE_YM2612);
            OPN2_Reset(&mut *chip);
            chip
        };
        Self { chip }
    }

    pub fn reset(&mut self) {
        unsafe {
            OPN2_Reset(&mut *self.chip);
        }
    }

    pub fn read_status(&mut self) -> u8 {
        unsafe { OPN2_Read(&mut *self.chip, 0) }
    }

    /// Write to a YM2612 register.
    /// port: 0 = Part I address, 1 = Part I data, 2 = Part II address, 3 = Part II data
    pub fn write(&mut self, port: u32, data: u8) {
        unsafe {
            OPN2_Write(&mut *self.chip, port, data);
        }
    }

    /// Advance one master clock cycle. Returns a stereo sample pair [left, right]
    /// when the chip produces output (every 24 clocks), or [0, 0] otherwise.
    pub fn clock(&mut self) -> [i16; 2] {
        let mut buffer = [0i16; 2];
        unsafe {
            OPN2_Clock(&mut *self.chip, buffer.as_mut_ptr());
        }
        buffer
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_new_and_reset() {
        let mut chip = Ym2612::new();
        chip.reset();
        let status = chip.read_status();
        assert_eq!(status, 0);
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /home/volence/sonic_hacks/megadaw/src-tauri
cargo test ym2612::chip::tests::test_new_and_reset -- --nocapture
```

Expected: PASS.

- [ ] **Step 5: Write test — FM tone generation produces non-silent output**

Add to the `tests` module in `chip.rs`:

```rust
#[test]
fn test_fm_tone_produces_output() {
    let mut chip = Ym2612::new();

    // Program a simple sine tone on FM channel 1 (algorithm 7 = all carriers)
    // Part I registers: address port 0, data port 1

    // Set algorithm 7 (all ops are carriers), feedback 0
    chip.write(0, 0xB0); // Register $B0 = Ch1 feedback/algorithm
    chip.write(1, 0x07); // Algorithm 7, feedback 0

    // Operator 1 (slot 0): set TL to 0 (max volume)
    chip.write(0, 0x40); // Register $40 = Op1 Total Level
    chip.write(1, 0x00); // TL = 0 (loudest)

    // Operator 1: fast attack
    chip.write(0, 0x50); // Register $50 = Op1 Attack Rate
    chip.write(1, 0x1F); // AR = 31 (fastest)

    // Operator 1: sustain level 0, release rate 0 (sustain forever)
    chip.write(0, 0x80); // Register $80 = Op1 Sustain Level / Release Rate
    chip.write(1, 0x00); // SL=0, RR=0

    // Operator 1: multiply = 1
    chip.write(0, 0x30); // Register $30 = Op1 Detune/Multiply
    chip.write(1, 0x01); // DT=0, MUL=1

    // Set frequency (A4 = 440Hz-ish, F-Number ~653 at block 4)
    chip.write(0, 0xA4); // Register $A4 = Ch1 frequency MSB (block + F-num high)
    chip.write(1, 0x22); // Block 4, F-num high bits
    chip.write(0, 0xA0); // Register $A0 = Ch1 frequency LSB
    chip.write(1, 0x8D); // F-num low bits

    // Key on: all operators for channel 1
    chip.write(0, 0x28); // Register $28 = Key On/Off
    chip.write(1, 0xF0); // All 4 ops on, channel 0 (ch1 = 0 in register space)

    // Clock the chip for a while and collect output
    let mut found_nonzero = false;
    for _ in 0..10000 {
        let sample = chip.clock();
        if sample[0] != 0 || sample[1] != 0 {
            found_nonzero = true;
            break;
        }
    }

    assert!(found_nonzero, "FM tone should produce non-zero audio output");
}
```

- [ ] **Step 6: Run test to verify it passes**

```bash
cd /home/volence/sonic_hacks/megadaw/src-tauri
cargo test ym2612::chip::tests::test_fm_tone_produces_output -- --nocapture
```

Expected: PASS — after programming registers and clocking, the chip produces non-zero samples.

- [ ] **Step 7: Update mod.rs and commit**

`src-tauri/src/ym2612/mod.rs`:
```rust
pub mod bindings;
pub mod chip;

pub use chip::Ym2612;
```

```bash
cd /home/volence/sonic_hacks/megadaw
git add src-tauri/src/ym2612/
git commit -m "feat: safe Ym2612 wrapper with Nuked OPN2, FM tone test passing"
```

---

## Task 4: Pure Rust SN76489 Emulator

**Files:**
- Modify: `src-tauri/src/sn76489/chip.rs`
- Modify: `src-tauri/src/sn76489/mod.rs`

The SN76489 is simple enough for a correct pure-Rust implementation: 3 tone channels (10-bit period counters), 1 noise channel (16-bit LFSR), 4-bit attenuation per channel.

- [ ] **Step 1: Write failing test — instantiation**

`src-tauri/src/sn76489/chip.rs`:

```rust
pub struct Sn76489 {
    // will be implemented
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_new_is_silent() {
        let mut chip = Sn76489::new();
        // After creation, all channels should be muted (attenuation = 0xF)
        let sample = chip.render_sample();
        assert_eq!(sample, 0, "New chip should be silent");
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/volence/sonic_hacks/megadaw/src-tauri
cargo test sn76489::chip::tests::test_new_is_silent -- --nocapture
```

Expected: FAIL — `Sn76489::new()` not implemented.

- [ ] **Step 3: Implement SN76489 emulator**

`src-tauri/src/sn76489/chip.rs`:

```rust
const VOLUME_TABLE: [i16; 16] = [
    8191, 6507, 5168, 4105, 3261, 2590, 2057, 1634,
    1298, 1031, 819, 650, 516, 410, 326, 0,
];

// SN76489 uses a 16-bit LFSR with taps at bits 0 and 3 for white noise
const NOISE_TAPPED: u16 = 0x0009;

pub struct Sn76489 {
    tone_period: [u16; 3],
    tone_counter: [u16; 3],
    tone_output: [bool; 3],
    volume: [u8; 4],          // 0-15, 15 = silent
    noise_shift: u16,
    noise_period: u8,         // 0-3 (selects divider)
    noise_white: bool,
    noise_counter: u16,
    latched_channel: u8,      // 0-3
    latched_type: bool,       // false = tone/noise, true = volume
}

impl Sn76489 {
    pub fn new() -> Self {
        Self {
            tone_period: [0; 3],
            tone_counter: [0; 3],
            tone_output: [false; 3],
            volume: [0xF, 0xF, 0xF, 0xF], // all muted
            noise_shift: 0x8000,
            noise_period: 0,
            noise_white: false,
            noise_counter: 0x10,
            latched_channel: 0,
            latched_type: false,
        }
    }

    pub fn reset(&mut self) {
        *self = Self::new();
    }

    /// Write a byte to the SN76489 register interface.
    /// Bit 7 = 1: latch/data byte (sets channel + type + low data bits)
    /// Bit 7 = 0: data byte (writes to previously latched register)
    pub fn write(&mut self, data: u8) {
        if data & 0x80 != 0 {
            // Latch byte
            self.latched_channel = (data >> 5) & 0x03;
            self.latched_type = data & 0x10 != 0;
            let value = (data & 0x0F) as u16;

            if self.latched_type {
                // Volume register
                self.volume[self.latched_channel as usize] = value as u8;
            } else if self.latched_channel < 3 {
                // Tone register low 4 bits
                let ch = self.latched_channel as usize;
                self.tone_period[ch] = (self.tone_period[ch] & 0x3F0) | value;
            } else {
                // Noise register
                self.noise_white = value & 0x04 != 0;
                self.noise_period = (value & 0x03) as u8;
                self.noise_shift = 0x8000;
            }
        } else {
            // Data byte — writes to latched register
            let value = (data & 0x3F) as u16;

            if self.latched_type {
                self.volume[self.latched_channel as usize] = (data & 0x0F) as u8;
            } else if self.latched_channel < 3 {
                let ch = self.latched_channel as usize;
                self.tone_period[ch] = (self.tone_period[ch] & 0x00F) | (value << 4);
            } else {
                self.noise_white = (data & 0x04) != 0;
                self.noise_period = (data & 0x03) as u8;
                self.noise_shift = 0x8000;
            }
        }
    }

    /// Clock the chip by one PSG cycle (master_clock / 16).
    /// Call this at the PSG clock rate.
    pub fn clock(&mut self) {
        // Tone channels
        for ch in 0..3 {
            if self.tone_counter[ch] > 0 {
                self.tone_counter[ch] -= 1;
            } else {
                self.tone_counter[ch] = self.tone_period[ch];
                self.tone_output[ch] = !self.tone_output[ch];
            }
        }

        // Noise channel
        let noise_period = match self.noise_period {
            0 => 0x10,
            1 => 0x20,
            2 => 0x40,
            _ => self.tone_period[2],  // period 3 uses tone channel 2's period
        };

        if self.noise_counter > 0 {
            self.noise_counter -= 1;
        } else {
            self.noise_counter = noise_period;
            let feedback = if self.noise_white {
                (self.noise_shift & NOISE_TAPPED).count_ones() & 1
            } else {
                self.noise_shift & 1
            };
            self.noise_shift = (self.noise_shift >> 1) | (feedback as u16) << 15;
        }
    }

    /// Render one mixed output sample (mono). Returns a signed 16-bit value.
    pub fn render_sample(&self) -> i16 {
        let mut output: i32 = 0;

        for ch in 0..3 {
            if self.tone_output[ch] {
                output += VOLUME_TABLE[self.volume[ch] as usize] as i32;
            }
        }

        // Noise channel: use bit 0 of shift register
        if self.noise_shift & 1 != 0 {
            output += VOLUME_TABLE[self.volume[3] as usize] as i32;
        }

        output.clamp(-32768, 32767) as i16
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_new_is_silent() {
        let chip = Sn76489::new();
        let sample = chip.render_sample();
        assert_eq!(sample, 0, "New chip should be silent");
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /home/volence/sonic_hacks/megadaw/src-tauri
cargo test sn76489::chip::tests::test_new_is_silent -- --nocapture
```

Expected: PASS.

- [ ] **Step 5: Write test — PSG tone produces output**

Add to the `tests` module:

```rust
#[test]
fn test_tone_produces_output() {
    let mut chip = Sn76489::new();

    // Set channel 0 volume to max (attenuation 0)
    chip.write(0x90);   // Latch ch0 volume, value 0 (loudest)

    // Set channel 0 tone period to 100
    chip.write(0x80 | 4);    // Latch ch0 tone, low nibble = 4
    chip.write(0x00 | 6);    // Data byte, high bits = 6 → period = (6 << 4) | 4 = 100

    // Clock enough times for the tone to cycle
    let mut found_nonzero = false;
    for _ in 0..1000 {
        chip.clock();
        let sample = chip.render_sample();
        if sample != 0 {
            found_nonzero = true;
            break;
        }
    }

    assert!(found_nonzero, "PSG tone should produce non-zero output");
}

#[test]
fn test_volume_silence() {
    let mut chip = Sn76489::new();

    // Set channel 0 tone but keep volume at 0xF (muted)
    chip.write(0x80 | 4);    // Latch ch0 tone, low nibble = 4
    chip.write(0x00 | 6);    // period = 100

    for _ in 0..1000 {
        chip.clock();
    }
    let sample = chip.render_sample();
    assert_eq!(sample, 0, "Muted channel should produce silence");
}
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
cd /home/volence/sonic_hacks/megadaw/src-tauri
cargo test sn76489::chip::tests -- --nocapture
```

Expected: all 3 PSG tests PASS.

- [ ] **Step 7: Update mod.rs and commit**

`src-tauri/src/sn76489/mod.rs`:
```rust
pub mod chip;

pub use chip::Sn76489;
```

```bash
cd /home/volence/sonic_hacks/megadaw
git add src-tauri/src/sn76489/
git commit -m "feat: pure Rust SN76489 emulator with tone generation tests"
```

---

## Task 5: Audio Command System

**Files:**
- Modify: `src-tauri/src/audio/command.rs`

- [ ] **Step 1: Define AudioCommand enum**

`src-tauri/src/audio/command.rs`:

```rust
#[derive(Debug, Clone)]
pub enum AudioCommand {
    /// Write a value to a YM2612 register.
    /// port: 0=Part I addr, 1=Part I data, 2=Part II addr, 3=Part II data
    Ym2612Write { port: u32, data: u8 },

    /// Write a byte to the SN76489 register interface.
    Sn76489Write { data: u8 },

    /// Key on: trigger note on an FM channel.
    /// channel: 0-5, operators: bitmask of which ops to enable (0xF0 = all 4)
    FmKeyOn { channel: u8, operators: u8 },

    /// Key off: release note on an FM channel.
    FmKeyOff { channel: u8 },

    /// Stop all sound immediately.
    Panic,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_command_is_send() {
        // AudioCommand must be Send to cross thread boundaries via ring buffer
        fn assert_send<T: Send>() {}
        assert_send::<AudioCommand>();
    }

    #[test]
    fn test_command_clone() {
        let cmd = AudioCommand::Ym2612Write { port: 0, data: 0x42 };
        let cmd2 = cmd.clone();
        match cmd2 {
            AudioCommand::Ym2612Write { port, data } => {
                assert_eq!(port, 0);
                assert_eq!(data, 0x42);
            }
            _ => panic!("wrong variant"),
        }
    }
}
```

- [ ] **Step 2: Run tests**

```bash
cd /home/volence/sonic_hacks/megadaw/src-tauri
cargo test audio::command::tests -- --nocapture
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
cd /home/volence/sonic_hacks/megadaw
git add src-tauri/src/audio/command.rs
git commit -m "feat: AudioCommand enum for audio engine communication"
```

---

## Task 6: Audio Engine

**Files:**
- Modify: `src-tauri/src/audio/engine.rs`
- Modify: `src-tauri/src/audio/mod.rs`

The AudioEngine owns both chip emulators and processes commands. It renders audio samples at a given output sample rate by clocking the emulators at the correct rate.

- [ ] **Step 1: Write failing test — engine renders silence when no commands**

`src-tauri/src/audio/engine.rs`:

```rust
pub struct AudioEngine {
    // will be implemented
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_renders_silence_by_default() {
        let mut engine = AudioEngine::new(44100);
        let mut buffer = vec![0.0f32; 128];
        engine.render(&mut buffer);
        assert!(buffer.iter().all(|&s| s == 0.0), "Should render silence");
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/volence/sonic_hacks/megadaw/src-tauri
cargo test audio::engine::tests::test_renders_silence_by_default -- --nocapture
```

Expected: FAIL.

- [ ] **Step 3: Implement AudioEngine**

`src-tauri/src/audio/engine.rs`:

```rust
use crate::audio::command::AudioCommand;
use crate::ym2612::Ym2612;
use crate::sn76489::Sn76489;

const YM2612_MASTER_CLOCK: f64 = 7_670_453.0; // NTSC
const SN76489_CLOCK_DIVIDER: f64 = 16.0;

pub struct AudioEngine {
    ym2612: Ym2612,
    sn76489: Sn76489,
    sample_rate: f64,
    ym_clocks_per_sample: f64,
    psg_clocks_per_sample: f64,
    ym_clock_accumulator: f64,
    psg_clock_accumulator: f64,
}

impl AudioEngine {
    pub fn new(sample_rate: u32) -> Self {
        let sr = sample_rate as f64;
        Self {
            ym2612: Ym2612::new(),
            sn76489: Sn76489::new(),
            sample_rate: sr,
            ym_clocks_per_sample: YM2612_MASTER_CLOCK / sr,
            psg_clocks_per_sample: (YM2612_MASTER_CLOCK / SN76489_CLOCK_DIVIDER) / sr,
            ym_clock_accumulator: 0.0,
            psg_clock_accumulator: 0.0,
        }
    }

    /// Process a single audio command.
    pub fn process_command(&mut self, cmd: AudioCommand) {
        match cmd {
            AudioCommand::Ym2612Write { port, data } => {
                self.ym2612.write(port, data);
            }
            AudioCommand::Sn76489Write { data } => {
                self.sn76489.write(data);
            }
            AudioCommand::FmKeyOn { channel, operators } => {
                self.ym2612.write(0, 0x28);
                self.ym2612.write(1, operators | channel);
            }
            AudioCommand::FmKeyOff { channel } => {
                self.ym2612.write(0, 0x28);
                self.ym2612.write(1, channel);
            }
            AudioCommand::Panic => {
                self.ym2612.reset();
                self.sn76489.reset();
            }
        }
    }

    /// Render interleaved stereo f32 samples into the buffer.
    /// Buffer length must be even (pairs of [left, right]).
    pub fn render(&mut self, buffer: &mut [f32]) {
        let num_frames = buffer.len() / 2;

        for frame in 0..num_frames {
            // Clock YM2612
            self.ym_clock_accumulator += self.ym_clocks_per_sample;
            let ym_clocks = self.ym_clock_accumulator as u32;
            self.ym_clock_accumulator -= ym_clocks as f64;

            let mut ym_left: i32 = 0;
            let mut ym_right: i32 = 0;
            let mut ym_samples = 0;

            for _ in 0..ym_clocks {
                let out = self.ym2612.clock();
                if out[0] != 0 || out[1] != 0 || ym_samples > 0 {
                    ym_left += out[0] as i32;
                    ym_right += out[1] as i32;
                    ym_samples += 1;
                }
            }

            // Average YM2612 output over the clocks
            let (ym_l, ym_r) = if ym_samples > 0 {
                (ym_left / ym_samples, ym_right / ym_samples)
            } else {
                (0, 0)
            };

            // Clock SN76489
            self.psg_clock_accumulator += self.psg_clocks_per_sample;
            let psg_clocks = self.psg_clock_accumulator as u32;
            self.psg_clock_accumulator -= psg_clocks as f64;

            for _ in 0..psg_clocks {
                self.sn76489.clock();
            }
            let psg_sample = self.sn76489.render_sample() as i32;

            // Mix: YM2612 is 14-bit signed, PSG is ~13-bit signed
            // Normalize to f32 [-1.0, 1.0]
            let left = ((ym_l + psg_sample) as f32) / 32768.0;
            let right = ((ym_r + psg_sample) as f32) / 32768.0;

            buffer[frame * 2] = left.clamp(-1.0, 1.0);
            buffer[frame * 2 + 1] = right.clamp(-1.0, 1.0);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_renders_silence_by_default() {
        let mut engine = AudioEngine::new(44100);
        let mut buffer = vec![0.0f32; 128];
        engine.render(&mut buffer);
        assert!(buffer.iter().all(|&s| s == 0.0), "Should render silence");
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /home/volence/sonic_hacks/megadaw/src-tauri
cargo test audio::engine::tests::test_renders_silence_by_default -- --nocapture
```

Expected: PASS.

- [ ] **Step 5: Write test — FM tone through engine produces non-silent output**

Add to the `tests` module:

```rust
#[test]
fn test_fm_tone_through_engine() {
    let mut engine = AudioEngine::new(44100);

    // Program FM channel 1 with a simple tone (same setup as Ym2612 test)
    engine.process_command(AudioCommand::Ym2612Write { port: 0, data: 0xB0 });
    engine.process_command(AudioCommand::Ym2612Write { port: 1, data: 0x07 });
    engine.process_command(AudioCommand::Ym2612Write { port: 0, data: 0x40 });
    engine.process_command(AudioCommand::Ym2612Write { port: 1, data: 0x00 });
    engine.process_command(AudioCommand::Ym2612Write { port: 0, data: 0x50 });
    engine.process_command(AudioCommand::Ym2612Write { port: 1, data: 0x1F });
    engine.process_command(AudioCommand::Ym2612Write { port: 0, data: 0x80 });
    engine.process_command(AudioCommand::Ym2612Write { port: 1, data: 0x00 });
    engine.process_command(AudioCommand::Ym2612Write { port: 0, data: 0x30 });
    engine.process_command(AudioCommand::Ym2612Write { port: 1, data: 0x01 });
    engine.process_command(AudioCommand::Ym2612Write { port: 0, data: 0xA4 });
    engine.process_command(AudioCommand::Ym2612Write { port: 1, data: 0x22 });
    engine.process_command(AudioCommand::Ym2612Write { port: 0, data: 0xA0 });
    engine.process_command(AudioCommand::Ym2612Write { port: 1, data: 0x8D });
    engine.process_command(AudioCommand::FmKeyOn { channel: 0, operators: 0xF0 });

    // Render a buffer and check for non-zero output
    let mut buffer = vec![0.0f32; 4096];
    engine.render(&mut buffer);

    let has_audio = buffer.iter().any(|&s| s.abs() > 0.001);
    assert!(has_audio, "FM tone through engine should produce audible output");
}

#[test]
fn test_panic_silences_everything() {
    let mut engine = AudioEngine::new(44100);

    // Start an FM tone
    engine.process_command(AudioCommand::Ym2612Write { port: 0, data: 0xB0 });
    engine.process_command(AudioCommand::Ym2612Write { port: 1, data: 0x07 });
    engine.process_command(AudioCommand::Ym2612Write { port: 0, data: 0x40 });
    engine.process_command(AudioCommand::Ym2612Write { port: 1, data: 0x00 });
    engine.process_command(AudioCommand::Ym2612Write { port: 0, data: 0x50 });
    engine.process_command(AudioCommand::Ym2612Write { port: 1, data: 0x1F });
    engine.process_command(AudioCommand::Ym2612Write { port: 0, data: 0x80 });
    engine.process_command(AudioCommand::Ym2612Write { port: 1, data: 0x00 });
    engine.process_command(AudioCommand::Ym2612Write { port: 0, data: 0x30 });
    engine.process_command(AudioCommand::Ym2612Write { port: 1, data: 0x01 });
    engine.process_command(AudioCommand::Ym2612Write { port: 0, data: 0xA4 });
    engine.process_command(AudioCommand::Ym2612Write { port: 1, data: 0x22 });
    engine.process_command(AudioCommand::Ym2612Write { port: 0, data: 0xA0 });
    engine.process_command(AudioCommand::Ym2612Write { port: 1, data: 0x8D });
    engine.process_command(AudioCommand::FmKeyOn { channel: 0, operators: 0xF0 });

    // Render to let the tone start
    let mut buffer = vec![0.0f32; 4096];
    engine.render(&mut buffer);

    // Panic
    engine.process_command(AudioCommand::Panic);

    // Render again — should be silent after a brief decay
    let mut buffer2 = vec![0.0f32; 8192];
    engine.render(&mut buffer2);

    // Check the tail of the buffer is silent (allow some decay time at the start)
    let tail = &buffer2[4096..];
    let tail_silent = tail.iter().all(|&s| s.abs() < 0.001);
    assert!(tail_silent, "After panic, output should decay to silence");
}
```

- [ ] **Step 6: Run all engine tests**

```bash
cd /home/volence/sonic_hacks/megadaw/src-tauri
cargo test audio::engine::tests -- --nocapture
```

Expected: all 3 tests PASS.

- [ ] **Step 7: Update mod.rs and commit**

`src-tauri/src/audio/mod.rs`:
```rust
pub mod command;
pub mod engine;
pub mod thread;

pub use command::AudioCommand;
pub use engine::AudioEngine;
```

```bash
cd /home/volence/sonic_hacks/megadaw
git add src-tauri/src/audio/
git commit -m "feat: AudioEngine combining YM2612 + SN76489 with command processing"
```

---

## Task 7: cpal Real-Time Audio Thread

**Files:**
- Modify: `src-tauri/src/audio/thread.rs`

- [ ] **Step 1: Implement AudioThread**

`src-tauri/src/audio/thread.rs`:

```rust
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use rtrb::{Consumer, Producer, RingBuffer};

use crate::audio::command::AudioCommand;
use crate::audio::engine::AudioEngine;

pub struct AudioThread {
    producer: Producer<AudioCommand>,
    stream: cpal::Stream,
    running: Arc<AtomicBool>,
}

impl AudioThread {
    pub fn new() -> Result<Self, Box<dyn std::error::Error>> {
        let host = cpal::default_host();
        let device = host.default_output_device()
            .ok_or("no audio output device found")?;

        let config = device.default_output_config()?;
        let sample_rate = config.sample_rate().0;
        let channels = config.channels() as usize;

        let (producer, consumer) = RingBuffer::new(1024);
        let running = Arc::new(AtomicBool::new(true));
        let running_clone = running.clone();

        let stream = Self::build_stream(
            &device,
            &config.into(),
            consumer,
            sample_rate,
            channels,
            running_clone,
        )?;

        stream.play()?;

        Ok(Self {
            producer,
            stream,
            running,
        })
    }

    fn build_stream(
        device: &cpal::Device,
        config: &cpal::StreamConfig,
        mut consumer: Consumer<AudioCommand>,
        sample_rate: u32,
        channels: usize,
        running: Arc<AtomicBool>,
    ) -> Result<cpal::Stream, Box<dyn std::error::Error>> {
        let mut engine = AudioEngine::new(sample_rate);

        let stream = device.build_output_stream(
            config,
            move |data: &mut [f32], _: &cpal::OutputCallbackInfo| {
                if !running.load(Ordering::Relaxed) {
                    data.fill(0.0);
                    return;
                }

                // Drain all pending commands
                while let Ok(cmd) = consumer.pop() {
                    engine.process_command(cmd);
                }

                // Render stereo into a temp buffer, then distribute to output channels
                if channels == 2 {
                    engine.render(data);
                } else {
                    // For mono or >2 channel configs, render stereo then map
                    let frames = data.len() / channels;
                    let mut stereo_buf = vec![0.0f32; frames * 2];
                    engine.render(&mut stereo_buf);
                    for i in 0..frames {
                        let left = stereo_buf[i * 2];
                        let right = stereo_buf[i * 2 + 1];
                        for ch in 0..channels {
                            data[i * channels + ch] = if ch % 2 == 0 { left } else { right };
                        }
                    }
                }
            },
            |err| {
                eprintln!("audio stream error: {}", err);
            },
            None,
        )?;

        Ok(stream)
    }

    /// Send a command to the audio engine. Non-blocking.
    /// Returns false if the ring buffer is full (command dropped).
    pub fn send(&mut self, cmd: AudioCommand) -> bool {
        self.producer.push(cmd).is_ok()
    }

    /// Stop the audio thread gracefully.
    pub fn stop(&self) {
        self.running.store(false, Ordering::Relaxed);
    }
}
```

- [ ] **Step 2: Verify it compiles**

```bash
cd /home/volence/sonic_hacks/megadaw/src-tauri
cargo build
```

Expected: compiles. No runtime test here — cpal requires an audio device, which may not be available in CI. Manual testing happens in Task 8.

- [ ] **Step 3: Update audio mod.rs exports**

`src-tauri/src/audio/mod.rs`:
```rust
pub mod command;
pub mod engine;
pub mod thread;

pub use command::AudioCommand;
pub use engine::AudioEngine;
pub use thread::AudioThread;
```

- [ ] **Step 4: Commit**

```bash
cd /home/volence/sonic_hacks/megadaw
git add src-tauri/src/audio/
git commit -m "feat: cpal real-time audio thread with lock-free command ring buffer"
```

---

## Task 8: Tauri IPC + Test UI

**Files:**
- Modify: `src-tauri/src/ipc/commands.rs`
- Modify: `src-tauri/src/ipc/mod.rs`
- Modify: `src-tauri/src/lib.rs`
- Modify: `src/App.tsx`
- Create: `src/components/TestPanel.tsx`

- [ ] **Step 1: Create Tauri state and IPC commands**

`src-tauri/src/ipc/commands.rs`:

```rust
use std::sync::Mutex;
use tauri::State;

use crate::audio::AudioThread;
use crate::audio::command::AudioCommand;

pub struct AudioState {
    pub thread: Mutex<AudioThread>,
}

#[tauri::command]
pub fn play_fm_test_tone(state: State<'_, AudioState>) -> Result<String, String> {
    let mut thread = state.thread.lock().map_err(|e| e.to_string())?;

    // Program a simple FM tone on channel 1
    // Algorithm 7 (all carriers), operator 1 only for a clean sine-ish tone
    let commands = vec![
        AudioCommand::Ym2612Write { port: 0, data: 0xB0 },  // algo/feedback
        AudioCommand::Ym2612Write { port: 1, data: 0x07 },  // algo 7, fb 0
        AudioCommand::Ym2612Write { port: 0, data: 0x40 },  // Op1 TL
        AudioCommand::Ym2612Write { port: 1, data: 0x10 },  // slight attenuation
        AudioCommand::Ym2612Write { port: 0, data: 0x50 },  // Op1 AR
        AudioCommand::Ym2612Write { port: 1, data: 0x1F },  // max attack
        AudioCommand::Ym2612Write { port: 0, data: 0x60 },  // Op1 DR
        AudioCommand::Ym2612Write { port: 1, data: 0x05 },  // moderate decay
        AudioCommand::Ym2612Write { port: 0, data: 0x70 },  // Op1 SR
        AudioCommand::Ym2612Write { port: 1, data: 0x02 },  // slow sustain decay
        AudioCommand::Ym2612Write { port: 0, data: 0x80 },  // Op1 SL/RR
        AudioCommand::Ym2612Write { port: 1, data: 0x2A },  // SL=2, RR=10
        AudioCommand::Ym2612Write { port: 0, data: 0x30 },  // Op1 DT/MUL
        AudioCommand::Ym2612Write { port: 1, data: 0x01 },  // DT=0, MUL=1
        AudioCommand::Ym2612Write { port: 0, data: 0xA4 },  // freq MSB
        AudioCommand::Ym2612Write { port: 1, data: 0x22 },  // block 4
        AudioCommand::Ym2612Write { port: 0, data: 0xA0 },  // freq LSB
        AudioCommand::Ym2612Write { port: 1, data: 0x8D },  // ~440Hz
        AudioCommand::FmKeyOn { channel: 0, operators: 0xF0 },
    ];

    for cmd in commands {
        thread.send(cmd);
    }

    Ok("FM tone playing".to_string())
}

#[tauri::command]
pub fn play_psg_test_tone(state: State<'_, AudioState>) -> Result<String, String> {
    let mut thread = state.thread.lock().map_err(|e| e.to_string())?;

    // PSG channel 0: set volume to max, tone period ~440Hz
    // At PSG clock of ~479 kHz, period for 440Hz ≈ 479403/(2*440) ≈ 545 = 0x221
    let commands = vec![
        AudioCommand::Sn76489Write { data: 0x80 | 0x01 },  // ch0 tone low nibble = 1
        AudioCommand::Sn76489Write { data: 0x22 },          // ch0 tone high bits = 0x22 → period = (0x22 << 4) | 1 = 0x221
        AudioCommand::Sn76489Write { data: 0x90 | 0x00 },   // ch0 volume = 0 (max)
    ];

    for cmd in commands {
        thread.send(cmd);
    }

    Ok("PSG tone playing".to_string())
}

#[tauri::command]
pub fn stop_all_sound(state: State<'_, AudioState>) -> Result<String, String> {
    let mut thread = state.thread.lock().map_err(|e| e.to_string())?;
    thread.send(AudioCommand::Panic);
    Ok("All sound stopped".to_string())
}
```

- [ ] **Step 2: Update ipc/mod.rs**

`src-tauri/src/ipc/mod.rs`:
```rust
pub mod commands;

pub use commands::{AudioState, play_fm_test_tone, play_psg_test_tone, stop_all_sound};
```

- [ ] **Step 3: Wire everything into lib.rs**

`src-tauri/src/lib.rs`:

```rust
mod audio;
mod ym2612;
mod sn76489;
mod ipc;

use std::sync::Mutex;
use ipc::{AudioState, play_fm_test_tone, play_psg_test_tone, stop_all_sound};
use audio::AudioThread;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let audio_thread = AudioThread::new()
        .expect("failed to initialize audio thread");

    tauri::Builder::default()
        .manage(AudioState {
            thread: Mutex::new(audio_thread),
        })
        .invoke_handler(tauri::generate_handler![
            play_fm_test_tone,
            play_psg_test_tone,
            stop_all_sound,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

- [ ] **Step 4: Create the React test panel**

`src/components/TestPanel.tsx`:

```tsx
import { invoke } from "@tauri-apps/api/core";
import { useState } from "react";

export function TestPanel() {
  const [status, setStatus] = useState("Ready");

  async function playFmTone() {
    try {
      const result = await invoke<string>("play_fm_test_tone");
      setStatus(result);
    } catch (e) {
      setStatus(`Error: ${e}`);
    }
  }

  async function playPsgTone() {
    try {
      const result = await invoke<string>("play_psg_test_tone");
      setStatus(result);
    } catch (e) {
      setStatus(`Error: ${e}`);
    }
  }

  async function stopAll() {
    try {
      const result = await invoke<string>("stop_all_sound");
      setStatus(result);
    } catch (e) {
      setStatus(`Error: ${e}`);
    }
  }

  return (
    <div style={{ padding: "2rem", fontFamily: "monospace" }}>
      <h1>MegaDAW — Phase 1 Audio Test</h1>
      <p>Status: {status}</p>
      <div style={{ display: "flex", gap: "1rem", marginTop: "1rem" }}>
        <button onClick={playFmTone} style={buttonStyle}>
          Play FM Tone (YM2612)
        </button>
        <button onClick={playPsgTone} style={buttonStyle}>
          Play PSG Tone (SN76489)
        </button>
        <button onClick={stopAll} style={{ ...buttonStyle, background: "#c44" }}>
          Stop All
        </button>
      </div>
      <div style={{ marginTop: "2rem", color: "#888", fontSize: "0.85rem" }}>
        <p>FM: Plays a ~440Hz sine-ish tone through Nuked OPN2 emulation</p>
        <p>PSG: Plays a ~440Hz square wave through SN76489 emulation</p>
        <p>Stop: Resets both chips (panic)</p>
      </div>
    </div>
  );
}

const buttonStyle: React.CSSProperties = {
  padding: "0.75rem 1.5rem",
  fontSize: "1rem",
  fontFamily: "monospace",
  background: "#2a6",
  color: "white",
  border: "none",
  borderRadius: "4px",
  cursor: "pointer",
};
```

- [ ] **Step 5: Update App.tsx to render the test panel**

Replace the contents of `src/App.tsx`:

```tsx
import { TestPanel } from "./components/TestPanel";

function App() {
  return <TestPanel />;
}

export default App;
```

- [ ] **Step 6: Build and test manually**

```bash
cd /home/volence/sonic_hacks/megadaw
npm run tauri dev
```

Manual verification:
1. The app window opens with "MegaDAW — Phase 1 Audio Test"
2. Click "Play FM Tone" → you hear a Genesis-style FM tone through your speakers
3. Click "Stop All" → the tone stops
4. Click "Play PSG Tone" → you hear a square wave beep
5. Click "Stop All" → silence

If no sound plays, check:
- `cargo test` passes (emulators working)
- Audio device is available (`cpal` found an output device)
- Volume is up on the system

- [ ] **Step 7: Commit**

```bash
cd /home/volence/sonic_hacks/megadaw
git add src-tauri/src/ipc/ src-tauri/src/lib.rs src/App.tsx src/components/
git commit -m "feat: Tauri IPC commands + test UI — play FM/PSG tones end-to-end"
```

---

## Verification Checklist

After completing all 8 tasks, verify:

- [ ] `cargo test --manifest-path src-tauri/Cargo.toml` — all tests pass
- [ ] `npm run tauri dev` — app launches, FM and PSG tones play correctly
- [ ] FM tone sounds like a Genesis (not a PC beep, not silence, not distortion)
- [ ] PSG tone sounds like a square wave chiptune tone
- [ ] Stop All silences everything cleanly (no clicks/pops on stop)
- [ ] Git log shows clean, incremental commits for each task
