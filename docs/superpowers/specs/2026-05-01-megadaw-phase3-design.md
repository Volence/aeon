# MegaDAW Phase 3: DAW Shell + Instrument Management

**Parent spec:** [2026-05-01-megadaw-design.md](2026-05-01-megadaw-design.md)
**Depends on:** Phase 2 (project model + backend, 27 IPC commands, 53 tests)

**Goal:** Build the full app shell (dark DAW theme) with project create/open/save flow, instrument browser, and complete FM/PSG/DAC instrument editors with visual tools and emulator preview. Deliverable: "I can create a project, build FM patches with visual envelope feedback, design PSG envelopes by drawing, import DAC samples with waveform preview, hear everything through the emulator, and save/reload my work."

**Phase 2 baseline:** Tauri v2 + React app at `/home/volence/sonic_hacks/megadaw/` with working audio engine (Nuked OPN2 + SN76489), ProjectManager, Flamedriver driver profile, DAC conversion pipeline, and 27 Tauri IPC commands. Frontend is a single TestPanel component with inline styles.

---

## Revised Roadmap

Phase 3 replaces the original phases 3-8 with a tighter UI-focused sequence:

| Phase | Focus | Deliverable |
|-------|-------|-------------|
| 3 (this) | DAW shell + instrument management | Patch design tool with emulator preview |
| 4 | Arrangement view + sequencer engine | Timeline with tracks, playback, transport controls |
| 5 | Piano roll + note editing | Composition workflow — draw/edit notes, velocity, quantize |
| 6 | Import/export + polish | SMPS import/export, undo/redo, keyboard shortcuts |

---

## 1. Tech Approach

- **Plain CSS modules** — no component library or utility CSS framework. DAW UI is 90% custom widgets (knobs, canvases, resizable panels) where libraries add friction.
- **Dark theme throughout** — `#1a1a1a` app background, `#2a2a2a` panel surfaces, `#3a3a3a` borders, `#e0e0e0` text, accent colors for channel types.
- **Custom widget library** — reusable Knob, EnvelopeDisplay, StepGraphEditor, WaveformViewer, and AlgorithmDiagram components built from scratch.
- **All state flows through Tauri IPC** — frontend does not maintain a separate copy of instrument data. Every edit calls the backend, every read queries the backend. The backend is the source of truth.

---

## 2. App Shell Layout

Fixed three-zone layout:

```
┌──────────────────────────────────────────────────┐
│  Top Bar (48px)                                   │
│  [Project Name] [Tempo] [TimeSig] [Driver Badge]  │
│  [File: New | Open | Save]                        │
├────────────┬─────────────────────────────────────┤
│            │                                     │
│  Sidebar   │         Main Area                   │
│  (240px,   │  (welcome screen or arrangement     │
│   two tabs)│   placeholder)                      │
│            │                                     │
│  Tracks    │                                     │
│  Instrmts  │                                     │
│            │                                     │
├────────────┴─────────────────────────────────────┤
│  Bottom Panel (~300px, collapsible)               │
│  [Instrument Editor — FM / PSG / DAC]             │
└──────────────────────────────────────────────────┘
```

### 2.1 Top Bar

- **Project name** — displays current project name, or "MegaDAW" when no project is open.
- **Tempo** — read-only display of BPM (editable in Phase 4 when transport exists).
- **Time signature** — read-only display (e.g., "4/4").
- **Driver badge** — small label showing active driver (e.g., "Flamedriver").
- **File actions** — New Project, Open Project, Save Project (Ctrl+S). These are buttons or a minimal menu bar.
- **Transport controls** — Play, Stop, Loop toggle. Present but disabled/grayed in Phase 3 (no sequencer). Visual placeholders so the top bar layout is stable for Phase 4.

### 2.2 Sidebar

Two tabs: **Tracks** and **Instruments**.

**Tracks tab:**
- Lists channels from the active driver profile (`get_driver_info` IPC).
- For Flamedriver: FM1, FM2, FM3, FM4, FM5, FM6/DAC, PSG1, PSG2, PSG3, PSG Noise, DAC.
- Each row shows channel name and type icon.
- Instrument assignment dropdown deferred to Phase 4.
- Solo/mute buttons deferred to Phase 4 (require sequencer playback).

**Instruments tab:**
- Three collapsible sections: FM, PSG, DAC.
- Each section shows a list of instruments by name.
- **"+" button** per section to add a new instrument.
  - FM/PSG: creates with defaults, opens editor immediately.
  - DAC: opens a file picker first (WAV or raw PCM via Tauri's native dialog), then creates and opens editor.
- **Click** an instrument → opens its editor in the bottom panel.
- **Right-click context menu**: Rename, Duplicate, Delete.
- Instruments populated from `list_fm_instruments`, `list_psg_instruments`, `list_dac_instruments` IPC calls.

### 2.3 Main Area

- **No project open:** Welcome screen with "New Project" and "Open Project" buttons, MegaDAW logo/title.
- **Project open:** Placeholder message — "Arrangement View (Phase 4)" with a brief description. This area will house the timeline in the next phase.

### 2.4 Bottom Panel

- Collapsible (click to expand/collapse, or drag the top edge to resize).
- Hosts the active instrument editor (FM, PSG, or DAC).
- Empty state: "Select an instrument to edit."
- Responds to instrument selection in the sidebar.

---

## 3. Project Flow

### 3.1 App States

Three mutually exclusive states:

1. **No project** — Welcome screen visible. Sidebar empty. Bottom panel hidden.
2. **New Project dialog** — Modal overlay.
3. **Project open** — Full shell with populated sidebar and active editing.

### 3.2 New Project Dialog

Modal with fields:
- **Name** — text input (required).
- **Location** — folder path with "Browse" button (Tauri `dialog.open` with `directory: true`).
- **Driver** — dropdown populated from `list_drivers` IPC. Default: first available.
- **Tempo** — number input, default 120, range 20-300.
- **Time signature** — two inputs: numerator (1-12, default 4), denominator (dropdown: 2, 4, 8, 16; default 4).
- **Create** button — calls `create_project` IPC with all fields. On success, transitions to project-open state and refreshes all panels.
- **Cancel** button — returns to previous state.

### 3.3 Open Project

- Triggers Tauri `dialog.open` with `directory: true`.
- Calls `open_project` IPC with selected path.
- On success: populates top bar, sidebar, enables bottom panel.
- On error: shows error message (e.g., "not a MegaDAW project").

### 3.4 Save

- Ctrl+S keyboard shortcut.
- Calls `save_project` IPC.
- Visual feedback: brief "Saved" indicator in the top bar (fades after 2 seconds).

### 3.5 Close / Switch Project

- Opening a new project or creating one implicitly closes the current one (calls `close_project` first).
- If there are unsaved changes, prompt "Save before closing?" — but dirty tracking is deferred. Phase 3 always saves on close without prompting. Dirty tracking is a Phase 6 polish item.

---

## 4. FM Instrument Editor

The most complex editor. Opens in the bottom panel.

### 4.1 Layout

```
┌──────────┬───────┬───────┬───────┬───────┬──────────┐
│ Algorithm │ Op 1  │ Op 2  │ Op 3  │ Op 4  │ Preview  │
│ + FB knob │       │       │       │       │ keyboard │
│ [diagram] │[envlp]│[envlp]│[envlp]│[envlp]│          │
│           │[knobs]│[knobs]│[knobs]│[knobs]│          │
└──────────┴───────┴───────┴───────┴───────┴──────────┘
```

### 4.2 Algorithm Selector + Diagram

- 8 selectable algorithms (0-7).
- Each displayed as a **topology diagram**: four boxes (Op1-4) with arrows/lines showing the routing. Carrier operators highlighted (e.g., with a different border color). Active algorithm highlighted.
- Click to select. Updates `algorithm` field, calls `update_fm_instrument`.
- The CARRIER_MASKS from the Flamedriver backend determine which operators are carriers per algorithm — the frontend uses the same table for visual highlighting.

### 4.3 Feedback Knob

- Single rotary knob, range 0-7.
- Positioned next to the algorithm diagram.

### 4.4 Operator Panels (×4)

Each operator panel contains:

**Envelope display** (top, ~200×80px canvas):
- Draws the ADSR shape based on current AR, D1R, D2R, SL, RR values.
- Approximation — not cycle-accurate YM2612 EG simulation, but visually representative of the envelope contour.
- Attack: steep/shallow slope from 0 to max based on AR (31=instant, 0=never).
- Decay 1: slope from max to sustain level based on D1R.
- Sustain: flat line at SL height (SL 0 = highest sustain, SL 15 = lowest).
- Decay 2: gradual slope during sustain based on D2R (0 = flat).
- Release: slope to zero based on RR.
- Updates live as knobs are dragged.

**Knobs:**
- Detune (0-7)
- Multiple (0-15)
- Total Level (0-127) — vertical slider instead of knob, since this is the primary "volume" control and benefits from higher precision.
- Rate Scale (0-3)
- Attack Rate (0-31)
- Decay 1 Rate (0-31)
- Decay 2 Rate (0-31)
- Sustain Level (0-15)
- Release Rate (0-15)

**AM toggle:** Checkbox.

**Visual label** — "Op 1", "Op 2", "Op 3", "Op 4" at the top. Carrier operators get a distinct label color matching the algorithm diagram.

### 4.5 Preview Keyboard

- Single octave of piano keys (C4-B4), rendered as clickable rectangles.
- Click a key → calls `preview_fm_instrument` with the instrument ID and corresponding MIDI note (60-71).
- Shift+click for octave up (72-83), Ctrl+click for octave down (48-59). Or simple octave +/- buttons.
- Visual feedback: key lights up briefly on click.

### 4.6 Edit Flow

Every parameter change:
1. Updates local component state (for immediate visual feedback).
2. Calls `update_fm_instrument` IPC with the full instrument struct.
3. On IPC error, reverts local state and shows error.

No debouncing — the IPC is cheap (Mutex lock + struct copy) and we want perfect sync.

---

## 5. PSG Instrument Editor

Opens in the bottom panel when a PSG instrument is selected.

### 5.1 Layout

```
┌─────────────────────────────────┬───────────┐
│  Volume Envelope Step Graph     │  Settings │
│  (drawable canvas)              │           │
│  ████▇▆▅▄▃▂▁                   │  Noise    │
│       ▲ loop marker             │  Loop pt  │
│                                 │  Preview  │
└─────────────────────────────────┴───────────┘
```

### 5.2 Volume Envelope Step Graph

- Canvas-rendered bar graph. X-axis = tick index, Y-axis = volume (0-15, 16 discrete levels).
- Each tick is a vertical bar. Bar height represents volume.
- **Click** a bar to set its height to the clicked Y position.
- **Click-drag** across bars to "paint" values (continuous drawing).
- **Add tick** button: appends a tick at the end (default volume 0).
- **Remove tick** button: removes last tick (minimum 1 tick).
- Bar width scales to fit the canvas, with a minimum width. Horizontal scroll if the envelope is very long.

### 5.3 Loop Point

- Displayed as a colored marker (triangle/flag) on the step graph at the loop position.
- **Drag** the marker to reposition.
- **Toggle** button in settings: "Loop: On/Off". When off, `loop_point` is None and the marker is hidden.
- When on, playback wraps from the end back to the loop point.

### 5.4 Noise Mode

- Three-state toggle: **Off** (normal tone), **Periodic**, **White**.
- When Periodic or White is selected, a period input appears (0-1023, or a dropdown of common values).

### 5.5 Preview

- Single "Preview" button.
- Calls `preview_psg_instrument` with a middle-range MIDI note (60 = C4).
- Optional: a small note selector (dropdown or +/- buttons) to change the preview pitch.

### 5.6 Edit Flow

Same pattern as FM: local state update → `update_psg_instrument` IPC → revert on error.

---

## 6. DAC Instrument Editor

Opens in the bottom panel when a DAC instrument is selected.

### 6.1 Layout

```
┌──────────────────────────────────────┬────────────┐
│  Waveform Display (read-only)        │  Settings  │
│  ∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿     │            │
│                                      │  Name      │
│                                      │  Source    │
│                                      │  Rate      │
│                                      │  Preview ▶ │
└──────────────────────────────────────┴────────────┘
```

### 6.2 Waveform Display

- Canvas rendering of PCM data as a waveform line.
- Unsigned 8-bit data (0-255), centered at 128. Drawn as a continuous line, amplitude mapped to canvas height.
- Read-only in Phase 3 (no trim/loop editing — deferred to Phase 6).
- Requires PCM data on the frontend. **New IPC command needed:** `get_dac_pcm_data(id: String) -> Vec<u8>` that returns the raw PCM bytes for the given instrument. Returns the cached data from `dac_pcm_cache`.

### 6.3 Settings Panel

- **Name** — editable text field. On blur, calls `update_dac_instrument`.
- **Source** — read-only label: "WAV" or "Raw PCM", plus original filename.
- **Sample rate** — dropdown: 8000, 11025, 16000, 22050, 32000. Changing calls `reconvert_dac` and refreshes the waveform display. Disabled when `source_is_raw` is true (no original WAV to reconvert from).
- **Preview** — button, calls `preview_dac`.

---

## 7. Custom Widget Components

Reusable across the app, built once:

### 7.1 Knob

- Circular rotary control.
- Interaction: **vertical drag** — drag up to increase, drag down to decrease. Standard DAW convention.
- Props: `min`, `max`, `value`, `onChange`, `label`, `size`.
- Visual: filled arc showing current value, label below, numeric value display.
- Double-click to type a specific value.

### 7.2 EnvelopeDisplay

- Canvas component that draws an ADSR-style envelope curve.
- Props: `attackRate`, `d1r`, `d2r`, `sustainLevel`, `releaseRate`, `width`, `height`.
- Pure visualization — read-only, no interaction.
- Renders the approximated envelope shape with labeled segments.

### 7.3 StepGraphEditor

- Canvas component for editing PSG volume envelopes.
- Props: `values: number[]`, `max: number`, `onChange`, `loopPoint`, `onLoopChange`.
- Interactive: click/drag to set bar heights, draggable loop marker.

### 7.4 WaveformViewer

- Canvas component for rendering PCM waveform data.
- Props: `data: Uint8Array`, `width`, `height`.
- Read-only visualization. Center line at 128. Downsamples long waveforms to fit canvas width.

### 7.5 AlgorithmDiagram

- SVG or canvas component showing YM2612 operator routing.
- Props: `algorithm: number`, `onSelect: (algo: number) => void`.
- Renders 8 diagrams, active one highlighted. Carrier operators visually distinct.

---

## 8. New IPC Command

One new backend command required:

```rust
#[tauri::command]
pub fn get_dac_pcm_data(
    state: State<'_, ProjectState>,
    id: String,
) -> Result<Vec<u8>, String>
```

Returns the raw PCM bytes for a DAC instrument from the in-memory cache. Needed for the frontend waveform display.

---

## 9. File Structure (Frontend)

```
src/
├── App.tsx                    # Root — app state machine (no project / dialog / project open)
├── App.module.css             # Root layout styles
├── main.tsx                   # Entry point (unchanged)
├── api/
│   └── ipc.ts                 # Typed wrappers around all Tauri invoke() calls
├── components/
│   ├── TopBar.tsx             # Project info, file actions, transport placeholder
│   ├── TopBar.module.css
│   ├── Sidebar.tsx            # Tabs: Tracks, Instruments
│   ├── Sidebar.module.css
│   ├── MainArea.tsx           # Welcome screen or arrangement placeholder
│   ├── MainArea.module.css
│   ├── BottomPanel.tsx        # Collapsible editor host
│   ├── BottomPanel.module.css
│   ├── NewProjectDialog.tsx   # Modal for project creation
│   ├── NewProjectDialog.module.css
│   ├── InstrumentBrowser.tsx  # FM/PSG/DAC lists with add/delete
│   ├── InstrumentBrowser.module.css
│   ├── FmEditor.tsx           # FM instrument editor
│   ├── FmEditor.module.css
│   ├── PsgEditor.tsx          # PSG instrument editor
│   ├── PsgEditor.module.css
│   ├── DacEditor.tsx          # DAC instrument editor
│   ├── DacEditor.module.css
│   └── TrackList.tsx          # Channel list from driver profile
│   └── TrackList.module.css
├── widgets/
│   ├── Knob.tsx               # Rotary knob control
│   ├── Knob.module.css
│   ├── EnvelopeDisplay.tsx    # FM ADSR envelope visualization
│   ├── StepGraphEditor.tsx    # PSG volume envelope editor
│   ├── StepGraphEditor.module.css
│   ├── WaveformViewer.tsx     # DAC waveform display
│   ├── AlgorithmDiagram.tsx   # FM algorithm topology selector
│   ├── AlgorithmDiagram.module.css
│   └── PianoKeys.tsx          # Clickable single-octave keyboard
│   └── PianoKeys.module.css
├── types/
│   └── model.ts               # TypeScript types mirroring Rust model structs
└── theme/
    └── tokens.css             # CSS custom properties for colors, spacing, typography
```

---

## 10. Color Palette

CSS custom properties in `tokens.css`:

```css
:root {
  --bg-app: #1a1a1a;
  --bg-panel: #2a2a2a;
  --bg-surface: #333333;
  --border: #3a3a3a;
  --text-primary: #e0e0e0;
  --text-secondary: #888888;
  --accent-fm: #4a9eff;       /* blue for FM */
  --accent-psg: #44cc66;      /* green for PSG */
  --accent-dac: #ff8844;      /* orange for DAC */
  --accent-active: #ffffff;
  --knob-track: #444444;
  --knob-fill: #4a9eff;
  --envelope-line: #66ccff;
  --envelope-fill: rgba(102, 204, 255, 0.15);
  --carrier-highlight: #ffcc44;
  --error: #cc4444;
  --success: #44cc66;
}
```

---

## 11. What Phase 3 Does NOT Include

Deferred explicitly to keep scope tight:

- **Arrangement view / timeline** — Phase 4
- **Sequencer engine / playback** — Phase 4
- **Transport controls (functional)** — Phase 4
- **Track solo/mute** — Phase 4
- **Track-to-instrument assignment** — Phase 4
- **Piano roll / note editing** — Phase 5
- **SMPS import/export** — Phase 6
- **Undo/redo** — Phase 6
- **Keyboard shortcuts (beyond Ctrl+S)** — Phase 6
- **DAC trim/loop editing** — Phase 6
- **Dirty state tracking / save prompts** — Phase 6
- **FM envelope cycle-accurate rendering** — Phase 6 (approximation is sufficient)
- **FM instrument import (TFI/DMP/VGI formats)** — Phase 6
- **Global preset library (~/.megadaw/)** — Phase 6
