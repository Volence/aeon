# Sonic 2 clip music: per-channel balance and drum level (2026-09-26)

Parcel `parcel/s2-music-volume`, base `origin/master` `91d4119c`. Row: `docs/DEFERRED_WORK.md`
`## S2CLIP-REGION-MUSIC`, "Volume parcel".

## The report

The owner listened to the clip build (`S2CLIP=s2_ehz_cpz`: Emerald Hill's song, switching to
Chemical Plant's at the tunnel exit) and said: *"I think it's mostly correct but volume levels
for different channels and drums aren't, moreso in ehz than cpz."*

## How it was measured (rendered audio, not register streams)

`tools/s2_music_balance.py` (new). It drives the system's Genesis Plus GX libretro core
(`/usr/lib/libretro/genesis_plus_gx_libretro.so`) through a small ctypes frontend, headless, one
process per render, and renders the same song from two ROMs:

- **Real Sonic 2**: `s2built.bin`, built from s2disasm (header `GM 00001051-01`, REV01,
  1,048,576 B, md5 `9feeb724052c39982d432a7851c98d3e`; the copy used was
  `/home/volence/sonic_hacks/.scratch/s2-residual-census/luaref/s2built.bin`). START is pulsed
  until `Game_Mode` reads `$0C` (Emerald Hill act 1), 120 frames pass, then `MusID_EHZ` `$82`
  or `MusID_CPZ` `$8E` is written to `Sound_Queue.Music0` (`$FFFFE0`). The driver restarts the
  song from the top.
- **Ours**: `s4.s2clip.bin`. After 150 frames (the act-load request lands at frame 45 plain,
  88 debug) the region service's own bytes are poked: `Music_Current = 0` (the service reposts
  EHZ from the top) or `Music_Want = SONG_S2_CPZ`.

Capture starts on the request frame and lasts 60 s. GPGX exposes a mixer volume per YM2612
channel and per PSG channel. A SOLO render sets all the others to 0. The per-channel volumes only
work under GPGX's **MAME** YM2612 core. Under the Nuked cores they are ignored: with all six FM
channels at 0 the title screen still rendered -24.8 dBFS under `nuked (ym2612)`, against -47.9
under `mame (ym2612)`. So the tool uses the MAME core, and every run also renders a MUTED control
with every channel at 0. The tool refuses to report unless that control is silent. The same core
and options are used for both ROMs, so the comparison is like for like. It is NOT the owner's
Oracle chip model (`model1-va0-va2`).

Levels are RMS dBFS over the 60 s window, with both stereo sides pooled. Channel mapping: FM1..FM5
are YM channels 1..5 in both drivers (S2 `zFMDACInitBytes` `6,0,1,2,4,5`; the engine's
`CHROUTE_FM1..5`), DAC is YM channel 6, PSG1/2 are tone channels 0/1, and the hat is the noise
channel in both. FM1 lands within 0.04 dB in both songs before any fix. That shows the capture
windows are aligned and the tempo matches.

## What was wrong

### 1. The converter threw away each channel's header volume (FIXED)

Both Sonic 2's driver and Sonic 3's copy the `smpsHeaderFM` / `smpsHeaderPSG` volume byte into
`zTrack.Volume` at song init. Every `smpsAlterVol` / `smpsPSGAlterVol` then ADDS to it
(`cfChangeFMVolume` / `cfChangePSGVolume`: `add a,(ix+zTrack.Volume)`; `zSetFMTLs` adds
`zTrack.Volume` to the carrier TLs picked by `zVolTLMaskTbl`).

`tools/smps_import.py` kept the running volume per channel (`ConvState.fm_vol_raw` /
`psg_vol_raw`) but seeded it with `None`, which `_alter_vol` read as 0, the loudest value. So a
channel's first AlterVol discarded its header attenuation, and every later volume in that channel
was relative to 0. The header value itself was only emitted as a `Vol` when no volume op came
before the first note (`_make_packable`).

**Why EHZ is worse than CPZ, the owner's clue:** EHZ's headers are large (FM2/FM3 `$16`, FM4
`$20`, FM5 `$25`, PSG1/2 `$04`), and FM2..FM5 and PSG1/2 all use AlterVol. CPZ's headers are
`$08..$10`, and FM2 never alters its volume. The lost attenuation therefore runs up to 28 dB in
EHZ, against at most 12 dB in CPZ.

The fix is `_seed_header_volume(st, ch)` in `convert_song`: FM `fm_vol_raw = header & $7F`,
PSG `psg_vol_raw = header & $0F`. Loop balance was checked with scratch instrumentation (not
committed): for every EHZ/CPZ channel, the running volume at its `smpsJump` equals the value at
the jump target. So the representation (unroll once, then jump) stays exact, and S2 does not
drift across loops either.

HCZ2 (the S3K path) has no AlterVol. It converts byte-identical: 6,511 B, equal to the committed
`song_hcz2.bin`.

### 2. The drums: Sonic 3's samples are hotter than Sonic 2's (NOT FIXED: owner call)

The DAC channel is +2.36 dB (EHZ) / +2.47 dB (CPZ) hot. The fix above does not touch this
number, which comes from the samples themselves. To measure it per drum, the DAC solo render was
split into hits: an onset after silence, an 80 ms window each, grouped by spectral centroid.
Levels are in dBFS:

| | real S2 kick | ours (S3K kick) | real S2 snare | ours (S3K snare) |
|---|---|---|---|---|
| EHZ | -19.60 rms / -11.04 pk (n 64) | -18.60 / -11.97 (n 63) | -23.59 / -12.22 (n 63), centroid ~2.4-4 kHz | -19.32 / -10.34 (n 67), centroid ~3 kHz |
| CPZ | -19.91 / -10.99 (n 61) | -18.16 / -11.86 (n 53) | -23.61 / -12.21 (n 84) | -19.41 / -10.73 (n 71) |

- The S3K kick is +1.0 to +1.7 dB RMS, yet its peak is about 0.9 dB LOWER than S2's. It is a
  denser sample, not a louder one.
- The S3K snare is about +4.2 dB RMS and +1.9 dB peak, and its timbre differs as well.

No single gain fixes both drums. The engine also has no DAC volume path: `DacSample.ds_vol` is
reserved and v1 ignores it, and scaling in the Z80 fill loop would cost a multiply per sample.
Attenuated copies of the S3K kick and snare would cost bank space and would still be the wrong
timbre. The faithful fix is Sonic 2's own drum samples (about 13 KB, which does not fit the current
drum bank per `docs/decisions.jsonl` S2CLIP-MUSIC-DRUMS). The owner ruled `s3k-drums`, so this
is his call. STOPPED; see the DEFERRED_WORK row.

Because FM2..FM5 were 11 to 19 dB too loud before fix 1, the drums were buried in the EHZ mix by
far more than 2.4 dB. The owner probably heard that burying, and fix 1 removes it. What remains is
the S3K kit sitting a little forward, the snare most of all.

### 3. The PSG volume envelope attacks one frame late (NOT FIXED: needs a sigil re-pin)

The noise hat is +1.18 dB hot in BOTH songs, and that number did not move with fix 1. It comes
from an engine timing difference, not from the data:

- Sonic 2's `zPSGUpdateTrack` runs `zPSGDoNoteOn` and then `zPSGDoVolFX` in the same frame.
  `VolFlutter` is reset at note-on, then read and incremented. So envelope byte 0 plays on the
  attack frame and byte 1 on the next.
- Sonic 3's driver does the same: `zUpdatePSGTrack`, `.skip_fill`, runs `zDoVolEnv` on the
  note-on frame.
- The engine runs `ModUpdate` (and so `PsgEnvUpdate`) BEFORE `Sequencer_Channel` within a frame,
  and `Psg_EnvCursorReset` zeroes the cursor and the output at the attack. So the attack plays
  delta 0, byte 0 plays one frame later, and every contour is one frame late and one frame long.
  With `fTone_02` = `0,2,4,6,8,$10`, S2 sounds 5 frames per hit and we sound 6.

**Mechanism test (scratch, not landed).** The engine body of `fTone_02` (id `$42`) was shifted to
`2,4,6,8,$10`, so that the one-frame-late engine reproduces S2's contour exactly. The build and the
measurement were then repeated, and the table was restored from the commit. Result:

- NOISE went from +1.18 to **-0.03 dB** (EHZ) and to **-0.12 dB** (CPZ).
- EHZ PSG1/2 moved by 0.01 dB. Their envelopes (`fTone_01/03/08/0B`) are slow, so one frame is
  a smaller share of each note.

This row's own history shows the same class: DEFERRED_WORK **D5** ("PSG envelope attack uses a
stale `sc_psgenv_out` / lands one frame late vs S3K") was closed as "ALREADY DONE" on the
strength of the zeroed `sc_psgenv_out`. That fixes the stale half. The one-frame-late half is
still live.

**Why it is not fixed here.** The natural fix grows the resident Z80 driver, and the brief says
no sigil changes. The fix: in `Seq_HookNoteOn`, after `Psg_NoteOn` / `Psg_Noise`, run
`PsgEnvUpdate` once when the channel has an envelope and keyed. That gives byte 0 on the attack
frame and byte 1 next frame, keeps write-on-change, and covers SFX too. It is +17 B plain. With
it, `emit_sound_blob` refuses the build: `plain blob is 6193 bytes, expected 6176 ($1820) ... re-pin
BLOB_LEN_PLAIN and the Z80_SOUND_SIZE mirrors`. The resident blob length is pinned in sigil
(`crates/sigil-harness/src/seam1.rs` `BLOB_LEN_PLAIN`/`BLOB_LEN_DEBUG`,
`crates/sigil-cli/tests/boot_port.rs` `Z80_SOUND_SIZE`, `repin_pins.rs`,
`tranche23_spelling_probes.rs`). A first attempt put the prime in `Psg_EnvCursorReset`. It is
refused for a second reason: seam-1 lowers `sound_psg.emp` against a per-module name list, and
`sc_psgenv` and `PsgVolEnvCtl_Loop` are not on it. STOPPED. The patch text is in the DEFERRED_WORK
row.

It would also move every sound-on shape, HCZ2 and every SFX with a PSG envelope, one frame toward
S3K. That wants the owner's ear too.

## Numbers: ours minus real Sonic 2, dB (60 s, per-channel solo)

Plain clip ROM before the fix, master `91d4119c`, `s4.s2clip.bin` crc `ca8b4ee1`; after the fix,
`f02ba121`:

| channel | EHZ before | EHZ after | CPZ before | CPZ after |
|---|---|---|---|---|
| MIX | +9.47 | +0.94 | +1.21 | +0.70 |
| FM1 | +0.04 | +0.04 | +0.98 | +0.05 |
| FM2 | +11.95 | +0.04 | -0.01 | -0.01 |
| FM3 | +10.96 | +0.06 | +1.68 | +0.03 |
| FM4 | +15.22 | +0.10 | +1.37 | +0.05 |
| FM5 | +18.90 | +0.04 | +0.83 | +0.02 |
| DAC | +2.36 | +2.36 | +2.47 | +2.47 |
| PSG1 | +8.17 | +0.17 | (+0.55) | (+0.55) |
| PSG2 | +8.13 | +0.12 | (+2.37) | (+2.37) |
| NOISE | +1.18 | +1.18 | +1.18 | +1.18 |
| mix log-spectrum correlation | 0.9671 | 0.9926 | 0.9947 | 0.9942 |

Absolute real-S2 levels in dBFS, for reference:

- EHZ: FM1 -26.93, FM2 -31.32, FM3 -34.24, FM4 -38.85, FM5 -35.76, DAC -27.90, PSG1 -43.47,
  PSG2 -45.32, NOISE -38.97, MIX -22.73.
- CPZ: FM1 -26.01, FM2 -27.12, FM3 -32.32, FM4 -30.06, FM5 -33.35, DAC -26.44, NOISE -34.61,
  MIX -20.37.

The CPZ PSG1/PSG2 values in parentheses are not a channel. In the source both are `smpsStop`, and
both ROMs measure about -78..-80 dBFS there, which is leakage near the floor.

The debug clip ROM after the fix (`aff832f9`) gives the same table within 0.04 dB (for example
EHZ FM4 +0.10, DAC +2.33, NOISE +1.17; CPZ DAC +2.36, NOISE +1.16).

## Confidence and limits

- The reference is real Sonic 2 code and data, played on the same emulator. The emulator is
  GPGX's MAME YM2612, not Nuked and not the owner's Oracle chip model. Balance BETWEEN channels
  is what was compared, and both ROMs share every mixer constant, so a chip-model difference
  should move both sides equally. It would not affect a relative dB result unless the two drivers
  drive the chip into regions that model differently. That was not measured.
- RMS over 60 s includes rests, so it is a balance measure, not a per-note level. FM agreement at
  0.03..0.10 dB is the strongest evidence that the volumes now match note for note.
- **Nothing was listened to by a person.** The owner's ear is the remaining check.
