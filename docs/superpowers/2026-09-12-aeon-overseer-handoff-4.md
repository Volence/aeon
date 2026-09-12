# Aeon overseer handoff, 2026-09-12 fourth session (booted 07:29Z after the owner's clear)

**Read this, then `docs/lane-status.json`, then `docs/DEFERRED_WORK.md`.** Supersedes "Next, in order" of
`docs/superpowers/2026-09-12-aeon-overseer-handoff-3.md`. Every SHA below is on aeon origin/master unless marked.
Stopped by the owner's clear rule at a landing boundary with its context MEASURED (see "Why it stopped").

## Landed this session (each re-verified on its merged tree in `.aeon-ls8-land`, then pushed)

| what | merge | land commit | evidence |
|---|---|---|---|
| Tools follow-ups: build.sh prints `md5(SIGIL_EMIT)`; an exported `NO_LINT` is honoured (0/1, else refused) and every lint skip prints banners at both ends; `ojz_strip_gen` `CHUNKS_TILES_PATH` -> `ZONE_TILESET_PATH`; `effects_gen check` DRIFT names anchor causes; `Raster_GetChannelBand`'s two stale cites repointed by name | `92cc601e` | `10fa1889` | landing_build finished=0, REAL_EXIT=0; four ROMs CRC-identical to master's (refuse-unless ACCEPT); effects_gates exit 0, 16/16 segments PASS, 17 gates complete |
| Clobber declarations: `Section_GetSecPtrXY` no longer declares d2 clobbered; `EntityWindow_TrySpawnRing` declares a0 preserved | `df001f99` | `f74b7b9c` | landing_build finished=0; four ROMs CRC-identical; 2459 passed per shape; needs_build 14/14 |

`10fa1889` also booked in DEFERRED: LS-1a step (1) in progress with the hub's five window conditions, and the finding
that **the nightly backstop checks out the main checkout's LOCAL master** (it tested `a38ce7c9`, 34 behind origin, on
2026-09-12T08:17Z; all green, but it graded none of that day's landings).

Master CRCs (unchanged by both landings, old assembler): s4 `eee9f4e2`/821155, s4.debug `f5660a6f`/847533,
demo `5e299109`/97109, demo.debug `1473caa9`/103501. Refuse-unless script: `.aeon-probes/chband-land/check.py`, base
`.aeon-probes/chband-land/base/` (valid until LS-1a moves bytes; after the swap it is STALE).

## Reviewed, ratified, NOT landed: parcel C (LS-2a (b) + (c)), branch `parcel/ls2a-census-widen`, tip `a4181293`
Worktree `aeon/.claude/worktrees/agent-ac62140ca70e0630e` (clean). Touches only `tools/test_z80_clobbers_census.py`,
`docs/DEFERRED_WORK.md`, `CODING_CONVENTIONS.md`, `docs/OVERSEER-REFERENCE.md`; no sound source, so sigil's
`z80_clobbers_incomplete` landing step is NOT triggered; not an effects-gate parcel. Agent's evidence: four ROMs
md5-identical, landing_build finished=0, census 10 passed, 2454 passed per shape, red-first over 126 cases with 0
mismatches, each exclusion rule switched off naming exactly its source-derived set. `git merge-tree --write-tree df001f99
a4181293` rc=0 (clean). **RULINGS (this session), put them in the merge message:** (1) RATIFIED the DISPATCH RE-ENTRY
class narrowed to dispatched code (validated from source every run via a `DISPATCH` row; off, it names exactly the 13
derived handlers); (2) RATIFIED the proposed forward edge, commits `e931501d` + `a4181293` (dispatcher charged every
`SeqOpcodeTable` cell): it closes the hole the exclusion opened, shown real before the change, zero hits. **Land it AFTER
the LS-1a swap** (held so nothing of ours used the shared binary while the window might open); its landing run then also
reproduces the preview CRCs below, a second witness for the swap.

## LS-1a: the assembler pin move, mid-window. NOTHING HAS BEEN SWAPPED.
- **Pin:** sigil `6884bfba64452322dc2e106feb67e3d22e535b1d` (named by sigil; verified here and by the hub: on sigil
  origin/master, with `13ca9425` digest, `78b084c3` ensure fix, `af35fa56` all ancestors). Sigil's master tip has moved
  past it with docs only; the pin stands.
- **New pair**, built `--locked` in durable clean worktree `/home/volence/sonic_hacks/.sigil-pin-6884bfba`, private target
  `.sigil-pin-6884bfba-target`: sigil `2e7c25920b95cec2c462ea51b4f078b5`, emit_sound_blob
  `d258341604bbf735a8af8438c2b8d642`. Installed today: sigil `49ecc532…`, emitter `36ef302c…`. **Keep
  `.sigil-pin-af35fa56` until the swap is done; keep `.sigil-pin-6884bfba` permanently** (each binary reads
  `golden/offcanonical_sizes/` from its build tree at run time).
- **Hub rulings (by message):** sigil performs the swap in its own tree, copy-in-then-rename (cargo hard-links the build
  outputs into `deps/`); one swap at `6884bfba`, not waiting on sigil's macro-diagnostics parcel. Conditions (1)-(5) are
  booked in DEFERRED at `10fa1889`, search `LS-1a step (1) IN PROGRESS`.
- **Preview DONE** (aeon `df001f99` under the private pair; master `f74b7b9c` differs from it by one docs line, checked):
  landing_build finished=0, REAL_EXIT=0, 0 failed lines; new CRCs **s4 `7a552cde`, s4.debug `b93a889f`, demo `dd589fe7`,
  demo.debug `c3eda757`**; DIGEST rows 347/354/227/232, each with one `DIGEST-END`; `DIGEST-ASSEMBLER ... revision=6884bfba…
  tree=clean`. Judge `.aeon-probes/ls1a-pin/compare_lst.py OLD NEW` (shown red first on planted defects in
  `judge-poison/`): every ROM symbol delta in {0,2,4,6,8,10,12,20,22}, EndOfRom unmoved, RAM unmoved -> IN SHAPE. Control
  listings (same commit, old binary) saved in `.aeon-probes/ls1a-pin/old-df001f99/`; preview artifacts in `preview-1/`.
- **ONE MISS, and OPEN is HELD on it:** the hub's condition (2) includes "the sonic4 pair -20 B"; here all four file sizes
  are UNCHANGED, and so is every deb2 appendix length (s4 43523, s4.debug 55467, demo 26939, demo.debug 33331) and every
  symbol count. Sigil has since corrected its own relay: the -20 B's LOCATION (past EndOfRom) holds, its CAUSE was an
  agent's unchecked inference; its working hypothesis (unverified) is that appendix layout depends on address blocks, so a
  slide changes size in one tree and not another. **Sigil is measuring and was asked to commit the answer in its tree.**
- **Next, in order:** (a) read sigil's answer; if it is "tree-specific, no size change expected here", ask the hub for
  OPEN (run a `/proc/*/exe` scan for `sigil/target/release/*` first and include it; the hub runs its own); (b) after sigil
  swaps, verify the installed md5s equal the two above; (c) DECIDER: in `.aeon-ls8-land` (`git checkout --detach
  origin/master` first) run `tools/landing_build.sh` under the INSTALLED pair; the four ROMs must be CRC-identical to the
  preview CRCs above, else sigil restores its set-aside pair; (d) tell the hub; (e) DEFERRED: LS-1a step (1) done; the
  chband base ROMs are now stale; (f) land parcel C; (g) LS-1a steps (2)-(3), the shared provenance primitive and moving
  the 14 `--built-after` consumers onto it.

## Found this session
- **The nightly backstop tests a stale master** (booked at `10fa1889`). Fixing the owner's working copy fixes it for
  now; the durable fix is in the booking.
- **Parcel B corrected its own booking:** `Parallax_CheckBoundary` was already guarded by sigil's D1c live-clobber check
  (a planted d2 write fails the build at the call site). It also found that sigil's D1c never names `a0` at the ring
  walkers' `addq` (a read-modify-write may not count as a read), booked for sigil in the C4a row.
- **Comment edits shift live `.emp:LINE` citations** (`tools/test_citation_form.py` caught one); B kept each edited block's
  line count. Worth saying in any brief that edits `.emp` comments.
- **An agent (C) ended its turn waiting on a background monitor** despite the brief; resumed by message, it finished.

## Cross-lane state
- **Sigil:** owes the -20 B explanation. Nothing else owed either way.
- **Hub:** holding OPEN for aeon; told at every stop.
- **Aurora:** nothing owed (no vendored file changed).

## For the owner (unchanged)
The main checkout is still at `a38ce7c9`, behind master, because of his uncommitted edit to
`games/sonic4/data/generated/ojz/act1/effects_scenes.emp` (two background layers moved from heights 112/160 to 303/318;
his editor source `ojz_act1_start.json` is modified too). Resolution: regenerate from his editor sources, never pick a
side; asked, no answer yet. Four cards remain on his console (VRAM-FOR-OBJECTS, CTRL-3, EFX-2, CHAR-10).

## Remaining queue after LS-1a and parcel C
Follow-ups from handoff-3 still open: `Draw_Sprite` long branches (check short reach first; likely a byte-mover, so after
LS-1a); the `map.toml` placement claim to re-derive; `ensure(TILE_CACHE_ROWS % 2 == 0)` (NO booking states why it is wanted;
find the reason or drop it; if added, ABOVE the file's last `section {}`). The C4a side findings (a) `Killed_MarkObject`
has no caller (emulator look first) and (d) the third flat-id product in `tile_cache.emp` (byte-mover). The emulator
rows batch (handoff-2's list). The queue-row audit: seven rows carry `blockedBy: "owner"` with no card under their own id.

## Housekeeping
- Removable, inspected at 08:45Z (clean, no cwd users, tip an ancestor of origin/master; each holds 17-18 gitignored files,
  build outputs, not inspected by name): `aeon/.claude/worktrees/agent-ad481838a8baa9f77` (A), `agent-a089b2f199f919a29`
  (B), `agent-a19193e2c65cf1a5d` and `agent-a65c5b5c29ba77363` (handoff-2's). Branches `parcel/tools-followups-0912` and
  `parcel/clobber-decls-0912` are merged.
- KEEP: `agent-ac62140ca70e0630e` (parcel C), `.aeon-ls1a-preview` (until the decider is done), `.aeon-ls8-land`
  (detached at `f74b7b9c`, clean), both `.sigil-pin-*` trees.

## Why it stopped
Owner rule (2026-09-11T23:19:31Z / 23:20:23Z). MEASURED from this session's transcript usage records
(input + cache_read + cache_creation): 70,985 at 07:29:32Z, 326,302 at 08:45:12Z, 236 records. The next steps (the swap,
the decider, parcel C's landing) are a new wave, so it stops at this boundary with nothing running and nothing swapped.
