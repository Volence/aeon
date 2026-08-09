# Sound-study triage — MDSDRV source study → actionable backlog (2026-08-08)

**Inputs:** `2026-08-07-mdsdrv-source-study.md` + its four evidence files
(`2026-08-07-mdsdrv/{core,z80-dma,sfx-and-gaps,format-toolchain}.md`), cross-checked
against `docs/DEFERRED_WORK.md` (sound sections) and the banked 2026-07-03 sound
package queue (`docs/superpowers/2026-07-03-sound-banking-queue.md` + the five open
package plans/specs).

**Standing state this triage is written against:** packages 1/3/4/5/6 remain open
(order 1→3→4→5→6; package 2 shipped 2026-07-07). Invariants every proposal below
respects: SFX priorities are 7-bit (bit 7 = non-latching flag); `SfxChannel` is 68 B
with `sx_pad@+58` aliasing `sc_detune` (the SeqChannel↔SfxChannel shared prefix is
load-bearing — **no proposal may grow the shared prefix**); Z80 resident-code headroom
is ~316 B DEBUG after the wave-4 reclaim; `MEV_EXT` sub-ops 0/1/2 are claimed
(COMM/PUMPSET/GHOSTSET) — new tenants start at 3.

**Judgment rule applied throughout:** MDSDRV is an input to weigh, not an authority.
Every verdict below is "best overall for OUR driver" — several MDSDRV features are
rejected precisely because our shipped design already dominates them.

---

## 1. Summary — what the study yielded

The 9.4k-line source read did **not** find a driver to imitate; it confirmed our
Z80-autonomous architecture dominates MDSDRV's 68k-sequencer model on every axis we
chose it for (bus holds 2/frame vs dozens, DAC rate, SFX arbitration — sfx-and-gaps §1.5
is a clean sweep in our favor). What it yielded instead is: **(a)** two latent defects
in our own DAC driver found by comparison (a Timer-A refill that reads banked ROM
through an active 68k DMA — hardware-only, needs a user ruling; and a ring-underrun
buzz with no recovery — emulator-provable, cheap); **(b)** one genuine architectural
correction — pitch modulation belongs in the log (semitone) domain, not the linear
f-num domain, which is both a fidelity fix and a net Z80 byte *saving*; **(c)** a
measured 3-5x data-density gap in our sequence format with four individually-measured
mechanisms behind it (duration encoding −26% on HCZ2, by-id payloads −14% on MT,
note-range/transpose 29% of MT, nested loops); **(d)** a cluster of small expressive
gaps (fade rates, envelope release, macro state-writes, slur); and **(e)** the
cross-cutting finding that our sound system is **under-instrumented** — no DMA-margin
telemetry, no SFX-channel observability, no driver cost meter. Several study headline
items (pause/resume, comm cue byte, status queries) turn out to be **already banked in
package 1** — they are corroboration, not new work.

---

## 2. Ranked adopt/fix list

Ranked by value-per-effort for a completeness/best-of-class driver. "Headroom" = Z80
resident code bytes against ~316 B free. Effort: S < 1 session, M = 1-2 sessions,
L = its own planned parcel.

### R1. DRAIN underrun guard — the ring-lap buzz latch
- **What:** `.drain`/`.loop` advance RD unconditionally; at lead 0 RD laps WR and
  replays the ring as a ~72 Hz full-amplitude buzz, and the tick's `cp LEAD_TARGET`
  then misreads the lapped ring as *full*, so it never recovers. Fix is a 34 T
  branchless "don't advance RD at lead 0" paid out of the existing 76 T DRAIN pad —
  the `ensure(cycles())` proofs re-derive unchanged.
- **Evidence:** z80-dma.md #2 (verified code read both sides; MDSDRV holds last sample,
  `mdssub.z80:299-310`); main study §2b.
- **Package:** none owns it. Cleanest home: **execute alongside package 4** (the
  correctness batch) as a rider commit, or as its own micro-parcel — do NOT rewrite
  the banked package-4 plan, just batch the session.
- **Effort:** S. **Risk:** low; ~9 B, **0 net cycles** (comes out of the pad);
  emulator-reproducible before/after, so fully provable to our normal standard.
- **Recommendation: ADOPT.** Highest-confidence correctness fix in the study, and the
  only one of the two DAC defects we can *prove*.

### R2. Sound-observability cluster (three cheap instruments)
- **What:** (i) ring-lead telemetry byte (`SND_STAT_MIN_LEAD`, sampled in the tick
  before refill — their `z_load`), ~5 B + 1 RAM byte from the 45 B map slack;
  (ii) driver cost meter — read the raw H/V counter after the sound update in VBlank,
  ~3 68k instructions; (iii) extend the DEBUG sound mirror to cover SFX channels
  (`{sc_flags, sc_route, sx_priority, id}` × 7 + the queue block ≈ 36 B of mirror)
  — today steals/drops/queue depth are completely unobservable.
- **Evidence:** z80-dma.md #4; sfx-and-gaps §3 #1/#2; main study §8b sweep
  ("our sound system is under-instrumented" — no DMA margin, no SFX visibility,
  no cost meter).
- **Package:** rider on **package 6** (closeout sweep) — 6's bank-latch corrupter hunt,
  boundary-tick audibility check, and coverage-debt tests all *want* these instruments;
  and the DEFERRED_WORK "DAC worst-tick profiling round" (line ~2518) and the A2/bank-latch
  emulator-gated items (lines ~120-130) become measurable instead of vibes. Also build
  the MDSDRV-style adjustable simulated-DMA-burn tuning ROM equivalent when acting on (i).
- **Effort:** S. **Risk:** none ((i) can be DEBUG-gated to 0 B release; (ii) is 68k;
  (iii) is inside the already-gated DEBUG mirror, budget permitting).
- **Recommendation: ADOPT.** Prerequisite for ever *claiming* DMA margin and SFX
  arbitration health rather than assuming them. Cheapest leverage in the whole list.

### R3. Log-domain pitch (8.8 semitones; f-num derived once by interpolation)
- **What:** move detune/portamento/vibrato/pitch-env onto one 8.8 semitone value per
  channel; convert to f-num once via table interpolation with a zero-fraction fast
  path. Fixes the real fidelity flaw that our authored depths are worth ~2x more cents
  at the bottom of an octave block than the top and jump discontinuously across block
  boundaries ("vibrato uneven in the high register" class). Deletes `Fm_FnumApplyDelta`
  (~55 resident B + its documented block-7 bit-bleed edge case).
- **Evidence:** main study §1 (verified in both codebases); core.md #1 (full mechanism,
  `mds_pitch_update` / `mds_get_fm_pitch` cites; Z80 cost ≈ 2.5% of frame for 6 FM
  channels via shift-add multiply, un-modulated notes free).
- **Package:** **new work, no package** — needs its own scoped spec+plan (the study
  itself says "a scoped plan, not a patch"). Sequence it *early* among new work: its
  ~55 B reclaim funds several smaller items below, and R10/ins_trs are gated on it.
- **Effort:** M-L. **Risk:** medium — every authored vibrato/porta/detune value in the
  two shipped songs is in f-num units; mitigation on file is keeping the f-num path for
  `MEV_NOTE_RAW` streams and making log-domain the default for table-derived notes.
  This is also a chip-stream change → full A/B render ritual (verify real output, not
  registers) + blob re-pin.
- **Recommendation: ADOPT.** Biggest single musical-correctness idea in the study, and
  net-negative on headroom. Flag for user sign-off as a novel bet (leapfrog-provenance
  rule): it changes the expression engine's unit system.

### R4. Fade rate as a rotating bit pattern (8 rates from 1 byte)
- **What:** replace the single hardcoded `SND_FADE_STEP=2`/`SND_FADE_DELAY=1` with
  MDSDRV's 8-entry spread-bit rate table + `rrc`/sign-test; branchless ±1 step. Gives
  authored fade speeds (and the API "selectable rate" gap sfx-and-gaps §2 row 0x0A
  identifies) for ~10-15 B net-zero (replaces the delay counter byte).
- **Evidence:** core.md #6; main study §4.
- **Package:** **package 1 rider** — package 1's Task on fade terminals already
  modifies `Fade_Ramp`; the plan itself notes MDSDRV's fade-rate lookup is "worth
  copying as implementation detail" (DEFERRED_WORK E-now-3 lineage). Execute in the
  same session, one extra commit; no re-banking needed.
- **Effort:** S. **Risk:** trivial.
- **Recommendation: ADOPT.**

### R5. Re-key flam on SFX restore — trace, then fix
- **What:** possible double-attack: `Seq_RekeySingle` leaves `SCF_REKEY` pending during
  a steal while `Sfx_Restore` independently re-keys from `sc_base_freq` — both may fire
  around one restore (two attacks a frame apart, possibly at two pitches). MDSDRV's
  guard (mask pending key-on when <5 ticks remain / always in drum mode) is an ~8 B fix
  either way.
- **Evidence:** main study §2c; core.md #9 — both explicitly mark it **[I] inferred,
  needs an emulator trace before it is treated as real**.
- **Package:** the trace is a foreground oracle session (subagents can't drive the
  emulator); if confirmed, the fix rides the same session as R1.
- **Effort:** S (trace + fix). **Risk:** low.
- **Recommendation: ADOPT the investigation;** fix only on a confirmed trace. Do not
  book the fix as work until then.

### R6. Sequence-format revision v1 (batched, one re-pack + re-pin)
- **What:** the format-semantic wins batched into ONE revision so the shipped blobs
  re-pack and the byte-parity pins re-freeze exactly once:
  1. two running-duration registers + bare-duration-byte-as-rest (**measured −26.2%**
     on the whole HCZ2 blob);
  2. id-referenced PitchEnv/OpBias payloads (**measured −14% on MT**: 1824 events,
     29 distinct payloads);
  3. `trs`/`trsm` transpose opcodes (near-free — `sc_transpose` exists and is applied;
     only `Seq_Op_SpinRev` writes it) + per-instrument transpose byte in `FmPatch`'s
     existing `fp_reserved[2]` — together the structural fix for MT's note-range tax
     (**3648 B, 29% of MT**, spent on `$E8 01 idx` single notes);
  4. `volm` relative volume, `slr` slur/tie (closes the recorded
     `smps_import.py:670-676` "accepted v1 fidelity gap" for different-pitch
     `smpsNoAttack`), header version byte (stale blob → diagnosable stop instead of a
     hang). All fit on free opcode slots ($FA-$FE + reserved $F1).
- **Evidence:** format-toolchain.md #1/#4/#5/#6/#7/#10/#17 (all measured on our real
  blobs, method in its §6); main study §6/§7.
- **Package:** **new work, no package.** Verify PSG honours `sc_transpose` (format
  study only checked FM — pairs with package 4's D4, which fixes exactly that for PSG:
  sequence format-v1 *after* package 4 so transpose is correct on both routes).
- **Effort:** M (engine bytes small — a channel byte + a few opcode handlers, est.
  ~30-50 B total; the bulk is packer/tooling + the byte-changing-parcel ritual).
- **Risk:** medium — format-semantic, every blob re-packs, `$00-$7F` changes from
  zero-tick to time-advancing (touches the validity rules' time-advancing event set).
  Chip-stream must be verified identical post-repack (render A/B).
- **Recommendation: ADOPT.** Do it once, early, before the soundtrack grows. Note
  data-density is a ROM-side win — it costs almost no resident headroom.

### R7. PSG/FM envelope release phase
- **What:** a "continue past sustain on key-off" branch so envelopes get a real release
  instead of `$81` holding forever until the next note-on. ~15-20 B. (MDSDRV's
  run-length *storage* format is explicitly NOT taken — see non-adoptions.)
- **Evidence:** core.md #7a; format-toolchain.md #9 (storage half deferred there too).
- **Package:** new work; small enough to ride the R6 format-revision session (it adds
  an envelope control code) or stand alone.
- **Effort:** S-M. **Risk:** low-medium — touches the shared envelope grammar our
  music-expression spec §3.3 generalises; decide at spec level (one-paragraph
  amendment), not ad hoc. Our env bodies are S3K-imported verbatim; release must be
  opt-in per envelope so fidelity work is untouched.
- **Recommendation: ADOPT (opt-in control code).**

### R8. Macro table writes channel *state*, not just YM registers
- **What:** `TAG_MAC_SET`/`TAG_MAC_ADD` pair (set/add a channel-struct byte at offset,
  saturating clamp on TL-class fields, auto-dirty volume) — makes the macro spine as
  expressive as MDSDRV's mtab for ~25-35 B; `(ix+d)` makes it native.
- **Evidence:** core.md #4; main study §7. Also worth folding in: the 2-byte
  register-write form (`cmd<<2` — every per-channel YM reg is a multiple of 4) vs our
  4-byte `TAG_MAC_REG`, and mtab loop-count/break (format-toolchain.md #13).
- **Package:** new work. Natural neighbor of package 5 (production suite — the TL-sweep
  and patch-vocabulary work would *use* it), but do not re-bank package 5; land this
  first or alongside.
- **Effort:** S-M. **Risk:** THE safety note is load-bearing: our interpreter walks
  both `SeqChannel` and `SfxChannel` with load-bearing aliases past +56 — the offset
  **must be build-gated in the transcoder** (and ideally runtime-clamped to
  `<= sc_last_freq`) or a music macro can poke an SFX slot's `sx_priority`. This is the
  `sx_pad@+58` invariant showing up again; the gate is non-negotiable.
- **Recommendation: ADAPT** (their idea, our build-time offset gate).

### R9. Loop-split PHASE — bank 30 T, zero SMC
- **What:** the study's own §10 resolution of the opcode-patch question: give
  DRAINING_TAIL its own loop so the 18356 Hz hot path stops testing a once-per-sample
  mode flag. −30 T/sample, ~+15 B, zero self-modifying code; all `cycles()` proofs
  still derive. **Bank the cycles; do not spend them on rate** — raising the loop rate
  re-pitches the whole ear-matched drum kit.
- **Evidence:** main study §10 (options table; #1 recommended; SMC variants dominated;
  build-gating decisively rejected — DEBUG/release would sit 3.6 semitones apart).
- **Package:** new work, no package.
- **Effort:** S-M. **Risk:** low-medium (hot-loop restructure, but machine-checked by
  the existing ensures; the §10 analysis already cleared the hazards). Remember the
  DEBUG state mirror slurps `SND_STATE_BASE` — keep PHASE's RAM writes (or fix the
  mirror) so the mirror byte doesn't go permanently stale.
- **Recommendation: ADOPT** — as the pre-payment on the polyphonic-PCM gap (a second
  mixed stream costs ~57-70 T; 30 T banked is a third of it). Not urgent; schedule
  behind R1-R6.

### R10. Structure phase: `pat` subroutines → drum mode → nested loops
- **What:** a per-channel call/loop capability: `pat` subroutines (2 B state), then
  drum mode (a note byte calls a percussion program, `MEV_DRUMFINISH` supplies the
  pitch — 1 byte per FM/PSG drum hit instead of a 5-10 B preamble), then nested counted
  loops + `lpb` loop-break if still wanted. Order matters: subroutines let the *packer*
  express nesting with 2 B of channel state instead of a 4 B/level stack.
- **Evidence:** core.md #2; format-toolchain.md #2/#3/#12 + §5 batching advice
  (loops carry MDSDRV's 2.8-6.1x expansion; `lpb` cheap even single-level).
- **Package:** new work, no package.
- **Effort:** M-L. **Risk:** medium — the real cost is per-channel RAM (2-level stack
  = 88 B across 11 channels; 3-level = 132 B), and **any SeqChannel growth must land
  entirely past the SfxChannel shared-prefix seam or in separate arrays** (the
  `sx_pad@+58 == sc_detune` alias forbids touching the prefix). A mis-encoded blob
  hangs (trust-the-packer) — R6's version byte helps here.
- **Recommendation: ADAPT, deferred-until-pulled.** Both shipped songs are machine
  ports that flatten structure — the measured density gap partly evaporates against
  them (HCZ2 has zero repeats to start with). Value materialises when hand-authored /
  Seraph-authored music exists. Bank the design; build when a real song or the Seraph
  S1 exporter wants it. `lpb` alone (single-level, ~2 B opcode) may ride R6 cheaply.

### R11. Generic pitch envelope replacing the dedicated vibrato machine
- **What:** replace the 11 B/channel single-shape vibrato state with a 6 B generic
  node-list pitch envelope (a looping 2-node envelope *is* vibrato; frees ~90 B of
  Z80 RAM across 18 slots and covers strictly more shapes).
- **Evidence:** core.md #10.
- **Package:** new work — **strictly sequenced after R3** (in the f-num domain a
  generic delta envelope inherits every block-boundary problem; the study says
  "together or not at all").
- **Effort:** M. **Risk:** medium (replaces a shipped, fidelity-verified vibrato path;
  full A/B render required).
- **Recommendation: ADAPT, conditional on R3.** Fold into the R3 plan as a phase-2
  task so the sequencing is structural.

### Already banked — corroborated, not new (do not double-plan)
| Study item | Where it already lives |
|---|---|
| Pause/resume (core.md #3, "we have *nothing*") | **Package 1**, Task 2 "Pause engine (Z80)" — `SND_REQ_CTRL`, pause gate in `Sequencer_Frame`, `Sfx_Restore`-based resume. The study's `nm_restore` read is implementation corroboration for the executor. |
| `comm` song→game cue byte (format-toolchain #8) | **Package 1** spec §6 — `SND_STAT_COMM` + `MEV_EXT $00` is literally logged as "MDSDRV `get_comm` steal". |
| "Is music playing?" status query (sfx-and-gaps §2 row 0x02) | **Package 1**, Task 1 — `SND_STAT_SEQ_ACTIVE` + 3 more status mirrors. |
| Fade *terminals* (stop/pause on completion) | **Package 1** (`SND_FADE_TERM`). Only the *rate* half (R4) is new. |
| Restore-suppression heuristics around steals | Partially: package 2 shipped the steal/restore engine; R5's flam is the residual question. |

---

## 3. Needs-user-ruling

These are taste/scope/confidence-class calls, not defects with obvious fixes. None
should be executed on assistant discretion.

**RULINGS (closed 2026-08-09):**

1. **Timer-A/DMA: fix TAKEN** (user-ruled). Accepted explicitly on
   reasoning + MDSDRV's documentation rather than in-loop verification — a
   recorded confidence-class exception to the verify-real-output practice,
   justified by the 6 B cost and the real-hardware failure mode. Rides
   package 1's session.
2. **Multi-tick tempo: ADOPTED as a strict superset** (user delegated to the
   top-of-the-line bar; shape is the assistant's call). S3K-range tempo values
   stay bit-exact — the multi-tick loop engages only above the old 1-tick/frame
   cap, so the S3K-exact contract is preserved for all existing content. Loop
   is bounded (fixing the hazard MDSDRV itself carries). Lands TOGETHER with
   the item-25 H1 mid-frame `$F3` broadcast correction as one tempo-contract
   parcel (do not split), with the `Sequencer_Frame` vs DAC-ring-lead profiler
   check as the acceptance gate.
3. **68k SFX policy layer: RULED IN as a future design task** (user-ruled) —
   frame-level policy on the 68k, live-state mechanism stays on the Z80.
   Queued after the banked packages (1→3→4→5→6); design session, not a parcel.
4. **R9 30 T: BANKED for polyphonic PCM** (user-ruled after briefing) — not
   spent on DAC rate. The headroom is earmarked for the two-voice DAC gap
   named by the driver comparison; rate spend would re-pitch the
   fidelity-matched kit for a modest gain and narrow the polyphony budget.

1. **Timer-A refill through an active DMA (the hardware-only fix).** Our
   `SndDrv_TimerATick` bulk-refills from banked ROM without checking
   `SND_CTRL_DMA_ACTIVE`; Timer A (60.05 Hz) free-runs against VBlank (59.92 Hz), so
   the tick walks through the DMA window continuously — exactly the address-line-glitch
   hazard MDSDRV's `doc/dma.md:18-26` documents (corrupted VRAM or 68k RAM at DMA
   start). Fix is 6 B, 0 hot-loop cycles (poll the flag inside `.refill`).
   **The catch:** this project has NO real hardware and Oracle does not model
   cartridge-bus contention — the hazard is unobservable in our entire verification
   loop, and so is the fix. Taking it means accepting a change on reasoning + MDSDRV's
   documentation instead of on verification — a different confidence class from our
   standing "verify real output" practice. The failure mode it prevents is
   flashcart/real-hardware corruption. My recommendation as input: take it (6 B is
   cheap insurance, the skipped-frame refill is exactly what R1 makes safe, and the
   study rates the reasoning solid) — but the ruling is the user's by prior agreement
   (main study §2a flags it verbatim).
2. **Multi-tick-per-frame tempo (sub-frame resolution).** Removes the hard 1-tick/frame
   cap (fast grids/arps become representable) — but our tempo model is **S3K-exact by
   design**, so this is a deliberate contract divergence, not a bug fix
   (core.md #5 says so explicitly). It also interacts with the DEFERRED_WORK item-25
   H1 correction (mid-frame `$F3` tempo broadcast phase-offset — do not compound the
   two changes without a ruling on the tempo contract). Bound the loop if adopted
   (MDSDRV doesn't — a latent hazard in *their* code). S effort, low-medium risk,
   worst-case `Sequencer_Frame` cost rises against the DAC ring lead (profiler check).
3. **68k-side SFX *policy* layer (context-aware arbitration).** Study §8c: not worth
   doing for space (net saving < queue size; headroom is fine post-wave-4), but there
   is an independent *quality* case — the 68k knows game context (boss death vs
   eleventh ring this second) that the Z80's blind priority numbers cannot express,
   and our own SFX spec (`2026-07-02-sfx-fidelity-and-mixing-design.md:72`) already
   names instance-limiting/per-context depth as the gap vs modern practice. This is a
   scope/architecture call: frame-level policy → 68k, live-state mechanism → Z80. If
   ruled in, it is a design task, not a parcel.
4. **Spending the R9 banked 30 T on DAC rate.** Raising the rate re-pitches the entire
   fidelity-matched drum kit; the study's recommendation is bank-don't-spend, with
   "re-render the kit in the tools" as the only acceptable spend path. Content/taste
   call — user's by the engine-vs-content rule.

---

## 4. Explicit non-adoptions

Recorded so these do not get re-litigated. All verdicts concur with the study's own
§8 rejects unless noted.

| Finding | Why not |
|---|---|
| **68k-resident sequencer / 4-slot BGM+SFX unification** | A rewrite, not a technique; our Z80-autonomy ruling stands and we *ship* things it lacks (ducking, voice allocation, 7 concurrent SFX, request ring). Also already SKIP'd in DEFERRED_WORK §E. |
| **Position-independent code + table-of-`bra.w` dispatch** | Z80 has no PC-relative addressing; our `SeqOpcodeTable` is already banked. Nothing to port. |
| **Opcode-patch SMC for hot-loop flags** | Superseded — the naive patch was proven buggy as specified (`.afterPoll` flag state) and the non-SMC loop split (R9) beats it on cycles at zero risk. Option 2 (SMC on the DMA flag) only ever behind a Sigil `patch_site` construct, which would have to exist first. |
| **16×256 B volume-LUT mixing** | Needs 4 KB of Z80 RAM that does not exist; unbankable (the `$8000` window holds sample payload). Reduced forms (bare saturating add; one shared halve-table) are recorded in z80-dma.md #6 for a future mixing phase — that phase itself stays deferred (single-voice DAC bet was user-ratified 2026-07-03). |
| **Z80 self-opens the DMA window (`ei` + /INT)** | Incompatible with our `di` end-to-end register-resident loop; their price is the shadow-register-detection hack. R1 + the §3 ruling capture the two safety properties (fail-closed, no-bus-in-window) without changing the trigger. |
| **Batch producer / register re-plan for the 16 T fetch gap** | Our single stream already outruns their two; every register re-plan costed out at zero or worse. Revisit only bundled with a real mixing phase. |
| **FM3 special mode** | 3 timbre-locked voices (shared patch+algorithm), collides with SFX stealing FM3 and `Sfx_Restore`'s one-channel model, plausibly 100-200 B. Already "someday" in DEFERRED_WORK §E; the study adds the full mechanism documentation (core.md §0.3) for whenever a song actually needs it. Banked, not near-term. |
| **PAL tempo compensation** | Prior ruling (PAL-delete parcel). |
| **Pointer-byte scavenging / type union / command-length table** | 68k-specific or measured at ~18 B total — under the aliasing-hazard bar our SfxChannel overlap already burned us on once. |
| **Tiered SFX priority ID lists (the MDTravis pattern)** | Correct-for-MDSDRV, strictly inferior to our authored `sfh_priority` + build-fatal `ensure`: second source of truth keyed on ID values, rots silently on renumber. sfx-and-gaps §1.4's verdict: nothing to take. |
| **PSG envelope run-length *storage* format** | Our env bodies are S3K-imported verbatim and the fidelity work rests on that; envelope data is not a ROM problem today. Take only the release *phase* (R7); adopt the ramp *authoring notation* at tool level if Seraph S1 ever wants it. |
| **`t_ins_trs` per-instrument f-num band as a timbral knob** | Trades away the single-band invariant our current detune/porta correctness rests on; subtle audible payoff. Auto-unlocks harmlessly if R3 lands (and R6 item 3 takes the *transpose* half for the note-range fix, which is the part with measured value). |
| **MML language wholesale** | Take the two notation ideas (`{a/b/c}` chord fan-out, `/` loop-break) as Seraph S1 / packer-front-end inputs; the language itself is ctrmml's, out-of-repo, and our authoring path is the packer DSL + (eventually) Seraph. |
| **`call burn_31` dense pads** | Blocked: `cycles()` doesn't follow calls; ~10-14 B reclaim is not worth a hand-pinned timing hole in the hot loop. Park until a sigil cycles-across-call feature exists. |
| **`quickrom` drag-and-drop test ROM** | `SOUND_DEBUG_HOTKEYS=1` sound test already covers the need. |

---

## 5. Cross-check against DEFERRED_WORK sound sections

Items above that are ALREADY tracked there (or adjacent), so nothing double-tracks:

- **Pause / comm / status / fade terminals** — owned by **package 1** per the
  DEFERRED_WORK §"From Sound Driver Work" 2026-07-03 STATE-OF-TRUTH banner (~line 1799:
  "game-feel gaps (pause/jingle/song-finished/API v2) → package 1"). The study items
  map as corroboration only (see the R-list table).
- **R1 (drain underrun)** — *partially* pre-captured as deep-audit **C4** ("no consumer
  underrun guard", ~line 2017), which was marked "mostly superseded" with exactly this
  residual: "a 68k DMA outlasting the ~200-sample ring lead mid-sample — re-evaluate".
  The study *is* that re-evaluation: the residual is real, and worse than C4 assumed
  (not just stale replay — a permanent lap-latch the refill can't see). Annotate C4
  when R1 lands.
- **R2 (cost meter / telemetry)** — adjacent to "Worst-tick shortening… profile what
  dominates" (~line 2518) and the CANNOT-BE-SETTLED-STATICALLY emulator items
  (A2 runtime check, bank-latch hunt, DAC worst-tick profiling, ~lines 120-130). R2 is
  the instrumentation those items keep needing; it does not duplicate them.
- **R3 (log domain)** — the deep-audit **E-now-1** entry (~line 2046) already cited
  "MDSDRV 256 steps/semitone" as frontier consensus, but E-now-1 closed on shipping
  detune+portamento *in f-num units*. R3 is the un-captured correction to that
  representation — new work, supersedes nothing in the file except the unit system.
- **Multi-tick tempo (ruling §3.2)** — interacts with **review item 25's H1
  correction** (~line 2568: per-channel tempo gate is NOT redundant; mid-frame `$F3`
  broadcast). Any tempo-model change must carry that correction forward.
- **FM3 special mode** — already SKIP/DEFER in the deep audit §E (~line 2109, "CH3
  special mode (someday; niche, complicates FM3 SFX voice arbitration)"); study concurs.
- **68k-resident sequencer** — already SKIP in §E (~line 2105); study's core.md #12 /
  sfx-and-gaps both concur from source.
- **E5 7th RegDelta group, D1/D4/D5/D6/D7** — untouched by the study; still package 4's
  cluster (and DEFERRED_WORK §6 near the top confirms D2 is DONE — don't re-plan).
  Note R6's transpose work *pairs* with D4 (PSG `sc_transpose`) — sequence R6 after
  package 4.
- **Polyphonic PCM / mixing (format-toolchain #18)** — already the known "real gap"
  (sound-driver-comparison memory; deep-audit E2/E3 record the single-voice
  ratification). The study adds honest cycle numbers (~16 kHz for 2 streams with R9
  banked) for whenever that bet is ever revisited. Nothing new to track.
- **Seraph-has-no-Aeon-exporter correction (study §9)** — matches the S0-banked,
  unstarted state in the Seraph banking queue; a fact correction, not a work item.

Genuinely NEW (no DEFERRED_WORK entry, no package): R3 (as a representation change),
R4's rate half, R6 (all four format items), R7, R8, R9, R10, R11, and the §3 rulings.
This triage doc is their capture point until they get plans; if any are ruled in,
add DEFERRED_WORK entries per the maintenance protocol when the work is scheduled.

---

## Appendix — the Harmony study (out of scope here)

The companion `2026-08-07-harmony-framework-study.md` is a GameMaker classic-Sonic
*framework* read, not a sound-driver study: its yield is player physics defects (roll
animation at half speed — confirmed), rendering techniques (per-band scroll-factor
ramp, marker-relative rebase), and dev tooling (Oracle/Aurora candidates). It contains
effectively zero sound-driver content and none of it maps onto the sound packages —
its items belong to the player/rendering/tooling tracks and should be triaged there.
