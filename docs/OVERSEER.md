# Aeon Overseer

**Boot prompt** (paste into a fresh session started in this repo):

> You're the overseer for this repo. Read `docs/OVERSEER.md` first, then
> `../empyrean/docs/OVERSEER-PROTOCOL.md`. Work the queue. Peers may or may not be
> running — check `ListAgents`; coordinate if present, proceed solo if not.

The role, delegation discipline, review bars, and peer protocol live in the shared
protocol doc. This file is what's aeon-specific.

## The queue

**`docs/DEFERRED_WORK.md` is the living queue** — check it at the start of every
planning phase; it books everything with provenance. The current arc and any owner
rulings live in the session memory and the most recent `docs/superpowers/*handoff*` /
`*summary*` docs. Do not duplicate queue content here; this file only says where it is.

## Landing lane (aeon owns the aeon↔sigil pair)

- Byte-moving parcels land as aeon+sigil PAIRS through THIS repo's overseer: merge →
  rebuild all four shapes → re-verify on the merged tree → effects-gate ritual (if
  `engine/effects/*`, `engine/level/bg_anim.emp`, or `engine/system/buffers.emp`
  moved) → sigil `refreeze --freeze NAME --ab <prose evidence>` → full sigil suite
  (`cargo test --release --workspace --no-fail-fast`, aggregate totals; the fully-green
  bar moves — derive it, don't quote this file) → push both. `refreeze --check` is NOT
  the goldens. The hand-typed baseline test (`repin_pins.rs`) demands a per-parcel
  term with its story when assembled lengths move.
- One byte-mover per branch. Serialize refreezes. When any session is live-editing
  content in the main tree, build + freeze from a CLEAN CHECKOUT of the merge SHA.
  **The clean checkout must be threaded through ALL THREE legs explicitly** (lived
  2026-08-20): `repin -- --aeon <clean>`, `refreeze` with `AEON_DIR=<clean>`, AND the
  full suite with `AEON_DIR=<clean>` — each defaults to the sibling main tree on its
  own. The tell for a dirty-tree repin is region pins shifting in lockstep (+0x100-ish)
  with lengths unchanged; the tell for a dirty-tree suite is broad `*_port`
  region-diff failures at embedded addresses. A fresh clean worktree also needs one
  `./build.sh` + `DEBUG=1 ./build.sh` first — repin resolves but does not generate.
- Zero-byte parcels (tools/docs) are aeon-only; verify CRC identity anyway —
  byte-count-neutral is not byte-identical, and DEBUG-only procs can still move the
  release deb2 appendix.
- **Sigil sessions/agents are read-only consumers of this tree** (their port gates read
  it via `AEON_DIR` at test runtime). Mid-brushstroke uncommitted aeon edits can flip
  sigil port-gate results — a sigil strict-gate run that matters points `AEON_DIR` at a
  clean checkout of a committed SHA, the same clean-checkout rule freezes use. Mirrored
  from sigil's `docs/OVERSEER.md` (024c7caa).

## Recovering a vintage artifact (before ANY toolchain-archaeology parcel)

**Prefer the committed artifact to the recipe that recreates it — and look for it at the revision
that PINNED it, not at the tip.** Shared protocol (`9b604f0` + companion clause `e650b96`); this
lane supplied the miss that earned the clause. **A SHA has a class; a path has a TIME.**

Lived 2026-08-22: recovering the profiler-corpus ROM (`d22dda85`), this overseer checked
`sigil master:crates/sigil-harness/golden/s4.debug.bin`, truthfully found `0dbaa80f` (correct for
master), reported "no committed blob shortcuts it", and was one step from a rebuild parcel. **The
blob was sitting at `7b46f075`** — the `refreeze: raster-cram-anchor-366` commit whose own message
named the paired golden move. A golden path is a MOVING POINTER: for a vintage artifact, the tip is
the one revision guaranteed not to have it.

The procedure, since this repo's landing lane generates exactly these pairings on every refreeze:
1. Find the refreeze/pairing commit that moved the golden (its message names the pairing).
2. `git -C sigil cat-file blob <rev>:<path> > out.bin`, then **hash the extracted bytes yourself**
   — never trust the claim, including a peer's.
3. `git merge-base --is-ancestor <rev> master` before depending on it (reachable, not gc-able).
4. Only if the artifact genuinely isn't there, consider the rebuild — and price it first: the
   `bc048e2a` attempt failed on a PRE-rename `HARNESS` path
   (`oracle/linux-port/harness`, now `oracle-old/...`) and would then have hit
   `[map.undeclared-island] at 0x99F0` from current sigil having moved past that tree's map.
   Both halves were one pinned sigil revision — the same `7b46f075`.

## Instruments (which oracle for what)

- **oracle-next / oracle-aether** (bus socket, headless): pixels, scanlines (sub-line
  since 2026-08-19), memory, watchpoints with per-hit mclk, the warp mailbox, and — once
  its profiler ships — cycle attribution (compare `cyclesSelf`, never inclusive).
  Client patterns: `tools/hblank_window_sweep.py`, `tools/sh_probe.py`. Assert
  `source == "raster"` on every scanline capture.
- **old oracle** (headless harness at `oracle-old/linux-port/harness`): the profiler until
  oracle-next's lands. Per-routine rows ONLY (`interrupts.hint` sums both handlers);
  match addresses on the low 24 bits; attribution LOSES ~20% when a tick spans VBlank —
  rest conclusions on preemption-free evidence. Patterns: `tools/raster_cost_probe.py`,
  `tools/engine_baseline_probe.py`, `tools/streaming_choke_probe.py`.
- Subagents NEVER touch emulator MCP tools (deadlock); headless bus scripts are the
  sanctioned instrument everywhere.

## Worktree quirks (agents hit all of these)

- Export `AEON_SKDISASM_DIR=/home/volence/sonic_hacks/skdisasm`; the worktree root's
  PARENT needs a `sigil` symlink. Without both, ~9-13 pytest failures are path
  artifacts, not signal.
- `SIGIL_BUILD`/`SIGIL_EMIT` point at the sigil repo's release binaries; missing =
  BLOCKED report, never a workaround.
- The committed ab_runner scenes hardcode the MAIN tree's `s4.debug.lst` — run against
  repointed copies in a worktree. `ab_runner --new` needs ABSOLUTE paths (relative
  resolves against the emulator's cwd and reports a convincing false verdict on
  uninitialised RAM).
- `FAST=1 ./build.sh` is the content-iteration loop (~1.3 s, lanes skipped, loud
  banner) — never the basis for landing evidence. Both build paths gate on level-data
  staleness.
- The effects gate lane self-segments with per-segment timeouts and scoped reaping;
  if a lane wedges anyway, kill only PIDs whose `/proc/<pid>/cmdline` carries YOUR
  worktree's ROM path.

## Aeon-specific review bars (beyond the protocol's)

- **Cross-repo claims verify against the described repo AT AUTHORING TIME, citing the SHA
  verified at** — now the shared protocol's rule too (empyrean `00334b6`, 2026-08-22), with
  this repo's effects-schema arc as its precedent, so put it in agent briefs that survey a
  sibling tree. Lived here: an assessment quoted aurora's ROADMAP faithfully and shipped a
  caveat that had been false since a commit that was an ANCESTOR of the assessment's own
  survey pin, plus a ruling aimed at a field the sibling's save path never writes. A
  quoted survey, roadmap, or plan caveat can be stale before its pin; only reading the
  described tree catches it. Peer verification found both — reciprocate it.
- **Check the CLASS of a SHA before citing it** — SHARED PROTOCOL, read it there, do not
  restate it here (empyrean `43fbfc9` + `6d38fbc`, both from this arc; the both-outcomes
  nuance this repo proposed is now upstream too). Summary only, so a brief author knows
  whether they need it: a code guarantee anchors to the merge that carries the code,
  `--stat`-ed before the citation hardens. Paired with the claim rule above — that one
  governs what a doc asserts, this one governs what it cites.
- **Enumerate by what TOUCHES the data, not what defines it** — SHARED PROTOCOL review bar 8
  (empyrean `dc629a5`), precedent again from this arc: two overseers cross-verified each
  other's sidecar-ref enumerations firsthand and both got 8; the real count was 13, the misses
  being copiers OUTSIDE the codec frame — one of them (`cloneSection`) unguarded under a
  3,909-test suite. Every named site was real and both verifications passed; the failure was the
  shared FRAME. **Mutual verification cannot catch a shared frame — only a changed frame can.**
  When counting where a field lives, grep the TYPE and every constructor/copier of the record,
  never just the field name in its owning module. Aeon's own ERRATUM 1 enumeration is the
  corrected example.
- **Never change the subject to suit the instrument** — SHARED PROTOCOL bar 9 (empyrean
  `c2c81e2`). **This one has teeth in THIS repo specifically:** almost every instrument here
  reaches the engine through a differently-configured build — `DEBUG=1` shapes, the MD Debugger
  island, the effects-gate lane's `s4.debug.bin`, profiler builds that alter what they profile.
  A number measured on a debug/instrumented shape and reported as RELEASE behaviour is exactly
  this failure, and it announces itself no more loudly than the timer-clamp case did. Say which
  shape produced a number, and if the instrument cannot reach the release shape, report the reach
  limit rather than quietly measuring the reachable thing. (`FAST=1` builds are the same trap in
  a different coat — see the build header.)
- **A gate's VERDICT and its STATED REASON are separately checkable** — SHARED PROTOCOL bar 10
  (same commit). Check the reason against the data before quoting it onward: a tripwire can fire
  correctly while its message fabricates the justification (precedent: a spread formula falling
  through a zero branch announced "medians agree to within 0.00%" about a set spanning
  0.000→0.800 ms). The reason is what a reader carries forward, so a sound verdict with a
  fabricated reason is worse than a failing gate. Relevant to every gate in `tools/` that prints
  its own explanation.

- Cycle claims near VDP ports: the bus absorbs adjacent OPERAND accesses but not
  instruction-stream fetches — nominal tables mispriced three consecutive parcels.
  Measure with the cost lane; the F-series/dense rows re-derive from shipped constants.
- Raster spins are SOLVED (`raster_dsl.emp`'s solver from the measured window anchor);
  a parcel that hand-adjusts a spin or a cost-gate expectation is wrong by definition.
- `.emp` comptime work: `docs/EMP_PITFALLS.md` first, every time.
- Cross-seam `Game.*`/`CAP_*` references: a FIRST reference in a module sigil's port
  harness compiles standalone breaks its `*_port` tests silently — extend the
  contract-env helpers in sigil's `test_support.rs`, values parsed from aeon source.
