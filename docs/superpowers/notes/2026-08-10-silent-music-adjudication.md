# Silent-music adjudication — 2026-08-10

Question (handoff workstream 5): is music playback on canonical shapes broken,
or was the pkg-1 session's direct `SND_REQ_MUSIC` poke an unsupported entry?

## Verdict: NOT broken. The poke was an unsupported entry.

`Sound_PlayMusic` (sound_api.emp) posts a **6-byte SND_MUSIC_PARAM block**
(bank, song $8000-window ptr LE, SH_FLAGS, patch window ptr LE) FIRST and the
`MUSIC_SLOT` trigger LAST, under one Z80 bus hold. The pkg-1 session's
`z80_write $1F02 = 1` set only the trigger — the Z80's loader then parsed a
zeroed param block (bank 0 / ptr $0000), armed the sequencer on garbage, and
produced no FM key-ons. That reproduces every observed symptom: request
consumed, `SND_STAT_SEQ_ACTIVE` mirror = 1, DMA flag normal, no audio.
Identical on pre-pkg-1 master because the entry was equally unsupported there.

Structurally, canonical shapes also have NO caller of `Sound_PlayMusic` at all:
`games/sonic4/config/game.emp` binds `boot_hook`/`debug_tick` only under
`SOUND_DEBUG_HOTKEYS==1`, so canonical builds boot silent by design — nothing
requests a song yet (game code will, once level music hooks exist).

## Evidence (real-audio A/B, house rule)

- Builds: canonical `DEBUG=1 ./build.sh` (crc 001b07ee) vs config-a hotkeys
  (`sigil build --aeon . --config-a`, crc ec2da120), both from master bdb0ad3c.
- Known-good route: config-a boot autoplay + A-restart (pattern 0), VGM capture
  → `configa_mt.vgm` → vgm2wav. Live FM spectrum confirmed first.
- Canonical route: no register-write tool in oracle, so the supported entry was
  emulated exactly: while paused, wrote the same bytes `Sound_PlayMusic` bakes
  (derived live from the loaded ROM's own code + SongTable at 0x5D522):
  param block `0B 07 86 03 C0 B7` → Z80 `$1CA6-$1CAB`, then `$1F02 = 1`
  (pause = the atomicity bracket). Resumed → `MUSIC_SLOT` consumed,
  `SND_STAT_SEQ_ACTIVE` = 1, strong FM spectrum → `canonical_mt.vgm` → wav.
- Comparison over 20 s windows: band-energy distribution (7 bands, 0-16 kHz)
  cosine similarity **0.9999**; same sub-200 Hz dominant structure; RMS ratio
  1.19 (different song sections in window — captures not sample-aligned).

## Operational facts worth keeping

- Z80 param block numeric addresses (this build): `SND_MUSIC_PARAM = $1CA6`
  (derived constant — re-derive after any sequencer-RAM growth; it slides).
- `SongTable = 0x5D522`, `SongPatchTable = 0x5D52E` (deb2 symbols resolve
  `SongTable` too).
- `Logic_Tick` is a RAM counter, NOT code — don't breakpoint it; use
  `VSync_Wait` for a safe main-loop break.
- Oracle has no 68k register-write tool — "oracle-call" of a proc isn't
  possible; the correct-mailbox emulation above is the working substitute.

## Consequences

- No P1 driver bug. Pkg 5 (production suite) is unblocked.
- Future debug sessions wanting music on canonical shapes: post the full param
  block + trigger (or use a config-a build); never trigger-only.
- The eventual game-side "play level music" call site remains open work (by
  design, not a defect).
