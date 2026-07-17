# Sound_PlayMusic repost gate — cross-seam design (H-1)

**Status:** ratified + implemented in fix/sprites-pb1-pb2. Cross-seam: 68k
`Sound_PlayMusic` (sound_api.emp + .asm twin) and the Z80 `Snd_LoadSong`
(z80_sound_driver.asm — **no .emp twin**, so only the 68k side pays lockstep).

## The race (review H-1)

`Sound_PlayMusic` posts a 6-byte param block (`SND_MUSIC_PARAM_{BANK,PTR_LO,
PTR_HI,FLAGS,PATCHPTR_LO,PATCHPTR_HI}`) then a trigger byte (`SND_REQ_MUSIC` =
song id) under one Z80 bus hold — that hold makes a SINGLE post atomic against
the Z80. It does **not** guard a *repost*: a second `Sound_PlayMusic` landing
while the Z80 is mid-`Snd_LoadSong` overwrites the param block the loader is
still reading (the loader reads it live at 6 sites, `z80…:1125–1183`) → a torn
bank/ptr/flags load (streams as noise), AND — because `Snd_LoadSong` cleared
`SND_REQ_MUSIC` at its END (`:1374`) — the second trigger is wiped when the
first load finishes → the new song is silently lost. The SFX slot already has
the correct shape (68k-side ring + `Sound_DrainSfxRing` one-per-frame drain);
music (and ping/fade/tempo/sample) had a bare read→handle→clear poll.

## The fix — a "previous request consumed" gate

Two coordinated changes:

1. **68k (`Sound_PlayMusic`): spin until `MUSIC_SLOT == 0` before posting.**
   The slot is nonzero from a post until the Z80 clears it. Spinning first means
   we never overwrite a param block the Z80 is still consuming, and never clobber
   a trigger the Z80 hasn't picked up. Placed at the very top, before deriving
   bank/ptr/flags, so the derive work overlaps nothing.

2. **Z80 (`Snd_LoadSong`): clear `SND_REQ_MUSIC` at `.fm6_pan_owned`** — just past
   the FM6-pan setup, the first point where the two FM6 branches rejoin AND every
   param read is done (`SND_MUSIC_PARAM_FLAGS` at `:1183` was the last). REMOVE the
   end-of-load clear. This is placed a few instructions later than the strict
   last-read point so the FM6-adaptive Z flag is dead and a plain `xor a` clear is
   safe — making the change **byte-neutral** (4 bytes moved, not added), so the Z80
   blob (which precedes the 68k engine block in the ROM) does not grow and shift
   every downstream region. The load tail below `.fm6_pan_owned` (channel init,
   tempo) never touches the param block.

### Why no snapshot-to-locals (a deviation from the first sketch)

The original sketch had the Z80 *snapshot* the 6 param bytes to locals and clear
`SND_REQ_MUSIC` *before* the load body, so the loader works from the copy. That
is only necessary if a repost could overwrite the shared param block while the
loader reads it. **The 68k gate already provides that mutual exclusion**: while
the slot is set, the 68k spins and cannot repost, so the loader may read the
shared param block directly and clear the slot *after* the last read. This drops
the snapshot entirely — no 6 bytes of scarce Z80 RAM (only $D4 free), no
redirection of the 5 read sites, no new failure surface in the delicate loader —
for the same guarantee. `read-then-clear` under the gate == `snapshot-then-clear`
without it. The clear moves from `:1374` to `:1185`; everything from `:1186` on
(sequencer arm, tempo) never touches the param block, so a repost landing in
that tail is safe and is handled by the next mailbox poll (the removed end-clear
is what would have wiped it).

Implementation nit: the clear uses `ld a,0` (not `xor a`) so it does not disturb
the FM6-adaptive Z flag that the `jr nz` two lines down tests.

## The spin bound (stated, per the review ask)

The spin is **empty in the common case**: a normal `Sound_PlayMusic` runs with no
load in flight, so `MUSIC_SLOT` is already 0 and the gate falls straight through.
It only waits on a genuine rapid repost (a second call before the Z80 consumed
the first). The wait is then bounded by:

  **(time for the Z80 to next poll the mailbox) + (time from Snd_LoadSong entry
  to the `:1185` param-consumption point).**

A load is finite, so this is bounded — it is not an unbounded busy-wait. The
second term is small (`Sequencer_StopAll` + `Sfx_StopAll` + the seq-block clear
loop + the 6 param reads — tens of µs); the early clear removes the entire
*rest* of the load (sequencer/channel init, tempo) from the window, which is the
bulk. The first term dominates and depends on the Z80 poll cadence (the Timer-A
tick polls the mailbox during streaming; worst case ~one driver frame tick).
Music changes are not a hot path and reposts are rare, so a worst-case ~1-frame
stall on a rapid double-post is acceptable — and strictly better than the torn
load / lost request it replaces.

## Slot audit — ping / fade / tempo / sample

Only **music** carries a multi-byte param block, so only music can be *torn*
mid-read; that is the one slot this gate is built for.

- **ping (`SND_REQ_PING`), sample (`SND_REQ_SAMPLE`), fade (`SND_REQ_FADE`),
  tempo (`SND_REQ_TEMPO`)** are all single-byte commands. A repost cannot tear
  them (one byte is written atomically). The only residual is the review's PB-2
  "latest-wins violated by read→handle→clear": a repost landing between the Z80's
  read and its clear is lost. For these slots the consequence is benign — a ping
  is a ping (idempotent-ish); a dropped duplicate fade/tempo/sample re-issues on
  the next state change. None drives a param block whose tearing corrupts state.
  **Decision: no gate for the single-byte slots this batch** — the SFX ring
  (already correct) + this music gate cover the two slots where a lost/torn
  request is user-visible. If a future consumer makes a lost fade/tempo audible,
  the same `MUSIC_SLOT`-style gate applies per-slot; recorded here as the pattern.

## Verification

Byte gate: sound_api region re-pinned (68k gate grows the region; twins in
lockstep). The Z80 change has no .emp twin — assembled directly. Boot-check the
sound build (music still starts; a scripted rapid double-PlayMusic must end on
the SECOND song, not silence/noise). No emulator models the repost timing window
precisely, so the primary proof is the code contract above + the boot check.
