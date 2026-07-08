# SFX Fidelity Stage B/C Implementation Plan (Banking Package 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the Stage-A-reserved `SfxHeader` fields (spec `2026-07-02-sfx-fidelity-and-mixing-design.md` §5 + §7 addendum): per-SFX gain, per-SFX duck depth, instance caps, non-latching priority, and the continuous-SFX class — all defaulting to Stage-A-exact behavior so the phase merges safe before any taste value is authored.

**Architecture:** Every hook point is seam-verified against the post-Stage-A engine on `master` (line numbers below are current as of this refinement). Stage B folds ride the two existing single volume paths (`Fm_SetVolume` / `Psg_SetVolume`) and the single duck-arm site; Stage C adds a per-slot tri-state re-ping countdown (`sx_extend`) gated at the shared stream loop boundary (`Seq_Op_Jump`). Transcoder and engine constants stay byte-synced per spec §6.

**Tech Stack:** AS Macro Assembler (Z80), Python 3 (`tools/sfx_transcode.py` + `tools/test_sfx_transcode.py` via pytest), `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`, oracle MCP (**foreground only, user go-ahead required — see Gates**).

---

## Gates (READ BEFORE STARTING — both are hard blocks)

1. **Merge gate.** Implementation MUST NOT begin until `feat/sound-perf-budget` merges to `master`. It touches the same files (`sound_sfx.asm`, `sound_fm.asm`, `sound_psg.asm`, `sound_constants.asm`, `tools/sfx_transcode.py`). Verify with `git log --oneline master | grep -i sound-perf` (or confirm the branch is gone / merged) before branching. This plan document is docs-only and safe to write/commit on `master` now.
2. **Emulator gate.** ANY oracle MCP use (the register/rendered A/B checks in Task 6, and the optional taste probes noted in Tasks 2/5) requires an explicit go-ahead from the user first — another session may hold the emulator. Every oracle step below is marked **[ORACLE — needs go-ahead]**. If go-ahead is not given, complete all build-assert / pytest / byte-identity gates (which need no emulator) and leave the oracle gates unchecked with a note; do NOT block the phase on them.

**Worktree:** branch off `master` AFTER the merge gate clears: `git checkout -b feat/sfx-fidelity-stage-bc master`.

**By-ear inputs (user, before or during execution):** authored `sfh_gain` / `sfh_duck` values per SFX. Plan defaults: **all gains 0, all ducks 0, all caps 1, no continuous flags** — byte-behavior-neutral, so the plan is fully executable without the user and taste values drop in later as data (Task 1 config table). The roll-taste decision (DEFERRED_WORK "Roll taste": S3K-authentic 2.2 kHz / 1.4 s fade; tame via `sfh_gain` ONLY as a deliberate divergence) is a by-ear call — default 0.

---

## Refinement note (2026-07-07)

This file supersedes the first banked skeleton of the same name. Three gaps in that skeleton were resolved against the real code and are baked into the tasks below:

- **RAM byte budget (was hand-waved "use a pad byte / else extend the struct").** `SfxChannel` is exactly 64 bytes with only ONE free pad (`sx_pad` +58), but three new per-slot bytes are needed. Resolution (Task 0): `sx_gain` reuses `sx_pad` (+58); `sx_duck` (+64) and `sx_extend` (+65) grow the struct to **66** bytes; `sx_extend` is **tri-state** so Stage C needs no fourth byte. Verified: +65 ≤ 127 (ix+d range) and the array grows only 14 B toward the mailbox, guarded by the existing `SND_SFX_RAM_END > SND_REQ_BASE` fatal.
- **Stage C could not identify a continuous slot.** SFX `35/36/3C/AB` set `SHF_LOOP` WITHOUT `SHF_CONTINUOUS` (header byte[1] = `$04`), so "an SFX that loops is continuous" is FALSE and `sx_extend == 0` cannot mean "expired." Resolution: `sx_extend` encodes **0 = not continuous (never touched); 1..N = continuous, alive; $FF = continuous, expiring (end at next loop boundary)**. Non-continuous looping SFX stay pinned at 0 → `Seq_Op_Jump` loops them normally.
- **Non-latching priority "min-of-active" had no source at the store site.** The victim-min is only computed inside steal tier (c); tiers (a)/(b) find a free slot and never scan. Resolution (Task 4): a small `Sfx_MinActiveKind` helper computes min `sx_priority` among active same-kind slots, called only when the incoming priority has bit 7 set.

---

### Task 0: RAM layout + constants (do this ONCE, up front)

Resolve the whole struct/constant surface before any logic uses it, so the overflow asserts fire once and later tasks only *read* the fields.

**Files:**
- Modify: `sound_constants.asm` (`SfxChannel` struct + len assert ~:912-985; `SFXH_*` aliases ~:886-889; SHF flags ~:899-905; new `SFX_EXTEND_FRAMES`)
- Modify: `engine/sound/sound_sfx.asm` (dispatch scratch chain :73-87)

- [ ] **Step 1: Grow `SfxChannel` to 66 bytes.** In `sound_constants.asm`, in the `SfxChannel struct` (:912): rename the `sx_pad` line (+58) to `sx_gain`, and append two fields after `sx_kind` (+63):

```asm
sx_kind         ds.b 1   ; +63 SFXEL_* of the owned voice (FM/PSG/NOISE) for restore dispatch
sx_duck         ds.b 1   ; +64 Stage B: per-slot copy of the SFX's authored duck depth
sx_extend       ds.b 1   ; +65 Stage C: continuity/re-ping state. 0 = not continuous;
                         ;     1..SFX_EXTEND_FRAMES = continuous & alive (counts down when
                         ;     un-pinged); $FF = continuous & expiring (end at next loop)
SfxChannel endstruct     ; = 66 bytes
```

and change the `sx_pad` alias/comment at +58:

```asm
sx_gain         ds.b 1   ; +58 Stage B: per-slot copy of the SFX's authored master gain
                         ;     (was sx_pad; keeps SfxChannel_len even)
```

- [ ] **Step 2: Update the length assert + add the field aliases.** Change the `<> 64` assert to `<> 66` (:978), and add sx_* aliases next to the existing ones (~:987-992):

```asm
        if SfxChannel_len <> 66
          error "SfxChannel struct is \{SfxChannel_len} bytes, expected 66"
        endif
```
```asm
sx_gain         = SfxChannel_sx_gain
sx_duck         = SfxChannel_sx_duck
sx_extend       = SfxChannel_sx_extend
```

The existing `if SfxChannel_sx_kind > 127` guard already covers the new fields transitively, but add an explicit one for clarity:

```asm
        if SfxChannel_sx_extend > 127
          error "SfxChannel sx_extend offset (\{SfxChannel_sx_extend}) exceeds (ix+d) +127"
        endif
```

- [ ] **Step 3: Header field aliases + the extend constant.** Next to `SFXH_PRIORITY`/`SFXH_FLAGS`/`SFXH_CHCOUNT` (:886-889) add:

```asm
SFXH_GAIN     = SfxHeader_sfh_gain      ; +3
SFXH_DUCK     = SfxHeader_sfh_duck      ; +4
SFXH_CAP      = SfxHeader_sfh_cap       ; +5
```

Near the SHF flags (:899-905) add the Stage C constant:

```asm
SFX_EXTEND_FRAMES = 10   ; Stage C: frames a continuous SFX survives after pings stop
                         ; (~one loop; countdown seeds sx_extend on ping)
```

- [ ] **Step 4: Two new dispatch-scratch bytes.** In `engine/sound/sound_sfx.asm`, in the dispatch chain (:73-87), insert after `SND_SFX_DISP_ID` (:79) and before `SND_SFX_ID_TAB` (:86):

```asm
SND_SFX_DISP_PRIO_RAW = SND_SFX_DISP_ID + 1           ; raw incoming priority (bit7 = non-latching)
SND_SFX_DISP_CAP   = SND_SFX_DISP_PRIO_RAW + 1        ; incoming SFX instance cap (sfh_cap)
SND_SFX_ID_TAB     = SND_SFX_DISP_CAP + 1             ; 7 bytes
```

- [ ] **Step 5: Build — asserts only, no behavior change yet.**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`
Expected: clean build. In particular NO `SFX RAM ... overruns the mailbox` fatal (the 14 B array growth + 2 scratch bytes fit under `SND_REQ_BASE`). If that fatal fires, STOP and report — the mailbox is at `$1F00` and there is documented slack, but the exact figure must be re-derived, not guessed.

- [ ] **Step 6: Commit**

```bash
git add sound_constants.asm engine/sound/sound_sfx.asm
git commit -m "refactor(sound): SfxChannel +sx_gain/sx_duck/sx_extend (64->66) + SFXH_* aliases + dispatch scratch — Stage B/C RAM layout, no behavior change"
```

---

### Task 1: Transcoder emits the real fields + validity rules

**Files:**
- Modify: `tools/sfx_transcode.py` (`pack_sfx()` header emission :1492-1500; the per-SFX config where priority/flags are authored — priority map ~:76, flag accumulation ~:823/:1247)
- Test: `tools/test_sfx_transcode.py`

- [ ] **Step 1: Write the failing tests.** Build these on the module's existing SFX test builders (mirror the nearest header-emission test):

```python
def test_header_carries_gain_duck_cap():
    blob = pack_sfx_fixture(gain=6, duck=0x18, cap=2, chcount=1)
    assert blob[3] == 6 and blob[4] == 0x18 and blob[5] == 2   # sfh_gain/duck/cap

def test_defaults_are_stage_a_bytes():
    blob = pack_sfx_fixture()                                  # no gain/duck/cap args
    assert blob[3] == 0 and blob[4] == 0 and blob[5] == 1      # 0/0/1 = Stage-A bytes

def test_cap_gt1_rejected_on_multichannel():
    with pytest.raises(TranscodeError, match="cap > 1 .* single-channel"):
        pack_sfx_fixture(cap=2, chcount=2)                     # spec §7.1 packer rule

def test_continuous_requires_loop():
    with pytest.raises(TranscodeError, match="SHF_CONTINUOUS requires SHF_LOOP"):
        pack_sfx_fixture(flags=SHF_CONTINUOUS)                 # continuous without loop -> reject
```

- [ ] **Step 2: Run the tests — verify they fail.**

Run: `python -m pytest tools/test_sfx_transcode.py -k "gain_duck_cap or defaults_are_stage or cap_gt1 or continuous_requires" -v`
Expected: FAIL (`pack_sfx` still hardcodes `0/0/1`; validity rules not present).

- [ ] **Step 3: Implement.** In `pack_sfx()` replace the hardcoded gain/duck/cap emission (:1496-1498) with descriptor values (defaults `gain=0, duck=0, cap=1`):

```python
    out.append(sfx_desc.get('gain', 0) & 0xFF)   # sfh_gain  (Stage B; 0 = Stage-A-exact)
    out.append(sfx_desc.get('duck', 0) & 0xFF)   # sfh_duck  (Stage B; 0 = no duck)
    out.append(sfx_desc.get('cap', 1) & 0xFF)    # sfh_cap   (Stage B; 1 = replace-in-place)
```

Add the two validity rules (place them where `chcount`/`flags` are finalized in `pack_sfx`, right after `chcount = len(channels)`):

```python
    cap = sfx_desc.get('cap', 1)
    if cap > 1 and chcount != 1:
        raise TranscodeError(f"sfh_cap > 1 ({cap}) is legal only for single-channel SFX "
                             f"(chcount={chcount}); multi-channel SFX stay cap=1")
    if (flags & SHF_CONTINUOUS) and not (flags & SHF_LOOP):
        raise TranscodeError("SHF_CONTINUOUS requires SHF_LOOP (a continuous SFX must self-loop)")
```

Thread `gain`/`duck`/`cap` from the per-SFX authoring config into `sfx_desc` (the same place `priority`/`flags` are set for each id — default all current 9 to `gain=0, duck=0, cap=1`, i.e. omit the keys). Update the layout docstring (:1444-1451) to state gain/duck/cap are now authored, not inert.

- [ ] **Step 4: Run the tests — verify they pass.**

Run: `python -m pytest tools/test_sfx_transcode.py -v`
Expected: PASS (all, including the pre-existing suite).

- [ ] **Step 5: Byte-identity regression.** Regenerate all 9 SFX blobs (whatever the repo's generate command is — e.g. the `tools/` SFX generator / build step that writes `games/sonic4/data/sound/sfx/*.asm`), then:

Run: `git diff --stat games/sonic4/data/sound/sfx/`
Expected: **ZERO changes** — defaults reproduce the exact Stage-A bytes (`$XX,$YY,$ZZ,$00,$00,$01,$00,$00,...`).

- [ ] **Step 6: Commit**

```bash
git add tools/sfx_transcode.py tools/test_sfx_transcode.py
git commit -m "feat(tools): SfxHeader gain/duck/cap authored per-SFX + Stage B/C validity rules (byte-identical defaults)"
```

---

### Task 2: `sfh_gain` fold (FM + PSG) — authored per-SFX attenuation

**Files:**
- Modify: `engine/sound/sound_sfx.asm` (slot init ~:876 — stash `sx_gain`), `engine/sound/sound_fm.asm` (`Fm_SetVolume` :344), `engine/sound/sound_psg.asm` (`Psg_SetVolume` :387)

- [ ] **Step 1: Stash `sfh_gain` into `sx_gain` at slot init.** In `Sfx_BeginSound`, at the bookkeeping block (:873-883, right after the `sx_priority` write at :876), add — using `push/pop iy` because `iy` currently holds the channel-record ptr that `Sfx_Steal` reads at :885:

```asm
        ; Stage B: stash the header's authored gain/duck into per-slot bytes so the
        ; volume paths / duck scan can read them without re-deriving the blob base.
        push    iy                       ; preserve the channel-record ptr (Sfx_Steal reads it)
        ld      iy, (SND_SFX_DISP_BASE)  ; iy = blob header base
        ld      a, (iy+SFXH_GAIN)
        ld      (ix+sx_gain), a
        ld      a, (iy+SFXH_DUCK)
        ld      (ix+sx_duck), a          ; used by Task 3's deepest-duck scan
        pop     iy
```

(Stashing `sx_duck` here too — Task 3 consumes it; harmless until then.)

- [ ] **Step 2: FM fold.** In `Fm_SetVolume`, immediately after the log-LUT store `ld (Fm_ScratchLog), a` (:351) and BEFORE the env-fold block (:353), insert an SFX-only gain fold. `Snd_ChanClass` returns CARRY set for MUSIC (same routine the duck fold uses at :388):

```asm
        ; --- Stage B sfh_gain (SFX slots only): authored per-SFX master attenuation
        ; in FM-TL units (0.75 dB/step). Folded into the carrier-TL delta BEFORE the
        ; env/duck folds so the existing $7F clamps cover the sum. Music SeqChannels
        ; have no sx_gain (offset +58 is a music field) -> gate on SFX class (inverse
        ; of the :388 duck fold). Gain 0 -> byte-identical to no fold (or a / jr z).
        call    Snd_ChanClass            ; CARRY set => MUSIC channel
        jr      c, .no_sfx_gain          ; music -> no per-SFX gain
        ld      a, (ix+sx_gain)
        or      a
        jr      z, .no_sfx_gain
        ld      hl, Fm_ScratchLog
        add     a, (hl)                  ; sx_gain + log delta
        jr      nc, .sfx_gain_cap
        ld      a, SND_FM_TL_MAX         ; 8-bit carry -> clamp $7F (silent)
.sfx_gain_cap:
        cp      SND_FM_TL_MAX+1
        jr      c, .sfx_gain_store
        ld      a, SND_FM_TL_MAX
.sfx_gain_store:
        ld      (hl), a
.no_sfx_gain:
```

- [ ] **Step 3: PSG fold.** In `Psg_SetVolume`, immediately after `Psg_VolToAtten` + `ld c, a` (:388-389) and BEFORE the env-fold block (:391), insert the mirror — `sx_gain >> 3` (the same TL→atten ÷8 the fade fold uses at :427-429), clamp `$0F`, SFX-only. `Snd_ChanClass` clobbers `hl` (this routine preserves `hl` by contract, so push/pop):

```asm
        ; --- Stage B sfh_gain (SFX slots only): +sx_gain>>3 in PSG atten units.
        push    hl                       ; Snd_ChanClass clobbers hl (contract: preserve)
        call    Snd_ChanClass            ; CARRY set => MUSIC
        pop     hl
        jr      c, .no_sfx_gain
        ld      a, (ix+sx_gain)
        or      a
        jr      z, .no_sfx_gain
        srl     a
        srl     a
        srl     a                        ; sx_gain (TL units) >> 3 -> atten units
        add     a, c
        cp      SND_PSG_ATTEN_SILENT+1
        jr      c, .sfx_gain_store
        ld      a, SND_PSG_ATTEN_SILENT  ; clamp $0F (silent)
.sfx_gain_store:
        ld      c, a
.no_sfx_gain:
```

- [ ] **Step 4: Build gate.**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`
Expected: clean build. Rough budget: ≤ ~30 B added across both paths.

- [ ] **Step 5: [ORACLE — needs go-ahead] Register gates.** With all gains 0 (Task 1 defaults): oracle jump ($62) / ring ($33) / skid ($36) programmed FM carrier-TLs and PSG attenuations must be **byte-identical to Stage A** (gain fold is a no-op at 0). Then a taste probe: temporarily set roll ($34) `gain=6` in the config, rebuild, verify its carrier TLs read exactly +6 vs the gain-0 build; revert to 0 unless the user picks a value. If go-ahead is not given, skip this step (the build asserts + gain-0 no-op logic already guarantee Stage-A equivalence); note it unchecked.

- [ ] **Step 6: Commit**

```bash
git add engine/sound/sound_sfx.asm engine/sound/sound_fm.asm engine/sound/sound_psg.asm
git commit -m "feat(sound): per-SFX sfh_gain fold — FM carrier-TL + PSG atten at the init-time volume paths (Stage B; gain 0 = Stage-A-exact)"
```

---

### Task 3: Per-SFX duck depth (`sfh_duck`) replaces the global threshold/depth

**Files:**
- Modify: `engine/sound/sound_sfx.asm` (duck-arm :896-914; `Sfx_Restore` release :1123-1134; rework `Sfx_AnyDuckActive` :1143-1159), `sound_constants.asm` (retire `SFX_DUCK_THRESHOLD` / `SFX_DUCK_DEPTH`), `tools/sfx_transcode.py` (retire the mirrored constants)

`sx_duck` is already stashed at init (Task 2 Step 1). This task changes the arm/release logic from priority-threshold to authored per-SFX depth, deepest-active wins (spec §7.1).

- [ ] **Step 1: Replace `Sfx_AnyDuckActive` with `Sfx_DeepestDuck`.** The old routine (:1143-1159) returns a carry if any active slot's `sx_priority >= SFX_DUCK_THRESHOLD`. Replace the whole routine with one that returns the DEEPEST active `sx_duck` (0 if none):

```asm
; ----------------------------------------------------------------------
; Sfx_DeepestDuck — scan the 7 SfxChannel slots; return the DEEPEST duck depth
; (max sx_duck) among ACTIVE slots, or 0 if none. (Walks via iy so an SFX-slot ix
; on the caller's stack is undisturbed.) Out: a = deepest sx_duck. Clobbers af,bc,de,iy.
; Preserves ix, hl.
; ----------------------------------------------------------------------
Sfx_DeepestDuck:
        ld      iy, SND_SFX_CHANNELS
        ld      b, SFX_VOICE_COUNT
        ld      de, SfxChannel_len
        ld      c, 0                     ; c = deepest so far
.scan:
        bit     SCF_ACTIVE_B, (iy+sc_flags)
        jr      z, .scan_next            ; inactive -> skip
        ld      a, (iy+sx_duck)
        cp      c
        jr      c, .scan_next            ; a < deepest -> keep
        ld      c, a                     ; new deepest
.scan_next:
        add     iy, de
        djnz    .scan
        ld      a, c
        ret
```

- [ ] **Step 2: Release path uses the deepest-active depth.** In `Sfx_Restore` `.deactivate` (:1123-1132), replace the carry-based keep/zero block with a direct write of the deepest remaining depth (this slot's `sx_priority` was cleared at :1121; also clear its `sx_duck` so it does not self-count):

```asm
        ; --- release the music duck to the DEEPEST duck still active (0 = none) -----
        ld      (ix+sx_duck), 0          ; this slot no longer contributes a duck
        call    Sfx_DeepestDuck          ; a = deepest sx_duck among active slots
        ld      (SND_SFX_DUCK_TARGET), a ; Sfx_DuckRamp ramps toward it (0 = back up)
```

- [ ] **Step 3: Arm the duck by authored depth, deepest wins.** In `Sfx_BeginSound`, replace the Task-10 arm block (:903-913) — the `SND_SFX_DISP_PRIO >= SFX_DUCK_THRESHOLD → SFX_DUCK_DEPTH` test — with a per-SFX authored-depth arm that never lowers a deeper active duck:

```asm
        ; --- arm the music duck to THIS SFX's authored depth (spec §7.1) ----------
        ; Threshold is now "sfh_duck != 0" (the byte IS the eligibility); rings/jump
        ; author 0 -> no duck. Never lower an already-deeper active duck (deepest
        ; wins); the release path (Sfx_DeepestDuck) re-resolves the exact depth.
        ld      iy, (SND_SFX_DISP_BASE)
        ld      a, (iy+SFXH_DUCK)
        or      a
        jr      z, .no_duck_arm          ; duck 0 -> do not duck
        ld      hl, SND_SFX_DUCK_TARGET
        cp      (hl)
        jr      c, .no_duck_arm          ; sfh_duck < current target -> keep deeper
        ld      (hl), a
.no_duck_arm:
        ret
```

- [ ] **Step 4: Retire the dead constants.** Delete `SFX_DUCK_THRESHOLD` (:805) and `SFX_DUCK_DEPTH` (:809) from `sound_constants.asm`, the mirrored copies in `tools/sfx_transcode.py`, and any now-dead build-assert that referenced them (e.g. the `SFXPRI_RING < SFX_DUCK_THRESHOLD` guard). Keep `SFX_DUCK_RAMP_STEP`. Confirm nothing else references them:

Run: `grep -rn "SFX_DUCK_THRESHOLD\|SFX_DUCK_DEPTH\|Sfx_AnyDuckActive" engine/ sound_constants.asm tools/`
Expected: **no matches** (all renamed to `Sfx_DeepestDuck` / removed).

- [ ] **Step 5: Build gate.**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`
Expected: clean build (no undefined-symbol errors from the deleted constants).

- [ ] **Step 6: [ORACLE — needs go-ahead] Behavior-change verification.** This is a deliberate Stage-A behavior CHANGE: Stage A ducked by priority; now nothing ducks until a `sfh_duck` is authored (all default 0). Verify the HCZ2 music bed level no longer dips under jump/spindash spam (rendered RMS check, per the "verify real output" rule). Record the divergence in the queue log for the user's by-ear pass. If go-ahead is not given, note this unchecked — the logic is verified by the build + the grep in Step 4.

- [ ] **Step 7: Commit**

```bash
git add engine/sound/sound_sfx.asm sound_constants.asm tools/sfx_transcode.py
git commit -m "feat(sound): per-SFX duck depth replaces global threshold/depth — duck is authored, deepest-active wins (Stage B)"
```

---

### Task 4: Non-latching priority (bit 7) + instance caps

**Files:**
- Modify: `engine/sound/sound_sfx.asm` (header read :722-723; retrigger scan :731-761; init store :875-876; new `Sfx_MinActiveKind` helper)

- [ ] **Step 1: Split the incoming priority into masked + raw at header read.** In `Sfx_BeginSound`, at the header read (:722-723), replace the single `SND_SFX_DISP_PRIO` write with a masked value for arbitration + a raw value (bit 7 preserved) for the store decision. All EXISTING compares read `SND_SFX_DISP_PRIO`, which is now always bit-7-clear, so no other compare needs masking:

```asm
        ld      a, (iy+SFXH_PRIORITY)
        ld      (SND_SFX_DISP_PRIO_RAW), a  ; raw: bit 7 = non-latching request
        and     $7F
        ld      (SND_SFX_DISP_PRIO), a      ; masked: every arbitration compare reads this
```

Also stash the cap for Step 3, right here (header base still in `iy`):

```asm
        ld      a, (iy+SFXH_CAP)
        ld      (SND_SFX_DISP_CAP), a
```

- [ ] **Step 2: Add the `Sfx_MinActiveKind` helper.** Place it near `Sfx_DeepestDuck`. Returns the minimum `sx_priority` among ACTIVE slots whose `sx_kind` matches `c`, or 0 if none:

```asm
; ----------------------------------------------------------------------
; Sfx_MinActiveKind — min sx_priority among ACTIVE same-kind slots.
; In: c = incoming kind (SFXEL_*). Out: a = min priority (0 if no same-kind active).
; Walks via iy. Clobbers af,b,de,hl,iy. Preserves ix, c.
; ----------------------------------------------------------------------
Sfx_MinActiveKind:
        ld      iy, SND_SFX_CHANNELS
        ld      b, SFX_VOICE_COUNT
        ld      de, SfxChannel_len
        ld      h, 255                   ; h = running min (sentinel)
        ld      l, 0                     ; l = found flag
.mk_scan:
        bit     SCF_ACTIVE_B, (iy+sc_flags)
        jr      z, .mk_next
        ld      a, (iy+sx_kind)
        cp      c
        jr      nz, .mk_next             ; different kind -> ignore
        ld      a, (iy+sx_priority)
        cp      h
        jr      nc, .mk_next             ; >= running min -> keep
        ld      h, a                     ; new min
        ld      l, 1                     ; mark found
.mk_next:
        add     iy, de
        djnz    .mk_scan
        ld      a, l
        or      a
        ld      a, h
        ret     nz                       ; found -> a = min priority
        xor     a                        ; none active -> 0
        ret
```

- [ ] **Step 3: Non-latching store at slot init.** In `Sfx_BeginSound`, replace the priority store (:875-876) — `sx_kind` is written just above at :871, so it is available:

```asm
        ; --- priority store: non-latching (bit 7) SFX record the current same-kind
        ; floor (min-of-active) instead of their own priority, so they play now but
        ; never raise the floor for later sounds (spec §5, S2's trick). Normal SFX
        ; store their (masked) priority. iy is the record ptr here -> save it.
        ld      a, (SND_SFX_DISP_PRIO_RAW)
        bit     7, a
        jr      z, .latch_prio
        push    iy                       ; preserve channel-record ptr (Sfx_Steal needs it)
        ld      c, (ix+sx_kind)
        call    Sfx_MinActiveKind        ; a = min same-kind active priority (0 if none)
        pop     iy
        jr      .store_prio
.latch_prio:
        ld      a, (SND_SFX_DISP_PRIO)   ; normal: store the real (masked) priority
.store_prio:
        ld      (ix+sx_priority), a
```

- [ ] **Step 4: Instance caps — count-then-act retrigger scan.** Replace the retrigger replace-in-place scan (:743-761) with a two-phase version: phase 1 counts active same-id instances and records the lowest-slot match (no `Sfx_Restore` inside the scan, since it clobbers `de`/`hl`/`bc`); phase 2 kills the lowest-slot match only when `count >= cap`. `sfh_cap == 1` degenerates to today's replace-in-place (byte-identical).

```asm
        ; --- RETRIGGER + INSTANCE CAP (spec §7.1) ----------------------------------
        ; Phase 1: count ACTIVE slots running THIS id; remember the LOWEST-slot match.
        ld      ix, SND_SFX_CHANNELS
        ld      hl, SND_SFX_ID_TAB
        ld      b, SFX_VOICE_COUNT
        ld      c, 0                     ; c = match count
        ld      d, SFX_SLOT_NONE         ; d = lowest-slot match (none yet)
        ld      e, 0                     ; e = slot cursor
.cap_scan:
        bit     SCF_ACTIVE_B, (ix+sc_flags)
        jr      z, .cap_next             ; inactive -> id entry stale
        ld      a, (SND_SFX_DISP_ID)
        cp      (hl)
        jr      nz, .cap_next            ; different id -> leave playing
        inc     c                        ; another live instance
        ld      a, d
        cp      SFX_SLOT_NONE
        jr      nz, .cap_next            ; already have a lower slot recorded
        ld      d, e                     ; record first (lowest) match slot
.cap_next:
        inc     hl
        inc     e
        push    de                       ; SfxChannel_len add clobbers nothing, but keep de tidy
        ld      de, SfxChannel_len
        add     ix, de
        pop     de
        djnz    .cap_scan
        ; Phase 2: if count < cap, allocate a NEW instance (no kill). Else kill the
        ; lowest-slot match (oldest-by-slot approx) then allocate into the freed voice.
        ld      a, c
        ld      hl, SND_SFX_DISP_CAP
        cp      (hl)
        jr      c, .cap_ok               ; count < cap -> room for a new instance
        ; count >= cap -> kill the lowest-slot match (d). d == NONE is impossible when
        ; count > 0, but guard defensively.
        ld      a, d
        cp      SFX_SLOT_NONE
        jr      z, .cap_ok
        call    Sfx_SlotPtr              ; ix = &SfxChannel[d]
        call    Sfx_Restore              ; full end path: restore/silence + deactivate
.cap_ok:
```

(`Sfx_SlotPtr` is the existing slot-index → `ix` helper used by `Sfx_SelectVoice` at :1458/:1486. `SFX_SLOT_NONE` is the existing sentinel.) The block that followed the old scan (`.chan_loop:` at :763) is unchanged — the just-freed voice is the preferred route again, so the net effect for cap 1 is replace-in-place.

- [ ] **Step 5: Build gate.**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`
Expected: clean build (~≤ 60 B for the helper + two scans).

- [ ] **Step 6: [ORACLE — needs go-ahead] Register gates.**
  - Jump ($62) spam: still exactly **1** concurrent instance (cap 1, count FM key-ons / `$28` writes = 1 — the Stage-A gate).
  - Author a single-channel test SFX with `cap=2` (Task 1 rule permits it), spam it: exactly **2** instances, then the 3rd replaces the oldest (lowest slot). Remove the test SFX before Task 6.
  - Non-latching: author a test SFX with `sfh_priority | $80`; confirm its stored `sx_priority` equals the min-active same-kind floor (read the slot RAM), and that a subsequent lower-priority SFX can steal its voice.

  If go-ahead is not given, note unchecked; the cap-1 byte-equivalence is asserted by the degenerate path, but the cap-2 and non-latching mechanics are best confirmed on the emulator — flag them as pending in the commit body.

- [ ] **Step 7: Commit**

```bash
git add engine/sound/sound_sfx.asm
git commit -m "feat(sound): non-latching priority (bit 7 floor-neutral, min-of-active store) + authored instance caps w/ oldest-slot kill (Stage B; cap 1 = Stage-A-exact)"
```

---

### Task 5: Stage C — continuous-SFX class

**Files:**
- Modify: `engine/sound/sound_sfx.asm` (slot init :876 block — seed `sx_extend`; retrigger path — re-ping short-circuit; `Sfx_Frame` per-slot loop :270-296), `engine/sound/sound_sequencer.asm` (`Seq_Op_Jump` :1752-1760)

`sx_extend` tri-state (Task 0): `0` = not continuous; `1..SFX_EXTEND_FRAMES` = continuous & alive; `$FF` = continuous & expiring. No current SFX sets `SHF_CONTINUOUS`, so the full-regression gate is "all 9 register-identical."

- [ ] **Step 1: Seed `sx_extend` at slot init.** In the Task 2 Step 1 init block (after stashing `sx_gain`/`sx_duck`, `iy` = header base inside the same `push iy`/`pop iy`), seed the countdown from the flag:

```asm
        ; Stage C: continuous SFX start their re-ping countdown; others pin sx_extend
        ; at 0 (never continuous). Seq_Op_Jump reads this tri-state at the loop boundary.
        ld      a, (iy+SFXH_FLAGS)
        and     SHF_CONTINUOUS
        jr      z, .not_continuous
        ld      a, SFX_EXTEND_FRAMES
        ld      (ix+sx_extend), a
        jr      .cont_done
.not_continuous:
        ld      (ix+sx_extend), 0
.cont_done:
```

(Fold this into the single `push iy … pop iy` from Task 2 Step 1 so `iy` is restored once.)

- [ ] **Step 2: Re-ping short-circuit in the retrigger path.** In `Sfx_BeginSound`, BEFORE the Task 4 cap scan, add a fast path: if the blob is continuous AND an active slot already runs this id, just reload that slot's countdown and RETURN — no re-key, no kill, so rev/`MEV_SPINREV` state is preserved by construction (spec §7.2). The header base is in `SND_SFX_DISP_BASE`:

```asm
        ; --- Stage C: continuous re-ping. If this id is continuous and already
        ; running, refresh its extend countdown and return (free ping; no re-key). --
        ld      iy, (SND_SFX_DISP_BASE)
        ld      a, (iy+SFXH_FLAGS)
        and     SHF_CONTINUOUS
        jr      z, .not_reping           ; not continuous -> normal dispatch
        ld      ix, SND_SFX_CHANNELS
        ld      hl, SND_SFX_ID_TAB
        ld      b, SFX_VOICE_COUNT
.reping_scan:
        bit     SCF_ACTIVE_B, (ix+sc_flags)
        jr      z, .reping_next
        ld      a, (SND_SFX_DISP_ID)
        cp      (hl)
        jr      nz, .reping_next
        ld      (ix+sx_extend), SFX_EXTEND_FRAMES  ; refresh countdown; keep playing
        ret                              ; ping consumed — do NOT re-dispatch
.reping_next:
        inc     hl
        ld      de, SfxChannel_len
        add     ix, de
        djnz    .reping_scan
.not_reping:
```

- [ ] **Step 3: Countdown in `Sfx_Frame`.** In the `Sfx_Frame` per-slot loop (:270-296), inside the active-slot body (after `push bc` at :273, before `ModUpdate` at :276), decrement continuous slots that are no longer being pinged, and mark the expiring state. Non-continuous slots (`sx_extend == 0`) are untouched:

```asm
        ; Stage C: age the re-ping countdown. 0 = not continuous (skip). 1 -> $FF
        ; (mark "expiring": end at the next loop boundary). 2..N -> decrement. A ping
        ; this frame (Sfx_BeginSound) already reset it to N before Sfx_Frame runs.
        ld      a, (ix+sx_extend)
        or      a
        jr      z, .extend_done          ; not continuous
        inc     a                        ; a==$FF (already expiring)? then a==0 -> leave
        jr      z, .extend_done
        dec     a                        ; undo the test-inc; a = current
        dec     a                        ; count down one
        jr      nz, .extend_store
        ld      a, $FF                   ; hit 0 -> expiring sentinel
.extend_store:
        ld      (ix+sx_extend), a
.extend_done:
```

- [ ] **Step 4: Loop-boundary gate in `Seq_Op_Jump`.** In `engine/sound/sound_sequencer.asm`, `Seq_Op_Jump` (:1752, SHARED by music + SFX). Add an SFX-class + expiring check FIRST: a continuous SFX slot in the `$FF` state ends here (fall through to `Seq_Op_End`'s behavior — the natural stream-end, which already carries the 0ac3403 modSet freeze / fade-tail semantics) instead of looping. Music channels (`ix < SND_SFX_BASE`) and alive/non-continuous SFX loop exactly as before:

```asm
Seq_Op_Jump:
        ; Stage C: a continuous SFX slot that has run out of pings (sx_extend == $FF)
        ; ENDS here instead of re-looping, so the last loop fades out ~one loop after
        ; pings stop. Guard on SFX class FIRST — music SeqChannels have no sx_extend
        ; (offset +65 is a music field), so they must never read it.
        push    hl
        call    Snd_ChanClass            ; CARRY set => MUSIC channel
        pop     hl
        jr      c, .do_jump              ; music -> normal loop (unchanged)
        ld      a, (ix+sx_extend)
        inc     a                        ; $FF -> 0 : expiring?
        jr      nz, .do_jump             ; not expiring (0/alive) -> normal loop
        jp      Seq_Op_End               ; expiring continuous SFX -> end the stream
.do_jump:
    ifdef __DEBUG__
        ld      a, SEQEV_JUMP
        call    Seq_Trace                ; (loads route from ix; hl not needed)
    endif
        ld      l, (ix+sc_loop_ptr)
        ld      h, (ix+sc_loop_ptr+1)    ; hl = loop target
        jr      Seq_ContinueFetch        ; zero tick -> resume fetching there
```

Note: `Seq_Op_End` re-reads `hl` as the current stream ptr for its `sc_stream_ptr` store, so the `jp Seq_Op_End` must be reached with `hl` = post-`MEV_JUMP`-opcode ptr — which it is (the fetch loop advanced `hl` past the opcode before dispatching). Verify `Snd_ChanClass` preserves the fetch cursor: it clobbers `hl`, hence the `push hl`/`pop hl` around it.

- [ ] **Step 5: Build + full regression gate.**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`
Expected: clean build (~≤ 45 B).

- [ ] **Step 6: [ORACLE — needs go-ahead] Mechanism proof.**
  - Full regression: NO current blob sets `SHF_CONTINUOUS`, so all 9 SFX (incl. the `SHF_LOOP`-only ones 35/36/3C/AB) must be **register-identical** to the pre-Task-5 build — `sx_extend == 0` means `Seq_Op_Jump` loops them exactly as before.
  - Author a looping test SFX with `SHF_CONTINUOUS | SHF_LOOP` (Task 1 fixtures): ping it every frame → it sustains; stop pinging → it fades and ends within one loop + `SFX_EXTEND_FRAMES` frames. Remove the test SFX before Task 6.
  - OPTIONAL taste: rendered spindash-charge A/B vs S3K IF the user opts to re-author spindash as continuous later — NOT a gate; record either way.

  If go-ahead is not given: the "all 9 pinned at `sx_extend == 0` → loop unchanged" argument makes the regression safe by construction; note the continuous-mechanism proof as pending.

- [ ] **Step 7: Commit**

```bash
git add engine/sound/sound_sfx.asm engine/sound/sound_sequencer.asm
git commit -m "feat(sound): continuous-SFX class — SHF_CONTINUOUS + tri-state sx_extend re-ping countdown, fade-out one loop after pings stop (Stage C, S3K semantics)"
```

---

### Task 6: Cross-package validity + tracking closure

**Files:**
- Modify: `tools/sfx_transcode.py` (jingle rule) + `tools/test_sfx_transcode.py`, `docs/DEFERRED_WORK.md`, `docs/ENGINE_ARCHITECTURE.md` (§6 sound), `docs/superpowers/2026-07-03-sound-banking-queue.md`, spec `docs/superpowers/specs/2026-07-02-sfx-fidelity-and-mixing-design.md`

- [ ] **Step 1: Package-1 cross-rule (jingle class).** If package 1 (game-feel spec §5) has merged: blobs marked jingle-class reject `SHF_CONTINUOUS`, `SHF_LOOP`, FM6 and DAC routes. Add the rule in `pack_sfx` (match however Task 1 shaped the config — a `jingle` descriptor bit or a `--jingle` class), plus a test per rejection:

```python
def test_jingle_rejects_continuous_loop_fm6_dac():
    for bad in (dict(flags=SHF_LOOP), dict(flags=SHF_CONTINUOUS | SHF_LOOP),
                dict(route=CHROUTE_FM6), dict(route=CHROUTE_DAC)):
        with pytest.raises(TranscodeError, match="jingle"):
            pack_sfx_fixture(jingle=True, **bad)
```

If package 1 has NOT merged, the rule still lands (it is packer-side only, harmless without jingle blobs); note the dependency in the commit body.

- [ ] **Step 2: Docs sync.**
  - `docs/DEFERRED_WORK.md`: the "SFX Fidelity Stage B/C" entry → per-item outcomes, INCLUDING the two flagged behavior changes (duck-by-authoring; the non-latching store = min-of-active vs the spec's literal "min-of-active" — matched). Keep H3 (music-relative level) and the full rendered S3K A/B as still-by-ear-gated in DEFERRED_WORK.
  - `docs/ENGINE_ARCHITECTURE.md` sound section → Stage B/C SHIPPED (gain/duck/cap/non-latching/continuous); note `sx_extend` tri-state + the 66-byte `SfxChannel`.
  - `docs/superpowers/2026-07-03-sound-banking-queue.md` → package 2 EXECUTED.
  - The spec gets a Stage-B/C outcome line under its Stage-A status header.

- [ ] **Step 3: Final gates.**

Run: `python -m pytest tools/test_sfx_transcode.py -v` → all PASS
Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` → clean
Run: `./build.sh` (plain, no sound) → clean (confirms the sound code is properly guarded)
Run: `git diff --stat games/sonic4/data/sound/sfx/` after regenerating with all defaults → ZERO changes (9-SFX byte-identity holds after ALL tasks)
Record the total resident-byte delta (target ≤ ~50 B code; RAM +16 B: 2 struct × 7 slots + 2 scratch).

- [ ] **Step 4: Commit**

```bash
git add tools/sfx_transcode.py tools/test_sfx_transcode.py docs/DEFERRED_WORK.md docs/ENGINE_ARCHITECTURE.md docs/superpowers/2026-07-03-sound-banking-queue.md docs/superpowers/specs/2026-07-02-sfx-fidelity-and-mixing-design.md
git commit -m "docs(sound): package 2 executed — Stage B/C closure sync + jingle-class validity rules"
```

- [ ] **Step 5: Finish the branch.** Use superpowers:finishing-a-development-branch to merge `feat/sfx-fidelity-stage-bc` to `master`.

---

## Self-review notes

- **Spec coverage:** §5/§7 gain → T2; duck depth → T3; non-latching priority + instance cap → T4; continuous class → T5; constants byte-sync rule (§6) → T1/T3; jingle cross-rules → T6. RAM layout for all three new per-slot bytes → T0. H3 (music-relative level) and the full rendered S3K A/B stay by-ear-gated (unchanged in DEFERRED_WORK).
- **Two deliberate behavior changes flagged for the user's by-ear pass:** (1) duck-by-authoring — no SFX ducks until a `sfh_duck` is authored (T3 Step 6 note; Stage A ducked by priority); (2) the roll-gain taste knob (default 0 = S3K-authentic).
- **One resolved ambiguity to surface:** non-latching store value. The plan implements the spec's literal "min-of-active" via `Sfx_MinActiveKind` (T4). A simpler `sx_priority = 0` (strictly floor-neutral) was considered and rejected to stay faithful to the banked addendum — swap-in is a one-line change if the user prefers it.
- **Byte-identity gates every task** — defaults reproduce Stage A exactly (gain 0 no-op, duck 0 no-arm, cap 1 replace-in-place, no continuous flags → `sx_extend` pinned 0), so the phase is safe to merge before any taste value is chosen.
- **Emulator gates isolated:** every oracle check is marked **[ORACLE — needs go-ahead]** and each has a build-assert/pytest/logic fallback so the phase completes without the emulator if go-ahead is withheld.
