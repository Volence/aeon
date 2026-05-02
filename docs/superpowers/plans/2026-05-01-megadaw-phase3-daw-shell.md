# MegaDAW Phase 3: DAW Shell + Instrument Management — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the full dark-themed DAW shell with project create/open/save flow, instrument browser, and complete FM/PSG/DAC instrument editors with visual tools and emulator preview.

**Architecture:** Tauri v2 + React 19 frontend with plain CSS modules (no component library). All instrument state lives on the Rust backend — the frontend sends every edit via IPC and renders the result. Custom canvas-based widgets (Knob, EnvelopeDisplay, StepGraphEditor, WaveformViewer, AlgorithmDiagram, PianoKeys) are built from scratch.

**Tech Stack:** Tauri v2, React 19.1, TypeScript 5.8, Vite 7, CSS Modules, `@tauri-apps/plugin-dialog` for file/folder pickers, Canvas API for widgets.

**Spec:** `docs/superpowers/specs/2026-05-01-megadaw-phase3-design.md`

---

## File Structure

### Backend (Rust) — Modify

| File | Change |
|------|--------|
| `src-tauri/Cargo.toml` | Add `tauri-plugin-dialog` |
| `src-tauri/src/ipc/commands.rs` | Add `get_dac_pcm_data` command |
| `src-tauri/src/ipc/mod.rs` | Export new command |
| `src-tauri/src/lib.rs` | Register dialog plugin + new command |
| `src-tauri/capabilities/default.json` | Add `dialog:default` permission |
| `src-tauri/tauri.conf.json` | Window title + size |

### Frontend (TypeScript/React) — Create

| File | Responsibility |
|------|---------------|
| `src/theme/tokens.css` | CSS custom properties — colors, typography |
| `src/types/model.ts` | TypeScript types mirroring Rust model structs |
| `src/api/ipc.ts` | Typed wrappers around all 28 Tauri invoke() calls |
| `src/App.tsx` | Root state machine (welcome / dialog / project-open) |
| `src/App.module.css` | Root layout — flexbox shell |
| `src/components/TopBar.tsx` + `.module.css` | Project info, file actions, transport placeholder |
| `src/components/Sidebar.tsx` + `.module.css` | Two tabs: Tracks / Instruments |
| `src/components/MainArea.tsx` + `.module.css` | Welcome screen or arrangement placeholder |
| `src/components/BottomPanel.tsx` + `.module.css` | Collapsible instrument editor host |
| `src/components/NewProjectDialog.tsx` + `.module.css` | Modal for project creation |
| `src/components/TrackList.tsx` + `.module.css` | Channel list from driver profile |
| `src/components/InstrumentBrowser.tsx` + `.module.css` | FM/PSG/DAC lists with add/delete/rename |
| `src/components/FmEditor.tsx` + `.module.css` | FM instrument editor (operators, knobs, preview) |
| `src/components/PsgEditor.tsx` + `.module.css` | PSG instrument editor (step graph, settings) |
| `src/components/DacEditor.tsx` + `.module.css` | DAC instrument editor (waveform, settings) |
| `src/widgets/Knob.tsx` + `.module.css` | Rotary knob (vertical drag) |
| `src/widgets/EnvelopeDisplay.tsx` | FM ADSR envelope canvas (read-only) |
| `src/widgets/AlgorithmDiagram.tsx` + `.module.css` | FM algorithm topology selector |
| `src/widgets/PianoKeys.tsx` + `.module.css` | Clickable single-octave keyboard |
| `src/widgets/StepGraphEditor.tsx` + `.module.css` | PSG volume envelope (click/drag) |
| `src/widgets/WaveformViewer.tsx` | DAC waveform canvas (read-only) |

### Frontend — Delete

| File | Reason |
|------|--------|
| `src/components/TestPanel.tsx` | Replaced by full UI |
| `src/App.css` | Replaced by App.module.css + tokens.css |

### Frontend — Modify

| File | Change |
|------|--------|
| `src/main.tsx` | Import tokens.css |
| `index.html` | Update title to "MegaDAW" |
| `package.json` | Add `@tauri-apps/plugin-dialog` |

---

### Task 1: Backend — get_dac_pcm_data IPC + dialog plugin

**Files:**
- Modify: `src-tauri/src/project/manager.rs` (add test)
- Modify: `src-tauri/src/ipc/commands.rs` (add command)
- Modify: `src-tauri/src/ipc/mod.rs` (export)
- Modify: `src-tauri/src/lib.rs` (register)
- Modify: `src-tauri/Cargo.toml` (dialog plugin)
- Modify: `src-tauri/capabilities/default.json` (permission)
- Modify: `src-tauri/tauri.conf.json` (window size + title)
- Modify: `index.html` (title)

- [ ] **Step 1: Write test for get_dac_pcm cache retrieval**

Add to the `#[cfg(test)]` block at the bottom of `src-tauri/src/project/manager.rs`:

```rust
#[test]
fn test_get_dac_pcm_returns_cached_data() {
    let path = temp_project_path("dac_pcm");
    let mut mgr = ProjectManager::new(test_registry());
    mgr.create(&path, "PCM Test", "flamedriver", 120.0, (4, 4)).unwrap();

    let inst = DacInstrument {
        id: Uuid::new_v4(),
        name: "Test".into(),
        target_sample_rate: 16000,
        loop_start: None,
        loop_length: None,
        original_file: "test.raw".into(),
        pcm_file: "test.pcm".into(),
        source_is_raw: true,
        metadata: InstrumentMetadata::default(),
    };
    let pcm_data = vec![128u8, 130, 132, 134];
    let id = mgr.add_dac_instrument(inst, pcm_data.clone());

    let cached = mgr.get_dac_pcm(&id).unwrap();
    assert_eq!(cached.as_ref(), &pcm_data);

    assert!(mgr.get_dac_pcm(&Uuid::new_v4()).is_none());

    cleanup(&path);
}
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd /home/volence/sonic_hacks/megadaw && cargo test --lib test_get_dac_pcm`
Expected: PASS (the `get_dac_pcm` method already exists — this test just confirms it)

- [ ] **Step 3: Add get_dac_pcm_data IPC command**

Add to the bottom of `src-tauri/src/ipc/commands.rs`:

```rust
#[tauri::command]
pub fn get_dac_pcm_data(
    state: State<'_, ProjectState>,
    id: String,
) -> Result<Vec<u8>, String> {
    let uuid = Uuid::parse_str(&id).map_err(|e| format!("invalid UUID: {e}"))?;
    let mgr = state.manager.lock().map_err(|e| format!("mutex poisoned: {e}"))?;
    let pcm = mgr
        .get_dac_pcm(&uuid)
        .ok_or("DAC PCM data not loaded")?;
    Ok(pcm.as_ref().clone())
}
```

- [ ] **Step 4: Export from ipc/mod.rs**

Add `get_dac_pcm_data` to the `pub use commands::{...}` block in `src-tauri/src/ipc/mod.rs`:

```rust
pub mod commands;

pub use commands::{
    AudioState, ProjectState,
    play_fm_test_tone, play_psg_test_tone, stop_all_sound,
    create_project, open_project, save_project, close_project, get_project_info,
    list_drivers, get_driver_info,
    add_fm_instrument, update_fm_instrument, delete_fm_instrument,
    list_fm_instruments, preview_fm_instrument,
    add_psg_instrument, update_psg_instrument, delete_psg_instrument,
    list_psg_instruments, preview_psg_instrument,
    import_dac_wav, import_dac_raw, update_dac_instrument, reconvert_dac,
    delete_dac_instrument, list_dac_instruments, preview_dac,
    get_dac_pcm_data,
};
```

- [ ] **Step 5: Register command + dialog plugin in lib.rs**

Replace `src-tauri/src/lib.rs` with:

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
    play_fm_test_tone, play_psg_test_tone, stop_all_sound,
    create_project, open_project, save_project, close_project, get_project_info,
    list_drivers, get_driver_info,
    add_fm_instrument, update_fm_instrument, delete_fm_instrument,
    list_fm_instruments, preview_fm_instrument,
    add_psg_instrument, update_psg_instrument, delete_psg_instrument,
    list_psg_instruments, preview_psg_instrument,
    import_dac_wav, import_dac_raw, update_dac_instrument, reconvert_dac,
    delete_dac_instrument, list_dac_instruments, preview_dac,
    get_dac_pcm_data,
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
        .plugin(tauri_plugin_dialog::init())
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
            get_dac_pcm_data,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

- [ ] **Step 6: Add dialog plugin to Cargo.toml**

Add under `[dependencies]` in `src-tauri/Cargo.toml`:

```toml
tauri-plugin-dialog = "2"
```

- [ ] **Step 7: Add dialog permission to capabilities**

Replace `src-tauri/capabilities/default.json`:

```json
{
  "$schema": "../gen/schemas/desktop-schema.json",
  "identifier": "default",
  "description": "Capability for the main window",
  "windows": ["main"],
  "permissions": [
    "core:default",
    "opener:default",
    "dialog:default"
  ]
}
```

- [ ] **Step 8: Update window config**

Replace the `"app"` section in `src-tauri/tauri.conf.json`:

```json
"app": {
  "windows": [
    {
      "title": "MegaDAW",
      "width": 1280,
      "height": 800
    }
  ],
  "security": {
    "csp": null
  }
}
```

- [ ] **Step 9: Update HTML title**

Change the `<title>` in `index.html` to:

```html
<title>MegaDAW</title>
```

- [ ] **Step 10: Install dialog plugin frontend package**

Run: `cd /home/volence/sonic_hacks/megadaw && npm install @tauri-apps/plugin-dialog`

- [ ] **Step 11: Verify build**

Run: `cd /home/volence/sonic_hacks/megadaw && cargo test --lib`
Expected: All tests pass (54 total — 53 existing + 1 new)

Run: `cd /home/volence/sonic_hacks/megadaw && cargo build`
Expected: Builds successfully with dialog plugin linked

- [ ] **Step 12: Commit**

```bash
cd /home/volence/sonic_hacks/megadaw
git add src-tauri/src/ipc/commands.rs src-tauri/src/ipc/mod.rs src-tauri/src/lib.rs \
  src-tauri/src/project/manager.rs src-tauri/Cargo.toml src-tauri/Cargo.lock \
  src-tauri/capabilities/default.json src-tauri/tauri.conf.json index.html package.json package-lock.json
git commit -m "feat(backend): get_dac_pcm_data IPC + dialog plugin setup"
```

---

### Task 2: Foundation — CSS theme tokens, TypeScript types, IPC wrapper

**Files:**
- Create: `src/theme/tokens.css`
- Create: `src/types/model.ts`
- Create: `src/api/ipc.ts`
- Modify: `src/main.tsx`
- Delete: `src/components/TestPanel.tsx`
- Delete: `src/App.css`

- [ ] **Step 1: Create CSS theme tokens**

Create `src/theme/tokens.css`:

```css
:root {
  --bg-app: #1a1a1a;
  --bg-panel: #2a2a2a;
  --bg-surface: #333333;
  --bg-input: #222222;
  --border: #3a3a3a;
  --border-focus: #555555;
  --text-primary: #e0e0e0;
  --text-secondary: #888888;
  --text-disabled: #555555;
  --accent-fm: #4a9eff;
  --accent-psg: #44cc66;
  --accent-dac: #ff8844;
  --accent-active: #ffffff;
  --knob-track: #444444;
  --knob-fill: #4a9eff;
  --envelope-line: #66ccff;
  --envelope-fill: rgba(102, 204, 255, 0.15);
  --carrier-highlight: #ffcc44;
  --error: #cc4444;
  --success: #44cc66;
}

*, *::before, *::after {
  box-sizing: border-box;
}

html, body {
  margin: 0;
  padding: 0;
  height: 100%;
  overflow: hidden;
  background: var(--bg-app);
  color: var(--text-primary);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 13px;
  line-height: 1.4;
}

#root {
  height: 100%;
}

button {
  font-family: inherit;
  font-size: inherit;
  cursor: pointer;
}

input, select {
  font-family: inherit;
  font-size: inherit;
}
```

- [ ] **Step 2: Create TypeScript model types**

Create `src/types/model.ts`:

```typescript
export interface FmOperator {
  detune: number;
  multiple: number;
  rateScale: number;
  attackRate: number;
  ampMod: boolean;
  d1r: number;
  d2r: number;
  sustainLevel: number;
  releaseRate: number;
  totalLevel: number;
}

export interface InstrumentMetadata {
  category: string;
  author: string;
  tags: string[];
}

export interface FmInstrument {
  id: string;
  name: string;
  algorithm: number;
  feedback: number;
  operators: [FmOperator, FmOperator, FmOperator, FmOperator];
  metadata: InstrumentMetadata;
}

export interface PsgInstrument {
  id: string;
  name: string;
  volumeSequence: number[];
  loopPoint: number | null;
  noiseMode: NoiseMode | null;
  metadata: InstrumentMetadata;
}

export type NoiseMode = { Periodic: number } | { White: number };

export interface DacInstrument {
  id: string;
  name: string;
  targetSampleRate: number;
  loopStart: number | null;
  loopLength: number | null;
  originalFile: string;
  pcmFile: string;
  sourceIsRaw: boolean;
  metadata: InstrumentMetadata;
}

export interface InstrumentBank {
  fm: FmInstrument[];
  psg: PsgInstrument[];
  dac: DacInstrument[];
}

export interface SongMetadata {
  name: string;
  tempo: number;
  timeSignature: [number, number];
  ticksPerBeat: number;
  driverId: string;
}

export type ChannelAssignment =
  | { Fm: number }
  | { Psg: number }
  | "PsgNoise"
  | { Dac: number };

export type Pan = "Left" | "Right" | "Center";

export interface Track {
  id: string;
  name: string;
  channel: ChannelAssignment;
  instrumentId: string | null;
  regions: Region[];
  muted: boolean;
  solo: boolean;
  volume: number;
  pan: Pan;
}

export interface Region {
  id: string;
  startTick: number;
  durationTicks: number;
  notes: Note[];
}

export interface Note {
  tick: number;
  pitch: number;
  velocity: number;
  durationTicks: number;
}

export interface Song {
  metadata: SongMetadata;
  tracks: Track[];
  instruments: InstrumentBank;
}

export interface FmChannelInfo {
  index: number;
  name: string;
  supportsSpecialMode: boolean;
}

export interface PsgChannelInfo {
  index: number;
  name: string;
  isNoise: boolean;
}

export interface DacChannelInfo {
  index: number;
  name: string;
}

export interface ChannelLayout {
  fmChannels: FmChannelInfo[];
  psgChannels: PsgChannelInfo[];
  dacChannels: DacChannelInfo[];
}

export interface DriverInfo {
  id: string;
  name: string;
}

export interface DriverDetail {
  id: string;
  name: string;
  layout: ChannelLayout;
  features: string[];
}

export type SelectedInstrument =
  | { type: "fm"; id: string }
  | { type: "psg"; id: string }
  | { type: "dac"; id: string };

export const DEFAULT_FM_OPERATOR: FmOperator = {
  detune: 0,
  multiple: 0,
  rateScale: 0,
  attackRate: 0,
  ampMod: false,
  d1r: 0,
  d2r: 0,
  sustainLevel: 0,
  releaseRate: 0,
  totalLevel: 127,
};

export const DEFAULT_METADATA: InstrumentMetadata = {
  category: "",
  author: "",
  tags: [],
};

export const CARRIER_MASKS = [
  0b1000, 0b1000, 0b1000, 0b1000,
  0b1010, 0b1110, 0b1110, 0b1111,
];

export function isCarrier(algorithm: number, opIndex: number): boolean {
  return (CARRIER_MASKS[algorithm] & (1 << opIndex)) !== 0;
}
```

- [ ] **Step 3: Create typed IPC wrapper**

Create `src/api/ipc.ts`:

```typescript
import { invoke } from "@tauri-apps/api/core";
import type {
  FmInstrument,
  PsgInstrument,
  DacInstrument,
  Song,
  SongMetadata,
  DriverInfo,
  DriverDetail,
} from "../types/model";

export async function playFmTestTone(): Promise<string> {
  return invoke<string>("play_fm_test_tone");
}

export async function playPsgTestTone(): Promise<string> {
  return invoke<string>("play_psg_test_tone");
}

export async function stopAllSound(): Promise<string> {
  return invoke<string>("stop_all_sound");
}

export async function createProject(
  path: string,
  name: string,
  driverId: string,
  tempo: number,
  timeSigNum: number,
  timeSigDen: number,
): Promise<void> {
  return invoke("create_project", { path, name, driverId, tempo, timeSigNum, timeSigDen });
}

export async function openProject(path: string): Promise<Song> {
  return invoke<Song>("open_project", { path });
}

export async function saveProject(): Promise<void> {
  return invoke("save_project");
}

export async function closeProject(): Promise<void> {
  return invoke("close_project");
}

export async function getProjectInfo(): Promise<SongMetadata | null> {
  return invoke<SongMetadata | null>("get_project_info");
}

export async function listDrivers(): Promise<DriverInfo[]> {
  return invoke<DriverInfo[]>("list_drivers");
}

export async function getDriverInfo(driverId: string): Promise<DriverDetail> {
  return invoke<DriverDetail>("get_driver_info", { driverId });
}

export async function addFmInstrument(instrument: FmInstrument): Promise<string> {
  return invoke<string>("add_fm_instrument", { instrument });
}

export async function updateFmInstrument(id: string, instrument: FmInstrument): Promise<void> {
  return invoke("update_fm_instrument", { id, instrument });
}

export async function deleteFmInstrument(id: string): Promise<void> {
  return invoke("delete_fm_instrument", { id });
}

export async function listFmInstruments(): Promise<FmInstrument[]> {
  return invoke<FmInstrument[]>("list_fm_instruments");
}

export async function previewFmInstrument(id: string, midiNote: number): Promise<void> {
  return invoke("preview_fm_instrument", { id, midiNote });
}

export async function addPsgInstrument(instrument: PsgInstrument): Promise<string> {
  return invoke<string>("add_psg_instrument", { instrument });
}

export async function updatePsgInstrument(id: string, instrument: PsgInstrument): Promise<void> {
  return invoke("update_psg_instrument", { id, instrument });
}

export async function deletePsgInstrument(id: string): Promise<void> {
  return invoke("delete_psg_instrument", { id });
}

export async function listPsgInstruments(): Promise<PsgInstrument[]> {
  return invoke<PsgInstrument[]>("list_psg_instruments");
}

export async function previewPsgInstrument(id: string, midiNote: number): Promise<void> {
  return invoke("preview_psg_instrument", { id, midiNote });
}

export async function importDacWav(wavPath: string, targetRate: number): Promise<string> {
  return invoke<string>("import_dac_wav", { wavPath, targetRate });
}

export async function importDacRaw(pcmPath: string, sampleRate: number): Promise<string> {
  return invoke<string>("import_dac_raw", { pcmPath, sampleRate });
}

export async function updateDacInstrument(id: string, instrument: DacInstrument): Promise<void> {
  return invoke("update_dac_instrument", { id, instrument });
}

export async function reconvertDac(id: string, newRate: number): Promise<void> {
  return invoke("reconvert_dac", { id, newRate });
}

export async function deleteDacInstrument(id: string): Promise<void> {
  return invoke("delete_dac_instrument", { id });
}

export async function listDacInstruments(): Promise<DacInstrument[]> {
  return invoke<DacInstrument[]>("list_dac_instruments");
}

export async function previewDac(id: string): Promise<void> {
  return invoke("preview_dac", { id });
}

export async function getDacPcmData(id: string): Promise<number[]> {
  return invoke<number[]>("get_dac_pcm_data", { id });
}
```

- [ ] **Step 4: Update main.tsx to import tokens**

Replace `src/main.tsx`:

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./theme/tokens.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

- [ ] **Step 5: Delete old files**

Delete `src/components/TestPanel.tsx` and `src/App.css`.

- [ ] **Step 6: Create placeholder App.tsx**

Replace `src/App.tsx` temporarily (full version comes in Task 3):

```tsx
export default function App() {
  return <div style={{ padding: "2rem" }}>MegaDAW — building UI...</div>;
}
```

- [ ] **Step 7: Verify TypeScript compilation**

Run: `cd /home/volence/sonic_hacks/megadaw && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 8: Commit**

```bash
cd /home/volence/sonic_hacks/megadaw
git add src/theme/tokens.css src/types/model.ts src/api/ipc.ts src/main.tsx src/App.tsx
git rm src/components/TestPanel.tsx src/App.css
git commit -m "feat(ui): foundation — theme tokens, TypeScript types, IPC wrapper"
```

---

### Task 3: App Shell — root layout, TopBar, MainArea

**Files:**
- Rewrite: `src/App.tsx`
- Create: `src/App.module.css`
- Create: `src/components/TopBar.tsx`
- Create: `src/components/TopBar.module.css`
- Create: `src/components/MainArea.tsx`
- Create: `src/components/MainArea.module.css`

- [ ] **Step 1: Create App.module.css**

Create `src/App.module.css`:

```css
.app {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg-app);
  color: var(--text-primary);
}

.body {
  display: flex;
  flex: 1;
  overflow: hidden;
}
```

- [ ] **Step 2: Create TopBar**

Create `src/components/TopBar.tsx`:

```tsx
import { useState, useEffect } from "react";
import type { SongMetadata } from "../types/model";
import styles from "./TopBar.module.css";

interface TopBarProps {
  projectMeta: SongMetadata | null;
  onNewProject: () => void;
  onOpenProject: () => void;
  onSave: () => void;
  showSaved: boolean;
}

export function TopBar({ projectMeta, onNewProject, onOpenProject, onSave, showSaved }: TopBarProps) {
  return (
    <div className={styles.topBar}>
      <div className={styles.projectInfo}>
        <span className={styles.projectName}>{projectMeta?.name ?? "MegaDAW"}</span>
        {projectMeta && (
          <>
            <span className={styles.separator}>|</span>
            <span className={styles.detail}>{projectMeta.tempo} BPM</span>
            <span className={styles.detail}>
              {projectMeta.timeSignature[0]}/{projectMeta.timeSignature[1]}
            </span>
            <span className={styles.driverBadge}>Flamedriver</span>
          </>
        )}
      </div>
      <div className={styles.actions}>
        <button className={styles.btn} onClick={onNewProject}>New</button>
        <button className={styles.btn} onClick={onOpenProject}>Open</button>
        {projectMeta && (
          <button className={styles.btn} onClick={onSave}>Save</button>
        )}
        {showSaved && <span className={styles.saved}>Saved</span>}
      </div>
      <div className={styles.transport}>
        <button className={styles.transportBtn} disabled title="Play (Phase 4)">&#9654;</button>
        <button className={styles.transportBtn} disabled title="Stop (Phase 4)">&#9632;</button>
        <button className={styles.transportBtn} disabled title="Loop (Phase 4)">&#8635;</button>
      </div>
    </div>
  );
}
```

Create `src/components/TopBar.module.css`:

```css
.topBar {
  display: flex;
  align-items: center;
  height: 48px;
  padding: 0 12px;
  background: var(--bg-panel);
  border-bottom: 1px solid var(--border);
  gap: 16px;
  flex-shrink: 0;
}

.projectInfo {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.projectName {
  font-weight: 600;
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.separator {
  color: var(--text-secondary);
}

.detail {
  color: var(--text-secondary);
  font-size: 12px;
  white-space: nowrap;
}

.driverBadge {
  font-size: 11px;
  padding: 2px 6px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 3px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.btn {
  padding: 4px 10px;
  background: var(--bg-surface);
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-radius: 3px;
}

.btn:hover {
  background: var(--border);
}

.saved {
  color: var(--success);
  font-size: 12px;
  animation: fadeOut 2s forwards;
}

@keyframes fadeOut {
  0% { opacity: 1; }
  70% { opacity: 1; }
  100% { opacity: 0; }
}

.transport {
  display: flex;
  gap: 4px;
}

.transportBtn {
  width: 32px;
  height: 28px;
  background: var(--bg-surface);
  color: var(--text-disabled);
  border: 1px solid var(--border);
  border-radius: 3px;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
}
```

- [ ] **Step 3: Create MainArea**

Create `src/components/MainArea.tsx`:

```tsx
import styles from "./MainArea.module.css";

interface MainAreaProps {
  projectOpen: boolean;
  onNewProject: () => void;
  onOpenProject: () => void;
}

export function MainArea({ projectOpen, onNewProject, onOpenProject }: MainAreaProps) {
  if (!projectOpen) {
    return (
      <div className={styles.welcome}>
        <h1 className={styles.title}>MegaDAW</h1>
        <p className={styles.subtitle}>Mega Drive Digital Audio Workstation</p>
        <div className={styles.welcomeActions}>
          <button className={styles.welcomeBtn} onClick={onNewProject}>New Project</button>
          <button className={styles.welcomeBtn} onClick={onOpenProject}>Open Project</button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.placeholder}>
      <p className={styles.placeholderText}>Arrangement View — Phase 4</p>
    </div>
  );
}
```

Create `src/components/MainArea.module.css`:

```css
.welcome {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
}

.title {
  font-size: 32px;
  font-weight: 300;
  margin: 0;
  color: var(--text-primary);
}

.subtitle {
  color: var(--text-secondary);
  margin: 0;
}

.welcomeActions {
  display: flex;
  gap: 12px;
  margin-top: 16px;
}

.welcomeBtn {
  padding: 10px 24px;
  background: var(--bg-surface);
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-radius: 4px;
  font-size: 14px;
}

.welcomeBtn:hover {
  border-color: var(--accent-fm);
}

.placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.placeholderText {
  color: var(--text-secondary);
  font-size: 14px;
}
```

- [ ] **Step 4: Wire up App.tsx**

Replace `src/App.tsx`:

```tsx
import { useState, useEffect, useCallback } from "react";
import type { SongMetadata, SelectedInstrument } from "./types/model";
import * as ipc from "./api/ipc";
import { TopBar } from "./components/TopBar";
import { MainArea } from "./components/MainArea";
import styles from "./App.module.css";

export default function App() {
  const [projectMeta, setProjectMeta] = useState<SongMetadata | null>(null);
  const [showSaved, setShowSaved] = useState(false);
  const [showNewProject, setShowNewProject] = useState(false);
  const [selectedInstrument, setSelectedInstrument] = useState<SelectedInstrument | null>(null);

  const projectOpen = projectMeta !== null;

  const handleSave = useCallback(async () => {
    if (!projectMeta) return;
    try {
      await ipc.saveProject();
      setShowSaved(true);
      setTimeout(() => setShowSaved(false), 2000);
    } catch (e) {
      console.error("Save failed:", e);
    }
  }, [projectMeta]);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        handleSave();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleSave]);

  async function handleOpenProject() {
    const { open } = await import("@tauri-apps/plugin-dialog");
    const selected = await open({ directory: true, title: "Open Project" });
    if (!selected) return;
    try {
      if (projectOpen) await ipc.closeProject();
      const song = await ipc.openProject(selected as string);
      setProjectMeta(song.metadata);
      setSelectedInstrument(null);
    } catch (e) {
      console.error("Open failed:", e);
    }
  }

  function handleProjectCreated(meta: SongMetadata) {
    setProjectMeta(meta);
    setShowNewProject(false);
    setSelectedInstrument(null);
  }

  return (
    <div className={styles.app}>
      <TopBar
        projectMeta={projectMeta}
        onNewProject={() => setShowNewProject(true)}
        onOpenProject={handleOpenProject}
        onSave={handleSave}
        showSaved={showSaved}
      />
      <div className={styles.body}>
        <MainArea
          projectOpen={projectOpen}
          onNewProject={() => setShowNewProject(true)}
          onOpenProject={handleOpenProject}
        />
      </div>
    </div>
  );
}
```

Note: Sidebar, BottomPanel, and NewProjectDialog are not wired yet — they come in Tasks 4-5.

- [ ] **Step 5: Verify dev server**

Run: `cd /home/volence/sonic_hacks/megadaw && npx tsc --noEmit`
Expected: No errors

Run: `cd /home/volence/sonic_hacks/megadaw && npm run tauri dev`
Expected: Dark window with TopBar showing "MegaDAW", welcome screen with New/Open buttons. Transport buttons grayed out.

- [ ] **Step 6: Commit**

```bash
cd /home/volence/sonic_hacks/megadaw
git add src/App.tsx src/App.module.css src/components/TopBar.tsx src/components/TopBar.module.css \
  src/components/MainArea.tsx src/components/MainArea.module.css
git commit -m "feat(ui): app shell — TopBar, MainArea, welcome screen"
```

---

### Task 4: App Shell — Sidebar + BottomPanel

**Files:**
- Create: `src/components/Sidebar.tsx`
- Create: `src/components/Sidebar.module.css`
- Create: `src/components/BottomPanel.tsx`
- Create: `src/components/BottomPanel.module.css`
- Modify: `src/App.tsx`

- [ ] **Step 1: Create Sidebar**

Create `src/components/Sidebar.tsx`:

```tsx
import { useState } from "react";
import type { SongMetadata, SelectedInstrument } from "../types/model";
import styles from "./Sidebar.module.css";

interface SidebarProps {
  projectMeta: SongMetadata;
  selectedInstrument: SelectedInstrument | null;
  onSelectInstrument: (inst: SelectedInstrument | null) => void;
}

export function Sidebar({ projectMeta, selectedInstrument, onSelectInstrument }: SidebarProps) {
  const [activeTab, setActiveTab] = useState<"tracks" | "instruments">("instruments");

  return (
    <div className={styles.sidebar}>
      <div className={styles.tabs}>
        <button
          className={`${styles.tab} ${activeTab === "tracks" ? styles.active : ""}`}
          onClick={() => setActiveTab("tracks")}
        >
          Tracks
        </button>
        <button
          className={`${styles.tab} ${activeTab === "instruments" ? styles.active : ""}`}
          onClick={() => setActiveTab("instruments")}
        >
          Instruments
        </button>
      </div>
      <div className={styles.content}>
        {activeTab === "tracks" && (
          <p className={styles.placeholder}>Track list — Task 6</p>
        )}
        {activeTab === "instruments" && (
          <p className={styles.placeholder}>Instrument browser — Task 6</p>
        )}
      </div>
    </div>
  );
}
```

Create `src/components/Sidebar.module.css`:

```css
.sidebar {
  width: 240px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-panel);
  border-right: 1px solid var(--border);
  overflow: hidden;
}

.tabs {
  display: flex;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.tab {
  flex: 1;
  padding: 8px 0;
  background: none;
  color: var(--text-secondary);
  border: none;
  border-bottom: 2px solid transparent;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.tab.active {
  color: var(--text-primary);
  border-bottom-color: var(--accent-fm);
}

.tab:hover {
  color: var(--text-primary);
}

.content {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.placeholder {
  color: var(--text-secondary);
  font-size: 12px;
  text-align: center;
  margin-top: 24px;
}
```

- [ ] **Step 2: Create BottomPanel**

Create `src/components/BottomPanel.tsx`:

```tsx
import { useState } from "react";
import type { SelectedInstrument } from "../types/model";
import styles from "./BottomPanel.module.css";

interface BottomPanelProps {
  selectedInstrument: SelectedInstrument | null;
}

export function BottomPanel({ selectedInstrument }: BottomPanelProps) {
  const [collapsed, setCollapsed] = useState(false);

  if (!selectedInstrument) {
    return (
      <div className={styles.panel}>
        <div className={styles.header} onClick={() => setCollapsed(!collapsed)}>
          <span className={styles.toggle}>{collapsed ? "▶" : "▼"}</span>
          <span>Instrument Editor</span>
        </div>
        {!collapsed && (
          <div className={styles.empty}>Select an instrument to edit</div>
        )}
      </div>
    );
  }

  return (
    <div className={`${styles.panel} ${collapsed ? styles.collapsed : ""}`}>
      <div className={styles.header} onClick={() => setCollapsed(!collapsed)}>
        <span className={styles.toggle}>{collapsed ? "▶" : "▼"}</span>
        <span>Instrument Editor</span>
      </div>
      {!collapsed && (
        <div className={styles.editor}>
          <p style={{ color: "var(--text-secondary)", textAlign: "center", marginTop: 40 }}>
            {selectedInstrument.type.toUpperCase()} editor — Tasks 9-11
          </p>
        </div>
      )}
    </div>
  );
}
```

Create `src/components/BottomPanel.module.css`:

```css
.panel {
  flex-shrink: 0;
  background: var(--bg-panel);
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  height: 300px;
  min-height: 32px;
}

.collapsed {
  height: 32px;
}

.header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  cursor: pointer;
  user-select: none;
  font-size: 12px;
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.header:hover {
  color: var(--text-primary);
}

.toggle {
  font-size: 10px;
}

.editor {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
}

.empty {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
  color: var(--text-secondary);
  font-size: 13px;
}
```

- [ ] **Step 3: Wire Sidebar + BottomPanel into App.tsx**

Replace `src/App.tsx`:

```tsx
import { useState, useEffect, useCallback } from "react";
import type { SongMetadata, SelectedInstrument } from "./types/model";
import * as ipc from "./api/ipc";
import { TopBar } from "./components/TopBar";
import { Sidebar } from "./components/Sidebar";
import { MainArea } from "./components/MainArea";
import { BottomPanel } from "./components/BottomPanel";
import styles from "./App.module.css";

export default function App() {
  const [projectMeta, setProjectMeta] = useState<SongMetadata | null>(null);
  const [showSaved, setShowSaved] = useState(false);
  const [showNewProject, setShowNewProject] = useState(false);
  const [selectedInstrument, setSelectedInstrument] = useState<SelectedInstrument | null>(null);

  const projectOpen = projectMeta !== null;

  const handleSave = useCallback(async () => {
    if (!projectMeta) return;
    try {
      await ipc.saveProject();
      setShowSaved(true);
      setTimeout(() => setShowSaved(false), 2000);
    } catch (e) {
      console.error("Save failed:", e);
    }
  }, [projectMeta]);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        handleSave();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleSave]);

  async function handleOpenProject() {
    const { open } = await import("@tauri-apps/plugin-dialog");
    const selected = await open({ directory: true, title: "Open Project" });
    if (!selected) return;
    try {
      if (projectOpen) await ipc.closeProject();
      const song = await ipc.openProject(selected as string);
      setProjectMeta(song.metadata);
      setSelectedInstrument(null);
    } catch (e) {
      console.error("Open failed:", e);
    }
  }

  function handleProjectCreated(meta: SongMetadata) {
    setProjectMeta(meta);
    setShowNewProject(false);
    setSelectedInstrument(null);
  }

  return (
    <div className={styles.app}>
      <TopBar
        projectMeta={projectMeta}
        onNewProject={() => setShowNewProject(true)}
        onOpenProject={handleOpenProject}
        onSave={handleSave}
        showSaved={showSaved}
      />
      <div className={styles.body}>
        {projectOpen && (
          <Sidebar
            projectMeta={projectMeta}
            selectedInstrument={selectedInstrument}
            onSelectInstrument={setSelectedInstrument}
          />
        )}
        <MainArea
          projectOpen={projectOpen}
          onNewProject={() => setShowNewProject(true)}
          onOpenProject={handleOpenProject}
        />
      </div>
      {projectOpen && (
        <BottomPanel selectedInstrument={selectedInstrument} />
      )}
    </div>
  );
}
```

- [ ] **Step 4: Verify**

Run: `cd /home/volence/sonic_hacks/megadaw && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
cd /home/volence/sonic_hacks/megadaw
git add src/App.tsx src/components/Sidebar.tsx src/components/Sidebar.module.css \
  src/components/BottomPanel.tsx src/components/BottomPanel.module.css
git commit -m "feat(ui): Sidebar + BottomPanel with collapsible behavior"
```

---

### Task 5: Project Flow — NewProjectDialog, open, save

**Files:**
- Create: `src/components/NewProjectDialog.tsx`
- Create: `src/components/NewProjectDialog.module.css`
- Modify: `src/App.tsx`

- [ ] **Step 1: Create NewProjectDialog**

Create `src/components/NewProjectDialog.tsx`:

```tsx
import { useState, useEffect } from "react";
import type { SongMetadata, DriverInfo } from "../types/model";
import * as ipc from "../api/ipc";
import styles from "./NewProjectDialog.module.css";

interface NewProjectDialogProps {
  onClose: () => void;
  onCreated: (meta: SongMetadata) => void;
}

export function NewProjectDialog({ onClose, onCreated }: NewProjectDialogProps) {
  const [name, setName] = useState("");
  const [location, setLocation] = useState("");
  const [drivers, setDrivers] = useState<DriverInfo[]>([]);
  const [driverId, setDriverId] = useState("");
  const [tempo, setTempo] = useState(120);
  const [timeSigNum, setTimeSigNum] = useState(4);
  const [timeSigDen, setTimeSigDen] = useState(4);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    ipc.listDrivers().then((list) => {
      setDrivers(list);
      if (list.length > 0) setDriverId(list[0].id);
    });
  }, []);

  async function handleBrowse() {
    const { open } = await import("@tauri-apps/plugin-dialog");
    const selected = await open({ directory: true, title: "Choose Project Location" });
    if (selected) setLocation(selected as string);
  }

  async function handleCreate() {
    if (!name.trim()) { setError("Name is required"); return; }
    if (!location.trim()) { setError("Location is required"); return; }
    if (!driverId) { setError("Select a driver"); return; }

    setCreating(true);
    setError("");
    try {
      const fullPath = `${location}/${name.replace(/[^a-zA-Z0-9_-]/g, "_")}`;
      await ipc.createProject(fullPath, name, driverId, tempo, timeSigNum, timeSigDen);
      const meta = await ipc.getProjectInfo();
      if (meta) onCreated(meta);
    } catch (e) {
      setError(String(e));
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.dialog} onClick={(e) => e.stopPropagation()}>
        <h2 className={styles.title}>New Project</h2>

        <label className={styles.label}>
          Name
          <input
            className={styles.input}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="My Song"
            autoFocus
          />
        </label>

        <label className={styles.label}>
          Location
          <div className={styles.browseRow}>
            <input
              className={styles.input}
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="/path/to/projects"
              readOnly
            />
            <button className={styles.browseBtn} onClick={handleBrowse}>Browse</button>
          </div>
        </label>

        <label className={styles.label}>
          Driver
          <select
            className={styles.select}
            value={driverId}
            onChange={(e) => setDriverId(e.target.value)}
          >
            {drivers.map((d) => (
              <option key={d.id} value={d.id}>{d.name}</option>
            ))}
          </select>
        </label>

        <div className={styles.row}>
          <label className={styles.label}>
            Tempo
            <input
              className={styles.input}
              type="number"
              min={20}
              max={300}
              value={tempo}
              onChange={(e) => setTempo(Number(e.target.value))}
            />
          </label>
          <label className={styles.label}>
            Time Signature
            <div className={styles.timeSigRow}>
              <input
                className={styles.smallInput}
                type="number"
                min={1}
                max={12}
                value={timeSigNum}
                onChange={(e) => setTimeSigNum(Number(e.target.value))}
              />
              <span>/</span>
              <select
                className={styles.smallSelect}
                value={timeSigDen}
                onChange={(e) => setTimeSigDen(Number(e.target.value))}
              >
                <option value={2}>2</option>
                <option value={4}>4</option>
                <option value={8}>8</option>
                <option value={16}>16</option>
              </select>
            </div>
          </label>
        </div>

        {error && <p className={styles.error}>{error}</p>}

        <div className={styles.buttons}>
          <button className={styles.cancelBtn} onClick={onClose}>Cancel</button>
          <button className={styles.createBtn} onClick={handleCreate} disabled={creating}>
            {creating ? "Creating..." : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}
```

Create `src/components/NewProjectDialog.module.css`:

```css
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.dialog {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 24px;
  width: 420px;
  max-width: 90vw;
}

.title {
  margin: 0 0 20px;
  font-size: 18px;
  font-weight: 500;
}

.label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 14px;
  font-size: 12px;
  color: var(--text-secondary);
}

.input {
  padding: 6px 8px;
  background: var(--bg-input);
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-radius: 3px;
}

.input:focus {
  border-color: var(--border-focus);
  outline: none;
}

.select {
  padding: 6px 8px;
  background: var(--bg-input);
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-radius: 3px;
}

.browseRow {
  display: flex;
  gap: 6px;
}

.browseRow .input {
  flex: 1;
}

.browseBtn {
  padding: 6px 12px;
  background: var(--bg-surface);
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-radius: 3px;
}

.browseBtn:hover {
  background: var(--border);
}

.row {
  display: flex;
  gap: 14px;
}

.row .label {
  flex: 1;
}

.timeSigRow {
  display: flex;
  align-items: center;
  gap: 6px;
}

.timeSigRow span {
  color: var(--text-secondary);
  font-size: 16px;
}

.smallInput {
  width: 48px;
  padding: 6px 8px;
  background: var(--bg-input);
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-radius: 3px;
}

.smallSelect {
  width: 56px;
  padding: 6px 4px;
  background: var(--bg-input);
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-radius: 3px;
}

.error {
  color: var(--error);
  font-size: 12px;
  margin: 0 0 12px;
}

.buttons {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 20px;
}

.cancelBtn {
  padding: 8px 16px;
  background: none;
  color: var(--text-secondary);
  border: 1px solid var(--border);
  border-radius: 3px;
}

.cancelBtn:hover {
  color: var(--text-primary);
}

.createBtn {
  padding: 8px 20px;
  background: var(--accent-fm);
  color: #fff;
  border: none;
  border-radius: 3px;
  font-weight: 500;
}

.createBtn:hover {
  opacity: 0.9;
}

.createBtn:disabled {
  opacity: 0.5;
  cursor: default;
}
```

- [ ] **Step 2: Wire NewProjectDialog into App.tsx**

Add the import at the top of `src/App.tsx`:

```tsx
import { NewProjectDialog } from "./components/NewProjectDialog";
```

Add just before the closing `</div>` of the root element (after the `{projectOpen && <BottomPanel ... />}` block):

```tsx
      {showNewProject && (
        <NewProjectDialog
          onClose={() => setShowNewProject(false)}
          onCreated={handleProjectCreated}
        />
      )}
```

- [ ] **Step 3: Verify project creation flow**

Run: `cd /home/volence/sonic_hacks/megadaw && npx tsc --noEmit`
Expected: No errors

Test in dev server:
1. Click "New" → modal appears with form fields
2. Fill in name, browse for location, click Create
3. TopBar shows project name, BPM, time sig, driver badge
4. Sidebar appears with placeholder tab content
5. BottomPanel appears at bottom
6. Click "Open" → folder picker appears
7. Ctrl+S → "Saved" indicator appears briefly in top bar

- [ ] **Step 4: Commit**

```bash
cd /home/volence/sonic_hacks/megadaw
git add src/App.tsx src/components/NewProjectDialog.tsx src/components/NewProjectDialog.module.css
git commit -m "feat(ui): project creation dialog + open/save flow"
```

---

### Task 6: Sidebar Content — TrackList + InstrumentBrowser

**Files:**
- Create: `src/components/TrackList.tsx`
- Create: `src/components/TrackList.module.css`
- Create: `src/components/InstrumentBrowser.tsx`
- Create: `src/components/InstrumentBrowser.module.css`
- Modify: `src/components/Sidebar.tsx`

- [ ] **Step 1: Create TrackList**

Create `src/components/TrackList.tsx`:

```tsx
import { useState, useEffect } from "react";
import type { ChannelLayout } from "../types/model";
import * as ipc from "../api/ipc";
import styles from "./TrackList.module.css";

interface TrackListProps {
  driverId: string;
}

export function TrackList({ driverId }: TrackListProps) {
  const [layout, setLayout] = useState<ChannelLayout | null>(null);

  useEffect(() => {
    ipc.getDriverInfo(driverId).then((d) => setLayout(d.layout));
  }, [driverId]);

  if (!layout) return null;

  return (
    <div className={styles.trackList}>
      {layout.fmChannels.map((ch) => (
        <div key={`fm-${ch.index}`} className={styles.track}>
          <span className={`${styles.badge} ${styles.fm}`}>FM</span>
          <span className={styles.name}>{ch.name}</span>
        </div>
      ))}
      {layout.psgChannels.map((ch) => (
        <div key={`psg-${ch.index}`} className={styles.track}>
          <span className={`${styles.badge} ${styles.psg}`}>PSG</span>
          <span className={styles.name}>{ch.name}</span>
        </div>
      ))}
      {layout.dacChannels.map((ch) => (
        <div key={`dac-${ch.index}`} className={styles.track}>
          <span className={`${styles.badge} ${styles.dac}`}>DAC</span>
          <span className={styles.name}>{ch.name}</span>
        </div>
      ))}
    </div>
  );
}
```

Create `src/components/TrackList.module.css`:

```css
.trackList {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.track {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 3px;
}

.track:hover {
  background: var(--bg-surface);
}

.badge {
  font-size: 10px;
  padding: 1px 4px;
  border-radius: 2px;
  font-weight: 600;
  text-transform: uppercase;
}

.fm { background: var(--accent-fm); color: #000; }
.psg { background: var(--accent-psg); color: #000; }
.dac { background: var(--accent-dac); color: #000; }

.name {
  font-size: 12px;
}
```

- [ ] **Step 2: Create InstrumentBrowser**

Create `src/components/InstrumentBrowser.tsx`:

```tsx
import { useState, useEffect, useCallback } from "react";
import type {
  FmInstrument, PsgInstrument, DacInstrument,
  SelectedInstrument, FmOperator, DEFAULT_FM_OPERATOR, DEFAULT_METADATA,
} from "../types/model";
import * as ipc from "../api/ipc";
import styles from "./InstrumentBrowser.module.css";

interface InstrumentBrowserProps {
  onSelect: (inst: SelectedInstrument | null) => void;
  selectedInstrument: SelectedInstrument | null;
}

export function InstrumentBrowser({ onSelect, selectedInstrument }: InstrumentBrowserProps) {
  const [fmList, setFmList] = useState<FmInstrument[]>([]);
  const [psgList, setPsgList] = useState<PsgInstrument[]>([]);
  const [dacList, setDacList] = useState<DacInstrument[]>([]);
  const [fmExpanded, setFmExpanded] = useState(true);
  const [psgExpanded, setPsgExpanded] = useState(true);
  const [dacExpanded, setDacExpanded] = useState(true);
  const [contextMenu, setContextMenu] = useState<{
    x: number; y: number; type: "fm" | "psg" | "dac"; id: string;
  } | null>(null);

  const refreshAll = useCallback(async () => {
    const [fm, psg, dac] = await Promise.all([
      ipc.listFmInstruments(),
      ipc.listPsgInstruments(),
      ipc.listDacInstruments(),
    ]);
    setFmList(fm);
    setPsgList(psg);
    setDacList(dac);
  }, []);

  useEffect(() => { refreshAll(); }, [refreshAll]);

  useEffect(() => {
    if (!contextMenu) return;
    function close() { setContextMenu(null); }
    window.addEventListener("click", close);
    return () => window.removeEventListener("click", close);
  }, [contextMenu]);

  const defaultOp: FmOperator = {
    detune: 0, multiple: 0, rateScale: 0, attackRate: 0,
    ampMod: false, d1r: 0, d2r: 0, sustainLevel: 0,
    releaseRate: 0, totalLevel: 127,
  };

  async function addFm() {
    const inst: FmInstrument = {
      id: "00000000-0000-0000-0000-000000000000",
      name: "New FM Patch",
      algorithm: 0,
      feedback: 0,
      operators: [defaultOp, defaultOp, defaultOp, defaultOp],
      metadata: { category: "", author: "", tags: [] },
    };
    const id = await ipc.addFmInstrument(inst);
    await refreshAll();
    onSelect({ type: "fm", id });
  }

  async function addPsg() {
    const inst: PsgInstrument = {
      id: "00000000-0000-0000-0000-000000000000",
      name: "New PSG Envelope",
      volumeSequence: [15, 14, 13, 12, 10, 8, 6, 4, 2, 0],
      loopPoint: null,
      noiseMode: null,
      metadata: { category: "", author: "", tags: [] },
    };
    const id = await ipc.addPsgInstrument(inst);
    await refreshAll();
    onSelect({ type: "psg", id });
  }

  async function addDac() {
    const { open } = await import("@tauri-apps/plugin-dialog");
    const selected = await open({
      filters: [
        { name: "Audio", extensions: ["wav"] },
        { name: "Raw PCM", extensions: ["pcm", "raw"] },
      ],
      title: "Import DAC Sample",
    });
    if (!selected) return;
    const path = selected as string;
    const ext = path.split(".").pop()?.toLowerCase();
    let id: string;
    if (ext === "wav") {
      id = await ipc.importDacWav(path, 16000);
    } else {
      id = await ipc.importDacRaw(path, 16000);
    }
    await refreshAll();
    onSelect({ type: "dac", id });
  }

  function handleContextMenu(e: React.MouseEvent, type: "fm" | "psg" | "dac", id: string) {
    e.preventDefault();
    setContextMenu({ x: e.clientX, y: e.clientY, type, id });
  }

  async function handleRename(type: "fm" | "psg" | "dac", id: string) {
    setContextMenu(null);
    const currentName =
      type === "fm" ? fmList.find((i) => i.id === id)?.name :
      type === "psg" ? psgList.find((i) => i.id === id)?.name :
      dacList.find((i) => i.id === id)?.name;
    const newName = window.prompt("Rename instrument:", currentName ?? "");
    if (!newName || newName === currentName) return;

    if (type === "fm") {
      const inst = fmList.find((i) => i.id === id);
      if (inst) await ipc.updateFmInstrument(id, { ...inst, name: newName });
    } else if (type === "psg") {
      const inst = psgList.find((i) => i.id === id);
      if (inst) await ipc.updatePsgInstrument(id, { ...inst, name: newName });
    } else {
      const inst = dacList.find((i) => i.id === id);
      if (inst) await ipc.updateDacInstrument(id, { ...inst, name: newName });
    }
    await refreshAll();
  }

  async function handleDuplicate(type: "fm" | "psg" | "dac", id: string) {
    setContextMenu(null);
    if (type === "fm") {
      const inst = fmList.find((i) => i.id === id);
      if (inst) {
        const newId = await ipc.addFmInstrument({
          ...inst,
          id: "00000000-0000-0000-0000-000000000000",
          name: `${inst.name} (Copy)`,
        });
        await refreshAll();
        onSelect({ type: "fm", id: newId });
      }
    } else if (type === "psg") {
      const inst = psgList.find((i) => i.id === id);
      if (inst) {
        const newId = await ipc.addPsgInstrument({
          ...inst,
          id: "00000000-0000-0000-0000-000000000000",
          name: `${inst.name} (Copy)`,
        });
        await refreshAll();
        onSelect({ type: "psg", id: newId });
      }
    }
  }

  async function handleDelete(type: "fm" | "psg" | "dac", id: string) {
    setContextMenu(null);
    if (type === "fm") await ipc.deleteFmInstrument(id);
    else if (type === "psg") await ipc.deletePsgInstrument(id);
    else await ipc.deleteDacInstrument(id);
    if (selectedInstrument?.id === id) onSelect(null);
    await refreshAll();
  }

  function isSelected(type: string, id: string) {
    return selectedInstrument?.type === type && selectedInstrument?.id === id;
  }

  return (
    <div className={styles.browser}>
      <div className={styles.section}>
        <div className={styles.sectionHeader} onClick={() => setFmExpanded(!fmExpanded)}>
          <span>{fmExpanded ? "▼" : "▶"}</span>
          <span className={styles.sectionTitle}>FM</span>
          <span className={styles.count}>{fmList.length}</span>
          <button className={styles.addBtn} onClick={(e) => { e.stopPropagation(); addFm(); }}>+</button>
        </div>
        {fmExpanded && fmList.map((inst) => (
          <div
            key={inst.id}
            className={`${styles.item} ${isSelected("fm", inst.id) ? styles.selected : ""}`}
            onClick={() => onSelect({ type: "fm", id: inst.id })}
            onContextMenu={(e) => handleContextMenu(e, "fm", inst.id)}
          >
            <span className={`${styles.dot} ${styles.fmDot}`} />
            <span className={styles.itemName}>{inst.name}</span>
          </div>
        ))}
      </div>

      <div className={styles.section}>
        <div className={styles.sectionHeader} onClick={() => setPsgExpanded(!psgExpanded)}>
          <span>{psgExpanded ? "▼" : "▶"}</span>
          <span className={styles.sectionTitle}>PSG</span>
          <span className={styles.count}>{psgList.length}</span>
          <button className={styles.addBtn} onClick={(e) => { e.stopPropagation(); addPsg(); }}>+</button>
        </div>
        {psgExpanded && psgList.map((inst) => (
          <div
            key={inst.id}
            className={`${styles.item} ${isSelected("psg", inst.id) ? styles.selected : ""}`}
            onClick={() => onSelect({ type: "psg", id: inst.id })}
            onContextMenu={(e) => handleContextMenu(e, "psg", inst.id)}
          >
            <span className={`${styles.dot} ${styles.psgDot}`} />
            <span className={styles.itemName}>{inst.name}</span>
          </div>
        ))}
      </div>

      <div className={styles.section}>
        <div className={styles.sectionHeader} onClick={() => setDacExpanded(!dacExpanded)}>
          <span>{dacExpanded ? "▼" : "▶"}</span>
          <span className={styles.sectionTitle}>DAC</span>
          <span className={styles.count}>{dacList.length}</span>
          <button className={styles.addBtn} onClick={(e) => { e.stopPropagation(); addDac(); }}>+</button>
        </div>
        {dacExpanded && dacList.map((inst) => (
          <div
            key={inst.id}
            className={`${styles.item} ${isSelected("dac", inst.id) ? styles.selected : ""}`}
            onClick={() => onSelect({ type: "dac", id: inst.id })}
            onContextMenu={(e) => handleContextMenu(e, "dac", inst.id)}
          >
            <span className={`${styles.dot} ${styles.dacDot}`} />
            <span className={styles.itemName}>{inst.name}</span>
          </div>
        ))}
      </div>

      {contextMenu && (
        <div className={styles.contextMenu} style={{ left: contextMenu.x, top: contextMenu.y }}>
          <button className={styles.menuItem} onClick={() => handleRename(contextMenu.type, contextMenu.id)}>Rename</button>
          {contextMenu.type !== "dac" && (
            <button className={styles.menuItem} onClick={() => handleDuplicate(contextMenu.type, contextMenu.id)}>Duplicate</button>
          )}
          <button className={`${styles.menuItem} ${styles.danger}`} onClick={() => handleDelete(contextMenu.type, contextMenu.id)}>Delete</button>
        </div>
      )}
    </div>
  );
}
```

Create `src/components/InstrumentBrowser.module.css`:

```css
.browser {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.section {
  display: flex;
  flex-direction: column;
}

.sectionHeader {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 4px;
  cursor: pointer;
  user-select: none;
  font-size: 11px;
  color: var(--text-secondary);
}

.sectionHeader:hover {
  color: var(--text-primary);
}

.sectionTitle {
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.count {
  color: var(--text-secondary);
  font-size: 10px;
  margin-left: auto;
}

.addBtn {
  width: 20px;
  height: 20px;
  padding: 0;
  background: var(--bg-surface);
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-radius: 3px;
  font-size: 14px;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.addBtn:hover {
  background: var(--border);
}

.item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px 4px 20px;
  cursor: pointer;
  border-radius: 3px;
  font-size: 12px;
}

.item:hover {
  background: var(--bg-surface);
}

.item.selected {
  background: var(--bg-surface);
  border-left: 2px solid var(--accent-fm);
  padding-left: 18px;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.fmDot { background: var(--accent-fm); }
.psgDot { background: var(--accent-psg); }
.dacDot { background: var(--accent-dac); }

.itemName {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.contextMenu {
  position: fixed;
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 4px 0;
  z-index: 200;
  min-width: 120px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
}

.menuItem {
  display: block;
  width: 100%;
  padding: 6px 12px;
  background: none;
  color: var(--text-primary);
  border: none;
  text-align: left;
  font-size: 12px;
}

.menuItem:hover {
  background: var(--bg-surface);
}

.menuItem.danger {
  color: var(--error);
}
```

- [ ] **Step 3: Wire into Sidebar**

Replace `src/components/Sidebar.tsx`:

```tsx
import { useState } from "react";
import type { SongMetadata, SelectedInstrument } from "../types/model";
import { TrackList } from "./TrackList";
import { InstrumentBrowser } from "./InstrumentBrowser";
import styles from "./Sidebar.module.css";

interface SidebarProps {
  projectMeta: SongMetadata;
  selectedInstrument: SelectedInstrument | null;
  onSelectInstrument: (inst: SelectedInstrument | null) => void;
}

export function Sidebar({ projectMeta, selectedInstrument, onSelectInstrument }: SidebarProps) {
  const [activeTab, setActiveTab] = useState<"tracks" | "instruments">("instruments");

  return (
    <div className={styles.sidebar}>
      <div className={styles.tabs}>
        <button
          className={`${styles.tab} ${activeTab === "tracks" ? styles.active : ""}`}
          onClick={() => setActiveTab("tracks")}
        >
          Tracks
        </button>
        <button
          className={`${styles.tab} ${activeTab === "instruments" ? styles.active : ""}`}
          onClick={() => setActiveTab("instruments")}
        >
          Instruments
        </button>
      </div>
      <div className={styles.content}>
        {activeTab === "tracks" && <TrackList driverId={projectMeta.driverId} />}
        {activeTab === "instruments" && (
          <InstrumentBrowser
            onSelect={onSelectInstrument}
            selectedInstrument={selectedInstrument}
          />
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Verify**

Run: `cd /home/volence/sonic_hacks/megadaw && npx tsc --noEmit`
Expected: No errors

Test in dev server: Create a project → Sidebar shows "Tracks" and "Instruments" tabs. Instruments tab has FM/PSG/DAC sections with "+" buttons. Click "+" on FM → new instrument appears. Right-click → context menu with Rename/Duplicate/Delete.

- [ ] **Step 5: Commit**

```bash
cd /home/volence/sonic_hacks/megadaw
git add src/components/TrackList.tsx src/components/TrackList.module.css \
  src/components/InstrumentBrowser.tsx src/components/InstrumentBrowser.module.css \
  src/components/Sidebar.tsx
git commit -m "feat(ui): TrackList + InstrumentBrowser with context menu"
```

---

### Task 7: Knob Widget

**Files:**
- Create: `src/widgets/Knob.tsx`
- Create: `src/widgets/Knob.module.css`

- [ ] **Step 1: Create Knob widget**

Create `src/widgets/Knob.tsx`:

```tsx
import { useRef, useState, useEffect } from "react";
import styles from "./Knob.module.css";

interface KnobProps {
  min: number;
  max: number;
  value: number;
  onChange: (value: number) => void;
  label: string;
  size?: number;
}

export function Knob({ min, max, value, onChange, label, size = 40 }: KnobProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [dragging, setDragging] = useState(false);
  const dragStartY = useRef(0);
  const dragStartValue = useRef(0);
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState("");

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    ctx.scale(dpr, dpr);

    const cx = size / 2;
    const cy = size / 2;
    const radius = size / 2 - 4;
    const startAngle = 0.75 * Math.PI;
    const endAngle = 2.25 * Math.PI;
    const range = max - min;
    const normalized = range > 0 ? (value - min) / range : 0;
    const valueAngle = startAngle + normalized * (endAngle - startAngle);

    ctx.clearRect(0, 0, size, size);

    ctx.beginPath();
    ctx.arc(cx, cy, radius, startAngle, endAngle);
    ctx.strokeStyle = getComputedStyle(canvas).getPropertyValue("--knob-track").trim() || "#444";
    ctx.lineWidth = 3;
    ctx.lineCap = "round";
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(cx, cy, radius, startAngle, valueAngle);
    ctx.strokeStyle = getComputedStyle(canvas).getPropertyValue("--knob-fill").trim() || "#4a9eff";
    ctx.lineWidth = 3;
    ctx.lineCap = "round";
    ctx.stroke();

    const ix = cx + (radius - 4) * Math.cos(valueAngle);
    const iy = cy + (radius - 4) * Math.sin(valueAngle);
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(ix, iy);
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 1.5;
    ctx.stroke();
  }, [value, min, max, size]);

  function handleMouseDown(e: React.MouseEvent) {
    if (e.detail === 2) {
      setEditing(true);
      setEditText(String(value));
      return;
    }
    setDragging(true);
    dragStartY.current = e.clientY;
    dragStartValue.current = value;
  }

  useEffect(() => {
    if (!dragging) return;

    const range = max - min;
    const sensitivity = Math.max(range / 100, 0.5);

    function handleMouseMove(e: MouseEvent) {
      const dy = dragStartY.current - e.clientY;
      const delta = Math.round(dy * sensitivity);
      const newValue = Math.max(min, Math.min(max, dragStartValue.current + delta));
      onChange(newValue);
    }

    function handleMouseUp() {
      setDragging(false);
    }

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [dragging, min, max, onChange]);

  function handleEditSubmit() {
    const parsed = parseInt(editText, 10);
    if (!isNaN(parsed)) {
      onChange(Math.max(min, Math.min(max, parsed)));
    }
    setEditing(false);
  }

  return (
    <div className={styles.knob}>
      <canvas
        ref={canvasRef}
        style={{ width: size, height: size }}
        onMouseDown={handleMouseDown}
        className={styles.canvas}
      />
      {editing ? (
        <input
          className={styles.editInput}
          style={{ width: size }}
          value={editText}
          onChange={(e) => setEditText(e.target.value)}
          onBlur={handleEditSubmit}
          onKeyDown={(e) => e.key === "Enter" && handleEditSubmit()}
          autoFocus
        />
      ) : (
        <span className={styles.value}>{value}</span>
      )}
      <span className={styles.label}>{label}</span>
    </div>
  );
}
```

Create `src/widgets/Knob.module.css`:

```css
.knob {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  user-select: none;
}

.canvas {
  cursor: ns-resize;
}

.value {
  font-size: 10px;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.label {
  font-size: 9px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.editInput {
  background: var(--bg-input);
  color: var(--text-primary);
  border: 1px solid var(--accent-fm);
  border-radius: 2px;
  text-align: center;
  font-size: 10px;
  padding: 1px;
}
```

- [ ] **Step 2: Verify TypeScript**

Run: `cd /home/volence/sonic_hacks/megadaw && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
cd /home/volence/sonic_hacks/megadaw
git add src/widgets/Knob.tsx src/widgets/Knob.module.css
git commit -m "feat(ui): Knob widget — rotary control with vertical drag"
```

---

### Task 8: FM Visual Widgets — AlgorithmDiagram, EnvelopeDisplay, PianoKeys

**Files:**
- Create: `src/widgets/AlgorithmDiagram.tsx`
- Create: `src/widgets/AlgorithmDiagram.module.css`
- Create: `src/widgets/EnvelopeDisplay.tsx`
- Create: `src/widgets/PianoKeys.tsx`
- Create: `src/widgets/PianoKeys.module.css`

- [ ] **Step 1: Create AlgorithmDiagram**

Create `src/widgets/AlgorithmDiagram.tsx`:

```tsx
import { useRef, useEffect } from "react";
import { CARRIER_MASKS } from "../types/model";
import styles from "./AlgorithmDiagram.module.css";

interface AlgorithmDiagramProps {
  algorithm: number;
  onSelect: (algo: number) => void;
}

interface AlgoLayout {
  ops: { x: number; y: number }[];
  connections: [number, number][];
}

const W = 86;
const H = 44;
const BOX_W = 14;
const BOX_H = 12;

const LAYOUTS: AlgoLayout[] = [
  { ops: [{x:4,y:16},{x:24,y:16},{x:44,y:16},{x:64,y:16}], connections: [[0,1],[1,2],[2,3]] },
  { ops: [{x:4,y:6},{x:4,y:28},{x:34,y:16},{x:64,y:16}], connections: [[0,2],[1,2],[2,3]] },
  { ops: [{x:4,y:6},{x:4,y:28},{x:34,y:28},{x:64,y:16}], connections: [[0,3],[1,2],[2,3]] },
  { ops: [{x:4,y:6},{x:34,y:6},{x:4,y:28},{x:64,y:16}], connections: [[0,1],[1,3],[2,3]] },
  { ops: [{x:4,y:6},{x:34,y:6},{x:4,y:28},{x:34,y:28}], connections: [[0,1],[2,3]] },
  { ops: [{x:4,y:16},{x:34,y:2},{x:34,y:16},{x:34,y:30}], connections: [[0,1],[0,2],[0,3]] },
  { ops: [{x:4,y:16},{x:34,y:16},{x:56,y:6},{x:56,y:28}], connections: [[0,1]] },
  { ops: [{x:4,y:16},{x:26,y:16},{x:48,y:16},{x:70,y:16}], connections: [] },
];

function drawAlgo(canvas: HTMLCanvasElement, algoIndex: number, isActive: boolean) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const dpr = window.devicePixelRatio || 1;
  canvas.width = W * dpr;
  canvas.height = H * dpr;
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, W, H);

  const layout = LAYOUTS[algoIndex];
  const carriers = CARRIER_MASKS[algoIndex];
  const style = getComputedStyle(canvas);
  const fmColor = style.getPropertyValue("--accent-fm").trim() || "#4a9eff";
  const carrierColor = style.getPropertyValue("--carrier-highlight").trim() || "#ffcc44";
  const textColor = style.getPropertyValue("--text-primary").trim() || "#e0e0e0";
  const dimColor = style.getPropertyValue("--text-secondary").trim() || "#888";

  for (const [from, to] of layout.connections) {
    const fx = layout.ops[from].x + BOX_W / 2;
    const fy = layout.ops[from].y + BOX_H / 2;
    const tx = layout.ops[to].x + BOX_W / 2;
    const ty = layout.ops[to].y + BOX_H / 2;
    ctx.beginPath();
    ctx.moveTo(fx, fy);
    ctx.lineTo(tx, ty);
    ctx.strokeStyle = isActive ? fmColor : dimColor;
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  for (let i = 0; i < 4; i++) {
    const { x, y } = layout.ops[i];
    const isCarrier = (carriers & (1 << i)) !== 0;
    ctx.fillStyle = isCarrier && isActive ? carrierColor : (isActive ? fmColor : dimColor);
    ctx.globalAlpha = isActive ? 0.25 : 0.1;
    ctx.fillRect(x, y, BOX_W, BOX_H);
    ctx.globalAlpha = 1;
    ctx.strokeStyle = isCarrier && isActive ? carrierColor : (isActive ? fmColor : dimColor);
    ctx.lineWidth = 1;
    ctx.strokeRect(x, y, BOX_W, BOX_H);
    ctx.fillStyle = isActive ? textColor : dimColor;
    ctx.font = "9px sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(String(i + 1), x + BOX_W / 2, y + BOX_H / 2);
  }
}

export function AlgorithmDiagram({ algorithm, onSelect }: AlgorithmDiagramProps) {
  const canvasRefs = useRef<(HTMLCanvasElement | null)[]>([]);

  useEffect(() => {
    for (let i = 0; i < 8; i++) {
      const canvas = canvasRefs.current[i];
      if (canvas) drawAlgo(canvas, i, i === algorithm);
    }
  }, [algorithm]);

  return (
    <div className={styles.grid}>
      {Array.from({ length: 8 }, (_, i) => (
        <div
          key={i}
          className={`${styles.cell} ${i === algorithm ? styles.active : ""}`}
          onClick={() => onSelect(i)}
        >
          <canvas
            ref={(el) => { canvasRefs.current[i] = el; }}
            style={{ width: W, height: H }}
          />
          <span className={styles.label}>{i}</span>
        </div>
      ))}
    </div>
  );
}
```

Create `src/widgets/AlgorithmDiagram.module.css`:

```css
.grid {
  display: grid;
  grid-template-columns: repeat(4, auto);
  gap: 4px;
}

.cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 4px;
  border: 1px solid var(--border);
  border-radius: 4px;
  cursor: pointer;
  background: var(--bg-app);
}

.cell:hover {
  border-color: var(--text-secondary);
}

.cell.active {
  border-color: var(--accent-fm);
  background: var(--bg-surface);
}

.label {
  font-size: 10px;
  color: var(--text-secondary);
}
```

- [ ] **Step 2: Create EnvelopeDisplay**

Create `src/widgets/EnvelopeDisplay.tsx`:

```tsx
import { useRef, useEffect } from "react";

interface EnvelopeDisplayProps {
  attackRate: number;
  d1r: number;
  d2r: number;
  sustainLevel: number;
  releaseRate: number;
  width?: number;
  height?: number;
}

export function EnvelopeDisplay({
  attackRate, d1r, d2r, sustainLevel, releaseRate,
  width = 180, height = 70,
}: EnvelopeDisplayProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    const pad = 4;
    const w = width - pad * 2;
    const h = height - pad * 2;

    const aFrac = attackRate > 0 ? Math.pow((31 - attackRate) / 31, 1.5) : 1;
    const d1Frac = d1r > 0 ? Math.pow((31 - d1r) / 31, 1.5) : 0;
    const d2Frac = d2r > 0 ? Math.pow((31 - d2r) / 31, 1.5) * 0.3 : 0;
    const rFrac = releaseRate > 0 ? Math.pow((15 - releaseRate) / 15, 1.5) : 1;

    const slNorm = 1 - sustainLevel / 15;
    const slY = pad + h * (1 - slNorm);

    const aW = Math.max(2, aFrac * w * 0.2);
    const d1W = Math.max(0, d1Frac * w * 0.2);
    const susW = w * 0.3;
    const d2W = Math.max(0, d2Frac * w * 0.15);
    const rW = Math.max(2, rFrac * w * 0.15);

    const style = getComputedStyle(canvas);
    const lineColor = style.getPropertyValue("--envelope-line").trim() || "#66ccff";
    const fillColor = style.getPropertyValue("--envelope-fill").trim() || "rgba(102,204,255,0.15)";

    ctx.beginPath();
    let x = pad;
    ctx.moveTo(x, pad + h);

    x += aW;
    ctx.lineTo(x, pad);

    const d2Decay = d2r > 0 ? slNorm * 0.15 * h : 0;

    x += d1W;
    ctx.lineTo(x, slY);

    x += susW;
    ctx.lineTo(x, slY + d2Decay);

    x += d2W;
    ctx.lineTo(x, slY + d2Decay);

    x += rW;
    ctx.lineTo(x, pad + h);

    ctx.strokeStyle = lineColor;
    ctx.lineWidth = 1.5;
    ctx.stroke();

    ctx.lineTo(x, pad + h);
    ctx.lineTo(pad, pad + h);
    ctx.closePath();
    ctx.fillStyle = fillColor;
    ctx.fill();
  }, [attackRate, d1r, d2r, sustainLevel, releaseRate, width, height]);

  return <canvas ref={canvasRef} style={{ width, height, display: "block" }} />;
}
```

- [ ] **Step 3: Create PianoKeys**

Create `src/widgets/PianoKeys.tsx`:

```tsx
import { useState } from "react";
import styles from "./PianoKeys.module.css";

interface PianoKeysProps {
  onNoteOn: (midiNote: number) => void;
}

const WHITE_SEMITONES = [0, 2, 4, 5, 7, 9, 11];
const BLACK_SEMITONES = [1, 3, 6, 8, 10];
const BLACK_POSITIONS = [0, 1, 3, 4, 5];

export function PianoKeys({ onNoteOn }: PianoKeysProps) {
  const [octave, setOctave] = useState(4);
  const [activeKey, setActiveKey] = useState<number | null>(null);

  function handleKey(semitone: number, e: React.MouseEvent) {
    let oct = octave;
    if (e.shiftKey) oct += 1;
    if (e.ctrlKey) oct -= 1;
    const midiNote = Math.max(0, Math.min(127, (oct + 1) * 12 + semitone));
    onNoteOn(midiNote);
    setActiveKey(semitone);
    setTimeout(() => setActiveKey(null), 150);
  }

  return (
    <div className={styles.container}>
      <div className={styles.controls}>
        <button className={styles.octBtn} onClick={() => setOctave(Math.max(0, octave - 1))}>-</button>
        <span className={styles.octLabel}>C{octave}</span>
        <button className={styles.octBtn} onClick={() => setOctave(Math.min(8, octave + 1))}>+</button>
      </div>
      <div className={styles.keyboard}>
        {WHITE_SEMITONES.map((semi) => (
          <div
            key={semi}
            className={`${styles.whiteKey} ${activeKey === semi ? styles.activeWhite : ""}`}
            onMouseDown={(e) => handleKey(semi, e)}
          />
        ))}
        {BLACK_SEMITONES.map((semi, i) => (
          <div
            key={semi}
            className={`${styles.blackKey} ${activeKey === semi ? styles.activeBlack : ""}`}
            style={{ left: `${(BLACK_POSITIONS[i] + 0.65) * (100 / 7)}%` }}
            onMouseDown={(e) => handleKey(semi, e)}
          />
        ))}
      </div>
    </div>
  );
}
```

Create `src/widgets/PianoKeys.module.css`:

```css
.container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 8px;
}

.controls {
  display: flex;
  align-items: center;
  gap: 4px;
}

.octBtn {
  width: 20px;
  height: 20px;
  padding: 0;
  background: var(--bg-surface);
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-radius: 3px;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.octLabel {
  font-size: 11px;
  color: var(--text-secondary);
  width: 24px;
  text-align: center;
}

.keyboard {
  position: relative;
  display: flex;
  width: 140px;
  height: 60px;
}

.whiteKey {
  flex: 1;
  background: #eee;
  border: 1px solid #999;
  border-radius: 0 0 3px 3px;
  cursor: pointer;
}

.whiteKey:hover {
  background: #ddd;
}

.whiteKey.activeWhite {
  background: var(--accent-fm);
}

.blackKey {
  position: absolute;
  width: 10%;
  height: 58%;
  background: #222;
  border: 1px solid #111;
  border-radius: 0 0 2px 2px;
  cursor: pointer;
  z-index: 1;
  transform: translateX(-50%);
}

.blackKey:hover {
  background: #444;
}

.blackKey.activeBlack {
  background: var(--accent-fm);
}
```

- [ ] **Step 4: Verify**

Run: `cd /home/volence/sonic_hacks/megadaw && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
cd /home/volence/sonic_hacks/megadaw
git add src/widgets/AlgorithmDiagram.tsx src/widgets/AlgorithmDiagram.module.css \
  src/widgets/EnvelopeDisplay.tsx src/widgets/PianoKeys.tsx src/widgets/PianoKeys.module.css
git commit -m "feat(ui): AlgorithmDiagram, EnvelopeDisplay, PianoKeys widgets"
```

---

### Task 9: FM Instrument Editor

**Files:**
- Create: `src/components/FmEditor.tsx`
- Create: `src/components/FmEditor.module.css`
- Modify: `src/components/BottomPanel.tsx`

- [ ] **Step 1: Create FmEditor**

Create `src/components/FmEditor.tsx`:

```tsx
import { useState, useEffect, useCallback } from "react";
import type { FmInstrument, FmOperator } from "../types/model";
import { isCarrier } from "../types/model";
import * as ipc from "../api/ipc";
import { Knob } from "../widgets/Knob";
import { AlgorithmDiagram } from "../widgets/AlgorithmDiagram";
import { EnvelopeDisplay } from "../widgets/EnvelopeDisplay";
import { PianoKeys } from "../widgets/PianoKeys";
import styles from "./FmEditor.module.css";

interface FmEditorProps {
  instrumentId: string;
}

export function FmEditor({ instrumentId }: FmEditorProps) {
  const [instrument, setInstrument] = useState<FmInstrument | null>(null);

  const load = useCallback(async () => {
    const list = await ipc.listFmInstruments();
    setInstrument(list.find((i) => i.id === instrumentId) ?? null);
  }, [instrumentId]);

  useEffect(() => { load(); }, [load]);

  if (!instrument) return null;

  async function updateInstrument(updates: Partial<FmInstrument>) {
    const updated = { ...instrument!, ...updates };
    setInstrument(updated);
    try {
      await ipc.updateFmInstrument(instrumentId, updated);
    } catch {
      load();
    }
  }

  async function updateOp(opIndex: number, updates: Partial<FmOperator>) {
    const ops = [...instrument!.operators] as [FmOperator, FmOperator, FmOperator, FmOperator];
    ops[opIndex] = { ...ops[opIndex], ...updates };
    await updateInstrument({ operators: ops });
  }

  return (
    <div className={styles.fmEditor}>
      <div className={styles.leftSection}>
        <AlgorithmDiagram
          algorithm={instrument.algorithm}
          onSelect={(a) => updateInstrument({ algorithm: a })}
        />
        <div className={styles.fbKnob}>
          <Knob min={0} max={7} value={instrument.feedback} onChange={(v) => updateInstrument({ feedback: v })} label="FB" size={44} />
        </div>
      </div>

      {instrument.operators.map((op, i) => (
        <div key={i} className={`${styles.opPanel} ${isCarrier(instrument.algorithm, i) ? styles.carrier : ""}`}>
          <div className={styles.opHeader}>
            <span>Op {i + 1}</span>
            {isCarrier(instrument.algorithm, i) && <span className={styles.carrierBadge}>C</span>}
          </div>
          <EnvelopeDisplay
            attackRate={op.attackRate}
            d1r={op.d1r}
            d2r={op.d2r}
            sustainLevel={op.sustainLevel}
            releaseRate={op.releaseRate}
          />
          <div className={styles.knobGrid}>
            <Knob min={0} max={7} value={op.detune} onChange={(v) => updateOp(i, { detune: v })} label="DT" size={36} />
            <Knob min={0} max={15} value={op.multiple} onChange={(v) => updateOp(i, { multiple: v })} label="MUL" size={36} />
            <Knob min={0} max={3} value={op.rateScale} onChange={(v) => updateOp(i, { rateScale: v })} label="RS" size={36} />
            <Knob min={0} max={31} value={op.attackRate} onChange={(v) => updateOp(i, { attackRate: v })} label="AR" size={36} />
            <Knob min={0} max={31} value={op.d1r} onChange={(v) => updateOp(i, { d1r: v })} label="D1R" size={36} />
            <Knob min={0} max={31} value={op.d2r} onChange={(v) => updateOp(i, { d2r: v })} label="D2R" size={36} />
            <Knob min={0} max={15} value={op.sustainLevel} onChange={(v) => updateOp(i, { sustainLevel: v })} label="SL" size={36} />
            <Knob min={0} max={15} value={op.releaseRate} onChange={(v) => updateOp(i, { releaseRate: v })} label="RR" size={36} />
          </div>
          <div className={styles.tlRow}>
            <span className={styles.tlLabel}>TL</span>
            <input
              type="range"
              className={styles.tlSlider}
              min={0}
              max={127}
              value={instrument.operators[i].totalLevel}
              onChange={(e) => updateOp(i, { totalLevel: parseInt(e.target.value) })}
            />
            <span className={styles.tlValue}>{op.totalLevel}</span>
          </div>
          <label className={styles.amToggle}>
            <input type="checkbox" checked={op.ampMod} onChange={(e) => updateOp(i, { ampMod: e.target.checked })} />
            AM
          </label>
        </div>
      ))}

      <div className={styles.previewSection}>
        <PianoKeys onNoteOn={(note) => ipc.previewFmInstrument(instrumentId, note)} />
      </div>
    </div>
  );
}
```

Create `src/components/FmEditor.module.css`:

```css
.fmEditor {
  display: flex;
  gap: 12px;
  padding: 12px;
  height: 100%;
  align-items: flex-start;
  overflow-x: auto;
}

.leftSection {
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: center;
  flex-shrink: 0;
}

.fbKnob {
  margin-top: 4px;
}

.opPanel {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px;
  background: var(--bg-app);
  border: 1px solid var(--border);
  border-radius: 6px;
  flex-shrink: 0;
  min-width: 190px;
}

.opPanel.carrier {
  border-color: var(--carrier-highlight);
}

.opHeader {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
}

.carrierBadge {
  font-size: 9px;
  padding: 1px 4px;
  background: var(--carrier-highlight);
  color: #000;
  border-radius: 2px;
  font-weight: 700;
}

.knobGrid {
  display: grid;
  grid-template-columns: repeat(4, auto);
  gap: 6px;
  justify-items: center;
}

.tlRow {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 2px 0;
}

.tlLabel {
  font-size: 9px;
  color: var(--text-secondary);
  text-transform: uppercase;
  width: 18px;
}

.tlSlider {
  flex: 1;
  height: 4px;
  accent-color: var(--accent-fm);
}

.tlValue {
  font-size: 10px;
  color: var(--text-primary);
  width: 24px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.amToggle {
  font-size: 11px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}

.amToggle input {
  accent-color: var(--accent-fm);
}

.previewSection {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
}
```

- [ ] **Step 2: Wire FmEditor into BottomPanel**

Replace `src/components/BottomPanel.tsx`:

```tsx
import { useState } from "react";
import type { SelectedInstrument } from "../types/model";
import { FmEditor } from "./FmEditor";
import styles from "./BottomPanel.module.css";

interface BottomPanelProps {
  selectedInstrument: SelectedInstrument | null;
}

export function BottomPanel({ selectedInstrument }: BottomPanelProps) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className={`${styles.panel} ${collapsed ? styles.collapsed : ""}`}>
      <div className={styles.header} onClick={() => setCollapsed(!collapsed)}>
        <span className={styles.toggle}>{collapsed ? "▶" : "▼"}</span>
        <span>Instrument Editor</span>
      </div>
      {!collapsed && (
        <div className={styles.editor}>
          {!selectedInstrument && (
            <div className={styles.empty}>Select an instrument to edit</div>
          )}
          {selectedInstrument?.type === "fm" && (
            <FmEditor instrumentId={selectedInstrument.id} />
          )}
          {selectedInstrument?.type === "psg" && (
            <div className={styles.empty}>PSG editor — Task 10</div>
          )}
          {selectedInstrument?.type === "dac" && (
            <div className={styles.empty}>DAC editor — Task 11</div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Verify**

Run: `cd /home/volence/sonic_hacks/megadaw && npx tsc --noEmit`
Expected: No errors

Test in dev server: Create project → add FM instrument → select it → bottom panel shows algorithm diagram, 4 operator panels with knobs and envelope displays, preview keyboard. Click a key → hear FM tone through emulator.

- [ ] **Step 4: Commit**

```bash
cd /home/volence/sonic_hacks/megadaw
git add src/components/FmEditor.tsx src/components/FmEditor.module.css src/components/BottomPanel.tsx
git commit -m "feat(ui): FM instrument editor with knobs, envelope display, preview"
```

---

### Task 10: StepGraphEditor Widget + PSG Editor

**Files:**
- Create: `src/widgets/StepGraphEditor.tsx`
- Create: `src/widgets/StepGraphEditor.module.css`
- Create: `src/components/PsgEditor.tsx`
- Create: `src/components/PsgEditor.module.css`
- Modify: `src/components/BottomPanel.tsx`

- [ ] **Step 1: Create StepGraphEditor widget**

Create `src/widgets/StepGraphEditor.tsx`:

```tsx
import { useRef, useEffect, useState, useCallback } from "react";
import styles from "./StepGraphEditor.module.css";

interface StepGraphEditorProps {
  values: number[];
  max: number;
  onChange: (values: number[]) => void;
  loopPoint: number | null;
  onLoopChange: (point: number | null) => void;
}

export function StepGraphEditor({ values, max, onChange, loopPoint, onLoopChange }: StepGraphEditorProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [drawing, setDrawing] = useState(false);
  const [draggingLoop, setDraggingLoop] = useState(false);
  const width = Math.max(200, values.length * 16);
  const height = 120;

  const barWidth = useCallback(() => {
    return Math.max(8, Math.min(20, width / values.length));
  }, [width, values.length]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    const bw = barWidth();
    const gap = 2;
    const style = getComputedStyle(canvas);
    const psgColor = style.getPropertyValue("--accent-psg").trim() || "#44cc66";

    for (let i = 0; i < values.length; i++) {
      const x = i * bw;
      const barH = (values[i] / max) * (height - 20);
      const y = height - 10 - barH;
      ctx.fillStyle = psgColor;
      ctx.globalAlpha = 0.7;
      ctx.fillRect(x + gap / 2, y, bw - gap, barH);
      ctx.globalAlpha = 1;
      ctx.strokeStyle = psgColor;
      ctx.strokeRect(x + gap / 2, y, bw - gap, barH);
    }

    if (loopPoint !== null && loopPoint < values.length) {
      const lx = loopPoint * bw + bw / 2;
      ctx.beginPath();
      ctx.moveTo(lx, 0);
      ctx.lineTo(lx, height);
      ctx.strokeStyle = "#ff6644";
      ctx.lineWidth = 2;
      ctx.setLineDash([4, 2]);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = "#ff6644";
      ctx.beginPath();
      ctx.moveTo(lx - 5, 0);
      ctx.lineTo(lx + 5, 0);
      ctx.lineTo(lx, 8);
      ctx.fill();
    }
  }, [values, max, width, height, loopPoint, barWidth]);

  function getBarIndex(e: React.MouseEvent): number {
    const rect = canvasRef.current!.getBoundingClientRect();
    const x = e.clientX - rect.left;
    return Math.floor(x / barWidth());
  }

  function getBarValue(e: React.MouseEvent): number {
    const rect = canvasRef.current!.getBoundingClientRect();
    const y = e.clientY - rect.top;
    const normalized = 1 - (y - 10) / (height - 20);
    return Math.max(0, Math.min(max, Math.round(normalized * max)));
  }

  function handleMouseDown(e: React.MouseEvent) {
    const idx = getBarIndex(e);
    if (idx < 0 || idx >= values.length) return;

    if (loopPoint !== null && Math.abs(idx - loopPoint) <= 0) {
      setDraggingLoop(true);
      return;
    }

    setDrawing(true);
    const val = getBarValue(e);
    const newValues = [...values];
    newValues[idx] = val;
    onChange(newValues);
  }

  function handleMouseMove(e: React.MouseEvent) {
    if (draggingLoop) {
      const idx = getBarIndex(e);
      if (idx >= 0 && idx < values.length) onLoopChange(idx);
      return;
    }
    if (!drawing) return;
    const idx = getBarIndex(e);
    if (idx < 0 || idx >= values.length) return;
    const val = getBarValue(e);
    const newValues = [...values];
    newValues[idx] = val;
    onChange(newValues);
  }

  function handleMouseUp() {
    setDrawing(false);
    setDraggingLoop(false);
  }

  return (
    <div className={styles.container}>
      <canvas
        ref={canvasRef}
        style={{ width, height }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        className={styles.canvas}
      />
    </div>
  );
}
```

Create `src/widgets/StepGraphEditor.module.css`:

```css
.container {
  overflow-x: auto;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--bg-app);
}

.canvas {
  display: block;
  cursor: crosshair;
}
```

- [ ] **Step 2: Create PsgEditor**

Create `src/components/PsgEditor.tsx`:

```tsx
import { useState, useEffect, useCallback } from "react";
import type { PsgInstrument, NoiseMode } from "../types/model";
import * as ipc from "../api/ipc";
import { StepGraphEditor } from "../widgets/StepGraphEditor";
import styles from "./PsgEditor.module.css";

interface PsgEditorProps {
  instrumentId: string;
}

export function PsgEditor({ instrumentId }: PsgEditorProps) {
  const [instrument, setInstrument] = useState<PsgInstrument | null>(null);

  const load = useCallback(async () => {
    const list = await ipc.listPsgInstruments();
    setInstrument(list.find((i) => i.id === instrumentId) ?? null);
  }, [instrumentId]);

  useEffect(() => { load(); }, [load]);

  if (!instrument) return null;

  async function update(updates: Partial<PsgInstrument>) {
    const updated = { ...instrument!, ...updates };
    setInstrument(updated);
    try {
      await ipc.updatePsgInstrument(instrumentId, updated);
    } catch {
      load();
    }
  }

  function getNoiseType(): "off" | "periodic" | "white" {
    if (!instrument!.noiseMode) return "off";
    if ("Periodic" in instrument!.noiseMode) return "periodic";
    return "white";
  }

  function getNoisePeriod(): number {
    if (!instrument!.noiseMode) return 0;
    if ("Periodic" in instrument!.noiseMode) return instrument!.noiseMode.Periodic;
    return instrument!.noiseMode.White;
  }

  function setNoiseType(type: "off" | "periodic" | "white") {
    if (type === "off") {
      update({ noiseMode: null });
    } else {
      const period = getNoisePeriod() || 100;
      const mode: NoiseMode = type === "periodic" ? { Periodic: period } : { White: period };
      update({ noiseMode: mode });
    }
  }

  function setNoisePeriod(period: number) {
    const type = getNoiseType();
    if (type === "periodic") update({ noiseMode: { Periodic: period } });
    else if (type === "white") update({ noiseMode: { White: period } });
  }

  return (
    <div className={styles.psgEditor}>
      <div className={styles.graphSection}>
        <div className={styles.graphHeader}>
          <span className={styles.sectionTitle}>Volume Envelope</span>
          <div className={styles.graphActions}>
            <button
              className={styles.smallBtn}
              onClick={() => update({ volumeSequence: [...instrument.volumeSequence, 0] })}
            >
              + Tick
            </button>
            <button
              className={styles.smallBtn}
              onClick={() => {
                if (instrument.volumeSequence.length > 1) {
                  update({ volumeSequence: instrument.volumeSequence.slice(0, -1) });
                }
              }}
            >
              - Tick
            </button>
          </div>
        </div>
        <StepGraphEditor
          values={instrument.volumeSequence}
          max={15}
          onChange={(values) => update({ volumeSequence: values })}
          loopPoint={instrument.loopPoint}
          onLoopChange={(point) => update({ loopPoint: point })}
        />
      </div>

      <div className={styles.settingsSection}>
        <div className={styles.settingGroup}>
          <span className={styles.settingLabel}>Loop</span>
          <label className={styles.toggle}>
            <input
              type="checkbox"
              checked={instrument.loopPoint !== null}
              onChange={(e) => update({ loopPoint: e.target.checked ? 0 : null })}
            />
            {instrument.loopPoint !== null ? `Point: ${instrument.loopPoint}` : "Off"}
          </label>
        </div>

        <div className={styles.settingGroup}>
          <span className={styles.settingLabel}>Noise Mode</span>
          <div className={styles.noiseButtons}>
            {(["off", "periodic", "white"] as const).map((type) => (
              <button
                key={type}
                className={`${styles.noiseBtn} ${getNoiseType() === type ? styles.activeNoise : ""}`}
                onClick={() => setNoiseType(type)}
              >
                {type.charAt(0).toUpperCase() + type.slice(1)}
              </button>
            ))}
          </div>
          {getNoiseType() !== "off" && (
            <div className={styles.periodRow}>
              <span className={styles.periodLabel}>Period</span>
              <input
                className={styles.periodInput}
                type="number"
                min={0}
                max={1023}
                value={getNoisePeriod()}
                onChange={(e) => setNoisePeriod(Number(e.target.value))}
              />
            </div>
          )}
        </div>

        <div className={styles.settingGroup}>
          <button
            className={styles.previewBtn}
            onClick={() => ipc.previewPsgInstrument(instrumentId, 60)}
          >
            Preview
          </button>
        </div>
      </div>
    </div>
  );
}
```

Create `src/components/PsgEditor.module.css`:

```css
.psgEditor {
  display: flex;
  gap: 16px;
  padding: 12px;
  height: 100%;
}

.graphSection {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.graphHeader {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sectionTitle {
  font-size: 12px;
  font-weight: 600;
  color: var(--accent-psg);
}

.graphActions {
  display: flex;
  gap: 4px;
}

.smallBtn {
  padding: 3px 8px;
  font-size: 11px;
  background: var(--bg-surface);
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-radius: 3px;
}

.smallBtn:hover {
  background: var(--border);
}

.settingsSection {
  width: 200px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.settingGroup {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.settingLabel {
  font-size: 11px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.toggle {
  font-size: 12px;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}

.toggle input {
  accent-color: var(--accent-psg);
}

.noiseButtons {
  display: flex;
  gap: 4px;
}

.noiseBtn {
  flex: 1;
  padding: 4px 8px;
  font-size: 11px;
  background: var(--bg-surface);
  color: var(--text-secondary);
  border: 1px solid var(--border);
  border-radius: 3px;
}

.noiseBtn:hover {
  color: var(--text-primary);
}

.noiseBtn.activeNoise {
  background: var(--accent-psg);
  color: #000;
  border-color: var(--accent-psg);
}

.periodRow {
  display: flex;
  align-items: center;
  gap: 6px;
}

.periodLabel {
  font-size: 11px;
  color: var(--text-secondary);
}

.periodInput {
  width: 80px;
  padding: 4px 6px;
  background: var(--bg-input);
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-radius: 3px;
}

.previewBtn {
  padding: 8px 16px;
  background: var(--accent-psg);
  color: #000;
  border: none;
  border-radius: 4px;
  font-weight: 500;
}

.previewBtn:hover {
  opacity: 0.9;
}
```

- [ ] **Step 3: Wire PsgEditor into BottomPanel**

In `src/components/BottomPanel.tsx`, add the import:

```tsx
import { PsgEditor } from "./PsgEditor";
```

Replace the PSG placeholder line:
```tsx
          {selectedInstrument?.type === "psg" && (
            <PsgEditor instrumentId={selectedInstrument.id} />
          )}
```

- [ ] **Step 4: Verify**

Run: `cd /home/volence/sonic_hacks/megadaw && npx tsc --noEmit`
Expected: No errors

Test in dev server: Create project → add PSG instrument → select it → bottom panel shows drawable step graph, loop toggle, noise mode, preview button. Draw on the graph, click Preview → hear PSG sound.

- [ ] **Step 5: Commit**

```bash
cd /home/volence/sonic_hacks/megadaw
git add src/widgets/StepGraphEditor.tsx src/widgets/StepGraphEditor.module.css \
  src/components/PsgEditor.tsx src/components/PsgEditor.module.css src/components/BottomPanel.tsx
git commit -m "feat(ui): PSG instrument editor with drawable step graph envelope"
```

---

### Task 11: WaveformViewer Widget + DAC Editor

**Files:**
- Create: `src/widgets/WaveformViewer.tsx`
- Create: `src/components/DacEditor.tsx`
- Create: `src/components/DacEditor.module.css`
- Modify: `src/components/BottomPanel.tsx`

- [ ] **Step 1: Create WaveformViewer widget**

Create `src/widgets/WaveformViewer.tsx`:

```tsx
import { useRef, useEffect } from "react";

interface WaveformViewerProps {
  data: number[];
  width?: number;
  height?: number;
}

export function WaveformViewer({ data, width = 500, height = 120 }: WaveformViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    if (data.length === 0) return;

    const style = getComputedStyle(canvas);
    const dacColor = style.getPropertyValue("--accent-dac").trim() || "#ff8844";

    const centerY = height / 2;
    ctx.beginPath();
    ctx.moveTo(0, centerY);
    ctx.lineTo(width, centerY);
    ctx.strokeStyle = "var(--border)";
    ctx.lineWidth = 1;
    ctx.stroke();

    const step = Math.max(1, Math.floor(data.length / width));
    ctx.beginPath();
    for (let x = 0; x < width; x++) {
      const sampleIndex = Math.floor((x / width) * data.length);
      let minVal = 255;
      let maxVal = 0;
      for (let j = sampleIndex; j < Math.min(sampleIndex + step, data.length); j++) {
        minVal = Math.min(minVal, data[j]);
        maxVal = Math.max(maxVal, data[j]);
      }
      const yMin = ((255 - maxVal) / 255) * height;
      const yMax = ((255 - minVal) / 255) * height;
      if (x === 0) {
        ctx.moveTo(x, (yMin + yMax) / 2);
      }
      ctx.lineTo(x, yMin);
      ctx.lineTo(x, yMax);
    }
    ctx.strokeStyle = dacColor;
    ctx.lineWidth = 1;
    ctx.stroke();
  }, [data, width, height]);

  return (
    <canvas
      ref={canvasRef}
      style={{ width, height, display: "block", border: "1px solid var(--border)", borderRadius: 4, background: "var(--bg-app)" }}
    />
  );
}
```

- [ ] **Step 2: Create DacEditor**

Create `src/components/DacEditor.tsx`:

```tsx
import { useState, useEffect, useCallback } from "react";
import type { DacInstrument } from "../types/model";
import * as ipc from "../api/ipc";
import { WaveformViewer } from "../widgets/WaveformViewer";
import styles from "./DacEditor.module.css";

interface DacEditorProps {
  instrumentId: string;
}

const SAMPLE_RATES = [8000, 11025, 16000, 22050, 32000];

export function DacEditor({ instrumentId }: DacEditorProps) {
  const [instrument, setInstrument] = useState<DacInstrument | null>(null);
  const [pcmData, setPcmData] = useState<number[]>([]);

  const load = useCallback(async () => {
    const list = await ipc.listDacInstruments();
    const inst = list.find((i) => i.id === instrumentId);
    setInstrument(inst ?? null);
    if (inst) {
      try {
        const data = await ipc.getDacPcmData(instrumentId);
        setPcmData(data);
      } catch {
        setPcmData([]);
      }
    }
  }, [instrumentId]);

  useEffect(() => { load(); }, [load]);

  if (!instrument) return null;

  async function handleNameChange(name: string) {
    const updated = { ...instrument!, name };
    setInstrument(updated);
    try {
      await ipc.updateDacInstrument(instrumentId, updated);
    } catch {
      load();
    }
  }

  async function handleRateChange(newRate: number) {
    try {
      await ipc.reconvertDac(instrumentId, newRate);
      await load();
    } catch (e) {
      console.error("Reconvert failed:", e);
    }
  }

  return (
    <div className={styles.dacEditor}>
      <div className={styles.waveformSection}>
        <WaveformViewer data={pcmData} width={500} height={120} />
        <span className={styles.sampleCount}>{pcmData.length.toLocaleString()} samples</span>
      </div>

      <div className={styles.settingsSection}>
        <div className={styles.field}>
          <span className={styles.fieldLabel}>Name</span>
          <input
            className={styles.nameInput}
            value={instrument.name}
            onChange={(e) => handleNameChange(e.target.value)}
            onBlur={() => ipc.updateDacInstrument(instrumentId, instrument)}
          />
        </div>

        <div className={styles.field}>
          <span className={styles.fieldLabel}>Source</span>
          <span className={styles.sourceInfo}>
            {instrument.sourceIsRaw ? "Raw PCM" : "WAV"} — {instrument.originalFile}
          </span>
        </div>

        <div className={styles.field}>
          <span className={styles.fieldLabel}>Sample Rate</span>
          <select
            className={styles.rateSelect}
            value={instrument.targetSampleRate}
            onChange={(e) => handleRateChange(Number(e.target.value))}
            disabled={instrument.sourceIsRaw}
          >
            {SAMPLE_RATES.map((rate) => (
              <option key={rate} value={rate}>{rate} Hz</option>
            ))}
          </select>
          {instrument.sourceIsRaw && (
            <span className={styles.hint}>Cannot reconvert raw imports</span>
          )}
        </div>

        <button
          className={styles.previewBtn}
          onClick={() => ipc.previewDac(instrumentId)}
        >
          Preview
        </button>
      </div>
    </div>
  );
}
```

Create `src/components/DacEditor.module.css`:

```css
.dacEditor {
  display: flex;
  gap: 20px;
  padding: 12px;
  height: 100%;
  align-items: flex-start;
}

.waveformSection {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  min-width: 0;
}

.sampleCount {
  font-size: 11px;
  color: var(--text-secondary);
}

.settingsSection {
  width: 240px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.fieldLabel {
  font-size: 11px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.nameInput {
  padding: 6px 8px;
  background: var(--bg-input);
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-radius: 3px;
}

.nameInput:focus {
  border-color: var(--border-focus);
  outline: none;
}

.sourceInfo {
  font-size: 12px;
  color: var(--text-primary);
  word-break: break-all;
}

.rateSelect {
  padding: 6px 8px;
  background: var(--bg-input);
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-radius: 3px;
}

.rateSelect:disabled {
  opacity: 0.5;
}

.hint {
  font-size: 10px;
  color: var(--text-secondary);
}

.previewBtn {
  padding: 8px 16px;
  background: var(--accent-dac);
  color: #000;
  border: none;
  border-radius: 4px;
  font-weight: 500;
  align-self: flex-start;
}

.previewBtn:hover {
  opacity: 0.9;
}
```

- [ ] **Step 3: Wire DacEditor into BottomPanel**

In `src/components/BottomPanel.tsx`, add the import:

```tsx
import { DacEditor } from "./DacEditor";
```

Replace the DAC placeholder line:
```tsx
          {selectedInstrument?.type === "dac" && (
            <DacEditor instrumentId={selectedInstrument.id} />
          )}
```

- [ ] **Step 4: Verify**

Run: `cd /home/volence/sonic_hacks/megadaw && npx tsc --noEmit`
Expected: No errors

Test in dev server: Create project → import DAC WAV → select it → bottom panel shows waveform display, name field, source info, sample rate dropdown, preview button. Click Preview → hear DAC playback. Change sample rate → waveform refreshes.

- [ ] **Step 5: Commit**

```bash
cd /home/volence/sonic_hacks/megadaw
git add src/widgets/WaveformViewer.tsx src/components/DacEditor.tsx \
  src/components/DacEditor.module.css src/components/BottomPanel.tsx
git commit -m "feat(ui): DAC instrument editor with waveform viewer + preview"
```

---

## Self-Review

**Spec coverage:**
- Section 1 (Tech approach): ✅ CSS modules, dark theme, custom widgets, IPC-driven state
- Section 2 (App shell): ✅ Task 3-4 — TopBar, Sidebar, MainArea, BottomPanel
- Section 3 (Project flow): ✅ Task 5 — NewProjectDialog, open, save, Ctrl+S
- Section 4 (FM editor): ✅ Task 8-9 — AlgorithmDiagram, EnvelopeDisplay, Knob, PianoKeys, full FmEditor
- Section 5 (PSG editor): ✅ Task 10 — StepGraphEditor, PsgEditor with noise mode
- Section 6 (DAC editor): ✅ Task 11 — WaveformViewer, DacEditor with sample rate
- Section 7 (Custom widgets): ✅ Tasks 7-8, 10-11 — all 6 widgets created
- Section 8 (New IPC command): ✅ Task 1 — get_dac_pcm_data
- Section 9 (File structure): ✅ all files from spec created
- Section 10 (Color palette): ✅ Task 2 — tokens.css
- Section 11 (Exclusions): ✅ none of the deferred items are in the plan

**Placeholder scan:** No TBDs, TODOs, or "fill in later" found.

**Type consistency:**
- `FmInstrument`, `PsgInstrument`, `DacInstrument` used consistently across model.ts, ipc.ts, and all editors
- `SelectedInstrument` type used consistently in App.tsx → Sidebar → InstrumentBrowser → BottomPanel
- `isCarrier()` function defined in model.ts, used in FmEditor
- `CARRIER_MASKS` defined in model.ts, used in AlgorithmDiagram and model.ts
- All IPC function names match between ipc.ts and Rust commands
