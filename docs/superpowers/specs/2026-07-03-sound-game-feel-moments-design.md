# Sound Game-Feel Moments — Design (Banking Package 1)

**Date:** 2026-07-03
**Status:** BANKED design (spec + plan pattern, 2026-07-03 sound design-banking session;
execution open for any future session)
**Fills:** the #1 gap from `2026-07-01-sound-specs-review.md` §5 — "the one spec nobody
wrote: the ten sound moments of an actual Sonic playthrough."
**Supersedes:** `2026-06-16-sound-command-api.md` (marked OUTGROWN by the review) — §8
below is command-API v2, the living contract.
**Novel-mechanism flag (provenance rule):** the freeze-in-place + jingle-as-SFX auto-resume
model in §5 is assistant-authored and shipped by NO reference driver (each was surveyed).
It is code-only (no format bet, fully reversible) and directly implements the user's
2026-07-03 mid-song-resume decision. User decisions recorded in
`2026-07-03-sound-banking-queue.md`: mid-song resume after 1-up; DAC single-voice ratified.

---

## 1. Problem

The engine ships a best-in-class sequencer/SFX/expression stack but has NO mechanism for
the sound moments every Sonic playthrough hits: pause/unpause, the 1-up jingle and what
happens to level music after it, invincibility swap-back, drowning recovery, a
song-finished signal for act-clear/death sequencing, and safe fade composition. S3K ships
all of these; we currently ship none. (Review §3 playthrough table.)

**Goal state per moment** (floor = classic parity, exceed = better than S3K):

| Moment | Target |
|---|---|
| Pause/unpause | Music freezes + mutes; **SFX stay alive** (menu blips); unpause resumes exactly, no stuck notes, no pan loss |
| 1-up jingle | Music freezes mid-note; jingle overlays; music **resumes at the exact position** with a short fade-in (EXCEEDS S3K, matches S2's feel with none of its RAM-copy fragility) |
| Invincibility | Song swap in; swap-back **restarts** level music (classic-faithful; every reference restarts) |
| Drowning countdown | Song swap in; on surfacing/death, normal song load (restart) |
| Speed shoes | Global tempo mod on / authored-restore off (SHIPPED — `SND_REQ_TEMPO`); §7 adds the load-boundary rule |
| Act clear | Composed fade-out-and-stop → jingle → tally SFX, sequenced by 68k off the song-finished contract |
| Death / Game over / Continue | Jingle as normal song load; song-finished contract drives the 68k state machine |
| Musical cues | Score-authored comm byte (MDSDRV `get_comm` steal) — song data can signal the 68k (intro-done, loop-hit, stinger points) |

## 2. Research summary (checklist: 8 disassemblies + online + modern)

- **S3K/S2/S.C.E. (SMPS lineage)** — pause = FM pan-clear + key-off + PSG max-atten, then
  simply stop ticking the sequencer (state frozen in place); unpause re-writes pan shadows.
  1-up = full track-RAM `ldir` backup (~470 B) + bank/tempo/voice-ptr side-set; restore =
  copy back + full patch re-upload + $40 fade-in. Jingle end is detected by a coordination
  flag **inside the jingle's own score** ($E2 $FF), not a timer. Edge policies: jingle
  during fade = DROPPED; second 1-up = restart jingle WITHOUT re-backup (snapshot
  preserved). Known lineage bugs: restore fade-in TL overflow (Clone Driver v2 fix), S2
  mutes ALL sound during the jingle, stock unpause off-by-one (PSG treated as FM).
  (skdisasm `Z80 Sound Driver.asm` 1717-1790/2725-2790/2229-2600; s2disasm 1675-1724/3082-3159.)
- **B&R (Zyrinx)** — no music pause found; jingles ride idle FM channels over live music
  via the direct-injection mailbox; fade = carrier-TL ramp. (batman_driver_analysis.md §7.)
- **Ristar** — 68k-resident sequencer state makes pause/resume trivially game-side; 8-entry
  SFX queue with 68k-side channel allocation. (ristar_disasm ANALYSIS.md sound §.)
- **Vectorman / Gunstar / Alien Soldier / TF4** — checked; sound drivers are not covered by
  the v1 disasm analyses (no mechanism-level findings; recorded honestly, not skipped).
- **Modern (online):** **XGM/XGM2** — pause/resume with the honest caveat "resume will
  never be perfect, some notes miss until next key-on" (YM state is write-only); explicit
  stop≠pause; **composed fade terminals** `fadeOutAndStop`/`fadeOutAndPause` +
  `isProcessingFade`; command-race hardening (play/pause/resume made mutually exclusive
  after a shipped race; issue #117). **MDSDRV** — per-priority pause scope; fade with
  stop-on-complete flag; per-priority `get_status` track bitmask; **`get_comm`: a
  communication byte written by song data** — the only surveyed music→game cue channel.
  **Echo** — music-scoped pause (SFX unaffected); status word with an explicit BUSY
  back-pressure bit; per-channel volume vector. **GEMS** — N concurrent sequences with
  priority arbitration; global pause mailbox. **Community consensus:** nobody ships
  seek/set-position; song-end is always polled, never interrupted; no modern homebrew
  ships snapshot-resume (they duck/overlay or restart).
- **Our engine (internals audit, 2026-07-03):** SeqChannels 11×60 B at `$1A08-$1C9B`;
  global expr 7 B at `$1CCC`; `SND_SONG_BANK` `$18F1`; `SND_FM6_ADAPTIVE` `$18FC`;
  the old 512 B `$1B00` buffer NO LONGER EXISTS (2026-07-02 A.3 repack consumed it —
  SeqChannels now occupy the range; code headroom 792 B). Pause groundwork exists:
  `Sequencer_StopAll` already key-offs FM + silences PSG; `SND_SEQ_ACTIVE=0` already
  early-outs `Sequencer_Frame` to the SFX path. `SCF_KEYED` is NOT cleared by StopAll
  (Stage-A field lesson) — restore paths must gate on it. Tempo/fade state snaps to the
  song header on EVERY load (`sound_sequencer.asm:1223-1225`). Mailbox slots `+$07..$0F`
  free; status block has room after `+$14`.

## 3. Design overview

Three engine pillars + one 68k layer:

1. **Pause engine** (§4) — a dedicated music-scoped freeze, distinct from stop.
2. **Jingle push/pop** (§5) — freeze-in-place + jingle-as-multi-channel-SFX + driver-side
   auto-resume. Zero-byte snapshot: because our SFX tier is SEPARATE RAM from the music
   SeqChannels, the frozen live structs ARE the snapshot. (SMPS needed the 470 B copy
   only because its jingle REUSES the music track RAM.)
3. **Status/comm contract** (§6) — `SND_STAT_SEQ_ACTIVE` mirror (liveness floor) +
   score-authored `SND_STAT_COMM` cue byte (MEV_EXT's first tenant) + composed fade
   terminals with a fade-busy mirror.
4. **68k game-feel flows** (§7) — the per-moment sequencing (1-up, invincibility,
   drowning, speed shoes, act clear, death) as a thin game-side layer over 1-3.

Everything here is engine-tier except the §7 flows' TRIGGERS (what counts as "got a
1-up") which are game code. The engine/game seam is tagged per item in §7.

## 4. Pause engine

**New driver state:** `SND_PAUSED` (1 B, in the `$1CD3` slack block). Distinct from
`SND_SEQ_ACTIVE` — stop kills the song (unresumable, XGM2 semantics); pause freezes it.

**`Snd_Pause` (Z80, on `SND_REQ_CTRL=1`):**
1. Set `SND_PAUSED=1`. `Sequencer_Frame` gains ONE check: if paused, skip the music
   channel loop (ModUpdate/MacroTick/tempo-gate untouched, streams frozen) and fall
   through to `Sfx_Frame` — **SFX stay alive** (Echo scope; ARCH §9.13's "keep driver
   running" finally has its sound-side counterpart).
2. Mute music voices WITHOUT touching sequencer state: for each ACTIVE music FM channel
   not under `SCF_SFX_OVERRIDE`: key-off ($28, op-mask 0) + pan-clear ($B4=0, the
   pop-free gate — SMPS's choice); PSG music channels: max attenuation. DAC: left
   running (S3K behavior; drums are <1 s, and stopping mid-sample DC-parks anyway).
3. Timer-A keeps running (T0.1 lesson: it is never disabled).

**`Snd_Unpause` (on `SND_REQ_CTRL=2`):**
1. Clear `SND_PAUSED`.
2. Zero every music channel's `sc_last_pan` — ModUpdate's write-on-change re-asserts
   pan/AMS/FMS on the next frame (the T1.6 `Sfx_Restore` fix generalized). Do NOT
   re-key held notes: keyed-off notes stay silent until their next musical event
   (`SCF_KEYED` stays set; the next note-on's off-then-on path is already unconditional).
   This is the honest YM contract every modern driver documents — no fake re-attack.
3. Patches/volume need nothing for PURE pause: registers were never overwritten.
   (When a jingle stole channels during the pause, §5's pop path handles the patch
   re-load — that path, not unpause, owns it.)

**Edge policies (each explicit, each tested):**
- Pause while a jingle (§5) is active: jingle SFX freezes too? NO — jingle is SFX-tier
  and pause is music-scoped; the GAME decides (classic games freeze everything on
  Start-pause: the 68k pause flow calls `Snd_Pause` + `Sfx_PauseAll` — a second CTRL
  code (=3/4 pause-all/unpause-all) covers the Start-menu case).
- Pause during a fade: fade state (master fade scalar, target, delay ctr) freezes with
  the frame — unpause resumes the ramp. (Beats S3K's unpause-during-fade = StopAllSound.)
- Pause when no song loaded / already paused: idempotent no-ops.
- Stop while paused: allowed; clears `SND_PAUSED` (stop wins).

**Cost:** ~45-60 B Z80 (gate check + mute sweep + shadow-zero loop + CTRL dispatch).

## 5. Jingle push/pop (mid-song resume)

**Authoring:** a jingle is a **multi-channel SFX blob** (existing `sfx_transcode.py`
tier — same format that already runs Dash on FM5+PSG3), NOT a music song. Cap: the
SFX tier's channels (FM4/FM5 + PSG per current window tables; the plan verifies the
1-up jingle fits — S3K's 1-up is melody+harmony+bass, 3 voices). Jingles are
`sfh_priority` = top, `SHF_LOOP`-free by validity rule (a looping jingle never pops).

**`Snd_JinglePush` (on `SND_REQ_JINGLE=id`):**
1. `Snd_Pause` (§4 — freeze + mute music; SFX tier untouched).
2. Set `SND_JINGLE_ACTIVE=1` (1 B, slack block) and remember the id.
3. Dispatch the jingle through the normal SFX path (steal/priority machinery as-is).

**Hardware voices:** the jingle's SFX slots acquire chip channels through the NORMAL
dynamic-selection/steal machinery — with music paused-muted, its channels are ideal
steal targets. That means jingle patches DO overwrite stolen music channels' YM
registers (unlike pure pause), and the pop path must force re-load.

**Auto-pop (driver-side, S3K's data-driven elegance without the flag):** `Sfx_Frame`
already knows when SFX slots free (stream end → slot release). When
`SND_JINGLE_ACTIVE=1` and ALL slots belonging to the jingle id are idle:
1. Clear `SND_JINGLE_ACTIVE`.
2. Per stolen channel, `Sfx_Restore` runs as today — **with a new `SND_PAUSED` gate on
   its held-note re-key** (the exact sibling of the Stage-A `SND_SEQ_ACTIVE` drone-fix
   gate, `a89430b`): re-keying a paused song's held note would sound it mid-pause.
   Paused restore = shadows only; the note re-articulates at its next musical event.
3. Zero `sc_last_patch` + `sc_last_pan` on every channel the jingle stole (jingle
   patches overwrote them; write-on-change re-asserts on the next note-on/frame).
4. `Snd_Unpause` (§4).
5. Arm a **resume fade-in**: `SND_MASTER_FADE = JINGLE_RESUME_FADE` (authored constant,
   ~$28 ≈ S2's ramp) with target 0 — reuses the shipped fade engine verbatim; its
   existing clamps prevent the Clone-Driver-v2 overflow class.

**Edge policies:**
- **Jingle during a fade-out** (act clear vs 1-up race): the jingle WINS and the fade
  state freezes with the pause; on pop, the frozen fade resumes from where it was.
  (S3K silently DROPS the 1-up here — we exceed; the review called this out.)
- **Jingle during jingle** (double 1-up): restart the jingle SFX; the frozen music
  state is untouched by construction (it lives in SeqChannel RAM no jingle can reach).
  S3K needed a guard for this; we get it structurally.
- **Gameplay SFX during jingle:** allowed (rings keep chiming — S2 muted everything;
  we don't), subject to normal SFX priority vs the jingle's top priority.
- **Jingle while music stopped:** no push (nothing to freeze); plays as plain SFX;
  auto-pop sees `SND_SEQ_ACTIVE=0` and skips unpause (the Stage-A drone-fix gate,
  `a89430b`, already established this discipline for `Sfx_Restore`).
- **PCM/bank rules (review §3 last row):** v1 validity rule — **jingles are FM6-free
  and DAC-free** (transcoder-enforced: reject jingle blobs routing FM6 or DAC).
  Music's `SND_SONG_BANK` is never touched (SFX blobs already co-locate in the engine
  bank); `SND_FM6_ADAPTIVE` never flips. The door to drum-carrying jingles stays
  closed until a real need appears (no classic jingle needs drums).
- **Invincibility/drowning are NOT jingles** (they're full songs, minutes-scale, need
  the music sequencer): they use normal `PlayMusic` swaps; swap-back RESTARTS level
  music — classic-faithful (§7). Mid-song resume is deliberately scoped to the
  SFX-expressible jingle class (1-up; the design's one taste boundary, user-visible).

**Cost:** ~60-90 B Z80 (push glue + jingle-slot-idle scan + pop sequence). No new RAM
beyond 2 slack bytes. No format change (SFX header already has priority; the FM6/DAC
restriction is packer-side).

## 6. Status + comm contract (song-finished and musical cues)

1. **`SND_STAT_SEQ_ACTIVE`** (status block `+$15`): Z80 mirrors `SND_SEQ_ACTIVE` every
   frame (~6 B). The 68k floor for "song ended" (a non-looping song's `MEV_END` on all
   channels clears it), "stop landed", and "jingle popped" (`SND_STAT_JINGLE` `+$17`
   optional mirror). Poll model — every surveyed driver polls; no interrupt.
2. **`SND_STAT_COMM`** (status block `+$16`): score-authored cue byte. New event
   **`MEV_EXT $00 <val>`** — the FIRST tenant of the reserved `$FA` extension prefix
   (proves the prefix dispatch, ~12 B: fetch sub-opcode, fetch val, write comm byte).
   Zero-tick, music-legal, any route. Uses: end-of-intro markers, boss-phase stingers,
   act-clear tally sync, loop-count signalling. The packer gains `Comm(val)`.
3. **Composed fade terminals** (XGM2 steal): `SND_REQ_FADE` grows codes 3 =
   fade-out-then-STOP, 4 = fade-out-then-PAUSE (terminal action fires when the ramp
   hits silent, ~10 B on the existing fade-complete branch). **`SND_STAT_FADE_BUSY`**
   (`+$18`, mirrors ramp-in-progress) gives the 68k `isProcessingFade` for sequencing
   act-clear without frame-counting.
4. **Command exclusivity rule (API v2, the SGDK race lesson):** CTRL/JINGLE/MUSIC/FADE
   requests are latest-wins single bytes consumed at tick boundaries; the 68k contract
   is: post at most ONE of {music-load, pause/unpause, jingle} per frame. The plan adds
   a DEBUG-build Z80 assert (multiple pending → error code via the existing debug path).

## 7. 68k game-feel flows (game-side layer; engine seams tagged)

- **Start-menu pause** [game]: `Sound_PauseAll()` / `Sound_UnpauseAll()` (CTRL 3/4).
  Pause-all = §4 music pause + SFX freeze (mute SFX channels the same way; `Sfx_Frame`
  gated on the same flag) — the whole soundscape halts, driver keeps ticking.
- **1-up** [game trigger, engine mechanism]: `Sound_PlayJingle(SFX_1UP)`. Nothing else —
  resume + fade-in are driver-autonomous (§5).
- **Invincibility** [game]: `Sound_PlayMusic(MUS_INVINCIBLE)`; on timeout/hit-water etc.
  `Sound_PlayMusic(level_song)` (restart; classic). Speed-shoes-during-invincibility:
  tempo re-assert after the swap (below).
- **Speed shoes** [game]: `Sound_Tempo(TURBO_MOD)` on; `Sound_Tempo($FF)` (authored
  restore) off. **Load-boundary rule (now spec'd):** song load SNAPS tempo to the new
  song's authored header value (`sound_sequencer.asm:1223-1225`) — the 68k re-asserts
  `Sound_Tempo(TURBO_MOD)` after ANY music load while shoes are active. SFX cadence is
  explicitly NOT tempo-scaled (SFX frames are Timer-A frames; review spec-hole #2 closed).
- **Drowning** [game]: countdown warning pings = existing SFX; `MUS_DROWNING` swap at
  T-12s; on surface: `Sound_PlayMusic(level_song)`; on death: death flow. Tempo scalar
  self-resets via the load-boundary rule — no special case.
- **Act clear** [game]: `Sound_Fade(FADE_OUT_STOP)` → poll `SND_STAT_FADE_BUSY` clear →
  `Sound_PlayMusic(MUS_ACT_CLEAR)` (non-looping) → poll `SND_STAT_SEQ_ACTIVE` clear →
  tally SFX ticks (each tally tick posts a normal SFX; `SND_STAT_COMM` optional for
  score-synced tally). **This flow is safe TODAY** — T0.1 (StopMusic killed the driver)
  was fixed 2026-07-01; the contract just makes it observable.
- **Death / Game over / Continue** [game]: `Sound_PlayMusic(jingle-as-song)` + poll
  SEQ_ACTIVE. Death during drowning/jingle: music-load wins by §6.4 exclusivity.

## 8. Command API v2 (consolidated contract — supersedes 2026-06-16-sound-command-api.md)

Request slots (`SND_REQ_BASE=$1F00`, latest-wins, 0=idle unless noted):

| Slot | Name | Values | Status |
|---|---|---|---|
| +$00 | PING | echo token | live |
| +$01 | SAMPLE | 1..$FE play DAC id | live |
| +$02 | MUSIC | 1..$FE play, $FF stop | live |
| +$03 | SFX | id (68k ring-drained) | live |
| +$04 | CTRL_DMA_ACTIVE | 68k DMA bracket | live |
| +$05 | FADE | 1 out, 2 in, **3 out+stop, 4 out+pause** | live + NEW codes |
| +$06 | TEMPO | 1..$FE mod, $FF authored-restore | live |
| **+$07** | **CTRL** | **1 pause, 2 unpause, 3 pause-all, 4 unpause-all** | **NEW** |
| **+$08** | **JINGLE** | **jingle SFX id (push/auto-pop)** | **NEW** |

Status block (`+$10` base): ALIVE/PING_ECHO/ACK_COUNT/TICK/DAC_ACTIVE live;
**NEW:** +$15 SEQ_ACTIVE, +$16 COMM, +$17 JINGLE_ACTIVE, +$18 FADE_BUSY.
68k wrappers: `Sound_Pause/Unpause/PauseAll/UnpauseAll`, `Sound_PlayJingle`,
`Sound_FadeOutStop/FadeOutPause`, `Sound_IsMusicPlaying/IsFading/GetComm` (readers).
Exclusivity rule per §6.4. Mailbox reserve after this: `+$09..$0F` (7 B) — publish
the budget (specs-review discipline, like the MEV budget).

## 9. Budgets

Z80 code: pause ~55 B + jingle ~75 B + status/comm ~30 B + fade terminals ~10 B ≈
**~170 B of the 792 B headroom** (leaves >600 B; portamento already landed resident so
the old ~323 B claim on this headroom is gone). Z80 RAM: 2-3 slack bytes (`$1CD3`
block holds 45). 68k: thin wrappers + the §7 flows (~150-250 B game-side). ROM: the
1-up jingle SFX blob (content, user-sourced per the content-decisions rule).

## 10. Conscious cuts (from the 30-op union survey)

Seek/set-position (nobody ships it); song-end interrupts (poll only); per-priority pause
levels beyond music/all (MDSDRV's generality — our two scopes cover Sonic);
per-channel volume vectors (Echo) and split FM/PSG volume (XGM2) — the fade scalar +
Stage-B `sfh_gain` cover our needs; manual-sync 68k ticking (XGM) — Timer-A autonomy is
the architecture; cross-song position persistence (resume level music after DEATH —
every classic restarts; cut); GEMS-style N-concurrent-songs (our jingle class + SFX
tier covers the Sonic use-cases at a fraction of the complexity).

## 11. Verification (all emulator work FOREGROUND, oracle MCP; audio by RENDER not registers)

1. Register gates: pause frame → all music FM $B4=0 + key-off, PSG atten $F, SFX channel
   untouched; unpause frame → $B4 shadows re-written exactly once; DEBUG assert none fire.
2. Jingle E2E: play MT → jingle push mid-bar → verify SeqChannel RAM byte-identical
   across the jingle (the zero-copy claim, memcmp via oracle) → pop → stream pointers
   advance from the frozen values; fade-in ramp observed on TL writes.
3. Edge matrix: jingle-during-fade, double-jingle, jingle-over-stopped (drone-fix gate),
   pause-during-jingle, stop-while-paused — one scripted oracle case each.
4. Rendered A/B: 1-up-over-HCZ2 capture vs S2's 1-up-over-EHZ for feel parity
   (fade-in slope), per the verify-real-output rule.
5. Regression: full sound self-test + MT/HCZ2 renders byte-stable vs pre-phase captures.

## 12. Resolve during writing-plans

- Exact `Sfx_Frame` hook point for the jingle-idle scan (cheapest: piggyback the
  existing slot-release path, not a per-frame scan).
- Whether `SND_STAT_JINGLE` is worth its byte vs SEQ_ACTIVE alone (default: yes, 1 B).
- `JINGLE_RESUME_FADE` constant value (start $28; by-ear).
- DEBUG assert form for the exclusivity rule.
- Transcoder rule wording for jingle FM6/DAC rejection (`--jingle` flag vs header bit).
