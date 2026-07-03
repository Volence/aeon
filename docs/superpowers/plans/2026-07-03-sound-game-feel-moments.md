# Sound Game-Feel Moments Implementation Plan (Banking Package 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the engine tier of spec `2026-07-03-sound-game-feel-moments-design.md` — pause/unpause, jingle push/pop with freeze-in-place mid-song resume, the song-finished/comm status contract, and composed fade terminals — plus the 68k API v2 wrappers.

**Architecture:** All engine-side; the spec's §7 game flows (act clear, drowning, etc.) are a documented API cookbook consumed later by game features (screens/HUD land in design-week package #7 — no game-side task here beyond the debug harness). Z80 additions ride existing machinery: the pause gate is one branch in `Sequencer_Frame`; jingle push/pop reuses `SfxDispatch`/`Sfx_Restore` + `SND_SFX_ID_TAB`; fade terminals extend `Fade_Ramp`'s existing clamp; the comm byte is `MEV_EXT`'s first tenant. Budget ceiling ~170 B resident (of 792 B free) — record the build's budget line after every engine task.

**Tech Stack:** AS Macro Assembler (Z80 + 68k), Python 3 (`tools/song_packer.py` + pytest), `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`, oracle MCP (FOREGROUND ONLY — controller session does all emulator steps).

**Worktree note:** branch off master AFTER `feat/sfx-fidelity` + `feat/sound-design-banking` merge. Line numbers cite `feat/sound-design-banking`; verify anchors by the quoted code, not the number.

---

### Task 1: Constants — RAM state, mailbox slots, status bytes

**Files:**
- Modify: `sound_constants.asm` (request slots ~:18-28 + their collision assert ~:41; status block :30-35; game-feel RAM after the `SND_GLOBAL_EXPR` chain)

- [ ] **Step 1: Add the two request slots** next to `SND_REQ_TEMPO` (`SND_REQ_BASE+$06`):

```asm
SND_REQ_CTRL            = SND_REQ_BASE+$07       ; transport ctrl (0 idle / 1 pause-music /
                                                 ;   2 unpause-music / 3 pause-all / 4 unpause-all)
SND_REQ_JINGLE          = SND_REQ_BASE+$08       ; jingle push (0 idle / SFX id: pause music,
                                                 ;   play id as SFX, auto-resume at jingle end)
```

Update the existing collision assert (`:41`, currently on `SND_REQ_TEMPO`) to test `SND_REQ_JINGLE >= SND_STAT_BASE` instead. Mailbox reserve after this: `+$09..$0F` — say so in the comment (published budget).

- [ ] **Step 2: Add the four status bytes** after `SND_STAT_DAC_ACTIVE` (`SND_STAT_BASE+$04`):

```asm
SND_STAT_SEQ_ACTIVE     = SND_STAT_BASE+$05      ; mirror of SND_SEQ_ACTIVE (song-finished floor)
SND_STAT_COMM           = SND_STAT_BASE+$06      ; score-authored cue byte (MEV_EXT sub-op 0)
SND_STAT_JINGLE         = SND_STAT_BASE+$07      ; mirror of SND_JINGLE_ACTIVE
SND_STAT_FADE_BUSY      = SND_STAT_BASE+$08      ; 1 while the master-fade ramp is off-target
```

- [ ] **Step 3: Add the game-feel RAM bytes.** Find the chained equates that end the `SND_GLOBAL_EXPR` block (`SND_TEMPO_BASE = SND_GLOBAL_EXPR+$06` at :1327) and the alignment-slack comment (`$1CD3-$1CFF`, 45 B — RAM map in this file's header block). Chain three bytes into that slack, following the file's existing derivation style:

```asm
SND_GAMEFEEL_BASE   = SND_GLOBAL_EXPR+$07   ; game-feel state (rides the $1CD3 slack)
SND_PAUSED          = SND_GAMEFEEL_BASE+$00 ; 0 run / 1 music paused / 2 all paused
SND_JINGLE_ACTIVE   = SND_GAMEFEEL_BASE+$01 ; nonzero while a pushed jingle plays
SND_JINGLE_ID       = SND_GAMEFEEL_BASE+$02 ; the pushed jingle's SFX id
SND_FADE_TERM       = SND_GAMEFEEL_BASE+$03 ; fade terminal action (0 none / 1 stop / 2 pause)
SND_GAMEFEEL_END    = SND_GAMEFEEL_BASE+$04
        if SND_GAMEFEEL_END > SND_SFX_BASE
          error "game-feel state (\{SND_GAMEFEEL_END}) runs into the SFX channels at \{SND_SFX_BASE}"
        endif
```

(If a seam assert already covers this range, extend it rather than duplicating — follow the file's fatal-assert idiom at :101-127.)

- [ ] **Step 4: Zero the new state at driver init.** In `z80_sound_driver.asm` `Snd_Init` (~:205-215, the block that zeroes fade/tempo with `a=0`), append:

```asm
        ld      (SND_PAUSED), a
        ld      (SND_JINGLE_ACTIVE), a
        ld      (SND_JINGLE_ID), a
        ld      (SND_FADE_TERM), a
```

Also zero the two new REQ slots next to the existing `ld (SND_REQ_FADE), a` at :190-191.

- [ ] **Step 5: Build green + commit**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh 2>&1 | grep -E "budget|complete"` → green; record budget.

```bash
git add sound_constants.asm engine/sound/z80_sound_driver.asm
git commit -m "feat(sound): game-feel constants — CTRL/JINGLE slots, 4 status mirrors, paused/jingle/fade-term state (the game-feel spec (pkg 1) §8)"
```

### Task 2: Pause engine (Z80)

**Files:**
- Modify: `engine/sound/sound_sequencer.asm` (`Sequencer_Frame` :45-109; `Sequencer_StopAll` :2051+)
- Modify: `engine/sound/z80_sound_driver.asm` (mailbox dispatch, after the `.no_tempo` block ~:618)

- [ ] **Step 1: Factor the mute sweep out of `Sequencer_StopAll`.** Read `Sequencer_StopAll` (:2051+): it key-offs all six FM channels ($28, op-mask 0), silences PSG (`Psg_SilenceAll`), and clears `SND_SEQ_ACTIVE`. Extract the FM-key-off + `$B4`-pan-clear + PSG-silence portion into a new subroutine directly above it, and make StopAll call it (byte-identical behavior — the extraction must not change StopAll's register effects; diff the .lst symbols before/after):

```asm
; ----------------------------------------------------------------------
; Seq_SilenceMusicVoices — key-off all FM ($28 op-mask 0), clear FM pan
; gates ($B4+ch = 0, pop-free output mute), max-attenuate all PSG. Touches
; the CHIP only — no SeqChannel state (SCF_KEYED deliberately left set;
; restore paths gate on it). Shared by StopMusic and Snd_Pause.
; ----------------------------------------------------------------------
Seq_SilenceMusicVoices:
        ; (moved body: the exact FM key-off loop, $B4 clear loop, and
        ;  Psg_SilenceAll call lifted verbatim from Sequencer_StopAll —
        ;  if StopAll today lacks the $B4 clear, ADD it here per spec §4
        ;  and keep StopAll calling this, gaining the same pop-free mute)
        ret
```

- [ ] **Step 2: The pause gate in `Sequencer_Frame`.** After the `SND_SEQ_ACTIVE` check (`jr z, .run_sfx` at the top), insert:

```asm
        ld      a, (SND_PAUSED)
        or      a
        jr      nz, .run_sfx             ; paused (any scope) -> music frozen; SFX path decides its own gate
```

And gate the SFX side for pause-all: at `.run_sfx` change the tail-call to:

```asm
.run_sfx:
        ld      a, (SND_PAUSED)
        cp      2
        ret     z                        ; pause-all: SFX frozen too (chip already muted)
        jp      Sfx_Frame                ; tail-call: SFX writes land AFTER music
```

- [ ] **Step 3: CTRL dispatch + the pause/unpause routines.** In `Snd_PollMailbox` after `.no_tempo` (:618), add a block following the file's exact slot idiom (read → `jr z` skip → handler → clear slot → `SND_STAT_ACK_COUNT` bump):

```asm
.no_tempo_ctrl:
        ; --- transport ctrl? (1 pause / 2 unpause / 3 pause-all / 4 unpause-all) ---
        ld      a, (SND_REQ_CTRL)
        or      a
        jr      z, .no_ctrl
        call    Snd_CtrlCommand
        xor     a
        ld      (SND_REQ_CTRL), a
        ld      a, (SND_STAT_ACK_COUNT)
        inc     a
        ld      (SND_STAT_ACK_COUNT), a
.no_ctrl:
```

New routines (place near `Snd_FadeCommand`; all RAM+chip, bank-safe):

```asm
; Snd_CtrlCommand — a = 1 pause-music / 2 unpause / 3 pause-all / 4 unpause-all.
; Idempotent: pausing while paused / unpausing while running are no-ops by
; construction (state writes are absolute, mute sweep is safe to repeat).
Snd_CtrlCommand:
        cp      1
        jr      z, .pause_music
        cp      3
        jr      z, .pause_all
        cp      2
        jr      z, .unpause
        cp      4
        ret     nz                       ; unknown code -> ignore
.unpause:                                ; codes 2 and 4 share the resume path
        xor     a
        ld      (SND_PAUSED), a
        jp      Snd_UnpauseShadows       ; zero pan shadows -> ModUpdate re-asserts
.pause_music:
        ld      a, 1
        jr      .pause_common
.pause_all:
        ld      a, 2
.pause_common:
        ld      (SND_PAUSED), a
        jp      Seq_SilenceMusicVoices   ; chip mute; sequencer state untouched

; Snd_UnpauseShadows — zero sc_last_pan on every MUSIC SeqChannel so the next
; ModUpdate frame re-writes $B4 pan/AMS/FMS (the T1.6 Sfx_Restore fix,
; generalized). Held notes stay silent until their next musical event
; (SCF_KEYED untouched — spec §4 honest-resume contract).
Snd_UnpauseShadows:
        ld      a, (SND_SEQ_CHCOUNT)
        or      a
        ret     z
        ld      b, a
        ld      ix, SND_SEQ_CHANNELS
        ld      de, SeqChannel_len
.loop:
        ld      (ix+sc_last_pan), 0
        add     ix, de
        djnz    .loop
        ret
```

(Verify `sc_last_pan`'s zero means "unknown, re-write" in `ModUpdate`'s pan compare — the Sfx_Restore fix already relies on exactly this; grep `sc_last_pan` in `sound_sfx.asm` for the precedent and mirror its comment.)

- [ ] **Step 4: Stop-wins rule.** In the `SND_REQ_MUSIC = $FF` stop path (grep `Sequencer_StopAll` call in `z80_sound_driver.asm`), add `xor a / ld (SND_PAUSED), a` before the StopAll call (spec §4 edge: stop while paused clears pause).

- [ ] **Step 5: Build + budget (≤ 70 B so far) + commit**

```bash
git add engine/sound/sound_sequencer.asm engine/sound/z80_sound_driver.asm
git commit -m "feat(sound): pause engine — CTRL slot, music/all scopes, factored mute sweep, shadow-zero unpause (the game-feel spec (pkg 1) §4)"
```

- [ ] **Step 6 (controller session): oracle gate** — play MT; post CTRL=1 (`z80_write 0x1F07 0x01`): music freezes (FM `$B4`=0 all music ch, PSG atten $F), `SND_STAT_TICK` keeps counting; jump SFX still audible. CTRL=2: music resumes at position; pan re-written once (register trace). CTRL=3: everything silent; CTRL=4 resumes.

### Task 3: Status mirrors + composed fade terminals

**Files:**
- Modify: `engine/sound/sound_sequencer.asm` (`Sequencer_Frame` top; `Fade_Ramp` :170-202)
- Modify: `engine/sound/z80_sound_driver.asm` (`Snd_FadeCommand` — grep it; currently accepts 1/2)

- [ ] **Step 1: Per-frame mirrors.** In `Sequencer_Frame` immediately after the `SND_STAT_TICK` increment block, add:

```asm
        ld      a, (SND_SEQ_ACTIVE)
        ld      (SND_STAT_SEQ_ACTIVE), a ; song-finished floor: 68k polls this
        ld      a, (SND_JINGLE_ACTIVE)
        ld      (SND_STAT_JINGLE), a
```

- [ ] **Step 2: Fade-busy mirror + terminals in `Fade_Ramp`.** Current code returns `z` at top when at target. Change head and add the terminal consume:

```asm
Fade_Ramp:
        ld      a, (SND_FADE_TARGET)
        ld      b, a
        ld      a, (SND_MASTER_FADE)
        cp      b
        jr      nz, .active
        xor     a
        ld      (SND_STAT_FADE_BUSY), a  ; steady at target
        ; consume a pending terminal exactly once (nonzero only right after
        ; the ramp arrives; both actions are idempotent anyway)
        ld      a, (SND_FADE_TERM)
        or      a
        ret     z
        xor     a
        ld      (SND_FADE_TERM), a
        ld      a, (SND_FADE_TERM+... )  ; <- NO: keep it simple, reload the saved code:
        ret                              ; (see replacement below)
.active:
        ld      a, 1
        ld      (SND_STAT_FADE_BUSY), a
        ; ... existing delay-gate + step body unchanged ...
```

Replace the placeholder above with this exact terminal consume (the action code was stashed in `SND_FADE_TERM` itself):

```asm
        ld      a, (SND_FADE_TERM)
        or      a
        ret     z                        ; no terminal armed
        push    af
        xor     a
        ld      (SND_FADE_TERM), a       ; one-shot
        pop     af
        dec     a
        jp      z, Sequencer_StopAll     ; term 1: fade-out-and-STOP
        ld      a, 1                     ; term 2: fade-out-and-PAUSE (music scope)
        jp      Snd_CtrlCommand.pause_common - 2 ; NO — call the public entry:
```

**Correction (use the public entry, no offset tricks):** terminal 2 executes `ld a, 1` then `call Snd_CtrlCommand` is wrong (that's the dispatcher). Give `Snd_CtrlCommand` a named internal entry instead — in Task 2's routine, label the pause body:

```asm
Snd_PauseMusic:                          ; public: pause-music entry (a clobbered)
        ld      a, 1
        jr      Snd_CtrlCommand.pause_common
```

…and the terminal consume ends `jp z, Sequencer_StopAll` / `jp Snd_PauseMusic`.

- [ ] **Step 3: Accept fade codes 3/4.** In `Snd_FadeCommand` (grep; it maps 1→out, 2→in), extend: 3 = set target silent (same as 1) + `ld a,1 / ld (SND_FADE_TERM),a`; 4 = same + term 2. Show the diff in the commit.

- [ ] **Step 4: Build + commit**

```bash
git add engine/sound/sound_sequencer.asm engine/sound/z80_sound_driver.asm
git commit -m "feat(sound): status mirrors (SEQ_ACTIVE/JINGLE/FADE_BUSY) + composed fade terminals out+stop / out+pause (the game-feel spec (pkg 1) §6)"
```

- [ ] **Step 5 (controller session): oracle gate** — post FADE=3 during MT: TL ramp to silence then `SND_STAT_SEQ_ACTIVE`→0 (stop landed); FADE=4: silence then paused (CTRL=2 resumes at position). `SND_STAT_FADE_BUSY` reads 1 during the ramp, 0 after.

### Task 4: `MEV_EXT` comm byte (Z80 + packer)

**Files:**
- Modify: `engine/sound/sound_sequencer.asm` (opcode dispatch — grep `Seq_BadOpcode` / the `$E0-$FF` jump table)
- Modify: `sound_constants.asm:509-515` (MEV_EXT comment: now has ONE tenant)
- Modify: `tools/song_packer.py` (+ `Comm` event), `docs/.../2026-06-23-music-expression-engine-design.md` validity rules
- Test: `tools/test_song_packer.py`

- [ ] **Step 1: Failing packer test**

```python
def test_comm_event_packs_ext_prefix():
    ch = Channel(route=0, events=[Patch(0), Vol(100), Comm(7), Note(10), End()])
    blob = pack_song(make_song([ch]))
    assert bytes([0xFA, 0x00, 0x07]) in blob   # MEV_EXT, sub-op 0, value
```

- [ ] **Step 2: Implement `Comm` in the packer** (route-legal everywhere, zero-tick, add to `_MUSIC_LEGAL_EXPRESSION_OPCODES` handling as the `$FA` family):

```python
@dataclass
class Comm:
    """MEV_EXT sub-op 0: write the operand to SND_STAT_COMM (score-authored cue
    byte, 68k-visible). Zero-tick. Any route."""
    val: int
    def validate(self, route):
        if not (0 <= self.val <= 255):
            raise PackError(f"Comm val {self.val} out of byte range")
    def emit(self):
        return bytes([MEV_EXT, 0x00, self.val])
```

(Match the module's actual event-class shape — every event there follows validate/emit; mirror `Detune`'s minimal pattern.)

- [ ] **Step 3: Z80 handler.** In the sequencer's command dispatch, route `$FA` to:

```asm
; Seq_Op_Ext — MEV_EXT ($FA) extension prefix: sub-op byte selects the event.
; Sub-op 0 = COMM: next byte -> SND_STAT_COMM (68k-visible cue). Zero-tick.
; Unknown sub-op -> Seq_BadOpcode (a NEW sub-op requires a driver update by
; construction — never skip unknown payloads silently, lengths are unknown).
Seq_Op_Ext:
        call    Seq_FetchByte            ; a = sub-op (use the file's stream-fetch helper — grep how Seq_Op_Detune fetches its operand and use the same routine/idiom)
        or      a
        jr      nz, Seq_BadOpcode
        call    Seq_FetchByte            ; a = comm value
        ld      (SND_STAT_COMM), a
        jp      Seq_NextEvent            ; zero-tick continue (same tail as other zero-tick ops)
```

Wire `$FA` in the dispatch table/compare-chain exactly as `$F9` is wired (grep `MEV_MACRO` dispatch). Update the `MEV_EXT` comment block (:509-515): sub-op 0 allocated to COMM, sub-ops 1-255 free.

- [ ] **Step 4: Validity-rules sync** — music-expr spec §(d): `$FA` legal with sub-op 0 only; unknown sub-ops are a pack error AND an engine trap.

- [ ] **Step 5: pytest + build green; commit**

```bash
git add tools/song_packer.py tools/test_song_packer.py engine/sound/sound_sequencer.asm sound_constants.asm docs/superpowers/specs/2026-06-23-music-expression-engine-design.md
git commit -m "feat(sound): MEV_EXT sub-op 0 = COMM — score-authored cue byte to SND_STAT_COMM (first EXT tenant; the game-feel spec (pkg 1) §6)"
```

### Task 5: Jingle push/pop

**Files:**
- Modify: `engine/sound/z80_sound_driver.asm` (JINGLE slot dispatch), `engine/sound/sound_sfx.asm` (`Sfx_Restore` ~:1100-1135 + the slot-release path)

- [ ] **Step 1: JINGLE dispatch.** Add the slot block after `.no_ctrl` (same idiom):

```asm
        ; --- jingle push? (id: pause music, dispatch as SFX, auto-pop at end) ---
        ld      a, (SND_REQ_JINGLE)
        or      a
        jr      z, .no_jingle
        call    Snd_JinglePush
        xor     a
        ld      (SND_REQ_JINGLE), a
        ld      a, (SND_STAT_ACK_COUNT)
        inc     a
        ld      (SND_STAT_ACK_COUNT), a
.no_jingle:
```

```asm
; Snd_JinglePush — a = jingle SFX id. If no song is active, plays as a plain
; SFX (nothing to freeze; auto-pop skips unpause via the SND_SEQ_ACTIVE gate).
; Double-push (jingle while jingle): restart the SFX; music state is frozen
; RAM no jingle can touch — structurally safe (spec §5).
Snd_JinglePush:
        ld      (SND_JINGLE_ID), a
        push    af
        ld      a, (SND_SEQ_ACTIVE)
        or      a
        jr      z, .dispatch             ; no song -> plain SFX, no pause
        call    Snd_PauseMusic           ; freeze + mute (fade state freezes too)
        ld      a, 1
        ld      (SND_JINGLE_ACTIVE), a
.dispatch:
        pop     af
        jp      SfxDispatch              ; normal SFX path: priority/steal as-is
```

(Match `SfxDispatch`'s real input contract — the mailbox SFX path at :590 calls it after loading the id; mirror that calling convention exactly.)

- [ ] **Step 2: `SND_PAUSED` gate on `Sfx_Restore`'s re-key.** Find the held-note re-key that is already gated on `SND_SEQ_ACTIVE` (the a89430b drone fix — grep its comment). Extend the gate: also skip re-key when `SND_PAUSED != 0` (shadows still restored). Keep the existing comment style and cite spec §5.

- [ ] **Step 3: Auto-pop scan.** At the END of `Sfx_Restore` (after the slot is freed and the duck re-scan at :1123-1132), add:

```asm
        ; --- jingle auto-pop: did the last slot of the pushed jingle just end? ---
        ld      a, (SND_JINGLE_ACTIVE)
        or      a
        jr      z, .no_pop
        ld      a, (SND_JINGLE_ID)
        ld      b, SFX_VOICE_COUNT       ; scan the 7-slot id table
        ld      hl, SND_SFX_ID_TAB
.pop_scan:
        cp      (hl)
        jr      z, .no_pop               ; a jingle slot still live -> not yet
        inc     hl
        djnz    .pop_scan
        ; all jingle slots idle -> pop: unpause + resume fade-in
        xor     a
        ld      (SND_JINGLE_ACTIVE), a
        ld      a, (SND_SEQ_ACTIVE)
        or      a
        jr      z, .no_pop               ; jingle-over-stopped: nothing to resume
        xor     a
        ld      (SND_PAUSED), a
        call    Snd_UnpauseShadows       ; pan re-assert; ALSO zero sc_last_patch
                                         ;   on FM music channels here (jingle
                                         ;   stole voices -> force patch reload;
                                         ;   add the ld inside the same loop)
        ld      a, JINGLE_RESUME_FADE
        ld      (SND_MASTER_FADE), a     ; start quiet...
        xor     a
        ld      (SND_FADE_TARGET), a     ; ...ramp to full (existing Fade_Ramp)
.no_pop:
```

Add `JINGLE_RESUME_FADE = $28` to `sound_constants.asm` near the fade constants. Extend `Snd_UnpauseShadows`'s loop with `ld (ix+sc_last_patch), 0` guarded by `bit SCF_IS_FM_B, (ix+sc_flags)` (PSG has no patch). NOTE: the id-table scan must run AFTER the freed slot's `SND_SFX_ID_TAB` entry is cleared — verify `Sfx_Restore` clears it (Stage A behavior); if it clears BEFORE this point the scan is correct as written.

- [ ] **Step 4: DEBUG exclusivity assert (spec §6.4).** In `Snd_PollMailbox`, DEBUG-only: if `SND_REQ_MUSIC` and `SND_REQ_JINGLE` are BOTH nonzero in one poll, route to the driver's error path (grep the existing DEBUG error idiom — `Seq_BadOpcode`-style):

```asm
    if SOUND_DEBUG
        ld      a, (SND_REQ_MUSIC)
        or      a
        jr      z, .excl_ok
        ld      a, (SND_REQ_JINGLE)
        or      a
        jp      nz, Seq_BadOpcode        ; 68k contract violation: one transport op/frame
.excl_ok:
    endif
```

- [ ] **Step 5: Build + budget (cumulative ≤ 170 B) + commit**

```bash
git add engine/sound/z80_sound_driver.asm engine/sound/sound_sfx.asm sound_constants.asm
git commit -m "feat(sound): jingle push/pop — freeze-in-place resume, SND_PAUSED re-key gate, auto-pop + resume fade-in (the game-feel spec (pkg 1) §5)"
```

- [ ] **Step 6 (controller session): oracle E2E gate (spec §11.2-11.3)** — the zero-copy proof: dump SeqChannel RAM (`0x1A08`, 660 B) → push a jingle mid-MT → dump again during the jingle → **byte-identical** except nothing (pause writes no channel state) → wait for pop → stream pointers advance from frozen values; fade-in TL ramp visible. Then the edge matrix: jingle-during-FADE=3, double-jingle, jingle-over-stopped (no drone — the a89430b gate), CTRL=3 during jingle, stop-while-paused.

### Task 6: 68k API v2 wrappers

**Files:**
- Modify: `engine/sound/sound_api.asm` (wrappers follow the `Sound_Ping` idiom at :49-51; fade/tempo wrappers at :243-262)

- [ ] **Step 1: Add the wrappers** (each is the standard two-liner; place after the fade/tempo group):

```asm
; ----------------------------------------------------------------------
; Game-feel transport (spec 2026-07-03-sound-game-feel-moments §8).
; One transport op per frame (DEBUG-asserted Z80-side).
; ----------------------------------------------------------------------
Sound_Pause:                             ; music freezes, SFX alive
        moveq   #1, d0
        lea     (SND_Z80_BASE+SND_REQ_CTRL).l, a0
        bra.w   Sound_PostByte
Sound_Unpause:
        moveq   #2, d0
        lea     (SND_Z80_BASE+SND_REQ_CTRL).l, a0
        bra.w   Sound_PostByte
Sound_PauseAll:                          ; Start-menu: whole soundscape
        moveq   #3, d0
        lea     (SND_Z80_BASE+SND_REQ_CTRL).l, a0
        bra.w   Sound_PostByte
Sound_UnpauseAll:
        moveq   #4, d0
        lea     (SND_Z80_BASE+SND_REQ_CTRL).l, a0
        bra.w   Sound_PostByte
Sound_PlayJingle:                        ; d0.b = jingle SFX id; auto-resumes
        lea     (SND_Z80_BASE+SND_REQ_JINGLE).l, a0
        bra.w   Sound_PostByte
Sound_FadeOutStop:                       ; composed terminal: silent -> StopMusic
        moveq   #3, d0
        lea     (SND_Z80_BASE+SND_REQ_FADE).l, a0
        bra.w   Sound_PostByte
Sound_FadeOutPause:                      ; composed terminal: silent -> pause
        moveq   #4, d0
        lea     (SND_Z80_BASE+SND_REQ_FADE).l, a0
        bra.w   Sound_PostByte
```

- [ ] **Step 2: Status readers.** Model on how the debug harness / self-test reads `SND_STAT_*` today (grep `SND_STAT_ALIVE` readers in `engine/` — the boot handshake reads it under a bus hold). Add one shared reader + three thin entries:

```asm
; Sound_ReadStat — d0.b = status byte at (a0) (SND_STAT_* address), read under
; the same masked-int bus hold as Sound_PostByte (copy its stop/start sequence
; verbatim — grep Sound_PostByte:18 and mirror, swapping the write for a read).
Sound_IsMusicPlaying:                    ; d0.b nonzero = playing
        lea     (SND_Z80_BASE+SND_STAT_SEQ_ACTIVE).l, a0
        bra.w   Sound_ReadStat
Sound_IsFading:
        lea     (SND_Z80_BASE+SND_STAT_FADE_BUSY).l, a0
        bra.w   Sound_ReadStat
Sound_GetComm:
        lea     (SND_Z80_BASE+SND_STAT_COMM).l, a0
        bra.w   Sound_ReadStat
```

- [ ] **Step 3: Build (both DEBUG and plain — the API file assembles in both) + commit**

```bash
git add engine/sound/sound_api.asm
git commit -m "feat(sound): 68k API v2 — pause/jingle/composed-fade wrappers + status readers (the game-feel spec (pkg 1) §8)"
```

### Task 7: Mark the old command-API spec superseded + tracking closure

**Files:**
- Modify: `docs/superpowers/specs/2026-06-16-sound-command-api.md` (header), `docs/DEFERRED_WORK.md`, `docs/ENGINE_ARCHITECTURE.md` §6, `docs/superpowers/2026-07-03-sound-banking-queue.md`

- [ ] **Step 1:** Old API spec gets a SUPERSEDED header pointing at the game-feel spec (pkg 1) §8. ARCH §6 gains a short game-feel paragraph (pause scopes, jingle model, status contract) + the index row updates "the current sound priority". DEFERRED_WORK: close the review's gap-list items this plan ships; the §7 game flows (act-clear sequencing etc.) get a NEW deferred entry pointing at the game-feel spec (pkg 1) §7 + the screens/HUD package. Queue doc: package 1 → EXECUTED.

- [ ] **Step 2: Final gates** — pytest suite green; DEBUG + plain builds green; final budget delta recorded (≤ 170 B); full oracle matrix from Task 5 Step 6 logged in the queue doc.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-06-16-sound-command-api.md docs/DEFERRED_WORK.md docs/ENGINE_ARCHITECTURE.md docs/superpowers/2026-07-03-sound-banking-queue.md
git commit -m "docs(sound): package 1 executed — API spec superseded, ARCH/DEFERRED sync"
```

---

## Self-review notes

- Spec coverage: §4 → Task 2; §5 → Task 5 (+ SND_PAUSED gate + patch-shadow zero); §6 → Tasks 3-4; §8 → Tasks 1, 6; §7 flows deliberately deferred to game features (recorded in Task 7); §11 verification distributed as controller-session gates on Tasks 2/3/5.
- The one authoring dependency: a real 1-up jingle SFX blob is CONTENT (user-sourced); the engine gates run against any multi-channel SFX id (Dash works as the test jingle).
- Consistency: `Snd_PauseMusic`/`Snd_CtrlCommand`/`Snd_UnpauseShadows`/`Seq_SilenceMusicVoices`/`JINGLE_RESUME_FADE` used identically across tasks; fetch-helper and error-path names are grep-anchored rather than assumed.
