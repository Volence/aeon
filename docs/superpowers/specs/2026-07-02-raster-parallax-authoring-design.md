# Raster Engine, Effect Sequencer & Parallax/Raster Authoring — design spec

**Date:** 2026-07-02
**Status:** Approved by user (design dialogue 2026-07-02)
**Extends:** the shipped §4.6 parallax engine (`engine/level/parallax.asm` — per-line
HScroll mandatory, per-cell rejected), the dormant HBlank dispatch
(`engine/system/hblank.asm` + the unshipped 2026-04-27 hblank-inline-jmp spec,
which this design lands), ARCH §7's raster wishlist (§7.2 "unified raster command
table" was aspiration-only vocabulary — this design builds it), the
Palette_Buffer/fade machinery (design #7's fade engine is a primitive here).
**Depends on:** design #7's fade engine + Palette_Buffer conventions (soft — the
sequencer's palette ops write through them); design #6/#7's Aurora document +
generator + MCP conventions; the damage spec's waterline seams (consumer).
**Design-week queue:** #8. Origin inspiration (user-stated): the Adventures of
Batman & Robin effects engine — studied via dedicated disassembly deep-dive.

---

## 1. Goal & user-ratified scope

Make raster effects and parallax **authorable data** instead of hand-written asm:
a data-driven HInt raster-script engine (the layer no reference game ever built),
a Batman-derived frame-level effect sequencer, parallax configs migrated to
Aurora-editable JSON, and an Aurora editor with **real-engine live preview over
Aether** (Aurora pushes edits into the running oracle emulator's RAM).

**V1 shipped effects (user decision):** water line, per-scanline palette
gradient, dynamic letterboxing, heat haze (haze already ships as a deform-table
parallax effect — its v1 work is Aurora authoring, not engine code).

**Architecture (user decision: approach B, three layers + live preview).**
Rejected: A (Ristar-style per-section hand-written HInt handlers — raster stays
unauthorable); C (dense demo-grade per-line polled engine + full TS scroll
simulator — gameplay needs none of it; the sparse op set reserves a dense-path
op for future set-pieces).

**Non-goals:** dense per-line effects (Overdrive-class — future op), sprite-table
mid-frame rewrites (DEFERRED_WORK multiplexing entry stands), shadow/highlight
*zone lighting* (S/H REG op exists; the lighting design is §7.3's own pass),
water *physics* (the damage spec's hooks + a future water spec own gameplay;
this design renders the line and owns `Water_Level` display state), TS scroll
simulation in Aurora (rejected for drift; the emulator is the preview),
vertical-border opening / interlace tricks.

## 2. Research grounding (checklist discharged)

All 8 disassemblies + online + modern, 6 subagents (incl. a dedicated Batman
deep-dive), 2026-07-02:

- **Batman & Robin (the origin inspiration) is TWO systems**, verified in the
  disassembly: (1) a 16-opcode byte-pair **coroutine interpreter**
  (`effects.asm:11230-11381`: dispatch on low nibble, high nibble = sub-mode;
  ops = reset / wait-N-frames-yield / relative branch / push+branch / pop /
  set-loop / dec-loop / **randomized branch via PRNG**; 8 palette-program ops;
  4-deep call stack at $FFF4FC) with a verified **zero-direct-VDP-writes**
  discipline — everything routes through queues/shadows. This is a *frame-level
  sequencer*, adopted as §5. (2) Its actual raster work: **hardcoded HInt state
  machines copied into RAM** ($FFFFE560 vector, `#$4EF9` inline-jmp patches,
  reg $00=$14 IE1 enabled, $0A=0 every line, disabled at screen bottom) — the
  "Batman uses no HBlank" note in our references is wrong. Batman never built a
  general raster table; §4 builds the layer it lacked. Also adopted: per-frame
  double-buffered VDP command words, budgeted work admission ($FF9916).
- **S3K water line** (read at `sonic3k.asm:944-1257`): five HInt variants —
  HInt2 full 64-color FIFO-throttled burst (32 unrolled `move.l`, dots pushed
  to left overscan); HInt3/4/5/6 paced 3-colors-per-HBlank with per-console
  delay constants (fragility to avoid — sync on the HB status flag instead) and
  a line-truncation guard against the known VInt-overrun bug. Water contract:
  `H_int_counter = Water_level − Camera_Y` clamped, `Water_full_screen_flag`
  selects the top-of-frame palette DMA, dynamic height eases Mean→Target.
- **S.C.E.**: band-record deform arrays consumed by shared `ApplyDeformation*`
  routines + zone descriptor of pointers — closest Sonic-side data-driven
  precedent (our §4.6 engine already exceeds it).
- **TF4**: 8-layer formula parallax + one shared wave table sampled at
  per-layer phase/depth (~1.5% frame); HInt RAM-pointer per level for splits
  only. **Ristar**: inline-jmp RAM vector (~12 cyc/fire saved), camera-tracked
  split line recomputed per frame, LUTs computed per frame not per line,
  cell-default/per-line-hero-shot policy. **Vectorman/Treasure**: RAM-patched
  HBlank universal (4/4 studios); sprite-driven otherwise.
- **Hardware numbers** (Kabuto/plutiedev/md.railgun/rasterscroll/SpritesMind):
  ~123 68k cycles true HBlank, interrupt entry eats ~⅓; 18 CPU slots/line H40
  (1 word CRAM/VSRAM each); FIFO 4 deep (burst-and-stall is exploitable);
  reg $0A fires at N+1 lines, reload lands only at expiry — **re-arm as the
  handler's first instruction** (S3K-proven; docs conflict → self-test, §4.6);
  ~6 VSRAM words/line practical ceiling (SpritesMind t=3201, real-HW verified);
  CRAM writes wholly inside HBlank produce no dot at all.
- **Per-line HScroll subsumes all horizontal effects** — shear, ripple, shake,
  haze are pure VBlank table data in the shipped parallax engine. HInt is only
  for CRAM/VSRAM/registers/display. This bounds the op set (§4.2).
- **No visual raster-authoring tool exists anywhere** (SGDK helpers are
  code/image-level). The Aurora half is novel. Aurora today: no parallax model,
  no oracle client (`busStore.ts:6` — "Oracle client lands in a later
  workstream"); the Aurora→Oracle bridge is the roadmap's named item, landed
  here minimally (§8). Oracle `write_memory` accepts 68k RAM only — hence the
  DEBUG override block (§8.2), since configs live in ROM and `Hscroll_Buffer`
  is rebuilt every frame.

## 3. Layer map (what owns what)

| Layer | Owns | Runs |
|---|---|---|
| §4.6 parallax engine (shipped, unchanged) | all per-line *horizontal* motion: bands, deform curves, haze/ripple/shake | main loop + VBlank DMA |
| §4 raster script engine (new) | mid-frame CRAM/VSRAM/register/display changes at scanlines | HInt |
| §5 effect sequencer (new) | *time*: palette programs, fades, envelopes, letterbox in/out, transitions | main loop, 1 tick/frame |

The sequencer writes state (palette buffers, water level, letterbox lines,
shake offset); the raster engine and parallax engine render state. No layer
writes another's outputs.

## 4. Raster script engine (engine)

### 4.1 Compiled script format
Sorted records, walked in order, one per HInt fire:
`{line_delta.b, op.b, args…}`, `$FF` delta terminates. Line 0's delta is armed
by the VBlank prologue each frame; the handler executes its record then
**re-arms reg $0A with the next record's delta as its first instruction**;
after the last record it disables HInt (reg $00 IE1 clear) — Batman's
bottom-of-screen discipline.

### 4.2 Op set (closed; each op declares slot cost for the build gate)
- `CRAM_BURST(addr, count, src)` — unrolled FIFO-throttled block (Hydrocity
  model; dots land in left overscan; masks `sr=$2700` for the burst).
- `CRAM_PACED(addr, count, src)` — 3 colors per HBlank, synced on the status
  HB flag (not cycle constants — avoids S3K's per-console HInt3/4 fork), with
  the truncation guard when the split is low on screen.
- `VSRAM_WRITE(offset, count≤6, src)` — per-2-cell-column vertical offsets.
- `REG_WRITE(reg, value)` — nametable base, S/H toggle, mode bits ($0B), etc.
- `DISPLAY(on/off)` — the blank escape hatch for bulk mid-frame work
  (S3K competition-mode pattern).
Dense per-line work is deliberately excluded; a future `DENSE_CALL` op may
address set-pieces without reshaping this format.

### 4.3 Dispatch
The 2026-04-27 inline-jmp spec lands here: IRQ4 vector → RAM 6-byte
`jmp imm.l` slot; `Raster_Install(a0=script)` patches the target long +
resets the walk state. Handler bodies live in ROM (Batman's copy-code-to-RAM
is explicitly avoided — swappable vector, ROM bodies). No handler touches the
VDP shadow or dirty masks (ARCH §0.4 rule); no DMA from HInt; Z80/Ptr-gate
rules untouched.

### 4.4 Camera-tracked lines
A record may carry `TRACK(track_id)` instead of a fixed line. The VBlank
prologue recomputes its delta from a **track table** (engine walks, game
populates): track 0 = water (`Water_Level − Camera_Y`, clamped to screen,
fullscreen flag semantics per S3K — flag decides which palette the top-of-frame
DMA uses, HInt swaps the other), further tracks = letterbox top/bottom, etc.
Water RAM contract (game-side values, engine-side easing):
`Water_Level`, `Mean_Water_Level`, `Target_Water_Level`, `Water_Speed`,
`Water_Fullscreen_Flag` — the damage spec's waterline seams now have their
renderer.

### 4.5 Attachment
`sec_raster_script ds.l 1` joins the `Sec` struct (0 = inherit act default,
`act_raster_script` fallback — mirrors `sec_parallax_config` resolution), and
screens/game states may install scripts directly (letterboxed title card).

### 4.6 Self-test
DEBUG boot runs a **two-split frame** self-test (like the compression golden):
arm a 2-record script, verify both fire lines via HV-counter capture, proving
the $0A in-handler re-arm semantics on oracle before the API promises chains.

## 5. Effect sequencer (engine)

The Batman interpreter, written fresh to our conventions:
- Byte-pair stream `{cmd, param}`; low nibble = opcode, high nibble = sub-mode.
- Ops 0–7: reset · wait-N-frames (yield; the saved PC **is** the state) ·
  relative branch · call (4-deep stack) · return · set-loop · dec-and-loop ·
  random branch (our RNG — organic variation, straight from Batman).
- Ops 8–F: palette programs — load/blend palette sets into `Palette_Buffer` /
  `Fade_Target` + dirty bits, start fades (design #7's fade engine is the
  primitive), set gradient animation phase, set letterbox target lines, set
  shake envelope values. **Only sinks: the engine's existing buffers** — the
  zero-direct-VDP-writes discipline holds by construction.
- One stream per controller slot (small fixed pool, e.g. 4); ticked once per
  frame from the main loop; game code starts/stops streams by id.
Uses: underwater entry/exit palette programs, sky gradient animation, screen
shake envelopes, letterbox in/out for #7's title card, section-transition
effects. Design #9 note: this sequencer is for *global/visual* effects;
object behaviors get their own sequencer in #9 — shared *idiom*, separate
machinery and streams (revisit merging only if #9's design finds the op sets
converge).

## 6. Data formats & generators

### 6.1 Documents (`games/sonic4/data/editor/`)
- `parallax/*.parallax.json` — bands (top cell, factor A/B as fraction strings
  the generator packs to shift-add encodings, validated against the
  representable set), vFactorBg/center/offset, transition, layer mask, deform
  curve refs. Curves inline: `{type:"sine", amplitude, period, phase}` or
  `{type:"points", data:[256]}`.
- `raster/*.raster.json` — script records (line: number or `{track:"water"}`,
  op, symbolic args — palette stops, register names), plus named sequencer
  programs authored as steps (wait/loop/call/palette-set/…).

### 6.2 Generators (`tools/parallax_gen.py`, `tools/raster_gen.py`)
Mirror `ojz_entity_gen.py`: validate → emit into `data/generated/` → nonzero
exit. Gates: sorted/duplicate lines, **per-record slot cost vs the op variant's
HBlank budget** (constants calibrated once on oracle, §10), representable
factor fractions, band ordering, dangling palette/track/program refs, curve
length. `parallax_gen.py` emits the *existing* `parallax_config`/`band_entry`
structs + deform tables — engine untouched. **Migration golden:** generated
output must byte-equal the current hand-asm configs (`ParallaxConfig_OJZ_*`,
effects variants in use) before the asm data files are retired; the engine
macro DSL (`engine/parallax_macros.inc`) remains for engine self-tests only.
Both wired into `build.sh`; pytest fixtures per gate.

## 7. Aurora parallax/raster mode

Fifth `AppMode` on the established pattern (#7 adds the fourth): band editor
(drag band boundaries over the real BG render, factor pickers limited to
representable fractions), curve editor (param sine / drawn 256-point, reusing
the sprite Timeline's rAF transport idiom), raster timeline (a 224-line strip
with split markers: water track, gradient stops, letterbox pair), sequencer
step editor. Viewport shows **static guides only** (band lines, curve
overlay) — no TS scroll simulation (drift rejected; the emulator is the
preview). Save writes the JSON documents via the atomic path. MCP/Aether tools
per the established conventions: `get_parallax`, `set_parallax_bands`,
`set_deform_curve`, `set_raster_splits`, `set_sequencer_program`,
`push_preview` — descriptors in `EDITOR_METHODS`, one undo step each.

## 8. Live preview over Aether

### 8.1 Aurora's first Aether client
Electron main connects to oracle's unix socket (`$XDG_RUNTIME_DIR/oracle.sock`,
NDJSON JSON-RPC, `initialize` handshake per `empyrean/contract/protocol.md`).
Surface used: `emulator/write_memory`, `emulator/read_memory`,
`emulator/screenshot`, `emulator/reload_rom` — nothing else (narrowest useful
bridge; debugger ops stay out). Connect/disconnect UI, push-on-change toggle,
"reset to ROM".

### 8.2 DEBUG RAM override block (engine)
DEBUG-only RAM: `Parallax_Override` (flag + full `parallax_config` + bands +
two 256-byte deform tables, ~1 KB) and `Raster_Override` (flag + script buffer
+ palette-stop buffer). Each frame, resolution checks the override flag before
the ROM pointer (parallax: in `Parallax_CheckBoundary`'s config resolution;
raster: in `Raster_Install`'s frame prologue). **Write protocol: payload first,
flag byte last** (Aurora writes the struct bytes then sets the flag; the engine
copies-then-uses, never reads a torn config). Aurora serializes with the same
packer logic as the generator (shared TS codec module, golden-tested against
`parallax_gen.py` output so the two can't drift). Result: slider drag → bytes
over Aether → the real engine renders the edit at 60 fps in oracle. Fallback
without oracle: save → build → `reload_rom` (works today, stays supported).

## 9. Engine/game tagging (design-#5 inputs)

**Engine:** raster script walker + trampoline + op handlers + track-table
walker + self-test, effect sequencer core, override-block checks (DEBUG),
`sec_raster_script` resolution. Zero game symbols (grep gate).
**Game:** all parallax/raster/sequencer documents + compiled data, track
population (water values), palette sets, per-act/section script wiring,
GS/screen script installs.

## 10. Testing

- **Build-time:** generator gates (fixture per gate) + the migration golden
  (byte-equal regeneration before asm retirement) + Aurora↔generator codec
  golden.
- **Calibration (one-time, foreground oracle):** measure actual writes-per-
  HBlank for each op variant on oracle; bake into the gate constants.
- **Runtime (foreground oracle):** two-split $0A self-test (DEBUG boot);
  water line **during motion** — camera crossing the line both directions,
  fullscreen enter/exit, the S3K overrun bug's regression case (line low on
  screen + camera moving down); gradient CRAM-dot audit via frame captures;
  letterbox animate in/out over gameplay; haze document authored in Aurora
  matches the retired hand-asm effect visually.
- **Preview soak:** rapid slider drags pushing overrides → no tearing, no
  crash, `Lag_Frame_Count` stable; kill oracle mid-session → Aurora degrades
  gracefully.

## 11. Sequencing & risks

**Plan order:** (1) trampoline + script walker + two-split self-test;
(2) water line end-to-end (track + palette double-buffer + fullscreen flag) —
the proving effect; (3) sequencer + letterbox + gradient; (4) generators +
parallax JSON migration (golden-gated asm retirement); (5) Aurora mode +
Aether client + override preview. Each stage independently mergeable.

**Risks:** $0A re-arm semantics vary in documentation — gated by the self-test
before any multi-split effect ships; slot-cost constants unverified until the
calibration pass (gates use conservative defaults first); the override block
is new DEBUG RAM (~1.3 KB — check DEBUG RAM headroom, pad even, runtime-boot
after ram.asm change); Aurora's Aether client is new attack surface in main —
loopback-only per the contract's trust model, and the socket path is
user-config; sequencer/raster interaction with design #7's screen player
(both install VInt/HInt state) — screens own their raster scripts explicitly,
no implicit inheritance from level state.
