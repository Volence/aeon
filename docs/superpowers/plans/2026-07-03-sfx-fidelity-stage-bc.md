# SFX Fidelity Stage B/C Implementation Plan (Banking Package B)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the Stage-A-reserved `SfxHeader` fields (spec `2026-07-02-sfx-fidelity-and-mixing-design.md` §5 + §7 addendum): per-SFX gain, per-SFX duck, instance caps, non-latching priority, and the continuous-SFX class.

**Architecture:** Every hook point is seam-verified in the spec's §7 addendum (2026-07-03). Stage B folds ride the two existing single volume paths (`Fm_SetVolume`/`Psg_SetVolume`) and the single duck-arm site; Stage C adds a per-slot re-ping countdown (`sx_extend`) gated at the blob's loop boundary. Transcoder and engine constants stay byte-synced per spec §6. Budget: ~35-50 B resident.

**Tech Stack:** AS Macro Assembler (Z80), Python 3 (`tools/sfx_transcode.py` + pytest), `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`, oracle MCP (FOREGROUND ONLY).

**Worktree note:** branch off master AFTER `feat/sfx-fidelity` + `feat/sound-design-banking` merge. If package A merged first, the jingle validity rule in Task 6 references its `SND_REQ_JINGLE` path; otherwise the rule still lands (it is packer-side only).

**By-ear inputs (user, before or during execution):** authored `sfh_gain` values per SFX — including the roll-taste decision (DEFERRED_WORK "Roll taste": S3K-authentic 2.2 kHz/1.4 s fade; tame via gain ONLY as deliberate divergence). Plan defaults: all gains 0 (chip-exact Stage-A behavior), duck 0 for all but nothing (no current SFX is death-class), caps 1. Defaults are byte-behavior-neutral — the plan is executable without the user, and taste values drop in later as data.

---

### Task 1: Transcoder emits the real fields + validity rules

**Files:**
- Modify: `tools/sfx_transcode.py` (`pack_sfx()` :1441-1520, header emission :1492-1500; per-SFX config table where priorities/flags are authored)
- Test: `tools/test_sfx_transcode.py`

- [ ] **Step 1: Failing tests**

```python
def test_header_carries_gain_duck_cap():
    blob = pack_sfx_fixture(gain=6, duck=0x18, cap=2, chcount=1)
    assert blob[3] == 6 and blob[4] == 0x18 and blob[5] == 2   # sfh_gain/duck/cap

def test_cap_gt1_rejected_on_multichannel():
    with pytest.raises(TranscodeError, match="cap > 1 .* single-channel"):
        pack_sfx_fixture(cap=2, chcount=2)                      # spec §7.1 rule

def test_continuous_requires_loop():
    with pytest.raises(TranscodeError, match="SHF_CONTINUOUS requires SHF_LOOP"):
        pack_sfx_fixture(flags=SHF_CONTINUOUS)                  # no loop -> reject
```

(Build `pack_sfx_fixture` on the module's existing test builders — mirror the nearest header-emission test.)

- [ ] **Step 2: Implement** — replace the hardcoded `0x00/0x00/0x01` emission (:1496-1498) with per-SFX authored values (default `gain=0, duck=0, cap=1` in the SFX config table so all current blobs stay byte-identical); add the two validity rules from spec §7 (`cap>1 → chcount==1`; `SHF_CONTINUOUS → SHF_LOOP`).

- [ ] **Step 3: Byte-identity regression** — rebuild all 9 SFX blobs; `git diff --stat games/sonic4/data/sound/sfx/` must show ZERO changes (defaults are the Stage-A bytes). pytest green.

- [ ] **Step 4: Commit**

```bash
git add tools/sfx_transcode.py tools/test_sfx_transcode.py
git commit -m "feat(tools): SfxHeader gain/duck/cap authored per-SFX + Stage B/C validity rules (byte-identical defaults)"
```

### Task 2: `sfh_gain` folds (FM + PSG)

**Files:**
- Modify: `engine/sound/sound_sfx.asm` (`Sfx_BeginSound` header read ~:719-726; per-slot init ~:876), `engine/sound/sound_fm.asm` (`Fm_SetVolume` :344-510), `engine/sound/sound_psg.asm` (`Psg_SetVolume` :387-450), `sound_constants.asm` (SfxChannel struct — new `sx_gain` byte in existing pad)

- [ ] **Step 1: Stash the gain per slot.** `Sfx_BeginSound` already reads the header base into `SND_SFX_DISP_BASE`; at slot init (where `sx_priority` is written, :876) add `sx_gain` = header `sfh_gain` (offset +3). Add `sx_gain` to the SfxChannel struct in `sound_constants.asm` using an existing pad byte (the struct has documented pad — cite it in the commit; if no pad remains, extend the struct and re-check the `$1D00` region seam assert).

- [ ] **Step 2: FM fold.** In `Fm_SetVolume` immediately after the log-LUT read (~:350, value in `Fm_ScratchLog`), add — SFX channels only (the existing music-only duck fold at :376-408 shows the ix-class test to invert):

```asm
        ; Stage B sfh_gain: authored per-SFX attenuation, FM-TL units (0.75 dB).
        ; SFX slots only; downstream env/fade clamps (SND_FM_TL_MAX) cover the sum.
        ; (ix >= SND_SFX_BASE test: same class check as the duck fold, inverted.)
        ...                              ; class test per the :376 idiom
        ld      a, (ix+sx_gain)
        or      a
        jr      z, .no_gain
        ld      hl, Fm_ScratchLog
        add     a, (hl)
        ld      (hl), a                  ; overflow lands in the existing :366 clamp path
.no_gain:
```

(EXECUTOR: read :361-373 first — if the env fold clamps before your add runs, move the gain add ABOVE the env fold so one clamp covers both; the invariant is gain participates in the clamped sum, exact ordering per the real code.)

- [ ] **Step 3: PSG fold.** In `Psg_SetVolume` after `Psg_VolToAtten` (~:388, attenuation in `c` per the report): add `sx_gain >> 3` (the same TL→atten ÷8 conversion the fade/duck fold uses at :427-429), clamp `$0F`, SFX class only.

- [ ] **Step 4: Gates** — build green (≤ 20 B); all-gains-0 → oracle jump/ring/skid registers byte-identical to Stage A (controller spot-check). Then a taste probe: set roll's gain to 6 in the config, rebuild, verify carrier TLs +6 exactly; revert to 0 unless the user picks a value.

- [ ] **Step 5: Commit**

```bash
git add engine/sound/sound_sfx.asm engine/sound/sound_fm.asm engine/sound/sound_psg.asm sound_constants.asm
git commit -m "feat(sound): per-SFX sfh_gain fold — FM TL + PSG atten at init-time volume paths (Stage B; 0 = Stage-A-exact)"
```

### Task 3: Per-SFX duck (`sfh_duck`)

**Files:**
- Modify: `engine/sound/sound_sfx.asm` (duck-arm :903-912; `Sfx_AnyDuckActive` scan :1123-1132 region), `sound_constants.asm` (SfxChannel `sx_duck` byte; retire `SFX_DUCK_DEPTH`/`SFX_DUCK_THRESHOLD` per clean-not-bolted-on)

- [ ] **Step 1:** Stash `sfh_duck` into new `sx_duck` at slot init (same pattern as Task 2 Step 1).

- [ ] **Step 2:** Duck-arm (:903-912): replace the `SND_SFX_DISP_PRIO >= SFX_DUCK_THRESHOLD` test with `sfh_duck != 0`, and write the SFX's own depth: `ld a,(header sfh_duck) / ld (SND_SFX_DUCK_TARGET), a`. DELETE `SFX_DUCK_THRESHOLD` + `SFX_DUCK_DEPTH` from both constants copies (transcoder too) — no dormant constants.

- [ ] **Step 3:** Un-duck scan: `Sfx_AnyDuckActive` currently scans `sx_priority >= threshold`; change to scan `sx_duck`, returning the MAX among active slots, and write that (not zero-or-constant) to `SND_SFX_DUCK_TARGET` — mixed-depth overlaps resolve to the deepest duck; all-idle resolves to 0 naturally (spec §7.1).

- [ ] **Step 4: Gates** — build green; ramp behavior: with all authored ducks 0 (Task 1 defaults), NO SFX ducks music (a Stage-A behavior CHANGE — Stage A ducked by priority; the spec's classic-faithful call is duck-by-authoring. Verify HCZ2 bed level no longer dips under jump spam — rendered check, and record the divergence note in the queue log for the user's by-ear pass). Commit:

```bash
git add engine/sound/sound_sfx.asm sound_constants.asm tools/sfx_transcode.py
git commit -m "feat(sound): per-SFX duck depth replaces global threshold/depth — duck is authored, deepest-active wins (Stage B)"
```

### Task 4: Non-latching priority (bit 7) + instance caps

**Files:**
- Modify: `engine/sound/sound_sfx.asm` (`Sfx_SelectVoice` :1330-1503; retrigger scan :731-761; init :876)

- [ ] **Step 1: Bit-7 masking.** Every priority COMPARISON in `Sfx_SelectVoice` and the retrigger path masks bit 7 (`and $7F`) before comparing — audit each `sx_priority`/`SND_SFX_DISP_PRIO` compare in :1330-1503 and list them in the commit body.

- [ ] **Step 2: Non-latching store.** At init (:876): if incoming priority has bit 7, store `min-of-active-slot-priorities` (the victim scan at :1431-1480 already computes the min — carry it to the store) instead of the incoming value. Effect: the sound plays now but never raises the floor for later sounds (spec §5, S2's trick).

- [ ] **Step 3: Caps.** Retrigger scan (:731-761) currently kills ANY same-id match (cap 1). Change: count matches; if `count < sfh_cap`, allocate a new instance (skip the kill); if `count == cap`, kill the LOWEST-slot match (oldest-by-slot, spec §7.1) then allocate. `sfh_cap`=1 must produce byte-identical Stage-A behavior (the count==1 path degenerates to today's kill) — verify by register trace.

- [ ] **Step 4: Gates + commit** — build (≤ 15 B); oracle: jump spam still 1 instance (cap 1); a test blob with cap=2 (single-channel, Task 1 rule) yields exactly 2 then replace-oldest.

```bash
git add engine/sound/sound_sfx.asm
git commit -m "feat(sound): non-latching priority (bit 7 floor-neutral) + authored instance caps w/ oldest-slot kill (Stage B)"
```

### Task 5: Stage C — continuous-SFX class

**Files:**
- Modify: `engine/sound/sound_sfx.asm` (`Sfx_BeginSound` retrigger path; `Sfx_Frame`; the `MEV_JUMP` loop-boundary handler in the SFX stream interpreter), `sound_constants.asm` (SfxChannel `sx_extend` byte + `SFX_EXTEND_FRAMES = 10`)

- [ ] **Step 1: Extend-on-re-ping.** In the retrigger scan, BEFORE the cap/kill logic: if the incoming id matches an active slot AND the blob's `sfh_flags` has `SHF_CONTINUOUS`: reload that slot's `sx_extend = SFX_EXTEND_FRAMES` and RETURN (no re-key, no kill — rev/`MEV_SPINREV` state untouched, spec §7.2).

- [ ] **Step 2: Countdown.** In `Sfx_Frame`'s per-slot loop: active + continuous + `sx_extend != 0` → `dec (ix+sx_extend)`. (Floor at 0; do not wrap.)

- [ ] **Step 3: Loop-boundary gate.** In the SFX interpreter's `MEV_JUMP` handler (grep how SFX streams take `MEV_JUMP`/`MEV_LOOP_POINT` — the `SHF_LOOP` path): for a continuous blob, `sx_extend != 0` → take the loop; `== 0` → fall through to the existing looped-SFX fade tail (the shipped B4/modSet-riding fade, commit 0ac3403) → `Sfx_Restore`. Init `sx_extend = SFX_EXTEND_FRAMES` at first dispatch.

- [ ] **Step 4: Gates** — build (≤ 15 B); NO current blob sets the flag → full regression: all 9 SFX register-identical. Then the mechanism proof with a test blob (author a looping test SFX with `SHF_CONTINUOUS` via the transcoder fixtures): ping every frame → sustains; stop pinging → fades within one loop + `SFX_EXTEND_FRAMES` frames. Controller session: rendered spindash-charge A/B vs S3K IF the user opts to flip spindash to continuous (taste pass — NOT a gate; record either way).

- [ ] **Step 5: Commit**

```bash
git add engine/sound/sound_sfx.asm sound_constants.asm tools/sfx_transcode.py tools/test_sfx_transcode.py
git commit -m "feat(sound): continuous-SFX class — SHF_CONTINUOUS + sx_extend re-ping countdown, fade-out one loop after pings stop (Stage C, S3K semantics)"
```

### Task 6: Cross-package validity + tracking closure

**Files:**
- Modify: `tools/sfx_transcode.py` (jingle rule), `docs/DEFERRED_WORK.md`, `docs/ENGINE_ARCHITECTURE.md` §6.7, `docs/superpowers/2026-07-03-sound-banking-queue.md`, spec §7 outcome header

- [ ] **Step 1:** Package A cross-rule (spec A §5): blobs marked jingle-class reject `SHF_CONTINUOUS`, `SHF_LOOP`, FM6 and DAC routes (transcoder `--jingle`-class flag or config bit — match however Task 1 shaped the config table) + a test per rejection.
- [ ] **Step 2:** Docs: DEFERRED_WORK "SFX Fidelity Stage B/C" entry → outcomes per item (incl. the duck-model divergence note for by-ear); ARCH §6.7 → SHIPPED; queue package B → EXECUTED; sfx-fidelity spec gets a Stage-B/C outcome line under its Stage-A header.
- [ ] **Step 3:** Final gates: full pytest, DEBUG + plain builds, budget delta recorded (target ≤ 50 B), 9-SFX register-identity regression re-run after ALL tasks. Commit:

```bash
git add tools/sfx_transcode.py tools/test_sfx_transcode.py docs/DEFERRED_WORK.md docs/ENGINE_ARCHITECTURE.md docs/superpowers/2026-07-03-sound-banking-queue.md docs/superpowers/specs/2026-07-02-sfx-fidelity-and-mixing-design.md
git commit -m "docs(sound): package B executed — Stage B/C closure sync + jingle-class validity rules"
```

---

## Self-review notes

- Spec §5/§7 coverage: gain → T2, duck → T3, non-latching + cap → T4, continuous → T5, constants-sync rule (§6) → T1, jingle cross-rules → T6. H3 and the rendered S3K A/B stay by-ear-gated (unchanged, still in DEFERRED_WORK).
- Two deliberate behavior changes are flagged for the user's by-ear pass: duck-by-authoring (no SFX ducks until authored — T3 Step 4 note) and the roll-gain taste knob (default 0 = S3K-authentic).
- Byte-identity regressions gate every task — defaults reproduce Stage A exactly, so the phase is safe to merge before any taste values are chosen.
