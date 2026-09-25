# aeon overseer handoff 25 (2026-09-25, session aeon-76, second boot of the day)

MID-WORK stop: the owner's usage ran out and he is switching accounts. FIVE agents were running and did NOT
survive the stop. Their worktrees are on disk under `.claude/worktrees/agent-*` and may hold UNCOMMITTED work.
For each one: `git -C <worktree> status --short` and `git log origin/master..<branch>`, then either finish it
(a fresh agent, pointed at that worktree and branch) or re-dispatch from the brief below. Nothing is half-merged:
master is clean and pushed.

## The owner's words this session (verbatim, heard directly or read at the hub's artifact)
- Flythrough (empyrean `aebf7f09` OVERSEER-LOG): *"s4 is now super laggy. We get to chemical plant but it's very
  short, we should add more sections to see more of the level please. Also the bgs should be from the games and such"*.
  He had `s4.s2clip.debug.bin` loaded (his screenshot).
- d-35-revised: *"I go with the recommendation"* = `clip-overlay-file`; then *"do what you recommend for the sound-data
  change"*, taken as: build aeon's half in parallel now.
- After the B-1 backgrounds: *"nice job with bgs but like the tunnel to tranisition has to be like an FG hiding the bg,
  right now it's just something we walk on. It doens't have to be so long either and the fg can use ehz or cpz art.
  Also it's still super duper laggy. finally there's not much in chemical plant yet still. Can we make the connector a
  little shorter, I think having it so long takes away a bit from the dramatic effect"*.
- Lag explained to him: streaming is the design, not the defect; its per-frame cost is the bug. He accepted it.

## Landed this session (origin/master)
- `7d409cdb` research: longer CPZ + original BGs costed. `58c2a671` research: the lag is game-side, from the first
  streaming act (14 pages vs 12 frames). Prefetch scan budget counts pages not cycles, so it is worst when everything
  ahead is resident; the patch lookups are 1.9-2.8x slower on the streaming path.
- `7c0baa73` S2CLIP-ORIGINAL-BGS B-1: static original backgrounds, S2 backdrop, and clip builds drop the OJZ bganim
  bank and the canonical DEBUG test BGs. Clip ROMs installed in the main checkout: `s4.s2clip.bin` 073b25f4,
  `s4.s2clip.debug.bin` 9e9e1979. Canonical unchanged (6d1af7a3 / 62238a15 / ce922bf7).
- Owner ruling d-35 banked in DEFERRED_WORK. Z80-TAP-ADDR-MOVE booked (hub §11.52; oracle coordinates the window).

## In flight at the stop (branch, tip at stop, what it was doing)
1. `parcel/pagecache-stream-lag` (8abf84e8, 4 commits): THE LAG FIX. Bounded/resumable prefetch scan plus direct-map patch
   lookups on the streaming path. The target is resident-act lag on the research doc's legs, with the EHZ start-of-act
   legs reported specifically. HIGHEST PRIORITY: he keeps hitting it.
2. `parcel/s2clip-tunnel-corridor` (no commits yet): the corridor becomes a short enclosed FG tunnel in EHZ/CPZ art that
   hides the BG, at the minimum width Z1 allows. Fix the 4 px step. `clips.json` changes redden aurora's currency test,
   so tell aurora.
3. `parcel/s2clip-bg-scroll` (no commits yet): B-2, S2 parallax. EHZ bands from s2disasm SwScrl_EHZ, ripple static;
   CPZ approximated. Data only; stop if engine code is needed.
4. `parcel/clip-anchor-overlay` (no commits yet): aeon half of d-35. Contract: sigil
   `62e01c49:docs/superpowers/notes/2026-09-25-clip-overlay-contract.md`, switch `--anchor-overlay` (NOT --map-overlay),
   ONE `games/sonic4/data/clips/<id>/anchors.toml` per clip with DEBUG binding (ruled with sigil). Pass it to BOTH sigil
   build and emit_sound_blob on S2CLIP builds only; a derive tool plus a staleness check. Sigil's branch
   `parcel/clip-overlay` is LOCAL in the sigil repo (c8db41b0 = early try); build it in your OWN detached worktree
   with its own target dir, never in `sigil/.worktrees/clip-overlay`, and never rebuild the shared sigil binary.
   The pair lands together on sigil's reviewed SHA. Then S2CLIP-CPZ-LONGER: extend CPZ to its 2nd checkpoint (x 6143).
5. `parcel/clip-bake-json` (f41ffe74, 5 commits): CLIP-BAKE-JSON for aurora. The agent was waiting on its
   landing_build `finished=` stamp. Review, land, and message aurora.

## Coordination state
- sigil: has the owner's d-35 answer (their fcaf2219). Told them aeon 7c0baa73 predictably reds their ojz_run_b_port
  (new name OJZ_CLIP_ACT in act_assets.emp); they booked it (2972558f). They confirmed s2_two_clip fixtures being
  refused by Z1 is by design.
- oracle: Z80 tap move. Filter YmTap on via=="z80"; the poison at $A00000 stays; they message before pushing.
- The hub knows about the flythrough triage and the d-35 ruling.

## Merge order advice
The lag fix is independent (engine). The tunnel, bg-scroll and overlay all touch the clip tools/data: land them one at a
time, re-run the clip builds after each, and reinstall `s4.s2clip*.bin` in the main checkout (the stale-artifact rule),
telling him the CRC. The converted donor trees are gitignored: in the main checkout, run
`python3 tools/s2_zone_convert.py convert s2disasm@CPZ` if the clip build refuses.
