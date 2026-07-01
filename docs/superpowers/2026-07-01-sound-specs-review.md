# Sound Engine Spec-Quality Review — best-in-class, and right for a Sonic game? (2026-07-01)

Companion to `2026-07-01-sound-engine-review-findings.md` (the code review). This reviews the DESIGN DOCS.
T-references (T0.1, T1.4…) point at that findings doc.

**Bottom line:** The *engine-mechanism* specs (music expression, DAC format revision) are genuinely
best-in-class designs with exemplary amendment discipline. The problem is at the two ends: (1) the older
vision docs (master sound spec, ARCH §6.2/6.3) still promise a different engine than the one the newer
specs decided to build, and (2) **the classic Sonic game-feel moments — pause, 1-up jingle resume,
invincibility swap-back, drowning restore — have no spec'd mechanism anywhere**, while the spec suite
chases novel game-feel (procedural ambient, distance attenuation) no Sonic game needs. The specs are
maximal where a tracker would be maximal and thin exactly where a *Sonic game* lives.

## (a) Verdict per spec doc

| Doc | Verdict | Why |
|---|---|---|
| `2026-06-23-music-expression-engine-design.md` | **SOUND** (minor staleness) | Best doc in the suite; "design for C, build for A" executed for real. Staleness: §3.3 macro grammar (`$80-$83`) vs shipped `TAG_MAC_*` `$E0-$E3` w/ 2-byte BE loop; §9.1 SeqChannel 39→56 vs shipped 58; companion recovery doc's "code-banking technique" proven UNSOUND — needs a data-only-banking amendment; portamento "zero new bytes" true for state, contradicted by the ~323 B resident-code reality. |
| `2026-06-24-dac-drum-format-revision-design.md` | **SOUND** — one unratified bet | The 2026-06-25 raw-8bit amendment is how specs should be maintained. §2.2's rejection of runtime mixing (pre-mixed composites) is the one irreversible format decision, contradicts three live docs, and the 9-byte descriptor has no `ds_vol`/mix-cursor. Ratify BEFORE a real drum library is authored. |
| `2026-06-16-sound-driver-design.md` (master spec) | **STALE in load-bearing sections** | §5 (BRR primary, N-channel mixer, >8-bit mix+dither, pitch-shifted PCM SFX), §6 (division-based portamento — rejected by music-expr), §5 busy-poll policy (contradicts ARCH §6.3 + shipped code), §4.3 (three-mode FM6 incl. permanent mixer), §14 (polyphonic-samples criterion) all superseded. No amendment header — anyone reading it cold designs the wrong engine. |
| ARCH §6 | **NEEDS REVISION** | §6.1 body current; DEFERRED paragraph stale (detune/LFO/tempo/fade shipped). §6.2 still advertises DPCM/multi-channel mixing/pitch-shifted SFX. §6.10 says "Flamedriver". §6.3 busy-poll note conflicts with master spec §5 — canonize the shipped fixed-spacing choice, record busy-poll as first suspect on real HW. |
| Phase-2 plans (global + pernote) | **SOUND as plans** | Shipped except porta. Task B1 tempo design is right; T1.4 is an implementation defect, not a plan defect. |
| `2026-06-28-portamento-resume.md` | **SOUND, turnkey** | Correct root cause, fix, and verification. Execute as written. |
| `2026-06-16-sound-command-api.md` | **OUTGROWN** | Live API grew past it (FADE/TEMPO, 8-deep ring); the game-feel command set (pause, jingle push/pop, song-finished) has no home. Needs a v2. |
| `2026-06-16-sound-z80-ram-map.md` | **STALE** (known, F1) | Headroom wrong twice over (docs 216 B; truth 138 B). |

## 1. Spec-vs-spec contradictions (beyond the known DAC-mixer one)

1. **DAC mixer**: DAC spec §2.2 rejects runtime mixing ↔ ARCH §6.2, master spec §5/§4.3/§14, DEFERRED E2/E3, ARCH §6.1-DEFERRED all still promise it.
2. **Portamento algorithm**: master spec §6 (16÷16 restoring division) ↔ music-expr §2 (linear-in-fnum, correct). Master spec never amended.
3. **YM busy-poll**: master spec §5 "DO busy-poll" ↔ ARCH §6.3 "deliberately fixed nop spacing". Shipped = ARCH. Canonize; record the caveat.
4. **DAC codec**: master spec §5 "BRR primary" ↔ amendment raw 8-bit; DEFERRED E3 still says re-adopt DPCM.
5. **Macro grammar bytes**: music-expr §3.3 `$80-$83` ↔ shipped `TAG_MAC_*` `$E0-$E3` + 2-byte BE loop. Update the spec to the shipped grammar (content will be authored against it).
6. **Fade-to-previous**: music-expr §7 lists it as a T4 deliverable ↔ shipped API is FadeOut/FadeIn only, and no doc defines "saved song state". Embryo of the jingle push/pop gap.
7. **Headroom**: DEFERRED F1/F5 216 B ↔ reality 138 B.
8. **SeqChannel size**: music-expr §9.1 "39→56" ↔ ARCH "58-byte end-state".
9. **Continuous SFX placement**: parked in monolithic Phase 5 ↔ near-term core-feel need (priority contradiction; unbundle).

## 2. Best-in-class test, per capability area

- **Music expression — EXCEEDS the field once portamento lands.** Shipped set already beats S3K SMPS, Flamedriver; matches MDSDRV's macro-track model. Zyrinx's two secrets = detune (shipped) + porta (turnkey). No structural gap. Small texture gaps: PSG note-fill nonexistent (T1.3), per-note vibrato onset/sign fidelity (T1.9, +2 B/channel — schedule w/ porta budget). Echo/delay correctly an authoring pattern. Perf caveat to SPEC as an invariant: a fully-lit expression frame costs ~half the Z80 frame in DAC stall — "expression must not degrade DAC below X kHz", enforced by env write-on-change.
- **SFX — best-in-class engine, two Sonic-critical gaps**: continuous/looping SFX (spindash charge, drowning warning) parked in Phase 5; retrigger policy undecided (today: up to 3 concurrent instances; classic drivers restart-same-channel). Sampled SFX foreclosed by the DAC decision (acceptable for classic-faithful FM/PSG SFX — but ratify). Authoring note: ring SFX alternates L/R per pickup.
- **DAC/percussion — best-in-class for the chosen shape.** 18.4 kHz DMA-survival beats S3K (~10-13 kHz, scratches under DMA), Echo (10.6k), XGM2 per-voice (13.3k). Composites cover music-internal overlap; the casualty is sampled-SFX/voice-over-drums only.
- **Game-feel integration — inverted priority.** Spec'd Phase 5 (banking, crossfades, distance attenuation, procedural ambient) exceeds every commercial game — while pause, 1-up, invincibility-end, drowning-recovery have NO mechanism. S3K ships pause/unpause + speed-shoes tempo + fades; S1/S2 ship mid-song 1-up resume (S3K's restart regression is a famous annoyance — resume is a cheap exceed).
- **Mixing/priority — adequate and spec'd.** Distance attenuation: nice-to-have, keep cheap and late.
- **Authoring pipeline — right architecture, contract at risk.** The packer is the de-facto format authority with hang-the-Z80 foot-guns (T0.5) where the format spec is silent. State the validity rules (single-level repeat, MacNext-before-MacLoop, music-legal set, offset bounds) in the spec — MegaDAW's exporter will be written against the SPEC.

## 3. (b) Sonic-playthrough gap list

| Moment | Status |
|---|---|
| Title/menu music | Covered |
| Level start fade-in | Covered (T1.10 blip aside) |
| Level music + expression | Covered; porta pending |
| Rings/jump/skid/spring SFX | Covered. Ring L/R alternation = spec authoring note |
| Spindash charge (continuous) | **Half-GAP** — spec'd but parked in Phase 5; pull forward. Retrigger policy decision lands here |
| Monitor jingles | Covered (SFX) |
| **1-UP jingle → music resumes** | **GAP** — no push/pop, no saved-state definition. Floor = restart (needs only song-finished notification); exceed = mid-song snapshot — the dead 512 B `$1B00` song buffer is the natural home, BUT the arch roadmap wants that RAM for the code-ceiling raise. **Arbitrate explicitly before the RAM-map rework.** |
| **Invincibility swap + swap-back** | **GAP (half)** — swap-in = PlayMusic; the flow (68k timer + restart) unspec'd. One paragraph near §6.9 |
| Underwater | Covered by omission (classic: no change) |
| **Drowning jingle → surface → restore** | **GAP** — push/pop family + tempo-ramp interaction (does the global tempo scalar reset on song load?) must be spec'd |
| **Speed shoes tempo-up** | **Design RIGHT, implementation broken (T1.4).** Spec holes: (1) scalar auto-reset on song load, (2) SFX cadence explicitly NOT scaled |
| **Pause / unpause** | **GAP — the worst.** No Sound_Pause/Unpause (freeze ticks + mute + resume w/ re-assert). StopMusic-as-pause is destructive AND currently kills the driver (T0.1). ARCH §9.13 promises "keep sound driver running" with no sound-side counterpart |
| Act clear (stop → jingle → tally) | Mechanism covered BUT T0.1 makes it a driver-killer today, and **no song-finished contract** — mirror `SND_SEQ_ACTIVE` into `SND_STAT_*` (+~6 B) |
| Death jingle / game over / continue | Covered (same caveats) |
| Boss/stingers/transitions | Spec'd (§6.9 + Phase 5), reasonable |
| PCM-jingle interactions | **Unspec'd corner**: jingle w/ FM6=DAC drums interrupting a STREAM FM6=FM song crosses bank + FM6-mode boundaries; snapshot must include `SND_SONG_BANK`/FM6 mode — or restrict jingles to drum-free |

## 4. Pigeonhole hunt (spec-level)

1. **DAC single-voice + composites** — right call for this game; RATIFY, and take the free insurance: add `ds_vol` + 2 reserved mix-cursor bytes to the descriptor before the drum library exists (~3 B/descriptor, zero code).
2. **MEV opcode space nearly exhausted** (~4 slots left for the format's life). **Reserve `MEV_EXT` (extension prefix + subcode byte = 256 more slots) NOW.** One spec line.
3. **59.06 Hz frame clock** — a spec decision nobody made deliberately; all music ~1.4% slow. Fix to N=125 (59.85 Hz) + write the wall-clock contract (what a macro step/env step/tempo unit means). Re-verify MT after. **PAL is already won by construction** (Timer-A off YM clock → ~0.9% drift vs 17% for VBlank-locked) — no spec claims this win; claim it.
4. **Timer A forecloses CSM mode** — correctly skipped; ch3-special-without-CSM stays reachable via MEV_REGWRITE (recorded).
5. **Envelope/macro ceiling vs MegaDAW** — no pigeonhole. Furnace-macro-class. (Only >1 independent slot[1] stream per channel is inexpressible; tag-interleaving covers it.)
6. **PSG** — no pigeonhole (MEV_PSGNOISE reaches the full control byte). PSG-as-PCM should be formally CUT, not left dangling.
7. **SSG-EG runtime sweep** (E5 half) — additive extension, fine deferred.
8. **Jingle-snapshot vs RAM-reclaim collision** — see playthrough table; arbitrate in the game-feel spec.

## 5. (c) Top 10 spec changes, ranked ([DOC] = fix the doc, [BUILD] = build it)

1. **[DOC+BUILD] Write the missing "Game-Feel Moments" spec** — pause/unpause, jingle push/pop + song-finished mirror, invincibility/drowning/1-up flows, PCM-jingle bank rules, 512 B buffer arbitration. ~40-60 B Z80 (pause + status) + 68k glue for the restart floor; +~30 B & the 512 B buffer for mid-song resume.
2. **[DOC] Single doc-sync pass with amendment headers** — master spec, ARCH §6, music-expr grammar, headroom, RAM map. Folds in the code review's drift list; zero bytes.
3. **[DOC→decision] Ratify the DAC single-voice bet + descriptor `ds_vol`/reserved bytes** before drum authoring.
4. **[DOC+BUILD] Frame clock → N=125 (59.85 Hz)** + wall-clock contract; re-verify MT.
5. **[BUILD] Execute the portamento resume plan** (relocate resident, bank DATA ~200-260 B, B2/B3, soak).
6. **[BUILD] Tempo borrow-loop fix (T1.4)** + **[DOC]** reset-on-load & SFX-unaffected semantics.
7. **[DOC+BUILD] Unbundle continuous SFX from Phase 5** (spindash charge, drowning warning, ~25-40 B) + **decide retrigger policy** (recommend classic restart-same-channel, ~25-35 B).
8. **[DOC] Reserve `MEV_EXT`** + publish the remaining-opcode budget.
9. **[DOC] Promote packer validity rules into the format spec** (pairs with T0.5 fixes).
10. **[DOC] Spec the expression-vs-DAC perf invariant** + env write-on-change (~10 B) as enforcement.

(Gating everything: T0.1 — act clear and death, the game's two most common music transitions, currently kill the driver.)

## 6. (d) CUT list

- **FADE_CROSSFADE** (two live sequencer contexts — wildly over budget; respec as fast out→switch→in; keep CUT + STINGER).
- **Procedural ambient soundscape (§6.6)** — near-incompatible with single-voice DAC (a random ambient PCM interrupts the music's drums); cut or re-scope PSG-only.
- **PSG-as-PCM aux channel** (master spec spike #2) — cut.
- **BRR codec, >8-bit mix + dither, pitch-shifted PCM SFX, half-rate voices** — children of the rejected mixer; cut from roadmap (`ds_codec`/`ds_rate` reserved bytes keep the door open at zero cost).
- **Software echo/reverb Z80 delay line** — authoring pattern (delayed ghost channel), free; cut the engine feature.
- **Verified Z80 bus write read-back** — superseded by the shipped (clean-audited) mailbox protocol; keep Ristar-style retry note for future bulk copies only.
- **Distance attenuation (§6.5)** — demote below the game-feel layer, don't cut.

**Overall:** with portamento landed and the doc-sync done, no commercial Genesis driver matches this
feature union, and only modern homebrew (MDSDRV, XGM2) matches slices. The two moves that most change
the *game* are cheap and mostly paperwork: ratify the DAC decision across all docs, and write the one
spec nobody wrote — the ten sound moments of an actual Sonic playthrough.
