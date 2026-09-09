# Gate blind-spot sift — lane C (2026-09-09)

Method: `docs/DEFERRED_WORK.md`, "A GATE THAT DOCUMENTS ITS OWN BLIND SPOT IS NOT
THEREBY COVERING IT (2026-09-09)" (read at commit `26b1d106`, line 30967). No
disagreement found between that doc and the dispatch brief — the operational rule is
identical in both: *a declaration says "this gate would not catch X"; only a control
says "and there is no X here today."* This report runs that control, file by file,
over the 13 files assigned to lane C.

Full pytest run over all 13 files (env: `AEON_SKDISASM_DIR=/home/volence/sonic_hacks/skdisasm`,
`PYTHONDONTWRITEBYTECODE=1`, `PYTHONPYCACHEPREFIX=/tmp/blindspot-c-cache`, stale
`__pycache__` cleared first): **243 passed, 2 skipped** (the 2 are
`test_system_pool_release_empty.py`'s `needs_build` rows, which only run against a
built `s4.bin`/`s4.lst` — see below). No red tests anywhere in the population.

Two of the 13 files needed the real ROM artifacts. `s4.bin`, `s4.lst`, `s4.debug.bin`,
`s4.debug.lst` were copied **read-only, gitignored, not committed** from the parent
checkout into this worktree to let `test_system_pool_release_empty.py` run for real;
md5 confirmed identical to the dispatch brief's stated hashes before use
(`s4.bin` `ed512d731ebd9fc652072f4d6bd5f7b6`, mtime 2026-09-09 05:07:13 -0400 =
09:07:13Z; `s4.debug.bin` `f2d6fc54ce8e8f7b598a46da5b3beec8`, 05:13:40 -0400 =
09:13:40Z — both match the brief exactly). With them present, all 12 tests in that
file passed, including the two `needs_build` rows.

## Totals

- **Files examined: 13/13** (all present, all green).
- **Statements extracted: 33** (rows in the table below), across 13 files.
  - **SPECIFIC-CONSTRUCTIBLE: 20**
  - **GENERAL-LIMIT: 8**
  - **FALSE POSITIVE (not a self-declared non-coverage of the file it's grepped from): 5**
- **Verdicts on the 20 SPECIFIC-CONSTRUCTIBLE statements:**
  - **CLEAR: 17**
  - **OCCUPIED: 2** (both detailed below; both already-known/tracked, one benign-on-trace)
  - **UNRUN: 1** (full load-site trace in `test_vram_window_guards.py`; a weaker proxy control ran CLEAR)
- Files with **zero genuine self-declared non-coverage** (only false positives or none
  at all matched): `test_suite_paths.py`, `test_vsplit_consumer_lint.py`.

**Leading finding for the owner:** no hidden/undisclosed occupied hole was found —
unlike sigil's precedent, both OCCUPIED verdicts here point at conditions the tree's
own docs already name and track (LS-12a, LS-13b). The one that most resembles the
sigil pattern — a docstring's named blind spot with a real, present instance behind it
that nothing gates on — is `tools/test_z80_bus_hold_mask_census.py`'s interprocedural
bullet: `engine/level/section.emp:485` has exactly the shape the docstring says this
file cannot see (a call between a hand-spelled mask and its bus-hold bracket), and
only a manual trace (done here) says the specific callee is safe. See "OCCUPIED
findings" below.

---

## Table: every declared non-coverage statement

| # | File | Line | Quote (trimmed) | Class | Verdict | Evidence (one line) |
|---|------|------|------------------|-------|---------|----------------------|
| 1 | test_sfx_bank_wiring.py | 98 | "SFX_TABLE_LEN and explicitly cannot see the emitted body (its comment says so). This closes that hole from the other side" | SPECIFIC-CONSTRUCTIBLE | CLEAR | Describes a hole in a *different* gate (sfx_bank.emp's own `ensure`) that this file's `test_win_tab_cell_count_matches_the_key_range` closes; ran it — passes, 137 cells match the derived key range. |
| 2 | test_sfx_transcode.py | 1477 | "song_packer's 1..255 rule does NOT cover SFX. The engine decrements before testing, so operand 0 wraps to 255 passes." | SPECIFIC-CONSTRUCTIBLE | CLEAR | `_validate_sfx_repeat` is unconditionally called for every channel in the real `pack_sfx` path (`tools/sfx_transcode.py:1576`), confirmed by reading the call site — not a dead/unwired function. |
| 3 | test_sigil_probe_fixture.py | 16-18 | "IT DOES NOT COMPILE ANYTHING ... Only sigil's own probe run can say that." | GENERAL-LIMIT | n/a | Requires an actual sigil compile of the fixture; no static control resolves it. |
| 4 | test_sigil_probe_fixture.py | 21-24 | "IT CANNOT SEE SIGIL ... If sigil renames them, this check goes on passing while their probe goes vacuous." | SPECIFIC-CONSTRUCTIBLE | CLEAR | Read peer repo `/home/volence/sonic_hacks/sigil` at HEAD `30189ca0` (descendant of the cited `43bf606a`, confirmed via `merge-base --is-ancestor`); `ObjCodeBase`, `Draw_Sprite`, `RefreshSpritePieceCount`, and both test fn names are still exactly as transcribed. |
| 5 | test_sigil_probe_fixture.py | 25 | "IT SAYS NOTHING ABOUT games/sonic4/objects/test_solid.emp." | GENERAL-LIMIT | n/a | A scope disclaimer, not a constructible case — the file explicitly delegates to a different (sigil-side) gate. |
| 6 | test_sigil_probe_fixture.py | 206 | "A `use` naming a third module is a source file the standalone compile cannot see." | FALSE POSITIVE | n/a | Describes the invariant `test_the_import_budget_is_the_two_ambient_modules` itself *enforces* (a bad import fails that test) — not an undefended gap. |
| 7 | test_sound_bus_hold_mask_lint.py | 46-58 | "ANY OTHER FILE. This lint reads sound_api.emp only ... ⚠ THEY ARE NO LONGER UNCHECKED" | SPECIFIC-CONSTRUCTIBLE | CLEAR | Self-amended in the same paragraph: superseded by the tree-wide census (LS-13a). Cross-validated: sound_api.emp's own floor (6) + the other 7 files' 16 = 22, exactly what `test_z80_bus_hold_mask_census.py`'s independent scan finds tree-wide. |
| 8 | test_sound_bus_hold_mask_lint.py | 59-65 | "THE ONE HOLD THAT IS NOT A BRACKET AT ALL ... Its PAIRING is still checked by nothing, here or in sigil." | SPECIFIC-CONSTRUCTIBLE | CLEAR (structural gap open, not presently exploited) | Read `engine/system/boot.emp:130-156` (bus request to release): only self-looping branches (`bne .wait_z80`, two `dbf` loops) between them — no early exit exists today. See "OCCUPIED findings" for the caveat: this is LS-13b, tracked and still open. |
| 9 | test_sound_bus_hold_mask_lint.py | 66-68 | "A MASK ESTABLISHED BY A CALLER ... The tree-wide gate takes the one honest exception" | GENERAL-LIMIT | n/a | Describes what the *other* (tree-wide) gate covers, not an unclosed gap of this file. |
| 10 | test_sound_bus_hold_mask_lint.py | 69-71 | "RUNTIME. Nothing here executes a ROM ... Reproducing the original hang needs an IRQ6" | GENERAL-LIMIT | n/a | Timing/hardware race; no static or built-artifact control can resolve it. |
| 11 | test_sound_bus_hold_mask_lint.py | 72-73 | "The inner .wait_z80 spin remains OUTSIDE SPIN_WATCHDOG_LIMIT's reach in every shape." | GENERAL-LIMIT | n/a | States a deliberate design fact (the watchdog was never meant to bound this spin), not a constructible search. |
| 12 | test_sound_bus_hold_mask_lint.py | 215 | "cannot see brackets that moved to another file, which this lint does not read." | SPECIFIC-CONSTRUCTIBLE | CLEAR | Floor is 6 for this file; independent tree-wide census (item 7) accounts for exactly 6 in sound_api.emp + 16 elsewhere = 22 — no evidence of an unaccounted move. |
| 13 | test_sprite_owner.py | 43-46 | "WHAT THIS GATE CANNOT SEE ... a SAT writer added in a THIRD module is outside the census below." | SPECIFIC-CONSTRUCTIBLE | CLEAR | `grep -rn "Sprite_Owner"` tree-wide: only `engine/objects/sprites.emp` (writes `a6 = &Sprite_Owner` once, in `Render_Sprites`) and `engine/objects/rings.emp` ever touch it; no third module references it at all. |
| 14 | test_sprite_owner.py | 257 | "which is why a VRAM-vs-buffer proof cannot catch it — it silently attributes ..." | GENERAL-LIMIT | n/a | Rationale inside an assert message for the same defect class as #13, not a separate claim. |
| 15 | test_suite_paths.py | 366 | "The case the nesting argument does not cover, and no row reached before." | FALSE POSITIVE | n/a | Docstring of `test_the_walk_outside_the_suite_tree_refuses_by_its_own_name`, which is the test that *closes* this case — not a declared gap of the file. |
| 16 | test_system_pool_release_empty.py | 47-52 | "A RUNTIME address ... Nothing static can see that." | GENERAL-LIMIT | n/a | Explicitly named as emulator-only work; no static or ROM-scan control applies. |
| 17 | test_system_pool_release_empty.py | 54-58 | "Opcode encodings outside `_PATTERNS` below ... A `movep`, an indexed absolute (`d8(An,Xn)`), or a byte store through a form not listed would pass unseen." | SPECIFIC-CONSTRUCTIBLE | CLEAR | Grepped all `.emp`/`.asm` for `movep` (7 hits, all in `dma_queue.emp`/`buffers.emp`/`sprites.emp` DMA-entry code, none touching `System_Slots`/`Effect_Slots`) and for any reference to those two symbols at all (only `lea`/`cmpa` sites in `core.emp`/`collision.emp`, every `lea System_Slots` gated `if DEBUG == 1`); ran the actual gate against the real `s4.bin`/`s4.lst` (md5 `ed512d731ebd`) — 12/12 pass, including the release-ROM scan. |
| 18 | test_system_pool_release_empty.py | 60-62 | "The DEMO game. Only sonic4 shapes are scanned ... if it ever gains some this file will not notice." | SPECIFIC-CONSTRUCTIBLE | CLEAR | `grep -rln "System_Slots\|Sst\b" games/demo/`: one hit (`demo_box.emp`, a bare `use engine.objects.sst.{Sst}` type import as a parameter type) — no reference to `System_Slots` at all. |
| 19 | test_system_pool_release_empty.py | 64-66 | "Whether skipping the sweep is CORRECT — only whether the pool is written." | GENERAL-LIMIT | n/a | A design-correctness question, explicitly out of scope by the file's own framing. |
| 20 | test_tier_tag_tables.py | 337-339 | "It cannot see `.rtag_names`' own absolute address ... so it proves RELATIVE parity only" | SPECIFIC-CONSTRUCTIBLE | CLEAR (today) | Read `s4.debug.lst`: `rtag_names=$BF36A`, `btag_names=$BF38E`, `.alphabet=$BF3A4` — all three currently even/word-aligned, so the untested absolute-parity premise happens to hold today. Future-facing limit remains real (not re-checked automatically). |
| 21 | test_timera_dma_guard_lint.py | 57-65 | "SndDrv_ISR's `call Snd_PollMailbox_Banked` ... deliberately left unguarded ... a live hole, not a hypothetical." | SPECIFIC-CONSTRUCTIBLE | **OCCUPIED — but disclosed and tracked** | Confirmed unguarded in source (its own census pins it as one of the 4 sites). Confirmed **currently open** in `docs/DEFERRED_WORK.md` as row `LS-12a` (2026-09-09 dispatch, still unresolved, candidate designs costed but none chosen). Not a hidden defect — the docstring's own wording already says so. |
| 22 | test_timera_dma_guard_lint.py | 66-69 | "ANY BANKED-ROM READ OUTSIDE THE TIMER-A TICK PATHS ... reachable only THROUGH these call sites today" | SPECIFIC-CONSTRUCTIBLE | CLEAR | Tree-wide grep for calls to `Run_SeqFrame_OnSongBank` (exactly 2: `z80_sound_driver.emp:374,1287`) and `Snd_PollMailbox_Banked` (exactly 2: `:619,1288`) — matches the lint's own census with no other call sites anywhere in the tree. |
| 23 | test_timera_dma_guard_lint.py | 70-72 | "THE 68k SIDE ... A raise without a lower would stall the sequencer and this lint cannot see it." | SPECIFIC-CONSTRUCTIBLE | CLEAR (count-level; not a control-flow proof) | Tree-wide grep for `SND_DMA_ACTIVE_SLOT`: 3 raises (`vblank.emp:130,346`; `section.emp:249`), 3 lowers (`vblank.emp:293,441`; `section.emp:486`) — balanced. Caveat: this is a raise/lower *count* check, not a dominance/control-flow proof that every raise is matched by ITS OWN lower on every path. |
| 24 | test_timera_dma_guard_lint.py | 73-76 | "THE HAZARD ITSELF, and its absence ... unobservable in this project's entire verification loop." | GENERAL-LIMIT | n/a | Explicitly named as a hardware-class fact no emulator in this project models. |
| 25 | test_timera_dma_guard_lint.py | 77-78 | "A DMA THAT BEGINS AFTER THE TEST. The guard narrows the window; it is not mutual exclusion." | GENERAL-LIMIT | n/a | A timing/race fact, not constructible statically. |
| 26 | test_vertical_bob.py | 9-12 | "Three things it structurally cannot see, and each one is a way to ship a background that sways wrongly with a perfectly green build" | FALSE POSITIVE | n/a | Names three gaps in the *expect-fail lane* (`tools/emp_expect_fail.py`), all three of which this file's own tests close (`test_SINE_AMPLITUDE_is_the_blob_s_actual_peak`, `test_the_low_nibble_is_the_period_and_the_high_nibble_the_amplitude`, `test_pcfg_bob_is_the_last_field_and_the_pad_is_gone` — all present and substantive, all in the passing 243). |
| 27 | test_vram_window_guards.py | 39-43 | "It cannot tell you a REGISTRY ROW is right: that the region a guard is pinned to is the region its DMA actually targets is a fact about the load site" | SPECIFIC-CONSTRUCTIBLE | **UNRUN** for the load-site claim proper; a weaker text-consistency proxy ran **CLEAR** | See "UNRUN" note below — full verification needs a register/data-flow trace per consumer, out of scope for a static-grep control at this budget. The 6 registry rows' claimed regions were cross-checked against the region NAMED in each guard's own `ensure` message and all 6 agree. |
| 28 | test_vram_window_guards.py | 43-45 | "It also says nothing about DMA queue-slot cost, run-time residency overlap between two regions with different lifetimes, or whether a region is correctly PLACED" | GENERAL-LIMIT | n/a | Explicitly delegated ("gen_vram_map.py's own coverage/overlap checks own that") — not this file's job by design. |
| 29 | test_vsplit_consumer_lint.py | 43 | '"put the ensure next to the scene" cannot see a consumer that lives somewhere else' | FALSE POSITIVE | n/a | Describes why the *comptime-ensure* approach fails (motivating this text lint's existence) — not a declared gap of this lint itself. No other genuine non-coverage statement found in this file. |
| 30 | test_z80_bus_hold_mask_census.py | 65-70 | "INTERPROCEDURAL ANYTHING ... a `jbsr` between a mechanism-2 mask and its bracket could lower the mask inside the callee and this file would not see it." | SPECIFIC-CONSTRUCTIBLE | **OCCUPIED (structural condition present); manually verified benign** | See "OCCUPIED findings" below — `engine/level/section.emp:485` is exactly this shape today. |
| 31 | test_z80_bus_hold_mask_census.py | 71-73 | "THE MASK'S VALUE beyond the shapes above ... $2700 is the tree's only spelling." | GENERAL-LIMIT | n/a | States a deliberate strictness rule, not an unclosed case. |
| 32 | test_z80_bus_hold_mask_census.py | 74-76 | "RUNTIME. Nothing here executes a ROM ... never that a particular IRQ6 was excluded." | GENERAL-LIMIT | n/a | Same class as items 10/24 — hardware timing, not statically constructible. |
| 33 | test_z80_bus_hold_mask_census.py | 76-79 / 80 | "SHAPE GATES ... a strength here and a mismatch to keep in mind" / "THE Z80 SIDE. Nothing about what the Z80 does while stopped." | GENERAL-LIMIT | n/a | Both are scope/comparison caveats about what population this file's ROM-vs-source mismatch means, and about the Z80 side being out of reach of a 68k-source lint — neither is a specific missed case to search for. |

---

## Full controls for the SPECIFIC-CONSTRUCTIBLE statements

### #1 — sfx_bank_wiring.py:98 (CLEAR)
```
$ python3 -m pytest -q -s tools/test_sfx_bank_wiring.py -k cell_count
.
1 passed, 6 deselected in 0.02s
```
Positive control: the assertion itself compares two independently-derived integers
(`len(cells)` from `sfx_blob_win_tab.emp`'s emitted body vs `hi - lo + 1` from
`sfx_bank.emp`'s key range) and is provably not vacuous — the file's own docstring
records it was "PROVEN RED" during authorship (mutation testing referenced in the
adjacent test file family). Reran clean: 137 cells, matches.

### #2 — sfx_transcode.py:1477 (CLEAR)
```
$ grep -n "_validate_sfx_repeat" tools/sfx_transcode.py
1502:def _validate_sfx_repeat(events, sfx_id=0):
1576:        _validate_sfx_repeat(ch['events'], sfx_desc.get('id', 0))
```
Line 1576 is inside `pack_sfx`'s per-channel loop, called unconditionally for every
channel of every SFX — not a helper that only the test calls directly. Positive
control: `test_repeat_end_zero_rejected` (same file) constructs exactly the
`RepeatEnd(0)` case and the function raises `"count 0"` — direct behavioral evidence
the check fires.

### #4 — sigil_probe_fixture.py:21-24 (CLEAR)
```
$ cd /home/volence/sonic_hacks/sigil && git log -1 --format="%H %ci"
30189ca0f27e6bd6f14429d83807987cac9f4884 2026-09-09 05:03:29 -0400
$ git merge-base --is-ancestor 43bf606a HEAD && echo ancestor
ancestor
$ grep -n "as_truth_equs\|as_label_at\|ObjCodeBase\|Draw_Sprite\|RefreshSpritePieceCount\|misspelled_objroutine_target_dangles_while_control_resolves\|reordered_falls_into_pair_fails_compile" crates/sigil-cli/tests/tranche6_negative_probes.rs
189:fn as_truth_equs() -> Vec<Section> {
221:               ObjCodeBase = $10000\n\
228:fn as_label_at(name: &str, vma: u32) -> Vec<Section> {
248:        as_truth_equs(),
249:        as_label_at("Draw_Sprite", 0x2970),
250:        as_label_at("RefreshSpritePieceCount", 0x2A00),
325:fn misspelled_objroutine_target_dangles_while_control_resolves() {
357:fn reordered_falls_into_pair_fails_compile() {
```
Positive control: this exact grep is the one that would fail to find a name if sigil
had renamed it (a rename would produce zero or different hits) — it found all five,
present-tense, at current HEAD, one ancestor generation past the cited revision.

### #7 / #12 — sound_bus_hold_mask_lint.py bracket-population claims (CLEAR)
```
$ python3 -m pytest -q -s tools/test_z80_bus_hold_mask_census.py -k population
`with z80_stopped` brackets across ('engine', 'games'): 22
  ... (6 in engine/sound/sound_api.emp, 16 across 7 other files, 1 RESET_SR — see full listing under finding #30) ...
2 passed, 4 deselected in 0.51s
```
The 22-total matches `sound_api.emp`'s own floor (6) plus the docstring's itemised
"SIXTEEN more ... across eight files" (vblank 6, section 3, bg 2, boot 1 [RESET_SR,
counted separately from the 22 code hits per LS-13a's own accounting], controllers 1,
parallax 1, sound_debug 1, ojz_scroll_test 1). No unaccounted bracket found.

### #8 — sound_bus_hold_mask_lint.py:59-65, boot pairing (CLEAR today / OPEN structurally — see OCCUPIED findings)
```
$ sed -n '128,156p' engine/system/boot.emp   # bus request at :130, release at :156
$ awk 'NR==130,NR==156' engine/system/boot.emp | grep -niE "\bj?b(ra|sr|cc|cs|eq|ne|gt|lt|ge|le|hi|ls|pl|mi|vs|vc)\b|\brts\b|\brte\b|\btrap\b"
6:        bne     .wait_z80
```
Only a self-loop found (`.wait_z80` polling itself). Positive control — same grep
against a span with real branches (`boot.emp:260-300`):
```
10:        jbsr    VDP_Shadow_Init
13:        jbsr    Init_DMA_Queue
...
37:        jbra    .region_done
```
proves the grep would have found an exit branch had one existed in the request/release
span.

### #13 — sprite_owner.py:43-46 (CLEAR)
```
$ grep -rn "Sprite_Owner" --include="*.emp" --include="*.asm" .
engine/ram.emp:1421:        Sprite_Owner: [u16; MAX_VDP_SPRITES], ...
engine/objects/sprites.emp:235:        lea     Sprite_Owner, a6
engine/objects/sprites.emp:750/879:  (the two other stamp sites)
engine/objects/rings.emp:259:        move.w  #1, (a6,d0.w)
(+ comment-only references in sprites.emp/rings.emp headers)
```
`a6 = &Sprite_Owner` is established exactly once (`sprites.emp:235`, inside
`Render_Sprites`) and consumed only within `sprites.emp` and `rings.emp` — no third
file references the symbol at all. Positive control: the same grep is what surfaced
the two *real* files this gate does scope to, proving it isn't silently matching
nothing.

### #17 — system_pool_release_empty.py:54-58 (CLEAR)
```
$ grep -rniE "\bmovep\b" --include="*.emp" --include="*.asm" .
(7 hits, all in engine/system/dma_queue.emp, engine/system/buffers.emp,
 engine/objects/sprites.emp — all DMAEntry field packing, none referencing
 System_Slots/Effect_Slots)
$ grep -rn "System_Slots\|Effect_Slots" --include="*.emp" --include="*.asm" .
(only lea/cmpa/comment hits in core.emp and collision.emp; every `lea System_Slots`
 site is inside `if DEBUG == 1 { ... }`)
```
And, against the real ROM (copied from the parent checkout, md5s confirmed matching
the dispatch brief):
```
$ python3 -m pytest -q tools/test_system_pool_release_empty.py
12 passed in 0.47s
```
including `test_release_rom_never_loads_a_system_slot_address` — the release ROM was
scanned instruction-by-instruction and contains exactly the one `cmpa.w` the file's
own docstring predicts, nothing else.

### #18 — system_pool_release_empty.py:60-62 (CLEAR)
```
$ grep -rln "System_Slots\|Sst\b" games/demo/
games/demo/objects/demo_box.emp
$ grep -n "System_Slots\|Sst\b" games/demo/objects/demo_box.emp
7:use engine.objects.sst.{Sst}
15:pub proc DemoBox_Main (a0: *Sst) clobbers(d0-d3/a1) preserves(a0) {
```
Only a type import used as a parameter annotation — no `System_Slots` reference, no
writer, matching the docstring's own factual claim exactly.

### #20 — tier_tag_tables.py:337-339 (CLEAR today)
```
$ grep -in "rtag_names\|btag_names\|\.alphabet" s4.debug.lst
2644:...$rtag_names:      -> BF36A
2645:...$btag_names:      -> BF38E
2647:...$alphabet:        -> BF3A4
```
All three absolute addresses are even. The declared gap (the lint can't see
`.rtag_names`'s absolute address, so it can't rule out THAT being odd even when the
relative span it measures is even) is not exercised today — but this is a
per-build fact, not a structural guarantee, so it is CLEAR now rather than closed
forever.

### #21 — timera_dma_guard_lint.py:57-65 (OCCUPIED, disclosed)
```
$ grep -n "LS-12a" docs/DEFERRED_WORK.md
29773:| LS-12a | `SndDrv_ISR`'s `Snd_PollMailbox_Banked` is the one banked-ROM path
a fail-closed guard cannot have, and LS-12 deliberately left it alone. ... BLOCKING
MEASUREMENT ... TAGGED for the controller ... |
```
Row is present, open, and dated as still-blocking as of this dispatch. Not a silent
hole — it is the single most heavily documented open item touching this file.

### #22 — timera_dma_guard_lint.py:66-69 (CLEAR)
```
$ grep -rn "Run_SeqFrame_OnSongBank" --include="*.emp" --include="*.asm" .
  (calls at z80_sound_driver.emp:374, :1287 — exactly 2)
$ grep -rn "Snd_PollMailbox_Banked" --include="*.emp" --include="*.asm" .
  (calls at z80_sound_driver.emp:619, :1288 — exactly 2)
```
Matches `EXPECTED_CALL_SITES` in the lint exactly, searched over the WHOLE tree
(not just the subject file) — positive control is that the same grep pattern is what
turned up all 4 real sites plus assorted comments naming them, so an added 5th site
would have shown up the same way.

### #23 — timera_dma_guard_lint.py:70-72 (CLEAR, count-level)
```
$ grep -rn "SND_DMA_ACTIVE_SLOT" --include="*.emp" --include="*.asm" .
engine/level/section.emp:249   move.b  #1, SND_DMA_ACTIVE_SLOT  // raise
engine/level/section.emp:486   move.b  #0, SND_DMA_ACTIVE_SLOT  // lower
engine/system/vblank.emp:130   move.b  #1, SND_DMA_ACTIVE_SLOT  // raise
engine/system/vblank.emp:293   move.b  #0, SND_DMA_ACTIVE_SLOT  // lower
engine/system/vblank.emp:346   move.b  #1, SND_DMA_ACTIVE_SLOT  // raise
engine/system/vblank.emp:441   move.b  #0, SND_DMA_ACTIVE_SLOT  // lower
```
3 raises, 3 lowers, tree-wide (`engine/` and `games/sonic4/` both searched). Caveat
stated in the table: this is a count, not a control-flow dominance proof.

### #27 — vram_window_guards.py:39-43 (UNRUN for the full claim; CLEAR for a weaker proxy)
The registry (`DPLC_GUARDS`, 6 rows) claims:
```
_dplc_sonic  -> character_window     _dplc_tail  -> tails_appendage
_dplc_tails  -> character_window     _dplc_insta -> insta_shield
_dplc_knux   -> character_window     _dplc_dust  -> dust_spindash
```
Grepping each blob's own `ensure(...)` message confirms all 6 name the SAME region in
prose as the registry claims (e.g. `collision_data.emp:106` names `character_window`
for `_dplc_sonic`; `tails_data.emp:159` names `tails_appendage` for `_dplc_tail`;
`player_instashield.emp:460` names `insta_shield`; `dust_data.emp:74` names
`dust_spindash`). This is a **text self-consistency** check, not a load-site trace —
it does not follow the DPLC pointer (`cd_dplc` in `sonic.emp`, `dplc_ptr` fields
elsewhere) through the runtime code that actually issues the VRAM DMA to confirm the
destination register is loaded from the SAME `*_TILES`/base pair named in the
`ensure`. That would need a register data-flow trace per consumer (which register
holds the destination base at the DMA call site, and where that value was loaded
from) — out of scope for a grep-based control at this budget. **Verdict: UNRUN** for
the load-site claim itself; the weaker consistency check is CLEAR.

### #30 — z80_bus_hold_mask_census.py:65-70 — OCCUPIED, see below.

---

## OCCUPIED findings

### Finding A — `test_timera_dma_guard_lint.py`: SndDrv_ISR's unguarded banked read (disclosed, tracked as LS-12a)

The docstring says outright: *"the first one is a live hole, not a hypothetical"* —
`SndDrv_ISR`'s `call Snd_PollMailbox_Banked` is deliberately left unguarded, one of
the lint's own 4 census sites (25%). This is **occupied** in the literal sense (the
case exists), but it is **not hidden**: `docs/DEFERRED_WORK.md` row `LS-12a` (still
open at time of audit) names it as a known, costed-but-unresolved design gap, with
candidate fixes listed and a blocking measurement (the flag's real duty cycle) that
needs emulator/foreground work tagged for the controller. **No action taken** — this
finding changes nothing about what to do next; it confirms the existing LS-12a
booking is accurate and current, not stale.

### Finding B — `test_z80_bus_hold_mask_census.py`: interprocedural mask gap is presently exercised at `engine/level/section.emp:485`

This is the closest match in the whole sift to the sigil precedent the audit exists
for: a docstring names a structural blind spot ("a `jbsr` between a mechanism-2 mask
and its bracket could lower the mask inside the callee and this file would not see
it"), and the file's OWN diagnostic (a `print`, not an `assert`) reports the count is
**1, not 0**, today:

```
$ python3 -m pytest -q -s tools/test_z80_bus_hold_mask_census.py -k every_bus_hold
mechanism-2 sites with a call between the mask and the bracket: 1 -> engine/level/section.emp:485 (1 call(s))
```

Traced by hand:
- `engine/level/section.emp:233` — `move.w #$2700, sr` (the mask, mechanism HAND_2700)
- `engine/level/section.emp:439` — `jbsr Section_GetSecPtrXY` (the intervening call)
- `engine/level/section.emp:485` — `with z80_stopped { move.b #0, SND_DMA_ACTIVE_SLOT }` (the bracket)
- `engine/level/section.emp:491` — `move.w (sp)+, sr` (the mask restore)

`Section_GetSecPtrXY` (`section.emp:143-178`) was read in full: it is a **leaf proc**
(no `jbsr`/`jsr`/`bsr` inside it) and contains **no instruction that writes `sr`** —
confirmed by grep (`sr\b` matches nothing in its body) and by reading every line. So
today this specific instance is **benign**: the mask genuinely holds across the call.

**Why this is still worth flagging loudly:** nothing in the gate, in sigil, or
anywhere else in the toolchain checks this. The only thing standing between "benign"
and "a live re-run of the LS-11 defect" is this one manual trace, done for this audit.
If `Section_GetSecPtrXY` is ever refactored to call something that touches `sr` (or
gains a call of its own to something that does), or if a *second* mechanism-2 site
ever grows a call in that span, nothing here or in sigil's `[bus.*]` net would notice
— the docstring is explicit that this is a documented, not a closed, limit. **No fix
applied** — this is exactly the "record the evidence and leave it" case the dispatch
asked for; the ruling on whether to close it is the owner's.

### Related, not new: LS-13b (boot's hand-spelled hold pairing) is open but not presently occupied

`test_sound_bus_hold_mask_lint.py`'s "PAIRING is still checked by nothing, here or in
sigil" bullet is the same underlying gap as `docs/DEFERRED_WORK.md` row `LS-13b`
(open, dated 2026-09-07/09). The control (full trace of `boot.emp`'s
request-to-release span, see finding #8 above) found **no early exit exists today** —
CLEAR at this moment, but the structural gap LS-13b describes is real and would
become occupied the instant anyone adds a branch out of that span. This is not a new
finding; it corroborates that LS-13b's own text ("An early exit added between the
request and the release would leave the Z80 halted with nothing to catch it") is an
accurate, currently-unexercised risk, not a stale claim.

---

## What this audit does not cover (running the same discipline on myself)

- **The 20 SPECIFIC-CONSTRUCTIBLE controls are static-source and static-ROM-scan
  controls.** None of them ran an emulator (per the dispatch's own prohibition) and
  none of them proves runtime behaviour — a CLEAR verdict here means "the named case
  is not present in the source/ROM today," never "the hazard the gate defends against
  cannot occur."
- **The count-based controls (#12, #23) are not control-flow proofs.** A
  raise-count-equals-lower-count or bracket-population-equals-census check cannot
  detect a raise on one path paired with a lower on an unrelated path, or a dead
  raise whose lower is unreachable. I flagged this caveat inline rather than silently
  upgrading a count match to a soundness proof.
- **#27's verdict is UNRUN, not CLEAR, and I want that distinction on the record**
  given the brief's own warning about rendering UNRUN as green: I ran a real but
  strictly weaker proxy (message-text agreement) and reported it as such, rather than
  spending the budget on a 6-consumer register data-flow trace. A future audit with
  more budget should either do that trace or explicitly accept the text-consistency
  proxy as sufficient.
- **The GENERAL-LIMIT classifications (13 of them) were not independently
  re-litigated** — I accepted the files' own reasoning that these are hardware-timing,
  cross-repo-build, or design-delegation facts no static control in this environment
  can resolve, rather than constructing a control for each and reporting UNRUN.
  Sub-editorializing risk: it's possible one of these 13 is actually more
  constructible than I judged (e.g. some "RUNTIME"-tagged item might have a
  ROM/listing proxy I didn't think to try) — I did not attempt to disconfirm every
  GENERAL-LIMIT tag.
- **The 5 FALSE POSITIVE calls are my own judgment reading**, not a mechanical test —
  I read the enclosing block for each (per the brief's own trap warning about grep
  hits that confirm the hypothesis) and concluded the quoted text describes a gap in
  something ELSE (a peer gate, an alternative approach, a different lane) that the
  file itself closes. A different reader could disagree on 1-2 of these at the
  margins (e.g. sfx_bank_wiring.py:98 and sigil_probe_fixture.py:206 are closer calls
  than the others); I erred toward classifying them as false positives only where I
  could point at the specific passing test that closes the named gap, which I did in
  every case.
- **I did not audit files outside the assigned 13**, including the other two lanes'
  (`parcel/blindspot-sift-a`, `parcel/blindspot-sift-b`) files, which target the same
  branch base (`26b1d106`) but had not diverged from it as of this dispatch — I did
  not read their in-progress work.
- **I did not re-derive the 38-file total** from `docs/DEFERRED_WORK.md`'s own grep;
  I trusted the dispatch's file list as lane C's slice and did not independently
  verify these 13 are a non-overlapping, complete partition of anything.
