# Sound Phase 5a — Core SFX Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the driver from "plays a demo song" into "the game makes sounds." Deliver the classic-faithful channel steal/restore SFX engine — override-flag steal, clean restore (no register snapshots), dynamic-among-eligible voice selection, per-SFX priority, ducking — plus the S3K SFX transcoder, `Sound_PlaySFX` API + Z80 dispatch, and wiring of the existing no-op game seams. Jump/ring/spindash/dash/roll/skid (plus death/ring-loss) all sound, using real Sonic 3 & Knuckles SFX, with the music's lead and bass never dropping out.

**Architecture:** A parallel SFX interpreter (`engine/sound_sfx.asm`) layered over the music sequencer, sharing the chip-writer code. A fixed array of 7 `SfxChannel` structs (the stealable set: FM3/4/5 + PSG1/2/3 + noise) at $1D00, each reusing the per-frame `ModUpdate`/cursor machinery. `Sfx_Frame` runs Z80-autonomously each frame **after `Sequencer_Frame`** so SFX hardware writes land last and own the channel. Steal sets a new `SCF_SFX_OVERRIDE_B` bit on the music `SeqChannel` — the music interpreter keeps advancing its cursor (so the song never desyncs) but its chip writes are gated off; restore clears the bit, re-uploads the music FM patch, and force-re-keys a held note. **Design-for-C / build-for-A:** the SFX format + hooks are laid out so deferred 5b/5c capabilities (continuous held loops, distance attenuation, FM6-as-SFX, deeper stealing) are purely additive.

**Tech Stack:** Z80 + 68000 assembly (AS Macro Assembler) + Python transcoder. No asm unit-test framework — every asm task verifies by `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe` (exit 0, advisory s4lint warnings OK), Exodus MCP (`emulator_get_channel_states`, `emulator_z80_read`/`emulator_z80_registers`, register reads) to confirm steal sets the override + loads the SFX voice and restore re-uploads the music patch + re-keys with no silence gap, and `emulator_vgm_start`/`vgm_stop` → `vgm2wav` rendered audio to confirm SFX audible AND music lead/bass intact through steal→restore + ducking dips/ramps. Python transcoder tasks verify via real `pytest`. Honor `CODING_CONVENTIONS.md` (`struct`/`endstruct`, `phase`/`dephase` mirrored by build-time RAM asserts, `function` for compile-time math, `.s`/`.w`/`.l` sized branches, no `mulu`/`divu`, PascalCase routines, ALL_CAPS constants, `.lowercase` locals).

**Spec:** `docs/superpowers/specs/2026-06-20-sound-phase5a-sfx-engine-design.md`
**References:** S2 `s2disasm/s2.sounddriver.asm` (PlaybackControl bit2, `zSFXPriority`, `zStopSoundEffects`→`zSetVoiceMusic`); S3K `skdisasm/Sound/Z80 Sound Driver.asm` (`set 2,(hl)` L2003, `cfStopTrack` L3490-3511) + `skdisasm/Sound/SFX/*.asm` (the SFX source set); Flamedriver `Sonic-Clean-Engine-S.C.E.-/Sound/Flamedriver.asm` (`bitSFXOverride`); `tools/song_packer.py` + `tools/zyrinx_port.py` (`translate_voice`, `emit_patch_bank_asm`) + `tools/zyrinx_player.py` (native emitter pattern) for the transcoder; `skdisasm/Sound/_smps2asm_inc.asm` (the SMPS coord-flag grammar).

---

## File Structure (what each file owns)

- `sound_constants.asm` — the `SfxChannel` struct (+ `_len` assert), the SFX RAM region (`SND_SFX_BASE`=$1D00, the 7-slot array, the SFX queue, scratch) carved from the free $1D00..$1EFF block with `> SND_REQ_BASE` overflow asserts, `SCF_SFX_OVERRIDE_B=6` (+ mask + extended sync assert), the `SFX_ELIGIBLE` eligibility table constants, the SFX-header field offsets, the priority constants, the symbolic `SFXID_*` id equates, and the duck-level tunables.
- `engine/sound_sfx.asm` — **NEW FILE.** `SfxDispatch` (queue enqueue + priority gate → eligible-voice select → steal → init `SfxChannel`), `Sfx_Frame` (per-frame `SfxChannel` interpreter, run after `Sequencer_Frame`), `Sfx_Steal`/`Sfx_Restore` (set/clear override, key-off, load SFX voice / re-upload music patch + PSG3-tone save-restore + held-note re-key), `Sfx_StopAll`, the queue drain, the duck-level ramp. Reuses `ModUpdate`/`Sequencer_Channel` for the SFX cursor and the `Fm_*`/`Psg_*` writers for chip output. Included inside the phase-0 blob after `sound_sequencer.asm`.
- `engine/sound_sequencer.asm` — the override gate added to `ModUpdate` (after the FM gate) + the 4 `Seq_Hook*` write entry points + `Seq_Op_RegDelta`/`Seq_Op_NoteRaw` direct YM writes; `Sequencer_Frame` gains a `call Sfx_Frame` tail (placed so SFX runs even with no music).
- `engine/z80_sound_driver.asm` — `SndDrv_PollMailbox` gains the `SND_REQ_SFX`→`SfxDispatch` block (before the SAMPLE block); the init clears the SFX RAM; `.music_stop`/`Snd_LoadSong` reconcile overrides via `Sfx_StopAll`/`Sfx_Reconcile`; the new file is `include`d in the blob.
- `engine/sound_api.asm` — `Sound_PlaySFX` (mirror `Sound_PlaySample`), with 68k-side ring L/R stereo alternation.
- `engine/objects/animate.asm`, `engine/player/*.asm`, `engine/objects/rings.asm`, `engine/game_loop.asm` — the game seams wired to real `Sound_PlaySFX` calls + a DEBUG SFX-trigger hotkey.
- `tools/sfx_transcode.py` — **NEW.** Parses skdisasm `Sound/SFX/*.asm`, reuses `translate_voice`/`emit_patch_bank_asm`/`pack_song`, emits the SFX blobs (`SfxHeader` prefix + event-list) + `data/sound/sfx/sfx_table.asm`. `tools/test_sfx_transcode.py` — its pytest.
- `data/sound/sfx/` — the generated SFX blobs + per-SFX patch banks + `sfx_table.asm`, wired into `main.asm` + the build.

---

## Task 1: RAM + cycle-budget sanity spike (de-risk before building)

**Goal:** confirm a 7-slot `SfxChannel` array + the SFX queue/scratch fit the free $1D00..$1EFF gap below the mailbox, and `Sfx_Frame`'s worst case fits the per-frame Z80 budget. Throwaway doc.

**Files:** Create `tools/sfx_budget_phase5a.md` (the measurement + verdict).

- [ ] **Step 1: RAM fit.** Document the Z80 map from `sound_constants.asm:670-676` + the computed gaps: song buffer ends `SND_SONG_BUF + SND_SONG_BUF_SIZE = $1B00+$200 = $1D00`; mailbox base `SND_REQ_BASE = $1F00`. So the free block is exactly **$1D00..$1EFF = 512 bytes**. The SFX array = 7 × `SfxChannel_len`. `SfxChannel` reuses the full 39-byte `SeqChannel`-compatible interpreter prefix (so `ModUpdate`/`Sequencer_Channel` walk it unmodified) plus 7 bytes of SFX bookkeeping (priority, voice-bank ptr, owned-music-route, saved-PSG3-note, kind) = **46 bytes** (the exact size Task 2 defines + asserts). 7×46 = 322 B. Queue: 3 entries × 2 B (id + priority) + head/tail/count = ~9 B. Duck-level scratch ~4 B. Total ≈ 335 B « 512 B. Record the verdict: **fits with ~177 B headroom** (leaves room for 5b growth).
- [ ] **Step 2: Cycle budget (reuse the phase3 method).** One frame at 59 Hz = `Z80_CLOCK_HZ / SND_FRAME_HZ = 3,579,545 / 59 ≈ 60,670` cycles. From `tools/cycle_budget_phase3.md`: the DAC loop spends ~168 passes/frame and the music `Sequencer_Frame` worst case is ~5.4k cyc. `Sfx_Frame` walks 7 slots; an active SFX slot runs the same `ModUpdate`/cursor path as a music channel (~900 cyc worst, mostly a patch-reload frame), inactive slots cost one `bit SCF_ACTIVE_B` test (~20 cyc). Worst realistic case ≈ 3 concurrent SFX × ~900 + 4 idle × ~20 ≈ 2,780 cyc. The duck ramp is ~6 carrier-TL writes/frame ≈ 200 cyc. Total `Sfx_Frame` ≈ 3.0k cyc. FM(5.4k) + SFX(3.0k) + DAC ≈ well under 60k. Write the arithmetic.
- [ ] **Step 3: Verdict + fallback.** If it fits (it does) → proceed with full per-frame `Sfx_Frame` every frame. Documented fallback if a future SFX set exceeds budget: even/odd-frame split of the 7 slots (mirror phase3's lever). Record the chosen approach (full per-frame).
- [ ] **Step 4: Commit.**
```bash
git add tools/sfx_budget_phase5a.md
git commit -m "spike(sound): Phase 5a SfxChannel RAM fit + Sfx_Frame cycle budget"
```

---

## Task 2: SfxChannel struct + RAM allocation + constants

**Goal:** define the `SfxChannel` struct, allocate the 7-slot array + queue + scratch at $1D00, add `SCF_SFX_OVERRIDE_B=6` (+ mask + extended sync assert), the `SFX_ELIGIBLE` table constants, the SFX-header offsets, priority constants, the duck tunables, and the symbolic `SFXID_*` equates. Build-assert RAM fits. **Regression: no behavior change — pure equate/struct additions.**

**Files:** Modify `sound_constants.asm`.

- [ ] **Step 1: Add `SCF_SFX_OVERRIDE_B=6` + mask + extend the sync assert.** In `sound_constants.asm`, the current free bits are 6 and 7 (last used = `SCF_REKEY_B=5`). After the `SCF_REKEY_B = 5` line (608 in context, before the masks at 658-663), add the bit number; add the mask after `SCF_REKEY = 1<<SCF_REKEY_B` (663); extend the sync assert at 666. Replace this exact block:
```asm
SCF_ACTIVE      = 1<<SCF_ACTIVE_B
SCF_KEYED       = 1<<SCF_KEYED_B
SCF_IS_FM       = 1<<SCF_IS_FM_B
SCF_IS_PSG      = 1<<SCF_IS_PSG_B
SCF_IS_DAC      = 1<<SCF_IS_DAC_B
SCF_REKEY       = 1<<SCF_REKEY_B

        ; the _B bit numbers and the masks must stay tied together.
        if (SCF_ACTIVE <> 1<<SCF_ACTIVE_B) || (SCF_KEYED <> 1<<SCF_KEYED_B) || (SCF_IS_FM <> 1<<SCF_IS_FM_B) || (SCF_IS_PSG <> 1<<SCF_IS_PSG_B) || (SCF_IS_DAC <> 1<<SCF_IS_DAC_B) || (SCF_REKEY <> 1<<SCF_REKEY_B)
          error "SCF_* masks and _B bit numbers are out of sync"
        endif
```
with:
```asm
; Phase 5a: SFX channel-steal override. When SET on a music SeqChannel, the music
; interpreter keeps advancing its cursor (so the song never desyncs) but every
; chip-write site early-returns — an SfxChannel owns this physical voice. Cleared
; on SFX restore (which also re-uploads the music patch + re-keys a held note).
; bit7 stays free.
SCF_SFX_OVERRIDE_B = 6

SCF_ACTIVE      = 1<<SCF_ACTIVE_B
SCF_KEYED       = 1<<SCF_KEYED_B
SCF_IS_FM       = 1<<SCF_IS_FM_B
SCF_IS_PSG      = 1<<SCF_IS_PSG_B
SCF_IS_DAC      = 1<<SCF_IS_DAC_B
SCF_REKEY       = 1<<SCF_REKEY_B
SCF_SFX_OVERRIDE = 1<<SCF_SFX_OVERRIDE_B

        ; the _B bit numbers and the masks must stay tied together.
        if (SCF_ACTIVE <> 1<<SCF_ACTIVE_B) || (SCF_KEYED <> 1<<SCF_KEYED_B) || (SCF_IS_FM <> 1<<SCF_IS_FM_B) || (SCF_IS_PSG <> 1<<SCF_IS_PSG_B) || (SCF_IS_DAC <> 1<<SCF_IS_DAC_B) || (SCF_REKEY <> 1<<SCF_REKEY_B) || (SCF_SFX_OVERRIDE <> 1<<SCF_SFX_OVERRIDE_B)
          error "SCF_* masks and _B bit numbers are out of sync"
        endif
```
Also update the `sc_flags` field comment at line 550 to note `bit6=sfx_override`.

- [ ] **Step 2: Add the eligibility model + SFXID_* equates + priority + duck tunables.** After the `CHROUTE_*` block (ends at line 490, `CHROUTE_FM6 must map...` assert) add:
```asm
; ======================================================================
; Phase 5a SFX engine — eligibility, ids, priority, ducking, RAM, structs.
; ======================================================================

; --- SFX channel eligibility (build-time data, spec §4) -----------------------
; Each PHYSICAL voice is either NEVER stealable (lead/bass/DAC) or stealable by an
; SFX. The stealable set sizes the SfxChannel array (3 FM + 3 PSG + noise = 7).
; FM6 is RESERVED in v1 (it is the DAC, or a music FM voice in DAC-off songs);
; opening it to SFX later for DAC-off songs is a one-line table edit (design-for-C).
; The table is indexed by CHROUTE_* and read by SfxDispatch's voice selector +
; the eligibility/kind asserts. SFXEL_NONE = not stealable; SFXEL_FM/SFXEL_PSG =
; stealable, with the kind (FM<->FM, PSG<->PSG dynamic substitution). Noise is its
; own kind (it cannot substitute for a tone PSG and vice versa).
SFXEL_NONE  = 0     ; never stealable (FM1, FM2, FM6, DAC)
SFXEL_FM    = 1     ; stealable FM voice (FM3, FM4, FM5)
SFXEL_PSG   = 2     ; stealable PSG tone voice (PSG1, PSG2, PSG3)
SFXEL_NOISE = 3     ; stealable PSG noise voice (PSGN)

SFX_VOICE_COUNT = 7 ; FM3,FM4,FM5,PSG1,PSG2,PSG3,PSGN — the stealable set

; --- Symbolic SFX ids (spec §9; ids posted to SND_REQ_SFX, disjoint from song ids)
; Values are the S3K source filenames so the transcoder's SfxTable index matches
; (id -> SfxTable[id-1] inside the contiguous SFX-id range; the transcoder densely
; renumbers, but these names are what gameplay refers to). See SfxIdRemap below.
SFXID_RING_RIGHT = $33
SFXID_RING_LEFT  = $34
SFXID_DEATH      = $35
SFXID_SKID       = $36
SFXID_ROLL       = $3C
SFXID_JUMP       = $62
SFXID_SPINDASH   = $AB
SFXID_DASH       = $B6
SFXID_RINGLOSS   = $B9

; --- Per-SFX priority tiers (authored; S3K has none — spec §6). Higher = wins.
; Seeded from S2 zSFXPriority for shared sounds: death/hurt > spindash > skid/roll
; > jump > ring/UI. The transcoder bakes a priority byte into each SfxHeader keyed
; by id; these tiers are the source of that map (mirrored in tools/sfx_transcode.py).
SFXPRI_RING     = $20    ; ring/UI — lowest; never ducks (below SFX_DUCK_THRESHOLD)
SFXPRI_JUMP     = $40
SFXPRI_ROLL     = $60
SFXPRI_SKID     = $60
SFXPRI_SPINDASH = $80
SFXPRI_DASH     = $80
SFXPRI_DEATH    = $C0    ; death/ring-loss — highest
SFXPRI_RINGLOSS = $C0

; --- Ducking (spec §7): a high-priority SFX transiently attenuates the music. A
; global duck-level byte ramps up on duck-eligible SFX and ramps back over N frames
; on SFX end. v1: fixed depth + linear ramp, all tunable.
SFX_DUCK_THRESHOLD = $80     ; SFX priority >= this ducks the music (spindash/dash/death)
SFX_DUCK_DEPTH     = $18     ; carrier-TL bump (attenuation units; bigger = quieter music)
SFX_DUCK_PSG_DEPTH = 3       ; PSG linear-volume drop applied while ducked
SFX_DUCK_RAMP_STEP = 4       ; duck-level change per frame (linear ramp up/down)
```

- [ ] **Step 3: Define the SfxHeader field offsets + SfxChannel struct + the `_len` assert.** After the `FmPatch` struct block (ends line 517) and before the `SeqChannel` struct, add:
```asm
; --- SFX blob header (emitted by tools/sfx_transcode.py, prefixes the event-list).
; An SFX "is a tiny song": the SfxHeader is followed by a pack_song-style channel
; blob. The header carries the SFX-specific metadata the song format has no field
; for (preferred route, priority, own-voice ptr, flags). Big-endian ptr offsets,
; matching the SongHeader convention. design-for-C: SHF_* reserves continuous/loop
; bits 5b will consume without a format change.
SfxHeader struct
sfh_priority    ds.b 1   ; +0  authored priority byte (SFXPRI_*); higher wins
sfh_flags       ds.b 1   ; +1  SHF_* (continuous / stereo-alt / loop)
sfh_chcount     ds.b 1   ; +2  number of SFX channels (1 or 2 for the core set)
sfh_pad         ds.b 1   ; +3  align the per-channel records to even
; per channel: route(.b) + kind(.b) + cmd_ptr(.w BE off) + voice_ptr(.w BE off)
SfxHeader endstruct      ; = 4 bytes (fixed prefix; per-channel array follows)

SFXH_PRIORITY = SfxHeader_sfh_priority
SFXH_FLAGS    = SfxHeader_sfh_flags
SFXH_CHCOUNT  = SfxHeader_sfh_chcount
SFXH_CHANNELS = SfxHeader_len          ; per-channel array starts after the prefix
; per-channel record (6 bytes): route, kind, cmd_ptr(BE), voice_ptr(BE)
SFXHC_ROUTE   = 0
SFXHC_KIND    = 1
SFXHC_CMD_HI  = 2
SFXHC_CMD_LO  = 3
SFXHC_VOICE_HI = 4
SFXHC_VOICE_LO = 5
SFXHC_LEN     = 6

; --- SfxHeader flags (SHF_*). bits 3-7 reserved for 5b (continuous-loop interp).
SHF_CONTINUOUS_B = 0     ; held-loop SFX (5b interprets; 5a only honors extend-not-retrigger)
SHF_STEREO_ALT_B = 1     ; ring-style L/R alternation (resolved 68k-side; informational here)
SHF_LOOP_B       = 2     ; the blob self-loops (smpsLoop -> MEV_LOOP/JUMP)
SHF_CONTINUOUS   = 1<<SHF_CONTINUOUS_B
SHF_STEREO_ALT   = 1<<SHF_STEREO_ALT_B
SHF_LOOP         = 1<<SHF_LOOP_B

; --- SfxChannel struct (per-active-SFX-voice state; Z80 RAM, indexed by ix). It
; REUSES the SeqChannel field LAYOUT for the fields ModUpdate/Sequencer_Channel
; read (so the shared interpreter walks it with the same (ix+sc_*) addressing),
; then appends the SFX bookkeeping. The shared-prefix fields MUST keep the same
; offsets as SeqChannel — asserted below. The appended fields use sx_* names.
SfxChannel struct
sc_stream_ptr   ds.w 1   ; +0  command stream read ptr (shared with SeqChannel)
sc_mod_ptr      ds.w 1   ; +2  modulation stream (NULL in 5a)
sc_dur_count    ds.b 1   ; +4
sc_dur_default  ds.b 1   ; +5
sc_patch        ds.b 1   ; +6  SFX's own FM patch index (into its own bank)
sc_last_patch   ds.b 1   ; +7  ($FF = force reload)
sc_volume       ds.b 1   ; +8
sc_note         ds.b 1   ; +9
sc_flags        ds.b 1   ; +10 SCF_* (ACTIVE/KEYED/IS_FM/IS_PSG; never SFX_OVERRIDE)
sc_route        ds.b 1   ; +11 the PHYSICAL voice this SFX currently owns (CHROUTE_*)
sc_loop_ptr     ds.w 1   ; +12
sc_repeat_ptr   ds.w 1   ; +14
sc_repeat_count ds.b 1   ; +16
sc_tempo_base   ds.b 1   ; +17
sc_tempo_accum  ds.b 1   ; +18
sc_pt_count     ds.b 1   ; +19
sc_pt_cursor    ds.b 1   ; +20
sc_points       ds.b 5   ; +21
sc_transpose    ds.b 1   ; +26
sc_pan          ds.b 1   ; +27
sc_opbias       ds.b 4   ; +28
sc_porta_accum  ds.w 1   ; +32
sc_porta_incr   ds.w 1   ; +34
sc_last_pan     ds.b 1   ; +36
sc_fill_master  ds.b 1   ; +37
sc_fill_count   ds.b 1   ; +38 (end of the shared SeqChannel-compatible prefix)
; --- SFX-only appended state (offsets >= SeqChannel_len) ---
sx_priority     ds.b 1   ; +39 the running SFX's priority (cleared on end; arbitration)
sx_patch_base   ds.w 1   ; +41 the SFX's own FmPatch-bank window ptr (set at steal)
sx_saved_route  ds.b 1   ; +43 the music route whose SeqChannel we overrode (for restore)
sx_saved_note   ds.b 1   ; +44 PSG3 tone note saved on a noise steal (periodic-noise coupling)
sx_kind         ds.b 1   ; +45 SFXEL_* of the owned voice (FM/PSG/NOISE) for restore dispatch
SfxChannel endstruct     ; = 46 bytes

        if SfxChannel_len <> 46
          error "SfxChannel struct is \{SfxChannel_len} bytes, expected 46"
        endif
        ; the shared interpreter prefix MUST mirror SeqChannel field offsets so
        ; ModUpdate/Sequencer_Channel walk an SfxChannel correctly.
        if (SfxChannel_sc_flags <> SeqChannel_sc_flags) || (SfxChannel_sc_route <> SeqChannel_sc_route) || (SfxChannel_sc_note <> SeqChannel_sc_note) || (SfxChannel_sc_points <> SeqChannel_sc_points) || (SfxChannel_sc_last_pan <> SeqChannel_sc_last_pan)
          error "SfxChannel shared prefix diverges from SeqChannel field offsets"
        endif
        ; largest field offset must stay within the (ix+d) signed-8-bit range.
        if SfxChannel_sx_kind > 127
          error "SfxChannel sx_kind offset (\{SfxChannel_sx_kind}) exceeds (ix+d) +127"
        endif

; sc_* aliases already exist (SeqChannel). Add sx_* aliases for the SFX fields.
sx_priority     = SfxChannel_sx_priority
sx_patch_base   = SfxChannel_sx_patch_base
sx_saved_route  = SfxChannel_sx_saved_route
sx_saved_note   = SfxChannel_sx_saved_note
sx_kind         = SfxChannel_sx_kind
```

- [ ] **Step 4: Allocate the SFX RAM region at $1D00 with overflow asserts.** After the song-buffer asserts (ends line 792, `song buffer ... overruns the mailbox`) add:
```asm
; --- Phase 5a SFX RAM region (the free $1D00..$1EFF gap, below the mailbox) ----
; Mirrors the seq-region asserts: guard the END against the mailbox ($1F00) above
; and against the song-buffer END ($1D00) below so it can't collide with either.
SND_SFX_BASE       = SND_SONG_BUF + SND_SONG_BUF_SIZE   ; = $1D00 (right after the song buffer)
SND_SFX_CHANNELS   = SND_SFX_BASE                       ; the 7-slot SfxChannel array
SND_SFX_CHAN_END   = SND_SFX_CHANNELS + (SFX_VOICE_COUNT * SfxChannel_len)
; SFX request queue (spec §9): a small priority-gated ring. 3 entries * 2 bytes
; (id, priority) + head/tail/count. SfxDispatch enqueues; the per-frame drain pops.
SND_SFX_QUEUE      = SND_SFX_CHAN_END
SFX_QUEUE_DEPTH    = 3
SFX_QUEUE_ENTRY    = 2                                  ; id + priority
SND_SFX_QUEUE_HEAD = SND_SFX_QUEUE + (SFX_QUEUE_DEPTH * SFX_QUEUE_ENTRY)
SND_SFX_QUEUE_TAIL = SND_SFX_QUEUE_HEAD + 1
SND_SFX_QUEUE_CNT  = SND_SFX_QUEUE_TAIL + 1
; Global music duck level (ramped envelope, spec §7) + the active-duck target.
SND_SFX_DUCK_LEVEL = SND_SFX_QUEUE_CNT + 1              ; current applied duck (0 = none)
SND_SFX_DUCK_TARGET = SND_SFX_DUCK_LEVEL + 1           ; target (set while a duck-SFX runs)
SND_SFX_RAM_END    = SND_SFX_DUCK_TARGET + 1

    if SND_SFX_BASE <> $1D00
      error "SND_SFX_BASE (\{SND_SFX_BASE}) must be $1D00 (right after the song buffer)"
    endif
    if SND_SFX_RAM_END > SND_REQ_BASE
      fatal "SFX RAM (\{SND_SFX_RAM_END}) overruns the mailbox at \{SND_REQ_BASE}"
    endif
    if SND_SFX_BASE < (SND_SONG_BUF + SND_SONG_BUF_SIZE)
      fatal "SFX RAM (\{SND_SFX_BASE}) collides with the song buffer below it"
    endif
```

- [ ] **Step 5: Build-verify the asserts.** `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe`. Expected: exit 0; the new struct/RAM asserts pass (no overflow). No runtime change (nothing reads these yet).
- [ ] **Step 6: Commit.**
```bash
git add sound_constants.asm
git commit -m "feat(sound): Phase 5a SfxChannel struct + SFX RAM region + override flag + eligibility/priority/duck constants"
```

---

## Task 3: Override gate (music side, regression-first)

**Goal:** make the override flag actually mute a music channel's chip writes while its cursor keeps advancing, with a debug-set bit, **before any SFX engine exists** (so the gate is proven in isolation). Gate `ModUpdate` + the 4 `Seq_Hook*` + the two direct-write opcodes. **Regression: with the bit clear, the song is byte-identical; with it set, the channel goes silent but stays in sync and clears cleanly.**

**Files:** Modify `engine/sound_sequencer.asm`.

- [ ] **Step 1: Gate `ModUpdate` (the per-frame FM renderer).** In `engine/sound_sequencer.asm`, `ModUpdate` opens at line 133 with the FM gate. Replace:
```asm
ModUpdate:
        ; Non-FM channels (PSG / DAC) have no per-frame FM modulation to render in
        ; Phase 3a -> no-op. (PSG modulation is out of scope; see spec §1.)
        bit     SCF_IS_FM_B, (ix+sc_flags)
        ret     z
```
with:
```asm
ModUpdate:
        ; Phase 5a: if an SFX has stolen this physical voice, render NOTHING (no
        ; $B4/note-fill/re-key writes) — the SfxChannel owns the channel. The music
        ; cursor still advances in Sequencer_Channel, so the song never desyncs.
        bit     SCF_SFX_OVERRIDE_B, (ix+sc_flags)
        ret     nz
        ; Non-FM channels (PSG / DAC) have no per-frame FM modulation to render in
        ; Phase 3a -> no-op. (PSG modulation is out of scope; see spec §1.)
        bit     SCF_IS_FM_B, (ix+sc_flags)
        ret     z
```

- [ ] **Step 2: Gate the 4 `Seq_Hook*` write entry points.** These are the opcode-driven chip writes (note-on/off/vol/patch) for FM and PSG. Add the override early-out to each. At `Seq_HookNoteOn` (line 869) replace:
```asm
Seq_HookNoteOn:
        bit     SCF_IS_FM_B, (ix+sc_flags)
        jr      nz, .fm
```
with:
```asm
Seq_HookNoteOn:
        bit     SCF_SFX_OVERRIDE_B, (ix+sc_flags)
        ret     nz                       ; SFX owns this voice -> emit no chip write
        bit     SCF_IS_FM_B, (ix+sc_flags)
        jr      nz, .fm
```
At `Seq_HookNoteOff` (line 885) replace:
```asm
Seq_HookNoteOff:
        bit     SCF_IS_FM_B, (ix+sc_flags)
        jp      nz, Fm_NoteOff
```
with:
```asm
Seq_HookNoteOff:
        bit     SCF_SFX_OVERRIDE_B, (ix+sc_flags)
        ret     nz
        bit     SCF_IS_FM_B, (ix+sc_flags)
        jp      nz, Fm_NoteOff
```
At `Seq_HookSetVol` (line 892) replace:
```asm
Seq_HookSetVol:
        bit     SCF_IS_FM_B, (ix+sc_flags)
        jr      nz, .fm
```
with:
```asm
Seq_HookSetVol:
        bit     SCF_SFX_OVERRIDE_B, (ix+sc_flags)
        ret     nz
        bit     SCF_IS_FM_B, (ix+sc_flags)
        jr      nz, .fm
```
At `Seq_HookSetPatch` (line 903) replace:
```asm
Seq_HookSetPatch:
        bit     SCF_IS_FM_B, (ix+sc_flags)
        ret     z                        ; PSG/DAC have no patch -> ignore
```
with:
```asm
Seq_HookSetPatch:
        bit     SCF_SFX_OVERRIDE_B, (ix+sc_flags)
        ret     nz
        bit     SCF_IS_FM_B, (ix+sc_flags)
        ret     z                        ; PSG/DAC have no patch -> ignore
```

- [ ] **Step 3: Gate the two direct-write opcodes (`Seq_Op_NoteRaw`, `Seq_Op_RegDelta`).** These write the YM directly, bypassing the hooks. In `Seq_Op_NoteRaw` (line 438), the FM gate is at line 456 (`bit SCF_IS_FM_B,(ix+sc_flags) / ret z`). Replace:
```asm
        bit     SCF_IS_FM_B, (ix+sc_flags)
        ret     z                        ; non-FM route -> time advanced, no key
        ; RETRIGGER the hardware envelope: key OFF then key ON, so every note
```
with:
```asm
        bit     SCF_SFX_OVERRIDE_B, (ix+sc_flags)
        ret     nz                       ; SFX owns this voice -> advance time, no key
        bit     SCF_IS_FM_B, (ix+sc_flags)
        ret     z                        ; non-FM route -> time advanced, no key
        ; RETRIGGER the hardware envelope: key OFF then key ON, so every note
```
In `Seq_Op_RegDelta` (line 624), the FM gate is at line 627. Replace:
```asm
Seq_Op_RegDelta:
        ld      a, (hl)
        inc     hl                       ; a = count; hl past the count byte
        bit     SCF_IS_FM_B, (ix+sc_flags)
        jr      nz, .fm
```
with:
```asm
Seq_Op_RegDelta:
        ld      a, (hl)
        inc     hl                       ; a = count; hl past the count byte
        bit     SCF_SFX_OVERRIDE_B, (ix+sc_flags)
        jr      nz, .skip_pre            ; SFX owns this voice -> consume operands, no write
        bit     SCF_IS_FM_B, (ix+sc_flags)
        jr      nz, .fm
.skip_pre:
```
(The existing `.non-FM` operand-skip path falls through `.skipped`; `.skip_pre` lands on the same `add a,a` skip code, so an overridden channel consumes `count*2` operand bytes and writes nothing — stream stays aligned.)

- [ ] **Step 4: Build + regression-verify (bit clear).** `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe`. Reload Moving Trucks in Exodus (`emulator_reload_rom`→`reset`→`resume`, press A to restart). Capture ~10 s VGM → `vgm2wav`; confirm the song is unchanged (no override set anywhere yet → all gates fall through). Expected: byte-identical playback to pre-change.
- [ ] **Step 5: Verify the gate in isolation (bit set).** With the song playing, use `emulator_z80_write` to set `SCF_SFX_OVERRIDE` (bit 6) in the `sc_flags` byte of one active FM channel's `SeqChannel` (address `SND_SEQ_CHANNELS + route*SeqChannel_len + sc_flags`; look up `SeqChannel_sc_flags`/`SND_SEQ_CHANNELS` via `emulator_lookup_symbol`). Observe via `emulator_get_channel_states`: that FM channel goes silent (no new key-ons), but `emulator_z80_read` on its `sc_stream_ptr` shows it still advancing (cursor moves). Clear the bit; the channel re-keys on its next note event. Expected: silent-but-in-sync while set, resumes when cleared.
- [ ] **Step 6: Commit.**
```bash
git add engine/sound_sequencer.asm
git commit -m "feat(sound): SCF_SFX_OVERRIDE gate on ModUpdate + 4 hooks + NoteRaw/RegDelta (cursor advances, writes muted)"
```

---

## Task 4: SFX format + transcoder core (`tools/sfx_transcode.py`) + pytest

**Goal:** parse skdisasm SMPS SFX, reuse the MT voice→FmPatch conversion + event emitting, emit our SFX blob (SfxHeader + event-list) + a `SfxTable`. pytest: round-trip a known SFX; assert no reserved-channel target; assert SfxTable completeness.

**Files:** Create `tools/sfx_transcode.py`, `tools/test_sfx_transcode.py`.

- [ ] **Step 1: The SMPS SFX parser + voice parser.** Create `tools/sfx_transcode.py`. Mirror the import pattern in `tools/zyrinx_port.py:271` (`sys.path.insert` then `from song_packer import ...`). Parse a skdisasm `Sound/SFX/NN - Name.asm`:
  - Header: `smpsHeaderVoice <label>`, `smpsHeaderSFXChannel <chanid>, <dataloc>, <pitch>, <vol>` (one per SFX channel). Map `chanid` via the exact equates from `_smps2asm_inc.asm`: `cPSG1=$80→CHROUTE_PSG1`, `cPSG2=$A0→CHROUTE_PSG2`, `cPSG3=$C0→CHROUTE_PSG3`, `cFM3=$02→CHROUTE_FM3`, `cFM4=$04→CHROUTE_FM4`, `cFM5=$05→CHROUTE_FM5`, `cFM6=$06→CHROUTE_FM6`, `cNoise=$E0→CHROUTE_PSGN`. `pitch`→`sc_transpose` seed, `vol`→initial `Vol` event.
  - Voice block: parse the `smpsVc*` macros into the `translate_voice` dict shape `{fb,algo,ams_fms_pan,dt_mul,tl,ks_ar,am_d1r,d2r,sl_rr}`: `smpsVcAlgorithm→algo`, `smpsVcFeedback→fb`, `smpsVcDetune`+`smpsVcCoarseFreq`→`dt_mul` (per-op `(detune<<4)|coarse`), `smpsVcRateScale`+`smpsVcAttackRate`→`ks_ar` (`(rs<<6)|ar`), `smpsVcAmpMod`+`smpsVcDecayRate1`→`am_d1r` (`(am<<7)|d1r`), `smpsVcDecayRate2→d2r`, `smpsVcDecayLevel`+`smpsVcReleaseRate`→`sl_rr` (`(dl<<4)|rr`), `smpsVcTotalLevel→tl`, `ams_fms_pan=$C0` (centered). Then call `translate_voice(v)` (reused from `zyrinx_port.py`).
  - Data stream: decode note bytes (`nRst=$80`, `nC0=$81`… per the `enum` at `_smps2asm_inc.asm:31`), duration bytes, and coord flags into `song_packer` Events.
- [ ] **Step 2: Coord-flag coverage (v1 — the subset the core set uses).** Decode exactly these, flagging any other `$E0-$FF` byte as a build error (spec §8: never silently dropped):
  - `smpsSetvoice $XX` (`$EF,voice`) → `Patch(voice)` into the SFX's own bank (single voice → index 0).
  - `smpsPan dir,amsfms` (`$E0,dir|amsfms`) → `Pan(dir|amsfms)` (panNone=$00/Right=$40/Left=$80/Centre=$C0 in bits 7-6).
  - `smpsPSGvoice sTone_XX` (`$F5,voice`) → store as a PSG-waveform note shaping; for v1 map to a `Patch`-equivalent no-op on PSG (PSG has no FM patch) — record the sTone index in a comment; the audible PSG shape comes from the note divisor. (PSG envelope tables are out of v1 scope; document.)
  - `smpsModSet w,s,c,st` (`$F0,…`) → **drop with a comment** for v1 (the engine has no per-note pitch-modulation envelope yet) BUT the note pitch + duration are preserved. Document this as the one *intentional* lossy mapping (the SFX still reads correctly); it is NOT a silent drop — emit a `# modset dropped` log line.
  - `smpsSpindashRev` (`$E9`) / `smpsResetSpindashRev` (`$FF,$07`) → the spindash frequency-ramp: translate the rev's accumulating transpose into explicit per-note `NoteRaw`/transposed notes at transcode time (the rev step is build-time known), so the engine needs no spindash opcode.
  - `smpsPSGform $XX` (`$F3,form`) → the noise-mode/PSG-form control. For a noise route, map `$E7`→the noise control byte (periodic, borrow PSG3). Emit it as the note's encoded form.
  - `smpsLoop idx,loops,loc` (`$F7,…`) → `LoopPoint`/`Jump` bounded by a build-time unroll OR `RepeatStart`/`RepeatEnd` if the body is uniform (reuse the existing repeat events). Set `SHF_LOOP`.
  - `smpsFMAlterVol vN` (`$E5,…`) → relative volume change → emit an absolute `Vol` recomputed at transcode time.
  - `smpsNoAttack` (`$E7` as a note prefix) → emit the note WITHOUT re-key (a held no-attack), via the engine's held-note path (same-index PitchEnv = no re-attack).
  - `smpsStop` (`$F2`) → `End()`.
- [ ] **Step 3: Emit the blob (SfxHeader + per-channel records + event streams) + the patch bank.** Add `pack_sfx(sfx_desc)` mirroring `pack_song`'s offset math: emit the 4-byte SfxHeader prefix (`priority, flags, chcount, pad`), then per channel a 6-byte record (`route, kind, cmd_ptr BE, voice_ptr BE`), then the packed event streams (back-patch `cmd_ptr` like `pack_song`), then the voice ptr points into the SFX's own FmPatch bank. Reuse `emit_patch_bank_asm` (from `zyrinx_port.py`) for the bank. Emit `data/sound/sfx/sfx_NN.asm` (the blob) + `data/sound/sfx/sfx_NN_patches.asm`. The `kind` byte = `SFXEL_FM`/`SFXEL_PSG`/`SFXEL_NOISE` derived from the route.
- [ ] **Step 4: Emit the SfxTable + the priority map.** `emit_sfx_table()` writes `data/sound/sfx/sfx_table.asm`: `SfxTable: dc.l <blob>` per SFX id (densely indexed, `SfxTable[id-1]`), a parallel `SfxPatchTable: dc.l <bank>`, `SFX_COUNT` enum, and the completeness assert `(SfxTable_End - SfxTable)/4 <> SFX_COUNT → error`. The authored priority map (keyed by id, the `SFXPRI_*` tiers) is applied into each blob's `sfh_priority`.
- [ ] **Step 5: pytest.** Create `tools/test_sfx_transcode.py` mirroring `tools/test_song_packer.py` (unittest + `sys.path.insert`). Tests:
  - `test_roundtrip_roll`: transcode `36 - Skid.asm` and `3C - Roll.asm` from a fixture string; assert the parsed route, the event sequence (note indices + durations), and the voice bytes match expected values; assert `sfh_priority == SFXPRI_ROLL`/`SFXPRI_SKID`.
  - `test_no_reserved_target`: for every transcoded SFX, assert no channel route is `CHROUTE_FM1`/`FM2`/`FM6`/`DAC` (reserved); the eligible-kind matches the route.
  - `test_sfxtable_complete`: assert `SfxTable` has exactly `SFX_COUNT` entries and every `SFXID_*` maps to a blob.
  - `test_unknown_flag_errors`: a stream with an undecoded `$E0-$FF` byte raises a build error (not silently dropped).
  Run: `python3 -m pytest tools/test_sfx_transcode.py -q`. Expected: all pass.
- [ ] **Step 6: Commit.**
```bash
git add tools/sfx_transcode.py tools/test_sfx_transcode.py
git commit -m "test(sound): S3K SFX transcoder (sfx_transcode.py) + pytest round-trip/reserved-channel/completeness"
```

---

## Task 5: Transcode the core SFX set + build wiring

**Goal:** transcode the eight core SFX to `data/sound/sfx/` and wire the generated asm + `SfxTable` into the build (the codegen step + `main.asm` include).

**Files:** Create `data/sound/sfx/*.asm` (generated), modify `build.sh`, `main.asm`.

- [ ] **Step 1: Run the transcoder over the core set.** Transcode: Jump `62`, Ring `33`+`34`, Skid `36`, Roll `3C`, Spindash `AB`, Dash `B6`, Death `35`, RingLoss `B9` from `skdisasm/Sound/SFX/`. Generate `data/sound/sfx/sfx_NN.asm` + `sfx_NN_patches.asm` per SFX + `data/sound/sfx/sfx_table.asm`. Verify each emitted blob's `sfh_chcount`/routes against the source (e.g. Dash `B6` = cFM5 + cPSG3 → 2 channels; Skid `36` = cPSG2 + cPSG1 → 2 channels). Run `python3 -m pytest tools/test_sfx_transcode.py -q` once more against the real files.
- [ ] **Step 2: Add the codegen step to `build.sh`.** Near the other codegen lines (after `gen_compression_vectors.py` at line 142, before the s4lint at 146), add:
```bash
python3 "${TOOLS}/sfx_transcode.py" generate
```
so committed `data/sound/sfx/*.asm` are regenerable in-build (matching the project's "generated, committed" pattern — `build.sh` `include`s the committed output; the transcoder is idempotent).
- [ ] **Step 3: Wire the includes into `main.asm`.** In the `ifdef SOUND_DRIVER_ENABLED` block (after `song_table.asm` at the end of the song includes, ~line 290), add the SFX data. SFX blobs are small FM/PSG (no DAC, no 32 KB streaming) so they do NOT need `align $8000`; emit them as plain inline 68k data the loader reads via the $8000 window (like the copy-path songs). Add:
```asm
        ; --- Phase 5a SFX data (generated by tools/sfx_transcode.py) ---
        ; Small FM/PSG blobs (no DAC, no bank-streaming) — plain inline data the
        ; Z80 SFX loader reads via the $8000 window. SfxTable indexes id -> blob.
        include "data/sound/sfx/sfx_62.asm"
        include "data/sound/sfx/sfx_62_patches.asm"
        include "data/sound/sfx/sfx_33.asm"
        include "data/sound/sfx/sfx_33_patches.asm"
        include "data/sound/sfx/sfx_34.asm"
        include "data/sound/sfx/sfx_35.asm"
        include "data/sound/sfx/sfx_35_patches.asm"
        include "data/sound/sfx/sfx_36.asm"
        include "data/sound/sfx/sfx_3C.asm"
        include "data/sound/sfx/sfx_3C_patches.asm"
        include "data/sound/sfx/sfx_AB.asm"
        include "data/sound/sfx/sfx_AB_patches.asm"
        include "data/sound/sfx/sfx_B6.asm"
        include "data/sound/sfx/sfx_B6_patches.asm"
        include "data/sound/sfx/sfx_B9.asm"
        include "data/sound/sfx/sfx_B9_patches.asm"
        include "data/sound/sfx/sfx_table.asm"
```
(Ring `33`/`34` share the `Sound_33_34_B9_Voices` bank in S3K → the transcoder emits one shared patch bank, referenced by `33` and `34` and `B9`; emit it once. Adjust the include list to whatever the transcoder actually produces — verify the generated filenames before finalizing.)
- [ ] **Step 4: Build.** `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe`. Expected: exit 0; `SfxTable` completeness assert passes; SFX blobs assembled (not yet referenced by any code — pure data).
- [ ] **Step 5: Commit.**
```bash
git add data/sound/sfx/ build.sh main.asm
git commit -m "feat(sound): transcode core S3K SFX set (jump/ring/skid/roll/spindash/dash/death/ringloss) + build/include wiring"
```

---

## Task 6: Sfx_Frame interpreter + steal core

**Goal:** create `engine/sound_sfx.asm` with `Sfx_Frame` (the per-frame `SfxChannel` interpreter, reusing `ModUpdate`/`Sequencer_Channel`) and the **steal** primitive (set override on the target music channel, init the SfxChannel, key-off the physical voice, load the SFX's own FM voice). Wire `Sfx_Frame` after `Sequencer_Frame` and include the new file. **No restore yet — an SFX plays once and leaves the music muted (proven, then fixed in Task 7).**

**Files:** Create `engine/sound_sfx.asm`; modify `engine/sound_sequencer.asm`, `engine/z80_sound_driver.asm`.

- [ ] **Step 1: Create `engine/sound_sfx.asm` with `Sfx_Frame`.** One-line header comment. `Sfx_Frame` walks the 7-slot `SfxChannel` array exactly like `Sequencer_Frame`'s `.chan_loop`, calling `ModUpdate` then the tempo-gated `Sequencer_Channel` per active slot (the shared interpreter — `ix` = SfxChannel, whose prefix matches SeqChannel). When a slot's stream hits `End` (`MEV_END`), it deactivates the slot and (Task 7) restores. Preserve `ix`/the caller's invariants:
```asm
; engine/sound_sfx.asm — Phase 5a SFX engine: steal/restore + per-frame interpreter
; ----------------------------------------------------------------------
; Sfx_Frame — run all active SfxChannels once per frame, AFTER Sequencer_Frame so
; SFX writes land last and own the stolen physical voice. Mirrors the music
; channel loop; reuses ModUpdate + Sequencer_Channel on the SfxChannel array.
; Clobbers af,bc,de,hl,ix (same as Sequencer_Frame). The caller (idle/timer tick)
; restores de=$4001 after.
; ----------------------------------------------------------------------
Sfx_Frame:
        ld      b, SFX_VOICE_COUNT       ; b = slot count (djnz bound)
        ld      ix, SND_SFX_CHANNELS     ; ix = first SfxChannel
.slot_loop:
        bit     SCF_ACTIVE_B, (ix+sc_flags)
        jr      z, .next_slot            ; inactive slot -> skip
        push    bc
        call    ModUpdate                ; render SFX modulation state -> chip
        ld      a, (ix+sc_tempo_accum)
        sub     16
        ld      (ix+sc_tempo_accum), a
        jr      nc, .slot_done           ; no borrow -> no event-tick this frame
        add     a, (ix+sc_tempo_base)
        ld      (ix+sc_tempo_accum), a
        call    Sequencer_Channel        ; advance the SFX cursor (shared interp)
        ; if the SFX stream ended, Sequencer_NextOpcode's End handler cleared
        ; SCF_ACTIVE — detect + restore (Task 7 fills Sfx_Restore).
        bit     SCF_ACTIVE_B, (ix+sc_flags)
        jr      nz, .slot_done
        call    Sfx_Restore              ; SFX ended -> hand the voice back to music
.slot_done:
        pop     bc
.next_slot:
        ld      de, SfxChannel_len
        add     ix, de
        djnz    .slot_loop
        ret
```
(The `End` opcode handler already clears `SCF_ACTIVE` and stops the cursor — verify in `Sequencer_NextOpcode`; reuse it. If `End` does not clear `SCF_ACTIVE` for the SFX context, the slot's stream self-terminates and `Sfx_Frame` detects the `MEV_END` via the active bit; confirm against the live `.end` handler when implementing.)

- [ ] **Step 2: `Sfx_Steal` — claim a physical voice for an SFX channel.** Add to `engine/sound_sfx.asm`. In: `ix` = the target SfxChannel (already partly initialized by `SfxDispatch`), `sc_route` = the physical voice to steal, `sx_saved_route` = the music route whose SeqChannel to override. Steps: (1) find that music `SeqChannel` (`SND_SEQ_CHANNELS + route*SeqChannel_len`, computed by `add`-loop, no multiply) and `set SCF_SFX_OVERRIDE_B,(that+sc_flags)`; (2) key-off the physical voice on the music side so the music note stops cleanly — for FM call `Fm_NoteOff` with `ix`=music channel, for PSG call `Psg_NoteOff`, for noise save PSG3's tone note into `sx_saved_note` first (Task 7 restore uses it); (3) point `SND_SEQ_PATCHTAB` at the SFX's own patch bank (`sx_patch_base`) so `Fm_PatchPtr`/`Fm_PatchLoad` resolve the SFX voice — OR (cleaner) load the SFX voice directly via `Fm_PatchLoad` with `hl` = the SFX voice ptr from `sx_patch_base` and `ix` = the SfxChannel; (4) set `SCF_ACTIVE` on the SfxChannel so `Sfx_Frame` runs it. Document the FM/PSG/noise dispatch via `sx_kind`. Preserve `ix` for the caller.

  Note on patch resolution (load-bearing): the music `Fm_PatchPtr` reads `SND_SEQ_PATCHTAB`. To avoid clobbering it, the SfxChannel carries its own voice ptr (`sx_patch_base`) and steal calls `Fm_PatchLoad` with `hl` preset to the SFX voice — `Fm_PatchLoad` takes `hl`=patch ptr directly (it does NOT call `Fm_PatchPtr`), so the SFX voice loads without touching `SND_SEQ_PATCHTAB`. Music restore (Task 7) re-derives the music patch via `Fm_PatchPtr` (unchanged `SND_SEQ_PATCHTAB`).

- [ ] **Step 3: Stub `SfxDispatch` + `Sfx_Restore` so the file assembles.** Add a minimal `SfxDispatch` (Task 8/9 fill the queue/selection): for now, given the posted id in `a`, look up `SfxTable[id-1]`, parse the SfxHeader's first channel, init one SfxChannel slot (copy route/kind, set `sc_stream_ptr` to the blob's `cmd_ptr`, `sx_patch_base` to the voice ptr, `sc_dur_count=1`, `sc_pt_count=1`, class flags via the kind), set `sx_saved_route` = the same physical route's music owner, `call Sfx_Steal`. Add a stub `Sfx_Restore: ret` (Task 7 fills it) and `Sfx_StopAll` (Task 12). This proves steal end-to-end before restore/selection exist.
- [ ] **Step 4: Include the new file + wire `Sfx_Frame`.** In `engine/z80_sound_driver.asm`, after the `include "engine/sound_sequencer.asm"` (line 1070), before `include "engine/sound_fm.asm"`, add:
```asm
; ======================================================================
; Phase 5a SFX engine — steal/restore + the per-frame SfxChannel interpreter.
; Included INSIDE the phase-0 blob (after the sequencer whose ModUpdate/
; Sequencer_Channel it reuses, before the FM/PSG writers it calls).
; ======================================================================
        include "engine/sound_sfx.asm"
```
In `engine/sound_sequencer.asm`, wire `Sfx_Frame` so it runs after the music loop AND even when no song plays. Replace `Sequencer_Frame`'s tail at line 85-86:
```asm
        add     ix, de
        djnz    .chan_loop
        ret
```
with:
```asm
        add     ix, de
        djnz    .chan_loop
.run_sfx:
        jp      Sfx_Frame                ; tail-call: SFX writes land AFTER music
```
AND change the two early `ret z` guards (line 55 and 59, "no song playing" / "no channels") to branch to `.run_sfx` so SFX still update with no music:
```asm
        ld      a, (SND_SEQ_ACTIVE)
        or      a
        jr      z, .run_sfx              ; no song -> still run SFX (own the chip)

        ld      a, (SND_SEQ_CHCOUNT)
        or      a
        jr      z, .run_sfx              ; no channels -> still run SFX
```

- [ ] **Step 5: Build + verify steal.** `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe`. In Exodus, play Moving Trucks, then use `emulator_z80_write` to post an SFX id to `SND_REQ_SFX` ($1F03) — e.g. Jump `$62`. Confirm via `emulator_get_channel_states` + `emulator_z80_read`: the SfxChannel slot goes `SCF_ACTIVE`, the target music channel's `sc_flags` gains `SCF_SFX_OVERRIDE` (bit6), the SFX's voice is loaded (FM patch regs changed), and the SFX sounds. Capture VGM → `vgm2wav`: the SFX is audible; the stolen music voice is muted (expected — no restore yet). Expected: steal works; music coasts muted on that one voice after the SFX (the Task-7 bug we fix next).
- [ ] **Step 6: Commit.**
```bash
git add engine/sound_sfx.asm engine/sound_sequencer.asm engine/z80_sound_driver.asm
git commit -m "feat(sound): Sfx_Frame interpreter + steal core (override music channel, load SFX voice); restore is Task 7"
```

---

## Task 7: Restore (clean)

**Goal:** on SfxChannel end, hand the physical voice back cleanly: clear the override, re-upload the music FM patch (`Fm_PatchPtr`+`Fm_PatchLoad`+`Fm_SetVolume`), restore PSG3/noise if touched, and force-re-key the held music note only if one was sounding. **Verify: no silence gap — the music voice resumes instantly through steal→restore.**

**Files:** Modify `engine/sound_sfx.asm`.

- [ ] **Step 1: Implement `Sfx_Restore` (no register snapshots — re-derive from stored state).** In: `ix` = the ending SfxChannel; `sx_saved_route` = the music route to hand back; `sx_kind` = FM/PSG/NOISE. Steps:
  1. Compute the music `SeqChannel` ptr for `sx_saved_route` (`SND_SEQ_CHANNELS + route*SeqChannel_len` via add-loop, no multiply) into a register pair; keep it for the rest of the routine.
  2. `res SCF_SFX_OVERRIDE_B,(music+sc_flags)` — un-mute the music channel's writes.
  3. Branch on `sx_kind`:
     - **FM:** with `ix` = the **music** SeqChannel: `call Fm_PatchPtr` (hl = music FmPatch ptr from its `sc_patch`, base `SND_SEQ_PATCHTAB` — untouched by steal), `call Fm_PatchLoad` (re-upload the music voice; re-asserts op-bias), then `ld a,(ix+sc_volume) / call Fm_SetVolume` (re-apply music loudness + op-bias on carriers). This is the exact `Seq_HookSetPatch` pair (sound_sequencer.asm:906-915). Then **force re-key** if `SCF_KEYED` is set on the music channel: mirror `ModUpdate`'s re-key (sound_fm.asm/`ModUpdate` L202-209): `bit SCF_KEYED_B,(ix+sc_flags) / jr z,.fm_no_rekey`; if keyed, `call Fm_NoteOff` (clean 0→1 edge) then `ld a,(ix+sc_note) / call Fm_NoteFromTable` (re-key the held note from the per-song table). If not keyed, just clearing the override is enough — the next note event keys normally. Honor `SND_REKEY_OFF_THEN_ON` (skip the `Fm_NoteOff` when it is 0).
     - **PSG (tone):** with `ix` = the music SeqChannel: if `SCF_KEYED`, `ld a,(ix+sc_note) / call Psg_NoteOn` (re-keys the tone + re-applies volume via its `Psg_SetVolume` tail). Else nothing.
     - **NOISE:** restore PSG3's borrowed tone register first — set `ix` = the PSG3 music channel, `ld a,(ix+sc_note)` (its held note), `call Psg_NoteOn` to re-latch PSG3's tone; then if the music noise channel was keyed, re-key it. Use `sx_saved_note` captured at steal if the live PSG3 `sc_note` is unreliable.
  4. Deactivate the SfxChannel: `res SCF_ACTIVE_B,(ix_sfx+sc_flags)` (already cleared by End — defensive), clear `sx_priority` = 0 (so the next SFX of any priority can play — spec §11), and (Task 10) signal the duck to ramp back if this SFX was ducking.
  Preserve the caller's `ix` (the SfxChannel) on exit so `Sfx_Frame`'s `add ix,de` advances correctly — save/restore it around the music-channel work (`push ix`/`pop ix`).
- [ ] **Step 2: Restore `SND_SEQ_PATCHTAB` discipline.** Confirm steal (Task 6) loaded the SFX voice via `Fm_PatchLoad(hl=sx_patch_base voice)` WITHOUT writing `SND_SEQ_PATCHTAB`, so restore's `Fm_PatchPtr` still resolves the music patch table. If Task 6 chose the `SND_SEQ_PATCHTAB`-swap approach instead, restore must save/restore it — prefer the no-swap approach. Document the chosen mechanism in the file header.
- [ ] **Step 3: Build + verify no silence gap.** `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe`. In Exodus, play Moving Trucks, post Jump `$62` to `SND_REQ_SFX` mid-phrase. Via `emulator_get_channel_states` across the steal→restore window: the music voice goes silent during the SFX, then **immediately re-keys** when the SFX ends (no dead frames). Confirm `SCF_SFX_OVERRIDE` clears, the music FM patch regs return to the music voice values (`emulator_z80_read`), and a key-on fires on the restore frame. Capture VGM → `vgm2wav`: the music lead/bass survive intact through the SFX; no audible dropout after. Expected: clean restore, no silence gap.
- [ ] **Step 4: Commit.**
```bash
git add engine/sound_sfx.asm
git commit -m "feat(sound): clean SFX restore — re-upload music patch + re-key held note + PSG3/noise restore, no silence gap"
```

---

## Task 8: Channel selection — dynamic-among-eligible + priority steal

**Goal:** make `SfxDispatch` pick the voice intelligently: prefer the SFX's declared route; if busy, pick another free eligible voice of the same kind; only when all eligible-of-kind are busy, steal the lowest-priority current occupant iff `incoming >= it`.

**Files:** Modify `engine/sound_sfx.asm`; add the `SfxEligTable` data.

- [ ] **Step 1: Add the `SfxEligTable` (CHROUTE_* → SFXEL_*).** In `engine/sound_sfx.asm`, a `db`-per-route table consumed by the selector (mirrors `SFX_ELIGIBLE` semantics, indexed by `CHROUTE_*`):
```asm
; Eligibility by physical route (CHROUTE_FM1..CHROUTE_DAC). FM1/FM2/FM6/DAC are
; SFXEL_NONE (lead/bass/DAC never stolen). Opening FM6 to SFX later for DAC-off
; songs is a one-byte edit here (design-for-C).
SfxEligTable:
        db      SFXEL_NONE   ; CHROUTE_FM1
        db      SFXEL_NONE   ; CHROUTE_FM2
        db      SFXEL_FM     ; CHROUTE_FM3
        db      SFXEL_FM     ; CHROUTE_FM4
        db      SFXEL_FM     ; CHROUTE_FM5
        db      SFXEL_NONE   ; CHROUTE_FM6 (reserved v1)
        db      SFXEL_PSG    ; CHROUTE_PSG1
        db      SFXEL_PSG    ; CHROUTE_PSG2
        db      SFXEL_PSG    ; CHROUTE_PSG3
        db      SFXEL_NOISE  ; CHROUTE_PSGN
        db      SFXEL_NONE   ; CHROUTE_DAC
        ; (build assert: table length == CHROUTE_COUNT)
SfxEligTable_End:
        if (SfxEligTable_End - SfxEligTable) <> CHROUTE_COUNT
          error "SfxEligTable length must equal CHROUTE_COUNT"
        endif
```
- [ ] **Step 2: `Sfx_SelectVoice` — the selection ladder.** In: the SFX's preferred route + kind + incoming priority. Out: a target SfxChannel slot + the physical route to own (carry set = "dropped, no voice"). Ladder:
  1. Map preferred route → its SfxChannel slot. If that slot is free (`SCF_ACTIVE` clear) → use it on the preferred route. Done.
  2. Else scan the SfxChannel slots of the SAME kind (`SfxEligTable[route]==kind`) for a free one (and whose physical voice is not currently sounding music that we'd rather not steal — but any eligible free voice is fine). First free same-kind slot → use it (dynamic substitution; more SFX sound at once).
  3. Else (all same-kind slots busy): find the slot with the **lowest `sx_priority`**; if `incoming_priority >= that lowest` → steal it (call `Sfx_Restore` on it to hand its voice back, then re-init for the incoming SFX). Else → DROP the incoming SFX (carry set). A low-priority SFX can never cut off a higher-priority one.
  No multiply (slot ptr via `add`-loop). Document the three tiers.
- [ ] **Step 3: Rewire `SfxDispatch` to use `Sfx_SelectVoice`.** Replace Task 6's "always slot 0" stub: parse the SfxHeader (priority + per-channel records), and for EACH channel of the SFX call `Sfx_SelectVoice`; on success init the slot (route/kind/stream/voice/priority) and `Sfx_Steal`; on drop (carry) skip that channel. Multi-channel SFX (Dash, Skid) steal their voices independently.
- [ ] **Step 4: Build + verify substitution + priority steal.** `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe`. In Exodus: (a) post Ring `$33` then immediately Ring `$34` — confirm via `emulator_get_channel_states` they take DIFFERENT eligible voices (substitution), both audible. (b) Occupy all eligible-of-kind, then post a higher-priority SFX — confirm it steals the lowest-priority occupant; post a lower-priority one — confirm it is dropped (no steal, the running SFX continues). Expected: dynamic selection + priority steal behave per spec §4/§6.
- [ ] **Step 5: Commit.**
```bash
git add engine/sound_sfx.asm
git commit -m "feat(sound): dynamic-among-eligible voice selection + priority-gated steal of lowest-priority occupant"
```

---

## Task 9: Priority model + SFX queue

**Goal:** a per-SFX priority byte (already in the header), a 3-deep priority-gated queue so multiple requests in one frame aren't lost, overflow drops the lowest-priority pending, priority cleared on SFX end, and the continuous-extend hook (same-id extends not retriggers).

**Files:** Modify `engine/sound_sfx.asm`.

- [ ] **Step 1: Implement the queue (enqueue in dispatch, drain per frame).** The mailbox is latest-wins single-byte; the queue lives Z80-side. `SfxDispatch` (the mailbox handler) ENQUEUES the posted id+priority into `SND_SFX_QUEUE` (3 entries, head/tail/count) rather than acting immediately. `Sfx_Frame` (or a `Sfx_DrainQueue` call at its top) POPS the highest-priority pending entry each frame and runs the real `Sfx_SelectVoice`+`Sfx_Steal`. On enqueue when full: compare the incoming priority against the queued entries; if incoming > the lowest queued, overwrite that lowest entry; else drop the incoming. No multiply (2-byte entries via `add`).
- [ ] **Step 2: Clear priority on SFX end.** Confirm `Sfx_Restore` (Task 7 Step 1.4) sets `sx_priority = 0` on the ended slot so the next SFX of any priority can occupy it (spec §11). Add the explicit clear if missing.
- [ ] **Step 3: Continuous-extend hook (5a partial; full feature is 5b).** When `SfxDispatch` enqueues an id whose SfxHeader has `SHF_CONTINUOUS` AND a slot is already running that same id, EXTEND it (reset its stream cursor / refresh its hold) rather than allocating a second slot — prevents machine-gun pops. For the 5a one-shot core set this path is dormant (none are continuous), but the hook is present so 5b's held-loops are additive. Document the seam. Spindash-rev is one-shot-per-tap so it is fully handled here without the continuous flag.
- [ ] **Step 4: Build + verify the queue.** `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe`. In Exodus: post three SFX ids in rapid succession (write `SND_REQ_SFX` three times across consecutive frames — or use the DEBUG hotkey from Task 12) and confirm via `emulator_get_channel_states` that all three play in priority order (not just the last); post a 4th when full + lowest-priority and confirm it is dropped. Expected: queue preserves multiple requests, overflow drops lowest-priority.
- [ ] **Step 5: Commit.**
```bash
git add engine/sound_sfx.asm
git commit -m "feat(sound): 3-deep priority-gated SFX queue + priority-clear-on-end + continuous-extend hook (5b-ready)"
```

---

## Task 10: Ducking

**Goal:** a global music duck-level ramped envelope; a threshold-gated high-priority SFX raises music carrier TL + lowers PSG volume, then ramps back over N frames on SFX end. Reuse the per-op TL path. Tunable constants.

**Files:** Modify `engine/sound_sfx.asm`.

- [ ] **Step 1: Set the duck target on a duck-eligible steal.** In `SfxDispatch`/`Sfx_Steal`, when an SFX's `sfh_priority >= SFX_DUCK_THRESHOLD` (spindash/dash/death/ring-loss), set `SND_SFX_DUCK_TARGET = SFX_DUCK_DEPTH`. On the SFX's restore (Task 7), if no other duck-eligible SFX is still active, set `SND_SFX_DUCK_TARGET = 0` (ramp back). Track "any duck-eligible SFX active" by scanning slots' `sx_priority >= SFX_DUCK_THRESHOLD` (cheap, 7 slots).
- [ ] **Step 2: `Sfx_DuckRamp` — ramp the level toward the target each frame.** Call at the top of `Sfx_Frame` (once per frame). Move `SND_SFX_DUCK_LEVEL` toward `SND_SFX_DUCK_TARGET` by `SFX_DUCK_RAMP_STEP` (linear, clamped, no overshoot). When the level CHANGES this frame, re-apply it to the music: for each ACTIVE, NON-overridden FM music channel, bump its carrier TL by the current duck level (re-call `Fm_SetVolume` with `sc_volume` mapped down, or add the duck to the per-op TL path — reuse the `Fm_SetVolume` carrier-only path which already clamps); for each PSG music channel, lower its volume by `SFX_DUCK_PSG_DEPTH`. When the level returns to 0, restore the music to its un-ducked `sc_volume` (re-call `Fm_SetVolume`/`Psg_SetVolume` with the stored `sc_volume`). Write-on-change: only touch the chip on frames the level actually changed. No multiply.
- [ ] **Step 3: Threshold gate (rings never duck).** Confirm `SFXPRI_RING ($20) < SFX_DUCK_THRESHOLD ($80)` so collecting rings does not pump the music; only spindash/dash/death/ring-loss duck. Build-assert `SFXPRI_RING < SFX_DUCK_THRESHOLD` in the file.
- [ ] **Step 4: Build + verify ducking.** `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe`. In Exodus, play Moving Trucks, post Spindash `$AB` (priority `$80`): confirm via `emulator_z80_read` that `SND_SFX_DUCK_LEVEL` ramps up to `SFX_DUCK_DEPTH`, the music FM carrier TLs rise (quieter) + PSG volumes drop, then ramp back to 0 over ~`DEPTH/STEP` frames after the SFX ends. Post Ring `$33` (priority `$20`): confirm `SND_SFX_DUCK_TARGET` stays 0 (no duck). Capture VGM → `vgm2wav`: the music audibly dips under the spindash then recovers; rings cause no dip. Expected: ducking dips + ramps for high-priority SFX only.
- [ ] **Step 5: Commit.**
```bash
git add engine/sound_sfx.asm
git commit -m "feat(sound): threshold-gated music ducking — ramped carrier-TL/PSG-vol dip under high-priority SFX, reuses the per-op TL path"
```

---

## Task 11: 68k API + Z80 dispatch + game seams

**Goal:** `Sound_PlaySFX` (68k) + the `SND_REQ_SFX`→`SfxDispatch` mailbox handler (Z80) + ring L/R stereo alternation; then wire the game seams with the exact scout-located lines.

**Files:** Modify `engine/sound_api.asm`, `engine/z80_sound_driver.asm`, `engine/objects/animate.asm`, `engine/player/player_ground.asm`, `engine/player/player_spindash.asm`, `engine/player/player_common.asm`, `engine/objects/rings.asm`.

- [ ] **Step 1: `Sound_PlaySFX` (68k API).** In `engine/sound_api.asm`, after `Sound_PlaySample` (ends line 59), add the single-byte-slot post + the ring stereo-alternation toggle:
```asm
; ----------------------------------------------------------------------
; Sound_PlaySFX — request an SFX by id. Posts the id into SND_REQ_SFX; the Z80
; SfxDispatch handler queues + arbitrates. Ring (SFXID_RING_RIGHT/_LEFT) auto-
; alternates L/R via a 68k speaker toggle so consecutive ring pickups pan opposite.
; In:  d0.b = sfx id (nonzero). Clobbers: SR restored; d0 (ring remap), a0.
; ----------------------------------------------------------------------
Sound_PlaySFX:
        lea     (SND_Z80_BASE+SND_REQ_SFX).l, a0
        bra.w   Sound_PostByte

; ----------------------------------------------------------------------
; Sound_PlayRing — collect-ring SFX with internal L/R alternation. Toggles
; Ring_Sfx_Speaker each call, posting SFXID_RING_RIGHT or _LEFT.
; In: none. Clobbers: d0, a0; SR restored.
; ----------------------------------------------------------------------
Sound_PlayRing:
        move.b  (Ring_Sfx_Speaker).w, d0
        eori.b  #1, d0
        move.b  d0, (Ring_Sfx_Speaker).w
        beq.s   .left
        moveq   #SFXID_RING_RIGHT, d0
        bra.s   Sound_PlaySFX
.left:
        moveq   #SFXID_RING_LEFT, d0
        bra.s   Sound_PlaySFX
```
Add `Ring_Sfx_Speaker: ds.b 1` to `ram.asm` (near the other sound debug RAM). Verify the `.w` addressing is valid for that RAM region.
- [ ] **Step 2: The `SND_REQ_SFX` mailbox handler (Z80).** In `engine/z80_sound_driver.asm` `SndDrv_PollMailbox`, insert an SFX block at `.no_music` (line 511) BEFORE the SAMPLE block's `ret z` (line 515), so a frame with only an SFX request still dispatches. Replace:
```asm
.after_music:
.no_music:
        ; --- sample request? (Task 6: id -> DacSampleTable[id-1] -> Snd_StartSample) ---
        ld      a, (SND_REQ_SAMPLE)
        or      a
        ret     z                        ; nothing else pending
```
with:
```asm
.after_music:
.no_music:
        ; --- SFX request? (Phase 5a: id -> SfxDispatch enqueue + arbitrate) ---
        ld      a, (SND_REQ_SFX)
        or      a
        jr      z, .no_sfx
        call    SfxDispatch              ; enqueue + (Sfx_Frame drains by priority)
        xor     a
        ld      (SND_REQ_SFX), a         ; clear slot (consumed)
        ld      a, (SND_STAT_ACK_COUNT)
        inc     a
        ld      (SND_STAT_ACK_COUNT), a
.no_sfx:
        ; --- sample request? (Task 6: id -> DacSampleTable[id-1] -> Snd_StartSample) ---
        ld      a, (SND_REQ_SAMPLE)
        or      a
        ret     z                        ; nothing else pending
```
- [ ] **Step 3: Wire `AF_SOUND` (both animate.asm handlers — note the different operand offsets).** In `engine/objects/animate.asm`, `.evt_sound` reads id at `2(a1,d1.w)`; `.pf_evt_sound` reads at `1(a1,d1.w)`. Preserve `a1`/`d1` (the anim interpreter relies on them; the `.evt_callback` paths already push `a1`). Replace `.evt_sound` (lines 190-194):
```asm
.evt_sound:
        ; dc.b AF_SOUND, sound_id
        ; Sound ID at 2(a1,d1.w) — consumed but not played (no driver yet)
        addq.b  #2, SST_anim_frame(a0)
        bra.s   .after_event
```
with:
```asm
.evt_sound:
        ; dc.b AF_SOUND, sound_id -> play the SFX
        move.b  2(a1,d1.w), d0
        movem.l a1/d1, -(sp)
        bsr.w   Sound_PlaySFX
        movem.l (sp)+, a1/d1
        addq.b  #2, SST_anim_frame(a0)
        bra.s   .after_event
```
Replace `.pf_evt_sound` (lines 351-355) identically but reading `1(a1,d1.w)`:
```asm
.pf_evt_sound:
        ; dc.b AF_SOUND, sound_id -> play the SFX
        move.b  1(a1,d1.w), d0
        movem.l a1/d1, -(sp)
        bsr.w   Sound_PlaySFX
        movem.l (sp)+, a1/d1
        addq.b  #2, SST_anim_frame(a0)
        bra.s   .pf_after_event
```
(Guard both with `ifdef SOUND_DRIVER_ENABLED` around the `bsr`/save-restore if the rest of the engine builds without the driver — check whether animate.asm is reachable in a no-sound build; if so, gate the calls.)
- [ ] **Step 4: Wire the player seams (jump/roll/rev/release/skid).** All gated `ifdef SOUND_DRIVER_ENABLED` (mirror game_loop.asm). Use `bsr.w` and preserve any live regs the contract requires.
  - **Jump** — `engine/player/player_ground.asm:718` (`Player_Jump` entry; covers ground + roll jump). After `clr.b (Player_JumpBuffer).w`:
```asm
Player_Jump:
        clr.b   (Player_JumpBuffer).w           ; consume the buffered press
      ifdef SOUND_DRIVER_ENABLED
        moveq   #SFXID_JUMP, d0
        bsr.w   Sound_PlaySFX
      endif
```
  - **Roll** — `engine/player/player_ground.asm:123-124` (`TODO: roll sfx`). After `bsr.w Player_SetState`:
```asm
        moveq   #PSTATE_ROLL, d0
        bsr.w   Player_SetState                 ; hook curls (+5px y-shift)
      ifdef SOUND_DRIVER_ENABLED
        moveq   #SFXID_ROLL, d0
        bsr.w   Sound_PlaySFX
      endif
```
  - **Spindash rev (per tap)** — `engine/player/player_spindash.asm:58` (after `addi.w #SPINDASH_CHARGE_STEP, _pl_spindash(a0)`):
```asm
        addi.w  #SPINDASH_CHARGE_STEP, _pl_spindash(a0)
      ifdef SOUND_DRIVER_ENABLED
        moveq   #SFXID_SPINDASH, d0
        bsr.w   Sound_PlaySFX
      endif
```
  - **Spindash release (Dash)** — `engine/player/player_spindash.asm:94-96` (`TODO: release sfx`). Before `bsr.w Player_SetState`:
```asm
        moveq   #PSTATE_ROLL, d0                ; release -> roll
      ifdef SOUND_DRIVER_ENABLED
        movem.l d0, -(sp)
        moveq   #SFXID_DASH, d0
        bsr.w   Sound_PlaySFX
        movem.l (sp)+, d0
      endif
        bsr.w   Player_SetState
```
  - **Skid (fresh-arm edge only)** — `engine/player/player_common.asm:336` (`.skid_show`, the not-already-latched path). After `st _pl_skid_latch(a0)`:
```asm
.skid_show:
        st      _pl_skid_latch(a0)              ; fresh-arm edge (line 327 returns if already latched)
      ifdef SOUND_DRIVER_ENABLED
        moveq   #SFXID_SKID, d0
        bsr.w   Sound_PlaySFX
      endif
        move.b  #ANIM_SKID, SST_anim(a0)
        rts
```
- [ ] **Step 5: Wire the ring-collect seam (stereo-alt).** In `engine/objects/rings.asm:250`, the pickup point (`addq.w #1,(Ring_Counter).w`) is inside a backward `dbf` loop with `d6`=index and `a2`=player ptr live. `Sound_PlayRing` touches only `d0/a0/SR` — safe. Replace:
```asm
        addq.w  #1, (Ring_Counter).w            ; <-- ring pickup point
```
with:
```asm
        addq.w  #1, (Ring_Counter).w            ; ring pickup point
      ifdef SOUND_DRIVER_ENABLED
        bsr.w   Sound_PlayRing                  ; L/R-alternating ring SFX ($33/$34)
      endif
```
- [ ] **Step 6: Death/ring-loss seams (where the player states live).** Locate the hurt/death player-state transitions (the spec lists Death `$35`, RingLoss `$B9`). Add `ifdef`-gated `moveq #SFXID_DEATH,d0 / bsr.w Sound_PlaySFX` at the death-state entry and `moveq #SFXID_RINGLOSS,d0 / bsr.w Sound_PlaySFX` at the ring-loss/hurt entry. If those states aren't implemented yet in the player, note it in the plan output as a gap (wire when the state exists) — do NOT invent a call site.
- [ ] **Step 7: Build + verify the API path end-to-end.** `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe`. In Exodus, play in-game: jump, collect a ring, spindash, release — confirm via `emulator_get_channel_states` + audio that each fires the right SFX through the real 68k→Z80 path (not a manual mailbox poke). Confirm ring L/R alternates (two pickups → opposite pan). Expected: real gameplay triggers the SFX.
- [ ] **Step 8: Commit.**
```bash
git add engine/sound_api.asm engine/z80_sound_driver.asm engine/objects/animate.asm engine/player/player_ground.asm engine/player/player_spindash.asm engine/player/player_common.asm engine/objects/rings.asm ram.asm
git commit -m "feat(sound): Sound_PlaySFX API + SND_REQ_SFX dispatch + ring L/R alternation + wire AF_SOUND/jump/roll/rev/release/skid/ring seams"
```

---

## Task 12: StopMusic/song-change reconciliation + edge cases + DEBUG hotkey + acceptance

**Goal:** StopMusic clears all overrides + kills SfxChannels; PlayMusic mid-SFX reconciles; a DEBUG SFX-trigger hotkey fires each SFX for capture; final in-game acceptance verified by rendered audio.

**Files:** Modify `engine/sound_sfx.asm`, `engine/z80_sound_driver.asm`, `engine/sound_sequencer.asm`, `engine/game_loop.asm`.

- [ ] **Step 1: `Sfx_StopAll` (clear overrides + kill SfxChannels + drop the queue).** Implement in `engine/sound_sfx.asm`: for each of the 11 music `SeqChannel`s, `res SCF_SFX_OVERRIDE_B,(ch+sc_flags)`; for each of the 7 SfxChannels, `res SCF_ACTIVE_B` + `clr sx_priority`; clear the queue (`SND_SFX_QUEUE_HEAD/TAIL/CNT = 0`); reset `SND_SFX_DUCK_LEVEL`/`SND_SFX_DUCK_TARGET = 0`. No multiply. Used by StopMusic so the next song starts clean (spec §11).
- [ ] **Step 2: Wire `Sfx_StopAll` into StopMusic.** In `engine/z80_sound_driver.asm` `.music_stop` (line 502-504), after `Sequencer_StopAll`:
```asm
.music_stop:
        call    Sequencer_StopAll        ; key-off FM + silence PSG + clear active flag
        call    Sfx_StopAll              ; Phase 5a: clear overrides + kill SfxChannels + queue
        call    Snd_TimerA_Disable       ; stop Timer A so no more ticks fire
```
- [ ] **Step 3: PlayMusic-mid-SFX reconciliation.** `Snd_LoadSong`'s `.seq_clr` wipe (lines 844-852) zeroes every `SeqChannel` (clearing stale override bits — correct, a fresh song has no overrides). But still-active SfxChannels now own physical voices the new song's channels will fight. Add `Sfx_Reconcile` (in `engine/sound_sfx.asm`), called from `Snd_LoadSong` AFTER the channel init completes: for each ACTIVE SfxChannel, re-`set SCF_SFX_OVERRIDE_B` on the NEW music `SeqChannel` whose `sc_route` matches the SfxChannel's owned physical route — so the new song doesn't write to a voice an SFX is using. (Simpler, spec-acceptable alternative: `Snd_LoadSong` calls `Sfx_StopAll` so a song change cancels in-flight SFX. Pick `Sfx_StopAll` for v1 unless the user wants SFX to survive a music change — document the choice; SFX are short.) Implement the `Sfx_StopAll`-on-load variant for v1 simplicity and note `Sfx_Reconcile` as the 5b upgrade.
- [ ] **Step 4: Edge-case sweep.** Confirm in code: (a) priority cleared on SFX end (Task 7/9); (b) noise/PSG3 restore (Task 7); (c) FM6↔DAC mutual exclusion is moot (FM6 `SFXEL_NONE`), documented; (d) `Sfx_Frame` runs even with no music (Task 6 Step 4). Add a one-paragraph comment block in `engine/sound_sfx.asm` listing these guarantees.
- [ ] **Step 5: DEBUG SFX-trigger hotkey.** In `engine/game_loop.asm` `Debug_MusicToggle` (or a sibling `Debug_SfxToggle`, gated `ifdef __DEBUG__ / ifdef SOUND_DRIVER_ENABLED`), mirror the `BUTTON_A` edge-detect pattern (lines 37-43) to fire each test SFX on a button/d-pad combo for VGM capture. Example using B + a direction to cycle through `SFXID_JUMP/RING_RIGHT/SPINDASH/DASH/ROLL/SKID/DEATH/RINGLOSS`:
```asm
        move.b  (Ctrl_1_Press).w, d0
        andi.b  #BUTTON_B, d0
        beq.s   .no_sfx_dbg
        moveq   #SFXID_JUMP, d0          ; (cycle via a Dbg_Sfx_Sel index for full coverage)
        bsr.w   Sound_PlaySFX
.no_sfx_dbg:
```
Make it cycle through all eight ids (a `Dbg_Sfx_Sel` RAM byte incremented per press, indexing an id table) so each can be captured. Verify `Ctrl_1_Press` + `BUTTON_B` don't collide with the existing A/START handlers.
- [ ] **Step 6: Build + full acceptance (rendered audio).** `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe`. In Exodus, play Moving Trucks and run the acceptance matrix via the DEBUG hotkey AND real gameplay:
  - Each SFX (jump/ring/spindash/dash/roll/skid/death/ring-loss) sounds — `emulator_vgm_start` → fire each → `vgm_stop` → `vgm2wav`, confirm each is audible.
  - The music NEVER loses its lead/bass through steal→restore (compare the rendered music spectrum during/after SFX vs a clean capture — lead+bass energy preserved).
  - No desync (the song resumes mid-phrase; `emulator_z80_read` shows cursors advancing through overrides).
  - Ducking works (spindash/dash/death dip the music then ramp back; rings don't).
  - StopMusic mid-SFX → clean (post Stop while an SFX runs; confirm no hung voice).
  Record the rendered-audio verdicts (energy + spectrum, per the verify-real-output rule). Expected: all acceptance criteria pass.
- [ ] **Step 7: Commit + merge.**
```bash
git add engine/sound_sfx.asm engine/z80_sound_driver.asm engine/sound_sequencer.asm engine/game_loop.asm
git commit -m "feat(sound): StopMusic/song-change SFX reconciliation + edge cases + DEBUG SFX hotkey + Phase 5a acceptance"
```
Merge `feat/sound-phase5a-sfx` → master once acceptance passes and the music regression holds (per CLAUDE.md git workflow). Keep `ENGINE_ARCHITECTURE.md` §6 in sync with the shipped SFX engine.

---

## Notes for the implementer

- **Gate the writes, not the loop** (the load-bearing half of steal): `Sequencer_Channel`/`.note`/`.rest` MUST keep advancing the overridden music channel's cursor (sets `SCF_KEYED`, reloads duration, commits `sc_stream_ptr`) or the song desyncs and won't resume mid-phrase. Only `ModUpdate` + the 4 `Seq_Hook*` + `Seq_Op_NoteRaw`/`Seq_Op_RegDelta` emit chip writes — gate exactly those (Task 3).
- **No register snapshots anywhere** (spec §5): restore re-derives everything — `Fm_PatchPtr`(music `sc_patch`)→`Fm_PatchLoad`→`Fm_SetVolume`(music `sc_volume`), then a forced re-key of `sc_note` if `SCF_KEYED`. The music channel's `sc_patch`/`sc_volume`/`sc_note`/`sc_pan` survive the steal because steal only sets the override bit + key-offs the chip — it must NOT overwrite those fields.
- **ix preservation is a project-critical contract** (sound_psg.asm L50-53 documents a prior bug from a false clobber comment): every `Fm_*`/`Psg_*` writer preserves `ix`; the SFX interpreter + steal/restore must `push ix`/`pop ix` around any work that re-points `ix` at a music channel.
- **de=$4001 invariant:** all FM writers use ABSOLUTE YM addressing + re-park `$2A` (`Fm_ReparkDac`); PSG writers never touch `$4000-3`/`de`. New SFX YM writes must go through these writers, never raw `ld (de),a`. `Sfx_Frame` clobbers `de`; the idle/timer ticks restore `de=$4001` after `Sequencer_Frame` (and now after the `Sfx_Frame` tail-call) — verify the restore still covers it.
- **PSG3↔noise coupling** is implicit and unhandled today (`Psg_Noise` writes only `$E0` control + `$F0` vol, never PSG3's tone register). A noise SFX with rate-bits `0b11` borrows PSG3's tone latch — save PSG3's `sc_note` on a noise steal, re-`Psg_NoteOn` PSG3 on restore (Task 7).
- **Design-for-C / build-for-A:** keep the SfxHeader's `SHF_CONTINUOUS`/`SHF_LOOP` bits + the continuous-extend hook (Task 9) + the FM6 `SFXEL_NONE` table entry present-but-dormant so 5b (held loops, distance, FM6-as-SFX) is purely additive — no format or struct migration.
- **Verify rendered audio, never a register proxy** (the verify-real-output rule): a key-on stream can be 100% correct yet inaudible. Every acceptance check renders VGM→wav and compares energy + spectrum (SFX audible AND music foundation intact).
- Each task: build (`-pe`), verify in Exodus + (transcoder) pytest, commit. Frequent commits — never lose work.
