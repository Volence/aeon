# Lens parcel z3 (2026-09-11): B2a-4, CTRL-1, B1-4, C3a-4

Branch `parcel/lens-z3-0911`, cut from `origin/master` = `e4b4f38f`. Four zero-byte lens
findings, one commit each, plus this record. No ROM byte moves: see the CRC table.

| id | commit | decision |
|---|---|---|
| B2a-4 | `a6b58289` | SHARE: one script walker pair in `engine/objects/animate.emp`, one art census in `engine/objects/dplc.emp` |
| CTRL-1 | `4bd437ce` | build-fatal Z80 under-declaration census; the 7 live cases carried as a derived, printed allow-list |
| B1-4 | `d10991dd` | the three branches in `Raster_VBlank` go unsized (byte-identical) |
| C3a-4 | `fa37d835` | comment only: the interlock's "ALWAYS" narrowed to the rewind provenance, the mask-left cursor named |

`engine/effects/raster.emp` is an EFFECTS-GATE file and is touched by B1-4 and C3a-4.
`tools/effects_gates.py` was NOT run here (it boots an emulator); the controller runs it at landing.

## Base CRCs

All four canonical shapes built at `e4b4f38f` before the first edit (`./build.sh`,
`DEBUG=1 ./build.sh`, `./build.sh demo`, `DEBUG=1 ./build.sh demo`, each exit 0):

```
377796925 821123 s4.bin
185770344 847389 s4.debug.bin
3809629044 97075 demo.bin
692590224 103359 demo.debug.bin
```

The tip CRCs and the `tools/landing_build.sh` totals are in the parcel report, not here:
this file is part of the tree that run grades, so it cannot quote the run.

## B2a-4: share, on the evidence of what differed

The finding named three solvers duplicated across `player_instashield.emp` and
`ring_sparkle.emp`. The ledger's correction (line 136) said two of the three differ in
body. Reading the bodies decided it:

- **`script_display_frames` differed in SEMANTICS.** The insta-shield copy STOPS at the
  first control byte; the ring sparkle copy FILTERED `byte < AF_SET_FIELD` over the whole
  script. They agree on every script either asset ships today and disagree on any script
  with an argument after a control code. S3K's `$FD, 0` terminator ends in a legal frame
  index, which the filtering copy counts as one more frame: the exact miscount
  `poison_instashield_frames.emp` exists to catch. That is a latent defect in one copy,
  not a purposeful difference. `script_display_frames` and `script_last_frame` now live
  once, in `engine/objects/animate.emp`, which owns the script format.
- **`count_bad_nibbles` and its predicate pair (`insta_index_ok` / `ring_index_ok`, the
  third solver) differed on purpose in exactly one thing**: each asset's palette index
  set. That is data. The walk is now `engine/objects/dplc.emp`'s
  `art_nibbles_outside(blob, len, allowed)`, self-contained (no free names, no calls), and
  each asset passes its set as a bit set (`INSTA_INDEX_SET` = 0x1C1, `RING_INDEX_SET` =
  0x3061).

**Host choice, checked against sigil's port tests (read-only, no cargo run):**
`animate.emp` is not in the harness's `COMPTIME_HELPERS` list, and its one port
(`animate_port.rs`) lowers it with `engine.constants` as ambient, so the walkers' free
name `AF_SET_FIELD` resolves there. No module-level `ensure` was added to `animate.emp`,
so its drift-guard count is unchanged. `dplc.emp` (the LS-9 host) was rejected for the
walkers because `dplc_port.rs`'s ambient lacks `engine.constants`. `objdef.emp` was
rejected because it is glob-injected and lowered by 8 port tests. Both helpers are
appended below every live line citation into their files.

**Evidence.**
- Screen: `FAST=1 DEBUG=1 ./build.sh` and the same for `demo`, both exit 0, CRCs equal
  to base. `python3 tools/emp_expect_fail.py` exit 0, 54/54; both poison rows pass with
  their original fragments (18 and 3), now graded through the shared walker.
- Red-first (a), after commit: the filtering body put back into the shared walker on
  disk. The negative lane exits 1 at its sentinel, because the REAL build is red:
  `player_instashield.emp:382 [Error] the insta-shield flash shows 14 display frames;
  S3K's Ani_InstaShield shows 15`. The shipped guard grades the stop semantics by itself,
  because the insta-shield's donor script carries `$FD, 0`. Restored from the commit.
- Red-first (b): bit 8 dropped from `INSTA_INDEX_SET` and bit $D from `RING_INDEX_SET` on
  disk. `FAST=1 DEBUG=1 ./build.sh` exits 1 with both census errors (insta-shield 349
  pixels outside {0,6,7,8}; ring sparkle 18 outside {0,5,6,$C,$D}). Restored.

**Names moved.** Two new cross-module `use`s per asset and in both poison fixtures, plus
new `pub comptime fn` items in `animate.emp` and `dplc.emp`. `player_port` follows the
native closure; `collision_data_port` admits `dplc.emp`'s comptime fns by category. None
of the `*_port` tests were run (no cargo in sigil), so this is expected, not measured.

## CTRL-1: the Z80 census, narrowed to the Z80 cells

`tools/test_z80_clobbers_census.py`, collected by build.sh's pre-build pytest lane
(directory glob, build-fatal). Every proc in an `engine/`/`games/` module or section
declared `cpu: z80` that contains no `call`/`rst` must declare each register half its
body writes (`ld R,` / `inc R` / `dec R` / `pop RR` / `ex de,hl` /
`add|adc|sbc HL|IX|IY,`) through `clobbers`, `preserves`, `out` or the module's
`invariant: preserves(...)`. 68000 over-declaration stays deliberately unguarded, per
LS-2's closure; nothing was added there.

**Population, derived at `e4b4f38f`:** 11 Z80 files, 172 procs, 97 leaves checked, 75
skipped for a `call`/`rst`.

**The seven:** `Seq_Op_NoteFill`, `Seq_Op_PsgEnv`, `Seq_Op_Detune`, `Seq_Op_Ext`,
`Seq_Op_Porta`, `Seq_Op_ModSet` and `Seq_Op_OpBias` in `engine/sound/sound_sequencer.emp`.
Each writes `h`/`l` (`inc hl`) with `hl` undeclared. The scanner derived the same set as
LS-2a's hand count. They are carried as `KNOWN_UNDER_DECLARED`, printed every run, and
ratcheted three ways: a NEW under-declarer fails, an allow-listed proc that GREW another
register fails, and a STALE row fails. The premise that makes them harmless is checked:
no `call` names any of them (0 today).

**BLOCKED: correcting the seven `clobbers()` attributes.** LS-2 measured that change as
zero-byte, and it is the better end state. `engine/sound/` was on this parcel's
stay-out list, so the correction is blocked on file ownership, not refused. The parser
was not widened to chase them.

**Measured side result.** A wider parser (ALU writes into `a`, flag-only writes, `djnz`,
the block ops, `exx`, `ex af,af'`, `ex (sp),hl`, `in r,(c)`, rotates, shifts, `set`/`res`)
adds ZERO hits over today's 97 leaves. The narrow parser costs no coverage today. This is
a scratchpad measurement, not wired anywhere, and it says nothing about the 75 procs with
a call.

**Evidence.**
- First run: standalone OK, pytest 6 passed.
- Red-first #1, after commit: the LS-2 control, `Seq_Op_NoteFill`'s `ld a, (hl)` to
  `ld b, (hl)`, which built GREEN with the warning summary unchanged under LS-2. The
  census now fails: `GREW engine/sound/sound_sequencer.emp:1145 Seq_Op_NoteFill now
  writes b (first written at :1146), h (...), l (...); the allow-list carries only h,l`.
  Standalone exit 1, pytest `1 failed, 5 passed`. Restored from the commit.
- Red-first #2: the `Seq_Op_Porta` row deleted from the allow-list. The census fails:
  `NEW  engine/sound/sound_sequencer.emp:1268 Seq_Op_Porta writes h (...), l (...),
  declared a,f`, exit 1. Restored; the census is OK again.
- Built-in fixture controls: a label-prefixed undeclared write fires; a comment, a
  string literal and memory destinations do not; the pair, half, `preserves` and
  `out(carry)` spellings compare correctly; a proc with `call` is skipped; an unknown
  attribute token refuses.

**A caveat on "prints".** The allow-list is printed on every run, but build.sh's lane
runs `pytest -q`, which captures stdout on a pass. So it shows up standalone, under
`-s`, or when the test fails, and not in a green build log.

## B1-4: unsized, because the bytes proved it free

`beq.s .no_install`, `bne.s .copy_program` and `beq.s .done` in `Raster_VBlank`. None of
them is an `@as_compat` port, a patched field or cycle-solved code. `Raster_VBlank` runs
once per frame from `VInt_Level`/`VInt_Lag`, and the `.s` sizes this file does argue
belong to `Raster_HInt`'s dispatch rungs. Sigil relaxes an unsized branch to the short
form by reach, and all three already assembled short. The two comments that name the
branch were re-spelled in place. The edit is line-neutral (2354 lines before and after).

FAST screen of all four shapes with only this change on disk: all four CRCs equal to
base (the table above).

## C3a-4: comment only

In `Raster_HInt`'s `.priming` arm, "it is sufficient, because a stale fire ALWAYS lands
on priming record 0" becomes "sufficient for the REWIND provenance only". The comment now
names the MASK-LEFT CURSOR. `Section_RedrawPlanes` sets SR to `$2700` and holds it until
its `move.w (sp)+, sr`. Its DEBUG assert pins IPL >= 6 inside that span, and nothing in
the span calls raster code. So no `Raster_HInt` fire and no `Raster_VBlank` rewind runs
during the storm, and at the SR restore `Raster_Cursor` is where the last pre-mask fire
left it. This is read from the code, not measured.

The consequence the seat gave (one frame of a band at the wrong height, self-healing) is
carried as its claim; this parcel did not re-derive it. No runtime test was added: that
needs an emulator, and this parcel runs none. The rewrite is 8 lines for 8, and every
live citation into the file resolves to the same text as at base (72 citations checked
across this parcel's files).

## What the brief or the ledger got wrong

1. **LS-2a's population was short.** Its census read 7 sound `.emp` files. The Z80 tree
   is 11 files, and it contains one more contract-less proc, `engine/system/z80_init.emp`
   `Z80_IdleProgram`. That one is deliberately attribute-less and argued in its source.
   The census pins it as an exact attribute-less set, so a new contract-less Z80 proc
   fails.
2. **LS-2a's "reached only through the trampoline" is off by one jump.** `Seq_Op_Ext` is
   also the target of a `jp z, Seq_Op_Ext` in `Sequencer_NextOpcode`. That proc declares
   `clobbers(af, bc, de, hl)`, so `hl` is covered on that path. Harmless, but not what
   the row says.
3. **The brief's two options for CTRL-1 met its own stay-out list.** "Correct the
   attributes if you prove them accurate" needed `engine/sound/`, which was off limits,
   so the allow-list was the only open option.
4. **The LS-9 precedent was followed in form, not in module.** The LS-9 host
   (`dplc.emp`) cannot hold the walkers without breaking `dplc_port`. See the host
   choice above.
5. **B2a-4 was stronger than the ledger's correction framed it.** The correction called
   it "a decision about whether two similar solvers should be one". One of the two walker
   copies was latently wrong for a script shape the tree already fixtures.
6. **The poison row can no longer grade the stop semantics in isolation.** The shipped
   insta-shield guard reds the build first (mutation (a) above), so the negative lane
   stops at its sentinel. That is redundancy, not a defect, but a future reader
   expecting the poison row to be the only witness should know.
7. **One RECORD citation moved:**
   `docs/audits/2026-09-09-gate-blindspot-sift-c.md` cites `player_instashield.emp:460`,
   which B2a-4's removals shifted. It is RECORD scope by `tools/test_citation_form.py`'s
   dated-basename rule, so it is left alone. The gate passes.
8. **Sift rows cite `raster.emp:975/:1006/:1051/:1423`.** At `e4b4f38f` those lines
   still held exactly the cited text; nothing was re-pointed.

## Proposed ledger lines

Each is the id's latest line in `docs/lens-findings.jsonl`, with only `at`, `state`,
`fixedAt` and `detail` changed. Old `detail` text is kept and the fix appended after
`||`. `docs/lens-findings.jsonl` and `docs/DEFERRED_WORK.md` are not edited by this
parcel.

```json
{"id": "B2a-4", "at": "2026-09-11T21:06:57Z", "sweep": {"date": "2026-09-06", "packet": "docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md", "sha": "9cfebb72", "pin": "61f22403"}, "seat": "B2a", "severity": "low", "title": "Three comptime solvers are duplicated verbatim across two modules with nothing keeping them in step", "state": "fixed", "fixedAt": "<merge>", "detail": " || CORRECTION (2026-09-09 sift, slice A): 'duplicated verbatim' is wrong for two of the three. count_bad_nibbles and script_display_frames share NAMES and algorithmic shape across the two modules, but their bodies differ (parameter shape, loop bound, and an extra stop-flag in script_display_frames). What is shared is the shape, not the literal code -- which changes the fix from a de-duplication into a decision about whether two similar solvers should be one. || FIXED (2026-09-11, parcel/lens-z3-0911, a6b58289): decided SHARE. The two script_display_frames bodies differed in SEMANTICS: the ring sparkle copy filtered `byte < AF_SET_FIELD` where the insta-shield copy stopped at the first control byte, so it would count the argument of S3K's `$FD, 0` terminator as a frame. script_display_frames and script_last_frame now live once in engine/objects/animate.emp (owner of the script format). The nibble censuses and their index predicates (the third solver, ring_index_ok / insta_index_ok) are one self-contained walk, engine/objects/dplc.emp art_nibbles_outside(blob, len, allowed), with each asset's palette set as a bit-set argument. Red-first: the filtering body put back into the shared walker fails the SHIPPED insta-shield guard (14 vs 15 display frames); dropping one index from either set fails that asset's census (349 and 18 pixels). Zero bytes: four-shape CRCs equal to base."}
{"id": "CTRL-1", "at": "2026-09-11T21:06:57Z", "sweep": {"date": "2026-09-06", "packet": "docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md", "sha": "9cfebb72", "pin": "61f22403"}, "seat": "controller", "severity": "high", "title": "Register contracts are machine-checked in one direction only, and not at all for the sound processor", "state": "fixed", "fixedAt": "<merge>", "detail": "Three of the four cells are unguarded from inside this repo. The conventions document states they are compiler-verified. Measured with three builds plus a cross-repo gate and its control. || CORRECTION (2026-09-09 sift, slice C): this row's own supporting sentence -- that CODING_CONVENTIONS.md claims the contracts are compiler-verified -- is STALE. b83204df (2026-09-07) had already replaced that with an honest 2x2 table a day before this row was written. The row's technical claim (three of four clobber-contract cells unguarded) is still true and is exactly what the corrected table documents. Fix the row's premise, not the finding. || FIXED, NARROWED TO THE Z80 UNDER-DECLARATION CELL (2026-09-11, parcel/lens-z3-0911, 4bd437ce): tools/test_z80_clobbers_census.py, in build.sh's pre-build pytest lane, fails the build on any Z80 leaf proc (no call/rst) whose explicit register writes are not declared by clobbers/preserves/out or the module invariant. The seven live under-declarations LS-2a counted (Seq_Op_NoteFill/PsgEnv/Detune/Ext/Porta/ModSet/OpBias, all hl) are an allow-list derived by the scanner, printed every run and ratcheted both ways, with its no-call-site premise checked; correcting their attributes is BLOCKED on engine/sound/ ownership, not refused. Red-first: the LS-2 control (ld a,(hl) to ld b,(hl) in Seq_Op_NoteFill), which built green, now fails (GREW); deleting an allow-list row fails (NEW). 68000 over-declaration stays deliberately unguarded per LS-2's closure. Z80 over-declaration stays unguarded too (not a correctness class). Not covered, stated in the test: procs with a call (75 of 172), tail jumps, implicit writers, templates.", "batch": "LS-2"}
{"id": "B1-4", "at": "2026-09-11T21:06:57Z", "sweep": {"date": "2026-09-06", "packet": "docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md", "sha": "9cfebb72", "pin": "61f22403"}, "seat": "B1", "severity": "low", "title": "Three explicit branch sizes in a VBlank routine have no argument, where the same file argues all its others", "state": "fixed", "fixedAt": "<merge>", "where": {"path": "engine/effects/raster.emp", "line": 975}, "detail": "FIXED (2026-09-11, parcel/lens-z3-0911, d10991dd): the three branches in Raster_VBlank (beq .no_install, bne .copy_program, beq .done) are unsized. None is an @as_compat port, a patched field or cycle-solved code (Raster_VBlank runs once per frame; the file's argued .s sizes are Raster_HInt's dispatch rungs), and sigil relaxes to the short form by reach, so the ROM does not move: four-shape CRCs equal to base. Line-neutral (2354 lines). EG: raster.emp is an effects-gate file."}
{"id": "C3a-4", "at": "2026-09-11T21:06:57Z", "sweep": {"date": "2026-09-06", "packet": "docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md", "sha": "9cfebb72", "pin": "61f22403"}, "seat": "C3a", "severity": "suspicion", "title": "A replan routine masks interrupts for three or four frames on a path where a raster program may be armed", "state": "fixed", "fixedAt": "<merge>", "where": {"path": "engine/level/section.emp"}, "detail": "Packet, seat C3a, suspicion S2: Section_RedrawPlanes is inert on the level-init path, but on the cache-recovery path its own header advertises it runs mid-game with display on and IE1 possibly set. The frame-rewind interlock (engine/effects/raster.emp:1459-1463) guards priming record 0 BY CONSTRUCTION -- its own comment says 'a stale fire ALWAYS lands on priming record 0'. A cursor left mid-schedule by a mask has a different provenance and sits outside that argument, which is stated as exhaustive. Consequence is one frame of a band at the wrong height, self-healing. The seat ranked it low and recorded it only because the interlock's coverage claim is absolute. Enrolled 2026-09-09: the packet's C3a section carries V1, S1, V2 and S2, and the ledger carried the first three. || FIXED, COMMENT ONLY (2026-09-11, parcel/lens-z3-0911, fa37d835): Raster_HInt's .priming comment now says the interlock is sufficient for the REWIND provenance only and names the MASK-LEFT CURSOR: Section_RedrawPlanes holds SR at $2700 from its mask to its SR restore, nothing in that span calls raster code, so no Raster_HInt fire and no Raster_VBlank rewind runs inside it, and at the restore Raster_Cursor is where the last pre-mask fire left it. Read from the code, not measured; the one-frame consequence is the seat's claim, carried not re-derived. No runtime test (needs an emulator). EG: raster.emp is an effects-gate file.", "batch": "Tier 2"}
```
