# Handoff — Music Expression Engine, Phase 3 (Macro/Automation Spine + SSG-EG + MEV_REGWRITE)

**Written:** 2026-06-27, for a fresh agent picking this up cold (the previous session ran long).
**Your job:** DESIGN then PLAN Phase 3 of the music expression engine. Phase 3 is the big, format-defining lift, so it warrants a real **brainstorm → spec → plan** pass (not transcribing an existing spec). SSG-EG and `MEV_REGWRITE` are **folded into Phase 3** (user decision).

---

## 0. Read these first (in order)
1. `s4_engine/CLAUDE.md` + `CODING_CONVENTIONS.md` — the law (sized branches, struct/endstruct, function for compile-time math, no mulu/divu, phase/dephase).
2. `docs/superpowers/specs/2026-06-23-music-expression-engine-design.md` — **§3.2 (dual-stream / macro spine)** and **§3.3 (generalized macro format)** are the seed of Phase 3. Also §2 scope (SSG-EG + `MEV_REGWRITE` are listed in-scope there).
3. The two Phase-2 plans (already written, NOT yet implemented) — they show the one-off features the spine will subsume:
   - `docs/superpowers/plans/2026-06-27-music-expression-phase2-global.md` (fade/tempo/LFO)
   - `docs/superpowers/plans/2026-06-27-music-expression-phase2-pernote.md` (portamento/detune/FM TL vol-env)
4. `docs/superpowers/plans/2026-06-26-music-expression-phase1.md` — the implemented Phase 1 (struct grow + un-gated vibrato).
5. The capability audit (engine-wide best-in-class gap analysis) is summarized in memory `project_hcz2_status_and_roadmap` + `project_music_expression_engine`; its recommendation: build the one-off renderers first, THEN the macro spine, then refactor the one-offs into macro *targets*.

## 1. Current state of the branch (conversation context you won't otherwise have)
- **Worktree/branch:** `/home/volence/sonic_hacks/s4_engine-music-expr` on `feat/music-expr-p1` (branched from `master`).
- **Phase 1 = IMPLEMENTED + verified, NOT merged.** Commits on this branch: RAM reorg (trace ring relocated off the `$1A00` page) → SeqChannel grown 43→**58 bytes** (mod block at the shared SfxChannel offsets +42..+54; `sc_noise_mode`→+55; `sc_detune` reserved at +56) → all 6 SFX-only vibrato gates removed (FM+PSG software vibrato now renders for music) → block-boundary octave correction in `Mod_Advance`. Verified OUR-side in Exodus: vibrato renders (HCZ2 FM channels modulate `last = base ± accum`), Moving Trucks golden unchanged (all `sc_mod_ctrl=0`), no crash. **The gold-standard S3K HCZ2 audio A/B is DEFERRED** (user chose to keep planning instead). Do NOT merge to master until that A/B is done.
- **Phase 2 = PLANNED only** (the two plan docs above). Not implemented.
- **master** has the HCZ2 fidelity fixes merged (drums, hi-hat ×3, PSG-octave/bright-hat) from earlier this session — those are separate from this branch's expression work.

## 2. Phase 3 scope
**A. The macro/automation spine** — the defining move. Today the format is a flat per-channel opcode stream. The header already carries a per-channel **slot[1] `sc_mod_ptr`** (a second stream pointer) that the song loader *parses but never reads*, and the packer always NULLs it. Phase 3 makes it real:
- A new per-frame reader (call it `MacroTick`) walks slot[1], parses macro events, and writes per-channel automation **state** (the existing `sc_*` fields). It does NOT touch the chip.
- The renderers (`ModUpdate` and friends) already turn `sc_*` state → chip writes once/frame. **So the spine ADDS a general authoring path that writes the SAME `sc_*` state the dedicated opcodes write — it does NOT rewrite the renderers.** This is why the one-off opcodes (`MEV_MODSET`, `MEV_FMENV`, `MEV_PAN`, …) **remain as ergonomic fast-paths** and coexist with the spine (per spec §3.3). Building the one-offs first (Phase 1/2) then the spine is therefore *not* a rewrite — it's "reader → state → renderer," with two readers feeding one renderer set.
- **Generalized macro format** (spec §3.3): the shipped PSG vol-env IS a macro in miniature — a body of value bytes + control codes (`$80` loop / `$81` sustain / `$83` rest / plain = delta), advanced one entry/frame via a tiny id→ptr map (`PsgVolEnv_Resolve`, `engine/sound_psg.asm`). Generalize that body format and bind a macro to a **target** (volume / pitch-offset / pan / arbitrary register). The end state: every future effect is "add a macro target," not "new opcode + new struct field."

**B. SSG-EG** ($90–$9E per operator) — buzzy/metallic/AY timbres at zero per-frame cost (pure hardware once written). Today `FmPatch` is a fixed 26 bytes with no SSG-EG byte, and `Fm_RegDelta`'s group table stops at `$80` (can't reach `$90`). Needs a ~4-byte FmPatch growth (RAM + every patch re-export) + a `$90`-group register writer (a 7th RegDelta group). Consider whether SSG-EG is also reachable as a macro/`MEV_REGWRITE` target.

**C. `MEV_REGWRITE`** — the anti-pigeonhole primitive: one opcode that writes any YM2612 register (part + reg + value) so no present/future chip feature ever forces a format break (`$22`, `$27`, `$28`, `$90`, etc.). MUST observe the DAC `$2A` address-park discipline (re-park `$2A` after the write via `Fm_ReparkDac`, like the LFO write does). This is small and high-leverage; it may even subsume SSG-EG authoring.

## 3. Hard constraints & coordination (verify against real code — see §6 lesson)
- **Opcode numbers already taken:** `$F2` MEV_PSGNOISE (shipped, master), `$F3` MEV_TEMPO + `$F4` MEV_LFO (Phase-2 global plan), `$F5` MEV_PORTA + `$F6` MEV_DETUNE + `$F7` MEV_FMENV (Phase-2 per-note plan). **Phase 3 must use `$F8`+** for `MEV_REGWRITE` + any macro opcodes, and add the fixed-slot collision asserts in `sound_constants.asm`. (These Phase-2 numbers are *planned*, not yet shipped — but treat them as reserved to avoid a collision when those plans execute.)
- **Z80 code ceiling = `$16F0`** (F5 table-banking already freed headroom on master, but the spine + SSG-EG add code — watch `s4budget`/the build-time size assert; if it overflows, that's the signal, not a logic error).
- **Z80 RAM is tight.** SeqChannel is now 58 bytes; the seq region tail is `SND_SEQ_END=$1A86`, trace ring ~`$1A97`, song buffer `$1B00`. Macro state that fits in the *existing* `sc_*` fields (the spine writes the same state) needs no new bytes — prefer that. If the spine needs new per-channel bytes, you have a real RAM-layout problem (the array is boxed by the trace ring + song buffer) — the Phase-1 plan documents how the reorg was done; the song buffer (`$1B00`, 512B) is unused by STREAM songs and is the obvious reclaim if you must.
- **AS does NOT auto-align `ds.w`/`ds.l`** — pad structs to even, and runtime-boot-verify after any RAM-layout change (build asserts alone are insufficient — a stale RAM layout address-errors at runtime).
- **DAC `$2A` park:** any YM write outside the DAC loop must save/restore the parked `$2A` (the addr port stays selected on `$2A` during playback). `MEV_REGWRITE`/SSG-EG writes must re-park.
- **Daemon-watched, do NOT touch:** `data/editor/**`, `tools/ojz_strip_gen.py` (a watcher auto-commits those; never `--amend` near them). `tools/smps_import.py` + `tools/song_packer.py` ARE fair game (the packer is where macro authoring lives).

## 4. Process (the established workflow)
- **Brainstorm → spec → writing-plans → subagent-driven-development** (superpowers skills). Phase 3 deserves a genuine brainstorm/design (the macro format is a real design decision) before a plan. Save the spec to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`, the plan to `docs/superpowers/plans/`.
- **Build sound with the flags:** `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`. A plain `./build.sh` EXCLUDES all sound — a green plain build proves nothing about sound code.
- **Subagent-driven execution pattern that worked this session:** dispatch one implementer subagent per task (model `sonnet` is fine for mechanical asm given exact code in the plan); the controller (you) does the spec+quality review of each diff AND keeps all **oracle/emulator verification in your own hands** (the implementers do edit+build+build-asserts+commit only). The emulator is a single shared instance.
- **Git:** commit each step; `git add` EXACT paths only (never `-A`/globs — there is unrelated untracked WIP in the tree); commit messages end with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Merge to master only when a phase is complete AND verified.

## 5. Verification standard (NON-NEGOTIABLE — this is a recorded lesson)
Verify by **rendered audio / observable chip behavior, measured against the real reference (S3K)** — never a convenient register proxy that can be "100% correct yet inaudible." Tools: `tools/vgm_intranote.py` (intra-note fnum/TL motion), `tools/vgm_modulation_diff.py` (OURS vs ORACLE), `tools/vgm_onsets.py`. Exodus MCP is `oracle` (single live emulator; `exodus` is a defunct symlink to it). **Use SHORT captures (≤450 frames) — long captures have frozen the emulator.** Runtime-boot after any RAM change. For a macro feature, "it plays" is not "it does what the macro says" — capture and confirm the targeted parameter actually moves as authored.

## 6. Lessons burned in this session (read the memory files; don't repeat these)
- **`feedback_measure_against_reference`** — "best in class" must be A/B-rendered against the actual source (S3K), and the cross-dimension audit run UP FRONT, not after the user notices. HCZ2 shipped many fidelity bugs because verification checked "it plays," not "sounds like S3K."
- **Verify against real code, not docs/memory** — this session, a capability audit's "already-spec'd" flags were unreliable, and the spec's §6 LFO premise was WRONG against the code (the LFO is already enabled at init). Both Phase-2 planning agents caught real discrepancies by reading the actual source. Do the same: confirm every anchor (field offsets, fold points, the slot[1] loader parse, the PSG-env body format) against the real files before designing on top.
- **`clean_not_bolted_on`** — build for the end-state; the macro spine should make later effects "complete, not rewrite." The fast-path opcodes are part of the end-state design (they coexist), so this is consistent — but don't bolt the spine on as a parallel half-system; it shares the `sc_*` state and renderers.

## 7. Suggested first steps
1. Confirm the slot[1] reality: grep `sc_mod_ptr` / the song header `mod_ptr` parse in `engine/z80_sound_driver.asm` (the loader) and `tools/song_packer.py` (where it's NULLed). Read `PsgEnvUpdate` + `PsgVolEnv_Resolve` (the macro-in-miniature to generalize).
2. Brainstorm the macro format + the target-binding model (volume/pitch/pan/arbitrary-reg), and how SSG-EG + `MEV_REGWRITE` fit (likely: `MEV_REGWRITE` is a tiny standalone opcode + an "arbitrary register" macro target; SSG-EG is an FmPatch field + reachable via the reg target). Decide whether the macro state reuses existing `sc_*` fields (preferred — no new RAM) or needs new bytes.
3. Resolve the open RAM question (does the spine need new per-channel state?) early — it gates everything.
4. Spec it, get user review, plan it, execute subagent-driven, verify against S3K, then this whole branch (Phase 1 + 2 + 3) gets its A/B and merges to master.

## 8. Pointers
- Engine source: `engine/sound_sequencer.asm` (opcode dispatch, ModUpdate, Mod_*), `engine/sound_fm.asm`, `engine/sound_psg.asm` (PsgEnvUpdate — the macro model), `engine/z80_sound_driver.asm` (loader, mailbox, DAC, `$2A` park), `sound_constants.asm` (RAM map, structs, MEV_* + SND_REG_* constants), `engine/sound_tables_z80.asm` (PsgVolEnv tables — model for FmVolEnv/macro tables), `tools/gen_sound_tables.py`, `tools/song_packer.py`, `tools/smps_import.py`.
- Architecture doc: `docs/ENGINE_ARCHITECTURE.md` §6 (sound) — keep it in sync as the source of truth.
- `docs/DEFERRED_WORK.md` — section E ("Best-in-class — the honest gaps") + D-list (D1–D8) catalog known sound gaps incl. the macro spine, SSG-EG, MEV_REGWRITE.
