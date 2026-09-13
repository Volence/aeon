# F3 RUNTIME-TAG: the 932 deleted sound-effect bytes, fired on a running game (2026-09-13)

**Closes** handoff-10's "Next" item 4 (`docs/superpowers/2026-09-12-aeon-overseer-handoff-10.md`) and the
`F3-RUNTIME-TAG` queue row: *"a green build cannot observe reachability of the 932 deleted bytes. Fire the 16 SFX."*
The F3 merge (`c0d1b816`) removed `SfxTable`'s 548 bytes of cells and the 384 bytes of separate `Sfx_NN_Patches`
copies. A build cannot see whether anything still READ those bytes, because a reader would change behaviour and
not the build. This note answers it at runtime, two ways, each with a control that could have failed.

**Scope, so the result is not read wider than it is:** boot, 600 frames idle in OJZ act 1, then each of the 16 SFX
fired once through the game's own request ring (`Sfx_Ring_Buf`, drained by `Sound_DrainSfxRing`), in the canonical
`s4.debug.bin` shape, with no music playing (canonical shapes carry none). Not exercised: SFX fired while music plays
(voice stealing), `Sound_PlaySFX` itself (the runner writes the ring directly; `Sound_PlaySFX` only enqueues an id),
other game states, and the release `s4.bin` shape.

## 1. A/B of the Z80 driver's own state, before and after the deletion, under one assembler

- **A** = `0dc9e0d1`, the F3 merge's first parent. **B** = `c0d1b816`, the F3 merge. **Tip** = `251f51fe`, the published
  tip at the time. (The F3 row's control was built at `47bc76d4`, the parcel's own base; the merge's parent is
  `0dc9e0d1`, and that is the one that isolates exactly what the merge brought.)
- Built clean, detached, `FAST=1 DEBUG=1 ./build.sh`, both `finished=0`, with the same sigil binaries
  (md5 identical before and after both builds). `s4.debug.bin`: A 847533 B CRC32 `9ce1c2ff`, B 846601 B CRC32
  `f6913405`, tip 846601 B CRC32 `e36d98ba`. The 932 B drop matches the F3 row.
- Runner: `2026-09-13-f3-runtime-tag/f3rt_run.py`. Each ROM in its own headless `oracle-aether`
  (`tools/aether_instance.py`, which checks the cart against the file). Boot 600 frames, checkpoint, then per SFX:
  restore, queue the id, step one frame at a time reading the 7 `SfxChannel` slots (Z80 `$1D00`, 68 B each,
  derived from `sound_constants.emp`; `sizeof(SfxChannel)` came out 68, matching the source's own `ensure`). Every
  pointer a channel holds (stream, `sx_patch_base`) is recorded relative to that SFX's own blob window, found in
  each ROM by a unique byte match of `sfx_NN.bin`, so traces from ROMs whose blobs sit at different addresses
  compare equal only if the driver behaves identically.
- **Result: 16 of 16 traces identical frame for frame, A against B, B against tip, A against tip.** 766 frames and
  786 active-channel rows per ROM. Every SFX: consumed once (`SND_STAT_ACK_COUNT` +1), started on frame 3, ended by
  itself (10 to 126 frames), driver alive throughout, 0 pointers outside its own blob. Every FM channel's patch base
  sits inside its own blob, at the same offset on all three ROMs, so in A, where the separate copies still existed,
  the Z80 was already reading the inline copy.
- **Comparator control:** `$33` against `$35` within A reports a difference, so equality is not a blind comparator.

## 2. Read watchpoints on the 932 bytes themselves, in ROM A where they still exist

- Runner: `2026-09-13-f3-runtime-tag/f3rt_watch.py`. Read-only bus watches armed at frame 0 on the 548 B `SfxTable`
  cells (`$0BDD2C..$0BDF4F` in A's `s4.debug.bin`, found as the only run of 137 longs whose non-zero cells are the 16
  blob addresses) and the 12 separate patch copies (384 B, the `sfx_NN_patches.bin` matches that lie inside no blob).
  Then boot and all 16 SFX in one timeline, no restore (a rewind can discard hits).
- **68k positive control, with a predicted count:** the first 16 bytes of the Z80 image (`Z80_Sound_Start`), which
  boot copies one byte at a time. **Predicted 16, measured 16**, fc 5, all at `EntryPoint.load_z80`. The instrument
  sees 68k ROM reads.
- **Result: 0 reads on all 13 ranges, dropped 0.** No 68k code read the deleted bytes in the scope above.
- **Z80 positive control FAILED, and that is a finding about the instrument, not the ROM.** A watch on `$33`'s inline
  patch bank, which the Z80 reads when `$33` plays, got 0 hits. Oracle's source at their `origin/main` agrees:
  `Z80Bus::read_window` (`crates/oracle-core/src/z80/bus.rs`) serves the bank window with no bus event, though the
  `watchpoints.rs` header says both bus adapters deliver every access. **So the watchpoints say nothing about Z80
  readers.** Section 1 answers the Z80 half instead. Reported to the oracle lane 2026-09-13; they confirmed it from
  their own source and booked it as **`F-Z80-ACCESSES-UNWATCHED`** (oracle `ea1dcb8`, a docs commit, reachable from
  their `origin/main`), and found it wider than reported here: no Z80 access at all reaches a watch (its own RAM,
  window writes, the VDP mirror), only its FM/PSG register writes.

## Reproduce

Needs `SIGIL_BUILD`/`SIGIL_EMIT` for the two builds. The runners import `tools/aether_instance.py` from a checkout
path hard-coded at the top of each file; point it at any aeon checkout.

```sh
python3 f3rt_run.py   <tree>/s4.debug.bin <tree>/s4.debug.lst <tip-tree>/games/sonic4/data/sound/sfx out.json
python3 f3rt_watch.py <A>/s4.debug.bin    <A>/s4.debug.lst    <A>/games/sonic4/data/sound/sfx      out.json
```
