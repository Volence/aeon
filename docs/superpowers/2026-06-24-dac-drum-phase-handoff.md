# Handoff: DAC Drum / DAC-Format-Revision Phase

**Date:** 2026-06-24
**For:** the agent picking up the DAC drum work.
**Status of the world:** master (`34fc2b9`) is clean + green. A prior exploratory branch
`feat/sound-stream-drums` is kept **as reference only — do NOT continue it**; start clean from master.

---

## 1. What you're building (one line)

A **clean, from-scratch DAC drum playback path** for the custom Z80 sound driver: songs trigger
PCM drum samples via the `$E2` (MEV_DAC) opcode; each one-shot sample plays once and cleanly
stops; FM6 is shared with the DAC. This is the engine-side of the **"DAC-format revision"**
(items E2/E3 in `DEFERRED_WORK.md` "From Sound Driver Work").

**Do it as a proper phase:** brainstorm → spec → plan → subagent-driven implementation. Do NOT
patch the old branch — it accumulated experiment cruft and three layered bugs (see §4).

---

## 2. Context you need first

- **The sound engine CORE is done and merged to master** (music FM+PSG sequencer, DMA-survival
  DAC, Phase-3a FM depth, SFX engine + game integration, Moving Trucks faithful). This phase is
  one slice of the remaining best-in-class backlog. See memory `project_sound_remaining.md`.
- **This phase sits under a larger committed effort, the "Music Expression Engine"**
  (`docs/superpowers/specs/2026-06-23-music-expression-engine-design.md`). Read memory
  `project_music_expression_engine.md` — it has the FULL history of this DAC investigation,
  the banking research, and every decision below with evidence.
- **Build flag (critical):** sound is EXCLUDED unless you build with
  `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`. A plain `./build.sh` proves nothing about sound.
- **The Z80 driver** is assembled inline as a `phase 0` blob in `engine/z80_sound_driver.asm`
  (+ `engine/sound_sequencer.asm`, `sound_fm.asm`, `sound_psg.asm`, `sound_constants.asm`).
  Z80 code headroom was recovered to ~1016 bytes in Task 0 (was 2) — there's room now.

---

## 3. DECISIONS already made — do NOT re-litigate (validated with research + the user)

1. **Banking = SHARED DAC bank (Flamedriver model).** DAC samples live in dedicated ROM bank(s)
   referenced by all songs; the song streams from its own bank; the Z80 `$8000` window **swaps
   per frame** between the song bank and the sample bank. Validated against Flamedriver (S3K) and
   Zyrinx (Batman & Robin) by reading their actual disassemblies. The swap is **cheap** —
   measured ~148 Z80 cycles/switch, ~0.5%/frame — so it is NOT a perf concern. The user chose
   this over per-song co-location because it's production-proven and ROM-efficient (S3K sizing
   showed co-location costs ~4×/+201 KB of duplicated kit). A shared bank == a shared kit, which
   also gives the cohesive-soundtrack feel the user wants. (The reference branch's *co-located
   STREAM* mode is the abandoned approach — ignore it.)
2. **Sample format = 4-bit DPCM** (JMan2050 delta, 16-entry decode table, 2 nibbles/byte,
   decoded inline). Borrowed from Flamedriver — halves ROM AND halves window-stream bandwidth.
   Resolves the flagged "DAC format pigeonhole." Borrow its compact 5-byte descriptor
   (`db rate; dc.w length; dc.w in-bank-ptr`) + per-sample rate byte (as a DATA feature; keep our
   cycle-balanced loop as the pacing authority, NOT Flamedriver's SMC djnz) + a build-time
   `align $8000` + fatal-on-bank-overflow assert.
3. **FM6 = adaptive time-share** is the goal (FM6 plays music between drum hits, toggles `$2B`
   bit7 to DAC for a hit, Echo-style: key-off + DC-center `$2A=$80` + re-key on return). The
   **proven-safe fallback** (if the toggle fights clicks) is Zyrinx's "dedicate FM6 to DAC for
   the whole sample." Also adopt Zyrinx's `$B6=$C0` (force DAC stereo) at sample start to avoid a
   stale-pan pop. **A reasonable phase-1 scope: dedicate-FM6-while-active first (simpler, proven),
   then add the adaptive toggle.**
4. **One-shot is the only mode for now.** No content loops. Do NOT build a loop branch that
   depends on a runtime loop field yet (the old one did, and it aliased a dead byte — see §4).

---

## 4. What's PROVEN, and the LANDMINES (from the prior debugging — don't repeat these)

**PROVEN GOOD (the mechanism works):**
- DAC sample playback via the `$E2` opcode **works bit-perfect** on the COPY path — verified
  r=1.000 cross-correlation of the captured `$2A` stream vs the actual sample waveform. So
  `$E2 → Seq_Op_Dac → Seq_HookDac → Snd_DacLookup → Snd_StartSample → DAC FILL` is fundamentally
  sound. The sequencer side parses correctly (`sc_note` = sample id, DAC channel route/flags set).
- The `$E2`-in-song trigger was historically **never exercised** before this (1C/1D used the
  *mailbox* `SND_REQ_SAMPLE`, not `$E2`), which is why latent bugs lived there. It works now.

**LANDMINES (bugs found; design the clean version to avoid them):**
- **`SND_LOOP_OFS` aliases the dead `SND_PLAY_MODE` byte.** In `sound_constants.asm`,
  `SND_LOOP_OFS = SND_STATE_BASE+$0E` is 2 bytes ($16FE/$16FF) and `SND_PLAY_MODE =
  SND_STATE_BASE+$0F` ($16FF) overlap. `SND_PLAY_MODE` is dead (never read), but the overlap
  means `SND_LOOP_OFS` reads garbage in its high byte (observed `$C7A6`). The old exhaust logic
  branched on `SND_LOOP_OFS` → took the re-loop path → **looped the sample forever**. **Fix in
  the clean design:** don't reuse these overlapping fields; give any loop/state field its own
  non-aliased byte (there's RAM headroom), and for now don't have a loop branch at all.
- **The old `.exhaustLoop` hard-coded the blip's pointer** (`SND_BLIP_PTR/LEN`) on re-loop, so it
  restarted the WRONG sample. Gone in the clean design (one-shot only).
- **Length runaway:** the FILL exhaust must be **underflow-safe**. Every sample is < 32 KB
  (< `$8000`), so a valid in-progress `len` is in `[2,$7FFE]` (bit15 clear); treat `len==0` OR
  bit15-set as exhausted so the read pointer can never run off the end into Z80 RAM (that was the
  garbage). The fix (commit `c96f027`) worked — reuse the idea.
- **The trigger/stop state machine is the hard part.** The prior attempts cycled through
  garbage → loops-forever → silent. The clean design needs a **well-specified state machine**:
  `idle($2A=$80) → [$E2] → Snd_StartSample (set bank/ptr/len, DAC_ACTIVE=1) → FILL/play →
  exhaust (len done) → drain ring tail → idle`, with **re-trigger** working (a later `$E2`
  cleanly restarts) and no stranded `DAC_ACTIVE=1`. Note: the streaming loop (`SndDrv_Sample`) is
  cycle-balanced and does NOT re-check `DAC_ACTIVE` — the stop is driven off the FILL exhaust
  path; only `SndDrv_Idle` re-checks `DAC_ACTIVE` to re-enter streaming. Spec this carefully.
- **COPY vs STREAM song modes + bank window:** read `Snd_LoadSong` (PATH A = COPY/FM6=DAC,
  song→RAM; PATH B = STREAM/FM6=FM). The shared-bank model means the window must hold the song
  bank for the sequencer stream read AND the sample bank for the DAC FILL — at different times
  per frame. Task 0 already added `Run_SeqFrame_Banked` (swaps to the engine-table bank around
  `Sequencer_Frame`); your DAC bank swap must compose with that. Map all the bank swaps in the
  spec BEFORE coding — multi-bank contention is where the bugs live.

---

## 5. HOW TO VERIFY — the project's hard-won rule (do not skip)

**Verify by RENDERED AUDIO, cross-correlated against the known sample waveform. NOT "is the DAC
non-silent."** "Non-silent" is a trap: an enabled DAC streaming a *bad pointer* produces
structured ROM/RAM garbage that looks like audio (high std, audible RMS) but is NOT the sample.
This nearly produced two false "it works" reports.

Method (the emulator is the **`oracle`** MCP server; it runs ~3× real-time):
1. Build, `emulator_reload_rom` the new `s4.bin`, trigger the drum test (a debug button or boot song).
2. `emulator_vgm_start` → wait (a `sleep` in a background Bash) → `emulator_vgm_stop`.
3. Extract the YM `$2A` (DAC data) byte stream from the VGM and **cross-correlate vs the sample's
   raw bytes** (`numpy.corrcoef`). **r ≥ ~0.9 over a contiguous sample-length window = the sample
   is really playing.** Also check the silence/burst structure matches the intended cadence (a
   one-shot should be mostly `$80` silence with discrete bursts).
4. Use `emulator_z80_read` to inspect live state when debugging: `SND_ROM_PTR`/`SND_ROM_LEN`
   ($16F8/$16FA — a valid sample ptr is in `$8000-$FFFF`, in-RAM = runaway), `SND_CUR_BANK`
   ($16FD), `SND_STAT_DAC_ACTIVE` ($1F14 — the REAL flag; `SND_PLAY_ACTIVE`@$16F0 is a dead
   legacy flag, don't trust it), `SND_SEQ_BADOP` ($1805 — nonzero = a sequencer derail).

A known-good test sample already exists on master: `data/sound/temp_blip.bin` (2880 B, the 1B
bring-up blip; descriptor id 1). Use it as the cross-correlation reference for the first proof,
then a real/temp drum. (The reference branch also has `data/sound/test/drum_kick_temp.bin`, an
8948 Hz temp kick — but author test samples at the driver's actual DAC rate.)

A ready-to-drop verification script (cross-correlate `$2A` vs a sample `.bin`) — save as
`tools/dac_verify.py`:
```python
import sys, struct, wave, numpy as np
def dac_stream(vgm):
    d=open(vgm,'rb').read(); voff=struct.unpack('<I',d[0x34:0x38])[0]; i=(0x34+voff if voff else 0x40); n=len(d); out=[]
    while i<n:
        c=d[i]
        if c==0x66: break
        elif c==0x52:
            if d[i+1]==0x2A: out.append(d[i+2])
            i+=3
        elif c==0x50: i+=2
        elif c==0x53: i+=3
        elif c==0x61: i+=3
        elif c in (0x62,0x63): i+=1
        elif 0x70<=c<=0x8f: i+=1
        elif c==0x67: i+=7+struct.unpack('<I',d[i+3:i+7])[0]
        elif c==0x4f: i+=2
        elif c==0xe0: i+=5
        else: i+=1
    return np.array(out,dtype=float)
dac=dac_stream(sys.argv[1])                      # the captured .vgm
smp=np.frombuffer(open(sys.argv[2],'rb').read(),dtype=np.uint8).astype(float)  # the sample .bin
L=len(smp); s=smp-smp.mean(); best=-1
for p in range(0,max(1,len(dac)-L),7):
    w=dac[p:p+L]; w=w-w.mean(); dn=np.sqrt((w*w).sum()*(s*s).sum())
    if dn>0: best=max(best,(w*s).sum()/dn)
print(f"$2A samples={len(dac)} silence($80)={np.mean(dac==128)*100:.0f}% best_xcorr_vs_sample={best:.3f}")
print("PLAYS" if best>0.9 else "NOT the sample (garbage/silent)")
```

---

## 6. Reference material

- **Memory (read first):** `project_music_expression_engine.md` (full DAC investigation +
  decisions), `project_sound_remaining.md` (backlog + DAC-format E2/E3), `feedback_verify_real_
  output_not_proxy.md`, `feedback_verify_sound_build_flag.md`, `feedback_best_of_class_north_star.md`.
- **Research outputs (the banking/format validation, with disasm cross-refs):** in memory under
  the Flamedriver/Zyrinx comparison entries; the local disasms are
  `.../The Adventures of Batman and Robin/disasm/sound/zyrinx_driver.asm` + `ZYRINX_FORMAT.md`,
  `skdisasm/Sound/Z80 Sound Driver.asm` (S3K/Flamedriver), and `flamewing/flamedriver` online.
- **Reference branch (DON'T continue it; read it):** `feat/sound-stream-drums` — `git show` its
  commits for the proven-playback code, the DrumTest harness (`data/sound/song_drumtest.asm`,
  song id 2, C-button trigger via `engine/game_loop.asm`), the temp kick, and the exact bugs.
- **Key driver code:** `engine/z80_sound_driver.asm` — `Snd_StartSample` (~682), `Snd_DacLookup`
  (~633), `DacSampleTable` (~1279), the FILL/exhaust/drain (~390-525), `SndDrv_Idle` (~313),
  `SndDrv_SetBank` (~765), `Snd_LoadSong` PATH A/B (~782-1040). `Seq_Op_Dac`/`Seq_HookDac` in
  `engine/sound_sequencer.asm` (~744, ~1283). DAC sample data: `data/sound/dac_samples.asm`.

---

## 7. Process / setup

- Use the standard flow: **brainstorming → writing-plans → subagent-driven-development**, in a
  **git worktree**. The worktree must be a **SIBLING** of `s4_engine` (e.g.
  `../s4_engine-dacdrum`) — the build references `../skdisasm`, so a nested `.worktrees/` worktree
  breaks it. After creating it, symlink the gitignored native tools from the main checkout:
  `ln -s .../s4_engine/tools/bin tools/bin` and
  `ln -s .../s4_engine/tools/salvador/salvador tools/salvador/salvador`. This machine builds with
  the NATIVE toolchain (`tools/bin`), not win32/Wine.
- The **`oracle` emulator** is the user's live emulator (MCP). Never auto-launch emulators; drive
  the running one via MCP. The DAC sample-rate constant + cycle-balance live in
  `sound_constants.asm` (`SND_LOOP_CYC`/`SND_DAC_RATE_HZ`) — keep them in sync if you touch the loop.
- **Daemon caution:** `tools/ojz_strip_gen.py` and `data/editor/` are auto-commit-daemon-watched;
  don't touch them. The user has unrelated WIP on master (`data/sprites/`, `forest_bg_gen.py`,
  `data/editor*`) — never `git add -A`; stage exact paths only.

---

## 8. Suggested first steps for the new agent

1. Read the memory files in §6 and skim the reference branch commits.
2. Brainstorm the DAC drum design with the user (the decisions in §3 are settled inputs; the open
   design is the trigger/stop state machine + the exact shared-bank swap choreography + DPCM
   descriptor format + the FM6 phase-1 scope).
3. Map ALL the per-frame bank swaps (song bank ↔ sample bank ↔ Task-0 engine-table bank) in the
   spec before writing code — that's where the bugs live.
4. Build the simplest provable slice first: one drum sample, triggered from a song via `$E2`,
   playing once and stopping to `$80` silence, verified by `tools/dac_verify.py` (r ≥ 0.9 +
   correct silence cadence). Then layer DPCM, the shared bank, and adaptive FM6.
