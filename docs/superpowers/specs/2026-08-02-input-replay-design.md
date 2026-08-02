# Input Layer Maturity + Demo Record/Replay — Design Spec

**Status:** DRAFT for Volence review (2026-08-02). Rulings already taken: full 6-button
now · recorder DEBUG-only · harness = in-ROM checkpoint net + manual oracle (CI
deferred until headless oracle). Research: three-agent fan-out 2026-08-02 (reference
disassemblies incl. Vectorman's 6-button read + S2/S3K demo systems; plutiedev/SGDK/
SukkoPera protocol detail; TAS/lockstep determinism practice). Substrate stocktake #1
(DEFERRED_WORK.md) is the demand source.

## Goals

1. Best-in-class controller layer: full 6-button protocol with per-frame type
   detection, both pads, exposing Mode/X/Y/Z to game code — while every existing
   consumer (`Ctrl_1_Held`/`Ctrl_1_Press` etc.) keeps working unchanged.
2. A deterministic demo record/replay harness at the input seam: record a play
   session in a DEBUG build, replay it byte-exactly, and catch any engine
   regression as a loud, localized desync — the standing regression net under all
   future engine work (and the tool that finally makes intermittent BUG-001
   capturable).
3. The determinism audit that makes (2) trustworthy, with its one code fix.

**Non-goals (this phase):** attract-mode/title wiring (the mechanism ships + one
committed fixture; menu integration is game-side later), TeamPlayer/mouse/multitap
(the dispatch seam accommodates them later), CI/strict-suite integration (needs
headless oracle), player-facing replay saving (recorder is DEBUG-only), RNG (none
exists yet; the replay header reserves a seed field for when it does).

## 1. Input layer (`engine/system/controllers.emp` rewrite)

**Read burst** (in VInt, once per frame — every VBlank including lag frames, which
satisfies the 6-button pad's ~1.5 ms counter-timeout spacing):

- The whole two-port burst is wrapped in ONE stop-Z80/start-Z80 pair — Z80 access
  to the 68k bus during I/O-port reads corrupts them (hardware bug; plutiedev,
  SGDK `HALT_Z80_ON_IO`, Vectorman's bus-request lock).
- Per port: the full 4-cycle TH burst (write $00/$40 alternating, 2-nop settle per
  phase — the S1/SGDK settle discipline already in our 3-button read):
  - cycles 1-2, TH=1: `1CBRLDU` — main buttons (as today)
  - cycle 3, TH=0: D-pad nibble all-zero = 6-button signature #1;
    cycle 3, TH=1: `1CB M X Y Z` — the extra buttons
  - cycle 4, TH=0: bits 3-2 forced `11` = signature #2
- **Detection = BOTH signatures** (SGDK's rule: the all-zero nibble alone is faked
  by broken/autofire pads), re-confirmed EVERY frame (hot-plug just works; a
  glitched frame degrades to 3-button data for one frame instead of latching a
  wrong type). 3-button/SMS/empty ports all resolve to PAD_3BTN behavior; their
  Ext bytes read 0.
- The existing SOCD guard (L+R / U+D cancel) stays, applied to the fused byte.

**Outputs** (RAM, engine-owned; existing cells unchanged, new cells appended to
the controller block):

| cell | meaning |
|---|---|
| `Ctrl_x_Held` / `_Press` / `_Press_Accum` | unchanged — `SACBRLDU` |
| `Ctrl_x_Ext_Held` / `_Ext_Press` / `_Ext_Press_Accum` | `0000MXYZ` (0 on 3-button) |
| `Pad_1_Type` / `Pad_2_Type` | `PAD_3BTN=0` / `PAD_6BTN=1`, refreshed per frame |

Ext press edges accumulate across lag frames and tick-latch in VInt exactly like
the main bytes (same consume-once pattern, vblank.emp latch site extended). 8 new
RAM bytes total (even-parity preserved).

**Structure:** the port read dispatches through a per-port routine selected by the
detect (today: one 3/6-common burst routine; the seam is the dispatch point where
a mouse/TeamPlayer handshake driver would slot in later without restructuring).

## 2. Logic-tick counter + the one audit fix

New `Logic_Tick` (u32) incremented once per game-logic tick in `GameLoop` (after
`VSync_Wait`, before state dispatch). `Frame_Counter` (VBlank-count, lag-inclusive)
stays for lag-aware code (tile_cache budget pacing — legitimately wants wall
frames).

**Audit fix:** `bg_anim` driver mode 2 switches `Frame_Counter` → `Logic_Tick`
(low word) so BG animation phase can't diverge between record and playback under
different lag patterns. (Behavior note: BG anims now freeze during lag frames —
arguably more correct visually; byte-changing, oracle A/B'd.)

**Audit findings (already verified, recorded here):** no RNG exists; no HV-counter
or VDP-status reads feed game logic outside DEBUG profiling; boot clears all 64KB
WRAM before any logic reads it (poisoned-RAM boot test in the gate procedure
proves it); sound mailbox flow is one-way 68k→Z80 (nothing driver-side feeds game
state). The lag-frame hazard is closed structurally by per-TICK replay (below).

## 3. Replay module (`engine/system/replay.emp`)

**The seam:** one call, `Input_Tick`, in `GameLoop` between `VSync_Wait` and the
state dispatch — after VInt latched the pads, before any consumer runs. Every
consumer downstream is untouched.

`Input_Source` (u8): `INPUT_LIVE=0` (call is a no-op), `INPUT_PLAYBACK=1`,
`INPUT_RECORD=2` (DEBUG builds only).

**Stream format** (ROM, via `embed()`; produced by `tools/replay_pack.py`):

```
header: magic "ARP0" (u32) · flags u8 · pad u8 · tick_count u32 ·
        core_hash u32 (build identity — stale replays fail loudly) ·
        rng_seed u32 (reserved, 0 until an RNG exists)
body:   RLE pairs (buttons u8 ≠ $FF, hold_minus_1 u8) ···
escape: $FF u8, opcode u8:
        $00 = end-of-stream
        $01 = checkpoint, payload hash u32 (covers the curated block, below)
        $02 = reserved (loop, for attract later)
```

Buttons byte = the latched `Ctrl_1_Held` (`SACBRLDU`). $FF as a held byte is
impossible (SOCD guard kills U+D+L+R), which is what frees it as the escape.
Ext/6-button state is NOT recorded in v1 (sonic4 consumes ABC+Start only; `flags`
bit 0 reserved for a future 2-byte-per-entry ext format). Pad 2 likewise (flags
bit 1 reserved).

**Playback** (`INPUT_PLAYBACK`, all builds — it's the attract mechanism too):
per tick: take the current stream byte as `Ctrl_1_Held`, derive
`Ctrl_1_Press = new & (new ^ prev_stream_byte)` — presses come from the STREAM's
history, never the live pad (the S1 REV00/S2 input-bleed desync bug, killed
structurally). Decrement hold; on borrow advance to the next pair. On a
checkpoint record (DEBUG only): recompute the curated-block checksum and
`raise_exception` on mismatch with tick number + expected/actual in registers
(release builds skip the compare and just step over the record). On end-of-stream:
set `Replay_Done`, revert to live. A live Start press during playback sets
`Replay_Exit_Request` (public flag; game decides what to do) — it does NOT merge
into the latched bytes, keeping the replayed input stream pure (cleaner than
S3K's OR-into-Ctrl approach, same capability).

**Recording** (`INPUT_RECORD`, DEBUG only): per tick, append the latched
`Ctrl_1_Held` raw into a RAM ring (`Replay_Record_Buf`, 8 KB = 8192 ticks ≈ 2:16
of play; DEBUG RAM has ~31 KB headroom today) and every 64 ticks append
`(tick, hash)` into a parallel checkpoint log (256 entries × 8 B = 2 KB). On ring
full: stop recording, latch `Replay_Done`. The overseer dumps both regions via
oracle; `tools/replay_pack.py` RLE-packs them into the stream format (interleaving
checkpoint records at their tick positions) and emits a `.bin` for `embed()`.

**The curated checkpoint block** (hashed by a shared `Replay_Hash` proc, simple
longword add+rol over): `Logic_Tick`, `Player_1` SST (80 B), `Camera_X/Y`,
`Dynamic_Live_Count`, `Effect_Free_SP`, `Dynamic_Free_SP`, the 4-entry
`Slot_Section_Map` + `Section_Stream_State`. A few hundred bytes, ~negligible
per-64-ticks cost. Deliberately excludes sound RAM, raw controller cells, VDP
staging buffers, DEBUG-only cells — gameplay state only, so the hash is identical
across build shapes and unaffected by audio.

## 4. Verification harness (this phase's bar)

1. **Determinism proof (oracle, overseer foreground):** record a ~90 s OJZ run
   (DEBUG ROM), pack it, embed it, replay it TWICE from reset — checkpoint net
   silent both times; full-WRAM compare (oracle read) at the final tick identical
   across the two replays. Then the poisoned-RAM variant: pre-fill WRAM with $FF
   via oracle before reset — replay still syncs (proves boot-clear coverage).
2. **The committed fixture:** the packed OJZ demo lands in
   `games/sonic4/data/replays/ojz_fixture.bin` + a `GameState`-adjacent DEBUG
   entry recipe (oracle pokes: `Input_Source=1`, stream ptr, enter OJZ init)
   documented in the evidence note. This is the standing regression net: any
   future engine parcel can replay the fixture and the checkpoint net localizes a
   desync to a 64-tick window + subsystem.
3. **Desync-catch demonstration:** deliberately perturb one physics constant in a
   scratch build and show the net TRAPS at the first affected checkpoint (proves
   the net actually bites — the negative-probe discipline).

## 5. File/parcel structure (implementation order)

- **Parcel I1 — 6-button input layer:** `controllers.emp` rewrite + `ram.emp`
  controller-block extension + `constants.emp` (PAD_* consts, button masks for
  MXYZ) + vblank latch extension. Oracle gate: 3-button behavior byte-compatible
  (existing consumers), detection correctness to the limit of oracle's pad
  emulation (if oracle only models 3-button pads, the 6-button path is gated by
  code review + the two-signature degrade proof, and a follow-up lands when
  oracle grows 6-button emulation — flagged honestly in the gate note).
- **Parcel I2 — Logic_Tick + bg_anim switch** (small, byte-changing).
- **Parcel I3 — replay module:** `replay.emp` + game_loop seam + DEBUG record
  ring + `tools/replay_pack.py`.
- **Parcel I4 — the harness session (overseer foreground):** record, pack, commit
  fixture, determinism + poisoned-RAM + desync-catch proofs, evidence note,
  DEFERRED_WORK/ARCH doc updates.

Each byte-changing parcel gates through the standard x6 + strict + repin +
refreeze procedure (chain 24 → …), Opus porters in worktrees, overseer
countersigns + runs all oracle work.

## Testing summary

Existing consumers proven unchanged (I1 A/B: held/press behavior identical on
3-button input). Replay determinism per §4. Sigil-side: new RAM cells repin;
negative probes where the format invites them (packer rejects U+D/L+R bytes,
reader traps on unknown escape opcode in DEBUG).
