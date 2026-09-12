# Aeon overseer handoff, 2026-09-12 (session booted 2026-09-11T23:40Z after the owner's clear)

**Read this, then `docs/lane-status.json`, then `docs/DEFERRED_WORK.md`.** Every SHA below is on origin/master
unless marked. This session stopped by the owner's clear rule (clear past ~200k at the next safe point; the figure is
HIS since 2026-09-11T23:20:23Z). Its context was an ESTIMATE, not a measurement: see "Why it stopped".

## Landed this session (each verified on a merged tree in `.aeon-ls8-land`, then pushed)

| what | merge / commit | evidence |
|---|---|---|
| Owner cards CTRL-3 (covers V-8), EFX-2, CHAR-10 FILED | `11e69e95`, `81200e00`, `801340f9` | `decisions_append.py` from the main checkout, hub check ran |
| B1-6 DECIDED by the lane (`per_group`, owner can reopen) | `6763a402` | draft card 3 kept as the reopen path |
| OVERSEER.md: the 200k clear figure is the owner's | `7577daee` | hub correction, verified at empyrean `7f4ddbb` |
| lens-Z3: B2a-4, CTRL-1, B1-4, C3a-4 (zero bytes) | merge `ad707b83`, land `af5e097b` | landing_build finished=0; effects_gates 16/16; ROMs = C1a-1 tip cksums; sigil port check clean (sigil `39179705`) |
| SPRING-PAL-IDX9 shade closure (owner: lighter, idx 8) | in `af5e097b` | hub `34afb82` |
| LS-10a: release System pool empty at runtime | `35f54923` | `docs/superpowers/notes/2026-09-12-ls10a-runtime.md` |
| Spring coil idx 9 -> 8 (byte-mover) | merge `3fae7374`, land `0b1cd022` | landing_build finished=0; spring_line0_gate PASS; ROM CRCs = branch's |
| C3b-3 runtime TAG closed (60 vs 50 frames) | in `0b1cd022` | `docs/superpowers/notes/2026-09-12-c3b3-runtime.md` |
| CTRL-1 follow-up: 7 Seq_Op_* declare hl, census allow-list gone | merge `312d9ee1`, land `ee52a9ea` | landing_build finished=0, ROMs = master's (byte check proven able to fail first); sigil z80_clobbers_incomplete 5 passed (pin checkout af35fa56, private target, export of merged tree, shared md5 unchanged); OVERSEER-REFERENCE's "no Z80 census" sentence corrected |
| C2a-6: sprite-cache staleness net runs before the overflow pre-check (DEBUG) | merge `60e26266`, land `8c5e6d35` | landing_build finished=0; release ROMs = master; debug +22/+20 B as measured; byte check proven able to refuse first |
| B2a-2: parent-chain assert in all four chaining creators (DEBUG) + landing_build.sh env stamp (tools) | merges `a0a72ff6` + `6cd63b08`, land `88dfaba4` | landing_build finished=0; release = master; debug +88 B each (additive on C2a-6, confirmed); stamp branch zero-byte on its own |
| C1b-3: Collision_GetType adds the cache origin before halving (-12 c/lookup derived) | merge `1f7c44f6`, land `3d6f95d9` | landing_build finished=0; all four ROMs same size, content moved below `$10000`; 0 listed symbols at or above `$10000` moved; every tail difference (60 s4 / 82 s4.debug) a -4 reference; flipped-byte control refused |
| **NOT LANDED, ready**: EFX-4b + C3b-2 (raster pair); the four-branch entity-window stack | see "READY TO LAND" | reviewed and ruled this session; no agent on them |

## READY TO LAND, reviewed and ruled, NO agent on them: the next session lands these, in this order
Each is a committed branch in the shared repo; its agent's full record is a notes doc ON the branch. Land one byte-mover
per landing, from `.aeon-ls8-land`, exactly as below. Re-derive every expected byte picture from the master you merge
onto (these were measured against older bases).

1. **Raster pair, together: `parcel/efx4b-bounded-copy` (`8fbcf69d`, EFX-4b, byte-mover) + `parcel/c3b2-latch-disjoint`
   (`eee80c90`, C3b-2, zero bytes).** Both merge cleanly onto master-after-C1b-3 and with each other (merge-tree, 0
   conflicts). Needs `tools/effects_gates.py` on the merged s4.debug (raster.emp). Expected: demo ROMs byte-identical to the
   pre-merge master; both sonic4 ROMs change content at equal size (the padding). A staged checker existed this session
   (demo identical, s4 same size + changed; proven to refuse an unchanged tree); rebuild it from that sentence. Ledger:
   EFX-4b `fixed`, C3b-2 `refuted` (residue accepted). ⚠ Regenerates `effects_scenes.emp`: see the main-checkout section.
2. **Entity-window stack, IN ORDER (one linear chain cut at `6763a402`):**
   - `parcel/ew-ensure-msg-0912` `a6d99aa4`: DEFERRED side finding (a), zero bytes.
   - `parcel/c4a3-despawn-rollptr` `ccc9a2be`: C4a-3, byte-mover (content, same sizes). DespawnRings walks with `a2`.
   - `parcel/c4a4-flatid-reuse` `928cc052`: C4a-4, byte-mover (content, same sizes). GetSecPtrXY returns the flat id;
     FlatIDXY keeps three callers and gains a written bound argument.
   - `parcel/c4a2-findslot-hoist` `62ee1599`: C4a-2, byte-mover (+32/+34 B, all in the deb2 symbol table past EndOfRom;
     code -20 B). Lazy slot lookup cached in `a4` (`inout`); DELETES `Collected_CheckRing` and `Killed_CheckObject`.
   **⚠ Branch 4 BREAKS A SIGIL TEST**: sigil `crates/sigil-cli/tests/preserves_corpus.rs` names both deleted procs and
   panics on a missing proc (see "Cross-lane" below for what sigil was told). Aeon's own build is unaffected.
   Rulings: lazy over the seat's eager lookup (never worse than +8 c/walk) RATIFIED; `a4 inout` RATIFIED (a2 is not
   free on the object path; DrawRings precedent). Corrections the agent made to the ledger's own numbers: C4a-4's
   "24 + 14 sec_y" describes mul_bounded, FlatIDXY is 56 + 22 sec_y; C4a-3 derives 24-30 c/ring.
   Found-not-fixed, to BOOK in DEFERRED_WORK: Parallax_CheckBoundary reads `d2` after GetSecPtrXY declares it clobbered
   (works by accident); the ring walkers advance `a0` after TrySpawnRing declares it clobbered; **`Killed_MarkObject` has
   no caller, so the killed mask is never set** (check whether destroyed badniks respawn); tile_cache.emp computes the
   flat-id product a third time. Runtime TAGs: profile DespawnRings; section ids unchanged across a slide; same rings
   spawn and collected stay collected across a slide and a coarse-row crossing.

## Cross-lane: what sigil was told (2026-09-12T01:4xZ, SendMessage to the sigil lane; recorded here because a
## commitment that lives only in mail does not survive a clear)
That `parcel/c4a2-findslot-hoist` (NOT landed) deletes `Collected_CheckRing` and `Killed_CheckObject`, and that sigil
`crates/sigil-cli/tests/preserves_corpus.rs:138-139` (read at sigil origin/master `e88b4921`) list both and read the aeon
tree, so that test fails once the branch lands; `lower_proc.rs:595` and `preserves.rs:14/237` name them in comments only.
**Sigil answered and banked its own side** (their `c6651e45`, `docs/OVERSEER.md` "COMMITMENT TO AEON 2026-09-12",
queue row `PRESERVES-CORPUS-TWO-PROCS-LEAVING`; reachable from sigil origin/master, checked here): **do NOT hold the
landing and do NOT ping them when it lands.** Their landing gate reads a tree pinned at `ec640bcf` and stays green; only
their nightly source gates (which check out our master) go red the first night after, naming one of the two procs, and
that red is their trigger. Remedy pre-decided: drop the two rows, nothing else (they rejected the conditional form
because a renamed proc would then pass silently). They verified the panic-by-name in `residue_status` themselves.
Aeon's own build is unaffected either way.

## Held / in flight at the time of writing — re-check each, never trust this list

**Nothing.** No agent is running and no landing is half-applied: every dispatched agent returned, and every branch
this session did not land is listed under "READY TO LAND" with its rulings. `.aeon-ls8-land` is left detached at the
last landing's pushed tip (reuse it; `git checkout --detach origin/master` first).

## The owner's open cards (docs/decisions.jsonl; lane-status blockedOnOwner)
VRAM-FOR-OBJECTS (since 09-09), CTRL-3, EFX-2, CHAR-10 (filed 09-11). Nothing else is owed by him from this lane.

## Next, in order (the lens residue, then the section/effects cleanup, then regions per the owner's 09-11 order)
- Bin B still open after this session: C4a-2/3/4, C1b-3, C2a-6, B2a-2, EFX-4b, C3b-2 are the parcels in flight above;
  if any came back declined, its ledger row wants `decided` with the agent's reason. C1a-3 only when dplc.emp is open.
- Emulator rows still the controller's: C3a-3 (M), CHAR-4 and CHAR-6 (Knuckles glide head clearance: REPRODUCE
  first, find a low overhang in OJZ; the oracle driver cannot press C), BUG-005 (no suspect, stays open).
- LS-2a remainder: 13 Seq_Op_* handlers WITH a call write hl undeclared, plus Seq_Op_RegWrite's e (zero-byte expected,
  not measured). Sigil's z80 gate at landing (method below).
- LS-1a (provenance digest): our pin must move first, WITH NOTICE to every lane.
- Follow-ups booked: build.sh ignores an exported NO_LINT=1 (`build.sh:355`, fails safe); Draw_Sprite long branches;
  map.toml placement claim to re-derive; ojz_strip_gen naming; worktree hygiene (see below).

## How landings ran (reuse, do not rebuild)
One clean checkout `/home/volence/sonic_hacks/.aeon-ls8-land`, detached at origin/master. Per parcel: merge there;
assert content; `tools/landing_build.sh <log>` detached via a copied run-unique script with `REAL_EXIT` + sigil md5
before/after; a push script that REFUSES unless finished=0, zero lines matching `(^|[^0-9])[1-9][0-9]* failed`, the
parcel-specific gates green, and the four ROM CRC32s equal the expected picture (zero-byte: master's; byte-mover: the
branch's own). **Prove the byte check can fail before trusting it** (this session caught a no-op guard piped to
/dev/null that would have passed anything). Ledger/lane-log/DEFERRED lines go in the SAME push; the main tree is then
fast-forwarded with `git -C /home/volence/sonic_hacks/aeon merge --ff-only origin/master`.
- **Zero-byte expectation = master's CURRENT ROMs**, not a parcel's recorded base: this session nearly compared Z3
  against a pre-C1a-1 control (sizes matched, content did not). Walk the landings since the base.
- **"Nothing above `$10000` moved" is a claim about ADDRESSES, not bytes.** This session's first C1b-3 guard required
  `[$10000, EndOfRom)` to be byte-identical and REFUSED a sound landing: code above `$10000` that references a routine
  below it embeds that routine's address, and those moved by -4 (60 bytes in s4, 82 in s4.debug, every one classified
  as a -4 address/displacement; 0 of 357/397 high symbols moved). The corrected checker is in the landing notes of C1b-3;
  translate a peer's claim into the property it actually states before guarding on it.
- **Sigil z80_clobbers_incomplete** (any parcel touching its seven sound inputs): from `.sigil-pin-af35fa56` (ours, clean,
  5 tests), `CARGO_TARGET_DIR=/home/volence/sonic_hacks/.aeon-landing-sigil-target SIGIL_STRICT_GATE=1
  AEON_DIR=<git archive export of the merged tree> cargo test --release --locked -p sigil-cli --test z80_clobbers_incomplete -- --nocapture`;
  require `5 passed`, a `reference-tree:` line naming the export, no `skip:`, shared sigil md5 unchanged. Warm: 2 s.
- **Effects-gate files** need `tools/effects_gates.py --rom s4.debug.bin --lst s4.debug.lst` on the merged tree
  (~4 min, 16 segments). **Spring art** needs `tools/spring_line0_gate.py` (1 s).
- Cross-module `use`/name additions: ask sigil for a base-vs-tip strict port differential first (they did Z3).

## Rulings taken in this session on returned work (ratified deviations)
- **Spring (`parcel/spring-coil-idx8`)**: the agent deleted `knuckles_data.emp`'s slot-9-must-differ ensure. Ratified: it
  existed only to force the old index-9 caveat out, and audit A9 had flagged it as pinning the colour bug.
- **B2a-2 (`parcel/b2a2-chain-assert`)**: overrides `children.emp`'s recorded "ASSERT COVERAGE IS DELIBERATELY PARTIAL"
  (`f638d478`, 2026-07-24; reason: asserts on zero-caller procs would push debug past `$8000` and relocate the object
  bank). Ratified because the agent re-measured the premise: `@scaffolding` procs are emitted in all four shapes anyway,
  both debug images already cross `$8000` on master, and `ObjCodeBase` is fixed at `$10000` with ~18 KB of engine
  headroom in s4.debug. Reverting the branch's commit `c1f2f1c7` restores the partial rail if the owner wants it.
- **C1b-3 (`parcel/c1b3-origin-half`, tip `e7356fd0`)**: ships a THIRD fix, not the row's "store the halved origin":
  `Collision_GetType` computes `floor((L+O)/2)` instead of `floor(L/2)+O/2` (-12 c/lookup derived, 8 B -> ... 4 B
  smaller routine, no RAM). Equal iff the cache origin is EVEN; exhaustively checked on the ROMs' own bytes (29,640 even
  cases 0 disagreements; odd-origin control 14,400). **Ratified after checking the premise at every writer**: the two
  `TileCache_VSlide(Up)` call sites (`tile_cache.emp`) both pass `moveq #2`, the wrap is +/-`TILE_CACHE_ROWS` = 60, and the
  other writers store 0 (init `clr.w`, boot RAM clear). The old code relied on the same premise. **Unguarded at build time:**
  the only `TILE_CACHE_ROWS` ensure is a size bound; `ensure(TILE_CACHE_ROWS % 2 == 0)` would pin it (booked, not done).
  Byte-mover: all four ROMs change CONTENT, none changes size (a -4 B shift absorbed by the `$10000` pad). RT TAG: collision
  with a non-zero origin (after vertical scroll) wants an emulator look.
- **EFX-4b (`parcel/efx4b-bounded-copy`, tip `8fbcf69d`; the name says bounded-copy, the fix is PADDING)**: every
  static raster program zero-padded to `RASTER_BUF_SIZE` (128 B) like patched ones, via `static_program()`/`static_words()`
  in `raster_dsl.emp` plus a `sizeof` ensure on the two dense-tier structs; 14 staged programs measured, all 128 B with
  zero tails. ~980 B release / 1080 B DEBUG of padding, NO ROM size change (absorption not measured). Ratified: the
  alternatives were rightly rejected (a length word moves arm0 off word 1, which every decoder assumes; a terminator scan
  is unsafe because a raw ramp start can contain the terminator's words mid-record; walking ROM in place breaks the
  dense scene's assert). Will stale sigil's `section:ojz_effects` pins: sigil's drift finding after the fact, per CUT THE
  CEREMONY, not a gate. RT TAG: `Raster_Buf_A` zeros past the terminator once installed.
- **C3b-2 (`parcel/c3b2-latch-disjoint`, tip `eee80c90`)**: the whole-frame dropout is REFUTED (`check_intervals`, inside
  `raster_program`, refuses overlapping bands for every buildable program; the seat looked one layer too low), the
  residue NARROWED to a one-frame cosmetic boundary offset on lag frames only. Zero bytes. Adds `poison_patchable_overlap`
  (expect-fail lane 55/55, red-first by disabling the ensure). Ledger state `refuted`, residue accepted in a comment.
- **CTRL-1 follow-up**: `clobbers(..., hl)`, not `out(hl)`, following the honest siblings; sigil would accept `out(hl)`
  (measured), so that spelling stays open as a convention call.

## Runtime TAGs left for a controller session (emulator)
- **C2a-6**: in `s4.debug.bin`, set an on-screen object's piece count to `$FF` and its cached frame offset wrong: expect
  the debugger assert from `Render_Sprites` on master-after-landing, a silent skip before it. Controls: piece count alone
  does not assert; zeroed mappings do not assert.
- **B2a-2 (optional, no live caller)**: call Complex / FlipAware with a parent whose `parent_ptr` is non-zero: assert;
  zero: no assert.

## Emulator (controller only)
Oracle MCP serves THIS session's own instance (`bus.mode own-instance`); a different session's oracle-aether (pid
20998, started 09-10) also runs — leave it. Load ROMs from a STABLE copy, verify with `memory_hash` over the cart vs a
local zlib CRC32, load the build's own listing after every reload. Record-mode watchpoints survive `emulator_reset`;
arm them BEFORE a reset to catch the boot clears as a positive control. `play_input` rows drive reproducibly; a held
button alone left Sonic stuck against a post (a clean result from a run that exercised nothing).

## ⚠ The main checkout and the owner's uncommitted edits
The main tree (`/home/volence/sonic_hacks/aeon`) carries uncommitted edits the owner has not ruled on, among them
`games/sonic4/data/editor/effects/*.json` and `games/sonic4/data/generated/ojz/act1/effects_scenes.emp` (mtime
2026-09-10 09:25 local). **Every landing runs in the clean `.aeon-ls8-land` checkout, so none of them bakes those edits in.**
A landing that touches one of those paths (EFX-4b regenerates `effects_scenes.emp`) still pushes fine, but the main tree's
`merge --ff-only` then REFUSES (git will not overwrite a modified file) and the main tree stays behind master. **Do not
force it and do not commit his edits.** The generated file is regenerated from the editor sources, so the resolution is to
regenerate, never to pick a side; ask him first.

## Housekeeping left
- Locked worktree `aeon/.claude/worktrees/agent-a79ab935058db83d7` (probe builds; branch `probe/c3b3-race-fixed`
  `b70f5c81`, throwaway, measured and recorded): the harness locked it to this session's pid. After this session:
  `git worktree unlock <path> && git worktree remove <path> && git branch -D probe/c3b3-race-fixed
  worktree-agent-a79ab935058db83d7`. Probe ROMs in `/home/volence/sonic_hacks/.aeon-probes/c3b3/` (outside any repo).
- **Two agent worktrees still hold the UNLANDED branches checked out** and must NOT be swept until those land:
  `aeon/.claude/worktrees/agent-a19193e2c65cf1a5d` (raster pair) and `aeon/.claude/worktrees/agent-a65c5b5c29ba77363`
  (entity-window stack). The branches live in the shared repo, so landing from the refs does not need the worktrees.
- Worktree hygiene parcel still booked (the 09-11 count was 173 agent worktrees, 2 dirty).

## Why it stopped
Owner rule 2026-09-11T23:19:31Z / 23:20:23Z: past ~200k, reach a landing boundary without dispatching the next wave,
commit a handoff, `atBoundary: true`, `inFlight: []`, tell the hub. This session's context was estimated at roughly
230-260k at 00:14Z from what it had read (boot protocol ~1120 lines, the reference, the handoff, card drafts, many
tool outputs); the harness gives no reading, so treat that as an estimate.
