# Handoff — Post Music-Expression Merge (what's next for s4_engine)

**Written:** 2026-06-27, for a fresh agent picking up cold after the music-expression engine landed on master.
**Your job:** pick up ONE of the prioritized threads in §4 (the user will tell you which "something else" to do), after the small post-merge cleanup in §3. Start by reading the project law (§5).

---

## 1. What just landed on master (state)
`master` = `39ac426` (fast-forwarded from `1fd11c5`). The whole **music-expression engine** stack merged:
- **Phase 1** — un-gated software vibrato / pitch-mod / `MEV_MODSET` for music; grew the music `SeqChannel` to its 58-byte end-state; FM block-boundary octave correction in `Mod_Advance`.
- **Phase 3 — the macro/automation spine** (the format-defining lift): `MEV_FMENV $F7` + `FmEnvUpdate` FM-TL carrier vol-env, `MEV_REGWRITE $F8` inline raw-register write (`$2A/$2B`-guarded), SSG-EG (`FmPatch` 26→32, `$90` group), slot[1] `MacroTick` reg-automation + `MEV_MACRO $F9` (tag grammar `TAG_MAC_*=$E0–$E3`, 2-byte BE loop + `Snd_SongBase` rebase), and the packer authoring side (`FmEnv`/`RegWrite`/`Macro` events, macro-body emitter, header `mod_ptr` back-patch, D8 music-illegal gate, `TAG_MAC_*` cross-file sync guard).
- **Phase 2 is PLAN-DOCS ONLY** on master (`docs/superpowers/plans/2026-06-27-music-expression-phase2-{global,pernote}.md`); opcodes `$F3–$F6` reserved, **no code yet**. (The per-note plan's Group C / FM-env was absorbed into Phase 3 and is struck — do NOT rebuild `$F7`.)

**Why the merge was safe (the gate, discharged):** spec §0.3 gated the merge on a gold-standard S3K HCZ2 A/B. The decisive fact: **no shipped song uses any of the new features** — grep for `ModSet`/vibrato across all song generators is empty; Phase 3 is inert when `sc_env=0`/`sc_mod_ptr=NULL` (which all songs are); SSG-EG defaults `$00` with byte-identical patch data. So the branch renders **HCZ2 / Moving Trucks / SFX identically to master** — verified on-device (oracle): HCZ2 (id 3) and MT (id 1) play clean with `sc_env=0`/`sc_mod_ptr=0`, channels streaming. The S3K-*fidelity* A/B only matters once content actually USES the new features → it lives in the HCZ2-revisit thread (§4.D), not the merge gate.

## 2. Verified state (don't re-litigate)
- Build green: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` → `s4.bin` (~556 KB). Z80 `Z80_SOUND_SIZE=$1618`, ceiling `$16F0` → **216 bytes headroom**.
- Python: `python3 -m pytest tools/ -q` → **768 passing**.
- On-device (oracle): the flagship FM swell moves the carrier TL per the contour (`vgm_intranote`: 8 TL changes, range 32); `MacroTick` executes a poked macro body (reg-write lands, `$2A` re-park survives → DAC clean); HCZ2/MT unchanged. Every task got two-stage review + a final whole-impl review ("implementation-complete + spec-complete").
- Reserved non-breaking: pitch/pan macro target slots (format allocated, no code/RAM until live).

## 3. Task 0 — post-merge doc-sync (do this first; ~30 min, contained)
The code shipped but the docs lag it (CLAUDE.md mandates keeping `ENGINE_ARCHITECTURE.md` in sync as the source of truth). On `master`:
1. `docs/DEFERRED_WORK.md` — mark CLOSED (strike `~~…~~` with a "DONE 2026-06-27 (music-expr merge)" note): **E-now-2** (per-frame FM TL vol-env), the **E3 raw-register escape** piece (`MEV_REGWRITE`), **E4** (dual-stream/`sc_mod_ptr` macro), **E5** (SSG-EG per-op-patch half — leave the dedicated 7th-RegDelta-group half open), **D8** (packer music-illegal gate). Leave the rest of the D-list (D1–D7) + E-now-1/3/4 open.
2. `docs/ENGINE_ARCHITECTURE.md` §6 (sound) — the audit found pre-existing drift: SFX, music PSG-envelopes, and the raw-register escape are listed DEFERRED but are SHIPPED; add the macro/automation spine (`sc_mod_ptr` slot[1], `MacroTick`, the `sc_env` contour slot, `MEV_FMENV/REGWRITE/MACRO`). Reconcile the stale "Phase 5 is current priority" text.
3. `BUGS.md` + `DEFERRED_WORK.md` — stale `Z80_SOUND_SIZE $16EE / "2 free"` → the real post-F5 value (`$1618` / 216 free).
4. The **LFO Hz doc bug**: `engine/z80_sound_driver.asm` LFO-init comments say `~3.98 Hz`; `$22=$08` = rate 0 = **3.82 Hz**. One-liner fix (also noted in the Phase-2-global plan).
5. Branch housekeeping (optional): ~27 fully-merged local branches are stale (`git branch -d`); `feat/plane-buffer-complete-guard` (tried+REJECTED — master shipped `b96c861` instead) and `feat/sound-stream-drums` (tip "NOT WORKING (silent)") are dead, not integration candidates.

## 4. The "something else" — prioritized next threads (the user picks one)
Each is a fresh brainstorm→spec→plan→subagent-driven-execution cycle (the established workflow). All sound threads build on the **now-merged spine**.

**A. Phase 2 sound — per-note + global (MEDIUM, plans already written, READY).**
Per-note: **portamento** (`MEV_PORTA $F5`) + **fine detune** (`MEV_DETUNE $F6`) — drive the reserved `sc_porta_accum/incr` (+32/+34) + `sc_detune` (+56) via a shared `Fm_FnumApplyDelta` block-correction helper; **zero new RAM**. Global: **master fade-in/out + tempo ramp + hardware LFO** (`MEV_LFO $F4`/`MEV_TEMPO $F3`) — level start/clear/death/drowning/invincibility/1-up game-feel. Plans: `docs/superpowers/plans/2026-06-27-music-expression-phase2-{pernote,global}.md`. NOTE (global plan F1): the LFO is **already init-enabled** (`$22=$08`), so `MEV_LFO`'s value is rate/enable control — verify the live `$22` empirically first. This is the most ready-to-execute thread (closes E-now-1/3/4).

**B. DAC format revision — the one true pigeonhole (LARGE, needs USER SIGN-OFF before building).**
The single irreversible architectural sound decision: an N-voice PCM mixer on the FM6 DAC (per-voice volume + 16.16 mix cursor, ship 1 voice) + round-out (loop point, priority, pan via `$B6`, auto-bankswitch, `ds_rate` pitch, optional 4-bit DPCM, sampled-SFX-as-mixer-voice). It also fixes real bugs in the shipped raw-8bit Layer-6 DAC (one-shots never stop / machine-gun, `ds_loop_ofs`/`ds_rate` ignored, odd-length runaway). **Must be done as ONE revision BEFORE authoring real multi-sample drum content** — C1 (one-shots never stop) breaks the moment real drums land. Spec exists: `docs/superpowers/specs/2026-06-24-dac-drum-format-revision-design.md`. FLAG for the user as a big irreversible bet (per `leapfrog_provenance_audit` discipline).

**C. Activate the reserved pitch + pan macro slots (SMALL–MED).**
Phase 3 reserved the format; going live needs the **`sc_mod_accum` arbitration rule** (a pitch contour and software vibrato both own `sc_mod_accum` — design a "contour owns while active" rule mirroring the porta↔vibrato decision). A pitch/detune macro must drive `sc_mod_accum`, NOT the renderer-less `sc_detune`. Pan is FM-only, lower priority. RAM (+3→+4 even B/channel) paid only on activation.

**D. HCZ2 deep revisit vs the S3K rip (MEDIUM, needs the S3K reference).**
Now that vibrato/detune/envelopes exist, re-derive the HCZ2 channel cadence/timbre against the gold S3K rip with a proper cross-dimension A/B (the new instrument covers what was patched piecemeal). NEEDS the S3K HCZ2 reference capture/ROM (the merge-gate A/B was substituted with the inertness proof; THIS thread is the real fidelity work). Lesson: measure rendered audio against the actual S3K source, not a proxy.

**E. The game shell — the biggest NON-sound gap (LARGE, needs brainstorm; no spec yet).**
Today only a test-harness `GameLoop` exists (function-pointer `Game_State` dispatch into a level+sound demo; `main.asm` drives the player through `objects/test_player.asm`). Missing: a top-level **game-state machine** (SEGA→Title→Menu→LevelSelect→Game→GameOver→Credits), a **text/font renderer** (`DrawString`/Hex/Decimal — the foundational dependency for HUD, menus, title cards, level select), a **HUD** (score/rings/timer/lives with dirty flags), and a **unified level-database descriptor** (§9.1). This is the biggest gap between "engine" and "game" — nothing boots into a playable flow. If the user wants a change of domain after all the sound work, this is the highest-impact pivot.

**F. Real gameplay object content + per-section physics (LARGE).**
Shields/monitors/springs/badniks `objdef`s with **object-vs-object collision** (only player-vs-object exists today — needs a `CheckObjectPair` helper), real ring/object art in proper VRAM-pool slots (replace placeholder squares), and the deferred **per-section physics modifier/Lerp** (§5.2, a flagship NOVEL feature currently inert — plumbing shipped, multiplier tables + boundary Lerp unbuilt). `data/objdefs/` has only `test_objects.asm`.

## 5. Project law (read before coding)
- `CLAUDE.md` (both root + `s4_engine/`) and **`CODING_CONVENTIONS.md`** — sized branches, `struct/endstruct`, `function` for compile-time math, **no `mulu/divu`**, even-align `ds.w`, the hl-preservation rule in opcode handlers. (Z80 sound RAM uses constant-arith + `if/error`, NOT phase/dephase — deliberate, to avoid the `phase 0` collision; CLAUDE.md L25 is stale for that subsystem.)
- **Sound build:** `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` — a plain `./build.sh` EXCLUDES all sound. The Z80 blob must be even-sized (odd → boot address-error). Budget gate = the build's `Z80_SOUND_SIZE > SND_STATE_BASE ($16F0)` fatal.
- **Verification = rendered audio / observable behavior vs the real reference**, never a register proxy. Oracle MCP is the single live emulator (`oracle`); drive it (reload_rom / run_frames / z80_read+write / vgm_start+stop), never auto-launch. VGM captures ≤450 frames. Songs: id 1 = Moving Trucks, id 3 = HCZ2; trigger via `z80_write $1F02 <id>` (`SND_REQ_MUSIC`). Tools: `tools/vgm_intranote.py`, `tools/vgm_onsets.py`, `tools/vgm_modulation_diff.py`.
- **Daemon-watched, do NOT touch / never `--amend` near:** `data/editor/**`, `tools/ojz_strip_gen.py` (an auto-commit daemon commits editor work to the current branch ~60s after changes — there is editor WIP uncommitted in the main repo right now; that's expected). `git add` EXACT paths only, never `-A`/globs. Commit-message trailer: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **Memory:** the full music-expr arc is in the auto-memory (`project_music_expr_phase3`, `project_music_expression_engine`, `project_sound_remaining`, etc.). The "best-of-class is the standing north star" + "decide by best overall" + "measure against the real reference" feedback memories govern how to work.

## 6. Recommendation
If the user has no preference: **Task 0 (doc-sync) → then Thread A (Phase 2 sound)** — it's the most ready (plans written), builds directly on the merged spine, closes three more best-in-class items (E-now-1/3/4), and needs no new big bets. If the user wants a **change of domain** after the deep sound run, **Thread E (the game shell)** is the highest-impact pivot — it's what turns the engine into a game. **Thread B (DAC revision)** should only start after explicit user sign-off (irreversible).
