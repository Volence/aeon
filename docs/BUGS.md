# Known Bugs

Open defects with reproduction notes and any captured live-emulator evidence. Newest first.
(Distinct from `DEFERRED_WORK.md`, which tracks deferred *features*, not defects.)

---

## BUG-002 — SFX gameplay-integration cluster (spurious triggers, wrong duration, rev churn)

**Status:** PARTLY FIXED (see each item). **Severity:** medium (audible wrongness, no crash).
**Reported:** 2026-06-21 by the user from live play: "when you walk and roll the SFX lasts too long and
gets weird at the end; spindash press-once-and-release-quick does no follow-up noises; rev a lot → weird
sounds; sometimes random things trigger sounds when they shouldn't — e.g. Sonic in the air triggers the
jump noise without jumping; a few others I can't reliably trigger."

### Common systemic thread — the 1-byte SFX mailbox (deferred A2)
The 68k posts SFX to a SINGLE byte (`SND_REQ_SFX` $1F03). **Two SFX in one frame → the second clobbers the
first → one is dropped.** This is the deferred A2 item (DEFERRED_WORK.md). Several symptoms below are this
collision surfacing in real play. A small ring-buffer mailbox (A2) is the systemic fix; the per-bug fixes
below remove specific collisions at the source.

### Item 4 + Item 2 — spurious roll-jump SFX after a spindash launch — **FIXED 2026-06-21**
**Root cause (data-flow traced, not guessed):** charge-mashing JUMP latches `Player_JumpBuffer`; `.rev`
consumes it each rev, BUT the release frame runs `.release` (never `.rev`), so a jump press landing in the
buffer window at the moment of release is never consumed. `.release` → `jmp PState_Roll`, and `PState_Roll`
(player_ground.asm:327) fires `Player_Jump` on any set buffer → (4) the jump SFX `$62` plays "in the air"
right after the launch + the player roll-jumps without an intentional press; AND (2) that same frame the dash
`$B6` and the spurious jump `$62` both hit the 1-byte mailbox → one drops → "no follow-up noise" on a quick
spindash. **Fix:** `clr.b (Player_JumpBuffer).w` at the spindash launch (player_spindash.asm `.launch`,
before `jmp PState_Roll`) — drops the stale charge press; a FRESH press after launch still roll-jumps.
**Verify when emulator reloaded:** spindash + mash jump + release → no airborne jump chirp; the dash plays.

### Item 1 — roll SFX "lasts too long and gets weird at the end" — **FIXED 2026-06-21**
**Ruled out** re-trigger-per-frame (roll/skid each fire ONCE). A 73-agent + adversarial-verify root-cause
pass found the real cause is in the **transcoded blob**: the roll `$3C` tail is a 42-pass `smpsLoop` whose
body has a per-pass `smpsFMAlterVol $01` (cumulative attenuation → fade to silence). Our engine has no
relative-AlterVol opcode, so the transcoder COLLAPSED the fade to ONE constant `MEV_VOL` inside a
`RepeatStart/RepeatEnd` body, which the engine replays identically every pass → the tail held flat at near-
full volume then HARD-CUT (= "lasts too long / weird at the end"). A secondary divergence: `smpsNoAttack`
was a transcoder no-op, so each pass re-keys the FM envelope (a stutter). NB the user's "walk" was the roll
FM tail — skid `$36` is byte-faithful PSG (no AlterVol; verified).
**Fix (transcoder-only — the Z80 driver has just 4 bytes free, so no new opcode):** `tools/sfx_transcode.py`
now UNROLLS an AlterVol-bearing `smpsLoop` into per-pass `Vol`+note events, walking the TL attenuation up by
the S&K per-pass delta and inverting `LogVolumeLutZ` to the `sc_volume` index that renders it — a dB-faithful
`+1 TL/pass` decay-to-quiet (regression test asserts each pass == +1 attenuation). Roll Vol now fades
`99→…→20`. **Deferred:** honoring `smpsNoAttack` (suppress the per-pass re-key) needs a Z80 no-key-on note
path — no room until bytes are reclaimed; the restored fade makes the re-key quiet, so re-evaluate by ear.

### Item 3 — "rev spindash a lot → weird sounds" — **FIXED 2026-06-21**
**Primary cause (confirmed):** the spindash `$AB` loop body is the SMPS bare-duration "replay previous note"
idiom (`dc.b smpsNoAttack, $02`); the transcoder dropped the standalone duration byte, so the `$AB`
`RepeatStart/RepeatEnd` body had **zero time-advancing events** → the Z80 ran all 24 reps in one frame and
fell to END → the rev played only its ~24-frame attack then stopped dead, and every rev tap re-fired that
truncated, tail-less attack (= "weird"). The same AlterVol-collapse (Item 1) flattened what little tail
existed. **Fix (transcoder-only):** (a) `_process_dcb` now implements the bare-duration replay (re-articulate
the previous pitch), restoring the loop body's timing; (b) the AlterVol unroll restores the per-pass fade.
`$AB` tail now has 24 note re-articulations fading `95→…→16`. The monotonic mod-sweep and `$10` transpose
clamp were verified **faithful — left unchanged**. A defensive packer backstop now rejects any
`REPEAT_START..REPEAT_END` body with no time-advancing event (the collapse class) for all SFX and music.

### Items 1 + 3 follow-up — re-key buzz + swept-pitch linger — **FIXED 2026-06-21 (hardware-verified)**
User retest after the fade fix: roll had "a higher pitch noise after", spindash-hold made "a jingle after a
second", and the spindash-release linger sounded "too high". VGM capture of OUR ROM proved the cause: the
unrolled tails RE-KEYED the FM envelope every pass (43× roll on `$28`/chsel `$04`, 26× spindash chsel `$05`,
at 30 Hz) = the jingle; and with the re-key gone the tail would have held at the modSet *swept* pitch
(spindash fnum `1912`) = the "too high" linger. Fix (the deferred `smpsNoAttack`, now done — see
DEFERRED_WORK B4): bit 7 of a NoteDur pitch = no-attack; `Seq_Op_NoteDur` skips the note-on hook for a held
note (4 Z80 bytes, the exact free budget); the transcoder holds all tail passes EXCEPT the first-after-modSet
(which re-keys to reset the swept pitch to base). **Re-captured & verified:** KEY-ON 43→2 / 26→2, tail holds
at base fnum (`1364` / `1288`, not swept), TL fade intact (`5→48` / `0→54`).

### Items 1 + 3 follow-up #3 — transition re-key click ("second faint spin") — **FIXED 2026-06-22**
The held-tail fix left ONE re-key at the main→tail seam (43→**2**): the main note sweeps up via its modSet,
then the first tail note re-keyed to reset the swept pitch to base — a faint "second attack" the user heard
as "a second more faint spin noise" on the momentum roll. **Fix:** `Seq_Op_ModSet` now, for an SFX FM channel
(route `< CHROUTE_PSG1`), re-writes the unmodulated `sc_base_freq` via **`Fm_WriteFreq`** — which changes a
HELD note's `$A4/$A0` with NO `$28` key-on (the vibrato path) — so when the sweep modSet turns off the tail
snaps to base with no re-key; the transcoder then holds ALL tail passes (dropped `_emit_notedur`'s
first-after-modSet exception). The +18 Z80 bytes were reclaimed by folding 6 more inline channel-class tests
into `Snd_ChanClass` (`Z80_SOUND_SIZE` back to `$16EE`, 2 free — *at this fix; post music-expr Task 0 banking +
Phase 1/3 the live value is now $1618 / 216 B free*). **Verified on hardware:** roll & spindash
KEY-ON **2→1**, fades still `5→53`/`0→54`, tails held at base — and a regression sweep confirmed skid/ring/
jump/dash all still sound (no fallout from the PSG-path conversions). The roll/spindash tails are now a single
clean attack fading smoothly to silence — fully S&K-faithful (one key-on, like S&K).

### Items 1 + 3 follow-up #2 — "distorted jingle for a bit" — **FIXED 2026-06-21 (RENDERED-audio verified)**
After the held-tail fix the user still heard "a distorted jungle [jingle] after them for a bit." The `$28`
re-key count was a PROXY; rendering the capture to WAV (vgm2wav) showed the truth: the roll RMS only faded
`1.00→0.68` then **plateaued**, and the spindash barely faded — yet one carrier's TL walked a full 32 dB.
Root cause: for alg-4 voices there are TWO carriers (S2+S4); only ONE faded. `Fm_SetVolume` reads the
algorithm/carrier-mask + base TLs via `Fm_PatchPtr`, which resolves `sc_patch` into the MUSIC patch table
`SND_SEQ_PATCHTAB` — but SFX channels load their voice from `sx_patch_base` and never set `sc_patch`, so
EVERY SFX volume write used a stale/empty patch's algorithm → wrong carrier mask → faded the wrong/one
carrier. Latent until now because one-shot SFX have constant volume; the fade fix exposed it. **Fix:**
`Fm_PatchPtr` returns `sx_patch_base` for SFX channels (`engine/sound_fm.asm`); `Sfx_Restore` passes the
MUSIC channel so its path is unaffected. The Z80 was at its $16F0 ceiling, so the bytes were reclaimed by
merging the two SFX gates in `Fm_NoteOnFreq` + factoring the 12-site `push ix/pop hl/ld a,h/cp` channel-class
test into `Snd_ChanClass` (5 sites converted; `Z80_SOUND_SIZE` now `$16EE`, 2 free — *at this fix; live value
post music-expr Task 0 banking + Phase 1/3 is $1618 / 216 B free, see DEFERRED_WORK F1/F5*). **Rendered-audio
verified:** both carriers (`$48`+`$4C` roll, `$49`+`$4D` spindash) now fade `5→53` / `0→54`, and the audio
RMS decays to `0.02` (fades to silence) — no plateau, no distortion. The roll/spindash tails are now a clean
held note fading smoothly to silence (S&K-faithful). LESSON: the `$28` count was a proxy; only the rendered
WAV envelope revealed the un-faded carrier.

### BUG-003 — dash `$B6` "duh" = PSG noise rendered as a TONE — **FIXED 2026-06-21**
After the FM tails were clean the user heard a "duh..." after the spindash (the *release* fires the dash
`$B6`). The dash's PSG3 channel uses `smpsPSGform $E7` (noise mode) — its release is meant to be **white
noise**. But the transcoder routed it as `CHROUTE_PSG3`/`SFXEL_PSG` (a TONE voice) and dropped the
`smpsPSGform` opcode ("handled via sx_kind" — but sx_kind was *tone*), so the engine played an audible
descending TONE on PSG ch2 = the "duh." (Pre-existing; unrelated to the FM work — exposed once the FM was
clean.) **Fix (transcoder):** pre-scan a PSG channel for `smpsPSGform`; if present, reroute it to
`CHROUTE_PSGN`/`SFXEL_NOISE` and emit a fixed white-noise mode note (`$E6`, clk/2048), dropping the
tone-only modulation. **Verified on hardware:** the dash now writes the noise control `$E6` + ch3 noise
volume fading `5→15`, ZERO ch2 tone writes; rendered audio spectral-flatness `0.667` = broadband noise (was
tonal), fading to silence. **Refinement deferred (DEFERRED_WORK B5):** S&K's `$E7` is white noise *tracking
PSG3's swept tone frequency* (a descending-pitch "pshhew"); reproducing that needs the engine to drive PSG3's
frequency as the noise clock (or a tone-clock + noise channel split). The fixed-rate noise is the right
*character*; the pitch sweep is the remaining nuance.

### "A few others" (user can't reliably trigger)
Most likely further instances of the 1-byte-mailbox collision (A2) — any frame that fires two SFX (e.g.
ring + skid, jump + ring). Tracked under A2 in DEFERRED_WORK.md; the ring-buffer mailbox resolves the class.

---

## BUG-001 — Section-streaming rendering corruption (background → garbage tiles + red field)

**Status:** OPEN. **Severity:** high (game becomes unplayable in that area). **Reproducibility:** INTERMITTENT
— happens "every now and then," often (but not always) right after a spindash. The user could NOT reliably
re-trigger it, so the live evidence below was captured from a single frozen occurrence (2026-06-21) and is the
primary record — a restart loses it.

**Screenshot:** `docs/research/bug_streaming_corruption_2026-06-21.png` — the whole background is a RED field
filled with a repeating grid of garbage tiles; the Sonic **sprite is intact**; the DEBUG HUD reads
`COL: need layout co…`.

### Symptom
The BACKGROUND planes render garbage tiles over a red backdrop. Sprites (player) are unaffected.

### NOT a crash, NOT sound
- 68k `PC = 0x1DD4` — the normal main-loop wait (`Process_DMA_Critical` region). CPU running fine; SR=$2600.
- The player sprite renders correctly → sprite VRAM + sprite palette are intact. This is a **plane / level-art /
  backdrop** corruption only.
- Unrelated to the sound work in this session.

### Live-emulator evidence (frozen frame, 2026-06-21)
- **Player** (object list): x=1301 (`$0515`), y=694 (`$02B6`). **Vel 0,0** (stopped). In section **(0,0)**.
- **Camera_X = `$04770000`, Camera_Y = `$02420000`** (16.16). Cam X=1143 — still inside section 0
  (`SECTION_SIZE = $0800` = 2048px), so `Sec (0,0)` is CORRECT; this is NOT a section-index mismatch.
- **`Section_Stream_State` ($FFA8EC): section 0 = `$02` (SS_RESIDENT), section 1 = `$02`, rest `$00` (IDLE).**
  → the engine believes section 0 (the player's section) is fully loaded.
- **`Slot_Section_Map` ($FFA8E0): slot0=(0,0) slot1=(1,0) slot2=(0,0) slot3=(0,0).**
- **`Tile_Cache_Nametable` (RAM $FF0000): BLANK — uniform tile-0 entries (`1000 0000` repeating).** The RAM-side
  section nametable cache holds no real art. (NOTE: `Decomp_Buffer` *aliases* `Tile_Cache_Nametable`,
  ram.asm:28 — a decompress firing during a streaming event would clobber this cache. Strong suspect.)
- **VRAM level-art region ($0000+): sparse / incomplete** — mostly zeros with a few stray bytes per tile;
  the section art is not actually resident in VRAM.
- **VRAM plane nametable (~$C000): GARBAGE** — random tile indices (`43BE 43F7 B8A7 33BF…`) mixed with
  repeating blank-tile entries (`00000001`, `00000004`). (Note: VRAM garbage ≠ the RAM cache's uniform blank,
  so the VRAM may be STALE pre-corruption content the DMA never overwrote — worth confirming the plane base.)
- **CRAM palette line 0 index 0 = `$000E` (pure RED, R7G0B0); lines 1-3 index 0 = `$0000` (black).** The
  backdrop entry alone is red → the red field. (Determine: is this a DELIBERATE debug "missing-layout" warning
  the engine paints, or palette corruption? Lines 1-3 being correct suggests a targeted write, i.e. likely a
  debug indicator paired with the `COL: need layout` HUD.)
- **No fill stuck:** `Cache_Fill_Resume_Col` = `$FFFF`, `Cache_Fill_RowResume_Row` = `$FFFF` (both "none
  pending"). So it is NOT a half-finished/interrupted tile-cache fill.
- `Section_Plane_Dirty` ($FFA8EA) = `$00` (no full redraw pending). `Section_Teleport_Guard` ($FFA8E9) = `$00`.
- `Section_Top_Row_Written` = `$0002`, `Section_Bottom_Row_Written` = `$003B`. `Lag_Frame_Count` = `$28` (40).
- HUD overlay: `COL: need layout co…` — the engine itself flagged that the **collision layout for the player's
  position is not loaded.**

### Diagnosis
**Section-streaming state↔data DESYNC: section 0 is flagged `SS_RESIDENT`, but its art (VRAM tiles + RAM
nametable cache) and collision LAYOUT are not actually loaded.** The engine even self-detects the missing
collision (`COL: need layout`). So a streaming event marked the section resident WITHOUT (re)loading its
art/collision, and the fill/DMA then drew the empty/blank cache → garbage tiles over the red backdrop.

### Leading suspects (unconfirmed)
1. **Teleport/rebase "pure rebase, no redraw" path** treating the section as already-resident and SKIPPING the
   art/collision (re)load in an edge case where the data wasn't actually present. (See `engine/level/section.asm`
   teleport/rebase; memory `project_teleport_rebase` — "teleports are pure rebases, reinit/redraw removed".)
2. **`Decomp_Buffer` aliases `Tile_Cache_Nametable`** (ram.asm:28). A decompress during the streaming event
   would overwrite the nametable cache → blank/garbage cache → blank/garbage VRAM after the next fill/DMA.
3. **Race/timing edge case** — the intermittency + the spindash trigger (fast camera jump stressing the
   streamer) point to a timing window, not a deterministic path.

### Recommended next step (its own focused session)
Reproduce with a **watchpoint** to trap the corrupting moment:
- Watch `Section_Stream_State + 0` (section 0's state byte) for a write to `$02` (resident) and check, at that
  instant, whether the art-load / collision-load actually ran. OR
- Watch the `Tile_Cache_Nametable` region for the write that blanks it (catch the aliased decomp clobber). OR
- Watch CRAM line-0 index-0 for the `$000E` write (find whether it's the debug warning or corruption).
Then trace backward from the trigger (spindash launch → camera jump → which section routine fires).
This is an **engine/section-streaming** bug — separate from sound. Do NOT guess a fix; trace the corrupting write.
