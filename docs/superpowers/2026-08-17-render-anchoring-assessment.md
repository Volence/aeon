# ASSESSMENT — where the deterministic pixel gate should live

**Date:** 2026-08-17. **Status:** evidence complete, direction fork OPEN (owner ruling required).
**Supersedes the framing of:** `2026-08-18-oracle-render-anchoring-brief.md` (its Parcel 1 diagnosis is
wrong; its Parcel 2 design survives intact and is emulator-agnostic).

Two independent research seats were run against the same question: **fix the pixel
nondeterminism inside `oracle`, or build the pixel gate on `oracle-next`?** They reached
opposite headlines. The opposition resolves — both are right about their half.

---

## 1. Oracle's defect is a hard-coded plane index, not the render thread

The brief blamed the async render worker being unanchored from `ExecuteSystemStep`. It isn't.
The render thread drains and joins on every step (`System.cpp:2321` → `DeviceContext.cpp:421` →
`S315-5313_General.cpp:573-584`, which blocks on `_renderThreadStopped`), and every read on the
render path is `ReadCommitted` / `AccessCommitted` (`S315-5313_Rendering.cpp:272-273, 702-2440`).
The renderer is already a pure function of committed state.

**The actual cause:** the VDP rotates through three framebuffer planes (`IS315_5313.h:38`,
`ImageBufferPlanes = 3`, advancing `0→1→2→0` at `Rendering.cpp:1136-1145`) while every capture
site reads plane **0** unconditionally, so one capture in three reads the plane being rasterised
into. Verified sites:

| site | code |
|---|---|
| `linux-port/cli/main.cpp:260` | `const unsigned int drawPlane = 0;   // VDP double-buffers; plane 0 is fine` — the comment is factually wrong |
| `linux-port/gui/main_gui.cpp:2051` | `CopyLatestFrame(vdp, 0, frame)` |
| `Devices/315-5313/S315-5313_General.cpp:3411, 3434` | `GetScreenshot` locks the *displaying* plane, then indexes `_drawingImageBufferPlane` |

Signature confirms the model: every difference is a contiguous row band with a moving lower edge
(a tear), and the differing frames are ≡ 2 (mod 3) — the plane-rotation phase. `--frames-dir`
output is not a frame sequence at all: it keeps one distinct frame in three, duplicates it once,
tears it once (`frame0003`/`frame0004` byte-identical, crc `0xae93d6d7`).

**Both of the brief's candidate approaches were aimed at the wrong target.** Approach (1) would
wait on `_pendingRenderOperationCount`, which the code documents in-tree as broken
(`Rendering.cpp:164-170`), via a condvar waited on under two different mutexes
(`General.cpp:1049` vs `:1324`/`:1536`) — undefined behaviour, and it would fix nothing.
Approach (2) is a ~2000-LOC renderer extraction whose cheap form renders from `_latestMemory`,
i.e. end-of-frame state, which erases the mid-frame effects the gate exists to measure.

**Cost of the real fix:** ~25 LOC across 5 files, no new lock acquisition, strictly positive
blast radius (the interactive GUI stops showing torn planes too). Traps: `CopyLatestFrame`
(`main_gui.cpp:209`) lacks the `endX > startX` guard its CLI twin has; `main_gui`'s token
early-out means staleness must be closed at the service point (`:2171`) as well as the tear;
and a rare drain race (`Rendering.cpp:200-216` can exit with queued work that
`General.cpp:533-538` discards) will present post-fix as an off-by-one *frame*, not a tear.

### The measurements reconcile

The brief recorded "26 of 28 frames agree, 2 differ". Re-measured at 600 frames: **465 / 455 /
238 of 598 frames differ pairwise**, 8k-13k pixels each. Not a worse bug — the same 1-in-3 tear,
measured once there are pixels to tear. The brief's 30-frame window was mostly black screen.

### Anti-gate warning, recorded

`ab_runner`'s `_settle_frame_token` **wins within a pair and loses across pairs**: two selfcheck
pairs were each internally EQUAL on the screenshot yet produced different images from the
identical scene (`0xaf686b55` vs `0xb047521b`). Flipping `advisory=False` on today's oracle
would ship a gate that passes its own control and lies in production — the exact shape of
[[reference_verified_vacuous_gates]].

---

## 2. Oracle's renderer is accurate; the S/H exhibit is not about oracle

A blind code read (performed before the owner's screenshot was shown to the seat) found oracle's
Shadow/Highlight implementation careful and correct: STE read per pixel from the timed register
buffer (`S315_5313.inl:1382-1385`), operator sprites at palette line 3 idx 15/14
(`Rendering.cpp:1340-1341`) excluded as colours but retained in the sprite line buffer, the
"index 14 on any other line forced normal" quirk implemented (`:1389-1396`), a 512-entry priority
LUT with matching encode/decode bit order, shadow+highlight cancelling to normal (`:2294-2302`).
Mid-frame register writes are effectively per-pixel-clock, not per-line: `_reg.AdvanceBySession`
runs inside the pixel loop (`Rendering.cpp:286-290`), and CRAM dot writes are modelled
(`:1476-1519`).

**Provenance of the owner's two S/H exhibits — settled by colour forensics.** The captures
contain `(255,182,109)`, `(91,127,54)`, `(72,36,36)`, `(36,18,18)`.

- oracle: `Rendering.cpp:16` — `{0,34,68,102,136,170,204,238}`, shadow `{0,17,…,119}`. Max 238.
  **255 is unreachable.**
- oracle-next: `render.rs:453` — `(step as u16 * 255 / 14)`, truncating: `0,18,36,54,72,91,109,
  127,145,163,182,200,218,236,255`. **Every exhibit colour is an exact hit.**

The exhibits are **oracle-next** output. They are therefore not evidence against oracle's
renderer; they are evidence about the candidate replacement, which moves the S/H question onto
the critical path rather than off it.

Independent measurements off the exhibits: the shadow arithmetic is exact (`(72,36,36)→(36,18,18)`,
`(0,72,36)→(0,36,18)`, `(182,255,109)→(91,127,54)` — odd ladder steps are unreachable by normal
3-bit CRAM, so those pixels provably went through S/H, and the math is right). Exhibit 1 has a
real per-scanline edge: identical brown art shadowed across a contiguous top band, normal below,
sharp transition at ~screen row 16 (3x scale). Exhibit 2 disagrees about the same art.

**Open, needs owner input:** how the two were captured (lens/layer toggles on one frame vs two
runs), and what the ROM programmed that frame. oracle-next derives shadow from the A/B priority
bits (`render.rs:918-937`) — correct hardware behaviour, under which a high-priority FG plane
stays full-brightness while a low-priority BG darkens. If OJZ's FG tiles carry the priority bit,
"line on BG, none on FG" is the emulator being right and the effect's assumption being wrong.
Not separable from a real bug without the intent.

### Measured, 2026-08-17: the priority hypothesis is DEAD, and attribution cannot answer this

Probed a live headless `oracle-aether` on `s4.debug.bin` at frame 600 (own socket, the owner's
interactive instance untouched), 55 dots — 11 rows × 5 columns, straddling line 120 at
118/119/120/121/125 — via `emulator/pixel_attribution`. Script:
`scratchpad/sh_probe.py`. Two results, both negative, both useful:

1. **No plane pixel carries the priority bit.** Every planeA and planeB candidate at all 55 dots
   reported `priority = 0` (P1=0 / P0=10 on every row). The only P1 pixel found anywhere was
   `sprite 0`. So "the FG plane is high-priority and therefore stays bright under S/H" is
   **false for OJZ** — that explanation for "line on BG, none on FG" is dead. (Bound: 55 dots on
   one frame, not a proof of absence across the act.)
2. **`pixel_attribution` cannot attribute raster banding — the aeon use case.** Every dot reported
   `state: "normal"`, including rows 121-215, even though the ROM fires `reg_sh_on()` at line 120.
   This is by design and documented in-tree (`engine.rs`, the method's own doc comment): it
   "answers about the VDP's state *now*", re-deriving the scanline from current registers and
   reading no framebuffer, so at a frame-boundary pause it sees the frame-top-flushed `$8C81` and
   reports normal everywhere. The doc names the reconciliation path: per-scanline capture, **not**
   pause.

Result (2) is a material qualification of §5's ceiling argument and is recorded as such: the
instrument that most distinguishes oracle-next has a blind spot exactly on per-line register
effects. It does not sink the case — the gate would ride the rastered frame + framediff, and
`ScanlineCapture` is the sanctioned path — but "attribution tells you *why* this dot is this
colour" is true of whole-frame state and **not** of raster bands until an attribution-at-a-given-
scanline surface exists. Treat that as a requirement to add, not a feature to assume.

The S/H exhibit therefore remains UNEXPLAINED and stays open. What is now excluded: plane
priority bits, and shadow arithmetic error. What is not yet excluded: lens/layer-view semantics
in oracle-next's frontend (its layer-removal flags do not mask S/H operator flags — see §6), and
whether the water fire is armed at all in the sampled section.

---

## 3. oracle-next is materially closer than its own README claims

Measured, not asserted (all by a seat working in that repo; local hand-run, not CI):

- **Boots `aeon/s4.debug.bin` today.** 600 frames in 1.17 s, final `pc 00004284` =
  `RingCollision.ring_loop+$6`, real VDP regs (H40), 64 CRAM words, renders the OJZ jungle.
- **Deterministic by construction.** Zero `thread`/`Mutex`/`Arc`/`unsafe` in the core; rendering
  is inside the emulation step loop (`system.rs:958-1057`, `render_scanline` called at the line's
  emulated time). 10 identical runs → 1 distinct state hash at both 200 and 600 frames; 3
  independent server processes with input injection → identical state hash **and byte-identical
  PNG** (crc `0x2b538f89`).
- **Validated against oracle pixel-for-pixel**: 0 / 71,680 differing pixels, static and in
  motion. The one divergence found was an *oracle* bug (`M-2`: held input inert from power-on).
- **Suite:** 1,462 passed / 0 failed / 36 legs, incl. a 1,000,058-case 68000 single-step sweep
  through two drivers, VDPFIFOTesting 16/16, and per-scanline golden frames over 17 ROMs.
- **Protocol parity:** same JSON-RPC bus, same Python client `ab_runner` already imports.
  Missing for gate parity: `emulator/reset`, `emulator/write_memory` (both have their mechanism
  already in-tree), and `emulator/memory_hash`. `launcher.py`'s sandboxing disappears (one
  `--socket` per instance).
- **It has `emulator/pixel_attribution`** — winner layer, CRAM index, RGB, S/H state, and the
  ordered losing-candidate list with per-candidate verdicts. That is the instrument the parallax
  and effects work actually wants, and oracle will never have it.

Honest weaknesses: no V30/PAL/interlace (irrelevant — aeon is NTSC V28 H40); no sub-scanline CRAM
(`F-CRAMDOT`; aeon's effects are HBlank/per-line); nine enumerated pixel divergences each with a
locking golden scene; scheduler events pop at instruction boundaries, so *which line* first sees a
register write can carry up to one instruction of slop — deterministic, but a band-edge row from
oracle-next is "oracle-next's edge", not proven silicon's, until a hardware/BlastEm confirmation
lands. And its CI never fetches the corpora its own anti-vacuity guards demand
(`ci.yml:43` runs only the 68000 SST fetch; `vendor/` is gitignored), so the green above is
local — the same pattern [[project_sigil_lens_sweep_2026_08_13]] found in sigil.

---

## 4. The finding that outranks the whole fork

On `s4.debug.bin` at frame 600, the **live per-scanline frame and an end-of-frame re-render differ
on 42,866 of 71,680 pixels across 220 of 224 rows.** A pixel gate built on post-hoc rendering
measures a frame that never existed — it collapses precisely the mid-frame register work the
effects vocabulary produces. oracle renders per-pixel-clock inline and is on the right side of
this. oracle-next has both paths and reports which one produced the image (`source: "raster"`).

Whatever we gate on must be the rastered frame, and must *say* that it is. This, not the tearing,
is what would have silently invalidated the parallax gates.

---

## 5. The fork (OWNER RULING REQUIRED)

| | fix oracle | build on oracle-next |
|---|---|---|
| work | ~25 LOC + re-measure at 600 frames | 2 bus methods + harness re-point + scene flip |
| risk | drain race remains; no test net in oracle at all (zero `add_test`, 8 hand-run scripts) | band-edge slop unproven vs silicon; local-only CI |
| ceiling | a gate that says "these pixels differ" | + `pixel_attribution`: *why* this dot is this colour |
| lifespan | oracle retires when oracle-next lands (`CHARTER.md:3-11`) | it is the successor |

Parcel 2 (`replay_framediff`) is emulator-agnostic by design and survives either choice unchanged.

**Recommendation:** fix oracle's plane index regardless — it is 25 LOC, it de-risks the incumbent
everything currently points at, and it repairs the interactive GUI too — but **do not flip the
screenshot to gated on oracle**, and site the pixel gate on oracle-next. Rationale: the gate is
wanted for the parallax phase and Aurora's preview round-trip, both of which want attribution
("why is this dot this colour"), not just difference; and oracle is scheduled to retire under its
own charter, so gate infrastructure built on it is written twice.

## 6. Requested bus surface (for the oracle-next session) — measured gap, 2026-08-17

Enumerated from a live `oracle-aether` handshake (28 methods), not guessed. Already present and
NOT needed: `run_to`, watchpoints (add/clear/list/hits), full checkpoint/restore/list/drop,
`sprites`, `registers`, `read`/`read_memory`/`read_vram`, `press`/`hold`/`play_input`/
`release_all`, `state_hash`, `screenshot` (raster-labelled), `pixel_attribution`, symbols,
`reload_rom`.

**Tier 1 — unblocks the pixel gate (the current aeon queue item):**
1. `emulator/write_memory` — the poke primitive. All three committed scenes
   (`aeon/tools/scenes/*.json`) poke; mechanism exists (`mega_bus().write8`, in production use by
   `replay_runner` at `oracle-replay/src/runner.rs:606-609`). THE blocker.
2. `emulator/reset` — cold-start scene preambles; `System::reset()` exists (`system.rs:443`),
   just not exposed.
3. `emulator/memory_hash` — named-region hashing for gates; FNV code already in `state_hash.rs`.

With these three, `ab_runner` re-points at a `--socket` spawn, `_settle_frame_token` is deleted,
and the screenshot is gated — Parcel 1's entire outcome with no C++ surgery.

**Tier 2 — the daily interactive debug loop (day-one parity with `mcp__oracle__*`):**
4. Instruction stepping: `step`, `step_over`, `step_out`. Nothing on the bus steps by
   instruction; `run_to` covers breakpoint-stops only.
5. `run_to_scanline`, and **attribution-at-a-scanline** — §2's measured blind spot:
   `pixel_attribution` re-derives from frame-boundary register state and reports `normal`
   across a live raster band (55/55 dots, this doc). The per-scanline capture path is the
   sanctioned reconciliation; expose it as an attribution surface.
6. Z80: `z80_read`, `z80_registers` — sound work is untouchable without them.
7. CRAM/VSRAM **write**; and confirm the unified `read` reads CRAM **live** (oracle's CRAM read
   was frame-latched and therefore a vacuous instrument — [[reference_oracle_gate_instruments]];
   committed-state reads would retire that trap wholesale).

**Tier 3 — instruments, later:**
8. Frames-dir-equivalent multi-frame rastered dump on the bus (feeds `replay_framediff`).
9. Aeon-aware conveniences (`object_list`, `object_slot`, `player_state`), `log_tail`, layer
   toggles (masking S/H operator flags correctly — see rider below), profiler.

Standing caveats for the switch, neither blocking: absolute band-edge claims (the
`EFFECTS_AUTHORING.md` landing-line numbers) keep oracle as reference until the
instruction-granularity slop closes — A/B gates cancel the slop, absolute measurements don't;
and the S/H exhibit (§2) is open against oracle-next's renderer/frontend, not oracle's.

## 7. Riders discovered, not yet actioned

- oracle-next ships `replay_runner`, which runs aeon's replay net against `s4.debug.bin` and
  **passes today** (`crates/oracle-replay/src/lib.rs`, written against aeon's own
  `DEFERRED_WORK.md:113-125`). Aeon's books still record that gap as open with an aborting test
  binary. Verify and close if it holds.
- oracle-next's layer-removal debug flags do not mask S/H operator flags (oracle has the same
  defect at `Rendering.cpp:1340-1347`): disabling sprites leaves operator sprites still shadowing
  the planes. Any lens-toggled capture inherits this — directly relevant to reading the exhibits.
- `emulator_set_layer_enabled` toggles are read live by oracle's render thread; a gated capture
  inherits whatever the last MCP session left set.
