# Input Layer + Demo Record/Replay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Full 6-button input layer + a tick-seam demo record/replay harness with an
embedded determinism checkpoint net, per the approved spec
`docs/superpowers/specs/2026-08-02-input-replay-design.md`.

**Architecture:** Three code parcels (I1 input layer, I2 Logic_Tick, I3 replay
module + packer tool) executed by Opus porters in isolated worktrees, each gated
x6 + strict + repin + refreeze by the overseer; then I4, the overseer's foreground
oracle harness session (record the OJZ fixture, prove determinism, prove the net
bites). Sequential merges I1 → I2 → I3 → I4.

**Tech Stack:** `.emp` (sigil sole toolchain, `SIGIL_BUILD`/`SIGIL_EMIT` env),
oracle MCP (overseer only), python3 packer in `tools/`.

**Standing gate procedure per byte-changing parcel** (identical to the
engine-debts opener, chain currently 24): porter builds all four shapes
delete-first (`./build.sh`, `DEBUG=1 ./build.sh`, `./build.sh demo`,
`DEBUG=1 ./build.sh demo`), sigil-side repin in a sigil worktree (`cargo run -p
sigil-harness --bin repin` + fixture updates, pin-sourced per the t24 lesson,
`--no-fail-fast` for the full red set), every changed value traced to the parcel
or STOP; overseer countersigns, oracle-gates, refreezes (`refreeze --freeze
<name> --ab <evidence>`), merges, re-runs strict to 2990+/0/4 (count grows if new
tests land). Porters never merge/refreeze/run emulators/touch shared checkouts.

---

## Parcel I1 — 6-button input layer

**Branch:** `input-6button` (both repos)

**Files:**
- Modify: `engine/system/controllers.emp` (full rewrite, ~68 → ~170 lines)
- Modify: `engine/ram.emp` (controller block, after line 127 `Ctrl_2_Press_Accum`)
- Modify: `engine/system/constants.emp` (PAD_*/BUTTON_EXT_* consts, near the
  BUTTON_* block at lines 22-34)
- Modify: `engine/system/vblank.emp` (extend the tick latch at lines 167-170)
- Reference (read, don't edit): Vectorman's proven 6-button burst at
  `/home/volence/sonic_hacks/The Adventures of Batman and Robin/vectorman_disasm/code/disasm.asm:7911-7975`
  and SGDK's detect signatures (research notes in the spec §1)

### Task I1.1: RAM + constants

- [ ] **Step 1:** In `engine/ram.emp`, append to the controller block directly
  after `Ctrl_2_Press_Accum` (line 127):

```
    // 6-button extension (2026-08-02 input parcel): MXYZ nibble per pad
    // (0 on a 3-button pad) + per-frame-refreshed pad type. Same
    // accumulate/latch discipline as the main bytes.
    Ctrl_1_Ext_Held:        u8,         // 0000MXYZ
    Ctrl_1_Ext_Press:       u8,         // tick-stable (latched like Ctrl_1_Press)
    Ctrl_2_Ext_Held:        u8,
    Ctrl_2_Ext_Press:       u8,
    Ctrl_1_Ext_Press_Accum: u8,
    Ctrl_2_Ext_Press_Accum: u8,
    Pad_1_Type:             u8,         // PAD_3BTN / PAD_6BTN (re-detected EVERY frame)
    Pad_2_Type:             u8,
```

  (8 bytes — even parity preserved; everything after shifts +8 → routine repin.)

- [ ] **Step 2:** In `engine/system/constants.emp`, after the `BUTTON_*_BIT`
  block (line 34):

```
// 6-button pad: extra-button masks (the Ext bytes' low nibble) + pad types.
pub const BUTTON_EXT_Z    = 1 << 0
pub const BUTTON_EXT_Y    = 1 << 1
pub const BUTTON_EXT_X    = 1 << 2
pub const BUTTON_EXT_MODE = 1 << 3
pub const PAD_3BTN = 0
pub const PAD_6BTN = 1
```

- [ ] **Step 3:** Commit (exact paths: the two files).

### Task I1.2: The burst rewrite

- [ ] **Step 1:** Rewrite `Read_Controllers` in `engine/system/controllers.emp`.
  Contract and structure (the porter writes the final `.emp`, matching house
  style — explicit branch sizes, comment discipline):

```
// Read_Controllers — full 6-button burst, both pads, once per VBlank.
// The WHOLE two-port burst runs under ONE stop_z80()/start_z80() bracket:
// Z80 access to the 68k bus during $A100xx I/O reads corrupts them (hardware
// bug — SGDK HALT_Z80_ON_IO / Vectorman's bus-request lock). See Step 2 for
// the sound-OFF-build nesting rule.
// Out: Ctrl_x_Held / Ctrl_x_Press_Accum, Ctrl_x_Ext_Held / Ctrl_x_Ext_Press_Accum,
//      Pad_x_Type — all updated. Clobbers: d0-d4, a0.
pub proc Read_Controllers () clobbers(d0-d4/a0) {
        stop_z80()                          // see Step 2: gated vs the OFF-build fence
        lea     HW_PORT_1_DATA, a0
        jbsr    .read_pad_6                 // d0=SACBRLDU d1=0000MXYZ d2=type
        // (per-pad merge: held/edge-accum for main + ext, store type — the
        //  existing eor/and edge idiom, applied twice)
        ...same for HW_PORT_2_DATA...
        start_z80()
        rts

    // .read_pad_6 — one full burst. Sequence = Vectorman disasm.asm:7911
    // (7 alternating writes starting $40, read after each, 2-nop settle):
    //   w$40 r1: TH=1  1CBRLDU      (main high)
    //   w$00 r2: TH=0  0SA00DU      (main low: Start/A)
    //   w$40 r3: TH=1  1CBRLDU      (repeat)
    //   w$00 r4: TH=0  0SA0000      <- 6-button SIGNATURE #1: D-pad nibble all-zero
    //   w$40 r5: TH=1  1CB MXYZ     <- extra buttons
    //   w$00 r6: TH=0  0SA1x1x      <- SIGNATURE #2: bits 3-2 forced %11 (SGDK cross-check)
    //   w$40      restore idle high
    // Detect = BOTH signatures (r4 nibble==0 AND r6 bits3-2==%11) -> PAD_6BTN,
    // ext = ~r5 & $0F. Either signature absent -> PAD_3BTN, ext = 0 (r1/r2
    // already carry the full 3-button state; a 3-button pad repeats them on
    // every cycle, so the burst is harmless). SOCD guard (existing L+R/U+D
    // cancel) applied to the fused main byte, unchanged.
```

  Fuse exactly as today: `d0 = ~((r2 & $30) << 2 | (r1 & $3F))` = `SACBRLDU`,
  1 = pressed; ext = `~r5 & $0F` = `0000MXYZ`, 1 = pressed. Per-pad merge (the
  existing edge idiom, now ×2 per pad):

```
        move.b  Ctrl_1_Held, d3
        move.b  d0, Ctrl_1_Held
        eor.b   d0, d3
        and.b   d0, d3
        or.b    d3, Ctrl_1_Press_Accum
        move.b  Ctrl_1_Ext_Held, d3
        move.b  d1, Ctrl_1_Ext_Held
        eor.b   d1, d3
        and.b   d1, d3
        or.b    d3, Ctrl_1_Ext_Press_Accum
        move.b  d2, Pad_1_Type
```

- [ ] **Step 2: The Z80-bracket nesting rule (trace before coding).** In the
  sound-OFF build, `VInt_Level` holds the Z80 across the whole VDP window
  (vblank.emp:87 `stop_z80()`) — trace where that fence RELEASES relative to the
  `Read_Controllers` call site (vblank.emp:161). If the Z80 is still held there,
  an inner `start_z80()` would release it early — WRONG. Rule: bracket the burst
  with `if SOUND_DRIVER_ENABLED == 1 { stop_z80() } ... if SOUND_DRIVER_ENABLED == 1 { start_z80() }`
  ONLY if the OFF-build fence provably covers the call site; otherwise bracket
  unconditionally. State the traced answer in a comment at the bracket.

- [ ] **Step 3:** Extend the VInt tick latch (vblank.emp:167-170) with the two
  ext latches, same mem-to-mem pattern:

```
        move.b  (Ctrl_1_Ext_Press_Accum).w, (Ctrl_1_Ext_Press).w
        clr.b   Ctrl_1_Ext_Press_Accum
        move.b  (Ctrl_2_Ext_Press_Accum).w, (Ctrl_2_Ext_Press).w
        clr.b   Ctrl_2_Ext_Press_Accum
```

- [ ] **Step 4:** Build all four shapes (delete-first). The checked-clobbers lint
  must accept the widened `clobbers(d0-d4/a0)` — `Read_Controllers`' only caller
  is VInt (verify its declaration covers d0-d4/a0; widen the caller's declaration
  if needed, with the honest-contract comment).
- [ ] **Step 5:** Commit (exact paths).

### Task I1.3: Sigil-side repin (standard)

- [ ] pins.rs regen (`repin` bin, AEON_DIR = your worktree); expect
  `READ_CONTROLLERS`/`CONTROLLERS` region len growth + downstream ROM shifts +
  RAM +8 shifts for everything after the controller block. Update
  live-ROM-comparing fixtures (parallax/g4 RAM VMAs) per the parcel-3 precedent
  (pin-source; check `boot_data_port`, `native_full_rom`, `native_offcanonical_full`,
  `seam1::blob_lma` are all pin-sourced now — they are, post-237c1afb, so they
  should ride automatically). `--no-fail-fast`; report the full red set with the
  refreeze-territory classification.
- [ ] Commit on sigil branch naming the aeon pairing.

### Overseer gate I1 (FOREGROUND — not the porter)

- [ ] Own-run rebuild + strict; oracle A/B: 3-button behavior identical
  (OJZ run: hold-right scroll + jump/spindash presses register exactly as
  pre-parcel; `Pad_1_Type` reads PAD_3BTN or PAD_6BTN per what oracle's pad model
  answers to the burst — record which, and if oracle lacks 6-button emulation,
  note the 6-button data path as review-gated pending oracle support).
  Refreeze chain 24 → 25 (`input-6button`), merge, push, docs.

---

## Parcel I2 — Logic_Tick + bg_anim audit fix

**Branch:** `logic-tick` (both repos)

**Files:**
- Modify: `engine/ram.emp` (after `Frame_Counter`, line 98)
- Modify: `engine/system/game_loop.emp:25-39` (`GameLoop`)
- Modify: `engine/level/bg_anim.emp:113-119` (driver 2) + header comment lines
  25/46

### Task I2.1

- [ ] **Step 1:** ram.emp, directly after `Frame_Counter: u16,`:

```
    Logic_Tick:             u32,        // logic-TICK counter (game loop, post-VSync) —
                                        // lag-immune, unlike Frame_Counter (VBlank count).
                                        // The replay/determinism timebase (spec 2026-08-02).
```

- [ ] **Step 2:** `GameLoop` (game_loop.emp), first thing after `jbsr VSync_Wait`:

```
        addq.l  #1, Logic_Tick          // the deterministic timebase (one per tick, never per VBlank)
```

- [ ] **Step 3:** bg_anim.emp driver 2 (line 117): replace
  `move.w Frame_Counter, d0` with `move.w Logic_Tick+2, d0` (low word) and update
  the two doc-comment mentions (lines 25/46) from `Frame_Counter` to `Logic_Tick`
  — plus the audit rationale: "lag-immune so BG anim phase can't diverge between
  record and playback".
- [ ] **Step 4:** Build x4 delete-first; commit exact paths.

### Task I2.2 + gate

- [ ] Sigil repin (RAM +4 after Frame_Counter; ROM near-neutral — bg_anim operand
  + game_loop +8ish). Overseer: oracle A/B (BG anim visually unchanged in a
  no-lag scroll run — bg anim advances 1/tick as before), refreeze 25 → 26
  (`logic-tick`), merge, push.

---

## Parcel I3 — Replay module + packer

**Branch:** `replay-harness` (both repos)

**Files:**
- Create: `engine/system/replay.emp`
- Modify: `engine/ram.emp` (replay block — live cells near controllers; the 8 KB
  DEBUG record ring + 2 KB checkpoint log in upper RAM via `if DEBUG == 1`
  comptime fields, following ram.emp's existing comptime-if precedent)
- Modify: `engine/system/game_loop.emp` (the seam call)
- Modify: `engine/system/constants.emp` (INPUT_* consts + format consts)
- Modify: `games/sonic4/map.toml` + `games/demo/map.toml` (order-list entries for
  the new module's head label, placed right after `GameLoop`; fixture data label
  sonic4-only — added in I4 when the fixture exists)
- Create: `tools/replay_pack.py`
- Test: packer `--selftest` (round-trip + reject-invalid), DEBUG in-ROM asserts

### Task I3.1: Constants + RAM

- [ ] **Step 1:** constants.emp:

```
// Replay/input-source (engine/system/replay.emp — spec 2026-08-02)
pub const INPUT_LIVE     = 0
pub const INPUT_PLAYBACK = 1
pub const INPUT_RECORD   = 2            // DEBUG builds only
pub const REPLAY_ESCAPE     = $FF       // impossible as a held byte (SOCD guard)
pub const REPLAY_OP_END     = $00
pub const REPLAY_OP_CHECK   = $01       // + u32 hash payload
pub const REPLAY_CHECK_MASK = 63        // checkpoint every 64 ticks (record side)
pub const REPLAY_RECORD_TICKS = 8192    // 8 KB ring (DEBUG)
pub const REPLAY_HEADER_LEN = 20        // magic4+flags1+pad1+ticks4+corehash4+seed4+reserved2
```

- [ ] **Step 2:** ram.emp — live cells (place after the controller block's new
  ext cells so the two input blocks read as one region):

```
    // --- Replay (engine/system/replay.emp) ---
    Input_Source:           u8,         // INPUT_LIVE/PLAYBACK/RECORD
    Replay_Exit_Request:    u8,         // live Start pressed during playback (game polls; never merged into Ctrl)
    Replay_Done:            u8,         // stream ended (playback) or ring full (record)
    Replay_Hold:            u8,         // remaining ticks of current RLE entry
    Replay_Prev:            u8,         // previous tick's stream byte (press derivation)
    pad(1),
    Replay_Ptr:             u32,        // current stream position (ROM)
```

  DEBUG-only (comptime-if block, upper-RAM home the porter picks with the
  alignment rules — 8 KB + 2 KB + cursors):

```
    if DEBUG == 1 {
    Replay_Record_Idx:      u16,        // ticks recorded (byte index into the ring)
    Replay_Check_Idx:       u16,        // checkpoint entries written
    Replay_Record_Buf:      [u8; REPLAY_RECORD_TICKS],
    Replay_Check_Log:       [u8; 256 * 8],   // (Logic_Tick u32, hash u32) pairs
    }
```

- [ ] **Step 3:** Build x4 (RAM-only change compiles); commit.

### Task I3.2: `engine/system/replay.emp`

- [ ] **Step 1:** Create the module. Full required behavior (porter writes house-
  style `.emp`; this is the contract, with the tricky cores spelled out):

```
// Input_Tick — the ONE replay seam. Called from GameLoop after VSync_Wait
// (inputs latched by VInt) and before the state dispatch. LIVE: no-op.
// PLAYBACK: overwrite Ctrl_1_Held/Ctrl_1_Press from the stream (presses derive
// from the STREAM's previous byte — never the live pad: the S1 REV00 input-
// bleed desync class, killed structurally). RECORD (DEBUG): tap the latched
// Ctrl_1_Held into the ring + emit periodic checkpoints.
pub proc Input_Tick () clobbers(d0-d3/a0-a1) {
        move.b  Input_Source, d0
        beq     .live                       // INPUT_LIVE -> rts
        cmpi.b  #INPUT_PLAYBACK, d0
        beq     .playback
        if DEBUG == 1 { jbra .record }      // INPUT_RECORD only exists in DEBUG
    .live:
        rts

    .playback:
        // Live Start -> exit-request FLAG (before the overwrite clobbers it)
        btst    #7, Ctrl_1_Press            // BUTTON_START bit
        beq     .no_exit
        st      Replay_Exit_Request
    .no_exit:
        tst.b   Replay_Hold
        bne     .hold                       // still inside the current RLE run
    .fetch:
        movea.l Replay_Ptr, a0
        move.b  (a0)+, d0
        cmpi.b  #REPLAY_ESCAPE, d0
        bne     .pair
        move.b  (a0)+, d1                   // escape opcode
        beq     .end                        // REPLAY_OP_END
        cmpi.b  #REPLAY_OP_CHECK, d1
        bne     .bad_stream                 // unknown opcode: DEBUG assert / release = end
        // checkpoint: payload u32 expected hash
        if DEBUG == 1 {
            move.l  (a0)+, d2
            move.l  a0, Replay_Ptr          // save BEFORE the hash call (clobbers)
            jbsr    Replay_Hash             // d0.l = curated-block hash
            cmp.l   d0, d2
            beq     .fetch_resume           // match -> continue fetching the real entry
            // DESYNC: trap with tick + expected/actual in registers
            move.l  Logic_Tick, d1
            raise_exception                 // (house idiom — the error handler shows regs)
        }
        if DEBUG == 0 { addq.l #4, a0 }     // release: step over the payload
        ...continue fetch loop...
    .pair:
        move.b  (a0)+, Replay_Hold          // hold-1 (0 = this tick only)
        move.l  a0, Replay_Ptr
        jbra    .apply                      // d0 = new held byte
    .hold:
        subq.b  #1, Replay_Hold
        move.b  Replay_Prev, d0             // same byte as last tick
    .apply:
        // press = new & (new ^ prev_stream)  — STREAM history, not live pad
        move.b  Replay_Prev, d1
        move.b  d0, Replay_Prev
        eor.b   d0, d1
        and.b   d0, d1
        move.b  d0, Ctrl_1_Held
        move.b  d1, Ctrl_1_Press
        rts
    .end:
        st      Replay_Done
        clr.b   Input_Source                // revert to live
        rts
}
```

  NOTE for the porter on `.hold` vs `.fetch` ordering: `Replay_Hold` stores
  `hold_minus_1`; a fresh pair applies its byte THIS tick with `Replay_Hold =
  hold_minus_1` remaining; the run ends when it hits 0 — verify the count with
  the packer's self-test vectors (Task I3.3 encodes the same convention).

```
// Replay_Hash — the curated-block checksum (DEBUG net + recorder).
// Longword sum + rol #1 over a const (addr, len_longs) table:
//   Logic_Tick (1 long) · Player_1 SST (20 longs) · Camera_X/Y (2) ·
//   Dynamic_Live_Count+Dynamic_Free_SP+Effect_Free_SP (packed reads, word-safe) ·
//   Slot_Section_Map (2) · Section_Stream_State region (len from ram.emp).
// Excludes: sound RAM, Ctrl_* cells, VDP staging, DEBUG-only cells — gameplay
// state only (hash identical across build shapes).
// Out: d0.l  Clobbers: d0-d2/a0-a1
```

```
// .record (DEBUG only, inside Input_Tick):
//   ring[Replay_Record_Idx++] = Ctrl_1_Held
//   if (Replay_Record_Idx & REPLAY_CHECK_MASK) == 0:
//       Check_Log[Replay_Check_Idx++] = { Logic_Tick, Replay_Hash() }  (8 B)
//   if Replay_Record_Idx == REPLAY_RECORD_TICKS: st Replay_Done; clr Input_Source
```

- [ ] **Step 2:** The seam in `GameLoop` (game_loop.emp), directly after the
  `addq.l #1, Logic_Tick` from I2:

```
        jbsr    Input_Tick              // replay seam: live no-op / playback overwrite / record tap
```

  (Widen `GameLoop`'s nominal clobbers comment if the lint asks; it already
  declares d0-d7/a0-a6.)

- [ ] **Step 3:** map.toml order lists — add the module head label (the first
  emitted proc, `Input_Tick`) right after `"GameLoop"` in BOTH
  `games/sonic4/map.toml` and `games/demo/map.toml` (the demo target builds the
  whole engine; a missing order entry fails the R2 subsequence validation loud).
- [ ] **Step 4:** Build x4 delete-first; commit exact paths.

### Task I3.3: `tools/replay_pack.py`

- [ ] **Step 1:** Create the packer. Interface:

```
replay_pack.py pack  --raw ring.bin --checks checklog.bin --ticks N \
                     --core-hash 0xXXXXXXXX --out fixture.bin
replay_pack.py dump  fixture.bin          # human-readable listing
replay_pack.py --selftest                 # exit 0 on pass
```

  Behavior: read N raw held-bytes; RLE-encode as `(byte, run_len-1)` pairs
  splitting runs > 256; **reject** any byte == $FF or with U+D ($03) / L+R ($0C)
  both set (SOCD-impossible — data corruption signal); interleave
  `$FF $01 <hash u32 BE>` records so each precedes the tick its log entry names
  (log pairs are big-endian `(tick u32, hash u32)`); terminate `$FF $00`; prepend
  the header (`ARP0`, flags=0, tick_count, core_hash, seed=0, reserved). All
  values big-endian (68k). `--selftest`: build synthetic streams (constant run,
  alternating bytes, >256 run, checkpoint interleave), pack → decode with an
  independent reference decoder → byte-exact round-trip; assert the reject paths
  reject.

- [ ] **Step 2:** Run `python3 tools/replay_pack.py --selftest` → exit 0.
- [ ] **Step 3:** Commit.

### Task I3.4: Sigil repin + gate

- [ ] Standard repin (new module → new region between GAME_LOOP and its
  successor; RAM shifts from the replay cells; DEBUG shapes also shift from the
  ring/log). Overseer gate: oracle smoke (live play unaffected; `Input_Source`
  poke to 2 in DEBUG records real bytes into the ring — spot-read via oracle),
  refreeze 26 → 27 (`replay-harness`), merge, push.

---

## Parcel I4 — The harness session (OVERSEER ONLY, foreground)

- [ ] **Record:** DEBUG ROM, OJZ from reset; oracle-poke `Input_Source=2`; play
  ~90 s (scroll, jumps, spindashes — touch the physics surface); on stop, dump
  `Replay_Record_Buf[0..Replay_Record_Idx]` + `Replay_Check_Log` via oracle reads
  to files.
- [ ] **Pack:** `replay_pack.py pack` with the build's cart-core hash → 
  `games/sonic4/data/replays/ojz_fixture.bin`; add the `embed()` data label
  (sonic4-side module, e.g. `games/sonic4/test/replay_fixture.emp`:
  `pub data Replay_OJZ_Fixture (align: 2) = embed("games/sonic4/data/replays/ojz_fixture.bin")`)
  + sonic4 map.toml order entry. (Small byte-changing commit → rides the I4
  refreeze.)
- [ ] **Determinism proof:** replay twice from reset (poke `Input_Source=1`,
  `Replay_Ptr=Replay_OJZ_Fixture+REPLAY_HEADER_LEN`, enter OJZ): checkpoint net
  silent both runs; final-tick full-WRAM oracle compare identical across runs.
- [ ] **Poisoned-RAM proof:** pre-fill WRAM $FF via oracle before reset; replay
  still syncs (boot-clear coverage).
- [ ] **The net bites (negative probe):** scratch build with one physics constant
  perturbed (e.g. gravity ±1) → replay must TRAP at the first affected
  checkpoint; record the tick number. Discard the scratch build.
- [ ] **Close-out:** evidence note (procedure + numbers + the oracle poke recipe
  as the standing regression runbook), DEFERRED_WORK stocktake #1 → RESOLVED,
  ENGINE_ARCHITECTURE input-layer section update, refreeze 27 → 28 if the
  fixture commit changed bytes, memory update, push.

---

## Self-review notes

- Spec coverage: §1→I1, §2→I2, §3→I3, §4→I4 ✓; the spec's flags/seed reserves are
  header-only (no code) ✓; attract wiring explicitly out of scope ✓.
- The `.hold`/`hold_minus_1` convention is defined identically in I3.2 and I3.3 ✓.
- `raise_exception` and comptime-if RAM fields are established idioms; porters
  verify precedent before use and STOP if the construct differs.
