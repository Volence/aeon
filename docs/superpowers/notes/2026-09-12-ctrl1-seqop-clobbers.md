# CTRL-1 follow-up (2026-09-12): the seven Seq_Op_* leaves declare the hl they advance

Branch `parcel/ctrl1-seqop-clobbers`, cut from `origin/master` = `af5e097b` (which contains
`tools/test_z80_clobbers_census.py`, landed as CTRL-1 by lens z3, merge `ad707b83`).

| commit | what |
|---|---|
| `870f19fb` | the seven attributes; the census's allow-list deleted; a handler-shape fixture control |
| `6094196b` | `docs/DEFERRED_WORK.md` LS-2a struck and re-booked; `CODING_CONVENTIONS.md` §2.8 Z80 cell |
| (this file's commit) | this record |

The four-shape run below graded `6094196b`. The only commit after it is this file, a
RECORD-scope `.md` that no build input reads.

**Landing note for the controller.** This parcel touches `engine/sound/sound_sequencer.emp`,
one of the seven inputs of sigil's `z80_clobbers_incomplete` gate
(`crates/sigil-cli/tests/z80_clobbers_incomplete.rs`). It was NOT run here: no cargo in the
sigil repo from an agent. All seven procs are in sigil's `is_opcode_dispatch_proc` set
(`Seq_Op_*`), which that gate reports as out of scope rather than as in-scope firings. So
the expectation is: in-scope firings stay 0, and `dispatch_submachine_is_excluded_but_present`
still sees a non-empty excluded set. That is expected, not measured.

## The seven, by symbol

Every one is an opcode handler: a `dc.w` cell of `SeqOpcodeTable`
(`engine/sound/seq_opcode_tab.emp`) reached through `Sequencer_NextOpcode`'s
`ex (sp),hl; ret` trampoline. `Seq_Op_Ext` is instead reached by `Sequencer_NextOpcode`'s
`jp z, Seq_Op_Ext`, which is ahead of the table. Every handler is entered with `hl` = the
stream pointer just past the opcode byte, and leaves by `jp Sequencer_NextOpcode.fetch`
with `hl` advanced past its operands. `.fetch` consumes it (`ld a, (hl)`). No `call` names
any `Seq_Op_*` anywhere in `engine/` or `games/`; the only direct transfers into the family
are that `jp z, Seq_Op_Ext` and `Seq_Op_Jump`'s `jp Seq_Op_End`.

| proc | old | new | body evidence (writes) |
|---|---|---|---|
| `Seq_Op_NoteFill` | `clobbers(af)` | `clobbers(af, hl)` | `ld a, (hl)`; `inc hl` (1 operand) |
| `Seq_Op_PsgEnv` | `clobbers(af)` | `clobbers(af, hl)` | `ld a, (hl)`; `inc hl` (1 operand) |
| `Seq_Op_Detune` | `clobbers(af)` | `clobbers(af, hl)` | `ld a, (hl)`; `inc hl` (1 operand) |
| `Seq_Op_Ext` | `clobbers(af)` | `clobbers(af, hl)` | `ld a, (hl)`; `inc hl`; `or a`; `ld a, (hl)`; `inc hl` (2 operands; the `jp nz, Seq_BadOpcode` exit also leaves `hl` advanced) |
| `Seq_Op_Porta` | `clobbers(af)` | `clobbers(af, hl)` | `ld a, (hl)`; `inc hl` (1 operand) |
| `Seq_Op_ModSet` | `clobbers(af, bc, de)` | `clobbers(af, bc, de, hl)` | four `ld a, (hl)` / `inc hl` pairs into `b`, `c`, `d`, `e` |
| `Seq_Op_OpBias` | `clobbers(af, bc)` | `clobbers(af, bc, hl)` | `inc hl` twice; `push hl`, `push ix`/`pop hl`, `add hl, bc`, `pop hl`: net `hl` = advanced stream pointer |

`Seq_Op_OpBias`'s header `Clobbers:` line said `af, bc ... Manipulates: hl (kept live)`; it
now names `hl` too, so it agrees with the attribute. The edit is line-neutral (the file is
2093 lines before and after), so no `sound_sequencer.emp:N` citation moves.

None stays on the list: no trampoline contract the census cannot see gives any of them a
reason to omit `hl`. The trampoline contract is exactly "hl comes back advanced", which is
a write.

## Why `clobbers(..., hl)` and not `out(hl)`: the sibling enumeration

The brief allowed `out(hl)` if `hl` is deliberately produced as an output. It is: the
dispatch loop consumes it. So the choice was decided by the tree's spelling for that effect.
`sound_sequencer.emp` defines 26 `Seq_Op_*` handlers (counted with `grep -c`). The
enumeration covers the 19 that are not among the seven:

- **Write `hl` and declare it (all in `clobbers`):** `Seq_Op_Macro` `clobbers(af, de, hl)`
  and `Seq_Op_RegDelta` `clobbers(af, bc, de, hl)` advance the stream pointer exactly as the
  seven do; `Seq_Op_SpinRev` `clobbers(af, hl)` borrows `hl` and restores it.
- **Write `hl` and do NOT declare it:** 13 handlers, all containing a `call` so the census
  skips them: `Seq_Op_Vol`, `PsgNoise`, `Lfo`, `Tempo`, `Patch`, `Dac`, `NoteDur`,
  `NoteRaw`, `PitchEnv`, `Pan`, `RegWrite`, `RepeatEnd`, `Jump`. They are the majority
  pattern, and they are wrong by the conventions (`CODING_CONVENTIONS.md` §2.8: every
  written register is declared). A majority of under-declarations is not a convention to
  match. They are booked (below), not fixed here.
- **No `hl` write outside a DEBUG save pair:** `Seq_Op_RepeatStart`, `LoopPoint`, `End`.
- **`out()` on any `Seq_Op_*`:** none. In the Z80 driver `out()` names a value returned to a
  `call` site (`Snd_ChanClass () out(hl, carry: music)`, `Fm_PatchPtr () out(hl)`,
  `Sfx_QueueEntryPtr () out(hl)`, and the rest). No handler has a call site.

Sigil treats both spellings as a declaration: its closure's allowed-write set is
`declared_clobbers ∪ out` (`crates/sigil-frontend-emp/src/closure.rs`, `check_firings`),
the census counts both, and `out ∩ clobbers` is a `[proc.out-clobbers-overlap]` error, so
a register is one or the other. Keeping the family on one spelling for one effect was the
deciding reason.

**Measured side result: sigil would also have accepted `out(hl)`.** On disk,
`Seq_Op_NoteFill` became `out(hl) clobbers(af)` and `FAST=1 DEBUG=1 ./build.sh` ran: exit 0.
The warning summary was identical to the baseline DEBUG sonic4 shape's:
`152 warnings, proc.clobber-undeclared 72, module.unreachable 58, module.path-mismatch 14,
proc.undeclared-fallthrough 5, import.no-names 2, proc.out-unwritten 1`. The
`out-unwritten 1` is present at `af5e097b` too. So no new `[proc.out-unverified] (Z80)`
firing stopped the sigil build's contract gate, and the Z80 out-verifier credited the
`inc hl` before the tail `jp` (it treats a tail transfer as a required return path). This
is a FAST-shape screen of ONE proc, not evidence for the other six, and it was restored
before anything was built for evidence. If the owner prefers `out(hl)` for the whole
family, it is open to them: it would add 7 or more Z80 out claims, which sigil verifies.

## The census

`tools/test_z80_clobbers_census.py`: the allow-list is DELETED, not left empty. With no
rows, its GREW and STALE branches could never run, and `test_allow_listed_procs_have_no_call_site`
had no subject: a green result that cannot fail. The census is now a zero-firing assertion,
and its failure message says there is no list to add a row to. A fixture control pins the
handler shape (`ld a,(hl)` / `inc hl` / a tail `jp` into a loop label): it fires `h, l`
under `clobbers(af)` and is clean under `clobbers(af, hl)`.

- Before the census edit, with the seven corrected on disk, the UNCHANGED census failed:
  exit 1, `STALE ... Seq_Op_<each> no longer under-declares h,l` for all seven. That was
  the ratchet seeing the fix.
- After: standalone `Z80 files: 11; procs: 172; leaves checked: 97; skipped for a call/rst: 75`,
  `Z80 leaves under-declaring: 0 of 97 checked`, `OK`, exit 0. pytest `5 passed` (it was 6;
  the premise test is gone).

**Red-first, after commit `870f19fb`.** Mutation on disk, quoted before the run:

```
1268:    pub proc Seq_Op_Porta () clobbers(af) {
```

Standalone census, exit 1:

```
Z80 leaves under-declaring: 1 of 97 checked
AssertionError: Z80 clobbers() under-declaration census (CTRL-1 / LS-2a):
  engine/sound/sound_sequencer.emp:1268 Seq_Op_Porta writes h (first written at :1270), l (first written at :1270), declared a,f
A Z80 proc must declare every register it writes in clobbers(), preserves() or out(). Fix the ATTRIBUTE: this census carries no allow-list.
```

pytest, exit 1: `FAILED tools/test_z80_clobbers_census.py::test_no_z80_leaf_under_declares_its_clobbers`,
`1 failed, 4 passed`. Before restoring, `git diff --stat` showed the mutation as the only
uncommitted change (`sound_sequencer.emp | 2 +-`). It was restored with
`git checkout HEAD -- engine/sound/sound_sequencer.emp` from the COMMITTED `870f19fb`, and
the line read back as `clobbers(af, hl)`.

Runner: build.sh's pre-build tool-suite pytest lane (collected by directory glob,
build-fatal). The census line in the tip run is quoted below.

## Bytes

Control first. `tools/landing_build.sh` ran at `af5e097b` (origin/master, before any edit)
and at `6094196b` (this parcel), each detached with a run-unique log, sigil `49ecc532…`
before and after both runs. Both runs: exit 0, `finished=0`.

| shape | size | CRC32 at `af5e097b` | CRC32 at `6094196b` | bytes |
|---|---|---|---|---|
| `s4.bin` | 821123 | `52828985` | `52828985` | identical |
| `s4.debug.bin` | 847389 | `ddf22eca` | `ddf22eca` | identical |
| `demo.bin` | 97075 | `c0898f05` | `c0898f05` | identical |
| `demo.debug.bin` | 103359 | `80bbeb9b` | `80bbeb9b` | identical |

"Identical" is a byte-for-byte comparison of the copied ROMs, not just the CRC. LS-2's
zero-byte argument for these attribute changes is now measured on all four shapes.

The tip run (`6094196b`): every shape `EXIT_*=0` at the sizes above. The pre-build pytest
lane read `2441 passed, 2 skipped, 14 deselected` in each shape. The base read 2442; the
difference is the one deleted test, `test_allow_listed_procs_have_no_call_site`. Both
sonic4 sigil warning summaries are identical to the base's (`165 warnings,
proc.clobber-undeclared 68, ...` plain; `152 warnings, proc.clobber-undeclared 72, ...`
debug). `needs_build`: `OK — all 14 marked test(s) ran and passed`, `EXIT_needs_build=0`,
`finished=0`. The machine was loaded while it ran (`load average: 13.36, 16.62, 14.07`), so
no timing here means anything.

`tools/effects_gates.py` was not run: this parcel touches no effects-gate file
(`engine/effects/*`, `engine/level/bg_anim.emp`, `engine/system/buffers.emp`).

## Found, not fixed (booked in `docs/DEFERRED_WORK.md` LS-2a)

A scratchpad scan (`nonleaf_direct_writes.py`, not wired anywhere) ran the census's own
scanner over the 75 procs it skips, counting each one's DIRECT writes and ignoring callee
effects. It returned 16 hits, and each was read at source:

- **13 real `hl` under-declarations**, in the handlers listed above: each does its own `inc hl`
  (or, for `Seq_Op_Jump`, `ld l/h` of the loop pointer) with `hl` undeclared.
- **1 real `e` under-declaration:** `Seq_Op_RegWrite` does `ld e, a` under `clobbers(af, bc)`.
- **Not defects:** `Seq_Op_RepeatStart`, `Seq_Op_LoopPoint` (`hl`) and `Seq_Op_RepeatEnd`
  (`c`) are the `pop` of a DEBUG-only save pair around `Seq_Trace`. `SndDrv_Init`'s `ld sp`
  is an `@noreturn` reset entry setting up its own stack.

The fix is the same attribute change, and they share the zero-call-site premise. It is
expected to be zero-byte, NOT measured. No gate sees them until the census models calls.

## What the brief or the tree got wrong

1. **"Search 'CTRL-1 follow-up'" in `docs/DEFERRED_WORK.md` finds nothing.** The only
   booking was LS-2a, which the z3 parcel left untouched (it did not edit DEFERRED_WORK).
   LS-2a now carries the follow-up under that name.
2. **"Match the convention of the compliant siblings":** by count, the siblings'
   dominant pattern is to OMIT `hl` (13 of 16 handlers that write it), invisibly to the
   census. The convention followed is the honest minority's (`Seq_Op_Macro`,
   `Seq_Op_RegDelta`), because it is the one the conventions document requires.
3. **`CODING_CONVENTIONS.md` §2.8 still said the Z80 under-declaration cell was UNCHECKED**
   after the census landed. It is corrected in `6094196b` to BUILD-FATAL for leaves and
   UNCHECKED for procs with a call.
4. **`docs/OVERSEER-REFERENCE.md` says the build "has no Z80 clobber census (CTRL-1 would
   add one)"**, which has been stale since `ad707b83`. Not edited here (controller-owned file).
