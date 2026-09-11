# Aeon overseer handoff, 2026-09-11 (committed 2026-09-11T23:18:28Z)

**Read this, then `docs/lane-status.json`, then `docs/DEFERRED_WORK.md` (search "2026-09-11").** Written by the
overseer session that booted 18:17Z. Every SHA below is on origin/master unless marked.

## Where the owner's order stands (empyrean 68b9a2e, his words 2026-09-11T18:23:49Z)
(1) finish and push the LS-8 landing: DONE. (2) LENS-FIX-RESIDUE: in progress, see below. (3) the section/effects
cleanup, the last aeon thing before regions: NOT STARTED (its visual half is blocked on his pixel choices,
SECTION-EFFECTS-VISUAL). Regions starts only "when it's at a good spot". Seraph stays held ("besides seraph").

## Landed today (all on origin/master, each verified on a merged tree with tools/landing_build.sh)
LS-8 (f7406b97) · lens-contracts A2-1/A2-2/A2-5/C3b-4/C1a-2/B1-5 (1bc7d5b8) · F09 Sonic walk frame, owner "ship"
(d864dd48) · lens-pins B2b-5/C2a-5/B2b-4/B1-2 (3492ce3a) · C3b-3 page-in lost frame (f9785755) · S0-2 (bb0924d3)
· C1a-1 + CTRL-7 sprite speedup (7c719ef5) · lens-tools V-5/C5-7/C2b-4 (6d4b5656) · lens-comments B2b-6/B2a-3/CTRL-10 + bg.emp plane pins (f0e9726a; strikes and the gate's measured cold compile 44f4f105)
Owner answers banked: block-dedup note -> regions docs (826159e7); SPRING-PAL-IDX9 = drop-grey (8c2c955e), SHADE
NOT YET PICKED (hub is asking him lighter idx 8 / darker idx 1; the gen_spring.py one-liner waits for it).

## The lens ledger after today
Count it, never copy this line: line-addressed, latest-line-wins over `docs/lens-findings.jsonl`.
Bin B rows still open after today (from docs/superpowers/notes/2026-09-11-lens-open-sift.md, minus what landed):
- byte-movers, ONE PER BRANCH, landed one at a time: C4a-3 (S), C1b-3 (S), C4a-4 (S, or its zero-byte bound
  argument), C2a-6 (DEBUG), B2a-2 (DEBUG), EFX-4b (S, effects-gate file), C4a-2 (M), C1a-3 (only when dplc.emp is
  open for another reason).
- zero-byte: C3b-2 (M, effects-gate file; first establish what check_intervals already covers).
- runtime / emulator, the controller's own (no emulator in subagents): C3a-3 (M), CHAR-4, CHAR-6, BUG-005, and the
  two booked TAGs: C3b-3's forced-race probe and LS-10a.
- CTRL-9: another sweep over the never-swept surfaces (L).
Bin C (owner): CTRL-3, V-8, EFX-2, B1-6, CHAR-10. Not yet filed as cards; file each as its own decisions.jsonl card
through tools/decisions_append.py when it is next up, never in a batch.

## Follow-ups booked today (DEFERRED_WORK, search each)
- CTRL-1 follow-up: correct the seven Seq_Op_* `clobbers()` attributes (zero-byte per LS-2) and shrink the census
  allow-list; it was blocked only by a parcel's stay-out list.
- entity_window.emp ensure message about MAX_LIST_ENTRIES is now wrong (a test compares it).
- landing_build.sh exits 1 with no finished= stamp when SIGIL_BUILD/SIGIL_EMIT is unset.
- ojz_strip_gen.py's misnamed tileset (CHUNKS_TILES_PATH), naming only.
- Draw_Sprite's two long-form entry branches (~4 cycles per call).
- map.toml's "frozen tables place sections" claim: re-derive (sigil's probe moved no byte).
- LS-1a: sigil's digest LANDED (13ca9425); ours needs the pin (.sigil-pin-af35fa56) moved first, WITH NOTICE to
  every lane, then one shared primitive, then 14 consumers migrated.
- Worktree hygiene: 173 agent worktrees, 2 dirty (preset-sec5-split 14 files, vertical-bob 40). A parcel of its own.
- Sound-driver ideas for after regions: DEFERRED_WORK ideas section (empyrean 2341c6f).

## How landings ran today (reuse, do not rebuild)
One clean checkout, `/home/volence/sonic_hacks/.aeon-ls8-land`, detached at origin/master; merge there, run
`tools/landing_build.sh` detached with a REAL_EXIT stamp, poll the log, then a landing script that REFUSES unless the
run is green (nonzero-failure matcher only: `(^|[^0-9])[1-9][0-9]* failed`), the byte picture matches the parcel's
measured one, and the notes carry exactly the expected ledger ids; ledger lines go in the SAME push. Effects-gate
files (engine/effects/*, bg_anim.emp, buffers.emp) need tools/effects_gates.py on the merged s4.debug. A parcel
touching sigil's z80_clobbers_incomplete inputs needs that gate, per docs/OVERSEER-REFERENCE.md, run against a
`git archive` EXPORT of the merged tree (their tests write into AEON_DIR). The shared sigil binary md5 was 49ecc532
all day; check it before trusting any landing.

## Traps hit today, so they are not hit again
- A failure matcher `[0-9]+ failed` matches "0 failed" in the final lane's success line.
- `git show "$B:path"` needs braces in zsh: `"${B}:path"`.
- A chain that cd's into the landing checkout runs its later `git merge --ff-only` THERE; fast-forward the main tree
  with `git -C /home/volence/sonic_hacks/aeon`.
- Agents that wait on a Monitor/background notification stall (one sat idle 50 minutes); brief them to poll the log.
- grep reads empyrean's docs/OVERSEER-LOG.md as binary; use `grep -a`.
- Adding a cross-module name can red sigil's *_port tests while all four aeon shapes build green: ask sigil for a
  base-vs-tip strict differential before landing such a parcel (they did it for Z3).

## HELD / NEXT AT THE TIME OF WRITING (2026-09-11T23:18:28Z); re-check each, never trust this list
- **Z3, `parcel/lens-z3-0911`, tip `79e78980`** (B2a-4, CTRL-1, B1-4, C3a-4; zero bytes; agent worktree
  `.claude/worktrees/agent-a6f8379ae7e779611`, untouched). HELD for sigil's base-vs-tip strict differential, because it
  adds cross-module names in animate.emp and dplc.emp. Sigil's first attempt died at the 21:45Z usage stop and was
  resumed 23:14Z; it provisions ROM-built trees, confirms animate_port / dplc_port / raster_port get past the reference
  read, and plants a canary. When sigil sends a clean canary-backed result: `zmerge.sh`-style merge in the landing
  checkout, landing_build, effects gates (raster.emp touched), then land with ledger rows B2a-4, CTRL-1, B1-4, C3a-4.
  If it reds, send the names back to a fresh agent; do not land.
- **Owner cards: DRAFTED, NOT FILED (2026-09-11T23:28:03Z).** Four cards for five lens rows are in
  `docs/superpowers/notes/2026-09-11-lens-owner-cards-draft.md` (merged to master; see that file's top for the rulings).
  CTRL-3 and V-8 are ONE card (id CTRL-3: ritual / gate / hosted, recommends `gate`); EFX-2 recommends `show`; B1-6
  recommends `per_group` (arguably a lane call, not his); CHAR-10 is AEON's card (oracle has none; the format and recorder
  are aeon's, oracle owns only the headless player), recommends `both`. All four passed `decisions_append.py --check-only`.
  **To file:** review each card first (costs he can picture, a real recommendation, no identifiers in question/options/
  recommend), then file from the MAIN checkout, not a worktree (in a worktree the tool's automatic hub check prints
  COULD NOT CHECK), one at a time, adding each to `lane-status.json` `blockedOnOwner` with its id. Corrections the draft
  found in the sift: nine preset sites, not ten; LS-2/LS-14 are narrower precedents than the sift said.
- Landing scripts used today lived in the session scratchpad and do not survive it; the method above is enough to
  rebuild them. The landing checkout is `.aeon-ls8-land` (kept; reuse it).
