# Region music: Emerald Hill to Chemical Plant (design pass + feasibility probe)

Date: 2026-09-25. Branch `research/region-music`, based on `origin/master` 09185beb.
Owner's ask, verbatim: "after this shall we test the music transitions per region from sonic 2
ehz to cpz?" The eventual deliverable is the clip build (`S2CLIP=s2_ehz_cpz`) playing Emerald
Hill's music and switching to Chemical Plant's at the region crossing. **This document is the
design and the evidence. Nothing here landed in the ROM.** The probe edits were reverted, and
the only files committed are this doc and the two throwaway probe scripts beside it
(`docs/research/2026-09-25-region-music/`).

**Nothing in this document is a judgement of how anything sounds.** No instrument in this
workspace renders audio (oracle's Rust core serves no audio methods). Every "it plays" below
means that the Z80 wrote key-ons and DAC samples to the YM2612. Timbre, pitch, tempo feel and
the transition's feel are **TAGGED FOR THE OWNER'S EARS** wherever they come up.

---

## Summary

1. **Import: feasible, and cheap.** The existing converter (`tools/smps_import.py`) took both
   Sonic 2 songs after a small pre-pass that applies the Sonic 2 to Sonic 3 conversions Sonic 2's
   own `_smps2asm_inc.asm` defines. EHZ packs to 2,522 B + 288 B of voices and CPZ to 3,611 B +
   192 B. Both were **assembled into a real config-A ROM, byte-verified in the phase bank, and
   sequenced by the real Z80 driver**: FM1-5 key-ons plus a live DAC stream, measured headlessly.
   What is still missing for fidelity: Sonic 2's PSG envelopes (EHZ's PSG gets the wrong ones
   **silently** today) and Sonic 2's own drum samples (the probe used the S3K drums).
2. **Playback in play: no new profile.** The driver is already in every sound-on shape. The only
   thing missing is a caller, and region data supplies it. Canonical OJZ rows carry "no song",
   so `s4.bin` goes on playing no music. Two structural costs: **sigil hardcodes the song
   count** (a cross-repo change for any new song), and the one 32 KB phase bank would be down to
   about 2.7 KB free in the DEBUG shape once both songs are in.
3. **The switch.** Add a song id to `Region`, read on `Parallax_CheckBoundary`'s slow path (the
   one place the engine notices a crossing), compared against the song already playing so that
   L-shaped regions and warps within a zone do nothing, and posted without blocking.
4. **The feel is the owner's call.** Recommendation: **the song changes when the player comes
   out of the tunnel**, not at its middle, optionally with Emerald Hill fading out through the
   tunnel. See the decision at the end. One fact shapes every fade option: **the driver's fade
   does not touch the DAC drums**.

---

## Q1. Can `smps_import.py` take Sonic 2's EHZ and CPZ?

### The controller's beliefs, checked

| Belief | Verdict | Evidence |
|---|---|---|
| S2 songs are Saxman-compressed | **Wrong for our purposes.** Saxman is applied when s2disasm *assembles* its ROM. The sources in the tree are plain smps2asm text, which is the only thing the converter reads. | `s2disasm/sound/music/82 - EHZ.asm` and `8E - CPZ.asm` are smps2asm macro source, 551 and 484 lines. |
| S2 uses a different SMPS variant with its own conventions | **True, and already solved in the source tree.** s2disasm's and skdisasm's `_smps2asm_inc.asm` are **byte-identical** (`diff` printed nothing, both 968 lines). The file converts a `SourceDriver 2` song to a `SonicDriverVer >= 3` target itself. We reproduce its rules and do not have to invent them. | `s2disasm/sound/_smps2asm_inc.asm:185-231` (tempo, PSG pitch), `:343-356` (PSG header), the `smpsModSet` block (~:554-563), `:52-59` (`nMaxPSG`). |
| Not converted yet | True. `SONG_*` ids are 1 Moving Trucks, 2 DrumTest, 3 HCZ2 only. | `games/sonic4/config/sound_ids.emp` |

### What the converter already handles

Every coordination flag the two songs use is in `_FLAG_MNEMONICS` / `_dispatch_flag`
(`tools/smps_import.py`: smpsSetvoice, AlterVol, PSGAlterVol, AlterNote, AlterPitch, ModSet,
ModOff, Pan, PSGvoice, PSGform, NoAttack, Call/Return/Loop/Jump, Stop). The voice converter
(`smps_voice_to_fmpatch`, which shares the verified SFX voice path) accepted all 15 inline voices.

### What breaks, and what each break needs

Measured by `docs/research/2026-09-25-region-music/s2_probe.py`, which runs the unmodified
converter behind a pre-pass. Each row below broke or would silently mis-convert:

| # | Difference | What happens without handling | Fix (from the include's own rule) |
|---|---|---|---|
| a | **Tempo model is inverted.** S2 `TempoWait`: on accumulator carry the music plays, otherwise every track stalls a tick (`s2disasm/s2.sounddriver.asm:596-617`). S3K, which the engine adopted exactly (`tools/smps_import.py`, `SongConfig` note), stalls *on* carry. | Silently wrong tempo. | `s2TempotoS3(n) = (0x100 - n) & 0xFF` (`_smps2asm_inc.asm:184`). EHZ `$9E` becomes `$62`, CPZ `$EE` becomes `$12`. Both reduce to the same ticks per frame (158/256 and 238/256). |
| b | **PSG header pitch** is 12 semitones apart | PSG an octave off, silently | `PSGPitchConvert`: `+psgdelta` (12) on the `smpsHeaderPSG` pitch (`:224-231`) |
| c | **`nMaxPSG`** (EHZ uses it 85 times, CPZ 18) | `KeyError` (the probe's second crash) | for an S3K target `nMaxPSG = nBb6 - psgdelta` (`:57`) |
| d | **Modulation parameters** use different units | Silently wrong vibrato | `smpsModSet w,s,c,st` becomes `w+1, s, c, ((st+1)*s)&$FF` |
| e | **PSG envelope names** are `fTone_NN`, not `sTone_NN` | `KeyError` (the probe's first crash) | a namespace in `resolve_const`, **plus (f)** |
| f | **PSG envelope BODIES differ from S3K's at the same number.** S2 `fTone_01` = `zPSG_Env1` = `0,0,0,1,1,1,2,2,2,...,7` (`s2.sounddriver.asm:3736`). The engine's id 1 is S3K `VolEnv_00` = `[2, rest]` (`tools/gen_sound_tables.py` `_PSG_VOL_ENVS`). `fTone_02` happens to match (`0,2,4,6,8,$10`). | **Silent wrong timbre.** Renaming `fTone` to `sTone` makes the converter accept ids 01/02/03/08 with no warning, because those S3K ids exist. Only `$0B` and `$00` warn. | Import S2's 13 envelopes as **new engine envelope ids** (`gen_sound_tables.py`) and map `fTone_NN` onto them. Terminator semantics (S2 `$80`) need checking against the engine's control bytes. **Unverified.** |
| g | **S2 DAC enum** (`dKick $81, dSnare $82 ... dMidTom $8C, dFloorTom $8E`, `_smps2asm_inc.asm:153-158`) | `KeyError` / unmapped | enum + a per-song `dac_remap` |
| h | **Inline voice bank** (`smpsHeaderVoice EHZ_Voices`), where HCZ2 used S3K's universal bank | `emit_patch_table` only reads the S3K driver's UVB | parse `_parse_vc_blocks` from the song's own `<ZONE>_Voices:` label. The helpers exist; only the entry point is UVB-specific. |

Two fidelity notes the converter prints (not breaks): CPZ's `smpsAlterNote $C0` (-64) is clamped
to -63 by the engine's single-step detune range, and different-pitch `smpsNoAttack` ties re-attack
(the known v1 gap HCZ2 also has).

### Probe results (commands and outputs)

```
python3 docs/research/2026-09-25-region-music/s2_probe.py
== EHZ: song blob 2522 B, 9 channels, tempo_mod $62; voices in bank 9, used $00..$08 -> patches 288 B
   DAC ids used (1-based): $01 $02 $0C $0E   fTone ids: {03: 6, 01: 2, 02: 12, 0B: 2, 08: 2}
   converter warnings: 2x sTone $0B has no imported PSG envelope; 2x sTone $00 ...
== CPZ: song blob 3611 B, 9 channels, tempo_mod $12; voices in bank 6, used $00..$05 -> patches 192 B
   DAC ids used (1-based): $01 $02   fTone ids: {02: 1}
   converter warnings: 2x smpsDetune -64 ... clamped to -63
```

The DAC tracks' reachable blocks (walked from `EHZ_DAC` / `CPZ_DAC`): EHZ uses kick 25, snare 27,
mid tom 7 and floor tom 7; CPZ uses kick 22 and snare 26. CPZ is therefore the easier song: its
only PSG envelope is the one that matches, and it needs no toms.

**Does it assemble into the sound blob? Yes, measured.** Adding a song id was refused, and that
refusal is a finding (see "sigil hardcodes the song count" under Q2). So the probe
**swapped the two S2 songs into the existing DEBUG slots**: EHZ into DrumTest's slot (id 2, with
its own patch bank) and CPZ into HCZ2's (id 3). It then pointed `SoundTest_BootPing` at id 2 and
built config-A to scratch:

```
sigil build --aeon . --native --config-a -o cfga_s2.bin --emit-lst cfga_s2.lst
built: config_a native ROM, crc=fa973579 len=849008          (baseline, unmodified: crc=afd451d5 len=849120)
```

The ROM read back through `SongTable`/`SongPatchTable`:

```
EHZ song     lma=0xbbb09 len=2522 match=True bank=0x17
CPZ song     lma=0xbc4e3 len=3611 match=True bank=0x17
EHZ patches  lma=0xbd3bf len=288  match=True bank=0x17
CPZ patches  lma=0xbd2ff len=192  match=True bank=0x17
```

All four are byte-identical to the converter's output and share the engine-table head's bank.

**Does the driver sequence them? Yes, measured headlessly** with
`docs/research/2026-09-25-region-music/keyon_census.py`. It boots an `oracle-aether` subprocess
(not MCP) and puts the Z80 YM-port watch from `tools/song_load_mid_drum_witness.py` (`YmTap`)
over the YM ports. It counts key-on writes to register `$28` per channel and DAC writes to
`$2A`/`$2B` over 600 frames:

| ROM, leg | key-ons (600 frames) | `$2A` writes | `$2B` |
|---|---|---|---|
| baseline, boot autoplay (Moving Trucks), **positive control** | FM1 43, FM2 43, FM3 71, FM4 61, FM5 38, FM6 37 = 293 | 602 | none |
| baseline, after START (stop), **negative control** | **0** | 601 | none |
| baseline, after UP (HCZ2) | FM1-5 = 197 | 87,432 | `$80` |
| probe, boot autoplay (**S2 EHZ**) | FM1 59, FM2 26, FM3 26, FM4 7, FM5 24 = 142 | 74,005 | `$80` |
| probe, after UP (**S2 CPZ**) | FM1 32, FM2 24, FM3 20, FM4 20, FM5 20 = 116 | 73,208 | `$80` |

The negative control reads zero, so the counter can fail, and the positive control reads a song
we know plays. **Key-on counts are LOWER BOUNDS:** the watch's hit ring dropped between 12,699 and
99,964 hits per window, which is the DAC stream overrunning it. Non-zero against zero is the
claim, not the exact number. PSG writes were not counted. The run was repeated from the committed
script copy with identical output.

**What this does NOT show: how either song sounds.** Tempo, octave, vibrato depth and voice
timbre are all **TAGGED FOR THE OWNER'S EARS**, ideally A/B against real Sonic 2 on the same
emulator (the direct measure-against-the-reference case). Two known confounds to disclose at
that listening test: the owner's open "dull and lifeless" timbre report on the existing imports
(`docs/DEFERRED_WORK.md`, the Moving Trucks/HCZ2 listening note, undiagnosed, shared-cause
suspected), which S2 songs will almost certainly inherit, and the frontend's `model1-va0-va2`
chip model.

### Fidelity risk, ranked

1. **PSG envelopes (EHZ): high, and silent today.** Fix (f) is required before EHZ can be judged.
2. **Drums: high for EHZ, medium for CPZ.** The engine's kick and snare are **S3K's** samples
   (`games/sonic4/data/sound/dac_samples.emp`, LS-7 note), and S3K's drums are not Sonic 2's.
   Sonic 2's own drums ship as WAVs (`s2disasm/sound/DAC/Kick.wav` 8,250 Hz 1,320 frames,
   `Snare.wav` 24,000 Hz 3,654, `Tom.wav` 13,500 Hz 3,612). The S2 driver's `dMidTom` is Tom at
   x1.70 and `dFloorTom` is Tom at x1.10 (`s2.sounddriver.asm`, `zDACMasterPlaylist`).
   `tools/import_s3k_dac.py`'s `wav_to_raw8` already does exactly this resample-with-pitch at
   the fixed 18,356 Hz. **Sizes (derived, not built):** kick ~2.9 KB, snare ~2.8 KB, mid tom
   ~2.9 KB, floor tom ~4.5 KB, about 13.1 KB in all. The shared drum bank has **7,014 B** free
   (32,768 - 25,754 of `.pcm`), so kick and snare fit and the toms do not. The blip bank's
   window holds one 2,880 B sample and ~29.9 KB of padding. Each DAC id carries its own
   `{bank, ptr, len}` triple, so a sample in that window *should* play, but that is **unverified**.
3. **Tempo, pitch, modulation: low.** These are the include's own exact conversions, and the
   engine's tempo model is S3K's exactly.
4. **FM voices: low.** Same macros, same verified converter.

---

## Q2. What does it take to play music during gameplay at all?

### The controller's beliefs, checked

* "No canonical shape plays music in play; only `--config-a` calls `Sound_PlayMusic`":
  **TRUE.** The only call sites are `games/sonic4/debug/game_debug.emp` (`Debug_MusicToggle`,
  `SoundTest_BootPing`), bound only when `SOUND_DEBUG_HOTKEYS == 1 && SOUND_DRIVER_ENABLED == 1`
  (`games/sonic4/config/game.emp:176-178`). build.sh refuses the old env-var recipe (memory
  note, and `CLAUDE.md` "Shapes").
* "No region/zone music switching exists anywhere": **TRUE, and it was deliberate.**
  `engine/structs.emp`'s Region header says: "NOTHING ELSE: no music/sound-bank/PLC/lookahead/flags.
  Those were Sec fields deleted on 2026-09-04 for having no reader; a field is added the day a
  consumer wants it." This parcel is that day.

### It is none of the three the brief offered

It is **not a new build profile**, not a clip-manifest flag, and not "turning on" the hotkeys
profile:

* The hotkeys profile is the wrong vehicle. It requires `DEBUG=1` (`game.emp:15`), it is
  unfrozen and off-canonical, and its boot hook autoplays Moving Trucks, which would fight the
  region's song.
* The sound driver, the sequencer and the DAC path are **already in every sound-on shape**,
  which is why gameplay SFX play in `s4.bin`. What is missing is a caller.
* The caller is **region data**. A region row names a song, and the crossing requests it (Q3).
  The shipped OJZ act's rows name no song, so `s4.bin` / `s4.debug.bin` keep playing no music,
  now by data rather than by the absence of code. The clip act's generated rows name EHZ and
  CPZ, so the clip build plays them. No profile and no build flag are involved.

### What it costs

| Resource | Cost | Evidence |
|---|---|---|
| 68k RAM | 2 bytes (`Music_Current`, `Music_Pending`) | design |
| Z80 RAM | 0 (music state is already allocated in the one driver blob every sound-on shape carries) | config-A and canonical differ only by 68k debug modules (map.toml's config_a line) |
| 68k time, per frame | a `tst.b` when nothing is pending | design |
| 68k time, on a switch | one `Sound_PlayMusic`: a masked bus-held slot probe, then one bracketed 6-byte param post. **Posted from a service call, not inside the crossing**, because `Sound_PlayMusic` *spins* while a previous load is unconsumed (`engine/sound/sound_api.emp`, the `.await_slot` loop), and the crossing frame already carries `Effects_InstallPreset` (~19,332 cycles worst, per `Region_Resolve`'s note) plus the background repaint. | `sound_api.emp` `Sound_PlayMusic` |
| Z80 time | the sequencer tick plus DAC streaming while a song plays. It is **the same load config-A already runs** (music + DAC + SFX on the B hotkey); gameplay adds nothing new in kind. | |
| ROM, songs | ~6.6 KB (EHZ 2,522+288, CPZ 3,611+192, plus 2x4 B of tables and pads) | probe |
| ROM, drums | 0 (reuse the S3K drums, wrong timbre) up to ~13.1 KB (Sonic 2's own) | Q1 |
| **Phase-bank room** | songs must share the one 32 KB window with the engine tables and SFX (co-residency: `games/sonic4/data/sound/mt_bank.emp`'s five `ensure(bankid(...) == bankid("MovingTrucks_Bank_Start"))`). **Measured in config-A:** sound data spans `$B8000`-`$BDBAC` = 23,468 B, so **~9.3 KB is left** (`SongTable $BD550`, SFX `$BD568`-`$BDBAC`, then 68k code). After EHZ+CPZ: **~2.7 KB in the DEBUG shapes.** The plain shape (no HCZ2/DrumTest) derives to ~16.0 KB free now and ~9.4 KB after. | listing of the baseline config-A build |
| DMA / DAC | Drums are designed to survive DMA ("1B DMA-survival", a ~200-sample / ~11 ms ring lead; `docs/ENGINE_ARCHITECTURE.md` sound section). The crossing's BG repaint DMA is the heaviest DMA this act does. **Unverified with music playing.** The clip is the first build where drums play *during gameplay DMA*, so it is also the first place the owner can hear LS-13's 60 Hz controller-read bus hold (~130 µs, ~2.4 DAC samples per frame). That row's fix was explicitly deferred "until a 60 Hz artefact is actually audible on the drums, which is evidence only he has" (`docs/DEFERRED_WORK.md`, LS-13). **TAGGED FOR THE OWNER'S EARS.** | |

### Owner rulings and standing constraints found

* **d-20 / PITCH-FORMAT** (`docs/decisions.jsonl` d-20-answered, 2026-08-26): "the music driver
  changes to storing musical pitch now, **before the soundtrack grows**". It is parked
  (empyrean `docs/OVERSEER-LOG.md`, 2026-09-06 seraph cleanup, `QUEUE-PARKED`). **Adding two
  songs is the soundtrack growing.** The songs are converter-generated, so a later format change
  re-runs the converter rather than re-authoring anything. Still, **the owner should know this
  parcel grows the soundtrack ahead of his stated order.**
* **LS-11 / LS-12** (the music-start spin lockup and the DMA guard on the tick path): both
  CLOSED 2026-09-07 (`docs/DEFERRED_WORK.md` rows). This matters because music in gameplay makes
  those paths reachable in a build the owner plays, not just in a debug profile.
* **"No music in canonical shapes"** is a fact about wiring (memory note), not an owner ruling.
  No decision record forbids music in play.

### Two structural findings that are not the owner's call but gate the build

1. **sigil hardcodes the song count.** `sigil/crates/sigil-harness/src/seam2.rs:1401`,
   `let song_count = if debug { 3 } else { 1 };`, feeds the mt_bank drift guard. Adding ids 4/5
   in aeon alone fails the build: `mt_bank.emp:125: SONG_COUNT drifted from games.sonic4.sound_ids: 5`
   (measured). The same carrier also fixes the mt_bank region at `size = 0x79F9`. **Any new song
   needs a sigil change.** The clean one is for sigil to derive the count from
   `games/sonic4/config/sound_ids.emp` rather than a literal. This is a cross-repo ask, and the
   aeon/sigil pairing rules apply. Flagged, not asked: the controller routes it.
2. **The phase bank is the soundtrack's ceiling.** At ~2.7 KB free in DEBUG after these two
   songs, the next zone's song will not fit. The real fix is songs in their own banks, which
   means the sequencer's window-relative engine tables must be reachable from a song bank
   (duplicated per bank, or moved to Z80 RAM). That is **L** and out of scope, and it is named
   so nobody discovers it by a failed build three songs from now.

---

## Q3. The switch

### Where the crossing event is

`Parallax_CheckBoundary` (`engine/level/parallax.emp`, its `.rescan` slow path) is, in its own
words, "the ONE place the engine notices 'the camera entered a new region'". Its only runtime
caller is the level state's per-frame step (`games/sonic4/test/ojz_scroll_test.emp:1244`). The
same slow path already runs in three situations, and the music switch gets all three for free:

* **act start:** `Parallax_Init` writes the sentinel rectangle `$FFFF0000`, so the first call
  always rescans and installs the start region. The start region's song therefore plays at act
  load with no separate "level music" call.
* **a walked crossing:** the camera centre (`Camera_X + CAM_SCREEN_HALF_W`) leaves the cached
  rectangle. For `s2_ehz_cpz` the crossing is at **x = 11,168**, the tunnel's middle
  (`games/sonic4/data/clips/s2_ehz_cpz/clips.json`, `crossing_overrides`).
* **the DEBUG warp:** step 7 re-arms the sentinel (`ojz_scroll_test.emp:1835-1837`).

The background switch (`rg_bg_tiles`, `BG_Stream_Update`) and the palette/parallax snap already
hang off this path, so music composes with them by construction.

### The smallest clean mechanism

**Data: two bytes appended to `Region`** (26 to 28 bytes, following the regions-part-2 precedent
of appending so that no offset moves):

```
rg_song:   u8 = 0,   // $1A: 0 = no change; 1..SONG_COUNT = this region's song;
                     //      $FF = fade the music out (a "leaving" row)
rg_music:  u8 = 0,   // $1B: how the song starts: 0 = cut; 1 = fade in (only if the owner picks it)
```

Why `Region` and not `EffectsPreset`: the preset is the *visual* identity record, and
backgrounds, the precedent for per-region non-effect data, went onto `Region`. Why a song **id**
and not a pointer: `Sound_PlayMusic` takes an id, and ids are the game's authority
(`sound_ids.emp`). `0 = no change` is what keeps every existing OJZ row (every `ojz_region(...)`
row) compiling unchanged through the `= 0` default, and it is what makes the canonical
behaviour "no music" by data.

**Engine: request on the slow path, post from a service.**

* In `.rescan`, after `Effects_InstallPreset`: `move.b Region.rg_song(a0), d0`; if non-zero and
  `!= Music_Current`, store it in `Music_Pending` (with `rg_music`'s bit). That is about 8
  instructions, compiled only when `SOUND_DRIVER_ENABLED == 1`. `games/demo` has no regions and
  never calls this proc, so it is unaffected.
* A `Music_Service` called once per frame right after `Parallax_CheckBoundary`. If nothing is
  pending it exits after one test. Otherwise it posts `Sound_PlayMusic` only when `MUSIC_SLOT`
  is already clear, which removes the spin from the frame, and sets `Music_Current`. The fade
  options (Q4) are sequenced here: post the fade, then wait for `Sound_IsFading` to clear before
  the play.
* `Music_Current` is cleared at act load (beside the `Parallax_Init` sentinel), so reloading an
  act restarts its song. It is **not** cleared by the DEBUG warp, so warping within a zone keeps
  the song playing, and warping across zones switches it.

**Identity is the song id, compared against what is playing,** not the region pointer. So two
rows naming one song (an L-shape, or a zone split into several rows) never restart it. This is
the same rule the background switch uses ("identity is the POINTER: two rows naming one blob
never re-upload").

**Generator:** `tools/clip_rom_bake.py`'s `_region_rows_text` emits `rg_song` from a new
per-clip `"music"` field in `clips.json`, spelled as a `SONG_*` name. `_parse_rows` and
`tools/region_table.py`'s offset-comment cross-check learn the two fields.

### Respawn, backwards, and dithering

* **Respawn:** this engine has no death yet ("this engine has no death, so a body under the
  terrain falls forever", `clips.json` `unbounded_fall`). The rule above gives an act reload a
  restarted song (Sonic 2 behaviour). A future checkpoint respawn *without* a reload goes
  through the crossing path like a warp, so it keeps or switches by region.
* **Backwards (CPZ to EHZ):** the rescan resolves Emerald Hill's region, and its song id differs,
  so **EHZ restarts from the top.** Resuming where it left off would need the Z80 to save and
  restore a whole sequencer state per song. The driver has one song slot and `Snd_LoadSong`
  always starts at pattern 0. That is **L**, not recommended now, and the owner may reasonably
  want it later.
* **Dithering:** a player who stops *on* the crossing and moves back and forth a few pixels would,
  with a single crossing line, restart a song on every pass. The mid-tunnel line is only as wide
  as a camera-centre pixel. This is the strongest argument for option D below: making the tunnel
  a **dead band** (rows inside it with `rg_song = 0`) gives 384 px of hysteresis for nothing.

---

## Q4. The feel: DECISION FOR THE OWNER

### Facts every option depends on (measured in the source, not by ear)

* **One song at a time.** The driver has one music slot and one sequencer, and two full songs
  cannot share 6 FM + 3 PSG channels. **A true crossfade (both songs audible together) is not
  possible on this hardware and this driver.**
* **Fade speed.** The fastest fade is one TL step (0.75 dB) per frame, so about 2.1 s to
  silence, which is about -22 dB after half a second (`engine/sound/sound_constants.emp`,
  `FadeRateTable` note; `z80_sound_driver.emp` `FadeRateTable = $01,$11,...,$FF`).
* **The fade does not touch the drums.** Only keyed FM and PSG are faded, and the DAC is
  excluded (`engine/sound/sound_sequencer.emp:556-569`). **During a fade-out, Emerald Hill's kick
  and snare stay at full volume while the melody fades.**
* **A new song starts at full volume**, whatever the fade left behind (`z80_sound_driver.emp:1746-1759`).
* **Time in the tunnel:** 384 px. At the 16 px/frame camera cap that is ~24 frames (0.4 s). At
  6 px/frame, a normal run, it is ~64 frames (~1 s). While walking it is several seconds.

### Options

| | What he sees and hears | Build cost |
|---|---|---|
| **A. Hard cut at the crossing** (mid-tunnel, x 11,168) | Emerald Hill stops mid-phrase and Chemical Plant starts from bar 1 on the same frame the palette and background snap, while only the tunnel is on screen. Standing on the line and wiggling restarts a song on every pass. | **S** (the mechanism with no fade logic) |
| **B. Fade out, then start** | Emerald Hill's melody dims across the tunnel **while its drums keep going at full volume**, then Chemical Plant cuts in at full volume at the crossing. At top speed the fade has only reached about -9 dB when the cut comes. | **M** (A + a "leaving" row + the fade sequencing in `Music_Service`). Making the drums fade too is a separate Z80 change: **S-M**, and unverified. |
| **C. "Crossfade"** (fade out, then the new song fades in) | As B, then Chemical Plant rises from silence over ~2 s. It is sequential, not overlapping (see above). | **M+** (B + `Sound_FadeIn` after the play. `sound_api.emp` documents "use right after `Sound_PlayMusic`" but also a one-transport-op-per-frame contract, so the ordering needs a witness.) |
| **D. Change at the tunnel exit** (recommended) | Emerald Hill plays all the way through the tunnel. Chemical Plant starts from bar 1 as the camera comes out into Chemical Plant (camera centre at x 11,360). Going back, Emerald Hill restarts as you come out on the Emerald Hill side. **The visuals still switch mid-tunnel, where nothing of either zone is on screen.** | **S** (A's mechanism + splitting each zone's region row at the tunnel edge: the inner halves carry `rg_song = 0`). Crossing the inner split re-runs `Effects_InstallPreset` for an identical preset, one extra install on that frame, which the L-shape rule already allows. |
| **D+fade** | As D, but Emerald Hill's melody fades while you are in the tunnel (drums still at full volume, see B). | **M** |

### Recommendation: **D, change at the tunnel exit, hard cut.**

The reason is the tunnel's job. The owner built it to hide the switch ("the tunnel to transition
has to be like an FG hiding the bg"), and **the ear is the one sense the tunnel cannot hide
anything from**. A cut in the middle (A) lands while the player is still in a dark corridor with
no new zone in view, so it reads as a glitch. At the exit, the new music arrives with the new
zone, the way a Sonic zone change reads.

D is also the cheapest option that has **hysteresis**: the tunnel becomes a 384-px dead band, so
standing on a line cannot thrash the music. And it avoids the drums-stay-loud artefact every
fade option carries.

Its cost is that Emerald Hill ends mid-phrase with a hard cut. If that grates, D+fade is the
upgrade, but it should wait until the owner has heard what "melody fades, drums don't" sounds
like.

**Question for the owner, as it would be put to him:** *"When you run from Emerald Hill into
Chemical Plant, when should the music change? (A) The moment the screen switches in the
middle of the tunnel. (B) Emerald Hill fades while you are in the tunnel, and Chemical Plant cuts
in at the middle. The drums don't fade, only the melody. (C) Like B, and Chemical Plant also
fades in. (D) Emerald Hill keeps playing through the tunnel and Chemical Plant starts as you come
out (RECOMMENDED: the music changes when the new zone appears, and wiggling at the line can't
flip it back and forth). D+fade is D with Emerald Hill's melody fading in the tunnel. And either
way, going back left restarts Emerald Hill from the top. Do you want that, or should it resume
where it was? (Resume is a big driver job.)"*

---

## Staged build plan

"Moves canonical bytes" means `s4.bin` / `s4.debug.bin` change. That is routine here, but it is
named for the landing check. S2CLIP-only changes live in the throwaway-baked tree and move nothing.

| Step | What | Size | Moves canonical bytes? |
|---|---|---|---|
| 0 | **sigil:** derive `SONG_COUNT` for the seam-2 carrier from `sound_ids.emp` instead of the literal at `seam2.rs:1401` (and revisit the `0x79F9` region size). Cross-repo; the controller routes it. | S (sigil) | no |
| 1 | **Converter S2 mode:** `SourceDriver=2` in `smps_import.py` (tempo, PSG +12, `nMaxPSG`, ModSet, `fTone` namespace, S2 DAC enum, song-local voice bank). Tests red-first against the two crashes and the silent tempo and octave errors the probe showed. A generator script beside `song_hcz2.py`. | S-M | no (tools only) |
| 2 | **S2 PSG envelopes** as new engine envelope ids (`gen_sound_tables.py`), with `fTone_NN` mapped to them. Required for EHZ. | S | **yes** (Z80 table blob, every sound-on shape) |
| 3 | **Drums**, the owner's pick: (a) map onto the S3K drums, 0 B, wrong drums; or (b) import S2 kick/snare/2 toms, ~13.1 KB, which needs the blip window or a new bank and a witness that a sample there plays. | S (a) / M (b) | (b) **yes** |
| 4 | **Songs join the bank** as ids 4/5 in plain and debug (the owner looks at *plain* S2CLIP, and plain carries only Moving Trucks today). Leaves ~2.7 KB free in DEBUG. Needs step 0. | S | **yes** (+~6.6 KB in every sound-on ROM) |
| 5 | **Engine switch:** `Region.rg_song`/`rg_music` (26 to 28 B), `Music_Current`/`Music_Pending`, the slow-path request, `Music_Service`. OJZ rows unchanged via defaults. Witness: canonical still issues **zero** music requests (the key-on census reads 0 across a walked OJZ crossing). | M | **yes** (Region stride + code; behaviour unchanged) |
| 6 | **Clip data:** `"music"` per clip in `clips.json`, the tunnel-edge row split for option D, and `clip_rom_bake.py` emits it; `test_clip_*` derive the split from the corridor. | S | no (S2CLIP tree only) |
| 7 | **Witness + listening:** a scripted headless run across the crossing and back in `s4.s2clip.bin` (key-on census before, inside and after the tunnel; song id per window), then **the owner's listening test**, A/B against real Sonic 2. | S + owner | no |
| later | Resume-on-return (per-song sequencer save/restore), songs in their own banks, drum fade. | L / L / S-M | yes |

Steps 1-3 are independent of 5-6 and can run in parallel. 4 needs 0. 7 needs all of them.

---

## Contradictions of the brief, stated plainly

* "Sonic 2 final uses Saxman-compressed songs": true of the Sonic 2 *ROM*, irrelevant to us.
  The import reads the uncompressed smps2asm sources.
* "An SMPS import path exists and was used for S3K": true, and it is more reusable than "S3K
  only" suggests. The macro include is shared, so the S2 to S3K rules are already written down.
* "Adding a song is an aeon change": **false today.** sigil's seam-2 carrier hardcodes the count.
  Measured by the refused build.
* "Turning music on in gameplay" is not a profile or a flag. It is data (region rows) plus about
  one screen of engine code, and the canonical ROM stays silent by data.

## Research scope, stated so it is not mistaken for complete

This parcel answered the brief's four questions from this repo, sigil, s2disasm and skdisasm. It
did **not** run CLAUDE.md's full design checklist: the other reference disassemblies (S.C.E.,
Batman & Robin, Vectorman, Gunstar Heroes, Alien Soldier, Thunder Force IV, Ristar) and the online
sources. The one directly relevant precedent it did not read is how S3K and S.C.E. change music
*inside* an act (Angel Island's mid-act fire transition, act-1-to-act-2 handoffs), which is
exactly the feel question. That research belongs at the start of steps 5 and 6.

## Research done at step 5 (2026-09-25, the gap named above)

How S3K and S.C.E. change music inside an act, and whether they avoid re-requesting the playing
song. **Neither dedups.** `Play_Music` writes the Z80 mailbox unconditionally (skdisasm
`sonic3k.asm:1470`; S.C.E. `Sound/Functions.asm:46`), and the driver always stops and reloads
(`zPlayMusic` -> `zPlayMusic_DoFade` -> `zBGMLoad`; Flamedriver the same). Their in-act changes
fire once, from events: a seamless act-1-to-2 change comes from the in-level title card calling
`Restore_LevelMusic` (sonic3k.asm:62239, looked up by `Apparent_zone_and_act`), bosses post
`cmd_FadeOut` then their song, and AIZ1's fire transition changes no music at all (its only
camera-X trigger, `Events_fg_5` at sonic3k.asm:38923, starts the fire). S.C.E. has no working
seamless act-2 music change. **Adopted:** a 68k-side current-song byte (`Current_music`'s role;
the engine's is `Music_Current`). **Rejected:** unconditional posting, because a region edge is
crossed repeatedly (every pass would restart the song), and per-zone camera-X event code, which
the region row replaces with data. As built in step 5, the compare lives in `Music_Service`, not
in the crossing, and `rg_music` was dropped (hard cut ruled); see `docs/DEFERRED_WORK.md`
`## S2CLIP-REGION-MUSIC`, "Step 5".

## Probe hygiene

The probe's `mt_bank.emp` / `sound_ids.emp` / `game_debug.emp` edits were reverted with
`git checkout`. The four generated `.bin` files (gitignored by `*.bin`) were deleted. The scratch
ROMs lived in the session scratchpad, not the tree. To reproduce the assemble test: run
`s2_probe.py --write`, apply the slot swap described under Q1 by hand, build config-A to a scratch
path, then run `keyon_census.py --rom <it> --lst <it> --press up`.
