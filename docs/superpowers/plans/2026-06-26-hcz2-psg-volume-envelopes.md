# PSG Volume Envelopes for Music Channels (HCZ2 hi-hat) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give HCZ2's PSG noise hi-hat (and the PSG1/2 tone leads) their per-hit S3K volume-envelope decay so the noise channel stops being a flat continuous wash.

**Architecture:** The engine already has an S3K-exact PSG volume-envelope engine (`PsgEnvUpdate`) and a global id-keyed envelope bank (`PsgVolEnv_*`), wired for SFX only. Extend the music `SeqChannel` by 3 bytes so it carries the envelope fields, flip the three SFX-only gates to also serve music PSG channels, import HCZ2's 5 `sTone` envelopes into the global bank, and have the converter map `sTone_NN → PsgEnv(NN)` instead of `PsgEnv(0)`.

**Tech Stack:** Z80 assembly (engine + tables), AS macro assembler, Python 3 (converter + table generator), oracle (Exodus) MCP for verification.

**Spec:** `docs/superpowers/specs/2026-06-26-hcz2-psg-volume-envelopes-design.md`

**Build/verify:** `timeout 360 env SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` (asl can hang — always timeout-wrap). Verify in oracle only (no real HW). HCZ2 trigger = DEBUG **UP** button.

**Key facts (researched):**
- `SeqChannel` is 39 bytes (`sound_constants.asm`, ends at `sc_fill_count` +38); `SfxChannel` (62 B) already has `sc_psgenv` +39 / `sc_psgenv_cur` +40 / `sc_psgenv_out` +41.
- RAM: `SND_SEQ_CHANNELS=$1808`, `CHROUTE_COUNT=11`, `SND_SONG_BUF=$1B00` and `SND_SFX_BASE=$1D00` are FIXED literals. `SND_SEQ_END=$1808+11*SeqChannel_len` → 39:$19B5, 42:$19D6 (far below $1B00; build-time `fatal` guards backstop). Growing the array does NOT move `$1D00`, so the music-vs-SFX high-byte gate is unaffected.
- Pitch-mod fields (`sc_mod_*`, +42+) stay SfxChannel-only — music gets ONLY the 3 env fields. The `ModUpdate` PSG gate must therefore SPLIT (music = env-only; SFX = mod+env), not blanket-ungate.
- Envelope engine `PsgEnvUpdate`/`PsgVolEnv_Resolve` unchanged. Body bytes: plain = atten delta, `$80` loop, `$81` sustain, `$83` rest.
- HCZ2 uses `sTone_01,02,08,0A,0C` (counts 36/1/34/1/3). Engine `sTone_NN` = S3K `VolEnv_(NN-1)` → import `VolEnv_00/01/07/09/0B` (all clean: plain deltas + `$81`/`$83`). Generator = `tools/gen_sound_tables.py` `_PSG_VOL_ENVS`; S3K source = `skdisasm/Sound/Z80 Sound Driver.asm:4503-4525`.
- Channel init (`engine/z80_sound_driver.asm` `.chan_init`) sets fields individually (no bulk clear) → the 3 new fields must be explicitly zeroed at load.

---

## Task 1: Extend `SeqChannel` with the 3 PSG-envelope fields

**Files:**
- Modify: `sound_constants.asm` (SeqChannel struct, ~lines 805-809)

- [ ] **Step 1: Add the fields after `sc_fill_count`**

In the `SeqChannel struct` block, replace the end:

```asm
sc_fill_count   ds.b 1   ; +38 live per-frame note-fill countdown (0 = expired or disabled)
sc_psgenv       ds.b 1   ; +39 PSG vol-env id (1-based; 0 = none) — music + SFX share this offset
sc_psgenv_cur   ds.b 1   ; +40 PSG vol-env cursor (frame index into the body)
sc_psgenv_out   ds.b 1   ; +41 last computed atten delta (folded by Psg_SetVolume)
SeqChannel endstruct      ; = 42 bytes
```

- [ ] **Step 2: Update the length assert (39 → 42)**

```asm
        if SeqChannel_len <> 42
          error "SeqChannel struct is \{SeqChannel_len} bytes, expected 42"
```

Note: the `SfxChannel` struct keeps its own `sc_psgenv*` at +39/+40/+41 — identical offsets, so the shared-prefix `(ix+sc_*)` addressing stays valid (it just now extends to +41 on both). Do NOT touch `SfxChannel`.

- [ ] **Step 3: Build to confirm RAM still fits**

Run: `cd /home/volence/sonic_hacks/s4_engine-hcz2 && timeout 360 env SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh > /tmp/env_build.log 2>&1; echo EXIT=$?; grep -iE "error|fatal|Build complete" /tmp/env_build.log | tail`
Expected: `EXIT=0`, `Build complete`. (If a `fatal` boundary guard fires, the seq region overflowed — it should not at 42 B; stop and re-check.)

- [ ] **Step 4: Commit**

```bash
git add sound_constants.asm
git commit -m "feat(sound): SeqChannel carries the 3 PSG vol-env fields (+39..+41)"
```

## Task 2: Zero the new fields at song load

**Files:**
- Modify: `engine/z80_sound_driver.asm` (`.chan_init` loop, ~after line 1209)

- [ ] **Step 1: Zero `sc_psgenv`/`cur`/`out` in the per-channel init**

After the existing `ld (ix+sc_dur_default), 1` line in `.chan_init`, add:

```asm
        ; PSG vol-env starts disabled (id 0); cursor/out cleared so a no-env PSG
        ; channel folds a 0 delta (byte-identical to no envelope). Set ONLY by the
        ; MEV_PSGENV opcode + PsgEnvUpdate. The init sets fields individually (no
        ; bulk clear), so these MUST be cleared here or a stale env id from a prior
        ; song/SFX would spuriously shape a music PSG channel.
        ld      (ix+sc_psgenv), 0
        ld      (ix+sc_psgenv_cur), 0
        ld      (ix+sc_psgenv_out), 0
```

- [ ] **Step 2: Build green**

Run: `cd /home/volence/sonic_hacks/s4_engine-hcz2 && timeout 360 env SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh > /tmp/env_build.log 2>&1; echo EXIT=$?; grep -iE "error|fatal|Build complete" /tmp/env_build.log | tail`
Expected: `EXIT=0`, `Build complete`.

- [ ] **Step 3: Commit**

```bash
git add engine/z80_sound_driver.asm
git commit -m "feat(sound): zero the PSG vol-env fields at song-load channel init"
```

## Task 3: Split the `ModUpdate` PSG gate — run env for music PSG

**Files:**
- Modify: `engine/sound_sequencer.asm` (lines ~149-171, the PSG branch of `ModUpdate`)

- [ ] **Step 1: Restructure the PSG gate**

Replace the current block (from `bit SCF_IS_FM_B` down to the `jp PsgEnvUpdate` line) with:

```asm
        bit     SCF_IS_FM_B, (ix+sc_flags)
        jr      nz, .is_fm
        bit     SCF_IS_PSG_B, (ix+sc_flags)
        ret     z                        ; DAC or other non-PSG -> nothing
        ; PSG route. The pitch-MOD fields (sc_mod_*) are SfxChannel-only (+42+), so
        ; only an SFX PSG channel runs the modulation path; the VOL-ENV fields
        ; (sc_psgenv* at +39..+41) now exist on BOTH music and SFX SeqChannels, so
        ; the envelope path runs for either.
        call    Snd_ChanClass            ; CARRY set => MUSIC channel
        jr      c, .psg_env              ; music PSG -> env only (no mod fields)
        ; --- SFX PSG: pitch modulation (spec §5) first, then the vol-env ---
        ld      a, (ix+sc_mod_ctrl)
        or      a
        call    nz, Psg_ApplyMod         ; advance accum + re-latch tone divisor (no re-key)
.psg_env:
        ; --- PSG VOLUME ENVELOPE (spec §4): advance the contour + re-emit volume ---
        ld      a, (ix+sc_psgenv)
        or      a
        ret     z                        ; no PSG vol-env -> done
        jp      PsgEnvUpdate             ; advance the contour + emit (tail-call, preserves ix)
.is_fm:
```

Keep the explanatory comment block above it accurate (music PSG now runs the env path; only the mod path is SFX-gated). The reverted-noise-gate note (D1/F5) is unaffected — leave it.

- [ ] **Step 2: Build green**

Run: `cd /home/volence/sonic_hacks/s4_engine-hcz2 && timeout 360 env SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh > /tmp/env_build.log 2>&1; echo EXIT=$?; grep -iE "error|fatal|Build complete" /tmp/env_build.log | tail`
Expected: `EXIT=0`, `Build complete`. (No behavior change yet — no song emits a nonzero music `sc_psgenv` until Task 6.)

- [ ] **Step 3: Commit**

```bash
git add engine/sound_sequencer.asm
git commit -m "feat(sound): run PsgEnvUpdate for music PSG channels (env-only split)"
```

## Task 4: Un-gate the key-on cursor reset + the volume-fold for music PSG

**Files:**
- Modify: `engine/sound_psg.asm` (`Psg_EnvCursorReset` ~109-115; `Psg_SetVolume` env fold ~284-305)

- [ ] **Step 1: `Psg_EnvCursorReset` — drop the music gate**

Replace the body:

```asm
Psg_EnvCursorReset:
        ; Restart the PSG vol-env contour on a fresh attack. sc_psgenv_cur (+40)
        ; now exists on both music and SFX SeqChannels, so no channel-class gate is
        ; needed. Harmless on a no-env channel (cursor is unused while sc_psgenv=0).
        ld      (ix+sc_psgenv_cur), 0
        ret
```

- [ ] **Step 2: `Psg_SetVolume` — fold the env delta for any PSG channel**

Replace the gated fold (the `push hl` / `call Snd_ChanClass` / `pop hl` / `jr c, .env_done` preamble) with the direct fold:

```asm
        ; --- PSG volume envelope (spec §4): add the per-frame env atten delta ------
        ; sc_psgenv_out (+41) now exists on every PSG SeqChannel (music + SFX). A
        ; channel with no envelope has sc_psgenv_out = 0 -> the `or a / jr z` fast
        ; path skips the fold (byte-identical to no envelope). Underflow guard
        ; (S3K `bit 4,a`): a sum >= $10 forces $0F silent.
        ld      a, (ix+sc_psgenv_out)
        or      a
        jr      z, .env_done             ; no env delta -> skip
        add     a, c                     ; atten + env delta
        bit     4, a                     ; >= $10 ?
        jr      z, .env_ok
        ld      a, SND_PSG_ATTEN_SILENT  ; $0F (silent) clamp
.env_ok:
        ld      c, a
.env_done:
```

(Removes the `Snd_ChanClass` call + its `push hl`/`pop hl` — `hl` is no longer touched here.)

- [ ] **Step 3: Build green**

Run: `cd /home/volence/sonic_hacks/s4_engine-hcz2 && timeout 360 env SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh > /tmp/env_build.log 2>&1; echo EXIT=$?; grep -iE "error|fatal|Build complete" /tmp/env_build.log | tail`
Expected: `EXIT=0`, `Build complete`.

- [ ] **Step 4: Confirm `Psg_EnvCursorReset` is called on the PSG key-on path only**

Run: `grep -rn "Psg_EnvCursorReset" engine/*.asm`
Expected: called from the PSG note-on path. If it is also reachable for a non-PSG channel, the write to `sc_psgenv_cur` is still in-bounds (every SeqChannel now has +40) and harmless — note it but no change needed.

- [ ] **Step 5: Commit**

```bash
git add engine/sound_psg.asm
git commit -m "feat(sound): apply PSG vol-env cursor-reset + volume-fold to music PSG"
```

## Task 5: Import HCZ2's 5 `sTone` envelopes into the global bank

**Files:**
- Modify: `tools/gen_sound_tables.py` (`_PSG_VOL_ENVS`, ~line 292)
- Regenerate: `engine/sound_tables_z80.asm`

- [ ] **Step 1: Add the 5 envelopes (S3K-verbatim) to `_PSG_VOL_ENVS`**

Insert these entries (keep the list sorted by id for readability). Bytes are copied verbatim from `skdisasm/Sound/Z80 Sound Driver.asm`:

```python
    # id    sTone       S3K body  (== VolEnv_(id-1), verbatim)
    (0x01, "sTone_01", [2, _CTL_REST]),                                   # VolEnv_00
    (0x02, "sTone_02", [0, 2, 4, 6, 8, 0x10, _CTL_REST]),                 # VolEnv_01
    (0x08, "sTone_08", [0, 0, 0, 2, 3, 3, 4, 5, 6, 7, 8, 9, 0x0A, 0x0B,
                        0x0E, 0x0F, _CTL_REST]),                          # VolEnv_07
    (0x0A, "sTone_0A", [1, 0, 0, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3, 3, 4,
                        4, 4, 5, 5, _CTL_SUSTAIN]),                       # VolEnv_09
    (0x0C, "sTone_0C", [0, 0, 1, 1, 3, 3, 4, 5, _CTL_REST]),              # VolEnv_0B
```

(`_CTL_REST` = `$83`, `_CTL_SUSTAIN` = `$81`, already defined in the file.)

- [ ] **Step 2: Regenerate the engine table**

Run: `cd /home/volence/sonic_hacks/s4_engine-hcz2 && python3 tools/gen_sound_tables.py`
Expected: rewrites `engine/sound_tables_z80.asm`. Verify the new ids landed:

Run: `grep -n "PsgVolEnv_Ids:\|PSGVOLENV_COUNT\|PsgVolEnv_01\b" engine/sound_tables_z80.asm | head`
Expected: `PsgVolEnv_Ids` now lists `01h, 02h, 03h, 08h, 0Ah, 0Ch, 0Dh, 0Eh, 0Fh, 11h, 1Dh` (11 ids); `PsgVolEnv_01` body present.

- [ ] **Step 3: Build green (table sits at the song-bank start, co-located with HCZ2)**

Run: `cd /home/volence/sonic_hacks/s4_engine-hcz2 && timeout 360 env SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh > /tmp/env_build.log 2>&1; echo EXIT=$?; grep -iE "error|fatal|Build complete" /tmp/env_build.log | tail`
Expected: `EXIT=0`, `Build complete`. (If a bank-fit assert fires, the MT+DrumTest+HCZ2 bank overflowed — unlikely from ~60 envelope bytes; stop and reassess.)

- [ ] **Step 4: Commit**

```bash
git add tools/gen_sound_tables.py engine/sound_tables_z80.asm
git commit -m "feat(sound): import HCZ2's 5 S3K PSG vol-envelopes (sTone 01/02/08/0A/0C)"
```

## Task 6: Converter — map `sTone_NN → PsgEnv(NN)` (validated)

**Files:**
- Modify: `tools/smps_import.py` (`_dispatch_flag` smpsPSGvoice; add `_parse_psg_env_ids`)
- Test: `tools/test_smps_import.py`
- Regenerate: `data/sound/song_hcz2.asm`

- [ ] **Step 1: Write the failing tests**

Add to `tools/test_smps_import.py`:

```python
def test_smpspsgvoice_emits_envelope_id():
    # sTone_08 must map to PsgEnv(8), not the old PsgEnv(0).
    ev = convert_channel("PSG", ["\tsmpsPSGvoice sTone_08", "\tdc.b nC4, $0C"],
                         {}, _cfg(), ConvState())
    envs = [e for e in ev if isinstance(e, PsgEnv)]
    assert len(envs) == 1 and envs[0].env_id == 0x08

def test_smpspsgvoice_unknown_env_falls_back_to_zero():
    # An sTone with no imported engine envelope warns + emits PsgEnv(0) (safe).
    ev = convert_channel("PSG", ["\tsmpsPSGvoice sTone_19", "\tdc.b nC4, $0C"],
                         {}, _cfg(), ConvState())
    envs = [e for e in ev if isinstance(e, PsgEnv)]
    assert len(envs) == 1 and envs[0].env_id == 0
```

Also UPDATE the existing `test_psg_voice_safe_env` (it asserts `PsgEnv ... env_id == 0` for `sTone_0C`; `sTone_0C` is now imported → `env_id == 0x0C`):

```python
def test_psg_voice_safe_env():
    ev = convert_channel("PSG", ["\tsmpsPSGvoice sTone_0C", "\tdc.b nC4, $0C"],
                         {}, _cfg(), ConvState())
    assert any(isinstance(e, PsgEnv) and e.env_id == 0x0C for e in ev)
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd /home/volence/sonic_hacks/s4_engine-hcz2/tools && python3 -m pytest test_smps_import.py -q -k "psgvoice or psg_voice_safe_env"`
Expected: FAIL (current code emits `PsgEnv(0)`).

- [ ] **Step 3: Add `_parse_psg_env_ids` + rewrite the smpsPSGvoice handler**

In `tools/smps_import.py`, add a parser that reads the engine's imported envelope ids (auto-tracks the table, like `_parse_log_volume_lut`):

```python
def _parse_psg_env_ids() -> set:
    """Parse PsgVolEnv_Ids from engine/sound_tables_z80.asm -> {int id}. These are
    the sTone ids that have an imported PSG volume envelope; smpsPSGvoice maps to
    PsgEnv(id) only for these (else PsgEnv(0) + warn)."""
    path = os.path.normpath(os.path.join(_HERE, "..", "engine", "sound_tables_z80.asm"))
    ids = set()
    with open(path) as f:
        for line in f:
            m = re.match(r"\s*PsgVolEnv_Ids:\s*db\s+(.*)", line)
            if not m:
                continue
            for tok in m.group(1).split(";", 1)[0].split(","):
                tok = tok.strip()
                mh = re.fullmatch(r"([0-9A-Fa-f]+)[hH]", tok)
                if mh:
                    ids.add(int(mh.group(1), 16))
                elif tok.startswith("$"):
                    ids.add(int(tok[1:], 16))
                elif re.fullmatch(r"\d+", tok):
                    ids.add(int(tok))
            break
    return ids

_PSG_ENV_IDS = _parse_psg_env_ids()
```

Replace the `smpsPSGvoice` branch in `_dispatch_flag`:

```python
    elif mnem == "smpsPSGvoice":
        # PSG voice = an S3K PSG volume-envelope id (sTone_NN). Map to the engine's
        # imported PsgEnv(id) so each PSG hit gets its S3K decay contour (the hi-hat
        # "ts"). If the engine table has no body for this id, fall back to PsgEnv(0)
        # (flat, no envelope) and warn — so a missing import is loud, not silent.
        env_id = resolve_const(args[0])
        if env_id not in _PSG_ENV_IDS:
            warn("sTone $%02X has no imported PSG envelope (engine PsgVolEnv_Ids);"
                 " emitting PsgEnv(0)" % env_id)
            env_id = 0
        out.append(PsgEnv(env_id))
```

Delete the now-unused `_psg_env_warned` global + `_warn_psg_env_once` (and its call) — they were the old "always PsgEnv(0)" path.

- [ ] **Step 4: Run to verify the converter tests pass**

Run: `cd /home/volence/sonic_hacks/s4_engine-hcz2/tools && python3 -m pytest test_smps_import.py -q`
Expected: PASS (all, including the updated tie/period tests).

- [ ] **Step 5: Regenerate the HCZ2 song**

Run: `cd /home/volence/sonic_hacks/s4_engine-hcz2 && python3 data/sound/song_hcz2.py 2>&1 | grep -iv "WARN: sTone" | head`
Expected: `wrote .../song_hcz2.asm`. Confirm the PSG channels now carry nonzero envs:

Run: `grep -c "EB" data/sound/song_hcz2.asm` (MEV_PSGENV = $EB) — expect many; and no `WARN: sTone $XX has no imported` lines for HCZ2's sTones (01/02/08/0A/0C are all imported).

- [ ] **Step 6: Build green**

Run: `cd /home/volence/sonic_hacks/s4_engine-hcz2 && timeout 360 env SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh > /tmp/env_build.log 2>&1; echo EXIT=$?; grep -iE "error|fatal|Build complete" /tmp/env_build.log | tail`
Expected: `EXIT=0`, `Build complete`.

- [ ] **Step 7: Commit**

```bash
git add tools/smps_import.py tools/test_smps_import.py data/sound/song_hcz2.asm
git commit -m "feat(tools): map smpsPSGvoice sTone_NN -> PsgEnv(NN) (HCZ2 PSG envelopes)"
```

## Task 7: Oracle verification

**Files:** none (verification only)

- [ ] **Step 1: Snapshot ROM + listing to /tmp, reload oracle, load symbols**

```bash
cd /home/volence/sonic_hacks/s4_engine-hcz2 && cp s4.bin /tmp/hcz2_env.bin && cp s4.lst /tmp/hcz2_env.lst
```
Then via MCP: `emulator_reload_rom(/tmp/hcz2_env.bin)`, `emulator_load_symbols(/tmp/hcz2_env.lst)`.

- [ ] **Step 2: Boot, trigger HCZ2 (UP), capture a VGM**

`emulator_run_frames(240)`; `emulator_vgm_start(/tmp/hcz2_env.vgm)`; `emulator_press(["up"],3)`; `emulator_run_frames(~1800)`; `emulator_vgm_stop`.

- [ ] **Step 3: Confirm the noise attenuation now DECAYS per hit**

Run the PSG-noise extractor (from the drums-fix session): `python3 /tmp/psg_noise.py /tmp/hcz2_env.vgm`
Expected: the noise `vol(atten)` histogram is now SPREAD across multiple values with a decay contour (e.g. starts loud `2/3`, climbs toward `0Fh` silent per hit), NOT the old `{3: 735}` constant. Distinct hi-hat hits, not a wash. PSG1/2 channels likewise show envelope shaping.

- [ ] **Step 4: Listen / sanity-check structure**

Render or audition the VGM; confirm the hi-hat is percussive "ts" hits, the melody is unchanged, and nothing regressed (drums still in phase from the prior fix).

- [ ] **Step 5: Update docs + memory**

Update `docs/ENGINE_ARCHITECTURE.md` §6 (PSG vol-envelopes now serve music channels, not just SFX) and the memory. Commit:

```bash
git commit -m "docs(sound): PSG vol-envelopes serve music channels — HCZ2 hi-hat verified"
```

## Task 8: Finish the branch

- [ ] Per superpowers:finishing-a-development-branch — converter tests pass (`cd tools && python3 -m pytest test_smps_import.py -q`), build green, oracle-verified. Decide with the user whether to FF-merge `feat/hcz2-import` → master (this rides on top of the drums fix on the same branch).

---

## Self-review

- **Spec coverage:** struct +3 (Task 1) + zero-init (Task 2) → spec §1; gate splits (Tasks 3-4) → spec §2; envelope import (Task 5) → spec §3; converter map (Task 6) → spec §4; oracle (Task 7) → spec §5. All covered. Spec said "4 envelopes"; the real count is **5** (added `sTone_0A`) — Task 5 uses 5.
- **No placeholders:** every code step shows the actual asm/python. Envelope bytes are verbatim from the named S3K lines.
- **Type/offset consistency:** `sc_psgenv`/`cur`/`out` at +39/+40/+41 match `SfxChannel`; `PSGVOLENV_COUNT` 6→11; converter `PsgEnv(env_id)` matches the engine's 1-based id lookup; mod fields stay SFX-only (Task 3 split honors this).
- **Ordering:** engine first (Tasks 1-4, no behavior change), then data (5), then converter (6) flips the behavior on — each task builds green independently.
