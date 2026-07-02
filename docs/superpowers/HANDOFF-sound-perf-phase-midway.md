# HANDOFF — Sound Performance & Budget Phase, midway (2026-07-02, session hit context limit)

**For:** the next session continuing this phase. Work resumes in the worktree
`/home/volence/sonic_hacks/aeon/.worktrees/sound-perf-budget` (branch `feat/sound-perf-budget`,
based on master `b024cb6`). Governing docs: spec
`docs/superpowers/specs/2026-07-01-sound-performance-budget-design.md` (APPROVED) and plan
`docs/superpowers/plans/2026-07-01-sound-performance-budget.md` (12 tasks). Execution model:
subagent-driven (fresh implementer per task + spec review + quality review), **but ALL oracle
emulator interaction is done by the CONTROLLER in the foreground — subagents must NEVER call
emulator MCP tools** (a hung MCP call deadlocked two background agents for 9 hours on 07-01/02).

## 1. Task status

| Task | Status |
|---|---|
| T1 harness+baselines | DONE. Register-level baselines solid (retrigger 0-2% vs ref 100%; bipolar 2× vibrato; tempo +1.16%). The handoff's RENDERED-magnitude claims did NOT reproduce — later gates = parity vs ref under the SAME script, not absolute numbers. |
| T2 A.1 COPY-path delete | DONE+reviewed, `0e5f8cc`+3 follow-ups. +132 B. |
| T3 A.2 bank tables | DONE+reviewed, `8bd307d` + self-heal `dcfd4b4` + fixes `1a166c0`. +146 B. Placement divergence (song-bank head, not "DAC bank") reviewed & endorsed. |
| T4 A.3 RAM repack | DONE+reviewed (`423e2e2` + `5536d79`). Ceiling $16F0→$18F0, ring page $19, seq $1A00, derived page-aligned SND_SFX_BASE (protects Snd_ChanClass), structs 60/64 with the two Task-6 reload fields. **Soak criterion MET**: 5,700 frames music+SFX+DAC flawless on the new map (game state verified; the stall that ended it was the EMULATOR loop, see §3). Boot + all hotkeys verified. Mark T4 complete. |
| T5 B rekey chokepoint | **DONE + capture-verified 2026-07-02** (`3d8d037` + comment `1355424`, net −10 B). Retrigger 100% all melody channels (baseline 0-2%, ref 100%), off/on ratios at ref parity, rendered bed +0.1 dB, MT unchanged, SFX-over-music clean — full numbers in `docs/research/phase_harness/t5_verification.md`. Latent semantic change: multipoint trills now genuinely re-attack (unreachable by shipped content — spec reviewer verified no count≥2 PITCHENV in any packed song). |
| T6 mod re-arm | **DONE + capture-verified 2026-07-02** (`1ff1c1f` + review fixes in `dac3643`, +18 B). The planning finding held: C.a alone produced ref contour — flat frames 6.9-14.0 (= ref), vib-note counts exact, unipolar-up, zero down-starts. Numbers: `phase_harness/t6_verification.md`. |
| T7 table renorm | **DONE + capture-verified 2026-07-02** (`af82335` + review minors, budget-neutral, pytest 811+2). FM1 depth 19.2→36.7 vs ref 36.6 (encoding gap CLOSED); all 7 C-notes S3K-aligned via the rounding-edge fix (spec review endorsed); MT proven table-independent; SFX spectral parity. Numbers: `phase_harness/t7_verification.md`. FM0/FM2 keep a ~4c residue (band-overlap notes, not a table artifact) — carry to the T12 matrix. |
| T8–T12 | Not started. T8/T9 are capture/profiler-heavy — fix the oracle floorTime park root cause first (see §3 RESIDUAL; needs user sign-off, the approved micro-round is spent). |
| T3.6 (unplanned) | StopMusic wedge → became the oracle saga (§3). Engine EXONERATED. |

**Z80 budget: `$15CE / $18F0 ($322 free)` = 802 bytes free** (was 6 at phase start).
pytest baseline: 808 passed, 2 skipped (2 old failures were fixed by the `.worktrees/skdisasm`
symlink — it must exist: `ln -sfn /home/volence/sonic_hacks/skdisasm /home/volence/sonic_hacks/aeon/.worktrees/skdisasm`).

## 2. Harness assets (RESCUED into repo — the session scratchpad is gone)

`docs/research/phase_harness/` now holds: all analysis scripts (clean_purity/dac_stall/
dac_perburst/drum_loud/melody_regs/melody_cmp/gate_vib/vib_series/spectral + vgmlib),
`s3k_hcz2_ref.vgm` (the purity-checked real-S3K HCZ2 reference), `sonic3k_muted.bin`,
`baseline_numbers.md` (T1's full table), `phase_notes.md` (accumulated T12 backlog notes:
$28 REGWRITE guard gap, sc_base_freq steal-latch note, etc.), `read_arbiter.py` (oracle
debug-state reader — call `python3 read_arbiter.py "emulator/debug_arbiter"`; note the
slash namespace), `arbiter_healthy.json`/`arbiter_wedged.json` (the wedge evidence),
plus the killed agents' repro/launcher scripts. `docs/research/wedge_evidence/` holds the
44s-corruption capture + README. Commit these with this handoff; decide later what stays.

## 3. The oracle saga (CRITICAL context — three defects, two fixed, one open)

All in `/home/volence/sonic_hacks/oracle` (user's emulator, deterministic mode
`ORACLE_DETERMINISTIC=1`). Engine code is EXONERATED (legal on real HW — memory
`project_oracle_arbiter_deadlock` has the full story). Commits: `23eeeb9` (v1: worker-flag
poisoning + CV gate + per-timeslice heal), `392f10a` (the `debug_arbiter` socket op — invaluable,
keep), `74a7d4a` (v2: clamp det-mode bus-event access_times to slice end — THE big fix).
`git stash@{0}` on oracle main = a killed agent's DeviceContext lost-wakeup guards (possibly
still-useful drain-hang fix; review before dropping).

- FIXED: the original wedge family (bus release stamped past timeslice end → 68k bus-granted
  forever). Stop→restart now WORKS (first time ever). Wedge horizon moved ~60s → ~95s.
  Counters prove ongoing healing (`det_clamped_br_releases` in the debug_arbiter output).
- FIXED 2026-07-02 (`7f88ce7`, micro-round completed): the negative-time BR orphan. The
  killed agent's WIP was finished (overdue sweep at NotifyUpcomingTimeslice + declared/wired
  `det_overdue_line_applies` counter through ArbiterDebugState + debug_arbiter). Validated:
  STOP repro passes (alive, SEQ_ACTIVE=0, UP restarts), 9,400-frame music+SFX soak at steady
  cadence, 21k overdue applies healed live.
- RESIDUAL (bounded stall, NOT a wedge; documented in `phase_harness/phase_notes.md`): every
  reload_rom seeds a ~70.9e9 ns far-future 68k park (absolute time through the floorTime
  escape hatch in MDBusArbiter::ClampHandshakeTimeDeterministic). Self-heals one slice per
  pumped slice; drain workflow in phase_notes. Root-cause clamp/flush at reload = candidate
  next micro-round. ALSO: VGM logging under run_frames stamps 2x waits — capture realtime only.
- Practical wedge recovery (until fixed): reset/reload MAY hang on drain → `pkill -x oracle_gui`
  (NEVER `pkill -f` — it matches your own shell) then relaunch:
  `cd /home/volence/sonic_hacks/oracle/linux-port/build && ORACLE_DETERMINISTIC=1 setsid nohup ./oracle_gui >/tmp/oracle.log 2>&1 </dev/null & disown`
  — **auto-launch is USER-APPROVED** (memory `feedback_oracle_autolaunch_ok`); ONE instance only
  (multiple contend for the socket and you end up debugging a stale binary — cost us an hour).
- Gotchas: `emulator_press` can time out mid-op and leave the run-lock stuck (→ relaunch);
  a paused frame-edge PC often samples at `Process_DMA_Critical+198` LEGITIMATELY — always
  `emulator_step` to discriminate (frozen = wedge); `emulator_reload_rom` takes a `path`;
  load symbols from the worktree `s4.lst` after every reload; Z80 addrs need `0x` prefix.

## 4. Immediate next steps, in order

1. (Optional, user-approved as "one micro-round") Re-dispatch the oracle negative-time fix
   with the §3 evidence + hard rules; controller validates: STOP repro (boot 300 → UP 3f →
   120 → START 3f → 60; expect: alive, SEQ_ACTIVE=0, UP restarts) + 6,000-frame soak.
2. T5 capture verification: build worktree ROM → oracle → capture 60s HCZ2 VGM (UP; NO stop;
   purity-check with clean_purity.py) → `melody_regs.py` (expect key-off ≈ note count/channel
   vs baseline 3/67) + `melody_cmp.py` bed-silence vs `s3k_hcz2_ref.vgm` → MT capture (A) →
   compare vs baseline (NOTE_RAW ordering flip should be inaudible/equal) → SFX-over-music ear
   check. Then mark T5 complete + tick plan checkboxes.
3. T6 dispatch (plan Task 6): Seq_Op_ModSet latches + Mod_ReArm reloads; verification =
   gate_vib/vib_series vs ref (13-14 flat frames/note, contour, depth). Struct fields exist.
4. Continue T7→T12 per plan. T12 extras accumulated in `phase_harness/phase_notes.md`; ALSO:
   master has moved (user's art-streaming spec work + daemon commits) — expect DEFERRED_WORK.md
   merge care; CLAUDE.md's "never auto-launch emulators" line needs softening per the memory.

## 5. Process rules in force (hard-learned this session)

- Subagents: code/build/pytest ONLY. Controller does ALL emulator work, foreground.
- Every agent command that can block gets `timeout`; no open-ended waits; agents report
  within ~30-45 min or return BLOCKED.
- `git add` exact paths only. The worktree build regenerates editor data — never sweep it.
- Post a short user-visible update after each task lands (user preference).
- The user watches token spend — keep dispatches lean, prefer controller-inline for small
  fixes (comment edits etc. were done inline this session).
