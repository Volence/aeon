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
| 1 | **Game-Feel Moments** — pause/unpause, song-finished contract (`SND_STAT_*` mirror), jingle push/pop (1-up/invincibility/drowning) w/ mid-song resume snapshot, tempo-scalar reset-on-load semantics, PCM-jingle bank/FM6-mode rules, 512 B buffer arbitration, command-API v2 (absorbs the outgrown `2026-06-16-sound-command-api.md`) | spec + plan | **EXECUTED** (2026-08-09, `sound-pkg1`) — engine tier + API v2 shipped, plus ride-alongs: R4 spread-bit fade rates ((rate<<4)\|cmd) and the user-ruled TimerA-DMA refill guard. Deviations recorded in DEFERRED_WORK's closing 2026-08-09 entry: resume = full FM voice re-upload (the plan's `sc_last_patch=$FF` has no runtime reader), auto-pop moved to Sfx_Frame's tail (double-push race), MEV_EXT dispatched via a `.coord` intercept (seam-1 HANDLER_SYMBOLS is a fixed list), §6.4 DEBUG assert omitted (resident ceiling, debug blob 6381/6384). Oracle gates = controller session. |
| 2 | **SFX Stage B/C** — per-SFX `sfh_gain`/`sfh_duck`/`sfh_cap`, non-latching priority (bit 7), continuous-SFX class (`SHF_CONTINUOUS`, spindash charge + drowning warning), instance discriminator for cap>1 multi-channel | plan (+ small spec addendum to `2026-07-02-sfx-fidelity-and-mixing-design.md` §5) | **EXECUTED** (2026-07-07, `feat/sfx-fidelity-stage-bc`) — all §5/§7 features shipped + oracle-verified. 2 plan defects fixed in review: sx_gain +58 detune aliasing; **bit-7 flag collided with 8-bit priority scale → SFXPRI_* rescaled to 7-bit (build-guarded)**. Jingle cross-rule → package 1. See spec status header. |
| 3 | **DAC drum-library readiness** — descriptor `ds_vol` + reserved mix-cursor bytes, Bank-D engine-table co-location hook (`gen_sound_tables.py` data-only twin), dead 68k table removal ~~(already resolved — verified 2026-07-03)~~, authoring guidance | plan (+ ratification amendment, done in 0) | **EXECUTED** (2026-08-10, `sound-pkg3`) — 12-byte `DacSample` shipped (append-only; ×12 stride kept the 8-bit lookup's exact byte count — resident blob unchanged, plain 6255 / debug 6381), all 10 descriptors + game-side size wall grown, seam-2 re-derived the head span ($607→$625) + MT/SFX bases with zero pin drift; `emit_emp_z80_data_only()` twin landed TDD (byte-equality + no-labels tests) against the CURRENT emp emitter — the plan's `emit_asm_z80`/main.asm activation was re-anchored to seam-2/embed mechanics; authoring runbook appended to the DAC spec with verified current paths. Ride-along: tools pytest suite was collection-broken on master (parsers read the deleted `sound_tables_z80.asm`) — re-anchored to the .emp. Oracle drum-trigger sanity = controller session. |
| 4 | **Correctness batch** — surviving audit bugs: D1 (PSG pitch-mod noise-route gate), D2 (zeroed `sc_dur_default` 255-tick note), D4 (`Psg_NoteOn` ignores `sc_transpose`), D5 (PSG env attack one frame late), D6 (stale `sc_repeat_count` across song loop), D7 (`MEV_REPEAT_END` operand 0), B3 (AM-enable byte fidelity), B5 ($E7 tone-tracked noise sweep), E5-runtime (SSG-EG 7th RegDelta group), F3/F4 ~~(verified already fixed/moot 2026-07-03 — SfxTable is LIVE; D2/D3/D5 also already fixed)~~ | plan | **EXECUTED** (2026-08-10, `sound-pkg4`) — D4/D1/D6/D7/B3/E5-runtime shipped; **B5 took the plan's own Step-2B fallback** (the tone-clock mechanism is MUSIC-GATED in `Psg_Noise`, and un-gating costs far more than the 12 B ceiling: it needs an SFX-side noise-mode carrier that cannot live in the shared prefix — `sc_noise_mode` +57 aliases `sx_priority` — plus a noise-route special case in `Psg_ApplyMod`, which is the very D1 corruption this package just closed; finding recorded verbatim in DEFERRED_WORK B5). Ride-along: **triage R1** DAC DRAIN underrun guard (24 T / 6 B, zero net cycles out of the existing pad). Funded by the Task-0 item-25 sequencer reclaim (-98 B). Resident cost of the batch itself: **+9 B** (plain 6155->6164 equivalent; measured plain 6157->6164, debug 6283->6294 of 6384, headroom 101->90 B). Two producer-side rules cost zero Z80 bytes, and D7's trap is DEBUG-only (plain blob unchanged across it, CRC-proven). **Re-anchorings the plan got wrong:** D4's `ld c, <const>` cannot assemble in `sound_psg.emp` (seam-1's per-module const-name list) -> the bound moved to a shared FM entry point, which made the fix byte-NEUTRAL; D6's engine defense is 4 B not 2 (`ld (ix+d),n`); D7 uncovered that `pack_sfx` never calls `Event.validate`, so the SFX half of the operand-0 rule was missing entirely; B3's "S3K byte parity" framing was wrong (the parity byte sets don't-care bits 6-5); R1's sketched `neg`/`ccf` sequence does not exist in this sigil era and its 34 T would not fit the pad's multiple-of-4 granularity. Oracle gates (D4 rev pitch-tracking, R1 before/after, rendered A/B on BOTH shapes) = controller session. Blob re-pin owed. |

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

**Seraph queue (2026-07-03):** the Seraph/MegaDAW retarget is FULLY BANKED in
`seraph/docs/superpowers/2026-07-03-seraph-banking-queue.md` (S0–S6 + cold-start
handoff). Seraph S0–S3 are executable independently of packages 1–6; manifest
feature flags flip as packages land.

## Path-migration note (2026-07-07/08, engine/game split executed)

The engine/game split (`docs/superpowers/plans/2026-07-07-engine-game-split-execution.md`)
moved every def/RAM file these banked-but-unexecuted packages may cite. Any package plan
above that references `sound_constants.asm`, `constants.asm`, `ram.asm`, `structs.asm`,
`macros.asm`, root `test/`, or `engine/system/game_loop.asm`'s debug harness must rebase
those paths mechanically before execution:

- `sound_constants.asm` → `engine/sound_constants.asm` (engine slice) +
  `games/sonic4/config/sound_ids.asm` (game slice: `SFXID_*`, `SFXPRI_*` ladder)
- `constants.asm` → `engine/constants.asm` (engine slice) +
  `games/sonic4/config/constants.asm` (game slice)
- `ram.asm` → `engine/ram.asm` (engine slice, ends at `Engine_RAM_End`) +
  `games/sonic4/config/ram.asm` (game slice, phases from `Engine_RAM_End`)
- `structs.asm` → `engine/structs.asm`
- `macros.asm` → `engine/macros.asm`
- root `test/` → `games/sonic4/test/`
- the debug sound harness (`Debug_MusicToggle`, `Dbg_SfxIdTable`) moved out of
  `engine/system/game_loop.asm` into `games/sonic4/debug/game_debug.asm`, invoked via the
  `gameDebugTick` manifest hook
- game content generators (ojz_strip_gen, sfx_transcode, collision import, etc.) are now
  invoked via `games/sonic4/prebuild.sh`, not inline in `build.sh`

Whichever plan executes first should apply this rebase; it is mechanical (path + include
rewrite only, no logic change).
