# Two DEBUG safety nets: C2a-6 and B2a-2 (2026-09-12)

Worktree-agent record for two lens rows from the 2026-09-11 open sift, Bin B. The two fixes
went out on two branches; the controller merges and lands them. This note rides on
branch 1 only. It is a RECORD: its line numbers and addresses describe the trees named
here and are not re-pointed later.

Toolchain for every build below: `sigil` release binary md5 `49ecc532e0b133ab0eab9447e071805c`,
checked before the first build and before each later landing run. It never changed.

## Controls

Both branches are measured against the four ROMs of their own base, each built with
`tools/landing_build.sh` (both `finished=0`, `REAL_EXIT=0`):

| shape | `6763a402` (branch 1 base) | `35f54923` (branch 2 base) | size |
|---|---|---|---|
| `s4.bin` | `0b93e768b265dc5c218d24f3967b8bdd` | same | 821123 |
| `s4.debug.bin` | `49d28ff5e2806e71ace1a4786466bb66` | same | 847389 |
| `demo.bin` | `93e46e149bc8546e7ee3daa03f461311` | same | 97075 |
| `demo.debug.bin` | `754ca219d55e2c4cab2a026f181e51c8` | same | 103359 |

`origin/master` moved from `6763a402` to `35f54923` (10 commits, the lens-z3 landing and
LS-10a) while branch 1 was in flight. Those commits are zero-byte in all four shapes (the
md5s above are identical), and they touch neither `sprites.emp` nor `children.emp`. Branch 1
stayed on `6763a402`: `git merge-tree --write-tree origin/master parcel/c2a6-staleness-first`
is clean. Branch 2 was cut from `35f54923` because it edits `ring_sparkle.emp` and
`player_instashield.emp`, both of which that range changed.

---

## Branch 1: `parcel/c2a6-staleness-first` (ledger C2a-6)

- **Evidence tip:** `fd15f468eb5693bcba7fc7053a0cf106d62af1c0` (base `6763a402`). The branch tip
  is the next commit, which adds only this note. The tools pytest lane was re-run on the tree
  with the note (`-m "not needs_build"`, the three build env vars exported): `2436 passed,
  2 skipped`, 0 failed. A first attempt without `SIGIL_BUILD` exported gave 5 errors in
  `test_extern_guard_reachability.py`, which refuses to skip when the assembler is missing.
  That was my run, not the note.
- **Commits:** `c8b4200d` (the fix), `fd15f468` (citations the fix shifted), then this note
- **Files:** `engine/objects/sprites.emp`; `docs/ART_PIPELINE_CONTRACT.md`,
  `engine/objects/animate.emp`, `engine/objects/children.emp`, `engine/objects/mapping_dsl.emp`
  (comments only)

### What changed

`Render_Sprites`' H1 staleness net (live-resolve `mapping_frame` through the mapping table,
compare with the `frame_off` cache) sat after the total-piece overflow pre-check.
`sprite_piece_count` and `frame_off` are one cache, written together by `refresh_piece_count`,
so a writer that skips the refresh leaves both stale, and the pre-check filters on the stale
count. An object whose stale count tripped `bhi .next_object` was skipped before its own
check ran.

The net now runs at the first point its inputs exist: right after the null band-entry guard,
before the overflow pre-check. It loads its own mapping base and skips a slot zeroed
mid-frame (null `mappings`), because there is nothing to live-resolve against. a3, d0 and d1
are dead at that point. The old downstream copy is deleted. Nothing between the two points
writes any of its inputs, so a second copy could only re-check the same values.

Inputs checked at the new point: a0 is a non-null band entry (the guard above), `mappings`
is tested before it is dereferenced, and nothing earlier in the iteration culls the object
for a reason that would make the comparison meaningless. The loop-top `cmpi.w
#MAX_VDP_SPRITES, d5 / bge .band_limit_pop` still ends the band once the SAT is full. That
filter is not steered by the stale cache, so it is not this finding.

**Out of scope, as the brief set it:** the finding's other half, that `s4.bin` carries no
staleness net at all, is untouched.

### Byte picture (vs `6763a402`)

| shape | md5 | size | delta | EndOfRom |
|---|---|---|---|---|
| `s4.bin` | `0b93e768...` | 821123 | **identical** | `$BDDA0` unchanged |
| `s4.debug.bin` | `d8e1db7812f29800a603f464cac2ef8c` | 847411 | +22 | `$C1602` unchanged |
| `demo.bin` | `93e46e14...` | 97075 | **identical** | |
| `demo.debug.bin` | `80e8147e4fea09079693143199030aa1` | 103379 | +20 | `$1121A` unchanged |

From the listings (label lines, `lstcmp.py` in the agent scratch):

- Release: the `s4.lst` and `demo.lst` label maps are identical (0 moved, 0 added).
- DEBUG: `Render_Sprites` spans 754 B to 762 B (+8: the self-contained `move.l`/`beq`/`movea.l`
  load). One new label, `$engine.objects.sprites$Render_Sprites$stale_net_done`. The module's
  assert raise stub moves -18 because the assert now sits earlier. 1367 (s4.debug) and 1114
  (demo.debug) labels move downstream of the growth.
- EndOfRom does not move in any shape, so the +8 B of code is absorbed inside the placed
  image. The +22/+20 B of file growth is past EndOfRom, in the deb2 symbol appendix.

### Evidence

`tools/landing_build.sh` at `fd15f468`: **`finished=0`, `REAL_EXIT=0`**. Per shape the build.sh
pytest lane read `2436 passed, 2 skipped, 14 deselected` and every shape exited 0. The
needs_build lane: 14 cases, 14 ran, 0 deferred, 0 failed.

The first run, at `c8b4200d`, was **red** (`finished=1`, all four shapes):
`test_citation_form.py::test_live_citations_resolve_to_something`. Its message was
`docs/ART_PIPELINE_CONTRACT.md:252 cites engine/objects/sprites.emp:646 -- blank line`. The
fix is a net +24-line insertion at line 306, so every citation below it moved. The gate only
sees citations that land on nothing. I enumerated every LIVE `sprites.emp:N` citation (the
gate's own `is_record()` boundary) instead of fixing the one it named. Six were past line 305,
and all six are now file plus symbol (CODING_CONVENTIONS, "CITE BY NAME, NOT BY LINE").
Two of the six were already wrong on `6763a402`: `mapping_dsl.emp` cited `:468` (an
`if DEBUG == 1 {` in the sibling walk) for the size packing, and `children.emp` cited `:354`
(the `.screen_pos` block) for the chain-head read. The remaining LIVE citations (lines 72,
194, 225) sit above the insertion and did not move.

### No gate added

A static check that goes red when the order regresses would need to see the pre-check in the
listing, and the listing carries labels only. Adding a release-visible label there would
change the deb2 appendix, and so the release ROM. A source-text order check is the
heuristic-lint shape LS-2/LS-14 set a precedent against. So there is no gate, and the runtime
probe is a TAG.

### TAG-C2a-6 (runtime, controller; emulator only)

On `s4.debug.bin` from this branch, pick an on-screen object in a live band. Poison its
`sprite_piece_count` to `$FF`, so `d5 + $FF > MAX_VDP_SPRITES` trips the pre-check for any
`d5`, and poison `frame_off` to a value that is not `(mappings)[mapping_frame]`.
- **Expected on the branch:** the MD Debugger assert screen from `Render_Sprites` (`assert.w
  d1, eq, d0`).
- **Expected on `origin/master`:** no assert, the object silently skipped.
- **Controls, both trees:** poison only `sprite_piece_count` (a correct `frame_off`) and expect
  no assert, the object skipped. Zero `mappings` on a slot still in a band and expect no assert.

---

## Branch 2: `parcel/b2a2-chain-assert` (ledger B2a-2)

- **Tip:** `c1f2f1c7116fe68d41a4a6745da073ef6ffd1a4a` (base `35f54923`)
- **Files:** `engine/objects/children.emp`; `games/sonic4/objects/dust_puff.emp`,
  `dust_spindash.emp`, `ring_sparkle.emp`, `games/sonic4/player/player_instashield.emp`
  (comments only)

### The brief contradicted by the tree

The `children.emp` header recorded the partial rail as a DECISION: "ASSERT COVERAGE IS
DELIBERATELY PARTIAL" (t24 pass 2, `f638d478`, 2026-07-24). Its reason was that an assert on a
zero-caller proc cannot fire, while its blob spends debug bytes "past a threshold [that] push
engine symbols across $8000 and relocate the whole debug object bank". Its re-arm rule was
"when either creator gains a caller, it gains the assert in the same change". The lens row
(2026-09-06) and the sift row do not cite it. I did not override it on the brief's say-so. I
measured its premise first, at `35f54923`:

- **`@scaffolding` does not strip a proc.** Complex (126 B) and FlipAware (158 B) are emitted in
  all four shapes: s4 `$441E`/`$449C`, s4.debug `$5210`/`$528E`, demo `$2B9A`/`$2C18`, demo.debug
  `$3906`/`$3984`. Leaving the assert out saved only the assert, never the proc.
- **The `$8000` threshold is already crossed.** Engine code runs past `$8000` in both debug
  images (s4.debug `Parallax_Step5_Vscroll` `$8102` through `Sound_GetComm` `$B952`; demo.debug
  `Waterline_Art_Update` `$80AA`, `CompressionSelfTest` `$80AE`), and in plain s4 too
  (`Sound_GetComm` `$861A`). `SoundTablesZ80_Head` at `$8000` is the phase bank's VMA, not
  engine code.
- **The object bank is anchored.** `ObjCodeBase` is `$10000` in all four shapes
  (`OBJ_CODE_BANK = 1`). In s4.debug the last engine label below it is `$46AE` bytes short, an
  upper bound on headroom.
- **The file did not follow its own rule uniformly.** Linked has zero callers too, and it
  already carried the assert.

The premise does not hold today, so the fix went ahead. The header now states complete
coverage and why. **If the owner prefers the partial rail regardless, reverting `c1f2f1c7` is
the whole undo.**

### Call sites, by reference (not by name in prose)

Non-comment references across `engine/`, `games/`, `tools/`, every source type:

| proc | call sites |
|---|---|
| `CreateChild_Normal` | 1: `games/sonic4/objects/test_parent.emp` `jbsr CreateChild_Normal` |
| `CreateChild_Complex` | 0 |
| `CreateChild_FlipAware` | 0 |
| `CreateChild_Linked` | 0 (already asserted) |

### Byte picture (vs `35f54923`)

| shape | md5 | size | delta | EndOfRom |
|---|---|---|---|---|
| `s4.bin` | `0b93e768...` | 821123 | **identical** | `$BDDA0` unchanged |
| `s4.debug.bin` | `dab5cab95dfebc05f51e752bb646d1ea` | 847477 | +88 | `$C1602` unchanged |
| `demo.bin` | `93e46e14...` | 97075 | **identical** | `$1121A` unchanged |
| `demo.debug.bin` | `d1afc7c46cef1f3055b252b997ae784d` | 103447 | +88 | `$1121A` unchanged |

From the listings:

- Release: the `s4.lst` and `demo.lst` label maps are identical (0 moved, 0 added). The four
  creators keep their plain spans: Normal 102, Complex 126, FlipAware 158, Linked 138.
- DEBUG, both images: Complex spans 126 B to **214 B** and FlipAware 158 B to **246 B** (+88
  each, one assert site with its message blob, the same +88 that Normal and Linked already
  carried over their plain spans). Normal stays 190 B and Linked 226 B. So the module grows
  **+176 B** of DEBUG code. The assert diagnostics renumber: `$diag7`/`$diag11`/`$diag15` are
  new and `$diag13` is gone (Linked's site, renumbered). 1054 (s4.debug) and 801 (demo.debug)
  labels move downstream, by +88 or +176.
- EndOfRom does not move in any shape and `ObjCodeBase` stays at `$10000`, so the +176 B is
  absorbed inside the placed image. The +88 B of file growth is past EndOfRom, in the deb2
  symbol appendix.

### Evidence

`tools/landing_build.sh` at `c1f2f1c7`: **`finished=0`, `REAL_EXIT=0`**. All four shapes exited 0
(`EXIT_s4=0`, `EXIT_s4.debug=0`, `EXIT_demo=0`, `EXIT_demo.debug=0`). Every shape's build.sh
pytest lane read `2442 passed, 2 skipped, 14 deselected`, with 0 failed. The count is 6 over
branch 1's 2436 because the base carries lens-z3's new census test file. The needs_build lane:
14 cases, 14 ran, 0 deferred, 0 failed (`EXIT_needs_build=0`).

### Citations

The two insertions shift every `children.emp` line below them. The five LIVE `children.emp:N`
citations (`dust_puff.emp`, `ring_sparkle.emp` and `player_instashield.emp` for the silent
pool-full skip; `dust_spindash.emp` and `player_instashield.emp` for the no-`parent_ptr` note)
are rewritten by name, one line for one line. `test_citation_form.py`: 3 passed, and no LIVE
`children.emp:N` citation remains.

### No gate added

A needs_build listing check ("every `CreateChild_*` span contains an assert raise label")
would enumerate creators by NAME. It cannot see a differently-named future creator, which is
exactly the case the finding is about, and rule 8's red-first bar would be spent on a check of
that shape. So there is no gate.

### TAG-B2a-2 (runtime, controller; optional)

No live caller exists, so no shipped path can fire the two new asserts. A probe would call
`CreateChild_Complex` (and then `CreateChild_FlipAware`) from a debug harness with `a0` = an
SST whose `parent_ptr != 0`, and expect the MD Debugger assert. The control is
`parent_ptr == 0`: no assert, and children spawn and prepend as before.

---

## For the landing (both branches)

- **New cross-module names: none.** Each assert expansion references `MDDBG__ErrorHandler` and
  `MDDBG__ErrorHandler_PagesController`. `sprites.emp` and `children.emp` already reference
  both in their debug shape, and sigil's `sprites_port.rs` and `children_port.rs` already list
  both in their DEBUG seam tables.
- **Both are DEBUG byte-movers for sigil's instruments.** `pins::SPRITES` and `pins::CHILDREN`
  debug windows, and the debug pins of every region placed after them, move (1367 labels in
  s4.debug for branch 1 alone). This is the stale-instrument class: `repin_pins` says STALE
  and the paired refreeze clears it. `children_port.rs`' only hand-typed shape relation is
  `debug_len > plain_len`, which still holds. I did not run the sigil suite: the shared
  checkout is live for other lanes, and the freeze belongs to the landing.
- **One byte-mover per branch** (`OVERSEER-REFERENCE`): these are two, so freeze them serially.
