# Sound Performance & Budget Phase — Design (2026-07-01)

**Status:** APPROVED by user 2026-07-01 (design presented and signed off in-session).
**Source:** `docs/superpowers/HANDOFF-sound-performance-phase.md` (green-lit phase kickoff) +
`2026-07-01-sound-engine-review-findings.md` + `2026-07-01-sound-specs-review.md`.
All evidence figures below are from same-emulator A/B against the real skdisasm-built S3K
(music id $04) — see the handoff §5 for regeneration instructions.

## 0. Scope and decisions made

This phase closes the last audible gap between our HCZ2 rendering and real S3K, plus the Z80
budget recovery everything queues behind. Six work items, strictly ordered:

**A. budget recovery → B. rekey fix → C. vibrato/detune trio → D. DAC starvation →
E. portamento → F. tempo closure**, then a final rendered-audio A/B against real S3K.

A is first because the driver has ~6-10 bytes free and every fix needs bytes. B/C land before D
because they change the per-frame tick's work; D's cost reduction is measured against the final
tick shape.

User decisions locked during design:

1. **The 512 B `SND_SONG_BUF` at $1B00 is RECLAIMED for code headroom** (not reserved as a
   jingle-resume snapshot). Rationale recorded: the future game-feel spec can build jingle-resume
   RAM-light — freeze music ticks (state stays in the live SeqChannel structs) and play the jingle
   on SFX-tier slots via the existing steal/restore machinery — so reclaiming does not foreclose
   best-in-class resume.
2. **Portamento execution is IN this phase** (the turnkey 2026-06-28 plan), since the budget work
   and porta relocation touch the same banking machinery.
3. **DAC starvation approach = "cheap tick + Timer-B-paced drain"** (option B below), chosen over
   cost-reduction-only and fully-resumable-slices.

Out of scope: the game-feel spec (pause/jingle/song-finished — its own phase), DAC format
ratification (`ds_vol` descriptor bytes), the doc-sync pass beyond files this phase touches,
SFX retrigger policy.

## A. Z80 budget recovery (~780 B expected)

### A.1 Delete the COPY load path

`Snd_LoadSong` PATH A (COPY / SH_F_STREAM clear) serves only legacy bring-up content
(Song_Test / Ode demo); HCZ2 and MT both STREAM. Per the reclaim decision and the
clean-not-bolted-on rule, delete it whole:

- The PATH A code in `Snd_LoadSong` (z80_sound_driver.asm ~1120-1141): the `ldir` into
  `SND_SONG_BUF`, the RAM song base, the inline-patch-table wiring.
- `SND_SONG_BUF` / `SND_SONG_BUF_SIZE` (sound_constants.asm ~1292) and their asserts.
- `FmPatchInlineTable` (z80_sound_driver.asm ~1444, 64 B, self-described "CLEARLY-TEMP
  bring-up data").
- `SH_F_STREAM` becomes the only mode — remove the flag test; keep the header bit reserved
  (packer keeps emitting it set) so the header contract doesn't churn.
- Song_Test / Ode demo content: repack as STREAM if anything still references it (debug hotkeys,
  self-tests), else retire the data. The plan resolves which by grepping references.

### A.2 Bank remaining DATA tables (co-location pattern)

Data-only banking; the resident-code invariant (banked in-frame CODE is unsafe under 68k bus
contention) stays absolute.

- `DacSampleTable` (90 B) → co-locate in the DAC sample bank. Its reader (`Snd_StartSample`
  mailbox path) already switches to the sample bank; the descriptor read moves inside that
  bracket.
- `SeqOpcodeTable` (~64 B) → co-locate at the song-bank head, exactly like `FmPitchTableZ`
  already is (generator emits it per song bank; today there is one song bank).

### A.3 RAM repack + ceiling raise

With $1B00 gone, repack the RAM map upward and raise `SND_STATE_BASE` (the code ceiling,
currently $16F0) by ~512:

- Regions in order: code | state block | ring (256-aligned page) | sequencer state + channels |
  SFX channels | mailbox/status. Every boundary gets an overlap assert; the ring page constant
  and every hardcoded page byte ($17 in registers) are updated together.
- SeqChannel 58→60 and SfxChannel 62→64 (+2 B each for item C: `sc_mod_wait_raw`,
  `sc_mod_delta_raw`). 36 B RAM total (11 seq + 7 SFX slots). The shared-offset assert between
  the two structs is extended to the new fields; both `_len` asserts updated.
- The stale Z80 RAM-map spec (`2026-06-16-sound-z80-ram-map.md`, DEFERRED F1) is REWRITTEN as
  part of this change with an amendment header — not deferred again.
- **Mandatory runtime boot test after the repack** (AS does not auto-align; an odd `ds.b` crashes
  the next word field at runtime while build+asserts stay green).

Expected recovery: 512 (buffer) + ~64 (`FmPatchInlineTable`) + ~90 (`DacSampleTable`) + ~64
(`SeqOpcodeTable`) + COPY-path code ≈ **~780 B**. Consumers: porta ~323, drain machinery
~80-120, rekey ~10, vibrato ~20-25, env write-on-change ~10, remainder = headroom for the
deferred small gates.

## B. Key-off-before-key-on for bare notes (~10 B gross, less after reclaim)

The YM2612 key-on is edge-triggered; keying an already-keyed channel is a chip NO-OP. Measured:
61 of 64 melody notes per channel get no EG retrigger; the mix bed never goes digitally silent
(ref: ~25% of frames), +2.1 dB bed RMS.

- In the **single key-on chokepoint** `Fm_NoteOnFreq.do_keyon` (sound_fm.asm ~833-861): if
  `SCF_KEYED` is set, `call Fm_NoteOff` before the $28 key-on write. Every producer (bare notes,
  ModUpdate rekeys, NOTE_RAW) gets a true 0→1 EG edge.
- Delete the now-redundant `SND_REKEY_OFF_THEN_ON` conditional block in `Seq_RekeySingle`
  (sound_sequencer.asm ~427-448) and NOTE_RAW's explicit off→on (~1166-1169) — the chokepoint
  covers both. The build lever constant is removed (one behavior, no dormant paths).
- The no-attack/tie path is untouched **by construction**: bit-7 held notes `ret` out of
  `Seq_Op_NoteDur` before `Seq_HookNoteOn` and never reach the chokepoint.
- The FM6-dedicate gate stays ahead of the keyon section (no chip $28 while DAC owns ch6).

## C. Vibrato/detune fidelity trio

### C.a Per-note modulation re-arm

`Mod_ReArm` (sound_sequencer.asm ~585) currently reloads accum/steps/speed but neither the
delay (`sc_mod_wait` — honored only on a channel's first note ever) nor the delta sign (flipped
in place by direction reversal; next note can start phase-inverted). S3K reloads both every note
(13-14 flat frames per melody note; short notes never vibrate).

- New struct fields `sc_mod_wait_raw` and `sc_mod_delta_raw` (+2 B both structs, RAM budgeted in
  A.3). `Seq_Op_ModSet` latches them; `Mod_ReArm` reloads `sc_mod_wait` and `sc_mod_delta`
  (original sign) from them on every note-on.

### C.b Unipolar-up contour

Our `Mod_Advance` renders a bipolar triangle (±depth around base, accum seeded 0, initial
half-period). S3K's `zDoModulation` is unipolar-UP (base → +depth → base): where encodings
match, ours doubles apparent depth (96.7 vs 47.6 cents on FM3) and biases pitch ~24c flat during
vibrato.

- Match `zDoModulation`'s accumulator semantics exactly, derived from the skdisasm source
  (accumulator seeded at +delta, S3K's step-count/sign-flip order), in
  `Mod_ReArm`/`Mod_Advance`. The plan step starts by reading `zDoModulation` and writing the
  reference contour table (frame → cents) that verification will compare against.

### C.c Pitch-table renormalization (deliberate engine-encoding change)

`gen_sound_tables.py` normalizes fnum into [·, 2047] (block 0 spans fnum 644-2044); S3K uses
canonical 644-1214 per block. On doubled-fnum encodings every fnum-denominated delta
(modulation, detune, porta) is worth HALF the cents: bass vibrato 36.3c vs ref 72.5c; FM3's
echo detune renders 5.4c vs S3K's 10.8c.

- Change `fnum_block()` to normalize to **fnum ∈ [644, 1287]** (halve while ≥ 1288), block
  clamped 0-7 (lowest notes may sit under 644 in block 0 — fine, matches S3K's own table floor).
- Transparent to packed content: songs reference pitch **indices**; NOTE_RAW songs (MT) embed
  raw $A4/$A0 bytes and bypass the table entirely; `MovingTrucks_PitchTable` is separate.
- Bonus: canonical fnums leave ±700 fnum of in-block headroom, so small deltas never need block
  crossings — `Mod_Advance`'s block-boundary churn disappears and the deferred block-edge clamps
  (B1-class) become near-moot (keep the cheap clamp anyway as a safety).
- Verification at two levels: a generator unit test asserting all 95 indices decode to the same
  Hz (±0.5 cent) as before, then rendered depth-in-cents vs ref on both encoding classes.

## D. DAC starvation fix (approach B: cheap tick + Timer-B-paced drain)

While `Sequencer_Frame` runs, the last sample stays latched on $2A — drums freeze. Measured:
ref loses 18.9% of drum airtime to holds; ours 45.3% (intro) / 63.5% (melody) with full-frame
16.7 ms freezes ref never has (ref max gap 5.6 ms); a 93 ms tom smears to 213 ms. Tick cost
under HCZ2 load: ~16k cycles median, ~57k worst.

Physical constraints (from code exploration): the 256 B ring can **drain** during the tick with
no bank switch (pure RAM→port) but cannot **refill** (window held on the song bank); full ring
≈ 16.9 ms of audio; ring lead equilibrium ~160 samples under max scroll; YM **Timer B is
completely unused** — free as the elapsed-time marker.

### D.1 Cheap tick

- **TL write-on-change**: `FmEnvUpdate` → `Fm_SetVolume` currently rewrites all carrier TLs
  every frame an envelope is active (sustain and rest paths re-emit unchanged values). Add a
  last-emitted shadow compare; skip the emit when unchanged. `PsgEnvUpdate`/`Psg_SetVolume` get
  the same gate. (~1k cycles/channel saved on sustained envelopes.)
- **Cached env-body pointer** (skip re-walking the envelope header per frame).
- **Fast inactive-channel skip** in the `.chan_loop` dispatch.

### D.2 Timer-B-paced interleaved drain

- Program Timer B once as a fixed elapsed marker (~2 ms class; exact period chosen in the plan
  from cycle math and verified by measurement).
- At each per-channel seam in `Sequencer_Frame`'s `.chan_loop` (and the `Sfx_Frame` slot seam),
  poll the YM status byte for Timer B overflow (cheap: the status read is the same port the
  Timer A poll already uses). On overflow: jump to a resident, cycle-padded drain burst that
  emits ring samples to $2A at the true ~195-cycle/sample pace — burst size = elapsed time /
  sample period (a constant, since the timer period is fixed) — re-arm Timer B, continue the
  tick. Gated on `SND_DAC_PHASE` (no ring when DAC idle).
- Burst size (~30 samples per 2 ms) stays well under the ~160-sample lead equilibrium; the
  existing post-tick bulk `.refill` restores lead.
- The 25-35 ms patch-change worst case (DEFERRED "boundary-tick patch pre-loading") happens
  inside ONE channel's work, so the seam poll alone won't catch it: add a poll inside the
  patch-register write loop too.
- Worst-case drum hold drops to ~one poll interval (~1-2 ms) vs ref's own 5.6 ms max gap.

### D.3 Evaluate-then-decide: hit-scoped $2B / FM6 duty

Ref toggles $2B per hit and keys FM6 off between hits (42-72% duty vs our always-armed 97%).
Our parked $2A value ($80 center) is already DC silence, so the expectation is **reject with
rationale**. Decide by rendered A/B (inter-hit noise floor), not by assumption; adopt only if
audible/measurable.

## E. Portamento (turnkey plan execution)

Execute `docs/superpowers/plans/2026-06-28-portamento-resume.md` as written: relocate
`Porta_Apply` (~257 B) + `Fm_FnumApplyDelta` (~66 B) resident — which also closes **T0.3**, the
last banked-code hazard — delete `engine/sound_banked_z80.asm` + its include; finish B2
(`MEV_PORTA = $F5` const + `Seq_Op_Porta` + dispatch slot) and B3 (packer `Porta(Event)` +
tests); verify per that plan (3000+ frame soak with PC never in $8xxx/$Cxxx, rendered glide
audio, $0000 reset-vector trap never fires).

Ordering interaction: porta deltas are fnum-denominated, so E lands **after** C.c and its
depth/glide verification uses the canonical table.

## F. Tempo closure

Heavy ticks push the next Timer-A poll late — the measured ~1.5% slowness on clean data beyond
the known ~0.5% idle-poll residual. After D lands:

1. Re-measure drift vs ref over 15+ s.
2. Retune `SND_TIMERA_N` to hit **effective** 59.92 Hz — measured in-emulator, not computed
   (the deferred note records N=136 measuring ~59.63 Hz where naive math said otherwise).
3. Re-verify MT feel/tempo after (it was verified against the old clock).

Target: drift vs ref < 0.3% over 15 s.

## G. Verification protocol (binding, from the handoff)

- Reference = skdisasm-built S3K in oracle, **NOP-patched** (`sonic3k_muted.bin`, patch
  `13 C0 00 A0 1C 0A/0B/0C` → NOPs ×3 sites), trigger via Z80 write `0x1C0A = $04`. ALWAYS
  purity-check every capture (per-second key-on histogram + content) before comparing.
- Oracle Z80 addresses need `0x`/`$` prefixes. Debug hotkeys: UP=HCZ2, A=MT, C=drumtest,
  START=stop, B=SFX cycle. `SOUND_DBG_MIRROR` stays OFF for captures.
- All fidelity claims by **rendered audio numbers** (vgm2wav: band RMS, per-hit RMS, duty/stall
  histograms, spectral centroid, cents series), note-matched per channel — never register
  counts alone. Recreate the 2026-07-01 analysis scripts (clean_purity / dac_stall /
  dac_perburst / drum_loud / melody_cmp / melody_regs / gate_vib / vib_series / spectral /
  prominence) from their descriptions if the scratchpad is gone.
- Regression gates on every merge-bound step: green `SOUND_DRIVER_ENABLED=1 DEBUG=1` build
  (plain `./build.sh` also has sound ON by default now), 803+ pytest in `tools/`, MT A/B
  unchanged (a REAL gate here — C.c and F both touch things MT was verified against), SFX
  steal/restore behavior, runtime boot after every RAM-map/struct change.

## H. Success criteria (phase gate, from the handoff §3)

1. Melody notes retrigger: key-off count ≈ note count per channel; ~25% inter-note digital
   silence returns to the mix bed.
2. Drum airtime lost to holds ≤ ~20% (parity with S3K's own driver); no full-frame freezes; tom
   hit duration within ~10% of ref; user confirms drums sit right by ear.
3. Vibrato: flat delay frames per note match ref (13-14 on the melody); unipolar-up contour;
   depth in cents matches ref on BOTH encoding classes; FM3 chorus width ~10.8 cents.
4. Tempo drift vs ref < 0.3% over 15 s.
5. Portamento: the 2026-06-28 plan's own verification passes (soak + rendered glides).
6. All regression gates green (§G).

## I. Risks

- **RAM repack** (highest): every region moves at once. Mitigation: it lands first, alone, as
  its own commit(s) on the branch; boundary asserts on every region; runtime boot test before
  anything stacks on it.
- **Drain-burst pacing**: mis-padded burst = drum pitch warble during ticks. Mitigation: A/B
  drum pitch during heavy ticks vs at-rest; the burst loop reuses the main loop's verified
  ~195-cycle padding discipline.
- **Pitch-table regen**: any generator slip shifts every note. Mitigation: the 95-index Hz
  identity unit test gates before any listening test.
- **Struct growth**: shared-offset assert between SeqChannel/SfxChannel extended first, so a
  drifted field fails the build, not the runtime.
- **MT regression surface**: C.c (table), B (rekey), F (clock) all touch MT-verified behavior —
  hence MT A/B as a standing gate, not a final check.

## J. Doc obligations bundled with this phase

Only what this phase touches (the full doc-sync pass stays a separate item): the Z80 RAM-map
spec rewrite (A.3), `ENGINE_ARCHITECTURE.md` §6 lines invalidated by A/D/E (banked-code file
deleted, COPY path deleted, tick/DAC interleave shape), DEFERRED_WORK updates (F1/F5 close,
E-item statuses, frame-clock item closes with F), and amendment headers on the superseded
handoff/plan docs.
