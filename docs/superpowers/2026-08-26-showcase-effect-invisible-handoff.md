# HANDOFF — the showcase effect does not render, and the foreground draws wrong

**Written 2026-08-26 by the aeon overseer, at the owner's instruction, so a fresh session can
continue without re-deriving anything.** The owner has said that if the current investigation
does not produce a named cause, he will reboot into a different model and hand it this document.
Everything below is either measured firsthand or attributed to the agent that measured it.

## The symptom, in the owner's own words

Playing `parcel/showcase-effects` (DEBUG shape), in section 4 (grid 1,1) where the new scene
is bound:

1. "2 bands moving up top, some animated background" — what he DOES see.
2. "the whole fg doesn't draw correctly (it's doing that thing where when you hold right it
   draws from right to left instead of left to right)"
3. "I don't see the depth, I don't see split, and I don't see curve"

**He has since ruled on provenance, and this is load-bearing:** it is **definitely caused by
this branch**, and it is a **recurring class** that appears "whenever we change some render
things like parallax". Do not spend time asking whether master has it. It does not.

## What the branch is

Authors owner decision `d-15`: turn on per-layer vertical depth (scanline P3 Task 11) and
curved scrolling (P3 T10) in the OJZ showcase. Leaves deform (T9) and the left-column mask
(T12) off. Five separable changes:

| # | change | note |
|---|---|---|
| 1 | `SCANLINE_CAPS` `$001F` -> `$005F` (`games/sonic4/config/game.emp`) | capability mask |
| 2 | `BAND_CURVE_N` `0` -> `1` (`engine/level/parallax.emp`) | adds a tail to EVERY band record |
| 3 | `BAND_CURVE_BYTES` `0` -> `10` (`engine/ram.emp`) | **MOVES RAM** |
| 4 | new scene `ojz_act1_depth.json` + `section_4.meta.json` + regenerated module + `act_descriptor.emp` section 4 | binds the scene |
| 5 | `OJZ_DepthVSplit` + `OJZ_Preset_Depth` (`ojz_effects.emp`) | hand-wired raster program |

Item 5 is hand-side because `tools/effects_gen.py` renders the attachment but emits no raster
program — editor raster composition is wave 2 and has not landed.

## CONFIRMED (measured, do not redo)

- **The scene is installed.** `Parallax_Current_Config` = `0x13924` =
  `EditorSceneBinding_OJZ_Act1_Sec4`, at rest and after two walked intervals inside the section.
- **The raster program is armed.** `Raster_Program` = `0x13D16` = `OJZ_DepthVSplit`.
- **Build-time wiring is correct.** `act_descriptor.emp` binds section 4 to `OJZ_Preset_Depth`,
  which carries `raster: OJZ_DepthVSplit`.
- **THE DISPLAY NEVER SETTLES.** Master is bit-stable at that arrival for 300+ frames. The
  branch produces **a new picture every 4 frames, forever**: 24 consecutive frames gave 7
  distinct pictures, pattern `ABBBBCCCCDDDDEEEEFFFFGGG`. This is the strongest lead and is a
  real defect owned by this parcel.
- **The churn has a SPECIFIC TRIGGER.** Boot-overriding into (1,0), (2,0), (0,1), or into (1,1)
  itself, then warping to (1,1): **stable**. Only arriving from the **authored start in section
  (0,0)** churns. So it is something the Aurora scene `EditorSceneBinding_OJZ_Act1_Sec0`
  installs that the destination preset never tears down.
  *Consequence for testing:* a ROM that BOOTS straight into section 4 may never show it,
  because section 0's scene is never installed.
- **The parcel moves `Raster_Buf_A`/`_B` by 84 bytes** (= `BAND_CURVE_BYTES * MAX_PARALLAX_BANDS
  + CURVE_CARRY_WORDS * 2).

## REFUTED (do not re-investigate)

- **Not a pre-existing master bug.** `boot_override_gate` on master is PASS, `rendered scanlines
  differing from the warp reference: 0 of 8`, re-verified across two master SHAs.
- **A debug warp DOES re-resolve the destination's parallax config.** Both routes carry
  byte-identical `Parallax_Current_Config`, `Target_Config` 0, `Transition_Frames` 0,
  `Snap_Pending` 0, `Prev_Sec` (1,1) at settle.
- **The diagonal-teleport hypothesis is dead.** `Parallax_CheckBoundary` has exactly two call
  sites, both in `games/sonic4/test/ojz_scroll_test.emp` (`:727` update loop, `:1181`
  `Debug_Warp_Consume` step 7); both re-resolve, and the warp writes `$FF` to
  `Parallax_Prev_Sec_X/Y` first, forcing the crossing rather than relying on edge detection.
- **Not a settling artifact in the gate.** `SETTLE = 30` frames vs `PARALLAX_TRANS_DEFAULT = 16`;
  both routes get the identical budget.
- **Not readable inter-frame state.** A whole-64KB Work-RAM diff attributes all 991 differing
  bytes to residue (HScroll tail past the 112 bytes the per-cell DMA ships; `Raster_Buf_B` while
  `Raster_Active_Buf` is `Buf_A` and identical; `Static_Pal_Ship` never enqueued; SAT past the
  link terminator; scratch). Both routes sit at the same `Logic_Tick` with byte-identical
  `cram`/`vsram`/`regs` at 13 scanlines spanning the frame. Parking both at the same beam
  position (0/112/223/260) changes nothing. BgAnim is provably in lockstep. **No single
  RAM-region transplant stops the churn.**

## THE OPEN QUESTION

`pixel_attribution` reports **different plane A cells winning at the same (x, line)** while
every state readable between frames is identical. So the divergence happens **during** the
frame. Two candidates, and the agent that found this flagged honestly that it could not
separate them:

1. a genuine mid-frame VDP write;
2. the emulator's raster capture not being a pure function of the state we can read.

**Separating those two is probably the crux.** If it is (2), this is partly an oracle question.

## THE PLAN IN FLIGHT (continue here)

**Bisect the parcel for the churn.** Build with ONE of the five changes at a time and find which
single change first makes the display stop settling. A previous agent already proved this
discipline works on this branch by attributing the ROM-space cost that way (baseline 13022 B /
vsplit only 12862 B / vsplit+curve 12094 B). Mechanical, not speculative.

Two leads to hold while bisecting:
- **The 4-frame period names its own subsystem.** What here has a 4-frame cycle: a fill/evict
  cadence, a page-frame rotation, a DMA queue drain, a BgAnim step?
- **Change 3 moves RAM.** A rendering fault that appears whenever parallax structures move is
  what a stale or mis-sized buffer boundary looks like. Check whether anything still addresses
  `Raster_Buf_A`/`_B` under an assumption the 84-byte shift invalidated.

**The historical experiment worth reusing:** on the 2026-04-28 instance the owner stubbed the
column-streaming routine to an immediate `rts` and all foreground content vanished, proving the
streaming engine was producing the artifact rather than failing to mask it. Cheap, decisive.

## The prior instance, and why NOT to reason from it

`docs/DEFERRED_WORK.md` ~line 2703 records the same symptom from 2026-04-28 in almost the
owner's words. **Its analysis is VOID.** It sits inside a DEAD CLUSTER, is framed on
`SECTION_SHIFT` and `Section_UpdateColumns` ring math that no longer exist, and its recommended
fix (camera teleport per plane width) is the OPPOSITE of the direction the engine took
(continuous scroll + floating-origin rebase, shipped 2026-06-22/23). The symptom class recurs;
the mechanism does not. Take the experiment, leave the analysis.

## Instruments, and the traps

- **Subagents must never touch `mcp__oracle__*`** — deadlock. Headless bus scripts via
  `tools/aether_instance.py` are the sanctioned instrument. The controller may use MCP directly.
- `run_to` takes a **symbol** and you must check `reached`. `read_memory` returns hex **with a
  `0x` prefix** — route reads through `aether_instance.read_bytes`. The bus is **24 bits**.
- **The Rust core does NOT serve `set_layer_enabled`** (`-32601 no such method`), so you cannot
  mute plane B to isolate the foreground. `pixel_attribution` and direct VRAM reads are the
  substitutes. **This is a filed instrument gap for oracle.**
- **The branch's canonical build FAILS by design** on the `bganim_room` ROM-ceiling gate (open
  owner decision `d-28`). Use `FAST=1 DEBUG=1 ./build.sh` and say so wherever a CRC is quoted.
  Branch FAST DEBUG crc is `83713589`; master DEBUG is `f8d06cae`.
- On the branch, canonical `DEBUG=1 ./build.sh` fails exactly **2** pytest tests, both bganim
  ROM-ceiling ones, positive-controlled as pre-existing. Any OTHER failure is real.
- Worktrees need `sigil`/`skdisasm` symlinks in the **PARENT** directory, never inside the
  checkout. Without them exactly 4 `tools/test_emp_helper_closure.py` tests fail resolving
  `<parent>/sigil/crates/sigil-harness/src/native.rs`. Those four only.
- **Verify DURING motion.** At-rest captures hide this entire class of artifact.

## Errors made in this investigation, recorded so they are not repeated

1. **Presence read as behaviour, by the overseer, in front of the owner.** Verifying
   `Parallax_Current_Config` and `Raster_Program` proves the scene is INSTALLED. It does not
   prove any mechanism is VISIBLE. Screenshots were sent captioned as showing depth and curve;
   the owner looked and saw neither. The layer movement in those stills is equally consistent
   with ordinary parallax plus the animated bands.
2. **Screenshots taken outside the section under test.** An early capture set was taken after
   scrolling far enough to LEAVE section 4, so `Parallax_Current_Config` had fallen back to
   `0x12C38` (the act default) and the images showed the OLD config. **A screenshot cannot say
   which config drew it; re-read the config at every capture.**
3. **A stale "known pre-existing failure" note was put into two agent briefs** before being
   measured. `boot_override`'s SETUP ERROR had been fixed hours earlier. That kind of note fails
   in the permissive direction: it licences an agent to write off a real red.
4. **"Possibly pre-existing" was the wrong frame for the foreground bug** and cost the
   investigation effort until the owner corrected it.

## Never established, stated plainly

Whether ANY of depth, split or curve is geometrically present in the output. Three worlds remain
open and they have completely different remedies: (a) the mechanisms are not executing;
(b) they execute but the authored magnitudes are imperceptible (the two vsplit offsets are
`at: 20` and `at: 44`; the curves go `FACTOR_1_4 -> FACTOR_3_8` and `FACTOR_1_2 -> FACTOR_1` —
**nobody has done the arithmetic on whether that is visible over a screen of travel**);
(c) they work and are drowned by the foreground defect.
