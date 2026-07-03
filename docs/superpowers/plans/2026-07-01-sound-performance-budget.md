# Sound Performance & Budget Phase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the last audible gap between our HCZ2 rendering and real S3K (EG retriggers, drum airtime, vibrato fidelity, tempo) and recover ~780 B of Z80 code budget, then land portamento.

**Architecture:** Six ordered stages on one branch: budget recovery (delete COPY path + bank data tables + RAM repack) → key-off-before-key-on at the single FM chokepoint → per-note vibrato re-arm + pitch-table renormalization → DAC starvation fix (env write-on-change + Timer-B-paced ring drain at sequencer seams) → portamento (turnkey 2026-06-28 plan) → frame-clock retune. Spec: `docs/superpowers/specs/2026-07-01-sound-performance-budget-design.md` (APPROVED).

**Tech Stack:** Z80 assembly (AS Macro Assembler, `engine/sound/`), Python toolchain (`tools/`), oracle emulator MCP, vgm2wav rendered-audio verification.

**Two planning-time findings that simplify the spec** (verified against source during planning; flag any contradiction found during execution):

1. **C.c is generator-only.** `FNUM_LO = $0284` (644) / `FNUM_HI = $0508` (1288) in `sound_constants.asm:663-664` are ALREADY the canonical S3K band, enforced by asserts, and both block-correction routines (`Fm_FnumApplyDelta`, `Mod_Advance`) normalize into it. Only `tools/gen_sound_tables.py:fnum_block()` normalizes to `< 0x800`. Fix the generator; the engine needs zero changes.
2. **C.b needs no mechanism change.** Instruction-level comparison of our `Mod_Advance` (sound_sequencer.asm:626-743) vs S3K `zDoModulation` $80-path (skdisasm `Sound/Z80 Sound Driver.asm:1279-1326`) shows parity: wait countdown held at 1, speed-gated sign-extended delta add, steps decremented EVERY post-wait frame (ours in `.have_word`:720, S3K in `.mod_sustain`:1319), full-raw reload + `neg` on flip. The S3K "unipolar-up" observable comes from per-note re-arm (`zPrepareModulation` re-copies wait/speed/delta via 3 `ldi`s each note, skdisasm:1250-1252): short notes only ever exhibit the initial upward half-period from a zeroed accumulator. Fixing C.a (reload `wait` + `delta` sign per note) is expected to produce the reference contour; C.b is the VERIFICATION that it does. If the cents-series still mismatches after C.a, stop and re-derive before writing new mechanism.

**Verification harness (used by Tasks 4-11):** All fidelity claims by rendered audio numbers, never register counts alone. Reference = skdisasm-built S3K, NOP-patched so the title demo can't post music, playing id $04, captured in oracle with a purity check. Oracle Z80 addresses ALWAYS with `0x` prefix. Debug hotkeys: UP=HCZ2, A=MT, C=drumtest, START=stop, B=SFX cycle. `SOUND_DBG_MIRROR` OFF for captures. Build for all sound work: `DEBUG=1 ./build.sh` (sound is ON by default; `SOUND_DRIVER_ENABLED=0` is the opt-out).

**Branch:** `feat/sound-perf-budget` off master. Commit per green step. Master merge only at the end (Task 12) — except the optional stable waypoint after Task 4 if the phase must pause.

---

### Task 1: Verification harness + baselines

**Files:**
- Create: `<scratchpad>/s3k_ref/` capture + analysis scripts (session-local, not committed)
- Read: `docs/superpowers/HANDOFF-sound-performance-phase.md` §2, `docs/research/reference_captures/README.md`

- [x] **Step 1: Research.** Read the handoff §2 verification protocol and `docs/research/reference_captures/README.md` (trust levels — note `mt_ref.vgm` is THE MT reference). Confirm vgm2wav is available (`which vgm2wav` or find prior usage in docs/memory: it was used 2026-06-21..07-01). Check `ls /home/volence/sonic_hacks/skdisasm/sonic3k.bin`; if absent build it: `cd /home/volence/sonic_hacks/skdisasm && lua buildSK.lua` (per root CLAUDE.md).

- [x] **Step 2: Build the muted S3K.** Create `sonic3k_muted.bin` next to the scratchpad captures — patch every `move.b d0,($A01C0A/0B/0C).l` (the title-demo music posts) to NOPs:

```python
import pathlib
rom = bytearray(pathlib.Path("/home/volence/sonic_hacks/skdisasm/sonic3k.bin").read_bytes())
n = 0
for tail in (0x0A, 0x0B, 0x0C):
    sig = bytes([0x13, 0xC0, 0x00, 0xA0, 0x1C, tail])   # move.b d0,($A01Cxx).l
    i = 0
    while (i := rom.find(sig, i)) != -1:
        rom[i:i+6] = b"\x4E\x71" * 3                      # 3x NOP
        n += 1; i += 6
print("patched", n, "sites")   # expect 3 total (per handoff); investigate if 0
pathlib.Path("<scratchpad>/s3k_ref/sonic3k_muted.bin").write_bytes(bytes(rom))
```

- [x] **Step 3: Capture the S3K HCZ2 reference.** Load `sonic3k_muted.bin` in oracle (`emulator_reload_rom`), run past init, start VGM logging (`emulator_vgm_start`), trigger music id $04 via `emulator_z80_write` address `0x1C0A` value `0x04`, capture 60+ s, `emulator_vgm_stop`. **Purity-check before use** (per-second key-on histogram + content vs known HCZ2 shape — two investigations were poisoned by contaminated references). Save as `s3k_hcz2_ref.vgm`.

- [x] **Step 4: Recreate the analysis scripts** in the scratchpad (the 2026-07-01 set is gone with its session). Each renders via vgm2wav and/or parses VGM command streams. Minimum set + what each must output:
  - `clean_purity.py` — per-second key-on histogram + channel content (capture trust gate)
  - `dac_stall.py` — histogram of $2A inter-write gaps; % airtime in gaps > 1.5× sample period; max gap ms
  - `dac_perburst.py` — per-drum-hit wall-clock duration ($2A activity envelope)
  - `drum_loud.py` — per-hit attack RMS (rendered)
  - `melody_regs.py` — per-channel key-on vs key-off counts from $28 writes
  - `melody_cmp.py` — note-matched per-channel band RMS + inter-note silence fraction (rendered)
  - `gate_vib.py` / `vib_series.py` — per-note flat-frame count + fnum→cents series per channel ($A4/$A0 write stream)
  - `spectral.py` — band RMS + spectral centroid A/B
- [x] **Step 5: Baseline OUR current state.** Build master (`DEBUG=1 ./build.sh`), load in oracle, capture HCZ2 (hotkey UP) 60+ s → `ours_baseline.vgm`. Run the full script set against both captures; save the numbers table to `<scratchpad>/baseline_numbers.md`. Expect ≈ the handoff's findings (61/64 no-retrigger, 45-63% drum holds, doubled vibrato depth). If baseline diverges wildly from the handoff, STOP and reconcile before proceeding.
- [x] **Step 6: Branch + gates.** `git checkout -b feat/sound-perf-budget`. Run `python3 -m pytest tools/ -q` (expect 803+ passed) and record the count. Nothing committed from this task (scratchpad only).

### Task 2: A.1 — Delete the COPY load path

**Files:**
- Modify: `engine/sound/z80_sound_driver.asm` (~1020-1145 PATH A block + `FmPatchInlineTable` ~1444-1446 + `Snd_SavedDacBank` if now unused)
- Modify: `sound_constants.asm` (~1292-1302 `SND_SONG_BUF*` + asserts; `SND_SFX_BASE` derivation :1308)
- Possibly modify: whatever still references Song_Test/Ode (grep first)

- [x] **Step 1: Research.** Grep for consumers: `grep -rn "SND_SONG_BUF\|FmPatchInlineTable\|SH_F_STREAM\|Song_Test\|SongTest\|Ode" engine/ games/ tools/ *.asm`. Identify every COPY-mode song in the song table (SH_F_STREAM clear) and every debug hook that can trigger one. Decide migrate-vs-retire: if a COPY song is reachable from debug hotkeys or self-tests, repack it as STREAM (tools/song_packer.py emits STREAM headers already — check how MT/HCZ2 set the flag); if it is dead bring-up content, delete the data + its table entry.
- [x] **Step 2: Delete PATH A.** In `Snd_LoadSong`: remove the `bit SH_F_STREAM_B, a / jp nz, .stream_path` branch and the whole PATH A block (z80_sound_driver.asm:1120-1145) so control falls straight into the current `.stream_path` body (keep the label as a comment landmark or fold it away — no dormant paths, per the clean rule). Keep the `SH_F_STREAM` header BIT reserved: add one comment line at the flag's constant that the packer still sets it and the engine now requires/ignores it, and add a packer-side assert (tools/song_packer.py) that every packed song has the flag SET — the packer is the format authority.
- [x] **Step 3: Delete the corpses.** `FmPatchInlineTable` (z80_sound_driver.asm:1444-1446), `SND_SONG_BUF`/`SND_SONG_BUF_SIZE` + their overrun asserts (sound_constants.asm:1292-1302), `Snd_SavedDacBank` if PATH A was its only user (grep). Re-derive `SND_SFX_BASE`: it is currently `SND_SONG_BUF + SND_SONG_BUF_SIZE` with a pinned `= $1D00` assert — for THIS task pin it directly (`SND_SFX_BASE = $1D00`) so the map doesn't move yet; Task 4 does the repack in one deliberate pass.
- [x] **Step 4: Build + boot.** `DEBUG=1 ./build.sh` — green, and record the freed bytes from the `Z80 sound budget` build line (expect ≈ +100-130 incl. code). Load in oracle, runtime boot test, then: HCZ2 plays (UP), MT plays (A), drumtest fires (C), an SFX plays (B). If a debug hotkey pointed at a retired COPY song, it must now do nothing gracefully or point at a STREAM song — no crash.
- [x] **Step 5: pytest.** `python3 -m pytest tools/ -q` — no regressions (packer assert from Step 2 included in a new/extended test in `tools/test_song_packer.py`: packing a song yields SH_F_STREAM set).
- [x] **Step 6: Commit.** `git add <exact files>` and commit: `feat(sound): delete the COPY load path — all songs stream (budget recovery A.1)`.

### Task 3: A.2 — Bank DacSampleTable + SeqOpcodeTable (data co-location)

**Files:**
- Modify: `engine/sound/z80_sound_driver.asm` (DacSampleTable ~1460-1532; the `phase 08000h` co-location block ~1422-1435)
- Modify: `engine/sound/sound_sequencer.asm` (SeqOpcodeTable + its dispatch read), reader sites for DacSampleTable

- [x] **Step 1: Research.** Read the existing co-location precedent: z80_sound_driver.asm:1422-1435 (`FmPitchTableZ` et al under `phase 08000h` at the song-bank head) and the `SfxBlobWinTab` banked-DATA pattern (sound_sfx.asm:530-546, engine/sound/sfx_blob_win_tab.asm). Read DEFERRED_WORK's "Bank-D DAC co-location hook" note (:1136 area) — the hook for placing data in the DAC bank may already exist. Map every reader of `DacSampleTable` (expect: `Snd_StartSample` descriptor fetch) and of `SeqOpcodeTable` (the `.coord` dispatch in `Sequencer_NextOpcode`) and note which bank the window holds at each read site (song bank during music dispatch, SFX blob bank during SFX dispatch, sample bank inside `Snd_StartSample`).
- [x] **Step 2: Move SeqOpcodeTable** into the same `phase 08000h` head block as `FmPitchTableZ`. Constraint this inherits (already true for FmPitchTableZ, which BOTH music dispatch and SFX-tier `Fm_NoteOn` read): **the engine-table head must be present in every bank the sequencer runs on** — today music + SFX share one bank, so one copy; add a loud comment at the phase block stating the replicate-per-bank rule for the multi-bank future. The dispatch read needs no code change (label resolves to its $8000-window address).
- [x] **Step 3: Move DacSampleTable** into the DAC sample bank head (the Bank-D hook / wherever the DAC samples assemble). The reader inside `Snd_StartSample` must read it with the window ON that bank — check the order of its existing SetBank vs the descriptor fetch and reorder within the routine if the fetch currently precedes the bank switch. If `Snd_StartSample` can be invoked while the window holds the song bank (mailbox poll mid-tick), the SetBank-first pattern from `SfxBlobWinTab` (push af / SetBank / pop af) is the model; the sample bank is left set afterward, which is the existing B1 contract.
- [x] **Step 4: Build + verify on oracle.** Green build; record freed bytes (expect ≈ +150 cumulative with Task 2). Boot; HCZ2 (drums audible = DacSampleTable read works), MT, drumtest C (every drum id fires), SFX cycle B (SFX dispatch = SeqOpcodeTable read on the SFX bank path works). A missing/garbled drum or a dead opcode = a bank-visibility mistake — fix before proceeding.
- [x] **Step 5: Commit.** `feat(sound): bank DacSampleTable + SeqOpcodeTable as co-located window data (budget recovery A.2)`.

### Task 4: A.3 — RAM repack + code-ceiling raise + struct growth

**Files:**
- Modify: `sound_constants.asm` (the whole Z80 RAM map region + SeqChannel/SfxChannel structs + shared-offset asserts)
- Modify: `engine/sound/z80_sound_driver.asm` (`SND_RING_PAGE` uses — the hardcoded `$17` lives in the constant already; verify no literal page bytes elsewhere)
- Rewrite: `docs/superpowers/specs/2026-06-16-sound-z80-ram-map.md`

- [x] **Step 1: Research.** Read the current full map (sound_constants.asm: state block :56-67, ring :186-200, seq :1176-1184, sfx :1308-1331, mailbox/status/stack — locate `SND_REQ_BASE`/`SND_STAT_BASE`/stack top) and list every pinned-address assert. Read the AS even-alignment lesson (memory: an odd `ds.b` count address-error-crashes the next word field at runtime while the build stays green — pad to even). Confirm which addresses are EXTERNAL contract: the mailbox/status region (`SND_REQ_MUSIC`=0x1F02 etc.) is used by 68k code via the shared constants AND by oracle debug workflows/docs — keep `$1F00+` FIXED.
- [x] **Step 2: Add the two struct fields.** In BOTH `SfxChannel` and `SeqChannel` structs (sound_constants.asm ~:890-1030), after `sc_mod_step_raw`: `sc_mod_wait_raw ds.b 1` and `sc_mod_delta_raw ds.b 1` (keeps the mod block contiguous; `sc_mod_accum`/`sc_base_freq`/`sc_last_freq` shift by 2 — they are struct-relative, so only the size asserts and the shared-offset assert list change). SeqChannel 58→60, SfxChannel 62→64 — update both `endstruct` size asserts and extend the shared-offset assert (:1041 area) with the two new names. Both sizes stay even.
- [x] **Step 3: Repack the map.** New layout (each region asserted against the next; keep `$1F00+` fixed):

```
SND_STATE_BASE   = $18F0                 ; code ceiling raised $16F0 -> $18F0 (+512)
                                          ; state block $18F0..$18FC (unchanged layout)
SND_RING_PAGE    = $19                   ; ring $1900..$19FF (256-aligned page)
SND_SEQ_BASE     = $1A00                 ; hdr $1A00..$1A07, channels $1A08 + 11*60 = ..$1CA3
SND_SFX_BASE     = $1CA4                 ; 7 * 64 = 448 -> ..$1E63
                                          ; $1E64..$1EFF = stack / spare (place per current map)
                                          ; $1F00+ mailbox/status — UNCHANGED (external contract)
```

  Derive `SND_SFX_BASE = SND_SEQ_CHANNELS + CHROUTE_COUNT*SeqChannel_len` (computed, not pinned) and add asserts: ring page ≥ state end, seq ≥ ring end, sfx array end < stack base, stack base ≤ `$1F00`. Delete the `$1D00` pin from Task 2. Update the code-ceiling assert message (z80_sound_driver.asm:1560) if it names the old value.
- [x] **Step 4: Sweep for hardcoded addresses.** `grep -rn "1700\|1800\|1808\|1B00\|1D00\|16F0\|\$17\b" engine/sound/ *.asm tools/` — every hit must be a constant reference or get one. Check `tools/` too (generators/tests may pin RAM addresses — the constants-sync pytest pattern).
- [x] **Step 5: Build + BOOT + soak.** Green build (record: ceiling gain +512, cumulative recovery ≈ 660-680, spendable headroom now ≈ the build line's report). **Runtime boot test is mandatory** (the alignment lesson). Then a 3000+ frame soak playing HCZ2 with SFX fired over it (B during UP), checking via oracle: `SND_SEQ_ACTIVE` nonzero at its NEW address, channel structs advancing, no Z80 PC excursion, no audio garbage. MT plays. Update any oracle-workflow doc snippets that cited old addresses (the RAM-map spec rewrite below is the home).
- [x] **Step 6: Rewrite the RAM-map spec.** Replace the stale content of `docs/superpowers/specs/2026-06-16-sound-z80-ram-map.md` with the new map + an amendment header (dated, pointing at this plan + the reclaim decision). This closes DEFERRED F1.
- [x] **Step 7: pytest + commit.** `python3 -m pytest tools/ -q` green. Commit: `feat(sound): Z80 RAM repack — +512 B code ceiling, +2 B mod-reload struct fields, RAM-map spec rewritten (A.3)`. *(Optional stable waypoint: if the phase must pause here, this tree is merge-safe after re-running Task 1's regression set.)*

### Task 5: B — Key-off-before-key-on at the FM chokepoint

**Files:**
- Modify: `engine/sound/sound_fm.asm` (`Fm_NoteOnFreq` keyon section :833-861)
- Modify: `engine/sound/sound_sequencer.asm` (`Seq_RekeySingle` :427-448, `Seq_Op_NoteRaw` :1159-1169)
- Modify: `sound_constants.asm` (delete `SND_REKEY_OFF_THEN_ON` :1142)

- [x] **Step 1: Research.** Read S3K's `zKeyOffIfActive`/key-on ordering in skdisasm `Sound/Z80 Sound Driver.asm` (grep `zKeyOffIfActive`) to confirm the reference order is off→freq→on vs our off→on after freq — the EG edge only needs OFF before ON; the freq write position is not the fidelity variable (S3K writes freq between; we write freq before both). Note for the record; no design change.
- [x] **Step 2: Add the off-then-on to the chokepoint.** In `Fm_NoteOnFreq.do_keyon` (sound_fm.asm:852), before the key-on write:

```asm
.do_keyon:
        ; --- EG RETRIGGER (spec B): the $28 key-on is edge-triggered; keying an
        ; already-keyed channel is a chip NO-OP. Key OFF first so EVERY producer
        ; funneling through this chokepoint (bare note, NOTE_DUR, NOTE_RAW,
        ; PITCHENV re-key) gets a true 0->1 edge. Held/tie notes (bit-7) never
        ; reach here (Seq_Op_NoteDur returns before the hook). ---
        bit     SCF_KEYED_B, (ix+sc_flags)
        call    nz, Fm_NoteOff           ; keyed -> key OFF first (fresh EG edge)
        ; --- KEY ON: $28 = $F0 | chsel, ALWAYS via part I ---
        call    Fm_ChSel                 ; a = chsel = (part<<2)|ch
        ...unchanged...
```

  Note `Fm_NoteOff` clobbers af,bc,de and preserves hl,ix — de (the fnum word) is already consumed by this point (freq was written above); verify nothing after `.do_keyon` still needs de.
- [x] **Step 3: Delete the now-redundant duplicates.** (a) `Seq_RekeySingle`: remove the whole `if SND_REKEY_OFF_THEN_ON` block (:439-443) and the `.rekey_on` label if now unreferenced — the chokepoint covers it; update the routine's RE-KEY comment. (b) `Seq_Op_NoteRaw`: remove the `push de / call Fm_NoteOff / pop de` (:1166-1168) — `Fm_NoteOnFreq` now keys off itself; update the comment. (c) Delete `SND_REKEY_OFF_THEN_ON` from sound_constants.asm — one behavior, no dormant lever.
- [x] **Step 4: Build + measure.** Green build (net bytes ≈ +2-4 spent). Capture HCZ2 60 s → run `melody_regs.py`: **key-off count ≈ note count per melody channel** (baseline: 3 vs 67; target: ≈67 vs 67, ref parity). Run `melody_cmp.py` rendered: inter-note digital-silence fraction returns toward ref's ~25%; bed RMS delta vs ref shrinks from +2.1 dB. Regression: MT capture — `melody_regs` on MT should be UNCHANGED vs baseline (NOTE_RAW already keyed off before; the chokepoint's `bit` test replaces the explicit pair 1:1). SFX cycle B still clean (SFX steal/restore re-key path funnels through the same chokepoint — listen for double-attack artifacts; there must be none for a not-currently-keyed channel because the `call nz` skips).
- [x] **Step 5: Commit.** `feat(sound): key-off-before-key-on at the FM chokepoint — every note retriggers the EG (spec B)`.

### Task 6: C.a + C.b — Per-note modulation re-arm + contour verification

**Files:**
- Modify: `engine/sound/sound_sequencer.asm` (`Seq_Op_ModSet` :987-1015, `Mod_ReArm` :585-604)

- [x] **Step 1: Research.** Re-read skdisasm `zPrepareModulation` (:1240-1259) — the reference behavior being mirrored: per note, wait/speed/delta re-copied from source, steps = raw>>1, accum = 0, and the whole re-arm SKIPPED for no-attack notes (our parity: `Mod_ReArm` is only reached from `Fm_NoteOnFreq`, which tie notes never enter).
- [x] **Step 2: Latch the raw values in `Seq_Op_ModSet`.** After the existing `ld (ix+sc_mod_step_raw), e`:

```asm
        ld      (ix+sc_mod_wait_raw), b   ; per-note reload source (S3K ldi #1)
        ld      (ix+sc_mod_delta_raw), d  ; per-note reload source incl. SIGN (S3K ldi #3)
```

- [x] **Step 3: Reload both in `Mod_ReArm`.** After the speed reload (:597-598):

```asm
        ld      a, (ix+sc_mod_wait_raw)  ; delay honored on EVERY note (was: first note ever)
        ld      (ix+sc_mod_wait), a
        ld      a, (ix+sc_mod_delta_raw) ; original SIGN each note (flip-parity no longer leaks)
        ld      (ix+sc_mod_delta), a
```

  Update `Mod_ReArm`'s header comment (also fix its stale "SFX-only" line — flagged in the doc-drift list) and `Seq_Op_ModSet`'s.
- [x] **Step 4: Edge case — `sc_mod_wait` semantics.** `Mod_Advance` does `dec (wait)` and holds at 1 once elapsed; a modset wait operand of 0 would wrap. Check what the transcoder emits for smpsModSet wait=0 (S3K treats the stored wait the same `dec`-first way — confirm by reading `zDoModulation`:1285). If S3K's own `dec`-first behavior with wait=0 gives 255 delay frames, ours matching it IS fidelity; do nothing beyond a comment. Record the finding.
- [x] **Step 5: Build + verify (this IS C.b).** Green build. Capture HCZ2 → `gate_vib.py`/`vib_series.py` note-matched vs `s3k_hcz2_ref.vgm`:
  - flat (unmodulated) frames per melody note = ref's 13-14; short notes never vibrate
  - per-note contour = base → up → (back), phase-locked at every note start (no inverted starts)
  - depth in cents ≈ ref on the MATCHING-encoding channels (FM3 96.7 → ≈47.6; full match on both encoding classes lands after Task 7)
  If depth or contour still deviates beyond the encoding-explained factor: STOP — re-derive from `zDoModulation` before inventing mechanism (per the planning finding).
- [x] **Step 6: Regression + commit.** MT A/B unchanged (MT has no MEV_MODSET — one grep of its packed data to confirm, then the capture check). Commit: `feat(sound): per-note vibrato re-arm — wait + delta sign reload every note-on (spec C.a)`.

### Task 7: C.c — Pitch-table renormalization to the canonical S3K band

**Files:**
- Modify: `tools/gen_sound_tables.py` (`fnum_block()` :65-77)
- Test: `tools/test_gen_sound_tables.py`
- Regenerate: `engine/sound/sound_tables_z80.asm`

- [x] **Step 1: Research.** Read S3K's FM note table (skdisasm `Sound/Z80 Sound Driver.asm`, grep `zFrequencies`) and confirm the per-block band (documented 644-1214 per octave entry; our engine band [644,1288) covers it with the same halving relation). Confirm the two engine constants: `FNUM_LO=$0284`/`FNUM_HI=$0508` (sound_constants.asm:663-669). Check how `sound_tables_z80.asm` regeneration is invoked (build.sh generator step or manual — grep build.sh for gen_sound_tables).
- [x] **Step 2: Write the failing test** in `tools/test_gen_sound_tables.py`:

```python
def test_fm_pitch_table_canonical_band():
    """Every entry normalizes fnum into the canonical S3K band [644, 1288)
    (== engine FNUM_LO/FNUM_HI), except block-7 top notes and block-0 floor
    notes, which may exceed/undershoot (band is unreachable by halving)."""
    for i, (word, fnum, block) in enumerate(gen_sound_tables.fm_pitch_table()):
        if block == 7 or (block == 0 and fnum < 644):
            continue
        assert 644 <= fnum < 1288, f"idx {i}: fnum {fnum} block {block} outside canonical band"

def test_fm_pitch_table_frequency_identity():
    """Decoded frequency of every entry stays within 2 cents of equal temperament
    (the canonical band halves fnum resolution vs the old <0x800 normalization;
    S3K ships the same resolution)."""
    for i, (word, fnum, block) in enumerate(gen_sound_tables.fm_pitch_table()):
        ideal = gen_sound_tables._pitch_freq(i)
        decoded = fnum * (2 ** block) * gen_sound_tables.FM_SAMPLE_RATE / 2 ** 21
        cents = 1200 * math.log2(decoded / ideal)
        assert abs(cents) <= 2.0, f"idx {i}: {cents:+.2f} cents"
```

- [x] **Step 3: Run to verify the band test fails** (`python3 -m pytest tools/test_gen_sound_tables.py -q` — the old normalization puts low-block entries in [1024,2048)).
- [x] **Step 4: Implement** in `fnum_block()`:

```python
def fnum_block(semitone: int) -> tuple[int, int]:
    """Return (fnum 11-bit, block 3-bit) for a pitch index.

    Normalize into the CANONICAL S3K per-block band [644, 1288) — the engine's
    FNUM_LO/FNUM_HI octave-correction band — so fnum-denominated deltas
    (modulation, detune, portamento) are worth the same cents at every note.
    Block saturates at 7 (top notes ride above the band, as in S3K).
    """
    freq = _pitch_freq(semitone)
    fnum = freq * 2 ** 21 / FM_SAMPLE_RATE
    block = 0
    while fnum >= 0x508 and block < 7:      # 0x508 = 1288 = engine FNUM_HI
        fnum /= 2
        block += 1
    return _round_half_up(fnum), block
```

- [x] **Step 5: Tests pass**, then regenerate `sound_tables_z80.asm` the same way the build does; diff the generated file (expect every FM entry's block to rise by ~1 and fnum to halve, PSG table untouched, `MovingTrucks_PitchTable` untouched — it is NOT emitted by this generator; verify by diff scope).
- [x] **Step 6: Verify on oracle.** Build; HCZ2: (a) `vib_series.py` — pitch identity: note-matched melody cents vs ref within the known ±2-3 cent residue (a wrong table shifts EVERYTHING — this gate catches it immediately); (b) depth in cents now matches ref on BOTH encoding classes: bass vibrato ≈72.5c (was 36.3), FM3 echo detune chorus width ≈10.8c (was 5.4). (c) MT A/B — MT is NOTE_RAW (bypasses the table entirely): captures byte-comparable on $A4/$A0 streams vs baseline. (d) SFX cycle B — SFX use the same table via `Fm_NoteOn`; spot-check ring/jump SFX against pre-change captures by ear + spectral.
- [x] **Step 7: Commit** (generator + test + regenerated table): `feat(sound): renormalize FmPitchTableZ to the canonical S3K fnum band — full-depth modulation/detune on every note (spec C.c)`.

### Task 8: D.1 — Envelope write-on-change (cheap tick, part 1)

**Files:**
- Modify: `engine/sound/sound_sequencer.asm` (`FmEnvUpdate` :527-567, `PsgEnvUpdate` :468-512)

- [x] **Step 1: Research + measure first.** Get a tick-cost baseline: oracle profiler (`emulator_get_profiler`/`emulator_get_profiler_frames`) or the Timer-B gap histogram from `dac_stall.py` on the Task-5 capture — record median/worst tick under HCZ2. (The findings' numbers: ~16k median / ~57k worst; ~1k cyc/channel from unconditional TL rewrites.)
- [x] **Step 2: FM gate.** In `FmEnvUpdate` — emit only when `sc_env_out` actually changes:

```asm
        ; --- plain value: store as the carrier-TL atten delta, advance the cursor ---
        cp      (ix+sc_env_out)
        jr      z, .advance_only         ; unchanged output -> no TL rewrite this frame
        ld      (ix+sc_env_out), a
        inc     (ix+sc_env_cur)
        jr      .emit
.advance_only:
        inc     (ix+sc_env_cur)
        ret
...
.sustain:
        ret                              ; held atten is already on the chip (TL latches)
...
.rest:
        ld      a, SND_FM_TL_MAX
        cp      (ix+sc_env_out)
        ret     z                        ; already TL-silenced -> nothing
        ld      (ix+sc_env_out), a
        jr      .emit
```

  Safety argument to verify in-code before committing: (1) volume changes outside the env (`Seq_Op_Vol` hook) emit directly; (2) master-fade re-assert is ModUpdate's own `SND_FADE_DIRTY` block, independent of this path; (3) key-on resets `sc_env_cur`/`sc_env_out` to 0 (`Fm_NoteOnFreq`:825-826) so a fresh note's first differing env byte emits. If any of the three doesn't hold as described, stop and reconcile.
- [x] **Step 3: PSG mirror.** Same three-site gate in `PsgEnvUpdate` (plain value compare vs `sc_psgenv_out`, `.sustain` → `ret`; PSG `.rest` already ends in a single `Psg_NoteOff` + KEYED-gate hold — no per-frame re-emit exists to gate; leave it).
- [x] **Step 4: Verify.** Build; HCZ2 rendered A/B vs the Task-7 capture: envelope contours identical (per-hit decay curves on the PSG hi-hat, FM env channels) — write-on-change must be inaudible. Re-measure tick cost (same method as Step 1): expect several k cycles off the median under HCZ2. `dac_stall.py`: drum-hold % already improves. MT unchanged (no envelopes).
- [x] **Step 5: Commit.** `perf(sound): envelope TL/attenuation write-on-change — sustained envelopes stop rewriting the chip every frame (spec D.1)`. *(Cached env-body pointer and dispatch micro-opts from the spec are YAGNI-deferred unless Task 9's criteria miss — the gate delivers the dominant saving.)*

### Task 9: D.2 + D.3 — Timer-B-paced ring drain at sequencer seams

> **OUTCOME 2026-07-02 (measurement-driven):** D.2 implemented faithfully (`8a43fd3` +
> Timer-A-gate amendment `1e1f2cc`), measured NET-NEGATIVE in two rounds (holds
> 24.1%→48.9%/51.1%, tempo −20% in round 1), root-caused as architecturally unsound
> (1:1 repayment stretches ticks past the Timer-A period; ring lead absorbs DMA stalls,
> not tick holds), and REVERTED (`d6c11dd`+). Current state = T8's, the measured best:
> holds 24.1% vs ref's own 21.4%. D.3 measured: both drivers digitally silent between
> hits → hit-scoped toggling REJECTED. Full record: `phase_harness/t9_verification.md`.
> Follow-up lever (DEFERRED_WORK at T12): shorten the WORST ticks, not in-tick draining.

**Files:**
- Modify: `sound_constants.asm` (Timer-B constants near the Timer-A block :168-182)
- Modify: `engine/sound/z80_sound_driver.asm` (`Snd_TimerA_Rearm` + tick entry; new `SndDrv_DrainBurst`)
- Modify: `engine/sound/sound_sequencer.asm` (seam polls in `.chan_loop`/`.tick_loop`), `engine/sound/sound_sfx.asm` (slot-seam poll)

- [x] **Step 1: Research.** (a) plutiedev.com YM2612 timers page + Kabuto notes: Timer B unit = 16× Timer A's base unit; reg $26 = reload N_B, period ∝ (256−N_B); $27 bits: 0=load A, 1=load B, 2=enable A, 3=enable B, 4=reset A, 5=reset B, 6-7=ch3 mode; status bit 0 = A overflow, bit 1 = B overflow. Verify against `Snd_TimerA_ProgramFixed` (z80_sound_driver.asm:961-975, writes $27=$05) and `Snd_TimerA_Rearm` (read it — note its exact $27 value and $2A re-park pattern; every $27 write in this task must preserve the A bits it sets). (b) Reference sweep for the interleave idea: S.C.E./S3K don't interleave (their tick is short — that's Task 8's lesson); Ristar's dual-PCM mixer and GEMS-era drivers pace DAC in software loops — skim `aeon/docs/research/ristar-techniques.md` §sound for prior notes; check SpritesMind for "timer B DAC" prior art. Record findings in the task log; the design below stands unless something contradicts it.
- [x] **Step 2: Constants.** In sound_constants.asm beside the Timer-A block:

```asm
; --- Timer B: the intra-tick elapsed-time marker for the DAC drain bursts (spec D.2).
; Unit = 16x the Timer-A base unit; period = (256 - SND_TIMERB_N) units (~150.2 us/unit).
; Target ~1.35 ms: long enough that a burst fully covers a typical seam gap, short
; enough that >=2 missed periods between seams is rare (seams: every channel + every
; event-tick + every SFX slot).
SND_TIMERB_N            = 247                     ; (256-247)*150.2us = ~1.35 ms
SND_TIMERB_OVF_MASK     = $02                     ; YM status bit 1 = Timer B overflow
SND_REG_TIMER_B         = $26
SND_REG_TIMER_CTRL      = $27                     ; (if a $27 reg constant exists, reuse it)
SND_YM27_TIMERS         = $0F                     ; load A|load B|enable A|enable B, ch3 normal
SND_YM27_RESET_B        = $20                     ; write-only: clear the B overflow flag
; samples owed per Timer-B period at the DAC loop's ~54.5 us/sample cadence:
SND_DRAIN_BURST         = 25                      ; ~1.35 ms / 54.5 us (calibrated Step 7)
```

  Compute the real numbers with `function`-style build-time math off the existing clock constants where they exist (mirror how `timerAReload` derives — read it); the literals above are the fallback with the derivation in comments.
- [x] **Step 3: Program + reset Timer B with Timer A.** In `Snd_TimerA_ProgramFixed`: also write `$26 = SND_TIMERB_N` and extend the $27 value to load+enable BOTH timers (`$05` → `$0F`). In `Snd_TimerA_Rearm`: extend its $27 reset value to also reset B's flag at tick entry (reset A|reset B|enable both|load both), so every burst measures elapsed-within-this-tick. Grep for ALL other `$27` writers (`StopMusic` wrote `$27`; the MEV_REGWRITE guard) and make each preserve the B bits — centralize the base value as a constant (`SND_YM27_TIMERS = $0F`) used by every site.
- [x] **Step 4: The drain burst routine** (resident, in z80_sound_driver.asm near the tick):

```asm
; ======================================================================
; SndDrv_DrainBurst — called from a sequencer-frame SEAM when Timer B overflowed:
; ~SND_TIMERB_N period elapsed inside this tick with the DAC frozen. Emit
; SND_DRAIN_BURST ring samples to $2A at the true streaming cadence (~195 cyc/
; sample), then re-arm Timer B. RAM-state based (the tick spilled the ring regs).
; Preserves EVERYTHING (af,bc,de,hl,ix) — seams sit inside live loops.
; No ROM/bank access: drain only (the window belongs to the song/SFX bank here).
; ======================================================================
SndDrv_DrainBurst:
        push    af
        ld      a, (SND_DAC_PHASE)
        or      a
        jr      z, .none                 ; DAC idle -> no ring to drain
        push    bc
        push    de
        push    hl
        ; reset Timer B (flag consumed; next overflow times from ~now)
        ld      a, SND_REG_TIMER_CTRL    ; $27
        ld      (SND_Z80_YM_A0), a
        ld      a, SND_YM27_TIMERS|SND_YM27_RESET_B
        ld      (SND_Z80_YM_A1), a
        ; select $2A for the data-port emits
        ld      a, SND_REG_DAC_DATA
        ld      (SND_Z80_YM_A0), a
        ld      a, (SND_RING_RD)
        ld      c, a                     ; c = RD
        ld      a, (SND_RING_WR)
        ld      b, a                     ; b = WR (empty stop bound)
        ld      de, SND_Z80_YM_A1
        ld      h, SND_RING_PAGE
        ld      a, SND_DRAIN_BURST
.burst:
        ld      l, c
        ex      af, af'                  ; save burst counter
        ld      a, c
        cp      b
        jr      z, .empty                ; RD == WR -> ring dry, stop (no wrap garbage)
        ld      a, (hl)                  ; ring[RD]
        ld      (de), a                  ; -> $2A data port
        inc     c
        ; --- pad to the streaming cadence (~195 cyc/iteration incl. loop overhead);
        ; count the cycles of THIS loop body and pad with nops exactly like the
        ; hot loop's balance proof (z80_sound_driver.asm top comment) ---
        rept    30
        nop
        endm
        ex      af, af'
        dec     a
        jr      nz, .burst
        jr      .store
.empty:
        ex      af, af'
.store:
        ld      a, c
        ld      (SND_RING_RD), a
        pop     hl
        pop     de
        pop     bc
.none:
        pop     af
        ret
```

  The `rept 30` pad count is a STARTING estimate — Step 7 calibrates it by measurement (the hot loop's ~195-cycle discipline is the target; document the final count with a cycle-sum comment like the main loop's). Flag preservation matters at the `.tick_loop` seam — hence the outer `push af`.
- [x] **Step 5: Seam polls.** Three sites, each gated to cost ~15 cycles when Timer B hasn't fired:

```asm
        ld      a, (SND_Z80_YM_A0)       ; YM status
        and     SND_TIMERB_OVF_MASK      ; Timer B overflow = drums frozen >= 1 period
        call    nz, SndDrv_DrainBurst    ; drain a paced burst, re-arm, continue
```

  (a) `Sequencer_Frame.chan_loop` — at `.next_chan` (sound_sequencer.asm:110), before `add ix, de`; (b) inside `.tick_loop` right after `call Sequencer_Channel` (:105) — catches multi-event channels + patch loads (a full patch load is a bounded ~30-write burst, so the seam AFTER it suffices; per spec, only add an intra-patch-loop poll if Step 7's histogram still shows >5.6 ms gaps); (c) `Sfx_Frame`'s per-slot loop seam (locate the slot-advance point in sound_sfx.asm; same 3 lines). Byte cost: ~10 B × 3 + routine ~70-90 B — within the recovered budget.
- [x] **Step 6: The idle-tick path.** `SndDrv_IdleTick` runs the same `Sequencer_Frame` while the DAC is idle — the `SND_DAC_PHASE` gate in the burst routine makes the polls harmless there (call + immediate return, ~40 cyc/seam only on the rare idle+TimerB-set frames). Confirm no other Sequencer_Frame callers exist (grep).
- [x] **Step 7: Calibrate + verify (the phase's headline numbers).** Build; capture HCZ2 60+ s:
  - `dac_stall.py`: **drum airtime lost to holds ≤ ~20%** (ref 18.9%; baseline 45-63%); **max gap well under 16.7 ms** — target ≤ ref's 5.6 ms class; no full-frame freezes.
  - `dac_perburst.py`: **tom hit duration within ~10% of ref** (ref 93 ms; baseline 213 ms).
  - Burst cadence correctness: drum PITCH during heavy ticks — render a sustained-drum stretch and compare pitch/spectral centroid during tick-heavy vs quiet frames; a mis-padded burst shows as warble. Adjust the `rept` pad / `SND_DRAIN_BURST` / `SND_TIMERB_N` and re-measure until clean.
  - Ring never dries mid-burst: `dac_stall.py` gap histogram has no `.empty`-shaped cliffs (and optionally assert-log via a debug counter if it does).
  - Regression: MT (FM6=FM stream path — polls fire but `SND_DAC_PHASE`=0 after its `$2B` off), SFX over HCZ2, drumtest C, 3000+ frame soak, boot.
- [x] **Step 8: D.3 — evaluate hit-scoped $2B/FM6 duty, then decide.** Measure inter-hit noise floor on rendered audio: ours (always-armed DAC parked at $80 DC) vs ref (keys FM6 off + toggles $2B per hit, 42-72% duty). Expected outcome per spec: parked-$80 is equally silent → REJECT hit-scoped toggling; write the decision + numbers into the task log and the spec's D.3 (one-line amendment). If measurement shows a real floor difference, design the hit-scoped disable as a follow-up item in DEFERRED_WORK rather than bolting it in here.
- [x] **Step 9: Commit.** `feat(sound): Timer-B-paced DAC ring drain at sequencer seams — drums keep streaming through the tick (spec D.2)` (+ a separate docs commit if D.3 amends the spec).

### Task 10: E — Portamento (execute the turnkey plan)

**Files:** per `docs/superpowers/plans/2026-06-28-portamento-resume.md` (+ `docs/superpowers/plans/porta-b1-WIP.patch`)

- [x] **Step 1:** Execute the 2026-06-28 plan AS WRITTEN, with these phase-context adjustments: (a) budget recovery is DONE (Tasks 2-4) — skip its own step 2 banking work except any residual bytes the assert demands; (b) `git apply` the preserved `porta-b1-WIP.patch` may conflict with this branch's sequencer/struct changes — apply, resolve against the new struct offsets (sc_mod fields moved +0 relative; sc_porta fields per patch), and re-verify by reading, not trusting, the patch; (c) `Porta_Apply` + `Fm_FnumApplyDelta` land RESIDENT next to `Tempo_Ramp`/`Fade_Ramp`; delete `engine/sound_banked_z80.asm` + its `main.asm` include (closes T0.3 — record that in the commit message); (d) B2 (`MEV_PORTA=$F5` + `Seq_Op_Porta` + dispatch slot) and B3 (packer `Porta(Event)` + music-legal set + test + `pytest tools/`) per that plan.
- [x] **Step 2: Verify per that plan's own gate:** 3000+ frame soak with PC never in `$8xxx`/`$Cxxx` (breakpoint/`emulator_registers` sampling), `SND_SEQ_ACTIVE`/`CHCOUNT` nonzero, `$0000` reset-vector trap (`F3 18 FE`) installed during the soak and never fires, rendered glide audio (vgm2wav) shows smooth fnum sweeps — now on the CANONICAL table (Task 7), so glide deltas are uniform cents; note the cents-linearity in the log.
- [x] **Step 3:** Update the 2026-06-28 plan doc's status header (executed, date, branch) + the recovery-doc/ARCH banked-code corrections it mandates. Commit(s) per its steps: `feat(sound): portamento resident + MEV_PORTA — closes T0.3 banked-code hazard (spec E)`.

### Task 11: F — Frame-clock measure + retune

**Files:**
- Modify: `sound_constants.asm` (:168-182 — `SND_FRAME_MILLIHZ`, the pinned `SND_TIMERA_N` guard)

- [ ] **Step 1: Measure the effective rate post-D.** With HCZ2 playing, sample `SND_STAT_TICK` (8-bit, wraps) against emulated frame count via oracle over 3600+ frames (read every ≤128 frames to disambiguate wraps): effective tick Hz = ticks × 59.9227 / frames... use the emulator frame count as the wall clock (NTSC field rate 59.9227 Hz). Record: baseline claim was ~59.06 effective w/ tick overruns; DEFERRED notes N=136 measured ~59.63 idle. Expect D to have pulled the loaded rate up toward the idle rate.
- [ ] **Step 2: Retune.** Compute the N step from the measurement (each Timer-A unit ≈ 1/(1024−N) of the period; from 136, one N step ≈ 0.11%). Change the PIN + `SND_FRAME_MILLIHZ`/comment so `timerAReload` lands on the new N (the pinned-assert at :181 exists precisely to force this deliberate edit — update the pin value and its comment with the measurement date + method). Rebuild, re-measure, iterate until **measured effective rate = 59.92 ± 0.02 Hz under HCZ2 load**.
- [ ] **Step 3: Drift gate.** 15+ s HCZ2 A/B vs ref: cumulative drift < 0.3% (note-onset alignment via `gate_vib.py` timestamps or onset cross-correlation). 
- [ ] **Step 4: MT re-verify.** MT was tuned against the old clock: full MT A/B (rendered energy + spectrum vs `mt_ref.vgm`-derived expectations per `docs/research/reference_captures/README.md`) — tempo now ~1.4% faster ≈ authentic. This is a FEEL change on a verified song: capture before/after renders for the user to hear, and note it in the phase summary.
- [ ] **Step 5: Commit.** `fix(sound): frame clock retuned to measured 59.92 Hz effective (spec F)`.

### Task 12: Phase gate + doc sync + merge

**Files:**
- Modify: `docs/ENGINE_ARCHITECTURE.md` §6, `docs/DEFERRED_WORK.md`, `docs/superpowers/HANDOFF-sound-performance-phase.md` (status header), spec status header
- Merge: `feat/sound-perf-budget` → master

- [ ] **Step 1: Full success-criteria matrix** (spec §H) — re-run EVERY number on fresh captures in one pass and table them: H.1 retrigger counts + bed silence, H.2 drum airtime/max-gap/tom duration + **user by-ear confirmation** (ask explicitly), H.3 vibrato delay/contour/depths both encodings + FM3 ~10.8c, H.4 tempo <0.3%, H.5 porta soak+glides, H.6 build + pytest (803+) + MT A/B + SFX steal/restore + boot.
- [ ] **Step 2: Doc sync (spec §J only).** ENGINE_ARCHITECTURE §6: COPY path gone (one load path), banked-code file deleted + data-only-banking invariant recorded, tick/DAC drain-burst shape, new RAM map pointer, porta shipped (§6.1 deferred list now empty of it). DEFERRED_WORK: close F1 (RAM-map spec rewritten), F5 numbers, the frame-clock item, T0.3; update headroom figures with the final build line; add anything Task 9 D.3 deferred. Handoff doc: status header "EXECUTED <date>, see plan + spec". Spec: status header note for the C.b planning finding (verification-only) + D.3 outcome.
- [ ] **Step 3: Merge.** All gates green → `git checkout master && git merge --ff-only feat/sound-perf-budget` (rebase the branch first if master moved). `git show --stat` review — exact paths only, no stray files (the repo has unrelated editor-data/sprites working changes that must NOT ride along). Post-merge: rebuild master, boot test, one HCZ2 listen.
- [ ] **Step 4: Phase summary to the user.** Lead with the H-matrix table + the MT tempo feel change + final Z80 headroom number.

---

## Self-review notes

- **Spec coverage:** A.1→T2, A.2→T3, A.3→T4, B→T5, C.a/C.b→T6, C.c→T7, D.1→T8, D.2/D.3→T9, E→T10, F→T11, §G harness→T1, §H+§J→T12. The spec's "cached env-body pointer + fast inactive-skip" (D.1) is deliberately deferred inside T8/T9 behind measurement (YAGNI) — revisit only if T9 Step 7 misses criteria.
- **Deviations from spec letter, by design (surface to the user at handoff):** C.b downgraded from mechanism-change to verification (planning finding #2); intra-patch-loop poll made conditional on measurement (T9 Step 5b).
- **Type consistency:** new fields `sc_mod_wait_raw`/`sc_mod_delta_raw` defined T4, consumed T6; `SND_TIMERB_N`/`SND_TIMERB_OVF_MASK`/`SND_DRAIN_BURST`/`SND_YM27_TIMERS` defined T9 Step 2, consumed Steps 3-5; `SND_YM27_RESET_B` must be defined alongside `SND_YM27_TIMERS` (add in Step 2).
- **Known execution risks:** T4 is the highest-risk task (everything moves) — it is deliberately isolated with its own soak before anything stacks; T9's pad calibration is measurement-driven by construction; T10's WIP patch may bit-rot against this branch — the instruction says read-and-resolve, not trust.
