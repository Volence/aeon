# Sound Closeout Sweep Implementation Plan (Banking Package 6)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Empty the sound-driver backlog — every remaining item verified 2026-07-03 is either EXECUTED here or formally CLOSED with a cited rationale. After this plan + packages A/B/C/D/5, the only sound line items anywhere are content-gated (drum authoring, Seraph export).

**Architecture:** Three kinds of tasks: (1) small executes (~25 B Z80 total + transcoder/tests), (2) one bounded investigation (bank-latch corrupter — emulator watchpoint work, CONTROLLER SESSION ONLY), (3) doc dispositions with citations. Verification report grounding all verdicts: the 2026-07-03 closeout sweep (items below cite current master `ca5eb5b` file:line). Items found ALREADY CORRECT in current code and needing only annotation: smpsSetVol operand decode (`tools/smps_import.py:629-643`), smpsPan AMS/FMS preservation (`:587-605`), portamento, frame-clock pin.

**User decisions embedded (2026-07-03):** no hanging sound items after packages 5/6 (Seraph excluded); H3 + rendered-A/B close on the user's Stage-A by-ear PASS; worst-tick-vs-S3K gap formally ACCEPTED (fixing it was measured net-negative twice — T9).

**Tech Stack:** AS Macro Assembler, Python 3 + pytest, `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`, oracle MCP (foreground only).

---

### Task 1: GATE articulation → `MEV_NOTEFILL` (import-time translation, zero engine bytes)

**Files:**
- Modify: `tools/smps_import.py` (GATE currently warn-skipped at ~:692)
- Test: `tools/test_smps_import.py`

- [ ] **Step 1: Failing test**

```python
def test_gate_translates_to_notefill():
    """smpsGate (S3K note-shortening, MT uses 340 of them) maps to the engine's
    existing NOTEFILL articulation — the note keys off N frames after key-on."""
    song = convert_song_snippet("""
      smpsSetvoice 0
      smpsGate $03
      dc.b nC4, $06
      smpsStop
    """, channel="FM1")          # use the module's existing snippet fixture idiom
    evs = song.channels["FM1"].events
    assert any(isinstance(e, NoteFill) for e in evs), "GATE must emit NoteFill"
```

(Adapt fixture call to the file's real helpers; also read skdisasm's `cfGate` handler first to confirm operand semantics — frames vs ticks and whether it's per-note or latched — and encode EXACTLY that in the translation + a comment citing the S3K line.)

- [ ] **Step 2: Implement** — in `_dispatch_flag`, replace the warn-skip with: decode the gate operand per S3K semantics → emit `NoteFill(converted_frames)`; a gate value of 0 restores full duration (`NoteFill(0)` = off, matching `MEV_NOTEFILL` master=0). No engine change — `sc_fill_master`/`sc_fill_count` machinery already keys off early.

- [ ] **Step 3: Re-import MT** — rebuild the MT score via the import pipeline; the 340 GATEs now emit. **Controller session:** rendered A/B of MT percussion vs the B&R reference capture (`mt_ref.vgm` is THE reference) — staccato articulation should now match; document the verdict either way. pytest + build green.

- [ ] **Step 4: Commit**

```bash
git add tools/smps_import.py tools/test_smps_import.py games/sonic4/data/sound/
git commit -m "feat(tools): GATE -> NOTEFILL import translation — MT's 340 staccato gates land, zero engine cost"
```

### Task 2: Small engine hardening batch (~25 B total)

**Files:**
- Modify: `engine/sound/z80_sound_driver.asm`, `engine/sound/sound_fm.asm`, `sound_constants.asm`, `tools/song_packer.py`
- Test: `tools/test_song_packer.py`

- [ ] **Step 1: `$28` REGWRITE guard (~4-6 B + packer rule).** `Seq_Op_RegWrite`'s deny-list covers `$2A/$2B/$24-$27` but NOT `$28` (key on/off — an authored write desyncs the engine's key state). Engine: extend the existing guard compare-chain (grep the `$24` check in the handler; add `$28`). Packer: extend `RegWrite.validate`'s refusal (`song_packer.py:315-323`) + a rejection test. Update the format-validity rules §(d)2 accordingly.

- [ ] **Step 2: Cold-boot DAC pan seed (~10 B).** `SND_REQ_SAMPLE` before any song plays silent/one-sided (YM power-on `$B6` has L/R=0). In `Snd_Init`, after the YM init block, write `$B6 = $C0` (L+R on, no AMS/FMS) once. (Debug-mailbox-only path today, but "no hanging items" — fix it.)

- [ ] **Step 3: FM env attack seam (~4 B).** FM key-on doesn't reset the `sc_env_out` shadow — an env body's leading zeros ride the PREVIOUS note's TL for 1-2 frames. Mirror the shipped PSG fix (D5, `Psg_EnvCursorReset` at `sound_psg.asm:110-116`): zero `sc_env_out` in the FM env cursor-reset at note-on (find the FM analogue near `FmEnvUpdate`, `sound_sequencer.asm:742`).

- [ ] **Step 4: Comment rot.** (a) `z80_sound_driver.asm:1290-1292` "once the gates are removed (later task)" — gates WERE removed (music-expr P1); rewrite to describe current behavior. (b) `sc_base_freq` steal-latch comment oversells behavior (bare-note/NOTE_DUR paths skip the latch under SFX override) — correct it to state exactly what latches when.

- [ ] **Step 5: Gates + commit** — pytest green, DEBUG + release builds green, budget delta recorded (≤ 25 B).

```bash
git add engine/sound/z80_sound_driver.asm engine/sound/sound_fm.asm engine/sound/sound_sequencer.asm sound_constants.asm tools/song_packer.py tools/test_song_packer.py docs/superpowers/specs/2026-06-23-music-expression-engine-design.md
git commit -m "fix(sound): closeout hardening — \$28 REGWRITE guard, cold-boot DAC pan seed, FM env attack seam, comment rot"
```

### Task 3: Test-coverage debt (importer re-trigger + opbias-on-carriers)

**Files:**
- Test: `tools/test_smps_import.py`, `tools/test_song_packer.py` (or a new `tools/test_fm_opbias.py` if the fixture doesn't fit)

- [ ] **Step 1: DAC bare-duration re-trigger test** (the shipped HCZ2 fix has no pin):

```python
def test_dac_bare_duration_retriggers_saved_sample():
    """HCZ2 snare rolls: bare-duration bytes re-trigger the saved DAC sample
    (S3K zUpdateDACTrack_cont semantics; fixed 2026-06-23)."""
    song = convert_song_snippet("""
      smpsPlaySound dSnareS3
      dc.b $06
      dc.b $06
      smpsStop
    """, channel="DAC")
    dacs = [e for e in song.channels["DAC"].events if isinstance(e, Dac)]
    assert len(dacs) == 3, "initial + 2 bare-duration re-triggers"
```

(Verify against the actual shipped semantics at `tools/smps_import.py:1006-1029` — if the initial trigger + N re-triggers count differently, pin the REAL behavior with a comment citing the S3K source.)

- [ ] **Step 2: opbias-on-carriers synthetic voice test.** The 05eca4a fix is correct-by-audit but exercised by NO shipped content (MT's carrier biases are 0). Author a packer-level test: a song with an alg-5 voice + `OpBias` on a carrier op; assert the packed patch/event bytes; PLUS a DEBUG-boot self-test hook if the existing self-test framework (grep `engine/debug/` sound self-tests) can key one note and assert the computed TL — if not feasible cheaply, the packer test + a one-time foreground oracle TL-register check (documented in the task log) closes it.

- [ ] **Step 3: pytest green + commit**

```bash
git add tools/test_smps_import.py tools/test_song_packer.py
git commit -m "test(sound): pin DAC bare-duration re-trigger + opbias-on-carriers (closeout coverage debt)"
```

### Task 4: HCZ2 import loop-length residual (tools-side audit, bounded)

**Files:**
- Investigate: `tools/smps_import.py` + the HCZ2 source score; Modify only if root-caused

- [ ] **Step 1:** Reproduce the measurement (engine tempo is S3K-exact since c56d708; the residual ~14 event-ticks/loop is IMPORT-side): count event-ticks per loop in our converted HCZ2 vs the skdisasm source score (Python script over both; commit the script under `tools/` or `docs/research/`). 
- [ ] **Step 2:** If a dropped/miscounted construct is found (call/repeat expansion, duration inheritance across loop seam): fix + test + re-import + rendered-length A/B. If NOT root-caused within the audit: write the findings (what was ruled out, exact tick counts) into the DEFERRED_WORK entry and CLOSE it as "quantified, inaudible at −14 ticks/loop, revisit only with new evidence" — a documented close is an acceptable outcome per the no-hanging-items directive.
- [ ] **Step 3: Commit** (fix or findings).

### Task 5 (CONTROLLER SESSION ONLY): bank-latch corrupter hunt (bounded)

**Files:**
- Investigate via oracle watchpoints; fix wherever the evidence lands

- [ ] **Step 1:** The persistence half shipped (`SND_CUR_BANK` poisoned with `$FF` sentinel at song load); the CORRUPTER (one observed HCZ2 capture desync at ~44 s, never reproduced) is unidentified. Execute the documented hunt plan (DEFERRED_WORK `:1586-1604`): oracle watchpoint on the `$6000` bank latch + `SND_CUR_BANK` shadow, soak HCZ2 ≥ 3 full loops × 3 runs, plus one run with heavy SFX spam (worst-case bus contention).
- [ ] **Step 2:** If it reproduces: root-cause and fix (evidence-first — do NOT patch on pattern-match). If it does NOT reproduce across the soak matrix: CLOSE the entry as "unreproduced after N×soak w/ watchpoints; persistence-half fix likely covered it; reopen on any field report" — cite run logs.
- [ ] **Step 3: Commit** (fix or close annotation).

### Task 6: Boundary-tick patch pre-load — audibility check, then fix-or-close

- [ ] **Step 1 (controller session):** Render the known worst case (measure-5 multi-channel instrument change). If NO audible stutter in the rendered capture (vgm2wav, transient inspection): CLOSE with the capture as evidence. If audible: implement the documented mitigation (pre-load patch bytes during the note-gate gap — DEFERRED_WORK `:1716-1721` sketches it) and re-render.
- [ ] **Step 2: Commit** (annotation or fix).

### Task 7: Formal dispositions (doc-only)

**Files:**
- Modify: `docs/DEFERRED_WORK.md`, `docs/ENGINE_ARCHITECTURE.md`, `docs/superpowers/2026-07-03-sound-banking-queue.md`

- [ ] **Step 1: Write each closure with its citation** (exact annotations drafted in the 2026-07-03 sweep; adapt in place):
  - **§6.4 section-aware banking → CLARIFIED + CLOSED:** not engine-level section sensing — game-code-triggered `Sound_PlayMusic`/composed fades over the shipped cached `SndDrv_SetBank`; multi-bank song layout is a ROM-linker choice with NO engine constraint (verified); the game-side pattern lives in game-feel spec §7.
  - **Phase 4 adaptive FM6/DAC → CLOSED:** dedicate + drain-gated time-share SHIPPED (`SND_FM6_ADAPTIVE` `$18FC`, suppress-while-streaming + re-key at drain); N-mixer dead by ratification; no concrete open use-case — reopen only when a real song hits a limit.
  - **Defensive Z80 upload → CLOSED:** inline-ROM driver + banked data model has no runtime Z80 byte-copy; mailbox protocol shipped; Ristar retry pattern noted for any FUTURE runtime streaming.
  - **H3 + rendered S3K A/B → CLOSED:** user by-ear PASS 2026-07-03 (Stage A); A/B machinery remains available on dispute.
  - **Worst-tick-vs-S3K gap → ACCEPTED (user, 2026-07-03):** in-tick draining measured net-negative twice (T9, reverted); the residual 24.1%-vs-21.4% DAC-hold tail is an accepted trade; reopen only with new evidence of audible impact.
  - **smpsSetVol / smpsPan review items → VERIFIED CORRECT in current code** (cite `:629-643`, `:587-605`) — the 2026-07-01 findings described an earlier version.
  - **Per-frame pitch/vol envelope variants → stays build-on-demand** (measured 97% redundant) — entry re-affirmed, not hanging: it has a trigger condition (a song that needs them).
- [ ] **Step 2: The queue doc gains the final state table:** packages A-D banked, 5 spec'd (+plan), 6 executed → sound backlog EMPTY except content-gated items (drum authoring via C's runbook; Seraph export retarget — its own project).
- [ ] **Step 3: Final build + full pytest + commit**

```bash
git add docs/DEFERRED_WORK.md docs/ENGINE_ARCHITECTURE.md docs/superpowers/2026-07-03-sound-banking-queue.md
git commit -m "docs(sound): closeout dispositions — backlog EMPTY except content-gated items (package 6 complete)"
```

---

## Self-review notes

- Every item from the 2026-07-03 verification sweep appears exactly once: executes in Tasks 1-3 + investigations in Tasks 4-6 + closures in Task 7. Nothing is silently dropped; "closed" always carries a citation and a reopen condition.
- Byte budget: Task 2's ~25 B is the plan's only resident cost.
- Tasks 5-6 are controller-session (emulator) work by construction — subagents must not touch the oracle (standing rule).
- Order flexibility: Tasks 1-4 and 7 are execution-independent of packages A/B/D; Task 2's budget line should still be recorded against whatever has merged by execution time.
