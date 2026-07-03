# Sound Production Suite Implementation Plan (Banking Package 5)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute spec `2026-07-03-sound-production-suite-design.md`: the build-time mastering layer (Tier 0), sidechain pump + autopan (Tier 1), and the budget-gated ghost-voice/ExtCh3 features (Tier 2).

**Architecture:** Tier 0 is Python + authoring docs (zero resident bytes). Tier 1 rides shipped machinery: the pump writes the duck LEVEL at the existing DAC trigger hook (`Seq_HookDac`, `sound_sequencer.asm:2019`) and lets the shipped duck ramp provide the release; autopan is a new shadow-coherent macro tag (`TAG_MAC_PAN = $E4` in the private `$E0-$E3+` tag namespace). Tier 2 (PLAN-LEVEL REFINEMENT of spec items 10+11, flagged): echo bus and detune-unison unify into ONE **ghost-voice engine** — a designated ghost channel replays a source channel's note-ons with authored (delay, vol-drop, detune, pan-mode, patch) — echo = delay>0 preset, unison = delay 0 + detune preset. One mechanism (~100-140 B) instead of two (~130-200 B). ExtCh3 remains its own item, last.

**Sequencing (normative, from the spec):** Tier 0 + Tier 1 execute any time after packages 1-4 merge. **Tier 2 tasks each begin with a measured budget gate** — build, read the `Z80 sound budget` line, STOP the task and record if free bytes < ceiling + 32 B safety floor. Priority: ghost-voice → ExtCh3.

**Tech Stack:** Python 3 (scipy/numpy for DSP; pytest), AS Macro Assembler, `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`, oracle MCP foreground-only, vgm2wav render pipeline.

**Interaction contract (with packages 2 + 4):** the pump and package 2's per-SFX duck share `SND_SFX_DUCK_LEVEL/TARGET`. Rule (resolves spec §6): **LEVEL combines as MAX** — the pump writes `level = max(level, pump_depth)` instantly (fast attack); TARGET stays owned by the SFX-duck logic (deepest-active, per package 2); the shipped ramp walking level→target IS the release. No new state.

---

### Task 1: Tier 0 — drum mastering chain

**Files:**
- Create: `tools/master_dac.py`; Test: `tools/test_master_dac.py`
- Modify: `tools/import_s3k_dac.py` (optional per-sample mastering config hook)
- Modify: `docs/superpowers/specs/2026-06-24-dac-drum-format-revision-design.md` (runbook: mastering step + ladder reference)

- [ ] **Step 1: Failing tests** — deterministic DSP on raw8 arrays:

```python
# tools/test_master_dac.py
import numpy as np
import master_dac as m

def _sine(hz=200, n=4096, sr=18356):
    t = np.arange(n) / sr
    return (np.sin(2*np.pi*hz*t) * 100 + 128).astype(np.uint8)   # raw8 unsigned, $80-centered

def test_compress_reduces_crest_factor():
    x = _sine()
    y = m.compress(x, threshold_db=-12, ratio=4.0, attack_ms=1, release_ms=60)
    assert m.crest_factor(y) < m.crest_factor(x)

def test_gated_reverb_extends_then_hard_cuts():
    x = _sine(n=1000)
    y = m.gated_reverb(x, tail_ms=90, gate_ms=70, wet_db=-9, seed=1234)
    assert len(y) > len(x)
    tail = y[-int(0.005*18356):].astype(int) - 128
    assert np.abs(tail).max() <= 2, "gate must hard-cut to near-silence (Amiga rule)"

def test_eq_peaking_is_deterministic():
    x = _sine()
    assert np.array_equal(m.eq_peaking(x, hz=2000, gain_db=3, q=1.0),
                          m.eq_peaking(x, hz=2000, gain_db=3, q=1.0))
```

- [ ] **Step 2: Implement `master_dac.py`** — pure-function DSP kit on raw8: `eq_peaking`/`eq_shelf` (biquads, scipy.signal), `compress` (envelope follower + gain computer), `saturate` (tanh drive), `gated_reverb` (seeded-noise early-reflection tail convolved/decayed, hard gate), `crest_factor`, and `master(x, chain: list[dict])` applying an ordered config. All functions take/return uint8 raw8 and are seed-deterministic (seeds required in configs — build reproducibility).

- [ ] **Step 3: Pipeline hook** — `import_s3k_dac.py`: per-sample optional `master:` chain in the sample config (dict list, applied after resample, before write). Default absent = byte-identical output (regression: rebuild kit, `git diff` shows no `.pcm` changes).

- [ ] **Step 4: Ladder reference decision (runbook)** — render one drum through the oracle path twice (MD1 ladder model on/off — check oracle's YM core setting; if the core is fixed, document which model it implements). Write the runbook rule: chosen reference target, and the level-staging guidance (quiet tails gain grit on MD1; stage kick fundamentals hot, let snare tails ride the discontinuity). This step is JUDGMENT + documentation — the deliverable is the runbook section, not code.

- [ ] **Step 5: pytest green + commit**

```bash
git add tools/master_dac.py tools/test_master_dac.py tools/import_s3k_dac.py docs/superpowers/specs/2026-06-24-dac-drum-format-revision-design.md
git commit -m "feat(tools): drum mastering chain — EQ/comp/saturate/gated-reverb on raw8, seed-deterministic; ladder reference rule in runbook"
```

### Task 2: Tier 0 — TL-filter-sweep generator + generative variation

**Files:**
- Create: `tools/tl_filter_env.py`, `tools/song_variation.py`; Tests: `tools/test_tl_filter_env.py`, `tools/test_song_variation.py`

- [ ] **Step 1: `tl_filter_env.py`** (failing test first): `filter_env(cutoff_curve, depth_tl) -> list[int]` maps a normalized 0..1 "filter cutoff" envelope to a modulator-TL byte curve (inverted: cutoff 1.0 → TL bias 0 = bright; 0.0 → +depth = dark), emitting either an `FmEnv` table row (for `MEV_FMENV`... NOTE: FMENV drives CARRIER volume — verify; if carrier-only, emit an `OpBias`/`RegDelta` macro body targeting MODULATOR TL via `TAG_MAC_REG` writes instead — the generator's job is producing the packer-ingestible body, whichever surface reaches modulators; resolve by reading `sound_constants.asm` FMENV route notes and pick the modulator-reaching surface). Test: monotonic curve in → monotonic TL bytes out, clamped 0..$7F, deterministic.

- [ ] **Step 2: `song_variation.py`**: seeded transforms over the packer's event lists — `humanize_vol(events, amount, seed)`, `ghost_notes(events, prob, vol_drop, seed)`, `alternate_sample_offsets(dac_events, variants)` (requires kit variants baked by Task 1's chain — bake 2-3 start-offset trims per drum), `flam(dac_events, pairs)` → emits references to pre-baked composite samples (NEVER runtime mixing). Tests: same seed = same output; no seed param = error (reproducibility contract).

- [ ] **Step 3: Authoring cookbook** — new section in the music-expression spec (or `docs/superpowers/sound-authoring-cookbook.md` if cleaner): TL-sweep patch vocabulary (wah/acid/filter-pad recipes), **PSG periodic-noise sub-bass** pattern (tone-2-clocked periodic mode, 4 octaves down — cite `MEV_PSGNOISE` ctrl byte values), **Follin echo rules** (−6 dB, opposite pan, duller patch, same-channel ghost fallback), SSG-EG timbre presets (post-package-4). Each recipe = concrete packer-event snippets, buildable.

- [ ] **Step 4: pytest + commit**

```bash
git add tools/tl_filter_env.py tools/song_variation.py tools/test_tl_filter_env.py tools/test_song_variation.py docs/
git commit -m "feat(tools): TL filter-sweep generator + seeded generative variation + authoring cookbook (Tier 0)"
```

### Task 3: Tier 1 — kick-sidechain pump (~30-50 B)

**Files:**
- Modify: `engine/sound/sound_sequencer.asm` (`Seq_HookDac` :2019 region; `Seq_Op_Ext` — extend package 1's `$FA` dispatch), `sound_constants.asm` (2 RAM bytes), `tools/song_packer.py` (+`PumpSet` event), tests

- [ ] **Step 1: Score surface** — `MEV_EXT` sub-op 1 = **PUMPSET** `+ id + depth`: sets `SND_PUMP_SAMPLE` (the trigger sample id; 0 = pump off) and `SND_PUMP_DEPTH` (TL units). Two RAM bytes chained in the game-feel slack block (extend package 1's `SND_GAMEFEEL_*` chain + seam assert). Zeroed at song load (grep the `.chan_init`/load-time state wipe — add both bytes; a song must opt in per-load). Packer `PumpSet(id, depth)` event + validity (music-legal, any route; depth 0..$7F) + test asserting `FA 01 id depth` bytes.

- [ ] **Step 2: Trigger hook** — in `Seq_HookDac` (sample id is in `sc_note`), after the existing trigger:

```asm
        ; Tier-1 sidechain pump: designated sample id slams the duck LEVEL
        ; (instant attack); the shipped Sfx_DuckRamp walking level->target is
        ; the release. MAX-combine with SFX ducking (level only rises here).
        ld      a, (SND_PUMP_SAMPLE)
        or      a
        jr      z, .no_pump
        cp      (ix+sc_note)
        jr      nz, .no_pump
        ld      a, (SND_SFX_DUCK_LEVEL)
        ld      b, a
        ld      a, (SND_PUMP_DEPTH)
        cp      b
        jr      c, .no_pump              ; current level already deeper -> leave it
        ld      (SND_SFX_DUCK_LEVEL), a  ; instant attack
        ; re-assert held music notes NOW (the ramp's write-on-change path):
        ; reuse the exact re-assert Sfx_DuckRamp performs on a level change —
        ; factor its re-assert loop into a callable if it isn't one (verify at
        ; sound_sfx.asm:345-373) and call it here.
.no_pump:
```

- [ ] **Step 3: Gates** — build (≤ 50 B); byte-identity: MT/HCZ2 renders unchanged (no PUMPSET authored). Then a scratch HCZ2 variant with `PumpSet(kick_id, $10)`: **rendered** capture shows RMS dips on kick onsets with ~ramp-step release slope; duck-target writes appear ONLY at triggers. **Controller session** for the renders.

- [ ] **Step 4: Commit**

```bash
git add engine/sound/sound_sequencer.asm sound_constants.asm tools/song_packer.py tools/test_song_packer.py
git commit -m "feat(sound): kick-sidechain pump — MEV_EXT PUMPSET + instant-attack duck-level slam, shipped ramp as release (Tier 1)"
```

### Task 4: Tier 1 — autopan macro tag (~20-40 B)

**Files:**
- Modify: `sound_constants.asm` (TAG_MAC_PAN = $E4 + collision asserts), `engine/sound/sound_sequencer.asm` (`MacroTick` tag dispatch), `tools/song_packer.py` (`MacPan` macro event + validity), tests

- [ ] **Step 1:** New macro tag (the TAG namespace is private to MacroTick; $E4 is free — extend the namespace comment at `sound_constants.asm:487-494`): `TAG_MAC_PAN + mode` where mode = `$80` L / `$40` R / `$C0` LR (the raw $B4 bits 7-6). Handler in `MacroTick`'s dispatch (mirror `TAG_MAC_REG`'s shape): write mode into `(ix+sc_pan)` bits 7-6 (PRESERVE AMS/FMS bits 5-0) and zero `(ix+sc_last_pan)` — ModUpdate's write-on-change re-emits `$B4` shadow-coherently next frame. Packer `MacPan(mode)` validating mode ∈ {L,R,LR} + tests (reject 0 = both off — that's a mute, use Vol).

- [ ] **Step 2:** Gates: build (≤ 40 B); pytest; scratch song with an 8-frame L/R autopan macro → **rendered stereo split** shows alternation; existing songs byte-identical. Commit:

```bash
git add sound_constants.asm engine/sound/sound_sequencer.asm tools/song_packer.py tools/test_song_packer.py
git commit -m "feat(sound): TAG_MAC_PAN — shadow-coherent macro autopan (Tier 1); AMS/FMS preserved"
```

### Task 5: Tier 2 (BUDGET-GATED) — ghost-voice engine (echo bus + unison unified)

**Files:**
- Modify: `engine/sound/sound_sequencer.asm`, `sound_constants.asm` (config + FIFO in the `$1ED2` block), `tools/song_packer.py` (+`GhostSet`), tests

- [ ] **Step 0: BUDGET GATE** — build; if `Z80 sound budget` free < **172 B** (140 ceiling + 32 floor), STOP: record the number in the queue doc + DEFERRED_WORK "Tier 2 blocked at N bytes" and skip to Task 6's gate (which will also fail — record and end the plan at Task 7). Do NOT shrink the safety floor to squeeze in.

- [ ] **Step 1: Score surface** — `MEV_EXT` sub-op 2 = **GHOSTSET** `+ src_route + ghost_route + delay_ticks + vol_drop + detune + pan_mode`: configures THE ghost slot (one per song, YAGNI). `delay_ticks = 0` + nonzero detune = unison; `delay > 0` = echo. `ghost_route` must be an FM route with NO score stream (packer-validated: the header's channel list must not include it). Packer event + validity tests.

- [ ] **Step 2: Engine** — config block (6 B) + note FIFO (8 entries × 3 B = 24 B: note byte, vol, due-tick low byte) in the `$1ED2-$1EFF` free block (46 B — fits with 16 B spare; add the seam assert). Hooks:
  1. Source note-on (in `Sequencer_Channel`'s note dispatch, gated on `src_route` match): push (note, vol, cur_tick+delay). Delay 0 bypasses the FIFO — immediate ghost key.
  2. Per-frame (in `Sequencer_Frame` after the channel loop, gated on ghost config armed): pop due entries → key the ghost channel via the normal FM note-on path with `vol - vol_drop`, `sc_detune = detune`, pan = pan_mode (opposite-pan default), and the DULLER-patch rule: ghost uses the source's patch with a fixed modulator-TL bias (+8, the Follin dullness — via the existing `sc_opbias` fields on the ghost channel, set at GHOSTSET time).
  3. **Arbitration:** skip the ghost key if the ghost channel is `SCF_SFX_OVERRIDE` (stolen) or currently keyed by anything else; a steal mid-tail is safe (SFX steal machinery already restores). Echo silently drops and returns — the priority-aware behavior IS this skip.
- [ ] **Step 3: Gates** — build (≤ 140 B, record actual); pytest; **renders (controller session):** (a) echo preset vs a hand-authored ghost-channel echo of the same phrase — indistinguishable spectra; (b) unison preset — stereo width visible in L/R split, mono-sum comb ≤ −3 dB (tune default detune accordingly); (c) SFX-steal mid-phrase — echo drops/returns, music channels byte-identical; (d) no GHOSTSET → all existing songs byte-identical.
- [ ] **Step 4: Commit**

```bash
git add engine/sound/sound_sequencer.asm sound_constants.asm tools/song_packer.py tools/test_song_packer.py
git commit -m "feat(sound): ghost-voice engine — unified echo bus + detune-unison (MEV_EXT GHOSTSET; priority-aware, FIFO in \$1ED2 block) [Tier 2]"
```

### Task 6: Tier 2 (BUDGET-GATED) — ExtCh3 operator-as-track

- [ ] **Step 0: BUDGET GATE** — same protocol; ceiling determined by the sizing step: FIRST write a sizing note (read `Fm_NoteOnFreq`/patch-load paths; count the op-frequency addressing delta: CH3 special mode = `$27` mode bits + `$A8-$AE`/`$AC-$AE` per-op frequency writes + a route variant `CHROUTE_FM3OP` decoding op index). If sizing lands > remaining budget − 32 B: record + close as "door documented, blocked at N bytes" (the spec's §4 CSM-style door treatment) — a legitimate outcome.
- [ ] **Step 1 (if funded):** v1 scope per spec: **alg-7 4-op chord mode only** (four independent sine-ish voices on FM3; alg-4 dual-voice stays door-only). Score surface: routes `CHROUTE_FM3_OP0..OP3` (packer maps them onto one physical channel; header validity: if any FM3-op route present, plain FM3 route is forbidden + `$27` mode set at load). Engine: note-on path for op routes writes the op's `$A8+`-block frequency + per-op TL as volume; no patch load per op (one shared FM3 patch, authored for alg 7).
- [ ] **Step 2:** Tests (packer validity + byte layout), build gates, scratch-song chord render (4-note organ pad on FM3 + bass/lead elsewhere — the polyphony demo), byte-identity for existing songs. Commit:

```bash
git add engine/sound/sound_sequencer.asm engine/sound/sound_fm.asm sound_constants.asm tools/song_packer.py tools/test_song_packer.py
git commit -m "feat(sound): ExtCh3 op-as-track — alg-7 4-op chords on FM3 (CHROUTE_FM3_OP*, MDSDRV-class) [Tier 2]"
```

### Task 7: Closure

**Files:**
- Modify: `docs/ENGINE_ARCHITECTURE.md` §6 (production-layer paragraph: what shipped which tier), `docs/DEFERRED_WORK.md` (detune-unison Ph3b orphan → absorbed here; record Tier-2 gate outcomes), `docs/superpowers/2026-07-03-sound-banking-queue.md` (package 5 → EXECUTED w/ tier outcomes), spec outcome header

- [ ] **Step 1:** Annotate all four docs; the Tier-2 gate outcomes (funded/blocked-at-N-bytes) are the load-bearing record either way.
- [ ] **Step 2:** Final sweep: full pytest, DEBUG + release builds, MT/HCZ2 golden byte-identity (all features off), final budget line recorded. Commit:

```bash
git add docs/ENGINE_ARCHITECTURE.md docs/DEFERRED_WORK.md docs/superpowers/2026-07-03-sound-banking-queue.md docs/superpowers/specs/2026-07-03-sound-production-suite-design.md
git commit -m "docs(sound): package 5 executed — production suite closure (tier outcomes recorded)"
```

---

## Self-review notes

- Spec coverage: items 1-7 (Tier 0) → Tasks 1-2; 8-9 (Tier 1) → Tasks 3-4; 10-11 → Task 5 (unified ghost voice — flagged plan-level refinement, spec §6 delegated the details); 12 → Task 6; §4 doors need no tasks (already doc'd in the spec); §5 verification distributed into task gates.
- Every Tier-2 task opens with a hard budget gate and has a legitimate blocked outcome — the plan cannot strand a future session.
- MEV_EXT sub-op registry after this plan: 0=COMM (package 1), 1=PUMPSET, 2=GHOSTSET — add the registry line to the format-validity rules in whichever task lands first at execution time.
- Consistency: `SND_PUMP_*`, `TAG_MAC_PAN`, `GhostSet`/`PumpSet`, `CHROUTE_FM3_OP*` named once and reused; all engine hooks cite verified anchors (`Seq_HookDac` :2019, TAG namespace :487-494, `$1ED2` block).
