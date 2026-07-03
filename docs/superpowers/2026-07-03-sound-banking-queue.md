# Sound Design-Banking Queue — 2026-07-03

**What this is:** the canonical record of the 2026-07-03 sound design-banking session
(limited Fable access; same pattern as `2026-07-02-design-week-queue.md`). Each package
gets a full research pass (all 8 reference disassemblies + online + modern, per
CLAUDE.md), a spec in `docs/superpowers/specs/`, a user review gate, and a
cold-executable implementation plan in `docs/superpowers/plans/` — so any future
session can execute without re-deriving anything.

**Branch:** `feat/sound-design-banking` (worktree, based off `feat/sfx-fidelity` —
NOT master, because sfx-fidelity carries the Stage-A doc state and is itself awaiting
the user's by-ear PASS → merge. Merge order: sfx-fidelity → master, then this branch.)

**Grounding:** the 2026-07-01 review pair
(`2026-07-01-sound-engine-review-findings.md`, `2026-07-01-sound-specs-review.md`) +
a full-repo open-items sweep (2026-07-03). The specs review's ranked top-10 is the
spine; items 4/5/6/10 already shipped in the sound-perf phase, item 8 (MEV_EXT) was
already reserved, and Stage A closed the retrigger policy — leaving the packages below.

## Decisions made this session (user, 2026-07-03)

1. **Scope:** packages A–D (now **1–4**) banked as spec+plan; doc-sync (E, now **0**) executed inline in this
   session; procedural ambient CUT; distance attenuation DEMOTED; MegaDAW (Phase 6)
   stays deferred (blocked on content sourcing).
2. **DAC format bet RATIFIED:** single voice + pre-mixed composites (2026-06-24 spec
   §2.2) confirmed; sampled-SFX-over-drums accepted as foreclosed; descriptor
   insurance (`ds_vol` + 2 reserved mix-cursor bytes) rides with package 3.
3. **Jingle policy: MID-SONG RESUME.** After a 1-up jingle, level music resumes
   where it left off (S1/S2 behavior, exceeds S3K's restart annoyance).
   **Mechanism correction (engine-internals research, same day):** the 512 B `$1B00`
   buffer named at decision time NO LONGER EXISTS — the 2026-07-02 A.3 repack already
   consumed it for the code-ceiling raise (SeqChannels now occupy that range). No
   snapshot buffer is needed: our SFX tier is SEPARATE RAM from the music SeqChannels
   (unlike SMPS, where the jingle overwrites music track RAM — the whole reason S2
   copies 470 B). Resume = freeze the sequencer in place (`SND_SEQ_ACTIVE=0`; the
   live SeqChannels ARE the snapshot) + play the jingle on SFX-tier channels + unpause
   at jingle end. Zero-byte snapshot, exact-position resume. Long takeover songs
   (invincibility, drowning countdown) remain full music loads; swap-back restarts
   level music (classic behavior in every reference game). The RAM arbitration is
   therefore MOOT — both claims are satisfied.

## Package queue (execution order)

> **RENUMBERED 2026-07-03 (user request, all-numeric):** doc-sync E → **0**; packages
> A/B/C/D → **1/2/3/4**; 5/6 unchanged. Historical Log entries and commit messages below
> keep the original letters — they are records, not live references. Anywhere else in the
> repo, "package N" uses the numeric scheme.

| # | Package | Deliverables | Status |
|---|---------|-------------|--------|
| 0 | Doc-sync + format hardening | inline edits, this branch | **DONE** (2fb0e4c + validity rules) |
| 1 | **Game-Feel Moments** — pause/unpause, song-finished contract (`SND_STAT_*` mirror), jingle push/pop (1-up/invincibility/drowning) w/ mid-song resume snapshot, tempo-scalar reset-on-load semantics, PCM-jingle bank/FM6-mode rules, 512 B buffer arbitration, command-API v2 (absorbs the outgrown `2026-06-16-sound-command-api.md`) | spec + plan | **BANKED** — spec APPROVED (user, 2026-07-03) + plan `plans/2026-07-03-sound-game-feel-moments.md` |
| 2 | **SFX Stage B/C** — per-SFX `sfh_gain`/`sfh_duck`/`sfh_cap`, non-latching priority (bit 7), continuous-SFX class (`SHF_CONTINUOUS`, spindash charge + drowning warning), instance discriminator for cap>1 multi-channel | plan (+ small spec addendum to `2026-07-02-sfx-fidelity-and-mixing-design.md` §5) | **BANKED** — addendum APPROVED (user, 2026-07-03) + plan `plans/2026-07-03-sfx-fidelity-stage-bc.md` |
| 3 | **DAC drum-library readiness** — descriptor `ds_vol` + reserved mix-cursor bytes, Bank-D engine-table co-location hook (`gen_sound_tables.py` data-only twin), dead 68k table removal ~~(already resolved — verified 2026-07-03)~~, authoring guidance | plan (+ ratification amendment, done in 0) | **BANKED** (`plans/2026-07-03-dac-drum-library-readiness.md` — no spec gate; rides the ratified DAC spec) |
| 4 | **Correctness batch** — surviving audit bugs: D1 (PSG pitch-mod noise-route gate), D2 (zeroed `sc_dur_default` 255-tick note), D4 (`Psg_NoteOn` ignores `sc_transpose`), D5 (PSG env attack one frame late), D6 (stale `sc_repeat_count` across song loop), D7 (`MEV_REPEAT_END` operand 0), B3 (AM-enable byte fidelity), B5 ($E7 tone-tracked noise sweep), E5-runtime (SSG-EG 7th RegDelta group), F3/F4 ~~(verified already fixed/moot 2026-07-03 — SfxTable is LIVE; D2/D3/D5 also already fixed)~~ | plan | **BANKED** (`plans/2026-07-03-sound-correctness-batch.md` — no spec gate; rides the audit findings doc) |

**Order rationale:** package 1 defines contracts (song-finished, push/pop, continuous-SFX seam,
API v2) that 2 references; 3 is mostly mechanical post-ratification; 4 is independent
and last. 0 ran first so research agents read truthful docs.

**Explicitly out of scope:** §6.4 section-aware banking (folds into A only where the
jingle/bank rules require it; otherwise stays Phase-5-deferred), §6.5 attenuation
(demoted), §6.6 ambient (CUT), Phase 6 MegaDAW compiler (deferred, content-driven),
H3 + rendered S3K A/B (pending by-ear), GATE articulation, per-frame pitch/vol
envelopes Phase-3a #2/#3 (build-on-demand).

**SECOND WAVE (same day, user-directed):** two more packages so NO sound-driver item
hangs afterward (Seraph/MegaDAW excluded — its own project):

| # | Package | Deliverables | Status |
|---|---------|-------------|--------|
| 5 | **Audio production suite** — build-time mastering + ladder-aware staging + TL-filter-sweep generator + PSG sub-bass + generative variation (Tier 0, zero bytes); kick-sidechain pump + autopan (Tier 1, ~70 B); echo bus + detune-unison + ExtCh3 op-tracks (Tier 2, budget-gated on measured post-1-4 headroom); CSM = door-only (Timer-A conflict); Paprium dismissed (fabricated) | spec `specs/2026-07-03-sound-production-suite-design.md` (user-APPROVED) + plan `plans/2026-07-03-sound-production-suite.md` | **BANKED** |
| 6 | **Closeout sweep** — GATE→NOTEFILL import translation, $28 guard + cold-boot pan seed + FM env seam (~25 B), coverage-debt tests, HCZ2 loop-residual audit, bank-latch corrupter hunt (bounded), boundary-tick audibility check, formal dispositions (§6.4 clarified-closed, Phase-4 closed, defensive-upload closed, H3 closed on user PASS, worst-tick ACCEPTED) | plan `plans/2026-07-03-sound-closeout-sweep.md` (no spec needed — dispositions embedded) | **BANKED** |

Post-5+6 state: sound backlog EMPTY except content-gated (drum authoring via C's runbook,
Seraph export retarget). Phase-4 question answered: adaptive FM6/DAC IS shipped
(dedicate + drain-gated time-share); the "richer modes" remainder closes with it.

**ALL FOUR PACKAGES BANKED 2026-07-03.** Execution order stands (1 -> 2 -> 3 -> 4, all
after feat/sfx-fidelity's by-ear merge). Every plan is cold-executable
(subagent-driven-development per plan headers); emulator gates are controller-session
steps marked FOREGROUND in each plan.

## Log

- 2026-07-03: Session scoped (A–D + inline E), DAC bet ratified, mid-song resume
  chosen. Worktree + branch created; baseline build green (557125 bytes,
  SOUND_DRIVER_ENABLED=1 DEBUG=1).
- 2026-07-03: Packages C + D plans written (research-verified same day: C's dead-tables
  item and D's D2/D3/D5/F3/F4 were ALREADY resolved by earlier phases — plans document
  this so no future session re-fixes them). B addendum (spec §7) resolved the sfh_cap
  discriminator (single-channel-only rule) and pinned Stage C to a re-ping countdown.
- 2026-07-03: E part 2 — format validity rules (normative, packer-cited, MegaDAW-exporter
  contract) appended to the music-expression spec; spot-checked 3 citations against
  song_packer.py before commit. E COMPLETE — note MEV_EXT reserve + master-spec amendment
  header + E-now closures were ALREADY done by earlier passes (verified, not duplicated).
- 2026-07-03: E part 1 — ratification records (ARCH §6 index row + §6.2, master spec
  amendment header, DAC spec header, DEFERRED_WORK ×2), §6.5 DEMOTED note, §6.6 CUT
  note, §6.7 continuous-SFX unbundled → Stage C pointer, ARCH §6 index-row DEFERRED
  clause refreshed (music-expr P2 shipped items moved to SHIPPED).
