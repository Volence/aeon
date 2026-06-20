# Sound Phase 5a — Core SFX Engine (S3K-sourced, classic-faithful + dynamic + ducking)

**Date:** 2026-06-20
**Status:** Design approved (brainstorming, 2026-06-20)
**Branch:** TBD (`feat/sound-phase5a-sfx` suggested)
**Builds on:** Phase 1 (1A/1B/1C) + Phase 3a FM depth + native Moving Trucks, merged to master
(`c89bea3`). Reuses the per-frame ModUpdate sequencer, the FM/PSG writers, the FM patch loader,
and the 68k↔Z80 mailbox.
**Drives / acceptance test:** the game makes the right sound when you play it — jump, ring,
spindash rev, dash/release, roll, skid (plus death / ring-loss) — using **real Sonic 3 & Knuckles
SFX**, with the music's lead and bass never dropping out.

---

## 1. Goal & scope

Turn the engine from "plays a demo song" into "the game makes sounds." This is the **core SFX
engine** — the first of four Phase-5 sub-projects. It delivers a classic-faithful channel
steal/restore mechanism, priority arbitration, ducking, dynamic voice selection, the 68k `PlaySFX`
API + Z80 dispatch, an **S3K SFX transcoder**, and wiring of the existing no-op game seams.

**In scope (5a):**
- The SFX voice mechanism: override-flag steal + clean restore (no register snapshots).
- Dynamic-among-eligible channel selection + per-voice priority stealing.
- A per-SFX priority model (authored, since S3K has none).
- Ducking (transient music attenuation under high-priority SFX).
- SFX data format + `tools/sfx_transcode.py` (skdisasm SMPS SFX → our format).
- `Sound_PlaySFX` 68k API + `SND_REQ_SFX` Z80 dispatch + a small priority-gated queue.
- Wiring `AF_SOUND` (animation events) + the player SFX TODO seams to real calls.
- The core-movement SFX set transcoded from S3K: Jump `$62`, Ring `$33`/`$34`, Skid `$36`,
  Roll `$3C`, Spindash `$AB`, Dash `$B6`, plus Death `$35`, RingLoss `$B9`.

**Out of scope (later Phase-5 sub-projects):**
- **5b** — `PlaySoundLocal` distance attenuation; true held-loop continuous SFX (shield buzz,
  speed shoes, drowning).
- **5c** — music triggered by game events (level/zone/boss/title), the music-fade state machine,
  section-aware music banking.
- **5d** — procedural ambient soundscape.
- **Sampled / DAC SFX** — needs the Phase-2 N-channel DAC mixer (and unblocking the multi-sample
  loop-restart latent bug). None of the 5a core SFX use DAC.

**North star (non-negotiable):** best-in-class. "Best" = the best *result* for our hardware
constraints, reasoned per-technique — not the most machinery. We adopt the classic
steal/override model **because it is genuinely optimal for a tight 6-FM + 4-PSG voice budget**
(permanently reserving SFX channels would gut every song), and we add only the modern techniques
that improve the actual outcome here (dynamic selection, ducking, priority), while deliberately
**not** building abstract voice pools / virtual voices / global voice-stealing — those add
complexity without a result gain on non-interchangeable channels (FM6=DAC, PSG3↔noise, FM3 special)
with short, low-polyphony SFX. **Design-for-C / build-for-A:** lay out the format + hooks so the
deferred capabilities (continuous loops, distance, FM6-as-SFX, deeper stealing) are purely additive.

## 2. Research basis (done)

A 7-source survey (S2, S3K, Flamedriver/S.C.E., Batman/Zyrinx, Gunstar, a Vectorman/Alien
Soldier/TF4/Ristar sweep, and online+modern) found an overwhelmingly consistent mechanism. Key
findings this design rests on:

- **Steal = a single override flag, never a register snapshot.** Every classic driver sets a "SFX
  is overriding this channel" bit on the music track; while set, the music interpreter keeps
  advancing its cursor but all its chip writes are gated off, so the song never desyncs and resumes
  mid-phrase. (S2 `s2.sounddriver.asm` PlaybackControl bit 2; S3K `Z80 Sound Driver.asm` `set 2,(hl)`
  at L2003; Flamedriver `bitSFXOverride`.)
- **Restore = clear flag + re-assert the music voice** (re-upload the FM patch from the stored
  voice index, let the next note re-key). No snapshot buffer. (S2 `zStopSoundEffects` →
  `zSetVoiceMusic`; S3K `cfStopTrack` re-upload L3490-3511.)
- **Protect the foundation:** SFX never steal FM1/FM2 (lead/bass) or the music DAC; they take the
  high voices FM3/FM4/FM5 + PSG1/2/3 + noise. (S2 rule "no SFX may use DAC, FM1, FM2, or FM6.")
- **Priority splits precedent:** S2 has a per-SFX priority byte (drop-if-lower); S3K/Flamedriver/
  Zyrinx/Gunstar dropped it (last-writer-wins, a known weakness). We re-add it.
- **PSG noise borrows PSG3's frequency** — noise SFX must save/restore PSG3's tone register.
- **Caveat for our engine:** SMPS songs re-send the instrument every note; our event-list songs set
  it once. So our restore must **explicitly** re-upload the music patch (which S3K/Flamedriver do
  anyway) rather than rely on implicit re-assertion.

S3K SFX confirmed FM/PSG-only for the core set (Jump=cPSG1, Ring=cFM4, Skid=cPSG1+cPSG2, Roll=cFM4,
Dash=cFM5+cPSG3), each carrying its own `smpsHeaderVoice` table — validating both the eligibility
model and the "SFX bring their own instrument" approach.

## 3. Architecture

A parallel SFX interpreter layered over the music sequencer, sharing the chip-writer code:

- **`engine/sound_sfx.asm`** — a fixed array of **`SfxChannel`** structs (one per concurrently-
  soundable SFX voice; sized to the stealable set: 3 FM + 3 PSG + noise). Each reuses the per-frame
  ModUpdate event-list interpreter. An SFX is a tiny song + an **SFX header**.
- Runs Z80-autonomously each frame **after `Sequencer_Frame`**, so SFX hardware writes land last
  and own the channel.
- Data in **`data/sound/sfx/`**, transcoded from S3K. The reserved `SND_REQ_SFX` mailbox slot
  (`sound_constants.asm:23`) becomes live.

## 4. Channel model & eligibility

- Each physical voice (FM1–6, PSG1–3, noise) has a current **owner** (music vs SFX), tracked by a
  new **`sc_sfx_override`** bit on the music `SeqChannel` plus the `SfxChannel`'s own active state.
- **Eligibility is a build-time data table** (`SFX_ELIGIBLE`), not hardcoded/SMC:
  - **FM1, FM2 — never stealable** (lead/bass always survive).
  - **FM3, FM4, FM5 — stealable.**
  - **PSG1, PSG2, PSG3 — stealable; noise — stealable** (coupled to PSG3, see below).
  - **FM6 — reserved in v1** (it is the DAC, or a music FM voice in DAC-off songs). The table is laid
    out so FM6 can be opened to SFX later for DAC-off songs without a format change (design-for-C).
- **Dynamic-among-eligible selection:** the transcoded S3K channel is the SFX's **preferred**
  target; if it's busy, pick another free eligible voice **of the same kind** (FM↔FM, PSG↔PSG)
  before resorting to priority-stealing. More SFX sound at once; the lead is never at risk.
- **PSG noise / PSG3 coupling:** periodic noise borrows PSG3's tone frequency, so a noise SFX
  saves and restores PSG3's tone register on steal/restore.

## 5. Steal / restore

- **Steal:** set `sc_sfx_override` on the chosen music channel(s); initialize the `SfxChannel`;
  key-off the channel; load the SFX's own FM voice. The music interpreter keeps advancing its event
  cursor, but the **chip-write sites in `sound_fm.asm` / `sound_psg.asm` gain a `sc_sfx_override`
  check** and early-return for an overridden channel — the song stays perfectly in time.
- **Restore (clean — our improvement over bare S3K):** when the `SfxChannel` ends →
  1. clear `sc_sfx_override`;
  2. re-upload the music channel's current FM patch (`Fm_PatchLoad` with its stored patch index),
     restore PSG noise/PSG3 register if touched;
  3. **if a note was sounding when the channel was stolen, force an immediate re-key** of the music
     channel's held note, so it resumes instantly rather than coasting silent until the next note
     event (the audible flaw in pure precedent); if the channel was between notes, just clear the
     override and let the next note key normally. No register-snapshot buffer anywhere.

## 6. Priority arbitration

- A **per-SFX priority byte** in the SFX header. Because dynamic-among-eligible selection runs
  first, priority only arbitrates when all eligible voices of the needed kind are busy: the
  incoming SFX steals the **lowest-priority current occupant** only if `incoming ≥ that`. A
  low-priority SFX can therefore never cut off a more important one (richer than S2's single global
  gate).
- **We author the priority bytes** (a table keyed by SFX id, consumed by the transcoder), from
  classic tiers — roughly `death/hurt > spindash > skid/roll > jump > ring/UI` — seeded from S2's
  `zSFXPriority` values for shared sounds.
- **Continuous-ready hooks (laid in now, full feature is 5b):** same-id continuous SFX *extends*
  rather than retriggers (prevents machine-gun pops); flagged-continuous priorities don't lock out
  later SFX. Spindash-rev is one-shot-per-tap so it is fully handled in 5a.

## 7. Ducking

- A global **music "duck level"** — a ramped envelope. A high-priority SFX bumps the level
  (transiently raising music carrier TL + lowering PSG volume so the SFX cuts through); on SFX end
  the level ramps back over a few frames. Cheap: reuses the per-op TL path the driver already drives
  for op-bias/volume.
- **Threshold-gated:** only SFX above a configured tier duck (collecting rings does not pump the
  music). The ramp envelope is structured to be reused by the 5c music-fade state machine.
- v1: fixed depth + linear ramp, both tunable constants.

## 8. SFX data format + S3K transcoder

- **Format** = our event-list (reusing ModUpdate events) preceded by an **SFX header**:
  `{ preferred channel + kind, priority byte, own FM voice (inline or table ptr), flags
  (continuous / stereo-alternate / loop) }`. A **`SfxTable`** indexes SFX id → blob.
- **`tools/sfx_transcode.py`** (fresh code, mirrors the Moving Trucks pipeline):
  - Parses skdisasm `Sound/SFX/*.asm`: `smpsHeaderSFXChannel`, `smpsHeaderVoice`, the event streams
    and coordination flags.
  - Reuses the MT voice-conversion to map S3K FM voices → our FM patch format.
  - Maps `cFMx`/`cPSGx`/noise → our preferred-channel + eligibility kind.
  - Emits our SFX blobs + the `SfxTable`.
  - **Any unsupported SMPS coord flag is flagged loudly** (build error), never silently dropped.
  - Applies the authored priority map keyed by SFX id.
- **Coord-flag coverage (v1):** note, duration, volume, pan, the spindash frequency-ramp, PSG noise
  mode, and loop — the subset the core set uses.
- **Build-time validation:** no SFX targets a reserved channel; each SFX's voices fit; the
  `SfxTable` is complete.

## 9. Request API + plumbing

- **68k (`sound_api.asm`):** `Sound_PlaySFX(id)` posts the id to the `SND_REQ_SFX` mailbox slot. Ring
  auto-alternates L/R internally (the `$33`/`$34` stereo pair) via a speaker toggle.
- **Z80 (`z80_sound_driver.asm`):** `SndDrv_PollMailbox` gains an `SND_REQ_SFX` handler →
  **`SfxDispatch`**: priority gate → eligible-voice select → steal → init `SfxChannel`.
- A small **2–3-deep priority-gated queue** so multiple requests in one frame aren't lost; queue
  overflow drops the lowest-priority pending entry.
- A symbolic **SFX-id header** (`sfx_*` equates) so gameplay refers to names, not hex.

## 10. Game integration seams

Replace the existing no-ops with real `Sound_PlaySFX` calls:

| Seam (file:line) | Today | Wire to |
|---|---|---|
| `engine/objects/animate.asm` `AF_SOUND` ($F9) handler | decodes id, no-ops | `Sound_PlaySFX(decoded id)` |
| `engine/player/player_ground.asm:56` | `TODO: rev sfx` | Spindash `$AB` (per rev tap) |
| `engine/player/player_ground.asm:124` | `TODO: roll sfx` | Roll `$3C` |
| `engine/player/player_spindash.asm:96` | `TODO: release sfx` | Dash `$B6` |
| jump init seam | (none) | Jump `$62` |
| skid state seam | (none) | Skid `$36` |
| ring-collect seam | (none) | Ring `$33`/`$34` (stereo-alt) |

(Hurt / death → RingLoss `$B9` / Death `$35` where those player states live.)

## 11. Error handling / edge cases

- **StopMusic while SFX active:** clears all `sc_sfx_override` + kills `SfxChannel`s so the next
  song starts clean.
- **PlayMusic mid-SFX:** the SFX finishes on its voice; the new song takes the rest; override bits
  reconciled.
- **Priority** cleared on SFX end so the next SFX of any priority can play.
- **Noise/PSG3 restore** verified (the periodic-noise gotcha).
- **FM6 ↔ DAC mutual exclusion** documented; moot in v1 (FM6 reserved), enforced by eligibility when
  FM6 is opened later.

## 12. Testing / verification

- **Transcoder pytest** (like the MT pipeline): round-trip a known SFX; assert event/voice/priority
  output; assert no SFX targets a reserved channel; assert `SfxTable` completeness.
- **Build:** `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` clean.
- **Exodus MCP:** channel-states/registers confirm steal sets the override + loads the SFX voice,
  and restore re-uploads the music patch + re-keys with **no silence gap**.
- **Rendered audio (per our verify-real-output rule):** VGM capture → vgm2wav to confirm SFX are
  audible *and* the music's lead/bass survive intact through steal→restore; confirm ducking dips the
  music then ramps back.
- A **DEBUG SFX-trigger hotkey** (à la the A-restart hotkey) to fire each SFX on demand for capture.
- **Acceptance:** play in-game — jump/ring/spindash/dash/roll/skid all sound, music never loses its
  foundation, no desync, clean restore.

## 13. Deferred / design-for-C hooks (built additively later)

- **Continuous held loops (5b):** the continuous flag + extend-not-retrigger hook are present now;
  5b adds the held-loop interpreter + stop API.
- **Distance attenuation (5b):** `PlaySoundLocal(id, distance, priority)` layers a distance→volume
  term (log-volume LUT already shipped) onto the existing priority/voice path.
- **FM6 as SFX voice:** opening FM6 in `SFX_ELIGIBLE` for DAC-off songs is a table edit, no format
  change.
- **Deeper voice management:** abstract pools / virtual voices / global lowest-priority-oldest-
  quietest stealing can layer on the eligibility+priority core if a real need ever appears
  (explicitly not built for v1 — no result gain on this budget).

## 14. References

- Research survey (this session): `s2disasm/s2.sounddriver.asm`, `skdisasm/Sound/Z80 Sound
  Driver.asm` + `Sound/SFX/*.asm`, `Sonic-Clean-Engine-S.C.E.-/Sound/Flamedriver.asm`, Batman/Zyrinx
  `disasm/sound/zyrinx_driver.asm`, `gunstar_disasm`, Alien Soldier/TF4/Vectorman/Ristar sweep,
  online SMPS SFX-override + Echo + MegaPCM + modern voice-management.
- Master sound spec: `docs/superpowers/specs/2026-06-16-sound-driver-design.md` (§12 Phase 5,
  PlaySFX/PlaySoundLocal/priority); command API: `docs/superpowers/specs/2026-06-16-sound-command-api.md`.
- Architecture: `docs/ENGINE_ARCHITECTURE.md` §6 (§6.4–6.7 are 5b–5d, deferred).
- S3K SFX ids: `skdisasm/sonic3k.constants.asm` (`sfx_Jump $62`, `sfx_RingRight $33`, `sfx_Skid $36`,
  `sfx_Roll $3C`, `sfx_Spindash $AB`, `sfx_Dash $B6`, `sfx_RingLoss $B9`, `sfx_Death $35`).
